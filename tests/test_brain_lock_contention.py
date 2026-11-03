"""Readers of one brain share its row; writers, erasure and recovery still exclude them (R5, gap 20)."""
import threading
import time
import uuid

import pytest
from test_learning import learning as learning
from test_recovery_erasure import pending, raw_event
from test_recovery_erasure import recovery as recovery

from membrain.client import default_budget, default_read_fence
from membrain.contracts import CONTRACT_VERSION
from membrain.helpers import uid
from membrain.notes import store_note
from membrain.service import MemoryService

pytestmark = pytest.mark.integration


def recall_request(harness, query, *, request_id=None, wall_ms=1000):
    return {"message_type": "request", "contract_version": CONTRACT_VERSION,
            "request_id": request_id or str(uuid.uuid4()), "action": "recall",
            "target": {"brain_ref": harness.brain},
            "payload": {"query": query, "intent": "explore", "cue_event_ids": [], "additional_cues": [],
                        "read_fence": default_read_fence(),
                        "budget": {**default_budget(16000), "max_wall_time_ms": wall_ms}}}


class Held:
    """Stops the first recall inside its transaction, after it has read the brain row, until released."""

    def __init__(self, harness, monkeypatch):
        self.inside, self.release, self.calls = threading.Event(), threading.Event(), 0
        original = harness.service._working

        def working(*args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                self.inside.set()
                assert self.release.wait(20)
            return original(*args, **kwargs)

        monkeypatch.setattr(harness.service, "_working", working)

    def run(self, target):
        results = {}

        def call():
            try:
                results["value"] = target()
            except BaseException as error:  # noqa: BLE001 - the main thread asserts on it
                results["error"] = error

        thread = threading.Thread(target=call, daemon=True)
        thread.start()
        assert self.inside.wait(20)
        return thread, results


def held_recall(harness, monkeypatch, check):
    harness.observe("The Vancouver library appointment is on Friday.")
    held = Held(harness, monkeypatch)
    thread, first = held.run(lambda: harness.service.handle(
        harness.principal, recall_request(harness, "library appointment", wall_ms=20000)))
    try:
        check()
    finally:
        held.release.set()
        thread.join(20)
    assert first["value"]["outcome"] == "completed", first


def test_a_recall_in_progress_does_not_block_another_recall(recovery, monkeypatch):
    harness, _ = recovery

    def second():
        # Before: the first recall held the brain row FOR UPDATE, so this one failed with budget_exceeded after
        # its 1 s deadline.
        response = harness.service.handle(harness.principal, recall_request(harness, "library appointment"))
        assert response["outcome"] == "completed", response

    held_recall(harness, monkeypatch, second)


def test_a_recall_in_progress_does_not_make_the_map_busy(recovery, monkeypatch):
    harness, _ = recovery
    # Before: the map waited 500 ms for the row the recall held and answered 503 "Memory is busy updating".
    held_recall(harness, monkeypatch, lambda: harness.memory.memory_map()["nodes"])


def test_an_erasure_still_waits_for_reads_and_reads_wait_for_it(recovery, monkeypatch):
    harness, authority = recovery
    secret = harness.observe("The locker code is 4471.")["accepted_event_ids"][0]
    held = Held(harness, monkeypatch)
    thread, first = held.run(lambda: harness.service.handle(
        harness.principal, recall_request(harness, "locker code", wall_ms=20000)))
    erased = threading.Event()

    def forget():
        harness.memory.forget([secret], kind="events", mode="erase_content", expected_scope_generation=1)
        erased.set()

    eraser = threading.Thread(target=forget, daemon=True)
    eraser.start()
    try:
        assert not erased.wait(1), "an erasure ran while a read held the brain"
    finally:
        held.release.set()
        thread.join(20)
    eraser.join(20)
    assert erased.is_set() and first["value"]["outcome"] == "completed"
    assert raw_event(harness, secret) == {"document": None, "deleted": True}
    after = harness.service.handle(harness.principal, recall_request(harness, "locker code"))
    assert "4471" not in str(after)
    assert all(item["event_id"] != secret for item in harness.service.timeline(harness.principal, harness.brain)["items"])


def test_a_pending_erasure_is_applied_before_a_shared_read(recovery):
    harness, authority = recovery
    secret = harness.observe("The alarm code is 9932.")["accepted_event_ids"][0]
    pending(harness, authority, secret)
    response = harness.service.handle(harness.principal, recall_request(harness, "alarm code"))
    assert response["outcome"] == "completed" and "9932" not in str(response)
    assert raw_event(harness, secret) == {"document": None, "deleted": True}
    pending(harness, authority, harness.observe("The gate code is 1188.")["accepted_event_ids"][0])
    assert "1188" not in str(harness.memory.memory_map())
    assert "1188" not in str(harness.memory.timeline(roles=("user",)))


def test_concurrent_recalls_with_one_request_id_store_one_response(recovery, monkeypatch):
    harness, _ = recovery
    harness.observe("The dentist is on Tuesday.")
    request = recall_request(harness, "dentist", request_id=str(uuid.uuid4()), wall_ms=20000)
    held = Held(harness, monkeypatch)
    thread, first = held.run(lambda: harness.service.handle(harness.principal, request))
    second = {}
    follower = threading.Thread(target=lambda: second.update(value=harness.service.handle(harness.principal, request)),
                                daemon=True)
    follower.start()
    follower.join(1)
    assert follower.is_alive(), "a second request with the same key did not wait for the first"
    held.release.set()
    thread.join(20)
    follower.join(20)
    assert first["value"]["outcome"] == second["value"]["outcome"] == "completed"
    assert first["value"]["result"] == second["value"]["result"]
    with harness.database.transaction(harness.principal) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_requests WHERE tenant_id=%s AND brain_id=%s "
                            "AND action='recall' AND key=%s",
                            (harness.principal.tenant_id, harness.brain, request["request_id"])).fetchone()["n"] == 1


