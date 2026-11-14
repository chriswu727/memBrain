import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from membrain import (
    cli,
    config,
    desktop,
    embedded_database,
    local_embeddings,
    native_adoption,
    native_bundle,
    storage,
)
from membrain.config import Settings
from membrain.local_profile import ensure_profile, load_profile
from membrain.storage import SchemaCompatibilityError


@pytest.fixture
def profile(tmp_path):
    return ensure_profile(tmp_path)


def running(profile, configuration):
    return {**desktop._base_status(profile), "ready": True, "state": "ready",
            "database": "ready", "worker": "ready", "instance_id": "existing",
            "configuration": configuration}


def forbid(*args, **kwargs):
    pytest.fail("This operation must not run")


def test_same_version_new_build_requires_restart_without_stopping_old_service(profile, monkeypatch):
    previous = running(profile, desktop._fingerprint(profile))
    monkeypatch.setattr(desktop, "BUILD_ID", "f" * 64)
    monkeypatch.setattr(desktop, "_probe", lambda candidate: previous.copy())
    monkeypatch.setattr(desktop, "_prepare_database", forbid)
    monkeypatch.setattr(desktop, "_launch", forbid)
    monkeypatch.setattr(desktop, "stop", forbid)
    status = desktop.status(profile.directory)
    assert status["version"] == desktop.__version__
    assert status["state"] == "restart_required" and not status["ready"]
    with pytest.raises(desktop.DesktopError) as error:
        desktop.start(profile.directory)
    assert error.value.code == "restart_required"
    assert load_profile(profile.directory) == profile


def test_supervisor_freezes_loaded_configuration_identity(profile, monkeypatch):
    supervisor = desktop.LocalSupervisor(profile, logging.getLogger("upgrade-test"))
    before = supervisor.configuration
    monkeypatch.setattr(desktop, "BUILD_ID", "e" * 64)
    assert desktop._fingerprint(profile) != before
    assert supervisor.configuration == before


@pytest.mark.parametrize("error", [SchemaCompatibilityError(), RuntimeError("secret database password")])
def test_restart_preflight_failure_preserves_running_service_and_configuration(profile, monkeypatch, error):
    monkeypatch.setattr(desktop, "_probe", lambda candidate: running(profile, "old-build"))
    monkeypatch.setattr(desktop, "stop", forbid)
    monkeypatch.setattr(desktop, "start", forbid)

    def check(*args, **kwargs):
        raise error

    monkeypatch.setattr(storage.Database, "check_compatibility", check)
    with pytest.raises(desktop.DesktopError) as rejected:
        desktop.restart(profile.directory)
    expected = "database_schema_incompatible" if isinstance(error, SchemaCompatibilityError) else "database_unavailable"
    assert rejected.value.code == expected
    assert "secret" not in str(rejected.value)
    assert load_profile(profile.directory) == profile


def test_compatible_restart_checks_before_stop_and_start(profile, monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, "_probe", lambda candidate: running(profile, "old-build"))
    monkeypatch.setattr(desktop, "_check_database", lambda candidate: calls.append("check"))
    monkeypatch.setattr(desktop, "stop", lambda directory: calls.append("stop"))
    monkeypatch.setattr(desktop, "start", lambda directory: calls.append("start") or {"ready": True})
    assert desktop.restart(profile.directory)["ready"]
    assert calls == ["check", "stop", "start"]


def test_offline_restart_can_start_database_without_assuming_schema_compatibility(profile, monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, "_probe", lambda candidate: None)
    monkeypatch.setattr(desktop, "_port_open", lambda port: False)
    monkeypatch.setattr(desktop, "_check_database", forbid)
    monkeypatch.setattr(desktop, "stop", lambda directory: calls.append("stop"))
    monkeypatch.setattr(desktop, "start", lambda directory: calls.append("start") or {"ready": True})
    assert desktop.restart(profile.directory)["ready"]
    assert calls == ["stop", "start"]


