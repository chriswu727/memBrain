"""Every action response stays validated against the contract when validation is not repeated (recall CPU work).

The service validates a completed ActionResponse once; the HTTP layer skips its own check only for that same,
unchanged object, and only when the service is an unmodified MemoryService. Cached responses, errors and any
overridden ``handle`` are still validated at the HTTP boundary.
"""
import copy
import hashlib
import uuid

import httpx
import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from test_learning import learning as learning

import membrain.api as api_module
import membrain.service as service_module
from membrain.api import create_app
from membrain.client import MemoryActionError, default_budget, default_read_fence
from membrain.config import Settings
from membrain.contracts import CONTRACT_VERSION
from membrain.helpers import DomainError, Principal
from membrain.service import MemoryService

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


def rejected_response(request):
    # A valid ActionResponse that needs no database: the action was refused.
    return {"message_type": "response", "contract_version": CONTRACT_VERSION, "request_id": request["request_id"],
            "action": request["action"], "outcome": "rejected",
            "error": DomainError("unsupported_capability", "Refused by the test service.").as_dict()}


class DuckTyped:
    """Any object with ``handle``, and no ``respond`` at all."""

    def __init__(self, reply):
        self.reply = reply

    def handle(self, principal, request):
        return self.reply(request)


class Subclass(MemoryService):
    """Overrides ``handle`` and never sets the attributes MemoryService.respond would read."""

    def __init__(self, reply):  # noqa: D107 - deliberately skips MemoryService.__init__
        self.reply = reply

    def handle(self, principal, request):
        return self.reply(request)


def patched_instance(reply):
    service = MemoryService(None)
    service.handle = lambda principal, request: reply(request)
    return service


SERVICES = {"subclass": Subclass, "instance-patch": patched_instance, "duck-typed": DuckTyped}


def post(service, request):
    settings = Settings(database_url="unused", api_keys={hashlib.sha256(KEY.encode()).hexdigest(): PRINCIPAL})
    with TestClient(create_app(settings, service)) as client:
        return client.post("/v1/actions", headers={"Authorization": f"Bearer {KEY}"}, json=request)


@pytest.mark.parametrize("make", SERVICES.values(), ids=SERVICES.keys())
def test_the_route_calls_an_overridden_handle_and_validates_its_response(make, monkeypatch):
    request = recall_request("brain")
    checked, original = [], api_module.validate

    def recording(definition, value):
        original(definition, value)
        checked.append((definition, value))

    monkeypatch.setattr(api_module, "validate", recording)
    response = post(make(rejected_response), request)
    assert response.status_code == 200, response.text
    assert response.json() == rejected_response(request)
    assert [definition for definition, _ in checked] == ["ActionRequest", "ActionResponse"]


@pytest.mark.parametrize("make", SERVICES.values(), ids=SERVICES.keys())
def test_an_invalid_response_from_an_overridden_handle_is_rejected(make):
    response = post(make(invalid_response), recall_request("brain"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_an_action_response_is_encoded_byte_for_byte_as_the_default_encoding_would():
    request = recall_request("brain")

    def reply(request):
        value = rejected_response(request)
        value["error"]["message"] = "Refusé: 图书馆   \"quoted\" \\ </script> 1.5e-07"
        return value

    response = post(DuckTyped(reply), request)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content == JSONResponse(jsonable_encoder(reply(request))).body


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


def corrupt_recall_results(monkeypatch):
    """Make cognition.recall produce a result that is not a RecallResult (an unknown status)."""
    import membrain.belief_resolution as belief_resolution

    original = belief_resolution.factor_relations

    def factor_relations(result):
        original(result)
        result["status"] = "not-a-status"

    monkeypatch.setattr(belief_resolution, "factor_relations", factor_relations)


def stored(harness, table):
    with harness.database.transaction(harness.principal) as conn:
        return conn.execute(f"SELECT count(*) AS n FROM {table} WHERE tenant_id=%s AND brain_id=%s",
                            (harness.principal.tenant_id, harness.brain)).fetchone()["n"]


@pytest.mark.integration
def test_an_invalid_recall_result_is_rejected_and_nothing_of_it_is_kept(learning, monkeypatch):
    harness = learning
    harness.observe("The Vancouver library appointment is on Friday.")
    harness.memory.work()
    request = recall_request(harness.brain)
    traces, requests = stored(harness, "memory_traces"), stored(harness, "memory_requests")
    with monkeypatch.context() as patch:
        corrupt_recall_results(patch)
        response = harness.service.handle(harness.principal, request)
    assert response["outcome"] == "rejected" and response["error"]["code"] == "validation_failed"
    assert "result" not in response
    assert (stored(harness, "memory_traces"), stored(harness, "memory_requests")) == (traces, requests)
    retried = harness.service.handle(harness.principal, request)
    assert retried["outcome"] == "completed" and retried["result"]["items"]


@pytest.mark.integration
def test_an_invalid_recall_result_is_rejected_when_preparing_context(learning, monkeypatch):
    harness = learning
    harness.observe("The Vancouver library appointment is on Friday.")
    harness.memory.work()
    cue = harness.observe("When is the library appointment?")["accepted_event_ids"]
    corrupt_recall_results(monkeypatch)
    with pytest.raises(MemoryActionError) as error:
        harness.memory.prepare("turn", conversation_id="chat", branch_id="main",
                               latest_input_event_ids=cue, budget=default_budget(4000))
    assert error.value.response["outcome"] == "rejected"
    assert error.value.response["error"]["code"] == "validation_failed"
    assert "RecallResult" in error.value.response["error"]["message"]
