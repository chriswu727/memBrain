"""The scenario production kit in its offline dry mode: launch.py with a fake session command, freeze.py on a
synthetic git repository, the literal-only scenario reader and the R4 precheck. No real session is launched, no
model is called and no network is used."""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "evaluations" / "acceptance-kit"
PLANT = "ZQ-PLANTED-HELD-OUT-9c1e"
pytestmark = pytest.mark.skipif(shutil.which("git") is None or os.name == "nt", reason="needs git and POSIX modes")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def r4_values(prefix="S1", plant=PLANT):
    """A synthetic scenario in the R4 shape: 15 sessions of 4 messages (each first message with the right weekday),
    11 cases, one off-the-record stretch, no persona, no page actions."""
    sessions = []
    for number in range(15):
        day = datetime.date(2026, 3, 2) + datetime.timedelta(days=3 * number)
        sessions.append((f"s{number:02d}", [
            f"Today is {day.strftime('%A')}, {day.strftime('%B')} {day.day}, 20:00. {plant} {number}.",
            f"{plant} a", f"{plant} b", f"{plant} c"]))
    cases = [(f"s{number:02d}", 2, f"{prefix}{number + 1:02d}-case", f"Criteria: must {plant}.")
             for number in range(11)]
    return {"YEAR": 2026, "HOST": f"You are a friendly assistant chatting with {plant}. Reply briefly and naturally.",
            "SESSIONS_LONG": sessions, "FACTS": f"- {plant}", "CASES": cases,
            "EXPECT_RECORDING_P": [("s03", 1, False), ("s03", 2, True)]}


def r4_scenario(prefix="S1", plant=PLANT, extra="", **changes):
    """The scenario file: literal assignments only, with ``changes`` replacing values (None drops a name), and
    ``extra`` appended as raw source."""
    values = {**r4_values(prefix, plant), **changes}
    return "".join(f"{name} = {value!r}\n" for name, value in values.items() if value is not None) + extra


FAKE_SESSION = r'''
import json, os, pathlib, sys
workdir, role = pathlib.Path(sys.argv[1]), sys.argv[2]
(workdir / "environment.json").write_text(json.dumps({name: os.environ[name] for name in sorted(os.environ)}))
scenario = pathlib.Path(sys.argv[3]).read_text()
print("fake session output that the lead never opens: " + scenario[:200])
if role == "author":
    assert (workdir / "assignment.md").read_text() and (workdir / "brief.md").read_text()
    (workdir / "scenario.py").write_text(scenario)
elif role == "reviewer":
    assert (workdir / "scenario.py").exists()
    (workdir / "findings.md").write_text("1. minor: " + scenario[:40])
    (workdir / "review.json").write_text(json.dumps({"approved": True, "findings": 1, "blocking": 0}))
else:
    assert (workdir / "findings.md").exists()
    (workdir / "scenario.py").write_text((workdir / "scenario.py").read_text() + "\n# fixed\n")
    (workdir / "fixes.json").write_text(json.dumps({"applied": 1}))
'''


@pytest.fixture
def kit(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    (private / "control").mkdir()
    models = private / "control" / "allowed-models.json"
    models.write_text(json.dumps(["fixture-model-small"]))
    fake = tmp_path / "fake_session.py"
    fake.write_text(FAKE_SESSION)
    source = tmp_path / "authored.py"
    source.write_text(r4_scenario())
    assignment = tmp_path / "assignment.md"
    assignment.write_text("Case prefix S1. Mainly English, one session in Spanish.\n")
    return {"private": private, "models": models, "fake": fake, "source": source, "assignment": assignment,
            "workdirs": tmp_path / "sessions"}


def launch(kit, role, *extra, env=None, model="fixture-model-small", workdirs=None, fake=True, tool="claude"):
    command = [sys.executable, str(KIT / "launch.py"), "--role", role, "--key", "s1", "--private", str(kit["private"]),
               "--tool", tool, "--model", model, "--allowed-models", str(kit["models"]),
               "--workdir-root", str(workdirs or kit["workdirs"]), "--python", sys.executable, *extra]
    if fake:
        command += ["--session-command", f"{sys.executable} {kit['fake']} {{workdir}} {{role}} {kit['source']}"]
    if role == "author":
        command += ["--assignment", str(kit["assignment"])]
    environment = {**os.environ, "OPENAI_API_KEY": "fixture-key", "DEEPSEEK_API_KEY": "fixture-key",
                   "MEMBRAIN_HOME": "/fixture", "C5_ATTEMPT_ID": "fixture", "PLANT_IN_SESSION": PLANT, **(env or {})}
    done = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=120)
    return done, json.loads(done.stdout.strip().splitlines()[-1])


