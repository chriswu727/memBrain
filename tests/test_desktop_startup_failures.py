import json
import os
from contextlib import asynccontextmanager

import pytest
import uvicorn
from fastapi import FastAPI

from membrain import desktop, recovery_profile
from membrain.local_profile import ensure_profile


@pytest.fixture
def supervisor_run(tmp_path, monkeypatch):
    profile = ensure_profile(tmp_path / "profile")
    workers = []

    def work(self):
        workers.append(self)
        self.stopped.wait()

    monkeypatch.setattr(desktop, "_evaluation_clock", lambda _: None)
    monkeypatch.setattr(desktop, "_check_database", lambda *args, **kwargs: None)
    monkeypatch.setattr(recovery_profile, "check_start_allowed", lambda _: None)
    monkeypatch.setattr(desktop.LocalSupervisor, "work", work)
    monkeypatch.setattr(desktop.LocalSupervisor, "app", lambda _: FastAPI())
    previous_umask = os.umask(0o077) if os.name != "nt" else None
    if previous_umask is not None:
        os.umask(previous_umask)
    try:
        yield profile, workers
    finally:
        if previous_umask is not None:
            os.umask(previous_umask)


def logs(profile, workers):
    assert workers and all(worker.stopped.is_set() and not worker.worker.is_alive() for worker in workers)
    text = (profile.directory / "service.log").read_text()
    assert "private startup detail" not in text
    assert profile.api_key not in text and profile.admin_password not in text
    return [json.loads(line) for line in text.splitlines()]


def test_actual_lifespan_failure_is_logged_as_failure_and_worker_is_joined(supervisor_run, monkeypatch):
    profile, workers = supervisor_run

    @asynccontextmanager
    async def startup(app):
        raise RuntimeError("private startup detail")
        yield

    monkeypatch.setattr(desktop.LocalSupervisor, "app", lambda _: FastAPI(lifespan=startup))
    with pytest.raises(desktop.DesktopError) as failure:
        desktop.run(profile.directory)
    assert failure.value.code == "service_failed"
    entries = logs(profile, workers)
    assert [entry["event"] for entry in entries] == ["service_started", "service_failed", "service_stopped"]
    assert entries[1]["error"]["code"] == "api_startup_failed"


@pytest.mark.parametrize("exit_code", [3, "private startup detail"])
@pytest.mark.parametrize("started", [False, True])
def test_unsuccessful_server_exit_is_sanitized(supervisor_run, monkeypatch, exit_code, started):
    profile, workers = supervisor_run

    def fail(server):
        server.started = started
        raise SystemExit(exit_code)

    monkeypatch.setattr(uvicorn.Server, "run", fail)
    with pytest.raises(desktop.DesktopError, match="Local service failed"):
        desktop.run(profile.directory)
    entries = logs(profile, workers)
    assert entries[1]["event"] == "service_failed"
    assert entries[1]["error"]["code"] == ("api_exit_failed" if started else "api_startup_failed")


def test_unsuccessful_server_construction_is_logged_and_resources_close(supervisor_run, monkeypatch):
    profile, _ = supervisor_run

    def fail(*args, **kwargs):
        raise SystemExit("private startup detail")

    monkeypatch.setattr(uvicorn, "Server", fail)
    with pytest.raises(desktop.DesktopError):
        desktop.run(profile.directory)
    text = (profile.directory / "service.log").read_text()
    assert "private startup detail" not in text
    assert [json.loads(line)["event"] for line in text.splitlines()] == ["service_failed", "service_stopped"]


def test_server_returning_before_start_is_a_failure(supervisor_run, monkeypatch):
    profile, workers = supervisor_run
    monkeypatch.setattr(uvicorn.Server, "run", lambda _: None)
    with pytest.raises(desktop.DesktopError):
        desktop.run(profile.directory)
    assert logs(profile, workers)[1]["error"]["code"] == "api_startup_failed"


@pytest.mark.parametrize("clean_exit", [False, True])
def test_normal_server_stop_is_not_logged_as_failure(supervisor_run, monkeypatch, clean_exit):
    profile, workers = supervisor_run

    def stop(server):
        server.started = True
        if clean_exit:
            raise SystemExit(0)

    monkeypatch.setattr(uvicorn.Server, "run", stop)
    if clean_exit:
        with pytest.raises(SystemExit) as stopped:
            desktop.run(profile.directory)
        assert stopped.value.code == 0
    else:
        desktop.run(profile.directory)
    assert [entry["event"] for entry in logs(profile, workers)] == ["service_started", "service_stopped"]
