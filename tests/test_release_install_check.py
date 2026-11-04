import importlib.util
import io
import json
import sys
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


def test_arguments_default_to_both_frozen_baselines_and_both_parts(runner, tmp_path):
    args = runner.parse_args([str(tmp_path / "out")])
    assert args.old == runner.OLD == "d0d7a0379f7ac5f1b81dad04504601bb6606f1b0"
    assert args.companion_old == runner.COMPANION_OLD == "19e894ca9e08cf65fa071e8019789499953478d0"
    assert args.parts == ["upgrade", "companion"]
    args = runner.parse_args([str(tmp_path / "out"), "--parts", "companion,upgrade", "--old", "a551100",
                              "--companion-old", "f" * 40])
    assert (args.parts, args.old, args.companion_old) == (["upgrade", "companion"], "a551100", "f" * 40)
    assert runner.parse_args([str(tmp_path / "out"), "--parts", "companion"]).parts == ["companion"]


@pytest.mark.parametrize("arguments", [["--companion-old", "19e894c"], ["--companion-old", "main"],
                                       ["--parts", "proxy"], ["--parts", ""], ["--parts", "upgrade,upgrade"]])
def test_a_moving_or_unknown_baseline_or_part_is_refused(runner, tmp_path, arguments):
    with pytest.raises(SystemExit) as caught:
        runner.parse_args([str(tmp_path / "out"), *arguments])
    assert caught.value.code == 2


def companion_observation(runner):
    written = {"persona_version": 1, "persona_name": "Wren", "baseline_mood": "cheerful", "feeling_note_id": "n1",
               "feeling": "nervous", "moment_note_id": "n2", "moment_text": runner.COMPANION["moment"]["text"],
               "boundary_topic": "my ex", "boundary_aliases": ["Jordan"], "kept_out": "Tahoe", "control": "Rainier",
               "support_style": runner.COMPANION["support_style"]}
    context = ('<membrain-persona version="1">\nName: Wren\nBaseline mood: cheerful (valence +1, energy 2 of 3)\n'
               "- Job interview at Northwind Labs next Monday. (the user said they felt nervous, 3 Nov)\n"
               f"How they like to be supported: {written['support_style']}\n- 3 Nov: {written['moment_text']}")
    seen = {"persona": {"version": 1, "card": {"name": "Wren"}},
            "affect": {"records": [{"note_id": "n1", "label": "nervous", "basis": "reported"}]},
            "notes": {"items": [{"event_id": "n1"}, {"event_id": "n2"}]},
            "relationship": {"boundaries": [{"topic": "my ex", "aliases": ["Jordan"]}],
                             "shared_moments": [{"id": "n2", "text": written["moment_text"]}],
                             "support_style": {"text": written["support_style"]}},
            "mood": {"label": "cheerful", "pinned": True, "baseline": {"label": "cheerful"}},
            "session_start": context, "unraised": "hiking at Mount Rainier", "raised": "hiking at Lake Tahoe"}
    return written, seen


def test_companion_items_pass_only_while_each_is_still_there_and_effective(runner):
    written, seen = companion_observation(runner)
    findings = runner.companion_findings(written, seen)
    assert [name for name, _, _ in findings] == [
        "the persona block is in session context with its version", "the feeling is listed with its note",
        "the boundary keeps its topic out of recall until the user raises it", "the shared moment is in the relationship",
        "the mood is still pinned at the persona's baseline", "the support style is kept"]
    assert all(ok for _, ok, _ in findings)
    json.dumps(findings)  # Every detail can be saved in the report.

    def broken(change):
        written, seen = companion_observation(runner)
        change(written, seen)
        return [name for name, ok, _ in runner.companion_findings(written, seen) if not ok]

    assert broken(lambda w, s: s["persona"].update(version=2)) == [findings[0][0]]
    assert broken(lambda w, s: s.update(session_start=s["session_start"].replace('version="1"', 'version="2"'))
                  ) == [findings[0][0]]
    assert broken(lambda w, s: s["affect"].update(records=[])) == [findings[1][0]]
    assert broken(lambda w, s: s["notes"].update(items=[{"event_id": "n2"}])) == [findings[1][0]]
    assert broken(lambda w, s: s.update(unraised=s["unraised"] + " and Lake Tahoe with Jordan")) == [findings[2][0]]
    assert broken(lambda w, s: s.update(unraised="nothing recalled")) == [findings[2][0]]
    assert broken(lambda w, s: s.update(raised="nothing recalled")) == [findings[2][0]]
    assert broken(lambda w, s: s["relationship"].update(boundaries=[{"topic": "my ex", "aliases": []}])
                  ) == [findings[2][0]]
    assert broken(lambda w, s: s["relationship"].update(shared_moments=[])) == [findings[3][0]]
    assert broken(lambda w, s: s.update(mood={"label": "concerned", "pinned": False, "baseline": {"label": "cheerful"}})
                  ) == [findings[4][0]]
    assert broken(lambda w, s: s["relationship"].update(support_style=None)) == [findings[5][0]]


