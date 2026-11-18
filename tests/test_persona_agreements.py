"""What the user agreed with the agent is memory, so it survives a change of personality type (owner's decision,
2026-11-18: "约定算记忆吧，我感觉需要跨性格保留", translation: "an agreement counts as memory; it must be kept across
personalities").

An agreement is a manner suggestion the user accepted or a "from now on" change the agent proposed and the user
confirmed. It is read from the persona's version history (``persona.agreements_by_version``): nothing new is stored.
Every switch of type and every reset applies the agreements in force on top of the new card, in the order they were
made; only the user ends one (an opposite or replacing change, an edit that removes it, a restore from before it,
deleting the personality history, erasing memory)."""
import asyncio
import hashlib
import io
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_persona_confirmation import confirm, propose
from test_persona_growth import CARD, listing, said
from test_persona_growth import brain as brain
from test_persona_growth import installation as installation

from membrain import host, persona_presets, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.api import create_app
from membrain.helpers import DomainError, uid
from membrain.mcp_server import create_server
from membrain.persona import (
    AGREEMENTS_DO_NOT_FIT,
    EMPTY_CARD,
    _save,
    agreements_by_version,
    base_card,
    current_persona,
    delete_persona_history,
    normalize_card,
    persona_versions,
    render_persona,
    reset_persona,
    restore_persona,
    set_persona,
    with_agreements,
)
from membrain.persona_growth import KINDS, accept_proposal
from membrain.persona_presets import switch_preset

SHORTER = KINDS["shorter"]["value"]["en"]
LONGER = KINDS["longer"]["value"]["en"]
PATIENT = "Is patient when the user is slow to decide"
SHORT_COMMENTS = ("Your replies are too long.", "You're too wordy.", "Please be more concise.")
LONG_COMMENTS = ("Your answers are too brief.", "Be more thorough, please.", "Can you be more detailed?")


def accept(brain, kind, comments):
    service, principal, ident = brain
    for text in comments:
        said(brain, text)
    proposal = next(item for item in listing(brain)["proposals"] if item["kind"] == kind and item["status"] == "open")
    return accept_proposal(service, principal, ident, proposal["id"])["persona"]


def agreed_change(brain, changes, reason="The user asked for this from now on."):
    """A "from now on" change the agent proposes and the user confirms in their next message."""
    asked = said(brain, "From now on, please change how you talk with me.")
    proposal = propose(brain, changes, reason=reason, source_event_ids=[asked])
    said(brain, "Shall I make that part of my persona?", role="assistant")
    yes = said(brain, "Yes, please.")
    result = confirm(brain, proposal["id"], yes)
    assert result["status"] == "confirmed", result
    return result["persona"]


def agree(brain):
    """Version 1: INTJ. Version 2: an accepted "shorter" suggestion. Version 3: a confirmed "be patient" change."""
    service, principal, ident = brain
    persona_presets.assign_first_persona(service, principal, ident, choose=lambda ids: "intj")
    assert accept(brain, "shorter", SHORT_COMMENTS)["version"] == 2
    assert agreed_change(brain, {"traits": ["patient"], "values": [PATIENT]})["version"] == 3
    return current_persona(service, principal, ident)


def agreements(brain):
    service, principal, ident = brain
    return persona_versions(service, principal, ident)["agreements"]


def kept_both(card):
    return card["voice"]["length"] == SHORTER and card["values"][-1] == PATIENT and card["traits"][-1] == "patient"


# Without a database ---------------------------------------------------------------------------------------------

def version(number, card, **fields):
    return {"version": number, "card": {**EMPTY_CARD, **normalize_card(card)}, "made_by": "user", "action": "edit",
            "feedback": None, "host_proposal": None, "restored_from": None, "reason": None,
            "recorded_at": f"2026-11-{number:02d}T10:00:00Z", **fields}


