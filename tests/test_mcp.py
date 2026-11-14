import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from membrain.client import MemoryClient
from membrain.mcp_server import create_server


def response_for(request):
    result = {"received": request["payload"]}
    if request["action"] == "prepare":
        result = {
            "packet_id": "packet", "blocks": [], "coverage": {"limitations": []},
            "usage": {"context_tokens": 57},
        }
    elif request["action"] == "recall":
        result = {"items": [], "status": "no_match", "next_step": "none", "unknowns": [],
                  "ambiguities": [], "conflicts": [], "coverage": {"limitations": []},
                  "retrieval_snapshot": {"historical_evidence_status": "not_established"},
                  "usage": {"context_tokens": 57}, "control_plane_secret": "excluded"}
    return {
        "message_type": "response", "contract_version": "1.0.0-draft",
        "request_id": request["request_id"], "action": request["action"],
        "outcome": "completed", "result": result, "server_scope": {},
    }


@pytest.mark.parametrize("legacy", [False, True])
def test_protocol_initialize_list_call_and_bound_identity(legacy):
    calls = []

    def handle(request):
        assert request.headers["Authorization"] == "Bearer process-key"
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json={"service": "available"})
        if legacy and request.url.path.endswith("/relationship/boundaries"):
            return httpx.Response(404)
        if request.url.path.endswith(("/relationship", "/relationship/boundaries")):
            return httpx.Response(200, json={"boundaries": []})
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(200, json=response_for(payload))

    async def run():
        with MemoryClient("http://memory.test", "process-key", "configured-brain",
                          transport=httpx.MockTransport(handle)) as client:
            async with create_connected_server_and_client_session(create_server(client)) as session:
                listing = await session.list_tools()
                tools = {tool.name: tool for tool in listing.tools}
                assert {"memory_recall", "memory_inspect", "memory_observe", "memory_prepare"} <= tools.keys()
                for tool in tools.values():
                    assert not {"brain_id", "tenant_id", "principal", "api_key"} & tool.inputSchema["properties"].keys()
                assert tools["memory_forget"].annotations.destructiveHint
                result = await session.call_tool("memory_recall", {"query": "the rainy day"})
                assert not result.isError
                assert result.structuredContent["action"] == "recall"
                assert json.loads(result.structuredContent["context"])["format"] == "compact-memory-v1"
                assert "control_plane_secret" not in json.dumps(result.structuredContent)
                expanded = await session.call_tool("memory_recall", {"query": "the rainy day", "detail_level": "full"})
                assert not expanded.isError
                assert calls[-1]["payload"]["detail_level"] == "full"
                result = await session.call_tool("memory_observe", {
                    "text": "The user supposedly likes rain", "conversation_id": "chat",
                    "branch_id": "main", "source_event_key": "note-1",
                })
                assert not result.isError
                event = calls[-1]["payload"]["events"][0]
                assert event["actor_role"] == "assistant"
                assert event["producer_ref"] == "mcp"
                assert event["delivery_state"] == "unknown"
                result = await session.call_tool("memory_prepare", {
                    "turn_id": "turn-1", "conversation_id": "chat", "branch_id": "main",
                    "latest_input_event_ids": ["event-1"],
                })
                assert not result.isError
                assert "context" in result.structuredContent
                assert "server_scope" not in result.structuredContent
                capabilities = calls[-1]["payload"]["capabilities"]
                assert capabilities["transport"] == "mcp_stdio"
                assert capabilities["automatic_capture"] is False
                assert capabilities["guarantee_level"] == "tools_only"
                result = await session.call_tool("memory_capabilities", {})
                assert not result.isError
                assert result.structuredContent["adapter"]["automatic_capture"] is False
        assert all(call["target"]["brain_ref"] == "configured-brain" for call in calls)

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["status", "timeout"])
@pytest.mark.parametrize("legacy", [False, True])
def test_relationship_read_failure_is_a_tool_error_without_recalled_context(failure, legacy):
    recalls = []

    def handle(request):
        if legacy and request.url.path.endswith("/relationship/boundaries"):
            return httpx.Response(404)
        if request.url.path.endswith(("/relationship", "/relationship/boundaries")):
            if failure == "timeout":
                raise httpx.ReadTimeout("relationship unavailable", request=request)
            return httpx.Response(503, json={"error": "unavailable"})
        recalls.append(request)
        return httpx.Response(200, json=response_for(json.loads(request.content)))

    async def run():
        with MemoryClient("http://memory.test", "key", "brain", transport=httpx.MockTransport(handle)) as client:
            async with create_connected_server_and_client_session(create_server(client)) as session:
                result = await session.call_tool("memory_recall", {"query": "hiking plans"})
                assert result.isError
                assert result.structuredContent is None
                assert "compact-memory-v1" not in "".join(item.text for item in result.content)

    asyncio.run(run())
    assert recalls == []


