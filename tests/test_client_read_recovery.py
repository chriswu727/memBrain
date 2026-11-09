import json
import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpcore._sync.http11 import HTTP11Connection
from uvicorn.protocols.http.h11_impl import H11Protocol

from membrain.client import MemoryClient
from membrain.runtime_client import RuntimeClient


@contextmanager
def server(actions):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            requests.append((self.command, self.path, dict(self.headers), body))
            action = actions[min(len(requests) - 1, len(actions) - 1)]
            if action == "drop":
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_WR)
                return
            content = b'not-json' if action == "invalid" else b'{"ready":true}'
            self.send_response(503 if action == "unavailable" else 200)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(content)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = respond

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: http.serve_forever(poll_interval=0.01))
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}", requests
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def test_read_recovers_once_after_real_response_disconnect(caplog):
    epoch = "ddf1ea58-8dfc-4ea1-b366-fd018a684fc1"
    with server(["drop", "ok"]) as (url, requests):
        with MemoryClient(url, "synthetic-key", "brain", trust_env=False, recovery_epoch=epoch) as client:
            assert RuntimeClient(client).cognitive_usage() == {"ready": True}
    assert len(requests) == 2 and requests[0] == requests[1]
    assert requests[0][1] == "/v1/brains/brain/runtime/cognitive-usage"
    assert requests[0][2]["Authorization"] == "Bearer synthetic-key"
    assert requests[0][2]["X-Memory-Recovery-Epoch"] == epoch
    assert "retrying once" in caplog.text
    assert "synthetic-key" not in caplog.text and epoch not in caplog.text


def test_repeated_read_disconnect_is_reported_after_two_requests():
    with server(["drop"]) as (url, requests):
        with MemoryClient(url, "key", "brain", trust_env=False) as client:
            with pytest.raises(httpx.RemoteProtocolError):
                RuntimeClient(client).cognitive_usage()
    assert len(requests) == 2


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_ambiguous_real_write_disconnect_is_never_replayed(method):
    with server(["drop", "ok"]) as (url, requests):
        with MemoryClient(url, "key", trust_env=False) as client:
            with pytest.raises(httpx.RemoteProtocolError):
                client._request(method, "write", json={"operation": "one"})
    assert len(requests) == 1 and json.loads(requests[0][3]) == {"operation": "one"}


@pytest.mark.parametrize("action,error", [("unavailable", httpx.HTTPStatusError), ("invalid", ValueError)])
def test_received_error_response_is_not_a_connection_retry(action, error):
    with server([action, "ok"]) as (url, requests):
        with MemoryClient(url, "key", trust_env=False) as client:
            with pytest.raises(error):
                client._request("GET", "read")
    assert len(requests) == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError])
def test_other_read_failures_are_not_retried(error):
    requests = []

    def handle(request):
        requests.append(request)
        raise error("synthetic failure", request=request)

    with MemoryClient("http://memory.test", "key", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(error):
            client._request("GET", "read")
    assert len(requests) == 1


def test_read_recovers_when_keepalive_closes_after_pool_reuse_check(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    from examples.evaluation_host import loopback_server

    app, requests, protocols = FastAPI(), [], []
    closed, armed, completed = threading.Event(), threading.Event(), threading.Event()

    @app.get("/v1/brains/brain/runtime/cognitive-usage")
    def usage():
        requests.append("GET")
        return {"requests_seen": len(requests)}

    original_complete = H11Protocol.on_response_complete
    original_timeout = H11Protocol.timeout_keep_alive_handler
    original_expired = HTTP11Connection.has_expired

    def complete(protocol):
        protocols.append(protocol)
        original_complete(protocol)
        completed.set()

    def timeout(protocol):
        original_timeout(protocol)
        closed.set()

    def has_expired(connection):
        expired = original_expired(connection)
        if armed.is_set() and not expired:
            armed.clear()
            protocol = protocols[-1]
            protocol.loop.call_soon_threadsafe(protocol.timeout_keep_alive_handler)
            assert closed.wait(3)
        return expired

    monkeypatch.setattr(H11Protocol, "on_response_complete", complete)
    monkeypatch.setattr(H11Protocol, "timeout_keep_alive_handler", timeout)
    monkeypatch.setattr(HTTP11Connection, "has_expired", has_expired)
    with loopback_server(app) as url:
        with MemoryClient(url, "key", "brain", trust_env=False) as client:
            runtime = RuntimeClient(client)
            assert runtime.cognitive_usage() == {"requests_seen": 1}
            assert completed.wait(3)
            armed.set()
            assert runtime.cognitive_usage() == {"requests_seen": 2}
    assert closed.is_set() and requests == ["GET", "GET"]


@pytest.mark.parametrize("body", [{"content": b"body"}, {"json": {"value": 1}}])
def test_read_with_request_body_is_not_replayed(body):
    requests = []

    def handle(request):
        requests.append(request)
        raise httpx.ReadError("private diagnostic", request=request)

    with MemoryClient("http://memory.test", "key", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.ReadError):
            client._request("GET", "read", **body)
    assert len(requests) == 1
