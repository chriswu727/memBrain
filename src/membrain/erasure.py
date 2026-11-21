import json

from psycopg.types.json import Jsonb

from .helpers import DomainError, digest, now, uid

# Every record that depends on the given ones, directly or through others, each with the record it was reached from:
# the one walk of ``memory_event_dependencies`` that an erasure takes (``dependent_events``) and that the memory page's
# delete questions are written from (``erased_with``), so the two cannot disagree.
_CLOSURE = ("WITH RECURSIVE affected(root,id) AS (SELECT r,r FROM unnest(%s::text[]) AS r UNION "
            "SELECT a.root,d.output_event_id FROM memory_event_dependencies d JOIN affected a "
            "ON d.input_event_id=a.id WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s) ")


def dependent_events(conn, params, event_ids) -> set[str]:
    """``event_ids`` and every record that depends on them: what erasing or hiding them reaches."""
    return {row["id"] for row in conn.execute(_CLOSURE + "SELECT DISTINCT id FROM affected",
                                              (list(event_ids), *params))}


def erased_with(conn, params, event_ids) -> dict[str, list[dict]]:
    """For each of ``event_ids``, the records deleting it alone would erase as well, oldest first: those whose content
    still exists (an erased record has nothing left to name). Each is named by what the page shows of it.

    ``kind`` is ``note``, ``earlier_note`` (a note a note in the walk replaced), ``hidden_note``, ``feeling``,
    ``message`` (with ``actor_role``, ``conversation_id``), ``suggestion`` (a personality suggestion) or ``record``.
    A note or message carries its ``text``; a feeling its ``label`` and ``topic``. Read on request, never stored.
    """
    from .affect import AFFECT_CONVERSATION
    from .notes import NOTES_CONVERSATION
    from .persona_growth import PROPOSALS_CONVERSATION

    event_ids = sorted(set(event_ids))
    if not event_ids:
        return {}
    rows = conn.execute(
        _CLOSURE + "SELECT a.root,e.id,e.conversation_id,e.sequence,e.suppressed OR e.retired AS hidden,"
        "e.document->'observed'->>'actor_role' AS actor_role,e.document->'system_time'->>'recorded_at' AS recorded_at,"
        "left(e.document->'observed'->'content'->>'text',2000) AS text,"
        "EXISTS(SELECT 1 FROM memory_event_dependencies r JOIN memory_events n ON n.tenant_id=r.tenant_id "
        "AND n.owner_id=r.owner_id AND n.brain_id=r.brain_id AND n.id=r.input_event_id AND n.conversation_id=%s "
        "WHERE r.tenant_id=e.tenant_id AND r.owner_id=e.owner_id AND r.brain_id=e.brain_id "
        "AND r.output_event_id=e.id) AS replaced "
        "FROM affected a JOIN memory_events e ON e.tenant_id=%s AND e.owner_id=%s AND e.brain_id=%s "
        "AND e.id=a.id AND e.is_current AND NOT e.deleted AND e.document IS NOT NULL "
        "WHERE a.id<>a.root ORDER BY a.root,e.sequence",
        (event_ids, *params, NOTES_CONVERSATION, *params)).fetchall()
    found: dict[str, list[dict]] = {}
    for row in rows:
        entry = {"event_id": row["id"], "recorded_at": row["recorded_at"]}
        if row["conversation_id"] == NOTES_CONVERSATION:
            kind = "note" if not row["hidden"] else "earlier_note" if row["replaced"] else "hidden_note"
            entry.update(kind=kind, text=row["text"] or "")
        elif row["conversation_id"] == AFFECT_CONVERSATION:
            try:
                affect = json.loads(row["text"] or "")["affect"]
                entry.update(kind="feeling", label=str(affect["label"]), topic=affect.get("topic") or None)
            except (ValueError, KeyError, TypeError):
                entry.update(kind="record")
        elif row["conversation_id"] == PROPOSALS_CONVERSATION:
            entry.update(kind="suggestion")
        elif row["actor_role"] in ("user", "assistant"):
            entry.update(kind="message", actor_role=row["actor_role"], conversation_id=row["conversation_id"],
                         text=row["text"] or "")
        else:
            entry.update(kind="record")
        found.setdefault(row["root"], []).append(entry)
    return found


def resolve_targets(service, conn, principal, brain, selector):
    params = service._params(principal, brain['id'])
    kind, ids = selector['kind'], selector['ids']
    event_ids, memory_ids = set(), set()
    if kind == 'memories':
        for row in conn.execute(
            'SELECT id,event_ids FROM memory_assertions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s '
            'AND id=ANY(%s::text[])', (*params, ids),
        ):
            memory_ids.add(row['id'])
            event_ids.update(row['event_ids'])
    else:
        condition = {'events': 'id=ANY(%s::text[])', 'conversation': 'conversation_id=ANY(%s::text[])',
                     'all_authorized_scope': 'true'}[kind]
        for row in conn.execute(
            'SELECT DISTINCT id FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND ' + condition,
            (*params, ids) if kind != 'all_authorized_scope' else params,
        ):
            event_ids.add(row['id'])
    found = service._dependent_events(conn, principal, brain, event_ids)
    if kind != 'all_authorized_scope' and not found and not memory_ids:
        # A request whose ids match nothing in this memory (never stored, another person's, or of another kind: a
        # note's id passed as a memory) was answered "completed" with zero objects, and a host told the user it was
        # done. It is refused instead and records nothing. A retry of a completed request is answered before this,
        # from its stored response or its recorded deletion intent; ids already erased still match.
        raise DomainError('not_found_or_forbidden', f'No {"memory" if kind == "memories" else "record"} with these '
                          'ids is stored in this memory; nothing was erased.')
    return found, memory_ids


