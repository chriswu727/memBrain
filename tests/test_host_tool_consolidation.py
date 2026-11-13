"""Hosts without the MCP bridge index earlier messages and ask for their own replies through their own tools.

OpenClaw runs ``membrain plugin tool consolidate``, a new process per call, so the batch's ``reviewed_through``
number travels with the cues. AstrBot's ``ChatMemory`` lives as long as the bot and remembers the batch it handed
out, as the MCP tool does. In both, the session notice asks for consolidation once five messages wait.
"""
import argparse
import asyncio
import io
import json
import types

import pytest
from test_chatbot_adapter import Event, _load_astrbot_plugin

from membrain import desktop, embedded_database, host, plugin, plugin_cli
from membrain.adapters.chatbot import ChatMemory, Speaker

POTTERY = "I signed up for a pottery class on Thursdays."
SISTER = "My sister Ana moved to Porto."
EARLIER = (POTTERY, "Thanks, that helps a lot!", SISTER, "What is 3 cups in millilitres?", "I am vegetarian.")
ASKED = "We are in Rome next month. Where can we get a good sandwich near the Vatican?"
REPLY = "Try Forno Feliziani on Via Candia: it is a short walk from the Vatican and known for its porchetta rolls."
needs_database = pytest.mark.skipif(not embedded_database.available(),
                                    reason="embedded PostgreSQL binaries are not installed")


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def _tool(directory, capsys, name, arguments):
    assert plugin.run_tool(name, directory, stream=io.BytesIO(json.dumps(arguments).encode())) == 0
    return json.loads(capsys.readouterr().out)


def _openclaw_notice(directory, capsys, session):
    assert plugin.run_hook("session-start", directory, stream=io.BytesIO(json.dumps({"session_id": session}).encode()),
                           host_name="openclaw") == 0
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]


def test_every_plugin_tool_is_accepted_by_the_command_line():
    parser = argparse.ArgumentParser()
    plugin_cli.add_commands(parser.add_subparsers(dest="command"))
    for name in plugin.TOOLS:
        assert parser.parse_args(["plugin", "tool", name]).name == name
    assert plugin.HOST_TOOLS["openclaw"]["consolidate"] == "membrain_consolidate"


def test_the_consolidation_tool_neither_opens_memory_nor_hands_out_a_batch_while_paused(tmp_path, monkeypatch, capsys):
    def unexpected(*args):
        raise AssertionError("A paused consolidation must not open a client")

    monkeypatch.setattr(host, "ready_client", unexpected)
    stranger = "openclaw:telegram::-1:7"
    host.pause(tmp_path, user_id=stranger)  # Someone else's own pause covers their memory.
    assert "paused" in _tool(tmp_path, capsys, "consolidate", {"membrain_user": stranger})["error"]
    host.pause(tmp_path)
    for arguments in ({}, {"cues": [], "reviewed_through": 3}):
        assert "paused" in _tool(tmp_path, capsys, "consolidate", arguments)["error"]


@pytest.mark.parametrize("value, replies", [(True, True), (False, False), ("true", False), (None, False)])
def test_the_search_tool_adds_the_assistant_s_replies_only_when_asked_for(tmp_path, monkeypatch, capsys, value,
                                                                          replies):
    from test_host import Client

    asked = []
    monkeypatch.setattr(host, "ready_client", lambda *args: Client())
    monkeypatch.setattr(host, "recall_context", lambda client, query, **options: asked.append(options) or "found")
    arguments = {"query": "deli near the Vatican"} | ({} if value is None else {"my_replies": value})
    assert _tool(tmp_path, capsys, "search", arguments) == {"context": "found"}
    assert asked[0]["replies"] is replies


class Pending:
    """A memory service double that offers one batch and records what is written back."""

    def __init__(self):
        self.written = []

    def pending_message_cues(self, *, limit, max_characters=6000, whole_conversations=False):
        if limit == 1 or self.written:
            return {"items": [], "through_sequence": None, "remaining": 0}
        return {"items": [{"sequence": 7, "recorded_at": "2026-11-10T09:00:00Z", "text": POTTERY},
                          {"sequence": 9, "recorded_at": "2026-11-10T09:01:00Z", "text": SISTER}],
                "through_sequence": 9, "remaining": 2}

    def write_message_cues(self, items, *, model_version=None, reviewed_through_sequence=None):
        self.written.append((items, reviewed_through_sequence))
        return {"written": len(items), "skipped": 0, "embedded": 0}


