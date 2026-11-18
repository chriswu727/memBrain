"""Removing or replacing an entry of the persona card by asking the agent (owner's line, 2026-11-18: the memory page
has no card editor, so the user only talks).

``memory_persona`` ``propose`` takes ``changes.remove``, entries of the card's traits, values or boundaries to take
off, beside any additions, so "replace X with Y" is one proposal. The confirmation rule is the one for every proposal:
the user's yes in a later message of the conversation, or Accept on the page. A removal changes the current card
only: it is never recorded as agreed, an agreement in force loses what it removes, and a later switch of type starts
from that type's own card plus what the user agreed.

Every test drives a host's own entry points on a real service: the MCP tool with Claude Code's hooks, OpenClaw's
tool command (``membrain plugin tool persona``) with the plugin hooks, a chat bot's ``ChatMemory.persona``, and the
routes the memory page uses."""
import asyncio
import io
import json
import re
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, host, persona_presets, persona_tool, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.helpers import uid
from membrain.mcp_server import create_server

REMOVES_NOTE = "This changes the current card only: switching type later starts from that type's own card"
ROOT = Path(__file__).parents[1]


# Without a database ---------------------------------------------------------------------------------------------

def test_every_host_with_the_persona_tool_is_told_how_to_remove_and_replace():
    description = persona_tool.TOOL_DESCRIPTION
    for rule in ("remove, an object of those lists, takes card entries off as worded there",
                 "(replace = remove + add, one proposal)", "(an empty string or null clears)",
                 "or to drop or change something on the card"):
        assert rule in description, rule
    # The parameter text OpenClaw and AstrBot show beside it (their descriptions are this text, checked in
    # test_persona_presets_host.py and test_chatbot_adapter.py).
    parameter = "and remove: the traits, values or boundaries entries to take off."
    assert parameter in (ROOT / "integrations/openclaw/membrain/index.js").read_text(encoding="utf-8")
    assert parameter in (ROOT / "integrations/astrbot/astrbot_plugin_membrain/main.py").read_text(encoding="utf-8")
    skill = (ROOT / "plugins/membrain/skills/membrain/SKILL.md").read_text(encoding="utf-8")
    section = skill[skill.index("## Persona and mood"):skill.index("## Searching on purpose")]
    for text in ("name the entries to drop in `remove`", "so a replacement is one proposal",
                 "A removal changes the current card only", "until they ask you to remove or change it"):
        assert text in section, text
    assert "until they change it themselves" not in skill


