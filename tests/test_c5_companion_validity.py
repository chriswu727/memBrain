"""Validity of a C5 (companion) run, on synthetic run directories (no service, no model): page-actions.jsonl holds
exactly the scenario's PAGE_ACTIONS in order, each done or not applicable for an allowed reason (reported, never
refused), never failed, F's outcome of each P's; F carried P's persona block at every turn; actions-digest keeps a
not-applicable action from looking like a removal. An R4 run (no page actions) is checked as before."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLANT = "zq-planted-6d1e"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pipeline():
    return _load("acceptance_review_companion_validity", ROOT / "evaluations" / "acceptance_review.py")


SESSIONS = [(f"{PLANT}-a", [f"Today is Monday, March 2, 20:00. {PLANT} one", f"{PLANT} two"]),
            (f"{PLANT}-b", [f"Today is Tuesday, March 3, 20:00. {PLANT} three", f"{PLANT} four"])]
ACTIONS = [(f"{PLANT}-b", 1, {"do": "clear_feelings"}),
           (f"{PLANT}-b", 0, {"do": "delete_message", "session": f"{PLANT}-a", "turn": 1}),
           (f"{PLANT}-b", 0, {"do": "remove_boundary", "topic": PLANT})]
ORDER = [1, 2, 0]  # Applied by position: both actions before message 1 of session 2, then the one before message 2.
BLOCK = f'<membrain-persona version="1">\n{PLANT} card\n</membrain-persona>'
SWITCHED = f'<membrain-persona version="2">\n{PLANT} other card\n</membrain-persona>'


def turn(version, block):
    return {"format": 1, "version": version, "sha256": hashlib.sha256(block.encode()).hexdigest() if block else None}


def record(index, status="done", reason=None, removed=None):
    session, before, action = ACTIONS[index]
    entry = {"format": 2, "index": index, "session": session, "before_turn": before, "action": action["do"],
             "detail": {}, "status": status, "before": {}, "after": {},
             "result": {"removed_records": removed or [], "removed_records_complete": True}}
    if reason:
        entry["reason"] = reason
    return entry


def world(tmp_path, *, p_actions=None, f_actions=None, f_blocks=None, actions=ACTIONS, write_actions=True):
    """A C5 scenario file and its two complete arms, with persona records and page actions as the harness writes."""
    scenario = tmp_path / "zq_companion.py"
    scenario.write_text(f"SESSIONS_LONG = {SESSIONS!r}\nPAGE_ACTIONS = {actions!r}\n")
    order = [(session, index) for session, turns in SESSIONS for index in range(len(turns))]
    blocks = [BLOCK, BLOCK, BLOCK, SWITCHED]  # The persona changed by the host's tool before the last turn.
    runs = []
    for number, arm in enumerate("PF"):
        run = tmp_path / f"k-{arm}"
        run.mkdir()
        rows = []
        for (session, index), block in zip(order, blocks):
            row = {"arm": arm, "scenario": scenario.stem, "session": session, "turn": index, "reply": "Hello",
                   "usage": {"prompt_tokens": 1}, "persona_turn": turn(1 if block == BLOCK else 2, block)}
            if arm == "P":
                row.update(persona_block=block, persona_shown_to_host=True, recorded=True)
            else:
                row["reference_persona"] = (f_blocks or blocks)[len(rows)]
            rows.append(row)
        (run / f"results_{scenario.stem}_{arm}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (run / "run.log").write_text(f"12:00:00 {arm} {scenario.stem} finished\n")
        (run / "persona.json").write_text(json.dumps({"arm": arm, "source": "seeded", "seed": "x", "preset": "enfp",
                                                      "card_sha256": "enfp", "version": 1}))
        start = 10 + 20 * number
        (run / "supervisor.log").write_text(f"started {start}\nfinished {start + 5}\ncleaned {start + 6}\n")
        entries = (p_actions if arm == "P" else f_actions)
        entries = entries if entries is not None else [record(index) for index in ORDER]
        if write_actions:
            (run / "page-actions.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in entries))
        runs.append(run)
    return scenario, runs


def test_a_companion_run_is_valid_and_reports_its_page_actions_and_persona_mirroring(pipeline, tmp_path, capsys):
    scenario, runs = world(tmp_path)
    result = pipeline.validity(runs, scenario, persona_preset="enfp")
    assert result["valid"], result["problems"]
    assert result["page_actions"] == {name: {"count": 3, "done": 3, "not_applicable": {"count": 0, "at": []}}
                                      for name in ("k-P (P)", "k-F (F)")}
    assert result["persona_mirroring"] == {"checked_turns": 4, "not_shown_to_p_host": {"count": 0, "positions": []}}
    assert PLANT not in capsys.readouterr().out


def test_a_not_applicable_action_is_reported_with_its_position_and_reason_never_refused(pipeline, tmp_path):
    entries = [record(1, "not_applicable", "message_not_recorded"), record(2), record(0)]
    # Since 2026-11-17 F still drops the message the user deleted, which P never recorded: the one asymmetry.
    f_entries = json.loads(json.dumps(entries))
    f_entries[0]["result"]["reference_removed"] = [[f"{PLANT}-a", 1, "user"]]
    f_entries[0]["after"] = {"removed_still_in_history": 0}
    scenario, runs = world(tmp_path, p_actions=entries, f_actions=f_entries)
    result = pipeline.validity(runs, scenario)
    assert result["valid"], result["problems"]
    assert result["page_actions"]["k-P (P)"] == {"count": 3, "done": 2, "not_applicable": {"count": 1, "at": [
        {"action": 2, "session": 2, "before_message": 1, "kind": "delete_message",
         "reason": "message_not_recorded"}]}}


@pytest.mark.parametrize("damage, problem", [
    ("failed", "page action 1 failed"),
    ("failed_result", "page action 1 failed"),
    ("unknown_reason", "has no valid status"),
    ("not_applicable_with_removal", "was not applicable but records removals"),
    ("missing", "does not hold exactly the scenario's PAGE_ACTIONS"),
    ("list_order", "does not hold exactly the scenario's PAGE_ACTIONS"),
    ("old_format", "does not hold exactly the scenario's PAGE_ACTIONS"),
    ("f_differs", "F's page-action outcomes are not P's"),
    ("no_file", "does not hold exactly the scenario's PAGE_ACTIONS"),
])
def test_page_action_evidence_that_is_not_exactly_the_scenarios_is_refused(pipeline, tmp_path, damage, problem):
    entries = [record(index) for index in ORDER]
    f_entries = [dict(entry) for entry in entries]
    if damage == "failed":
        entries[2] = record(0, "failed", "service_refused")
    elif damage == "failed_result":
        entries[2]["result"]["failed"] = f"{PLANT} message"
    elif damage == "unknown_reason":
        entries[2] = record(0, "not_applicable", f"{PLANT}_reason")
    elif damage == "not_applicable_with_removal":
        entries[2] = record(0, "not_applicable", "no_feeling_from_message",
                            removed=[{"kind": "feeling", "established": False}])
    elif damage == "missing":
        entries.pop()
    elif damage == "list_order":
        entries = [record(index) for index in range(3)]
    elif damage == "old_format":
        del entries[0]["format"]
    elif damage == "f_differs":
        f_entries[0] = record(1, "not_applicable", "message_already_removed")
    scenario, runs = world(tmp_path, p_actions=entries, f_actions=f_entries, write_actions=damage != "no_file")
    result = pipeline.validity(runs, scenario)
    assert not result["valid"] and any(problem in item for item in result["problems"]), result["problems"]
    assert PLANT not in json.dumps(result["problems"])


@pytest.mark.parametrize("damage", ["other_block", "other_identity", "no_record", "p_block_mismatch"])
def test_f_must_carry_ps_persona_block_at_every_turn(pipeline, tmp_path, damage):
    blocks = [BLOCK, BLOCK, BLOCK, SWITCHED]
    if damage == "other_block":  # F kept the starting card although P's host switched it.
        blocks = [BLOCK, BLOCK, BLOCK, BLOCK]
    scenario, runs = world(tmp_path, f_blocks=blocks)
    path = runs[1 if damage != "p_block_mismatch" else 0] / f"results_{scenario.stem}_{'F' if damage != 'p_block_mismatch' else 'P'}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if damage == "other_identity":
        rows[3]["persona_turn"] = turn(1, BLOCK)
    elif damage == "no_record":
        del rows[1]["persona_turn"]
    elif damage == "p_block_mismatch":
        rows[3]["persona_block"] = BLOCK
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = pipeline.validity(runs, scenario)
    assert not result["valid"]
    assert any("persona" in item for item in result["problems"]), result["problems"]


def test_a_turn_whose_persona_p_host_was_not_shown_is_reported_not_refused(pipeline, tmp_path):
    scenario, runs = world(tmp_path)
    path = runs[0] / f"results_{scenario.stem}_P.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[3]["persona_shown_to_host"] = False
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = pipeline.validity(runs, scenario)
    assert result["valid"] and result["persona_mirroring"]["not_shown_to_p_host"] == {"count": 1,
                                                                                         "positions": [[2, 2]]}


def test_an_r4_run_without_page_actions_or_persona_records_is_checked_as_before(pipeline, tmp_path):
    scenario, runs = world(tmp_path, actions=[], write_actions=False)
    for run in runs:
        path = next(run.glob("results_*.jsonl"))
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            for key in ("persona_turn", "persona_block", "reference_persona", "persona_shown_to_host"):
                row.pop(key, None)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = pipeline.validity(runs, scenario)
    assert result["valid"], result["problems"]
    assert result["page_actions"] == {} and result["persona_mirroring"]["checked_turns"] == 0
    # Required with --companion, and page actions recorded for a scenario without any are refused.
    result = pipeline.validity(runs, scenario, companion=True)
    assert not result["valid"] and any("persona" in item for item in result["problems"])
    (runs[0] / "page-actions.jsonl").write_text(json.dumps(record(0)) + "\n")
    result = pipeline.validity(runs, scenario)
    assert not result["valid"] and any("PAGE_ACTIONS" in item for item in result["problems"])


def test_the_validity_cli_takes_companion(pipeline, tmp_path):
    import subprocess
    import sys

    scenario, runs = world(tmp_path)
    done = subprocess.run([sys.executable, pipeline.__file__, "validity", "--scenario", str(scenario), "--companion",
                           *map(str, runs)], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["valid"] is True


# actions-digest and RC2: an action that found no target removed nothing, and says so ----------------------------

def test_the_digest_refuses_a_not_applicable_action_that_claims_a_removal(pipeline):
    sessions = [session for session, _ in SESSIONS]
    clean = record(1, "not_applicable", "message_not_recorded")
    assert pipeline._digest_outcome(clean, "P", sessions) == ([], True)
    for damage in ({"removed_records": [{"kind": "message", "established": False}]},
                   {"removed": [[SESSIONS[0][0], 1, "user"]]}, {"removed_records_complete": False}):
        damaged = json.loads(json.dumps(clean))
        damaged["result"].update(damage)
        with pytest.raises(SystemExit):
            pipeline._digest_outcome(damaged, "P", sessions)
    for status in ("failed", "skipped"):
        with pytest.raises(SystemExit):
            pipeline._digest_outcome({**record(0), "status": status}, "P", sessions)
    unknown = record(1, "not_applicable", f"{PLANT}_reason")
    with pytest.raises(SystemExit) as refused:
        pipeline._digest_outcome(unknown, "P", sessions)
    assert PLANT not in str(refused.value)


def test_the_pipeline_and_the_harness_agree_on_the_formats(pipeline):
    harness = _load("c5_harness_formats", ROOT / "evaluations" / "c5-harness.py")
    assert pipeline.NOT_APPLICABLE == harness.NOT_APPLICABLE
    assert pipeline.PAGE_RECORD_FORMAT == harness.PAGE_RECORD_FORMAT
    assert pipeline.PERSONA_TURN_FORMAT == harness.PERSONA_TURN_FORMAT
    assert pipeline._application_order(ACTIONS, [session for session, _ in SESSIONS]) == ORDER == \
        harness.application_order(ACTIONS, SESSIONS)
    block = "<membrain-persona>x</membrain-persona>"
    assert pipeline._persona_identity_ok(block, harness.persona_turn(3, block))
    assert pipeline._persona_identity_ok("", harness.persona_turn(0, ""))
