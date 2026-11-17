"""The C5 side of the scenario kit, offline: the precheck's --c5 mode (every code, on synthetic scenarios), freeze.py
--gate C5, launch.py --gate C5 with a fake session, the blind sheet's companion blocks (and the R4 sheet unchanged),
the C5 briefs, novelty on a C5 scenario and the C5 stub rehearsal's use of the kit. No service, database, session or
model is started, and no network is used."""
import copy
import datetime
import hashlib
import importlib.util
import json
import os
import random
import runpy
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS = ROOT / "evaluations"
KIT = EVALUATIONS / "acceptance-kit"
PLANT = "ZQ-PLANTED-C5-HELD-OUT-71f0"
pytestmark = pytest.mark.skipif(shutil.which("git") is None or os.name == "nt", reason="needs git and POSIX modes")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


precheck_module = _load("c5_precheck_for_kit_tests", EVALUATIONS / "c5-precheck.py")

# Sixteen sessions of four messages over 53 days, with a 19-day absence before the thirteenth. The second session
# starts three hours after the first (the "within hours" mood case: at most 6 hours, sessions at least 3 apart).
DATES = [(3, 2, 20), (3, 2, 23), (3, 5, 20), (3, 7, 10), (3, 9, 19), (3, 11, 20), (3, 13, 20), (3, 15, 18),
         (3, 18, 20), (3, 21, 11), (3, 24, 20), (3, 27, 20), (4, 15, 20), (4, 18, 20), (4, 21, 20), (4, 24, 20)]


def first_message(month, day, hour, text, year=2026, later=0):
    when = datetime.date(year, month, day) + datetime.timedelta(days=later)
    return f"Today is {when.strftime('%A')}, {when.strftime('%B')} {when.day}, {hour:02d}:00. {text}"


def c5_values(prefix="C1", plant=PLANT, dates=DATES):
    """A synthetic held-out C5 scenario that passes the precheck: 16 sessions of 4 messages, 11 cases, five page
    actions, a full COVERAGE table and one off-the-record stretch."""
    sessions = [(f"s{number:02d}", [first_message(month, day, hour, f"{plant} {number}."), f"{plant} a {number}",
                                    f"{plant} b {number}", f"{plant} c {number}"])
                for number, (month, day, hour) in enumerate(dates)]
    places = [("s01", 0), ("s02", 0), ("s03", 0), ("s04", 0), ("s04", 2), ("s05", 1), ("s06", 1), ("s07", 0),
              ("s12", 0), ("s12", 1), ("s13", 1)]
    cases = [(session, turn, f"{prefix}{number + 1:02d}-case-{number + 1}", f"Criteria: must {plant}.")
             for number, (session, turn) in enumerate(places)]

    def case(number):
        return cases[number - 1][2]

    return {
        "YEAR": 2026,
        "HOST": f"You are a friendly companion chatting with {plant} in a messaging app. Reply briefly and naturally.",
        "SESSIONS_LONG": sessions, "FACTS": f"- {plant}", "CASES": cases,
        "PAGE_ACTIONS": [("s03", 0, {"do": "accept_proposal", "origin": "feedback", "kind": "less_formal"}),
                         ("s05", 0, {"do": "add_boundary", "topic": f"{plant} topic", "aliases": [plant]}),
                         ("s06", 1, {"do": "delete_message", "session": "s00", "turn": 1}),
                         ("s07", 0, {"do": "switch_persona", "preset": "random"}),
                         ("s13", 0, {"do": "reset_relationship"})],
        "COVERAGE": {
            "stated_feeling": {"message": ("s00", 1), "case": case(4)},
            # Before the mood news: no declared feeling between the news and the later mood case.
            "inferred_feeling": {"message": ("s00", 0), "case": case(5)},
            "mood": {"event": ("s00", 2), "within_hours": case(1), "after_48_hours": case(2)},
            "feelings_question": {"case": case(2)},
            "boundary_in_conversation": {"asked": ("s01", 2), "case": case(5)},
            "boundary_on_page": {"action": ("s05", 0, "add_boundary"), "case": case(6)},
            "page_deletion": {"action": ("s06", 1, "delete_message"), "case": case(7)},
            "reset": {"action": ("s13", 0, "reset_relationship"), "case": case(11)},
            "manner_feedback": {"comments": [("s00", 3), ("s01", 3), ("s02", 1)],
                                "accept": ("s03", 0, "accept_proposal"), "case": case(3)},
            "from_now_on": {"request": ("s03", 1), "yes": ("s03", 2), "case": case(4)},
            "switch": {"action": ("s07", 0, "switch_persona"), "case": case(8)},
            "shared_moments": {"play": ("s02", 2), "hard": ("s05", 3), "case": case(10)},
            "absence": {"case": case(9)},
        },
        "EXPECT_RECORDING_P": [("s14", 1, False), ("s14", 2, True)],
    }


# The pair's split of the thirteen COVERAGE items (2026-11-17): each scenario covers its own items, one case each.
SCENARIO_ONE = ("stated_feeling", "inferred_feeling", "mood", "feelings_question", "boundary_in_conversation",
                "page_deletion", "absence")
SCENARIO_TWO = ("boundary_on_page", "reset", "manner_feedback", "from_now_on", "switch", "shared_moments")


def split_values(part=1, prefix="C1"):
    """c5_values with COVERAGE cut to one scenario's items of the split, each item with its own case."""
    values = c5_values(prefix)
    table, cases = values["COVERAGE"], values["CASES"]
    if part == 1:  # c5_values shares cases 2 and 5 between two items each; scenario one gives each item its own.
        table["feelings_question"] = {"case": cases[2][2]}
        table["boundary_in_conversation"] = {"asked": ("s01", 2), "case": cases[5][2]}
    values["COVERAGE"] = {item: table[item] for item in (SCENARIO_ONE if part == 1 else SCENARIO_TWO)}
    return values


