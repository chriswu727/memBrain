"""Queryable recording outcomes for host exchanges.

``host.finish_turn`` reports a recording receipt to its caller and then the receipt is gone. This module keeps the
last observation about each exchange so a user or host can look it up later, including after a process restart.

Outcomes live in the session's existing turn ledger (``plugin/sessions/*.json``), beside the staged-turn entry they
describe, so they share that ledger's owner, bounds, private files, expiry and erasure and add no second store:

* the completion callback writes its admission-time receipt in the same write that completes the turn;
* a later replay of the durable journal, in any process, replaces a message's entry with what the service answered;
* a callback that settled no ledger entry (unknown, repeated, ambiguous, or refused admission with nothing staged)
  is kept in a short per-session list and never changes the exchange it named.

An outcome is the last observation, not the present state. ``recorded`` says the service confirmed storage when it was
observed; a later deletion made elsewhere is not reflected. ``queued`` says journal admission was confirmed and server
storage was not: an answer that was lost may already be committed. Nothing here contains message text, and a lookup
only reads local files: it never contacts the service, replays the journal or changes a recording control.

Every ledger entry is bound to the recording target (account, brain, service and recovery epoch) its turn was captured
or observed under. A lookup returns anything about it, including that it was erased or is still awaiting completion,
only while the local profile still resolves to that target, and only to the owner (the installation's own memory, or
one user) whose turn it was; anything else is reported as not found.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from . import host_receipts, host_turns
from .helpers import digest

VERSION = "host-recording-outcome-v1"
MAX_CALLBACKS = 16  # Callbacks that settled no ledger entry, kept per session.
RECENT_SESSIONS = 32  # Session ledgers a listing without a session may read, newest first.
LOOKUP_LOCK_SECONDS = 2.0  # A lookup that cannot get the ledger lock reports the store as busy.
MAX_RECENT = 50
UNMATCHED = frozenset({"turn_not_staged", "turn_ambiguous", "turn_already_finished", "turn_mismatch"})
OBSERVERS = ("callback", "replay", "recovery")
_DETAILS = ("scope", "applies_to", "evidence", "event_id", "duplicate", "code", "retryable")
_EXCHANGE = re.compile(r"([a-f0-9]{32})\.([a-f0-9]{64})\Z")


def identity(owner: str | None, producer: str, source_event_key: str) -> str:
    """The ledger key of the exchange whose user message has this source key."""
    return host_turns.key({"_user": owner, "producer_ref": producer, "source_event_key": source_event_key})


def _marker(session: str) -> str:
    return digest(["session", session])[:32]


def exchange_id(session: str, turn_id: str, *, producer: str | None = None, user_id: str | None = None,
                roleplay: str | None = None) -> str:
    """A stable handle for one exchange, computable before the exchange is recorded. It is an address, not a
    credential: a lookup also requires the exchange's owner."""
    from . import host

    owner = host.roleplay_user(user_id, roleplay)
    return f"{_marker(session)}.{identity(owner, producer or host.PRODUCER, host._source_key(session, turn_id, 'user'))}"


# Writing (callers hold the session-state lock) ---------------------------------------------------------------------

def _stored(message: dict, now: float, by: str) -> dict:
    value = {"role": message["role"], "state": message["state"], "at": round(now, 3), "by": by}
    for name in ("reason", *_DETAILS):
        if message.get(name) is not None:
            value[name] = message[name]
    return value


def _find(state: dict, key: str | None):
    turns = state.get("turns")
    entry = turns.get(key) if isinstance(turns, dict) and key is not None else None
    return entry if isinstance(entry, dict) else None


def bound(entry: dict):
    """The recording target an entry belongs to: its outcome's, else the one its capture was stamped with, else
    the one the profile resolved to when it was staged. None only for turns older than any installation."""
    stored, recording = entry.get("outcome"), entry.get("recording")
    if isinstance(stored, dict) and stored.get("target") is not None:
        return stored["target"]
    if isinstance(recording, dict) and recording.get("target") is not None:
        return recording["target"]
    return entry.get("bound")


