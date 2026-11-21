"""Forgetting what the user asks to have forgotten, as one call of a host's forget tool.

In a real-host trial (2026-11-19) the user said "Forget what I told you about pnpm. I don't want that kept." The host
looked the tool up, passed the note's id from the notes block as a "memory" with a scope generation of 0, got a bare
HTTP 422, looked the generation up, passed the id again as a memory and was told "completed" with nothing erased: a
note is an event, not a memory. The note and the message stayed. The tool asked for the low-level contract (a kind,
a mode, a scope generation), and the way to use it was written only in a skill that hosts do not read.

Here the host passes what it has: ids of notes (from the notes block) or of messages (from a search with ids), or a
few words about what to forget, which only lists candidates and erases nothing. What one id sweeps along:

- A note: the note, the notes it replaced, and the messages it was drawn from (with the reply to each). A message
  is kept when erasing it would also erase a current note the call did not name (the same message said something
  else that has a note of its own, or the reply to it did): the answer names that message and the note, and says how
  to erase it too. Nothing the user did not point at is erased without being named first.
- A message: the message, the reply to it, and every note drawn from either (with the notes those replaced): a
  deletion reaches everything derived from it, as on the memory page.

What each record takes with it is read from the service's timeline with ``erasure`` (``erased_with``: the same walk
of the dependency table the erasure itself takes, ``erasure.dependent_events``, and the one the memory page's
question before a delete reads), so the tool's plan, its answer, the page and the erasure cannot disagree. Everything
derived (feelings, cues, lineage, archived copies) goes with the erasure itself (``erasure.apply_erasure``). Only the
service's public reads and its ``forget`` action are used.
"""
from __future__ import annotations

from .client import MemoryActionError
from .helpers import local_date
from .notes import NOTES_CONVERSATION, list_notes, matching_notes
from .privacy import neutralize, scrub

TOOL_DESCRIPTION = (
    "Forget something for good when the user asks. Pass ids: a note's id from the notes block (the messages it was "
    "drawn from and the notes it replaced go with it) or a message's id from a search with ids (the notes drawn from "
    "it go with it). Without an id, pass query, a few words about it: you get candidates and nothing is erased; then "
    "call again with the right ids, asking the user first if more than one could be meant. Tell the user what the "
    "answer's message says.")
IDS_FIELD = {"type": "array", "items": {"type": "string"}, "maxItems": 20,
             "description": "Ids of notes (from the notes block) or messages to forget."}
QUERY_FIELD = {"type": "string", "description": "A few words about what to forget, when you have no id."}
MAX_IDS = 20
CANDIDATES = 5
_RESERVED = "membrain-"  # Conversations memBrain keeps for its own records (notes, feelings, persona, ...).
_STARTS = 80
_STOP_USING = "Do not keep using it from earlier in this conversation."


def _chunks(values, size):
    values = list(values)
    return [values[start:start + size] for start in range(0, len(values), size)]


class OlderService(Exception):
    """The service does not say what an erasure would take with it."""


def _visible(client, ids, *, erasure: bool = False) -> dict[str, dict]:
    """The current, stored messages and notes among ``ids`` (deleted, hidden and replaced ones are left out); with
    ``erasure`` each carries ``erased_with``, what deleting it alone would also erase."""
    found = {}
    for chunk in _chunks(dict.fromkeys(ids), 100):
        response = client.timeline(roles=("user", "assistant"), event_ids=chunk, max_characters=200_000,
                                   max_item_characters=_STARTS * 4, limit=100, **({"erasure": True} if erasure else {}))
        if erasure and any("erased_with" not in item for item in response.get("items", [])):
            raise OlderService()
        found.update({item["event_id"]: item for item in response.get("items", [])
                      if isinstance(item.get("event_id"), str)})
    return found


def _is_note(item) -> bool:
    return item.get("conversation_id") == NOTES_CONVERSATION


def _is_message(item) -> bool:
    return not str(item.get("conversation_id") or "").startswith(_RESERVED)


def _days(items) -> list[str]:
    return sorted({local_date(item.get("recorded_at")) for item in items if item.get("recorded_at")})


def _joined(parts) -> str:
    parts = list(parts)
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _counted(items, one: str, many: str) -> str:
    """"the note of 2026-11-19" or "the 2 notes of 2026-11-18 and 2026-11-19"."""
    days = _joined(_days(items)) or "an unknown day"
    return (one if len(items) == 1 else many).format(count=len(items), days=days)


def _starts(text: str) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= _STARTS:
        return neutralize(text)
    return neutralize(text[:_STARTS].rsplit(" ", 1)[0] + "…")


