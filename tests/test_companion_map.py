import hashlib
import json
from dataclasses import replace
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from membrain import desktop, embedded_database, host
from membrain import service as service_module
from membrain.api import create_app
from membrain.client import MemoryClient
from membrain.companion_map import companion_map
from membrain.config import configured_service
from membrain.helpers import DomainError, Principal, uid
from membrain.local_profile import load_profile
from membrain.mood import reset_mood
from membrain.notes import store_note
from membrain.persona import delete_persona_history, set_persona
from membrain.persona_growth import accept_proposal, persona_proposals
from membrain.relationship import add_boundary, reset_relationship, set_cap, set_support_style

WHEN = "2026-11-03T18:00:00Z"


@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    assert embedded_database.available(), "Embedded PostgreSQL is required for companion graph acceptance."
    directory = tmp_path_factory.mktemp("companion-map") / "installation"
    with patch.dict("os.environ", {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            settings = load_profile(directory).settings()
            with configured_service(settings) as service:
                yield service, settings
        finally:
            desktop.stop(directory)


@pytest.fixture
def brain(installation, monkeypatch):
    from membrain import mood

    monkeypatch.setattr(service_module, "now", lambda: WHEN)
    monkeypatch.setattr(mood, "_now", lambda: WHEN)
    service, settings = installation
    principal = next(iter(settings.principals().values()))
    return service, principal, service.create_brain(principal, "Companion graph")['id']


def say(brain, text):
    service, principal, ident = brain
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": "companion-map-test",
            "actor_ref": "user", "actor_role": "user", "event_kind": "message",
            "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
        }]},
    })
    assert result["outcome"] == "completed", result
    return result["result"]["accepted_event_ids"][0]


def note(brain, text, **fields):
    return store_note(*brain, {"request_id": uid(), "text": text, **fields})


def erase(brain, event_id):
    service, principal, ident = brain
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [event_id]},
                    "mode": "erase_content", "expected_scope_generation": generation},
    })
    assert result["outcome"] == "completed", result


def assert_graph(graph):
    ids = {node["id"] for node in graph["nodes"]}
    assert len(ids) == len(graph["nodes"]) <= graph["limits"]["max_nodes"]
    assert len(graph["edges"]) <= graph["limits"]["max_edges"]
    assert all(edge["source"] in ids and edge["target"] in ids for edge in graph["edges"])
    assert sum(region["count"] for region in graph["regions"]) == len(ids)
    assert all(len(node["label"]) <= 80 for node in graph["nodes"])


def test_personality_acceptance_has_real_feedback_and_decision_edges(brain):
    set_persona(*brain, {"name": "Aster", "voice": {"register": "formal"}}, made_by="host")
    sources = [say(brain, "You're too formal. Please be more casual.") for _ in range(3)]
    proposal = persona_proposals(*brain, now=WHEN)["proposals"][0]
    assert proposal["status"] == "open"
    open_graph = companion_map(*brain)
    proposal_id = "proposal:" + proposal["id"]
    assert next(node for node in open_graph["nodes"] if node["id"] == proposal_id)["details"]["status"] == "open"
    assert not any(edge["type"] == "accepted_proposal" for edge in open_graph["edges"])
    accept_proposal(*brain, proposal["id"], now=WHEN)
    graph = companion_map(*brain)
    assert_graph(graph)
    version = next(node for node in graph["nodes"] if node["kind"] == "persona" and node["details"]["version"] == 2)
    assert {edge["target"] for edge in graph["edges"] if edge["source"] == version["id"]
            and edge["type"] == "based_on_feedback"} == {"msg:" + source for source in sources}
    assert {"source": version["id"], "target": proposal_id, "type": "accepted_proposal",
            "basis": "persona_feedback_proposal_id"} in graph["edges"]


