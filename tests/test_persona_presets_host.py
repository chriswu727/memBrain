"""Personality types through the hosts: the first session's random type and its one-time intro, the persona tool on
every host (MCP ``memory_persona``, OpenClaw and AstrBot ``membrain_persona``, ``membrain plugin tool persona``), the
Claude Code ``/membrain:persona`` command, and a change the host AI proposes and the user confirms in conversation."""
import asyncio
import inspect
import io
import json
import re
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, host, persona_tool, plugin, plugin_cli
from membrain.adapters.chatbot import ChatMemory
from membrain.mcp_server import create_server
from membrain.persona_presets import IDS

ROOT = Path(__file__).parents[1]
OPENCLAW = ROOT / "integrations/openclaw/membrain"
PLUGIN = ROOT / "plugins/membrain"
INTRO = "A personality type was picked at random"


# Without a database ---------------------------------------------------------------------------------------------

def test_every_host_offers_the_persona_tool_with_the_same_text():
    assert "persona" in plugin.TOOLS and plugin.HOST_TOOLS["openclaw"]["persona"] == "membrain_persona"
    assert host.TOOL_NAMES["persona"] == "memory_persona"
    assert plugin.HOST_TOOLS["claude-code"]["persona_command"] == "/membrain:persona"
    assert "persona_command" not in host.TOOL_NAMES  # Codex and WorkBuddy have no slash command format here.
    import argparse

    parser = argparse.ArgumentParser()
    plugin_cli.add_commands(parser.add_subparsers(dest="command"))
    assert parser.parse_args(["plugin", "tool", "persona"]).name == "persona"
    script = (OPENCLAW / "index.js").read_text(encoding="utf-8")
    declared = script[script.index('name: "membrain_persona"'):]
    description = declared[declared.index("description:"):declared.index("parameters:")]
    assert "".join(re.findall(r'"([^"]*)"', description)) == persona_tool.TOOL_DESCRIPTION  # Written out in JS.
    actions = re.search(r"action: \{ type: \"string\", enum: \[([^\]]*)\]", declared).group(1)
    assert tuple(re.findall(r'"(\w+)"', actions)) == persona_tool.ACTIONS
    manifest = json.loads((OPENCLAW / "openclaw.plugin.json").read_text(encoding="utf-8"))
    assert "membrain_persona" in manifest["contracts"]["tools"]
    assert manifest["toolMetadata"]["membrain_persona"] == {"sideEffecting": True}
    description = persona_tool.TOOL_DESCRIPTION
    for rule in ("only when the user asked in this conversation to switch", "Never propose a change on your own taste",
                 "Nothing changes until the user says yes", "manner-feedback tool", "never invent a source",
                 "never resets the mood or familiarity", "sixteen personality types",
                 "reset their persona, that means switch with random, or with the type they name"):
        assert rule in description, rule


def test_astrbot_registers_the_persona_tool_with_the_runtimes_text(monkeypatch, tmp_path):
    from test_chatbot_adapter import _load_astrbot_plugin

    _, handlers = _load_astrbot_plugin(monkeypatch, tmp_path)
    doc = inspect.getdoc(handlers["membrain_persona"])
    assert doc.startswith(persona_tool.TOOL_DESCRIPTION) and all(action in doc for action in persona_tool.ACTIONS)


def test_the_slash_command_the_manifest_and_the_skill_describe_switching():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["commands"] == ["./commands/"]
    for folder in (".codex-plugin", ".codebuddy-plugin"):  # Only Claude Code's plugin format has commands here.
        assert "commands" not in json.loads((PLUGIN / folder / "plugin.json").read_text(encoding="utf-8"))
    command = (PLUGIN / "commands" / "persona.md").read_text(encoding="utf-8")
    assert command.startswith("---\ndescription: ") and "$ARGUMENTS" in command
    front = command.split("---", 2)[1]
    assert "argument-hint:" in front and all(ident in front for ident in IDS) and "random" in front
    assert "reset [<type>]" in front and "`reset` alone" in command and "`reset` followed by a type" in command
    assert "any case" in command  # Types are read in any case.
    assert "mcp__plugin_membrain_membrain__memory_persona" in front and "Bash(membrain plugin tool persona)" in front
    assert '"switch"' in command and '"list"' in command and "do not ask again" in command
    assert "membrain plugin tool persona" in command and "one or two plain sentences" in command
    skill = (PLUGIN / "skills" / "membrain" / "SKILL.md").read_text(encoding="utf-8")
    section = skill[skill.index("## Persona and mood"):]
    for text in ("memory_persona", "/membrain:persona", "memory_manner_feedback", "clear yes", "own taste"):
        assert text in section, text


