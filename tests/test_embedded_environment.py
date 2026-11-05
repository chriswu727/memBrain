import os
import subprocess
from types import SimpleNamespace

import pytest

from membrain import embedded_database


@pytest.mark.parametrize("crypto_modules", [False, True])
@pytest.mark.parametrize("service_account", [False, True])
def test_database_and_backup_processes_isolate_host_overrides(tmp_path, monkeypatch, crypto_modules, service_account):
    poison = {
        "PGOPTIONS": "-c shared_preload_libraries=host_override",
        "PGSERVICEFILE": str(tmp_path / "host-service"),
        "PGPASSWORD": "host-password",
        "MEMORY_DATABASE_URL": "host-database",
        "MEMBRAIN_NATIVE_OVERRIDE": "host-native",
        "DYLD_LIBRARY_PATH": str(tmp_path / "host-dylibs"),
        "DYLD_INSERT_LIBRARIES": str(tmp_path / "host-dylib"),
        "LD_LIBRARY_PATH": str(tmp_path / "host-libs"),
        "LD_PRELOAD": str(tmp_path / "host-lib"),
        "OPENSSL_CONF": str(tmp_path / "host-ssl.conf"),
        "OPENSSL_MODULES": str(tmp_path / "host-ssl-modules"),
        "PYTHONHOME": str(tmp_path / "host-python"),
        "PYTHONPATH": str(tmp_path / "host-pythonpath"),
        "LC_ALL": "host-locale",
    }
    for name, value in poison.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SYSTEMROOT", "system-runtime")
    prefix = tmp_path / "engine"
    modules = prefix / "lib/ossl-modules"
    if crypto_modules:
        modules.mkdir(parents=True)
    account = (123, 456) if service_account else None
    layout = embedded_database._Layout(prefix / "bin", tmp_path / "data", tmp_path / "log", account)
    monkeypatch.setattr(embedded_database, "_layout", lambda profile: layout)
    calls = []

    def execute(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=b"tool")

    monkeypatch.setattr(embedded_database.subprocess, "run", execute)
    embedded_database._run(layout, "pg_controldata", str(layout.data), capture=True)
    command, options = calls[0]
    assert command[1:] == [str(layout.data)]
    assert options["stdout"] == subprocess.PIPE
    if service_account:
        assert (options["user"], options["group"], options["extra_groups"], options["cwd"]) == (
            123, 456, [], str(layout.data.parent))
    profile = SimpleNamespace(database_port=54329, admin_password="owned-password")
    backup, backup_environment = embedded_database.client_command(profile, "pg_dump", "--dbname=agent_memory")
    assert backup[1:] == ["--host=127.0.0.1", "--port=54329", "--dbname=agent_memory"]
    for environment in (options["env"], backup_environment):
        assert all(environment.get(name) != value for name, value in poison.items())
        assert environment["LC_ALL"] == "C" and environment["SYSTEMROOT"] == "system-runtime"
        assert environment.get("OPENSSL_CONF") == (os.devnull if crypto_modules else None)
        assert environment.get("OPENSSL_MODULES") == (str(modules) if crypto_modules else None)
    assert "PGPASSWORD" not in options["env"]
    assert backup_environment["PGPASSWORD"] == "owned-password"
    assert backup_environment["PGCONNECT_TIMEOUT"] == "5"
    assert all(os.environ[name] == value for name, value in poison.items())
