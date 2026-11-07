import json
import math
import threading
from functools import lru_cache

from jsonschema import Draft202012Validator, FormatChecker, _format

from . import contracts

_KEYWORDS = {"$ref", "type", "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
             "minLength", "maxLength", "minimum", "maximum", "uniqueItems", "enum", "const",
             "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "format", "pattern", "description", "title"}
_PATTERNS = {"^[0-9a-f]{64}$", "^[a-f0-9]{64}$", "^[A-Z]{3}$",
             "^[A-Za-z][A-Za-z0-9_.:-]{0,127}$", "^[a-zA-Z][a-zA-Z0-9_]{0,63}$"}
_CHECK = FormatChecker.check
_DATETIME = getattr(_format, "is_datetime", None)
_MIN_RESPONSE_ITEMS = 16
_COMPILE_LOCK = threading.RLock()


class _Ineligible(Exception):
    pass


def _plain(value, depth=0, *, small_numbers=True):
    if depth > 64:
        return False
    kind = type(value)
    if kind is str or kind is bool or value is None:
        return True
    if kind is int:
        return not small_numbers or abs(value) <= 2**53
    if kind is float:
        return math.isfinite(value) and (not small_numbers or abs(value) <= 2**53)
    if kind is list:
        return all(_plain(item, depth + 1, small_numbers=small_numbers) for item in value)
    if kind is dict:
        return all(type(key) is str and _plain(item, depth + 1, small_numbers=small_numbers)
                   for key, item in value.items())
    return False


def _definitions_snapshot(definitions, dialect):
    try:
        return _encode_definitions(definitions, dialect)
    except Exception:  # noqa: BLE001 - unsupported schemas keep the existing Python validation path
        return None


def _encode_definitions(definitions, dialect):
    if type(definitions) is not dict or any(type(name) is not str for name in definitions):
        return None
    ids = {id(value): name for name, value in definitions.items() if type(value) is dict}

    def node(value, *, top=False, depth=0):
        if depth > 64:
            raise _Ineligible
        if type(value) is bool:
            return value
        if type(value) is not dict:
            raise _Ineligible
        if not top and id(value) in ids:
            return {"$ref": "#/$defs/" + ids[id(value)].replace("~", "~0").replace("/", "~1")}
        if any(type(key) is not str or key not in _KEYWORDS for key in value):
            raise _Ineligible
        if "$ref" in value and (len(value) != 1 or contracts._local(value) not in definitions):
            raise _Ineligible
        if "pattern" in value and value["pattern"] not in _PATTERNS:
            raise _Ineligible
        if "format" in value and value["format"] != "date-time":
            raise _Ineligible
        result = {}
        for key, child in value.items():
            if key in contracts._SCHEMA_MAPS:
                if type(child) is not dict or any(type(name) is not str for name in child):
                    raise _Ineligible
                result[key] = {name: node(inner, depth=depth + 1) for name, inner in child.items()}
            elif key in contracts._SCHEMA_ONE:
                result[key] = node(child, depth=depth + 1)
            elif key in contracts._SCHEMA_LISTS:
                if type(child) is not list:
                    raise _Ineligible
                result[key] = [node(inner, depth=depth + 1) for inner in child]
            elif _plain(child, small_numbers=False):
                result[key] = child
            else:
                raise _Ineligible
        return result

    document = {"$schema": dialect, "$defs": {
        name: node(value, top=True) for name, value in definitions.items()}, "$ref": "#/$defs/ActionResponse"}
    return json.dumps(document, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _same_validators(current, expected):
    return expected is not None and len(current._validators) == len(expected) and all(
        function is old_function and name is old_name and value is old_value
        for (function, name, value), (old_function, old_name, old_value)
        in zip(current._validators, expected, strict=True))


def _capture_containers(values):
    pending, seen, captured = list(values), set(), []
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if type(value) is dict:
            expected = tuple(value.items())
            captured.append((value, expected))
            pending.extend(item for _, item in expected)
        elif type(value) is list:
            expected = tuple(value)
            captured.append((value, expected))
            pending.extend(expected)
        else:
            rules = getattr(value, "_validators", None)
            if rules is not None:
                pending.append(rules)
    return tuple(captured)


def _unchanged(containers):
    for value, expected in containers:
        if len(value) != len(expected):
            return False
        if type(value) is dict:
            if any(key is not old_key or item is not old_item
                   for (key, item), (old_key, old_item) in zip(value.items(), expected, strict=True)):
                return False
        elif any(item is not old_item for item, old_item in zip(value, expected, strict=True)):
            return False
    return True


def _snapshot(current):
    root = contracts._prepared_root()
    if (root is None or type(current) is not type(root)
            or current.TYPE_CHECKER is not Draft202012Validator.TYPE_CHECKER
            or tuple(current.VALIDATORS.items()) != type(root)._membrain_keywords
            or root.schema is not type(root)._membrain_root_schema):
        return None
    definitions = root.schema["$defs"]
    if type(definitions) is not dict or current.schema is not definitions.get("ActionResponse"):
        return None
    checker = current.format_checker
    if (_DATETIME is None or type(checker) is not FormatChecker or type(checker.checkers) is not dict
            or checker.checkers.get("date-time") != (_DATETIME, ())
            or getattr(checker.check, "__func__", None) is not _CHECK
            or any(getattr(getattr(current, name), "__func__", None) is not method
                   for name, method in type(root)._membrain_methods)):
        return None
    snapshot = type(root)._membrain_schema
    if snapshot is None or not _unchanged(type(root)._membrain_containers):
        return None
    if not _same_validators(current, type(root)._membrain_validators.get(id(current.schema))):
        return None
    if any(type(child) is not type(root) or child.schema is not schema or child.format_checker is not root.format_checker
           or child._validators is not expected for child, schema, expected in type(root)._membrain_nodes):
        return None
    return snapshot


@lru_cache(maxsize=8)
def _compiled(snapshot):
    try:
        import jsonschema_rs

        Draft202012Validator.check_schema(json.loads(snapshot))
        return jsonschema_rs.Draft202012Validator(
            snapshot, formats={"date-time": _DATETIME}, validate_formats=True, offline=True,
        )
    except Exception:  # noqa: BLE001 - no unsupported or failed accelerator may bypass the reference validator
        return None


def accepts_response(current, value):
    try:
        if (type(value) is not dict or type(value.get("action")) is not str or value["action"] != "recall"
                or type(value.get("outcome")) is not str or value["outcome"] != "completed"):
            return False
        result = value.get("result")
        if type(result) is not dict or type(result.get("items")) is not list or len(result["items"]) < _MIN_RESPONSE_ITEMS:
            return False
        # Audit schema and prepared-rule mutations; never reuse validation of an instance.
        snapshot = _snapshot(current)
        if snapshot is None or not _plain(value):
            return False
        with _COMPILE_LOCK:
            candidate = _compiled(snapshot)
        return candidate is not None and candidate.is_valid(value)
    except Exception:  # noqa: BLE001 - the caller still runs the reference validator, including its exact errors
        return False
