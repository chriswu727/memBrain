import json
import math
from contextvars import ContextVar
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError, validators

from .helpers import DomainError

CONTRACT_VERSION = "1.0.0-draft"


@lru_cache
def schema() -> dict:
    development = Path(__file__).resolve().parents[2] / "architecture/memory-contract.schema.json"
    source = development if development.is_file() else files("membrain").joinpath(
        "resources/memory-contract.schema.json"
    )
    return json.loads(source.read_text(encoding="utf-8"))


_LOCAL = "#/$defs/"
# Draft 2020-12 keywords whose values are subschemas: a map of them, one of them, or a list of them.
_SCHEMA_MAPS = {"$defs", "properties", "patternProperties", "dependentSchemas"}
_SCHEMA_ONE = {"not", "if", "then", "else", "contains", "items", "additionalProperties", "propertyNames",
               "unevaluatedItems", "unevaluatedProperties", "contentSchema"}
_SCHEMA_LISTS = {"allOf", "anyOf", "oneOf", "prefixItems"}
# Keywords that change how references resolve or which dialect applies below them.
_SCOPE = {"$schema", "$id", "$anchor", "$dynamicAnchor", "$dynamicRef", "$recursiveAnchor", "$recursiveRef"}
_PROPERTY_CHECKS = ContextVar("contract_property_checks", default=None)
_PROPERTIES = Draft202012Validator.VALIDATORS["properties"]


def _property_key(value):
    if type(value) is not dict or not 4 <= len(value) <= 64:
        return None
    parts, size = [], 0
    for key, item in value.items():
        kind = type(item)
        if type(key) is not str or kind not in (str, bool, int, float, type(None)):
            return None
        if kind is float and not math.isfinite(item) or kind is int and item.bit_length() > 64:
            return None
        size += len(key) + (len(item) if kind is str else 8)
        if size > 2048:
            return None
        parts.append((key, kind, item))
    return tuple(sorted(parts))


def _properties_once(validator, properties, instance, schema):
    checked = _PROPERTY_CHECKS.get()
    key = _property_key(instance) if checked is not None and len(properties) >= 4 else None
    identity = (id(schema), key)
    if key is not None and identity in checked:
        return
    failed = False
    for error in _PROPERTIES(validator, properties, instance, schema):
        failed = True
        yield error
    # Only completed property checks of identical plain JSON values can be reused inside one validation.
    # All other keywords still run, and scoped/dynamic schemas use the unmodified validator.
    if key is not None and not failed and len(checked) < 512:
        checked.add(identity)


_MemoizedValidator = validators.extend(Draft202012Validator, {"properties": _properties_once})


def _local(value) -> str | None:
    """The name of the definition a subschema consisting only of ``{"$ref": "#/$defs/<name>"}`` names."""
    if isinstance(value, dict) and len(value) == 1 and isinstance(value.get("$ref"), str):
        name = value["$ref"].removeprefix(_LOCAL)
        if name != value["$ref"] and name and not {"/", "~", "%"} & set(name):
            return name
    return None


def _subschemas(root) -> list[dict]:
    """Every schema object reachable from ``root`` through subschema keywords, once each."""
    found, pending, seen = [], [root], set()
    while pending:
        current = pending.pop()
        if isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, dict) and id(current) not in seen:
            seen.add(id(current))
            found.append(current)
            for key, value in current.items():
                if key in _SCHEMA_MAPS and isinstance(value, dict):
                    pending.extend(value.values())
                elif key in _SCHEMA_ONE or key in _SCHEMA_LISTS:
                    pending.append(value)
    return found


@lru_cache
def _linked_definitions() -> dict | None:
    """The definitions, with every subschema that is only ``{"$ref": "#/$defs/X"}`` replaced by definition X itself,
    so that validation descends into X directly instead of resolving the reference again on every use.

    That is the same validation: X is in the same document; a schema whose only keyword is $ref applies exactly
    the referenced schema; and no definition sets a base URI, an anchor, a dialect or a dynamic reference (if one
    did, this returns None and the plain definitions are used). Only subschema positions change, never values such
    as const, enum or default, and errors keep their instance paths. The result has cycles where definitions are
    recursive, so it is only ever given to validators, never serialized; nothing changes it after this.
    """
    import copy

    definitions = copy.deepcopy(schema()["$defs"])
    nodes = [node for value in definitions.values() for node in _subschemas(value)]
    if any(_SCOPE & node.keys() for node in nodes):
        return None

    def target(value):
        names = set()
        while (name := _local(value)) is not None and name not in names and name in definitions:
            names.add(name)
            value = definitions[name]
        return value

    for node in nodes:
        for key, value in node.items():
            if key in _SCHEMA_MAPS and key != "$defs" and isinstance(value, dict):
                for name, inner in value.items():
                    value[name] = target(inner)
            elif key in _SCHEMA_ONE:
                node[key] = target(value)
            elif key in _SCHEMA_LISTS and isinstance(value, list):
                value[:] = [target(inner) for inner in value]
    return definitions


@lru_cache
def validator(definition: str | None = None) -> Draft202012Validator:
    document = schema()
    linked = _linked_definitions() if definition is not None else None
    if definition is not None:
        document = {
            "$schema": document["$schema"],
            "$defs": linked or document["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    implementation = _MemoizedValidator if linked is not None else Draft202012Validator
    return implementation(document, format_checker=FormatChecker())


def validate(definition: str | None, value: object) -> None:
    token = _PROPERTY_CHECKS.set(set())
    try:
        validator(definition).validate(value)
    except ValidationError as error:
        path = ".".join(map(str, error.absolute_path)) or "$"
        raise DomainError("validation_failed", f"Invalid {definition or 'contract'} at {path}") from error
    finally:
        _PROPERTY_CHECKS.reset(token)
