import json

import pytest
from test_hermes_adapter import Client, provider

from membrain import host


@pytest.mark.parametrize("context", ["subagent", "cron", "flush"])
@pytest.mark.parametrize("tool", ["note", "boundary", "pause", "resume"])
def test_readonly_context_cannot_change_memory_or_primary_recording(tmp_path, monkeypatch, context, tool):
    client = Client(notes=[{"event_id": "original", "text": "The user prefers tea."}])
    instance = provider(tmp_path, monkeypatch, client, agent_context=context)
    directory = instance._directory
    if tool == "resume":
        host.pause(directory)
        host.prompt_context(directory, "h1", "A private primary exchange.")
    paused_before = host.paused(directory)
    result = json.loads(instance.handle_tool_call(f"membrain_{tool}", {
        "text": "The user prefers coffee.", "replaces": ["original"], "topic": "tea",
        "until_resumed": True,
    }))
    assert client.observed == [] and client.forgotten == []
    assert host.paused(directory) == paused_before
    assert not host.turn_resumed(directory, "h1")
    assert "cannot change memory" in result.get("error", "")


@pytest.mark.parametrize("context", ["subagent", "cron", "flush"])
def test_readonly_context_offers_search_without_advertising_write_tools(tmp_path, monkeypatch, context):
    client = Client()
    instance = provider(tmp_path, monkeypatch, client, agent_context=context)
    assert [tool["name"] for tool in instance.get_tool_schemas()] == ["membrain_search"]
    block = instance.system_prompt_block()
    assert "membrain_note" not in block and "membrain_pause" not in block
    result = json.loads(instance.handle_tool_call("membrain_search", {"query": "tea"}))
    assert result == {"context": "No matching records."}
    assert client.observed == []
