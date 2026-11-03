"""helpers.deep_copy must copy exactly as copy.deepcopy does: nothing mutable is shared with the original."""
import copy
from collections import OrderedDict
from datetime import UTC, datetime

from membrain.helpers import Principal, deep_copy
from membrain.service import MemoryService


def containers(value, found=None):
    found = {} if found is None else found
    if isinstance(value, (dict, list)) and id(value) not in found:
        found[id(value)] = value
        for item in value.values() if isinstance(value, dict) else value:
            containers(item, found)
    return found


def document():
    return {"memory_id": "m", "revision": 2, "score": 0.5, "pinned": False, "summary": None,
            "statement": "The library appointment is on Friday.",
            "evidence_refs": [{"event_id": "e", "event_revision": 1, "span": {"start": 0, "end": 4}}],
            "nested": [[1, [2, {"deep": ["x"]}]], {}], "unicode": "图书馆"}


def test_json_data_is_copied_equal_and_shares_no_container():
    original = document()
    result = deep_copy(original)
    assert result == original == copy.deepcopy(original)
    assert list(result) == list(original)  # key order is kept
    assert not containers(result).keys() & containers(original).keys()
    result["evidence_refs"][0]["span"]["end"] = 99
    result["nested"][0][1][1]["deep"].append("y")
    assert original == document()


def test_shared_parts_and_cycles_come_out_as_deepcopy_makes_them():
    part = {"x": [1]}
    value = {"a": part, "b": [part, part]}
    value["self"] = value
    result, expected = deep_copy(value), copy.deepcopy(value)
    assert result["a"] is result["b"][0] is result["b"][1] and result["self"] is result
    assert expected["a"] is expected["b"][0] and expected["self"] is expected
    assert result["a"] is not part and result is not value


def test_other_types_are_copied_by_deepcopy():
    inner = [1, 2]
    value = {"tuple": (inner, 3), "ordered": OrderedDict(k=[1]), "when": datetime(2026, 1, 1, tzinfo=UTC),
             "set": {1, 2}, "same": inner}
    result = deep_copy(value)
    assert result == copy.deepcopy(value)
    assert type(result["ordered"]) is OrderedDict and result["ordered"] is not value["ordered"]
    assert result["tuple"][0] is not inner and result["tuple"][0] is result["same"]
    result["ordered"]["k"].append(2)
    result["set"].add(3)
    assert value["ordered"]["k"] == [1] and value["set"] == {1, 2}


def test_a_rebound_document_shares_nothing_with_the_stored_one():
    stored = {**document(), "scope": {"conversation_id": "c", "branch_id": "main", "visibility": "private"},
              "disclosure_basis": {"dependency_generation": 1, "support_paths": [{
                  "permitted_scope": {"visibility": "private", "conversation_id": "c", "branch_id": "main"},
                  "dependency_generation": 1}]}}
    before = copy.deepcopy(stored)
    brain = {"id": "brain", "scope_generation": 3, "dependency_generation": 7}
    rebound = MemoryService(None)._rebind(stored, Principal("tenant", "owner"), brain)
    assert not containers(rebound).keys() & containers(stored).keys()
    rebound["evidence_refs"][0]["span"]["start"] = 3
    rebound["disclosure_basis"]["support_paths"][0]["permitted_scope"]["visibility"] = "shared"
    assert stored == before
    assert rebound["scope"]["scope_generation"] == 3 and rebound["disclosure_basis"]["dependency_generation"] == 7


def test_recalled_items_and_traces_share_nothing_with_the_memories_and_scope_given(monkeypatch):
    from test_belief_recall import scenario
    from test_cognition import STAMP, request, scope

    from membrain import cognition

    monkeypatch.setattr(cognition, "now", lambda: STAMP)
    sources, memories, current = scenario()
    given, bound = copy.deepcopy(memories), scope()
    result = cognition.recall(bound, request("routine"), memories, sources, current)
    assert result["items"] and result["recall_traces"]
    inputs = containers([memories, bound])
    copies = containers([result["scope"], [item["memory"] for item in result["items"]],
                         [[trace["scope"], trace["evidence_refs"]] for trace in result["recall_traces"]]])
    assert not inputs.keys() & copies.keys()
    for item in result["items"]:
        item["memory"]["evidence_refs"][0]["event_id"] = "changed"
    for trace in result["recall_traces"]:
        trace["scope"]["tenant_id"] = "changed"
    result["scope"]["brain_id"] = "changed"
    assert memories == given and bound == scope()


def test_non_json_keys_are_copied_with_their_shared_values():
    class Key:
        def __init__(self):
            self.parts = ["original"]

    key = Key()
    original = {key: key}
    result = deep_copy(original)
    copied_key = next(iter(result))
    assert copied_key is not key
    assert result[copied_key] is copied_key
    copied_key.parts.append("changed")
    assert key.parts == ["original"]
