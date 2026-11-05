import json
import os
import threading
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest

from membrain import desktop, embedded_database, local_profile, native_adoption, native_transition
from membrain.local_profile import LocalProfileError, ensure_profile, load_profile
from membrain.recovery_profile import check_start_allowed, read_document, write_document


@pytest.fixture
def case(tmp_path, monkeypatch):
    profile = ensure_profile(tmp_path / "profile", database_engine="embedded")
    prefix = tmp_path / "target"
    prefix.mkdir()
    engine = SimpleNamespace(prefix=tmp_path / "original", directory=tmp_path / "capsule", commitment="a" * 64)
    state = SimpleNamespace(running=False, version=160015, identifier="1234567", calls=[])
    layout = embedded_database._Layout(prefix / "bin", profile.directory / "postgres", profile.directory / "postgres.log", None)
    monkeypatch.setattr(embedded_database, "_installation", lambda: prefix)
    monkeypatch.setattr(embedded_database, "_legacy_installation", lambda: tmp_path / "legacy")
    monkeypatch.setattr(native_transition, "_target", lambda candidate: "b" * 64)
    monkeypatch.setattr(native_adoption.native_engine_store, "preserve", lambda *args, **kwargs: engine)
    monkeypatch.setattr(native_adoption.native_engine_store, "verify", lambda *args: engine)
    monkeypatch.setattr(native_adoption, "_version", lambda candidate: state.version)
    monkeypatch.setattr(native_transition, "_open_port", lambda port: state.running if port == profile.database_port else False)
    monkeypatch.setattr(native_adoption.native_snapshot, "_control", lambda *args, **kwargs: {"system_identifier": state.identifier})

    def identity(candidate, candidate_layout, versions, identifier=None):
        assert state.running
        if state.version not in versions or identifier is not None and identifier != state.identifier:
            raise native_transition.NativeTransitionError("binding")
        return state.version, state.identifier

    def start(candidate, candidate_layout, *, initialize=False):
        assert load_profile(profile.directory).native_engine == "16.15"
        assert read_document(profile.directory / "native-source.json") is not None
        state.calls.append((candidate_layout, initialize))
        if initialize:
            assert not candidate_layout.data.exists()
            candidate_layout.data.mkdir()
            (candidate_layout.data / "PG_VERSION").write_text("16\n")
        state.running = True
        candidate_layout.log.write_text(f"LOG: starting PostgreSQL 16.{state.version % 10000} on fake\n")

    monkeypatch.setattr(native_transition, "_identity", identity)
    monkeypatch.setattr(embedded_database, "_start_layout", start)
    return SimpleNamespace(profile=profile, layout=layout, state=state, engine=engine)


def legacy(case):
    case.state.version = 160002
    case.layout.data.mkdir()
    (case.layout.data / "PG_VERSION").write_text("16\n")
    case.layout.log.write_text("LOG: starting PostgreSQL 16.2 on fake\n")


def test_native_fuse_preserves_credentials_and_rejects_unknown_versions_and_docker(tmp_path):
    profile = ensure_profile(tmp_path / "embedded", database_engine="embedded")
    old = json.loads((profile.directory / "profile.json").read_text())
    adopted = local_profile.adopt_native_engine(profile)
    current = json.loads((profile.directory / "profile.json").read_text())
    assert current.pop("native_engine") == "16.15" and current == old
    assert replace(adopted, native_engine=None) == profile
    assert local_profile.adopt_native_engine(adopted) == adopted
    with pytest.raises(LocalProfileError):
        local_profile.adopt_native_engine(profile)
    for version in [None, "16.2", "17", 16.15, True]:
        with pytest.raises(LocalProfileError):
            local_profile._validate({**old, "native_engine": version}, profile.directory)
    docker = ensure_profile(tmp_path / "docker")
    with pytest.raises(LocalProfileError):
        local_profile.adopt_native_engine(docker)
    assert "native_engine" not in json.loads((docker.directory / "profile.json").read_text())


