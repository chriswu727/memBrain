"""Deferred notes must bind to the exact message that actually arrives."""
import pytest
from test_note_workflow import brain as brain
from test_note_workflow import write
from test_timeline import Brain

from membrain.affect import affect_records
from membrain.helpers import DomainError, uid
from membrain.notes import NOTES_CONVERSATION, store_note
from membrain.relationship import relationship

pytestmark = pytest.mark.integration


def reference(revision=1):
    # An opaque non-digest key remains identifiable in erasure tombstones.
    return {"producer_ref": "timeline-test", "source_event_key": "practice-interview", "source_revision": revision}


def observe(brain, ref, *, state="received", kind="message", conversation="first"):
    return brain.action("observe", {"idempotency_key": uid(), "events": [{
        **ref, "actor_ref": "user", "actor_role": "user", "event_kind": kind,
        "content": {"media_type": "text/plain", "text": "The practice interview was fun."},
        "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
        "interpretation_hint": "unknown", "delivery_state": state, "parent_source_event_keys": [],
    }]}, conversation=conversation)["accepted_event_ids"][0]


def forget(brain, source, mode="erase_content"):
    generation = brain.service.dashboard(brain.principal, brain.brain)["brain"]["scope_generation"]
    return brain.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [source]},
                                   "mode": mode, "expected_scope_generation": generation})


def notes(brain):
    return brain.timeline(roles=("user", "assistant"), conversation_id=NOTES_CONVERSATION)["items"]


@pytest.mark.parametrize("damage", ["superseded", "erase_content", "suppress_recall", "draft", "cancelled", "future"])
def test_known_unavailable_reference_cannot_replace_a_valid_note(brain, damage):
    ref = reference()
    source = observe(brain, ref, state=damage if damage in ("draft", "cancelled") else "received")
    if damage == "superseded":
        observe(brain, reference(2))
    elif damage in ("erase_content", "suppress_recall"):
        forget(brain, source, damage)
    elif damage == "future":
        ref = reference(2)
    kept = write(brain, "An independent appointment is on Friday.")
    with pytest.raises(DomainError) as failure:
        write(brain, "A stale interpretation.", replaces=[kept["note_id"]], source_messages=[ref],
              shared=True, kind="milestone", moment="play", affect={"label": "glad", "valence": 1,
              "intensity": 1, "basis": "reported"})
    assert failure.value.code == "source_unavailable"
    assert [note["event_id"] for note in notes(brain)] == [kept["note_id"]]
    assert affect_records(brain.service, brain.principal, brain.brain)["records"] == []


@pytest.mark.parametrize("revision,state", [(2, "received"), (1, "draft"), (1, "cancelled")])
def test_invalid_arrival_retires_only_its_pending_interpretation_and_erasure_reaches_it(brain, revision, state):
    source = brain.say("An independent appointment is on Friday.")
    kept = write(brain, "The Friday appointment.", source_event_ids=[source])
    pending = write(brain, "Our fun practice interview.", source_messages=[reference()],
                    shared=True, kind="milestone", moment="play", affect={"label": "glad", "valence": 1,
                    "intensity": 1, "basis": "reported"})
    assert pending["pending_source_count"] == 1
    original = observe(brain, reference(revision), state=state)
    assert [note["event_id"] for note in notes(brain)] == [kept["note_id"]]
    assert affect_records(brain.service, brain.principal, brain.brain)["records"] == []
    assert relationship(brain.service, brain.principal, brain.brain)["familiarity"]["shared_moments"] == 0
    # Retirement keeps provenance, so deleting the original also erases the old interpretation's body.
    forget(brain, original)
    with brain.service.database.transaction(brain.principal) as conn:
        rows = conn.execute("SELECT deleted,document FROM memory_events WHERE brain_id=%s AND id=ANY(%s::text[])",
                            (brain.brain, [pending["note_id"], pending["affect_id"]])).fetchall()
    assert len(rows) == 2 and all(row["deleted"] and row["document"] is None for row in rows)
    assert [note["event_id"] for note in notes(brain)] == [kept["note_id"]]


def test_exact_arrival_still_links_then_correction_retires_without_affecting_another_brain(brain):
    pending = write(brain, "Our fun practice interview.", source_messages=[reference()],
                    affect={"label": "glad", "valence": 1, "intensity": 1, "basis": "inferred"})
    other = Brain(brain.service, brain.principal)
    other_note = write(other, "Another brain's practice interview.", source_messages=[reference()])
    source = observe(brain, reference())
    assert notes(brain)[0]["source_event_ids"] == [source]
    assert notes(brain)[0]["pending_source_count"] == 0
    assert affect_records(brain.service, brain.principal, brain.brain)["records"][0]["source_event_ids"] == [source]
    observe(brain, reference(2))
    assert notes(brain) == []
    assert affect_records(brain.service, brain.principal, brain.brain)["records"] == []
    assert notes(other)[0]["event_id"] == other_note["note_id"]
    assert notes(other)[0]["pending_source_count"] == 1
    fresh = write(brain, "The corrected interpretation.", source_messages=[reference(2)])
    assert fresh["source_event_ids"] == [source]
    assert fresh["note_id"] != pending["note_id"]