def test_hook_output_is_read_as_the_host_receives_it(runner):
    block = '<membrain-persona version="1">\nName: Wren\n</membrain-persona>'
    output = json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": block}})
    assert '<membrain-persona version="1">' not in output  # Escaped quotes: the raw JSON would fail the check.
    assert runner.delivered(output) == block
    assert runner.delivered("plain text context") == "plain text context"
    assert runner.delivered("") == ""


def test_proxy_findings_need_injected_memory_and_a_recorded_reply(runner):
    first, second = (runner.PROXY_REPLY.format(count=count) for count in (1, 2))
    seen = [{"messages": [{"role": "user", "content": runner.PROXY_FACT}]},
            {"messages": [{"role": "user", "content": f"<membrain-history>{runner.PROXY_FACT}</membrain-history>\n\n"
                                                      f"{runner.PROXY_QUESTION}"}]}]
    replies = [{"choices": [{"message": {"content": first}}]}, {"choices": [{"message": {"content": second}}]}]
    export = json.dumps({"events": [runner.PROXY_FACT, first]})
    assert all(ok for _, ok, _ in runner.proxy_findings(seen, replies, export))
    plain = [seen[0], {"messages": [{"role": "user", "content": runner.PROXY_QUESTION}]}]
    assert [ok for _, ok, _ in runner.proxy_findings(plain, replies, export)] == [True, False, True]
    assert [ok for _, ok, _ in runner.proxy_findings(seen, replies, json.dumps([runner.PROXY_FACT]))] == [
        True, True, False]
    assert [ok for _, ok, _ in runner.proxy_findings(seen[:1], replies[:1], export)] == [False, False, True]


def test_the_stub_upstream_answers_without_a_model_and_keeps_each_request(runner):
    import urllib.request

    url, seen = runner.stub_upstream(lambda body, count: f"reply {count} to {body['user']}")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url + "/chat/completions", data=json.dumps({"user": "bot", "messages": []}).encode(),
                                     headers={"content-type": "application/json"})
    with opener.open(request, timeout=10) as response:
        assert json.loads(response.read())["choices"][0]["message"]["content"] == "reply 1 to bot"
    assert seen == [{"user": "bot", "messages": []}]


def test_a_failed_step_stops_only_its_part_and_is_saved(runner):
    def companion():
        runner.check("companion: a persona card is written on the baseline", True)
        runner.require("companion: the mood is pinned on the baseline", False, "no pin_mood")
        runner.check("never reached", True)

    def upgrade():
        raise RuntimeError("proxy did not start")

    assert runner.run_part("companion", companion) is False
    assert runner.run_part("upgrade", upgrade) is False
    assert runner.run_part("other", lambda: runner.check("later part still runs", True)) is True
    report = json.loads(runner.report_path.read_text())["results"]
    assert [(item["check"], item["ok"]) for item in report] == [
        ("companion: a persona card is written on the baseline", True),
        ("companion: the mood is pinned on the baseline", False), ("acceptance execution completed", False),
        ("acceptance execution completed", False), ("later part still runs", True)]
    assert report[2]["detail"] == {"part": "companion", "stopped_after": "companion: the mood is pinned on the baseline"}
    assert report[3]["detail"] == {"part": "upgrade", "type": "RuntimeError", "error": "proxy did not start"}


