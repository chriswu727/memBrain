"""Hardening of the acceptance scoring pipeline after the independent plan review (I1, I5, S2, S3, S5).

Synthetic fixtures only, written to tmp_path. No model call, no held-out scenario, no database.
"""
import importlib.util
import json
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
