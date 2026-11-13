"""Erasure of derived rows that the runtime no longer writes.

Older installations, configured profiles and restored archives can still hold these rows, so editing or forgetting
their sources must keep clearing them. Plain SQL only: this module must not import the code that used to write them.
``params`` is ``(tenant_id, owner_id, brain_id)``, as ``MemoryService._params`` returns it.
"""


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
