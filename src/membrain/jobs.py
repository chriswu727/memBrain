import hashlib
import secrets
from contextlib import contextmanager

from .helpers import DomainError, _identifier, _integer

FAILURE_CODES = frozenset({
    "provider_failed", "provider_uncertain", "invalid_proposal", "source_unavailable",
    "context_stale", "superseded", "budget_exceeded", "cancelled", "dependency_unavailable", "internal_error",
    "recording_paused", "recording_stale",
})
PUBLIC_FIELDS = (
    "id", "brain_id", "kind", "state", "attempts", "fence", "lease_expires_at", "available_at",
    "model_calls", "input_bytes", "max_model_calls", "max_input_bytes", "last_error",
    "created_at", "updated_at", "completed_at",
)
# The jobs a claim may take; parameters: tenant, owner, brain, max_attempts, kinds, kinds, job_id, job_id.
# A job is due when its time has come, or when it was never delayed: ``available_at`` and ``created_at`` default to
# the same transaction time, and only a retry moves ``available_at`` later. Comparing a never-delayed job with the
# clock made it wait whenever the wall clock had stepped back since it was created (NTP, a resumed virtual machine,
# WSL), by as long as the step. Background learning was removed: the ``orient`` and ``consolidate`` jobs an older
# runtime left (queued, failed, deferred, or running under an expired lease) are never claimed again, whatever kinds
# a caller asks for; they stay readable, and erasure still clears them with their sources.
_CLAIMABLE = (
    "tenant_id=%s AND owner_id=%s AND brain_id=%s "
    "AND attempts<%s AND (available_at<=created_at OR available_at<=clock_timestamp()) "
    "AND NOT payload ? 'recovery_job_id' "
    "AND NOT EXISTS (SELECT 1 FROM memory_recovery_quarantine q WHERE q.tenant_id=memory_jobs.tenant_id "
    "AND q.owner_id=memory_jobs.owner_id AND q.brain_id=memory_jobs.brain_id "
    "AND q.object_kind='job' AND q.object_id=memory_jobs.id) "
    "AND (state IN ('queued','failed') OR (state='running' AND lease_expires_at<=clock_timestamp())) "
    "AND (%s::text[] IS NULL OR kind=ANY(%s::text[])) "
    "AND (%s::text IS NULL OR id=%s) "
    "AND kind NOT IN ('orient','consolidate') "
)