def settle(state: dict, *, owner: str | None, producer: str, receipt: dict, reason: str | None,
           target_of, now: float, by: str = "callback") -> None:
    """Keep what a completion callback (or abandoned-turn recovery) observed, in the ledger ``state`` the caller is
    about to write. ``target_of`` gives the recording target for a turn's stored capture (None without one).

    A callback that matched no unfinished turn is listed on its own; it must not overwrite the outcome of the
    exchange it named (a repeated callback would otherwise replace a confirmed result with ``unknown``).
    """
    messages = receipt["messages"]
    source = next((item["source"]["source_event_key"] for item in messages
                   if item["role"] == "user" and isinstance(item.get("source"), dict)), None)
    key = identity(owner, producer, source) if isinstance(source, str) else None
    stored = [_stored(item, now, by) for item in messages]
    entry = _find(state, key) if reason not in UNMATCHED else None
    if entry is not None and entry.get("owner") == owner:
        # The capture's own target first; a capture without one belongs to the profile it was staged under.
        target = target_of(entry.get("recording")) if entry.get("bound") is None else bound(entry)
        previous = entry.get("outcome")
        if isinstance(previous, dict) and previous.get("target") == target and isinstance(previous.get("messages"), list):
            # A retried callback re-admits the turn; what a replay already confirmed stays confirmed.
            confirmed = {item["role"]: item for item in previous["messages"]
                         if isinstance(item, dict) and item.get("state") == "recorded"}
            stored = [confirmed.get(item["role"], item) for item in stored]
        entry["outcome"] = {"target": target, "messages": stored}
        return
    callbacks = [item for item in state.get("callbacks", []) if isinstance(item, dict)]
    callbacks.append({"at": round(now, 3), "owner": owner, "producer": producer, "key": key, "source": source,
                      "target": target_of(None), "messages": stored})
    state["callbacks"] = callbacks[-MAX_CALLBACKS:]


def stored_ledger(path: Path) -> dict:
    """The session ledger as stored, or a new one; raises rather than replace a ledger that cannot be read."""
    return _read(path) or {}


def reference(record) -> dict | None:
    """Where a journal record's outcome belongs, without its text; None when it is not a host turn message."""
    try:
        role, session = record["role"], record["conversation_id"]
        source = record["source_event_key"] if role == "user" else record["parent_source_event_keys"][0]
        if role not in ("user", "assistant") or not isinstance(session, str) or not isinstance(source, str):
            return None
        owner = record.get("_user")
        return {"session": session, "owner": owner, "role": role,
                "key": identity(owner, record.get("producer_ref", "sdk"), source)}
    except Exception:
        return None


def _erased(entry: dict) -> bool:
    stored = entry.get("exclusion")
    return isinstance(stored, dict) and stored.get("reason") == "erased"


def _refine(stored: dict, role: str, message: dict, target: str | None, now: float, *, admitted: bool) -> bool:
    """Replace one message of a stored outcome with what a replay saw, if that is better evidence."""
    if not isinstance(stored, dict) or not isinstance(stored.get("messages"), list):
        return False
    if stored.get("target") not in (None, target):
        return False  # Observed against another account or brain: that owner's receipt is left as it was.
    for index, current in enumerate(stored["messages"]):
        if isinstance(current, dict) and current.get("role") == role:
            # Without a confirmed admission, only an admission that may have happened can have reached the journal.
            if not admitted and current.get("reason") != "admission_unconfirmed":
                return False
            # A server confirmation is the strongest evidence and is never replaced; an interrupted attempt only
            # refines a message that was still merely queued.
            if current.get("state") == "recorded" or (message["state"] == "queued" and current.get("state") != "queued"):
                return False
            stored["messages"][index] = _stored(message, now, "replay")
            if target is not None:
                stored["target"] = target
            return True
    return False


def _apply(state: dict, observation: dict, message: dict, target: str | None, now: float) -> bool:
    owner, role = observation["owner"], observation["role"]
    entry = _find(state, observation["key"])
    if entry is not None:
        if entry.get("owner") != owner or _erased(entry):
            return False
        # An unfinished turn stays unfinished: its callback failed, and only its uncertain admission is refined.
        return _refine(entry.get("outcome"), role, message, target, now, admitted=bool(entry.get("done")))
    for item in reversed(state.get("callbacks", []) if isinstance(state.get("callbacks"), list) else []):
        if isinstance(item, dict) and item.get("key") == observation["key"] and item.get("owner") == owner:
            return _refine(item, role, message, target, now, admitted=False)
    return False


