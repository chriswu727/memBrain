import copy
import json

import pytest
from test_consolidation import memory as memory
from test_pattern_store import store as store
from test_semantic import reference

from membrain.contracts import validate
from membrain.helpers import now, uid
from membrain.notes import store_note
from membrain.structure_map import structure_map

pytestmark = pytest.mark.integration


def saved_state(store, source, *, revision=1, branch="main", items=None, loops=None):
    with store.database.transaction(store.principal) as conn:
        brain = store.service._brain(conn, store.principal, store.brain_id)
        target = {"conversation_ref": "test", "branch_ref": branch}
        stamp = now()
        item = {"key": "current_goal", "value": "Plan the library visit", "knowledge_state": "inferred",
                "evidence_refs": [reference(source)], "expires_at": "2000-01-01T00:00:00Z", "updated_at": stamp}
        loop = {"loop_id": "visit", "description": "Visit the library", "state": "planned",
                "due_time": {"start": "2000-01-01T00:00:00Z", "end": None, "precision": "day", "basis": "source_explicit"},
                "evidence_refs": [reference(source)], "last_updated_at": stamp}
        document = {"scope": store.service._scope(store.principal, brain, target), "revision": revision,
                    "through_sequence": brain["durable_sequence"], "items": [item] if items is None else items,
                    "open_loops": [loop] if loops is None else loops, "updated_at": stamp}
        validate("WorkingState", document)
        store.service._working_save(conn, store.principal, brain, target, document)
        return document


def graph(store, **options):
    return structure_map(store.service, store.principal, store.brain_id, **options)


def test_persisted_state_items_and_loops_keep_status_and_exact_evidence(store):
    source = store.observe("I plan to visit the library.")
    saved_state(store, source)
    result = graph(store)
    assert result["coverage"]["working_state"] == "bounded_stored_versions_with_current_evidence"
    nodes = {node["kind"]: node for node in result["nodes"]}
    assert nodes["working_state"]["details"]["revision"] == 1
    assert nodes["working_item"]["details"]["knowledge_state"] == "inferred"
    assert nodes["working_item"]["details"]["expired"]
    assert nodes["open_loop"]["details"]["status"] == "planned"
    assert {(edge["source"], edge["target"]) for edge in result["edges"] if edge["type"] == "working_evidence"} == {
        (nodes[kind]["id"], "msg:" + source["event_id"]) for kind in ("working_item", "open_loop")}
    assert len([edge for edge in result["edges"] if edge["type"] == "working_member"]) == 2


def test_unknown_has_no_fabricated_evidence_and_versions_are_branch_specific(store):
    source = store.observe("Plan a visit.")
    document = saved_state(store, source)
    unknown = {**document["items"][0], "knowledge_state": "unknown", "value": None, "evidence_refs": []}
    saved_state(store, source, items=[unknown], loops=[])
    first = graph(store)
    first_ids = {node["id"] for node in first["nodes"] if node["region"] == "working"}
    assert not any(edge["type"] == "working_evidence" for edge in first["edges"])
    saved_state(store, source, revision=2, branch="alternate")
    both = graph(store)
    assert len([node for node in both["nodes"] if node["kind"] == "working_state"]) == 2
    saved_state(store, source, revision=3)
    assert first_ids.isdisjoint(node["id"] for node in graph(store)["nodes"])


@pytest.mark.parametrize("damage", ["revision", "hash", "span"])
def test_stale_or_invalid_evidence_cannot_expose_state_content(store, damage):
    source = store.observe("Plan a visit.")
    document = saved_state(store, source)
    item = copy.deepcopy(document["items"][0])
    item["value"] = "invalid-only-secret"
    ref = item["evidence_refs"][0]
    if damage == "revision":
        ref["event_revision"] += 1
    elif damage == "hash":
        ref["source_content_sha256"] = "0" * 64
    else:
        ref["span"]["end"] += 100
    saved_state(store, source, items=[item], loops=[])
    result = graph(store)
    assert not any(node["kind"] == "working_item" for node in result["nodes"])
    assert "invalid-only-secret" not in json.dumps(result)


@pytest.mark.parametrize("mode", ["erase_content", "suppress_recall"])
def test_erasure_or_suppression_removes_working_evidence_and_content(store, mode):
    source = store.observe("Plan the secret outing.")
    saved_state(store, source)
    store.action("forget", {"selector": {"kind": "events", "ids": [source["event_id"]]}, "mode": mode,
                            "expected_scope_generation": 1, "idempotency_key": uid()})
    result = graph(store)
    assert not any(node["kind"] in {"working_item", "open_loop"} for node in result["nodes"])
    assert not any(edge["type"] == "working_evidence" for edge in result["edges"])


