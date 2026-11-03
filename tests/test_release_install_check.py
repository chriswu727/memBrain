import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def runner(tmp_path, monkeypatch):
    path = Path(__file__).parents[1] / "evaluations" / "release-install-2026-11-01.py"
    spec = importlib.util.spec_from_file_location("release_install_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "report_path", tmp_path / "results.json")
    return module


def test_mcp_errors_keep_the_original_payload_instead_of_raising_a_json_parse_error(runner):
    client = object.__new__(runner.MCP)
    payload = {"isError": True, "content": [{"type": "text", "text": "Connection refused during model activation"}]}
    client.request = lambda *args: payload
    with pytest.raises(RuntimeError, match="Connection refused during model activation") as caught:
        client.call("memory_recall", {"query": "dentist"})
    assert "memory_recall" in str(caught.value) and '"isError": true' in str(caught.value)
    client.request = lambda *args: {"isError": False, "structuredContent": {"records": []}, "content": []}
    assert json.loads(client.call("memory_recall", {})) == {"records": []}


def test_failed_runs_preserve_partial_checks_and_stop_the_test_service(runner):
    stopped = []
    home = SimpleNamespace(membrain=lambda *args: stopped.append(args) or SimpleNamespace(returncode=0))

    def interrupted():
        runner.cleanup.append((home, None))
        runner.check("upgrade preserved the brain", True)
        assert json.loads(runner.report_path.read_text())["results"][0]["ok"]
        raise RuntimeError("original MCP tool failure")

    runner.main = interrupted
    assert runner.run_checked() == 1
    report = json.loads(runner.report_path.read_text())
    assert report["results"][0]["ok"]
    assert report["results"][-1]["detail"]["error"] == "original MCP tool failure"
    assert stopped == [("desktop", "stop")]


def test_a_completed_run_with_a_failed_check_exits_nonzero(runner):
    def failed_check():
        runner.check("corrected note was delivered", False, "missing")
        runner.report_metadata["completed"] = True

    runner.main = failed_check
    assert runner.run_checked() == 1
    assert json.loads(runner.report_path.read_text())["completed"] is True


def test_cleanup_failure_cannot_make_a_successful_workflow_green(runner):
    home = SimpleNamespace(membrain=lambda *args: SimpleNamespace(returncode=1, stdout="", stderr="service still running"))

    def completed():
        runner.cleanup.append((home, None))
        runner.check("upgrade preserved the brain", True)
        runner.report_metadata["completed"] = True

    runner.main = completed
    assert runner.run_checked() == 1
    assert json.loads(runner.report_path.read_text())["results"][-1] == {
        "check": "test installation stopped", "ok": False, "detail": "service still running"}


def test_completed_success_returns_zero_and_keeps_its_report(runner):
    def completed():
        runner.check("upgrade preserved the brain", True)
        runner.report_metadata["completed"] = True

    runner.main = completed
    assert runner.run_checked() == 0
    assert json.loads(runner.report_path.read_text())["results"] == [
        {"check": "upgrade preserved the brain", "ok": True, "detail": ""}]


def test_an_existing_output_directory_is_preserved(runner, tmp_path, monkeypatch):
    old = tmp_path / "previous-attempt"
    old.mkdir()
    report = old / "results.json"
    report.write_text('{"original_failure":true}')
    monkeypatch.setattr("sys.argv", ["release-install", str(old)])
    with pytest.raises(SystemExit) as caught:
        runner.main()
    assert caught.value.code == 2
    assert report.read_text() == '{"original_failure":true}'
