"""The host AI reports the user's feedback on its manner.

Whether a user has commented on how the assistant talks ("too long", "less formal please") is a judgement the host
AI can make in any language; a table of phrasings cannot. The tool below passes that judgement, with the message
it rests on, to the service, where it is counted with the user's other feedback under the unchanged rules of
``persona_growth``. Nothing is sent while recording is paused.
"""
from __future__ import annotations

from pathlib import Path

KINDS = ("less_formal", "more_formal", "more_playful", "shorter", "longer", "less_emoji", "more_emoji")
TOOL_DESCRIPTION = (
    "Record that the user gave you feedback on how you talk or behave, only when they actually said so: too long "
    "(shorter), too short or too thin (longer), too formal or stiff (less_formal), too casual (more_formal), too "
    "serious or more jokes please (more_playful), fewer emoji (less_emoji), more emoji (more_emoji). Never record "
    "your own guess about what they might like, a comment about someone else, role-play or a quotation, and skip "
    "comments that fit none of these kinds. Cite the message it came from: source_messages from the current "
    "membrain-source block, or source_event_ids for earlier recorded messages; never invent a source. One kind per "
    "call. memBrain counts it with the user's other feedback; after three, the user can accept or reject a change "
    "to the persona on their memory page. Keep doing what the user asked in the conversation itself.")


def report(directory: Path, client, kind, *, source_event_ids=(), source_messages=(), user_id=None,
           recording_capture=None) -> dict:
    """The ``memory_manner_feedback`` tool: pass a report of the user's feedback on the companion's manner to the
    service (``persona_growth.report_feedback``), unless recording is paused; then nothing is sent or stored.
    Errors come back to the AI as ``error``."""
    import httpx

    from . import host
    from .host_recording import capture_marker

    if host.paused(directory, user_id, marker=capture_marker(recording_capture)):
        return {"error": "Recording is paused, so manner feedback is not recorded. Nothing was saved."}
    try:
        result = client.report_manner_feedback(kind, source_event_ids=list(source_event_ids or ()),
                                               source_messages=list(source_messages or ()))
    except httpx.HTTPStatusError as error:
        try:
            rejected = error.response.json()["error"]
            return {"error": rejected["message"], "code": rejected["code"]}
        except (ValueError, KeyError, TypeError):
            raise error from None
    return {**result, "note": ("Recorded with the user's other feedback on your manner. Keep following what they "
                               "asked in this conversation; any change to the persona is the user's decision on "
                               "their memory page.")}
