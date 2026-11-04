import httpx
import pytest

from membrain import host, mcp_server
from membrain.client import MemoryClient


@pytest.mark.parametrize("read", [host._boundaries, mcp_server._boundaries], ids=["host", "mcp"])
@pytest.mark.parametrize("status", [401, 403, 409, 429, 500, 503])
def test_boundary_read_failure_is_never_an_empty_boundary_list(read, status):
    def handle(request):
        return httpx.Response(status, json={"error": "unavailable"})

    with MemoryClient("http://memory.test", "key", "brain", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.HTTPStatusError) as failure:
            read(client)
        assert failure.value.response.status_code == status


@pytest.mark.parametrize("read", [host._boundaries, mcp_server._boundaries], ids=["host", "mcp"])
def test_boundary_timeout_does_not_disable_the_boundary(read):
    def handle(request):
        raise httpx.ReadTimeout("relationship read timed out", request=request)

    with MemoryClient("http://memory.test", "key", "brain", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.ReadTimeout):
            read(client)


@pytest.mark.parametrize("read", [host._boundaries, mcp_server._boundaries], ids=["host", "mcp"])
@pytest.mark.parametrize("status", [404, 405])
def test_only_an_older_service_without_the_route_has_no_boundaries(read, status):
    def handle(request):
        return httpx.Response(status, json={"error": "route not available"})

    with MemoryClient("http://memory.test", "key", "brain", transport=httpx.MockTransport(handle)) as client:
        assert read(client) == []


def test_host_never_runs_recall_when_its_boundary_read_failed(monkeypatch):
    recalls = []
    monkeypatch.setattr(host, "recall", lambda *args: recalls.append(args) or {"result": {"items": []}})

    def handle(request):
        return httpx.Response(503, json={"error": "temporarily unavailable"})

    with MemoryClient("http://memory.test", "key", "brain", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            host.recall_context(client, "hiking plans")
    assert recalls == []


def test_failed_session_snapshot_never_returns_unfiltered_history(tmp_path, monkeypatch):
    histories = []
    monkeypatch.setattr(host, "flush", lambda *args: None)
    monkeypatch.setattr(host, "_finish_pending", lambda *args: None)
    monkeypatch.setattr(host, "_finish_abandoned", lambda *args: None)
    monkeypatch.setattr(host, "_history", lambda *args, **kwargs: histories.append(args) or
                        ("Jordan and the user hiked together.", True))
    monkeypatch.setattr(host, "_saved_context", lambda client, *args: host._relationship(client))

    def handle(request):
        return httpx.Response(503, json={"error": "temporarily unavailable"})

    with MemoryClient("http://memory.test", "key", "brain", transport=httpx.MockTransport(handle)) as client:
        monkeypatch.setattr(host, "ready_client", lambda *args: client)
        context = host.session_context(tmp_path, "session")
    assert "Jordan" not in context
    assert histories == []
