import copy
import hashlib
import json
import math
import re
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg import sql

from membrain import native_maintenance, native_snapshot

CATALOG_HASHES = native_maintenance._catalog_hashes


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Socket:
    def __init__(self, backend):
        self.backend = backend

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        pass

    def settimeout(self, timeout):
        assert timeout == .2

    def connect_ex(self, address):
        return 0 if self.backend.api_active else 1


class Connection:
    def __init__(self, backend, name):
        self.backend, self.name = backend, name

    def __enter__(self):
        assert self.backend.databases[self.name]["allow"]
        return self

    def __exit__(self, *arguments):
        if self.backend.lock is self:
            self.backend.lock = None

    @contextmanager
    def transaction(self):
        before = copy.deepcopy(self.backend.databases[self.name])
        try:
            yield
        except BaseException:
            self.backend.databases[self.name] = before
            raise

    def execute(self, query, params=None, **options):
        text = query if isinstance(query, str) else query.as_string()
        self.backend.trace.append((self.name, text))
        db = self.backend.databases[self.name]
        if text.startswith("SET "):
            return Cursor()
        if "pg_try_advisory_lock" in text:
            if self.backend.lock is not None:
                return Cursor([(False,)])
            self.backend.lock = self
            return Cursor([(True,)])
        if text.startswith("SELECT current_setting"):
            assert "host(inet_server_addr())" in text
            return Cursor([(self.backend.version, self.backend.identity, str(self.backend.layout.data),
                            "on", "127.0.0.1", self.backend.profile.database_port, False, "postgres")])
        if text.startswith("SELECT oid,datname"):
            return Cursor([(row["oid"], name, row["allow"], row["limit"])
                           for name, row in sorted(self.backend.databases.items(), key=lambda item: item[1]["oid"])])
        if text.startswith("SELECT oid FROM pg_database"):
            return Cursor([(db["oid"],)])
        if text.startswith("SELECT e.extversion"):
            return Cursor([(db["vector"], "vector lab")] if db["vector"] else [])
        if text == self.backend.script:
            db["fixed"] = True
            return Cursor()
        if text.startswith("ALTER DATABASE"):
            for name, row in self.backend.databases.items():
                prefix = "ALTER DATABASE " + sql.Identifier(name).as_string() + " WITH "
                if text.startswith(prefix):
                    match = re.fullmatch(r"ALLOW_CONNECTIONS (true|false) CONNECTION LIMIT\s+(-?\d+)", text[len(prefix):])
                    assert match, text
                    row["allow"], row["limit"] = match[1] == "true", int(match[2])
                    return Cursor()
            raise AssertionError(text)
        if text.startswith("ALTER EXTENSION"):
            db["vector"] = "0.8.6"
            db["upgrades"] += 1
            return Cursor()
        if text.startswith("REINDEX DATABASE"):
            db["reindexes"] += 1
            db["invalid_index"] = False
            return Cursor()
        if " OPERATOR(" in text:
            assert '"vector lab".vector OPERATOR("vector lab".<->)' in text
            return Cursor([(math.sqrt(27),)])
        if text.startswith("SELECT 1 FROM pg_index"):
            return Cursor([(1,)] if db["invalid_index"] else [])
        raise AssertionError(text)


@pytest.fixture
def backend(tmp_path, monkeypatch):
    layout = SimpleNamespace(data=tmp_path / "data", binaries=tmp_path / "engine/bin")
    layout.data.mkdir()
    (layout.binaries.parent / "share").mkdir(parents=True)
    script = "SELECT 'synthetic catalog repair';"
    (layout.binaries.parent / "share/fix-CVE-2024-4317.sql").write_text(script)
    profile = SimpleNamespace(installation_id=str(uuid4()), api_port=9876, database_port=9877)
    databases = {name: {"oid": oid, "allow": allowed, "limit": limit, "vector": vector,
                        "fixed": False, "upgrades": 0, "reindexes": 0, "invalid_index": False}
                 for name, oid, allowed, limit, vector in [
                     ("template1", 1, True, -1, None), ("template0", 4, False, -1, None),
                     ("postgres", 5, True, -1, None), ("agent_memory", 100, True, 20, "0.6.2"),
                     ('closed "quoted', 101, False, 3, "0.6.2")]}
    state = SimpleNamespace(layout=layout, profile=profile, script=script, identity="1234567890123456789",
                            version=160015, operation=str(uuid4()), commitment="a" * 64, lock=None,
                            databases=databases, trace=[], api_active=False, backup_checks=0,
                            backup_directory=tmp_path / "snapshot")

    def backup(directory, commitment):
        assert directory == state.backup_directory and commitment == state.commitment
        state.backup_checks += 1
        state.trace.append(("backup", "verify"))
        return {"control": {"system_identifier": state.identity}}

    def hashes(connection):
        if not state.databases[connection.name]["fixed"]:
            raise native_maintenance.NativeMaintenanceError("failed")
        return {"pg_stats_ext": "b" * 64, "pg_stats_ext_exprs": "c" * 64}

    monkeypatch.setattr(native_maintenance, "CATALOG_SCRIPT_SHA256", hashlib.sha256(script.encode()).hexdigest())
    monkeypatch.setattr(native_maintenance, "socket", SimpleNamespace(socket=lambda: Socket(state)))
    monkeypatch.setattr(native_maintenance.embedded_database, "_admin_connection",
                        lambda profile, name: Connection(state, name))
    monkeypatch.setattr(native_maintenance.native_snapshot, "verify", backup)
    monkeypatch.setattr(native_maintenance, "_catalog_hashes", hashes)
    return state