def test_an_author_session_prints_only_hashes_and_counts_and_its_output_stays_private(kit):
    done, result = launch(kit, "author")
    assert done.returncode == 0, done.stderr
    assert PLANT not in done.stdout + done.stderr
    scenario = kit["private"] / "s1" / "scenario_s1.py"
    assert result["sha256"] == hashlib.sha256(scenario.read_bytes()).hexdigest()
    assert (result["sessions"], result["turns"], result["cases"]) == (15, 60, 11)
    assert result["precheck"] == {"ok": True, "codes": []}
    assert set(result) <= {"role", "key", "session", "session_exit", "sha256", "sessions", "turns", "cases", "loads",
                           "precheck", "produced"}
    assert stat.S_IMODE(scenario.stat().st_mode) == 0o600
    log = kit["private"] / "logs" / "s1-author-1.log"
    assert PLANT in log.read_text() and stat.S_IMODE(log.stat().st_mode) == 0o600  # Kept, never printed.


def test_the_session_gets_no_credential_and_an_unusable_memory_directory(kit):
    launch(kit, "author")
    seen = json.loads((kit["workdirs"] / "s1-author-1" / "environment.json").read_text())
    assert not [name for name in seen if name.endswith("_API_KEY") or name.startswith(("C5_", "PLANT"))]
    assert [name for name in seen if name.startswith("MEMBRAIN")] == ["MEMBRAIN_DIRECTORY"]
    assert set(seen) <= {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "LC_CTYPE",
                         "PWD", "SHLVL", "_", "MEMBRAIN_DIRECTORY"}
    nomemory = Path(seen["MEMBRAIN_DIRECTORY"])
    assert nomemory.is_dir() and not list(nomemory.iterdir()) and stat.S_IMODE(nomemory.stat().st_mode) == 0o500
    assert nomemory.parent == kit["workdirs"] and nomemory != kit["workdirs"] / "s1-author-1"


def test_the_plugin_hooks_resolve_their_installation_from_membrain_directory(tmp_path, monkeypatch):
    """The second barrier: the plugin's hook entry point and its MCP server find their installation through
    host.profile_directory, which honours MEMBRAIN_DIRECTORY."""
    from membrain import host, plugin

    monkeypatch.setenv("MEMBRAIN_DIRECTORY", str(tmp_path / "nomemory"))
    assert plugin.profile_directory(None) == host.profile_directory(None) == tmp_path / "nomemory"


def test_an_author_scenario_that_is_not_literal_is_never_run_and_its_text_never_printed(kit, tmp_path):
    marker = tmp_path / "ran"
    kit["source"].write_text(r4_scenario(extra=f"import os\nos.write(1, b'{PLANT}')\nopen({str(marker)!r}, 'w')\n"))
    done, result = launch(kit, "author")
    assert done.returncode == 0, done.stderr
    assert result["loads"] is False and result["precheck"] == {"ok": False, "codes": ["not_literal"]}
    assert PLANT not in done.stdout + done.stderr and not marker.exists()


def test_a_planted_precheck_code_is_never_relayed(kit, tmp_path, monkeypatch):
    launch_module = _load("launch_codes", KIT / "launch.py")
    path = tmp_path / "scenario.py"
    path.write_text(r4_scenario())
    planted = tmp_path / "planted-python"
    planted.write_text(f"#!/bin/sh\necho '{{\"ok\": false, \"codes\": [\"{PLANT}\", \"r4_persona\"]}}'\nexit 1\n")
    planted.chmod(0o755)
    result = launch_module.counts(path, planted)
    assert result["precheck"] == {"ok": False, "codes": ["r4_persona", "unknown_code"]}


