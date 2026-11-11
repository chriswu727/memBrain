"""Embedded PostgreSQL for desktop and plugin installations without Docker.

Only verified PostgreSQL and pgvector binaries are used. The cluster
listens on 127.0.0.1 with password authentication, so connection strings, migrations, roles and
row-level security match the Docker engine exactly.
"""
from __future__ import annotations

import importlib.util
import os
import secrets
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from .native_bundle import environment as native_environment

ENGINES = ("docker", "embedded")
SERVICE_ACCOUNT = "membrain-db"
SHARED_ROOT = Path("/var/lib/membrain")
# Root clusters created before the memBrain rename stay where they are, under their original account.
LEGACY_SERVICE_ACCOUNT = "agent-memory-db"
LEGACY_SHARED_ROOT = Path("/var/lib/agent-memory")
_EXECUTABLE = ".exe" if os.name == "nt" else ""


class EmbeddedDatabaseError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _legacy_installation() -> Path | None:
    try:
        spec = importlib.util.find_spec("pgserver")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    root = Path(next(iter(spec.submodule_search_locations))) / "pginstall"
    required = ("initdb", "pg_ctl", "postgres", "pg_dump", "pg_restore")
    if not all((root / "bin" / (name + _EXECUTABLE)).is_file() for name in required):
        return None
    return root


def _installation() -> Path | None:
    from .native_bundle import prepare

    return prepare()


def available() -> bool:
    from .native_bundle import available as supplier_available

    return supplier_available()


def default_engine() -> str:
    return "embedded" if available() else "docker"


def _running_as_root() -> bool:
    return os.name != "nt" and os.geteuid() == 0


@dataclass(frozen=True)
class _Layout:
    binaries: Path
    data: Path
    log: Path
    account: tuple[int, int] | None


def _nologin() -> str:
    return next((path for path in ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false") if Path(path).exists()),
                "/bin/false")


def _service_account(name: str = SERVICE_ACCOUNT) -> tuple[int, int]:
    import pwd

    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        commands = (
            ["useradd", "--system", "--no-create-home", "--home-dir", "/nonexistent",
             "--shell", _nologin(), name],
            ["adduser", "-S", "-D", "-H", "-h", "/nonexistent", "-s", _nologin(), name],
        )
        for command in commands:
            if shutil.which(command[0]):
                subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=30, check=False)
                break
        try:
            entry = pwd.getpwnam(name)
        except KeyError:
            raise EmbeddedDatabaseError(
                "embedded_database_account_unavailable",
                f"PostgreSQL cannot run as root and the '{name}' system account could not be "
                "created. Run as a regular user or choose the Docker database engine.",
            ) from None
    return entry.pw_uid, entry.pw_gid


def _shared_binaries(source: Path, shared_root: Path = SHARED_ROOT) -> Path:
    from .native_engine_store import NativeEngineStoreError, preserve

    try:
        return preserve(source, shared_root, shared=True).directory
    except NativeEngineStoreError as error:
        raise EmbeddedDatabaseError(error.code, str(error)) from None


def _traversable(directory: Path) -> bool:
    """Whether every directory down to ``directory`` lets other accounts pass through it."""
    try:
        path = Path(directory).resolve()
        return all(os.stat(part).st_mode & 0o001 for part in (path, *path.parents))
    except OSError:
        return False


def _layout(profile) -> _Layout:
    from .native_adoption import recorded_layout

    recorded = recorded_layout(profile)
    if recorded is not None:
        return recorded
    source = _installation()
    if source is None:
        raise EmbeddedDatabaseError(
            "embedded_database_unavailable",
            "The embedded database is not installed for this platform. Install the 'embedded' extra "
            "or choose the Docker database engine.",
        )
    return _layout_from_source(profile, source)


