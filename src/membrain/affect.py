"""Affect records (``user_affect``): feelings the user expressed, kept as evidence and never as a score.

A record belongs to one note. The host writes it with the note tool's ``affect`` field and, behind the proxy, the
optional extraction model does; no model call is made for it. Each record is one event in a reserved conversation,
stored apart from the note it belongs to, with the ``system`` role: it is configuration-like evidence, not something
anyone said, so it is never extracted into recalled memories, shown as history or counted as a message.

Every record depends on its note (and on the messages it was read from), so the audited deletion that removes a note
or a source message removes the record too: correcting or deleting the source deletes the record. A later reading
is a new record; nothing here rewrites an earlier one.

"Clear feelings" erases every record and writes a reset marker with the time and the sequence it applies from.
Feelings are never recreated from messages recorded before the latest marker, and later layers (the companion's
simulated mood) count only records after it. Erasing all memory removes the markers too.
"""
from __future__ import annotations

import json

from .helpers import DomainError, uid
from .notes import NOTES_CONVERSATION, check_affect, parse_note

AFFECT_CONVERSATION = "membrain-affect"
AFFECT_PRODUCER = "membrain-affect"
ARCHIVE_PRODUCER = "archive-import"
CLEARED = "cleared"
MAX_RECORDS = 500
_VISIBLE = ("tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current AND NOT deleted AND NOT suppressed "
            "AND NOT retired AND document IS NOT NULL")


def _entry(row) -> dict | None:
    """A stored record, a reset marker, or None for anything this module did not write."""
    document = row["document"]
    observed = document["observed"]
    if observed.get("actor_role") != "system" or row["producer_ref"] not in (AFFECT_PRODUCER, ARCHIVE_PRODUCER):
        return None
    try:
        stored = json.loads(observed["content"].get("text") or "")
        base = {"id": document["event_id"], "sequence": document["sequence"],
                "recorded_at": document["system_time"]["recorded_at"]}
        if stored.get("affect_marker") == CLEARED:
            count = stored.get("cleared_records")
            if set(stored) != {"affect_marker", "cleared_records"} or type(count) is not int or count < 0:
                return None
            return {**base, "marker": CLEARED, "applies_from_sequence": document["sequence"],
                    "cleared_records": count}
        if set(stored) != {"affect", "note_id", "written_by", "source_event_ids"}:
            return None
        record = stored["affect"]
        sources, note_id, author = stored["source_event_ids"], stored["note_id"], stored["written_by"]
        if (not isinstance(note_id, str) or not 0 < len(note_id) <= 200
                or (author is not None and (not isinstance(author, str) or len(author) > 200))
                or not isinstance(sources, list) or len(sources) > 128
                or not all(isinstance(source, str) and 0 < len(source) <= 200 for source in sources)
                or len(set(sources)) != len(sources)
                or not isinstance(record, dict)
                or not all(isinstance(record.get(key), str) for key in ("label", "basis", "felt_at"))
                or ("topic" in record and not isinstance(record["topic"], str))):
            return None
        checked = check_affect(record, sourced=True)
        entry = {**base, "note_id": note_id, **checked, "topic": checked.get("topic"), "written_by": author,
                 "read_from": list(sources), "_from_archive": row["producer_ref"] == ARCHIVE_PRODUCER}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return entry


def _markers(service, conn, principal, brain_id, limit=20) -> list[dict]:
    """Archive imports rewrite source keys, so the stored marker kind identifies resets."""
    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "AND document->'observed'->'content'->>'text' LIKE %s ORDER BY sequence DESC LIMIT %s",
        (*service._params(principal, brain_id), AFFECT_CONVERSATION, '{"affect_marker"%', limit)).fetchall()
    return [entry for entry in map(_entry, rows) if entry and "marker" in entry]


def latest_marker(service, conn, principal, brain_id) -> dict | None:
    """The latest affect reset marker; derived values count only records after its ``applies_from_sequence``."""
    markers = _markers(service, conn, principal, brain_id, limit=1)
    return markers[0] if markers else None