def test_mood_points_to_the_actual_affect_note_and_original_message(brain):
    source = say(brain, "I am thrilled about my new job.")
    saved = note(brain, "Started a new job.", kind="milestone", source_event_ids=[source],
                 affect={"label": "thrilled", "basis": "reported", "valence": 2, "intensity": 3,
                         "topic": "new job", "felt_at": "2026-11-03"})
    graph = companion_map(*brain)
    assert_graph(graph)
    state = next(node for node in graph["nodes"] if node["kind"] == "simulated_mood")
    assert state["details"]["simulated"] is True and state["details"]["at_baseline"] is False
    assert any(edge["source"] == "mood:current" and edge["type"] == "affected_by" for edge in graph["edges"])
    assert {"source": "affect:" + saved["affect_id"], "target": "note:" + saved["note_id"],
            "type": "feeling_of", "basis": "affect_note_id"} in graph["edges"]
    assert {"source": "note:" + saved["note_id"], "target": "msg:" + source,
            "type": "derived_from", "basis": "source_event_ids"} in graph["edges"]
    erase(brain, saved["note_id"])
    after = companion_map(*brain)
    assert not any(node["kind"] in ("affect", "mood_trigger") for node in after["nodes"])
    assert next(node for node in after["nodes"] if node["kind"] == "simulated_mood")["details"]["at_baseline"]
    assert "new job" not in json.dumps(after)


def test_relationship_reset_removes_settings_and_moments_but_keeps_persona(brain):
    set_persona(*brain, {"name": "Aster"}, made_by="host")
    add_boundary(*brain, "old workplace")
    set_support_style(*brain, "Listen first, then offer advice.")
    source = say(brain, "We finished our first puzzle together.")
    saved = note(brain, "Finished our first puzzle together.", kind="milestone", shared=True,
                 source_event_ids=[source])
    before = companion_map(*brain)
    assert {"boundary", "support_style", "persona"} <= {node["kind"] for node in before["nodes"]}
    assert any(node["id"] == "note:" + saved["note_id"] for node in before["nodes"])
    reset_relationship(*brain)
    after = companion_map(*brain)
    assert not any(node["kind"] in ("boundary", "support_style") for node in after["nodes"])
    assert any(node["kind"] == "persona" for node in after["nodes"])
    assert "first puzzle" not in json.dumps(after)


def test_reading_the_graph_never_creates_a_proposal_or_changes_the_persona(brain):
    service, principal, ident = brain
    set_persona(*brain, {"name": "Aster"}, made_by="host")

    def records():
        with service.database.transaction(principal) as conn:
            return conn.execute("SELECT id,revision,document FROM memory_events WHERE tenant_id=%s "
                                "AND owner_id=%s AND brain_id=%s ORDER BY sequence",
                                service._params(principal, ident)).fetchall()

    before = records()
    companion_map(*brain)
    companion_map(*brain)
    assert records() == before
    delete_persona_history(*brain)
    assert not any(node["kind"] == "persona" for node in companion_map(*brain)["nodes"])


def test_sensitive_shared_moment_and_its_source_are_masked(brain):
    source = say(brain, "Our secret planetarium meeting.")
    saved = note(brain, "Our secret planetarium meeting.", kind="milestone", shared=True, sensitive=True,
                 source_event_ids=[source])
    hidden = companion_map(*brain)
    assert "planetarium" not in json.dumps(hidden)
    assert next(node for node in hidden["nodes"] if node["id"] == "note:" + saved["note_id"])["sensitive"]
    assert all(node["recorded_at"] is None for node in hidden["nodes"] if node.get("masked"))
    visible = companion_map(*brain, include_sensitive=True)
    assert "planetarium" in json.dumps(visible)
    revealed = next(node for node in visible["nodes"] if node["id"] == "note:" + saved["note_id"])
    assert revealed["sensitive"] is True and revealed["masked"] is False
    assert revealed["recorded_at"] is not None


def test_a_sensitive_original_cannot_leak_through_another_affect_or_trigger(brain):
    source = say(brain, "I am thrilled about the secret planetarium job.")
    note(brain, "The planetarium job is private.", kind="constraint", sensitive=True, source_event_ids=[source])
    saved = note(brain, "Accepted the planetarium position.", kind="milestone", source_event_ids=[source],
                 affect={"label": "planetarium excitement", "basis": "reported", "valence": 2, "intensity": 3,
                         "topic": "planetarium", "felt_at": "2026-11-03"})
    graph = companion_map(*brain)
    assert "planetarium" not in json.dumps(graph)
    assert next(node for node in graph["nodes"] if node["id"] == "affect:" + saved["affect_id"])["sensitive"]
    assert next(node for node in graph["nodes"] if node["kind"] == "mood_trigger")["details"] == {}
    assert "planetarium" in json.dumps(companion_map(*brain, include_sensitive=True))


