"""Capture-time recording policy; replay never refreshes a record's revision."""

import json

from .client import MemoryActionError
from .helpers import digest
from .local_profile import profile_lock


def _target(client):
    http = getattr(client, "_http", None)
    return digest([client.brain_id, str(http.base_url) if http else None,
                   http.headers.get("Authorization") if http else None,
                   http.headers.get("X-Memory-Recovery-Epoch") if http else None])


def _valid(policy):
    return (isinstance(policy, dict) and type(policy.get("paused")) is bool
            and type(policy.get("revision")) is int and 0 <= policy["revision"] <= 2**53 - 1)


def status(directory, client=None, user_id=None):
    from .host import _write_state, log, state_directory

    root = state_directory(directory)
    path = root / "recording-policies" / (digest([user_id]) + ".json")

    def cached():
        try:
            policy = json.loads(path.read_text(encoding="utf-8"))
            if _valid(policy) and isinstance(policy.get("target"), str):
                return policy
        except FileNotFoundError:
            return {"paused": False, "revision": 0, "target": None}
        except (OSError, ValueError):
            pass
        return {"paused": True, "revision": 0, "target": None}

    reader = getattr(client, "recording_status", None)
    if not callable(reader):
        return cached()
    try:
        policy = reader()
        if not _valid(policy):
            raise ValueError("Invalid recording policy response.")
        policy = {"paused": policy["paused"], "revision": policy["revision"], "target": _target(client)}
        with profile_lock(root / "recording-policy-lock", timeout=5):
            previous = cached()
            if previous["target"] == policy["target"] and previous["revision"] > policy["revision"]:
                return previous
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _write_state(path, policy)
        return policy
    except Exception as error:
        log(directory, f"recording policy unavailable: {type(error).__name__}")
        return cached()


def stamp(record, policy):
    record["_recording"] = {"revision": policy["revision"], "target": policy["target"]}


def captured_revision(client, token):
    if (not isinstance(token, dict) or type(token.get("revision")) is not int
            or not 0 <= token["revision"] <= 2**53 - 1
            or token.get("target") not in (None, _target(client))):
        raise MemoryActionError({"error": {"code": "recording_stale", "retryable": False,
                                           "message": "The captured recording policy is unavailable for this target."}})
    return token["revision"]


def observe(client, record):
    values = {key: value for key, value in record.items() if key not in ("_user", "_recording")}
    revision = captured_revision(client, record.get("_recording", {"revision": 0, "target": None}))
    if callable(getattr(client, "recording_status", None)):
        values["expected_recording_revision"] = revision
    return client.observe(**values)


def notice(policy):
    if policy["paused"]:
        return ("Recording is paused by the memory service or its last known policy. New messages are not being "
                "remembered. Local resume cannot change this policy; reconnect and use the server recording "
                "controls to resume it explicitly.")
    return ""
