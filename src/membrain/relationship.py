"""The relationship layer (``relationship``): shared moments, familiarity, boundaries and the commitment record.

What is stored here, and where:

- **Shared moments** are milestone notes flagged ``shared`` (``[milestone · shared] ...``): something the user and
  the companion did or reached together. They are notes, so they keep their sources, dates, editing and audited
  deletion; ``kind: relationship`` stays for lasting facts about the relationship that are not moments.
- **Support style, boundaries, a familiarity cap and acknowledgements of missed commitments** are records in a
  reserved conversation, with the ``system`` role, like persona versions and affect records: they are what the user
  asked for, not something anyone said, so they are never extracted into recalled memories, shown as history,
  counted as messages or scheduled for learning.
- **Familiarity is derived, never set**: distinct days with user messages and the number of shared moments, both
  counted after the latest reset marker, mapped to four levels by ``THRESHOLDS``. The user can cap it lower. A
  message's day is when it happened as its host reported it, never later than when it was recorded. A restored
  archive keeps a message's reported time but records it again, so messages without one count on the restore
  day (open: a restored brain must stay identical to its archive, so the restore cannot add records for this).
- **Commitments kept and missed** come from ``agent_commitment`` notes: done is kept; still open after its date is
  missed. A missed one is shown once in context and then acknowledged, so it is not repeated.

Reset erases the shared-moment notes, the support style, the boundaries, the cap and the acknowledgements with the
same audited deletion as notes, and writes a reset marker with the sequence it applies from. Nothing before the
marker counts again: not days of conversation, not moments, not commitments, and a moment read from messages
before it is refused its ``shared`` flag. Conversations themselves stay, so recall of what was said is unchanged.

This module has no model call and imports nothing heavy at load, so hooks can render the block.
"""
from __future__ import annotations

import datetime as _datetime
import json
import re
from collections.abc import Iterator

from .helpers import DomainError, uid
from .helpers import today as _clock_today
from .notes import _MONTHS, NOTES_CONVERSATION, OPEN_STATUSES, parse_note
from .privacy import neutralize, scrub

RELATIONSHIP_CONVERSATION = "membrain-relationship"
RELATIONSHIP_PRODUCER = "membrain-relationship"
# Restoring an exported archive keeps every record but files it under the import producer.
ARCHIVE_PRODUCER = "archive-import"
RESET = "reset"
LEVELS = ("new", "getting_to_know", "familiar", "close")
LEVEL_LABELS = {"new": "new", "getting_to_know": "getting to know", "familiar": "familiar", "close": "close"}
# (level, at least this many distinct days with user messages, at least this many shared moments). A level needs
# both; the highest level whose two thresholds are met applies. Counted after the latest reset marker only.
THRESHOLDS = (("getting_to_know", 3, 0), ("familiar", 14, 2), ("close", 45, 6))
SUPPORT_CHARACTERS = 200
TOPIC_CHARACTERS = 60
ALIAS_CHARACTERS = 40
MAX_ALIASES = 6
MAX_BOUNDARIES = 12
BOUNDARIES_CHARACTERS = 900  # The rendered boundaries line; a new boundary that would pass it is refused.
RELATIONSHIP_CHARACTERS = 2200  # The whole block, including its fixed header.
MOMENTS_IN_CONTEXT = 3
MAX_MOMENTS = 500
_VISIBLE = ("tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current AND NOT deleted AND NOT suppressed "
            "AND NOT retired AND document IS NOT NULL")
# Leading words dropped from a boundary topic before matching, so "my ex" matches "my ex texted" and "the ex".
_LEADING = re.compile(r"^(?:(?:my|our|the|a|an|about|his|her|their|your)(?:\s+|$))+", re.IGNORECASE)
_LEADING_ZH = re.compile(r"^(?:关于|我的|我们的)+")
_CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿가-힯]")


BOUNDARY_TOOL_DESCRIPTION = (
    "Save a boundary when the user asks you not to bring up a topic (\"please don't bring up my ex again\", "
    "\"别再提我前任了\"): topic in a few words and aliases for other words they use for it, in any language. Earlier "
    "messages about it are then left out of recalled memory unless the user raises it. It is not a pause: the "
    "conversation is still remembered. The user can remove it on the memory page.")


