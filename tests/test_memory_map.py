import hashlib
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from membrain import desktop, embedded_database, host
from membrain.api import create_app
from membrain.client import MemoryClient
from membrain.config import configured_service
from membrain.helpers import DomainError, Principal, uid
from membrain.local_profile import load_profile
from membrain.memory_map import REGIONS, memory_map
from membrain.notes import store_note


@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    from unittest.mock import patch

    directory = tmp_path_factory.mktemp("memory-map") / "installation"
    with patch.dict("os.environ", {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            settings = load_profile(directory).settings()
            with configured_service(settings) as service:
                yield service, settings
        finally:
            desktop.stop(directory)


@pytest.fixture
def brain(installation):
    service, settings = installation
    principal = next(iter(settings.principals().values()))
    ident = service.create_brain(principal, "Map test")["id"]
    return service, principal, ident


def say(brain, text, *, role="user", conversation="chat"):
    service, principal, ident = brain
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": "map-test", "actor_ref": role,
            "actor_role": role, "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "delivered" if role == "assistant" else "received",
            "parent_source_event_keys": [],
        }]},
    })
    assert result["outcome"] == "completed", result
    return result["result"]["accepted_event_ids"][0]


def note(brain, text, **fields):
    service, principal, ident = brain
    return store_note(service, principal, ident, {"request_id": uid(), "text": text, **fields})["note_id"]


def test_notes_messages_and_source_links_are_real_and_bounded(brain):
    user = say(brain, "Mira is my sister. We plan to visit the planetarium.")
    say(brain, "I once suggested a folding stool.", role="assistant")
    person = note(brain, "Mira is my sister.", kind="person", about="Mira", source_event_ids=[user])
    plan = note(brain, "Visit the planetarium with Mira.", kind="plan", about="Mira", status="intended",
                due="2026-11-08", source_event_ids=[user])
    result = memory_map(*brain)
    assert {node["id"] for node in result["nodes"]} == {"msg:" + user, "note:" + person, "note:" + plan}
    assert set(edge["basis"] for edge in result["edges"]) == {"source_event_ids", "about"}
    assert {"source": "note:" + plan, "target": "note:" + person,
            "type": "about_person", "basis": "about"} in result["edges"]
    assert result["truncated"] is False
    assert sum(region["count"] for region in result["regions"]) == len(result["nodes"])
    assert [region["id"] for region in result["regions"]] == list(REGIONS.values())
    assert not any("folding stool" in node["label"] for node in result["nodes"])


def test_sensitive_notes_do_not_leak_through_sources_dates_or_person_links(brain):
    source = say(brain, "Mira's private appointment is on November 8.")
    person = note(brain, "Mira is my sister.", kind="person", about="Mira")
    private = note(brain, "Mira's private appointment.", kind="plan", about="Mira", status="scheduled",
                   due="2026-11-08", sensitive=True, source_event_ids=[source])
    hidden = memory_map(*brain)
    nodes = {node["id"]: node for node in hidden["nodes"]}
    assert nodes["note:" + private]["label"] == nodes["msg:" + source]["label"] == "Sensitive memory"
    assert nodes["note:" + private]["date"] is None and nodes["note:" + private]["status"] is None
    assert not any(edge["target"] == "note:" + person for edge in hidden["edges"])
    assert "appointment" not in json.dumps(hidden)
    visible = memory_map(*brain, include_sensitive=True)
    assert any("appointment" in node["label"] for node in visible["nodes"])


def test_erased_sources_and_superseded_notes_disappear_without_a_cache(brain):
    source = say(brain, "Meet Mira on Saturday.")
    old = note(brain, "Meet Mira on Saturday.", kind="plan", source_event_ids=[source])
    current = note(brain, "Meet Mira on Sunday.", kind="plan", replaces=[old])
    assert "note:" + old not in {node["id"] for node in memory_map(*brain)["nodes"]}
    service, principal, ident = brain
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [source]},
                    "mode": "erase_content", "expected_scope_generation": generation},
    })
    assert result["outcome"] == "completed", result
    ids = {node["id"] for node in memory_map(*brain)["nodes"]}
    assert {"msg:" + source, "note:" + old, "note:" + current}.isdisjoint(ids)


def test_sensitive_source_stays_masked_when_its_note_is_outside_the_sample(brain):
    source = say(brain, "A private appointment.")
    note(brain, "A private appointment.", kind="constraint", sensitive=True, source_event_ids=[source])
    for index in range(8):
        note(brain, f"Ordinary preference {index}.", kind="preference")
    result = memory_map(*brain, max_nodes=2)
    message = next(node for node in result["nodes"] if node["id"] == "msg:" + source)
    assert message["sensitive"] and message["label"] == "Sensitive memory"


def test_caps_and_ambiguous_person_names_do_not_create_guessed_edges(brain):
    source = say(brain, "Mira works at the planetarium.")
    for _ in range(2):
        note(brain, "A person called Mira.", kind="person", about="Mira")
    note(brain, "Ask Mira about the visit.", kind="plan", about="Mira", source_event_ids=[source])
    assert not any(edge["type"] == "about_person" for edge in memory_map(*brain)["edges"])
    capped = memory_map(*brain, max_nodes=2, max_edges=0)
    assert len(capped["nodes"]) <= 2 and capped["edges"] == [] and capped["truncated"]
    assert memory_map(*brain, max_nodes=1)["limits"]["max_nodes"] == 1


