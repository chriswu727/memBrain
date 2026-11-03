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


# B3: failed extraction is reported ------------------------------------------------------------------------------

class _FailingExtractor:
    """A stub extraction transport that refuses every request (a 400, which is not retried)."""

    def __init__(self, script=None):
        self.key = None

    def __call__(self, request):
        import httpx

        return httpx.Response(400, json={"error": {"message": "stub extraction refused"}})


@pytest.fixture
def extraction_watch(tmp_path):
    import logging

    watch = harness.watch_extraction(tmp_path)
    yield watch
    logging.getLogger("membrain.extraction").removeHandler(watch)


def test_a_failed_extraction_is_read_from_the_extractors_own_status(tmp_path, extraction_watch):
    from membrain.extraction import record_outcome

    assert not extraction_watch.failed()
    record_outcome(tmp_path, saved=1)
    assert not extraction_watch.failed()
    record_outcome(tmp_path, error="HTTP 400")
    assert extraction_watch.failed() and not extraction_watch.failed()  # Each failure is reported once.
    record_outcome(tmp_path, skipped=True)
    assert extraction_watch.failed()


def test_a_failure_the_extractor_only_logs_is_detected(tmp_path, extraction_watch):
    import httpx

    from membrain.extraction import Extractor

    extractor = Extractor("http://stub.invalid", "stub", "stub", transport=httpx.MockTransport(_FailingExtractor()))
    extractor.submit(lambda: extractor.propose("I moved to Lisbon.", "Nice.", ""))
    extractor.wait(10)
    assert not extractor._queue.unfinished_tasks
    assert extraction_watch.failed()  # Extractor._run swallowed the HTTP error and only logged it.
    assert not extraction_watch.failed()


SCENARIO = '''
HOST = "You are a companion. Reply briefly."
SESSIONS_LONG = [
    ("s1", ["Today is Monday, March 2, 20:00. I moved to Lisbon for a design job.",
            "My sister Ana visits on the 14th.", "She loves tiles, by the way."]),
    ("s2", ["Today is Tuesday, March 3, 21:00. Ana booked her flight."]),
]
'''


def _free_ports(count: int) -> list:
    import socket

    sockets = [socket.socket() for _ in range(count)]
    try:
        for item in sockets:
            item.bind(("127.0.0.1", 0))
        return [item.getsockname()[1] for item in sockets]
    finally:
        for item in sockets:
            item.close()


@pytest.fixture
def stub_run(tmp_path, monkeypatch):
    """Runs one arm of a synthetic scenario through ``run`` in stub mode, on a real local service."""
    import logging
    import os
    import socket
    import time

    from membrain import embedded_database

    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    environment, handlers = dict(os.environ), list(logging.getLogger("membrain.extraction").handlers)
    monkeypatch.setattr(harness, "STUB", True)
    monkeypatch.setattr(socket.socket, "connect", socket.socket.connect)  # refuse_network replaces it.
    for name in ("MEMBRAIN_MODEL_CACHE", evaluation_clock.ENV):
        os.environ.pop(name, None)
    os.environ.update({"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1",
                       "MEMBRAIN_PORTS": ",".join(map(str, _free_ports(2)))})

    def run(arm, source, script_host=None):
        path = tmp_path / "zq-synthetic-scenario.py"
        path.write_text(source + f"\nSTUB_HOST = {script_host or {}!r}\n")
        out = tmp_path / f"run-{arm}"
        try:
            harness.run(arm, str(path), out)
        finally:
            harness.stop_started()
        rows = [json.loads(line) for line in (out / f"results_{path.stem}_{arm}.jsonl").read_text().splitlines()]
        return rows, _events(out)

    try:
        yield run
    finally:
        os.environ.clear()
        os.environ.update(environment)
        time.tzset()
        for handler in logging.getLogger("membrain.extraction").handlers:
            if handler not in handlers:
                logging.getLogger("membrain.extraction").removeHandler(handler)


def test_a_stub_proxy_run_reports_every_failed_extraction_turn_and_finishes(stub_run, monkeypatch, capsys):
    monkeypatch.setattr(harness, "StubExtractor", _FailingExtractor)
    rows, events = stub_run("E", SCENARIO)
    assert len(rows) == 4 and all(row["recorded"] for row in rows)  # A dry run records the event and goes on.
    failed = [(event["session"], event["turn"]) for event in events if event["kind"] == "extraction_failed"]
    assert failed == [("s1", 0), ("s1", 1), ("s1", 2), ("s2", 0)]
    assert all(set(event) == {"time", "kind", "session", "turn"} for event in events
               if event["kind"] == "extraction_failed")
    assert capsys.readouterr().out.rstrip().endswith("E zq-synthetic-scenario finished")

