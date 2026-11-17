"""C5 scenario review that converges (2026-11-17, after the public authoring diagnostic): the precheck's new codes
(short messages, reaction openings, --require, one case per item), the assignment's coverage line, launch.py's
one full review and verifier rounds in its offline dry mode, freeze.py's union check, and R4 launches, R4 precheck
and R4 freeze unchanged. No service, database, session or model is started, and no network is used."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_acceptance_kit import r4_scenario, r4_values
from test_c5_kit import (
    PLANT,
    PRIVATE,
    REQUIRED_ONLY,
    SCENARIO_ONE,
    SCENARIO_TWO,
    _load,
    _sessions_with,
    c5_scenario,
    c5_values,
    coverage_line,
    freeze,
    run_precheck,
    split_values,
)
from test_c5_kit import repo as _repo

repo = _repo  # The fixture of test_c5_kit, by the name the tests below take.
ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS = ROOT / "evaluations"
KIT = EVALUATIONS / "acceptance-kit"
pytestmark = pytest.mark.skipif(shutil.which("git") is None or os.name == "nt", reason="needs git and POSIX modes")
precheck = _load("c5_precheck_for_converge_tests", EVALUATIONS / "c5-precheck.py")
assignment = _load("c5_assignment_for_converge_tests", KIT / "assignment.py")


# The precheck: messages that stand on their own -----------------------------------------------------------------------

@pytest.mark.parametrize("text, first, short", [
    ("Fair enough.", False, True),  # 12: the diagnostic's longest bare reaction.
    ("x" * 15, False, True),
    ("x" * 16, False, False),
    ("Long day at work.", False, False),  # 17: the shortest ordinary message of the public practice scenarios.
    ("Today is Monday, March 30, 20:00. Hi there!", True, True),  # The date and time do not count.
    ("Today is Monday, March 30, 20:00. Hi! Long day, I'm wiped.", True, False),
    ("Heute ist Dienstag, der 3. März, 21:00. Klingt gut.", True, True),  # The date's own period is not the end.
    ("好的。", False, True),
    ("有道理啊。", False, True),  # 5 characters, mostly CJK.
    ("要不要换盆？", False, False),  # 6: the shortest ordinary message of the public Chinese scenarios.
    ("今天是3月3日，星期二，21:00。好的。", True, True),
])
def test_the_short_message_thresholds(text, first, short):
    assert precheck.short_message(text, first) is short
    assert (precheck.SHORT_MESSAGE, precheck.SHORT_MESSAGE_CJK) == (16, 6)


# The reply-dependent openings of the public diagnostic's first version, and the three its second reviewer found.
DIAGNOSTIC_REACTIONS = [
    "Fair enough. Anyway, I'm trying a new curry recipe tonight.", "Klingt gut. Ich probiere es am Wochenende aus.",
    "Good shout. I'll have a look at the market on Saturday.", "Ha, fair enough. I'll tell her tomorrow.",
    "Ha. Right, I'm off to finish the cardboard bike.", "Cool. Anyway, off to make a massive breakfast.",
    "Thanks. Speak soon!", "Ha, I'm calling that our official pun contest, I'll win the rematch.",
    "好的。哦对了，生日会改到下午两点。", "Haha, true. Anyway, bed.", "Thank you, that helps a lot.",
]
ORDINARY = [
    "Thank you for staying with me through that, it was a horrible night.",
    "Haircut tomorrow, finally.", "Cooler weather today, thank goodness.", "Thanksgiving plans are chaos.",
    "Halfway through the training plan!", "Yes, please do that from now on.", "Danach gehe ich schlafen.",
    "Good news: I got the flat!", "I'll have a look at the market on Saturday.", "好久没下雨了。",
]


@pytest.mark.parametrize("text", DIAGNOSTIC_REACTIONS)
def test_a_reaction_opening_is_found(text):
    assert precheck.reaction_opening(text, False)


@pytest.mark.parametrize("text", ORDINARY)
def test_an_ordinary_opening_is_not_a_reaction(text):
    assert not precheck.reaction_opening(text, False)


def _messages(path):
    literals = _load("scenario_literals_for_converge", EVALUATIONS / "scenario_literals.py")
    return [(session, turn, text) for session, turns in literals.read(path).SESSIONS_LONG
            for turn, text in enumerate(turns)]


def test_the_public_practice_scenarios_have_no_short_message_and_one_reaction():
    for name in ("c5-practice-scenario.py", "r4-practice-scenario.py"):
        assert not [(s, t) for s, t, text in _messages(EVALUATIONS / name) if precheck.short_message(text, t == 0)]
    # The C5 practice (a stub rehearsal script, never prechecked in --c5 mode) thanks for a reply once.
    assert [(s, t) for s, t, text in _messages(EVALUATIONS / "c5-practice-scenario.py")
            if precheck.reaction_opening(text, t == 0)] == [("s12-yes", 2)]
    assert not [(s, t) for s, t, text in _messages(EVALUATIONS / "r4-practice-scenario.py")
                if precheck.reaction_opening(text, t == 0)]


def test_the_codes_give_the_position_and_the_declared_yes_is_exempt(tmp_path):
    sessions = _sessions_with(15, c5_values()["SESSIONS_LONG"][15][1][:2] + ["Ha.", "Cool. Off to bed now, night!"])
    code, summary, output = run_precheck(tmp_path, c5_scenario(SESSIONS_LONG=sessions))
    assert code == 1 and summary["codes"] == ["c5_reaction_opening", "c5_short_message"]
    assert "FAIL code=c5_short_message at=15:2" in output and "FAIL code=c5_reaction_opening at=15:3" in output
    values = c5_values()  # The declared yes (s03, 2) may answer the companion's question.
    values["SESSIONS_LONG"] = _sessions_with(3, values["SESSIONS_LONG"][3][1][:2] + ["Sounds good, yes please.",
                                                                                     values["SESSIONS_LONG"][3][1][3]])
    code, summary, output = run_precheck(tmp_path, c5_scenario(values=values))
    assert code == 0, output


# The precheck: --require and one case per item ------------------------------------------------------------------------

def test_each_scenario_of_the_split_passes_with_its_items_only(tmp_path):
    for part, items in ((1, SCENARIO_ONE), (2, SCENARIO_TWO)):
        code, summary, output = run_precheck(tmp_path, c5_scenario(values=split_values(part)), require=items)
        assert code == 0, output
        assert (summary["coverage"], summary["requirements"]) == (len(items), len(items))
        assert f"coverage {len(items)} of {len(items)}" in output
    assert set(SCENARIO_ONE) | set(SCENARIO_TWO) == set(precheck.COVERAGE_FIELDS)
    assert not set(SCENARIO_ONE) & set(SCENARIO_TWO)


def _one(**entries):
    table = dict(split_values(1)["COVERAGE"])
    for name, value in entries.items():
        if value is None:
            table.pop(name)
        else:
            table[name] = value
    return table


UNFIT_REQUIRED = {
    "an item of the line left out": (_one(absence=None), "c5_coverage_missing", "field=absence"),
    "an item not on the line": ({**_one(), "reset": c5_values()["COVERAGE"]["reset"]}, "c5_coverage_not_required",
                                "field=reset"),
    "a case serving two items": (_one(feelings_question={"case": c5_values()["CASES"][1][2]}),
                                 "c5_coverage_shared_case", "field=feelings_question part=case"),
    "a boundary case that is also a feeling's": (_one(boundary_in_conversation={
        "asked": ("s01", 2), "case": c5_values()["CASES"][4][2]}), "c5_coverage_shared_case",
        "field=boundary_in_conversation part=case"),
}


@pytest.mark.parametrize("table, expected, where", list(UNFIT_REQUIRED.values()), ids=list(UNFIT_REQUIRED))
def test_the_require_list_refuses_each_unfit_table(tmp_path, table, expected, where):
    code, summary, output = run_precheck(tmp_path, c5_scenario(values=split_values(1), COVERAGE=table),
                                         require=SCENARIO_ONE)
    assert code == 1 and expected in summary["codes"], output
    assert f"FAIL code={expected} {where}" in output


def test_the_required_only_codes_are_the_ones_tested_here():
    assert {expected for _, expected, _ in UNFIT_REQUIRED.values()} - {"c5_coverage_missing"} == REQUIRED_ONLY


def test_without_require_all_thirteen_are_required_and_cases_may_be_shared(tmp_path):
    code, summary, output = run_precheck(tmp_path, c5_scenario())  # c5_values shares three cases.
    assert code == 0 and summary["requirements"] == 13, output
    code, summary, _ = run_precheck(tmp_path, c5_scenario(values=split_values(1)))
    assert code == 1 and summary["codes"] == ["c5_coverage_missing"]


@pytest.mark.parametrize("arguments", [["--c5", "--require", "mood,mood"], ["--c5", "--require", "moods"],
                                       ["--c5", "--require", ""], ["--r4", "--require", "mood"],
                                       ["--require", "mood"], ["--c5", "--require"]])
def test_a_malformed_require_is_a_usage_error(tmp_path, arguments):
    path = tmp_path / "scenario.py"
    path.write_text(c5_scenario())
    done = subprocess.run([sys.executable, str(EVALUATIONS / "c5-precheck.py"), *arguments, str(path)],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 2 and json.loads(done.stdout) == {"ok": False, "error": "usage"}


# The assignment's coverage line -----------------------------------------------------------------------------------------

def test_the_coverage_line_is_parsed_strictly():
    text = "# Assignment\n\n- Case prefix: `D2`.\n- Coverage items: mood, absence, stated_feeling\n"
    assert assignment.required_items(text) == ("mood", "absence", "stated_feeling")
    assert assignment.required_items("Coverage items: switch") == ("switch",)
    assert assignment.coverage_fields() == tuple(precheck.COVERAGE_FIELDS)


@pytest.mark.parametrize("text, reason", [
    ("- Case prefix: `D2`.\n", "no 'Coverage items:' line"),
    ("- Coverage items: mood\n- Coverage items: absence\n", "more than one"),
    ("- Coverage items: mood\nThe coverage items above are yours.\n", "more than one"),
    ("- Coverage items: mood, absence.\n", "not of the form"),
    ("- Coverage items: mood,absence\n", "not of the form"),
    ("- Coverage items:  mood\n", "not of the form"),
    ("* Coverage items: mood\n", "not of the form"),
    ("- coverage items: mood\n", "not of the form"),
    ("- Coverage items: mood, emoji\n", "not a COVERAGE item"),
    ("- Coverage items: mood, absence, mood\n", "twice"),
])
def test_a_malformed_coverage_line_is_refused_with_a_fixed_reason(text, reason):
    with pytest.raises(assignment.AssignmentError, match=reason) as caught:
        assignment.required_items(text)
    assert "emoji" not in str(caught.value)  # A fixed reason, never the file's words.


# launch.py: one full review, then verifications ----------------------------------------------------------------------

FAKE = r'''
import json, pathlib, shutil, sys
workdir, role, plan_path = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
plan = json.loads(plan_path.read_text())
(workdir / "received.json").write_text(json.dumps(sorted(path.name for path in workdir.iterdir())))
if role == "author":
    shutil.copyfile(plan["authored"], workdir / "scenario.py")
elif role in ("reviewer", "verifier"):
    counter = plan_path.with_name("verdicts.count")
    number = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(number + 1))
    approved, blocking = plan["verdicts"][number]
    heading = "Findings" if role == "reviewer" else "Verification"
    (workdir / "findings.md").write_text(f"# {heading}\n\n## Blocking\n" + ("None.\n" if not blocking else "B1. x\n"))
    (workdir / "review.json").write_text(json.dumps({"approved": approved, "findings": blocking,
                                                     "blocking": blocking}))
else:
    replacement = plan.get("fixed")
    text = pathlib.Path(replacement).read_text() if replacement else (workdir / "scenario.py").read_text()
    counter = plan_path.with_name("fixes.count")
    number = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(number + 1))
    (workdir / "scenario.py").write_text(text + f"\n# fixed {number}\n")
    (workdir / "fixes.json").write_text(json.dumps({"applied": 1, "fixes": [{"finding": "B1", "change": "x"}]}))
'''


@pytest.fixture
def kit(tmp_path):
    (tmp_path / "private" / "control").mkdir(parents=True, mode=0o700)
    (tmp_path / "private" / "control" / "allowed-models.json").write_text(json.dumps(["fixture-model-small"]))
    (tmp_path / "fake.py").write_text(FAKE)
    (tmp_path / "authored.py").write_text(c5_scenario(values=split_values(1)))
    (tmp_path / "assignment.md").write_text("- Case prefix: `C1`.\n" + coverage_line(SCENARIO_ONE))
    plan(tmp_path, verdicts=[])
    return tmp_path


def plan(kit, **values):
    (kit / "plan.json").write_text(json.dumps({"authored": str(kit / "authored.py"), **values}))


def launch(kit, role, *extra, gate="C5", assignment_file=None):
    command = [sys.executable, str(KIT / "launch.py"), "--role", role, "--key", "c1", "--private",
               str(kit / "private"), "--tool", "claude", "--model", "fixture-model-small", "--allowed-models",
               str(kit / "private" / "control" / "allowed-models.json"), "--workdir-root", str(kit / "sessions"),
               "--python", sys.executable, *(["--gate", gate] if gate else []), "--session-command",
               f"{sys.executable} {kit / 'fake.py'} {{workdir}} {{role}} {kit / 'plan.json'}", *extra]
    if role == "author":
        command += ["--assignment", str(assignment_file or kit / "assignment.md")]
    done = subprocess.run(command, capture_output=True, text=True, timeout=120)
    assert PLANT not in done.stdout + done.stderr
    return done, json.loads(done.stdout.strip().splitlines()[-1])


def received(kit, role, number):
    return json.loads((kit / "sessions" / f"c1-{role}-{number}" / "received.json").read_text())


def test_one_full_review_then_verifications_until_approved(kit):
    folder = kit / "private" / "c1"
    plan(kit, verdicts=[[False, 2], [False, 1], [True, 0]])
    done, result = launch(kit, "author")
    assert done.returncode == 0 and result["precheck"] == {"ok": True, "codes": []}, done.stdout
    assert (folder / "assignment.md").read_bytes() == (kit / "assignment.md").read_bytes()
    done, result = launch(kit, "verifier")
    assert done.returncode == 2 and "full review first" in result["refused"]

    done, result = launch(kit, "reviewer")
    assert (result["approved"], result["blocking"], result["round"]) == (False, 2, 1)
    assert received(kit, "reviewer", 1) == ["assignment.md", "author-brief.md", "brief.md", "scenario.py"]
    assert (kit / "sessions" / "c1-reviewer-1" / "author-brief.md").read_text() == \
        (KIT / "c5-author-brief.md").read_text()
    assert (folder / "findings-1.md").exists() and (folder / "review-1.json").exists()
    done, result = launch(kit, "reviewer")
    assert done.returncode == 2 and "already has its full review" in result["refused"]
    done, result = launch(kit, "verifier")
    assert done.returncode == 2 and "already reviewed or verified" in result["refused"]

    done, result = launch(kit, "fixer")
    assert result["findings_from"] == "reviewer" and result["precheck"]["ok"]
    assert received(kit, "fixer", 1) == ["assignment.md", "author-brief.md", "brief.md", "findings.md", "scenario.py"]
    assert (kit / "sessions" / "c1-fixer-1" / "findings.md").read_bytes() == (folder / "findings-1.md").read_bytes()
    done, result = launch(kit, "fixer")
    assert done.returncode == 2 and "earlier version" in result["refused"]

    done, result = launch(kit, "verifier")
    assert (result["approved"], result["round"]) == (False, 2) and "receipt_sha256" not in result
    workdir = kit / "sessions" / "c1-verifier-1"
    assert received(kit, "verifier", 1) == ["assignment.md", "author-brief.md", "brief.md", "findings-1.md",
                                            "fixes-1.json", "rounds.md", "scenario.py"]
    assert (workdir / "brief.md").read_text() == (KIT / "c5-verifier-brief.md").read_text()
    assert (workdir / "findings-1.md").read_bytes() == (folder / "findings-1.md").read_bytes()
    assert (workdir / "scenario.py").read_bytes() == (folder / "scenario_c1.py").read_bytes()
    table = (workdir / "rounds.md").read_text()
    assert "full review (round 1) | findings-1.md | not approved, 2 blocking" in table
    assert "a fixer applied the findings of round 1 | fixes-1.json | applied 1" in table and PLANT not in table

    done, result = launch(kit, "fixer")
    assert result["findings_from"] == "verifier"
    assert (kit / "sessions" / "c1-fixer-2" / "findings.md").read_bytes() == (folder / "findings-2.md").read_bytes()
    done, result = launch(kit, "verifier")
    assert (result["approved"], result["blocking"], result["round"]) == (True, 0, 3)
    assert received(kit, "verifier", 2) == ["assignment.md", "author-brief.md", "brief.md", "findings-1.md",
                                            "findings-2.md", "fixes-1.json", "fixes-2.json", "rounds.md",
                                            "scenario.py"]
    receipt = json.loads((kit / "private" / "control" / "c1-review-approved.json").read_text())
    current = (folder / "scenario_c1.py").read_bytes()
    assert receipt["sha256"] == hashlib.sha256(current).hexdigest() == result["reviewed_sha256"]
    assert (receipt["gate"], receipt["role"], receipt["round"], receipt["cases"]) == ("C5", "verifier", 3, 11)
    done, result = launch(kit, "fixer")
    assert done.returncode == 2 and "approved" in result["refused"]
    ledger = json.loads((folder / "rounds.json").read_text())
    assert [step["kind"] for step in ledger["steps"]] == ["author", "review", "fix", "verification", "fix",
                                                          "verification"]
    assert oct((folder / "rounds.json").stat().st_mode & 0o777) == "0o600"


def test_at_most_three_verification_rounds(kit):
    plan(kit, verdicts=[[False, 1]] * 4)
    launch(kit, "author")
    launch(kit, "reviewer")
    for _ in range(3):
        assert launch(kit, "fixer")[0].returncode == 0
        assert launch(kit, "verifier")[1]["approved"] is False
    launch(kit, "fixer")
    done, result = launch(kit, "verifier")
    assert done.returncode == 2 and "3 verification rounds" in result["refused"]


def test_a_failing_version_gets_a_fixer_before_any_review_or_verification(kit):
    failing = kit / "failing.py"
    values = split_values(1)
    values["COVERAGE"]["absence"] = {"case": values["CASES"][0][2]}  # Shared with mood, and no absence there.
    failing.write_text(c5_scenario(values=values))
    plan(kit, authored=str(failing), verdicts=[[False, 1]])
    done, result = launch(kit, "author")
    assert not result["precheck"]["ok"] and "c5_coverage_shared_case" in result["precheck"]["codes"]
    done, result = launch(kit, "reviewer")
    assert done.returncode == 2 and "fails the precheck" in result["refused"]
    plan(kit, authored=str(failing), fixed=str(kit / "authored.py"), verdicts=[[False, 1]])
    done, result = launch(kit, "fixer")
    assert result["findings_from"] == "precheck" and result["precheck"]["ok"]
    done, result = launch(kit, "reviewer")
    assert result["round"] == 1
    plan(kit, authored=str(failing), fixed=str(failing), verdicts=[[False, 1]])
    done, result = launch(kit, "fixer")  # The reviewer's findings applied, badly: the version fails again.
    assert not result["precheck"]["ok"]
    done, result = launch(kit, "verifier")
    assert done.returncode == 2 and "fails the precheck" in result["refused"]


def test_a_c5_launch_needs_a_well_formed_coverage_line_and_keeps_the_authors(kit):
    (kit / "plain.md").write_text("Case prefix C1. Mainly English, one session in German.\n")
    done, result = launch(kit, "author", assignment_file=kit / "plain.md")
    assert done.returncode == 2 and result["refused"] == "the assignment has no 'Coverage items:' line"
    assert not (kit / "sessions").exists()
    (kit / "bad.md").write_text("- Coverage items: mood, emoji\n")
    done, result = launch(kit, "author", assignment_file=kit / "bad.md")
    assert done.returncode == 2 and "not a COVERAGE item" in result["refused"]
    plan(kit, verdicts=[[True, 0]])
    assert launch(kit, "author")[0].returncode == 0
    done, result = launch(kit, "reviewer", "--assignment", str(kit / "plain.md"))
    assert done.returncode == 2 and "differs" in result["refused"]
    assert launch(kit, "reviewer", "--assignment", str(kit / "assignment.md"))[0].returncode == 0


def test_the_verifier_is_c5_only_and_r4_launches_are_unchanged(kit):
    r4 = kit / "r4.py"
    r4.write_text(r4_scenario())
    plan(kit, authored=str(r4), verdicts=[[False, 1], [True, 0]])
    (kit / "plain.md").write_text("Case prefix S1. Mainly English, one session in Spanish.\n")
    done, result = launch(kit, "author", gate=None, assignment_file=kit / "plain.md")
    assert done.returncode == 0 and result["precheck"] == {"ok": True, "codes": []}
    folder = kit / "private" / "c1"
    assert not (folder / "assignment.md").exists() and not (folder / "rounds.json").exists()
    done, result = launch(kit, "verifier", gate=None)
    assert done.returncode == 2 and result["refused"] == "the verifier role is for the C5 gate only"
    done, result = launch(kit, "reviewer", gate=None)
    assert "round" not in result and received(kit, "reviewer", 1) == ["brief.md", "scenario.py"]
    assert (kit / "sessions" / "c1-reviewer-1" / "brief.md").read_text() == (KIT / "reviewer-brief.md").read_text()
    done, result = launch(kit, "fixer", gate=None)
    assert "findings_from" not in result and received(kit, "fixer", 1) == ["brief.md", "findings.md", "scenario.py"]
    done, result = launch(kit, "reviewer", gate=None)  # R4 keeps any number of reviews, named by session.
    assert done.returncode == 0 and result["approved"] is True
    assert sorted(path.name for path in folder.glob("review-*.json")) == ["review-1.json", "review-2.json"]
    receipt = json.loads((kit / "private" / "control" / "c1-review-approved.json").read_text())
    assert set(receipt) == {"key", "sha256", "sessions", "turns", "cases", "approved", "findings", "review_session"}
    assert not (folder / "rounds.json").exists()


def test_the_r4_precheck_is_unchanged_by_the_c5_rules(tmp_path):
    sessions = [(name, [*turns[:3], "Ha."]) for name, turns in r4_values()["SESSIONS_LONG"]]
    code, summary, output = run_precheck(tmp_path, r4_scenario(SESSIONS_LONG=sessions), mode="--r4")
    assert code == 0 and summary["mode"] == "r4" and "coverage" not in summary, output


# The briefs -------------------------------------------------------------------------------------------------------

def _fatal(name):
    text = (KIT / name).read_text()
    return text.split("<!-- FATAL-LIST-START -->\n")[1].split("<!-- FATAL-LIST-END -->")[0]


def test_the_fatal_list_is_the_same_in_the_author_reviewer_and_verifier_briefs():
    block = _fatal("c5-author-brief.md")
    assert block == _fatal("c5-reviewer-brief.md") == _fatal("c5-verifier-brief.md")
    assert [line.split(" ")[1].strip("*") for line in block.splitlines() if line.startswith("- **F")] == \
        [f"F{number}" for number in range(1, 11)]


def test_the_briefs_state_the_procedure():
    author = (KIT / "c5-author-brief.md").read_text()
    reviewer = (KIT / "c5-reviewer-brief.md").read_text()
    verifier = (KIT / "c5-verifier-brief.md").read_text()
    fixer = (KIT / "c5-fixer-brief.md").read_text()
    for item in precheck.COVERAGE_FIELDS:
        assert f"**`{item}`" in author, item  # Every item has a criteria template.
    assert "Every user message stands on its own" in author and '"Klingt gut.' in author
    assert "Coverage items" in author and "ordinary memory cases" in author and "`c5_short_message`" in author
    assert "one full review" in reviewer and "Message scan" in reviewer and "exact change" in reviewer
    assert "deviation" in reviewer and "never the template itself" in reviewer
    assert "may not reopen" in verifier and "Advisory" in verifier and "Approve exactly when" in verifier
    assert "do not apply the advisory notes" in fixer and "word for word" in fixer
    for text in (author, reviewer, verifier, fixer):
        assert "membrain" not in text.lower() and "deepseek" not in text.lower()


# freeze.py --gate C5: the pair covers all thirteen together -----------------------------------------------------------

def test_freeze_records_each_scenarios_items_and_freezes_its_assignment(repo, tmp_path):
    done, result = freeze(repo, tmp_path / "manifest.json")
    assert done.returncode == 0, done.stdout
    assert [item["coverage_items"] for item in result["scenarios"]] == [list(SCENARIO_ONE), list(SCENARIO_TWO)]
    files = json.loads((tmp_path / "manifest.json").read_text())["files"]
    assert {f"{PRIVATE}/control/c1-assignment.md", f"{PRIVATE}/control/c2-assignment.md"} <= set(files)


def test_freeze_refuses_a_pair_that_misses_an_item(repo, tmp_path):
    (repo / PRIVATE / "c2" / "scenario_c2.py").write_text(c5_scenario(values=split_values(1, "C2")))
    (repo / PRIVATE / "control" / "c2-assignment.md").write_text(coverage_line(SCENARIO_ONE))
    done, result = freeze(repo, tmp_path / "manifest.json")
    assert done.returncode == 2 and not (tmp_path / "manifest.json").exists()
    assert result["refused"] == ("the pair's scenarios do not cover every C5 item together: " + ", ".join(
        SCENARIO_TWO_IN_ORDER) + " missing")


SCENARIO_TWO_IN_ORDER = [item for item in precheck.COVERAGE_FIELDS if item in SCENARIO_TWO]


def test_freeze_prechecks_each_scenario_with_its_own_items(repo, tmp_path):
    (repo / PRIVATE / "control" / "c2-assignment.md").write_text(coverage_line(SCENARIO_ONE))
    done, result = freeze(repo, tmp_path / "manifest.json")
    assert done.returncode == 2 and result["refused"].startswith("scenario c2 fails the C5 precheck: ")
    assert "c5_coverage_missing" in result["refused"] and "c5_coverage_not_required" in result["refused"]


def test_freeze_needs_an_assignment_per_c5_scenario_and_refuses_one_for_r4(repo, tmp_path):
    (repo / PRIVATE / "control" / "c1-assignment.md").write_text("- Coverage items: mood.\n")
    done, result = freeze(repo, tmp_path / "manifest.json")
    assert done.returncode == 2 and result["refused"].startswith("the assignment for c1: ")
    done, result = freeze(repo, tmp_path / "m2.json", "--assignment", f"c1={PRIVATE}/control/c1-assignment.md",
                          gate=None)
    assert done.returncode == 2 and result["refused"] == "--assignment is for the held-out scenarios of the C5 gate"
    arguments = [sys.executable, str(KIT / "freeze.py"), "--repo", str(repo), "--attempt-id", "maturity-zq",
                 "--private-root", PRIVATE, "--out", str(tmp_path / "m3.json"), "--python", sys.executable,
                 "--allowed-models", f"{PRIVATE}/control/allowed-models.json", "--gate", "C5",
                 "--scenario", f"c1={PRIVATE}/c1/scenario_c1.py", "--receipt",
                 f"c1={PRIVATE}/control/c1-review-approved.json"]
    done = subprocess.run(arguments, capture_output=True, text=True, timeout=120)
    assert json.loads(done.stdout)["refused"] == "every C5 scenario needs exactly one --assignment (its coverage items)"
