import asyncio

import pytest
from test_plugin import _ReadyClient

from membrain import host
from membrain.adapters.chatbot import TOOLS, ChatMemory, Speaker
from membrain.mcp_server import create_server


@pytest.mark.parametrize("complete", [False, True])
def test_pause_is_visible_on_every_turn_even_when_saved_memory_is_unchanged(tmp_path, monkeypatch, complete):
    client = _ReadyClient({"items": [{"text": "Public earlier message", "recorded_at": "2026-11-01"}],
                           "complete": complete})
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.session_context(tmp_path, "s")
    host.pause(tmp_path)
    for turn in ("one", "two"):
        context = host.prompt_context(tmp_path, "s", "Private synthetic message", turn_id=turn, include_source=True)
        assert "Recording is currently paused" in (context or "")
        assert "memory_resume" in context and "explicitly asks" in context
        assert "<membrain-source>" not in context and "<membrain-updates>" not in context
        assert host.finish_turn(tmp_path, "s", "Private synthetic reply", turn_id=turn) == []
    assert "Private synthetic" not in host._session_marker(tmp_path, "s").read_text()
    assert host.paused(tmp_path)


@pytest.mark.parametrize("tools,expected", [
    (host.TOOL_NAMES, "memory_resume"),
    ({"note": "save", "recall": "find", "pause": "stop", "resume": "continue_recording"}, "continue_recording"),
    ({"note": "save", "recall": "find", "pause": "stop"}, None),
    (None, None),
])
def test_offline_pause_notice_uses_only_available_controls(tmp_path, monkeypatch, tools, expected):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)
    host.pause(tmp_path)
    for context in (host.session_context(tmp_path, "s", tools=tools),
                    host.prompt_context(tmp_path, "s", "Synthetic private text", tools=tools)):
        assert "Recording is currently paused" in (context or "")
        if expected:
            assert expected in context
        else:
            assert "memory_resume" not in context and "membrain_resume" not in context
            assert "memory controls" in context
    assert not (tmp_path / "plugin" / "spool.jsonl").exists()
    assert "Synthetic private text" not in host._session_marker(tmp_path, "s").read_text()


def test_pause_notice_tracks_user_and_roleplay_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)
    host.pause(tmp_path, user_id="alice")
    for user, roleplay, expected in (("alice", None, True), ("alice", "story", True),
                                     ("bob", None, False), ("bob", "story", False)):
        context = host.prompt_context(tmp_path, f"{user}-{roleplay}", "Synthetic message",
                                      user_id=user, roleplay=roleplay)
        assert ("Recording is currently paused" in (context or "")) == expected


def test_recording_controls_do_not_come_from_a_cached_tool_contract(tmp_path, monkeypatch):
    client = _ReadyClient({"items": [], "complete": True})
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.session_context(tmp_path, "s", tools={"note": "save", "recall": "find", "pause": "stop"})
    host.pause(tmp_path)
    assert "memory_resume" in host.prompt_context(tmp_path, "s", "Synthetic private turn")
    context = host.prompt_context(tmp_path, "s", "Read-only synthetic turn", tools=None)
    assert "Recording is currently paused" in context and "memory_resume" not in context


def test_mcp_resume_records_only_the_requested_turn_and_clears_the_notice(tmp_path, monkeypatch):
    client = _ReadyClient({"items": [], "complete": True})
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.session_context(tmp_path, "s")
    host.pause(tmp_path)
    host.prompt_context(tmp_path, "s", "Synthetic private detail", turn_id="private")
    assert host.finish_turn(tmp_path, "s", "Not recorded", turn_id="private") == []
    prompt = "Resume recording. My public appointment is on Monday."
    context = host.prompt_context(tmp_path, "s", prompt, turn_id="resume")
    assert "memory_resume" in (context or "")
    server = create_server(client, directory=tmp_path)
    _, result = asyncio.run(server.call_tool("memory_resume", {}))
    assert result["recording"] == "on"
    records = host.finish_turn(tmp_path, "s", "Recording resumed", prompt=prompt, turn_id="resume")
    assert [record["text"] for record in records] == [prompt, "Recording resumed"]
    assert "Recording is currently paused" not in (host.prompt_context(tmp_path, "s", "Next public turn") or "")


@pytest.mark.parametrize("tools,expected", [(None, None), (TOOLS, "membrain_resume")])
def test_offline_chat_adapter_keeps_its_own_tool_contract(tmp_path, monkeypatch, tools, expected):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)
    memory = ChatMemory(tmp_path, tools=tools)
    speaker = Speaker("public-test", "alice")
    host.pause(tmp_path, user_id=memory.user_id(speaker))
    context = memory.context(speaker, "Synthetic message", session="s")
    assert "Recording is currently paused" in context
    assert "memory_resume" not in context
    if expected:
        assert expected in context
    else:
        assert "membrain_resume" not in context