def test_fresh_source_is_bound_before_initialize_and_cannot_reinitialize_missing_data(case):
    native_adoption.start_source(case.profile)
    assert case.state.calls[0][1] is True
    source = read_document(case.profile.directory / "native-source.json")
    assert source["system_identifier"] == case.state.identifier
    case.state.running = False
    (case.layout.data / "PG_VERSION").unlink()
    case.layout.data.rmdir()
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(load_profile(case.profile.directory))
    assert len(case.state.calls) == 1 and not case.layout.data.exists()


def test_stopped_legacy_source_is_started_with_preserved_binary_without_initialization(case):
    legacy(case)
    native_adoption.start_source(case.profile)
    layout, initialize = case.state.calls[0]
    assert not initialize and layout.binaries == case.engine.prefix / "bin"
    assert layout.data == case.layout.data
    assert read_document(case.profile.directory / "native-source.json")["original"]["version"] == 160002


@pytest.mark.parametrize("version", ["16.15", "16.20", "17.1", None])
def test_unknown_or_newer_cold_source_is_not_started_or_fused(case, version):
    legacy(case)
    case.layout.log.write_text(f"LOG: starting PostgreSQL {version} on fake\n" if version else "no version\n")
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(case.profile)
    assert not case.state.calls
    assert load_profile(case.profile.directory).native_engine is None
    assert not (case.profile.directory / "native-source.json").exists()


def test_linked_cold_source_log_is_refused_before_fusing_profile(case):
    legacy(case)
    os.link(case.layout.log, case.layout.log.with_suffix(".linked"))
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(case.profile)
    assert not case.state.calls and load_profile(case.profile.directory).native_engine is None


def test_source_identity_cannot_change_between_observation_and_restart(case):
    legacy(case)
    native_adoption.start_source(case.profile)
    case.state.running = False
    case.state.identifier = "7654321"
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(load_profile(case.profile.directory))
    assert len(case.state.calls) == 1 and case.layout.data.exists()


def test_interruption_after_handoff_retries_without_reinterpreting_source(case, monkeypatch):
    original = local_profile._save

    def fail(profile):
        if profile.native_engine:
            raise OSError("disk full")
        original(profile)

    monkeypatch.setattr(local_profile, "_save", fail)
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(case.profile)
    assert (case.profile.directory / "native-source.json").exists()
    assert not case.state.calls and load_profile(case.profile.directory).native_engine is None
    monkeypatch.setattr(local_profile, "_save", original)
    monkeypatch.setattr(embedded_database, "_installation", lambda: pytest.fail("Use the durable handoff"))
    native_adoption.start_source(case.profile)
    assert len(case.state.calls) == 1


def test_interruption_after_fuse_preserves_pending_state_and_blocks_direct_clients(case, monkeypatch):
    original = embedded_database._start_layout
    monkeypatch.setattr(embedded_database, "_start_layout", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("interrupted")))
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(case.profile)
    adopted = load_profile(case.profile.directory)
    assert adopted.native_engine == "16.15" and not case.layout.data.exists()
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        check_start_allowed(adopted)
    check_start_allowed(adopted, allow_native_upgrade=True)
    monkeypatch.setattr(embedded_database, "_start_layout", original)
    native_adoption.start_source(adopted)
    assert len(case.state.calls) == 1


def test_target_selection_never_silently_falls_back_to_legacy(case, monkeypatch):
    monkeypatch.setattr(native_adoption.native_bundle, "prepare", lambda: None)
    monkeypatch.setattr(embedded_database, "_installation", lambda: native_adoption.native_bundle.prepare())
    assert embedded_database._installation() is None
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(case.profile)
    assert not case.state.calls and load_profile(case.profile.directory).native_engine is None