def _clean(value, scrubbing: bool = True) -> str:
    return " ".join((scrub(str(value)) if scrubbing else str(value)).split())


# Boundaries in recall --------------------------------------------------------------------------------------------

def boundary_terms(boundary: dict) -> list[str]:
    """The words a boundary is matched by: its topic without leading "my", "the", "关于" and so on, and its aliases."""
    terms = []
    for value in [boundary.get("topic") or "", *(boundary.get("aliases") or ())]:
        text = " ".join(str(value).split()).casefold()
        text = _LEADING_ZH.sub("", _LEADING.sub("", text)).strip()
        if text and text not in terms:
            terms.append(text)
    return terms


def _matches(term: str, text: str) -> bool:
    if _CJK.search(term):
        return term in text  # Chinese and Japanese are not written with spaces between words.
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?:s|es)?(?!\w)", text) is not None


def touches(text: str, boundaries) -> list[dict]:
    """The boundaries whose topic or an alias appears in ``text``: a whole-word, case-insensitive match, or a
    substring for Chinese and Japanese."""
    folded = " ".join(str(text or "").split()).casefold()
    if not folded:
        return []
    return [boundary for boundary in boundaries or () if any(_matches(term, folded) for term in boundary_terms(boundary))]


def kept_out(text: str, boundaries, current: str | None = None) -> bool:
    """True when ``text`` is about a boundary topic that the user's current message does not raise."""
    touched = touches(text, boundaries)
    if not touched:
        return False
    raised = {boundary.get("id") for boundary in touches(current or "", touched)}
    return any(boundary.get("id") not in raised for boundary in touched)


def shown(item: dict, boundaries) -> bool:
    """Whether a shared moment or a missed promise may be raised in context without the user raising it: not
    sensitive and not about a boundary topic. The page lists it either way."""
    return not item.get("sensitive") and not touches(item.get("text") or "", boundaries)


# Records --------------------------------------------------------------------------------------------------------

def _support(value, scrubbing: bool = True) -> str:
    if not isinstance(value, str):
        raise DomainError("validation_failed", "The support style is text.")
    text = _clean(value, scrubbing)
    if len(text) > SUPPORT_CHARACTERS:
        raise DomainError("validation_failed", f"Keep the support style under {SUPPORT_CHARACTERS} characters.")
    return text


def _boundary(topic, aliases=(), scrubbing: bool = True) -> dict:
    if not isinstance(topic, str) or not isinstance(aliases, (list, tuple)):
        raise DomainError("validation_failed", "A boundary is a topic and an optional list of other words for it.")
    topic = _clean(topic, scrubbing)
    if not topic or len(topic) > TOPIC_CHARACTERS:
        raise DomainError("validation_failed", f"A boundary topic is 1 to {TOPIC_CHARACTERS} characters.")
    kept = []
    for alias in aliases:
        alias = _clean(alias, scrubbing) if isinstance(alias, str) else None
        if alias is None or not alias or len(alias) > ALIAS_CHARACTERS:
            raise DomainError("validation_failed", f"Each other word for a boundary is 1 to {ALIAS_CHARACTERS} "
                                                   "characters.")
        if alias.casefold() != topic.casefold() and alias not in kept:
            kept.append(alias)
    if len(kept) > MAX_ALIASES:
        raise DomainError("validation_failed", f"A boundary has at most {MAX_ALIASES} other words.")
    if not boundary_terms({"topic": topic, "aliases": kept}):
        raise DomainError("validation_failed", "Name the topic itself, not only words like \"my\" or \"the\".")
    return {"topic": topic, "aliases": kept}


def _level(value) -> str | None:
    if value is not None and value not in LEVELS[:-1]:
        raise DomainError("validation_failed", "A familiarity cap is new, getting_to_know or familiar, or none.")
    return value


