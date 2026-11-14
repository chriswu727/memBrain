"""The scenario production kit in its offline dry mode: launch.py with a fake session command, and freeze.py on a
synthetic git repository. No real session is launched, no model is called and no network is used."""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "evaluations" / "acceptance-kit"
PLANT = "ZQ-PLANTED-HELD-OUT-9c1e"
pytestmark = pytest.mark.skipif(shutil.which("git") is None or os.name == "nt", reason="needs git and POSIX modes")


def r4_scenario(prefix="S1", plant=PLANT, extra=""):
    """A synthetic scenario in the R4 shape: 15 sessions of 4 messages, 11 cases, no persona, no page actions."""
    sessions = []
    for number in range(15):
        day = 2 + number * 3
        month, day = (3, day) if day <= 31 else (4, day - 31)
        name = ["March", "April"][month - 3]
        sessions.append((f"s{number:02d}", [f"Today is Monday, {name} {day}, 20:00. {plant} {number}.",
                                            f"{plant} a", f"{plant} b", f"{plant} c"]))
    cases = [(f"s{number:02d}", 2, f"{prefix}{number + 1:02d}-case", f"Criteria: must {plant}.")
             for number in range(11)]
    return textwrap.dedent(f"""
        YEAR = 2026
        HOST = "You are a friendly assistant chatting with {plant}. Reply briefly and naturally."
        SESSIONS_LONG = {sessions!r}
        FACTS = "- {plant}"
        CASES = {cases!r}
        EXPECT_RECORDING_P = [("s03", 1, False), ("s03", 2, True)]
        {extra}
    """)