def test_sensitive_feedback_masks_the_proposal_and_accepted_version(brain):
    set_persona(*brain, {"name": "Aster", "voice": {"register": "formal"}}, made_by="host")
    first = say(brain, "You're too formal. Please be more casual. My private code is STARLIGHT.")
    for _ in range(2):
        say(brain, "You're too formal. Please be more casual.")
    note(brain, "STARLIGHT is private.", kind="constraint", sensitive=True, source_event_ids=[first])
    proposal = persona_proposals(*brain, now=WHEN)["proposals"][0]
    accept_proposal(*brain, proposal["id"], now=WHEN)
    graph = companion_map(*brain)
    assert "STARLIGHT" not in json.dumps(graph)
    assert next(node for node in graph["nodes"] if node["id"] == "proposal:" + proposal["id"])["sensitive"]
    assert next(node for node in graph["nodes"] if node["kind"] == "persona" and node["sensitive"])["details"] == {}
    erase(brain, first)
    after = companion_map(*brain, include_sensitive=True)
    assert "STARLIGHT" not in json.dumps(after)
    assert "msg:" + first not in {node["id"] for node in after["nodes"]}


def test_mood_reset_and_time_recovery_do_not_show_active_old_connections(brain, monkeypatch):
    from membrain import mood

    source = say(brain, "We laughed over our first puzzle.")
    note(brain, "We laughed over our first puzzle.", kind="milestone", shared=True, source_event_ids=[source])
    assert any(edge["type"] == "affected_by" for edge in companion_map(*brain)["edges"])
    monkeypatch.setattr(mood, "_now", lambda: "2026-11-06T18:00:00Z")
    ended = companion_map(*brain)
    assert any(node["kind"] == "mood_trigger" and node["details"]["status"] == "ended" for node in ended["nodes"])
    assert not any(edge["type"] == "affected_by" for edge in ended["edges"])
    reset_mood(*brain, now="2026-11-06T18:00:00Z")
    assert not any(node["kind"] == "mood_trigger" for node in companion_map(*brain)["nodes"])


def test_archive_restore_keeps_companion_records_without_retriggering_historical_affect(brain):
    service, principal, ident = brain
    set_persona(*brain, {"name": "Aster"}, made_by="host")
    add_boundary(*brain, "old workplace")
    source = say(brain, "We laughed over our first puzzle.")
    note(brain, "We laughed over our first puzzle.", kind="milestone", shared=True, source_event_ids=[source])

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "key", ident, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        restored = service.create_brain(principal, "Restored companion graph")["id"]
        result = client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                                expected_scope_generation=1, mode="new_brain", brain_id=restored)
        assert result["outcome"] == "completed", result
    graph = companion_map(service, principal, restored)
    assert_graph(graph)
    assert {"persona", "boundary"} <= {node["kind"] for node in graph["nodes"]}
    assert any("first puzzle" in node["label"] for node in graph["nodes"])
    assert not any(node["kind"] == "mood_trigger" for node in graph["nodes"])


def test_python_client_preserves_scope_and_explicit_sensitive_opt_in():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"nodes": [], "edges": []})

    with MemoryClient("http://memory.test", "graph-key", "brain / one", transport=httpx.MockTransport(handle)) as client:
        client.companion_map()
        client.companion_map(brain_id="brain two", max_nodes=25, max_edges=30, include_sensitive=True)
    assert requests[0].url.raw_path.startswith(b"/v1/brains/brain%20%2F%20one/companion-map?")
    assert requests[0].url.params["include_sensitive"] == "false"
    assert requests[1].url.path == "/v1/brains/brain two/companion-map"
    assert dict(requests[1].url.params) == {"max_nodes": "25", "max_edges": "30", "include_sensitive": "true"}


