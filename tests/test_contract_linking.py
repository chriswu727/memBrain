"""Validators that reach definitions directly must accept and reject exactly what the plain contract does."""
import copy
import json
import random
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from test_belief_recall import recall, scenario
from test_cognition import STAMP, prepare_payload, scope, working

from membrain import cognition, contracts
from membrain.helpers import DomainError

SOURCE = Path(contracts.__file__).resolve().parents[2] / "architecture/memory-contract.schema.json"


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(cognition, "now", lambda: STAMP)


def plain(definition):
    document = json.loads(SOURCE.read_text(encoding="utf-8"))
    return Draft202012Validator({"$schema": document["$schema"], "$defs": document["$defs"],
                                 "$ref": f"#/$defs/{definition}"}, format_checker=FormatChecker())


def first_error(validator, value):
    error = next(validator.iter_errors(value), None)
    return None if error is None else list(error.absolute_path)


def paths(value, prefix=()):
    yield prefix
    if isinstance(value, dict):
        for key, item in value.items():
            yield from paths(item, (*prefix, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from paths(item, (*prefix, index))


def mutations(document, count, seed):
    """Deterministic broken copies: a field removed, retyped, given an unknown value or date, or an extra key."""
    rng, every = random.Random(seed), list(paths(document))[1:]
    for _ in range(count):
        broken, path = copy.deepcopy(document), rng.choice(every)
        parent = broken
        for key in path[:-1]:
            parent = parent[key]
        kind = rng.choice(["delete", "retype", "string", "date", "extra", "null"])
        if kind == "delete" and isinstance(parent, dict):
            del parent[path[-1]]
        elif kind == "retype":
            parent[path[-1]] = 7 if isinstance(parent[path[-1]], (list, str)) else []
        elif kind == "string":
            parent[path[-1]] = "not-a-valid-value"
        elif kind == "date":
            parent[path[-1]] = "2026-13-45T25:61:00Z"
        elif kind == "extra" and isinstance(parent[path[-1]], dict):
            parent[path[-1]]["unexpected_field"] = 1
        else:
            parent[path[-1]] = None
        yield broken


def documents():
    sources, memories, current = scenario(kind="exception")
    result = recall(sources, memories, current)
    packet = cognition.prepare(scope(), prepare_payload(), working(), result, current)
    envelope = {"message_type": "response", "contract_version": contracts.CONTRACT_VERSION, "request_id": "r",
                "action": "recall", "outcome": "completed", "server_scope": scope(), "result": result}
    return {"ActionResponse": envelope, "RecallResult": result, "ContextPacket": packet,
            "MemoryAssertion": memories[0], "Event": sources[0], "RecallTrace": result["recall_traces"][0]}


def test_definitions_are_linked_and_the_published_schema_is_unchanged():
    linked = contracts._linked_definitions()
    assert linked is not None
    assert contracts.schema() == json.loads(SOURCE.read_text(encoding="utf-8"))
    json.dumps(contracts.schema())  # still a plain, serializable document
    assert linked["RecallResult"]["properties"]["recall_traces"]["items"] is linked["RecallTrace"]


@pytest.mark.parametrize("definition", sorted(documents()))
def test_linked_validators_agree_with_the_plain_contract(definition):
    document = documents()[definition]
    linked, reference = contracts.validator(definition), plain(definition)
    assert first_error(linked, document) is None and first_error(reference, document) is None
    for index, broken in enumerate(mutations(document, 150, seed=definition)):
        assert first_error(linked, broken) == first_error(reference, broken), index


def test_every_definition_rejects_the_same_wrong_shapes():
    for definition in json.loads(SOURCE.read_text(encoding="utf-8"))["$defs"]:
        linked, reference = contracts.validator(definition), plain(definition)
        for value in (None, 1, 1.5, True, "x", [], [{}], {}, {"unexpected_field": 1}):
            assert first_error(linked, value) == first_error(reference, value), (definition, value)


def test_formats_are_still_enforced():
    trace = copy.deepcopy(documents()["RecallTrace"])
    contracts.validate("RecallTrace", trace)
    trace["recorded_at"] = "2026-13-45T25:61:00Z"
    with pytest.raises(DomainError, match="RecallTrace at recorded_at"):
        contracts.validate("RecallTrace", trace)


@pytest.fixture
def synthetic(monkeypatch):
    def use(document):
        monkeypatch.setattr(contracts, "schema", lambda: document)
        contracts._linked_definitions.cache_clear()
        contracts.validator.cache_clear()
    yield use
    contracts._linked_definitions.cache_clear()
    contracts.validator.cache_clear()


def test_only_subschema_positions_are_linked(synthetic):
    reference = {"$ref": "#/$defs/When"}
    synthetic({"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": {
        "When": {"type": "string", "format": "date-time"},
        "Alias": {"$ref": "#/$defs/When"},
        "Item": {"type": "object", "additionalProperties": False, "properties": {
            "at": dict(reference), "via": {"$ref": "#/$defs/Alias"}, "marker": {"const": dict(reference)},
            "noted": {"$ref": "#/$defs/When", "description": "kept as a reference"},
            "list": {"type": "array", "items": dict(reference)}, "either": {"anyOf": [dict(reference), {"type": "null"}]},
        }},
    }})
    linked = contracts._linked_definitions()
    item = linked["Item"]["properties"]
    assert item["at"] is linked["When"] and item["via"] is linked["When"]
    assert item["list"]["items"] is linked["When"] and item["either"]["anyOf"][0] is linked["When"]
    assert item["marker"] == {"const": reference} and item["noted"]["$ref"] == "#/$defs/When"
    contracts.validate("Item", {"at": "2026-01-01T00:00:00Z", "marker": reference, "list": [], "either": None})
    for wrong in ({"at": "yesterday"}, {"via": "2026-02-30T00:00:00Z"}, {"marker": {"$ref": "#/$defs/Item"}},
                  {"list": ["soon"]}, {"either": "later"}, {"noted": "never"}):
        with pytest.raises(DomainError):
            contracts.validate("Item", wrong)


def test_definitions_that_change_reference_scope_are_not_linked(synthetic):
    synthetic({"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": {
        "When": {"$id": "urn:example:when", "type": "string"},
        "Item": {"properties": {"at": {"$ref": "#/$defs/When"}}},
    }})
    assert contracts._linked_definitions() is None
    with pytest.raises(DomainError):
        contracts.validate("Item", {"at": 1})
