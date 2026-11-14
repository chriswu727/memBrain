"""Archives that carry the cognitive views and interpretations an older runtime's learning stored.

Nothing writes these views any more, but archives exported by older runtimes hold them, and a brain restored from one
holds them again. The brains here are restored from archives the runtime at 2600219b exported (see
``legacy_cognition.py``); each test then exports, restores, uploads or erases as the original tests of these views
did when the pipeline still built them.
"""
import copy
import json

import pytest
from legacy_cognition import archive as archive
from legacy_cognition import fixture, legacy_brain
from psycopg.types.json import Jsonb

from membrain.archive_views import REBUILD_POLICY
from membrain.context_views import assistant_speech
from membrain.helpers import DomainError

pytestmark = pytest.mark.integration

CLAIM_SOURCE_KEY = "versioned-source"
CONTEXT = "这段上下文决定本次记忆的适用情境。"
DERIVED = "工作情境中的反馈模式。"


def populated(archive, name="views"):
    """Restore a brain an older runtime's learning filled; return its claim source and unselected context."""
    result, _ = legacy_brain(archive, name)
    assert result["quarantined_event_count"] == 0
    events = [archive.event(row["id"]) for row in archive.rows("memory_events", "AND is_current")]
    source = next(event for event in events if event["observed"]["source_event_key"] == next(
        item["event_id"] for item in fixture(name)["events"]
        if item["observed"]["source_event_key"] == CLAIM_SOURCE_KEY))
    context = next(event for event in events if event["observed"]["content"]["text"] == CONTEXT)
    return source, context


