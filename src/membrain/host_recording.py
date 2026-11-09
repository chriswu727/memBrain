"""Capture-time recording policy; replay never refreshes a record's revision."""

import json
import re
from secrets import compare_digest

from .client import MemoryActionError
from .helpers import digest
from .local_profile import profile_lock

CAPTURE_FIELD = {"recording_capture": {
    "type": "string", "maxLength": 130,
    "description": "Copy recording_capture from this turn's membrain-source block. Never reuse another turn's value."}}


def save_note(directory, client, text, *, recording_capture=None, user_id=None, **fields):
    import httpx

    from .notes import save_note as write

    try:
        revision = note_revision(directory, client, recording_capture, user_id)
        return write(client, text, expected_recording_revision=revision, **fields)
    except ValueError as error:
        return {"error": str(error)}
    except MemoryActionError as error:
        if error.code not in ("recording_paused", "recording_stale"):
            raise
        return {"error": str(error), "code": error.code}
    except httpx.HTTPStatusError as error:
        try:
            rejected = error.response.json()["error"]
        except (ValueError, KeyError, TypeError):
            raise error
        if not isinstance(rejected, dict) or rejected.get("code") not in ("recording_paused", "recording_stale"):
            raise
        return {"error": rejected["message"], "code": rejected["code"]}


def note_capture(session, record, nonce):
    from .host_turns import key

    if not nonce:
        return None
    return ".".join((digest(["session", session])[:32], key(record), nonce))


def note_revision(directory, client, capture, user_id=None):
    from .host import paused, state_directory

    if not isinstance(capture, str) or not re.fullmatch(r"[a-f0-9]{32}\.[a-f0-9]{64}\.[a-f0-9]{32}", capture):
        raise ValueError("Saving memory requires recording_capture from the original turn's membrain-source block.")
    marker, identity, nonce = capture.split(".")
    root = state_directory(directory)
    with profile_lock(root / "session-state-lock", timeout=5):
        if paused(directory, user_id):
            raise ValueError("Recording is paused. Resume before saving agent notes.")
        try:
            state = json.loads((root / "sessions" / (marker + ".json")).read_text(encoding="utf-8"))
            entry = state["turns"][identity]
            valid = (entry["owner"] == user_id and not entry.get("paused")
                     and compare_digest(entry.get("note_capture", ""), nonce))
            recording = entry.get("recording")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            valid, recording = False, None
        if not valid:
            raise ValueError("The original turn's recording permission is unavailable or revoked. Do not retry with another turn's capture.")
        return captured_revision(client, recording)


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