def test_a_remembered_batch_is_the_one_answered_and_a_stateless_tool_needs_its_number():
    client, handed_out = Pending(), {}
    batch = host.consolidate(client, handed_out=handed_out)
    assert "reviewed_through" not in batch and handed_out == {"through": 9, "ids": {7, 9}}
    # A wrong number from the AI does not change which batch counts as read.
    saved = host.consolidate(client, [{"id": 7, "cues": ["user hobbies"]}], 3, handed_out=handed_out)
    assert saved["indexed"] == 1 and client.written[-1][1] == 9 and handed_out == {}

    client = Pending()
    batch = host.consolidate(client)
    assert batch["reviewed_through"] == 9 and batch["instructions"].endswith("reviewed_through = 9, exactly as given here.")
    for cues, through in (([{"id": 7, "cues": ["x"]}], None), ([{"id": 7, "cues": ["x"]}], True),
                          ([{"id": 10, "cues": ["x"]}], 9), ("user hobbies", 9), ([{"id": "7", "cues": ["x"]}], 9)):
        assert "error" in host.consolidate(client, cues, through)
    assert client.written == []
    assert host.consolidate(client, None, 9)["indexed"] == 0 and client.written == [([], 9)]


def test_chat_memory_consolidation_respects_unrecorded_groups_and_pauses(tmp_path, monkeypatch):
    def unexpected(*args):
        raise AssertionError("Consolidation must not open this memory")

    monkeypatch.setattr(host, "ready_client", unexpected)
    memory, speaker = ChatMemory(tmp_path, record_groups=False), Speaker("telegram", "42")
    assert "not available" in memory.consolidate(Speaker("telegram", "42", "9"))["error"]
    memory.pause(speaker)
    assert "paused" in memory.consolidate(speaker)["error"]


@needs_database
def test_openclaw_indexes_earlier_messages_through_the_tool_command_with_the_batch_number(tmp_path, capsys):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        assert "not been indexed" not in _openclaw_notice(directory, capsys, "first")
        assert "reviewed_through" in _tool(directory, capsys, "consolidate", {"cues": []})["error"]
        for number, text in enumerate(EARLIER[:2], start=1):
            host.prompt_context(directory, "monday", text, turn_id=str(number), include_source=True)
            host.finish_turn(directory, "monday", "Noted.", turn_id=str(number))
        assert "not been indexed" not in _openclaw_notice(directory, capsys, "monday-evening")  # Below five.
        for number, text in enumerate(EARLIER[2:], start=3):
            host.prompt_context(directory, "monday", text, turn_id=str(number), include_source=True)
            host.finish_turn(directory, "monday", "Noted.", turn_id=str(number))

        opening = _openclaw_notice(directory, capsys, "tuesday")
        assert "5 earlier messages have not been indexed by memory yet." in opening
        assert "membrain_consolidate" in opening and "memory_consolidate" not in opening

        batch = _tool(directory, capsys, "consolidate", {})
        assert [message["text"] for message in batch["messages"]] == list(EARLIER)
        through = batch["reviewed_through"]
        assert through == batch["messages"][-1]["id"] and f"reviewed_through = {through}" in batch["instructions"]
        first, sister = batch["messages"][0]["id"], batch["messages"][2]["id"]
        for wrong in ({"cues": [{"id": first, "cues": ["x"]}]}, {"cues": [{"id": through + 1, "cues": ["x"]}],
                                                                  "reviewed_through": through},
                      {"cues": [{"id": first}], "reviewed_through": through}):
            assert "error" in _tool(directory, capsys, "consolidate", wrong)
        assert _tool(directory, capsys, "consolidate", {})["reviewed_through"] == through  # Nothing was marked read.
        # Someone else OpenClaw talks to has a memory of their own, with nothing waiting in it.
        assert _tool(directory, capsys, "consolidate", {"membrain_user": "openclaw:telegram::-1:7"})["messages"] == []

        saved = _tool(directory, capsys, "consolidate", {"reviewed_through": through, "cues": [
            {"id": first, "cues": ["user hobbies and activities"]},
            {"id": sister, "cues": ["user's sister where she lives", "user family members"]}]})
        assert (saved["indexed"], saved["skipped"], saved["remaining"]) == (2, 0, 0) and "few words" in saved["note"]
        assert _tool(directory, capsys, "consolidate", {})["messages"] == []
        assert "not been indexed" not in _openclaw_notice(directory, capsys, "wednesday")
        with host.ready_client(directory) as client:
            found = host.recall_records(client, host.recall(client, "What are my hobbies?"))
        assert any(record["text"] == POTTERY for record in found["records"])

        host.prompt_context(directory, "rome", ASKED, turn_id="rome", include_source=True)
        host.finish_turn(directory, "rome", REPLY, turn_id="rome")
        assert "Forno Feliziani" not in _tool(directory, capsys, "search", {"query": "deli near the Vatican"})["context"]
        assert "Forno Feliziani" in _tool(directory, capsys, "search", {"query": "deli near the Vatican",
                                                                       "my_replies": True})["context"]
        assert "my_replies" in host._session_notice(False, plugin.HOST_TOOLS["openclaw"], False, None)

        host.pause(directory)
        assert "paused" in _tool(directory, capsys, "consolidate", {})["error"]
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