@pytest.mark.parametrize("origin", ["source", "direct_note", "shared_note"])
def test_sensitive_evidence_masks_state_children_and_parent_before_visual_bounds(store, origin):
    source = store.observe("private-source-731")
    secret = store_note(store.service, store.principal, store.brain_id,
                        {"request_id": uid(), "text": "private-note-731", "kind": "constraint", "sensitive": True,
                         "source_event_ids": [source["event_id"]]})
    if origin == "shared_note":
        secret = store_note(store.service, store.principal, store.brain_id,
                            {"request_id": uid(), "text": "related-note-731", "kind": "other",
                             "source_event_ids": [source["event_id"]]})
    if origin != "source":
        with store.database.transaction(store.principal) as conn:
            brain = store.service._brain(conn, store.principal, store.brain_id)
            source = store.service._events(conn, store.principal, brain, event_ids=[secret["note_id"]])[0]
    saved_state(store, source)
    result = graph(store)
    working = [node for node in result["nodes"] if node["region"] == "working"]
    assert len(working) == 3
    assert all(node["masked"] and node["details"] == {} and node["recorded_at"] is None for node in working)
    for count in (1, 2, 3, 4):
        small = graph(store, max_nodes=count, max_edges=1)
        assert all(node["masked"] for node in small["nodes"] if node["region"] == "working")
        assert "Plan the library visit" not in json.dumps(small)
    revealed = graph(store, include_sensitive=True)
    assert all(not node["masked"] and node["sensitive"] for node in revealed["nodes"] if node["region"] == "working")


def test_map_does_not_write_state_and_restore_uses_current_brain_identities(store):
    source = store.observe("Plan a visit.")
    saved_state(store, source)
    before = store.rows("memory_working_states")
    first = graph(store)
    assert store.rows("memory_working_states") == before
    store.restore(store.export())
    restored = graph(store)
    assert {node["kind"] for node in restored["nodes"]} >= {"working_state", "working_item", "open_loop"}
    assert {node["id"] for node in first["nodes"] if node["region"] == "working"}.isdisjoint(
        node["id"] for node in restored["nodes"] if node["region"] == "working")
    assert all(edge["source"] in {node["id"] for node in restored["nodes"]} and
               edge["target"] in {node["id"] for node in restored["nodes"]} for edge in restored["edges"])


def test_oversized_documents_and_previews_are_explicitly_bounded(store):
    source = store.observe("Plan a visit.")
    document = saved_state(store, source)
    item = {**document["items"][0], "value": "x" * 4096}
    saved_state(store, source, items=[item], loops=[])
    item_node = next(node for node in graph(store)["nodes"] if node["kind"] == "working_item")
    assert len(item_node["details"]["text"]) == 2048 and item_node["details"]["text_truncated"]
    item["value"] = "x" * 65536
    saved_state(store, source, items=[item], loops=[])
    result = graph(store)
    assert result["truncated"] and not any(node["region"] == "working" for node in result["nodes"])


def test_sensitive_note_outside_evidence_fetch_bound_still_masks_parent(store):
    secret = store_note(store.service, store.principal, store.brain_id,
                        {"request_id": uid(), "text": "private-branch-evidence", "kind": "constraint", "sensitive": True})
    with store.database.transaction(store.principal) as conn:
        brain = store.service._brain(conn, store.principal, store.brain_id)
        source = store.service._events(conn, store.principal, brain, event_ids=[secret["note_id"]])[0]
    document = saved_state(store, source)
    refs = [{**reference(source), "event_id": f"!unavailable-{index:03d}"} for index in range(64)] + [reference(source)]
    item = {**document["items"][0], "evidence_refs": refs}
    saved_state(store, source, items=[item], loops=[], branch="private-branch-name")
    result = graph(store, max_nodes=16)
    assert result["truncated"]
    assert "private-branch-name" not in json.dumps(result)
    assert all(node["masked"] for node in result["nodes"] if node["kind"] == "working_state")


def test_current_source_revision_and_cross_brain_scope_are_checked(store):
    key = uid()
    source = store.observe("Old visit plan.", key=key)
    saved_state(store, source)
    store.observe("The visit is cancelled.", key=key, revision=2)
    assert not any(node["kind"] in {"working_item", "open_loop"} for node in graph(store)["nodes"])
    original_brain = store.brain_id
    store.brain_id = store.service.create_brain(store.principal, "Another brain")["id"]
    foreign = store.observe("Foreign visit plan.")
    store.brain_id = original_brain
    saved_state(store, foreign)
    result = graph(store)
    assert not any(node["kind"] in {"working_item", "open_loop"} for node in result["nodes"])
    assert "Foreign visit plan" not in json.dumps(result)


def test_state_sampling_marks_omitted_branches_without_mutating_them(store):
    source = store.observe("Plan a visit.")
    for index in range(5):
        saved_state(store, source, branch=f"branch-{index}")
    result = graph(store, max_nodes=8)
    assert result["truncated"]
    assert len([node for node in result["nodes"] if node["kind"] == "working_state"]) == 1
    assert len(store.rows("memory_working_states")) == 5
