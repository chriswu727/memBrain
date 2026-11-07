import pytest
from test_affect import NERVOUS, forget, say, write
from test_persona_decisions import brain as brain
from test_persona_growth import _restored

from membrain.affect import affect_records, clear_affect
from membrain.helpers import uid
from membrain.memory_map import memory_map
from membrain.mood import mood_state

pytestmark = pytest.mark.integration
INFERRED = {**NERVOUS, "basis": "inferred"}


def observed(brain, ref, *, role="user", delivery=None, conversation="chat"):
    service, principal, ident = brain
    target = {"brain_ref": ident, "branch_ref": "main"}
    if conversation is not None:
        target["conversation_ref"] = conversation
    response = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": target,
        "payload": {"idempotency_key": uid(), "events": [{
            **ref, "actor_ref": role, "actor_role": role, "event_kind": "message",
            "content": {"media_type": "text/plain", "text": "Nervous about Friday's interview."},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": delivery or ("received" if role == "user" else "delivered"),
            "parent_source_event_keys": [],
        }]},
    })
    assert response["outcome"] == "completed", response
    return response["result"]["accepted_event_ids"][0]


def new_reference():
    return {"producer_ref": "affect-provenance-test", "source_event_key": uid(), "source_revision": 1}


def assert_no_feeling(brain):
    assert affect_records(*brain)["records"] == []
    assert mood_state(*brain)["at_baseline"]
    assert not any(node["kind"] == "affect" for node in memory_map(*brain)["nodes"])


@pytest.mark.parametrize("restored", [False, True])
def test_assistant_speculation_cannot_become_user_affect(brain, restored):
    source = say(brain, "You might be nervous.", role="assistant")
    write(brain, "Interview on Friday.", source_event_ids=[source], affect=INFERRED)
    if restored:
        brain = (*brain[:2], _restored(brain, "Restored speculation"))
    assert_no_feeling(brain)


@pytest.mark.parametrize("role,delivery", [("user", "received"), ("assistant", "delivered"), ("user", "draft")])
def test_pending_inference_waits_for_actual_user_evidence(brain, role, delivery):
    ref = new_reference()
    saved = write(brain, "Interview on Friday.", source_messages=[ref], affect=INFERRED)
    assert saved["affect_id"]
    assert_no_feeling(brain)
    source = observed(brain, ref, role=role, delivery=delivery)
    if role == "user" and delivery == "received":
        (record,) = affect_records(*brain)["records"]
        assert record["source_event_ids"] == [source]
        assert not mood_state(*brain)["at_baseline"]
        restored = (*brain[:2], _restored(brain, "Restored resolved inference"))
        assert affect_records(*restored)["records"][0]["source_event_ids"] == [source]
        forget(brain, [source])
    assert_no_feeling(brain)


@pytest.mark.parametrize("pending", [False, True])
def test_replacing_a_note_cannot_recreate_cleared_feelings_from_inherited_sources(brain, pending):
    if pending:
        ref = new_reference()
        note = write(brain, "Interview on Friday.", source_messages=[ref])
        note = write(brain, "Interview next Friday.", replaces=[note["note_id"]])
        observed(brain, ref)
    else:
        source = say(brain, "I'm nervous about Friday.")
        note = write(brain, "Interview on Friday.", source_event_ids=[source], affect=NERVOUS)
    clear_affect(*brain)
    updated = write(brain, "Interview at 9 on Friday.", replaces=[note["note_id"]], affect=NERVOUS)
    assert updated["affect_id"] is None and "cleared" in updated["affect_refused"]
    assert updated["note_id"]
    assert_no_feeling(brain)


