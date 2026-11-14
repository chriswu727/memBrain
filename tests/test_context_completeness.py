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
