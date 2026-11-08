import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient
from test_turns import Turns

from membrain import host
from membrain.api import create_app
from membrain.client import MemoryActionError, MemoryClient, default_budget
from membrain.config import Settings
from membrain.helpers import DomainError, Principal, digest, uid
from membrain.notes import store_note
from membrain.recording_control import recording_status, set_recording
from membrain.service import MemoryService
from membrain.storage import Database


@pytest.fixture
def turns():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("MEMORY_DATABASE_URL must point to the dedicated test database")
    return Turns(Database(settings.database_url))


def policy(turns, paused, revision):
    return set_recording(turns.service, turns.principal, turns.brain,
                         paused=paused, expected_revision=revision)


def observation(turns, text="A new synthetic source."):
    captured = []
    with MemoryClient("http://testserver", "test-key", turns.brain,
                      transport=httpx.MockTransport(lambda request: captured.append(json.loads(request.content))
                                                    or httpx.Response(500))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.observe(text, role="user", conversation_id=turns.conversation,
                           branch_id=turns.branch, source_event_key=uid())
    return captured[0]


def test_pause_rejects_raw_events_notes_and_new_turns_without_storing_requests(turns):
    old = turns.observe("Existing memory remains readable.")
    assert policy(turns, True, 0) == {"paused": True, "revision": 1}
    request = observation(turns)
    rejected = turns.service.handle(turns.principal, request)
    assert rejected["error"]["code"] == "recording_paused"
    assert rejected["error"]["retryable"] is False
    with pytest.raises(DomainError, match="Recording is paused"):
        store_note(turns.service, turns.principal, turns.brain, {"text": "Rejected note.", "request_id": uid()})
    with pytest.raises(DomainError, match="Recording is paused"):
        turns.begin()
    with turns.database.transaction(turns.principal) as conn:
        params = turns.service._params(turns.principal, turns.brain)
        assert conn.execute("SELECT count(*) AS n FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s",
                            params).fetchone()["n"] == 1
        assert conn.execute("SELECT 1 FROM memory_requests WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND key=%s",
                            (*params, request["payload"]["idempotency_key"])).fetchone() is None
        assert conn.execute("SELECT id FROM memory_events WHERE id=%s", (old["event_id"],)).fetchone()
    assert policy(turns, False, 1) == {"paused": False, "revision": 2}
    assert turns.observe()["event_id"] != old["event_id"]


def test_policy_survives_service_restart_and_stale_resume_cannot_override_it(turns):
    assert recording_status(turns.service, turns.principal, turns.brain) == {"paused": False, "revision": 0}
    assert policy(turns, False, 0)["revision"] == 0
    policy(turns, True, 0)
    restarted = MemoryService(turns.database)
    assert recording_status(restarted, turns.principal, turns.brain) == {"paused": True, "revision": 1}
    with pytest.raises(DomainError) as error:
        policy(turns, False, 0)
    assert error.value.code == "version_conflict" and error.value.current_revision == 1
    other = restarted.create_brain(turns.principal, "Other brain")["id"]
    assert recording_status(restarted, turns.principal, other)["paused"] is False
    for outsider in (Principal(uid(), turns.principal.principal_id), Principal(turns.principal.tenant_id, uid())):
        with pytest.raises(DomainError) as denied:
            set_recording(restarted, outsider, turns.brain, paused=False, expected_revision=1)
        assert denied.value.code == "not_found_or_forbidden"


def test_paused_brain_can_read_export_and_erase_but_cannot_import(turns):
    event = turns.observe("Existing synthetic memory.")
    policy(turns, True, 0)
    archive = turns.action("export", {"include_events": True, "include_working_states": True,
                           "include_assertions": True, "include_provenance": True, "include_tombstones": True,
                           "budget": default_budget()})
    document = turns.service.download_archive(turns.principal, archive["archive_id"])["document"]
    timeline = turns.service.timeline(turns.principal, turns.brain)
    assert any(item["text"] == "Existing synthetic memory." for item in timeline["items"])
    with pytest.raises(DomainError) as denied:
        turns.service.upload_archive(turns.principal, turns.brain, document)
    assert denied.value.code == "recording_paused"
    request = observation(turns)
    request.update(action="restore", payload={"uploaded_archive_ref": archive["archive_id"],
                   "expected_manifest_sha256": archive["manifest_sha256"], "mode": "merge_authorized_brain",
                   "apply_current_tombstones": True, "expected_scope_generation": 1, "budget": default_budget()})
    assert turns.service.handle(turns.principal, request)["error"]["code"] == "recording_paused"
    turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [event["event_id"]]},
                            "mode": "erase_content", "expected_scope_generation": 1})
    assert not turns.service.timeline(turns.principal, turns.brain)["items"]


@pytest.mark.parametrize("stage,reason", [("started", "cancelled"), ("prepared", "cancelled"),
                                        ("generating", "generation_uncertain"),
                                        ("delivering", "delivery_uncertain")])