def coverage_line(items) -> str:
    return "- Coverage items: " + ", ".join(items) + "\n"


def c5_scenario(extra="", values=None, **changes):
    values = {**(values or c5_values()), **changes}
    return "".join(f"{name} = {value!r}\n" for name, value in values.items() if value is not None) + extra


def covered(**entries):
    """c5_values' COVERAGE with some requirements replaced (None drops one)."""
    table = copy.deepcopy(c5_values()["COVERAGE"])
    for name, value in entries.items():
        if value is None:
            table.pop(name)
        else:
            table[name] = value
    return table


def run_precheck(tmp_path, source, mode="--c5", require=None):
    path = tmp_path / "scenario.py"
    path.write_text(source)
    extra = ["--require", ",".join(require)] if require else []
    done = subprocess.run([sys.executable, str(EVALUATIONS / "c5-precheck.py"), *([mode] if mode else []), *extra,
                           str(path)], capture_output=True, text=True, timeout=60)
    assert PLANT not in done.stdout + done.stderr
    return done.returncode, json.loads(done.stdout.strip().splitlines()[-1]), done.stdout


# The precheck's C5 mode ---------------------------------------------------------------------------------------------

def test_the_c5_precheck_passes_a_fit_scenario_and_prints_counts_only(tmp_path):
    code, summary, output = run_precheck(tmp_path, c5_scenario())
    assert code == 0, output
    assert summary == {"ok": True, "mode": "c5", "sessions": 16, "turns": 64, "actions": 5, "cases": 11,
                       "failures": 0, "codes": [], "span_days": 53, "coverage": 13, "requirements": 13,
                       "pause_openings": {"recognised": 0, "stretches": 1}}
    assert "coverage 13 of 13" in output and "span days 53" in output


def test_the_off_the_record_stretch_is_allowed_not_required_and_a_switch_may_be_asked_for(tmp_path):
    table = covered(switch={"request": ("s06", 2), "case": c5_values()["CASES"][7][2]})
    actions = c5_values()["PAGE_ACTIONS"][:3] + c5_values()["PAGE_ACTIONS"][4:]
    code, summary, output = run_precheck(tmp_path, c5_scenario(EXPECT_RECORDING_P=None, COVERAGE=table,
                                                               PAGE_ACTIONS=actions))
    assert code == 0, output


def test_a_relationship_reset_between_a_boundary_and_its_case_no_longer_undoes_it(tmp_path):
    # Since 2026-11-18 a relationship reset keeps the boundaries, so a reset between either boundary and its case is
    # allowed; removing the page boundary still undoes it ("page boundary removed before its case" below).
    actions = c5_values()["PAGE_ACTIONS"]
    actions = [("s02", 0, {"do": "reset_relationship"}), *actions[:2], ("s05", 1, {"do": "reset_relationship"}),
               *actions[2:]]
    code, summary, output = run_precheck(tmp_path, c5_scenario(PAGE_ACTIONS=actions))
    assert code == 0 and summary["codes"] == [] and summary["actions"] == 7, output


def test_the_c5_precheck_never_runs_the_scenario(tmp_path):
    marker = tmp_path / "ran"
    code, summary, _ = run_precheck(tmp_path, c5_scenario(extra=f"open({str(marker)!r}, 'w')\n"))
    assert code == 1 and summary["codes"] == ["c5_not_literal"] and not marker.exists()


def _sessions_with(index, messages):
    sessions = copy.deepcopy(c5_values()["SESSIONS_LONG"])
    sessions[index] = (sessions[index][0], messages)
    return sessions


def _actions_plus(*entries):
    return c5_values()["PAGE_ACTIONS"] + list(entries)


