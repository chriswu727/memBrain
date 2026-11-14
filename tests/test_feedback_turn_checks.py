"""The checks the commit action's feedback proof makes of an old runtime turn (src/membrain/feedback.py).

Runtime turns are no longer created; brains from older runtimes still hold them, and ``recall_feedback`` credits a
memory only when such a turn's delivery receipt and prepared memory selection match the turn exactly. These are the
pure-function tests of those checks from the retired tests/test_delivery_receipts.py and
tests/test_prepared_selection.py, with receipts and selections written in the shape the removed runtime wrote them.
"""
import copy
import hashlib
import json

import pytest

from membrain.feedback import (
    _sanitize_delivery_receipt,
    _sanitize_prepared_selection,
    recorded_delivery_receipt,
    selection_for_turn,
)
from membrain.helpers import digest


def authorized_row():
    return {
        "output_event_refs": [{"event_id": "draft", "revision": 1}], "context_fingerprint": digest("context"),
        "context_generation": 3, "working_revision": 2, "fence": 1, "revision": 7,
    }


def receipt(row, text, state, *, reasons=(), failure=None):
    """A delivery receipt as the removed runtime's ``delivery_receipts.receipt_for`` wrote it (content recorded)."""
    encoded = text.encode("utf-8")
    return {
        "version": "runtime-delivery-receipt-v1", "state": state,
        "content_sha256": hashlib.sha256(encoded).hexdigest(), "content_bytes": len(encoded),
        "authorization": {
            "draft_event_ref": copy.deepcopy(row["output_event_refs"][0]),
            "context_fingerprint": row["context_fingerprint"], "context_generation": row["context_generation"],
            "working_revision": row["working_revision"], "turn_fence": row["fence"], "turn_revision": row["revision"],
        },
        "disposition": "content_recorded", "stale_reasons": sorted(reasons), "failure_code": failure,
    }


def recorded_row(stage="delivered"):
    original = authorized_row()
    return {**original, "output_event_refs": [{"event_id": "draft", "revision": 2}], "revision": 8,
            "delivery_receipt": receipt(original, "Actual reply", "delivered"), "stage": stage, "failure_code": None,
            "scope_reserved": stage == "delivered",
            "working_revision": original["working_revision"] + int(stage == "completed")}


def test_receipt_sanitizer_keeps_only_bounded_metadata():
    value = receipt(authorized_row(), "Actual 中文 reply", "partially_delivered")
    hostile = copy.deepcopy(value)
    hostile["body"] = "Private reply"
    hostile["authorization"]["lease_token"] = "Private token"
    hostile["authorization"]["draft_event_ref"]["text"] = "Private draft"
    assert _sanitize_delivery_receipt(hostile) == value
    assert "Private" not in json.dumps(_sanitize_delivery_receipt(hostile))


@pytest.mark.parametrize(("field", "value"), [
    ("version", "other"), ("state", []), ("content_sha256", "x" * 64), ("content_bytes", True),
    ("content_bytes", 64001), ("content_bytes", 0), ("disposition", "arbitrary"),
    ("stale_reasons", ["raw secret"]), ("stale_reasons", ["source_unavailable", "source_unavailable"]),
    ("failure_code", "source_unavailable"), ("authorization", []),
])
def test_receipt_sanitizer_rejects_malformed_or_inconsistent_metadata(field, value):
    stored = receipt(authorized_row(), "Actual reply", "delivered")
    stored[field] = value
    assert _sanitize_delivery_receipt(stored) is None


def test_recorded_receipt_requires_exact_binding_and_terminal_classification():
    assert recorded_delivery_receipt(recorded_row())
    assert recorded_delivery_receipt(recorded_row("completed"))
    for changes in ({"stage": []}, {"scope_reserved": 1}, {"working_revision": True},
                    {"context_fingerprint": digest("different")}, {"context_generation": 4},
                    {"output_event_refs": [{"event_id": "other", "revision": 2}]},
                    {"revision": 7}, {"failure_code": "cancelled"}):
        assert not recorded_delivery_receipt(recorded_row() | changes)
    failed_receipt = receipt(authorized_row(), "Actual reply", "delivered", reasons=["working_revision_changed"],
                             failure="commit_failed")
    failed = recorded_row() | {"stage": "failed", "scope_reserved": False, "failure_code": "commit_failed",
                               "delivery_receipt": failed_receipt}
    assert recorded_delivery_receipt(failed)


