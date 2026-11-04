import hashlib

import httpx
import pytest
from fastapi.testclient import TestClient
from test_belief_store import linked
from test_consolidation import memory as _memory
from test_memory_hologram_browser import preview as _preview
from test_memory_observatory_browser import _tab
from test_memory_observatory_browser import browser as _browser
from test_pattern_store import populated
from test_pattern_store import store as _store

from membrain.api import create_app
from membrain.client import MemoryClient
from membrain.config import Settings
from membrain.helpers import DomainError, Principal, uid
from membrain.notes import store_note
from membrain.structure_map import episode_key, memory_key, structure_map

memory, store, browser, preview = _memory, _store, _browser, _preview
pytestmark = pytest.mark.integration


def graph(store, **options):
    return structure_map(store.service, store.principal, store.brain_id, **options)


def test_stored_assertions_episodes_patterns_and_exact_membership(store):
    sources, memories, episodes, _, _ = populated(store)
    result = graph(store)
    nodes = {node["id"]: node for node in result["nodes"]}
    assert result["contract_version"] == "memory-structure-v1"
    assert {memory_key(item["memory_id"], item["revision"]) for item in memories} <= nodes.keys()
    assert {episode_key(item["episode_id"], item["revision"]) for item in episodes} <= nodes.keys()
    assert {"msg:" + item["event_id"] for item in sources} <= nodes.keys()
    assert any(node["kind"] == "pattern" for node in nodes.values())
    assert all(edge["source"] in nodes and edge["target"] in nodes for edge in result["edges"])
    memberships = {(episode_key(row["episode_id"], row["episode_revision"]),
                    memory_key(row["memory_id"], row["memory_revision"]), row["role"])
                   for row in store.rows("memory_episode_members")}
    assert {(edge["source"], edge["target"], edge["basis"]) for edge in result["edges"]
            if edge["type"] == "episode_member"} == memberships
    associations = {(memory_key(row["source_id"], row["source_revision"]),
                     memory_key(row["target_id"], row["target_revision"]), row["relation"])
                    for row in store.rows("memory_associations") if not row["invalidated"]}
    assert {(edge["source"], edge["target"], edge["basis"]) for edge in result["edges"]
            if edge["type"] == "association"} == associations
    for item in memories:
        node = nodes[memory_key(item["memory_id"], item["revision"])]
        assert node["details"]["activation"] == item["dynamics"]["activation"]
        assert node["details"]["epistemic_status"] == item["epistemic_status"]
    assert any(edge["type"] == "pattern_member" for edge in result["edges"])


def test_exact_belief_versions_and_labels_are_projected(store):
    _, old, new, _, _, _, metadata = linked(store)
    result = graph(store)
    relation = next(edge for edge in result["edges"] if edge["type"] == "belief_relation")
    assert relation == {"source": memory_key(new["memory_id"], new["revision"]),
                        "target": memory_key(old["memory_id"], old["revision"]),
                        "type": "belief_relation", "basis": "exception"}
    assert metadata["belief_relation_versions"]


def test_sensitive_evidence_masks_assertions_episodes_patterns_and_sources(store):
    sources, _, _, _, _ = populated(store)
    sensitive = sources[0]["event_id"]
    store_note(store.service, store.principal, store.brain_id,
               {"request_id": uid(), "text": "This source is private.", "kind": "constraint", "sensitive": True,
                "source_event_ids": [sensitive]})
    result = graph(store)
    masked = [node for node in result["nodes"] if node.get("masked")]
    assert {"assertion", "episode", "pattern"} <= {node["kind"] for node in masked}
    assert all(node["label"] == "Sensitive memory" and node["details"] == {} for node in masked)
    assert all(node["recorded_at"] is None for node in result["nodes"] if node.get("sensitive"))
    assert next(node for node in result["nodes"] if node["id"] == "msg:" + sensitive)["label"] == "Sensitive memory"
    revealed = graph(store, include_sensitive=True)
    assert all(not node.get("masked") for node in revealed["nodes"])
    assert any(node["sensitive"] and node["kind"] == "assertion" for node in revealed["nodes"])
    assert all(node["recorded_at"] is not None for node in revealed["nodes"]
               if node.get("sensitive") and node["kind"] not in {"episode", "pattern"})
    original = next(node for node in revealed["nodes"] if node["id"] == "msg:" + sensitive)
    assert original["recorded_at"] == sources[0]["system_time"]["recorded_at"]


@pytest.mark.parametrize("mode", ["erase_content", "suppress_recall"])
def test_forgetting_a_source_removes_dependent_nodes_and_links(store, mode):
    sources, _, _, _, _ = populated(store)
    before = graph(store)
    source = sources[0]
    store.action("forget", {"selector": {"kind": "events", "ids": [source["event_id"]]}, "mode": mode,
                            "expected_scope_generation": 1, "idempotency_key": uid()})
    after = graph(store)
    ids = {node["id"] for node in after["nodes"]}
    assert "msg:" + source["event_id"] not in ids
    assert len(after["nodes"]) < len(before["nodes"])
    assert not any(node["kind"] == "pattern" for node in after["nodes"])
    assert all(edge["source"] in ids and edge["target"] in ids for edge in after["edges"])