class Unused:
    """A client the refused calls must never reach."""
    brain_id = "brain"

    def __getattr__(self, name):
        raise AssertionError(f"nothing may be sent: {name}")


def test_writing_actions_are_refused_while_paused_and_listing_still_works(tmp_path, capsys):
    server = create_server(Unused(), directory=tmp_path)
    assert "memory_persona" in {tool.name for tool in asyncio.run(server.list_tools())}
    assert "memory_persona" not in {tool.name for tool in asyncio.run(create_server(Unused()).list_tools())}
    host.ensure_installation(tmp_path)
    reference = [{"producer_ref": "membrain-claude-code", "source_event_key": "t", "source_revision": 1}]
    assert "Cite the user's message" in persona_tool.run(tmp_path, Unused(), "switch", preset="intj")["error"]
    assert "Cite the user's message" in persona_tool.run(tmp_path, Unused(), "confirm", proposal_id="p")["error"]
    assert "action must be one of" in persona_tool.run(tmp_path, Unused(), "delete")["error"]
    host.pause(tmp_path)
    for arguments in ({"action": "switch", "preset": "intj", "source_messages": reference},
                      {"action": "propose", "changes": {"traits": ["calm"]}, "reason": "Asked."},
                      {"action": "confirm", "proposal_id": "p", "source_messages": reference},
                      {"action": "decline", "proposal_id": "p"}):
        _, result = asyncio.run(server.call_tool("memory_persona", arguments))
        assert "paused" in result["error"] and "Nothing was saved" in result["error"], arguments

    class Listing(Unused):
        def persona_presets(self):
            return {"presets": [], "current": {"kind": "none"}}

    assert persona_tool.run(tmp_path, Listing(), "list")["current"] == {"kind": "none"}


class Recorded:
    """A client that keeps what a host passes on."""
    brain_id = "brain"

    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def switch_persona_preset(self, preset, **sources):
        self.calls.append(("switch", preset, sources))
        return {"version": 2, "unchanged": False, "choice": {"kind": "preset", "preset": {"id": preset}}}

    def propose_persona_change(self, changes, *, reason, **sources):
        self.calls.append(("propose", changes, reason, sources))
        return {"proposal": {"id": "p1", "changes": [{"field": "traits", "before": [], "after": ["calm"]}]}}

    def confirm_persona_change(self, proposal_id, **sources):
        self.calls.append(("confirm", proposal_id, sources))
        return {"status": "waiting_for_message", "persona": None}

    def decline_persona_change(self, proposal_id):
        self.calls.append(("decline", proposal_id))
        return {}


def test_openclaw_and_astrbot_pass_the_actions_and_sources_and_send_nothing_while_paused(tmp_path, monkeypatch,
                                                                                         capsys):
    from test_chatbot_adapter import Event, _load_astrbot_plugin

    client, users = Recorded(), []
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: users.append(user_id) or client)
    reference = [{"producer_ref": "membrain-openclaw", "source_event_key": "turn-1", "source_revision": 1}]
    stranger = "openclaw:telegram::-1:7"

    def openclaw(arguments):  # OpenClaw's membrain_persona runs `membrain plugin tool persona`.
        assert plugin.run_tool("persona", tmp_path, stream=io.BytesIO(json.dumps(arguments).encode())) == 0
        return json.loads(capsys.readouterr().out)

    module, _ = _load_astrbot_plugin(monkeypatch, tmp_path)
    bot = module.MembrainPlugin.__new__(module.MembrainPlugin)
    bot.memory = ChatMemory(tmp_path)
    event = Event("1001", "Be an INTJ.")
    person = bot.memory.user_id(module._speaker(event))

    def astrbot(action, **arguments):
        return json.loads(asyncio.run(bot.membrain_persona(event, action, **arguments)))

    switched = openclaw({"action": "switch", "preset": "intj", "source_messages": reference,
                         "membrain_user": stranger})
    assert switched["current"]["preset"]["id"] == "intj" and "carried over" in switched["note"]
    proposed = astrbot("propose", changes={"traits": ["calm"]}, reason="Asked twice.", source_event_ids=["evt-1"])
    assert proposed["proposal_id"] == "p1" and "ask" in proposed["note"]
    assert astrbot("confirm", proposal_id="p1", source_messages=reference)["status"] == "waiting_for_message"
    assert "Do not propose the same change again" in openclaw({"action": "decline", "proposal_id": "p1"})["note"]
    assert client.calls == [
        ("switch", "intj", {"source_event_ids": [], "source_messages": reference}),
        ("propose", {"traits": ["calm"]}, "Asked twice.", {"source_event_ids": ["evt-1"], "source_messages": []}),
        ("confirm", "p1", {"source_event_ids": [], "source_messages": reference}),
        ("decline", "p1")]
    assert users == [stranger, person, person, None]  # Each in the memory of the person who asked.
    assert "role-play" in ChatMemory(tmp_path, roleplay="Ada").persona(module._speaker(event), "list")["error"]
    host.pause(tmp_path, user_id=stranger)
    host.pause(tmp_path, user_id=person)
    assert "paused" in openclaw({"action": "switch", "preset": "enfj", "source_messages": reference,
                                 "membrain_user": stranger})["error"]
    assert "paused" in astrbot("switch", preset="enfj", source_messages=reference)["error"]
    assert len(client.calls) == 4 and len(users) == 4  # Refused before a client is opened.


