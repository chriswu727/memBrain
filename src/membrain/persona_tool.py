"""The persona tool the host AI calls: list the personality types, switch when the user asks (a request to reset the
persona is a switch too), and propose a change the user then confirms or declines in the conversation.

Switching is the user's own request, so it is done at once; it must cite the user's message, as notes do. A proposed
change waits for the user's answer, and the service will not apply it without a later user message
(``persona_growth.confirm_change`` states the rule). Every writing action is refused, with nothing sent, while
recording is paused; listing still works.

Confirming with the current message: hooks record a turn when it ends, so the yes the AI cites is usually not recorded
yet. The tool finds that message's staged turn and sends its conversation, so the service refuses at once a yes that
cannot answer a question asked in that conversation (``NOT_HERE``) instead of keeping it waiting. A confirmation the
service keeps waiting is remembered here, by ids only (``pending_notice``): if the turn ends without the change being
saved (the message was not recorded, or did not pass the rule when it was), the AI is told once, at the next
per-message context or session notice, that the proposal is still open.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

ACTIONS = ("list", "switch", "propose", "confirm", "decline")
WRITES = ("switch", "propose", "confirm", "decline")
TOOL_DESCRIPTION = (
    "The companion persona: how you present yourself to this user. One persona, one relationship: switching or "
    "changing it never resets the mood or familiarity. action list: the sixteen personality types (id such as intj, "
    "label, summary) and which one is current. action switch with preset (a type, in any case, or random for a "
    "different one): only when the user asked in this conversation to switch; that request is enough, do not ask "
    "again. When the user asks to reset their persona, that means switch with random, or with the type they name. "
    "action propose with "
    "changes and a short reason: values, traits or boundaries are lists of phrases to ADD to the card (a behaviour "
    "goes in values as one sentence), voice is an object of short phrases (register, length, emoji, language), "
    "name and baseline_mood replace; only when the user "
    "explicitly asks you to behave differently from now on ('be more patient from now on') or keeps asking for "
    "something the persona does not say, beyond what the manner-feedback tool records (too long, too formal, more "
    "jokes, emoji). Never propose a change on your own taste. Nothing changes until the user says yes: describe the "
    "change in a sentence and ask; when they clearly say yes in a later message, call confirm with the proposal_id; "
    "when they say no, call decline and do not propose the same change again in this conversation. Cite the user's "
    "message for switch and confirm (and for propose when a message prompted it): source_messages from the current "
    "membrain-source block, or source_event_ids for an earlier recorded message; never invent a source. Writing "
    "actions are refused while recording is paused.")
NOTES = {
    "list": "Tell the user the choices in a sentence or two, in their language, and which one is current.",
    "switch": ("Switched. Tell the user in a sentence, in their language, and present yourself this way from now on. "
               "The mood and familiarity carried over unchanged."),
    "unchanged": "That persona is already the current one; nothing changed.",
    "propose": ("Nothing has changed yet. Describe this change to the user in one sentence, in their language, and ask "
                "whether they want it. When they clearly say yes in their next message, call this tool with action "
                "confirm, this proposal_id and that message as the source; when they say no, call decline."),
    "confirmed": "Saved as a new persona version. Tell the user briefly; present yourself this way from now on.",
    "waiting_for_message": ("Not saved yet: the new persona version is saved when this turn is recorded and shows from "
                            "the next message. Tell the user briefly that it takes effect from their next message (not "
                            "that it is already saved), and present yourself this way now."),
    "decline": ("Declined; nothing changed. Do not propose the same change again in this conversation. The user can "
                "still change the persona themselves on the memory page."),
}
PAUSED = "Recording is paused, so the persona is not changed. Nothing was saved."


def refusal(directory: Path, action, user_id=None, recording_capture=None) -> dict | None:
    """Why a call is refused before anything is sent: an unknown action, or a writing action while recording is
    paused. Hosts that open a client for each call ask this first, so a paused user gets this answer whether or not
    the service is running."""
    from . import host
    from .host_recording import capture_marker

    if action not in ACTIONS:
        return {"error": f"action must be one of {', '.join(ACTIONS)}."}
    if action in WRITES and host.paused(directory, user_id, marker=capture_marker(recording_capture)):
        return {"error": PAUSED}
    return None


def _cited(source_event_ids, source_messages) -> bool:
    return bool(list(source_event_ids or ()) or list(source_messages or ()))


def run(directory: Path, client, action, *, preset=None, changes=None, reason=None, proposal_id=None,
        source_event_ids=(), source_messages=(), user_id=None, recording_capture=None) -> dict:
    """The persona tool (``memory_persona``, ``membrain_persona``, ``membrain plugin tool persona``). Errors come back
    to the AI as ``error``."""
    import httpx

    refused = refusal(directory, action, user_id, recording_capture)
    if refused:
        return refused
    sources = {"source_event_ids": list(source_event_ids or ()), "source_messages": list(source_messages or ())}
    if action in ("switch", "confirm") and not _cited(**sources):
        return {"error": ("Cite the user's message that asked for this: source_messages from the current "
                          "membrain-source block, or source_event_ids. Nothing was saved.")}
    try:
        if action == "list":
            return {**client.persona_presets(), "note": NOTES["list"]}
        if action == "switch":
            saved = client.switch_persona_preset(preset, **sources)
            choice = saved.get("choice") or {}
            return {"current": choice, "version": saved.get("version"), "unchanged": saved.get("unchanged"),
                    "note": NOTES["unchanged" if saved.get("unchanged") else "switch"]}
        if action == "propose":
            result = client.propose_persona_change(changes, reason=reason, **sources)
            proposal = result.get("proposal") or {}
            return {"proposal_id": proposal.get("id"), "changes": proposal.get("changes"), "note": NOTES["propose"]}
        if action == "confirm":
            exchange, conversation = (staged_turn(directory, sources["source_messages"][0], user_id, recording_capture)
                                      if len(sources["source_messages"]) == 1 and not sources["source_event_ids"]
                                      else (None, None))
            result = client.confirm_persona_change(
                proposal_id, **sources, **({"conversation_id": conversation} if conversation else {}))
            status = result.get("status")
            if status == "waiting_for_message" and exchange is not None:
                _remember(directory, user_id, proposal_id, exchange)
            return {"status": status, "version": (result.get("persona") or {}).get("version"), "note": NOTES[status]}
        client.decline_persona_change(proposal_id)
        return {"status": "declined", "note": NOTES["decline"]}
    except httpx.HTTPStatusError as error:
        try:
            rejected = error.response.json()["error"]
            return {"error": rejected["message"], "code": rejected["code"]}
        except (ValueError, KeyError, TypeError):
            raise error from None


# A confirmation waiting for the current message -------------------------------------------------------------------
# The staged turn of the cited message gives its conversation (sent with the confirmation) and its exchange handle
# (``host_outcomes``), kept with the proposal id until the turn's outcome is known. Ids and digests only, never text.

PENDING_SECONDS = 7 * 24 * 3600  # A turn whose outcome is still unknown after this is given up silently.
PENDING_KEPT = 8
NOT_APPLIED = ("Your confirmation of the persona change was not applied (the user's answer could not be used as "
               "evidence). The proposal is still open: ask again and confirm after their yes.")
_EXCHANGE = re.compile(r"[a-f0-9]{32}\.[a-f0-9]{64}")


def _ledgers(directory: Path, capture) -> list[Path]:
    """The capture's own session ledger first, then the most recently written ones (as ``host_outcomes.recent``)."""
    from .host_outcomes import RECENT_SESSIONS
    from .host_recording import capture_marker

    root = Path(directory) / "plugin" / "sessions"
    found = []
    try:
        with os.scandir(root) as entries:
            for item in entries:
                if re.fullmatch(r"[a-f0-9]{32}\.json", item.name):
                    try:
                        found.append((item.stat().st_mtime, item.name))
                    except OSError:
                        continue
    except OSError:
        return []
    found.sort(reverse=True)
    marker = capture_marker(capture)
    names = ([marker + ".json"] if marker else []) + [name for _, name in found[:RECENT_SESSIONS]]
    return [root / name for name in dict.fromkeys(names)]


