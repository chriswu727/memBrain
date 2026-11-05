from test_relationship import brain as brain
from test_relationship import installation as installation
from test_relationship import say

from membrain.helpers import uid
from membrain.relationship import (
    _append,
    add_boundary,
    relationship,
    relationship_boundaries,
    reset_relationship,
    set_cap,
)


def test_relationship_controls_and_reset_survive_more_than_5000_records(brain):
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        stored_brain = service._brain(conn, principal, ident)
        for _ in range(5000):
            _append(service, conn, principal, stored_brain,
                    {"relationship_marker": "reset", "removed": {}}, uid())
    say(brain, "Please keep our earlier conversations private.")
    saved = add_boundary(*brain, "earlier conversations")
    assert [item["topic"] for item in saved["boundaries"]] == ["earlier conversations"]
    assert relationship_boundaries(*brain)["boundaries"] == saved["boundaries"]
    assert set_cap(*brain, "new")["familiarity"]["cap"] == "new"
    result = reset_relationship(*brain)
    assert result["removed"]["boundaries"] == 1
    assert result["removed"]["cap"] == 1
    assert len(result["markers"]) == 5001
    assert result["marker"] == result["markers"][0]
    assert result["familiarity"]["days"] == 0
    assert result["familiarity"]["cap"] is None
    assert relationship_boundaries(*brain)["boundaries"] == []
    say(brain, "We can start again today.")
    assert relationship(*brain)["familiarity"]["days"] == 1


def test_familiarity_counts_shared_moments_before_display_sampling(brain):
    from membrain.notes import NOTES_CONVERSATION, format_note, store_note

    service, principal, ident = brain
    store_note(*brain, {"request_id": uid(), "text": "Our first conversation.", "kind": "milestone", "shared": True, "sensitive": True})
    with service.database.transaction(principal) as conn:
        stored_brain = service._brain(conn, principal, ident)
        target = {"conversation_ref": NOTES_CONVERSATION, "branch_ref": "main"}
        def append(text, shared):
            service._append_event(conn, principal, stored_brain, target, {
                "source_event_key": uid(), "source_revision": 1, "producer_ref": "relationship-history-test",
                "actor_ref": "user", "actor_role": "user", "event_kind": "message",
                "content": {"media_type": "text/plain", "text": format_note(text, kind="milestone", shared=shared)},
                "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})
        for i in range(2500):
            append(f"An unrelated milestone {i}.", False)
    result = relationship(*brain)
    assert result["familiarity"]["shared_moments"] == 1
    assert result["shared_moments"][0]["text"] == "Our first conversation."
    with service.database.transaction(principal) as conn:
        stored_brain = service._brain(conn, principal, ident)
        for i in range(500):
            append(f"A shared milestone {i}.", True)
    result = relationship(*brain)
    assert result["familiarity"]["shared_moments"] == 501
    assert result["shared_moments_total"] == 501
    assert result["shared_moments_truncated"]
    assert len(result["shared_moments"]) == 500
    from membrain.companion_map import companion_map

    assert companion_map(*brain, max_nodes=1)["familiarity"] == {"derived": True, "masked": True}
    visible = companion_map(*brain, max_nodes=1, include_sensitive=True)["familiarity"]
    assert visible["shared_moments"] == 501 and visible["evidence"]["shared_moments_truncated"]
    reset = reset_relationship(*brain)
    assert reset["removed"]["shared_moments"] == 501
    assert reset["familiarity"]["shared_moments"] == 0