def test_a_reviewer_approval_writes_the_receipt_freeze_checks(kit):
    launch(kit, "author")
    done, result = launch(kit, "reviewer")
    assert done.returncode == 0, done.stderr
    assert PLANT not in done.stdout
    assert (result["approved"], result["findings"], result["blocking"]) == (True, 1, 0)
    receipt = json.loads((kit["private"] / "control" / "s1-review-approved.json").read_text())
    scenario = kit["private"] / "s1" / "scenario_s1.py"
    assert receipt == {"key": "s1", "sha256": hashlib.sha256(scenario.read_bytes()).hexdigest(), "sessions": 15,
                       "turns": 60, "cases": 11, "approved": True, "findings": 1, "review_session": 1}
    assert (kit["private"] / "s1" / "findings-1.md").exists()


def test_a_fixer_keeps_the_earlier_version_and_reports_only_its_count(kit):
    launch(kit, "author")
    launch(kit, "reviewer")
    done, result = launch(kit, "fixer")
    assert done.returncode == 0, done.stderr
    assert result["applied"] == 1 and PLANT not in done.stdout
    assert (kit["private"] / "s1" / "scenario_s1.v1.py").exists()
    assert (kit["private"] / "s1" / "scenario_s1.py").read_text().endswith("# fixed\n")


def test_a_model_outside_the_leads_list_is_refused_before_anything_runs(kit):
    done, result = launch(kit, "author", model="fixture-model-largest")
    assert done.returncode == 2 and "allowed" in result["refused"]
    assert not kit["workdirs"].exists() or not list(kit["workdirs"].iterdir())


def test_a_session_directory_inside_a_checkout_or_the_private_root_is_refused(kit, tmp_path):
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    done, result = launch(kit, "author", workdirs=checkout / "sessions")
    assert done.returncode == 2 and "outside every checkout" in result["refused"]
    assert not (checkout / "sessions").exists()  # Refused before anything is created there.
    done, result = launch(kit, "author", workdirs=kit["private"] / "sessions")
    assert done.returncode == 2 and "outside the private root" in result["refused"]


def test_an_author_writes_a_key_once_and_a_reviewer_needs_a_scenario(kit):
    done, result = launch(kit, "reviewer")
    assert done.returncode == 2 and "no scenario" in result["refused"]
    launch(kit, "author")
    done, result = launch(kit, "author")
    assert done.returncode == 2 and "once" in result["refused"]


def session_args(tool="claude", accept_risk=None, role="author"):
    return types.SimpleNamespace(session_command=None, tool=tool, accept_risk=accept_risk, role=role,
                                 model="fixture-model-small")


def test_the_claude_session_argv_isolates_the_session_exactly():
    launch_module = _load("launch_argv", KIT / "launch.py")
    argv = launch_module.session_command(session_args(), Path("/work/s1-author-1"))
    assert argv == ["claude", "-p", launch_module.PROMPTS["author"], "--model", "fixture-model-small", "--safe-mode",
                    "--restricted", "--strict-mcp-config", "--no-session-persistence", "--tools", "Read,Write,Edit",
                    "--disallowedTools", "Bash,WebFetch,WebSearch,Task", "--permission-mode", "acceptEdits"]
    assert "--mcp-config" not in argv and "--add-dir" not in argv and "--bare" not in argv
    assert "--dangerously-skip-permissions" not in argv and "bypassPermissions" not in argv


def test_a_non_isolating_tool_is_refused_unless_its_risk_is_named(kit):
    launch_module = _load("launch_codex", KIT / "launch.py")
    with pytest.raises(launch_module.Refused, match="reads-outside-the-session-directory"):
        launch_module.session_command(session_args("codex"), Path("/work/x"))
    with pytest.raises(launch_module.Refused):
        launch_module.session_command(session_args("codex", accept_risk="something else"), Path("/work/x"))
    argv = launch_module.session_command(session_args("codex", accept_risk="reads-outside-the-session-directory"),
                                         Path("/work/x"))
    assert argv[:2] == ["codex", "exec"] and argv[-1] == launch_module.PROMPTS["author"]
    done, result = launch(kit, "author", fake=False, tool="codex")
    assert done.returncode == 2 and "does not isolate" in result["refused"]
    assert not kit["workdirs"].exists() or not list(kit["workdirs"].iterdir())