@pytest.mark.parametrize("by_reference", [False, True])
def test_new_reading_uses_new_evidence_without_borrowing_old_note_sources(brain, by_reference):
    old = say(brain, "I'm nervous about Friday.")
    note = write(brain, "Interview on Friday.", source_event_ids=[old], affect=NERVOUS)
    clear_affect(*brain)
    ref = new_reference()
    fresh = observed(brain, ref)
    sources = {"source_messages": [ref]} if by_reference else {"source_event_ids": [fresh]}
    saved = write(brain, "Interview at 9 on Friday.", replaces=[note["note_id"]], affect=INFERRED, **sources)
    assert saved["affect_id"]
    assert set(saved["source_event_ids"]) == {old, fresh}
    (record,) = affect_records(*brain)["records"]
    assert record["source_event_ids"] == [fresh]
    restored = (*brain[:2], _restored(brain, "Restored new reading"))
    assert affect_records(*restored)["records"][0]["source_event_ids"] == [fresh]


def test_pending_new_inference_cannot_borrow_inherited_user_evidence(brain):
    old = say(brain, "I'm nervous about Friday.")
    note = write(brain, "Interview on Friday.", source_event_ids=[old])
    ref = new_reference()
    write(brain, "Interview at 9.", replaces=[note["note_id"]], source_messages=[ref], affect=INFERRED)
    assert_no_feeling(brain)
    observed(brain, ref, role="assistant")
    assert_no_feeling(brain)


def test_unresolved_reading_can_resolve_after_archive_restore(brain):
    ref = new_reference()
    write(brain, "Interview on Friday.", source_messages=[ref], affect=INFERRED)
    restored = (*brain[:2], _restored(brain, "Restored pending reading"))
    assert_no_feeling(restored)
    source = observed(restored, ref)
    (record,) = affect_records(*restored)["records"]
    assert record["source_event_ids"] == [source]
    assert mood_state(*restored)["at_baseline"]
    forget(restored, [source])
    assert_no_feeling(restored)


@pytest.mark.parametrize("pending", [False, True])
def test_user_sources_without_a_conversation_resolve_in_either_order(brain, pending):
    service, principal, ident = brain
    ref = new_reference()
    if not pending:
        source = observed(brain, ref, conversation=None)
    saved = write(brain, "Interview on Friday.", source_messages=[ref], affect=INFERRED)
    if pending:
        assert_no_feeling(brain)
        source = observed(brain, ref, conversation=None)
    assert affect_records(*brain)["records"][0]["source_event_ids"] == [source]
    notes = service.timeline(principal, ident, conversation_id="membrain-notes", roles=("assistant",))["items"]
    assert next(note for note in notes if note["event_id"] == saved["note_id"])["source_event_ids"] == [source]


@pytest.mark.parametrize("fresh_source", [False, True])
def test_legacy_reading_keeps_reset_boundary_without_rejecting_explicit_new_evidence(brain, monkeypatch, fresh_source):
    from membrain.affect import AFFECT_CONVERSATION, record_affect
    from membrain.notes import check_affect

    service, principal, ident = brain
    old = say(brain, "I'm nervous about Friday.")
    note = write(brain, "Interview on Friday.", source_event_ids=[old])
    clear_affect(*brain)
    sources = [say(brain, "I'm still nervous about Friday.")] if fresh_source else []
    append = service._append_event

    def legacy_append(conn, who, current, target, incoming, **kwargs):
        if target["conversation_ref"] == AFFECT_CONVERSATION:
            incoming.pop("source_references", None)
        return append(conn, who, current, target, incoming, **kwargs)

    monkeypatch.setattr(service, "_append_event", legacy_append)
    with service.database.transaction(principal) as conn:
        current = service._brain(conn, principal, ident)
        saved = record_affect(service, conn, principal, current, note_id=note["note_id"],
                              affect=check_affect(NERVOUS, sourced=bool(sources)),
                              request_id=uid(), producer="membrain-notes", source_event_ids=sources)
        assert saved["affect_id"]
    restored = (*brain[:2], _restored(brain, "Restored legacy reading"))
    for candidate in (brain, restored):
        if fresh_source:
            assert affect_records(*candidate)["records"][0]["source_event_ids"] == sources
        else:
            assert_no_feeling(candidate)