@pytest.mark.parametrize("recorded", [False, True])
@pytest.mark.parametrize("service_account", [False, True])
@pytest.mark.parametrize("code", ["embedded_database_dependencies_missing", "embedded_database_bundle_invalid",
                                   "embedded_database_space_low"])
def test_native_target_failure_preserves_running_service(tmp_path, monkeypatch, recorded, code, service_account):
    profile = ensure_profile(tmp_path / "profile", database_engine="embedded")
    before = (profile.directory / "profile.json").read_bytes()
    prefix = tmp_path / "native"
    layout = SimpleNamespace(binaries=prefix / "bin", account=(123, 456) if service_account else None)
    monkeypatch.setattr(desktop, "_probe", lambda candidate: running(profile, "old-build"))
    monkeypatch.setattr(desktop, "_check_database", lambda candidate: None)
    monkeypatch.setattr(desktop, "stop", forbid)
    monkeypatch.setattr(desktop, "start", forbid)
    monkeypatch.setattr(native_adoption, "recorded_layout", lambda candidate: layout if recorded else None)

    def reject(*args, **kwargs):
        assert kwargs == ({"shared": True} if recorded and service_account else {})
        raise native_bundle.NativeBundleError(code, "Target cannot run; existing service preserved.")

    monkeypatch.setattr(embedded_database, "_installation", forbid if recorded else reject)
    monkeypatch.setattr(native_bundle, "_versions", reject if recorded else forbid)
    with pytest.raises(desktop.DesktopError) as error:
        desktop.restart(profile.directory)
    assert error.value.code == code
    assert (profile.directory / "profile.json").read_bytes() == before
    assert not (profile.directory / "native-source.json").exists()
    assert not (profile.directory / "native-transition.json").exists()


@pytest.mark.parametrize("recorded", [False, True])
@pytest.mark.parametrize("service_account", [False, True])
def test_native_restart_checks_selected_engine_before_stopping(tmp_path, monkeypatch, recorded, service_account):
    profile = ensure_profile(tmp_path / "profile", database_engine="embedded")
    calls = []
    prefix = tmp_path / "native"
    layout = SimpleNamespace(binaries=prefix / "bin", account=(123, 456) if service_account else None)
    monkeypatch.setattr(desktop, "_probe", lambda candidate: running(profile, "old-build"))
    monkeypatch.setattr(desktop, "_check_database", lambda candidate: calls.append("schema"))
    monkeypatch.setattr(native_adoption, "recorded_layout", lambda candidate: layout if recorded else None)
    monkeypatch.setattr(embedded_database, "_installation",
                        forbid if recorded else lambda: calls.append("engine") or prefix)

    def versions(candidate, *, shared=False):
        assert candidate == prefix
        assert shared is service_account
        calls.append("engine")

    monkeypatch.setattr(native_bundle, "_versions", versions if recorded else forbid)
    monkeypatch.setattr(desktop, "stop", lambda directory: calls.append("stop"))
    monkeypatch.setattr(desktop, "start", lambda directory: calls.append("start") or {"ready": True})
    assert desktop.restart(profile.directory)["ready"]
    assert calls == ["schema", "engine", "stop", "start"]
    assert load_profile(profile.directory) == profile


def test_missing_native_supplier_preserves_running_service(tmp_path, monkeypatch):
    profile = ensure_profile(tmp_path / "profile", database_engine="embedded")
    monkeypatch.setattr(desktop, "_probe", lambda candidate: running(profile, "old-build"))
    monkeypatch.setattr(desktop, "_check_database", lambda candidate: None)
    monkeypatch.setattr(embedded_database, "_installation", lambda: None)
    monkeypatch.setattr(desktop, "stop", forbid)
    monkeypatch.setattr(desktop, "start", forbid)
    with pytest.raises(desktop.DesktopError) as error:
        desktop.restart(profile.directory)
    assert error.value.code == "embedded_database_unavailable"
    assert load_profile(profile.directory) == profile