def _entry(row) -> dict | None:
    """A stored record or reset marker, or None for anything this module did not write or cannot accept."""
    document = row["document"]
    observed = document["observed"]
    if observed.get("actor_role") != "system" or row["producer_ref"] not in (RELATIONSHIP_PRODUCER, ARCHIVE_PRODUCER):
        return None
    imported = row["producer_ref"] == ARCHIVE_PRODUCER
    base = {"id": document["event_id"], "sequence": document["sequence"],
            "recorded_at": document["system_time"]["recorded_at"]}
    try:
        stored = json.loads(observed["content"].get("text") or "")
        if stored.get("relationship_marker") == RESET:
            removed = stored.get("removed") or {}
            return {**base, "marker": RESET, "applies_from_sequence": document["sequence"],
                    "removed": {key: int(removed.get(key, 0)) for key in (
                        "shared_moments", "boundaries", "support_style", "cap", "acknowledgements")}}
        kind = stored["relationship"]
        # Every record passes the checks of a new save; an archive is outside this module's control, so its records are
        # scrubbed again too. Anything that does not pass is ignored rather than trusted.
        if kind == "support_style":
            return {**base, "kind": kind, "text": _support(stored["text"], imported)}
        if kind == "boundary":
            return {**base, "kind": kind, **_boundary(stored["topic"], stored.get("aliases", []), imported)}
        if kind == "cap":
            return {**base, "kind": kind, "level": _level(stored.get("level"))}
        if kind == "acknowledged":
            return {**base, "kind": kind, "note_id": str(stored["note_id"])}
    except (ValueError, KeyError, TypeError, AttributeError, DomainError):
        return None
    return None


def _entries(service, conn, principal, brain_id) -> Iterator[dict]:
    with conn.cursor(name="relationship_" + uid()) as cursor:
        cursor.itersize = 256
        cursor.execute(
            f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
            "ORDER BY sequence", (*service._params(principal, brain_id), RELATIONSHIP_CONVERSATION))
        for row in cursor:
            entry = _entry(row)
            if entry is not None:
                yield entry


def _state(service, conn, principal, brain_id) -> dict:
    """The latest marker, the markers newest first, and the records after the latest marker."""
    markers, records = [], []
    for entry in _entries(service, conn, principal, brain_id):
        if "marker" in entry:
            markers.append(entry)
            records.clear()
        else:
            records.append(entry)
    after = markers[-1]["applies_from_sequence"] if markers else 0
    latest = {kind: next((entry for entry in reversed(records) if entry["kind"] == kind), None)
              for kind in ("support_style", "cap")}
    return {"marker": markers[-1] if markers else None, "markers": list(reversed(markers)), "after": after,
            "records": records, "support_style": latest["support_style"], "cap": latest["cap"],
            "boundaries": [entry for entry in records if entry["kind"] == "boundary"],
            "acknowledged": {entry["note_id"] for entry in records if entry["kind"] == "acknowledged"}}


def latest_marker(service, conn, principal, brain_id) -> dict | None:
    """The latest relationship reset marker; derived values count only events after ``applies_from_sequence``."""
    return _state(service, conn, principal, brain_id)["marker"]


def _notes(service, conn, principal, brain_id, kind: str, after: int, limit: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id,sequence,document->'observed'->'content'->>'text' AS text,"
        "document->'observed'->>'actor_role' AS actor_role,document->'system_time'->>'recorded_at' AS recorded_at,"
        "ARRAY(SELECT d.input_event_id FROM memory_event_dependencies d WHERE d.tenant_id=memory_events.tenant_id "
        "AND d.owner_id=memory_events.owner_id AND d.brain_id=memory_events.brain_id "
        "AND d.output_event_id=memory_events.id ORDER BY d.input_event_id) AS source_event_ids "
        f"FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s AND sequence>%s "
        "AND document->'observed'->'content'->>'text' LIKE %s ORDER BY sequence DESC LIMIT %s",
        (*service._params(principal, brain_id), NOTES_CONVERSATION, after, f"[{kind}%", limit)).fetchall()
    result = []
    for row in rows:
        fields, sentence = parse_note(row["text"] or "")
        if fields.get("kind") == kind:
            result.append({"id": row["id"], "sequence": row["sequence"], "text": sentence, "fields": fields,
                           "actor_role": row["actor_role"], "recorded_at": row["recorded_at"], "stored": row["text"],
                           "source_event_ids": list(row["source_event_ids"] or [])})
    return result


