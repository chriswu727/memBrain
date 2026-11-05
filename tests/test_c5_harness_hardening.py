"""C5 harness hardening (no model call, no network): a degraded live arm stops, harness events carry no content,
failed extraction is reported, timed pauses are refused and unintended unrecorded turns are flagged."""
import importlib.util
import json
from pathlib import Path

import pytest

from membrain import evaluation_clock
from membrain import host as membrain_host

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
    # Brains already created are remembered by service URL; an earlier test's service may have had these ports.
    monkeypatch.setattr(membrain_host, "_ENSURED_BRAINS", set())
    for name in ("MEMBRAIN_MODEL_CACHE", evaluation_clock.ENV):
        os.environ.pop(name, None)
    os.environ.update({"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1",
                       "MEMBRAIN_PORTS": ",".join(map(str, _free_ports(2)))})

    def run(arm, source, script_host=None):
        """``source`` is a synthetic scenario's code, or the path of a public scenario file."""
        if isinstance(source, Path):
            path = source
        else:
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


# I3: timed pauses are refused; unintended unrecorded turns are flagged ------------------------------------------

class _NoToolCalls:
    def __init__(self):
        self.calls = []

    def call(self, server, name, arguments):
        self.calls.append((name, arguments))
        return json.dumps({"recording": "paused", "until": None})


def test_a_timed_pause_is_refused_with_a_tool_error_and_an_event(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "STUB", True)
    memory = _NoToolCalls()
    result = json.loads(harness.call_tool(memory, None, "memory_pause", {"hours": 2}, tmp_path, "s1", 3))
    assert "Timed pauses are unavailable in this evaluation" in result["error"] and memory.calls == []
    (event,) = _events(tmp_path)
    assert (event["kind"], event["session"], event["turn"]) == ("timed_pause_refused", "s1", 3)
    assert set(event) == {"time", "kind", "session", "turn"}
    # An untimed pause, and any other tool, reaches the plugin's tool as before.
    harness.call_tool(memory, None, "memory_pause", {}, tmp_path, "s1", 4)
    harness.call_tool(memory, None, "memory_pause", {"until_resumed": True, "hours": None}, tmp_path, "s1", 5)
    assert [name for name, _ in memory.calls] == ["memory_pause", "memory_pause"] and len(_events(tmp_path)) == 1


