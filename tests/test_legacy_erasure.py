"""Rows in tables the runtime no longer writes: old data must still be erasable, restorable and harmless.

Pattern views (migration 008) were built by a module that has been removed. Installations, configured profiles and
restored archives can still hold them, so these tests write such rows with plain SQL, as an older runtime left them.
"""
import copy
import json

import pytest
from psycopg.types.json import Jsonb
from test_cognition import prepare_payload, request
from test_cognitive_archives import Archives
from test_consolidation import memory as memory
from test_semantic import episode, proposals, run

from membrain import cognition
from membrain.archive_views import memory_sources
from membrain.contracts import validate
from membrain.helpers import Principal, digest, uid

pytestmark = pytest.mark.integration

LEGACY_PATTERN_FORMAT = "schema-residual-v1"


@pytest.fixture
def store(memory):
    return Archives(memory.database)


def pattern_rows(store):
    with store.database.transaction(store.principal) as conn:
        return conn.execute(
            "SELECT * FROM memory_pattern_views WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s ORDER BY id",
            store.service._params(store.principal, store.brain_id),
        ).fetchall()


def legacy_pattern_view(store, memories, episodes):
    """Insert a pattern view over these memories and episodes, with the source columns an older runtime filled."""
    with store.database.transaction(store.principal) as conn:
        brain = store.service._brain(conn, store.principal, store.brain_id)
        scope = store.service._scope(store.principal, brain, {"conversation_ref": "test", "branch_ref": "main"})
        rows = conn.execute(
            "SELECT event_ids FROM memory_episodes WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND id=ANY(%s::text[])",
            (*store.service._params(store.principal, store.brain_id), [item["episode_id"] for item in episodes]),
        ).fetchall()
        source_ids = {identifier for memory in memories for identifier in memory_sources(memory)}
        source_ids.update(identifier for row in rows for identifier in row["event_ids"])
        for item in episodes:
            source_ids.update(item.get("root_event_ids", []))
            source_ids.update(ref["event_id"] for ref in item["member_refs"])
        view = {
            "format_version": LEGACY_PATTERN_FORMAT, "scope": scope, "coverage": "selected_assertions_only",
            "definition": {"shared_claims": []},
            "source_memory_versions": [{"memory_id": item["memory_id"], "revision": item["revision"]}
                                       for item in memories],
            "root_event_ids": sorted(source_ids),
            "instances": [{"episode_ref": {"episode_id": item["episode_id"], "revision": item["revision"]},
                           "observed_memory_versions": [], "shared_bindings": [], "residual_memory_versions": []}
                          for item in episodes],
        }
        view["view_id"] = "pattern-" + digest(view)
        conn.execute(
            "INSERT INTO memory_pattern_views(tenant_id,owner_id,brain_id,id,document,event_ids,memory_ids,episode_ids) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (*store.service._params(store.principal, store.brain_id), view["view_id"], Jsonb(view), sorted(source_ids),
             sorted({item["memory_id"] for item in memories}), sorted({item["episode_id"] for item in episodes})),
        )
    return view


def episodes_only(store, *, hidden_context=False):
    """Two verified episodes with a shared practice and different details: the input an old pattern was built from."""
    sources = []
    for detail in ("今天复习代数。", "今天复习几何。"):
        common = store.observe("先交流，再制定计划。")
        specific = store.observe(detail)
        inputs = [common, specific]
        if hidden_context and not sources:
            inputs.append(store.observe("本轮另有未引用的上下文。"))
        batch = store.batch(*inputs)
        action = episode(common, member_refs=[{"event_id": source["event_id"], "revision": source["revision"]}
                                             for source in (common, specific)])
        store.publish(batch, run(batch, proposals(episodes=[action])))
        sources.extend(inputs)
    memories = [row["document"] for row in store.rows("memory_assertions")]
    episodes = [row["document"] for row in store.rows("memory_episodes")]
    return sources, memories, episodes


def populated(store, *, hidden_context=False):
    """Episodes plus the pattern view an older runtime would have stored for them."""
    sources, memories, episodes = episodes_only(store, hidden_context=hidden_context)
    batch = store.batch(*sources, existing_assertions=tuple(memories), episodes=tuple(episodes))
    result = run(batch, proposals())
    metadata = store.publish(batch, result)
    assert metadata["pattern_view_ids"] == []
    assert pattern_rows(store) == []
    legacy_pattern_view(store, memories, episodes)
    assert len(pattern_rows(store)) == 1
    return sources, memories, episodes, batch, result


@pytest.mark.parametrize("mode", ["suppress_recall", "erase_content"])
def test_forget_clears_a_legacy_pattern_view_and_leaves_unrelated_facts_independent(store, mode):
    sources, _, _, _, _ = populated(store)
    store.action("forget", {"selector": {"kind": "events", "ids": [sources[0]["event_id"]]},
                            "mode": mode, "expected_scope_generation": 1, "idempotency_key": uid()})
    assert all(row["invalidated"] and row["document"] is None for row in pattern_rows(store))
    assert all(row["deleted"] is (mode == "erase_content") for row in pattern_rows(store))
    other_ids = {source["event_id"] for source in sources[2:]}
    other = [row for row in store.rows("memory_assertions") if set(row["event_ids"]) <= other_ids]
    assert other and all(not row["invalidated"] and not row["deleted"] for row in other)


