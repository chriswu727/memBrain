import json
import threading

import pytest

from membrain import diagnostics, host


def test_doctor_does_not_create_an_installation(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    directory = tmp_path / "not-installed"
    result = diagnostics.diagnose(directory)
    assert not result["ok"] and not directory.exists()
    service = next(check for check in result["checks"] if check["name"] == "service")
    assert service["state"] == "error" and "plugin start" in service["fix"]


def test_doctor_reports_model_and_queue_recovery_without_printing_content(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "installation_status", lambda directory: {
        "ready": False, "state": "stopped", "semantic_recall": "not_downloaded", "pending_records": 3})
    result = diagnostics.diagnose(tmp_path)
    checks = {check["name"]: check for check in result["checks"]}
    assert not result["ok"]
    assert checks["queue"]["state"] == "warning" and "3 records" in checks["queue"]["detail"]
    assert "fetch-model" in checks["semantic_recall"]["fix"]


def test_status_and_doctor_ignore_the_status_file_of_the_removed_extraction_model(tmp_path, monkeypatch):
    """An installation that ran the separate note-extraction model kept its outcomes in plugin/extraction.json. That
    model was removed: the file stays on disk, untouched, and is no longer reported or checked."""
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    state = tmp_path / "plugin"
    state.mkdir()
    old = {"turns_read": 4, "notes_saved": 2, "turns_failed": 3, "turns_skipped": 0, "failed_since_success": 3,
           "last_error": "HTTP 401", "last_failure_at": "2026-11-01T10:00:00+00:00"}
    (state / "extraction.json").write_text(json.dumps(old))
    assert "note_extraction" not in host.installation_status(tmp_path)
    result = diagnostics.diagnose(tmp_path)
    assert "note_extraction" not in {check["name"] for check in result["checks"]}
    assert "HTTP 401" not in json.dumps(result)
    assert json.loads((state / "extraction.json").read_text()) == old


STOPPED = {"ready": False, "state": "stopped", "semantic_recall": "ready", "pending_records": 0,
           "base_url": "http://127.0.0.1:45255"}


def checks_of(result):
    return {check["name"]: check for check in result["checks"]}


@pytest.mark.parametrize("available", [True, False])
def test_doctor_checks_the_database_engine_the_installation_uses(tmp_path, monkeypatch, available):
    """The service status never carried the engine, so this check was never made. The profile names it."""
    from membrain import embedded_database
    from membrain.local_profile import ensure_profile

    ensure_profile(tmp_path, database_engine="embedded")
    monkeypatch.setattr(host, "installation_status", lambda directory: dict(STOPPED))
    monkeypatch.setattr(embedded_database, "available", lambda: available)
    engine = checks_of(diagnostics.diagnose(tmp_path))["database_engine"]
    assert engine["detail"] == "Embedded PostgreSQL"
    assert (engine["state"], engine["fix"]) == (("pass", None) if available else
                                                ("error", "Install membrain-ai[embedded] with Python 3.12."))


def test_doctor_reports_a_start_in_progress_as_starting_not_as_a_stopped_service(tmp_path, monkeypatch):
    """While the first start prepares its database the service reads as stopped; the start holds the lifecycle lock."""
    from membrain.local_profile import profile_lock

    monkeypatch.setattr(host, "installation_status", lambda directory: dict(STOPPED))
    held, release = threading.Event(), threading.Event()

    def start_in_progress():
        with profile_lock(tmp_path / "lifecycle"):
            held.set()
            release.wait(10)

    thread = threading.Thread(target=start_in_progress)
    thread.start()
    try:
        assert held.wait(10)
        result = diagnostics.diagnose(tmp_path)
    finally:
        release.set()
        thread.join()
    service = checks_of(result)["service"]
    assert (service["state"], service["detail"]) == ("warning", "starting_or_stopping")
    assert "doctor again" in service["fix"] and result["ok"]
    after = checks_of(diagnostics.diagnose(tmp_path))["service"]  # The start finished without a service.
    assert (after["state"], after["detail"]) == ("error", "stopped") and "desktop logs" in after["fix"]


def test_doctor_reports_starting_when_the_start_holds_the_profile_longer_than_it_waits(tmp_path, monkeypatch):
    """The first database preparation held the profile for 30 seconds in the 2026-11-19 sandbox run; past the
    doctor's wait this read as an unreadable configuration."""
    from membrain.local_profile import LocalProfileBusy

    def busy(directory):
        raise LocalProfileBusy("Another process is updating this profile; try again shortly.")

    monkeypatch.setattr(host, "installation_status", busy)
    result = diagnostics.diagnose(tmp_path)
    service = checks_of(result)["service"]
    assert (service["state"], service["detail"]) == ("warning", "starting_or_stopping") and result["ok"]
    assert "installation" not in checks_of(result)


def test_doctor_names_the_port_another_program_holds(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "installation_status", lambda directory: {**STOPPED, "state": "port_conflict"})
    service = checks_of(diagnostics.diagnose(tmp_path))["service"]
    assert service["state"] == "error" and "port 45255" in service["fix"] and "plugin start" in service["fix"]


@pytest.mark.parametrize("state,expected", [
    ("ready", ("pass", "ready", None)),
    ("downloading", ("warning", "downloading in the background; recall matches words until it finishes.", None)),
    ("download_failed", ("warning", "download_failed; recall matches words only.", "HF_ENDPOINT")),
    ("unavailable", ("warning", None, "semantic extras")),
    ("not_downloaded", ("warning", "not_downloaded; recall matches words only.", "fetch-model")),
])
def test_doctor_says_what_each_semantic_state_means_and_advises_only_what_helps(tmp_path, monkeypatch, state,
                                                                               expected):
    monkeypatch.setattr(host, "installation_status", lambda directory: {**STOPPED, "semantic_recall": state})
    check = checks_of(diagnostics.diagnose(tmp_path))["semantic_recall"]
    level, detail, fix = expected
    assert check["state"] == level
    assert detail is None or check["detail"] == detail
    assert check["fix"] is None if fix is None else fix in check["fix"]