def test_local_cognitive_archive_restores_exact_views_and_remaps_source_revisions(archive):
    data = fixture("views_revised")
    assert data["archive_origin"] == "local_export"
    assert data["cognitive_views"]["episodes"] and data["cognitive_views"]["members"]
    assert data["cognitive_views"]["associations"]
    assert data["rebuild_policy"] == REBUILD_POLICY
    original = next(item for item in data["events"] if item["observed"]["source_event_key"] == CLAIM_SOURCE_KEY)
    assert original["revision"] == 2
    source, _ = populated(archive, "views_revised")
    assert source["event_id"] == original["event_id"] and source["revision"] == 1
    restored_memories = {row["id"]: row["document"] for row in archive.rows("memory_assertions")}
    for memory in data["memories"]:
        restored = restored_memories[memory["memory_id"]]
        assert restored["revision"] == memory["revision"]
        assert restored["derivation"]["source_memory_versions"] == memory["derivation"]["source_memory_versions"]
        for ref in restored["evidence_refs"]:
            if ref["event_id"] == source["event_id"]:
                assert ref["event_revision"] == 1
    restored_episode = archive.rows("memory_episodes")[0]
    assert restored_episode["revision"] == data["cognitive_views"]["episodes"][0]["document"]["revision"]
    assert restored_episode["document"]["member_refs"] == [{"event_id": source["event_id"], "revision": 1}]
    for field in ("organization_statement", "organization_scope", "organization_action", "organization_source_version"):
        assert restored_episode["document"][field] == data["cognitive_views"]["episodes"][0]["document"][field]
    assert len(archive.rows("memory_episode_members")) == len(data["cognitive_views"]["members"])
    assert len(archive.rows("memory_associations")) == len(data["cognitive_views"]["associations"])
    with archive.database.transaction(archive.principal) as conn:
        projection = conn.execute("SELECT count(*) AS n, bool_and(search_lexemes = to_tsvector('simple',search_text)) AS valid "
                                  "FROM memory_assertions WHERE brain_id=%s", (archive.brain_id,)).fetchone()
        assert projection["n"] == len(restored_memories) and projection["valid"]
        restored = conn.execute("SELECT document,recall_non_speech FROM memory_assertions WHERE brain_id=%s",
                                (archive.brain_id,)).fetchall()
        assert all(row["recall_non_speech"] is (not assistant_speech(row["document"])) for row in restored)
        for table in ("memory_access_state", "memory_embeddings", "memory_cognitive_operations"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE brain_id=%s", (archive.brain_id,)).fetchone()["n"] == 0


def test_export_includes_exact_noncurrent_parent_version_without_rewriting_to_latest(archive):
    data = fixture("noncurrent_parent")
    (parent,) = data["dependency_memories"]
    assert parent["revision"] == 7
    result, _ = legacy_brain(archive, "noncurrent_parent")
    assert result["quarantined_event_count"] == 0
    rows = archive.rows("memory_assertions")
    restored_parent = next(row for row in rows if row["id"] == parent["memory_id"])
    assert restored_parent["revision"] == 7 and not restored_parent["is_current"]
    restored_child = next(row["document"] for row in rows if row["id"] != parent["memory_id"])
    assert restored_child["derivation"]["source_memory_versions"] == [{"memory_id": parent["memory_id"], "revision": 7}]
    exported = archive.export()
    assert [(m["memory_id"], m["revision"]) for m in exported["document"]["dependency_memories"]] == [
        (parent["memory_id"], 7)]


def test_erasure_removes_archived_semantics_episodes_and_unselected_root_context(archive):
    _, context = populated(archive)
    exported = archive.export()
    semantic_ids = {m["memory_id"] for m in exported["document"]["memories"] if m.get("verification")}
    assert semantic_ids
    offline = copy.deepcopy(exported["document"])
    offline["events"] = [event for event in offline["events"] if event["event_id"] != context["event_id"]]
    for memory in offline["memories"]:
        if memory["memory_id"] in semantic_ids:
            memory["memory_id"] = "offline-renamed-" + memory["memory_id"]
    archive.forget("events", [context["event_id"]])
    sanitized = archive.service.download_archive(archive.principal, exported["archive_id"])["document"]
    assert not any(m.get("verification") and context["event_id"] in m.get("root_event_ids", [])
                   for m in sanitized["memories"])
    assert not sanitized["cognitive_views"]["episodes"]
    assert not sanitized["cognitive_views"]["members"]
    assert not sanitized["cognitive_views"]["associations"]
    assert DERIVED not in json.dumps(sanitized, ensure_ascii=False)
    uploaded = archive.service.upload_archive(archive.principal, archive.brain_id, offline)
    sanitized_upload = archive.service.download_archive(archive.principal, uploaded["archive_id"])["document"]
    assert not any(m.get("verification") and context["event_id"] in m.get("root_event_ids", [])
                   for m in sanitized_upload["memories"])
    assert not sanitized_upload["cognitive_views"]["episodes"]


def test_upload_cannot_assert_local_semantic_verification_or_restore_execution_state(archive):
    assert fixture("views")["cognitive_views"]["episodes"][0]["document"]["organization_statement"]
    result, _ = legacy_brain(archive, upload=True)
    assert result["quarantined_event_count"] >= 2
    assert all(row["document"].get("verification") is None for row in archive.rows("memory_assertions"))
    assert not archive.rows("memory_episodes")
    assert not archive.rows("memory_episode_members")
    assert not archive.rows("memory_associations")
    assert any("reverification" in detail for detail in result["job"]["details"])


def test_episode_transition_archive_preserves_audit_identity_without_restoring_old_history(archive):
    data = fixture("episode_transition")
    assert len(data["cognitive_views"]["episodes"]) == 1
    archived_episode = copy.deepcopy(data["cognitive_views"]["episodes"][0]["document"])
    assert archived_episode["revision"] == 3
    assert archived_episode["organization_source_version"] == {"episode_id": archived_episode["episode_id"],
                                                               "revision": 2}
    result, stored = legacy_brain(archive, "episode_transition")
    assert result["quarantined_event_count"] == 0
    restored_rows = archive.rows("memory_episodes")
    assert len(restored_rows) == 1 and restored_rows[0]["revision"] == 3
    restored = restored_rows[0]["document"]
    assert restored["revision"] == 3
    assert restored["organization_source_version"] == archived_episode["organization_source_version"]
    assert restored["organization_statement"] == archived_episode["organization_statement"]
    assert restored["organization_scope"] == "episode_transition" and restored["organization_action"] == "close"
    assert all(ref["revision"] == 1 for ref in restored["member_refs"])
    assert restored["boundary_ref"] == {"event_id": archived_episode["boundary_ref"]["event_id"], "revision": 1}
    assert archive.service.download_archive(archive.principal, stored["archive_id"])["document"][
        "cognitive_views"]["episodes"][0]["document"] == archived_episode


def test_legacy_episode_archive_roundtrip_does_not_invent_organization_metadata(archive):
    populated(archive)
    legacy = copy.deepcopy(archive.rows("memory_episodes")[0]["document"])
    for field in ("organization_statement", "organization_scope", "organization_action", "organization_source_version"):
        legacy.pop(field)
    with archive.database.transaction(archive.principal) as conn:
        conn.execute("UPDATE memory_episodes SET document=%s WHERE tenant_id=%s AND brain_id=%s AND id=%s",
                     (Jsonb(legacy), archive.principal.tenant_id, archive.brain_id, legacy["episode_id"]))
    exported = archive.export()
    assert exported["document"]["cognitive_views"]["episodes"][0]["document"] == legacy
    result = archive.restore(exported)
    assert result["quarantined_event_count"] == 0
    restored = archive.rows("memory_episodes")[0]["document"]
    assert set(restored) == set(legacy)
    assert {key: value for key, value in restored.items() if key != "scope"} == {
        key: value for key, value in legacy.items() if key != "scope"}


def test_upload_literal_label_cannot_hide_an_unsupported_statement(archive):
    document = fixture("views")
    literal = next(m for m in document["memories"] if m["derivation"]["method"] == "direct_capture")
    literal["statement"] = "Unsupported private claim that was never in the source."
    result = archive.restore({"document": document}, upload=True)
    assert result["quarantined_event_count"] >= 1
    assert all("Unsupported private claim" not in row["document"]["statement"] for row in archive.rows("memory_assertions"))


def test_export_without_assertions_does_not_include_cognitive_interpretations(archive):
    populated(archive)
    data = archive.export(include_assertions=False)["document"]
    assert data["memories"] == data["dependency_memories"] == []
    assert all(data["cognitive_views"][field] == [] for field in ("episodes", "members", "associations"))
    assert data["belief_relations"] == []
    assert DERIVED not in json.dumps(data, ensure_ascii=False)


def test_archive_without_sources_quarantines_interpretations_instead_of_assuming_latest(archive):
    populated(archive)
    exported = archive.export(include_events=False)
    result = archive.restore(exported)
    assert result["imported_event_count"] == 0
    assert result["quarantined_event_count"] >= 2
    assert not archive.rows("memory_assertions")
    assert not archive.rows("memory_episodes")


@pytest.mark.parametrize("mutate", [
    lambda data: data.update(untracked_summary="hidden private content"),
    lambda data: data["cognitive_views"].update(unknown_private_field="hidden content"),
    lambda data: data["cognitive_views"]["episodes"][0]["document"].update(hidden_text="untracked private summary"),
    lambda data: data["cognitive_views"]["episodes"][0]["document"].update(root_event_ids=["x"] * 257),
    lambda data: data["cognitive_views"]["members"][0].update(memory_revision=0),
    lambda data: data["cognitive_views"]["associations"][0].update(event_ids=["x"] * 513),
])
def test_cognitive_archive_extension_fields_are_strict_and_bounded(archive, mutate):
    populated(archive)
    data = archive.export()["document"]
    mutate(data)
    with pytest.raises(DomainError):
        archive.service.upload_archive(archive.principal, archive.brain_id, data)
    original = fixture("views")
    mutate(original)
    with pytest.raises(DomainError):
        archive.service.upload_archive(archive.principal, archive.brain_id, original)


def test_same_local_archive_merge_is_idempotent_for_episode_versions(archive):
    populated(archive)
    exported = archive.export()
    before = len(archive.rows("memory_episodes"))
    result = archive.restore(exported, new_brain=False)
    assert len(archive.rows("memory_episodes")) == before
    assert result["quarantined_event_count"] == 0
    assert '"quarantined_views": 0' in result["job"]["details"][1]


def test_uploaded_working_state_does_not_bypass_semantic_reverification(archive):
    source, _ = populated(archive)
    exported = archive.export()
    with archive.database.transaction(archive.principal) as conn:
        brain = archive.service._brain(conn, archive.principal, archive.brain_id)
        working = archive.service._working(conn, archive.principal, brain,
                                          {"conversation_ref": "test", "branch_ref": "main"}, None)
    working["revision"] = 1
    working["items"] = [{"key": "fabricated", "value": "Never established by the source.",
                         "knowledge_state": "grounded", "evidence_refs": [exported["document"]["memories"][0]["evidence_refs"][0]],
                         "expires_at": None, "updated_at": source["system_time"]["recorded_at"]}]
    exported["document"]["working_states"] = [working]
    archive.restore(exported, upload=True)
    assert not archive.rows("memory_working_states")


def test_restore_reports_conflicting_association_instead_of_overwriting_it(archive):
    populated(archive)
    exported = archive.export()
    association_id = exported["document"]["cognitive_views"]["associations"][0]["id"]
    with archive.database.transaction(archive.principal) as conn:
        conn.execute("UPDATE memory_associations SET relation='exception' WHERE brain_id=%s AND id=%s", (archive.brain_id, association_id))
    result = archive.restore(exported, new_brain=False)
    assert archive.rows("memory_associations")[0]["relation"] == "exception"
    assert '"quarantined_views": 1' in result["job"]["details"][1]


def test_invalidated_episode_does_not_reappear_or_abort_entire_restore(archive):
    populated(archive)
    exported = archive.export()
    with archive.database.transaction(archive.principal) as conn:
        conn.execute("UPDATE memory_episodes SET invalidated=true,document=NULL WHERE brain_id=%s", (archive.brain_id,))
    result = archive.restore(exported, new_brain=False)
    assert archive.rows("memory_episodes")[0]["document"] is None
    assert result["read_enabled"]
    assert '"quarantined_views": 0' not in result["job"]["details"][1]


def test_an_older_archive_restored_twice_keeps_one_copy_and_stays_erasable(archive):
    """The stored fixture restored into the same brain again merges instead of duplicating, and forgetting its
    claim source then clears what was restored both times."""
    source, _ = populated(archive)
    stored = archive.export()
    archive.restore(stored, new_brain=False)
    assert len(archive.rows("memory_episodes")) == 1
    archive.forget("events", [source["event_id"]])
    assert all(row["invalidated"] for row in archive.rows("memory_episodes"))
    assert all(row["invalidated"] for row in archive.rows("memory_associations"))