def observe(directory: Path, observations: list[tuple[dict, dict]], target_of, *, now: float | None = None) -> int:
    """Record what a journal replay saw for each message it reached. The caller holds the replay lock, so an erasure
    cannot run between the service's answer and this write. Returns the number of messages updated."""
    from . import host
    from .local_profile import profile_lock

    grouped: dict[str, list[tuple[dict, dict]]] = {}
    for item, message in observations:
        grouped.setdefault(item["session"], []).append((item, message))
    now, updated, root = time.time() if now is None else now, 0, Path(directory) / "plugin"
    for session, items in grouped.items():
        path = root / "sessions" / (_marker(session) + ".json")
        with profile_lock(root / "session-state-lock", timeout=1):
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue  # The ledger expired or cannot be read; the observation has nowhere to go.
            if not isinstance(state, dict):
                continue
            changed = 0
            for item, message in items:
                try:
                    changed += _apply(state, item, message, target_of(item["owner"]), now)
                except Exception:
                    continue  # One damaged entry or unresolvable owner must not hide the others.
            if changed:
                host._write_session_marker(path, state)
                updated += changed
    return updated


def forget(state: dict, owner: str | None) -> None:
    """Remove one owner's outcomes from a ledger whose turns are being erased. Only the target an erased entry was
    bound to is kept, so the fact of its erasure stays inside that account and brain."""
    turns = state.get("turns")
    for entry in turns.values() if isinstance(turns, dict) else ():
        if isinstance(entry, dict) and entry.get("owner") == owner:
            target = bound(entry)
            entry.pop("outcome", None)
            if target is not None:
                entry["outcome"] = {"target": target}
    if "callbacks" in state:
        state["callbacks"] = [item for item in state["callbacks"] if isinstance(item, dict)
                              and item.get("owner") != owner] if isinstance(state["callbacks"], list) else []


# Reading (local files only) ----------------------------------------------------------------------------------------

def _missing() -> dict:
    return {"version": VERSION, "status": "not_found",
            "detail": "No retained outcome under this identity for this owner and recording target: it was never "
                      "observed here, has expired, or belongs to another scope."}


def _unavailable(reason: str) -> dict:
    return {"version": VERSION, "status": "unavailable", "reason": reason}


def _read(path: Path):
    """A ledger's content, ``None`` when it does not exist; raises when it cannot be read."""
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(state, dict):
        raise ValueError("A session ledger must be an object.")
    return state


def _read_stored(directory: Path, paths: list[Path]) -> list:
    """Each ledger's content (``None`` when absent, the error when unreadable), read while holding the ledger lock:
    on Windows an open reader would make a writer's atomic replacement fail. Creates nothing when none exists."""
    from .local_profile import profile_lock

    paths = [path for path in paths if path.exists()]
    if not paths:
        return []
    found = []
    with profile_lock(Path(directory) / "plugin" / "session-state-lock", timeout=LOOKUP_LOCK_SECONDS):
        for path in paths:
            try:
                found.append((path, _read(path)))
            except (OSError, ValueError) as error:
                found.append((path, error))
    return found


def _sources(producer, source):
    if not isinstance(source, str):
        return {"user": None, "assistant": None}
    user = {"producer_ref": producer, "source_event_key": source, "source_revision": 1}
    return {"user": user, "assistant": {**user, "source_event_key": source.removesuffix(":user") + ":assistant"}}


def _visible(bound, target) -> bool:
    return bound is None or (isinstance(bound, str) and bound == target)


def _messages(stored, references: dict) -> list[dict]:
    """Stored observations as validated receipt entries; raises when the stored value is damaged."""
    messages = []
    for item in stored:
        if type(item["at"]) not in (int, float) or item["by"] not in OBSERVERS:
            raise ValueError("Invalid observation.")
        details = {name: item[name] for name in _DETAILS if name in item}
        messages.append({**host_receipts.message(item["role"], references[item["role"]], item["state"],
                                                 item.get("reason"), **details),
                         "observed_at": item["at"], "observed_by": item["by"]})
    if not messages:
        raise ValueError("An outcome names at least one message.")
    return messages


def _callbacks(state: dict, key: str | None, owner, target) -> list[list[dict]]:
    """The validated messages of each unsettled callback that named this exchange, oldest first."""
    found = []
    for item in state.get("callbacks", []) if isinstance(state.get("callbacks"), list) else ():
        if (isinstance(item, dict) and item.get("owner") == owner and item.get("key") == key
                and _visible(item.get("target"), target)):
            try:
                found.append(_messages(item["messages"], _sources(item.get("producer"), item.get("source"))))
            except (KeyError, TypeError, ValueError):
                continue
    return found