CASE = {number: c5_values()["CASES"][number - 1][2] for number in range(1, 12)}
UNFIT = {
    "persona": ({"PERSONA": {"name": "x"}}, "", "c5_persona"),
    "stub script": ({"STUB_HOST": {}}, "", "c5_stub_script"),
    "unknown name": ({"EXPECT": []}, "", "c5_unknown_name"),
    "missing": ({"FACTS": None}, "", "c5_missing"),
    "case count": ({"CASES": c5_values()["CASES"] + [("s15", 0, "C112-case", "Criteria: x")]}, "", "c5_case_count"),
    "turn count": ({"SESSIONS_LONG": _sessions_with(15, c5_values()["SESSIONS_LONG"][15][1] + ["x", "y", "z"])}, "",
                   "c5_turn_count"),
    "case position": ({"CASES": c5_values()["CASES"][:10] + [("s99", 0, "C111-case", "Criteria: x")]}, "",
                      "c5_case_position"),
    "case id": ({"CASES": c5_values()["CASES"][:10] + [("s15", 0, "c111 case", "Criteria: x")]}, "", "c5_case_id"),
    "case prefix": ({"CASES": c5_values()["CASES"][:10] + [("s15", 0, "D111-case", "Criteria: x")]}, "",
                    "c5_case_prefix"),
    "recording position": ({"EXPECT_RECORDING_P": [("s14", 8, False), ("s14", 9, True)]}, "",
                           "c5_recording_position"),
    "recording shape": ({"EXPECT_RECORDING_P": [("s14", 1, False), ("s15", 0, True)]}, "", "c5_recording_shape"),
    "no weekday": ({"SESSIONS_LONG": _sessions_with(15, ["今天是4月24日 20:00。x", "a", "b", "c"])}, "",
                   "c5_no_weekday"),
    "action arms": ({"PAGE_ACTIONS": _actions_plus(("s15", 0, {"do": "reset_mood", "arms": ["P"]}))}, "",
                    "c5_action_arms"),
    "action off record": ({"PAGE_ACTIONS": _actions_plus(("s15", 0, {"do": "delete_message", "session": "s14",
                                                                     "turn": 1}))}, "", "c5_action_off_record"),
    "action limit": ({"PAGE_ACTIONS": _actions_plus(("s15", 0, {"do": "add_boundary", "topic": "x" * 61}))}, "",
                     "c5_action_limit"),
    "support style limit": ({"PAGE_ACTIONS": _actions_plus(("s15", 0, {"do": "set_support_style", "text": "y" * 201}))},
                            "", "c5_action_limit"),
    "card limit": ({"PAGE_ACTIONS": _actions_plus(("s15", 0, {"do": "set_persona", "card": {"mood": "x"}}))}, "",
                   "c5_action_limit"),
    "span": ({"SESSIONS_LONG": [(name, [first_message(3, 2, 20, "x", later=2 * number), *messages[1:]])
                                for number, (name, messages) in enumerate(c5_values()["SESSIONS_LONG"])]}, "",
             "c5_span"),
    "weekday": ({"SESSIONS_LONG": _sessions_with(4, ["Today is Friday, March 9, 19:00. x", "a", "b", "c"])}, "",
                "weekday_mismatch"),
    "bad action": ({"PAGE_ACTIONS": _actions_plus(("s15", 0, {"do": "delete_note", "match": "x"}))}, "",
                   "bad_action"),
    "coverage not a table": ({"COVERAGE": [1, 2]}, "", "c5_coverage_shape"),
    "coverage entry shape": ({"COVERAGE": covered(mood={"event": ("s00", 2), "within_hours": CASE[1]})}, "",
                             "c5_coverage_shape"),
    "switch with both": ({"COVERAGE": covered(switch={"request": ("s07", 0), "action": ("s07", 0, "switch_persona"),
                                                      "case": CASE[8]})}, "", "c5_coverage_shape"),
    "two comments only": ({"COVERAGE": covered(manner_feedback={"comments": [("s00", 3), ("s01", 3)],
                                                                "accept": ("s03", 0, "accept_proposal"),
                                                                "case": CASE[3]})}, "", "c5_coverage_shape"),
    "coverage unknown key": ({"COVERAGE": {**c5_values()["COVERAGE"], "surprise": {"case": CASE[1]}}}, "",
                             "c5_coverage_unknown"),
    "coverage missing": ({"COVERAGE": covered(absence=None)}, "", "c5_coverage_missing"),
    "coverage position": ({"COVERAGE": covered(stated_feeling={"message": ("s00", 9), "case": CASE[4]})}, "",
                          "c5_coverage_position"),
    "coverage case": ({"COVERAGE": covered(feelings_question={"case": "C199-nowhere"})}, "", "c5_coverage_case"),
    "coverage action kind": ({"COVERAGE": covered(reset={"action": ("s07", 0, "switch_persona"), "case": CASE[11]})},
                             "", "c5_coverage_action"),
    "coverage action missing": ({"COVERAGE": covered(boundary_on_page={"action": ("s04", 0, "add_boundary"),
                                                                       "case": CASE[6]})}, "", "c5_coverage_action"),
    "accept of any origin": ({"PAGE_ACTIONS": [("s03", 0, {"do": "accept_proposal"})] + c5_values()["PAGE_ACTIONS"][1:]},
                             "", "c5_coverage_action"),
    "same feeling message": ({"COVERAGE": covered(inferred_feeling={"message": ("s00", 1), "case": CASE[5]})}, "",
                             "c5_coverage_distinct"),
    "yes in another conversation": ({"COVERAGE": covered(from_now_on={"request": ("s03", 1), "yes": ("s04", 1),
                                                                      "case": CASE[6]})}, "", "c5_coverage_order"),
    "from-now-on case in the same conversation": ({"COVERAGE": covered(from_now_on={
        "request": ("s03", 1), "yes": ("s03", 2), "case": CASE[3]})}, "", "c5_coverage_order"),
    "case before its feeling": ({"COVERAGE": covered(stated_feeling={"message": ("s05", 1), "case": CASE[4]})}, "",
                                "c5_coverage_order"),
    "comments after the accept": ({"COVERAGE": covered(manner_feedback={
        "comments": [("s00", 3), ("s01", 3), ("s03", 3)], "accept": ("s03", 0, "accept_proposal"),
        "case": CASE[3]})}, "", "c5_coverage_order"),
    "mood not within hours": ({"COVERAGE": covered(mood={"event": ("s00", 2), "within_hours": CASE[2],
                                                         "after_48_hours": CASE[3]})}, "", "c5_coverage_timing"),
    "mood not 48 hours after": ({"COVERAGE": covered(mood={"event": ("s00", 2), "within_hours": CASE[1],
                                                           "after_48_hours": CASE[1]})}, "", "c5_coverage_timing"),
    "hard moment too recent": ({"COVERAGE": covered(shared_moments={"play": ("s02", 2), "hard": ("s05", 3),
                                                                    "case": CASE[8]})}, "", "c5_coverage_timing"),
    "no long absence": ({"COVERAGE": covered(absence={"case": CASE[11]})}, "", "c5_coverage_timing"),
    "feelings cleared before the case": ({"PAGE_ACTIONS": _actions_plus(("s02", 0, {"do": "clear_feelings"}))}, "",
                                         "c5_coverage_undone"),
    "page boundary removed before its case": ({"PAGE_ACTIONS": _actions_plus(
        ("s05", 1, {"do": "remove_boundary", "topic": f"{PLANT}  TOPIC"}))}, "", "c5_coverage_undone"),
    "persona switched before the from-now-on case": ({"COVERAGE": covered(switch={"request": ("s03", 3),
                                                                                  "case": CASE[8]})}, "",
                                                     "c5_coverage_undone"),
    "mood reset before the within-hours case": ({"PAGE_ACTIONS": _actions_plus(("s01", 0, {"do": "reset_mood"}))}, "",
                                                "c5_coverage_undone"),
    "relationship reset before the hard-moment case": ({"PAGE_ACTIONS": _actions_plus(
        ("s10", 0, {"do": "reset_relationship"}))}, "", "c5_coverage_undone"),
    "coverage off the record": ({"COVERAGE": covered(boundary_in_conversation={"asked": ("s14", 1),
                                                                               "case": CASE[5]})}, "",
                                "c5_coverage_off_record"),
    # 2026-11-17 review fixes.
    "named preset (M7)": ({"PAGE_ACTIONS": _actions_plus(("s15", 0, {"do": "switch_persona", "preset": "enfp"}))}, "",
                          "c5_named_preset"),
    "page decision between the request and the yes (M9)": ({"PAGE_ACTIONS": _actions_plus(
        ("s03", 2, {"do": "reject_proposal", "origin": "host"}))}, "", "c5_coverage_undone"),
    "accepted suggestion between the yes and its case (M9)": ({"PAGE_ACTIONS": _actions_plus(
        ("s04", 0, {"do": "accept_proposal", "origin": "feedback", "kind": "shorter"}))}, "", "c5_coverage_undone"),
    "deletion of a reply (m1)": ({"PAGE_ACTIONS": c5_values()["PAGE_ACTIONS"][:2] + [
        ("s06", 1, {"do": "delete_message", "session": "s00", "turn": 1, "role": "assistant"})]
        + c5_values()["PAGE_ACTIONS"][3:]}, "", "c5_coverage_action"),
    "acceptance without its manner kind (m2)": ({"PAGE_ACTIONS": [("s03", 0, {"do": "accept_proposal",
                                                                               "origin": "feedback"})]
                                                 + c5_values()["PAGE_ACTIONS"][1:]}, "", "c5_coverage_action"),
    "mood case 7 hours later (M6)": ({"SESSIONS_LONG": _sessions_with(1, [first_message(3, 3, 3, "x"), "a", "b",
                                                                          "c"])}, "", "c5_coverage_timing"),
    "mood case 48 hours later (M6)": ({"SESSIONS_LONG": _sessions_with(2, [first_message(3, 4, 20, "x"), "a", "b",
                                                                           "c"])}, "", "c5_coverage_timing"),
    "a declared feeling between the news and the later mood case (M6)": ({"COVERAGE": covered(
        inferred_feeling={"message": ("s01", 1), "case": CASE[5]})}, "", "c5_coverage_timing"),
    # 2026-11-17 authoring diagnostic: reply-independent messages.
    "a bare reaction": ({"SESSIONS_LONG": _sessions_with(15, c5_values()["SESSIONS_LONG"][15][1][:3] + ["Fair enough."])},
                        "", "c5_short_message"),
    "a reaction opening a longer message": ({"SESSIONS_LONG": _sessions_with(
        15, c5_values()["SESSIONS_LONG"][15][1][:3] + ["Cool. Anyway, off to make a massive breakfast."])}, "",
        "c5_reaction_opening"),
}
# Codes that only a --require list can give (one scenario of the pair): tested in UNFIT_REQUIRED.
REQUIRED_ONLY = {"c5_coverage_not_required", "c5_coverage_shared_case"}


