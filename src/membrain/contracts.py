import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

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
    if definition is not None:
        document = {
            "$schema": document["$schema"],
            "$defs": _linked_definitions() or document["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    return Draft202012Validator(document, format_checker=FormatChecker())


def validate(definition: str | None, value: object) -> None:
    try:
        validator(definition).validate(value)
    except ValidationError as error:
        path = ".".join(map(str, error.absolute_path)) or "$"
        raise DomainError("validation_failed", f"Invalid {definition or 'contract'} at {path}") from error
