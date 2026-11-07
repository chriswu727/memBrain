import copy

import pytest
from test_persona_growth import CARD, _restored, forget, later, listing, said

from membrain.companion_map import companion_map
from membrain.config import Settings
from membrain.helpers import DomainError, Principal, uid
from membrain.persona import delete_persona_history, persona_versions, restore_persona, set_persona
from membrain.persona_growth import accept_proposal, reject_proposal
from membrain.service import MemoryService
from membrain.storage import Database

pytestmark = pytest.mark.integration


@pytest.fixture
def brain():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("MEMORY_DATABASE_URL must point to the dedicated test database")
    database = Database(settings.database_url)
    service = MemoryService(database)
    principal = Principal(uid(), uid())
    try:
        yield service, principal, service.create_brain(principal, "Persona decision test")["id"]
    finally:
        database.close()


def opposite_accepted(brain):
    set_persona(*brain, {**CARD, "voice": {**CARD["voice"], "register": "neutral"}}, made_by="user")
    older = [said(brain, text) for text in (
        "you're too formal", "be more casual please", "Can you be more casual?")]
    original = next(p for p in listing(brain)["proposals"] if p["kind"] == "less_formal")
    newer = [said(brain, text) for text in (
        "you're too casual", "be more formal please", "Can you be more formal?")]
    assert next(p for p in listing(brain)["proposals"] if p["id"] == original["id"])["status"] == "withdrawn"
    opposite = next(p for p in listing(brain)["proposals"] if p["kind"] == "more_formal")
    accepted = accept_proposal(*brain, opposite["id"])
    assert accepted["persona"]["card"]["voice"]["register"] == "formal"
    forget(brain, newer)
    return original["id"], opposite["id"], older


def assert_consumed(brain, original, accepted):
    proposals = {p["id"]: p for p in listing(brain)["proposals"]}
    assert proposals[original]["status"] == "withdrawn"
    assert proposals[original]["withdrawn_because"] == "contradicted"
    assert proposals[accepted]["status"] == "accepted"
    assert proposals[accepted]["source_count"] == 0
    assert listing(brain)["open"] == 0
    with pytest.raises(DomainError) as refused:
        accept_proposal(*brain, original)
    assert refused.value.code == "version_conflict"
    history = persona_versions(*brain)["versions"]
    assert [version["version"] for version in history] == [2, 1]
    assert history[0]["card"]["voice"]["register"] == "formal"
    assert history[0]["feedback_messages"] == []
    graph = companion_map(*brain)
    proposals = {node["details"]["event_id"]: node for node in graph["nodes"] if node["kind"] == "persona_proposal"}
    assert proposals[original]["details"]["status"] == "withdrawn"
    assert proposals[accepted]["details"]["status"] == "accepted"
    assert any(edge["target"] == "proposal:" + accepted and edge["type"] == "accepted_proposal"
               for edge in graph["edges"])
    assert not any(edge["target"] == "proposal:" + original and edge["type"] == "accepted_proposal"
                   for edge in graph["edges"])


@pytest.mark.parametrize("restored", [False, True])
def test_accepted_direction_still_consumes_old_proposal_after_feedback_erasure(brain, restored):
    original, accepted, _ = opposite_accepted(brain)
    if restored:
        brain = (*brain[:2], _restored(brain, "Restored accepted direction"))
    assert_consumed(brain, original, accepted)
    for text in ("Please be more casual.", "You are too formal."):
        said(brain, text)
        assert listing(brain)["open"] == 0
    said(brain, "Can you be more casual now?")
    fresh = next(p for p in listing(brain)["proposals"] if p["status"] == "open")
    assert fresh["id"] != original and fresh["kind"] == "less_formal"
    assert fresh["source_count"] == 3
    assert accept_proposal(*brain, fresh["id"])["persona"]["card"]["voice"]["register"] == "casual"


def revise(brain, event_id, text=None):
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        current = service._brain(conn, principal, ident)
        source = service._events(conn, principal, current, event_ids=[event_id])[0]
    event = copy.deepcopy(source["observed"])
    event["source_revision"] += 1
    event["content"]["text"] = text if text is not None else event["content"]["text"] + " Please."
    result = service.handle(principal, {
        "contract_version": "1.0.0-draft", "message_type": "request", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [event]},
    })
    assert result["outcome"] == "completed", result
    assert result["result"]["accepted_event_ids"] == [event_id]


def test_revising_one_old_source_does_not_reauthorize_an_old_proposal(brain):
    original, accepted, older = opposite_accepted(brain)
    for event_id in older[:2]:
        revise(brain, event_id)
        assert_consumed(brain, original, accepted)
    revise(brain, older[2])
    proposals = {p["id"]: p for p in listing(brain)["proposals"]}
    assert proposals[original]["status"] == "withdrawn"
    fresh = next(p for p in proposals.values() if p["status"] == "open")
    assert fresh["id"] != original and fresh["source_count"] == 3
    assert accept_proposal(*brain, fresh["id"])["persona"]["card"]["voice"]["register"] == "casual"


def test_history_reset_removes_old_decisions_and_requires_new_feedback(brain):
    original, _, _ = opposite_accepted(brain)
    delete_persona_history(*brain)
    assert listing(brain)["proposals"] == []
    for text in ("Please be more casual.", "You are too formal."):
        said(brain, text)
        assert listing(brain)["proposals"] == []
    said(brain, "Can you be more casual now?")
    fresh = listing(brain)["proposals"][0]
    assert fresh["id"] != original and fresh["status"] == "open"
    assert accept_proposal(*brain, fresh["id"])["persona"]["version"] == 1


@pytest.mark.parametrize("decision", ["accepted", "rejected"])
def test_revising_old_feedback_cannot_bypass_a_later_decision_of_the_same_kind(brain, decision):
    set_persona(*brain, CARD, made_by="user")
    sources = [said(brain, text) for text in (
        "you're too formal", "be more casual please", "Can you be more casual?")]
    original = listing(brain)["proposals"][0]
    revise(brain, sources[0], "I like green tea.")
    assert listing(brain)["proposals"][0]["status"] == "withdrawn"
    said(brain, "Please be more casual now.")
    newer = next(p for p in listing(brain)["proposals"] if p["status"] == "open")
    assert newer["id"] != original["id"]
    if decision == "accepted":
        accept_proposal(*brain, newer["id"])
        restore_persona(*brain, 1, made_by="user")
    else:
        reject_proposal(*brain, newer["id"])
    revise(brain, sources[0], "Please be more casual.")
    current = listing(brain)
    assert current["open"] == 0
    proposals = {p["id"]: p for p in current["proposals"]}
    assert proposals[original["id"]]["withdrawn_because"] == "feedback_used"
    assert proposals[newer["id"]]["status"] == decision
    with pytest.raises(DomainError) as refused:
        accept_proposal(*brain, original["id"])
    assert refused.value.code == "version_conflict"
    said(brain, "Can you be more casual now?")
    assert listing(brain)["open"] == 0
    said(brain, "Your replies are too formal.")
    if decision == "rejected":
        assert listing(brain)["open"] == 0
        assert listing(brain, now=later(29))["open"] == 0
    ready = listing(brain, now=later(31))
    fresh = next(p for p in ready["proposals"] if p["status"] == "open")
    assert fresh["id"] not in (original["id"], newer["id"])
    assert fresh["source_count"] == 3
    assert accept_proposal(*brain, fresh["id"], now=later(31))["persona"]["card"]["voice"]["register"] == "casual"