class JobStore:
    def __init__(self, database):
        self.database = database

    def _params(self, principal, brain_id):
        return principal.tenant_id, principal.principal_id, _identifier(brain_id)

    @contextmanager
    def _transaction(self, principal, brain_id):
        with self.database.transaction(principal) as conn:
            conn.execute("SELECT set_config('statement_timeout','5000',true)")
            conn.execute("SELECT set_config('lock_timeout','2000',true)")
            brain = conn.execute(
                "SELECT * FROM memory_brains WHERE tenant_id=%s AND owner_id=%s AND id=%s FOR UPDATE",
                self._params(principal, brain_id),
            ).fetchone()
            if brain is None:
                raise DomainError("not_found_or_forbidden", "Brain is unavailable.")
            from .recovery_authority import reconcile_brain

            reconcile_brain(self.database, conn, principal, brain)
            yield conn, brain

    def _row(self, conn, principal, brain_id, job_id):
        row = conn.execute(
            "SELECT *,clock_timestamp() AS db_now FROM memory_jobs "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s FOR UPDATE",
            (*self._params(principal, brain_id), _identifier(job_id)),
        ).fetchone()
        if row is None:
            raise DomainError("not_found_or_forbidden", "Job is unavailable.")
        return row

    def _lease(self, row, lease_token, fence):
        token_digest = hashlib.sha256(_identifier(lease_token).encode()).hexdigest()
        if (row["state"] != "running" or row["fence"] != _integer(fence, 1)
                or not row["lease_token_digest"]
                or not secrets.compare_digest(row["lease_token_digest"], token_digest)
                or not row["lease_expires_at"] or row["lease_expires_at"] <= row["db_now"]):
            raise DomainError("lease_conflict", "Job lease is missing, expired, or fenced.")

    def _public(self, row):
        result = {key: row[key] for key in PUBLIC_FIELDS}
        result["lease_active"] = bool(row["state"] == "running" and row["lease_expires_at"]
                                      and row["lease_expires_at"] > row["db_now"])
        if result["last_error"] not in FAILURE_CODES:
            result["last_error"] = "internal_error" if result["last_error"] else None
        for key in ("lease_expires_at", "available_at", "created_at", "updated_at", "completed_at"):
            if result[key] is not None:
                result[key] = result[key].isoformat()
        return result

    def get(self, principal, brain_id, job_id):
        with self._transaction(principal, brain_id) as (conn, _):
            return self._public(self._row(conn, principal, brain_id, job_id))

    def list(self, principal, brain_id, *, limit=100):
        _integer(limit, 1, 200)
        with self._transaction(principal, brain_id) as (conn, _):
            rows = conn.execute(
                "SELECT *,clock_timestamp() AS db_now FROM memory_jobs "
                "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                "ORDER BY updated_at DESC,id LIMIT %s",
                (*self._params(principal, brain_id), limit),
            )
            return [self._public(row) for row in rows]

    def _may_claim(self, principal, brain_id, claimable):
        """Whether a claim could find work, read without locking the brain row.

        A worker polls every brain about once a second. Taking the row ``FOR UPDATE`` only to find nothing to do held
        off every reader that arrived meanwhile (readers share the row, see ``MemoryService._brain``). This reads the
        brain and its jobs under no row lock, and answers yes whenever the locked claim could do anything: a job
        matches, or the recovery registry holds an erasure the database has not applied (the locked path applies it,
        as every exclusive access does). Only a no is acted on, so the claim, its lock order, lease, fence and
        ordering are unchanged; a job queued after this read is found by the next poll, as it would have been had
        the poll run a moment earlier.
        """
        from .recovery_authority import pending_erasure

        with self.database.transaction(principal) as conn:
            conn.execute("SELECT set_config('statement_timeout','5000',true)")
            conn.execute("SELECT set_config('lock_timeout','2000',true)")
            brain = conn.execute("SELECT * FROM memory_brains WHERE tenant_id=%s AND owner_id=%s AND id=%s",
                                 self._params(principal, brain_id)).fetchone()
            if brain is None:
                raise DomainError("not_found_or_forbidden", "Brain is unavailable.")
            if pending_erasure(self.database, conn, principal, brain):
                return True
            return conn.execute("SELECT EXISTS (SELECT 1 FROM memory_jobs WHERE " + _CLAIMABLE + ") AS found",
                                (*self._params(principal, brain_id), *claimable)).fetchone()["found"]

    def claim(self, principal, brain_id, *, worker_id, lease_seconds=60, kinds=None, max_attempts=3, job_id=None):
        _identifier(worker_id)
        _integer(lease_seconds, 1, 3600)
        _integer(max_attempts, 1, 100)
        if job_id is not None:
            _identifier(job_id)
        if kinds is not None:
            if not isinstance(kinds, (list, tuple)) or not 1 <= len(kinds) <= 32:
                raise DomainError("validation_failed", "Job kinds must be a bounded nonempty list.")
            kinds = [_identifier(kind) for kind in kinds]
        claimable = (max_attempts, kinds, kinds, job_id, job_id)
        if not self._may_claim(principal, brain_id, claimable):
            return None
        with self._transaction(principal, brain_id) as (conn, _):
            params = self._params(principal, brain_id)
            row = conn.execute(
                "SELECT * FROM memory_jobs WHERE " + _CLAIMABLE
                + "ORDER BY CASE kind WHEN 'extract' THEN 0 WHEN 'rebuild' THEN 1 ELSE 2 END,created_at,id "
                "LIMIT 1 FOR UPDATE SKIP LOCKED",
                (*params, *claimable),
            ).fetchone()
            if row is None:
                return None
            token = secrets.token_urlsafe(32)
            row = conn.execute(
                "UPDATE memory_jobs SET state='running',attempts=attempts+1,fence=fence+1,worker_id=%s,"
                "lease_token_digest=%s,lease_expires_at=clock_timestamp()+make_interval(secs=>%s),"
                "updated_at=clock_timestamp(),completed_at=NULL WHERE tenant_id=%s AND owner_id=%s "
                "AND brain_id=%s AND id=%s RETURNING *,clock_timestamp() AS db_now",
                (worker_id, hashlib.sha256(token.encode()).hexdigest(), lease_seconds, *params, row["id"]),
            ).fetchone()
            result = self._public(row)
            result.update(payload=row["payload"], recording_revision=row["recording_revision"],
                          worker_id=worker_id, lease_token=token)
            return result

    def renew(self, principal, brain_id, job_id, *, lease_token, fence, lease_seconds=60):
        _integer(lease_seconds, 1, 3600)
        with self._transaction(principal, brain_id) as (conn, _):
            current = self._row(conn, principal, brain_id, job_id)
            self._lease(current, lease_token, fence)
            row = conn.execute(
                "UPDATE memory_jobs SET lease_expires_at=clock_timestamp()+make_interval(secs=>%s),"
                "updated_at=clock_timestamp() WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s "
                "RETURNING *,clock_timestamp() AS db_now",
                (lease_seconds, *self._params(principal, brain_id), job_id),
            ).fetchone()
            return self._public(row)

    def complete(self, principal, brain_id, job_id, *, lease_token, fence, publish=None):
        with self._transaction(principal, brain_id) as (conn, _):
            row = self._row(conn, principal, brain_id, job_id)
            self._lease(row, lease_token, fence)
            result = publish(conn, row) if publish is not None else None
            self._lease(self._row(conn, principal, brain_id, job_id), lease_token, fence)
            completed = conn.execute(
                "UPDATE memory_jobs SET state='completed',lease_token_digest=NULL,lease_expires_at=NULL,"
                "worker_id=NULL,last_error=NULL,completed_at=clock_timestamp(),updated_at=clock_timestamp() "
                "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s "
                "AND lease_expires_at>clock_timestamp() RETURNING id",
                (*self._params(principal, brain_id), job_id),
            ).fetchone()
            if completed is None:
                raise DomainError("lease_conflict", "Job lease expired before publication completed.")
            return result

    def fail(self, principal, brain_id, job_id, *, lease_token, fence, failure_code,
             retry=True, retry_delay_seconds=0):
        if failure_code not in FAILURE_CODES or type(retry) is not bool:
            raise DomainError("validation_failed", "Job failure must use a redacted failure code.")
        _integer(retry_delay_seconds, 0, 2_592_000)
        with self._transaction(principal, brain_id) as (conn, _):
            self._lease(self._row(conn, principal, brain_id, job_id), lease_token, fence)
            params = (*self._params(principal, brain_id), job_id)
            row = conn.execute(
                "UPDATE memory_jobs SET state=%s,lease_token_digest=NULL,lease_expires_at=NULL,worker_id=NULL,"
                "last_error=%s,available_at=clock_timestamp()+make_interval(secs=>%s),updated_at=clock_timestamp() "
                "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s RETURNING *,clock_timestamp() AS db_now",
                ("failed" if retry else ("superseded" if failure_code == "superseded" else "cancelled"),
                 failure_code, retry_delay_seconds, *params),
            ).fetchone()
            return self._public(row)
