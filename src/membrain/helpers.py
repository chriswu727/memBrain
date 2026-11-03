import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    principal_id: str


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        current_revision: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.current_revision = current_revision

    def as_dict(self) -> dict:
        result = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.current_revision is not None:
            result["current_revision"] = self.current_revision
        return result


def uid() -> str:
    return str(uuid4())


# Set only by evaluation_clock.enable() in a disposable evaluation profile; None (the wall clock) everywhere else.
_scenario_clock = None


def now() -> str:
    moment = _scenario_clock() if _scenario_clock is not None else datetime.now(UTC)
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def today() -> date:
    """The local date, from the same clock as ``now()``."""
    return _scenario_clock().astimezone().date() if _scenario_clock is not None else date.today()


def digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def deep_copy(value: Any, memo: dict | None = None) -> Any:
    """``copy.deepcopy``, faster for JSON data: plain dicts and lists are copied directly, strings, numbers,
    booleans and None are shared as deepcopy shares them, and anything else is handed to deepcopy. Objects reached
    twice are copied once, so shared parts and cycles come out exactly as deepcopy makes them."""
    kind = type(value)
    if kind is dict or kind is list:
        if memo is None:
            memo = {}
        found = memo.get(id(value))
        if found is not None:
            return found
        if kind is dict:
            result = memo[id(value)] = {}
            for key, item in value.items():
                inner = type(item)
                result[key if type(key) is str else deep_copy(key, memo)] = (
                    item if (inner is str or inner is int or inner is float or inner is bool
                             or item is None) else deep_copy(item, memo))
        else:
            result = memo[id(value)] = []
            for item in value:
                inner = type(item)
                result.append(item if (inner is str or inner is int or inner is float or inner is bool
                                       or item is None) else deep_copy(item, memo))
        return result
    if kind is str or kind is int or kind is float or kind is bool or value is None:
        return value
    return copy.deepcopy(value, memo)