def _observed(messages: list[dict], now: float) -> dict:
    latest = max(item["observed_at"] for item in messages)
    return {"messages": messages, "states": host_receipts.turn(messages)["states"], "observed_at": latest,
            "age_seconds": round(max(0.0, now - latest), 3), "basis": "last_observation"}


def _describe(marker: str, key: str | None, entry: dict | None, callbacks: list[list[dict]], target,
              now: float) -> dict:
    """One exchange's result from its ledger entry and the unsettled callbacks that named it."""
    from . import host

    result = {"version": VERSION, "exchange": f"{marker}.{key}" if key else None}
    if entry is not None and not _visible(bound(entry), target):
        entry = None  # Another account's or brain's turn: nothing about it is disclosed, not even its erasure.
    if entry is not None and _erased(entry):
        return {**result, "status": "erased",
                "detail": "This owner's memory was erased; the exchange's outcome was removed with it."}
    stored = entry.get("outcome") if entry is not None else None
    if isinstance(stored, dict):
        try:
            messages = _messages(stored["messages"], _sources(entry.get("producer"), entry.get("source")))
        except (KeyError, TypeError, ValueError):
            return {**result, **_unavailable("outcome_unreadable")}
        result.update(status="observed", completed=bool(entry.get("done")), **_observed(messages, now))
    elif entry is not None:
        if entry.get("done"):
            # Completed before outcomes were kept, or its outcome could not be written.
            return {**result, **_unavailable("outcome_not_retained")}
        result.update(status="awaiting_completion", completed=False)
        started = entry.get("started")
        if type(started) in (int, float):
            result.update(staged_at=started, age_seconds=round(max(0.0, now - started), 3))
        if entry.get("paused") and not (entry["paused"] == "prompt" and entry.get("resumed")):
            result["staged_exclusion"] = host._stored_exclusion(entry)  # Why it will not be recorded as staged.
    elif callbacks:
        result.update(status="observed", completed=False, **_observed(callbacks[-1], now))
        callbacks = callbacks[:-1]
    else:
        return _missing()
    if callbacks:
        # Callbacks that named this exchange without settling it; they never replace its outcome.
        result["unsettled_callbacks"] = [
            {"observed_at": max(item["observed_at"] for item in messages),
             "messages": [{name: item[name] for name in ("role", "state", "reason") if name in item}
                          for item in messages]} for messages in callbacks]
    return result


def lookup(directory: Path, *, exchange: str | None = None, session: str | None = None, turn_id: str | None = None,
           source_event_key: str | None = None, producer: str | None = None, user_id: str | None = None,
           roleplay: str | None = None, now: float | None = None) -> dict:
    """The retained recording outcome of one exchange, for its owner.

    Name the exchange by its ``exchange`` handle, or by ``session`` with the host's ``turn_id`` (or the user
    message's ``source_event_key``) and ``producer``. ``status`` is ``observed`` (with per-message states and when
    each was observed), ``awaiting_completion`` (staged; no completion callback seen), ``erased``, ``not_found`` or
    ``unavailable`` (the local store could not be read). Reads local files only.
    """
    from . import host, host_recording

    owner = host.roleplay_user(user_id, roleplay)
    if exchange is not None:
        matched = _EXCHANGE.match(exchange) if isinstance(exchange, str) else None
        if matched is None:
            raise ValueError("An exchange handle is 32 and 64 lowercase hexadecimal characters joined by a dot.")
        marker, key = matched.groups()
    else:
        if not isinstance(session, str) or not 1 <= len(session) <= 200:
            raise ValueError("Name the exchange by its handle, or by session with a turn or source key.")
        if isinstance(turn_id, str) and 1 <= len(turn_id) <= 120:
            source_event_key = host._source_key(session, turn_id, "user")
        if not isinstance(source_event_key, str) or not 1 <= len(source_event_key) <= 600:
            raise ValueError("Name the exchange by its handle, or by session with a turn or source key.")
        marker, key = _marker(session), identity(owner, producer or host.PRODUCER, source_event_key)
    from .local_profile import LocalProfileBusy

    try:
        stored = _read_stored(directory, [Path(directory) / "plugin" / "sessions" / (marker + ".json")])
    except LocalProfileBusy:
        return _unavailable("store_busy")
    except OSError:
        return _unavailable("store_unreadable")
    state = stored[0][1] if stored else None
    if isinstance(state, Exception):
        return _unavailable("store_unreadable")
    if state is None:
        return _missing()
    target = host_recording.local_target(directory, owner)
    entry = _find(state, key)
    if entry is not None and entry.get("owner") != owner:
        entry = None
    return _describe(marker, key, entry, _callbacks(state, key, owner, target), target,
                     time.time() if now is None else now)