@pytest.mark.parametrize("changes, extra, expected", list(UNFIT.values()), ids=list(UNFIT))
def test_the_c5_precheck_refuses_each_unfit_scenario_with_its_code(tmp_path, changes, extra, expected):
    code, summary, output = run_precheck(tmp_path, c5_scenario(extra=extra, **changes))
    assert code == 1 and expected in summary["codes"], output


def test_every_c5_code_is_tested_and_known_and_the_briefs_document_them():
    tested = {expected for _, _, expected in UNFIT.values()} | {"c5_not_literal"} | REQUIRED_ONLY
    assert set(precheck_module.C5_CODES) == tested - {"weekday_mismatch", "bad_action"}
    assert set(precheck_module.C5_CODES) <= set(precheck_module.CODES)
    author, reviewer = (KIT / "c5-author-brief.md").read_text(), (KIT / "c5-reviewer-brief.md").read_text()
    for code in precheck_module.C5_CODES:
        assert f"`{code}`" in author, code
    for field, keys in precheck_module.COVERAGE_FIELDS.items():
        assert f'"{field}"' in author and f'"{field}"' in reviewer, field
        for key in keys:
            assert f'"{key}"' in author, (field, key)


def test_a_failure_names_only_fixed_fields_never_the_scenarios_words(tmp_path):
    table = covered(stated_feeling={"message": ("s00", 9), "case": CASE[4]})
    table[PLANT] = {"case": CASE[1]}
    code, summary, output = run_precheck(tmp_path, c5_scenario(COVERAGE=table, **{"EXTRA_" + "X" * 3: PLANT}))
    assert code == 1 and "FAIL code=c5_coverage_position field=stated_feeling part=message" in output
    assert "FAIL code=c5_coverage_unknown count=1" in output and "FAIL code=c5_unknown_name count=1" in output


