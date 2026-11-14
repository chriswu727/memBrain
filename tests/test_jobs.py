import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from psycopg.types.json import Jsonb

from membrain.config import Settings
from membrain.helpers import DomainError, Principal, digest, uid
from membrain.jobs import JobStore
from membrain.service import MemoryService
from membrain.storage import Database

pytestmark = pytest.mark.integration


class Jobs:
    def __init__(self, database):
        self.database = database
        self.store = JobStore(database)
        self.principal = Principal(uid(), uid())
        self.brain = MemoryService(database).create_brain(self.principal, "Durable background jobs")["id"]
        self.job_id = self.enqueue()
        self.claimed = None

    def enqueue(self, kind="extract", payload=None):
        job_id = uid()
        payload = payload or {"event_id": uid(), "revision": 7, "private": "Never put this in monitoring."}
        with self.database.transaction(self.principal) as conn:
            conn.execute(
                "INSERT INTO memory_jobs(tenant_id,owner_id,brain_id,id,kind,payload) VALUES(%s,%s,%s,%s,%s,%s)",
                (self.principal.tenant_id, self.principal.principal_id, self.brain, job_id, kind, Jsonb(payload)),
            )
        return job_id

    def claim(self, **kwargs):
        self.claimed = self.store.claim(self.principal, self.brain, worker_id=uid(), **kwargs)
        return self.claimed

    def call(self, method, **kwargs):
        return getattr(self.store, method)(self.principal, self.brain, self.job_id, **kwargs)

    def lease(self):
        return {"lease_token": self.claimed["lease_token"], "fence": self.claimed["fence"]}

    def expire(self):
        with self.database.transaction(self.principal) as conn:
            conn.execute(
                "UPDATE memory_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' "
                "WHERE tenant_id=%s AND brain_id=%s AND id=%s",
                (self.principal.tenant_id, self.brain, self.job_id),
            )


@pytest.fixture
def jobs():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("MEMORY_DATABASE_URL must point to the dedicated test database")
    return Jobs(Database(settings.database_url))


def test_concurrent_claims_have_one_owner_and_exact_payload(jobs):
    barrier = Barrier(2)

    def claim():
        barrier.wait()
        return JobStore(jobs.database).claim(jobs.principal, jobs.brain, worker_id=uid())

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim(), range(2)))
    claimed = [item for item in claims if item is not None]
    assert len(claimed) == 1
    assert claimed[0]["payload"]["revision"] == 7
    assert claimed[0]["payload"]["private"] == "Never put this in monitoring."
    assert claimed[0]["attempts"] == claimed[0]["fence"] == 1
    assert jobs.call("get")["lease_active"]


def test_a_job_created_before_the_clock_stepped_back_is_still_due(jobs):
    """After a backward step of the wall clock a new job's default times lie in the future; it was never delayed."""
    with jobs.database.transaction(jobs.principal) as conn:
        conn.execute(
            # One value for both columns, as their shared default gives; two clock readings would differ.
            "UPDATE memory_jobs SET created_at=now()+interval '40 seconds',"
            "available_at=now()+interval '40 seconds' WHERE tenant_id=%s AND brain_id=%s AND id=%s",
            (jobs.principal.tenant_id, jobs.brain, jobs.job_id))
    assert jobs.claim()["id"] == jobs.job_id


def test_a_retry_delay_still_waits(jobs):
    with jobs.database.transaction(jobs.principal) as conn:
        conn.execute(
            "UPDATE memory_jobs SET available_at=clock_timestamp()+interval '40 seconds' "
            "WHERE tenant_id=%s AND brain_id=%s AND id=%s", (jobs.principal.tenant_id, jobs.brain, jobs.job_id))
    assert jobs.claim() is None


def test_exact_claim_and_kind_filter_do_not_take_another_turn_job(jobs):
    current = jobs.enqueue("orientation", {"turn_id": "current"})
    later = jobs.enqueue("orientation", {"turn_id": "later"})
    assert jobs.claim(job_id=current, kinds=["extract"]) is None
    claimed = jobs.claim(job_id=current, kinds=["orientation"])
    assert claimed["id"] == current
    assert claimed["payload"] == {"turn_id": "current"}
    assert jobs.claim(job_id=current) is None
    assert jobs.claim(kinds=["orientation"])["id"] == later
    assert jobs.claim()["id"] == jobs.job_id


def test_expired_claim_fences_old_worker_after_restart(jobs):
    old = jobs.claim()
    jobs.expire()
    jobs.store = JobStore(jobs.database)
    assert jobs.claim()["fence"] == old["fence"] + 1
    invoked = []
    for method, extra in (
        ("renew", {}),
        ("complete", {"publish": lambda *_: invoked.append(True)}),
        ("fail", {"failure_code": "provider_failed"}),
    ):
        with pytest.raises(DomainError, match="expired, or fenced"):
            jobs.call(method, lease_token=old["lease_token"], fence=old["fence"], **extra)
    assert not invoked
    assert jobs.call("renew", **jobs.lease())["lease_active"]


