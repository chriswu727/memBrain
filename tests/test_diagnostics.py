import json

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
