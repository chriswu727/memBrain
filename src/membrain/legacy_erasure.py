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