def _moments(service, conn, principal, brain_id, after) -> list[dict]:
    """Shared moments after the marker, oldest first by their date (or when they were saved)."""
    notes = _notes(service, conn, principal, brain_id, "milestone", after, 5 * MAX_MOMENTS)
    moments = [{"id": note["id"], "text": note["text"], "occurs_at": note["fields"].get("occurs_at"),
                "sensitive": bool(note["fields"].get("sensitive")), "recorded_at": note["recorded_at"],
                "written_by_user": note["actor_role"] == "user", "source_event_ids": note["source_event_ids"],
                "sequence": note["sequence"], "note_text": note["stored"]}
               for note in notes if note["fields"].get("shared")][:MAX_MOMENTS]
    return sorted(moments, key=lambda moment: ((moment["occurs_at"] or (moment["recorded_at"] or "")[:10]),
                                               moment["sequence"]))


def _date(value) -> _datetime.date | None:
    try:
        return _datetime.date.fromisoformat(value if len(value) == 10 else value + "-01") if value else None
    except (TypeError, ValueError):
        return None


def _commitments(service, conn, principal, brain_id, after, acknowledged, today) -> dict:
    """``agent_commitment`` notes after the marker: kept (done), missed (still open after its date), cancelled
    and open. A cancelled one is not counted as missed: the plan changed, the promise was not broken."""
    record = {"kept": [], "missed": [], "cancelled": [], "open": []}
    for note in reversed(_notes(service, conn, principal, brain_id, "agent_commitment", after, 1000)):
        fields = note["fields"]
        status = fields.get("status", "intended")
        when = _date(fields.get("due") or fields.get("occurs_at"))
        item = {"note_id": note["id"], "text": note["text"], "status": status, "due": fields.get("due"),
                "occurs_at": fields.get("occurs_at"), "recorded_at": note["recorded_at"],
                "sensitive": bool(fields.get("sensitive"))}
        if status == "done":
            record["kept"].append(item)
        elif status == "cancelled":
            record["cancelled"].append(item)
        elif status in OPEN_STATUSES and when is not None and when < today:
            record["missed"].append({**item, "acknowledged": note["id"] in acknowledged})
        elif status in OPEN_STATUSES:
            record["open"].append(item)
    return record


def _utc_day(value) -> str | None:
    """The UTC day of an ISO time (a time without a zone is read as UTC), or None when it is not one."""
    try:
        moment = _datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        moment = moment if moment.tzinfo else moment.replace(tzinfo=_datetime.UTC)
        return moment.astimezone(_datetime.UTC).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _days(service, conn, principal, brain_id, after) -> list[str]:
    """Distinct days (UTC) with a user message after the marker. Notes, messages written on the memory page and
    every reserved conversation are not conversation.

    A message's day is when it occurred as its host reported it, but never later than when it was recorded. With no
    reported time, it is the day it was recorded. A message restored from an archive was recorded when the original
    was (``restored_from_recorded_at``), not on the day of the restore, so a restore never folds its days into one."""
    rows = conn.execute(
        "SELECT DISTINCT left(document->'system_time'->>'recorded_at',10) AS recorded,"
        "left(document->'system_time'->>'restored_from_recorded_at',10) AS restored_from,"
        "document->'observed'->'occurred_time'->>'start' AS occurred FROM memory_events "
        f"WHERE {_VISIBLE} AND sequence>%s AND document->'observed'->>'event_kind'='message' "
        "AND document->'observed'->>'actor_role'='user' AND conversation_id IS DISTINCT FROM %s "
        "AND producer_ref <> 'membrain-memory-page'",
        (*service._params(principal, brain_id), after, NOTES_CONVERSATION)).fetchall()
    days = set()
    for row in rows:
        if not row["recorded"]:
            continue
        latest = min(row["recorded"], row["restored_from"] or row["recorded"])
        occurred = _utc_day(row["occurred"]) if row["occurred"] else None
        days.add(occurred if occurred and occurred <= latest else latest)  # Never a time still to come.
    return sorted(days)


