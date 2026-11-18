"""What a replacement note replaced, and which messages a current note overruled, read from the records themselves.

When a note is saved with ``replaces``, the new note and each note it replaced are linked by one row of
``memory_event_dependencies`` (input: the new note, output: the replaced one). Nothing of the replaced note is
copied: its sentence and date are read from its own record, which a replacement only hides (``suppress_recall``).
The row is also an ordinary deletion dependency, so erasing or hiding the current note reaches every note it
replaced, and a replaced note is never left as a stored sentence that nothing shows and nothing can delete. When a
replaced note's content is erased (it was deleted itself, or a message it rests on was), nothing of it is read:
neither its sentence nor its date.

A replacement note also keeps its predecessors' source messages as its own deletion dependencies
(``notes.store_note``: deleting a message reaches every note drawn from it, and a correction may restate the note it
corrects), so the messages behind a note are of two kinds. Which kind is derived here, never stored: the messages
behind the notes it replaced are those the replaced notes rest on (their own dependency rows, which outlive their
content); the current note's own are the rest.

A user message is "superseded" by a current note when a replaced note whose content still exists rests on it, that
current note is at the head of the replaced note's chain, and the current note has at least one source message of
its own: a replacement without one (a status update, a rewording) does not show that the user said something new.
A message the current note rests on itself is never superseded by it; one that both a replaced note and the current
note named cannot be told apart from an inherited one, and is treated as inherited.
"""
from __future__ import annotations

from .notes import NOTES_CONVERSATION

CHAIN_LIMIT = 20  # Replaced notes read per current note; a fact corrected more often still shows its latest 20.
_JOIN = ("{alias}.tenant_id=d.tenant_id AND {alias}.owner_id=d.owner_id AND {alias}.brain_id=d.brain_id "
         "AND {alias}.is_current AND {alias}.conversation_id=%s")
_READABLE = "NOT {alias}.deleted AND NOT {alias}.retired AND {alias}.document IS NOT NULL"