def recent(directory: Path, *, session: str | None = None, producer: str | None = None, user_id: str | None = None,
           roleplay: str | None = None, limit: int = 10, now: float | None = None) -> dict:
    """This owner's most recently observed exchanges, newest first: one session's, or without ``session`` those in
    the most recently written session ledgers (at most ``RECENT_SESSIONS`` are read). Reads local files only."""
    from . import host, host_recording

    if type(limit) is not int or not 1 <= limit <= MAX_RECENT:
        raise ValueError(f"A listing returns 1 to {MAX_RECENT} exchanges.")
    owner, root = host.roleplay_user(user_id, roleplay), Path(directory) / "plugin" / "sessions"
    now = time.time() if now is None else now
    unreadable = truncated = 0
    if session is not None:
        if not isinstance(session, str) or not 1 <= len(session) <= 200:
            raise ValueError("A session identifier is required.")
        paths = [root / (_marker(session) + ".json")]
    else:
        found = []
        try:
            with os.scandir(root) as entries:
                for item in entries:
                    if re.fullmatch(r"[a-f0-9]{32}\.json", item.name):
                        try:
                            found.append((item.stat().st_mtime, item.name))
                        except OSError:
                            continue
        except FileNotFoundError:
            pass
        except OSError:
            unreadable += 1
        found.sort(reverse=True)
        truncated = int(len(found) > RECENT_SESSIONS)
        paths = [root / name for _, name in found[:RECENT_SESSIONS]]
    from .local_profile import LocalProfileBusy

    target = host_recording.local_target(directory, owner)
    exchanges = []
    try:
        stored = _read_stored(directory, paths)
    except (LocalProfileBusy, OSError):
        stored, unreadable = [], unreadable + len(paths)
    for path, state in stored:
        if isinstance(state, Exception):
            unreadable += 1
            continue
        if state is None:
            continue
        turns = state.get("turns") if isinstance(state.get("turns"), dict) else {}
        for key, entry in turns.items():
            if (isinstance(entry, dict) and entry.get("owner") == owner
                    and producer in (None, entry.get("producer"))):
                exchanges.append(_describe(path.stem, key, entry, _callbacks(state, key, owner, target), target, now))
        # Callbacks that named no retained exchange are listed once per exchange; those that named none, each.
        unsettled = {"callbacks": [item for item in state.get("callbacks", [])
                                   if isinstance(item, dict) and item.get("key") not in turns
                                   and producer in (None, item.get("producer"))]
                     if isinstance(state.get("callbacks"), list) else []}
        for key in dict.fromkeys(item.get("key") for item in unsettled["callbacks"]
                                 if isinstance(item.get("key"), str)):
            exchanges.append(_describe(path.stem, key, None, _callbacks(unsettled, key, owner, target), target, now))
        for messages in _callbacks(unsettled, None, owner, target):
            exchanges.append(_describe(path.stem, None, None, [messages], target, now))
    exchanges = [item for item in exchanges if item["status"] in ("observed", "awaiting_completion")]
    exchanges.sort(key=lambda item: item.get("observed_at", item.get("staged_at", 0.0)), reverse=True)
    return {"version": VERSION, "exchanges": exchanges[:limit],
            "truncated": bool(truncated) or len(exchanges) > limit, "unreadable_sessions": unreadable,
            "retention": {"finished_exchanges_per_session": host_turns.MAX_FINISHED,
                          "unsettled_callbacks_per_session": MAX_CALLBACKS,
                          "session_ledger_days": host.SESSION_MARKER_SECONDS // 86400,
                          "sessions_read_without_a_session": RECENT_SESSIONS}}


def needs_attention(result: dict | None) -> bool:
    """Whether a lookup shows a message that was neither confirmed, queued nor deliberately excluded."""
    return isinstance(result, dict) and result.get("status") == "observed" and host_receipts.needs_attention(result)
