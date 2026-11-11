"""Database clients refuse every authentication method other than SCRAM-SHA-256 on loopback.

The server below is not PostgreSQL: it answers the startup message with a password request and records
what the client sends afterwards. No real database is needed.
"""

import socket
import struct
import subprocess
import threading
from types import SimpleNamespace

import psycopg
import pytest

from membrain import embedded_database, storage

PASSWORD = "loopback-secret-7f3c9a"
CLEARTEXT = struct.pack("!cii", b"R", 8, 3)
MD5 = struct.pack("!cii", b"R", 12, 5) + b"salt"
_NEGOTIATION = {80877103, 80877104}  # SSLRequest, GSSENCRequest


class PasswordRequestServer:
    def __init__(self, request: bytes):
        self.request = request
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.connections = 0
        self.received = bytearray()
        self.handled = threading.Semaphore(0)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self.stopped.is_set():
            try:
                client, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            self.connections += 1
            with client:
                client.settimeout(5)
                try:
                    self._answer(client)
                except OSError:
                    pass
            self.handled.release()

    def _read(self, client, size):
        data = bytearray()
        while len(data) < size:
            chunk = client.recv(size - len(data))
            if not chunk:
                raise ConnectionError
            data += chunk
        return bytes(data)

    def _answer(self, client):
        while True:
            length = struct.unpack("!i", self._read(client, 4))[0]
            body = self._read(client, length - 4)
            if struct.unpack("!i", body[:4])[0] not in _NEGOTIATION:
                break
            client.sendall(b"N")
        client.sendall(self.request)
        # A client that refuses the method closes the connection; one that accepts sends its answer.
        self.received += client.recv(4096)

    def wait(self, count=1):
        for _ in range(count):
            assert self.handled.acquire(timeout=10), "the client never completed a startup exchange"

    def close(self):
        self.stopped.set()
        self.thread.join(5)
        self.listener.close()


@pytest.fixture(params=[CLEARTEXT, MD5], ids=["cleartext", "md5"])
def server(request):
    instance = PasswordRequestServer(request.param)
    yield instance
    instance.close()


def _assert_password_withheld(server, connections=1):
    server.wait(connections)
    assert server.connections == connections
    assert PASSWORD.encode() not in server.received
    assert not server.received.startswith(b"p")


def test_control_unconstrained_client_answers_the_request():
    server = PasswordRequestServer(CLEARTEXT)
    try:
        with pytest.raises(psycopg.OperationalError):
            psycopg.connect(host="127.0.0.1", port=server.port, user="postgres", password=PASSWORD,
                            dbname="postgres", sslmode="disable", connect_timeout=5).close()
        server.wait()
    finally:
        server.close()
    assert PASSWORD.encode() in server.received


def test_embedded_admin_connection_withholds_password(server):
    profile = SimpleNamespace(database_port=server.port, admin_password=PASSWORD)
    with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
        embedded_database._admin_connection(profile, "postgres")
    _assert_password_withheld(server)


def test_configured_loopback_url_without_require_auth_withholds_password(server):
    url = f"postgresql://postgres:{PASSWORD}@127.0.0.1:{server.port}/agent_memory?connect_timeout=5"
    with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
        storage.Database(url).check_compatibility()
    _assert_password_withheld(server)


def test_pooled_connections_withhold_password(server):
    database = storage.Database(f"postgresql://memory_app:{PASSWORD}@127.0.0.1:{server.port}/agent_memory",
                                pool=True)
    try:
        pool = database.pool
        with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
            pool.connection_class.connect(pool.conninfo, **pool.kwargs)
    finally:
        database.close()
    _assert_password_withheld(server)


def test_profile_urls_withhold_password(server):
    from membrain.local_profile import DesktopProfile

    fields = {name: None for name in DesktopProfile.__dataclass_fields__}
    profile = DesktopProfile(**fields | {"database_port": server.port, "admin_password": PASSWORD,
                                         "app_password": PASSWORD})
    for url in (profile.database_url, profile.migration_database_url):
        assert "require_auth=scram-sha-256" in url
        with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
            storage.connect(url).close()
    _assert_password_withheld(server, 2)


def test_backup_tools_require_scram(tmp_path, monkeypatch):
    profile = SimpleNamespace(database_port=54329, admin_password=PASSWORD)
    layout = embedded_database._Layout(tmp_path / "bin", tmp_path / "data", tmp_path / "log", None)
    monkeypatch.setattr(embedded_database, "_layout", lambda _: layout)
    _, environment = embedded_database.client_command(profile, "pg_dump", "--dbname=agent_memory")
    assert environment["PGREQUIREAUTH"] == "scram-sha-256"


def test_bundled_pg_dump_withholds_password(server, tmp_path, monkeypatch):
    installation = embedded_database._legacy_installation()
    if installation is None:
        pytest.skip("no PostgreSQL client tools are installed")
    profile = SimpleNamespace(database_port=server.port, admin_password=PASSWORD)
    layout = embedded_database._Layout(installation / "bin", tmp_path / "data", tmp_path / "log", None)
    monkeypatch.setattr(embedded_database, "_layout", lambda _: layout)
    command, environment = embedded_database.client_command(
        profile, "pg_dump", "--username=postgres", "--dbname=agent_memory", "--schema-only")
    result = subprocess.run(command, env=environment | {"PGSSLMODE": "disable"}, capture_output=True,
                            timeout=30, check=False)
    assert result.returncode != 0
    assert b"scram-sha-256" in result.stderr
    _assert_password_withheld(server)


def test_old_client_library_fails_before_connecting(monkeypatch):
    instance = PasswordRequestServer(CLEARTEXT)
    try:
        monkeypatch.setattr(storage.psycopg.pq, "version", lambda: 150007)
        url = f"postgresql://postgres:{PASSWORD}@127.0.0.1:{instance.port}/agent_memory"
        with pytest.raises(storage.DatabaseClientError, match="libpq 15.7"):
            storage.connect(url)
        with pytest.raises(storage.DatabaseClientError):
            storage.connect(url + "?require_auth=scram-sha-256")
    finally:
        instance.close()
    assert instance.connections == 0


def test_rule_for_configured_urls(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("PGHOSTADDR", raising=False)

    def options(conninfo, **params):
        return psycopg.conninfo.conninfo_to_dict(storage.connection_info(conninfo, **params))

    for url in ("postgresql://u:p@127.0.0.1:5432/db", "postgresql://u:p@localhost/db",
                "postgresql://u:p@[::1]:5432/db", "host=db.example,127.0.0.1 user=u",
                "host=db.example hostaddr=127.0.0.1 user=u"):
        assert options(url)["require_auth"] == "scram-sha-256", url
    for url in ("postgresql://u:p@db.example:5432/db", "host=db.example hostaddr=192.0.2.10 user=u",
                "host=/var/run/postgresql user=u"):
        assert "require_auth" not in options(url), url
    assert options("postgresql://u:p@127.0.0.1/db?require_auth=password")["require_auth"] == "password"
    assert options("postgresql://u@127.0.0.1/db?connect_timeout=5", connect_timeout="2")["connect_timeout"] == "2"
    monkeypatch.setenv("PGHOST", "127.0.0.1")
    assert options("dbname=db")["require_auth"] == "scram-sha-256"