def test_the_briefs_name_no_product_and_keep_the_r4_shape():
    for name in ("author-brief.md", "reviewer-brief.md", "fixer-brief.md"):
        text = (KIT / name).read_text()
        assert "membrain" not in text.lower() and "<membrain" not in text
    author = (KIT / "author-brief.md").read_text()
    for needle in ("Exactly 11", "60 to 66", "PERSONA", "PAGE_ACTIONS", "EXPECT_RECORDING_P", "persona-agnostic",
                   "Hoy es martes, 3 de marzo, 21:00.", "Heute ist Dienstag, der 3. März, 21:00.",
                   "今天是3月3日，星期二，21:00。", "at least one\n  hour apart", "no f-strings", "consecutive turn"):
        assert needle in author, needle


# The literal-only scenario reader --------------------------------------------------------------------------------

literals = _load("scenario_literals_kit", ROOT / "evaluations" / "scenario_literals.py")


@pytest.mark.parametrize("source, code", [
    ("import os\n", "statement"), ("def f():\n    pass\n", "statement"), ("X = print('x')\n", "value"),
    ("A = 1\nB = A\n", "value"), ('X = f"{1}"\n', "value"), ("X = {**{}}\n", "value"), ("X, Y = 1, 2\n", "target"),
    ("X = 1\nX = 2\n", "duplicate"), ("X = (\n", "syntax"), ("X.y = 1\n", "target"), ("print('x')\n", "statement"),
])
def test_the_reader_refuses_anything_but_literal_assignments_without_running_it(tmp_path, source, code):
    path = tmp_path / "scenario.py"
    path.write_text(f'"""A docstring."""\n{source}')
    with pytest.raises(literals.NotLiteral) as refused:
        literals.read(path)
    assert refused.value.code == code and str(refused.value) == code


def test_the_reader_gives_the_same_values_as_loading_the_module(tmp_path):
    path = tmp_path / "scenario.py"
    path.write_text('"""Docstring."""\n' + r4_scenario() + "# a comment\n")
    loaded, read = _load("scenario_kit_loaded", path), literals.read(path)
    for name in ("YEAR", "HOST", "SESSIONS_LONG", "FACTS", "CASES", "EXPECT_RECORDING_P"):
        assert getattr(read, name) == getattr(loaded, name)
    assert literals.is_literal(ROOT / "evaluations" / "r4-practice-scenario.py")


# The R4 precheck ------------------------------------------------------------------------------------------------

def precheck(tmp_path, source, r4=True):
    path = tmp_path / "scenario.py"
    path.write_text(source)
    done = subprocess.run([sys.executable, str(ROOT / "evaluations" / "c5-precheck.py"), *(["--r4"] if r4 else []),
                           str(path)], capture_output=True, text=True, timeout=60)
    assert PLANT not in done.stdout + done.stderr
    return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])


def with_first(index, text):
    sessions = r4_values()["SESSIONS_LONG"]
    sessions[index] = (sessions[index][0], [text, *sessions[index][1][1:]])
    return sessions


def test_the_r4_precheck_passes_a_fit_scenario(tmp_path):
    code, summary = precheck(tmp_path, r4_scenario())
    assert code == 0 and summary["ok"] and summary["mode"] == "r4" and summary["cases"] == 11


@pytest.mark.parametrize("changes, extra, expected", [
    ({"PERSONA": {"name": "x"}}, "", "r4_persona"),
    ({"PAGE_ACTIONS": [("s01", 0, {"do": "reset_mood"})]}, "", "r4_page_actions"),
    ({"STUB_HOST": {}}, "", "r4_stub_script"),
    ({"CASES": r4_values()["CASES"][:10]}, "", "r4_case_count"),
    ({"SESSIONS_LONG": r4_values()["SESSIONS_LONG"][:-1]}, "", "r4_turn_count"),
    ({"CASES": r4_values()["CASES"][:10] + [("s99", 0, "S111-case", "Criteria: x")]}, "", "r4_case_position"),
    ({"EXPECT_RECORDING_P": [("s03", 9, False), ("s03", 10, True)]}, "", "r4_recording_position"),
    ({"EXPECT_RECORDING_P": None}, "", "r4_recording_missing"),
    ({}, "import os\n", "r4_not_literal"),
    ({"SESSIONS_LONG": with_first(4, f"Today is Friday, March 14, 20:00. {PLANT}")}, "", "weekday_mismatch"),
], ids=["persona", "page actions", "stub", "case count", "turn count", "case position", "recording position",
        "no recording stretch", "not literal", "wrong weekday"])