FAKE_SESSION = r'''
import json, os, pathlib, sys
workdir, role = pathlib.Path(sys.argv[1]), sys.argv[2]
(workdir / "environment.json").write_text(json.dumps(sorted(os.environ)))
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


def launch(kit, role, *extra, env=None, model="fixture-model-small", workdirs=None):
    command = [sys.executable, str(KIT / "launch.py"), "--role", role, "--key", "s1", "--private", str(kit["private"]),
               "--tool", "claude", "--model", model, "--allowed-models", str(kit["models"]),
               "--workdir-root", str(workdirs or kit["workdirs"]),
               "--session-command", f"{sys.executable} {kit['fake']} {{workdir}} {{role}} {kit['source']}", *extra]
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


def test_the_session_gets_no_credential_or_attempt_variable(kit):
    launch(kit, "author")
    names = json.loads((kit["workdirs"] / "s1-author-1" / "environment.json").read_text())
    assert not [name for name in names if name.endswith("_API_KEY") or name.startswith(("MEMBRAIN", "C5_", "PLANT"))]
    assert set(names) <= {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "LC_CTYPE",
                          "PWD", "SHLVL", "_"}


def test_a_reviewer_approval_writes_the_receipt_freeze_checks(kit):
    launch(kit, "author")
    done, result = launch(kit, "reviewer")
    assert done.returncode == 0, done.stderr
    assert (result["approved"], result["findings"], result["blocking"]) == (True, 1, 0)
    receipt = json.loads((kit["private"] / "control" / "s1-review-approved.json").read_text())
    scenario = kit["private"] / "s1" / "scenario_s1.py"
    assert receipt == {"key": "s1", "sha256": hashlib.sha256(scenario.read_bytes()).hexdigest(), "sessions": 15,
                       "turns": 60, "cases": 11, "approved": True, "findings": 1, "review_session": 1}
    assert (kit["private"] / "s1" / "findings-1.md").exists() and PLANT not in done.stdout


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


def test_a_session_directory_inside_a_checkout_is_refused(kit, tmp_path):
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


def test_the_default_session_commands_give_no_extra_directory_shell_or_web():
    commands = json.loads((KIT / "session-commands.json").read_text())
    claude, codex = commands["claude"], commands["codex"]
    assert "--add-dir" not in claude and "Bash" in claude.split("--disallowedTools")[1]
    assert "WebFetch" in claude and "WebSearch" in claude and "--strict-mcp-config" in claude
    assert "--setting-sources project" in claude
    assert "web_search=false" in codex and "workspace-write" in codex and "mcp_servers" in codex


def test_the_briefs_name_no_product_and_keep_the_r4_shape():
    for name in ("author-brief.md", "reviewer-brief.md", "fixer-brief.md"):
        text = (KIT / name).read_text()
        assert "membrain" not in text.lower() and "<membrain" not in text
    author = (KIT / "author-brief.md").read_text()
    for needle in ("Exactly 11", "60 to 66", "PERSONA", "PAGE_ACTIONS", "EXPECT_RECORDING_P", "persona-agnostic",
                   "Hoy es martes, 3 de marzo, 21:00.", "Heute ist Dienstag, der 3. März, 21:00.",
                   "今天是3月3日，星期二，21:00。", "at least one\n  hour apart"):
        assert needle in author, needle


# freeze.py on a synthetic repository ------------------------------------------------------------------------------

def git(repo, *arguments):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                    *arguments], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "evaluations" / "acceptance-review").mkdir(parents=True)
    (root / "src" / "pkg").mkdir(parents=True)
    for name in ("acceptance_review.py", "acceptance-attempt-driver.py", "acceptance_persona.py"):
        shutil.copyfile(ROOT / "evaluations" / name, root / "evaluations" / name)
    (root / "evaluations" / "acceptance-review" / "first.md").write_text("first\n")
    (root / "evaluations" / "notes.txt").write_text("not frozen\n")
    (root / "src" / "pkg" / "module.py").write_text("VALUE = 1\n")
    (root / "AGENTS.md").write_text("conventions\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    private = root / "evaluations" / ".maturity-heldout-zq"
    for key, prefix in (("s1", "S1"), ("s2", "S2")):
        (private / key).mkdir(parents=True)
        (private / key / f"scenario_{key}.py").write_text(r4_scenario(prefix))
    (private / "control").mkdir()
    return root


def receipt(repo, key, **changes):
    path = repo / "evaluations" / ".maturity-heldout-zq" / "control" / f"{key}-review-approved.json"
    scenario = repo / "evaluations" / ".maturity-heldout-zq" / key / f"scenario_{key}.py"
    path.write_text(json.dumps({"key": key, "sha256": hashlib.sha256(scenario.read_bytes()).hexdigest(),
                                "sessions": 15, "turns": 60, "cases": 11, "approved": True, "findings": 0,
                                **changes}))
    return f"evaluations/.maturity-heldout-zq/control/{key}-review-approved.json"


def freeze(repo, out, *extra, receipts=True):
    arguments = [sys.executable, str(KIT / "freeze.py"), "--repo", str(repo), "--attempt-id", "maturity-zq",
                 "--private-root", "evaluations/.maturity-heldout-zq", "--out", str(out)]
    for key in ("s1", "s2"):
        arguments += ["--scenario", f"{key}=evaluations/.maturity-heldout-zq/{key}/scenario_{key}.py"]
        if receipts:
            arguments += ["--receipt", f"{key}={receipt(repo, key)}"]
    done = subprocess.run([*arguments, *extra], capture_output=True, text=True, timeout=60)
    return done, json.loads(done.stdout.strip().splitlines()[-1])


def test_freeze_writes_a_manifest_both_validators_accept(repo, tmp_path):
    out = tmp_path / "manifest.json"
    done, result = freeze(repo, out)
    assert done.returncode == 0, done.stdout + done.stderr
    assert PLANT not in done.stdout + done.stderr
    manifest = json.loads(out.read_text())
    persona = json.loads(subprocess.run([sys.executable, str(ROOT / "evaluations" / "acceptance_persona.py"),
                                         "maturity-zq"], capture_output=True, text=True).stdout)
    assert manifest["persona"] == {"seed": "maturity-zq", "preset": persona["preset"]}
    assert result["persona"] == persona["preset"]
    assert manifest["order"] == ["s1", "s2"] and [pair["gate"] for pair in manifest["pairs"]] == ["R4"]
    frozen = set(manifest["files"])
    assert {"evaluations/acceptance_review.py", "evaluations/acceptance-attempt-driver.py",
            "evaluations/acceptance_persona.py", "evaluations/acceptance-review/first.md", "src/pkg/module.py",
            "AGENTS.md"} <= frozen
    assert "evaluations/notes.txt" not in frozen
    assert {f"evaluations/.maturity-heldout-zq/control/{key}-review-approved.json" for key in ("s1", "s2")} <= frozen
    assert [(item["key"], item["turns"], item["cases"]) for item in result["scenarios"]] == [("s1", 60, 11),
                                                                                             ("s2", 60, 11)]
    assert result["manifest_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert result["files"] == len(manifest["files"])
    done, again = freeze(repo, out)
    assert done.returncode == 2 and "written once" in again["refused"]


@pytest.mark.parametrize("damage", ["tracked change", "untracked elsewhere", "scenario tracked", "receipt hash",
                                    "receipt counts", "no receipt"])
def test_freeze_refuses_an_unclean_tree_or_a_receipt_that_does_not_approve_these_bytes(repo, tmp_path, damage):
    receipts = True
    if damage == "tracked change":
        (repo / "src" / "pkg" / "module.py").write_text("VALUE = 2\n")
    elif damage == "untracked elsewhere":
        (repo / "evaluations" / "stray.py").write_text("x = 1\n")
    elif damage == "scenario tracked":
        git(repo, "add", "-f", "evaluations/.maturity-heldout-zq/s1/scenario_s1.py")
        git(repo, "commit", "-q", "-m", "a held-out scenario committed by mistake")
    elif damage == "no receipt":
        receipts = False
    out = tmp_path / "manifest.json"
    if damage in ("receipt hash", "receipt counts"):
        arguments = [sys.executable, str(KIT / "freeze.py"), "--repo", str(repo), "--attempt-id", "maturity-zq",
                     "--private-root", "evaluations/.maturity-heldout-zq", "--out", str(out)]
        for key in ("s1", "s2"):
            changes = {} if key == "s1" else ({"sha256": "0" * 64} if damage == "receipt hash" else {"turns": 61})
            arguments += ["--scenario", f"{key}=evaluations/.maturity-heldout-zq/{key}/scenario_{key}.py",
                          "--receipt", f"{key}={receipt(repo, key, **changes)}"]
        done = subprocess.run(arguments, capture_output=True, text=True, timeout=60)
        result = json.loads(done.stdout.strip().splitlines()[-1])
    else:
        done, result = freeze(repo, out, receipts=receipts)
    assert done.returncode == 2 and "refused" in result and not out.exists()
    assert PLANT not in done.stdout + done.stderr


def test_freeze_without_receipts_is_marked_as_the_stub_rehearsal(repo, tmp_path):
    done, result = freeze(repo, tmp_path / "manifest.json", "--no-receipts", receipts=False)
    assert done.returncode == 0, done.stdout
    assert result["receipts"] == "none (stub rehearsal)"


def test_the_r4_precheck_refuses_persona_page_actions_stubs_and_the_wrong_size(tmp_path):
    def precheck(source):
        path = tmp_path / "scenario.py"
        path.write_text(source)
        done = subprocess.run([sys.executable, str(ROOT / "evaluations" / "c5-precheck.py"), "--r4", str(path)],
                              capture_output=True, text=True, timeout=60)
        assert PLANT not in done.stdout + done.stderr
        return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])

    code, summary = precheck(r4_scenario())
    assert code == 0 and summary["ok"] and summary["mode"] == "r4" and summary["cases"] == 11
    for extra, expected in (('PERSONA = {"name": "x"}', "r4_persona"),
                            ('PAGE_ACTIONS = [("s01", 0, {"do": "reset_mood"})]', "r4_page_actions"),
                            ("STUB_HOST = {}", "r4_stub_script"),
                            ("CASES = CASES[:10]", "r4_case_count"),
                            ("SESSIONS_LONG = SESSIONS_LONG[:-1]", "r4_turn_count"),
                            ('CASES = CASES[:10] + [("s99", 0, "S111-case", "Criteria: x")]', "r4_case_position"),
                            ('EXPECT_RECORDING_P = [("s03", 9, False)]', "r4_recording_position")):
        code, summary = precheck(r4_scenario(extra=extra))
        assert code == 1 and expected in summary["codes"], (extra, summary)
    # Without --r4 the C5 precheck still accepts a persona card and page actions.
    path = tmp_path / "c5.py"
    path.write_text(r4_scenario(extra='PERSONA = {"name": "x"}'))
    done = subprocess.run([sys.executable, str(ROOT / "evaluations" / "c5-precheck.py"), str(path)],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0