def plan(client, ids) -> dict:
    """What forgetting ``ids`` erases and keeps, read from the service; nothing is changed."""
    found = _visible(client, ids, erasure=True)
    notes = {key: found[key] for key in ids if key in found and _is_note(found[key])}
    messages = {key: found[key] for key in ids if key in found and _is_message(found[key])}
    missing = [key for key in ids if key not in notes and key not in messages]
    sources = [key for note in notes.values() for key in note.get("source_event_ids", []) if key not in messages]
    source_items = {key: item for key, item in _visible(client, sources, erasure=True).items() if _is_message(item)}

    def current_notes(items) -> set[str]:
        return {entry["event_id"] for item in items for entry in item["erased_with"] if entry.get("kind") == "note"}

    # A current note the call did not name, which erasing a named note's message would also erase, keeps that
    # message. Notes the named messages take with them anyway hold nothing back.
    going = set(notes) | current_notes(messages.values())
    kept, erased_sources = [], {}
    for key, item in source_items.items():
        others = [entry for entry in item["erased_with"] if entry.get("kind") == "note"
                  and entry["event_id"] not in going]
        if others:
            kept.append({"message": item, "notes": others})
        else:
            erased_sources[key] = item
    erased_messages = {**messages, **erased_sources}
    named = {*notes, *erased_messages}
    reached: dict[str, dict] = {}
    for item in [*notes.values(), *erased_messages.values()]:
        for entry in item["erased_with"]:
            if entry["event_id"] not in named:
                reached.setdefault(entry["event_id"], entry)

    def of(*kinds) -> dict[str, dict]:
        return {key: entry for key, entry in reached.items() if entry.get("kind") in kinds}

    replies = {key: entry for key, entry in of("message").items() if entry.get("actor_role") == "assistant"}
    known = ("note", "earlier_note", "hidden_note", "feeling")
    return {"notes": notes, "messages": messages, "missing": missing, "sources": erased_sources, "kept": kept,
            "replies": replies, "derived": of("note"), "earlier": of("earlier_note", "hidden_note"),
            "feelings": of("feeling"), "others": {key: entry for key, entry in reached.items()
                                                  if entry.get("kind") not in known and key not in replies},
            "unlinked": [note for note in notes.values() if not note.get("source_event_ids")],
            "erase": list(dict.fromkeys([*notes, *messages, *erased_sources]))}


def _summary(found: dict) -> str:
    """What was erased, by kind, count and day; never what it said."""
    notes = "it" if len(found["notes"]) == 1 else "they"
    messages = "it" if len(found["messages"]) + len(found["sources"]) == 1 else "them"
    parts = []
    if found["notes"]:
        parts.append(_counted(list(found["notes"].values()), "the note of {days}", "the {count} notes of {days}"))
    if found["earlier"]:
        parts.append(_counted(list(found["earlier"].values()), f"the earlier note {notes} replaced, of {{days}}",
                              f"the {{count}} earlier notes {notes} replaced, of {{days}}"))
    if found["sources"]:
        parts.append(_counted(list(found["sources"].values()), f"the message {notes} came from, said on {{days}}",
                              f"the {{count}} messages {notes} came from, said on {{days}}"))
    if found["messages"]:
        parts.append(_counted(list(found["messages"].values()), "the message of {days}",
                              "the {count} messages of {days}"))
    if found["derived"]:
        parts.append(_counted(list(found["derived"].values()), f"the note drawn from {messages}, of {{days}}",
                              f"the {{count}} notes drawn from {messages}, of {{days}}"))
    if found["replies"]:
        parts.append(f"your reply to {messages}" if len(found["replies"]) == 1
                     else f"your {len(found['replies'])} replies to {messages}")
    if found["feelings"]:
        parts.append("the feeling kept with it" if len(found["feelings"]) == 1
                     else f"the {len(found['feelings'])} feelings kept with them")
    if found["others"]:
        parts.append("1 other record resting on them" if len(found["others"]) == 1
                     else f"{len(found['others'])} other records resting on them")
    return "Forgotten for good: " + "; ".join(parts) + "."


def _kept_sentence(entry: dict) -> str:
    message, others = entry["message"], entry["notes"]
    day = local_date(message.get("recorded_at"))
    named = _joined([f"{local_date(note.get('recorded_at'))} (id: {note['event_id']})" for note in others])
    which, that = ("note", "that note") if len(others) == 1 else ("notes", "those notes")
    return (f"Kept the message of {day} it came from (id: {message['event_id']}), because it also supports your "
            f"{which} of {named}; it still holds what the user said. If they want it gone too, call memory_forget "
            f"with its id: that also erases {that}.")