def test_forgetting_a_memory_clears_a_legacy_pattern_view_that_names_it(store):
    _, memories, _, _, _ = populated(store)
    store.action("forget", {"selector": {"kind": "memories", "ids": [memories[0]["memory_id"]]},
                            "mode": "erase_content", "expected_scope_generation": 1, "idempotency_key": uid()})
    assert all(row["invalidated"] and row["deleted"] and row["document"] is None for row in pattern_rows(store))


def test_source_edit_clears_a_legacy_pattern_view(store):
    sources, _, _, _, _ = populated(store)
    source = sources[0]
    store.observe("今天不交流，直接制定计划。", key=source["observed"]["source_event_key"], revision=2)
    assert all(row["document"] is None and row["invalidated"] and not row["deleted"] for row in pattern_rows(store))


def test_unselected_episode_root_of_a_legacy_view_is_an_erasure_dependency(store):
    sources, _, _, _, _ = populated(store, hidden_context=True)
    hidden = sources[2]
    assert all(hidden["event_id"] in row["event_ids"] for row in pattern_rows(store))
    store.action("forget", {"selector": {"kind": "events", "ids": [hidden["event_id"]]},
                            "mode": "erase_content", "expected_scope_generation": 1, "idempotency_key": uid()})
    assert all(row["document"] is None and row["deleted"] for row in pattern_rows(store))


def test_episode_revision_clears_a_legacy_view_and_builds_no_new_one(store):
    sources, memories, episodes, _, _ = populated(store)
    previous = episodes[0]
    refs = previous["member_refs"]
    selected = {ref["event_id"] for ref in refs}
    inputs = [source for source in sources if source["event_id"] in selected]
    batch = store.batch(*inputs, episodes=(previous,))
    action = episode(inputs[0], action="close", episode_id=previous["episode_id"], expected_revision=previous["revision"],
                     member_refs=refs, boundary_ref=refs[-1])
    store.publish(batch, run(batch, proposals(episodes=[action])))
    assert all(row["document"] is None and row["invalidated"] for row in pattern_rows(store))
    assert all(not row["invalidated"] for row in store.rows("memory_assertions"))
    current = [row["document"] for row in store.rows("memory_episodes") if row["is_current"]]
    refreshed = store.batch(*sources, existing_assertions=tuple(memories), episodes=tuple(current))
    assert store.publish(refreshed, run(refreshed, proposals()))["pattern_view_ids"] == []
    assert len(pattern_rows(store)) == 1


def test_legacy_pattern_table_keeps_principal_isolation(store):
    populated(store)
    with store.database.transaction(Principal(uid(), uid())) as conn:
        assert conn.execute("SELECT count(*) AS value FROM memory_pattern_views WHERE brain_id=%s",
                            (store.brain_id,)).fetchone()["value"] == 0


def recalled(store):
    result = store.action("recall", request("复习"))
    return result["status"], [(item["memory"]["memory_id"], item["memory"]["revision"], item["display_mode"])
                              for item in result["items"]]


def test_recall_output_is_the_same_with_or_without_a_legacy_pattern_view(store):
    _, memories, episodes = episodes_only(store)
    before = recalled(store)
    assert before[1]
    legacy_pattern_view(store, memories, episodes)
    assert recalled(store) == before


def test_prepare_on_a_brain_with_a_legacy_pattern_view_uses_the_original_facts(store):
    _, memories, episodes = episodes_only(store)
    legacy_pattern_view(store, memories, episodes)
    latest = store.observe("复习")
    payload = prepare_payload()
    payload["latest_input_event_ids"] = [latest["event_id"]]
    packet = store.action("prepare", payload)
    validate("ContextPacket", packet)
    blocks = [json.loads(block["text"]) for block in packet["blocks"]
              if block["section"] in {"relevant_memory", "conditional_memory"}]
    assert blocks and not any(isinstance(content, dict) and content.get("format") == LEGACY_PATTERN_FORMAT
                              for content in blocks)
    rendered = cognition.render_context(packet)
    assert "今天复习代数" in rendered and "今天复习几何" in rendered


@pytest.mark.parametrize("upload", [False, True])
def test_archive_of_a_brain_that_held_patterns_restores_its_episodes_without_rebuilding_views(store, upload):
    populated(store)
    exported = store.export()
    data = exported["document"]
    assert LEGACY_PATTERN_FORMAT not in json.dumps(data)
    assert len(data["cognitive_views"]["episodes"]) == 2
    original = copy.deepcopy(store.rows("memory_assertions"))
    result = store.restore(exported, upload=upload)
    assert result["read_enabled"] is True
    assert not pattern_rows(store)
    assert not any("patterns_rebuilt" in detail for detail in result["job"]["details"])
    if not upload:
        assert result["quarantined_event_count"] == 0
        assert len(store.rows("memory_episodes")) == 2
        assert len(store.rows("memory_assertions")) == len(original)
    assert recalled(store)[1]