def selection():
    return {
        "version": "prepared-memory-selection-v1", "state": "complete", "unavailable_reason": None,
        "turn_id": "turn", "brain_id": "brain", "conversation_id": "conversation", "branch_id": "main",
        "packet_id": "packet", "model_context_sha256": "a" * 64, "context_fingerprint": "b" * 64,
        "context_generation": 0, "working_revision": 0, "prepared_at": "2026-10-25T00:00:00Z",
        "input_event_refs": [{"event_id": "input", "revision": 1}],
        "source_event_refs": [{"event_id": "source", "revision": 1, "content_sha256": "c" * 64}],
        "memories": [{"memory_id": "memory", "memory_revision": 1, "statement_sha256": "d" * 64,
                      "trace_id": "trace", "recall_id": "recall", "evidence_refs": [{
                          "event_id": "source", "event_revision": 1,
                          "source_content_sha256": "c" * 64, "relationship": "supports"}]}],
    }


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(private_text="private-content"),
    lambda value: value.update(context_generation=True),
    lambda value: value.update(working_revision=1.0),
    lambda value: value.update(input_event_refs=[]),
    lambda value: value["source_event_refs"].append({**value["source_event_refs"][0], "revision": 2}),
    lambda value: value["input_event_refs"].append({"event_id": "input", "revision": 2}),
    lambda value: value["memories"].append({**value["memories"][0], "memory_revision": 2}),
    lambda value: value["memories"][0].update(memory_revision=1.0),
    lambda value: value["memories"][0].update(evidence_refs=[]),
    lambda value: value["memories"][0]["evidence_refs"][0].update(event_id="unbound"),
    lambda value: value["memories"][0]["evidence_refs"][0].update(source_content_sha256="e" * 64),
    lambda value: value["memories"][0]["evidence_refs"][0].update(event_revision=True),
])
def test_corrupt_selection_cannot_authorize_feedback_or_leak_extra_fields(mutation):
    value = selection()
    mutation(value)
    assert _sanitize_prepared_selection(value) is None


def test_selection_is_detached_and_matches_turn_identity_without_rebasing_prepared_revision():
    value = selection()
    detached = _sanitize_prepared_selection(value)
    assert detached == value and detached is not value
    detached["memories"].clear()
    assert value["memories"]
    row = {**value, "working_revision": 9, "prepared_memory_selection": value,
           "context_event_refs": [{"event_id": "source", "revision": 1}]}
    assert selection_for_turn(row) == value
    for changes in ({"turn_id": "different"}, {"conversation_id": "other"}, {"brain_id": "other"},
                    {"context_generation": 1}, {"context_fingerprint": "f" * 64},
                    {"input_event_refs": [{"event_id": "new", "revision": 1}]}, {"context_event_refs": []}):
        assert selection_for_turn({**row, **changes}) is None


def test_custom_context_is_valid_metadata_but_never_an_attribution_binding():
    sentinel = {"version": "prepared-memory-selection-v1", "state": "unavailable",
                "unavailable_reason": "custom_context"}
    assert _sanitize_prepared_selection(sentinel) == sentinel
    assert selection_for_turn({"prepared_memory_selection": sentinel}) is None
    assert _sanitize_prepared_selection({**sentinel, "text": "private-context"}) is None
    assert _sanitize_prepared_selection({**sentinel, "unavailable_reason": "unknown"}) is None


def test_selection_size_and_count_bounds_are_enforced_before_feedback():
    value = selection()
    value["memories"] = [{**copy.deepcopy(value["memories"][0]), "memory_id": str(index)} for index in range(65)]
    assert _sanitize_prepared_selection(value) is None
    value = selection()
    value["memories"][0]["evidence_refs"] = [{
        **value["memories"][0]["evidence_refs"][0], "span": {"start": index, "end": index + 1, "unit": "unicode_code_point"},
    } for index in range(1024)]
    value["memories"] = [{**copy.deepcopy(value["memories"][0]), "memory_id": str(index)} for index in range(2)]
    assert _sanitize_prepared_selection(value) is None