def test_agreements_are_read_from_the_history_and_end_only_when_the_card_loses_them():
    base = persona_presets.card("intj")
    shorter = {**base, "voice": {**base["voice"], "length": SHORTER}}
    both = {**shorter, "values": [*shorter["values"], PATIENT]}
    switched = with_agreements(persona_presets.card("enfp"), [
        {"changes": {"voice": {"length": SHORTER}}}, {"changes": {"values": [PATIENT]}}])
    history = [
        version(1, base, action="preset", preset="intj"),
        version(2, shorter, made_by="feedback", action="feedback",
                feedback={"proposal_id": "p1", "kind": "shorter", "source_event_ids": ["a", "b", "c"]}),
        version(3, both, action="proposal", host_proposal={"proposal_id": "p2", "confirmed_by": "m"},
                agreed_changes={"values": [PATIENT]}),
        version(4, switched, action="preset", preset="enfp"),
        version(5, base, action="restore", restored_from=1, preset="intj"),
        version(6, switched, action="restore", restored_from=4, preset="enfp"),
        version(7, {**switched, "values": switched["values"][:-1]}),  # An edit that removes the value.
    ]
    found = agreements_by_version(history)
    assert found[1] == []
    assert [(item["version"], item["source"], item["kind"], item["changes"]) for item in found[3]] == [
        (2, "feedback", "shorter", {"voice": {"length": SHORTER}}), (3, "proposal", None, {"values": [PATIENT]})]
    assert found[4] == found[3]  # A switch keeps them, in the order they were made.
    assert found[5] == []  # Restoring a version from before them ends them.
    assert found[6] == found[4]  # Restoring a version that had them brings them back.
    assert [item["version"] for item in found[7]] == [2]  # The edit removed the value, so that agreement ended.
    # The page shows the card without them, so nothing carried over looks like part of the type.
    plain = base_card(switched, found[4])
    assert plain["voice"]["length"] == "" and PATIENT not in plain["values"]
    assert plain["traits"] == persona_presets.card("enfp")["traits"]


def test_a_card_that_cannot_hold_the_agreements_is_refused_and_nothing_is_cut():
    full = {**CARD, "traits": [f"trait {number}" for number in range(8)]}
    with pytest.raises(DomainError) as error:
        with_agreements(full, [{"changes": {"traits": ["patient"]}}])
    assert error.value.code == "validation_failed" and error.value.message == AGREEMENTS_DO_NOT_FIT


def test_shorter_and_longer_state_a_limit_a_reader_can_check():
    for kind, words in (("shorter", ("one to three sentences", "detail")), ("longer", ("four or more", "short"))):
        value = KINDS[kind]["value"]
        assert all(word in value["en"] for word in words) and len(value["en"]) <= 60 and len(value["zh"]) <= 60
        assert value["zh"] in ("一到三句话，除非用户要求详细", "至少四句话，除非用户要求简短")
    rendered = render_persona({"version": 2, "card": with_agreements(persona_presets.card("intj"), [
        {"changes": {"voice": {"length": SHORTER}}}])})
    assert f"length {SHORTER}" in rendered


# On a real service -----------------------------------------------------------------------------------------------

def test_every_switch_and_reset_keeps_the_agreements_in_the_order_they_were_made(brain):
    service, principal, ident = brain
    agree(brain)
    made = [(item["version"], item["source"]) for item in agreements(brain)]
    assert made == [(2, "feedback"), (3, "proposal")]

    def check(saved, ident_):
        assert saved["card"] == with_agreements(persona_presets.card(ident_), agreements(brain)), ident_
        assert kept_both(saved["card"]) and saved["preset"] == ident_
        assert SHORTER in saved["block"] and PATIENT in saved["block"]
        assert [(item["version"], item["source"]) for item in agreements(brain)] == made

    asked = said(brain, "Can you switch to ENFP?")
    check(switch_preset(service, principal, ident, "enfp", source_event_ids=[asked]), "enfp")  # The host's tool.
    check(switch_preset(service, principal, ident, "istj"), "istj")  # The memory page.
    check(switch_preset(service, principal, ident, "random", choose=lambda ids: "esfp"), "esfp")
    check(reset_persona(service, principal, ident, made_by="user", choose=lambda ids: "isfj"), "isfj")
    check(reset_persona(service, principal, ident, made_by="user", preset="ENTP"), "entp")
    # Asking for the current type again changes nothing.
    assert switch_preset(service, principal, ident, "entp")["unchanged"] is True
    # The listing shows each carried agreement apart from the type.
    current = persona_versions(service, principal, ident)["versions"][0]
    assert current["base_card"] == {**persona_presets.card("entp"), "voice": {
        **persona_presets.card("entp")["voice"], "length": ""}}
    assert persona_presets.current_choice(current)["kind"] == "preset"


