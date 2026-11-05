from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_recall_executor import STAMP, arguments, canonical

from membrain import api, cognition
from membrain.config import Settings
from membrain.helpers import DomainError
from membrain.recall_executor import RecallExecutor


def test_start_prepares_every_worker_before_the_first_recall():
    executor = RecallExecutor(2)
    try:
        executor.start()
        processes = list(executor._pool._processes.values())
        assert len(processes) == 2 and all(process.is_alive() for process in processes)
        assert all(future.done() and future.exception() is None for future in executor._ready)
        actual = executor(*arguments(), access_at=STAMP)
        assert canonical(actual) == canonical(cognition.recall(*arguments(), access_at=STAMP))
        executor.start()
        assert list(executor._pool._processes.values()) == processes
    finally:
        executor.close()
    assert all(not process.is_alive() for process in processes)


def test_failed_start_reaps_workers_and_allows_a_new_pool(monkeypatch):
    executor = RecallExecutor(2)
    original = executor._executor
    processes = []

    def capture():
        pool = original()
        processes.extend(pool._processes.values())
        return pool

    monkeypatch.setattr(executor, "_executor", capture)
    try:
        with pytest.raises(DomainError, match="startup"):
            executor.start(timeout=0)
        assert processes and all(not process.is_alive() for process in processes)
        assert executor._pool is None
        executor.start()
        assert executor(*arguments())["items"]
    finally:
        executor.close()
    assert all(not process.is_alive() for process in processes)


@pytest.mark.parametrize("fail", [False, True])
def test_api_startup_waits_for_recall_readiness_and_closes_failed_resources(monkeypatch, fail):
    from membrain import recall_executor

    events = []

    @contextmanager
    def factory(settings):
        events.append("service opened")
        try:
            yield SimpleNamespace()
        finally:
            events.append("service closed")

    class Executor:
        def __init__(self, workers):
            assert workers == 2

        def start(self):
            events.append("workers starting")
            if fail:
                raise DomainError("dependency_unavailable", "worker startup failed", retryable=True)
            events.append("workers ready")

        def close(self):
            events.append("workers closed")

    monkeypatch.setattr(api, "configured_service", factory)
    monkeypatch.setattr(recall_executor, "RecallExecutor", Executor)
    app = api.create_app(Settings(database_url="unused"))
    if fail:
        with pytest.raises(DomainError, match="startup"):
            with TestClient(app):
                pytest.fail("The application accepted requests before its workers became ready")
        assert events == ["service opened", "workers starting", "workers closed", "service closed"]
    else:
        with TestClient(app) as client:
            assert events == ["service opened", "workers starting", "workers ready"]
            assert client.get("/health").status_code == 200
        assert events[-2:] == ["workers closed", "service closed"]
