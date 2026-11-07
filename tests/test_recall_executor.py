import copy
import os
import time
from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
from datetime import UTC, datetime

import pytest
from test_cognition import STAMP, budget, event, request, scope, state

from membrain import cognition, helpers
from membrain.config import Settings
from membrain.helpers import DomainError
from membrain.recall_executor import RecallExecutor, _compute


@pytest.fixture(scope="module")
def runner():
    executor = RecallExecutor(2)
    try:
        yield executor
    finally:
        executor.close()


def arguments():
    source = event("Mara spread the blue map. I chose the path.")
    query = request("blue map", budget=budget(12000))
    query["budget"]["max_wall_time_ms"] = 10000
    return [scope(), query, cognition.extract_event(source), [source], state()]


def canonical(result):
    result = copy.deepcopy(result)
    assert type(result["usage"]["elapsed_ms"]) is int and result["usage"]["elapsed_ms"] >= 0
    result["usage"]["elapsed_ms"] = 0
    result["recall_id"] = "recall"
    snapshot = result["retrieval_snapshot"]
    assert datetime.fromisoformat(snapshot["created_at"].replace("Z", "+00:00")).tzinfo is not None
    snapshot.update(snapshot_id="snapshot", created_at="time")
    for index, trace in enumerate(result["recall_traces"]):
        assert datetime.fromisoformat(trace["recorded_at"].replace("Z", "+00:00")).tzinfo is not None
        trace.update(trace_id=f"trace-{index}", recall_id="recall", retrieval_snapshot_id="snapshot", recorded_at="time")
    return result


@pytest.mark.parametrize("case", ["normal", "foreign_scope", "missing_source", "stale_source", "context_budget"])
def test_process_recall_preserves_results_provenance_scope_and_context_budget(runner, case):
    args = arguments()
    if case == "foreign_scope":
        args[2][0]["scope"]["brain_id"] = "another-brain"
    elif case == "missing_source":
        args[3] = []
    elif case == "stale_source":
        args[3][0]["revision"] += 1
    elif case == "context_budget":
        args[1]["budget"]["max_context_tokens"] = 1800
    original = copy.deepcopy(args)
    expected = cognition.recall(*args, access_at=STAMP)
    actual = runner(*args, access_at=STAMP)
    assert canonical(actual) == canonical(expected)
    assert len(actual["model_context"].encode()) <= args[1]["budget"]["max_context_tokens"]
    assert args == original


def test_domain_errors_survive_process_transport_and_pool_remains_usable(runner):
    args = arguments()
    args[1]["budget"]["max_context_tokens"] = 1
    with pytest.raises(DomainError) as direct:
        cognition.recall(*args)
    with pytest.raises(DomainError) as remote:
        runner(*args)
    assert remote.value.as_dict() == direct.value.as_dict()
    assert runner(*arguments())["items"]


def test_queue_and_transfer_time_count_against_the_recall_budget():
    assert _compute(arguments(), {}, time.monotonic()-1, None) == {
        "error": {"code": "budget_exceeded", "message": "Recall computation deadline exceeded.", "retryable": True}}


def test_a_timed_out_running_task_keeps_its_admission_slot_until_finished(monkeypatch):
    from types import SimpleNamespace

    executor = RecallExecutor(1)
    pending = Future()
    assert pending.set_running_or_notify_cancel()
    monkeypatch.setattr(executor, "_executor", lambda: SimpleNamespace(submit=lambda *args: pending))
    args = arguments()
    args[1]["budget"]["max_wall_time_ms"] = 1
    with pytest.raises(DomainError, match="deadline exceeded"):
        executor(*args)
    for _ in range(3):
        assert executor._slots.acquire(blocking=False)
    assert not executor._slots.acquire(blocking=False)
    pending.set_result({"result": None})
    assert executor._slots.acquire(blocking=False)
    for _ in range(4):
        executor._slots.release()
    executor.close()


def test_scenario_clock_crosses_process_boundary_without_leaking_to_next_request(runner, monkeypatch):
    future = datetime(2040, 1, 1, tzinfo=UTC)
    with monkeypatch.context() as patcher:
        patcher.setattr(helpers, "_scenario_clock", lambda: future)
        actual = runner(*arguments())
    assert actual["retrieval_snapshot"]["created_at"].startswith("2040-01-01")
    assert not runner(*arguments())["retrieval_snapshot"]["created_at"].startswith("2040-")


def test_bounded_admission_rejects_excess_work_and_close_joins_workers():
    executor = RecallExecutor(1)
    try:
        assert executor(*arguments())["items"]
        processes = list(executor._pool._processes.values())
        for _ in range(4):
            assert executor._slots.acquire(blocking=False)
        try:
            with pytest.raises(DomainError, match="busy") as caught:
                executor(*arguments())
            assert caught.value.retryable
        finally:
            for _ in range(4):
                executor._slots.release()
    finally:
        executor.close()
    assert all(not process.is_alive() for process in processes)
    with pytest.raises(DomainError, match="stopping"):
        executor(*arguments())


def test_crashed_worker_rejects_request_then_recovers_without_replaying_it():
    executor = RecallExecutor(1)
    try:
        assert executor(*arguments())["items"]
        future = executor._pool.submit(os._exit, 1)
        with pytest.raises(BrokenProcessPool):
            future.result(timeout=10)
        with pytest.raises(DomainError, match="restarted") as caught:
            executor(*arguments())
        assert caught.value.retryable
        assert executor(*arguments())["items"]
    finally:
        executor.close()


@pytest.mark.parametrize("value", [-1, 5, True, 1.5, "2"])
def test_invalid_worker_configuration_is_rejected(value):
    with pytest.raises(ValueError, match="RECALL_PROCESSES"):
        Settings(database_url="unused", recall_processes=value)


def test_worker_configuration_supports_inline_mode_and_environment(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_RECALL_PROCESSES", "0")
    assert Settings(database_url="unused").recall_processes == 0
    monkeypatch.setenv("MEMBRAIN_RECALL_PROCESSES", "2")
    assert Settings(database_url="unused").recall_processes == 2
    monkeypatch.setenv("MEMBRAIN_RECALL_PROCESSES", "invalid")
    with pytest.raises(ValueError, match="bounded positive integer"):
        Settings(database_url="unused")