def test_publish_and_completion_are_atomic_and_do_not_run_twice(jobs):
    jobs.claim()
    original = "Durable background jobs"

    def failing_publish(conn, row):
        conn.execute("UPDATE memory_brains SET name='rolled back' WHERE id=%s", (row["brain_id"],))
        raise DomainError("context_stale", "Evidence changed while the model was running.")

    with pytest.raises(DomainError, match="Evidence changed"):
        jobs.call("complete", **jobs.lease(), publish=failing_publish)
    with jobs.database.transaction(jobs.principal) as conn:
        assert conn.execute("SELECT name FROM memory_brains WHERE id=%s", (jobs.brain,)).fetchone()["name"] == original
    assert jobs.call("get")["state"] == "running"
    called = []

    def publish(conn, row):
        called.append(row["payload"])
        conn.execute("UPDATE memory_brains SET name='published' WHERE id=%s", (row["brain_id"],))
        return {"published": True}

    assert jobs.call("complete", **jobs.lease(), publish=publish) == {"published": True}
    with pytest.raises(DomainError, match="lease"):
        jobs.call("complete", **jobs.lease(), publish=publish)
    assert len(called) == 1
    assert jobs.call("get")["state"] == "completed"


def test_lease_expiry_during_publish_rolls_back_changes(jobs):
    jobs.claim()

    def publish(conn, row):
        conn.execute("UPDATE memory_brains SET name='must roll back' WHERE id=%s", (row["brain_id"],))
        conn.execute("UPDATE memory_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s", (row["id"],))

    with pytest.raises(DomainError, match="expired"):
        jobs.call("complete", **jobs.lease(), publish=publish)
    with jobs.database.transaction(jobs.principal) as conn:
        assert conn.execute("SELECT name FROM memory_brains WHERE id=%s", (jobs.brain,)).fetchone()["name"] == "Durable background jobs"
    assert jobs.call("get")["state"] == "running"


def test_retry_delay_attempt_limit_and_terminal_failure(jobs):
    jobs.claim(max_attempts=2)
    jobs.call("fail", **jobs.lease(), failure_code="provider_failed", retry_delay_seconds=30)
    assert jobs.claim(max_attempts=2) is None
    with jobs.database.transaction(jobs.principal) as conn:
        conn.execute("UPDATE memory_jobs SET available_at=clock_timestamp() WHERE id=%s", (jobs.job_id,))
    assert jobs.claim(max_attempts=2)["attempts"] == 2
    jobs.call("fail", **jobs.lease(), failure_code="provider_failed")
    assert jobs.claim(max_attempts=2) is None
    jobs.claim(max_attempts=3)
    jobs.call("fail", **jobs.lease(), failure_code="superseded", retry=False)
    assert jobs.call("get")["state"] == "superseded"
    assert jobs.claim(max_attempts=100) is None


def test_failure_codes_are_redacted_and_monitoring_shows_no_payload(jobs):
    jobs.claim()
    with pytest.raises(DomainError, match="redacted failure code"):
        jobs.call("fail", **jobs.lease(), failure_code="Private network response")
    monitoring = json.dumps(jobs.store.list(jobs.principal, jobs.brain))
    assert "Never put this" not in monitoring
    assert jobs.claimed["lease_token"] not in monitoring
    assert "payload" not in monitoring


def test_cognitive_operation_and_budget_tables_enforce_rls(jobs):
    """The removed cognition pipeline's reservations and budget, as an older runtime stored them, stay private."""
    jobs.claim()
    with jobs.database.transaction(jobs.principal) as conn:
        conn.execute(
            "INSERT INTO memory_cognitive_operations(tenant_id,owner_id,brain_id,job_id,operation_id,request_fingerprint,"
            "input_bytes,fence) VALUES(%s,%s,%s,%s,%s,%s,100,%s)",
            (jobs.principal.tenant_id, jobs.principal.principal_id, jobs.brain, jobs.job_id, uid(), digest("request"),
             jobs.claimed["fence"]))
        conn.execute(
            "INSERT INTO memory_cognitive_budgets(tenant_id,owner_id,brain_id,window_seconds,max_model_calls,"
            "max_input_bytes) VALUES(%s,%s,%s,3600,100,2000000)",
            (jobs.principal.tenant_id, jobs.principal.principal_id, jobs.brain))
    for outsider in (Principal(jobs.principal.tenant_id, uid()), Principal(uid(), jobs.principal.principal_id)):
        with jobs.database.transaction(outsider) as conn:
            for table in ("memory_cognitive_operations", "memory_cognitive_budgets"):
                assert conn.execute(f"SELECT * FROM {table} WHERE brain_id=%s", (jobs.brain,)).fetchall() == []
        with pytest.raises(DomainError, match="Brain is unavailable"):
            jobs.store.get(outsider, jobs.brain, jobs.job_id)
    with jobs.database.transaction(jobs.principal) as conn:
        rows = conn.execute(
            "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE relname=ANY(%s)", (["memory_cognitive_operations", "memory_cognitive_budgets"],),
        ).fetchall()
        assert len(rows) == 2
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