def test_a_reset_to_the_hosts_own_default_card_keeps_them_too(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host", host_default=True)
    accept(brain, "shorter", SHORT_COMMENTS)
    agreed_change(brain, {"values": [PATIENT]})
    switch_preset(service, principal, ident, "enfp")
    saved = reset_persona(service, principal, ident, made_by="user")
    assert (saved["action"], saved["restored_from"]) == ("reset", 1)
    assert saved["card"] == normalize_card({**CARD, "voice": {**CARD["voice"], "length": SHORTER},
                                            "values": [*CARD["values"], PATIENT]})


def test_an_opposite_manner_change_or_a_replacing_change_ends_the_earlier_agreement(brain):
    service, principal, ident = brain
    agree(brain)
    accept(brain, "longer", LONG_COMMENTS)
    assert [(item["source"], item["kind"]) for item in agreements(brain)] == [("proposal", None), ("feedback", "longer")]
    saved = switch_preset(service, principal, ident, "enfp")
    assert saved["card"]["voice"]["length"] == LONGER and saved["card"]["values"][-1] == PATIENT
    # A confirmed change of the same field replaces the accepted one; one that adds keeps the earlier additions.
    agreed_change(brain, {"voice": {"length": "two sentences at most"}, "values": ["Says when it is unsure"]})
    assert [item["kind"] or item["source"] for item in agreements(brain)] == ["proposal", "proposal"]
    saved = switch_preset(service, principal, ident, "istj")
    assert saved["card"]["voice"]["length"] == "two sentences at most"
    assert saved["card"]["values"][-2:] == [PATIENT, "Says when it is unsure"]


def test_restoring_a_version_takes_its_agreements_and_deleting_the_history_ends_them(brain):
    service, principal, ident = brain
    agree(brain)
    switched = switch_preset(service, principal, ident, "enfp")  # Version 4, with both.
    # Restoring the type as it was before any agreement ends both: a later switch gives the plain type.
    assert restore_persona(service, principal, ident, 1, made_by="user")["card"] == persona_presets.card("intj")
    assert agreements(brain) == []
    assert switch_preset(service, principal, ident, "istj")["card"] == persona_presets.card("istj")
    # Restoring a version that had them brings them back, and they carry over again.
    assert restore_persona(service, principal, ident, switched["version"], made_by="user")["card"] == switched["card"]
    assert [item["version"] for item in agreements(brain)] == [2, 3]
    assert kept_both(switch_preset(service, principal, ident, "esfp")["card"])
    # Restoring the version with only the first agreement keeps only that one.
    restore_persona(service, principal, ident, 2, made_by="user")
    assert [item["version"] for item in agreements(brain)] == [2]
    assert switch_preset(service, principal, ident, "infp")["card"]["values"] == persona_presets.card("infp")["values"]
    # Deleting the personality history erases every version, so nothing is carried any more.
    delete_persona_history(service, principal, ident)
    assert current_persona(service, principal, ident)["empty"] and agreements(brain) == []
    assert switch_preset(service, principal, ident, "entj")["card"] == persona_presets.card("entj")


def test_an_edit_on_the_page_keeps_the_agreements_it_still_has(brain):
    service, principal, ident = brain
    card = agree(brain)["card"]
    # An edit that keeps both keeps both; one that removes the confirmed change ends only that one.
    set_persona(service, principal, ident, {**card, "name": "Wren"}, made_by="user")
    assert [item["version"] for item in agreements(brain)] == [2, 3]
    set_persona(service, principal, ident, {**card, "name": "Wren", "values": card["values"][:-1],
                                            "traits": card["traits"][:-1]}, made_by="user")
    assert [item["version"] for item in agreements(brain)] == [2]
    saved = switch_preset(service, principal, ident, "enfp")
    assert saved["card"]["voice"]["length"] == SHORTER and PATIENT not in saved["card"]["values"]


def test_history_from_before_this_change_is_read_the_same_way(brain):
    """Versions are stored as they always were, so an accepted change in an existing user's history is recognised.
    A switch made before this change dropped the agreements from the card; they stay ended, and are not brought
    back by a later switch."""
    service, principal, ident = brain
    agree(brain)
    # A switch as the earlier runtime saved it: the type's card alone.
    _save(service, principal, ident, lambda find: (persona_presets.card("enfp"), {"preset": "enfp"}),
          made_by="user", reason=None, action="preset")
    assert agreements(brain) == []
    assert switch_preset(service, principal, ident, "istj")["card"] == persona_presets.card("istj")


def test_the_page_routes_and_every_host_path_keep_the_agreements(installation, capsys):
    directory, service, settings = installation
    principal = next(iter(settings.principals().values()))

    def ready(user):
        """Agreements in this user's own memory, set up through the SDK as hosts and the page reach them."""
        with host.ready_client(directory, user) as client:
            client.assign_first_persona()
            for text in SHORT_COMMENTS:
                client.observe(text, conversation_id="chat", branch_id="main", source_event_key=uid(),
                               producer_ref="agreements-test")
            proposal = next(item for item in client.persona_proposals()["proposals"] if item["kind"] == "shorter")
            client.accept_persona_proposal(proposal["id"])
            asked = client.observe("From now on, be patient with me.", conversation_id="chat", branch_id="main",
                                   source_event_key=uid(), producer_ref="agreements-test")
            changed = client.propose_persona_change({"values": [PATIENT]}, reason="Asked for patience.",
                                                    source_event_ids=asked["result"]["accepted_event_ids"])
            client.observe("Shall I?", conversation_id="chat", branch_id="main", source_event_key=uid(),
                           producer_ref="agreements-test", role="assistant", delivery_state="delivered")
            yes = client.observe("Yes.", conversation_id="chat", branch_id="main", source_event_key=uid(),
                                 producer_ref="agreements-test")
            client.confirm_persona_change(changed["proposal"]["id"],
                                          source_event_ids=yes["result"]["accepted_event_ids"])
            return client.brain_id, yes["result"]["accepted_event_ids"]

    def card(user):
        with host.ready_client(directory, user) as client:
            return client.persona()["card"]

    # MCP memory_persona (Claude Code, Codex): switch on the user's request.
    brain_id, cited = ready("agreements-mcp")
    with host.ready_client(directory, "agreements-mcp") as client:
        _, result = asyncio.run(create_server(client, directory=directory).call_tool(
            "memory_persona", {"action": "switch", "preset": "random", "source_event_ids": cited}))
    assert "agreed to earlier carried over" in result["note"] and kept_both_values(card("agreements-mcp"))
    # OpenClaw's membrain_persona runs `membrain plugin tool persona`.
    _, cited = ready("agreements-openclaw")
    with host.ready_client(directory, "agreements-openclaw") as client:  # The first type is random: switch away.
        target = "istp" if client.persona().get("based_on") == "isfp" else "isfp"
    capsys.readouterr()
    code = plugin.run_tool("persona", directory, stream=io.BytesIO(json.dumps(
        {"action": "switch", "preset": target, "source_event_ids": cited,
         "membrain_user": "agreements-openclaw"}).encode()))
    assert code == 0 and "carried over" in json.loads(capsys.readouterr().out)["note"]
    assert kept_both_values(card("agreements-openclaw"))
    # A chat bot (AstrBot and others): the persona tool in the speaker's own memory.
    memory = ChatMemory(directory)
    speaker = Speaker(platform="test", user="agreements-bot")
    _, cited = ready(memory.user_id(speaker))
    switched = memory.persona(speaker, "switch", preset="estp", source_event_ids=cited)
    assert "error" not in switched and kept_both_values(card(memory.user_id(speaker)))
    # The memory page: a named switch, a random pick and a reset, through the HTTP routes.
    brain_id, _ = ready("agreements-page")
    key = "agreements-page-key"
    page_settings = replace(settings, api_keys={hashlib.sha256(key.encode()).hexdigest(): principal})
    with TestClient(create_app(page_settings, service), base_url="http://127.0.0.1",
                    headers={"Authorization": f"Bearer {key}"}) as page:
        base = f"/v1/brains/{brain_id}/persona"
        for response in (page.post(f"{base}/preset", json={"preset": "infj", "made_by": "user"}),
                         page.post(f"{base}/preset", json={"preset": "random", "made_by": "user"}),
                         page.post(f"{base}/reset", json={"made_by": "user"})):
            assert response.status_code == 200 and kept_both_values(response.json()["card"]), response.text
        listed = page.get(f"{base}/versions").json()
    assert [item["source"] for item in listed["agreements"]] == ["feedback", "proposal"]
    assert PATIENT not in listed["versions"][0]["base_card"]["values"]
    assert listed["versions"][0]["base_card"]["voice"]["length"] == ""


def kept_both_values(card):
    return card["voice"]["length"] == SHORTER and card["values"][-1] == PATIENT


def test_the_switch_note_and_the_page_say_the_agreements_carry_over():
    from pathlib import Path

    from membrain import persona_tool

    web = Path(__file__).parents[1] / "src" / "membrain" / "web"
    assert "the changes the user agreed to earlier carried over" in persona_tool.NOTES["switch"]
    assert "keeps the changes the user agreed to" in persona_tool.TOOL_DESCRIPTION
    script, dictionary = (web / "memory.js").read_text(encoding="utf-8"), (web / "i18n.js").read_text(encoding="utf-8")
    for text in ("Kept from what you agreed with your agent, whatever the personality type:",
                 "The mood, familiarity and what you agreed with your agent carry over."):
        assert text in script and text in dictionary
    assert "version.base_card" in script and "agreement.changes" in script
    for sample in ("From version 4: a suggestion you accepted",
                   "From version 12: a change your agent suggested and you agreed to"):
        assert "From version ${agreement.version}" in script and sample.split(": ", 1)[1] in dictionary
