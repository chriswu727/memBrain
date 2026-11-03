"""Hardening of the acceptance scoring pipeline after the independent plan review (I1, I5, S2, S3, S5).

Synthetic fixtures only, written to tmp_path. No model call, no held-out scenario, no database.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SECRET = "ZQXSECRET"  # Planted in every content field; must never be printed or written by these commands.


@pytest.fixture
def pipeline():
    path = Path(__file__).parents[1] / "evaluations" / "acceptance_review.py"
    spec = importlib.util.spec_from_file_location("acceptance_review_hardening", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


# I1: diagnose prints only kinds, counts, positions and exception class names ------------------------------------------

def test_diagnose_prints_kinds_counts_and_positions_but_never_content(pipeline, tmp_path, monkeypatch, capsys):
    first, second = f"{SECRET}-session-one", f"{SECRET}-session-two"
    order = [(first, 0), (first, 1), (second, 0), (second, 1), (second, 2)]
    rows = [{"arm": "P", "scenario": "practice", "session": first, "turn": 0, "reply": f"{SECRET} reply"},
            {"arm": "P", "scenario": "practice", "session": first, "turn": 1, "reply": ""}]
    log = "\n".join([
        "12:00:00 P practice start live proposals",
        f"12:00:01 P practice {first} 0 1234 recall({SECRET}-tool-argument)",
        f"12:00:02 host error ValueError {SECRET}-host-message",
        f"12:00:03 host error HTTPStatusError Client error for url https://{SECRET}.example",
        f"12:00:04 harness event page_action_failed {{'action': 'delete_note', 'reason': '{SECRET}-reason'}}",
        f"12:00:05 page action delete_note before {second} turn 0 result: {{'failed': '{SECRET}-match'}}",
        "Traceback (most recent call last):",
        '  File "/somewhere/c5-harness.py", line 12, in <module>',
        f"    session_start('{SECRET}-code-line')",
        f"ValueError: no scenario time after the date in: '{SECRET}-session-start-text'",
        f"RuntimeError: host call cap reached {SECRET}",
        f"{SECRET}Error: {SECRET}-crafted",
    ])
    monkeypatch.setattr(pipeline, "_run", lambda _: (rows, order, log))
    events = [
        {"kind": "page_action_failed", "action": "delete_note", "session": second, "turn": 2,
         "reason": f"no note containing '{SECRET}-note'"},
        {"kind": "page_action_failed", "action": "delete_feeling", "session": second, "turn": 0,
         "reason": f"no feeling '{SECRET}-label'"},
        {"kind": "clock_already_past", "session": first, "requested": SECRET, "now": SECRET},
        {"kind": "index_wait_timed_out", "brain": f"brain-{SECRET}"},
        {"kind": f"{SECRET} not a kind", "session": first, "turn": 0},
    ]
    (tmp_path / "harness-events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + f"\n{{broken {SECRET}\n")
    pipeline.diagnose([tmp_path])
    out = capsys.readouterr().out
    assert SECRET.casefold() not in out.casefold(), out
    assert "2 of 5 turns done" in out and "empty reply at turn 2 of 5" in out
    assert "page_action_failed: 2 at session 2 of 2, message 3; session 2 of 2, message 1" in out
    assert "clock_already_past: 1 at session 1 of 2" in out
    assert "index_wait_timed_out: 1" in out
    assert "malformed event lines: 2" in out
    for line in ("log: host error ValueError: 1", "log: host error HTTPStatusError: 1", "log: Traceback: 1",
                 "log: exception ValueError: 1", "log: exception RuntimeError: 1", "log: cap reached: 1",
                 "log: harness event lines: 1", "log: exception other: 1", "harness events: 6"):
        assert line in out, (line, out)


# I5: an arm-blind digest of what each page action actually removed, for RC2 ----------------------------------------

ALPHA, BETA = f"{SECRET}-alpha", f"{SECRET}-beta"
SCENARIO = f'''
SESSIONS_LONG = [({ALPHA!r}, ["Today is Monday, March 2, 09:00. {SECRET} one", "{SECRET} two", "{SECRET} three"]),
                 ({BETA!r}, ["Today is Friday, March 6, 09:00. {SECRET} four", "{SECRET} five", "{SECRET} six"])]
CASES = [({BETA!r}, 1, "S01-case", "Criteria: {SECRET}"), ({ALPHA!r}, 1, "S02-case", "Criteria: {SECRET}")]
PAGE_ACTIONS = [
    ({BETA!r}, 0, {{"do": "delete_message", "session": {ALPHA!r}, "turn": 0}}),
    ({BETA!r}, 0, {{"do": "delete_feeling", "label": "{SECRET}-label"}}),
    ({BETA!r}, 1, {{"do": "add_boundary", "topic": "{SECRET}-topic", "arms": ["E"]}}),
    ({BETA!r}, 1, {{"do": "reset_relationship"}}),
    ({BETA!r}, 2, {{"do": "clear_feelings"}}),
]
'''


def world(**changes):
    state = {"messages": 6, "notes": 1, "feelings": 3, "boundaries": [f"{SECRET}-topic"], "shared_moments": 2,
             "familiarity": f"{SECRET}-level", "familiarity_days": 4, "mood": f"{SECRET}-mood", "mood_pinned": False,
             "persona_version": 1}
    return {**state, **changes}


def record(session, turn, action, before, after, result):
    return {"session": session, "before_turn": turn, "action": action, "time": f"{SECRET}-time",
            "detail": {"topic": f"{SECRET}-detail"}, "before": before, "after": after, "result": result}


REMOVED_P = [[ALPHA, 0, "assistant"], [ALPHA, 0, "user"]]
REFERENCE = {"history_items": 4, "persona_version": 1}
RECORDS = {
    "P": [record(BETA, 0, "delete_message", world(), world(messages=4), {"deleted": 1, "removed": REMOVED_P}),
          record(BETA, 0, "delete_feeling", world(messages=4), world(messages=4, feelings=2), {"deleted": 1}),
          record(BETA, 1, "reset_relationship", world(), world(shared_moments=0, familiarity_days=0,
                                                               familiarity=f"{SECRET}-new"), {}),
          record(BETA, 2, "clear_feelings", world(), world(feelings=0), {})],
    "E": [record(BETA, 0, "delete_message", world(feelings=2), world(messages=5, feelings=2),
                 {"deleted": 1, "removed": [[ALPHA, 0, "user"]]}),
          record(BETA, 0, "delete_feeling", world(feelings=2), world(feelings=1), {"deleted": 1}),
          record(BETA, 1, "add_boundary", world(boundaries=[]), world(), {}),
          record(BETA, 1, "reset_relationship", world(), world(shared_moments=0), {}),
          record(BETA, 2, "clear_feelings", world(), world(feelings=0), {})],
    "F": [record(BETA, 0, "delete_message", {"history_items": 6, "persona_version": 1},
                 {**REFERENCE, "removed_still_in_history": 0}, {"deleted": 2, "removed": REMOVED_P}),
          record(BETA, 0, "delete_feeling", REFERENCE, REFERENCE, {}),
          record(BETA, 1, "reset_relationship", REFERENCE, REFERENCE, {}),
          record(BETA, 2, "clear_feelings", REFERENCE, REFERENCE, {})],
}


def blank():
    return {"critical": [], "confirmed": [], "rejected": [], "added": [], "evidence": f"{SECRET} evidence"}


def companion_world(tmp_path, mapping=None, records=None):
    """A synthetic companion scenario, its three arms' run directories, blinded mapping and review files."""
    scenario = tmp_path / "practice.py"
    scenario.write_text(SCENARIO)
    review, blind = tmp_path / "review", tmp_path / "blind"
    mapping = mapping or {"S01-case": {"A": "E", "B": "F", "C": "P"}, "S02-case": {"A": "P", "B": "E", "C": "F"}}
    put(blind / "sealed_practice.json", mapping)
    verdict = {case: {label: {"score_ignoring_critical": 1, "critical": [], "reason": f"{SECRET} reason"}
                      for label in "ABC"} for case in ("S01-case", "S02-case")}
    for label in "AB":
        verdict["S01-case"][label]["critical"] = [8]
    verdict["S02-case"]["A"]["critical"] = [8]
    put(review / "verdicts-practice.json", verdict)
    first = {label: blank() for label in "ABC"}
    for label in "AB":
        first[label].update(critical=[8], confirmed=[8])
    first["C"].update(critical=[8], added=[8])
    put(review / "recheck-practice" / "S01-case.json", first)
    second = {label: blank() for label in "ABC"}
    second["A"].update(rejected=[8])
    put(review / "recheck-practice" / "S02-case.json", second)
    runs = []
    for arm, entries in (records or RECORDS).items():
        run = tmp_path / f"run-{arm}"
        run.mkdir()
        (run / "results_practice_X.jsonl").write_text(json.dumps(
            {"arm": arm, "scenario": "practice", "session": ALPHA, "turn": 0, "reply": f"{SECRET} reply"}) + "\n")
        (run / "page-actions.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in entries))
        runs.append(run)
    return scenario, review, blind, runs


def strings(value):
    """Every key and string value in a JSON document."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


BOTH_SIDES = [[1, 1, "assistant"], [1, 1, "user"]]
OUTCOMES = {  # What each arm's actions before S01-case removed: message positions (session index, message), kinds.
    "P": [(BOTH_SIDES, []), ([], ["feelings"]), ([], []), ([], ["shared_moments", "familiarity"])],
    "E": [([[1, 1, "user"]], []), ([], ["feelings"]), ([], []), ([], ["shared_moments"])],
    "F": [(BOTH_SIDES, []), ([], []), ([], []), ([], [])],  # The reference history holds only the conversation.
}


@pytest.mark.parametrize("mapping", [
    {"S01-case": {"A": "E", "B": "F", "C": "P"}, "S02-case": {"A": "P", "B": "E", "C": "F"}},
    {"S01-case": {"A": "F", "B": "P", "C": "E"}, "S02-case": {"A": "E", "B": "F", "C": "P"}},
])
def test_actions_digest_reports_actual_removals_per_blinded_label(pipeline, tmp_path, mapping):
    scenario, review, blind, runs = companion_world(tmp_path, mapping)
    pipeline.actions_digest(review, blind, str(scenario), "practice", runs)
    written = json.loads((review / "actions-practice.json").read_text())
    assert written["stage"] == "resolution" and "resolution reviewer only" in written["disclosure"]
    assert any("suggest which assistant" in item for item in written["limitations"])
    digest = written["replies"]
    # Only replies with a candidate type 8 mark: S01 A and B (first reviewer), C (added), S02 A (later rejected).
    assert sorted(digest) == ["S01-case/A", "S01-case/B", "S01-case/C", "S02-case/A"]
    assert digest["S02-case/A"] == {"session": 1, "message": 2, "actions": []}
    for label, arm in mapping["S01-case"].items():
        entry = digest[f"S01-case/{label}"]
        assert (entry["session"], entry["message"]) == (2, 2)
        assert [(item["action"], item["session"], item["before_message"]) for item in entry["actions"]] == [
            ("delete_message", 2, 1), ("delete_feeling", 2, 1), ("add_boundary", 2, 2),
            ("reset_relationship", 2, 2)]  # Not the clear_feelings after the case's message.
        assert [(item["removed_messages"], item["removed_records"]) for item in entry["actions"]] == OUTCOMES[arm]
        # No counts, state or comparison with the other replies: only what this reply's world lost.
        assert all(set(item) == {"action", "session", "before_message", "removed_messages", "removed_records"}
                   for item in entry["actions"])


def test_actions_digest_is_arm_blind_and_holds_no_content(pipeline, tmp_path, capsys):
    scenario, review, blind, runs = companion_world(tmp_path)
    pipeline.actions_digest(review, blind, str(scenario), "practice", runs)
    text = (review / "actions-practice.json").read_text()
    printed = capsys.readouterr().out
    assert SECRET.casefold() not in (text + printed).casefold()
    found = set(strings(json.loads(text)))
    assert not found & {"P", "E", "F", "arm", "arms", "sealed", "detail", "time", "mood", "boundaries", "deltas",
                        "before", "after", "same_for_all_labels", "messages", "history_items"}
    assert all(not value.endswith(("/P", "/E", "/F")) for value in found)


@pytest.mark.parametrize("damage", ["failed", "missing", "extra", "wrong_kind", "unknown_position", "f_kept"])
def test_actions_digest_refuses_incomplete_or_failed_action_evidence(pipeline, tmp_path, damage):
    records = json.loads(json.dumps(RECORDS))
    if damage == "failed":
        records["E"][1]["result"] = {"failed": f"no feeling '{SECRET}'"}
    elif damage == "missing":
        records["E"].pop(2)
    elif damage == "extra":
        records["F"].append(records["E"][2])
    elif damage == "wrong_kind":
        records["P"][1]["action"] = "clear_feelings"
    elif damage == "unknown_position":
        records["P"][0]["result"]["removed"].append([f"{SECRET}-elsewhere", 0, "user"])
    else:
        records["F"][0]["after"]["removed_still_in_history"] = 1
    scenario, review, blind, runs = companion_world(tmp_path, records=records)
    with pytest.raises(SystemExit) as refused:
        pipeline.actions_digest(review, blind, str(scenario), "practice", runs)
    assert SECRET not in str(refused.value)
    assert not (review / "actions-practice.json").exists()


def test_actions_digest_is_written_once_and_needs_every_sealed_arm(pipeline, tmp_path):
    scenario, review, blind, runs = companion_world(tmp_path)
    with pytest.raises(SystemExit, match="not the arms of the sealed mapping"):
        pipeline.actions_digest(review, blind, str(scenario), "practice", runs[:2])
    result = subprocess.run([sys.executable, pipeline.__file__, "actions-digest", str(review), str(blind),
                             str(scenario), "practice", *map(str, runs)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert SECRET not in result.stdout and json.loads((review / "actions-practice.json").read_text())
    with pytest.raises(SystemExit, match="written once"):
        pipeline.actions_digest(review, blind, str(scenario), "practice", runs)


@pytest.mark.parametrize("stage", ["second review missing", "second review incomplete", "resolution exists"])
def test_actions_digest_is_made_only_for_the_resolution_stage(pipeline, tmp_path, stage):
    scenario, review, blind, runs = companion_world(tmp_path)
    if stage == "second review missing":
        (review / "recheck-practice" / "S02-case.json").unlink()
    elif stage == "second review incomplete":
        put(review / "recheck-practice" / "S02-case.json", {"A": blank()})
    else:
        put(review / "resolution-practice.json", {})
    with pytest.raises(SystemExit, match="second review is complete|resolution already exists"):
        pipeline.actions_digest(review, blind, str(scenario), "practice", runs)
    assert not (review / "actions-practice.json").exists()


def test_no_earlier_stage_command_reads_the_actions_digest(pipeline):
    import inspect

    readers = {name for name, function in inspect.getmembers(pipeline, inspect.isfunction)
               if function.__module__ == pipeline.__name__ and "actions-" in inspect.getsource(function)}
    # Written by actions_digest, read only by the tally that applies the resolution (and its rule check).
    assert readers == {"actions_digest", "tally", "_resolution_change_problem"}


def test_tally_refuses_an_actions_file_not_made_by_the_digest_command(pipeline, tmp_path):
    scenario, blind = resolution_world(tmp_path, first=[8], confirmed=[8], change={
        "remove": [8], "rules": {"8": "RC2"}, "reason": "RC2: nothing removed"})
    put(tmp_path / "actions-practice.json", {"S01-practice/A": {"session": 1, "message": 1, "actions": []}})
    with pytest.raises(SystemExit, match="invalid actions digest"):
        pipeline.tally(tmp_path, blind, str(scenario), "practice", companion=True)


# S3: C5 resolution changes are checked against the rule that may make them and its evidence ------------------------

def resolution_world(tmp_path, first, confirmed=(), added=(), conditions=(), change=None, r5=None, digest=False):
    """One synthetic case whose reply A has these first-review marks, second-review decisions and resolution."""
    scenario = tmp_path / "practice.py"
    scenario.write_text('CASES = [(0, 0, "S01-practice", "A public synthetic practice case")]\n')
    verdict = {label: {"score_ignoring_critical": 1, "critical": []} for label in "ABC"}
    verdict["A"].update(critical=list(first), conditions=[{"type": mark, "condition": "practice"}
                                                         for mark in conditions])
    put(tmp_path / "verdicts-practice.json", {"S01-practice": verdict})
    second = {label: {"critical": [], "confirmed": [], "rejected": [], "added": [], "evidence": ""}
              for label in "ABC"}
    second["A"].update(critical=sorted({*confirmed, *added}), confirmed=list(confirmed), added=list(added),
                       rejected=[mark for mark in first if mark not in confirmed], evidence="Practice evidence.")
    put(tmp_path / "recheck-practice" / "S01-practice.json", second)
    put(tmp_path / "blind" / "sealed_practice.json", {"S01-practice": {"A": "P", "B": "E", "C": "F"}})
    if change is not None:
        put(tmp_path / "resolution-practice.json", {"S01-practice/A": change})
    if r5 is not None:
        put(tmp_path / "r5-practice" / "S01-A.json", {"type4_cleared": r5})
    if digest:
        put(tmp_path / "actions-practice.json", {"stage": "resolution", "replies": {
            "S01-practice/A": {"session": 1, "message": 1, "actions": []}}})
    return scenario, tmp_path / "blind"


def resolved(pipeline, tmp_path, scenario, blind):
    pipeline.tally(tmp_path, blind, str(scenario), "practice", companion=True)
    return json.loads((tmp_path / "tally-practice.json").read_text())["rows"][0]["resolved"]


VALID = {
    "R5 clears type 4": (dict(first=[4], confirmed=[4], r5=True,
                              change={"remove": [4], "rules": {"4": "R5"}, "reason": "R5 result cleared it"}), []),
    "RC1 removes type 6": (dict(first=[6], confirmed=[6],
                                change={"remove": [6], "rules": {"6": "RC1"}, "reason": "RC1: said in s1/2"}), []),
    "RC2 removes type 8": (dict(first=[8], confirmed=[8], digest=True,
                                change={"remove": [8], "rules": {"8": "RC2"}, "reason": "RC2: nothing removed"}), []),
    "RC2 adds type 8": (dict(first=[8], digest=True,
                             change={"add": [8], "rules": {"8": "RC2"}, "reason": "RC2: action 2/1 removed it"}), [8]),
    "R3 removes an added 7": (dict(first=[], added=[7],
                                   change={"remove": [7], "rules": {"7": "R3"}, "reason": "R3: no quoted line"}), []),
    "R2 re-checks 4 as 3": (dict(first=[4], confirmed=[4], change={
        "remove": [4], "add": [3], "rules": {"4": "R2", "3": "R2"}, "reason": "R2: corrected in s1/3"}), [3]),
    "R2 adds a rejected 4": (dict(first=[4], change={"add": [4], "rules": {"4": "R2"}, "reason": "R2: never said"}),
                             [4]),
    "R1 settles a condition": (dict(first=[2], confirmed=[2], conditions=[2], change={
        "remove": [2], "rules": {"2": "R1"}, "reason": "R1: the condition is false"}), []),
    "mixed rules": (dict(first=[4, 6, 8], confirmed=[4, 6, 8], r5=True, change={
        "remove": [4, 6], "rules": {"4": "R5", "6": "RC1"}, "reason": "R5 cleared; RC1 said in s1/2"}), [8]),
}


@pytest.mark.parametrize("name", VALID)
def test_companion_tally_accepts_changes_made_by_their_rule_on_its_evidence(pipeline, tmp_path, name):
    arguments, expected = VALID[name]
    scenario, blind = resolution_world(tmp_path, **arguments)
    assert resolved(pipeline, tmp_path, scenario, blind) == expected


REFUSED = {
    "no rule tag": (dict(first=[4], confirmed=[4], r5=True, change={"remove": [4], "reason": "R5 cleared"}),
                    "rule tag"),
    "a type without its tag": (dict(first=[4, 6], confirmed=[4, 6], r5=True, change={
        "remove": [4, 6], "rules": {"4": "R5"}, "reason": "R5 cleared"}), "rule tag"),
    "unknown rule": (dict(first=[4], confirmed=[4], change={"remove": [4], "rules": {"4": "R9"}, "reason": "R9"}),
                     "no known rule tag"),
    "R5 on type 6": (dict(first=[6], confirmed=[6], r5=True,
                          change={"remove": [6], "rules": {"6": "R5"}, "reason": "R5"}), "R5 cannot change type 6"),
    "R5 on type 7": (dict(first=[7], confirmed=[7], r5=True,
                          change={"remove": [7], "rules": {"7": "R5"}, "reason": "R5"}), "R5 cannot change type 7"),
    "R5 on type 8": (dict(first=[8], confirmed=[8], r5=True,
                          change={"remove": [8], "rules": {"8": "R5"}, "reason": "R5"}), "R5 cannot change type 8"),
    "R5 on type 9": (dict(first=[9], confirmed=[9], r5=True,
                          change={"remove": [9], "rules": {"9": "R5"}, "reason": "R5"}), "R5 cannot change type 9"),
    "R5 without a result": (dict(first=[4], confirmed=[4],
                                 change={"remove": [4], "rules": {"4": "R5"}, "reason": "R5"}), "does not clear"),
    "R5 not cleared": (dict(first=[4], confirmed=[4], r5=False,
                            change={"remove": [4], "rules": {"4": "R5"}, "reason": "R5"}), "does not clear"),
    "RC1 on type 8": (dict(first=[8], confirmed=[8], digest=True,
                           change={"remove": [8], "rules": {"8": "RC1"}, "reason": "RC1"}), "RC1 cannot change type 8"),
    "RC2 on type 6": (dict(first=[6], confirmed=[6], digest=True,
                           change={"remove": [6], "rules": {"6": "RC2"}, "reason": "RC2"}), "RC2 cannot change type 6"),
    "R3 on type 8": (dict(first=[8], confirmed=[8],
                          change={"remove": [8], "rules": {"8": "R3"}, "reason": "R3"}), "R3 cannot change type 8"),
    "R3 on type 6": (dict(first=[6], confirmed=[6],
                          change={"remove": [6], "rules": {"6": "R3"}, "reason": "R3"}), "R3 cannot change type 6"),
    "R2 on type 7": (dict(first=[7], confirmed=[7],
                          change={"remove": [7], "rules": {"7": "R2"}, "reason": "R2"}), "R2 cannot change type 7"),
    "R1 on type 9": (dict(first=[9], confirmed=[9], conditions=[9],
                          change={"remove": [9], "rules": {"9": "R1"}, "reason": "R1"}), "R1 cannot change type 9"),
    "R1 on type 1": (dict(first=[1], confirmed=[1], conditions=[1],
                          change={"remove": [1], "rules": {"1": "R1"}, "reason": "R1"}), "R1 cannot change type 1"),
    "R1 on type 4": (dict(first=[4], confirmed=[4], conditions=[4],
                          change={"remove": [4], "rules": {"4": "R1"}, "reason": "R1"}), "R1 cannot change type 4"),
    "R1 on another type's condition": (dict(first=[3, 5], confirmed=[3, 5], conditions=[5], change={
        "remove": [3], "rules": {"3": "R1"}, "reason": "R1"}), "no condition for type 3"),
    "R3 on a mark both made": (dict(first=[7], confirmed=[7],
                                    change={"remove": [7], "rules": {"7": "R3"}, "reason": "R3"}), "R3 removes only"),
    "R3 adding": (dict(first=[9], change={"add": [9], "rules": {"9": "R3"}, "reason": "R3"}), "can only remove"),
    "R5 adding": (dict(first=[4], r5=True, change={"add": [4], "rules": {"4": "R5"}, "reason": "R5"}),
                  "can only remove"),
    "RC1 adding an unmade mark": (dict(first=[], change={"add": [6], "rules": {"6": "RC1"}, "reason": "RC1"}),
                                  "no reviewer made it"),
    "R2 type 3 without a 1 or 4": (dict(first=[2], confirmed=[2], change={
        "add": [3], "rules": {"3": "R2"}, "reason": "R2"}), "R2 only adds type 3"),
    "reason without the rule": (dict(first=[6], confirmed=[6], change={
        "remove": [6], "rules": {"6": "RC1"}, "reason": "said in s1/2"}), "does not name RC1"),
    "RC2 without the digest": (dict(first=[8], confirmed=[8], change={
        "remove": [8], "rules": {"8": "RC2"}, "reason": "RC2"}), "no entry"),
    "R1 without a condition": (dict(first=[2], confirmed=[2], change={
        "remove": [2], "rules": {"2": "R1"}, "reason": "R1"}), "no condition"),
    "removing a mark that does not stand": (dict(first=[6], change={
        "remove": [6], "rules": {"6": "RC1"}, "reason": "RC1"}), "does not stand literally"),
    "adding a mark that stands": (dict(first=[8], confirmed=[8], digest=True, change={
        "add": [8], "rules": {"8": "RC2"}, "reason": "RC2"}), "already stands"),
}


@pytest.mark.parametrize("name", REFUSED)
def test_companion_tally_refuses_changes_outside_their_rule(pipeline, tmp_path, name):
    arguments, message = REFUSED[name]
    scenario, blind = resolution_world(tmp_path, **arguments)
    with pytest.raises(SystemExit, match=f"invalid resolution: S01-practice/A: .*{message}"):
        pipeline.tally(tmp_path, blind, str(scenario), "practice", companion=True)
    assert not (tmp_path / "tally-practice.json").exists()


def test_companion_tally_refuses_a_resolution_for_an_unknown_reply(pipeline, tmp_path):
    scenario, blind = resolution_world(tmp_path, first=[])
    put(tmp_path / "resolution-practice.json", {"S01-practice/D": {"remove": [4], "reason": "R5"}})
    with pytest.raises(SystemExit, match="invalid resolution: every entry"):
        pipeline.tally(tmp_path, blind, str(scenario), "practice", companion=True)


def test_r4_tally_keeps_its_untagged_resolutions(pipeline, tmp_path):
    """R4 semantics stay exactly as they were: no rule tags, R5 evidence or digest are required."""
    scenario, blind = resolution_world(tmp_path, first=[4], confirmed=[4],
                                       change={"remove": [4], "reason": "practice evidence"})
    pipeline.tally(tmp_path, blind, str(scenario), "practice")
    assert json.loads((tmp_path / "tally-practice.json").read_text())["rows"][0]["resolved"] == []


# S2: tallies and gates bound to the frozen attempt manifest -------------------------------------------------------

# Arbitrary keys: nothing in the pipeline may assume the plan's own key names.
PAIRS = {"R4": ["core-x", "core-y"], "C5": ["comp-x", "comp-y"]}


def synthetic_attempt(tmp_path):
    """Four synthetic scenarios with complete, critical-free review files, and the manifest that freezes them."""
    review, blind = tmp_path / "review", tmp_path / "blind"
    pairs, files = [], {}
    for number, (gate_name, keys) in enumerate(PAIRS.items()):
        scenarios = []
        for index, key in enumerate(keys):
            case = f"S{number}{index}-practice"
            path = f"evaluations/practice-{key}.py"
            scenario = tmp_path / path
            scenario.parent.mkdir(parents=True, exist_ok=True)
            scenario.write_text(f'CASES = [(0, 0, "{case}", "A public synthetic practice case")]\n')
            put(review / f"verdicts-{key}.json",
                {case: {label: {"score_ignoring_critical": 1, "critical": []} for label in "ABC"}})
            put(review / f"recheck-{key}" / f"{case}.json",
                {label: {"critical": [], "confirmed": [], "rejected": [], "added": [], "evidence": ""}
                 for label in "ABC"})
            put(blind / f"sealed_practice-{key}.json", {case: {"A": "P", "B": "E", "C": "F"}})
            digest = pipeline_sha(scenario)
            scenarios.append({"key": key, "path": path, "sha256": digest})
            files[path] = digest
        pairs.append({"gate": gate_name, "scenarios": scenarios})
    manifest = {"version": 1, "attempt_id": "synthetic-attempt", "files": files, "pairs": pairs,
                "order": [key for keys in PAIRS.values() for key in keys]}
    return review, blind, put(tmp_path / "manifest.json", manifest), manifest


def pipeline_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scenario_path(tmp_path, key):
    return str(tmp_path / f"evaluations/practice-{key}.py")


def tally_all(pipeline, tmp_path, review, blind, path, gate_name):
    for key in PAIRS[gate_name]:
        pipeline.tally(review, blind, scenario_path(tmp_path, key), key, companion=gate_name == "C5", manifest=path)


def test_load_manifest_returns_a_valid_manifest(pipeline, tmp_path):
    _, _, path, manifest = synthetic_attempt(tmp_path)
    assert pipeline.load_manifest(path) == manifest
    assert [item["key"] for item in pipeline.manifest_scenarios(manifest, "C5")] == PAIRS["C5"]


def first_scenario(manifest):
    return manifest["pairs"][0]["scenarios"][0]


@pytest.mark.parametrize("damage", {
    "extra field": lambda m: m.update(extra=1),
    "missing field": lambda m: m.pop("files"),
    "version": lambda m: m.update(version=2),
    "boolean version": lambda m: m.update(version=True),
    "empty attempt": lambda m: m.update(attempt_id=" "),
    "duplicate key": lambda m: m["pairs"][1]["scenarios"][0].update(key="core-x"),
    "order misses a key": lambda m: m["order"].pop(),
    "order has an unknown key": lambda m: m["order"].append("other"),
    "order repeats a key": lambda m: m["order"].__setitem__(1, "core-x"),
    "unknown gate": lambda m: m["pairs"][0].update(gate="R6"),
    "two R4 pairs": lambda m: m["pairs"][1].update(gate="R4"),
    "no pairs": lambda m: m.update(pairs=[], order=[]),
    "empty pair": lambda m: m["pairs"][1].update(scenarios=[]),
    "extra scenario field": lambda m: first_scenario(m).update(note="x"),
    "bad hash": lambda m: first_scenario(m).update(sha256="ABC"),
    "absolute path": lambda m: first_scenario(m).update(path="/tmp/practice.py"),
    "parent path": lambda m: first_scenario(m).update(path="../practice.py"),
    "not a scenario file": lambda m: first_scenario(m).update(path="evaluations/practice.json"),
    "duplicate stem": lambda m: first_scenario(m).update(path="other/practice-core-y.py"),
    "hash differs from files": lambda m: first_scenario(m).update(sha256="0" * 64),
    "bad files entry": lambda m: m["files"].update({"/abs.py": "0" * 64}),
    "unsafe key": lambda m: (first_scenario(m).update(key="../x"), m["order"].__setitem__(0, "../x")),
}.items(), ids=lambda item: item[0] if isinstance(item, tuple) else None)
def test_load_manifest_refuses_an_invalid_structure(pipeline, tmp_path, damage):
    _, _, path, manifest = synthetic_attempt(tmp_path)
    damage[1](manifest)
    put(path, manifest)
    with pytest.raises(pipeline.ManifestError, match="invalid manifest"):
        pipeline.load_manifest(path)
    assert issubclass(pipeline.ManifestError, ValueError)


def test_every_tally_records_its_scenario_key_stem_and_hash(pipeline, tmp_path):
    review, blind, path, manifest = synthetic_attempt(tmp_path)
    pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x")
    data = json.loads((review / "tally-core-x.json").read_text())
    assert data["scenario"] == {"key": "core-x", "stem": "practice-core-x", "sha256": first_scenario(manifest)["sha256"]}
    assert "manifest" not in data
    pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x", manifest=path)
    assert json.loads((review / "tally-core-x.json").read_text())["manifest"] == {
        "attempt_id": "synthetic-attempt", "sha256": pipeline_sha(path)}


def test_tally_with_a_manifest_refuses_a_scenario_outside_its_gate_or_changed(pipeline, tmp_path):
    review, blind, path, _ = synthetic_attempt(tmp_path)
    with pytest.raises(SystemExit, match="not in the manifest's C5 pair"):
        pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x", companion=True, manifest=path)
    with pytest.raises(SystemExit, match="not in the manifest's R4 pair"):
        pipeline.tally(review, blind, scenario_path(tmp_path, "comp-x"), "comp-x", manifest=path)
    with pytest.raises(SystemExit, match="not the manifest's 'core-x' scenario"):
        pipeline.tally(review, blind, scenario_path(tmp_path, "core-y"), "core-x", manifest=path)
    with open(scenario_path(tmp_path, "core-x"), "a") as stream:
        stream.write("# changed after freezing\n")
    with pytest.raises(SystemExit, match="not the manifest's 'core-x' scenario"):
        pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x", manifest=path)
    assert not (review / "tally-core-x.json").exists()


@pytest.mark.parametrize("gate_name", ["R4", "C5"])
def test_each_gate_takes_exactly_its_manifest_pair_independently(pipeline, tmp_path, gate_name):
    review, blind, path, manifest = synthetic_attempt(tmp_path)
    tally_all(pipeline, tmp_path, review, blind, path, gate_name)  # The other pair is never tallied or read.
    companion, keys = gate_name == "C5", PAIRS[gate_name]
    result = pipeline.gate(review, list(reversed(keys)), companion=companion, manifest=path)
    assert result[gate_name] is True
    assert result["manifest"]["attempt_id"] == "synthetic-attempt"
    assert sorted(item["key"] for item in result["manifest"]["scenarios"]) == sorted(keys)
    put(review / "tally-extra.json", json.loads((review / f"tally-{keys[0]}.json").read_text()))
    for wrong in (keys[:1], [*keys, "extra"]):
        with pytest.raises(SystemExit, match=f"gate {gate_name} needs exactly"):
            pipeline.gate(review, wrong, companion=companion, manifest=path)


@pytest.mark.parametrize("damage", ["no manifest", "other manifest", "hash", "stem", "key"])
def test_gate_with_a_manifest_refuses_a_tally_not_bound_to_it(pipeline, tmp_path, damage):
    review, blind, path, manifest = synthetic_attempt(tmp_path)
    tally_all(pipeline, tmp_path, review, blind, path, "R4")
    target = review / "tally-core-y.json"
    data = json.loads(target.read_text())
    if damage == "no manifest":
        data.pop("manifest")
    elif damage == "other manifest":
        data["manifest"]["sha256"] = "0" * 64
    elif damage == "hash":
        data["scenario"]["sha256"] = "0" * 64
    elif damage == "stem":
        data["scenario"]["stem"] = "practice-core-x"
    else:
        data["scenario"]["key"] = "core-x"
    put(target, data)
    with pytest.raises(SystemExit, match="invalid tally tally-core-y.json: not"):
        pipeline.gate(review, PAIRS["R4"], manifest=path)
    assert not (review / "gate.json").exists()


def test_gate_without_a_manifest_still_accepts_historical_tallies(pipeline, tmp_path):
    review, blind, path, _ = synthetic_attempt(tmp_path)
    tally_all(pipeline, tmp_path, review, blind, path, "R4")
    for key in PAIRS["R4"]:  # A historical tally has no scenario or manifest record.
        data = json.loads((review / f"tally-{key}.json").read_text())
        put(review / f"tally-{key}.json", {field: data[field] for field in ("totals", "rows")})
    assert pipeline.gate(review, PAIRS["R4"])["R4"] is True
    with pytest.raises(SystemExit, match="not the manifest's"):
        pipeline.gate(review, PAIRS["R4"], manifest=path)


def r4_reply_with_type4(review, change, r5=None):
    """Reply A of the R4 scenario core-x gets a confirmed type 4 mark, a resolution and maybe an R5 result."""
    case = "S00-practice"
    verdict = json.loads((review / "verdicts-core-x.json").read_text())
    verdict[case]["A"].update(critical=[4], conditions=[{"type": 4, "condition": "practice"}])
    put(review / "verdicts-core-x.json", verdict)
    second = json.loads((review / "recheck-core-x" / f"{case}.json").read_text())
    second["A"].update(critical=[4], confirmed=[4], evidence="Practice evidence.")
    put(review / "recheck-core-x" / f"{case}.json", second)
    put(review / "resolution-core-x.json", {f"{case}/A": change})
    if r5 is not None:
        put(review / "r5-core-x" / "S00-A.json", {"type4_cleared": r5})


R4_REFUSED = {
    "untagged": ({"remove": [4], "reason": "R5 cleared it"}, True, "rule tag"),
    "R5 without a clearing result": ({"remove": [4], "rules": {"4": "R5"}, "reason": "R5"}, False, "does not clear"),
    "R5 without any result": ({"remove": [4], "rules": {"4": "R5"}, "reason": "R5"}, None, "does not clear"),
    "R1 on type 4": ({"remove": [4], "rules": {"4": "R1"}, "reason": "R1"}, None, "R1 cannot change type 4"),
    "R3 on type 4": ({"remove": [4], "rules": {"4": "R3"}, "reason": "R3"}, None, "R3 cannot change type 4"),
    "reason without the rule": ({"remove": [4], "rules": {"4": "R2"}, "reason": "never said"}, None,
                                "does not name R2"),
}


@pytest.mark.parametrize("name", R4_REFUSED)
def test_manifest_bound_r4_tally_enforces_rule_tags_and_r5_proof(pipeline, tmp_path, name):
    review, blind, path, _ = synthetic_attempt(tmp_path)
    change, r5, message = R4_REFUSED[name]
    r4_reply_with_type4(review, change, r5)
    with pytest.raises(SystemExit, match=f"invalid resolution: S00-practice/A: .*{message}"):
        pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x", manifest=path)
    assert not (review / "tally-core-x.json").exists()


def test_manifest_bound_r4_tally_accepts_a_proven_change_and_historical_tallies_stay_untagged(pipeline, tmp_path):
    review, blind, path, _ = synthetic_attempt(tmp_path)
    r4_reply_with_type4(review, {"remove": [4], "rules": {"4": "R5"}, "reason": "R5 cleared it"}, True)
    pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x", manifest=path)
    assert json.loads((review / "tally-core-x.json").read_text())["rows"][0]["resolved"] == []
    r4_reply_with_type4(review, {"remove": [4], "reason": "practice evidence"})  # Untagged, no R5 proof.
    pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x")  # No manifest: as before.
    assert json.loads((review / "tally-core-x.json").read_text())["rows"][0]["resolved"] == []
    with pytest.raises(SystemExit, match="invalid resolution: every entry"):
        put(review / "resolution-core-x.json", {"S00-practice/D": {"remove": [4], "reason": "R5"}})
        pipeline.tally(review, blind, scenario_path(tmp_path, "core-x"), "core-x", manifest=path)


def test_manifest_cli_for_tally_and_gate(pipeline, tmp_path):
    review, blind, path, _ = synthetic_attempt(tmp_path)
    script = pipeline.__file__
    for key in PAIRS["C5"]:
        result = subprocess.run([sys.executable, script, "tally", str(review), str(blind),
                                 scenario_path(tmp_path, key), key, "--companion", "--manifest", str(path)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    result = subprocess.run([sys.executable, script, "gate", str(review), "--manifest", str(path), *PAIRS["C5"],
                             "--companion"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((review / "gate-c5.json").read_text())["manifest"]["attempt_id"] == "synthetic-attempt"
    result = subprocess.run([sys.executable, script, "verdicts", "x", "y", "--manifest", str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 1 and "--manifest PATH is valid once for tally or gate" in result.stderr


# S5: R4 and C5 gates exit alike: the gate file is written first, then a failed gate exits nonzero --------------------

@pytest.mark.parametrize("gate_name", ["R4", "C5"])
@pytest.mark.parametrize("passes", [True, False])
def test_both_gates_write_their_file_then_exit_nonzero_only_on_failure(pipeline, tmp_path, gate_name, passes):
    rows = [{"case": "S01-practice", "label": label, "arm": arm, "base": 1, "literal": [], "resolved": []}
            for label, arm in zip("ABC", "PEF", strict=True)]
    totals = {"P": 1, "E": 1, "F": 1}
    if not passes:
        rows[0]["resolved"] = [4]  # A standing critical error in P with no attribution: memory-caused.
        totals["P"] = 0
    put(tmp_path / "tally-practice.json", {"totals": {"resolved": totals}, "rows": rows,
                                           **({"gate": "C5"} if gate_name == "C5" else {})})
    result = subprocess.run([sys.executable, pipeline.__file__, "gate", str(tmp_path), "practice",
                             *(["--companion"] if gate_name == "C5" else [])], capture_output=True, text=True)
    written = json.loads((tmp_path / ("gate-c5.json" if gate_name == "C5" else "gate.json")).read_text())
    assert written[gate_name] is passes
    assert result.returncode == (0 if passes else 1), result.stderr