def run(backend, **overrides):
    return native_maintenance.maintain(backend.profile, backend.layout, backend.backup_directory,
                                       overrides.get("commitment", backend.commitment),
                                       overrides.get("operation", backend.operation))


def journal_path(backend):
    return backend.layout.data.parent / ".native-maintenance/catalog.json"


def load(backend):
    return json.loads(journal_path(backend).read_text())


def controls(backend):
    return {name: (row["oid"], row["allow"], row["limit"]) for name, row in backend.databases.items()}


def test_complete_run_repairs_every_database_and_preserves_controls_and_repeat_safety(backend):
    original = controls(backend)
    assert run(backend)["state"] == "complete"
    assert controls(backend) == original and backend.lock is None
    assert all(row["fixed"] and row["reindexes"] == 1 for row in backend.databases.values())
    assert backend.databases["agent_memory"]["vector"] == "0.8.6"
    assert backend.databases['closed "quoted']["vector"] == "0.8.6"
    first = copy.deepcopy(backend.databases)
    assert run(backend)["state"] == "complete"
    assert backend.databases == first and controls(backend) == original
    assert load(backend)["state"] == "complete"


def test_original_closed_controls_are_durable_before_the_first_opening(backend, monkeypatch):
    update = native_maintenance._set_controls

    def check(connection, row, allowed, limit):
        if allowed:
            original = next(value for value in load(backend)["databases"] if value["oid"] == row["oid"])
            assert original["allow_connections"] is False and original["connection_limit"] == row["connection_limit"]
            assert limit == 0
        return update(connection, row, allowed, limit)

    monkeypatch.setattr(native_maintenance, "_set_controls", check)
    run(backend)


def test_resume_closes_interrupted_database_before_backup_verification_even_when_backup_fails(backend, monkeypatch):
    run(backend)
    backend.databases["template0"].update(allow=True, limit=0)

    def broken(directory, commitment):
        assert backend.databases["template0"]["allow"] is False
        assert backend.databases["template0"]["limit"] == -1
        raise native_snapshot.NativeSnapshotError("invalid")

    monkeypatch.setattr(native_maintenance.native_snapshot, "verify", broken)
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_backup"
    assert backend.databases["template0"]["allow"] is False and backend.lock is None


def test_resume_restores_known_closed_controls_before_rejecting_an_added_database(backend):
    run(backend)
    backend.databases["template0"].update(allow=True, limit=0)
    backend.databases["extra"] = {**backend.databases["postgres"], "oid": 999, "limit": -2}
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_binding"
    assert backend.databases["template0"]["allow"] is False


@pytest.mark.parametrize("damage", ["operation", "commitment", "installation", "cluster", "path", "version", "row_type", "duplicate", "progress"])
def test_mismatched_or_malformed_journals_never_reopen_or_repair_a_database(backend, damage):
    run(backend)
    value = load(backend)
    if damage == "operation":
        value["operation_id"] = str(uuid4())
    elif damage == "commitment":
        value["snapshot_receipt_sha256"] = "d" * 64
    elif damage == "installation":
        value["installation_id"] = str(uuid4())
    elif damage == "cluster":
        value["system_identifier"] = "123"
    elif damage == "path":
        value["data_directory"] = str(backend.layout.data.parent / "other")
    elif damage == "version":
        value["target_server"] = True
    elif damage == "row_type":
        value["databases"][0]["allow_connections"] = 1
    elif damage == "duplicate":
        value["databases"].append(value["databases"][0])
    else:
        value["databases"][0]["reindexed"] = False
    journal_path(backend).write_text(json.dumps(value))
    original = copy.deepcopy(backend.databases)
    with pytest.raises(native_maintenance.NativeMaintenanceError):
        run(backend)
    assert backend.databases == original and backend.lock is None


@pytest.mark.parametrize("value", [None, 1, True, "invalid", "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF"])
def test_invalid_operation_identity_has_no_sql_side_effects(backend, value):
    with pytest.raises(native_maintenance.NativeMaintenanceError):
        run(backend, operation=value)
    assert backend.trace == []


def test_api_or_advisory_lock_conflict_never_runs_catalog_work(backend):
    backend.api_active = True
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_active" and backend.trace == []
    backend.api_active = False
    backend.lock = object()
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_busy" and backend.backup_checks == 0


