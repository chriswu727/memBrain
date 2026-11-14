import copy
import hashlib
import json
import unicodedata
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


def display_zone():
    """The time zone of dates and times written for the host AI: this computer's own (None), which is the user's,
    since memBrain runs on their computer. Tests replace this function to fix the zone."""
    return None


def local_date(value) -> str:
    """The user's calendar date (YYYY-MM-DD) of a recorded time, for text written for the host AI.

    Records and API fields keep UTC, so a message recorded on a Friday evening west of UTC carries Saturday's UTC
    date. A bare date (one the user gave) is returned as it is; text that is not a time is cut to ten characters."""
    text = str(value or "")
    if len(text) <= 10:
        return text
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:10]
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(display_zone()).date().isoformat()


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


# Bounded identifier, counter, digest and event-reference checks for stored records.
def _identifier(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 256
            or any(character.isspace() or unicodedata.category(character).startswith("C")
                   for character in value)):
        raise DomainError("validation_failed", "Identifiers must be bounded and contain no whitespace or controls.")
    return value


def _integer(value, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise DomainError("validation_failed", "Counter is outside its permitted range.")
    return value


def _hash(value):
    if (not isinstance(value, str) or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)):
        raise DomainError("validation_failed", "Fingerprint must be a SHA-256 digest.")
    return value


def _refs(value):
    if not isinstance(value, list) or len(value) > 64:
        raise DomainError("validation_failed", "A turn may reference at most 64 events per group.")
    result = []
    for ref in value:
        if not isinstance(ref, dict) or set(ref) != {"event_id", "revision"}:
            raise DomainError("validation_failed", "Event references contain only an identifier and revision.")
        checked = {"event_id": _identifier(ref["event_id"]), "revision": _integer(ref["revision"], 1)}
        if checked in result:
            raise DomainError("validation_failed", "Event references must be distinct.")
        result.append(checked)
    return result