def staged_turn(directory: Path, reference, user_id=None, recording_capture=None) -> tuple[str | None, str | None]:
    """(exchange handle, conversation) of this owner's staged turn whose user message is ``reference``; the
    conversation only while the turn is unfinished. (None, None) when no such turn is kept here: then the service
    applies only its own rule, and nothing is followed up."""
    from . import host_outcomes

    try:
        producer, key = reference["producer_ref"], reference["source_event_key"]
        if not isinstance(producer, str) or not isinstance(key, str) or reference.get("source_revision") != 1:
            return None, None
        identity = host_outcomes.identity(user_id, producer, key)
        for path, state in host_outcomes._read_stored(directory, _ledgers(directory, recording_capture)):
            turns = state.get("turns") if isinstance(state, dict) else None
            entry = turns.get(identity) if isinstance(turns, dict) else None
            if not isinstance(entry, dict) or entry.get("owner") != user_id or entry.get("source") != key:
                continue
            record = entry.get("record") if not entry.get("done") else None
            conversation = record.get("conversation_id") if isinstance(record, dict) else None
            return f"{path.stem}.{identity}", conversation if isinstance(conversation, str) else None
    except Exception:  # A lookup aid: without it the service still checks the rule when the message is recorded.
        pass
    return None, None


def _pending_file(directory: Path, user_id, *, create: bool = True) -> Path:
    """Beside the off-the-record dates: the installation's own file, or one per memory owner."""
    from .host import state_directory, user_brain_id

    root = state_directory(directory) if create else Path(directory) / "plugin"
    if user_id is None:
        return root / "persona-confirmations.json"
    folder = root / "persona-confirmations-users"
    if create:
        folder.mkdir(mode=0o700, exist_ok=True)
    return folder / (user_brain_id(user_id) + ".json")


