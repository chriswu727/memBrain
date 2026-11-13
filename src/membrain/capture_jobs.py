"""The worker's jobs that every brain runs, with or without a cognition model.

``extract`` and ``rebuild`` publish the literal statement captures of new or rebuilt events and advance the indexed
sequence; ``embed`` stores vectors for them. Background learning (``learning.LearningEngine``) adds its own job kinds
on top of these and is only used when a semantic processor is configured.
"""
from . import cognition
from .helpers import DomainError, uid
from .jobs import JobStore

_FAILURE_CODES = frozenset({
    "source_unavailable", "context_stale", "budget_exceeded", "provider_uncertain", "recording_paused",
    "recording_stale",
})


def capture(service, jobs, principal, brain_id, job):
    from .service import reading

    # Only reads: the captures are published below under the exclusive lock, and only for events still current.
    with reading(), service.database.transaction(principal) as conn:
        brain = service._brain(conn, principal, brain_id)
        event_ids = ([job["payload"]["event_id"]] if job["kind"] == "extract"
                     else job["payload"].get("event_ids", []))
        events = service._events(conn, principal, brain, event_ids=event_ids[:128], limit=128)
        if job["kind"] == "extract":
            events = [e for e in events if e["revision"] == job["payload"]["revision"]]
        memories = [(event, service._current_captures(conn, principal, brain, event)) for event in events]

    def publish(conn, _):
        brain = service._brain(conn, principal, brain_id)
        current = {(e["event_id"], e["revision"]) for e in service._events(
            conn, principal, brain, event_ids=event_ids[:128], limit=128)}
        for event, captures in memories:
            if (event["event_id"], event["revision"]) in current:
                blocked = service._superseded_evidence(conn, principal, brain, [event["event_id"]])
                for memory in captures:
                    if not any(cognition.evidence_overlaps(ref, old) for ref in memory["evidence_refs"] for old in blocked):
                        service._publish(conn, principal, brain, memory)
        if len(event_ids) > 128:
            service._job(conn, principal, brain, "rebuild", {"event_ids": event_ids[128:]})
        # Runs under the exclusive brain lock once per indexed message. A brain the statistics have not seen yet
        # (any new one, or one that just took a bulk import) is estimated at one row, and the planner then
        # compares every pending job with every event (seconds at a few thousand messages, while reads wait).
        # The hash join answers the same query in milliseconds at any size; the setting is restored after it.
        nestloop = conn.execute("SELECT current_setting('enable_nestloop') AS value").fetchone()["value"]
        conn.execute("SELECT set_config('enable_nestloop','off',true)")
        pending = conn.execute(
            "SELECT min(e.sequence) AS value FROM memory_events e JOIN memory_jobs j ON "
            "j.tenant_id=e.tenant_id AND j.brain_id=e.brain_id AND j.payload->>'event_id'=e.id "
            "AND (j.payload->>'revision')::bigint=e.revision "
            "WHERE e.tenant_id=%s AND e.owner_id=%s AND e.brain_id=%s AND j.kind='extract' "
            "AND j.state<>'completed' AND j.id<>%s", (*service._params(principal, brain_id), job["id"]),
        ).fetchone()["value"]
        conn.execute("SELECT set_config('enable_nestloop',%s,true)", (nestloop,))
        indexed = brain["durable_sequence"] if pending is None else pending - 1
        conn.execute("UPDATE memory_brains SET indexed_sequence=%s WHERE tenant_id=%s AND owner_id=%s AND id=%s",
                     (indexed, *service._params(principal, brain_id)))

    jobs.complete(principal, brain_id, job["id"], lease_token=job["lease_token"], fence=job["fence"], publish=publish)


def execute(service, jobs, principal, brain_id, job, *, semantic=None):
    """Run one claimed job. ``semantic`` runs ``orient`` and ``consolidate`` jobs; without it they are not claimed."""
    try:
        if job["kind"] in ("extract", "rebuild"):
            capture(service, jobs, principal, brain_id, job)
        elif job["kind"] in ("orient", "consolidate") and semantic is not None:
            semantic(principal, brain_id, job)
        elif job["kind"] == "embed":
            from .vector_jobs import embed_memory

            embed_memory(service, principal, brain_id, job)
    except Exception as error:
        try:
            jobs.fail(principal, brain_id, job["id"], lease_token=job["lease_token"], fence=job["fence"],
                      failure_code=error.code if isinstance(error, DomainError) and error.code in _FAILURE_CODES
                      else "internal_error",
                      retry=not isinstance(error, DomainError),
                      retry_delay_seconds=(60 * 2 ** min(job["attempts"] - 1, 5)
                                           if job["kind"] == "consolidate" else 0))
        except DomainError:
            pass
        raise


def run_next(service, jobs, principal, brain_id, kinds, run):
    """Claim and run the next job of these kinds (plus ``embed`` with an embedding provider); return the work done."""
    kinds = list(kinds)
    if service.embedding_provider:
        kinds.append("embed")
    job = jobs.claim(principal, brain_id, worker_id=uid(), kinds=kinds, lease_seconds=120)
    if job is None and service.embedding_provider:
        from .vector_jobs import backfill_embeddings

        if backfill_embeddings(service, principal, brain_id):
            job = jobs.claim(principal, brain_id, worker_id=uid(), kinds=kinds, lease_seconds=120)
    if job is None:
        return 0
    if job["kind"] == "embed" and not getattr(service.embedding_provider, "metered", True):
        from .vector_jobs import embed_local_batch

        return embed_local_batch(service, principal, brain_id, job)
    run(principal, brain_id, job)
    return 1


def work_once(service, principal, brain_id):
    """One worker step for a brain without background learning: capture, rebuild or embed."""
    jobs = JobStore(service.database)
    return run_next(service, jobs, principal, brain_id, ("extract", "rebuild"),
                    lambda principal, brain_id, job: execute(service, jobs, principal, brain_id, job))
