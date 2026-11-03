"""C5 harness hardening (no model call, no network): a degraded live arm stops, harness events carry no content,
failed extraction is reported, timed pauses are refused and unintended unrecorded turns are flagged."""
import importlib.util
import json
from pathlib import Path

import pytest

from membrain import evaluation_clock

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load("c5_harness_hardening", ROOT / "evaluations" / "c5-harness.py")
practice = _load("c5_practice_hardening", ROOT / "evaluations" / "c5-practice-scenario.py")


@pytest.fixture(autouse=True)
def clean_clock(monkeypatch):
    monkeypatch.delenv(evaluation_clock.ENV, raising=False)
    yield
    evaluation_clock.disable()


def _events(directory: Path) -> list:
    path = directory / "harness-events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# U2: a degraded live run stops ----------------------------------------------------------------------------------

def test_a_live_harness_event_is_recorded_then_stops_the_arm_and_blocks_the_ledger(tmp_path, monkeypatch):
    stops = []

    class Guard:
        def stop(self, reason):
            stops.append(reason)

    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setattr(harness, "BILLING", Guard())
    with pytest.raises(harness.DegradedRun) as stopped:
        harness.harness_event(tmp_path, "extraction_unfinished", session="s1", turn=2)
    # A SystemExit, so no `except Exception` on the way out swallows it, with a non-zero exit code; the main
    # block's cleanup (stop_started) still runs.
    assert isinstance(stopped.value, SystemExit) and not isinstance(stopped.value, Exception)
    assert stopped.value.code not in (0, None) and stopped.value.kind == "extraction_unfinished"
    assert stops == ["harness_degraded"]
    assert [event["kind"] for event in _events(tmp_path)] == ["extraction_unfinished"]


def test_a_live_stop_still_raises_when_the_ledger_cannot_be_blocked(tmp_path, monkeypatch):
    class Guard:
        def stop(self, reason):
            raise OSError("offline stop fixture")

    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setattr(harness, "BILLING", Guard())
    with pytest.raises(harness.DegradedRun):
        harness.harness_event(tmp_path, "page_action_failed", action="delete_note", session="s1", turn=0)


def test_a_stub_harness_event_is_recorded_and_the_run_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "STUB", True)
    harness.harness_event(tmp_path, "index_wait_timed_out")
    harness.harness_event(tmp_path, "clock_already_past", session="s2", behind_seconds=60)
    assert [event["kind"] for event in _events(tmp_path)] == ["index_wait_timed_out", "clock_already_past"]


def test_a_failed_page_action_event_names_a_code_never_the_scenarios_words():
    planted = "zq-planted-topic-7731"
    assert harness.failure_code({"failed": f"no boundary {planted!r}"}) == "not_found"
    assert harness.failure_code({"failed": "x", "differing_fields": ["voice"]}) == "card_differs"
    assert harness.failure_code({"failed": "x", "unknown_removed": 1}) == "unknown_removed"


def test_the_index_wait_event_names_no_brain(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(harness, "STUB", True)
    memory = object.__new__(harness.Memory)
    memory.host = SimpleNamespace(ready_client=lambda directory, user: None)
    memory.directory, memory.user = tmp_path / "brain-zq-planted-scenario-P", None
    monkeypatch.setattr(harness.time, "sleep", lambda seconds: None)
    memory.wait_until_indexed(timeout=0.01)
    (event,) = _events(tmp_path)
    assert event["kind"] == "index_wait_timed_out" and set(event) == {"time", "kind"}


def test_the_refused_connection_event_names_no_host(tmp_path, monkeypatch):
    import socket

    monkeypatch.setattr(harness, "STUB", True)
    monkeypatch.setattr(socket.socket, "connect", socket.socket.connect)
    harness.refuse_network(tmp_path)
    with socket.socket() as connection, pytest.raises(OSError):
        connection.connect(("192.0.2.1", 443))
    (event,) = _events(tmp_path)
    assert set(event) == {"time", "kind"} and "192.0.2.1" not in json.dumps(event)


def test_every_harness_event_call_passes_only_kinds_positions_and_counts():
    import ast

    allowed = {"session", "turn", "role", "action", "reason", "new_messages", "behind_seconds"}
    tree = ast.parse((ROOT / "evaluations" / "c5-harness.py").read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and getattr(node.func, "id", None) == "harness_event"]
    assert len(calls) >= 8
    for call in calls:
        assert {keyword.arg for keyword in call.keywords} <= allowed, ast.unparse(call)
        reason = next((keyword.value for keyword in call.keywords if keyword.arg == "reason"), None)
        if reason is not None:  # A reason is a fixed code, never the result's own message.
            assert ast.unparse(reason).startswith("failure_code("), ast.unparse(call)
