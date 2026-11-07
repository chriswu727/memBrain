import subprocess
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from membrain import embedded_database, native_engine_store, native_snapshot, native_transition
from membrain.deletion_registry import DeletionRegistry
from membrain.helpers import Principal
from membrain.local_profile import ensure_profile
from membrain.recovery_profile import read_document, write_document


class Crash(BaseException):
    pass


@pytest.fixture
def case(tmp_path, monkeypatch):
    profile = ensure_profile(tmp_path / "profile", database_engine="embedded")
    data = profile.directory / "postgres"
    data.mkdir(mode=0o700)
    (data / "PG_VERSION").write_text("16\n")
    (data / "global").mkdir()
    (data / "global/pg_control").write_bytes(b"synthetic control")
    (data / "catalog").write_text("0.6.2")
    (data / "cluster-id").write_text("1234567890123456789")
    (data / "empty").mkdir()
    old = native_engine_store.PreservedEngine(tmp_path / "original", "a" * 64, 6, 60)
    target = embedded_database._Layout(tmp_path / "target/bin", data, profile.directory / "postgres.log", None)
    state = SimpleNamespace(running=True, version=160002, active=data, calls=[], clients=0)
    monkeypatch.setattr(native_transition, "_target", lambda layout: "b" * 64)
    monkeypatch.setattr(native_engine_store, "verify", lambda directory, commitment: old)
    monkeypatch.setattr(native_transition, "_open_port", lambda port: state.running if port == profile.database_port else False)
    monkeypatch.setattr(native_snapshot, "_space", lambda *args: None)

    def identity(p, layout, versions, identifier=None):
        observed = (layout.data / "cluster-id").read_text()
        if (not state.running or state.active != layout.data or state.version not in versions
                or identifier is not None and observed != identifier):
            raise native_transition.NativeTransitionError("binding")
        return state.version, observed

    def run(layout, tool, *arguments, **kwargs):
        if tool == "postgres":
            return subprocess.CompletedProcess([], 0, stdout=b"postgres (PostgreSQL) 16.2\n")
        action = arguments[0]
        state.calls.append((action, str(layout.data)))
        if action == "status":
            return subprocess.CompletedProcess([], 0 if state.running and state.active == layout.data else 3)
        if action == "stop":
            state.running = False
        elif action == "start":
            version = 160002 if layout.binaries == old.prefix / "bin" else 160015
            if version == 160002:
                assert (layout.data / "catalog").read_text() == "0.6.2"
            state.running, state.version, state.active = True, version, layout.data
        return subprocess.CompletedProcess([], 0)

    def control(layout, *, clean=True):
        if state.running and state.active == layout.data:
            raise native_snapshot.NativeSnapshotError("not_stopped")
        return {"system_identifier": (layout.data / "cluster-id").read_text(), "checkpoint": "0/1234ABCD"}

    def maintain(handle):
        (data / "catalog").write_text("0.8.6")
        row = {"oid": 1, "name": "agent_memory", "allow_connections": True, "connection_limit": -1,
               "inspected": True, "vector_before": "0.6.2", "catalog_hashes": None, "reindexed": False, "complete": False}
        write_document(handle.maintenance / "catalog.json", {
            "version": 1, "operation_id": handle.journal["operation_id"], "installation_id": profile.installation_id,
            "system_identifier": "1234567890123456789", "data_directory": str(data.resolve()),
            "snapshot_receipt_sha256": handle.journal["snapshot"]["commitment"],
            "target_server": 160015, "target_vector": "0.8.6", "state": "running", "databases": [row]})

    monkeypatch.setattr(native_transition, "_identity", identity)
    monkeypatch.setattr(embedded_database, "_run", run)
    monkeypatch.setattr(embedded_database, "_admin_connection", lambda *args: nullcontext(SimpleNamespace(
        execute=lambda *args: SimpleNamespace(fetchone=lambda: (state.clients,)))))
    monkeypatch.setattr(native_snapshot, "_control", control)
    monkeypatch.setattr(native_transition.Transition, "_maintain", maintain)
    monkeypatch.setattr(native_transition.Transition, "_application", lambda self: None)
    monkeypatch.setattr(native_transition.Transition, "_ready", lambda self: None)
    return SimpleNamespace(profile=profile, layout=target, old=old, state=state, root=tmp_path,
                           path=profile.directory / "native-transition.json")


def open_case(case, **kwargs):
    return native_transition.session(case.profile, case.layout, original=case.old, **kwargs)


def bind(case):
    registry = DeletionRegistry.create(case.root / "registry", case.profile.installation_id)
    write_document(case.profile.directory / "recovery.json", {
        "version": 1, "registry_path": str(registry.directory), "registry_id": registry.registry_id,
        "installation_id": case.profile.installation_id, "state": "active", "recovery_epoch": None})
    return registry