@pytest.fixture(scope="module")
def directory(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("removal") / "brain"
    try:
        host.start(directory)
        yield directory
    finally:
        desktop.stop(directory)


def source(context):
    found = re.search(r"pass source_messages=(\[.*?\])\. This reference", context or "")
    assert found, context
    return json.loads(found.group(1))


def persona_block(context):
    found = re.search(r'<membrain-persona version="(\d+)">.*?</membrain-persona>', context or "", re.S)
    assert found, context
    return int(found.group(1)), found.group(0)


def traits_line(block):
    return next(line for line in block.splitlines() if line.startswith("Traits: "))


# Claude Code over MCP --------------------------------------------------------------------------------------------

def test_the_user_asks_to_drop_a_trait_and_the_next_session_shows_the_card_without_it(directory):
    """The walk-through: the user asks, the agent proposes the removal and asks, the yes comes in the next message,
    the card no longer holds the trait and the next session's persona block shows the new card."""
    tools = plugin.HOST_TOOLS["claude-code"]

    with host.ready_client(directory, None) as client:
        server = create_server(client, directory=directory)

        def call(arguments):
            _, result = asyncio.run(server.call_tool("memory_persona", arguments))
            return result

        opening = host.session_context(directory, "drop-1", tools=tools)  # The first session picks a type.
        before = client.persona()
        trait = before["card"]["traits"][0]
        assert trait in traits_line(persona_block(opening)[1])

        # Turn 1: the user asks to drop it; the agent proposes the removal, worded loosely, and asks.
        context = host.prompt_context(directory, "drop-1", f"Please stop being so {trait}, drop that from your "
                                      "persona.", turn_id="1", include_source=True)
        proposal = call({"action": "propose", "changes": {"remove": {"traits": [f"  {trait.upper()} "]}},
                         "reason": f"The user asked to drop '{trait}'.", "source_messages": source(context)})
        assert proposal["summary"] == [f'Remove from traits: "{trait}".'], proposal
        assert "Say what it removes" in proposal["note"] and REMOVES_NOTE in proposal["note"]
        assert client.persona()["version"] == before["version"]  # Nothing changed yet.
        host.finish_turn(directory, "drop-1", f"Shall I take '{trait}' off my persona? This changes the current "
                         "card only.", turn_id="1")

        # Turn 2: the yes; the confirmation waits for this message and is saved when the turn is recorded.
        context = host.prompt_context(directory, "drop-1", "Yes, please.", turn_id="2", include_source=True)
        confirmed = call({"action": "confirm", "proposal_id": proposal["proposal_id"],
                          "source_messages": source(context)})
        assert confirmed["status"] == "waiting_for_message", confirmed
        host.finish_turn(directory, "drop-1", "Done.", turn_id="2")
        saved = client.persona()
        assert saved["version"] == before["version"] + 1 and saved["action"] == "proposal"
        assert trait not in saved["card"]["traits"]
        assert saved["card"]["traits"] == [item for item in before["card"]["traits"] if item != trait]
        assert {key: saved["card"][key] for key in ("voice", "values", "boundaries", "baseline_mood")} == {
            key: before["card"][key] for key in ("voice", "values", "boundaries", "baseline_mood")}
        assert saved["agreed_changes"] == {} and saved["host_proposal"]["confirmed_by"]
        assert saved["reason"] == f"The user asked to drop '{trait}'."
        assert client.persona_versions()["agreements"] == []

    # The next session's persona block shows the new card.
    later = host.session_context(directory, "drop-2", tools=tools)
    version, block = persona_block(later)
    assert version == saved["version"] and trait not in traits_line(block)


# OpenClaw's tool command -----------------------------------------------------------------------------------------

def openclaw(directory, capsys, user, arguments):
    """OpenClaw's membrain_persona: `membrain plugin tool persona` with the turn's memory owner."""
    capsys.readouterr()
    assert plugin.run_tool("persona", directory, stream=io.BytesIO(
        json.dumps({**arguments, "membrain_user": user}).encode())) == 0
    return json.loads(capsys.readouterr().out)


def hooks(directory, user, session):
    producer = plugin.PRODUCERS["openclaw"]

    def prompt(text, turn):
        return plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": turn, "membrain_user": user},
                                  directory, producer)

    def reply(text, turn):
        plugin.stop({"session_id": session, "last_assistant_message": text, "prompt_id": turn,
                     "membrain_user": user}, directory, producer)

    plugin.session_start({"session_id": session, "membrain_user": user}, directory, producer)
    return prompt, reply