def _layout_from_source(profile, source) -> _Layout:
    if not _running_as_root():
        return _Layout(source / "bin", profile.directory / "postgres", profile.directory / "postgres.log", None)
    legacy = (LEGACY_SHARED_ROOT / "clusters" / profile.installation_id / "data" / "PG_VERSION").is_file()
    shared_root = LEGACY_SHARED_ROOT if legacy else SHARED_ROOT
    account = _service_account(LEGACY_SERVICE_ACCOUNT if legacy else SERVICE_ACCOUNT)
    cluster = shared_root / "clusters" / profile.installation_id
    shared_root.mkdir(mode=0o755, parents=True, exist_ok=True)
    (shared_root / "clusters").mkdir(mode=0o755, exist_ok=True)
    if not legacy and not (cluster / "data" / "PG_VERSION").is_file() and _traversable(profile.directory):
        # Keep the data with the installation (a container's data volume, for example) when the service account
        # can reach it; only the binaries need the shared root.
        cluster = profile.directory / "postgres-cluster"
    cluster.mkdir(mode=0o700, exist_ok=True)
    os.chown(cluster, *account)
    binaries = _shared_binaries(source, shared_root) / "pgserver" / "pginstall" / "bin"
    return _Layout(binaries, cluster / "data", cluster / "postgres.log", account)


def _run(layout: _Layout, program: str, *arguments: str, timeout: float = 120,
         capture: bool = False) -> subprocess.CompletedProcess:
    command = [str(layout.binaries / (program + _EXECUTABLE)), *arguments]
    options = {}
    if layout.account is not None:
        options.update(user=layout.account[0], group=layout.account[1], extra_groups=[],
                       cwd=str(layout.data.parent))
    environment = native_environment(layout.binaries.parent, shared=layout.account is not None)
    # pg_ctl leaves the postmaster attached to inherited pipes, so only short-lived tools are captured.
    output = subprocess.PIPE if capture else subprocess.DEVNULL
    return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT if capture
                          else subprocess.DEVNULL, env=environment, timeout=timeout, check=False, **options)


def _log_tail(layout: _Layout, limit: int = 1200) -> str:
    try:
        with open(layout.log, "rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - limit))
            return stream.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


def _failure(code: str, summary: str, layout: _Layout) -> EmbeddedDatabaseError:
    tail = _log_tail(layout)
    detail = f" Last database log lines:\n{tail}" if tail else f" See {layout.log}."
    return EmbeddedDatabaseError(code, summary + detail)


def _configuration(profile, buffers: int = 128) -> str:
    return ("\n# memBrain embedded engine\n"
            "listen_addresses = '127.0.0.1'\n"
            f"port = {profile.database_port}\n"
            "unix_socket_directories = ''\n"
            "max_connections = 50\n"
            f"shared_buffers = {buffers}MB\n")


def _update_managed_defaults(profile, layout: _Layout) -> None:
    path = layout.data / "postgresql.conf"
    if path.is_symlink():
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > 1024 * 1024:
            return
        original = stream.read()
    replacements = []
    for newline in (b"\n", b"\r\n"):
        old = _configuration(profile, 32).encode().replace(b"\n", newline)
        if original.count(old) == 1:
            replacements.append((old, _configuration(profile).encode().replace(b"\n", newline)))
    if len(replacements) != 1:
        return
    old, new = replacements[0]
    temporary = path.parent / (".configuration-" + secrets.token_hex(8))
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(original.replace(old, new, 1))
            if os.name != "nt":
                os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
                if _running_as_root() or os.fstat(stream.fileno()).st_gid != metadata.st_gid:
                    os.fchown(stream.fileno(), metadata.st_uid if _running_as_root() else -1, metadata.st_gid)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _initialize(profile, layout: _Layout) -> None:
    if (layout.data / "PG_VERSION").is_file():
        return
    staging = layout.data.parent / (".initdb-" + secrets.token_hex(8))
    password_file = layout.data.parent / (".password-" + secrets.token_hex(8))
    try:
        descriptor = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(profile.admin_password + "\n")
        if layout.account is not None:
            os.chown(password_file, *layout.account)
        result = _run(layout, "initdb", "-D", str(staging), "-U", "postgres", "-A", "scram-sha-256",
                      "--pwfile", str(password_file), "-E", "UTF8", "--locale=C", "--no-instructions",
                      timeout=300, capture=True)
        if result.returncode:
            detail = result.stdout.decode("utf-8", "replace").strip()[-800:]
            raise EmbeddedDatabaseError("database_initialization_failed",
                                        "The embedded database could not be initialized." + (
                                            f" initdb reported:\n{detail}" if detail else ""))
        with open(staging / "postgresql.conf", "a", encoding="utf-8") as stream:
            stream.write(_configuration(profile))
        os.replace(staging, layout.data)
    finally:
        password_file.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)