def test_upgrade_admission_is_durable_and_never_rolls_back_after_launch_timeout(case):
    with open_case(case) as handle:
        assert handle.prepare()["state"] == "prepared"
        assert case.state.version == 160015
        backup = handle.journal["snapshot"].copy()
        assert handle.admit(lambda: None)["state"] == "admitted"
    with open_case(case) as resumed:
        assert resumed.prepare()["state"] == "admitted"
        with pytest.raises(native_transition.NativeTransitionError) as error:
            resumed.rollback()
        assert error.value.code == "native_transition_admitted"
        assert resumed.journal["snapshot"] == backup
        assert (case.layout.data / "catalog").read_text() == "0.8.6"


def test_guarded_rollback_preserves_failed_data_and_archives_target_sql_journal(case):
    with open_case(case) as handle:
        handle.prepare()
        (case.layout.data / "new-target-file").write_text("preserve failed target")
        assert handle.rollback()["state"] == "rolled_back"
        failed = Path(handle.journal["restore"]["failed"])
        assert (failed / "new-target-file").read_text() == "preserve failed target"
        assert not (case.layout.data / "new-target-file").exists()
        assert (case.layout.data / "catalog").read_text() == "0.6.2"
        assert not (handle.maintenance / "catalog.json").exists()
        assert (handle.maintenance / ("catalog-" + handle.journal["operation_id"] + ".failed.json")).exists()
        assert handle.rollback()["state"] == "rolled_back"
        with pytest.raises(native_transition.NativeTransitionError) as error:
            handle.prepare()
        assert error.value.code == "native_transition_rolled_back"


@pytest.mark.parametrize("phase", ["backed_up", "maintaining", "restarting", "prepared", "admitted"])
@pytest.mark.parametrize("after_write", [False, True])
def test_journal_failure_invalidates_handle_and_resume_uses_disk_state(case, monkeypatch, phase, after_write):
    real = native_transition.write_document
    fired = False

    def interrupted(path, document):
        nonlocal fired
        if path == case.path and document["phase"] == phase and not fired:
            fired = True
            if after_write:
                real(path, document)
            raise OSError("private journal detail")
        real(path, document)

    monkeypatch.setattr(native_transition, "write_document", interrupted)
    with open_case(case) as handle:
        with pytest.raises(native_transition.NativeTransitionError):
            handle.admit(lambda: None) if phase == "admitted" else handle.prepare()
        assert fired and not handle.valid
        with pytest.raises(native_transition.NativeTransitionError):
            handle.rollback()
    with open_case(case) as resumed:
        state = resumed.admit(lambda: None) if phase == "admitted" else resumed.prepare()
        assert state["state"] in {"prepared", "admitted"}
        assert case.state.version == 160015


@pytest.mark.parametrize("move_number", [1, 2, 3])
def test_process_death_after_each_recovery_rename_resumes_without_overwrite(case, monkeypatch, move_number):
    move = native_transition._move_absent
    calls = 0

    def interrupted(source, target):
        nonlocal calls
        move(source, target)
        calls += 1
        if calls == move_number:
            raise Crash()

    with open_case(case) as handle:
        handle.prepare()
        monkeypatch.setattr(native_transition, "_move_absent", interrupted)
        with pytest.raises(Crash):
            handle.rollback()
    monkeypatch.setattr(native_transition, "_move_absent", move)
    with native_transition.session(case.profile) as resumed:
        assert resumed.rollback()["state"] == "rolled_back"
        assert case.state.version == 160002
        assert (case.layout.data / "catalog").read_text() == "0.6.2"


def test_retry_after_rollback_starts_new_operation_and_takes_new_backup(case):
    with open_case(case) as handle:
        handle.prepare()
        old_operation = handle.journal["operation_id"]
        handle.rollback()
    (case.layout.data / "between-operations").write_text("new data")
    with open_case(case, retry_rolled_back=True) as handle:
        assert handle.journal["operation_id"] != old_operation
        assert (handle.path.parent / ("transition-" + old_operation + ".json")).exists()
        handle.prepare()
        handle.rollback()
        assert (case.layout.data / "between-operations").read_text() == "new data"


@pytest.mark.parametrize("change", ["binding", "deletion"])
def test_authority_changes_refuse_rollback_before_stopping_or_mutating_target(case, change):
    registry = bind(case) if change == "deletion" else None
    with open_case(case) as handle:
        handle.prepare()
        if change == "binding":
            bind(case)
        else:
            registry.append(key_digest="c" * 64, fingerprint="d" * 64,
                            principal=Principal(case.profile.tenant_id, case.profile.principal_id),
                            brain_id=case.profile.brain_id, mode="erase_content", cutoff=0,
                            event_ids=[str(uuid4())], memory_ids=[], expected_installation_id=case.profile.installation_id)
        calls = list(case.state.calls)
        with pytest.raises(native_transition.NativeTransitionError) as error:
            handle.rollback()
        assert error.value.code == "native_transition_authority"
        assert case.state.calls == calls and case.state.running
        assert (case.layout.data / "catalog").read_text() == "0.8.6"


