import asyncio
import io
import json

import pytest
from test_host_recording import connected as connected
from test_server_recording import policy
from test_server_recording import turns as turns

from membrain import host, host_recording, host_turns, plugin
from membrain.adapters import hermes
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.mcp_server import create_server


def capture(context):
    if "recording_capture=" not in (context or ""):
        return "missing-capture"
    return json.JSONDecoder().raw_decode(context.split("recording_capture=", 1)[1])[0]


def invoke(kind, directory, connected, capsys, token, **fields):
    args = {"text": "A synthetic private note.", "recording_capture": token, **fields}
    if kind == "plugin":
        plugin.run_tool("note", directory, stream=io.BytesIO(json.dumps(args).encode()))
        return json.loads(capsys.readouterr().out)
    if kind == "hermes":
        provider = hermes.MembrainProvider()
        provider._directory = directory
        return json.loads(provider.handle_tool_call("membrain_note", args))
    if kind == "chat":
        memory = ChatMemory(directory)
        memory.user_id = lambda speaker: None
        return memory.note(Speaker("api", "owner"), **args)
    with connected(directory) as client:
        server = create_server(client, directory=directory)
        return asyncio.run(server.call_tool("memory_note", args))[1]


@pytest.mark.parametrize("kind", ["plugin", "hermes", "chat", "mcp"])
@pytest.mark.parametrize("control", ["local", "server"])
def test_delayed_manual_note_cannot_write_after_pause_and_resume(turns, connected, tmp_path, capsys, kind, control):
    token = capture(host.prompt_context(tmp_path, "s", "Original private detail.", turn_id="old", include_source=True))
    if control == "local":
        host.pause(tmp_path)
        host.resume(tmp_path)
    else:
        policy(turns, True, 0)
        policy(turns, False, 1)
    result = invoke(kind, tmp_path, connected, capsys, token)
    assert "error" in result
    assert turns.service.timeline(turns.principal, turns.brain, conversation_id="membrain-notes", roles=("assistant",))["items"] == []


@pytest.mark.parametrize("kind", ["plugin", "hermes", "chat", "mcp"])
def test_manual_note_needs_original_turn_authority(turns, connected, tmp_path, capsys, kind):
    result = invoke(kind, tmp_path, connected, capsys, None)
    assert "error" in result
    assert turns.service.timeline(turns.principal, turns.brain, conversation_id="membrain-notes", roles=("assistant",))["items"] == []


def test_prompt_issues_capture_for_the_original_turn_only(turns, connected, tmp_path):
    context = host.prompt_context(tmp_path, "s", "Original public detail.", turn_id="old", include_source=True)
    assert capture(context) != "missing-capture"
    host.pause(tmp_path)
    private = host.prompt_context(tmp_path, "s", "Private detail.", turn_id="private", include_source=True)
    assert "recording_capture=" not in private


@pytest.mark.parametrize("kind", ["plugin", "hermes", "chat", "mcp"])
def test_new_turn_after_resume_can_save_and_replace_with_original_sources(turns, connected, tmp_path, capsys, kind):
    policy(turns, True, 0)
    policy(turns, False, 1)
    context = host.prompt_context(tmp_path, "s", "A public appointment.", turn_id="new", include_source=True)
    token = capture(context)
    references = json.JSONDecoder().raw_decode(context.split("source_messages=", 1)[1])[0]
    first = invoke(kind, tmp_path, connected, capsys, token, source_messages=references)
    assert first["pending_source_count"] == 1
    host.finish_turn(tmp_path, "s", "Understood.", turn_id="new")
    second = invoke(kind, tmp_path, connected, capsys, token, replaces=[first["note_id"]], source_messages=references)
    assert second["replaced"] == [first["note_id"]]
    assert len(second["source_event_ids"]) == 1
    host.pause(tmp_path)
    host.resume(tmp_path)
    rejected = invoke(kind, tmp_path, connected, capsys, token, replaces=[second["note_id"]])
    assert "error" in rejected
    notes = turns.service.timeline(turns.principal, turns.brain, conversation_id="membrain-notes", roles=("assistant",))["items"]
    assert [note["event_id"] for note in notes] == [second["note_id"]]


def test_capture_survives_restart_without_borrowing_a_new_turns_revision(turns, connected, tmp_path):
    old = capture(host.prompt_context(tmp_path, "s", "First detail.", turn_id="one", include_source=True))
    policy(turns, True, 0)
    policy(turns, False, 1)
    new = capture(host.prompt_context(tmp_path, "s", "Second detail.", turn_id="two", include_source=True))
    with connected(tmp_path) as client:
        assert host_recording.note_revision(tmp_path, client, old) == 0
        assert host_recording.note_revision(tmp_path, client, new) == 2
        assert host_recording.save_note(tmp_path, client, "Old detail.", recording_capture=old)["code"] == "recording_stale"
        assert "note_id" in host_recording.save_note(tmp_path, client, "New detail.", recording_capture=new)


@pytest.mark.parametrize("mutation", [None, "", "../bad", "f" * 10000, {}, True])
def test_malformed_or_missing_capture_cannot_write(turns, connected, tmp_path, mutation):
    with connected(tmp_path) as client:
        assert "error" in host_recording.save_note(tmp_path, client, "Rejected.", recording_capture=mutation)
    assert turns.service.timeline(turns.principal, turns.brain, conversation_id="membrain-notes", roles=("assistant",))["items"] == []


