"""Hardening of the acceptance scoring pipeline after the independent plan review (I1, I5, S2, S3, S5).

Synthetic fixtures only, written to tmp_path. No model call, no held-out scenario, no database.
"""
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
    ({BETA!r}, 2, {{"do": "reset_relationship"}}),
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
          record(BETA, 2, "reset_relationship", world(), world(shared_moments=0, familiarity_days=0), {})],
    "E": [record(BETA, 0, "delete_message", world(feelings=2), world(messages=5, feelings=2),
                 {"deleted": 1, "removed": [[ALPHA, 0, "user"]]}),
          record(BETA, 0, "delete_feeling", world(feelings=2), world(feelings=1), {"deleted": 1}),
          record(BETA, 1, "add_boundary", world(boundaries=[]), world(), {}),
          record(BETA, 2, "reset_relationship", world(), world(shared_moments=0), {})],
    "F": [record(BETA, 0, "delete_message", {"history_items": 6, "persona_version": 1},
                 {**REFERENCE, "removed_still_in_history": 0}, {"deleted": 2, "removed": REMOVED_P}),
          record(BETA, 0, "delete_feeling", REFERENCE, REFERENCE, {}),
          record(BETA, 2, "reset_relationship", REFERENCE, REFERENCE, {})],
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


ZERO = {"messages": 0, "notes": 0, "feelings": 0, "shared_moments": 0, "familiarity_days": 0}
OUTCOMES = {  # What each arm's actions before S01-case removed, in scenario positions (session index, message).
    "P": [{"removed": [[1, 1, "assistant"], [1, 1, "user"]], "deltas": {**ZERO, "messages": -2}},
          {"removed": [], "deltas": {**ZERO, "feelings": -1}}, {"removed": [], "deltas": ZERO}],
    "E": [{"removed": [[1, 1, "user"]], "deltas": {**ZERO, "messages": -1}},
          {"removed": [], "deltas": {**ZERO, "feelings": -1}}, {"removed": [], "deltas": ZERO}],
    "F": [{"removed": [[1, 1, "assistant"], [1, 1, "user"]], "deltas": {**ZERO, "messages": -2}},
          {"removed": [], "deltas": ZERO}, {"removed": [], "deltas": ZERO}],
}


@pytest.mark.parametrize("mapping", [
    {"S01-case": {"A": "E", "B": "F", "C": "P"}, "S02-case": {"A": "P", "B": "E", "C": "F"}},
    {"S01-case": {"A": "F", "B": "P", "C": "E"}, "S02-case": {"A": "E", "B": "F", "C": "P"}},
])
def test_actions_digest_reports_actual_removals_per_blinded_label(pipeline, tmp_path, mapping):
    scenario, review, blind, runs = companion_world(tmp_path, mapping)
    pipeline.actions_digest(review, blind, str(scenario), "practice", runs)
    digest = json.loads((review / "actions-practice.json").read_text())
    # Only replies with a candidate type 8 mark: S01 A and B (first reviewer), C (added), S02 A (later rejected).
    assert sorted(digest) == ["S01-case/A", "S01-case/B", "S01-case/C", "S02-case/A"]
    assert digest["S02-case/A"] == {"session": 1, "message": 2, "actions": []}
    for label, arm in mapping["S01-case"].items():
        entry = digest[f"S01-case/{label}"]
        assert (entry["session"], entry["message"]) == (2, 2)
        assert [(item["action"], item["session"], item["before_message"]) for item in entry["actions"]] == [
            ("delete_message", 2, 1), ("delete_feeling", 2, 1), ("add_boundary", 2, 2)]  # Not the later reset.
        assert [{"removed": item["removed"], "deltas": item["deltas"]} for item in entry["actions"]] == OUTCOMES[arm]
        # The arms removed different messages and feelings; the arm-limited boundary removed nothing anywhere.
        assert [item["same_for_all_labels"] for item in entry["actions"]] == [False, False, True]


def test_actions_digest_is_arm_blind_and_holds_no_content(pipeline, tmp_path, capsys):
    scenario, review, blind, runs = companion_world(tmp_path)
    pipeline.actions_digest(review, blind, str(scenario), "practice", runs)
    text = (review / "actions-practice.json").read_text()
    printed = capsys.readouterr().out
    assert SECRET.casefold() not in (text + printed).casefold()
    found = set(strings(json.loads(text)))
    assert not found & {"P", "E", "F", "arm", "arms", "sealed", "detail", "time", "mood", "boundaries"}
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
