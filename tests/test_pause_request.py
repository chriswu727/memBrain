"""A host AI's pause carries the user's own words (evaluations/maturity-sixth-attempt-stop-2026-11-16.md).

No service and no database: memory clients are stand-ins, and every installation is a temporary directory."""
import asyncio
import importlib.util
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from test_hermes_adapter import Client as HermesClient
from test_hermes_adapter import provider as hermes_provider
from test_host import Client

from membrain import host, host_recording, local_recording, plugin, plugin_cli
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.mcp_server import create_server

ROOT = Path(__file__).resolve().parents[1]
REFUSAL = ("Pause only when the user asks you not to remember or store something. Pass request: their own words, "
           "copied from their current message.")


@pytest.fixture
def client(monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    return client


def _stage(directory, text, session="s1", turn="t1", **options):
    host.prompt_context(directory, session, text, turn_id=turn, **options)


@pytest.mark.parametrize("message,request_", [
    ("Honestly   DON'T keep the part about my sister in memory, ok?", '"don\'t keep the part about my sister."'),
    ("今天面试的事，这个别记。", "「这个别记」"),
    ("ＯＦＦ　ＴＨＥ　ＲＥＣＯＲＤ please, it's about money", "off the record"),
    ("Keep this to yourself:\n\nreally,   don't\nremember it", "  Don't remember it!  "),
])
def test_a_pause_quoting_the_users_current_message_is_accepted(tmp_path, client, message, request_):
    _stage(tmp_path, message)
    result = host_recording.agent_pause(tmp_path, request_, conversation=True)
    assert result["recording"] == "paused" and result["scope"] == "this conversation"
    assert result["note"] == "Tell the user in a few words that this conversation is no longer being recorded."
    host.finish_turn(tmp_path, "s1", "Understood.", turn_id="t1")
    assert client.observed == []  # The exchange that asked is not stored either.


@pytest.mark.parametrize("request_", [None, "", "   ", '"."', "x", "「」", 42, ["don't remember this"]])
def test_a_pause_without_the_users_words_is_refused_and_pauses_nothing(tmp_path, client, request_):
    _stage(tmp_path, "Don't remember the part about my sister, please.")
    result = host_recording.agent_pause(tmp_path, request_, conversation=True)
    assert result == {"error": REFUSAL + " Nothing was paused.", "code": "pause_request_missing"}
    assert not host.paused(tmp_path) and not host._pause_file(tmp_path).exists()
    # Without a staged message too: the required words are then the only guard, and they are missing.
    assert host_recording.agent_pause(tmp_path / "other", request_)["code"] == "pause_request_missing"
    assert not host.paused(tmp_path / "other")


def test_a_pause_with_words_that_are_not_in_the_current_message_is_refused_and_the_turn_is_recorded(tmp_path, client):
    _stage(tmp_path, "My sister moved to Leeds last week.")
    for request_ in ("don't remember this", "Leeds last month", "my brother moved"):
        result = host_recording.agent_pause(tmp_path, request_, conversation=True)
        assert result == {"error": REFUSAL + " Nothing was paused.", "code": "pause_request_not_in_message"}
    assert not host.paused(tmp_path)
    host.finish_turn(tmp_path, "s1", "Leeds is lovely.", turn_id="t1")
    assert [record["text"] for record in client.observed] == ["My sister moved to Leeds last week.", "Leeds is lovely."]
    # The words are checked against the current message only: the next one no longer holds them.
    _stage(tmp_path, "What should I cook tonight?", turn="t2")
    assert host_recording.agent_pause(tmp_path, "my sister moved")["code"] == "pause_request_not_in_message"


def test_an_older_unfinished_turn_of_the_conversation_is_not_its_current_message(tmp_path, client):
    _stage(tmp_path, "Don't store my home address anywhere.")  # The host was interrupted; no Stop came.
    _stage(tmp_path, "What should I cook tonight?", turn="t2")
    assert host_recording.agent_pause(tmp_path, "don't store my home address")["code"] == "pause_request_not_in_message"
    assert host.messages_in_progress(tmp_path, None) == ["What should I cook tonight?"]


def test_the_comparison_uses_the_message_as_staged_without_its_private_part(tmp_path, client):
    _stage(tmp_path, "Please don't keep this one: <private>my salary is 90k</private> thanks")
    assert host.messages_in_progress(tmp_path, None) == ["Please don't keep this one: [private] thanks"]
    # A quotation that copies the private part verbatim is compared without it, as it would be stored.
    result = host_recording.agent_pause(tmp_path, "don't keep this one: <private>my salary is 90k</private>")
    assert result["recording"] == "paused"


def test_a_pause_is_accepted_on_its_words_when_no_message_in_progress_is_known(tmp_path, client):
    # A host that stages no message, or a turn already finished: nothing to compare with.
    result = host_recording.agent_pause(tmp_path, "off the record", conversation=True)
    assert result["recording"] == "paused" and "note" in result
    host.resume(tmp_path)
    _stage(tmp_path, "My sister moved to Leeds.")
    host.finish_turn(tmp_path, "s1", "Noted.", turn_id="t1")
    assert host.messages_in_progress(tmp_path, None) == []
    assert host_recording.agent_pause(tmp_path, "please stop recording")["recording"] == "paused"


def test_a_current_message_that_was_not_kept_cannot_be_compared_so_the_words_are_trusted(tmp_path, client):
    # The message itself asked for the pause, so it was excluded when it arrived and its text was never kept;
    # an unrelated message in progress in another window, opened after it, does not make the request look invented.
    _stage(tmp_path, "Off the record: I'm job hunting.", session="s1")
    _stage(tmp_path, "My sister moved to Leeds.", session="other")
    assert sorted(host.messages_in_progress(tmp_path, None), key=str) == ["My sister moved to Leeds.", None]
    result = host_recording.agent_pause(tmp_path, "Stop remembering until I say so")
    assert result["recording"] == "paused" and result["until"] is None and "scope" not in result


def test_other_peoples_messages_are_not_this_users_current_message(tmp_path, client):
    _stage(tmp_path, "Don't remember what I say next.", session="alice-chat", user_id="alice")
    _stage(tmp_path, "What is the capital of Peru?", session="bob-chat", user_id="bob")
    assert host_recording.agent_pause(tmp_path, "don't remember what i say next", user_id="bob",
                                      conversation=True)["code"] == "pause_request_not_in_message"
    assert host_recording.agent_pause(tmp_path, "don't remember what I say next", user_id="alice",
                                      conversation=True)["recording"] == "paused"
    assert host.paused(tmp_path, "alice") and not host.paused(tmp_path, "bob")


@pytest.mark.parametrize("options,told", [
    ({"conversation": True}, "this conversation is no longer being recorded"),
    ({"hours": 2, "conversation": True}, "nothing is being recorded for the next 2 hours"),
    ({"hours": 1}, "nothing is being recorded for the next 1 hour"),
    ({"hours": 0.5}, "nothing is being recorded for the next 0.5 hours"),
    ({}, "nothing is being recorded until they say to start again"),
])
def test_the_answer_asks_the_host_to_tell_the_user_in_the_pauses_own_scope(tmp_path, client, options, told):
    result = host_recording.agent_pause(tmp_path, "don't remember this", options.pop("hours", None), **options)
    assert result["note"] == f"Tell the user in a few words that {told}."


def test_an_invalid_duration_still_raises_after_the_words_are_accepted_and_pauses_nothing(tmp_path, client):
    with pytest.raises(ValueError, match="positive number of hours"):
        host_recording.agent_pause(tmp_path, "don't remember this", -1)
    assert not host.paused(tmp_path)


def test_the_users_own_controls_need_no_quotation(tmp_path, client, capsys):
    _stage(tmp_path, "My sister moved to Leeds.")
    assert host_recording.pause(tmp_path)["recording"] == "paused"  # Library control, as before.
    host.resume(tmp_path)
    plugin_cli.dispatch(SimpleNamespace(plugin_command="pause", directory=tmp_path, hours=None))
    assert json.loads(capsys.readouterr().out)["recording"] == "paused" and host.paused(tmp_path)
    host.resume(tmp_path)
    local_recording.change(tmp_path, paused=True)  # The memory page's device-capture control.
    assert host.paused(tmp_path)


# Host entry points -----------------------------------------------------------------------------------------------

def test_the_mcp_pause_tool_requires_the_users_words_and_passes_them_on(tmp_path, client):
    server = create_server(Client(), directory=tmp_path)
    tool = {tool.name: tool for tool in asyncio.run(server.list_tools())}["memory_pause"]
    assert tool.inputSchema["required"] == ["request"]
    assert tool.inputSchema["properties"]["request"] == host_recording.REQUEST_FIELD["request"]
    assert tool.description.startswith(host.PAUSE_TOOL_DESCRIPTION) and "request is required" in tool.description
    _stage(tmp_path, "Between us, don't remember the bit about my debt.")
    _, missing = asyncio.run(server.call_tool("memory_pause", {}))
    _, invented = asyncio.run(server.call_tool("memory_pause", {"request": "the user asked to pause"}))
    assert (missing["code"], invented["code"]) == ("pause_request_missing", "pause_request_not_in_message")
    assert not host.paused(tmp_path)
    _, result = asyncio.run(server.call_tool("memory_pause", {"request": "don't remember the bit about my debt"}))
    assert result["scope"] == "this conversation" and "Tell the user" in result["note"] and host.paused(tmp_path)


def test_the_plugin_tool_command_passes_the_users_words_on(tmp_path, client, capsys):
    def tool(arguments):
        plugin.run_tool("pause", tmp_path, io.BytesIO(json.dumps(arguments).encode()))
        return json.loads(capsys.readouterr().out)

    _stage(tmp_path, "这个别记，我刚换了工作。", producer="membrain-openclaw")
    assert tool({})["code"] == "pause_request_missing"
    assert tool({"request": "别记录这个"})["code"] == "pause_request_not_in_message"
    assert not host.paused(tmp_path)
    result = tool({"request": "这个别记", "until_resumed": True})
    assert result["recording"] == "paused" and result["until"] is None and "until they say" in result["note"]


def test_the_plugin_tool_command_checks_a_bot_users_own_message(tmp_path, client, capsys):
    _stage(tmp_path, "Off the record: the owner's secret.", session="owner")
    _stage(tmp_path, "What's the weather?", session="guest", user_id="openclaw:guest")
    plugin.run_tool("pause", tmp_path, io.BytesIO(json.dumps(
        {"request": "the owner's secret", "membrain_user": "openclaw:guest"}).encode()))
    assert json.loads(capsys.readouterr().out)["code"] == "pause_request_not_in_message"
    plugin.run_tool("pause", tmp_path, io.BytesIO(json.dumps(
        {"request": "the weather", "membrain_user": "openclaw:guest"}).encode()))
    assert json.loads(capsys.readouterr().out)["recording"] == "paused"


def test_the_chat_bot_pause_passes_the_speakers_words_on(tmp_path, client):
    memory, mei, tom = ChatMemory(tmp_path), Speaker("discord", "mei"), Speaker("discord", "tom")
    host.prompt_context(tmp_path, memory.session(mei), "Please forget I said that, don't remember it.",
                        user_id=memory.user_id(mei))
    host.prompt_context(tmp_path, memory.session(tom), "Hello there!", user_id=memory.user_id(tom))
    assert memory.pause(mei)["code"] == "pause_request_missing"
    assert memory.pause(mei, request="hello there")["code"] == "pause_request_not_in_message"
    result = memory.pause(mei, 3, request="don't remember it")
    assert result["recording"] == "paused" and "next 3 hours" in result["note"]
    assert host.paused(tmp_path, memory.user_id(mei)) and not host.paused(tmp_path, memory.user_id(tom))


def test_a_role_play_bot_checks_the_message_of_the_persons_role_play(tmp_path, client):
    memory, mei = ChatMemory(tmp_path, roleplay="Captain Vale"), Speaker("qq", "mei")
    host.prompt_context(tmp_path, memory.session(mei), "Captain, don't log this in the ship's memory.",
                        user_id=memory.user_id(mei), roleplay="Captain Vale")
    assert memory.pause(mei, request="the treasure map")["code"] == "pause_request_not_in_message"
    assert memory.pause(mei, request="don't log this")["recording"] == "paused"


def test_hermes_passes_the_users_words_on_and_lists_them_as_required(tmp_path, monkeypatch):
    instance = hermes_provider(tmp_path, monkeypatch, HermesClient())
    schema = {schema["name"]: schema for schema in instance.get_tool_schemas()}["membrain_pause"]
    assert schema["parameters"]["required"] == ["request"] and schema["description"] == host.PAUSE_TOOL_DESCRIPTION
    instance.prefetch("I'd rather you didn't store this one: my diagnosis came back.", session_id="h1")
    assert json.loads(instance.handle_tool_call("membrain_pause", {}))["code"] == "pause_request_missing"
    assert json.loads(instance.handle_tool_call("membrain_pause", {"request": "pause"}))["code"] == \
        "pause_request_not_in_message"
    result = json.loads(instance.handle_tool_call("membrain_pause", {"request": "didn't store this one"}))
    assert result["recording"] == "paused" and "note" in result


def test_every_host_describes_the_same_pause_tool():
    script = (ROOT / "integrations" / "openclaw" / "membrain" / "index.js").read_text(encoding="utf-8")
    block = script[script.index('name: "membrain_pause"'):script.index('name: "membrain_resume"')]
    description = re.search(r"description: '((?:[^'\\]|\\.)*)'", block)[1].replace("\\'", "'")
    assert description == host.PAUSE_TOOL_DESCRIPTION
    assert 'required: ["request"]' in block and "request: { type: \"string\"" in block
    astrbot = (ROOT / "integrations" / "astrbot" / "astrbot_plugin_membrain" / "main.py").read_text(encoding="utf-8")
    assert "membrain_pause.__doc__ = PAUSE_TOOL_DESCRIPTION" in astrbot and "request(string): Required." in astrbot
    assert "with their words" in host.privacy_notice()
    assert "pause" not in host.server_instructions() and len(host.server_instructions()) <= 1400


# Consolidation's final answer ---------------------------------------------------------------------------------------

class _Cues:
    def write_message_cues(self, items, **options):
        return {"written": len(items), "skipped": 0}

    def pending_message_cues(self, limit):
        return {"remaining": 0}


def test_consolidations_answer_says_the_host_is_finished_when_its_answer_is_written():
    # Changed after the seventh maturity attempt: the host now indexes before it replies, so the last answer asks
    # for the reply once, and a reply written before the call is not written again (a doubled answer).
    note = host.consolidate(_Cues(), [{"id": 1, "cues": ["Leeds"]}], 1)["note"]
    assert note == ("Done. Now write your reply to the user's message, once. If you already wrote it before calling "
                    "this tool, do not write it again: end your turn with no more than a word and call no other tool. "
                    "Do not describe the indexing beyond a few words.")
    # A host once ended its turn with only "Memory's updated.": the note still asks for the reply itself.
    assert note.startswith("Done. Now write your reply") and "call no other tool" in note


class _Pending:
    def pending_message_cues(self, limit):
        return {"remaining": 7}


@pytest.mark.parametrize("tools,name", [(host.TOOL_NAMES, "memory_consolidate"),
                                        (plugin.HOST_TOOLS["openclaw"], "membrain_consolidate")])
def test_the_notice_asks_for_indexing_before_the_reply_on_every_host(tools, name):
    # Seventh maturity attempt: answering first and indexing after showed the user two answers in 11 of 124 turns.
    assert host.consolidation_notice(_Pending(), tools) == (
        f"7 earlier messages have not been indexed by memory yet. Once in this conversation, before you write your "
        f"reply to the user's first message, call the {name} tool without arguments and do what it returns; then "
        "write your reply. Do not describe the indexing to the user beyond a few words.")


def test_nothing_shared_with_hosts_still_asks_for_the_answer_before_indexing(tmp_path):
    from membrain.adapters.chatbot import TOOLS as CHAT_TOOLS

    batch = host.consolidate(_Batch(), handed_out={})
    texts = [host.consolidation_notice(_Pending(), {**CHAT_TOOLS, "consolidate": "membrain_consolidate"}),
             host.consolidation_notice(_Pending()), host.server_instructions(), host.CONSOLIDATION_INSTRUCTIONS,
             batch["instructions"], host.consolidate(_Batch(), [], 3)["note"],
             (ROOT / "plugins" / "membrain" / "skills" / "membrain" / "SKILL.md").read_text(encoding="utf-8")]
    for text in texts:
        lowered = text.lower()
        assert "after you have answered" not in lowered and "answered the user" not in lowered
        assert "answer first" not in lowered
    assert len(host.server_instructions()) <= 1400


def test_the_standing_instructions_ask_for_memory_tools_before_the_reply():
    # Seventh maturity attempt: 2 of 11 doubled answers were a reply written beside a memory_note call, then written
    # again after the tool answered. Text written before a tool call is shown to the user.
    text = host.server_instructions()
    sentence = "Use memory tools before your reply, not after it."
    assert text.count(sentence) == 1
    assert text.index(sentence) > text.index("when the session notice asks.")
    assert text.endswith(sentence + " Mention memory use in a few words at most.")
    assert len(text) <= 1400


class _Batch(_Cues):
    def pending_message_cues(self, limit, **options):
        if limit == 1:
            return {"remaining": 0}
        return {"items": [{"sequence": 3, "text": "My sister moved to Leeds.", "recorded_at": "2026-09-12T10:00:00Z"}],
                "through_sequence": 3, "remaining": 0}

    def relationship_boundaries(self):
        return {"boundaries": []}


# The evaluation harness ------------------------------------------------------------------------------------------

def _harness():
    spec = importlib.util.spec_from_file_location("c5_harness_pause", ROOT / "evaluations" / "c5-harness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_harness_quotes_the_turns_words_for_a_scripted_pause_without_them(monkeypatch):
    harness = _harness()
    monkeypatch.setattr(harness, "STUB", True)  # No key is read.
    stub = harness.StubHost({("s1", 0): [{"tool": "memory_pause", "arguments": {}}],
                             ("s1", 1): [{"tool": "memory_pause", "arguments": {"request": "their words"}}]})
    tools = [{"type": "function", "function": {"name": "memory_pause", "parameters": {"properties": {}}}}]
    model = harness.Host(cap=5, transport=httpx.MockTransport(stub))
    calls = []
    for turn, text in enumerate(("Off the record: I'm job hunting.", "Their words, please.")):
        stub.key, stub.text = ("s1", turn), text
        message, _ = model.call([{"role": "system", "content": "x"},
                                 {"role": "user", "content": "<membrain-recall>...</membrain-recall>\n\n" + text}],
                                tools)
        calls.append(json.loads(message["tool_calls"][0]["function"]["arguments"]))
    assert calls == [{"request": "Off the record: I'm job hunting."}, {"request": "their words"}]
    # The script itself is unchanged, so what the scenario means to leave unrecorded is read as before.
    assert stub.script[("s1", 0)] == [{"tool": "memory_pause", "arguments": {}}]
    script = {("s1", 0): [{"tool": "memory_pause", "arguments": {}}],
              ("s1", 1): [{"tool": "memory_resume", "arguments": {"session_id": "s1"}}]}
    module = SimpleNamespace(SESSIONS_LONG=[("s1", ["a", "b"])], STUB_HOST=script)
    assert harness.intended_unrecorded(module) == {("s1", 0)}
