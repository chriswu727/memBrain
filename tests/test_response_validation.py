"""Every action response stays validated against the contract when validation is not repeated (recall CPU work).

The service validates a completed ActionResponse once; the HTTP layer skips its own check only for that same,
unchanged object. Cached responses and errors are still validated at the HTTP boundary.
"""
import copy
import hashlib
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from test_learning import learning as learning

import membrain.service as service_module
from membrain.api import create_app
from membrain.client import default_budget, default_read_fence
from membrain.config import Settings
from membrain.contracts import CONTRACT_VERSION
from membrain.helpers import Principal

KEY = "response-validation-key"
PRINCIPAL = Principal("tenant-a", "owner-a")


def recall_request(brain, query="library appointment", request_id=None):
    return {"message_type": "request", "contract_version": CONTRACT_VERSION,
            "request_id": request_id or str(uuid.uuid4()), "action": "recall",
            "target": {"brain_ref": brain},
            "payload": {"query": query, "intent": "explore", "cue_event_ids": [], "additional_cues": [],
                        "read_fence": default_read_fence(), "budget": default_budget(16000)}}


def invalid_response(request):
    # outcome "completed" without server_scope/result, and an unknown field: not an ActionResponse.
    return {"message_type": "response", "contract_version": CONTRACT_VERSION, "request_id": request["request_id"],
            "action": request["action"], "outcome": "completed", "unexpected": True}


class HandleOnly:
    """A service without ``respond``: the HTTP layer validates whatever ``handle`` returns."""

    def handle(self, principal, request):
        return invalid_response(request)


class UnvalidatedRespond:
    """A service whose ``respond`` says it did not validate: the HTTP layer must."""

    def respond(self, principal, request):
        return invalid_response(request), False


@pytest.mark.parametrize("service", [HandleOnly(), UnvalidatedRespond()], ids=["handle", "respond"])
def test_http_layer_rejects_an_invalid_response_it_was_not_told_is_validated(service):
    settings = Settings(database_url="unused", api_keys={hashlib.sha256(KEY.encode()).hexdigest(): PRINCIPAL})
    with TestClient(create_app(settings, service)) as client:
        response = client.post("/v1/actions", headers={"Authorization": f"Bearer {KEY}"},
                               json=recall_request("brain"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


@pytest.mark.integration
def test_a_completed_recall_is_validated_once_and_returned_unchanged(learning, monkeypatch):
    harness = learning
    harness.observe("The Vancouver library appointment is on Friday.")
    harness.memory.work()
    checked, original = [], service_module.validate

    def recording(definition, value):
        original(definition, value)
        checked.append((definition, value, copy.deepcopy(value)))

    monkeypatch.setattr(service_module, "validate", recording)
    envelope, validated = harness.service.respond(harness.principal, recall_request(harness.brain))
    assert envelope["outcome"] == "completed" and validated is True
    responses = [(value, snapshot) for definition, value, snapshot in checked if definition == "ActionResponse"]
    assert len(responses) == 1
    value, snapshot = responses[0]
    # The flag is only true for the very object that was validated, with nothing changed after validation.
    assert value is envelope and envelope == snapshot


@pytest.mark.integration
def test_a_cached_response_is_validated_again_at_the_http_boundary(learning):
    harness = learning
    harness.observe("The Vancouver library appointment is on Friday.")
    harness.memory.work()
    request = recall_request(harness.brain)
    first = harness.memory.send(request)
    assert first["outcome"] == "completed"
    assert harness.service.respond(harness.principal, request)[1] is False  # the replay is not trusted
    with harness.database.transaction(harness.principal) as conn:
        changed = conn.execute(
            "UPDATE memory_requests SET response=jsonb_set(response,'{result,status}','\"not-a-status\"') "
            "WHERE tenant_id=%s AND brain_id=%s AND action='recall' AND key=%s",
            (harness.principal.tenant_id, harness.brain, request["request_id"]),
        ).rowcount
    assert changed == 1
    with pytest.raises(httpx.HTTPStatusError) as error:
        harness.memory.send(request)
    assert error.value.response.status_code == 422
    assert error.value.response.json()["error"]["code"] == "validation_failed"