def test_the_r4_precheck_refuses_each_unfit_scenario_with_its_code(tmp_path, changes, extra, expected):
    code, summary = precheck(tmp_path, r4_scenario(extra=extra, **changes))
    assert code == 1 and expected in summary["codes"], summary


@pytest.mark.parametrize("entries", [
    [("s03", 1, False), ("s04", 0, True)],  # Split across sessions.
    [("s03", 0, False), ("s03", 2, True)],  # A gap: turn 1 undeclared would stop a live arm.
    [("s03", 1, False), ("s03", 2, False)],  # No resume request.
    [("s03", 1, True), ("s03", 2, False)],  # The resume before the stretch.
    [("s03", 2, True)],  # A resume with nothing off the record.
    [("s03", 2, False), ("s03", 1, True)],  # Out of order.
    [("s03", 1, False), ("s03", 2, True), ("s03", 3, False)],  # The stretch goes on after the resume.
], ids=["two sessions", "gap", "no resume", "resume first", "resume only", "out of order", "after the resume"])
def test_the_r4_precheck_refuses_a_recording_stretch_the_harness_would_stop_on(tmp_path, entries):
    code, summary = precheck(tmp_path, r4_scenario(EXPECT_RECORDING_P=entries))
    assert code == 1 and summary["codes"] == ["r4_recording_shape"], summary


@pytest.mark.parametrize("first, ok", [
    ("Today is Thursday, March 5, 20:00.", True), ("Today is Friday, March 5, 20:00.", False),
    ("Hoy es jueves, 5 de marzo, 20:00.", True), ("Hoy es miércoles, 5 de marzo, 20:00.", False),
    ("Heute ist Donnerstag, der 5. März, 20:00.", True), ("Heute ist Freitag, der 5. März, 20:00.", False),
    ("今天是3月5日，星期四，20:00。", True), ("今天是3月5日，星期三，20:00。", False),
    ("今天是3月8日，星期天，20:00。", True), ("今天是3月8日，周日，20:00。", True), ("今天是3月8日，周六，20:00。", False),
])
def test_every_stated_weekday_must_be_its_dates_weekday(tmp_path, first, ok):
    sessions = [("s01", [f"{first} {PLANT}"]), ("s02", ["Today is Monday, March 30, 20:00. x"])]
    code, summary = precheck(tmp_path, r4_scenario(SESSIONS_LONG=sessions), r4=False)
    assert ("weekday_mismatch" in summary["codes"]) is (not ok), summary


def test_an_r4_session_must_state_a_weekday(tmp_path):
    code, summary = precheck(tmp_path, r4_scenario(SESSIONS_LONG=with_first(0, f"今天是3月2日 20:00。{PLANT}")))
    assert code == 1 and "r4_no_weekday" in summary["codes"]


def test_the_public_practice_scenarios_state_their_weekdays_right(tmp_path):
    for name in ("c5-practice-scenario.py", "r4-practice-scenario.py"):
        done = subprocess.run([sys.executable, str(ROOT / "evaluations" / "c5-precheck.py"),
                               str(ROOT / "evaluations" / name)], capture_output=True, text=True, timeout=60)
        assert done.returncode == 0 and "weekday_mismatch" not in done.stdout, name


def test_the_c5_precheck_without_r4_still_accepts_a_persona_card(tmp_path):
    code, _ = precheck(tmp_path, r4_scenario(PERSONA={"name": "x"}), r4=False)
    assert code == 0


# freeze.py on a synthetic repository ------------------------------------------------------------------------------

