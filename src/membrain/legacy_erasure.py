"""Erasure of derived rows that the runtime no longer writes, or writes only outside the plugin path.

Older installations, configured profiles and restored archives can still hold these rows, so editing or forgetting
their sources must keep clearing them. Plain SQL only: this module must not import the code that writes them.
``params`` is ``(tenant_id, owner_id, brain_id)``, as ``MemoryService._params`` returns it.
"""

# Policy version stamped on recomputed access state (migration 014).
ACCESS_VERSION = "contextual-access-v2"


def invalidate_pattern_views(conn, params, *, event_ids=(), memory_ids=(), episode_ids=(), deleted=False):
    """Clear every pattern view (migration 008) built from one of these events, memories or episodes."""
    if not event_ids and not memory_ids and not episode_ids:
        return
    conn.execute(
        "UPDATE memory_pattern_views SET document=NULL,invalidated=true,deleted=deleted OR %s "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND (event_ids && %s::text[] OR memory_ids && %s::text[] OR episode_ids && %s::text[])",
        (deleted, *params, sorted(set(event_ids)), sorted(set(memory_ids)), sorted(set(episode_ids))),
    )


def invalidate_belief_relations(conn, params, *, event_ids=(), memory_ids=(), deleted=False):
    """Clear every belief relation (migration 009) that depends on one of these events or memories."""
    if event_ids or memory_ids:
        conn.execute(
            "UPDATE memory_belief_relations SET document=NULL,invalidated=true,deleted=deleted OR %s "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND (event_ids && %s::text[] OR memory_ids && %s::text[])",
            (deleted, *params, sorted(set(event_ids)), sorted(set(memory_ids))),
        )


def recompute_access(conn, params, versions):
    """Rebuild the access state (migration 014) of these memory versions from their remaining feedback."""
    versions = sorted(set(versions))
    if not versions:
        return
    ids, revisions = [key[0] for key in versions], [key[1] for key in versions]
    conn.execute(
        "INSERT INTO memory_access_state(tenant_id,owner_id,brain_id,memory_id,memory_revision,external_uses,"
        "successes,failures,last_external_use_at,last_reinforcement_at,last_feedback_event_id,policy_version) "
        "SELECT tenant_id,owner_id,brain_id,memory_id,memory_revision,count(*),"
        "count(*) FILTER (WHERE kind='user_confirmed'),count(*) FILTER (WHERE kind='user_corrected'),"
        "max(observed_at),max(observed_at) FILTER (WHERE kind<>'user_corrected'),"
        "(array_agg(feedback_event_id ORDER BY observed_at DESC,feedback_event_id,feedback_event_revision DESC))[1],%s "
        "FROM memory_feedback_contributions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND (memory_id,memory_revision) IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) "
        "AND invalidated_at IS NULL GROUP BY tenant_id,owner_id,brain_id,memory_id,memory_revision "
        "ON CONFLICT(tenant_id,brain_id,memory_id,memory_revision) DO UPDATE SET "
        "revision=memory_access_state.revision+1,external_uses=EXCLUDED.external_uses,successes=EXCLUDED.successes,"
        "failures=EXCLUDED.failures,last_external_use_at=EXCLUDED.last_external_use_at,"
        "last_reinforcement_at=EXCLUDED.last_reinforcement_at,last_feedback_event_id=EXCLUDED.last_feedback_event_id,"
        "policy_version=EXCLUDED.policy_version",
        (ACCESS_VERSION, *params, ids, revisions),
    )
    conn.execute(
        "DELETE FROM memory_access_state a WHERE a.tenant_id=%s AND a.owner_id=%s AND a.brain_id=%s "
        "AND (a.memory_id,a.memory_revision) IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) "
        "AND NOT EXISTS (SELECT 1 FROM memory_feedback_contributions c WHERE c.tenant_id=a.tenant_id "
        "AND c.owner_id=a.owner_id AND c.brain_id=a.brain_id AND c.memory_id=a.memory_id "
        "AND c.memory_revision=a.memory_revision AND c.invalidated_at IS NULL)",
        (*params, ids, revisions),
    )


def invalidate_contributions(conn, params, *, event_ids=(), memory_ids=()):
    """Invalidate feedback contributions (migration 014) that cite these events or memories; recompute access."""
    rows = conn.execute(
        "UPDATE memory_feedback_contributions SET invalidated_at=clock_timestamp() "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND invalidated_at IS NULL "
        "AND (source_event_ids && %s::text[] OR source_memory_ids && %s::text[]) RETURNING memory_id,memory_revision",
        (*params, list(event_ids), list(memory_ids)),
    ).fetchall()
    recompute_access(conn, params, [(row["memory_id"], row["memory_revision"]) for row in rows])