def record(conn, params, note_id: str, replaced_ids) -> None:
    """Link a new note to each note it replaced (the replaced one is the dependent record)."""
    for replaced in sorted(set(replaced_ids) - {note_id}):
        conn.execute(
            "INSERT INTO memory_event_dependencies(tenant_id,owner_id,brain_id,input_event_id,output_event_id) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (*params, note_id, replaced))


def _chain() -> str:
    """A recursive term walking from notes to the notes they replaced, whatever became of those since."""
    return (
        "SELECT c.head,d.output_event_id,o.sequence,c.depth+1 FROM chain c JOIN memory_event_dependencies d "
        "ON d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s AND d.input_event_id=c.id "
        f"JOIN memory_events o ON o.id=d.output_event_id AND {_JOIN.format(alias='o')} AND o.suppressed "
        "AND o.sequence<c.sequence WHERE c.depth<%s")


def replaced_notes(conn, params, note_ids, *, max_characters: int = 480) -> dict[str, list[dict]]:
    """For each of ``note_ids``, the notes it replaced, directly or through earlier replacements, newest first.

    Each entry holds the replaced note's id, ``depth`` (1 for a note this one replaced directly) and the source
    messages that note rests on itself. While its content exists it also holds its recording time, its stored text
    (cut to ``max_characters``), who wrote it and its producer; once erased it holds ``erased: true`` and nothing
    else of it, so a page can still tell which of the current note's messages were the earlier note's without
    showing that note. One query for all notes.
    """
    note_ids = sorted(set(note_ids))
    if not note_ids:
        return {}
    rows = conn.execute(
        "WITH RECURSIVE chain(head,id,sequence,depth) AS ("
        "SELECT d.input_event_id,d.output_event_id,o.sequence,1 FROM memory_event_dependencies d "
        f"JOIN memory_events i ON {_JOIN.format(alias='i')} AND i.id=d.input_event_id "
        f"JOIN memory_events o ON o.id=d.output_event_id AND {_JOIN.format(alias='o')} AND o.suppressed "
        "AND o.sequence<i.sequence "
        "WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s AND d.input_event_id=ANY(%s::text[]) "
        f"UNION {_chain()}) "
        f"SELECT c.head,c.depth,o.id,o.sequence,o.producer_ref,{_READABLE.format(alias='o')} AS readable,"
        "o.document->'observed'->>'actor_role' AS actor_role,"
        "o.document->'system_time'->>'recorded_at' AS recorded_at,"
        "o.document->'observed'->'content'->>'text' AS text,"
        "ARRAY(SELECT s.input_event_id FROM memory_event_dependencies s JOIN memory_events m "
        "ON m.tenant_id=s.tenant_id AND m.owner_id=s.owner_id AND m.brain_id=s.brain_id AND m.id=s.input_event_id "
        "AND m.is_current WHERE s.tenant_id=o.tenant_id AND s.owner_id=o.owner_id AND s.brain_id=o.brain_id "
        "AND s.output_event_id=o.id AND m.conversation_id IS DISTINCT FROM %s ORDER BY s.input_event_id) "
        "AS source_event_ids "
        "FROM chain c JOIN memory_events o ON o.tenant_id=%s AND o.owner_id=%s AND o.brain_id=%s AND o.id=c.id "
        "AND o.is_current ORDER BY c.head,o.sequence DESC,c.depth",
        (NOTES_CONVERSATION, NOTES_CONVERSATION, *params, note_ids, *params, NOTES_CONVERSATION, CHAIN_LIMIT,
         NOTES_CONVERSATION, *params)).fetchall()
    found: dict[str, list[dict]] = {}
    for row in rows:
        entries = found.setdefault(row["head"], [])
        if any(entry["event_id"] == row["id"] for entry in entries) or len(entries) >= CHAIN_LIMIT:
            continue  # Reached twice (a note that replaced two notes, which replaced one).
        entry = {"event_id": row["id"], "depth": row["depth"], "source_event_ids": list(row["source_event_ids"])}
        if not row["readable"]:
            entries.append({**entry, "erased": True})
            continue
        text = row["text"] or ""
        if len(text) > max_characters:
            text = text[:max_characters - 1] + "…"
        entries.append({**entry, "recorded_at": row["recorded_at"], "text": text, "actor_role": row["actor_role"],
                        "producer": row["producer_ref"]})
    return found


def _inherited(note: str, message: str) -> str:
    """SQL: whether ``message`` is a message of a note that ``note`` replaced directly. A replacement keeps every
    message of its direct predecessor (and so of the whole chain), so that is enough to tell an inherited one."""
    return (
        "EXISTS (SELECT 1 FROM memory_event_dependencies r JOIN memory_events p ON p.tenant_id=r.tenant_id "
        "AND p.owner_id=r.owner_id AND p.brain_id=r.brain_id AND p.id=r.output_event_id AND p.is_current "
        "AND p.conversation_id=%s JOIN memory_event_dependencies q ON q.tenant_id=r.tenant_id "
        "AND q.owner_id=r.owner_id AND q.brain_id=r.brain_id AND q.output_event_id=r.output_event_id "
        f"AND q.input_event_id={message} WHERE r.tenant_id=%s AND r.owner_id=%s AND r.brain_id=%s "
        f"AND r.input_event_id={note})")


def superseded(conn, params, message_ids) -> dict[str, dict]:
    """For each of ``message_ids``, the current note that overruled it, if any: {note_id, recorded_at, actor_role}.

    See the module's description for when a message is overruled. When several current notes overruled one
    message, the newest is named. One query for all messages, whatever the number of lines it serves.
    """
    message_ids = sorted(set(message_ids))
    if not message_ids:
        return {}
    rows = conn.execute(
        "WITH RECURSIVE up(message,note,sequence,depth) AS ("
        # A replaced note whose content exists, for which the message is its own (not kept from its predecessor).
        "SELECT d.input_event_id,d.output_event_id,o.sequence,0 FROM memory_event_dependencies d "
        f"JOIN memory_events o ON o.id=d.output_event_id AND {_JOIN.format(alias='o')} AND o.suppressed "
        f"AND {_READABLE.format(alias='o')} "
        "WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s AND d.input_event_id=ANY(%s::text[]) "
        f"AND NOT {_inherited('o.id', 'd.input_event_id')} "
        "UNION "
        "SELECT u.message,d.input_event_id,n.sequence,u.depth+1 FROM up u JOIN memory_event_dependencies d "
        "ON d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s AND d.output_event_id=u.note "
        f"JOIN memory_events n ON n.id=d.input_event_id AND {_JOIN.format(alias='n')} "
        f"AND {_READABLE.format(alias='n')} AND n.sequence>u.sequence WHERE u.depth<%s) "
        "SELECT DISTINCT u.message,h.id AS note,h.sequence,h.document->'system_time'->>'recorded_at' AS recorded_at,"
        "h.document->'observed'->>'actor_role' AS actor_role FROM up u JOIN memory_events h ON h.tenant_id=%s "
        "AND h.owner_id=%s AND h.brain_id=%s AND h.id=u.note AND h.is_current AND NOT h.suppressed "
        # The current note at the head has a message of its own.
        "WHERE u.depth>0 AND EXISTS (SELECT 1 FROM memory_event_dependencies own JOIN memory_events m "
        "ON m.tenant_id=own.tenant_id AND m.owner_id=own.owner_id AND m.brain_id=own.brain_id "
        "AND m.id=own.input_event_id AND m.is_current AND m.conversation_id IS DISTINCT FROM %s "
        "WHERE own.tenant_id=h.tenant_id AND own.owner_id=h.owner_id AND own.brain_id=h.brain_id "
        f"AND own.output_event_id=h.id AND NOT {_inherited('h.id', 'own.input_event_id')}) "
        "ORDER BY u.message,h.sequence DESC",
        (NOTES_CONVERSATION, *params, message_ids, NOTES_CONVERSATION, *params, *params, NOTES_CONVERSATION,
         CHAIN_LIMIT, *params, NOTES_CONVERSATION, NOTES_CONVERSATION, *params)).fetchall()
    found: dict[str, dict] = {}
    for row in rows:
        found.setdefault(row["message"], {"note_id": row["note"], "recorded_at": row["recorded_at"],
                                          "actor_role": row["actor_role"]})
    return found
