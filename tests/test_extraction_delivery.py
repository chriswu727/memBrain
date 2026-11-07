import copy
import json

import httpx
import pytest
from test_extraction_source_fences import chat as chat

from membrain.client import MemoryClient
from membrain.extraction import extraction_status, record_outcome


def reject(status, code="temporary"):
    request = httpx.Request("POST", "http://memory.test/notes")
    response = httpx.Response(status, request=request, json={"error": {"code": code}})
    return httpx.HTTPStatusError("private diagnostic must not reach status", request=request, response=response)


def intercept(monkeypatch, handler):
    original = MemoryClient._request
    writes = []

    def request(client, method, path, **kwargs):
        if method == "POST" and path.endswith("/notes"):
            writes.append(copy.deepcopy(kwargs["json"]))
            return handler(len(writes), lambda: original(client, method, path, **kwargs))
        return original(client, method, path, **kwargs)

    monkeypatch.setattr(MemoryClient, "_request", request)
    return writes


@pytest.mark.parametrize("failure", [429, 503, "before_commit", "after_commit"])
def test_transient_delivery_reuses_one_request_without_another_model_call(chat, monkeypatch, failure):
    chat.record("My planetarium visit is on Thursday.", "first")
    chat.response = lambda body: [{"text": "Planetarium visit on Thursday."}]

    def deliver(number, send):
        if number == 1:
            if failure == "after_commit":
                send()
            if isinstance(failure, int):
                raise reject(failure)
            raise httpx.ReadTimeout("response unavailable")
        return send()

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 2 and writes[0] == writes[1]
    assert len(chat.seen) == 1 and len(chat.notes()) == 1
    status = extraction_status(chat.directory)
    assert status["state"] == "ok" and status["notes_saved"] == 1 and status["turns_failed"] == 0


def test_exhausted_delivery_is_degraded_and_does_not_try_unconfirmed_later_notes(chat, monkeypatch):
    chat.record("Remember my Thursday appointment and my Friday visit.", "first")
    chat.response = lambda body: [{"text": "Thursday appointment."}, {"text": "Friday visit."}]

    def deliver(number, send):
        raise reject(503)

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 2 and writes[0] == writes[1]
    assert len(chat.seen) == 1 and chat.notes() == []
    status = extraction_status(chat.directory)
    assert status["state"] == "degraded" and status["turns_failed"] == 1 and status["notes_saved"] == 0
    assert status["last_error"] == "HTTP 503"


def test_rejected_proposal_is_not_retried_and_does_not_hide_a_partial_save(chat, monkeypatch):
    chat.record("Remember my Thursday appointment and my Friday visit.", "first")
    chat.response = lambda body: [{"text": "Thursday appointment."}, {"text": "Friday visit."}]

    def deliver(number, send):
        if number == 1:
            raise reject(422)
        return send()

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 2 and writes[0]["request_id"] != writes[1]["request_id"]
    assert len(chat.notes()) == 1 and "Friday" in chat.notes()[0]["text"]
    status = extraction_status(chat.directory)
    assert status["state"] == "degraded" and status["notes_saved"] == 1 and status["turns_failed"] == 1
    assert status["last_error"] == "HTTP 422" and "private diagnostic" not in str(status)


def test_status_preserves_confirmed_saves_when_the_rest_of_a_turn_fails(tmp_path):
    record_outcome(tmp_path, saved=2, error="source_context_changed")
    status = extraction_status(tmp_path)
    assert status["state"] == "degraded" and status["notes_saved"] == 2
    assert status["turns_failed"] == 1 and status["turns_read"] == 0


def test_lost_replacement_response_replays_without_duplicate_feelings(chat, monkeypatch):
    old = chat.client.write_note("The visit is on Thursday.")["note_id"]
    chat.record("Move the visit to Friday; I feel relieved.", "first")
    chat.response = lambda body: [{"text": "The visit is on Friday.", "replaces": [old],
                                  "affect": {"label": "relieved", "valence": 1, "intensity": 1,
                                             "basis": "reported"}}]

    def deliver(number, send):
        result = send()
        if number == 1:
            raise httpx.ReadTimeout("lost committed response")
        return result

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 2 and writes[0] == writes[1]
    assert len(chat.notes()) == 1 and chat.notes()[0]["event_id"] != old
    assert len(chat.client.affect_records()["records"]) == 1
    assert extraction_status(chat.directory)["notes_saved"] == 1