@needs_database
def test_astrbot_indexes_each_person_s_earlier_messages_and_remembers_the_batch(tmp_path, monkeypatch):
    module, handlers = _load_astrbot_plugin(monkeypatch, tmp_path)
    assert {"membrain_consolidate", "membrain_search"} <= set(handlers)
    directory = tmp_path / "plugin_data" / "membrain"
    try:
        bot = module.MembrainPlugin(context=None, config={})
        host.start(directory)

        async def turn(event, reply, conversation="c1"):
            request = types.SimpleNamespace(system_prompt="You are a friendly bot.", prompt=event.text,
                                            conversation=types.SimpleNamespace(cid=conversation))
            await bot.add_memory(event, request)
            await bot.store_turn(event, types.SimpleNamespace(role="assistant", completion_text=reply))
            return request.system_prompt

        async def scenario():
            for number, text in enumerate(EARLIER):
                await turn(Event("1001", text, message_id=f"m{number}"), "Noted.")
            await turn(Event("2002", ASKED, message_id="b1"), REPLY)
            asking = Event("1001", "Hello again", message_id="m9")
            prompt = await turn(asking, "Hi!", conversation="c2")
            other = await turn(Event("2002", "Hello", message_id="b2"), "Hi!", conversation="c3")
            fresh = json.loads(await bot.membrain_consolidate(Event("1001", ""), cues=[]))
            batch = json.loads(await bot.membrain_consolidate(asking))
            sister = next(message["id"] for message in batch["messages"] if message["text"] == SISTER)
            saved = json.loads(await bot.membrain_consolidate(asking, cues=[{"id": sister, "cues": ["user family"]}]))
            searched = [json.loads(await bot.membrain_search(Event("2002", ""), "deli near the Vatican", my_replies=value))
                        for value in (False, True)]
            return prompt, other, fresh, batch, saved, searched

        prompt, other, fresh, batch, saved, searched = asyncio.run(scenario())
        assert "membrain_consolidate" in prompt and "earlier messages have not been indexed" in prompt
        assert "not been indexed" not in other  # Bob's own memory has only two messages.
        assert "error" in fresh  # A conversation that was handed no batch has none to answer.
        assert [message["text"] for message in batch["messages"]][:5] == list(EARLIER)
        assert "reviewed_through" not in batch and ASKED not in json.dumps(batch)
        assert saved["indexed"] == 1
        assert "Forno Feliziani" not in searched[0]["context"] and "Forno Feliziani" in searched[1]["context"]
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