def plain_error(error, fallback: str) -> str:
    """What a refused or failed service call says, as a sentence a host can repeat: the service's own message, never
    a bare HTTP status or a link (a host trial was shown "Client error '422 Unprocessable Entity' for url ... For more
    information check: https://developer.mozilla.org/...")."""
    import httpx

    reason = None
    if isinstance(error, MemoryActionError):
        reason = (error.response.get("error") or {}).get("message")
    elif isinstance(error, httpx.HTTPStatusError):
        try:
            detail = error.response.json()
            reason = (detail.get("error") or {}).get("message") if isinstance(detail, dict) else None
        except ValueError:
            reason = None
    elif isinstance(error, httpx.TransportError):
        reason = "Memory is not reachable right now."
    reason = " ".join(str(reason or "").split())
    if not reason:
        return fallback
    return reason if reason.endswith((".", "!", "?")) else reason + "."


def _failure(error, *, erased: bool) -> dict:
    """A refusal or failure as a sentence: never a bare HTTP status or a link."""
    if isinstance(error, MemoryActionError) and error.code == "version_conflict":
        reason = "memory changed while forgetting"
    else:
        reason = plain_error(error, "memory could not do it right now").rstrip(".")
    if erased:
        return {"outcome": "unconfirmed",
                "message": f"Memory erased what was asked, but could not confirm it ({reason}). Do not tell the user "
                           "it is gone until a later call confirms it. " + _STOP_USING}
    return {"outcome": "error", "message": f"Nothing was erased: {reason[:1].lower() + reason[1:]}. Try again in a "
                                          "moment."}


def _execute(client, ids, *, directory=None, user_id=None, forgotten=None, raise_unsent=False) -> dict:
    import httpx

    for attempt in range(2):
        found = plan(client, ids)
        if not found["erase"]:
            return _nothing(found, ids, forgotten)
        # The scope generation guards against another deletion between this plan and the erasure: the service
        # refuses the erasure if one happened, and the plan is made again once.
        generation = client.dashboard()["brain"]["scope_generation"]
        try:
            client.forget(found["erase"], kind="events", mode="erase_content", expected_scope_generation=generation)
            break
        except MemoryActionError as error:
            if error.code != "version_conflict" or attempt:
                raise
        except httpx.TransportError as error:
            if raise_unsent and isinstance(error, httpx.ConnectError):
                raise  # Nothing was sent.
            return {"outcome": "unknown",
                    "message": "Memory stopped answering during the erasure, so it is not known whether it was done. "
                               "Call memory_forget again with the same ids to check. " + _STOP_USING}
    gone = [*found["notes"], *found["derived"], *found["messages"], *found["sources"], *found["replies"]]
    if directory is not None:
        from . import host_recording

        try:  # The host's own copies (turn state, queued records) of what was erased.
            host_recording.status(directory, client, user_id)
        except Exception:
            pass  # The next hook does it.
    try:
        remaining = _visible(client, gone)
    except Exception as error:
        return _failure(error, erased=True)
    if forgotten is not None:
        forgotten.update([*found["notes"], *found["messages"]])
    result = {"outcome": "forgotten" if not remaining else "incomplete",
              "notes_erased": len(found["notes"]) + len(found["derived"]) + len(found["earlier"]),
              "messages_erased": len(found["messages"]) + len(found["sources"]) + len(found["replies"])}
    sentences = [_summary(found)]
    if remaining:
        sentences = [f"Memory reported the erasure, but {len(remaining)} of these records are still stored. Do not "
                     "tell the user they are gone; try again."]
    sentences += [_kept_sentence(entry) for entry in found["kept"]]
    if found["unlinked"]:
        sentences.append("The note had no linked message, so the user's own words may still be in their history: "
                         "to find them, call memory_forget with query.")
    if found["missing"]:
        sentences.append(_missing_sentence(found["missing"], forgotten))
    sentences.append(_STOP_USING)
    if found["kept"]:
        result["kept"] = [{"id": entry["message"]["event_id"], "said_on": local_date(entry["message"].get("recorded_at")),
                           "also_behind": [note["event_id"] for note in entry["notes"]]} for entry in found["kept"]]
    if found["missing"]:
        result["not_found"] = found["missing"]
    return {**result, "message": " ".join(sentences)}


def _missing_sentence(missing, forgotten) -> str:
    earlier = [key for key in missing if forgotten is not None and key in forgotten]
    unknown = [key for key in missing if key not in earlier]
    parts = []
    if earlier:
        parts.append(f"Already forgotten earlier in this conversation: {', '.join(earlier)}.")
    if unknown:
        parts.append(f"No note or message with the id {', '.join(unknown)} is stored now; it may have been forgotten "
                     "already.")
    return " ".join(parts)


def _nothing(found, ids, forgotten) -> dict:
    if forgotten is not None and all(key in forgotten for key in ids):
        return {"outcome": "already_forgotten", "not_found": list(ids),
                "message": "Nothing more was erased: this was already forgotten earlier in this conversation. "
                           + _STOP_USING}
    return {"outcome": "not_found", "not_found": list(ids),
            "message": "Nothing was erased. " + _missing_sentence(found["missing"], forgotten)
                       + " To find what the user means, call memory_forget with query: a few words about it."}