def test_preflight_failure_prevents_transition_and_application_admission(case, monkeypatch):
    monkeypatch.setattr(native_transition, "session", lambda *args, **kwargs: pytest.fail("No transition"))

    def incompatible(profile):
        raise desktop.DesktopError("database_schema_incompatible", "Existing newer schema")

    with pytest.raises(desktop.DesktopError):
        native_adoption.prepare(case.profile, lambda profile: pytest.fail("No bootstrap"), preflight=incompatible)
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        check_start_allowed(load_profile(case.profile.directory))


def test_prepare_admits_application_inside_controller_and_reloads_profile(case, monkeypatch):
    events = []

    @contextmanager
    def session(profile, layout, *, original):
        assert profile.native_engine == "16.15" and original == case.engine
        events.append("enter")

        def admit(bootstrap):
            events.append("prepare")
            bootstrap()
            events.append("admitted")

        yield SimpleNamespace(admit=admit)
        events.append("exit")

    monkeypatch.setattr(native_transition, "session", session)
    native_adoption.prepare(case.profile, lambda profile: events.append("bootstrap"),
                            preflight=lambda profile: events.append("preflight"))
    assert events == ["preflight", "enter", "prepare", "bootstrap", "admitted", "exit"]


def test_recorded_transition_precedes_missing_data_and_source_handoff(case, monkeypatch):
    monkeypatch.setattr(native_transition, "recorded_layout", lambda profile: case.layout)
    monkeypatch.setattr(native_adoption, "_source", lambda profile: pytest.fail("Use transition state"))
    assert not case.layout.data.exists()
    assert embedded_database._layout(case.profile) == case.layout
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(case.profile)
    assert not case.layout.data.exists() and not case.state.calls


def test_recorded_restart_prepares_database_before_schema_preflight(case, monkeypatch):
    events = []
    monkeypatch.setattr(native_transition, "recorded_layout", lambda profile: case.layout)

    @contextmanager
    def session(profile, layout, *, original):
        assert original is None

        def prepare():
            events.append("database_started")

        def admit(bootstrap):
            assert events == ["database_started", "preflight"]
            bootstrap()
            events.append("admitted")

        yield SimpleNamespace(prepare=prepare, admit=admit)

    def preflight(profile):
        assert events == ["database_started"]
        events.append("preflight")

    monkeypatch.setattr(native_transition, "session", session)
    native_adoption.prepare(case.profile, lambda profile: events.append("bootstrap"), preflight=preflight)
    assert events == ["database_started", "preflight", "bootstrap", "admitted"]


def test_running_api_blocks_source_handoff_and_fuse(case, monkeypatch):
    monkeypatch.setattr(native_transition, "_open_port", lambda port: True)
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(case.profile)
    assert not (case.profile.directory / "native-source.json").exists()
    assert load_profile(case.profile.directory).native_engine is None


def test_active_supervisor_blocks_source_handoff_before_fuse(case):
    entered, release = threading.Event(), threading.Event()

    def supervisor():
        with local_profile.profile_lock(case.profile.directory / "supervisor"):
            entered.set()
            release.wait(10)

    thread = threading.Thread(target=supervisor)
    thread.start()
    try:
        assert entered.wait(5)
        with pytest.raises(embedded_database.EmbeddedDatabaseError):
            native_adoption.start_source(case.profile)
        assert not (case.profile.directory / "native-source.json").exists()
        assert not case.state.calls and load_profile(case.profile.directory).native_engine is None
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()


def test_profile_identity_change_invalidates_handoff_without_start(case):
    native_adoption.start_source(case.profile)
    source = read_document(case.profile.directory / "native-source.json")
    source["profile"]["api_port"] += 1
    write_document(case.profile.directory / "native-source.json", source)
    case.state.running = False
    with pytest.raises(embedded_database.EmbeddedDatabaseError):
        native_adoption.start_source(load_profile(case.profile.directory))
    assert len(case.state.calls) == 1