def test_the_intro_names_the_command_only_where_the_host_has_it():
    preset = {"id": "intj", "label": "INTJ", "summary": "Thinks ahead."}
    claude = host._intro(preset, plugin.HOST_TOOLS["claude-code"])
    assert claude.startswith(INTRO) and "companion: INTJ (Thinks ahead.)" in claude and "/membrain:persona" in claude
    for tools in (host.TOOL_NAMES, plugin.HOST_TOOLS["openclaw"], None):
        text = host._intro(preset, tools)
        assert "/membrain:persona" not in text and "ask you to switch" in text
    assert "once" in claude and "do not repeat it" in claude and host._intro(None, host.TOOL_NAMES) == ""


# On a real service ---------------------------------------------------------------------------------------------

def source(context):
    found = re.search(r"pass source_messages=(\[.*?\])\. This reference", context or "")
    assert found, context
    return json.loads(found.group(1))


@pytest.fixture(scope="module")
def directory(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("presets") / "brain"
    try:
        host.start(directory)
        yield directory
    finally:
        desktop.stop(directory)


def test_the_first_session_gets_a_random_persona_and_mentions_it_once(directory):
    user = "presets-first"
    tools = plugin.HOST_TOOLS["claude-code"]
    opening = host.session_context(directory, "s1", tools=tools, user_id=user)
    assert opening.count(INTRO) == 1 and "/membrain:persona" in opening
    assert opening.count("<membrain-persona version=\"1\">") == 1
    with host.ready_client(directory, user) as client:
        current = client.persona_presets()["current"]
        versions = client.persona_versions()["versions"]
    assert current["kind"] == "preset" and current["preset"]["label"] in opening
    assert [(v["version"], v["made_by"], v["action"], v["host_default"]) for v in versions] == [
        (1, "host", "preset", False)]
    # A context rebuilt before the first prompt (a resumed session) still has it.
    rebuilt = host.session_context(directory, "s1", tools=tools, user_id=user)
    assert rebuilt.count(INTRO) == 1
    turn = host.prompt_context(directory, "s1", "Hello!", turn_id="t1", user_id=user, tools=tools) or ""
    assert INTRO not in turn and "<membrain-updates>" not in turn  # No resend: the intro is not in the snapshot.
    host.finish_turn(directory, "s1", "Hi! I picked a persona for myself.", turn_id="t1", user_id=user)
    later = host.prompt_context(directory, "s1", "How are you?", turn_id="t2", user_id=user, tools=tools) or ""
    assert INTRO not in later and "<membrain-updates>" not in later
    assert INTRO not in host.session_context(directory, "s1", tools=tools, user_id=user)  # After the first prompt.
    assert INTRO not in host.session_context(directory, "s2", tools=tools, user_id=user)  # Nor in a later session.
    with host.ready_client(directory, user) as client:
        assert len(client.persona_versions()["versions"]) == 1


def test_a_session_whose_start_missed_the_service_gets_it_with_the_first_prompt(directory):
    # A new installation's first session usually starts before the service is up: the first prompt's context is
    # the session's first memory context, and it brings the persona and the intro.
    user = "presets-late"
    turn = host.prompt_context(directory, "late", "Hi, first time here.", turn_id="t1", user_id=user) or ""
    assert turn.count(INTRO) == 1 and "ask you to switch" in turn and "<membrain-persona version=\"1\">" in turn
    host.finish_turn(directory, "late", "Welcome!", turn_id="t1", user_id=user)
    again = host.prompt_context(directory, "late", "Next.", turn_id="t2", user_id=user) or ""
    assert INTRO not in again


def test_no_persona_in_a_role_play_or_while_paused_and_a_failure_never_blocks_the_session(directory, monkeypatch):
    roleplay = host.session_context(directory, "story", user_id="presets-story", roleplay="Captain Ada")
    assert INTRO not in roleplay and "<membrain-persona" not in roleplay
    with host.ready_client(directory, host.roleplay_user("presets-story", "Captain Ada")) as client:
        assert client.persona()["version"] == 0
    host.pause(directory, user_id="presets-paused")
    try:
        paused = host.session_context(directory, "quiet", user_id="presets-paused")
        assert INTRO not in paused and "<membrain-persona" not in paused
    finally:
        host.resume(directory, user_id="presets-paused")
    from membrain.client import MemoryClient

    def broken(self):
        raise RuntimeError("service hiccup")

    monkeypatch.setattr(MemoryClient, "assign_first_persona", broken)
    context = host.session_context(directory, "hiccup", user_id="presets-hiccup")
    assert "memBrain memory is active" in context and INTRO not in context
    monkeypatch.undo()
    assert INTRO in host.session_context(directory, "hiccup-2", user_id="presets-hiccup")  # The next session.


def test_a_chat_bot_mentions_the_persona_in_the_first_reply_of_the_day_only(directory):
    from membrain.adapters.chatbot import Speaker

    memory = ChatMemory(directory)
    speaker = Speaker("telegram", "presets-bot")
    session = memory.session(speaker)
    first = memory.context(speaker, "hello", session=session, turn_id="1") or ""
    assert first.count(INTRO) == 1
    memory.record(speaker, "Hi!", session=session, turn_id="1")
    assert INTRO not in (memory.context(speaker, "again", session=session, turn_id="2") or "")


def test_a_host_ai_switches_and_proposes_a_change_the_user_confirms_in_the_next_turn(directory):
    user = None  # The installation's own memory, as Claude Code uses it.

    def call(server, arguments):
        _, result = asyncio.run(server.call_tool("memory_persona", arguments))
        return result

    with host.ready_client(directory, user) as client:
        server = create_server(client, directory=directory)
        host.session_context(directory, "h1", tools=plugin.HOST_TOOLS["claude-code"])
        start = client.persona_presets()["current"]["preset"]["id"]
        listed = call(server, {"action": "list"})
        assert [item["id"] for item in listed["presets"]] == list(IDS) and listed["current"]["preset"]["id"] == start

        # Turn 1: the user asks to switch; the AI switches at once, citing the turn's message.
        context = host.prompt_context(directory, "h1", "Can you switch to a different persona?", turn_id="1",
                                      include_source=True)
        capture = json.loads(re.search(r'recording_capture=("[^"]+")', context).group(1))
        target = next(ident for ident in IDS if ident != start)
        switched = call(server, {"action": "switch", "preset": target, "source_messages": source(context),
                                 "recording_capture": capture})
        assert switched["current"]["preset"]["id"] == target and switched["version"] == 2
        host.finish_turn(directory, "h1", "Done, I switched.", turn_id="1")

        # Turn 2: the user asks for something lasting; the AI proposes and cannot confirm in the same turn.
        context = host.prompt_context(directory, "h1", "From now on, keep replies to one sentence.", turn_id="2",
                                      include_source=True)
        proposal = call(server, {"action": "propose", "changes": {"voice": {"length": "one sentence"}},
                                 "reason": "The user asked for one-sentence replies from now on.",
                                 "source_messages": source(context)})
        assert proposal["proposal_id"] and "ask" in proposal["note"]
        early = call(server, {"action": "confirm", "proposal_id": proposal["proposal_id"],
                              "source_messages": source(context)})
        assert early["code"] == "source_unavailable" and "has not answered" in early["error"]
        host.finish_turn(directory, "h1", "Shall I make one-sentence replies part of my persona?", turn_id="2")

        # Turn 3: the user says yes; the AI confirms citing this turn's message, recorded only when the turn ends.
        context = host.prompt_context(directory, "h1", "Yes, do it.", turn_id="3", include_source=True)
        confirmed = call(server, {"action": "confirm", "proposal_id": proposal["proposal_id"],
                                  "source_messages": source(context)})
        assert confirmed["status"] == "waiting_for_message" and "next message" in confirmed["note"]
        assert client.persona()["version"] == 2
        host.finish_turn(directory, "h1", "Done.", turn_id="3")
        saved = client.persona()
        assert (saved["version"], saved["action"], saved["based_on"]) == (3, "proposal", target)
        assert saved["card"]["voice"]["length"] == "one sentence" and saved["host_proposal"]["confirmed_by"]
        turn = host.prompt_context(directory, "h1", "Thanks.", turn_id="4") or ""
        assert '<membrain-persona version="3">' in turn and "one sentence" in turn