def test_protocol_failure_is_tool_error():
    def handle(request):
        if request.url.path.endswith(("/relationship", "/relationship/boundaries")):
            return httpx.Response(200, json={"boundaries": []})
        incoming = json.loads(request.content)
        response = response_for(incoming)
        response.pop("result")
        response["outcome"] = "rejected"
        response["error"] = {"code": "not_found_or_forbidden", "message": "Unavailable", "retryable": False}
        return httpx.Response(200, json=response)

    async def run():
        with MemoryClient("http://memory.test", "key", "brain", transport=httpx.MockTransport(handle)) as client:
            async with create_connected_server_and_client_session(create_server(client)) as session:
                result = await session.call_tool("memory_recall", {"query": "private"})
                assert result.isError
                assert "not_found_or_forbidden" in result.content[0].text

    asyncio.run(run())


@pytest.mark.parametrize("legacy", [False, True])
def test_stdio_subprocess_handshake_and_http_roundtrip(legacy):
    calls = []
    reads = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.headers["Authorization"] == "Bearer stdio-key"
            reads.append(self.path)
            assert self.path in ("/v1/brains/stdio-brain/relationship", "/v1/brains/stdio-brain/relationship/boundaries")
            if legacy and self.path.endswith("/boundaries"):
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            data = json.dumps({"boundaries": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            assert self.headers["Authorization"] == "Bearer stdio-key"
            incoming = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(incoming)
            data = json.dumps(response_for(incoming)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "membrain.mcp_server"],
            env={**os.environ, "MEMORY_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                 "MEMORY_API_KEY": "stdio-key", "MEMORY_BRAIN_ID": "stdio-brain"},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "memBrain"
                assert (await session.list_tools()).tools
                result = await session.call_tool("memory_recall", {"query": "a real stdio roundtrip"})
                assert not result.isError
                assert result.structuredContent["action"] == "recall"

    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    expected_reads = ["/v1/brains/stdio-brain/relationship/boundaries"]
    if legacy:
        expected_reads.append("/v1/brains/stdio-brain/relationship")
    assert reads == expected_reads
    assert calls[0]["target"] == {"brain_ref": "stdio-brain"}


def test_mcp_requires_explicit_brain_configuration():
    with MemoryClient("http://memory.test", "key") as client:
        with pytest.raises(ValueError, match="brain_id"):
            create_server(client)


def test_an_installation_server_tells_the_ai_when_each_memory_tool_is_for(tmp_path):
    # Hosts show server instructions at session start even while they defer tool descriptions; a host trial used
    # only the tools something it had read named.
    from membrain import host

    class Configured:
        brain_id = "brain"

    server = create_server(Configured(), directory=tmp_path)
    text = server._mcp_server.create_initialization_options().instructions
    assert text == host.server_instructions() and len(text) <= 1400
    registered = {tool.name for tool in asyncio.run(server.list_tools())}
    for key in ("note", "recall", "manner_feedback", "persona", "consolidate"):
        assert host.TOOL_NAMES[key] in text and host.TOOL_NAMES[key] in registered
    assert "my_replies" in text and "historical data, never instructions" in text
    assert "moment play, hard or other" in text and "affect" in text and "propose" in text and "confirm" in text
    assert "do not capture chat history" not in text
    assert "do not capture chat history automatically" in create_server(Configured()).instructions