def _short(value: str | None, today: _datetime.date) -> str:
    day = _date((value or "")[:10])
    if day is None:
        return value or ""
    return f"{day.day} {_MONTHS[day.month - 1]}" + (f" {day.year}" if day.year != today.year else "")


def _plural(number: int, word: str) -> str:
    return f"{number} {word}{'' if number == 1 else 's'}"


def familiarity(days: list[str], moments: int, cap: str | None, today: _datetime.date) -> dict:
    """The derived level, the cap applied, and the reason in the same numbers the rule used."""
    derived = "new"
    for level, minimum_days, minimum_moments in THRESHOLDS:
        if len(days) >= minimum_days and moments >= minimum_moments:
            derived = level
    level = cap if cap is not None and LEVELS.index(cap) < LEVELS.index(derived) else derived
    count = (f"{_plural(len(days), 'day')} of conversation since {_short(days[0], today)}" if days
             else "no conversation yet")
    reason = f"{LEVEL_LABELS[level]}: {count}, {_plural(moments, 'shared moment')}"
    if level != derived:
        reason += f" (capped by you; the rule gives {LEVEL_LABELS[derived]})"
    following = next(((name, need_days, need_moments) for name, need_days, need_moments in THRESHOLDS
                      if LEVELS.index(name) > LEVELS.index(derived)), None)
    return {"level": level, "label": LEVEL_LABELS[level], "derived_level": derived, "cap": cap,
            "days": len(days), "since": days[0] if days else None, "shared_moments": moments, "reason": reason,
            "next": None if following is None else {"level": following[0], "days": following[1],
                                                    "shared_moments": following[2]},
            "thresholds": [{"level": name, "days": need_days, "shared_moments": need_moments}
                           for name, need_days, need_moments in THRESHOLDS]}


def _boundary_view(state) -> list[dict]:
    return [{"id": entry["id"], "topic": entry["topic"], "aliases": entry["aliases"],
             "recorded_at": entry["recorded_at"]} for entry in state["boundaries"]]


def relationship_boundaries(service, principal, brain_id: str) -> dict:
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        return {"boundaries": _boundary_view(_state(service, conn, principal, brain_id))}


def _read(service, conn, principal, brain_id, today) -> dict:
    state = _state(service, conn, principal, brain_id)
    after = state["after"]
    moments = _moments(service, conn, principal, brain_id, after)
    commitments = _commitments(service, conn, principal, brain_id, after, state["acknowledged"], today)
    cap = state["cap"]["level"] if state["cap"] else None
    known = familiarity(_days(service, conn, principal, brain_id, after), len(moments), cap, today)
    support = state["support_style"]
    return {"familiarity": known,
            "support_style": None if not support or not support["text"] else {
                "text": support["text"], "id": support["id"], "recorded_at": support["recorded_at"]},
            "boundaries": _boundary_view(state),
            "shared_moments": [{key: value for key, value in moment.items() if key != "sequence"}
                               for moment in moments],
            "commitments": commitments,
            "markers": [{key: value for key, value in marker.items() if key not in ("id", "sequence")}
                        for marker in state["markers"]],
            "today": today.isoformat()}


def _today(today) -> _datetime.date:
    return today or _clock_today()


def relationship(service, principal, brain_id: str, *, today: _datetime.date | None = None) -> dict:
    """The current relationship and why it is so, with its context block."""
    today = _today(today)
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        result = _read(service, conn, principal, brain_id, today)
    return {**result, **relationship_context(result)}


# Context --------------------------------------------------------------------------------------------------------

HEADER = ("How the user and you, the companion, relate, as memBrain recorded it. Familiarity is derived from days "
          "of conversation and shared moments; it is not a score of the user. Let it shape warmth and informality "
          "lightly, as the persona card says if it does. Never use it, absence or time apart to pressure the user.")


