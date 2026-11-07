import asyncio
import io
import json

import pytest
from test_host import Client

from membrain import host, plugin
from membrain.mcp_server import create_server


@pytest.mark.parametrize("transport", ["mcp", "cli"])
def test_unscoped_resume_never_selects_another_conversations_private_turn(tmp_path, monkeypatch, transport):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.pause(tmp_path)
    host.prompt_context(tmp_path, "requester", "Resume recording please.")
    host.prompt_context(tmp_path, "private", "Unrelated private synthetic detail.")
    if transport == "mcp":
        server = create_server(client, directory=tmp_path)
        asyncio.run(server.call_tool("memory_resume", {}))
    else:
        plugin.run_tool("resume", tmp_path, stream=io.BytesIO(b"{}"))
    assert host.finish_turn(tmp_path, "private", "Private reply", prompt="Unrelated private synthetic detail.") == []
    assert not host.turn_resumed(tmp_path, "requester")
    assert client.observed == []


def test_owner_resume_does_not_reactivate_another_users_only_paused_turn(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.pause(tmp_path)
    host.prompt_context(tmp_path, "other-user", "Another user's private synthetic detail.", user_id="other")
    host.resume(tmp_path, current_turn=True, session="other-user")
    assert not host.turn_resumed(tmp_path, "other-user")
    assert host.finish_turn(tmp_path, "other-user", "Private reply", prompt="Another user's private synthetic detail.",
                            user_id="other") == []
    assert client.observed == []


def test_unscoped_resume_does_not_guess_even_when_only_one_private_turn_exists(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.pause(tmp_path)
    host.prompt_context(tmp_path, "private", "Private synthetic detail from another conversation.")
    result = host.resume(tmp_path, current_turn=True)
    assert result == {"recording": "on", "current_turn_resumed": False, "reason": "session_required"}
    assert host.finish_turn(tmp_path, "private", "Private reply", prompt="Private synthetic detail from another conversation.") == []
    host.prompt_context(tmp_path, "future", "New public turn")
    records = host.finish_turn(tmp_path, "future", "Public reply")
    assert [record["text"] for record in records] == ["New public turn", "Public reply"]


@pytest.mark.parametrize("transport", ["mcp", "cli"])
def test_explicit_resume_records_the_requesting_conversation_even_when_another_turn_starts_later(
        tmp_path, monkeypatch, transport):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.pause(tmp_path)
    prompt = "Resume recording. My public appointment is on Monday."
    context = host.prompt_context(tmp_path, "requester", prompt)
    assert 'session_id="requester"' in context
    host.prompt_context(tmp_path, "private", "Unrelated private synthetic detail.")
    arguments = {"session_id": "requester"}
    if transport == "mcp":
        server = create_server(client, directory=tmp_path)
        asyncio.run(server.call_tool("memory_resume", arguments))
    else:
        plugin.run_tool("resume", tmp_path, stream=io.BytesIO(json.dumps(arguments).encode()))
    assert host.turn_resumed(tmp_path, "requester") and not host.turn_resumed(tmp_path, "private")
    assert host.finish_turn(tmp_path, "private", "Private reply", prompt="Unrelated private synthetic detail.") == []
    records = host.finish_turn(tmp_path, "requester", "Recording resumed", prompt=prompt)
    assert [record["text"] for record in records] == [prompt, "Recording resumed"]
    assert [record["text"] for record in client.observed] == [prompt, "Recording resumed"]


@pytest.mark.parametrize("session", ["", 5, "s" * 201])
def test_invalid_resume_scope_does_not_clear_the_pause(tmp_path, session):
    host.pause(tmp_path)
    with pytest.raises(ValueError, match="resume session"):
        host.resume(tmp_path, current_turn=True, session=session)
    assert host.paused(tmp_path)
