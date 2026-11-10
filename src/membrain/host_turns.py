"""Bounded turn state; callers hold the host's session-state lock while reading and writing it."""

import time
from secrets import token_hex

from .helpers import digest

MAX_ACTIVE = 64
MAX_FINISHED = 256


def key(record):
    return digest([record.get("_user"), record["producer_ref"], record["source_event_key"]])


def entries(state):
    turns = state.setdefault("turns", {})
    pending = state.pop("pending", None)
    paused = state.pop("paused_turn", False)
    resumed = state.pop("resumed_turn", False)
    if isinstance(pending, dict) or paused:
        if paused:
            state["turns_require_staging"] = True
        record = pending or {}
        entry = {"owner": record.get("_user", state.get("user_id")),
                 "producer": record.get("producer_ref"), "source": record.get("source_event_key"),
                 "paused": paused, "resumed": resumed, "started": state.pop("paused_at", time.time())}
        if pending:
            entry.update(record=pending, fingerprint=digest([pending["text"]]))
        turns[key(pending) if pending else "legacy-paused"] = entry
        state["turns_managed"] = True
    return turns


def compact(state):
    turns = entries(state)
    finished = [identity for identity, entry in turns.items() if entry.get("done")]
    for identity in finished[:-MAX_FINISHED]:
        del turns[identity]


def complete(entry):
    entry.pop("record", None)
    entry.pop("resumed", None)
    entry["done"] = True


def stage(state, record, paused, now, *, implicit=False):
    turns = entries(state)
    state["turns_managed"] = True
    if paused:
        state["turns_require_staging"] = True
    identity = key(record)
    existing = turns.get(identity)
    fingerprint = digest([record["text"]])
    if existing and not (implicit and existing.get("done")):
        if existing.get("fingerprint") != fingerprint:
            raise ValueError("A turn ID cannot identify different user messages.")
        if (paused or implicit) and not existing.get("done"):
            existing.pop("record", None)
            existing["paused"] = ("server" if paused == "server" or existing.get("paused") == "server"
                                  else True if implicit or existing.get("paused") is True else paused or True)
            existing.pop("resumed", None)
        return
    active = [entry for entry in turns.values() if not entry.get("done")]
    if len(active) >= MAX_ACTIVE:
        raise ValueError("Too many unfinished turns in this session; finish them or start a new session.")
    overlapping = [entry for entry in active
                   if entry["owner"] == record.get("_user") and entry["producer"] == record["producer_ref"]]
    for entry in overlapping:
        entry["needs_identity"] = True
    entry = {"owner": record.get("_user"), "producer": record["producer_ref"],
             "source": record["source_event_key"], "fingerprint": fingerprint, "started": now,
             "paused": paused, "needs_identity": bool(overlapping)}
    if "_recording" in record:
        entry["recording"] = record["_recording"]
    if not paused:
        entry["record"] = record
        entry["note_capture"] = token_hex(16)
    turns.pop(identity, None)
    turns[identity] = entry
    compact(state)


def take(state, *, owner, producer, source=None, prompt=None, allow_unstaged=False, legacy_source=None,
         outcome=None):
    """The staged turn to complete. ``outcome``, when given, receives why nothing is returned: a ``reason`` for an
    unmatched turn, or the stored ``exclusion`` of a paused one, plus the matched ``source``."""
    report = outcome if outcome is not None else {}
    turns = entries(state)
    candidates = [entry for entry in turns.values()
                  if (owner is None or entry["owner"] == owner)
                  and entry.get("producer") in (None, producer)]
    if source is not None:
        exact = [entry for entry in candidates if entry.get("source") == source]
        legacy = [entry for entry in candidates if legacy_source is not None and entry.get("source") == legacy_source]
        candidates = exact or legacy or [entry for entry in candidates if entry.get("source") is None]
    elif prompt is not None:
        fingerprint = digest([prompt["text"]])
        candidates = [entry for entry in candidates if entry.get("fingerprint") in (None, fingerprint)]
    else:
        candidates = [entry for entry in candidates if not entry.get("done")]
    if not candidates:
        active = any(not entry.get("done") and entry["owner"] == owner
                     and entry.get("producer") in (None, producer) for entry in turns.values())
        if (prompt is None or active or state.get("turns_require_staging")
                or (state.get("turns_managed") and not allow_unstaged)):
            report["reason"] = "turn_not_staged"
            return None, True, owner, False
        entry = {"owner": owner, "producer": producer, "source": prompt["source_event_key"],
                 "fingerprint": digest([prompt["text"]]), "done": True}
        turns[key(prompt)] = entry
        compact(state)
        return prompt, False, owner, False
    if len(candidates) != 1:
        report["reason"] = "turn_ambiguous"
        return None, True, owner, False
    entry = candidates[0]
    unidentified = not entry.get("done") and source is None and prompt is None and entry.get("needs_identity")
    if entry.get("source") and not unidentified:  # An unidentified callback must not borrow this turn's key.
        report["source"] = {"producer_ref": entry.get("producer") or producer, "source_event_key": entry["source"]}
    if entry.get("done") or unidentified:
        report["reason"] = "turn_already_finished" if entry.get("done") else "turn_ambiguous"
        stored = entry.get("exclusion")
        if entry.get("done") and isinstance(stored, dict) and stored.get("reason") == "erased":
            report["exclusion"] = dict(stored)
        return None, True, entry["owner"], bool(entry.get("paused"))
    if prompt is not None and entry.get("fingerprint") not in (None, digest([prompt["text"]])):
        report["reason"] = "turn_mismatch"
        return None, True, owner, False
    excluded = bool(entry.get("paused")) and not (entry["paused"] == "prompt" and entry.get("resumed"))
    if excluded:
        report["exclusion"] = dict(entry["exclusion"]) if isinstance(entry.get("exclusion"), dict) else None
        report["paused"] = entry["paused"]
    else:
        entry.pop("exclusion", None)  # A resumed turn is recorded; its earlier exclusion no longer describes it.
    record = entry.get("record")
    if record is None and not excluded and prompt is not None:
        record = {**prompt}
        if "recording" in entry:
            record["_recording"] = entry["recording"]
        else:
            record.pop("_recording", None)
        if entry.get("source"):
            record["source_event_key"] = entry["source"]
        if entry["owner"] is not None:
            record["_user"] = entry["owner"]
    if record is None and not excluded:
        report["reason"] = "message_unavailable"  # Sent while paused, resumed, but not supplied again.
    complete(entry)
    compact(state)
    return record, excluded, entry["owner"], bool(entry.get("paused"))