def git(repo, *arguments):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                    *arguments], check=True, capture_output=True)


PRIVATE = "evaluations/.maturity-heldout-zq"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "evaluations" / "acceptance-review").mkdir(parents=True)
    (root / "src" / "pkg").mkdir(parents=True)
    for name in ("acceptance_review.py", "acceptance-attempt-driver.py", "acceptance_persona.py", "c5-precheck.py",
                 "c5-harness.py", "scenario_literals.py"):
        shutil.copyfile(ROOT / "evaluations" / name, root / "evaluations" / name)
    (root / "evaluations" / "acceptance-review" / "first.md").write_text("first\n")
    (root / "evaluations" / "notes.txt").write_text("not frozen\n")
    (root / "src" / "pkg" / "module.py").write_text("VALUE = 1\n")
    (root / "AGENTS.md").write_text("conventions\n")
    (root / "evaluations" / "binding.md").write_text("Attempt `maturity-zq` uses the new execution clone.\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    private = root / PRIVATE
    for key, prefix in (("s1", "S1"), ("s2", "S2")):
        (private / key).mkdir(parents=True)
        (private / key / f"scenario_{key}.py").write_text(r4_scenario(prefix))
    (private / "control").mkdir()
    (private / "control" / "allowed-models.json").write_text(json.dumps(["fixture-model-small"]))
    return root


def receipt(repo, key, **changes):
    path = repo / PRIVATE / "control" / f"{key}-review-approved.json"
    scenario = repo / PRIVATE / key / f"scenario_{key}.py"
    path.write_text(json.dumps({"key": key, "sha256": hashlib.sha256(scenario.read_bytes()).hexdigest(),
                                "sessions": 15, "turns": 60, "cases": 11, "approved": True, "findings": 0,
                                **changes}))
    return f"{PRIVATE}/control/{key}-review-approved.json"


def freeze(repo, out, *extra, receipts=True, scenarios=None, receipt_changes=None, allowed=True):
    arguments = [sys.executable, str(KIT / "freeze.py"), "--repo", str(repo), "--attempt-id", "maturity-zq",
                 "--private-root", PRIVATE, "--out", str(out), "--python", sys.executable]
    if allowed:
        arguments += ["--allowed-models", f"{PRIVATE}/control/allowed-models.json"]
    for key in ("s1", "s2"):
        path = (scenarios or {}).get(key, f"{PRIVATE}/{key}/scenario_{key}.py")
        arguments += ["--scenario", f"{key}={path}"]
        if receipts:
            arguments += ["--receipt", f"{key}={receipt(repo, key, **((receipt_changes or {}).get(key, {})))}"]
    done = subprocess.run([*arguments, *extra], capture_output=True, text=True, timeout=120)
    lines = done.stdout.strip().splitlines()
    return done, json.loads(lines[-1]) if lines else {}


def test_freeze_writes_a_manifest_both_validators_accept(repo, tmp_path):
    out = tmp_path / "manifest.json"
    done, result = freeze(repo, out, "--binding", "evaluations/binding.md")
    assert done.returncode == 0, done.stdout + done.stderr
    assert PLANT not in done.stdout + done.stderr
    manifest = json.loads(out.read_text())
    persona = _load("acceptance_persona_kit", ROOT / "evaluations" / "acceptance_persona.py")
    assert manifest["persona"] == {"seed": "maturity-zq", "preset": persona.draw("maturity-zq")}
    assert result["persona"] == persona.draw("maturity-zq") and "practice" not in manifest
    assert manifest["order"] == ["s1", "s2"] and [pair["gate"] for pair in manifest["pairs"]] == ["R4"]
    frozen = set(manifest["files"])
    assert {"evaluations/acceptance_review.py", "evaluations/acceptance-attempt-driver.py",
            "evaluations/acceptance_persona.py", "evaluations/scenario_literals.py", "evaluations/c5-precheck.py",
            "evaluations/acceptance-review/first.md", "src/pkg/module.py", "AGENTS.md",
            f"{PRIVATE}/control/allowed-models.json"} <= frozen
    assert "evaluations/notes.txt" not in frozen
    assert {f"{PRIVATE}/control/{key}-review-approved.json" for key in ("s1", "s2")} <= frozen
    assert [(item["key"], item["turns"], item["cases"]) for item in result["scenarios"]] == [("s1", 60, 11),
                                                                                             ("s2", 60, 11)]
    assert result["manifest_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert result["files"] == len(manifest["files"])
    done, again = freeze(repo, out)
    assert done.returncode == 2 and "written once" in again["refused"]


@pytest.mark.parametrize("damage", ["tracked change", "untracked elsewhere", "scenario tracked", "receipt hash",
                                    "receipt counts", "no receipt", "no allowed models", "allowed models malformed",
                                    "precheck fails", "not literal", "binding names another attempt",
                                    "binding not committed"])
def test_freeze_refuses_an_unfit_tree_scenario_receipt_or_control(repo, tmp_path, damage):
    out, options, extra = tmp_path / "manifest.json", {}, []
    s2 = repo / PRIVATE / "s2" / "scenario_s2.py"
    if damage == "tracked change":
        (repo / "src" / "pkg" / "module.py").write_text("VALUE = 2\n")
    elif damage == "untracked elsewhere":
        (repo / "evaluations" / "stray.py").write_text("x = 1\n")
    elif damage == "scenario tracked":
        git(repo, "add", "-f", f"{PRIVATE}/s1/scenario_s1.py")
        git(repo, "commit", "-q", "-m", "a held-out scenario committed by mistake")
    elif damage == "receipt hash":
        options["receipt_changes"] = {"s2": {"sha256": "0" * 64}}
    elif damage == "receipt counts":
        options["receipt_changes"] = {"s2": {"turns": 61}}
    elif damage == "no receipt":
        options["receipts"] = False
    elif damage == "no allowed models":
        options["allowed"] = False
    elif damage == "allowed models malformed":
        (repo / PRIVATE / "control" / "allowed-models.json").write_text("{}")
    elif damage == "precheck fails":
        s2.write_text(r4_scenario("S2", SESSIONS_LONG=with_first(4, f"Today is Friday, March 14, 20:00. {PLANT}")))
    elif damage == "not literal":
        s2.write_text(r4_scenario("S2", extra=f"raise ValueError({PLANT!r})\n"))
    elif damage == "binding names another attempt":
        (repo / "evaluations" / "binding.md").write_text("Attempt `maturity-other` uses the clone.\n")
        git(repo, "commit", "-q", "-am", "another binding")
        extra = ["--binding", "evaluations/binding.md"]
    else:
        (repo / PRIVATE / "binding.md").write_text("Attempt `maturity-zq`.\n")
        extra = ["--binding", f"{PRIVATE}/binding.md"]
    done, result = freeze(repo, out, *extra, **options)  # A missing --allowed-models is an argparse refusal.
    assert done.returncode == 2, done.stdout + done.stderr
    assert not out.exists() and PLANT not in done.stdout + done.stderr and "Traceback" not in done.stderr
    if damage != "no allowed models":
        assert "refused" in result
    if damage == "precheck fails":
        assert result["refused"] == "scenario s2 fails the R4 precheck: weekday_mismatch"


def test_freeze_without_receipts_takes_only_practice_copies_and_marks_the_manifest(repo, tmp_path):
    done, result = freeze(repo, tmp_path / "refused.json", "--no-receipts", receipts=False)
    assert done.returncode == 2 and "practice copies only" in result["refused"]
    for key in ("s1", "s2"):
        (repo / PRIVATE / key / f"r4_practice_{key}.py").write_text(r4_scenario(key.upper()))
    practice = {key: f"{PRIVATE}/{key}/r4_practice_{key}.py" for key in ("s1", "s2")}
    out = tmp_path / "manifest.json"
    done, result = freeze(repo, out, "--no-receipts", receipts=False, scenarios=practice)
    assert done.returncode == 0, done.stdout
    assert result["receipts"] == "none (stub rehearsal)" and json.loads(out.read_text())["practice"] is True
    done, result = freeze(repo, tmp_path / "again.json", scenarios=practice)
    assert done.returncode == 2 and "never frozen as a held-out" in result["refused"]