def test_the_precheck_time_rules_are_the_products():
    from membrain import persona_growth, relationship

    assert (precheck_module.HARD_DAYS, precheck_module.HARD_CONVERSATION_DAYS) == (
        relationship.HARD_MELLOW_DAYS, relationship.HARD_MELLOW_CONVERSATION_DAYS)
    assert persona_growth.THRESHOLD == 3  # The brief asks for three comments of one kind.
    from membrain import mood

    # The later mood case: an hour past the product's cutoff (it counts from the trigger's recorded time on a clock
    # that runs with wall time); the "within hours" case: no later than the product's easing point.
    assert precheck_module.MOOD_AFTER == mood.CUTOFF + datetime.timedelta(hours=1)
    assert precheck_module.MOOD_WITHIN == mood.EASING_AFTER


def test_the_r4_mode_and_the_default_mode_are_unchanged_by_c5(tmp_path):
    code, summary, _ = run_precheck(tmp_path, c5_scenario(), mode="--r4")
    assert code == 1 and "r4_page_actions" in summary["codes"] and "mode" in summary and summary["mode"] == "r4"
    assert not any(code.startswith("c5_") for code in summary["codes"])
    code, summary, _ = run_precheck(tmp_path, c5_scenario(PERSONA={"name": "x"}), mode=None)
    assert code == 0 and "mode" not in summary


# freeze.py --gate C5 ------------------------------------------------------------------------------------------------

def git(repo, *arguments):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                    *arguments], check=True, capture_output=True)


PRIVATE = "evaluations/.maturity-heldout-zq"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "evaluations" / "acceptance-review").mkdir(parents=True)
    for name in ("acceptance_review.py", "acceptance-attempt-driver.py", "acceptance_persona.py", "c5-precheck.py",
                 "c5-harness.py", "scenario_literals.py"):
        shutil.copyfile(EVALUATIONS / name, root / "evaluations" / name)
    (root / "evaluations" / "acceptance-review" / "companion.md").write_text("companion\n")
    (root / "AGENTS.md").write_text("conventions\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    private = root / PRIVATE
    (private / "control").mkdir(parents=True)
    # The pair splits the thirteen items: c1 covers scenario one's, c2 scenario two's (2026-11-17).
    for key, prefix, part, items in (("c1", "C1", 1, SCENARIO_ONE), ("c2", "C2", 2, SCENARIO_TWO)):
        (private / key).mkdir(parents=True)
        (private / key / f"scenario_{key}.py").write_text(c5_scenario(values=split_values(part, prefix)))
        (private / "control" / f"{key}-assignment.md").write_text(f"- Case prefix: `{prefix}`.\n" + coverage_line(items))
    (private / "control" / "allowed-models.json").write_text(json.dumps(["fixture-model-small"]))
    return root


def receipt(repo, key, **changes):
    path = repo / PRIVATE / "control" / f"{key}-review-approved.json"
    scenario = repo / PRIVATE / key / f"scenario_{key}.py"
    value = {"key": key, "sha256": hashlib.sha256(scenario.read_bytes()).hexdigest(), "sessions": 16, "turns": 64,
             "cases": 11, "approved": True, "findings": 0, "gate": "C5", **changes}
    path.write_text(json.dumps({name: item for name, item in value.items() if item is not None}))
    return f"{PRIVATE}/control/{key}-review-approved.json"


def freeze(repo, out, *extra, gate="C5", receipt_changes=None):
    arguments = [sys.executable, str(KIT / "freeze.py"), "--repo", str(repo), "--attempt-id", "maturity-zq",
                 "--private-root", PRIVATE, "--out", str(out), "--python", sys.executable,
                 "--allowed-models", f"{PRIVATE}/control/allowed-models.json", *(["--gate", gate] if gate else [])]
    for key in ("c1", "c2"):
        arguments += ["--scenario", f"{key}={PRIVATE}/{key}/scenario_{key}.py",
                      "--receipt", f"{key}={receipt(repo, key, **((receipt_changes or {}).get(key, {})))}"]
        if gate == "C5":  # A C5 held-out scenario is frozen with its assignment (its coverage items).
            arguments += ["--assignment", f"{key}={PRIVATE}/control/{key}-assignment.md"]
    done = subprocess.run([*arguments, *extra], capture_output=True, text=True, timeout=120)
    return done, json.loads(done.stdout.strip().splitlines()[-1])


def test_freeze_gate_c5_writes_the_c5_pair_both_validators_accept(repo, tmp_path):
    out = tmp_path / "manifest.json"
    done, result = freeze(repo, out)
    assert done.returncode == 0, done.stdout + done.stderr
    assert PLANT not in done.stdout + done.stderr
    manifest = json.loads(out.read_text())
    assert [pair["gate"] for pair in manifest["pairs"]] == ["C5"] and result["gate"] == "C5"
    assert [item["key"] for item in manifest["pairs"][0]["scenarios"]] == ["c1", "c2"]
    review = _load("acceptance_review_for_kit_c5", EVALUATIONS / "acceptance_review.py")
    assert review.manifest_scenarios(review.load_manifest(out), "C5") == manifest["pairs"][0]["scenarios"]
    driver = _load("acceptance_driver_for_kit_c5", EVALUATIONS / "acceptance-attempt-driver.py")
    driver.validate_manifest(manifest)
    assert [(item["key"], item["turns"], item["cases"]) for item in result["scenarios"]] == [("c1", 64, 11),
                                                                                             ("c2", 64, 11)]


def test_freeze_gate_c5_runs_the_c5_precheck(repo, tmp_path):
    (repo / PRIVATE / "c2" / "scenario_c2.py").write_text(c5_scenario(values=split_values(2, "C2"), PERSONA={"x": 1}))
    done, result = freeze(repo, tmp_path / "manifest.json")
    assert done.returncode == 2 and result["refused"] == "scenario c2 fails the C5 precheck: c5_persona"


@pytest.mark.parametrize("receipt_gate", [None, "R4"], ids=["receipt without a gate", "an R4 receipt"])
def test_an_r4_receipt_never_freezes_a_scenario_for_c5(repo, tmp_path, receipt_gate):
    done, result = freeze(repo, tmp_path / "manifest.json", receipt_changes={"c2": {"gate": receipt_gate}})
    assert done.returncode == 2 and result["refused"] == "the receipt for c2 is a review for another gate than C5"
    assert not (tmp_path / "manifest.json").exists()


def test_freeze_without_a_gate_is_r4_and_refuses_c5_scenarios(repo, tmp_path):
    done, result = freeze(repo, tmp_path / "manifest.json", gate=None)
    assert done.returncode == 2 and result["refused"].startswith("scenario c1 fails the R4 precheck: ")
    assert "r4_page_actions" in result["refused"]


# launch.py --gate C5 in its offline dry mode -------------------------------------------------------------------------

FAKE_SESSION = r'''
import json, pathlib, shutil, sys
workdir, role, source = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
(workdir / "brief-seen.md").write_text((workdir / "brief.md").read_text())
if role == "author":
    shutil.copyfile(source, workdir / "scenario.py")
elif role == "reviewer":
    (workdir / "findings.md").write_text("No findings.")
    (workdir / "review.json").write_text(json.dumps({"approved": True, "findings": 0, "blocking": 0}))
else:
    (workdir / "fixes.json").write_text(json.dumps({"applied": 0}))
'''


@pytest.fixture
def kit(tmp_path):
    private = tmp_path / "private"
    (private / "control").mkdir(parents=True, mode=0o700)
    (private / "control" / "allowed-models.json").write_text(json.dumps(["fixture-model-small"]))
    (tmp_path / "fake_session.py").write_text(FAKE_SESSION)
    # A C5 scenario covers its assignment's items (2026-11-17): scenario one's split, with its coverage line.
    (tmp_path / "authored.py").write_text(c5_scenario(values=split_values(1)))
    (tmp_path / "assignment.md").write_text("Case prefix C1. Mainly English, one session in German.\n"
                                            + coverage_line(SCENARIO_ONE))
    return tmp_path


def launch(kit, role, *extra):
    command = [sys.executable, str(KIT / "launch.py"), "--role", role, "--key", "c1", "--private",
               str(kit / "private"), "--tool", "claude", "--model", "fixture-model-small", "--allowed-models",
               str(kit / "private" / "control" / "allowed-models.json"), "--workdir-root", str(kit / "sessions"),
               "--python", sys.executable, "--session-command",
               f"{sys.executable} {kit / 'fake_session.py'} {{workdir}} {{role}} {kit / 'authored.py'}", *extra]
    if role == "author":
        command += ["--assignment", str(kit / "assignment.md")]
    environment = {**os.environ, "DEEPSEEK_API_KEY": "fixture-key", "C5_ATTEMPT_ID": "fixture"}
    done = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=120)
    return done, json.loads(done.stdout.strip().splitlines()[-1])