def test_main_runs_the_chosen_parts_and_is_complete_only_when_each_finishes(runner, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "upgrade_part", lambda out, old, pin, hooks: calls.append(("upgrade", old)))
    monkeypatch.setattr(runner, "companion_part", lambda out, old, hooks: calls.append(("companion", old)))
    monkeypatch.setattr("sys.argv", ["release-install", str(tmp_path / "run")])
    assert runner.run_checked() == 0
    report = json.loads((tmp_path / "run" / "results.json").read_text())
    assert calls == [("upgrade", runner.OLD), ("companion", runner.COMPANION_OLD)]
    assert (report["completed"], report["parts"], report["companion_old"]) == (True, ["upgrade", "companion"],
                                                                               runner.COMPANION_OLD)

    def fails(out, old, hooks):
        raise runner.StepFailed("companion: baseline 19e894c installs through its own hooks and records turns")

    runner.results.clear()
    monkeypatch.setattr(runner, "companion_part", fails)
    monkeypatch.setattr("sys.argv", ["release-install", str(tmp_path / "second"), "--parts", "companion"])
    assert runner.run_checked() == 1
    report = json.loads((tmp_path / "second" / "results.json").read_text())
    assert report["completed"] is False and report["parts"] == ["companion"]
    assert report["results"][-1]["detail"]["part"] == "companion"


def test_the_installed_sdk_reports_a_missing_runtime_or_api_by_name(runner, tmp_path):
    home = runner.Home(tmp_path / "base")
    with pytest.raises(RuntimeError, match="no installed runtime"):
        runner.sdk(home, [["persona", [], {}]])
    python = home.runtime_python()
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\ncat >/dev/null\necho '{\"error\": \"the SDK has no MemoryClient.pin_mood\"}'\n")
    python.chmod(0o755)
    with pytest.raises(RuntimeError, match="SDK has no MemoryClient.pin_mood"):
        runner.sdk(home, [["pin_mood", [True], {}]])
    python.write_text("#!/bin/sh\ncat >/dev/null\necho 'log line'\necho '{\"results\": [{\"version\": 3}]}'\n")
    assert runner.sdk(home, [["persona", [], {}]]) == [{"version": 3}]
    python.write_text("#!/bin/sh\necho Traceback >&2\nexit 1\n")
    with pytest.raises(RuntimeError, match="exit 1.*Traceback"):
        runner.sdk(home, [["persona", [], {}]])
    assert runner.missing(["memory_note"], runner.COMPANION_TOOLS) == ["memory_boundary"]

def test_the_installed_sdk_fails_on_a_nonzero_exit_even_after_printing_results(runner, tmp_path, monkeypatch):
    home = runner.Home(tmp_path / "base")
    python = home.runtime_python()
    python.parent.mkdir(parents=True)
    python.write_text("")
    crashed = runner.subprocess.CompletedProcess(
        [], 1, stdout='{"results": ["printed before crash"]}\n', stderr="process failed")
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: crashed)
    with pytest.raises(RuntimeError, match=r"(?s)exit 1.*printed before crash.*process failed"):
        runner.sdk(home, [["persona", [], {}]])


def test_baseline_setup_waits_for_download_and_service_readiness(runner, tmp_path, monkeypatch, capsys):
    states = iter([{"ready": True, "downloading": True}, {"ready": False, "downloading": False},
                   {"ready": True, "downloading": False, "semantic_recall": "ready"}])
    observed = []

    def status(directory):
        state = next(states)
        observed.append(state)
        return state

    marker = SimpleNamespace(exists=lambda: observed[-1]["downloading"])
    fake = SimpleNamespace(profile_directory=lambda value: tmp_path, installation_status=status,
                           _download_marker=lambda directory: marker)
    monkeypatch.setitem(sys.modules, "membrain", SimpleNamespace(host=fake))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"calls": [["wait_model_activation", [], {}]]})))
    with pytest.raises(SystemExit) as exited:
        exec(runner.SDK_SCRIPT, {})
    assert exited.value.code == 0
    assert json.loads(capsys.readouterr().out) == {"results": [{"ready": True, "semantic_recall": "ready"}]}
    assert len(observed) == 3


def test_baseline_activation_timeout_remains_a_failed_check(runner, tmp_path, monkeypatch, capsys):
    fake = SimpleNamespace(profile_directory=lambda value: tmp_path,
                           installation_status=lambda directory: {"ready": False},
                           _download_marker=lambda directory: SimpleNamespace(exists=lambda: True))
    monkeypatch.setitem(sys.modules, "membrain", SimpleNamespace(host=fake))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"calls": [["wait_model_activation", [0], {}]]})))
    with pytest.raises(SystemExit):
        exec(runner.SDK_SCRIPT, {})
    assert json.loads(capsys.readouterr().out) == {
        "error": "the baseline did not finish model activation", "results": []}