@pytest.mark.parametrize("nodes,edges", [(1, 0), (2, 1), (8, 4), (200, 400), (500, 1000)])
def test_bounds_and_trace_counts_match_the_returned_graph(store, nodes, edges):
    sources, _, _, _, _ = populated(store)
    result = graph(store, max_nodes=nodes, max_edges=edges,
                   trace={"at": "2026-11-03T12:00:00Z", "event_ids": [source["event_id"] for source in sources]})
    assert len(result["nodes"]) <= nodes and len(result["edges"]) <= edges
    assert result["trace"]["shown"] == sum(bool(node.get("traced")) for node in result["nodes"])
    if nodes < 8:
        assert result["truncated"]


def test_empty_brain_has_no_fabricated_memory_or_edge(store):
    result = graph(store)
    assert result["nodes"] == result["edges"] == []
    assert not result["truncated"]


def test_read_does_not_change_learning_or_access_state(store):
    populated(store)

    def snapshot():
        with store.database.transaction(store.principal) as conn:
            return {table: conn.execute("SELECT to_jsonb(t) AS value FROM " + table + " t WHERE "
                                        "tenant_id=%s AND owner_id=%s AND brain_id=%s ORDER BY to_jsonb(t)::text",
                                        store.service._params(store.principal, store.brain_id)).fetchall()
                    for table in ("memory_assertions", "memory_episodes", "memory_associations", "memory_pattern_views",
                                  "memory_access_state", "memory_jobs", "memory_requests")}

    before = snapshot()
    graph(store)
    assert snapshot() == before


def test_api_requires_owner_and_sdk_opts_in_explicitly(store):
    populated(store)
    key, other = uid(), uid()
    settings = Settings(database_url=store.database.dsn, api_keys={
        hashlib.sha256(key.encode()).hexdigest(): store.principal,
        hashlib.sha256(other.encode()).hexdigest(): Principal(store.principal.tenant_id, uid())})
    with TestClient(create_app(settings, service=store.service), base_url="http://127.0.0.1") as client:
        url = f"/v1/brains/{store.brain_id}/memory-map?structure=true"
        assert client.get(url).status_code == 401
        assert client.get(url, headers={"Authorization": "Bearer " + other}).status_code == 404
        response = client.get(url, headers={"Authorization": "Bearer " + key})
        assert response.status_code == 200
        assert response.json()["contract_version"] == "memory-structure-v1"
    requested = []

    def receive(request):
        requested.append(request)
        return httpx.Response(200, json={"nodes": [], "edges": []})

    with MemoryClient("http://127.0.0.1", key, brain_id="brain one", transport=httpx.MockTransport(receive)) as client:
        client.memory_map()
        client.memory_map(structure=True, brain_id="brain two")
    assert "structure" not in requested[0].url.params
    assert requested[1].url.params["structure"] == "true" and "brain%20two" in str(requested[1].url)


@pytest.mark.parametrize("options", [{"max_nodes": 0}, {"max_nodes": True}, {"max_nodes": 501},
                                    {"max_edges": -1}, {"max_edges": 1001}, {"include_sensitive": "yes"}])
def test_invalid_limits_are_rejected(store, options):
    with pytest.raises(DomainError, match="allow|must"):
        graph(store, **options)


@pytest.mark.parametrize("language", ["en", "zh"])
def test_database_graph_is_identical_in_3d_hologram_and_2d(store, browser, preview, language):
    sources, _, _, _, _ = populated(store)
    payload = graph(store)
    preview.set_map(payload)
    context, tab = _tab(browser)
    page = tab.page
    try:
        page.goto(f"{preview.base_url}/memory?demo=brain&lang={language}")
        page.wait_for_function("() => window.observatory.snapshot().nodes.length > 0")
        expected = {node["id"] for node in payload["nodes"]}
        assert set(page.evaluate("window.observatory.snapshot().nodes")) == expected
        positions = page.evaluate("map => window.observatory.layout(map)", payload)
        shuffled = {**payload, "nodes": list(reversed(payload["nodes"])), "edges": list(reversed(payload["edges"]))}
        assert page.evaluate("map => window.observatory.layout(map)", shuffled) == positions
        disconnected = {**payload, "edges": []}
        assert page.evaluate("map => window.observatory.layout(map)", disconnected) != positions
        page.locator("#brain-showcase").click()
        page.wait_for_function("() => window.memoryHologram.snapshot().ready")
        hologram = page.evaluate("window.memoryHologram.snapshot()")
        assert set(hologram["nodeIds"]) == expected
        assert hologram["edges"] == payload["edges"]
        assert hologram["positions"] == positions
        assert page.locator(".hologram-canvas").is_visible()
        page.locator("#show-close").click()
        page.locator("#mode-2d").click()
        assert set(page.locator(".brain-node").evaluate_all("nodes => nodes.map(node => node.dataset.id)")) == expected
        assert page.locator(".brain-edge").count() == len(payload["edges"])
        store.action("forget", {"selector": {"kind": "events", "ids": [sources[0]["event_id"]]},
                                "mode": "erase_content", "expected_scope_generation": 1, "idempotency_key": uid()})
        updated = graph(store)
        preview.set_map(updated)
        page.reload()
        page.wait_for_function("() => document.querySelectorAll('.brain-node').length > 0")
        assert "msg:" + sources[0]["event_id"] not in page.locator(".brain-node").evaluate_all(
            "nodes => nodes.map(node => node.dataset.id)")
        assert tab.errors == []
    finally:
        context.close()