def test_tampered_catalog_script_or_older_server_never_changes_databases(backend):
    path = backend.layout.binaries.parent / "share/fix-CVE-2024-4317.sql"
    path.write_text("unexpected")
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_unsupported" and backend.trace == []
    path.write_text(backend.script)
    backend.version = 160002
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_unsupported" and backend.backup_checks == 0


def test_newer_vector_cannot_be_downgraded_and_closed_controls_are_restored(backend):
    backend.databases["template0"]["vector"] = "0.9.0"
    original = controls(backend)
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_unsupported"
    assert backend.databases["template0"]["upgrades"] == 0 and controls(backend) == original


def test_journal_failure_after_sql_commit_can_resume_without_repeating_vector_upgrade(backend, monkeypatch):
    save = native_maintenance._save

    def interrupted(path, value):
        if any(row["name"] == "agent_memory" and row["catalog_hashes"] is not None for row in value["databases"]):
            raise native_maintenance.NativeMaintenanceError("journal")
        return save(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(native_maintenance, "_save", interrupted)
        with pytest.raises(native_maintenance.NativeMaintenanceError):
            run(backend)
    assert backend.databases["agent_memory"]["vector"] == "0.8.6"
    assert backend.databases["agent_memory"]["upgrades"] == 1
    assert load(backend)["state"] == "running"
    run(backend)
    assert backend.databases["agent_memory"]["upgrades"] == 1


def test_first_journal_failure_prevents_any_catalog_or_connection_mutation(backend, monkeypatch):
    original = copy.deepcopy(backend.databases)

    def fail(*args):
        raise native_maintenance.NativeMaintenanceError("journal")

    monkeypatch.setattr(native_maintenance, "_save", fail)
    with pytest.raises(native_maintenance.NativeMaintenanceError):
        run(backend)
    assert backend.databases == original and backend.lock is None


def test_operator_does_not_restore_or_widen_unrecognized_external_control_changes(backend):
    run(backend)
    backend.databases["template0"].update(allow=False, limit=5)
    with pytest.raises(native_maintenance.NativeMaintenanceError):
        run(backend)
    assert backend.databases["template0"]["allow"] is False
    assert backend.databases["template0"]["limit"] == 5


def test_reindex_failure_keeps_closed_controls_and_can_resume_after_committed_extension_change(backend, monkeypatch):
    execute = Connection.execute
    original = controls(backend)

    def fail(connection, query, *args, **kwargs):
        text = query if isinstance(query, str) else query.as_string()
        if connection.name == 'closed "quoted' and text.startswith("REINDEX DATABASE"):
            from psycopg.errors import LockNotAvailable

            raise LockNotAvailable("synthetic index lock")
        return execute(connection, query, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Connection, "execute", fail)
        with pytest.raises(native_maintenance.NativeMaintenanceError):
            run(backend)
    assert controls(backend) == original and backend.lock is None
    assert backend.databases['closed "quoted']["vector"] == "0.8.6"
    assert backend.databases['closed "quoted']["upgrades"] == 1
    run(backend)
    assert backend.databases['closed "quoted']["upgrades"] == 1
    assert controls(backend) == original


def test_verified_backup_for_another_cluster_is_rejected_before_journal_or_sql_mutation(backend, monkeypatch):
    original = copy.deepcopy(backend.databases)
    monkeypatch.setattr(native_maintenance.native_snapshot, "verify",
                        lambda *args: {"control": {"system_identifier": "123"}})
    with pytest.raises(native_maintenance.NativeMaintenanceError) as error:
        run(backend)
    assert error.value.code == "native_maintenance_binding"
    assert backend.databases == original and not journal_path(backend).exists()


@pytest.mark.parametrize("damage", [None, "owner", "barrier", "table_role", "rls", "missing"])
def test_catalog_verification_requires_both_owned_security_barriers_and_exact_privacy_predicates(damage):
    definition = "pg_has_role(c.relowner, 'USAGE'::text) AND NOT row_security_active(c.oid)"
    rows = [[name, definition, ["security_barrier=true"], True] for name in ("pg_stats_ext", "pg_stats_ext_exprs")]
    if damage == "owner":
        rows[0][3] = False
    elif damage == "barrier":
        rows[0][2] = []
    elif damage == "table_role":
        rows[0][1] = definition.replace("c.relowner", "s.stxowner")
    elif damage == "rls":
        rows[0][1] = definition.replace("row_security_active(c.oid)", "false")
    elif damage == "missing":
        rows.pop()
    connection = SimpleNamespace(execute=lambda *args: Cursor(rows))
    if damage is None:
        assert set(CATALOG_HASHES(connection)) == {"pg_stats_ext", "pg_stats_ext_exprs"}
    else:
        with pytest.raises(native_maintenance.NativeMaintenanceError):
            CATALOG_HASHES(connection)