def test_live_incompatible_database_is_not_reconfigured_by_compose(profile, monkeypatch):
    monkeypatch.setattr(desktop, "_port_open", lambda port: True)
    monkeypatch.setattr(desktop, "_compose", forbid)

    def check(*args, **kwargs):
        raise SchemaCompatibilityError()

    monkeypatch.setattr(storage.Database, "check_compatibility", check)
    with pytest.raises(desktop.DesktopError, match="compatible release"):
        desktop._prepare_database(profile)


def test_offline_database_is_checked_after_start_before_role_or_schema_changes(profile, monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, "_port_open", lambda port: False)
    monkeypatch.setattr(desktop, "_compose", lambda *args: calls.append("compose"))
    monkeypatch.setattr(cli, "bootstrap", forbid)

    def check(*args, **kwargs):
        calls.append("check")
        raise SchemaCompatibilityError()

    monkeypatch.setattr(storage.Database, "check_compatibility", check)
    with pytest.raises(desktop.DesktopError) as error:
        desktop._prepare_database(profile)
    assert error.value.code == "database_schema_incompatible"
    assert calls == ["compose", "check"]


def test_bootstrap_rejects_schema_before_role_provisioning(monkeypatch):
    def check(*args, **kwargs):
        raise SchemaCompatibilityError()

    monkeypatch.setattr(storage.Database, "check_compatibility", check)
    monkeypatch.setattr(storage.psycopg, "connect", forbid)
    with pytest.raises(SchemaCompatibilityError):
        cli.bootstrap(Settings(database_url="unused", migration_database_url="unused"), app_password="private")


def test_service_factory_checks_current_schema_before_constructing_provider(monkeypatch):
    calls = []

    def check(self, *, require_current=False):
        calls.append((self.dsn, require_current))
        raise SchemaCompatibilityError()

    monkeypatch.setattr(storage.Database, "check_compatibility", check)
    monkeypatch.setattr(local_embeddings, "LocalEmbeddingProvider", forbid)
    settings = Settings(database_url="application-connection", migration_database_url="admin-connection",
                        embedding_local_directory="/models/local-embedding")
    with pytest.raises(SchemaCompatibilityError):
        with config.configured_service(settings):
            pytest.fail("An incompatible service must not start")
    assert calls == [("application-connection", True)]


def test_runtime_entry_rejects_pending_schema_before_opening_log_or_worker(profile, monkeypatch):
    calls = []

    def check(candidate, *, require_current=False):
        calls.append(require_current)
        raise desktop.DesktopError("database_schema_incompatible", "incompatible")

    monkeypatch.setattr(desktop, "_check_database", check)
    monkeypatch.setattr(desktop, "_logger", forbid)
    with pytest.raises(desktop.DesktopError):
        desktop.run(profile.directory)
    assert calls == [True]


def test_build_diagnostics_do_not_include_credentials(profile):
    result = json.dumps(desktop._base_status(profile))
    assert len(desktop._base_status(profile)["build_id"]) == 64
    assert len(desktop._base_status(profile)["schema_id"]) == 64
    for secret in (profile.api_key, profile.admin_password, profile.app_password):
        assert secret not in result


@pytest.mark.parametrize("state", ["uninitialized", "migration_required", "incompatible"])
def test_pending_or_incompatible_schema_never_reports_ready(profile, monkeypatch, state):
    supervisor = desktop.LocalSupervisor(profile, logging.getLogger("upgrade-test"))
    supervisor.worker = SimpleNamespace(is_alive=lambda: True)
    supervisor.worker_state = "ready"
    queries = []

    @contextmanager
    def transaction(*args):
        yield SimpleNamespace(execute=lambda statement: queries.append(statement))

    def check(connection):
        if state == "incompatible":
            raise SchemaCompatibilityError()
        return {"state": state}

    monkeypatch.setattr(storage.Database, "transaction", transaction)
    monkeypatch.setattr(storage, "schema_status", check)
    result = supervisor.snapshot()
    assert not result["ready"]
    assert result["database"] == ("incompatible" if state == "incompatible" else "migration_required")
    assert queries == ["SET LOCAL statement_timeout = '2000'"]