def test_pause_stops_active_turns_and_resume_does_not_revive_them(turns, stage, reason):
    if stage == "started":
        turns.begin()
    elif stage == "delivering":
        turns.generate()
        turns.advance("delivering")
    else:
        turns.prepare()
        if stage == "generating":
            turns.advance("generating")
    policy(turns, True, 0)
    row = turns.store.get(turns.principal, turns.brain, turns.turn_id)
    assert row["stage"] == "failed" and row["failure_code"] == reason
    assert not row["scope_reserved"] and not row["lease_active"]
    assert turns.call("history")[-1]["operation"] == "fail"
    policy(turns, False, 1)
    assert turns.begin()["stage"] == "failed"
    with pytest.raises(DomainError):
        turns.claim()
    if turns.token:
        with pytest.raises(DomainError):
            turns.record_output("Late output must not be recorded.", "delivered" if stage == "delivering" else "draft")
    turns.store.begin(turns.principal, turns.brain, turn_id=uid(), conversation_id=turns.conversation,
                      branch_id=turns.branch, input_fingerprint=digest("new input"))


def test_pause_preserves_confirmed_delivery_and_allows_completion(turns):
    turns.deliver()
    policy(turns, True, 0)
    assert turns.store.get(turns.principal, turns.brain, turns.turn_id)["stage"] == "delivered"
    result = turns.call("finish", lease_token=turns.token, expected_revision=turns.row["revision"])
    assert result["stage"] == "completed"


def test_pause_waits_for_prior_write_transaction_and_then_rejects_new_content(turns, monkeypatch):
    entered, release, pausing = Event(), Event(), Event()
    original = turns.service._append_event

    def held_write(*args, **kwargs):
        result = original(*args, **kwargs)
        entered.set()
        assert release.wait(5)
        return result

    def pause():
        pausing.set()
        return policy(turns, True, 0)

    monkeypatch.setattr(turns.service, "_append_event", held_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        write = pool.submit(turns.observe)
        try:
            assert entered.wait(5)
            control = pool.submit(pause)
            assert pausing.wait(5)
            with pytest.raises(TimeoutError):
                control.result(timeout=0.1)
        finally:
            release.set()
        assert write.result(timeout=5)["event_id"]
        assert control.result(timeout=5)["paused"]
    rejected = turns.service.handle(turns.principal, observation(turns))
    assert rejected["error"]["code"] == "recording_paused"


def test_write_queued_behind_pause_checks_policy_after_taking_lock(turns, monkeypatch):
    entered, release = Event(), Event()
    original = turns.service._brain

    def held_brain(*args, **kwargs):
        brain = original(*args, **kwargs)
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return brain

    request = observation(turns)
    monkeypatch.setattr(turns.service, "_brain", held_brain)
    with ThreadPoolExecutor(max_workers=2) as pool:
        control = pool.submit(policy, turns, True, 0)
        try:
            assert entered.wait(5)
            write = pool.submit(turns.service.handle, turns.principal, request)
            with pytest.raises(TimeoutError):
                write.result(timeout=0.1)
        finally:
            release.set()
        assert control.result(timeout=5)["paused"]
        assert write.result(timeout=5)["error"]["code"] == "recording_paused"


def test_http_and_python_client_use_authenticated_strict_revisioned_control(turns):
    key = "recording-test-key"
    settings = Settings(database_url=turns.database.dsn,
                        api_keys={hashlib.sha256(key.encode()).hexdigest(): turns.principal}, recall_processes=0)
    with TestClient(create_app(settings, turns.service)) as api:
        path = f"/v1/brains/{turns.brain}/recording"
        assert api.get(path).status_code == 401
        headers = {"Authorization": f"Bearer {key}"}
        for body in ({"paused": "true", "expected_revision": 0}, {"paused": True, "expected_revision": False},
                     {"paused": True, "expected_revision": 0, "owner_id": "other"}):
            assert api.put(path, headers=headers, json=body).status_code == 422

        def transport(request):
            response = api.request(request.method, request.url.path, headers=request.headers, content=request.content)
            return httpx.Response(response.status_code, json=response.json())

        with MemoryClient("http://testserver", key, turns.brain, transport=httpx.MockTransport(transport)) as client:
            assert client.recording_status() == {"paused": False, "revision": 0}
            assert client.set_recording(paused=True, expected_revision=0) == {"paused": True, "revision": 1}
            with pytest.raises(httpx.HTTPStatusError) as stale:
                client.set_recording(paused=False, expected_revision=0)
            assert stale.value.response.status_code == 409
            with pytest.raises(MemoryActionError) as rejected:
                client.observe("No raw write through HTTP.", conversation_id="session", branch_id="main",
                               source_event_key="blocked")
            assert rejected.value.code == "recording_paused"


def test_host_does_not_spool_or_archive_content_rejected_by_server(tmp_path):
    class Client:
        brain_id = "brain"

        def observe(self, **kwargs):
            raise MemoryActionError({"error": {"code": "recording_paused", "retryable": False}})

    record = {"text": "Rejected synthetic private text.", "role": "user", "source_event_key": "s:t:user"}
    assert host.deliver(tmp_path, Client(), record) is False
    assert not (tmp_path / "plugin" / "spool.jsonl").exists()
    host.spool(tmp_path, record)
    assert host.flush(Client(), tmp_path) == 1
    assert not (tmp_path / "plugin" / "spool.jsonl").read_text().strip()
    assert all(record["text"] not in p.read_text() for p in tmp_path.rglob("*") if p.is_file())