def _pending(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = value.get("pending") if isinstance(value, dict) else None
    return [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("proposal_id"), str)
            and 0 < len(entry["proposal_id"]) <= 200 and isinstance(entry.get("exchange"), str)
            and _EXCHANGE.fullmatch(entry["exchange"]) and type(entry.get("at")) in (int, float)
            ] if isinstance(entries, list) else []


def _keep(directory: Path, user_id, entries: list[dict]) -> None:
    from .host import _write_state

    if entries:
        _write_state(_pending_file(directory, user_id), {"pending": entries[-PENDING_KEPT:]})
    else:
        _pending_file(directory, user_id, create=False).unlink(missing_ok=True)


def _remember(directory: Path, user_id, proposal_id: str, exchange: str) -> None:
    """Keep a confirmation the service is waiting on. Bookkeeping: it never fails the tool call."""
    from .host import log, state_directory
    from .local_profile import profile_lock

    try:
        with profile_lock(state_directory(directory) / "session-state-lock", timeout=5):
            entries = [entry for entry in _pending(_pending_file(directory, user_id, create=False))
                       if (entry["proposal_id"], entry["exchange"]) != (proposal_id, exchange)]
            _keep(directory, user_id, [*entries, {"proposal_id": proposal_id, "exchange": exchange,
                                                  "at": round(time.time(), 3)}])
    except Exception as error:
        log(directory, f"persona confirmation not kept: {type(error).__name__}")


def _recorded(outcome: dict) -> bool | None:
    """Whether the confirming message was recorded (True), will never be (False), or is not known yet (None)."""
    status = outcome.get("status")
    if status in ("erased", "not_found"):
        return False
    if status != "observed":
        return None  # Still staged (``awaiting_completion``), or the ledger is busy or unreadable.
    state = next((item.get("state") for item in outcome.get("messages") or () if item.get("role") == "user"), None)
    return True if state == "recorded" else False if state in ("excluded", "failed") else None


def pending_notice(directory: Path, client, user_id=None) -> str:
    """The one-time line for confirmations the service waited on that ended without the change: the confirming
    message's turn is settled (recorded, or it never will be) and the proposal is still open. A settled entry is
    removed whether or not it is reported, so the line is given once; a proposal decided otherwise (saved, declined,
    replaced, accepted or rejected on the page) is dropped silently. Empty when there is nothing to say; never fails
    the context it is part of."""
    from . import host_outcomes
    from .host import log, state_directory
    from .local_profile import profile_lock

    try:
        path = _pending_file(directory, user_id, create=False)
        if not path.exists():
            return ""
        entries, settled, failed, proposals = _pending(path), [], [], None
        for entry in entries:
            if time.time() - entry["at"] > PENDING_SECONDS:
                settled.append(entry)
                continue
            if _recorded(host_outcomes.lookup(directory, exchange=entry["exchange"], user_id=user_id)) is None:
                continue
            if proposals is None:
                proposals = {item.get("id"): item for item in client.persona_proposals().get("proposals") or ()}
            item = proposals.get(entry["proposal_id"]) or {}
            settled.append(entry)
            if item.get("kind") == "host" and item.get("status") == "open" and entry["proposal_id"] not in failed:
                failed.append(entry["proposal_id"])
        if not settled:
            return ""
        with profile_lock(state_directory(directory) / "session-state-lock", timeout=5):
            done = {(entry["proposal_id"], entry["exchange"]) for entry in settled}
            _keep(directory, user_id, [entry for entry in _pending(path)
                                       if (entry["proposal_id"], entry["exchange"]) not in done])
        if not failed:
            return ""
        return NOT_APPLIED + " " + " ".join(f"proposal_id: {ident}." for ident in failed)
    except Exception as error:  # The line is a courtesy; it never costs the turn its context.
        log(directory, f"persona confirmation check failed: {type(error).__name__}")
        return ""


def forget_pending(directory: Path, user_id=None) -> None:
    """Remove this owner's waiting confirmations, with their memory (``host.erase_user``)."""
    _pending_file(directory, user_id, create=False).unlink(missing_ok=True)