@pytest.mark.parametrize("options", [{"max_nodes": 0}, {"max_nodes": 501}, {"max_nodes": True},
                                     {"max_edges": -1}, {"max_edges": 1001}, {"include_sensitive": "false"}])
def test_invalid_limits_fail_before_database_access(options):
    with pytest.raises(DomainError) as error:
        memory_map(None, None, "unused", **options)
    assert error.value.code == "validation_failed"


def test_api_reuses_authentication_and_brain_ownership(installation, brain):
    service, principal, ident = brain
    say(brain, "Only this brain can see the observatory.")
    other = Principal(principal.tenant_id, uid())
    foreign = service.create_brain(other, "Foreign")
    headers = {"Authorization": "Bearer map-test-key"}
    settings = replace(installation[1], api_keys={hashlib.sha256(b"map-test-key").hexdigest(): principal})
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1") as client:
        path = f"/v1/brains/{ident}/memory-map"
        assert client.get(path).status_code == 401
        assert client.get(path, headers=headers).status_code == 200
        assert client.get(path + "?max_nodes=501", headers=headers).status_code == 422
        denied = client.get(f"/v1/brains/{foreign['id']}/memory-map", headers=headers)
        assert denied.status_code == 404 and "observatory" not in denied.text


def test_a_busy_brain_returns_a_sample_without_unbounded_nodes_or_labels(brain):
    for index in range(30):
        source = say(brain, f"Original source {index}: " + "a long diary entry. " * 15)
        note(brain, f"Plan number {index}.", kind="plan", source_event_ids=[source])
    result = memory_map(*brain, max_nodes=20, max_edges=10)
    assert len(result["nodes"]) == 20 and len(result["edges"]) <= 10 and result["truncated"]
    ids = {node["id"] for node in result["nodes"]}
    assert all(len(node["label"]) <= 80 for node in result["nodes"])
    assert all(edge["source"] in ids and edge["target"] in ids for edge in result["edges"])
    assert sum(region["count"] for region in result["regions"]) == 20


def test_map_backpressure_reports_retry_without_waiting_for_a_writer(installation, brain):
    service, principal, ident = brain
    headers = {"Authorization": "Bearer map-test-key"}
    settings = replace(installation[1], api_keys={hashlib.sha256(b"map-test-key").hexdigest(): principal})
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1") as client:
        with service.database.transaction(principal) as conn:
            service._brain(conn, principal, ident)
            result = client.get(f"/v1/brains/{ident}/memory-map", headers=headers)
    assert result.status_code == 503
    assert result.json()["error"] == {"code": "dependency_unavailable", "retryable": True,
                                      "message": "Memory is busy updating. Retry the map shortly."}


def test_map_read_does_not_write_or_schedule_processing(brain):
    service, principal, ident = brain
    note(brain, "Prefer a quiet trail.", kind="preference")
    with service.database.transaction(principal) as conn:
        before = [conn.execute(f"SELECT count(*) AS count FROM {table} WHERE tenant_id=%s AND owner_id=%s "
                               "AND brain_id=%s", service._params(principal, ident)).fetchone()
                  for table in ("memory_events", "memory_jobs")]
    first, second = memory_map(*brain), memory_map(*brain)
    assert first["nodes"] == second["nodes"] and first["edges"] == second["edges"]
    with service.database.transaction(principal) as conn:
        after = [conn.execute(f"SELECT count(*) AS count FROM {table} WHERE tenant_id=%s AND owner_id=%s "
                              "AND brain_id=%s", service._params(principal, ident)).fetchone()
                 for table in ("memory_events", "memory_jobs")]
    assert before == after


def test_demo_has_only_fictional_nodes_and_all_edges_have_existing_endpoints():
    demo = json.loads((Path(__file__).parents[1] / "examples" / "memory-map-demo.json").read_text())
    assert demo["demo"] and demo["brain_id"] == "fictional-demo"
    ids = {node["id"] for node in demo["nodes"]}
    assert len(ids) == len(demo["nodes"]) and all(len(node["label"]) <= 80 for node in demo["nodes"])
    assert all(edge["source"] in ids and edge["target"] in ids for edge in demo["edges"])
    assert {region["id"] for region in demo["regions"]} == set(REGIONS.values())


def test_sdk_uses_the_brain_scoped_route_and_explicit_sensitive_flag():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"nodes": []})

    with MemoryClient("http://127.0.0.1:8790", "test", brain_id="my-brain",
                      transport=httpx.MockTransport(respond)) as client:
        assert client.memory_map(max_nodes=20, max_edges=0) == {"nodes": []}
    assert requests[0].url.path == "/v1/brains/my-brain/memory-map"
    assert dict(requests[0].url.params) == {"max_nodes": "20", "max_edges": "0", "include_sensitive": "false"}