def _boundary_text(boundary: dict) -> str:
    aliases = boundary.get("aliases") or []
    return boundary["topic"] + (f" (also: {', '.join(aliases)})" if aliases else "")


def boundaries_line(boundaries) -> str | None:
    if not boundaries:
        return None
    return ("Boundaries: topics the user asked you not to bring up. Do not raise them, or anything recalled about "
            "them, unless the user does: " + "; ".join(_boundary_text(item) for item in boundaries) + ".")


def relationship_context(result: dict | None) -> dict:
    """``block``: the ``<membrain-relationship>`` block. ``stable``: what decides whether it changed, without the day
    count (which grows every day) and without the one-time line, so neither causes a refresh on its own; every
    missed commitment's id is in it instead, so a newly missed one does. ``once``: missed commitments shown in this
    block for the first and only time, to be acknowledged once the block is delivered."""
    if not result or "familiarity" not in result:
        return {"block": None, "stable": None, "once": []}
    today = _date(result.get("today")) or _clock_today()
    known = result["familiarity"]
    lines = [f"Familiarity: {known['reason']}."]
    # The default level is left out, so a block that only carried a one-time line and then goes away does not
    # count as a change.
    stable = [f"Familiarity: {known['level']}."] if known["level"] != "new" or known.get("cap") else []
    if result.get("support_style"):
        line = f"How they like to be supported: {result['support_style']['text']}"
        lines.append(line)
        stable.append(line)
    boundaries = result.get("boundaries") or []
    line = boundaries_line(boundaries)
    if line:
        lines.append(line)
        stable.append(line)
    missed = [item for item in (result.get("commitments") or {}).get("missed") or () if shown(item, boundaries)]
    once = [item for item in missed if not item.get("acknowledged")][:2]
    once_lines = [f"A promise you made is past its date and not done (shown once): {item['text']} (due "
                  f"{item.get('due') or item.get('occurs_at')}, id: {item['note_id']}). Acknowledge it briefly if it "
                  "fits, and update its note when it is done or dropped." for item in once]
    moments = [moment for moment in result.get("shared_moments") or () if shown(moment, boundaries)]
    header = f"<membrain-relationship>\n{HEADER}\n"
    footer = "\n</membrain-relationship>"
    body = "\n".join(lines + once_lines)
    chosen = []
    for moment in reversed(moments[-MOMENTS_IN_CONTEXT:]):  # The most recent first, until the block is full.
        when = moment.get("occurs_at") or (moment.get("recorded_at") or "")[:10]
        text = f"- {_short(when, today)}: {moment['text']} (id: {moment['id']})"
        size = len(header) + len(body) + len(footer) + len("\nShared moments, oldest first:") + sum(
            len(value) + 1 for value in chosen) + len(text) + 1
        if size > RELATIONSHIP_CHARACTERS:
            break
        chosen.insert(0, text)
    if chosen:
        body += "\nShared moments, oldest first:\n" + "\n".join(chosen)
        stable.append("\n".join(chosen))
    stable.append(json.dumps(sorted(item["note_id"] for item in missed)))
    if not stable[:-1] and not once_lines:
        # Nothing beyond the default: a first session, or one after a reset, gets no block at all.
        return {"block": None, "stable": "\n".join(stable), "once": []}
    # The user's own words (style, topics, moments) are defused, so they can never close or open a memory block.
    return {"block": header + neutralize(body) + footer, "stable": "\n".join(stable),
            "once": [item["note_id"] for item in once]}


# Writes ---------------------------------------------------------------------------------------------------------

