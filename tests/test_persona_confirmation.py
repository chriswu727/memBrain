"""Changes to the persona that the host AI proposes: nothing changes until the user says yes in a later message.

The service refuses a confirmation unless it cites a user message recorded after an assistant message of the same
conversation that was itself recorded after the proposal (``persona_growth.confirm_change``). Hosts record a turn's
message and reply when the turn ends, so the proposal's own turn, an older message or an assistant message can never
confirm it; the user's next message can, also when it is recorded only after the call."""
import pytest
from test_persona_feedback_host import say_as
from test_persona_growth import CARD, listing, said
from test_persona_growth import brain as brain
from test_persona_growth import installation as installation

from membrain.helpers import DomainError, uid
from membrain.persona import current_persona, persona_versions, set_persona
from membrain.persona_growth import (
    accept_proposal,
    confirm_change,
    decline_change,
    propose_change,
    reject_proposal,
    report_feedback,
)

PATIENT = {"traits": ["warm", "patient"]}


def reference(key):
    return {"producer_ref": "growth-test", "source_event_key": key, "source_revision": 1}


def propose(brain, changes=PATIENT, reason="The user asked twice for more patience from now on.", **sources):
    service, principal, ident = brain
    return propose_change(service, principal, ident, changes, reason=reason, **sources)["proposal"]


def confirm(brain, proposal_id, *ids, messages=()):
    service, principal, ident = brain
    return confirm_change(service, principal, ident, proposal_id, source_event_ids=list(ids),
                          source_messages=list(messages))


def turn(brain, text, reply="Okay.", key=None):
    """One host turn as hooks record it when it ends: the user's message, then the reply, in one conversation."""
    key = key or "turn-" + uid()
    message = say_as(brain, text, key)
    say_as(brain, reply, key + ":reply", role="assistant")
    return message


def version(brain):
    service, principal, ident = brain
    return current_persona(service, principal, ident)


def refused(code, call, *args, **kwargs):
    with pytest.raises(DomainError) as error:
        call(*args, **kwargs)
    assert error.value.code == code, error.value.message
    return error.value.message