def test_capture_cannot_cross_owner_roleplay_or_service_target(turns, connected, tmp_path):
    alice = "alice-" + turns.brain
    token = capture(host.prompt_context(tmp_path, "s", "Alice's detail.", turn_id="one", user_id=alice, include_source=True))
    for owner in (None, "bob-" + turns.brain, host.roleplay_user(alice, "Ada")):
        with connected(tmp_path, owner) as client:
            assert "error" in host_recording.save_note(tmp_path, client, "Rejected.", recording_capture=token, user_id=owner)
    with connected(tmp_path, alice) as client:
        client._http.headers["X-Memory-Recovery-Epoch"] = "00000000-0000-4000-8000-000000000001"
        assert host_recording.save_note(tmp_path, client, "Rejected.", recording_capture=token, user_id=alice)["code"] == "recording_stale"


def test_pausing_one_owner_revokes_their_completed_captures_only(turns, connected, tmp_path):
    alice, bob = "alice-" + turns.brain, "bob-" + turns.brain
    tokens = {}
    for owner in (alice, bob, host.roleplay_user(alice, "Ada")):
        tokens[owner] = capture(host.prompt_context(tmp_path, "s", "A public detail.", turn_id="one", user_id=owner, include_source=True))
        host.finish_turn(tmp_path, "s", "Understood.", turn_id="one", user_id=owner)
    host.pause(tmp_path, user_id=alice)
    host.resume(tmp_path, user_id=alice)
    for owner, token in tokens.items():
        with connected(tmp_path, owner) as client:
            result = host_recording.save_note(tmp_path, client, "A new note.", recording_capture=token, user_id=owner)
        assert ("note_id" in result) is (owner == bob)


def test_evicted_and_reused_implicit_turn_captures_fail_closed(turns, connected, tmp_path, monkeypatch):
    monkeypatch.setattr(host_turns, "MAX_FINISHED", 1)
    old = capture(host.prompt_context(tmp_path, "s", "First detail.", include_source=True))
    host.finish_turn(tmp_path, "s", "Understood.")
    new = capture(host.prompt_context(tmp_path, "s", "First detail.", include_source=True))
    assert old != new
    host.finish_turn(tmp_path, "s", "Understood.")
    host.prompt_context(tmp_path, "s", "Another detail.", turn_id="other", include_source=True)
    host.finish_turn(tmp_path, "s", "Understood.", turn_id="other")
    with connected(tmp_path) as client:
        for token in (old, new):
            assert "error" in host_recording.save_note(tmp_path, client, "Rejected.", recording_capture=token)


def test_local_mcp_observation_uses_original_recording_revision(turns, connected, tmp_path):
    token = capture(host.prompt_context(tmp_path, "s", "First detail.", turn_id="one", include_source=True))
    with connected(tmp_path) as client:
        server = create_server(client, directory=tmp_path)
        args = {"text": "An observation.", "conversation_id": "s", "branch_id": "main", "source_event_key": "observed"}
        missing = asyncio.run(server.call_tool("memory_observe", args))[1]
        assert "error" in missing
        saved = asyncio.run(server.call_tool("memory_observe", {**args, "recording_capture": token}))[1]
        assert saved["result"]["accepted_event_ids"]
        policy(turns, True, 0)
        policy(turns, False, 1)
        rejected = asyncio.run(server.call_tool("memory_observe", {**args, "source_event_key": "late", "recording_capture": token}))[1]
        assert rejected.get("outcome") == "rejected" or "error" in rejected


def test_tools_only_mcp_keeps_explicit_writes_and_does_not_ignore_supplied_capture(turns, connected, tmp_path):
    with connected(tmp_path) as client:
        server = create_server(client, directory=tmp_path, require_turn_capture=False)
        capabilities = asyncio.run(server.call_tool("memory_capabilities", {}))[1]
        assert capabilities["recording_capture_required"] is False
        saved = asyncio.run(server.call_tool("memory_note", {"text": "An explicit tools-only note."}))[1]
        assert saved["note_id"]
        refused = asyncio.run(server.call_tool("memory_note", {"text": "Rejected.", "recording_capture": "invalid"}))[1]
        assert "error" in refused
        host.pause(tmp_path)
        assert "error" in asyncio.run(server.call_tool("memory_note", {"text": "Private."}))[1]


def test_host_disabled_groups_cannot_use_note_tools(turns, connected, tmp_path):
    memory = ChatMemory(tmp_path, record_groups=False)
    assert "not available" in memory.note(Speaker("api", "alice", "group"), "Rejected.")["error"]


def test_tampered_capture_and_corrupt_marker_fail_closed(turns, connected, tmp_path):
    token = capture(host.prompt_context(tmp_path, "s", "A public detail.", turn_id="one", include_source=True))
    with connected(tmp_path) as client:
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        assert "error" in host_recording.save_note(tmp_path, client, "Rejected.", recording_capture=tampered)
        host._session_marker(tmp_path, "s").write_text('{"turns": []}')
        assert "error" in host_recording.save_note(tmp_path, client, "Rejected.", recording_capture=token)


def test_remote_mcp_cannot_silently_drop_a_host_capture(turns, connected, tmp_path):
    with connected(tmp_path) as client:
        server = create_server(client)
        for name, args in (("memory_note", {"text": "Rejected."}), ("memory_observe", {
            "text": "Rejected.", "conversation_id": "s", "branch_id": "main", "source_event_key": "k"})):
            result = asyncio.run(server.call_tool(name, {**args, "recording_capture": "unavailable"}))[1]
            assert "cannot validate" in result["error"]
    assert turns.service.timeline(turns.principal, turns.brain, roles=("assistant",))["items"] == []
