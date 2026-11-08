import hashlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi.testclient import TestClient
from test_note_workflow import brain as brain
from test_note_workflow import write

from membrain.api import create_app
from membrain.config import Settings
from membrain.helpers import DomainError, uid
from membrain.notes import store_note
from membrain.recording_control import set_recording

pytestmark = pytest.mark.integration


def policy(brain, paused, revision):
    return set_recording(brain.service, brain.principal, brain.brain,
                         paused=paused, expected_revision=revision)


@pytest.mark.parametrize("resume", [False, True])
def test_old_note_cannot_replace_records_or_leave_a_request_after_policy_change(brain, resume):
    kept = write(brain, "Keep the original note.")["note_id"]
    request = {"request_id": uid(), "text": "Rejected replacement.", "replaces": [kept],
               "expected_recording_revision": 0}
    policy(brain, True, 0)
    if resume:
        policy(brain, False, 1)
    before = brain.timeline(roles=("assistant",))["items"]
    with pytest.raises(DomainError) as error:
        store_note(brain.service, brain.principal, brain.brain, request)
    assert error.value.code == ("recording_stale" if resume else "recording_paused")
    assert not error.value.retryable
    assert brain.timeline(roles=("assistant",))["items"] == before
    with brain.service.database.transaction(brain.principal) as conn:
        assert conn.execute("SELECT 1 FROM memory_requests WHERE brain_id=%s AND key=%s",
                            (brain.brain, request["request_id"])).fetchone() is None
    if resume:
        result = store_note(brain.service, brain.principal, brain.brain,
                            {**request, "expected_recording_revision": 2})
        assert result["replaced"] == [kept]


def test_completed_note_retry_remains_an_acknowledgement_without_new_writes(brain):
    request = {"request_id": uid(), "text": "An already committed note.", "expected_recording_revision": 0}
    first = store_note(brain.service, brain.principal, brain.brain, request)
    policy(brain, True, 0)
    assert store_note(brain.service, brain.principal, brain.brain, request) == first
    policy(brain, False, 1)
    assert store_note(brain.service, brain.principal, brain.brain, request) == first
    assert len(brain.timeline(roles=("assistant",))["items"]) == 1
    with pytest.raises(DomainError) as error:
        store_note(brain.service, brain.principal, brain.brain, {**request, "expected_recording_revision": 2})
    assert error.value.code == "idempotency_conflict"


@pytest.mark.parametrize("revision", [-1, True, "0", 1.5, 2**63])
def test_note_recording_revision_is_strict_in_http_and_service(brain, revision):
    key = "note-fence-test-key"
    settings = Settings(database_url=brain.service.database.dsn, recall_processes=0,
                        api_keys={hashlib.sha256(key.encode()).hexdigest(): brain.principal})
    request = {"request_id": uid(), "text": "Rejected malformed revision.", "expected_recording_revision": revision}
    with TestClient(create_app(settings, brain.service)) as api:
        response = api.post(f"/v1/brains/{brain.brain}/notes", json=request,
                            headers={"Authorization": f"Bearer {key}"})
        assert response.status_code == 422
    with pytest.raises(DomainError) as error:
        store_note(brain.service, brain.principal, brain.brain, request)
    assert error.value.code == "validation_failed"
    assert brain.timeline(roles=("assistant",))["items"] == []


def test_source_snapshot_reports_recording_changes_without_blocking_existing_memory_reads(brain):
    key = uid()
    brain.say("An existing appointment.", source_key=key)
    references = [{"producer_ref": "timeline-test", "source_event_key": key, "source_revision": 1}]
    for paused, revision in ((False, 0), (True, 1), (False, 2)):
        if revision:
            policy(brain, paused, revision - 1)
        snapshot = brain.service.source_messages(brain.principal, brain.brain, references)
        assert snapshot["recording_paused"] is paused and snapshot["recording_revision"] == revision
        assert snapshot["items"][0]["text"] == "An existing appointment."


@pytest.mark.parametrize("pause_first", [True, False])
def test_note_write_and_pause_share_the_transactional_policy_lock(brain, monkeypatch, pause_first):
    entered, release = Event(), Event()
    original = brain.service._brain

    def hold(*args, **kwargs):
        result = original(*args, **kwargs)
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(brain.service, "_brain", hold)
    def note():
        return write(brain, "A concurrent note.", expected_recording_revision=0)
    def pause():
        return policy(brain, True, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(pause if pause_first else note)
        try:
            assert entered.wait(5)
            second = pool.submit(note if pause_first else pause)
            with pytest.raises(TimeoutError):
                second.result(timeout=0.1)
        finally:
            release.set()
        first.result(timeout=5)
        if pause_first:
            with pytest.raises(DomainError) as error:
                second.result(timeout=5)
            assert error.value.code == "recording_paused"
        else:
            assert second.result(timeout=5)["paused"]
    assert len(brain.timeline(roles=("assistant",))["items"]) == (0 if pause_first else 1)