def clear_query_embeddings(conn, params):
    """Clear the query vectors and source snapshots that ``query_embedding`` jobs of a metered provider kept in their
    result. Older runtimes wrote those rows; the local model writes none."""
    conn.execute(
        "UPDATE memory_jobs SET result=NULL WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND kind='query_embedding'",
        params,
    )


# A digest erased from a runtime turn row reads as 64 zeros: the content-free marker temporary turns already carry
# (migration 034), which no real SHA-256 digest is taken to be. ``input_fingerprint`` is NOT NULL and must be 64 hex
# digits, so it cannot be cleared; the JSON fields keep their shape so the rows stay readable.
REDACTED_DIGEST = "0" * 64


def _refers(refs, event_ids):
    return any(isinstance(ref, dict) and ref.get("event_id") in event_ids for ref in refs or ())


def redact_runtime_turns(conn, params, *, event_ids=(), memory_ids=()):
    """Remove from runtime turn rows (migration 004 and later) every digest of erased content.

    Older runtimes stored, beside each turn's event references, SHA-256 digests of what the turn said and showed:
    of its input (``input_fingerprint``, over the message id and text), of the delivered answer
    (``delivery_receipt.content_sha256``), of the reviewed draft (``response_review.draft_sha256``) and of each
    selected memory's statement (``prepared_memory_selection.memories[].statement_sha256``). A digest of a short
    message confirms a guess of it, so content erasure replaces those of erased events and memories with
    ``REDACTED_DIGEST``. The rows, their stages and every id stay, for recovery quarantine and referential integrity.
    """
    event_ids, memory_ids = set(event_ids), set(memory_ids)
    if not event_ids and not memory_ids:
        return 0
    from psycopg.types.json import Jsonb

    rows = conn.execute(
        "SELECT turn_id,input_fingerprint,input_event_refs,output_event_refs,delivery_receipt,response_review,"
        "prepared_memory_selection FROM memory_runtime_turns t WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND ("
        "EXISTS (SELECT 1 FROM jsonb_array_elements(t.input_event_refs || t.output_event_refs) r "
        "WHERE r->>'event_id'=ANY(%s::text[])) "
        "OR t.delivery_receipt #>> '{authorization,draft_event_ref,event_id}'=ANY(%s::text[]) "
        "OR EXISTS (SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(t.prepared_memory_selection->'memories')"
        "='array' THEN t.prepared_memory_selection->'memories' ELSE '[]'::jsonb END) m "
        "WHERE m->>'memory_id'=ANY(%s::text[]) OR (jsonb_typeof(m->'evidence_refs')='array' AND EXISTS ("
        "SELECT 1 FROM jsonb_array_elements(m->'evidence_refs') e WHERE e->>'event_id'=ANY(%s::text[])))))",
        (*params, sorted(event_ids), sorted(event_ids), sorted(memory_ids), sorted(event_ids)),
    ).fetchall()
    for row in rows:
        inputs = _refers(row["input_event_refs"], event_ids)
        receipt = row["delivery_receipt"]
        outputs = _refers(row["output_event_refs"], event_ids) or (
            isinstance(receipt, dict)
            and _refers([(receipt.get("authorization") or {}).get("draft_event_ref")], event_ids))
        fingerprint = REDACTED_DIGEST if inputs else row["input_fingerprint"]
        if outputs and isinstance(receipt, dict) and receipt.get("content_bytes"):
            receipt = {**receipt, "content_sha256": REDACTED_DIGEST}
        review = row["response_review"]
        if outputs and isinstance(review, dict) and "draft_sha256" in review:
            review = {**review, "draft_sha256": REDACTED_DIGEST}
        selection = row["prepared_memory_selection"]
        if isinstance(selection, dict) and isinstance(selection.get("memories"), list):
            selection = {**selection, "memories": [
                {**memory, "statement_sha256": REDACTED_DIGEST}
                if isinstance(memory, dict) and (memory.get("memory_id") in memory_ids
                                                 or _refers(memory.get("evidence_refs"), event_ids))
                else memory for memory in selection["memories"]]}
        conn.execute(
            "UPDATE memory_runtime_turns SET input_fingerprint=%s,delivery_receipt=%s,response_review=%s,"
            "prepared_memory_selection=%s WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND turn_id=%s",
            (fingerprint, Jsonb(receipt) if receipt is not None else None,
             Jsonb(review) if review is not None else None,
             Jsonb(selection) if selection is not None else None, *params, row["turn_id"]),
        )
    return len(rows)