def test_a_proposal_changes_nothing_and_shows_its_before_and_after(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    asked = said(brain, "From now on, please be more patient with me.")
    proposal = propose(brain, PATIENT | {"voice": {"length": "short"}}, source_event_ids=[asked])
    assert (proposal["kind"], proposal["status"], proposal["base_version"]) == ("host", "open", 1)
    assert proposal["changes"] == [
        {"field": "traits", "before": ["warm"], "after": ["warm", "patient"]},
        {"field": "voice.length", "before": "two or three sentences", "after": "short"}]
    assert proposal["proposed_card"]["voice"]["register"] == "formal"  # Everything else stays.
    assert [source["event_id"] for source in proposal["sources"]] == [asked]
    assert proposal["reason"] == "The user asked twice for more patience from now on."
    assert version(brain)["version"] == 1  # Nothing changed.
    assert listing(brain)["open"] == 1 and listing(brain)["proposals"][0]["id"] == proposal["id"]


def test_proposals_are_validated_and_at_most_one_is_open(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    assert "nothing to propose" in refused("validation_failed", propose, brain, {"traits": ["warm"]})
    assert "changes must name" in refused("validation_failed", propose, brain, {"mood": "glad"})
    assert "Persona card field traits" in refused("validation_failed", propose, brain, {"traits": ["x" * 61]})
    assert "rendered" in refused("validation_failed", propose, brain, {"values": ["v" * 150] * 8})
    assert "reason" in refused("validation_failed", propose, brain, PATIENT, reason="")
    reply = said(brain, "Sure.", role="assistant")
    assert refused("source_unavailable", propose, brain, PATIENT, source_event_ids=[reply])
    older = propose(brain)
    newer = propose(brain, {"traits": ["warm", "calm"]})
    statuses = {item["id"]: (item["status"], item["withdrawn_because"]) for item in listing(brain)["proposals"]}
    assert statuses == {newer["id"]: ("open", None), older["id"]: ("withdrawn", "replaced")}
    # A proposal made on an older card is withdrawn once the card changes.
    set_persona(service, principal, ident, {**CARD, "name": "Mira 2"}, made_by="user")
    assert [item["withdrawn_because"] for item in listing(brain)["proposals"]] == ["persona_changed", "replaced"]


def test_a_proposal_stores_its_fields_scrubbed_like_the_card(brain):
    service, principal, ident = brain
    secret = "sk-proj-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
    proposal = propose(brain, {"traits": ["warm", f"key {secret}"]})
    assert secret not in str(proposal["proposed_card"]) and secret not in str(proposal["changes"])
    with service.database.transaction(principal) as conn:
        texts = [row["text"] for row in conn.execute(
            "SELECT document->'observed'->'content'->>'text' AS text FROM memory_events WHERE brain_id=%s "
            "AND conversation_id='membrain-persona-proposals'", (ident,))]
    assert texts and not any(secret in text for text in texts)


def test_proposing_and_confirming_in_one_turn_is_refused_and_the_next_message_confirms(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    turn(brain, "Hi there.")  # An earlier exchange.
    # Turn 1: the user asks; the AI proposes and tries to confirm at once, citing the turn's own message.
    asking = "turn-" + uid()
    proposal = propose(brain, source_messages=[reference(asking)])
    assert "has not answered" in refused("source_unavailable", confirm, brain, proposal["id"],
                                         messages=[reference(asking)])
    other = "turn-" + uid()  # Any other reference in that turn too: nothing was said after the proposal.
    refused("source_unavailable", confirm, brain, proposal["id"], messages=[reference(other)])
    asked = turn(brain, "From now on, please be more patient.", "Shall I add 'patient' to my persona?", key=asking)
    # Turn 2: the older message, the assistant's reply and malformed citations are refused.
    assert "not the user's answer" in refused("source_unavailable", confirm, brain, proposal["id"], asked)
    reply = said(brain, "Noted.", role="assistant")
    refused("source_unavailable", confirm, brain, proposal["id"], reply)
    refused("validation_failed", confirm, brain, proposal["id"])
    refused("validation_failed", confirm, brain, proposal["id"], asked, messages=[reference(other)])
    assert version(brain)["version"] == 1
    # The user's yes, cited before the turn is recorded: confirmed, and saved when the message arrives.
    yes = "turn-" + uid()
    waiting = confirm(brain, proposal["id"], messages=[reference(yes)])
    assert waiting["status"] == "waiting_for_message" and waiting["proposal"]["waiting_for_confirmation"]
    assert confirm(brain, proposal["id"], messages=[reference(yes)])["status"] == "waiting_for_message"
    assert version(brain)["version"] == 1
    answer = turn(brain, "Yes, please do.", key=yes)
    saved = version(brain)
    assert (saved["version"], saved["made_by"], saved["action"]) == (2, "user", "proposal")
    assert saved["host_proposal"] == {"proposal_id": proposal["id"], "confirmed_by": answer}
    assert saved["card"]["traits"] == ["warm", "patient"] and saved["reason"] == proposal["reason"]
    decided = next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])
    assert (decided["status"], decided["version"]) == ("accepted", 2)
    assert len(persona_versions(service, principal, ident)["versions"]) == 2


def test_a_recorded_later_user_message_confirms_at_once(brain):
    # Hosts that record the user's message before the AI's tool call cite it by id.
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    proposal = propose(brain)
    said(brain, "Want me to be more patient from now on?", role="assistant")
    yes = said(brain, "Yes.")
    result = confirm(brain, proposal["id"], yes)
    assert result["status"] == "confirmed" and result["persona"]["version"] == 2
    assert result["persona"]["host_proposal"]["confirmed_by"] == yes
    assert "no longer open" in refused("version_conflict", confirm, brain, proposal["id"], yes)


def test_a_reply_in_another_conversation_does_not_count_as_the_question(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    proposal = propose(brain)
    said(brain, "Elsewhere.", role="assistant", conversation="another-chat")
    yes = said(brain, "Yes.")
    refused("source_unavailable", confirm, brain, proposal["id"], yes)


def test_a_waiting_confirmation_applies_only_to_a_user_message_while_the_proposal_is_open(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    first = propose(brain)
    turn(brain, "Be more patient from now on.", "Shall I?")
    yes = "turn-" + uid()
    confirm(brain, first["id"], messages=[reference(yes)])
    replacement = propose(brain, {"traits": ["warm", "calm"]})  # Replaced before the user's message arrives.
    turn(brain, "Yes.", key=yes)
    assert version(brain)["version"] == 1
    turn(brain, "And this one?", "Shall I add 'calm' instead?")
    key = "turn-" + uid()
    confirm(brain, replacement["id"], messages=[reference(key)])
    say_as(brain, "I'll do it.", key, role="assistant")  # The reference turned out to be the AI's own message.
    assert version(brain)["version"] == 1
    assert next(item for item in listing(brain)["proposals"] if item["id"] == replacement["id"])["status"] == "open"


def test_decline_rejects_without_a_pause_and_only_applies_to_the_agents_proposals(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    proposal = propose(brain)
    declined = decline_change(service, principal, ident, proposal["id"])
    assert (declined["proposal"]["status"], declined["proposal"]["paused_until"]) == ("rejected", None)
    assert declined["pauses"] == [] and version(brain)["version"] == 1
    assert propose(brain, {"traits": ["warm", "calm"]})["status"] == "open"  # No pause machinery.
    for text in ("Shorter answers, please.", "Too much text.", "TL;DR next time?"):
        report_feedback(service, principal, ident, "shorter", source_event_ids=[said(brain, text)])
    feedback = next(item for item in listing(brain)["proposals"] if item["kind"] == "shorter")
    assert "memory page" in refused("validation_failed", decline_change, service, principal, ident, feedback["id"])
    refused("validation_failed", confirm, brain, feedback["id"], said(brain, "Yes"))


def test_the_memory_page_can_accept_or_reject_the_agents_proposal(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    proposal = propose(brain)
    accepted = accept_proposal(service, principal, ident, proposal["id"])
    assert accepted["persona"]["host_proposal"] == {"proposal_id": proposal["id"], "confirmed_by": None}
    assert (accepted["persona"]["made_by"], accepted["persona"]["action"]) == ("user", "proposal")
    other = propose(brain, {"traits": ["warm", "patient", "calm"]})
    rejected = reject_proposal(service, principal, ident, other["id"])
    assert rejected["proposal"]["status"] == "rejected" and rejected["pauses"] == []
