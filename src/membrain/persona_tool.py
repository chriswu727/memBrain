"""The persona tool the host AI calls: list the personality types, switch when the user asks (a request to reset the
persona is a switch too), and propose a change the user then confirms or declines in the conversation.

Switching is the user's own request, so it is done at once; it must cite the user's message, as notes do. A proposed
change waits for the user's answer, and the service will not apply it without a later user message
(``persona_growth.confirm_change`` states the rule). Every writing action is refused, with nothing sent, while
recording is paused; listing still works.
"""
from __future__ import annotations

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
    "waiting_for_message": ("Confirmed. The new persona version is saved when this turn is recorded, so it shows from "
                            "the next message. Tell the user briefly and present yourself this way now."),
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
            result = client.confirm_persona_change(proposal_id, **sources)
            status = result.get("status")
            return {"status": status, "version": (result.get("persona") or {}).get("version"), "note": NOTES[status]}
        client.decline_persona_change(proposal_id)
        return {"status": "declined", "note": NOTES["decline"]}
    except httpx.HTTPStatusError as error:
        try:
            rejected = error.response.json()["error"]
            return {"error": rejected["message"], "code": rejected["code"]}
        except (ValueError, KeyError, TypeError):
            raise error from None
