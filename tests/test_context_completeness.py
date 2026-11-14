import copy
from datetime import UTC, datetime, timedelta

import pytest
from test_cognition import STAMP, scope
from test_contextual_recall import UNBOUNDED, case

from membrain import cognition
from membrain.ontology import CORE_REGISTRY


def variant(observation, index):
    value = copy.deepcopy(observation)
    value["observation_id"] = f"observation-{index}"
    value["valid_during"] = {
        **copy.deepcopy(UNBOUNDED),
        "start": {"kind": "instant", "at": (datetime(2020, 1, 1, tzinfo=UTC) + timedelta(seconds=index)).isoformat()},
    }
    return value


def assess(memory, current):
    return cognition._memory_applicability(memory, current, scope(), current["working_event_metadata"], STAMP)


@pytest.mark.parametrize("first", ["positive", "negative"])
def test_direct_context_overflow_cannot_turn_a_truncated_side_into_a_decision(first):
    memory, _, current = case("conflict")
    first_index = 0 if first == "positive" else 1
    selected = current["context_observations"][first_index]
    contrary = current["context_observations"][1 - first_index]
    current["context_observations"] = [variant(selected, index) for index in range(128)] + [contrary]
    result = assess(memory, current)
    assert result["value"] == "unknown"
    assert "context_incomplete" in result["reasons"]
    assert result["evidence_refs"] == selected["evidence_refs"]


def test_model_generated_ids_do_not_make_duplicate_observations_consume_the_limit():
    memory, _, current = case("conflict")
    positive, negative = current["context_observations"]
    current["context_observations"] = [
        {**copy.deepcopy(positive), "observation_id": f"random-model-id-{index}"} for index in range(160)
    ] + [negative]
    result = assess(memory, current)
    assert result["value"] == "unknown" and result["conflict"]
    assert "context_incomplete" not in result["reasons"]
    assert {ref["event_id"] for ref in result["evidence_refs"]} == {"event-2", "event-3"}


@pytest.mark.parametrize("condition,expired,expected", [
    (None, False, "unknown"),
    ({"op": "eq", "key": "activity", "value": "exam_preparation"}, False, "unknown"),
    ({"op": "always"}, False, "true"),
    (None, True, "false"),
])
def test_incomplete_context_keeps_independent_unconditional_and_temporal_decisions(condition, expired, expected):
    memory, _, current = case()
    memory["condition_registry_fingerprint"] = CORE_REGISTRY.fingerprint
    if condition is not None:
        memory["conditions"] = condition
    if expired:
        memory["valid_during"] = {**copy.deepcopy(UNBOUNDED), "end": {"kind": "instant", "at": STAMP}}
    current["context_observations_complete"] = False
    result = assess(memory, current)
    assert result["value"] == expected
    if condition != {"op": "always"}:
        assert "context_incomplete" in result["reasons"]
    if expired:
        assert "expired" in result["reasons"]


def test_legacy_always_rule_requires_qualification_but_literal_captures_do_not():
    memory, _, current = case()
    memory["conditions"] = {"op": "always"}
    result = assess(memory, current)
    assert result["value"] == "unknown"
    assert "legacy_unqualified_rule" in result["reasons"]
    del memory["conditions"]
    assert assess(memory, current)["value"] == "true"


def test_fingerprinted_always_rule_and_contextual_value_do_not_require_observation_completeness():
    memory, _, current = case()
    memory["conditions"] = {"op": "always"}
    current["context_observations_complete"] = False
    memory["condition_registry_fingerprint"] = CORE_REGISTRY.fingerprint
    assert assess(memory, current)["value"] == "true"
    del memory["condition_registry_fingerprint"], memory["memory_id"], memory["valid_during"]
    assert assess(memory, current)["value"] == "true"


def test_fingerprinted_always_rule_still_requires_declared_validity():
    memory, _, current = case()
    memory["conditions"] = {"op": "always"}
    memory["condition_registry_fingerprint"] = CORE_REGISTRY.fingerprint
    del memory["valid_during"]
    result = assess(memory, current)
    assert result["value"] == "unknown"
    assert "validity_unstated" in result["reasons"]
    assert "legacy_unqualified_rule" not in result["reasons"]