def test_http_map_reports_busy_while_a_writer_holds_the_brain(installation, brain):
    service, settings = installation
    _, principal, ident = brain
    settings = replace(settings, api_keys={hashlib.sha256(b"graph-key").hexdigest(): principal})
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1") as client:
        with service.database.transaction(principal) as conn:
            service._brain(conn, principal, ident)
            response = client.get(f"/v1/brains/{ident}/companion-map", headers={"Authorization": "Bearer graph-key"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"
    assert response.json()["error"]["retryable"] is True


def test_bounds_and_ownership_hold_for_every_returned_edge(brain):
    set_persona(*brain, {"name": "Aster"}, made_by="host")
    add_boundary(*brain, "old workplace")
    for size in (1, 2, 5, 20):
        graph = companion_map(*brain, max_nodes=size, max_edges=0)
        assert_graph(graph)
    assert companion_map(*brain, max_nodes=1)["truncated"]
    service, principal, ident = brain
    with pytest.raises(DomainError, match="Brain is unavailable"):
        companion_map(service, Principal(principal.tenant_id, "someone-else"), ident)


def test_old_persona_versions_cannot_hide_other_companion_layers(brain):
    for version in range(12):
        set_persona(*brain, {"name": f"Aster {version}"}, made_by="host")
    add_boundary(*brain, "old workplace")
    set_support_style(*brain, "Listen first.")
    graph = companion_map(*brain, max_nodes=8)
    assert {"simulated_mood", "persona", "boundary", "support_style"} <= {node["kind"] for node in graph["nodes"]}
    assert any(node["kind"] == "persona" and node["details"]["version"] == 12 for node in graph["nodes"])
    assert graph["truncated"]
    assert_graph(graph)


def test_commitments_show_actual_states_and_a_cap_is_configuration_not_affection(brain):
    set_cap(*brain, "getting_to_know")
    source = say(brain, "You promised to help with the puzzle.")
    expected = {}
    for status, state in (("done", "kept"), ("cancelled", "cancelled"), ("intended", "missed")):
        saved = note(brain, f"Help with the puzzle ({status}).", kind="agent_commitment", status=status,
                     due="2026-10-01", source_event_ids=[source])
        expected["note:" + saved["note_id"]] = state
    graph = companion_map(*brain)
    actual = {node["id"]: node["details"]["commitment_state"] for node in graph["nodes"]
              if node["kind"] == "agent_commitment"}
    assert actual == expected
    cap = next(node for node in graph["nodes"] if node["kind"] == "relationship_cap")
    assert cap["details"]["level"] == "getting_to_know"
    assert all(node["region"] == "commitments" for node in graph["nodes"] if node["kind"] == "agent_commitment")
    assert_graph(graph)
    reset_relationship(*brain)
    assert not any(node["kind"] in ("agent_commitment", "relationship_cap") for node in companion_map(*brain)["nodes"])


@pytest.mark.parametrize("arguments", [{"max_nodes": 0}, {"max_nodes": True}, {"max_nodes": 501},
                                        {"max_edges": -1}, {"max_edges": 1001}, {"include_sensitive": "yes"}])
def test_direct_calls_reject_invalid_bounds_without_reading_memory(brain, arguments):
    with pytest.raises(DomainError) as error:
        companion_map(*brain, **arguments)
    assert error.value.code == "validation_failed"


def test_http_route_authenticates_scopes_and_validates_the_window(installation, brain):
    service, settings = installation
    _, principal, ident = brain
    other = Principal(principal.tenant_id, "another-owner")
    foreign = service.create_brain(other, "Another owner's graph")
    keys = {hashlib.sha256(b"graph-key").hexdigest(): principal}
    with TestClient(create_app(replace(settings, api_keys=keys), service), base_url="http://127.0.0.1") as client:
        route = f"/v1/brains/{ident}/companion-map"
        assert client.get(route).status_code == 401
        denied = client.get(f"/v1/brains/{foreign['id']}/companion-map",
                            headers={"Authorization": "Bearer graph-key"})
        assert denied.status_code == 404 and "Another owner's graph" not in denied.text
        assert client.get(route + "?max_nodes=501", headers={"Authorization": "Bearer graph-key"}).status_code == 422
        response = client.get(route, headers={"Authorization": "Bearer graph-key"})
        assert response.status_code == 200
        assert_graph(response.json())
        assert response.json()["coverage"]["learned_memory"] == "not_projected"