def _admin_connection(profile, database: str):
    from .storage import SCRAM_ONLY, connect

    return connect(host="127.0.0.1", port=profile.database_port, user="postgres",
                   password=profile.admin_password, dbname=database, connect_timeout=5,
                   require_auth=SCRAM_ONLY, autocommit=True)


def running(profile) -> bool:
    layout = _layout(profile)
    return (layout.data / "PG_VERSION").is_file() and _run(layout, "pg_ctl", "status", "-D", str(layout.data),
                                                         timeout=30).returncode == 0


def start(profile) -> None:
    from .native_adoption import start_source

    start_source(profile)


def _start_layout(profile, layout, *, initialize=False) -> None:
    if initialize:
        if layout.data.exists() or layout.data.is_symlink():
            raise EmbeddedDatabaseError("database_initialization_conflict", "The database initialization path already exists; existing data was preserved.")
        _initialize(profile, layout)
    elif not (layout.data / "PG_VERSION").is_file():
        raise EmbeddedDatabaseError("database_missing", "The recorded database is missing; restore it before starting. Existing paths were preserved.")
    if _run(layout, "pg_ctl", "status", "-D", str(layout.data), timeout=30).returncode != 0:
        try:
            _update_managed_defaults(profile, layout)
        except OSError:
            raise EmbeddedDatabaseError(
                "database_configuration_failed",
                "The embedded database configuration could not be updated. Existing data was preserved. "
                "Check file access and available disk space before retrying.",
            ) from None
        result = _run(layout, "pg_ctl", "start", "-D", str(layout.data), "-l", str(layout.log),
                      "-w", "-t", "90", timeout=120)
        if result.returncode:
            raise _failure("database_start_failed", "The embedded database did not start.", layout)
    deadline = time.monotonic() + 30
    while True:
        try:
            with _admin_connection(profile, "postgres") as connection:
                exists = connection.execute(
                    "SELECT 1 FROM pg_database WHERE datname='agent_memory'").fetchone()
                if not exists:
                    connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier("agent_memory")))
            return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise _failure("database_start_failed", "The embedded database is not accepting connections.",
                               layout) from None
            time.sleep(0.3)


def stop(profile) -> None:
    layout = _layout(profile)
    if not (layout.data / "PG_VERSION").is_file():
        return
    if _run(layout, "pg_ctl", "status", "-D", str(layout.data), timeout=30).returncode != 0:
        return
    if _run(layout, "pg_ctl", "stop", "-D", str(layout.data), "-m", "fast", "-w", "-t", "60",
            timeout=90).returncode:
        raise _failure("database_stop_failed", "The embedded database did not stop.", layout)


def client_command(profile, program: str, *arguments: str) -> tuple[list[str], dict[str, str]]:
    """Command and environment for pg_dump or pg_restore against the embedded cluster."""
    layout = _layout(profile)
    environment = native_environment(layout.binaries.parent, shared=layout.account is not None)
    # The bundled client tools are PostgreSQL 16, which honours PGREQUIREAUTH; see storage.connection_info.
    environment.update(PGPASSWORD=profile.admin_password, PGCONNECT_TIMEOUT="5", PGREQUIREAUTH="scram-sha-256")
    command = [str(layout.binaries / (program + _EXECUTABLE)), "--host=127.0.0.1",
               f"--port={profile.database_port}", *arguments]
    return command, environment