def test_a_replacement_is_one_proposal_through_openclaws_tool_command(directory, capsys):
    user = "openclaw:telegram::-1:removal-" + uid()
    prompt, reply = hooks(directory, user, "oc-" + uid())
    context = prompt("Switch to INTJ, please.", "1")
    assert openclaw(directory, capsys, user, {"action": "switch", "preset": "intj",
                                              "source_messages": source(context)})["current"]["preset"]["id"] == "intj"
    reply("Done: INTJ.", "1")

    context = prompt("From now on be gentle instead of reserved.", "2")
    proposal = openclaw(directory, capsys, user, {
        "action": "propose", "changes": {"traits": ["gentle"], "remove": {"traits": ["reserved"]}},
        "reason": "The user asked to be gentle instead of reserved.", "source_messages": source(context)})
    assert proposal["summary"] == ['Remove from traits: "reserved".', 'Add to traits: "gentle".'], proposal
    assert REMOVES_NOTE in proposal["note"]
    assert proposal["changes"] == [{"field": "traits", "before": persona_presets.card("intj")["traits"],
                                    "after": ["imaginative", "logical", "organised", "gentle"]}]
    reply("Shall I replace 'reserved' with 'gentle'?", "2")

    context = prompt("Yes, do that.", "3")
    assert openclaw(directory, capsys, user, {"action": "confirm", "proposal_id": proposal["proposal_id"],
                                              "source_messages": source(context)})["status"] == "waiting_for_message"
    reply("Done.", "3")
    with host.ready_client(directory, user) as client:
        saved = client.persona()
        assert saved["card"]["traits"] == ["imaginative", "logical", "organised", "gentle"]
        assert saved["agreed_changes"] == {"traits": ["gentle"]}  # Only what it adds is agreed.
        assert [item["changes"] for item in client.persona_versions()["agreements"]] == [{"traits": ["gentle"]}]

    # A switch keeps what was agreed and starts from the new type's own card: ENFP has no "reserved", ISTJ does.
    context = prompt("Now try ENFP.", "4")
    switched = openclaw(directory, capsys, user, {"action": "switch", "preset": "enfp",
                                                  "source_messages": source(context)})
    reply("Switched.", "4")
    with host.ready_client(directory, user) as client:
        plain = persona_presets.card("enfp")
        assert switched["version"] and client.persona()["card"]["traits"] == [*plain["traits"], "gentle"]
        assert client.switch_persona_preset("istj")["card"]["traits"] == [
            *persona_presets.card("istj")["traits"], "gentle"]  # The page's switch: ISTJ's own "reserved" is back.


def test_a_removal_the_card_does_not_hold_is_refused_with_its_entries_listed(directory, capsys):
    user = "openclaw:telegram::-1:refused-" + uid()
    with host.ready_client(directory, user) as client:
        client.switch_persona_preset("intj")
        listed_before = client.persona_proposals()["proposals"]
    refused = openclaw(directory, capsys, user, {
        "action": "propose", "changes": {"traits": ["gentle"], "remove": {"traits": ["sarcastic"]}},
        "reason": "The user asked to stop being sarcastic."})
    assert refused["code"] == "validation_failed", refused
    assert refused["error"] == ('The card\'s traits have no entry "sarcastic" to remove. Its traits are: "reserved"; '
                                '"imaginative"; "logical"; "organised". Ask the user which they mean, or remove one '
                                'of these as written. Nothing was saved.')
    empty = openclaw(directory, capsys, user, {"action": "propose", "changes": {"remove": {"boundaries": ["x"]}},
                                               "reason": "Asked."})
    assert "The card has no boundaries" in empty["error"] and "Nothing was saved" in empty["error"]
    shape = openclaw(directory, capsys, user, {"action": "propose", "changes": {"remove": {"voice": ["emoji"]}},
                                               "reason": "Asked."})
    assert "changes.remove names entries to remove from traits, values or boundaries" in shape["error"]
    with host.ready_client(directory, user) as client:
        assert client.persona()["version"] == 1 and client.persona_proposals()["proposals"] == listed_before


# A chat bot's persona method ------------------------------------------------------------------------------------

