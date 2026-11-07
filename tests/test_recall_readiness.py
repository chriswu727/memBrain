import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_recall_executor import STAMP, arguments, canonical

from membrain import api, cognition
from membrain.config import Settings
from membrain.helpers import DomainError
from membrain.recall_executor import RecallExecutor, _stop_failed_pool


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
    from membrain import recall_service_executor

    events = []

    @contextmanager
    def factory(settings):
        events.append("service opened")
        try:
            yield SimpleNamespace()
        finally:
            events.append("service closed")

    class Executor:
        def __init__(self, workers, settings):
            assert workers == settings.recall_processes == 4

        def respond(self, *args):
            raise AssertionError("No request was submitted by this startup check")

        def start(self):
            events.append("workers starting")
            if fail:
                raise DomainError("dependency_unavailable", "worker startup failed", retryable=True)
            events.append("workers ready")

        def close(self):
            events.append("workers closed")

    monkeypatch.setattr(api, "configured_service", factory)
    monkeypatch.setattr(recall_service_executor, "RecallServiceExecutor", Executor)
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


def test_failed_pool_cleanup_waits_for_the_manager_to_finish_reaping():
    released = threading.Event()
    reaped = threading.Event()

    def manage():
        released.wait()
        reaped.set()

    joined = []

    class Manager(threading.Thread):
        def join(self, timeout=None):
            joined.append(True)
            return super().join(timeout)

    manager = Manager(target=manage)
    manager.start()

    class Process:
        def is_alive(self):
            return not reaped.is_set()

        def terminate(self):
            pass

        def kill(self):
            pass

        def join(self, timeout=None):
            pass

    class Pool:
        _processes = {1: Process()}
        _executor_manager_thread = manager

        def shutdown(self, *, wait, cancel_futures):
            assert cancel_futures
            released.set()
            if wait:
                manager.join()
            self._executor_manager_thread = None

    try:
        _stop_failed_pool(Pool())
        assert joined
        assert not manager.is_alive()
        assert reaped.is_set()
    finally:
        released.set()
        manager.join()


def _blocked_initializer(event):
    event.wait()


@pytest.mark.parametrize("workers", [1, 4])
def test_failed_start_reaps_blocked_initializers_and_their_manager(monkeypatch, workers):
    import multiprocessing

    executor = RecallExecutor(workers)
    event = multiprocessing.get_context("spawn").Event()
    initialization = executor._initialization
    original = executor._executor
    processes, managers = [], []

    def capture():
        pool = original()
        processes.extend(pool._processes.values())
        managers.append(pool._executor_manager_thread)
        return pool

    monkeypatch.setattr(executor, "_executor", capture)
    monkeypatch.setattr(executor, "_initialization", lambda context: (_blocked_initializer, (event,)))
    try:
        with pytest.raises(DomainError, match="startup"):
            executor.start(timeout=0.2)
        assert len(processes) == workers
        assert all(not process.is_alive() for process in processes)
        assert all(not manager.is_alive() for manager in managers)
        assert executor._pool is None
        monkeypatch.setattr(executor, "_initialization", initialization)
        executor.start()
        assert executor(*arguments())["items"]
    finally:
        event.set()
        executor.close()
    assert all(not process.is_alive() for process in processes)
    assert all(not manager.is_alive() for manager in managers)
