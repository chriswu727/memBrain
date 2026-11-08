from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from psycopg.types.json import Jsonb
from test_jobs import jobs as jobs
from test_learning import learning as learning
from test_learning_recovery import operation_rows, retry
from test_learning_windows import claim, execute, observations

from membrain.helpers import DomainError
from membrain.jobs import JobStore
from membrain.learning import LearningEngine
from membrain.recording_control import set_recording
from membrain.service import MemoryService

pytestmark = pytest.mark.integration


def pause(harness, resume=False):
    service = getattr(harness, "service", None) or MemoryService(harness.database)
    set_recording(service, harness.principal, harness.brain, paused=True, expected_revision=0)
    if resume:
        set_recording(service, harness.principal, harness.brain, paused=False, expected_revision=1)


@pytest.mark.parametrize("kind", ["orient", "consolidate"])
def test_pause_leaves_unstarted_learning_queued_without_spending_attempts(jobs, kind):
    identifier = jobs.enqueue(kind)
    pause(jobs)
    assert jobs.claim(job_id=identifier) is None
    row = jobs.store.get(jobs.principal, jobs.brain, identifier)
    assert row["state"] == "queued" and row["attempts"] == row["model_calls"] == 0
    assert jobs.claim(job_id=jobs.job_id)["kind"] == "extract"
    service = MemoryService(jobs.database)
    set_recording(service, jobs.principal, jobs.brain, paused=False, expected_revision=1)
    selected = jobs.claim(job_id=identifier)
    assert selected["recording_revision"] == 2


@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("method", ["renew", "reserve_operation", "complete"])
def test_active_learning_cannot_renew_spend_or_publish_after_policy_changes(jobs, resume, method):
    jobs.job_id = jobs.enqueue("consolidate")
    jobs.claim(job_id=jobs.job_id)
    pause(jobs, resume)
    published = []
    with pytest.raises(DomainError) as error:
        if method == "reserve_operation":
            jobs.reserve()
        else:
            options = {"publish": lambda *_: published.append(True)} if method == "complete" else {}
            jobs.call(method, **jobs.lease(), **options)
    assert error.value.code == ("recording_stale" if resume else "recording_paused")
    assert not published
    assert jobs.call("get")["model_calls"] == 0


@pytest.mark.parametrize("resume", [False, True])
def test_claimed_learning_checks_policy_before_building_snapshot_or_calling_model(learning, resume):
    observations(learning, 1)
    selected = claim(learning)
    pause(learning, resume)
    with pytest.raises(DomainError) as error:
        execute(learning, selected)
    assert error.value.code == ("recording_stale" if resume else "recording_paused")
    row = learning.job(selected["id"])
    assert row["state"] == "cancelled" and row["last_error"] == error.value.code
    assert row["result"] is None and row["model_calls"] == 0
    assert learning.calls == []


@pytest.mark.parametrize("resume", [False, True])
def test_pause_during_proposal_settles_usage_but_stops_verification_and_publication(learning, resume):
    observations(learning, 1)
    selected = claim(learning)
    learning.during_proposal = lambda _: pause(learning, resume)
    with pytest.raises(DomainError) as error:
        execute(learning, selected)
    assert error.value.code == ("recording_stale" if resume else "recording_paused")
    row = learning.job(selected["id"])
    assert row["state"] == "cancelled" and row["last_error"] == error.value.code
    assert learning.calls == ["proposal"] and row["model_calls"] == 1
    operations = operation_rows(learning)
    assert len(operations) == 1 and operations[0]["outcome"] == "completed"
    assert "publication" not in row["result"] and learning.working() is None
    if not resume:
        with pytest.raises(DomainError) as blocked:
            retry(learning, row)
        assert blocked.value.code == "recording_paused"
        assert "recovery_job_id" not in learning.job(row["id"])["payload"]
        set_recording(learning.service, learning.principal, learning.brain,
                      paused=False, expected_revision=1)
    learning.during_proposal = None
    recovered = retry(learning, row)
    fresh = claim(learning, recovered["id"])
    assert fresh["recording_revision"] == 2
    assert execute(learning, fresh)["state"] == "completed"
    assert learning.job(row["id"])["model_calls"] == 1


