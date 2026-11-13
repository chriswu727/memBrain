import copy
import time
from types import SimpleNamespace

import pytest
from test_response_validation import PRINCIPAL, invalid_response, post, recall_request

from membrain import helpers, recall_deadline, recall_service_executor, vector_jobs
from membrain.config import Settings
from membrain.embeddings import EmbeddingSpace
from membrain.helpers import DomainError
from membrain.recall_service_executor import RecallServiceExecutor, _respond
from membrain.service import MemoryService


def test_workers_receive_no_models_or_provider_credentials():
    settings = Settings(database_url="database", migration_database_url="private-admin", api_keys={"private": PRINCIPAL},
                        cognition_base_url="https://example.com", cognition_api_key="private-text-key",
                        cognition_model="model", embedding_local_directory="/private/model")
    executor = RecallServiceExecutor(4, settings)
    try:
        child = executor._settings
        assert child.database_url == settings.database_url
        assert executor._principals == (PRINCIPAL,)
        assert child.migration_database_url is None
        assert not child.api_keys and child.api_keys_file is None
        assert child.cognition_base_url is child.cognition_api_key is child.cognition_model is None
        assert child.embedding_local_directory is None
        assert child.recall_processes == 0
        assert settings.cognition_api_key == "private-text-key"
        assert settings.embedding_local_directory == "/private/model"
    finally:
        executor.close()


@pytest.mark.parametrize("failure", [None, "domain", "unexpected"])
def test_worker_restores_clock_provider_and_deadline_on_every_exit(monkeypatch, failure):
    request = recall_request("brain")
    before = copy.deepcopy(request)
    provider = object()
    def prior_clock():
        return None
    space = EmbeddingSpace("model", "version", 3)
    embedding = (None, None, 0)
    def call(principal, body, *, embedding):
        assert body == before and principal == PRINCIPAL
        assert service.embedding_provider.space == space
        assert helpers.now().startswith("2030-01-02")
        assert 0 < recall_deadline.remaining(30000) <= 1000
        if failure == "domain":
            raise DomainError("context_stale", "Changed source", retryable=True)
        if failure == "unexpected":
            raise ValueError("private database detail")
        return {"value": "preserved"}, False
    service = SimpleNamespace(embedding_provider=provider, access_time_provider=None, _respond=call)
    monkeypatch.setattr(recall_service_executor, "_SERVICE", service)
    monkeypatch.setattr(helpers, "_scenario_clock", prior_clock)
    start = time.monotonic()
    result = _respond(PRINCIPAL, request, embedding, space, start, start+1, ("2030-01-02T00:00:00Z", start))
    assert service.embedding_provider is provider and helpers._scenario_clock is prior_clock
    assert service.access_time_provider is None
    assert recall_deadline.remaining(30000) == 30000
    assert request == before
    if failure:
        assert result["error"]["code"] == ("context_stale" if failure == "domain" else "internal_error")
        assert "private database detail" not in str(result)
    else:
        assert result["response"] == ({"value": "preserved"}, False)


@pytest.mark.parametrize("action", ["recall", "observe"])
def test_expired_or_disallowed_work_never_enters_the_service(monkeypatch, action):
    def call(*args, **kwargs):
        pytest.fail("Expired or unsupported work entered the transaction")
    monkeypatch.setattr(recall_service_executor, "_SERVICE", SimpleNamespace(embedding_provider=None, access_time_provider=None, _respond=call))
    request = {**recall_request("brain"), "action": action}
    start = time.monotonic()-1
    result = _respond(PRINCIPAL, request, (None, None, 0), None, start, start, None)
    assert result["error"]["code"] == ("budget_exceeded" if action == "recall" else "unsupported_capability")


def test_embedding_handoff_does_not_change_request_or_trust_unvalidated_response(monkeypatch):
    request = recall_request("brain")
    before = copy.deepcopy(request)
    service = MemoryService(None)
    calls = []
    embedding = (object(), {"snapshot": "kept"}, 1)
    monkeypatch.setattr(vector_jobs, "query_embedding", lambda *args: embedding)
    def dispatch(principal, body, prepared, space, *, access_at):
        assert access_at is None
        calls.append((principal, copy.deepcopy(body), prepared, space))
        return invalid_response(body), True
    service.request_runner = dispatch
    response, validated = service.respond(PRINCIPAL, request)
    assert calls == [(PRINCIPAL, before, embedding, None)] and request == before
    assert response["error"]["code"] == "validation_failed" and not validated


def test_deadline_window_restores_outer_window(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(recall_deadline.time, "monotonic", lambda: clock[0])
    with recall_deadline.window(99, 105):
        assert recall_deadline.remaining(10000) == 5000
        with recall_deadline.window(99, 101):
            clock[0] = 102
            with pytest.raises(DomainError, match="deadline"):
                recall_deadline.remaining(10000)
        assert recall_deadline.remaining(10000) == 3000
        assert recall_deadline.elapsed(0) == 3000
    assert recall_deadline.remaining(10000) == 10000


@pytest.mark.parametrize("instance_override", [False, True])
def test_private_response_override_cannot_bypass_http_validation(instance_override):
    class Override(MemoryService):
        def _respond(self, principal, request, **kwargs):
            return invalid_response(request), True
    service = MemoryService(None) if instance_override else Override(None)
    if instance_override:
        service._respond = lambda principal, request: (invalid_response(request), True)
    response = post(service, recall_request("brain"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