def _append(service, conn, principal, brain, stored: dict, key: str) -> str:
    target = {"brain_ref": brain["id"], "conversation_ref": RELATIONSHIP_CONVERSATION, "branch_ref": "main"}
    event_id, _, _ = service._append_event(conn, principal, brain, target, {
        "source_event_key": key, "source_revision": 1, "producer_ref": RELATIONSHIP_PRODUCER,
        "actor_ref": RELATIONSHIP_PRODUCER, "actor_role": "system", "event_kind": "message",
        "content": {"media_type": "text/plain", "text": json.dumps(stored, ensure_ascii=False, sort_keys=True)},
        "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
        "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})
    return event_id


def _erase(service, conn, principal, brain, ids, key) -> dict:
    """Audited deletion, as for notes: tombstones keep the records gone if an older backup is restored."""
    if not ids:
        return brain
    target = {"brain_ref": brain["id"], "conversation_ref": RELATIONSHIP_CONVERSATION, "branch_ref": "main"}
    service._forget(conn, principal, brain, {
        "request_id": key, "target": target,
        "payload": {"idempotency_key": key, "selector": {"kind": "events", "ids": list(ids)},
                    "mode": "erase_content", "expected_scope_generation": brain["scope_generation"]}})
    return service._brain(conn, principal, brain["id"])


def _write(service, principal, brain_id, change, today):
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)  # Locks the brain, so concurrent edits apply in order.
        change(conn, brain, _state(service, conn, principal, brain_id))
        result = _read(service, conn, principal, brain_id, _today(today))
    return {**result, **relationship_context(result)}


def set_support_style(service, principal, brain_id: str, text, *, today=None) -> dict:
    """Replace how the user likes to be supported; empty text removes it. The earlier text is erased."""
    text = _support(text)

    def change(conn, brain, state):
        earlier = [entry["id"] for entry in state["records"] if entry["kind"] == "support_style"]
        if state["support_style"] and state["support_style"]["text"] == text:
            return
        brain = _erase(service, conn, principal, brain, earlier, "relationship-support-" + uid())
        if text:
            _append(service, conn, principal, brain, {"relationship": "support_style", "text": text},
                    "relationship-support-" + uid())

    return _write(service, principal, brain_id, change, today)


def add_boundary(service, principal, brain_id: str, topic, aliases=(), *, today=None) -> dict:
    """Add a topic the user asked the companion not to bring up. The same topic again changes nothing."""
    boundary = _boundary(topic, list(aliases or ()))

    def change(conn, brain, state):
        existing = [entry for entry in state["boundaries"] if entry["topic"].casefold() == boundary["topic"].casefold()]
        if existing and existing[0]["aliases"] == boundary["aliases"]:
            return
        others = [entry for entry in state["boundaries"] if entry not in existing]
        if len(others) >= MAX_BOUNDARIES:
            raise DomainError("validation_failed", f"There can be at most {MAX_BOUNDARIES} boundaries. Remove one "
                                                   "first.")
        if len(boundaries_line([*others, boundary]) or "") > BOUNDARIES_CHARACTERS:
            raise DomainError("validation_failed", "The boundaries would be too long to show in full. Shorten them "
                                                   "or remove one first.")
        brain = _erase(service, conn, principal, brain, [entry["id"] for entry in existing],
                       "relationship-boundary-" + uid())
        _append(service, conn, principal, brain, {"relationship": "boundary", **boundary},
                "relationship-boundary-" + uid())

    return _write(service, principal, brain_id, change, today)


def remove_boundary(service, principal, brain_id: str, boundary_id: str, *, today=None) -> dict:
    """Erase a boundary (audited, so it is not kept anywhere); recall treats the topic normally again."""
    def change(conn, brain, state):
        if boundary_id not in {entry["id"] for entry in state["boundaries"]}:
            raise DomainError("not_found_or_forbidden", "That boundary is not available.")
        _erase(service, conn, principal, brain, [boundary_id], "relationship-boundary-" + uid())

    return _write(service, principal, brain_id, change, today)


def set_cap(service, principal, brain_id: str, level, *, today=None) -> dict:
    """Cap familiarity at a lower level (new, getting_to_know or familiar), or remove the cap with None."""
    level = _level(level)

    def change(conn, brain, state):
        earlier = [entry["id"] for entry in state["records"] if entry["kind"] == "cap"]
        if (state["cap"]["level"] if state["cap"] else None) == level:
            return
        brain = _erase(service, conn, principal, brain, earlier, "relationship-cap-" + uid())
        if level is not None:
            _append(service, conn, principal, brain, {"relationship": "cap", "level": level},
                    "relationship-cap-" + uid())

    return _write(service, principal, brain_id, change, today)


def acknowledge(service, principal, brain_id: str, note_ids, *, today=None) -> dict:
    """Record that missed commitments were shown, so the context does not repeat them. Unknown ids are ignored."""
    if not isinstance(note_ids, (list, tuple)) or len(note_ids) > 50 or not all(
            isinstance(value, str) and 0 < len(value) <= 256 for value in note_ids):
        raise DomainError("validation_failed", "note_ids is a list of at most 50 note IDs.")
    today = _today(today)

    def change(conn, brain, state):
        # Only a promise the context may show can have been shown: never a sensitive or bounded one.
        missed = {item["note_id"] for item in _commitments(
            service, conn, principal, brain_id, state["after"], state["acknowledged"], today)["missed"]
            if shown(item, state["boundaries"])}
        for note_id in dict.fromkeys(note_ids):
            if note_id in missed and note_id not in state["acknowledged"]:
                _append(service, conn, principal, brain, {"relationship": "acknowledged", "note_id": note_id},
                        "relationship-ack-" + uid())

    return _write(service, principal, brain_id, change, today)


def reset_relationship(service, principal, brain_id: str, *, today=None) -> dict:
    """Erase the shared moments, support style, boundaries, cap and acknowledgements, and write a reset marker.

    Familiarity then counts only days after the marker, and nothing before it is derived again. Conversations,
    the user's other notes, the persona, feelings and mood are untouched.
    """
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        state = _state(service, conn, principal, brain_id)
        moments = _moments(service, conn, principal, brain_id, 0)
        params = service._params(principal, brain_id)
        # Earlier versions of a moment that was edited are hidden, not deleted: they go too.
        hidden = [row["id"] for row in conn.execute(
            "SELECT DISTINCT id,document->'observed'->'content'->>'text' AS text FROM memory_events "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND conversation_id=%s AND NOT deleted "
            "AND document IS NOT NULL AND document->'observed'->'content'->>'text' LIKE '[milestone%%'",
            (*params, NOTES_CONVERSATION)) if parse_note(row["text"] or "")[0].get("shared")]
        marker_ids = {marker["id"] for marker in state["markers"]}
        records = [row["id"] for row in conn.execute(
            "SELECT DISTINCT id FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND conversation_id=%s AND NOT deleted", (*params, RELATIONSHIP_CONVERSATION))
            if row["id"] not in marker_ids]
        removed = {"shared_moments": len(moments), "boundaries": len(state["boundaries"]),
                   "support_style": int(bool(state["support_style"] and state["support_style"]["text"])),
                   "cap": int(bool(state["cap"] and state["cap"]["level"])),
                   "acknowledgements": len(state["acknowledged"])}
        key = "relationship-reset-" + uid()
        brain = _erase(service, conn, principal, brain,
                       list(dict.fromkeys(records + [moment["id"] for moment in moments] + hidden)), key)
        _append(service, conn, principal, brain, {"relationship_marker": RESET, "removed": removed}, key)
        result = _read(service, conn, principal, brain_id, _today(today))
    marker = result["markers"][0] if result["markers"] else None
    if marker is None:
        raise DomainError("dependency_unavailable", "The reset marker could not be read back.", retryable=True)
    return {**result, **relationship_context(result), "removed": removed, "marker": marker}


def shared_refusal(service, conn, principal, brain_id, sequences) -> str | None:
    """Why a shared moment read from messages with these sequences is refused, or None when it may be kept."""
    marker = latest_marker(service, conn, principal, brain_id)
    known = [value for value in sequences if isinstance(value, int)]
    if marker and known and min(known) < marker["applies_from_sequence"]:
        return ("The relationship was reset after this message; a shared moment is never recreated from messages "
                "before that. The note was saved without the shared flag.")
    return None