def test_a_read_only_request_cannot_change_memory(recovery):
    from membrain.service import reading

    harness, _ = recovery
    with reading(), pytest.raises(RuntimeError, match="read-only"):
        store_note(harness.service, harness.principal, harness.brain, {"request_id": uid(), "text": "A plan."})


def test_the_index_worker_reading_a_message_does_not_make_the_map_busy(recovery, monkeypatch):
    harness, _ = recovery
    harness.observe("The Vancouver library appointment is on Friday.")
    inside, release = threading.Event(), threading.Event()
    original = harness.service._current_captures

    def captures(*args, **kwargs):
        inside.set()
        assert release.wait(20)
        return original(*args, **kwargs)

    monkeypatch.setattr(harness.service, "_current_captures", captures)
    worker = threading.Thread(target=harness.service.work_once, args=(harness.principal, harness.brain), daemon=True)
    worker.start()
    assert inside.wait(20)
    try:
        # Before: the worker read the message with the brain row FOR UPDATE, so the map answered 503.
        assert harness.memory.memory_map()["nodes"]
    finally:
        release.set()
        worker.join(20)
    assert harness.memory.dashboard()["status"]["index_lag"] == 0


def test_reads_wait_for_a_write_in_progress(recovery, monkeypatch):
    """Readers share the brain row, but a writer holds it exclusively (sequence allocation, invalidation and the
    erasure fence depend on that), so a read waits for an observation in progress rather than reading around it."""
    harness, _ = recovery
    inside, release = threading.Event(), threading.Event()
    original = harness.service._job

    def job(*args, **kwargs):
        inside.set()
        assert release.wait(20)
        return original(*args, **kwargs)

    monkeypatch.setattr(harness.service, "_job", job)
    writer = threading.Thread(target=harness.observe, args=("The bike lock code is 5150.",), daemon=True)
    writer.start()
    assert inside.wait(20)
    try:
        waited = harness.service.handle(harness.principal, recall_request(harness, "bike lock", wall_ms=500))
        assert waited["outcome"] == "failed" and waited["error"]["code"] == "budget_exceeded"
    finally:
        release.set()
        writer.join(20)
    after = harness.service.handle(harness.principal, recall_request(harness, "bike lock"))
    assert after["outcome"] == "completed" and "5150" in str(after)


def test_indexing_a_message_of_a_new_bulk_import_holds_the_brain_briefly(recovery):
    harness, _ = recovery
    service = MemoryService(harness.database)
    brain = service.create_brain(harness.principal, "Bulk import")["id"]
    for start in range(0, 2000, 500):
        response = service.handle(harness.principal, {
            "message_type": "request", "contract_version": CONTRACT_VERSION, "request_id": str(uuid.uuid4()),
            "action": "observe", "target": {"brain_ref": brain, "conversation_ref": "import", "branch_ref": "main"},
            "payload": {"idempotency_key": uid(), "events": [{
                "source_event_key": f"import-{index}", "source_revision": 1, "producer_ref": "import-test",
                "actor_ref": "user", "actor_role": "user", "event_kind": "message",
                "content": {"media_type": "text/plain", "text": f"Imported message {index} about the planetarium."},
                "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
            } for index in range(start, start + 500)]}})
        assert response["outcome"] == "completed", response
    began = time.perf_counter()
    assert service.work_once(harness.principal, brain) == 1
    # Before: the indexed-sequence query compared every pending job with every event under the exclusive lock
    # (about 2.5 s here), longer than the map's 500 ms lock timeout.
    assert time.perf_counter() - began < 0.5
    with harness.database.transaction(harness.principal) as conn:
        done = conn.execute("SELECT j.payload->>'event_id' AS id FROM memory_jobs j WHERE j.tenant_id=%s "
                            "AND j.brain_id=%s AND j.state='completed'", (harness.principal.tenant_id, brain)).fetchall()
        row = conn.execute("SELECT indexed_sequence FROM memory_brains WHERE tenant_id=%s AND id=%s",
                           (harness.principal.tenant_id, brain)).fetchone()
        first = conn.execute("SELECT id FROM memory_events WHERE tenant_id=%s AND brain_id=%s AND sequence=1",
                             (harness.principal.tenant_id, brain)).fetchone()["id"]
    # Every message before the first one still waiting is indexed: one, if the job that ran was the first.
    assert len(done) == 1 and row["indexed_sequence"] == (1 if done[0]["id"] == first else 0)