@pytest.mark.parametrize("kind,conversation", [("artifact", "first"), ("message", NOTES_CONVERSATION)])
def test_non_original_arrival_never_grounds_a_pending_note(brain, kind, conversation):
    pending = write(brain, "An interpretation of an original message.", source_messages=[reference()])
    source = observe(brain, reference(), kind=kind, conversation=conversation)
    assert pending["note_id"] not in {item["event_id"] for item in notes(brain)}
    with pytest.raises(DomainError) as failure:
        write(brain, "It is still unavailable.", source_messages=[reference()])
    assert failure.value.code == "source_unavailable"
    forget(brain, source)
    assert notes(brain) == []


def test_pending_reference_to_a_future_revision_is_not_rebound_to_the_first_arrival(brain):
    pending = write(brain, "A reading of revision two.", source_messages=[reference(2)])
    observe(brain, reference())
    assert notes(brain) == []
    observe(brain, reference(2))
    assert notes(brain) == []  # Recording a later revision cannot resurrect a retired interpretation.
    assert write(brain, "A new reading of revision two.", source_messages=[reference(2)])["note_id"] != pending["note_id"]


def test_invalid_arrival_revokes_cached_note_acknowledgement_and_pending_replacements(brain):
    args = {"request_id": uid(), "text": "The first interpretation.", "source_messages": [reference()]}
    first = store_note(brain.service, brain.principal, brain.brain, args)
    assert store_note(brain.service, brain.principal, brain.brain, args) == first
    newer = write(brain, "The corrected interpretation.", replaces=[first["note_id"]])
    assert newer["pending_source_count"] == 1  # Replacements retain privacy dependencies.
    observe(brain, reference(2))
    assert notes(brain) == []
    with pytest.raises(DomainError) as failure:
        store_note(brain.service, brain.principal, brain.brain, args)
    assert failure.value.code == "version_conflict"


def test_retired_pending_interpretations_stay_retired_after_archive_restore(brain):
    from test_persona_growth import _restored

    pending = write(brain, "Our practice interview.", source_messages=[reference()],
                    shared=True, kind="milestone", moment="play", affect={"label": "glad", "valence": 1,
                    "intensity": 1, "basis": "reported"})
    source = observe(brain, reference(2))
    restored_id = _restored((brain.service, brain.principal, brain.brain), "Retired pending interpretation")
    restored = Brain.__new__(Brain)
    restored.service, restored.principal, restored.brain = brain.service, brain.principal, restored_id
    assert notes(restored) == []
    assert affect_records(restored.service, restored.principal, restored.brain)["records"] == []
    forget(restored, source)
    with brain.service.database.transaction(brain.principal) as conn:
        rows = conn.execute("SELECT deleted,document FROM memory_events WHERE brain_id=%s AND id=ANY(%s::text[])",
                            (restored_id, [pending["note_id"], pending["affect_id"]])).fetchall()
    assert len(rows) == 2 and all(row["deleted"] and row["document"] is None for row in rows)


def test_erased_digest_key_still_requires_the_existing_capture_revision_fence(brain):
    ref = {**reference(), "source_event_key": "a" * 64}
    source = observe(brain, ref)
    captured = brain.service.source_messages(brain.principal, brain.brain, [ref])["recording_revision"]
    forget(brain, source)
    with pytest.raises(DomainError) as failure:
        write(brain, "A delayed interpretation.", source_messages=[ref], expected_recording_revision=captured)
    assert failure.value.code == "recording_stale"
    assert notes(brain) == []


@pytest.mark.parametrize("hidden_by", ["replacement", "suppress_recall"])
@pytest.mark.parametrize("revision", [1, 2])
def test_hidden_pending_note_still_acquires_erasure_provenance(brain, hidden_by, revision):
    pending = write(brain, "The private first interpretation.", source_messages=[reference()],
                    affect={"label": "glad", "valence": 1, "intensity": 1, "basis": "reported"})
    if hidden_by == "replacement":
        write(brain, "The corrected interpretation.", replaces=[pending["note_id"]])
    else:
        forget(brain, pending["note_id"], "suppress_recall")
    source = observe(brain, reference(revision))
    assert pending["note_id"] not in {item["event_id"] for item in notes(brain)}
    forget(brain, source)
    with brain.service.database.transaction(brain.principal) as conn:
        rows = conn.execute("SELECT deleted,document FROM memory_events WHERE brain_id=%s AND id=ANY(%s::text[])",
                            (brain.brain, [pending["note_id"], pending["affect_id"]])).fetchall()
    assert len(rows) == 2 and all(row["deleted"] and row["document"] is None for row in rows)



def test_http_note_write_reports_unavailable_source_without_replacing_the_saved_note(brain):
    import hashlib

    from fastapi.testclient import TestClient

    from membrain.api import create_app
    from membrain.config import Settings

    observe(brain, reference(2))
    kept = write(brain, "Keep the independently supported appointment.")
    settings = Settings(database_url=brain.service.database.dsn,
                        api_keys={hashlib.sha256(b"local-test").hexdigest(): brain.principal})
    with TestClient(create_app(settings, service=brain.service)) as client:
        url = f"/v1/brains/{brain.brain}/notes"
        headers = {"Authorization": "Bearer local-test"}
        response = client.post(url, headers=headers, json={"request_id": uid(), "text": "Stale interpretation.",
            "replaces": [kept["note_id"]], "source_messages": [reference()]})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "source_unavailable"
        assert [note["event_id"] for note in notes(brain)] == [kept["note_id"]]
        fresh = client.post(url, headers=headers, json={"request_id": uid(), "text": "A current interpretation.",
            "source_messages": [reference(2)]})
        assert fresh.status_code == 200
        assert fresh.json()["pending_source_count"] == 0
