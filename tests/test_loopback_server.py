"""The loopback test server (tests/loopback.py) serves real TCP, starts and stops within its time limits, and
reports failures without private detail."""
import asyncio
import socket
import threading
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi import FastAPI
from loopback import LoopbackServerError, loopback_server


def test_loopback_serves_real_tcp_and_releases_socket_after_shutdown():
    app = FastAPI()
    threads_before = {thread.ident for thread in threading.enumerate()}

    @app.get("/ready")
    def ready():
        return {"ready": True}

    with loopback_server(app) as base_url:
        url = urlsplit(base_url)
        assert url.hostname == "127.0.0.1" and url.port > 0
        with httpx.Client(trust_env=False) as client:
            assert client.get(base_url + "/ready").json() == {"ready": True}
    with socket.socket() as probe:
        assert probe.connect_ex((url.hostname, url.port)) != 0
    assert not [thread for thread in threading.enumerate()
                if thread.name == "memory-evaluation-http" and thread.ident not in threads_before]


def test_loopback_cleanup_preserves_body_exception():
    with pytest.raises(ValueError, match="caller_failed"):
        with loopback_server(FastAPI()) as base_url:
            url = urlsplit(base_url)
            raise ValueError("caller_failed")
    with socket.socket() as probe:
        assert probe.connect_ex((url.hostname, url.port)) != 0


def test_loopback_startup_failure_is_reported():
    @asynccontextmanager
    async def lifespan(app):
        raise RuntimeError("private-startup-detail")
        yield

    with pytest.raises(LoopbackServerError, match="startup_failed") as error:
        with loopback_server(FastAPI(lifespan=lifespan)):
            pytest.fail("Startup must not complete")
    assert "private-startup-detail" not in str(error.value)


def test_loopback_cancels_hung_async_startup_within_shutdown_budget():
    cancelled = threading.Event()

    @asynccontextmanager
    async def lifespan(app):
        try:
            await asyncio.Event().wait()
            yield
        finally:
            cancelled.set()

    with pytest.raises(LoopbackServerError, match="startup_timeout"):
        with loopback_server(FastAPI(lifespan=lifespan), startup_timeout_seconds=0.05,
                             shutdown_timeout_seconds=0.5):
            pytest.fail("Startup must not complete")
    assert cancelled.is_set()


def test_loopback_rejects_invalid_timeouts(kwargs):
    with pytest.raises(ValueError):
        with loopback_server(FastAPI(), **kwargs):
            pytest.fail("Invalid timeout must be rejected")
