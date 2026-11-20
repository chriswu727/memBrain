"""The host-trial tool without any host, model, service or database: the scenario format and its lint, the approval
refusals, the ledger, the launcher rewrite, log parsing and cost, and the redaction of what is published.

The end-to-end runs through the stub host and a real service are in tests/test_host_trial_e2e.py.
"""
import datetime
import getpass
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "evaluations" / "host-trial"
EVIDENCE = ROOT / "evaluations" / "evidence" / "host-trial-2026-11-18"


def _load():
    spec = importlib.util.spec_from_file_location("host_trial_tool", TOOL / "trial.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trial = _load()
scenarios = trial.scenarios
report = trial.report
A = TOOL / "scenarios" / "resume-after-correction.json"
B = TOOL / "scenarios" / "show-forget-boundary.json"


# The scenario format and the lint ----------------------------------------------------------------------------------

def test_the_delivered_scenarios_are_valid_and_pass_the_lint():
    for path in (A, B):
        scenario = scenarios.load(path)
        assert scenarios.lint(scenario) == []
    assert len(scenarios.turns(scenarios.load(A))) == 7
    assert len(scenarios.turns(scenarios.load(B))) <= 6


def test_resume_after_correction_sends_exactly_the_messages_of_2026_11_18():
    sent = [line.split(": ", 1)[1] for line in (EVIDENCE / "messages.txt").read_text().splitlines()]
    plan = scenarios.turns(scenarios.load(A))
    assert [turn["message"] for turn in plan] == sent
    assert [turn["new_session"] for turn in plan] == [True, False, True, False, True, False, False]


@pytest.mark.parametrize("message, flagged", [
    ("Please call memory_note with this.", "tool name"),
    ("Use the memory tool for that.", "memory"),
    ("Make a note: we use SQLite.", "note"),
    ("Remember that I like pnpm.", "remember"),
    ("Don't forget the migration.", "forget"),
    ("Run Bash and show me.", "tool name"),
    ("Open membrain plugin ui for me.", "membrain"),
    ("Save this for later.", "save"),
])
def test_the_lint_flags_tool_names_and_reminders(message, flagged):
    found = scenarios.lint_message(message)
    assert any(item.startswith(flagged) for item in found), found


def test_the_lint_passes_ordinary_messages_and_an_override_allows_only_its_words():
    assert scenarios.lint_message("Quick correction on the database: only the server uses PostgreSQL.") == []
    message = "Please forget the pnpm thing, and remember SQLite."
    assert {item.split(":")[0] for item in scenarios.lint_message(message)} == {"forget", "remember"}
    allowed = scenarios.lint_message(message, {"words": ["forget"], "reason": "asks to forget"})
    assert [item.split(":")[0] for item in allowed] == ["remember"]
    scenario = scenarios.load(B)
    scenario["sessions"][0]["turns"][2]["lint_override"] = {"words": ["forget"], "reason": " "}
    assert any("gives a reason" in problem for problem in scenarios.lint(scenario))
    del scenario["sessions"][0]["turns"][2]["lint_override"]
    assert any("forget" in problem for problem in scenarios.lint(scenario))


def test_the_format_refuses_what_it_cannot_play():
    scenario = json.loads(A.read_text())
    scenario["sessions"][0]["turns"][0]["checks"].append({"type": "erased", "ref": "never-saved"})
    scenario["project"]["files"]["../outside.txt"] = "x"
    scenario["memory"] = {"old": True}
    problems = scenarios.validate(scenario)
    assert any("never-saved" in problem for problem in problems)
    assert any("outside.txt" in problem for problem in problems)
    assert any(problem.startswith("memory") for problem in problems)


def test_tool_checks_match_predicates_save_ids_and_report_informational_checks_without_failing():
    calls = [{"name": "mcp__plugin_membrain_membrain__memory_note", "input": {"text": "Local is SQLite.",
                                                                          "replaces": ["n1"]},
              "result": {"note_id": "n2"}},
             {"name": "Bash", "input": {"command": "membrain plugin ui --note n2"}, "result": "Memory page"}]
    refs = {"decision": "n1"}
    check = {"type": "tool", "name": "memory_note", "where": [{"field": "replaces", "includes_ref": "decision"}],
             "save": {"corrected": "result.note_id"}}
    assert scenarios.evaluate(check, turn=None, calls=calls, state=None, project=Path("."), refs=refs)["verdict"] == "pass"
    assert refs["corrected"] == "n2"
    page = {"type": "tool", "name": "Bash", "where": [{"field": "command", "contains": "membrain plugin ui"},
                                                      {"field": "command", "includes_ref": "corrected"}]}
    assert scenarios.evaluate(page, turn=None, calls=calls, state=None, project=Path("."), refs=refs)["verdict"] == "pass"
    absent = {"type": "tool", "name": ["Write", "Edit"], "called": False}
    assert scenarios.evaluate(absent, turn=None, calls=calls, state=None, project=Path("."), refs=refs)["verdict"] == "pass"
    wrong = {"type": "tool", "name": "memory_note", "where": [{"field": "replaces", "includes_ref": "corrected"}],
             "informational": True}
    result = scenarios.evaluate(wrong, turn=None, calls=calls, state=None, project=Path("."), refs=refs)
    assert (result["verdict"], result["holds"]) == ("noted", False)
    state = {"notes": [{"event_id": "n2", "text": "[other] Local is SQLite.", "replaced": [{"event_id": "n1", "depth": 1}]}],
             "boundaries": [{"topic": "the old Heroku setup", "aliases": []}], "records": [], "still_present": []}
    for check, verdict in (({"type": "note_replaces", "matching": "sqlite", "ref": "decision"}, "pass"),
                           ({"type": "note_current", "ref": "decision", "present": False}, "pass"),
                           ({"type": "boundary", "matching": "heroku"}, "pass"),
                           ({"type": "erased", "ref": "decision"}, "pass"),
                           ({"type": "erased", "ref": "unset"}, "FAIL")):
        assert scenarios.evaluate(check, turn=None, calls=[], state=state, project=Path("."), refs=refs)["verdict"] == verdict


# Approvals and the ledger ------------------------------------------------------------------------------------------

def approval(tmp_path, **changes):
    document = {"approved_by": "owner", "date": datetime.date.today().isoformat(), "model": "sonnet",
                "max_turns": 7, "scenario_sha256": scenarios.sha256(A), **changes}
    document = {key: value for key, value in document.items() if value is not None}
    path = tmp_path / f"approval-{len(list(tmp_path.glob('approval-*')))}.json"
    path.write_text(json.dumps(document))
    return path


def check(path):
    return trial.check_approval(path, sha=scenarios.sha256(A), turns=7, commit="4fc15455" + "0" * 32)


def test_an_approval_states_who_when_which_model_how_many_turns_and_the_scenario(tmp_path):
    assert check(approval(tmp_path))["model"] == "sonnet"
    assert check(approval(tmp_path, model="haiku", max_turns=12, commit="4fc15455"))["max_turns"] == 12
    refusals = {
        "no approval file": None,
        "only sonnet or haiku": approval(tmp_path, model="opus"),
        "only sonnet or haiku ": approval(tmp_path, model="Sonnet"),
        "only sonnet or haiku  ": approval(tmp_path, model="claude-sonnet"),
        "over the approved limit": approval(tmp_path, max_turns=6),
        "another scenario hash": approval(tmp_path, scenario_sha256="0" * 64),
        "in the future": approval(tmp_path, date=(datetime.date.today() + datetime.timedelta(days=1)).isoformat()),
        "names who approved": approval(tmp_path, approved_by=" "),
        "exactly": approval(tmp_path, model=None),
        "exactly ": approval(tmp_path, extra="x"),
        "from 1 to": approval(tmp_path, max_turns=trial.MAX_TURNS + 1),
        "another commit": approval(tmp_path, commit="deadbeef"),
    }
    for expected, path in refusals.items():
        with pytest.raises(trial.Refused, match=expected.strip()):
            check(path)


def fake_trial(tmp_path) -> Path:
    """A prepared-looking trial directory (no runtime, no memory): enough for every refusal before a turn runs."""
    folder = tmp_path / "trials" / "resume-after-correction-1"
    folder.mkdir(parents=True)
    shutil.copyfile(A, folder / "scenario.json")
    (folder / "prepared.json").write_text(json.dumps({"scenario_sha256": scenarios.sha256(A),
                                                      "commit": "4fc15455" + "0" * 32, "runtime_digest": "x"}))
    return folder


def not_a_host(tmp_path) -> Path:
    """A `claude` that is not the stub and must never run: refusals happen before any turn."""
    folder = tmp_path / "bin"
    folder.mkdir()
    (folder / "claude").write_text("#!/bin/sh\necho ran >> \"$0.ran\"\nexit 9\n")
    (folder / "claude").chmod(0o755)
    return folder


def test_the_runner_refuses_before_any_turn_and_never_starts_the_host(tmp_path, monkeypatch):
    folder, host = fake_trial(tmp_path), not_a_host(tmp_path)
    monkeypatch.setenv("PATH", f"{host}:/usr/bin:/bin")
    for path, expected in ((None, "no approval file"), (approval(tmp_path, model="opus"), "only sonnet or haiku"),
                           (approval(tmp_path, max_turns=3), "over the approved limit"),
                           (approval(tmp_path, scenario_sha256="1" * 64), "another scenario hash")):
        with pytest.raises(trial.Refused, match=expected):
            trial.run(folder, path)
    # A changed scenario after preparation is refused even with an approval of its new hash.
    (folder / "scenario.json").write_text(A.read_text().replace("pnpm over npm", "pnpm over yarn"))
    with pytest.raises(trial.Refused, match="changed after it was prepared"):
        trial.run(folder, approval(tmp_path, scenario_sha256=scenarios.sha256(folder / "scenario.json")))
    shutil.copyfile(A, folder / "scenario.json")
    # The ledger: an approval is used once, and a scenario never runs twice on one commit. A rehearsal never counts.
    used = approval(tmp_path)
    ledger = folder.parent / trial.LEDGER
    ledger.write_text(json.dumps({"rehearsal": True, "approval_sha256": scenarios.sha256(used),
                                  "scenario_sha256": scenarios.sha256(A), "commit": "4fc15455" + "0" * 32}) + "\n")
    with pytest.raises(trial.Refused, match="runtime changed"):  # Past the ledger: the rehearsal did not count.
        trial.run(folder, used)
    ledger.write_text(json.dumps({"approval_sha256": scenarios.sha256(used), "status": "completed"}) + "\n")
    with pytest.raises(trial.Refused, match="already used"):
        trial.run(folder, used)
    ledger.write_text(json.dumps({"scenario_sha256": scenarios.sha256(A), "commit": "4fc15455" + "0" * 32,
                                  "status": "stopped"}) + "\n")
    with pytest.raises(trial.Refused, match="never rerun"):
        trial.run(folder, approval(tmp_path, notes="a second approval"))
    (folder / "run.json").write_text("{}")
    with pytest.raises(trial.Refused, match="already run"):
        trial.run(folder, approval(tmp_path))
    assert not (host / "claude.ran").exists()
    assert not (folder / "logs").exists()


def test_the_cli_reports_a_refusal_with_exit_status_2(tmp_path, monkeypatch, capsys):
    folder, host = fake_trial(tmp_path), not_a_host(tmp_path)
    monkeypatch.setenv("PATH", f"{host}:/usr/bin:/bin")
    assert trial.main(["run", str(folder), "--approval", str(approval(tmp_path, model="opus"))]) == 2
    assert "only sonnet or haiku" in json.loads(capsys.readouterr().out)["refused"]
    assert not (host / "claude.ran").exists()


# Preparation pieces ------------------------------------------------------------------------------------------------

def test_the_plugin_copy_runs_the_frozen_runtime_and_keeps_the_not_ready_notice(tmp_path):
    copy = tmp_path / "trial" / "plugin"
    shutil.copytree(ROOT / "plugins" / "membrain", copy)
    python = tmp_path / "trial" / "runtime" / ".venv" / "bin" / "python"
    seen = trial.rewrite_plugin(copy, python)
    assert sorted(seen) == ["SessionStart: plugin hook session-start", "SessionStart: plugin start",
                            "Stop: plugin hook stop", "UserPromptSubmit: plugin hook user-prompt"]
    mcp = json.loads((copy / ".claude-mcp.json").read_text())["mcpServers"]["membrain"]
    assert mcp == {"command": str(python), "args": ["-m", "membrain.cli", "plugin", "mcp"]}
    commands = [hook["command"] for groups in json.loads((copy / "hooks" / "claude-hooks.json").read_text())["hooks"].values()
                for group in groups for hook in group["hooks"]]
    assert all(command.startswith(str(python) + " -m membrain.cli plugin ") for command in commands)
    assert all("uv" not in command.split("membrain.cli", 1)[0] for command in commands)
    start = next(command for command in commands if "session-start" in command)
    assert "runtime is not ready yet" in start and "uv was not found" not in start
    diff = trial.plugin_diff(ROOT / "plugins" / "membrain", copy, tmp_path / "trial")
    assert "(trial)/runtime/.venv/bin/python" in diff and str(tmp_path) not in diff
    with pytest.raises(trial.Refused, match="unknown shape"):
        trial._launcher("node something-else.js", "python")


def test_prepare_refuses_a_root_inside_a_checkout_and_a_continuation_without_its_trial(tmp_path):
    with pytest.raises(trial.Refused, match="outside every checkout"):
        trial.prepare(A, commit="HEAD", root=ROOT / "tmp-trials")
    with pytest.raises(trial.Refused, match="--continue-from"):
        trial.prepare(B, commit="HEAD", root=tmp_path)
    with pytest.raises(trial.Refused, match="does not apply"):
        trial.prepare(A, commit="HEAD", root=tmp_path, continue_from=tmp_path)
    assert not (ROOT / "tmp-trials").exists() and list(tmp_path.iterdir()) == []


# Logs, cost and redaction ------------------------------------------------------------------------------------------

USER = getpass.getuser()
HOME = str(Path.home())
CAPTURE = "cap.v1.Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5"
REAL_CAPTURE = "0123456789abcdef0123456789abcdef." + "a1" * 32 + ".fedcba9876543210fedcba9876543210"
UUID = "3561e59e-2277-4072-85cb-33d79e18115c"
KEY = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-AbCdEf"
MEMBRAIN_KEY = "am_Zx9yW8vU7tS6rQ5pO4nM3lK2jI1hG0fEdCbA"


def write_log(path: Path, trial_root: str):
    context = (f"memBrain memory is active. Pass recording_capture=\"{CAPTURE}\" with notes. Notes: - Local is SQLite. "
               f"(id: {UUID}) Project in {HOME}/projects/tidepool for {USER}.")
    events = [
        {"type": "system", "subtype": "hook_response", "hook_event": "SessionStart", "hook_name": "SessionStart:startup",
         "exit_code": 0, "output": json.dumps({"hookSpecificOutput": {"additionalContext": context}}),
         "session_id": UUID},
        {"type": "system", "subtype": "init", "model": "stub-model", "claude_code_version": "stub", "session_id": UUID,
         "cwd": f"{trial_root}/work", "tools": ["mcp__plugin_membrain_membrain__memory_note"],
         "mcp_servers": [{"name": "plugin:membrain:membrain", "status": "connected"}],
         "apiKeySource": "none", "messaging_socket_path": "/tmp/cc-socks/8287.sock"},
        {"type": "assistant", "message": {"id": "msg_011ChAwb2qTrfmRSg6eAfDVi", "content": [
            {"type": "thinking", "thinking": "", "signature": "CAQSpwgKEAgTGAI4AUIIdGhpbmtpbmcSDFEKGQobJvItUau27hoM"},
            {"type": "tool_use", "id": "toolu_01ABCdefGHIjkl", "name": "mcp__plugin_membrain_membrain__memory_note",
             "input": {"text": "Local is SQLite.", "recording_capture": REAL_CAPTURE,
                       "source_messages": [{"producer_ref": "membrain-plugin", "source_event_key": f"{UUID}:{UUID}:user",
                                            "source_revision": 1}]}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_01ABCdefGHIjkl",
                                                  "content": [{"type": "text", "text": json.dumps({"note_id": UUID})}]}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_02", "name": "Bash",
                                                       "input": {"command": f"cat {HOME}/.config/thing"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_02", "content":
            f"api_key={KEY}\nMEMORY_API_KEY: {MEMBRAIN_KEY}\nAuthorization: Bearer abcDEF123456ghiJKL789\n"
            f"page http://127.0.0.1:45991/memory?code=Q2xvc2VkU2VjcmV0Q29kZTEyMzQ1Njc4OQ#note={UUID} "
            f"mail {USER}@example.com ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ab"}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": f"Done, {USER}. It is in {trial_root}/work."}]}},
        {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3, "result": f"Done, {USER}.",
         "total_cost_usd": 0.16, "model_usage_since_last_result": {"stub-model": {"costUSD": 0.0096}},
         "permission_denials": [], "credential_expires_at": "2026-12-01T00:00:00Z"},
    ]
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n")


def test_a_log_with_a_home_path_the_user_name_a_capture_token_a_uuid_and_keys_comes_out_clean(tmp_path):
    trial_root = str(tmp_path / "trials" / "resume-after-correction-1")
    log = tmp_path / "t01.jsonl"
    write_log(log, trial_root)
    parsed = report.parse_log(log)
    assert parsed["calls"][0]["result"] == {"note_id": UUID} and parsed["cost"] == 0.0096
    text = report.summary("t01", f"Hello from {HOME}", parsed, extra=(trial_root,))
    text += report.redact(log.read_text(), extra=(trial_root,))
    for secret in (HOME, USER, CAPTURE, *REAL_CAPTURE.split("."), UUID, KEY, MEMBRAIN_KEY, "abcDEF123456ghiJKL789", "Q2xvc2VkU2VjcmV0Q29kZTEy",
                   "ghp_ABCDEFGHIJ", "CAQSpwgKEAgTGAI4", "toolu_01ABC", "msg_011Ch", "/tmp/cc-socks", "45991",
                   "example.com", trial_root, str(tmp_path)):
        assert secret not in text, secret
    assert USER.lower() not in text.lower()
    # What the lead needs stays readable.
    assert "Local is SQLite." in text and "TOOL memory_note" in text and "(removed)" in text and "(id)" in text


def test_a_capture_cut_short_in_a_detail_is_removed_without_swallowing_the_lines_after_it():
    # A check's detail keeps the first 300 characters of a tool's input, which can end inside the capture string;
    # the record draft is then redacted again as a whole document.
    detail = '{"text": "Local is SQLite.", "recording_capture": "0123456789abcdef0123456789abcdef.a1a1a1'
    table = report.checks_table([{"turn": "t01", "label": "first", "verdict": "pass", "detail": detail},
                                 {"turn": "t02", "label": "second", "verdict": "FAIL", "detail": "x"}])
    again = report.redact(table)
    assert "a1a1a1" not in again and "0123456789abcdef" not in again
    assert "| t02 | second | FAIL | x |" in again and again.count("\n| t0") == 2


def test_turn_cost_comes_from_the_host_result_event_or_the_difference_of_its_total(tmp_path):
    log = tmp_path / "t.jsonl"
    log.write_text(json.dumps({"type": "result", "is_error": False, "total_cost_usd": 0.30}) + "\n")
    assert report.parse_log(log, previous_total=0.25)["cost"] == pytest.approx(0.05)
    assert report.parse_log(log)["cost"] == pytest.approx(0.30)
    missing = tmp_path / "none.jsonl"
    assert report.parse_log(missing)["result"] is None


def test_the_stub_is_marked_and_the_real_host_is_never_read_as_one(tmp_path):
    assert trial.is_stub(TOOL / "stub" / "claude")
    other = tmp_path / "claude"
    other.write_bytes(b"\x7fELF" + os.urandom(64))
    assert not trial.is_stub(other)