def test_removing_an_agreed_entry_ends_that_agreement_and_a_later_switch_does_not_bring_it_back(directory):
    memory = ChatMemory(directory)
    speaker = Speaker("telegram", "removal-agreed-" + uid())
    session = memory.session(speaker)
    user = memory.user_id(speaker)

    def turn(text, number, reply, action=None, **arguments):
        context = memory.context(speaker, text, session=session, turn_id=str(number))
        result = memory.persona(speaker, action, source_messages=source(context), **arguments) if action else None
        memory.record(speaker, reply, session=session, turn_id=str(number))
        return result

    turn("Hello.", 1, "Hi!")  # The first context picks a random type.
    with host.ready_client(directory, user) as client:
        client.switch_persona_preset("intj")  # The page's switch, to a known card.
    proposal = turn("From now on, be patient with me.", 2, "Shall I add 'patient'?", "propose",
                    changes={"traits": ["patient"]}, reason="The user asked for patience from now on.")
    assert proposal["summary"] == ['Add to traits: "patient".'] and REMOVES_NOTE not in proposal["note"]
    assert turn("Yes.", 3, "Done.", "confirm", proposal_id=proposal["proposal_id"])["status"] == "waiting_for_message"
    with host.ready_client(directory, user) as client:
        assert [item["changes"] for item in client.persona_versions()["agreements"]] == [{"traits": ["patient"]}]
        switched = client.switch_persona_preset("enfp")
        assert switched["card"]["traits"] == [*persona_presets.card("enfp")["traits"], "patient"]  # Carried over.

    removal = turn("Actually, drop 'patient' from your persona again.", 4, "Shall I take 'patient' off?",
                   "propose", changes={"remove": {"traits": ["Patient"]}},
                   reason="The user asked to drop 'patient'.")
    assert removal["summary"] == ['Remove from traits: "patient".'] and REMOVES_NOTE in removal["note"]
    assert turn("Yes, take it off.", 5, "Done.", "confirm", proposal_id=removal["proposal_id"])["status"] == (
        "waiting_for_message")
    with host.ready_client(directory, user) as client:
        saved = client.persona()
        assert saved["card"] == persona_presets.card("enfp") and saved["agreed_changes"] == {}
        listed = client.persona_versions()
        assert listed["agreements"] == []  # The agreement ended with the removal.
        assert [item["changes"] for item in next(version for version in listed["versions"]
                                                 if version["version"] == switched["version"])["agreements"]] == [
            {"traits": ["patient"]}]  # The history still says it was in force before.
        for preset in ("istj", "infp"):  # A later switch does not bring it back.
            assert client.switch_persona_preset(preset)["card"] == persona_presets.card(preset)
        # Restoring the version that had it brings the agreement back, as restoring always does.
        restored = client.restore_persona(switched["version"], made_by="user")
        assert "patient" in restored["card"]["traits"]
        assert [item["changes"] for item in client.persona_versions()["agreements"]] == [{"traits": ["patient"]}]


# The memory page's routes ---------------------------------------------------------------------------------------

def test_a_removal_and_a_cleared_voice_field_accepted_on_the_page_change_only_the_current_card(directory):
    user = "removal-page-" + uid()
    with host.ready_client(directory, user) as client:
        client.switch_persona_preset("intj")
        plain = persona_presets.card("intj")
        proposal = client.propose_persona_change(  # An SDK host's proposal; the page lists it.
            {"values": ["Answers in plain words"], "remove": {"values": ["likes a plan and a CLEAR decision"]},
             "voice": {"emoji": ""}}, reason="The user asked for plain words instead of plans, and no emoji.")["proposal"]
        listed = next(item for item in client.persona_proposals()["proposals"] if item["id"] == proposal["id"])
        assert listed["status"] == "open" and listed["changes"] == [
            {"field": "voice.emoji", "before": "rarely", "after": ""},
            {"field": "values", "before": plain["values"],
             "after": [*plain["values"][:3], "Answers in plain words"]}]
        lines, removes = persona_tool.summary(listed["changes"])
        assert removes and lines == ['Clear voice.emoji (now "rarely").',
                                     'Remove from values: "Likes a plan and a clear decision".',
                                     'Add to values: "Answers in plain words".']
        accepted = client.accept_persona_proposal(proposal["id"])["persona"]  # The page's Accept.
        assert accepted["host_proposal"] == {"proposal_id": proposal["id"], "confirmed_by": None}
        assert accepted["card"]["voice"]["emoji"] == "" and "Likes a plan and a clear decision" not in (
            accepted["card"]["values"])
        assert accepted["agreed_changes"] == {"values": ["Answers in plain words"]}  # Not the clearing.
        assert [item["changes"] for item in client.persona_versions()["agreements"]] == [
            {"values": ["Answers in plain words"]}]
        # Another type keeps its own emoji and values, plus the one value the user agreed to.
        switched = client.switch_persona_preset("enfp")["card"]
        assert switched["voice"]["emoji"] == persona_presets.card("enfp")["voice"]["emoji"]
        assert switched["values"] == [*persona_presets.card("enfp")["values"], "Answers in plain words"]