def test_worker_keeps_existing_history_indexable_while_learning_is_paused(learning):
    observations(learning, 1)
    pause(learning)
    engine = LearningEngine(learning.service)
    for _ in range(10):
        if not engine.work_once(learning.principal, learning.brain):
            break
    else:
        pytest.fail("Paused worker did not become idle")
    assert learning.calls == []
    assert claim(learning) is None


def test_retry_after_restart_preserves_original_recording_revision(jobs):
    jobs.job_id = jobs.enqueue("consolidate")
    jobs.claim(job_id=jobs.job_id)
    jobs.call("fail", **jobs.lease(), failure_code="provider_failed")
    pause(jobs, True)
    jobs.store = JobStore(jobs.database)
    selected = jobs.claim(job_id=jobs.job_id)
    assert selected["recording_revision"] == 0
    with pytest.raises(DomainError) as error:
        jobs.reserve()
    assert error.value.code == "recording_stale"


def test_claim_rechecks_pause_after_unlocked_availability_probe(jobs, monkeypatch):
    jobs.job_id = jobs.enqueue("consolidate")
    probe = jobs.store._may_claim

    def race(*args):
        found = probe(*args)
        assert found
        pause(jobs)
        return found

    monkeypatch.setattr(jobs.store, "_may_claim", race)
    assert jobs.claim(job_id=jobs.job_id) is None
    assert jobs.call("get")["attempts"] == 0


def test_legacy_started_job_does_not_acquire_new_recording_authority(jobs):
    jobs.job_id = jobs.enqueue("consolidate")
    with jobs.database.transaction(jobs.principal) as conn:
        conn.execute("UPDATE memory_jobs SET attempts=1 WHERE id=%s AND tenant_id=%s AND brain_id=%s",
                     (jobs.job_id, jobs.principal.tenant_id, jobs.brain))
    pause(jobs, True)
    assert jobs.claim(job_id=jobs.job_id)["recording_revision"] == 0
    with pytest.raises(DomainError) as error:
        jobs.reserve()
    assert error.value.code == "recording_stale"


@pytest.mark.parametrize("resume", [False, True])
def test_policy_changed_after_verification_prevents_final_publication(learning, monkeypatch, resume):
    observations(learning, 1)
    selected = claim(learning)
    engine = LearningEngine(learning.service)
    complete = engine.jobs.complete

    def race(*args, **kwargs):
        pause(learning, resume)
        return complete(*args, **kwargs)

    monkeypatch.setattr(engine.jobs, "complete", race)
    with pytest.raises(DomainError) as error:
        engine._execute(learning.principal, learning.brain, selected)
    assert error.value.code == ("recording_stale" if resume else "recording_paused")
    assert learning.calls == ["proposal", "verification"]
    row = learning.job(selected["id"])
    assert row["state"] == "cancelled" and "publication" not in row["result"]
    assert len(operation_rows(learning)) == 2
    assert all(item["outcome"] == "completed" for item in operation_rows(learning))


def test_pause_waits_for_already_locked_learning_publication(jobs, monkeypatch):
    jobs.job_id = jobs.enqueue("consolidate")
    jobs.claim(job_id=jobs.job_id)
    publishing, pause_started, release = Event(), Event(), Event()
    lock_brain = MemoryService._brain

    def lock_for_pause(*args, **kwargs):
        pause_started.set()
        return lock_brain(*args, **kwargs)

    monkeypatch.setattr(MemoryService, "_brain", lock_for_pause)

    def publish(conn, row):
        publishing.set()
        assert release.wait(5)
        conn.execute("UPDATE memory_jobs SET result=%s WHERE tenant_id=%s AND brain_id=%s AND id=%s",
                     (Jsonb({"published": True}), jobs.principal.tenant_id, jobs.brain, row["id"]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        done = pool.submit(jobs.call, "complete", **jobs.lease(), publish=publish)
        try:
            assert publishing.wait(5)
            control = pool.submit(pause, jobs)
            assert pause_started.wait(5)
            assert not control.done()
        finally:
            release.set()
        done.result(timeout=5)
        control.result(timeout=5)
    assert jobs.call("get")["state"] == "completed"
