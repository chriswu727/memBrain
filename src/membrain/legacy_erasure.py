"""Erasure of derived rows that the runtime no longer writes, or writes only outside the plugin path.

Older installations, configured profiles and restored archives can still hold these rows, so editing or forgetting
their sources must keep clearing them. Plain SQL only: this module must not import the code that writes them.
``params`` is ``(tenant_id, owner_id, brain_id)``, as ``MemoryService._params`` returns it.
"""

import re

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


# A digest erased from a row reads as 64 zeros: the content-free marker temporary turns already carry (migration
# 034), which no real SHA-256 digest is taken to be. The columns that hold digests are NOT NULL (and some must be 64
# hex digits), so they cannot be cleared; JSON fields keep their shape so the rows stay readable.
REDACTED_DIGEST = "0" * 64
_HEX = re.compile(r"[0-9a-f]{64}")
# Configuration fingerprints: they identify a reviewer's setup, never content.
_CONFIGURATION_KEYS = frozenset({"policy_fingerprint"})


def redact_digests(value, keep=_CONFIGURATION_KEYS):
    """``value`` with every 64-hex string replaced by ``REDACTED_DIGEST``, except under the keys in ``keep``."""
    if isinstance(value, dict):
        return {key: item if key in keep else redact_digests(item, keep) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_digests(item, keep) for item in value]
    if isinstance(value, str) and _HEX.fullmatch(value):
        return REDACTED_DIGEST
    return value


def redact_runtime_turns(conn, params, *, event_ids=(), memory_ids=()):
    """Remove every digest from the runtime turn rows (migration 004 and later) that name erased content.

    Older runtimes stored digests beside each turn's references: of its input (``input_fingerprint``), of its
    prepared context (``context_fingerprint``, ``prepared_memory_selection.model_context_sha256``), of the delivered
    answer and the reviewed draft, of each selected memory's statement and source, of recall queries, orientation
    dependencies and transitions. One rule: a turn row that names an erased event or memory keeps none of them. Every
    digest becomes ``REDACTED_DIGEST`` (``last_transition_hash``, which may be NULL, is cleared), except the
    reviewer's configuration fingerprint. The rows, their stages and every id stay, for recovery quarantine.
    """
    ids = sorted(set(event_ids) | set(memory_ids))
    if not ids:
        return 0
    from psycopg.types.json import Jsonb

    columns = ("delivery_receipt", "response_review", "prepared_memory_selection", "recall_plan",
               "orientation_route", "orientation_preflight")
    rows = conn.execute(
        "SELECT turn_id,context_fingerprint," + ",".join(columns) + " FROM memory_runtime_turns t "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND EXISTS (SELECT 1 FROM unnest(%s::text[]) i WHERE strpos(t::text, i) > 0)",
        (*params, ids),
    ).fetchall()
    for row in rows:
        values = [Jsonb(redact_digests(row[column])) if row[column] is not None else None for column in columns]
        conn.execute(
            "UPDATE memory_runtime_turns SET input_fingerprint=%s,context_fingerprint=%s,last_transition_hash=NULL,"
            + ",".join(f"{column}=%s" for column in columns)
            + " WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND turn_id=%s",
            (REDACTED_DIGEST, REDACTED_DIGEST if row["context_fingerprint"] is not None else None, *values,
             *params, row["turn_id"]),
        )
    return len(rows)


def redact_legacy_digests(conn, params, *, event_ids=(), memory_ids=()):
    """Digests of erased content in the other rows only older runtimes wrote: feedback contributions (migration 014)
    keep the content hashes of the confirmation and of the delivered answer they cite, and model-call reservations
    (migration 006) the fingerprints of the request and response a learning job sent about its sources."""
    event_ids, memory_ids = sorted(set(event_ids)), sorted(set(memory_ids))
    if not event_ids and not memory_ids:
        return
    conn.execute(
        "UPDATE memory_feedback_contributions SET feedback_content_hash=%s,delivery_content_hash=%s,"
        "source_event_refs=(SELECT coalesce(jsonb_agg(CASE WHEN jsonb_typeof(r)='object' AND r ? 'content_sha256' "
        "THEN r || jsonb_build_object('content_sha256',%s::text) ELSE r END),'[]'::jsonb) "
        "FROM jsonb_array_elements(source_event_refs) r) "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND (source_event_ids && %s::text[] "
        "OR source_memory_ids && %s::text[] OR feedback_event_id=ANY(%s::text[]) OR delivery_event_id=ANY(%s::text[]))",
        (REDACTED_DIGEST, REDACTED_DIGEST, REDACTED_DIGEST, *params, event_ids, memory_ids, event_ids, event_ids),
    )
    conn.execute(
        "UPDATE memory_cognitive_operations o SET request_fingerprint=%s,"
        "response_fingerprint=CASE WHEN o.response_fingerprint IS NULL THEN NULL ELSE %s END "
        "FROM memory_jobs j WHERE j.tenant_id=o.tenant_id AND j.owner_id=o.owner_id AND j.brain_id=o.brain_id "
        "AND j.id=o.job_id AND o.tenant_id=%s AND o.owner_id=%s AND o.brain_id=%s "
        "AND (j.source_event_ids && %s::text[] OR j.source_memory_ids && %s::text[])",
        (REDACTED_DIGEST, REDACTED_DIGEST, *params, event_ids, memory_ids),
    )