def test_erasure_after_lost_commit_invalidates_retry_without_resurrection(chat, monkeypatch):
    sources = chat.record("Remember the Thursday appointment.", "first")
    chat.response = lambda body: [{"text": "Thursday appointment."}]

    def deliver(number, send):
        result = send()
        if number == 1:
            chat.erase(sources)
            raise httpx.ReadTimeout("lost committed response")
        return result

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 2 and writes[0] == writes[1] and chat.notes() == []
    assert len(chat.seen) == 1
    status = extraction_status(chat.directory)
    assert status["last_error"] == "source_context_changed" and status["notes_saved"] == 0


@pytest.mark.parametrize("fault", ["json", "shape", "lost_all_responses"])
def test_unconfirmed_commits_stop_later_proposals_and_remain_degraded(chat, monkeypatch, fault):
    chat.record("Remember Thursday, Friday and Saturday visits.", "first")
    chat.response = lambda body: [{"text": "Thursday visit."}, {"text": "Friday visit."}]

    def deliver(number, send):
        result = send()
        if fault == "json":
            raise json.JSONDecodeError("private response", "invalid", 0)
        if fault == "shape":
            return {"note_id": result["note_id"], "dependency_generation": True}
        raise httpx.ReadTimeout("lost committed response")

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == (2 if fault == "lost_all_responses" else 1)
    assert all(item == writes[0] for item in writes)
    assert len(chat.notes()) == 1 and "Thursday" in chat.notes()[0]["text"]
    status = extraction_status(chat.directory)
    assert status["state"] == "degraded" and status["notes_saved"] == 0 and status["turns_failed"] == 1
    assert len(chat.seen) == 1 and "private response" not in str(status)


def test_confirmed_saves_survive_a_later_exhausted_delivery(chat, monkeypatch):
    chat.record("Remember Thursday, Friday and Saturday visits.", "first")
    chat.response = lambda body: [{"text": f"{day} visit."} for day in ("Thursday", "Friday", "Saturday")]

    def deliver(number, send):
        if number > 1:
            raise reject(503)
        return send()

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 3 and writes[1] == writes[2]
    assert len(chat.notes()) == 1
    status = extraction_status(chat.directory)
    assert status["state"] == "degraded" and status["notes_saved"] == 1 and status["turns_failed"] == 1


def test_pause_between_delivery_attempts_prevents_retry(chat, monkeypatch):
    from membrain import host

    chat.record("Remember Thursday's visit.", "first")
    chat.response = lambda body: [{"text": "Thursday visit."}]

    def deliver(number, send):
        host.pause(chat.directory, user_id=chat.memory.user_id(chat.person))
        raise reject(503)

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 1 and chat.notes() == []
    assert extraction_status(chat.directory)["last_error"] == "recording_paused"


def test_local_validation_rejects_only_that_proposal(chat, monkeypatch):
    chat.record("Remember Friday's visit.", "first")
    chat.response = lambda body: [{"text": "x" * 400}, {"text": "Friday visit."}]
    writes = intercept(monkeypatch, lambda number, send: send())
    chat.run()
    assert len(writes) == 1 and len(chat.notes()) == 1
    status = extraction_status(chat.directory)
    assert status["state"] == "degraded" and status["notes_saved"] == 1
    assert status["last_error"] == "NoteValidationError"


@pytest.mark.parametrize("status,code", [(403, "validation_failed"), (409, "idempotency_conflict")])
def test_permission_and_idempotency_rejections_stop_all_writes(chat, monkeypatch, status, code):
    chat.record("Remember Thursday and Friday visits.", "first")
    chat.response = lambda body: [{"text": "Thursday visit."}, {"text": "Friday visit."}]

    def deliver(number, send):
        raise reject(status, code)

    writes = intercept(monkeypatch, deliver)
    chat.run()
    assert len(writes) == 1 and len(chat.seen) == 1 and chat.notes() == []
    result = extraction_status(chat.directory)
    assert result["state"] == "degraded" and result["last_error"] == f"HTTP {status}"