def test_launch_gate_c5_uses_the_c5_briefs_and_precheck_and_marks_the_receipt(kit):
    done, result = launch(kit, "author", "--gate", "C5")
    assert done.returncode == 0, done.stdout + done.stderr
    assert PLANT not in done.stdout + done.stderr
    assert result["precheck"] == {"ok": True, "codes": []} and (result["turns"], result["cases"]) == (64, 11)
    assert (kit / "sessions" / "c1-author-1" / "brief-seen.md").read_text() == (KIT / "c5-author-brief.md").read_text()
    done, result = launch(kit, "reviewer", "--gate", "C5")
    assert done.returncode == 0 and result["approved"] is True
    assert (kit / "sessions" / "c1-reviewer-1" / "brief-seen.md").read_text() == \
        (KIT / "c5-reviewer-brief.md").read_text()
    receipt = json.loads((kit / "private" / "control" / "c1-review-approved.json").read_text())
    assert receipt["gate"] == "C5" and receipt["turns"] == 64 and receipt["cases"] == 11


def test_launch_without_a_gate_is_r4_as_before(kit):
    done, result = launch(kit, "author")
    assert done.returncode == 0
    assert "r4_page_actions" in result["precheck"]["codes"] and not result["precheck"]["ok"]
    assert (kit / "sessions" / "c1-author-1" / "brief-seen.md").read_text() == (KIT / "author-brief.md").read_text()
    launch(kit, "reviewer")
    receipt = json.loads((kit / "private" / "control" / "c1-review-approved.json").read_text())
    assert "gate" not in receipt


# The C5 briefs ------------------------------------------------------------------------------------------------------

def test_the_c5_briefs_are_product_free_and_state_the_format():
    for name in ("c5-author-brief.md", "c5-reviewer-brief.md", "c5-fixer-brief.md"):
        text = (KIT / name).read_text()
        assert "membrain" not in text.lower() and "deepseek" not in text.lower(), name
    author = (KIT / "c5-author-brief.md").read_text()
    harness = _load("c5_harness_for_kit_briefs", EVALUATIONS / "c5-harness.py")
    for kind, (required, optional) in harness.ACTION_ARGUMENTS.items():
        assert f"`{kind}`" in author, kind
        for argument in required | optional:
            assert f"`{argument}`" in author, (kind, argument)
    for needle in ("Exactly 11", "60 to 66", "PERSONA", "STUB_", "COVERAGE", "PAGE_ACTIONS", "EXPECT_RECORDING_P",
                   "same conversation", "45", "Hoy es martes, 3 de marzo, 21:00.", "今天是3月3日，星期二，21:00。",
                   "no f-strings"):
        assert needle in author, needle
    # The R4 briefs are unchanged by the C5 kit.
    assert "Do not define `PERSONA`, `PAGE_ACTIONS`" in (KIT / "author-brief.md").read_text()