def search(client, query: str) -> dict:
    """Candidates for a description: current notes and messages it matches, with ids. Nothing is erased."""
    from . import host

    query = scrub(" ".join(query.split()))
    response = host.recall(client, query, deliberate=True)
    records = [record for record in host.recall_records(client, response)["records"]
               if not str(record.get("conversation_id") or "").startswith(_RESERVED)][:CANDIDATES]
    notes = matching_notes(list_notes(client), query, limit=CANDIDATES)
    candidates = [{"id": item["event_id"], "kind": "note", "date": local_date(item.get("recorded_at")),
                   "starts": _starts(sentence)} for item, _fields, sentence in notes]
    # A message a listed note was drawn from goes with that note, so it is not listed as a match of its own.
    with_notes = {key for item, _fields, _sentence in notes for key in item.get("source_event_ids", [])}
    records = [record for record in records if record["event_id"] not in with_notes]
    reaches = _visible(client, [record["event_id"] for record in records], erasure=True) if records else {}
    for record in records:
        behind = [entry["event_id"] for entry in (reaches.get(record["event_id"]) or {}).get("erased_with", [])
                  if entry.get("kind") == "note"]
        candidate = {"id": record["event_id"], "kind": "message",
                     "said_by": "user" if record.get("role") == "user" else "you", "date": record.get("recorded_at"),
                     "starts": _starts(record.get("text"))}
        if behind:
            candidate["notes_drawn_from_it"] = behind
        candidates.append(candidate)
    if not candidates:
        return {"outcome": "no_match", "candidates": [],
                "message": "Nothing was erased, and nothing in memory matches those words. Try other words (a name, "
                           "place, date or topic), or ask the user what they mean."}
    return {"outcome": "candidates", "candidates": candidates,
            "message": f"Nothing was erased yet. {len(candidates)} possible match"
                       f"{'' if len(candidates) == 1 else 'es'} below. Call memory_forget again with the id of what "
                       "the user meant; if more than one could be meant, ask the user first. Forgetting a note also "
                       "erases the messages it came from; forgetting a message also erases the notes drawn from it."}


def forget(client, ids=None, query=None, *, directory=None, user_id=None, forgotten=None,
           raise_unsent=False) -> dict:
    """One call of the host's forget tool. ``forgotten`` keeps the ids this connection has erased, so a second call
    for the same id says it was already forgotten instead of only "not found". With ``raise_unsent`` a connection that
    could not be made before anything was erased is raised, for a tool server that reconnects to its service and
    answers with its state (``mcp_server.create_server(pending=...)``)."""
    if isinstance(ids, str):  # One id, or a list some models send as JSON text.
        import json

        try:
            parsed = json.loads(ids)
        except ValueError:
            parsed = None
        ids = parsed if isinstance(parsed, list) else [ids]
    if ids is not None and (not isinstance(ids, list) or any(not isinstance(key, str) or not 1 <= len(key) <= 256
                                                              for key in ids)):
        return {"outcome": "refused", "message": "Nothing was erased: each id must be an id as the notes block or a "
                                                 "search shows it."}
    if query is not None and not isinstance(query, str):
        return {"outcome": "refused", "message": "Nothing was erased: query must be a few words of text."}
    ids = list(dict.fromkeys(key.strip() for key in ids or () if key.strip()))
    query = (query or "").strip()
    if ids and query:
        return {"outcome": "refused", "message": "Nothing was erased: pass either ids or query, not both."}
    if not ids and not query:
        return {"outcome": "refused", "message": "Nothing was erased: pass ids (a note's id from the notes block, or "
                                                 "a message's id) or query (a few words about what to forget)."}
    if len(ids) > MAX_IDS:
        return {"outcome": "refused", "message": f"Nothing was erased: pass at most {MAX_IDS} ids in one call."}
    if len(query) > 300:
        return {"outcome": "refused", "message": "Nothing was erased: keep query to a few words."}
    try:
        if query:
            return search(client, query)
        return _execute(client, ids, directory=directory, user_id=user_id, forgotten=forgotten,
                        raise_unsent=raise_unsent)
    except OlderService:
        return {"outcome": "error", "message": "Nothing was erased: the memory service is older than this tool and "
                                               "cannot say what forgetting would take with it. Update memBrain and "
                                               "try again."}
    except Exception as error:
        import httpx

        if not isinstance(error, (MemoryActionError, httpx.HTTPError)) or (
                raise_unsent and isinstance(error, httpx.ConnectError)):
            raise
        return _failure(error, erased=False)