def record_affect(service, conn, principal, brain, *, note_id, affect, request_id, producer,
                  source_event_ids=(), source_messages=()) -> dict:
    """Store one affect record for a note just written in this transaction (called by ``store_note``).

    ``affect`` is already checked (``notes.check_affect``). A record read from a message recorded before the latest
    "Clear feelings" is refused, so a reset cannot be recomputed from older conversations; the note is kept.
    """
    params = service._params(principal, brain["id"])
    explicit = list(dict.fromkeys(source_event_ids))
    for ref in source_messages:
        row = conn.execute(
            f"SELECT id FROM memory_events WHERE {_VISIBLE} AND producer_ref=%s AND source_key=%s "
            "AND source_revision=%s AND conversation_id IS DISTINCT FROM %s",
            (*params, ref["producer_ref"], ref["source_event_key"], ref["source_revision"],
             NOTES_CONVERSATION)).fetchone()
        if row and row["id"] not in explicit:
            explicit.append(row["id"])  # A reference not recorded yet is newer than any marker.
    marker = latest_marker(service, conn, principal, brain["id"])
    if marker and explicit:
        oldest = conn.execute(
            "SELECT min(sequence) AS sequence FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND id=ANY(%s::text[])", (*params, explicit)).fetchone()["sequence"]
        if oldest is not None and oldest < marker["applies_from_sequence"]:
            return {"affect_id": None, "affect_refused": (
                "Feelings were cleared after this message; a feeling is never recreated from messages before that.")}
    stored = {"affect": affect, "note_id": note_id, "written_by": producer, "source_event_ids": explicit}
    target = {"brain_ref": brain["id"], "conversation_ref": AFFECT_CONVERSATION, "branch_ref": "main"}
    record_id, _, _ = service._append_event(conn, principal, brain, target, {
        "source_event_key": "affect-" + request_id, "source_revision": 1, "producer_ref": AFFECT_PRODUCER,
        "actor_ref": producer, "actor_role": "system", "event_kind": "message",
        "content": {"media_type": "text/plain", "text": json.dumps(stored, ensure_ascii=False, sort_keys=True)},
        "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
        "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})
    for source in [note_id, *explicit]:
        conn.execute(
            "INSERT INTO memory_event_dependencies(tenant_id,owner_id,brain_id,input_event_id,output_event_id) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (*params, source, record_id))
    return {"affect_id": record_id}


def _records(service, conn, principal, brain_id, limit=MAX_RECORDS + 1) -> list[dict]:
    """Current records whose note is still current, newest first, each with its note and evidence."""
    params = service._params(principal, brain_id)
    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "AND document->'observed'->'content'->>'text' NOT LIKE %s ORDER BY sequence DESC LIMIT %s",
        (*params, AFFECT_CONVERSATION, '{"affect_marker"%', limit)).fetchall()
    records = [entry for entry in map(_entry, rows) if entry and "marker" not in entry]
    marker = latest_marker(service, conn, principal, brain_id)
    if marker:  # Erased by the reset; kept out here too, so nothing before the marker can count.
        records = [record for record in records if record["sequence"] > marker["applies_from_sequence"]]
    note_ids = list({record["note_id"] for record in records})
    notes = {row["id"]: row for row in conn.execute(
        "SELECT id,document->'observed'->'content'->>'text' AS text,"
        "ARRAY(SELECT d.input_event_id FROM memory_event_dependencies d JOIN memory_events s "
        "ON s.tenant_id=d.tenant_id AND s.owner_id=d.owner_id AND s.brain_id=d.brain_id AND s.id=d.input_event_id "
        "WHERE d.tenant_id=memory_events.tenant_id AND d.owner_id=memory_events.owner_id "
        "AND d.brain_id=memory_events.brain_id AND d.output_event_id=memory_events.id AND s.is_current "
        "AND NOT s.deleted AND NOT s.suppressed AND NOT s.retired AND s.document IS NOT NULL "
        "ORDER BY s.sequence) AS sources "
        f"FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s AND id=ANY(%s::text[])",
        (*params, NOTES_CONVERSATION, note_ids))} if note_ids else {}
    read_from = list({value for record in records for value in record["read_from"]}
                     | {value for note in notes.values() for value in note["sources"]})
    visible = {row["id"]: row for row in conn.execute(
        "SELECT id,conversation_id,producer_ref,document->'observed'->>'actor_role' AS actor_role "
        f"FROM memory_events WHERE {_VISIBLE} AND id=ANY(%s::text[])", (*params, read_from))} if read_from else {}
    result = []
    for record in records:
        imported = record.pop("_from_archive")
        note = notes.get(record["note_id"])
        if note is None:
            continue  # Its note was corrected or deleted; the cascade removes the record with it.
        fields, sentence = parse_note(note["text"] or "")
        sources = [value for value in record.pop("read_from") if value in visible]
        sources += [value for value in note["sources"] if value not in sources]
        if imported and record["basis"] == "inferred" and not any(
                visible[source]["actor_role"] == "user" and visible[source]["conversation_id"] != NOTES_CONVERSATION
                and visible[source]["producer_ref"] != "membrain-memory-page" for source in sources):
            continue
        result.append({**record, "source_event_ids": sources, "note_text": sentence,
                       "note_kind": fields.get("kind"), "sensitive": bool(fields.get("sensitive"))})
    return result


def affect_records(service, principal, brain_id: str) -> dict:
    """Every current affect record, newest first, with its evidence, and the reset markers, newest first.

    ``complete`` is false when more than ``MAX_RECORDS`` exist. There is deliberately no overall score.
    """
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        records = _records(service, conn, principal, brain_id)
        markers = _markers(service, conn, principal, brain_id)
    return {"records": records[:MAX_RECORDS], "complete": len(records) <= MAX_RECORDS, "markers": markers}


def clear_affect(service, principal, brain_id: str) -> dict:
    """"Clear feelings": erase every affect record, reported and inferred, and write an affect reset marker.

    Records are erased with the same audited deletion as notes (tombstones, so a restored backup keeps them gone),
    including copies hidden when their note was corrected. Notes, messages and other layers are untouched.
    """
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        params = service._params(principal, brain_id)
        cleared = len(_records(service, conn, principal, brain_id, limit=100_000))
        ids = [row["id"] for row in conn.execute(
            "SELECT DISTINCT id FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND conversation_id=%s AND NOT deleted AND (document IS NULL OR "
            "document->'observed'->'content'->>'text' NOT LIKE %s)",
            (*params, AFFECT_CONVERSATION, '{"affect_marker"%'))]
        key = "affect-reset-" + uid()
        target = {"brain_ref": brain_id, "conversation_ref": AFFECT_CONVERSATION, "branch_ref": "main"}
        if ids:
            service._forget(conn, principal, brain, {
                "request_id": key, "target": target,
                "payload": {"idempotency_key": key, "selector": {"kind": "events", "ids": ids},
                            "mode": "erase_content", "expected_scope_generation": brain["scope_generation"]}})
            brain = service._brain(conn, principal, brain_id)
        service._append_event(conn, principal, brain, target, {
            "source_event_key": key, "source_revision": 1, "producer_ref": AFFECT_PRODUCER,
            "actor_ref": AFFECT_PRODUCER, "actor_role": "system", "event_kind": "message",
            "content": {"media_type": "text/plain",
                        "text": json.dumps({"affect_marker": CLEARED, "cleared_records": cleared})},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})
        marker = latest_marker(service, conn, principal, brain_id)
    if marker is None:
        raise DomainError("dependency_unavailable", "The reset marker could not be read back.", retryable=True)
    return {"cleared_records": cleared, "marker": marker}