def test_partial_bootstrap_with_new_authority_can_retry_forward_but_cannot_rollback(case):
    def bootstrap():
        bind(case)
        raise RuntimeError("interrupted application setup")

    with open_case(case) as handle:
        with pytest.raises(native_transition.NativeTransitionError) as error:
            handle.admit(bootstrap)
        assert error.value.code == "native_transition_application"
        assert read_document(case.path)["phase"] == "bootstrapping"
        with pytest.raises(native_transition.NativeTransitionError) as error:
            handle.rollback()
        assert error.value.code == "native_transition_authority"
    with open_case(case) as resumed:
        assert resumed.admit(lambda: None)["state"] == "admitted"


@pytest.mark.parametrize("damage", ["profile", "identity", "phase", "snapshot_path", "extra"])
def test_foreign_or_malformed_journal_is_rejected_without_database_changes(case, damage):
    with open_case(case) as handle:
        handle.prepare()
    document = read_document(case.path)
    if damage == "profile":
        document["profile"]["database_port"] += 1
    elif damage == "identity":
        document["system_identifier"] = "0"
    elif damage == "phase":
        document["phase"] = "unknown"
    elif damage == "snapshot_path":
        document["snapshot"]["directory"] = str(case.root / "foreign")
    else:
        document["extra"] = True
    write_document(case.path, document)
    before = list(case.state.calls)
    with pytest.raises(native_transition.NativeTransitionError):
        with open_case(case):
            pytest.fail("Invalid journal must not open")
    assert case.state.calls == before


def test_existing_failed_directory_is_never_overwritten(case):
    with open_case(case) as handle:
        handle.prepare()
        failed = case.layout.data.parent / (".native-failed-" + handle.journal["operation_id"])
        failed.mkdir()
        with pytest.raises(native_transition.NativeTransitionError):
            handle.rollback()
        assert failed.is_dir() and (case.layout.data / "catalog").read_text() == "0.8.6"


def test_admitted_restart_does_not_require_old_backup_or_original_engine(case, monkeypatch):
    with open_case(case) as handle:
        handle.admit(lambda: None)
    monkeypatch.setattr(native_transition.Transition, "_backup", lambda self: pytest.fail("No rollback backup read after admission"))
    monkeypatch.setattr(native_transition.Transition, "_old", lambda self: pytest.fail("No old engine after admission"))
    with open_case(case) as resumed:
        assert resumed.prepare()["state"] == "admitted"


@pytest.mark.parametrize("kind", ["source_stopped", "clients", "active_api", "foreign_version", "docker"])
def test_preflight_refuses_unowned_or_busy_sources_without_stopping_them(case, monkeypatch, kind):
    profile = case.profile
    if kind == "source_stopped":
        case.state.running = False
    elif kind == "clients":
        case.state.clients = 1
    elif kind == "active_api":
        monkeypatch.setattr(native_transition, "_open_port", lambda port: True)
    elif kind == "foreign_version":
        case.state.version = 160016
    else:
        profile = replace(profile, database_engine="docker")
    with pytest.raises(native_transition.NativeTransitionError):
        with native_transition.session(profile, case.layout, original=case.old):
            pytest.fail("Unsafe preflight must not open")
    assert not case.path.exists() and not any(action == "stop" for action, _ in case.state.calls)


def test_atomic_moves_refuse_existing_empty_directory(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    with pytest.raises(FileExistsError):
        native_transition._move_absent(source, destination)
    assert source.is_dir() and destination.is_dir()


def test_handle_cannot_mutate_after_releasing_lifecycle_locks(case):
    with open_case(case) as handle:
        handle.prepare()
    before = list(case.state.calls)
    for method in (handle.prepare, handle.rollback, lambda: handle.admit(lambda: None)):
        with pytest.raises(native_transition.NativeTransitionError) as error:
            method()
        assert error.value.code == "native_transition_failed"
    assert case.state.calls == before


def test_api_opening_after_context_entry_still_blocks_recovery(case, monkeypatch):
    with open_case(case) as handle:
        handle.prepare()
        before = list(case.state.calls)
        monkeypatch.setattr(native_transition, "_open_port", lambda port: True)
        with pytest.raises(native_transition.NativeTransitionError) as error:
            handle.rollback()
        assert error.value.code == "native_transition_active" and case.state.calls == before