# The blind sheet -----------------------------------------------------------------------------------------------------

def _row(arm, scenario, session, turn, *, block, version, reply):
    row = {"arm": arm, "scenario": scenario, "session": session, "turn": turn, "date": "2026-03-02",
           "input": f"message {session} {turn}", "reply": reply,
           "persona_turn": {"format": 1, "version": version,
                            "sha256": hashlib.sha256(block.encode()).hexdigest() if block else None}}
    row["reference_persona" if arm == "F" else "persona_block"] = block
    return row


def _blind(tmp_path, scenario_text, rows, page=None, extra=()):
    blind = tmp_path / "blind"
    blind.mkdir(parents=True, exist_ok=True)
    scenario = tmp_path / "practice_sheet.py"
    scenario.write_text(scenario_text)
    for arm in ("P", "F"):
        (blind / f"results_practice_sheet_{arm}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows if row["arm"] == arm))
        if page is not None:
            (blind / f"page-actions_practice_sheet_{arm}.jsonl").write_text(
                "".join(json.dumps(record) + "\n" for record in page[arm]))
    state = random.getstate()
    original = secrets.SystemRandom
    secrets.SystemRandom = lambda: random.Random(7)  # The same shuffle as the expected sheet below.
    argv = sys.argv
    try:
        sys.argv = ["blind", str(blind), str(scenario), "PF", *extra]
        runpy.run_path(str(EVALUATIONS / "v1-2026-10-29-phase-b-blind.py"), run_name="__main__")
    finally:
        sys.argv, secrets.SystemRandom = argv, original
        random.setstate(state)
    return blind, (blind / "blind_practice_sheet.md").read_text()


SHEET_SESSIONS = [("s1", ["Today is Monday, March 2, 20:00. hi", "two"]), ("s2", ["Today is Wednesday, March 4, 20:00. x"])]


def test_an_r4_sheet_is_byte_for_byte_the_sheet_before_companion_mode(tmp_path):
    cases = [("s1", 1, "S101-a", "Criteria: must a."), ("s2", 0, "S102-b", "Criteria: must b.")]
    text = f"SESSIONS_LONG = {SHEET_SESSIONS!r}\nFACTS = '- facts'\nCASES = {cases!r}\n"
    rows = [_row(arm, "practice_sheet", session, turn, block="<p>x</p>", version=1, reply=f"{arm} reply {turn}")
            for arm in ("P", "F") for session, turns in SHEET_SESSIONS for turn in range(len(turns))]
    blind, sheet = _blind(tmp_path, text, rows)
    expected, sealed = ["# practice_sheet\n\n## Ground truth\n\n- facts\n"], json.loads(
        (blind / "sealed_practice_sheet.json").read_text())
    for session, turn, case, criteria in cases:
        arms = ["P", "F"]
        random.Random(7).shuffle(arms)  # The patched SystemRandom: a fresh Random(7) for every case.
        assert sealed[case] == dict(zip("AB", arms))
        order = [name for name, _ in SHEET_SESSIONS].index(session)
        expected.append(f"## {case}\n\n**Date:** 2026-03-02 (session {order + 1} of 2, message {turn + 1} of that "
                        f"session; earlier messages that day come before it)\n\n**Criteria:** "
                        f"{criteria.removeprefix('Criteria:').strip()}\n\n**User:** message {session} {turn}\n")
        expected += [f"### {label}\n\n{arm} reply {turn}\n" for label, arm in zip("AB", arms)]
    assert sheet == "\n".join(expected)
    assert "Persona in effect" not in sheet and "Page actions" not in sheet


def _companion_scenario():
    cases = [("s1", 1, "C101-a", "Criteria: must a."), ("s2", 0, "C102-b", "Criteria: must b.")]
    actions = [("s2", 0, {"do": "delete_message", "session": "s1", "turn": 0}),
               ("s1", 1, {"do": "accept_proposal", "origin": "feedback"}),
               ("s2", 0, {"do": "add_boundary", "topic": "work", "aliases": ["the office"]})]
    return (f"SESSIONS_LONG = {SHEET_SESSIONS!r}\nFACTS = '- facts'\nCASES = {cases!r}\n"
            f"PAGE_ACTIONS = {actions!r}\n"), actions


def _page_records(actions, outcomes, arm):
    order = sorted(range(len(actions)), key=lambda index: (["s1", "s2"].index(actions[index][0]), actions[index][1],
                                                           index))
    records = []
    for index in order:
        status, reason = outcomes[index]
        record = {"format": 2, "index": index, "session": actions[index][0], "before_turn": actions[index][1],
                  "action": actions[index][2]["do"], "status": status,
                  "before": {"messages": 3 if arm == "P" else 1}, "after": {"messages": 2}, "result": {}}
        if reason:
            record["reason"] = reason
        records.append(record)
    return records


def test_a_companion_sheet_shows_the_page_actions_so_far_and_the_persona_in_effect(tmp_path):
    text, actions = _companion_scenario()
    outcomes = {0: ("done", None), 1: ("not_applicable", "no_open_proposal"), 2: ("done", None)}
    page = {arm: _page_records(actions, outcomes, arm) for arm in ("P", "F")}
    blocks = {("s1", 0): ("", 0), ("s1", 1): ('<membrain-persona version="2">casual</membrain-persona>', 2),
              ("s2", 0): ('<membrain-persona version="3">```x```</membrain-persona>', 3)}
    rows = [_row(arm, "practice_sheet", session, turn, block=blocks[(session, turn)][0],
                 version=blocks[(session, turn)][1], reply=f"{arm} {session} {turn}")
            for arm in ("P", "F") for session, turns in SHEET_SESSIONS for turn in range(len(turns))]
    _, sheet = _blind(tmp_path, text, rows, page)
    first, second = sheet.split("## C102-b")
    assert ("- Action 2, before message 2 of session 1: accept_proposal (origin \"feedback\"): "
            "**not_applicable (no_open_proposal)**") in first
    assert "Action 1," not in first and "Action 3," not in first  # Only the actions before the case's message.
    assert 'version 2; the same for every reply of this case:\n\n```text\n<membrain-persona version="2">casual' in first
    assert ("- Action 1, before message 1 of session 2: delete_message (message: session 1, message 1, user): "
            "**done**") in second
    assert '- Action 3, before message 1 of session 2: add_boundary (topic "work", aliases ["the office"]): **done**' \
        in second
    assert "````text\n" in second  # A longer fence than any run of backticks in the block.
    assert '"messages"' not in sheet and "before_turn" not in sheet  # Nothing that differs between arms.
    assert sheet.index("**Page actions so far**") < sheet.index("**Persona in effect") < sheet.index("**Criteria:**")


def test_a_companion_sheet_is_refused_when_the_arms_differ_or_a_record_is_missing(tmp_path):
    text, actions = _companion_scenario()
    outcomes = {0: ("done", None), 1: ("done", None), 2: ("done", None)}
    rows = [_row(arm, "practice_sheet", session, turn, block="<p>x</p>", version=1, reply="r")
            for arm in ("P", "F") for session, turns in SHEET_SESSIONS for turn in range(len(turns))]
    with pytest.raises(SystemExit, match="page-actions_practice_sheet_P.jsonl"):
        _blind(tmp_path / "missing", text, rows)
    page = {"P": _page_records(actions, outcomes, "P"),
            "F": _page_records(actions, {**outcomes, 1: ("not_applicable", "no_open_proposal")}, "F")}
    with pytest.raises(SystemExit, match="differ between arms"):
        _blind(tmp_path / "outcomes", text, rows, page)
    page = {arm: _page_records(actions, outcomes, arm) for arm in ("P", "F")}
    changed = [dict(row, reference_persona="<p>y</p>") if row["arm"] == "F" else row for row in rows]
    with pytest.raises(SystemExit, match="no valid persona record|differs between arms"):
        _blind(tmp_path / "persona", text, changed, page)
    failed = {arm: [dict(record, status="failed") for record in page[arm]] for arm in page}
    with pytest.raises(SystemExit, match="no valid outcome"):
        _blind(tmp_path / "failed", text, rows, failed)


def test_a_sheet_split_keeps_the_companion_blocks_in_each_case_file(tmp_path):
    text, actions = _companion_scenario()
    outcomes = {index: ("done", None) for index in range(3)}
    page = {arm: _page_records(actions, outcomes, arm) for arm in ("P", "F")}
    rows = [_row(arm, "practice_sheet", session, turn, block="<p>x</p>", version=1, reply=f"{arm} reply")
            for arm in ("P", "F") for session, turns in SHEET_SESSIONS for turn in range(len(turns))]
    blind, _ = _blind(tmp_path, text, rows, page)
    review = _load("acceptance_review_for_sheet_split", EVALUATIONS / "acceptance_review.py")
    verdicts = tmp_path / "verdicts.json"
    verdicts.write_text(json.dumps({case: {label: {"score_ignoring_critical": 1, "critical": [], "conditions": [],
                                                   "reason": "x"} for label in "AB"} for case in ("C101-a", "C102-b")}))
    review.split(blind / "blind_practice_sheet.md", verdicts, blind, str(tmp_path / "practice_sheet.py"),
                 tmp_path / "recheck")
    case = (tmp_path / "recheck" / "C102-b.md").read_text()
    assert "**Page actions so far**" in case and "**Persona in effect at this message:** version 1" in case


# Novelty and the rehearsal ------------------------------------------------------------------------------------------

def test_novelty_measures_a_c5_scenario_against_the_public_practice(tmp_path):
    novelty = _load("novelty_for_kit_c5", KIT / "novelty.py")
    root = tmp_path / "public"
    (root / "evaluations").mkdir(parents=True)
    shutil.copyfile(EVALUATIONS / "c5-practice-scenario.py", root / "evaluations" / "c5-practice-scenario.py")
    (root / "evaluations" / "binding.md").write_text("Recorded hash " + "ab" * 32 + ".\n")  # git grep needs a match.
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "public")
    heldout = tmp_path / "scenario_c1.py"
    heldout.write_text(c5_scenario())
    done = subprocess.run([sys.executable, str(KIT / "novelty.py"), "--repo", str(root), "--base", "HEAD",
                           "--threshold-pct", "10", str(heldout)], capture_output=True, text=True, timeout=60)
    summary = json.loads(done.stdout)
    assert done.returncode == 0 and summary["ok"] and summary["earlier_files"] == 1, summary
    assert summary["results"][0]["max_8gram_overlap_pct"] < 10 and PLANT not in done.stdout
    copy_of_practice = tmp_path / "copy.py"
    copy_of_practice.write_bytes((EVALUATIONS / "c5-practice-scenario.py").read_bytes())
    files, recorded = novelty.earlier(root, "HEAD")
    assert not novelty.check([copy_of_practice.read_bytes()], files, recorded, 10)["ok"]


def test_the_c5_rehearsal_freezes_with_the_kit_and_shows_the_companion_sheet():
    source = (EVALUATIONS / "c5-stub-rehearsal.py").read_text()
    assert '"--gate", "C5"' in source and "def c5_manifest" not in source and 'gate"] = "C5"' not in source
    assert "page-actions_{path.stem}_{arm}.jsonl" in source and "**Persona in effect at this message:**" in source
