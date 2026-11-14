import copy

import pytest
from jsonschema import Draft202012Validator
from test_applicability import AT, holds, observation

from membrain.applicability import (
    CONDITION_SCHEMA,
    NEW_CONDITION_SCHEMA,
    evaluate_applicability,
    validate_condition,
    validate_new_condition,
    validate_observation,
)

UNRESOLVED = {"op": "unresolved", "label": "银色状态"}
LEGACY = {"op": "eq", "key": "user_defined_state", "value": "silver"}


@pytest.mark.parametrize("expression", [
    LEGACY,
    {**LEGACY, "op": "ne"},
    {"op": "not", "arg": LEGACY},
    {"op": "any", "args": [{"op": "always"}, LEGACY]},
    {"op": "all", "args": [holds(), {"op": "not", "arg": LEGACY}]},
])
def test_legacy_condition_remains_readable_but_cannot_be_new_model_output(expression):
    before = copy.deepcopy(expression)
    validate_condition(expression)
    assert Draft202012Validator(CONDITION_SCHEMA).is_valid(expression)
    assert not Draft202012Validator(NEW_CONDITION_SCHEMA).is_valid(expression)
    with pytest.raises(ValueError, match="Invalid condition"):
        validate_new_condition(expression)
    assert expression == before


def test_historical_free_key_conditions_do_not_prove_current_context():
    result = evaluate_applicability(LEGACY, [observation()], at=AT)
    assert result.value == "unknown"
    assert result.reasons == ("legacy_condition",)
    assert not result.supporting_observation_ids


def test_unresolved_label_is_never_implicitly_mapped_to_a_registered_concept():
    expression = {"op": "unresolved", "label": "备考"}
    validate_new_condition(expression)
    result = evaluate_applicability(expression, [observation()], at=AT)
    assert result.value == "unknown"
    assert result.reasons == ("unresolved_condition",)
    assert not result.supporting_observation_ids


@pytest.mark.parametrize("expression", [
    {"op": "unresolved", "label": ""},
    {"op": "unresolved", "label": "x" * 513},
    {"op": "unresolved", "label": "silver", "value": True},
    {"op": "unresolved", "label": "silver", "predicate_ref": {"id": "core.emotion", "version": 1}},
    holds("activity:silver"),
    holds(value={"type": "string", "value": "silver"}),
])
def test_unknown_concept_cannot_invent_a_registry_mapping_or_untyped_value(expression):
    with pytest.raises(ValueError):
        validate_new_condition(expression)


@pytest.mark.parametrize("changes", [
    {"value": UNRESOLVED},
    {"value": {"type": "unresolved", "label": "银色状态"}},
    {"value": {"type": "concept", "id": "activity:silver"}},
    {"predicate_ref": {"id": "user_defined_state", "version": 1}},
])
def test_unresolved_condition_is_not_a_registered_current_state_observation(changes):
    with pytest.raises(ValueError):
        validate_observation(observation(**changes))