def apply_erasure(service, conn, principal, brain, *, event_ids, memory_ids, mode, deletion_id=None,
                  recording_revision_floor=0, revoke_recording=True):
    if type(revoke_recording) is not bool or (not revoke_recording and mode != "suppress_recall"):
        raise ValueError("Only internal replacement suppression may preserve recording permission.")
    params = service._params(principal, brain['id'])
    event_ids = service._dependent_events(conn, principal, brain, event_ids)
    memory_ids = set(memory_ids)
    memory_ids.update(service._invalidate(conn, principal, brain, event_ids, memory_ids))
    service._advance(conn, principal, brain, scope=True)
    if revoke_recording:
        brain['recording_revision'] = conn.execute(
            'UPDATE memory_brains SET recording_revision=GREATEST(recording_revision+1,%s) '
            'WHERE tenant_id=%s AND owner_id=%s AND id=%s RETURNING recording_revision',
            (recording_revision_floor, *params),
        ).fetchone()['recording_revision']
    for object_kind, object_ids in (('event', event_ids), ('memory', memory_ids)):
        for object_id in sorted(object_ids):
            conn.execute(
                'INSERT INTO memory_tombstones(tenant_id,owner_id,brain_id,object_kind,object_id,mode) '
                'VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,owner_id,brain_id,object_kind,object_id) '
                "DO UPDATE SET mode=CASE WHEN memory_tombstones.mode='erase_content' THEN 'erase_content' ELSE EXCLUDED.mode END",
                (*params, object_kind, object_id, mode),
            )
    erase = mode == 'erase_content'
    if erase:
        from .legacy_erasure import (
            REDACTED_DIGEST,
            invalidate_belief_relations,
            invalidate_pattern_views,
            redact_legacy_digests,
            redact_runtime_turns,
        )

        invalidate_pattern_views(conn, params, event_ids=event_ids, memory_ids=memory_ids, deleted=True)
        invalidate_belief_relations(conn, params, event_ids=event_ids, memory_ids=memory_ids, deleted=True)
        redact_runtime_turns(conn, params, event_ids=event_ids, memory_ids=memory_ids)
        redact_legacy_digests(conn, params, event_ids=event_ids, memory_ids=memory_ids)
        # An erased message keeps no digest of itself: content_hash and input_hash (both NOT NULL) of every revision.
        conn.execute(
            'UPDATE memory_events SET content_hash=%s,input_hash=%s '
            'WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=ANY(%s::text[])',
            (REDACTED_DIGEST, REDACTED_DIGEST, *params, sorted(event_ids)),
        )
        # A host that has no turn id for a message keys it by a digest of its session, role and text
        # (host.message_record), so such a source key would confirm a guess too. An erased event's key that holds a
        # digest-shaped run (32 or more hex digits) is replaced by one naming only the event. Hosts' queued copies
        # are refused anyway, by the capture revision the erasure revoked; other callers' keys are left, so a copy
        # they send again is still refused as erased (MemoryService._append_event).
        conn.execute(
            "UPDATE memory_events SET source_key='erased:' || id WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND id=ANY(%s::text[]) AND source_key ~ '[0-9a-f]{32}'",
            (*params, sorted(event_ids)),
        )
        # Request fingerprints are digests of whole requests, and an observation's or a recall's request holds the
        # message or query text beside values a reader of the table can see (its key, target and budget), so it would
        # confirm a guess; an observation's key can hold a content-derived source key too. Which stored request
        # carried the erased text cannot be told once responses are cleared (every change of the brain clears them).
        # So content erasure removes every stored observation request of the brain (an observation sent again is
        # matched by its events: still recorded, a duplicate; erased, refused) and wipes every other fingerprint (a
        # request sent again with the same key is then answered as one whose stored response is gone).
        conn.execute("DELETE FROM memory_requests WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND action='observe'",
                     params)
        conn.execute('UPDATE memory_requests SET request_hash=%s WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s',
                     (REDACTED_DIGEST, *params))
    from .legacy_erasure import clear_query_embeddings

    clear_query_embeddings(conn, params)
    conn.execute(
        'UPDATE memory_events SET suppressed=true,deleted=deleted OR %s,document=CASE WHEN %s THEN NULL ELSE document END '
        'WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=ANY(%s::text[])',
        (erase, erase, *params, sorted(event_ids)),
    )
    conn.execute(
        'UPDATE memory_assertions SET suppressed=true,deleted=deleted OR %s,'
        "document=CASE WHEN %s THEN NULL ELSE document END,search_text='',embedding=NULL,source_han_majority=NULL "
        'WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=ANY(%s::text[])',
        (erase, erase, *params, sorted(memory_ids)),
    )
    conn.execute('DELETE FROM memory_working_states WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s', params)
    conn.execute('DELETE FROM memory_traces WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s', params)
    if erase:
        for archive in conn.execute(
            'SELECT id,brain_id,document FROM memory_archives WHERE tenant_id=%s AND owner_id=%s',
            (principal.tenant_id, principal.principal_id),
        ).fetchall():
            data = service._sanitize_archive(conn, principal, archive['document'])
            if data != archive['document']:
                conn.execute(
                    'UPDATE memory_archives SET document=%s,manifest_hash=%s '
                    'WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s',
                    (Jsonb(data), digest(data), principal.tenant_id, principal.principal_id, archive['brain_id'], archive['id']),
                )
    return {'deletion_id': deletion_id or uid(), 'mode': mode, 'scope_generation': brain['scope_generation'],
            'recall_blocked_at': now(), 'purge_state': 'completed' if erase else 'not_requested',
            'backup_expiry_deadline': None, 'tombstone_recorded': True,
            'affected_object_count': len(event_ids) + len(memory_ids)}