def test_a_live_timed_pause_stops_the_arm(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setattr(harness, "BILLING", None)
    with pytest.raises(harness.DegradedRun):
        harness.call_tool(_NoToolCalls(), None, "memory_pause", {"hours": 1}, tmp_path, "s1", 0)


def test_only_a_scripted_untimed_pause_and_resume_pair_is_intended():
    assert harness.intended_unrecorded(practice) == {("s7-recording", 0), ("s7-recording", 1)}

    class Scenario:
        SESSIONS_LONG = [("s1", ["a", "b", "c", "d"]), ("s2", ["e", "f"])]
        STUB_HOST = {("s1", 0): [{"tool": "memory_pause", "arguments": {"hours": 2}}],
                     ("s1", 1): [{"tool": "memory_resume", "arguments": {}}],
                     ("s1", 2): [{"tool": "memory_pause", "arguments": {}}],
                     ("s2", 0): [{"tool": "memory_resume", "arguments": {}}]}

    assert harness.intended_unrecorded(Scenario) == set()  # Timed, or a resume in another session.
    Scenario.EXPECT_RECORDING_P = [("s1", 2, False), ("s1", 3, False), ("s2", 0, True)]
    assert harness.intended_unrecorded(Scenario) == {("s1", 2), ("s1", 3)}


def test_a_stub_plugin_run_refuses_a_timed_pause_and_flags_an_unintended_unrecorded_turn(stub_run, capsys):
    script = {("s1", 0): [{"tool": "memory_pause", "arguments": {"hours": 2}}],
              ("s1", 1): [{"tool": "memory_pause", "arguments": {}}]}  # Never resumed: not intended.
    rows, events = stub_run("P", SCENARIO, script)
    assert [row["recorded"] for row in rows] == [True, False, False, True]
    assert "Timed pauses are unavailable" in rows[0]["tool_calls"][0]["result"]
    assert [(event["kind"], event["session"], event["turn"]) for event in events] == [
        ("timed_pause_refused", "s1", 0), ("turn_not_recorded", "s1", 1), ("turn_not_recorded", "s1", 2)]
    assert capsys.readouterr().out.rstrip().endswith("P zq-synthetic-scenario finished")


# A stopped live arm keeps the paid turn's row -------------------------------------------------------------------

def test_a_live_stop_during_a_turns_bookkeeping_waits_for_its_row(tmp_path, monkeypatch):
    stops = []

    class Guard:
        def stop(self, reason):
            stops.append(reason)

    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setattr(harness, "BILLING", Guard())
    with harness.deferred_stop([]) as stopping:
        harness.harness_event(tmp_path, "message_identity_unknown", session="s1", turn=0, role="user",
                              new_messages=0)
        harness.harness_event(tmp_path, "turn_not_recorded", session="s1", turn=0)
    assert stopping == ["message_identity_unknown", "turn_not_recorded"]
    assert stops == ["harness_degraded", "harness_degraded"]  # The ledger is blocked at once.
    with pytest.raises(harness.DegradedRun):  # Outside a turn's bookkeeping a live arm stops at the event.
        harness.harness_event(tmp_path, "index_wait_timed_out")


def test_a_live_arm_stopped_by_a_turns_event_writes_that_turns_row_first(stub_run, tmp_path, monkeypatch, capsys):
    review = _load("c5_acceptance_review_hardening", ROOT / "evaluations" / "acceptance_review.py")
    monkeypatch.setattr(harness, "StubExtractor", _FailingExtractor)
    monkeypatch.setattr(harness, "stops_on_events", lambda: True)  # The live stop, with the stub host and extractor.
    scenario = ROOT / "evaluations" / "c5-practice-scenario.py"
    with pytest.raises(harness.DegradedRun) as stopped:
        stub_run("E", scenario)
    assert stopped.value.kind == "extraction_failed" and stopped.value.code == 3
    directory = tmp_path / "run-E"
    (directory / "run.log").write_text(capsys.readouterr().out)
    (row,) = [json.loads(line) for line in (directory / f"results_{scenario.stem}_E.jsonl").read_text().splitlines()]
    assert (row["session"], row["turn"], row["stopped_after"]) == ("s1-arrival", 0, "extraction_failed")
    assert row["reply"].startswith("(stub reply") and row["usage"]["total_tokens"] > 0 and row["transcript"]
    assert row["input"] == practice.SESSIONS_LONG[0][1][0] and row["recorded"] is True
    assert [event["kind"] for event in _events(directory)] == ["extraction_failed"]
    result = review.validity([directory])
    assert result["valid"] is False and any("harness degradation extraction_failed" in problem
                                            for problem in result["problems"])


# Another arm stops the shared ledger during this arm's paid call (fakes only) -----------------------------------

class _FakeProvider:
    """The provider behind the real billing guard: fixed replies, billed usage, and a hook after a given call."""

    def __init__(self, after=None):
        self.models, self.after = [], after or {}
        self.messages = {}

    def __call__(self, request):
        import httpx

        model = json.loads(request.content)["model"]
        self.models.append(model)
        content = json.dumps({"notes": []}) if model == "fake-extract" else "Fake reply."
        response = httpx.Response(200, json={
            "model": model, "choices": [{"message": self.messages.get(
                len(self.models), {"role": "assistant", "content": content})}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        if len(self.models) in self.after:
            self.after[len(self.models)]()
        return response


@pytest.fixture
def shared_ledger(tmp_path, monkeypatch):
    """A fake live run: the real billing guard on a temporary shared ledger, a fake provider behind it, and a
    second guard on the same ledger standing for another arm."""
    import os

    import httpx

    budget = harness.billing_module()
    rate = {"context_tokens": 100_000, "max_output_tokens": 20_000, "input_cny_per_million": "1",
            "output_cny_per_million": "1"}
    path = tmp_path / "ledger.json"
    frozen = budget.create_ledger(path, run_id="fake-attempt", limit_cny="100",
                                  endpoint=harness.BASE_URL + "/chat/completions",
                                  models={harness.MODEL: rate, "fake-extract": rate})
    for name in [key for key in os.environ if key.startswith(("MEMORY_", "MEMBRAIN_EXTRACT", "MEMBRAIN_UPSTREAM"))
                 or key.endswith("_API_KEY")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    monkeypatch.setenv("EXTRACT_MODEL", "fake-extract")
    monkeypatch.setenv("C5_BILLING_LEDGER", str(path))
    monkeypatch.setenv("C5_ATTEMPT_ID", "fake-attempt")
    monkeypatch.setenv("C5_BILLING_POLICY_SHA256", frozen["policy_sha256"])
    provider = _FakeProvider()

    def guarded(**options):
        return budget.GuardedTransport(path, run_id="fake-attempt", policy_sha256=frozen["policy_sha256"],
                                       transport=httpx.MockTransport(provider), **options)

    monkeypatch.setattr(harness, "billing_transport", guarded)
    other_arm = budget.GuardedTransport(path, run_id="fake-attempt", policy_sha256=frozen["policy_sha256"])
    return SimpleLedger(path, provider, other_arm)


class SimpleLedger:
    def __init__(self, path, provider, other_arm):
        self.path, self.provider, self.other_arm = path, provider, other_arm

    def state(self):
        return json.loads(self.path.read_text())


@pytest.mark.parametrize("arm", ["F", "E"])
def test_an_arm_writes_its_paid_row_before_a_stop_another_arm_made_during_its_call(
        stub_run, shared_ledger, tmp_path, monkeypatch, arm):
    monkeypatch.setattr(harness, "STUB", False)  # Live, with the fake provider behind the real guard.
    monkeypatch.setattr(harness, "BILLING", None)
    budget = harness.billing_module()
    # Arm A stops the shared ledger once arm B's first host call has been billed, before B's bookkeeping.
    shared_ledger.provider.after[1] = lambda: shared_ledger.other_arm.stop("arm_failed")
    with pytest.raises(budget.BudgetStop):
        stub_run(arm, SCENARIO)
    (row,) = [json.loads(line) for line in
              (tmp_path / f"run-{arm}" / f"results_zq-synthetic-scenario_{arm}.jsonl").read_text().splitlines()]
    assert (row["session"], row["turn"], row["stopped_after"]) == ("s1", 0, "billing_stop")
    assert row["reply"] == "Fake reply." and row["usage"]["total_tokens"] == 15 and row["transcript"]
    # No paid call after the stop: no extraction of the turn, no next turn.
    assert shared_ledger.provider.models == [harness.MODEL]
    state = shared_ledger.state()
    assert state["blocked"] is True and state["stop_reason"] == "arm_failed"
    assert [entry.get("actual_micros") is not None for entry in state["requests"].values()] == [True]


@pytest.mark.parametrize("stop_at", ["before_tool", "before_next_round"])
def test_a_stopped_tool_turn_keeps_each_billed_round_without_claiming_a_complete_reply(
        stub_run, shared_ledger, tmp_path, monkeypatch, stop_at):
    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setattr(harness, "BILLING", None)
    message = {"role": "assistant", "content": "Let me check that memory.",
               "reasoning_content": "private reasoning fixture",
               "tool_calls": [{"id": "call-1", "type": "function",
                               "function": {"name": "memory_recall", "arguments": '{"query":"Lisbon"}'}}]}
    shared_ledger.provider.messages[1] = message
    tools = []

    def tool(*args):
        tools.append(args[2])
        shared_ledger.other_arm.stop("arm_failed")
        return "No matching memory."

    monkeypatch.setattr(harness, "call_tool", tool)
    if stop_at == "before_tool":
        shared_ledger.provider.after[1] = lambda: shared_ledger.other_arm.stop("arm_failed")
    with pytest.raises(harness.billing_module().BudgetStop):
        stub_run("P", SCENARIO)
    directory = tmp_path / "run-P"
    (row,) = [json.loads(line) for line in (directory / "host-rounds.jsonl").read_text().splitlines()]
    assert (row["arm"], row["session"], row["turn"], row["round"]) == ("P", "s1", 0, 0)
    assert row["message"] == {k: v for k, v in message.items() if k != "reasoning_content"}
    assert row["usage"]["total_tokens"] == 15
    result = directory / "results_zq-synthetic-scenario_P.jsonl"
    assert not result.exists() or not result.read_text().strip()
    assert shared_ledger.provider.models == [harness.MODEL]
    assert tools == ([] if stop_at == "before_tool" else ["memory_recall"])
    state = shared_ledger.state()
    assert state["blocked"] and state["stop_reason"] == "arm_failed"
    assert len(state["requests"]) == 1 and all("actual_micros" in r for r in state["requests"].values())


def test_a_partial_round_journal_cannot_be_resumed_even_without_a_completed_turn(tmp_path, monkeypatch):
    scenario = tmp_path / "zq-practice.py"
    scenario.write_text(SCENARIO + "\nSTUB_HOST = {}\n")
    monkeypatch.setattr(harness, "STUB", True)
    monkeypatch.setattr(harness, "refuse_network", lambda out: None)
    journal = tmp_path / "host-rounds.jsonl"
    original = '{"round":0,"message":{"content":"Partial reply."}}\n'
    journal.write_text(original)
    monkeypatch.setattr(harness, "Host", lambda **kwargs: pytest.fail("resumed run initialized a host"))
    with pytest.raises(SystemExit, match="never resumed"):
        harness.run("F", str(scenario), tmp_path)
    assert journal.read_text() == original


def _fresh_ledger(path: Path) -> dict:
    rate = {"context_tokens": 1000, "max_output_tokens": 100, "input_cny_per_million": "1",
            "output_cny_per_million": "1"}
    frozen = harness.billing_module().create_ledger(path, run_id="fake-attempt", limit_cny="1",
                                                    endpoint="https://fake.invalid/chat/completions",
                                                    models={"fake": rate})
    return {"C5_BILLING_LEDGER": str(path), "C5_ATTEMPT_ID": "fake-attempt",
            "C5_BILLING_POLICY_SHA256": frozen["policy_sha256"]}


def _stop(environment: dict, *arguments):
    import os
    import subprocess
    import sys

    return subprocess.run([sys.executable, str(ROOT / "evaluations" / "c5-harness.py"), "--stop", *arguments],
                          capture_output=True, text=True, timeout=60, env={**os.environ, **environment})


def test_the_stop_entry_point_records_the_first_reason_it_is_given(tmp_path):
    environment = _fresh_ledger(tmp_path / "ledger.json")
    assert _stop(environment, "--reason", "invalid").returncode == 0
    assert _stop(environment, "--reason", "other").returncode == 0
    state = json.loads((tmp_path / "ledger.json").read_text())
    assert state["blocked"] is True and state["stop_reason"] == "invalid"  # The first reason wins.
    plain = _fresh_ledger(tmp_path / "plain.json")
    assert _stop(plain).returncode == 0  # Without --reason, as before.
    assert json.loads((tmp_path / "plain.json").read_text())["stop_reason"] == "arm_failed"


@pytest.mark.parametrize("arguments", [["--reason", "Bad-Code"], ["--reason", "1st"], ["--reason", "x" * 41],
                                       ["--reason"], ["--reason", "ok", "extra"], ["--why", "invalid"]])
def test_the_stop_entry_point_refuses_a_malformed_reason_before_touching_the_ledger(tmp_path, arguments):
    environment = _fresh_ledger(tmp_path / "ledger.json")
    before = (tmp_path / "ledger.json").read_text()
    done = _stop(environment, *arguments)
    assert done.returncode != 0 and "usage: c5-harness.py --stop" in done.stderr
    assert (tmp_path / "ledger.json").read_text() == before
    assert harness.stop_reason(["--reason", "a" + "0" * 39]) == "a" + "0" * 39


# The dry-run check fails on any harness event -------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["extraction_failed", "turn_not_recorded", "timed_pause_refused",
                                  "unexpected_recording", "message_identity_unknown", "page_action_failed"])
def test_the_dry_run_check_fails_its_run_verdict_on_any_harness_event_kind(tmp_path, kind):
    check = _load("c5_dry_run_check_hardening", ROOT / "evaluations" / "c5-dry-run-check.py")
    scenario = str(ROOT / "evaluations" / "c5-practice-scenario.py")
    for arm in "PEF":
        (tmp_path / f"k-{arm}").mkdir()
    clean = check.check(scenario, tmp_path, "k")["run"]["failures"]
    assert not any("harness events" in failure for failure in clean)
    (tmp_path / "k-E" / "harness-events.jsonl").write_text(
        json.dumps({"time": 0, "kind": kind, "session": "s1-arrival", "turn": 0}) + "\n")
    failures = check.check(scenario, tmp_path, "k")["run"]["failures"]
    assert f"E: harness events ['{kind}']" in failures


# Which records a page action removed ----------------------------------------------------------------------------

REMOVAL_SCENARIO = '''
HOST = "You are a companion. Reply briefly."
SESSIONS_LONG = [
    ("s1", ["Today is Monday, March 2, 20:00. I'm nervous about Thursday's review. Please never mention Tom.",
            "I'm nervous about the move too. And please leave work out of it."]),
    ("s2", ["Today is Tuesday, March 3, 21:00. Hi again."]),
]
PAGE_ACTIONS = [
    ("s2", 0, {"do": "delete_message", "session": "s1", "turn": 1, "role": "user"}),
    ("s2", 0, {"do": "remove_boundary", "topic": "Tom"}),
]
'''
NERVOUS = {"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported"}
REMOVAL_SCRIPT = {
    ("s1", 0): [{"tool": "memory_note", "arguments": {"text": "Review on 2026-03-05.", "kind": "plan",
                                                      "affect": NERVOUS}, "source": "current"},
                {"tool": "memory_boundary", "arguments": {"topic": "Tom"}}],
    ("s1", 1): [{"tool": "memory_note", "arguments": {"text": "Move on 2026-03-20.", "kind": "plan",
                                                      "affect": NERVOUS}, "source": "current"},
                {"tool": "memory_boundary", "arguments": {"topic": "Work"}}],
}


def test_removed_records_name_exactly_the_removed_one_of_two_alike_records(stub_run, tmp_path):
    rows, events = stub_run("P", REMOVAL_SCENARIO, REMOVAL_SCRIPT)
    assert len(rows) == 3 and events == []
    deletion, removal = [json.loads(line) for line in (tmp_path / "run-P" / "page-actions.jsonl").read_text()
                         .splitlines()]
    turn = [["s1", 1, "user"]]
    removed = deletion["result"]["removed_records"]
    assert all(entry["established"] for entry in removed) and deletion["result"]["removed_records_complete"] is True
    assert removal["result"]["removed_records_complete"] is True
    assert sorted(entry["kind"] for entry in removed) == ["feeling", "message", "note"]
    for entry in removed:  # Only the second turn's message, its note and its feeling; never the first turn's.
        assert entry["sources"] == turn
        assert entry["ref"] == harness.record_ref(entry["kind"], [tuple(source) for source in turn], {})
    assert deletion["before"]["feelings"] == 2 and deletion["after"]["feelings"] == 1
    other = harness.record_ref("feeling", [("s1", 0, "user")], {})
    assert other not in {entry["ref"] for entry in removed}
    # F names the deleted message with the same ref, from P's removed positions.
    message = next(entry for entry in removed if entry["kind"] == "message")
    assert harness.message_records(deletion["result"]["removed"]) == [message]
    (boundary,) = removal["result"]["removed_records"]
    assert boundary == {"kind": "boundary", "established": True, "sources": [],
                        "ref": harness.record_ref("boundary", [], {"topic": "Tom", "aliases": []})}
    assert boundary["ref"] != harness.record_ref("boundary", [], {"topic": "Work", "aliases": []})
    text = json.dumps(deletion) + json.dumps(removal)
    assert "nervous" not in json.dumps(deletion["result"]) and "Move on" not in text and "Review on" not in text


def test_the_ref_is_the_shared_formula():
    import hashlib

    sources = [["s2", 0, "user"], ["s1", 10, "assistant"], ["s1", 2, "user"]]
    expected = "src:" + hashlib.sha256(json.dumps(["feeling", sorted(sources)], separators=(",", ":"),
                                                  ensure_ascii=False).encode("utf-8")).hexdigest()
    assert harness.record_ref("feeling", sources) == expected
    assert harness.record_ref("feeling", [tuple(source) for source in reversed(sources)]) == expected
    content = {"topic": "Tomás", "aliases": ["mi ex"]}
    assert harness.record_ref("boundary", [], content) == harness.record_ref("boundary", content=content) == (
        "content:" + hashlib.sha256(json.dumps(["boundary", content], separators=(",", ":"), ensure_ascii=False,
                                               sort_keys=True).encode("utf-8")).hexdigest())


def test_a_count_drop_no_id_diff_explains_is_not_established():
    assert harness.removed_records({}, {}, {"feelings": 2, "boundaries": ["a"]}, {"feelings": 1, "boundaries": []}) \
        == [{"kind": "boundary", "established": False}, {"kind": "feeling", "established": False}]
    held = {("feeling", "id-1"): {"kind": "feeling", "sources": [("s1", 0, "user")], "content": {"label": "x"}}}
    (entry,) = harness.removed_records(held, {}, {"feelings": 1}, {"feelings": 0})
    assert entry["established"] and entry["ref"].startswith("src:") and "id-1" not in json.dumps(entry)
    unlinked = {("boundary", "id-2"): {"kind": "boundary", "sources": [], "content": {"topic": "zq", "aliases": []}}}
    (entry,) = harness.removed_records(unlinked, {})
    assert entry["ref"].startswith("content:") and "zq" not in json.dumps(entry) and "id-2" not in json.dumps(entry)
    # A commitment that reads as a plain note after a relationship reset was not removed.
    kept = {"id-3": {"kind": "commitment", "sources": [], "content": {"text": "x"}}}
    assert harness.removed_records(kept, {"id-3": {**kept["id-3"], "kind": "note"}}, {"notes": 1}, {"notes": 1}) == []


# I2: the count-only precheck ------------------------------------------------------------------------------------

PLANT = "zq-planted-7f3c91"


def _precheck(path: Path):
    import os
    import subprocess
    import sys

    environment = {key: value for key, value in os.environ.items() if key != "C5_STUB"}
    done = subprocess.run([sys.executable, str(ROOT / "evaluations" / "c5-precheck.py"), str(path)],
                          capture_output=True, text=True, timeout=120, env=environment)
    return done.returncode, done.stdout, done.stderr, json.loads(done.stdout.splitlines()[-1])


def test_the_precheck_passes_the_public_practice_scenario_printing_counts_only():
    code, out, err, summary = _precheck(ROOT / "evaluations" / "c5-practice-scenario.py")
    assert code == 0 and err == ""
    assert summary == {"ok": True, "sessions": 7, "turns": 18, "actions": 7, "failures": 0, "codes": []}
    assert "intended unrecorded turns 2" in out
    for text in ("s1-arrival", "Lisbon", "Tom", "casual", "Juniper", "Today"):
        assert text not in out


GOOD = [(f"{PLANT}-s1", [f"Today is Monday, March 2, 20:00. {PLANT} one.", f"{PLANT} two."]),
        (f"{PLANT}-s2", [f"Today is Tuesday, March 3, 21:00. {PLANT} three."])]


@pytest.mark.parametrize("change, codes", [
    ({"SESSIONS_LONG": [(f"{PLANT}-s1", [f"Today is Monday, March 2. {PLANT}"])]}, ["no_time"]),
    ({"SESSIONS_LONG": [(f"{PLANT}-s1", [f"{PLANT} hello at 20:00"])]}, ["no_date"]),
    ({"SESSIONS_LONG": [(f"{PLANT}-s1", [f"Today is Monday, Smarch 2, 20:00. {PLANT}"])]}, ["bad_date"]),
    ({"SESSIONS_LONG": [GOOD[1], (f"{PLANT}-s0", [f"Today is Monday, March 2, 20:00. {PLANT}"])]},
     ["not_increasing"]),
    ({"SESSIONS_LONG": [GOOD[0], (f"{PLANT}-s2", [f"Today is Monday, March 2, 20:30. {PLANT}"])]}, ["too_close"]),
    ({"SESSIONS_LONG": [GOOD[0], GOOD[0]]}, ["duplicate_session", "not_increasing"]),
    ({"SESSIONS_LONG": [(f"{PLANT}-s1", [])]}, ["malformed_session"]),
    ({"PAGE_ACTIONS": [(f"{PLANT}-s9", 0, {"do": "add_boundary", "topic": PLANT})]}, ["bad_action"]),
    ({"PAGE_ACTIONS": [(f"{PLANT}-s1", 1, {"do": f"{PLANT}"})]}, ["bad_action"]),
    ({"PAGE_ACTIONS": [(f"{PLANT}-s1", 1, {"do": "accept_persona_proposal", "match": PLANT})]},
     ["proposal_without_card"]),
    ({"PAGE_ACTIONS": [(f"{PLANT}-s1", 1, {"do": "pause_recording", "hours": 2, "note": PLANT})]},
     ["bad_action", "timed_pause"]),
    ({"STUB_HOST": {(f"{PLANT}-s1", 1): [{"tool": "memory_pause", "arguments": {"hours": 3}}]}}, ["timed_pause"]),
    ({"RAISE": True}, ["load_failed"]),
])
def test_a_bad_scenario_fails_with_codes_and_never_prints_its_words(tmp_path, change, codes):
    scenario = {"YEAR": 2026, "HOST": PLANT, "SESSIONS_LONG": GOOD, "PAGE_ACTIONS": [], **change}
    source = "".join(f"{key} = {value!r}\n" for key, value in scenario.items() if key != "RAISE")
    if change.get("RAISE"):
        source += f"print({PLANT!r})\nimport sys\nprint({PLANT!r}, file=sys.stderr)\nraise ValueError({PLANT!r})\n"
    path = tmp_path / f"{PLANT}-scenario.py"
    path.write_text(source)
    code, out, err, summary = _precheck(path)
    assert code == 1 and summary["ok"] is False and summary["codes"] == sorted(codes)
    assert PLANT not in out and PLANT not in err and "Traceback" not in out + err
    assert all(line.startswith(("sessions ", "turns ", "actions ", "intended ", "FAIL code=", "{"))
               for line in out.splitlines())


def test_a_good_synthetic_scenario_passes(tmp_path):
    path = tmp_path / "scenario.py"
    path.write_text(f"HOST = {PLANT!r}\nSESSIONS_LONG = {GOOD!r}\n"
                    f"PAGE_ACTIONS = [({GOOD[1][0]!r}, 0, {{'do': 'add_boundary', 'topic': {PLANT!r}}})]\n")
    code, out, err, summary = _precheck(path)
    assert (code, summary["ok"], summary["turns"], summary["actions"]) == (0, True, 3, 1)
    assert PLANT not in out + err


def test_billed_host_reply_is_retained_when_memory_bookkeeping_raises(stub_run, shared_ledger, tmp_path, monkeypatch):
    monkeypatch.setattr(harness, 'STUB', False)
    monkeypatch.setattr(harness, 'BILLING', None)

    def unavailable(*args, **kwargs):
        raise RuntimeError('independent synthetic bookkeeping failure')

    monkeypatch.setattr(harness.Memory, 'record_turn', unavailable)
    with pytest.raises(RuntimeError, match='independent synthetic bookkeeping failure'):
        stub_run('P', SCENARIO)
    state = shared_ledger.state()
    assert len(state['requests']) == 1
    assert all(entry.get('actual_micros') is not None for entry in state['requests'].values())
    result = tmp_path / 'run-P/results_zq-synthetic-scenario_P.jsonl'
    assert result.exists(), 'The host reply was billed but its result row was never written.'
    rows = [json.loads(line) for line in result.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]['reply'] == 'Fake reply.' and rows[0]['usage']['total_tokens'] == 15
    assert rows[0]['stopped_after'] == 'bookkeeping_failed' and rows[0]['recorded'] is None
    events = [json.loads(line) for line in (tmp_path / 'run-P/harness-events.jsonl').read_text().splitlines()]
    assert len(events) == 1 and events[0]['kind'] == 'bookkeeping_failed'
    assert set(events[0]) == {'time', 'kind', 'session', 'turn'}
    assert shared_ledger.provider.models == [harness.MODEL]
    assert state['blocked'] is True and state['stop_reason'] == 'harness_degraded'
