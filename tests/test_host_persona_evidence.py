"""Host suggestions retain the evidence they actually saw, across correction and decisions."""
import pytest
from test_persona_confirmation import PATIENT, confirm, propose, reference, turn, version
from test_persona_decisions import revise
from test_persona_growth import CARD, _restored, forget, listing, said
from test_persona_growth import brain as brain
from test_persona_growth import installation as installation

from membrain.companion_map import companion_map
from membrain.helpers import DomainError
from membrain.persona import set_persona
from membrain.persona_growth import accept_proposal, reject_proposal


@pytest.mark.parametrize("change", ["revise", "erase"])
@pytest.mark.parametrize("by_reference", [False, True])
def test_changed_evidence_withdraws_an_unaccepted_host_suggestion(brain, change, by_reference):
    set_persona(*brain, CARD, made_by="user")
    source = turn(brain, "Please be more patient with me.", key="request")
    citation = {"source_messages": [reference("request")]} if by_reference else {"source_event_ids": [source]}
    proposal = propose(brain, **citation)
    if change == "revise":
        revise(brain, source, "Actually, keep your current manner.")
    else:
        forget(brain, [source])
    listed = next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])
    assert listed["status"] == "withdrawn"
    assert listed["withdrawn_because"] == "source_unavailable"
    assert listed["sources"] == []
    with pytest.raises(DomainError) as refused:
        accept_proposal(*brain, proposal["id"])
    assert refused.value.code == "version_conflict"
    assert version(brain)["card"] == CARD


@pytest.mark.parametrize("decision", ["accepted", "rejected"])
@pytest.mark.parametrize("restored", [False, True])
def test_a_decided_suggestion_never_claims_a_later_revision_as_its_evidence(brain, decision, restored):
    set_persona(*brain, CARD, made_by="user")
    source = said(brain, "Please be more patient with me.")
    proposal = propose(brain, source_event_ids=[source])
    (accept_proposal if decision == "accepted" else reject_proposal)(*brain, proposal["id"])
    revise(brain, source, "I never asked for that change; keep the original manner.")
    if restored:
        brain = (*brain[:2], _restored(brain, "Restored host evidence"))
    listed = next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])
    assert listed["status"] == decision
    assert listed["sources"] == []
    assert listed["evidence"]["status"] == "unavailable"
    graph = companion_map(*brain)
    assert not any(edge["source"] == "proposal:" + proposal["id"] and edge["target"] == "msg:" + source
                   for edge in graph["edges"])
    # A choice the user already made remains a choice, even when its evidence is gone.
    assert version(brain)["card"]["traits"] == (PATIENT["traits"] if decision == "accepted" else CARD["traits"])


def test_pending_evidence_is_honest_and_cannot_be_accepted_until_recorded(brain):
    set_persona(*brain, CARD, made_by="user")
    proposal = propose(brain, source_messages=[reference("request")])
    assert proposal["evidence"] == {"status": "pending", "cited": 1, "available": 0, "pending": 1, "unavailable": 0}
    with pytest.raises(DomainError) as refused:
        accept_proposal(*brain, proposal["id"])
    assert refused.value.code == "source_unavailable"
    source = turn(brain, "Please be patient.", "Shall I add patient to my persona?", key="request")
    listed = next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])
    assert listed["evidence"]["status"] == "available"
    assert [item["event_id"] for item in listed["sources"]] == [source]
    yes = turn(brain, "Yes, please.")
    assert confirm(brain, proposal["id"], yes)["status"] == "confirmed"
    graph = companion_map(*brain)
    assert any(edge["type"] == "accepted_proposal" and edge["target"] == "proposal:" + proposal["id"]
               for edge in graph["edges"])


def test_uncited_suggestion_is_labelled_without_breaking_existing_callers(brain):
    set_persona(*brain, CARD, made_by="user")
    proposal = propose(brain)
    assert proposal["evidence"]["status"] == "not_cited"
    assert accept_proposal(*brain, proposal["id"])["persona"]["card"]["traits"] == PATIENT["traits"]


@pytest.mark.parametrize("hint", ["hypothetical", "quotation", "roleplay"])
def test_pending_citation_must_arrive_as_eligible_real_feedback(brain, hint):
    set_persona(*brain, CARD, made_by="user")
    proposal = propose(brain, source_messages=[reference("pending")])
    from membrain.helpers import uid

    service, principal, ident = brain
    result = service.handle(principal, {
        "contract_version": "1.0.0-draft", "message_type": "request", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": "pending", "source_revision": 1, "producer_ref": "growth-test",
            "actor_ref": "user", "actor_role": "user", "event_kind": "message", "delivery_state": "received",
            "content": {"media_type": "text/plain", "text": "Please be patient with me."},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": hint, "parent_source_event_keys": []}]}})
    assert result["outcome"] == "completed", result
    listed = next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])
    assert listed["status"] == "withdrawn" and listed["sources"] == []


def test_archive_with_unresolved_reference_cannot_claim_that_recording_is_still_pending(brain):
    set_persona(*brain, CARD, made_by="user")
    proposal = propose(brain, source_messages=[reference("missing")])
    brain = (*brain[:2], _restored(brain, "Unresolved source reference"))
    listed = next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])
    assert listed["evidence"]["status"] == "unavailable"
    assert listed["status"] == "withdrawn"


def test_duplicate_citation_forms_share_one_quote_and_have_consistent_counts(brain):
    set_persona(*brain, CARD, made_by="user")
    source = turn(brain, "Please be more patient.", key="request")
    proposal = propose(brain, source_event_ids=[source], source_messages=[reference("request")])
    assert proposal["source_count"] == 1
    assert proposal["evidence"] == {"status": "available", "cited": 2, "available": 2, "pending": 0, "unavailable": 0}


def test_a_future_revision_of_an_erased_source_is_not_reported_as_pending(brain):
    set_persona(*brain, CARD, made_by="user")
    source = turn(brain, "Please be patient.", key="request")
    proposal = propose(brain, source_messages=[{**reference("request"), "source_revision": 2}])
    assert proposal["evidence"]["status"] == "pending"
    forget(brain, [source])
    listed = next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])
    assert listed["evidence"]["status"] == "unavailable"
    assert listed["status"] == "withdrawn"
