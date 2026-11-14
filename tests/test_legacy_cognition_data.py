"""A brain that an older runtime's cognition pipeline filled keeps working after the pipeline was removed.

Its derived rows (semantic claims, episodes, members, associations, belief relations, learning jobs, operations,
budgets, feedback and access state) are never written again, but recall, the memory page and archives still read
them, and editing, forgetting or erasing a source must still clear every row that depended on it. See
``legacy_cognition.py`` for how such a brain is built.
"""
import json

import pytest
from legacy_cognition import Brain, fixture, legacy_brain, legacy_feedback, legacy_jobs
from legacy_cognition import brain as brain
from psycopg.types.json import Jsonb
from test_cognition import prepare_payload, request

from membrain import cognition
from membrain.companion_map import companion_map
from membrain.contracts import validate
from membrain.helpers import Principal, uid
from membrain.jobs import JobStore
from membrain.memory_map import memory_map
from membrain.structure_map import structure_map

pytestmark = pytest.mark.integration

CLAIM_SOURCE = "工作时我希望直接获得建议。"
CONTEXT = "这段上下文决定本次记忆的适用情境。"
OLD_PREFERENCE = "平时我希望直接获得建议。"
EXCEPTION = "2026年10月24日只需要先听我说，不要马上给建议。"


def sources(brain):
    """The restored source messages by their text."""
    return {row["document"]["observed"]["content"]["text"]: brain.event(row["id"])
            for row in brain.rows("memory_events", "AND is_current AND document IS NOT NULL")}


def semantic(brain):
    return [row["document"] for row in brain.rows("memory_assertions", "AND is_current AND document IS NOT NULL")
            if row["document"].get("verification")]


def filled(brain, *, jobs=True):
    """A brain restored from the ``views`` archive, with learning jobs, a reserved operation, a budget, and the
    feedback and access state of one claim."""
    result, archive = legacy_brain(brain)
    assert result["quarantined_event_count"] == 0
    texts = sources(brain)
    claims = semantic(brain)
    identifiers = legacy_jobs(brain, list(texts.values())) if jobs else {}
    claim = next(memory for memory in claims if memory["statement"] == "用户报告在工作时希望直接获得建议。"
                 and any(ref["event_id"] == texts[CLAIM_SOURCE]["event_id"] for ref in memory["evidence_refs"]))
    legacy_feedback(brain, claim, texts[CLAIM_SOURCE], texts[CONTEXT])
    return texts, claims, identifiers, archive


def counts(brain):
    tables = ("memory_episodes", "memory_episode_members", "memory_associations", "memory_belief_relations",
              "memory_cognitive_operations", "memory_cognitive_budgets", "memory_cognitive_budget_changes",
              "memory_feedback_contributions", "memory_access_state")
    return {table: len(brain.rows(table)) for table in tables}


def test_the_restored_brain_holds_every_kind_of_row_the_pipeline_wrote(brain):
    _, claims, identifiers, _ = filled(brain)
    assert len(claims) >= 4
    assert all(count >= 1 for count in counts(brain).values()), counts(brain)
    kinds = {(row["kind"], row["state"]) for row in brain.rows("memory_jobs", "AND id=ANY(%s)",
                                                                (list(identifiers.values()),))}
    assert kinds == {("consolidate", state) for state in ("queued", "failed", "running", "deferred", "completed")} | {
        ("orient", "queued"), ("orient", "completed")}


def recalled(brain, query="建议"):
    result = brain.action("recall", request(query))
    # Recall reports itself partial while restored messages wait to be captured, or when a relation an older
    # runtime stored no longer has all its endpoints; either way it answers.
    assert result["status"] in ("completed", "partial"), result["status"]
    return result["status"], [(item["memory"]["memory_id"], item["memory"]["revision"]) for item in result["items"]]


def test_recall_and_prepare_answer_on_a_brain_an_older_runtime_filled(brain):
    _, claims, _, _ = filled(brain)
    _, items = recalled(brain)
    assert {memory["memory_id"] for memory in claims} & {memory_id for memory_id, _ in items}
    brain.work()
    assert recalled(brain)[1]
    latest = brain.observe("还记得我希望怎样获得建议吗？")
    payload = prepare_payload()
    payload["latest_input_event_ids"] = [latest["event_id"]]
    packet = brain.action("prepare", payload)
    validate("ContextPacket", packet)
    assert cognition.render_context(packet)


def test_learning_jobs_are_never_claimed_and_do_not_count_as_pending(brain):
    _, _, identifiers, _ = filled(brain)

    def learning_rows():
        return {row["id"]: (row["state"], row["attempts"], row["fence"], row["lease_expires_at"])
                for row in brain.rows("memory_jobs", "AND id=ANY(%s)", (list(identifiers.values()),))}

    before = learning_rows()
    brain.work()
    assert learning_rows() == before
    assert JobStore(brain.database).claim(brain.principal, brain.brain_id, worker_id=uid()) is None
    for kinds in (["consolidate"], ["orient"], ["consolidate", "orient", "extract"]):
        assert JobStore(brain.database).claim(brain.principal, brain.brain_id, worker_id=uid(), kinds=kinds) is None
    assert learning_rows() == before
    status = brain.service.memory_status(brain.principal, brain.brain_id)
    assert (status["pending_jobs"], status["failed_jobs"], status["embedding_pending"]) == (0, 0, 0)
    dashboard = brain.service.dashboard(brain.principal, brain.brain_id)
    assert dashboard["status"]["pending_jobs"] == 0
    assert dashboard["status"]["extraction"] == "deterministic_source_capture"
    assert {job["id"] for job in dashboard["jobs"]} >= set(identifiers.values())
    listed = {job["id"]: job for job in JobStore(brain.database).list(brain.principal, brain.brain_id)}
    assert all(listed[job_id]["kind"] in ("consolidate", "orient") and "learning_summary" not in listed[job_id]
               for job_id in identifiers.values())
    assert brain.rows("memory_cognitive_operations")[0]["outcome"] == "reserved"


def test_the_memory_page_reads_the_old_derived_rows(brain):
    texts, _, _, _ = filled(brain)
    structure = structure_map(brain.service, brain.principal, brain.brain_id)
    kinds = {node["kind"] for node in structure["nodes"]}
    assert {"episode"} <= kinds, kinds
    assert any(edge for edge in structure["edges"])
    plain = memory_map(brain.service, brain.principal, brain.brain_id)
    assert {node["id"] for node in plain["nodes"]} >= {"msg:" + texts[CLAIM_SOURCE]["event_id"]}
    assert companion_map(brain.service, brain.principal, brain.brain_id)["nodes"] is not None
    assert brain.service.memory_status(brain.principal, brain.brain_id)["recorded_messages"] == len(texts)


def dependent(brain, event_id):
    """Every derived row that names this source, by table."""
    result = {}
    for table in ("memory_assertions", "memory_episodes", "memory_associations", "memory_belief_relations"):
        result[table] = [row for row in brain.rows(table) if event_id in row["event_ids"]]
    result["memory_jobs"] = [row for row in brain.rows("memory_jobs") if event_id in row["source_event_ids"]]
    result["memory_feedback_contributions"] = [row for row in brain.rows("memory_feedback_contributions")
                                               if event_id in row["source_event_ids"]]
    return result


def assert_cleared(brain, before, mode):
    for table, rows in before.items():
        current = {row["id"] if "id" in row else (row["memory_id"], row["feedback_event_id"]): row
                   for row in brain.rows(table)}
        for row in rows:
            key = row["id"] if "id" in row else (row["memory_id"], row["feedback_event_id"])
            now = current.get(key)
            if table == "memory_jobs":
                assert now["state"] == "superseded" and now["result"] is None and now["lease_token_digest"] is None
            elif table == "memory_feedback_contributions":
                assert now["invalidated_at"] is not None
            elif now is not None:
                assert now["invalidated"], (table, key)
                if table in ("memory_episodes", "memory_belief_relations"):
                    assert now["document"] is None, (table, key)
                if table == "memory_belief_relations":
                    assert now["deleted"] is (mode == "erase_content")
    contributing = {(row["memory_id"], row["memory_revision"]) for row in brain.rows(
        "memory_feedback_contributions", "AND invalidated_at IS NULL")}
    assert all((row["memory_id"], row["memory_revision"]) in contributing for row in brain.rows("memory_access_state"))


def archived_text(brain, archive_id):
    return json.dumps(brain.service.download_archive(brain.principal, archive_id)["document"], ensure_ascii=False)


@pytest.mark.parametrize("mode", ["suppress_recall", "erase_content"])
@pytest.mark.parametrize("text,tables", [
    (CLAIM_SOURCE, {"memory_assertions", "memory_episodes", "memory_associations", "memory_jobs",
                    "memory_feedback_contributions"}),
    (EXCEPTION, {"memory_assertions", "memory_belief_relations", "memory_jobs"}),
    (CONTEXT, {"memory_jobs", "memory_feedback_contributions"}),
])
def test_forgetting_a_source_clears_every_row_derived_from_it(brain, mode, text, tables):
    texts, _, _, _ = filled(brain)
    exported = brain.export()
    target = texts[text]
    before = dependent(brain, target["event_id"])
    assert {table for table, rows in before.items() if rows} >= tables
    brain.forget("events", [target["event_id"]], mode)
    assert_cleared(brain, before, mode)
    if mode == "erase_content":
        # Erasure also rewrites the archives already stored: nothing derived from the message stays in them.
        archived = json.loads(archived_text(brain, exported["archive_id"]))
        assert text not in json.dumps(archived, ensure_ascii=False)
        assert all(target["event_id"] not in [ref["event_id"] for ref in memory.get("evidence_refs", [])]
                   for memory in archived["memories"])
        assert all(target["event_id"] not in relation["root_event_ids"] for relation in archived["belief_relations"])
    recalled(brain)


def test_forgetting_a_claim_clears_its_relation_feedback_and_access_state(brain):
    texts, claims, _, _ = filled(brain)
    claim = next(memory for memory in claims if any(
        ref["event_id"] == texts[EXCEPTION]["event_id"] for ref in memory["evidence_refs"]))
    relations = [row for row in brain.rows("memory_belief_relations") if claim["memory_id"] in row["memory_ids"]]
    assert relations
    brain.forget("memories", [claim["memory_id"]])
    assert all(row["invalidated"] and row["document"] is None for row in brain.rows(
        "memory_belief_relations", "AND id=ANY(%s)", ([row["id"] for row in relations],)))


def test_retracting_a_claim_clears_its_relations_and_learning_jobs(brain):
    texts, claims, identifiers, _ = filled(brain)
    claim = next(memory for memory in claims if any(
        ref["event_id"] == texts[EXCEPTION]["event_id"] for ref in memory["evidence_refs"]))
    relations = [row["id"] for row in brain.rows("memory_belief_relations") if claim["memory_id"] in row["memory_ids"]]
    correction = brain.observe("那条例外记错了，请撤回。")
    generation = brain.service.dashboard(brain.principal, brain.brain_id)["brain"]["dependency_generation"]
    brain.action("correct", {"memory_id": claim["memory_id"], "expected_revision": claim["revision"],
                             "expected_dependency_generation": generation,
                             "correction_event_ids": [correction["event_id"]], "operation": "retract",
                             "idempotency_key": uid()})
    assert relations and all(row["invalidated"] and row["document"] is None for row in brain.rows(
        "memory_belief_relations", "AND id=ANY(%s)", (relations,)))
    jobs = brain.rows("memory_jobs", "AND id=ANY(%s)", (list(identifiers.values()),))
    assert all(row["state"] == "superseded" and row["result"] is None for row in jobs
               if texts[EXCEPTION]["event_id"] in row["source_event_ids"])


def plain_rows(brain, source, memory):
    """Derived rows over an ordinary captured message, written with plain SQL as an older runtime wrote them."""
    params = brain.service._params(brain.principal, brain.brain_id)
    version = {"memory_id": memory["memory_id"], "revision": memory["revision"]}
    with brain.database.transaction(brain.principal) as conn:
        conn.execute(
            "INSERT INTO memory_episodes(tenant_id,owner_id,brain_id,id,revision,conversation_id,branch_id,state,"
            "document,event_ids) VALUES(%s,%s,%s,%s,1,'test','main','open',%s,%s)",
            (*params, "episode-" + uid(), Jsonb({"organization_statement": source["observed"]["content"]["text"]}),
             [source["event_id"]]))
        conn.execute(
            "INSERT INTO memory_associations(tenant_id,owner_id,brain_id,id,source_id,source_revision,target_id,"
            "target_revision,relation,event_ids) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'context',%s)",
            (*params, "association-" + uid(), memory["memory_id"], memory["revision"], memory["memory_id"],
             memory["revision"], [source["event_id"]]))
        conn.execute(
            "INSERT INTO memory_belief_relations(tenant_id,owner_id,brain_id,id,revision,document,event_ids,memory_ids,"
            "endpoint_versions,endpoint_keys) VALUES(%s,%s,%s,%s,1,%s,%s,%s,%s,%s)",
            (*params, "belief-" + uid(), Jsonb({"statement": source["observed"]["content"]["text"]}),
             [source["event_id"]], [memory["memory_id"]], Jsonb([version]),
             [f"{memory['memory_id']}:{memory['revision']}"]))
    legacy_feedback(brain, memory, source, source)
    return legacy_jobs(brain, [source])


def test_editing_a_message_clears_what_an_older_runtime_derived_from_it(brain):
    source = brain.observe("工作时我希望直接获得建议。", key="edited-source")
    brain.work()
    memory = next(row["document"] for row in brain.rows("memory_assertions", "AND is_current")
                  if source["event_id"] in row["event_ids"])
    plain_rows(brain, source, memory)
    before = dependent(brain, source["event_id"])
    assert all(before[table] for table in ("memory_assertions", "memory_episodes", "memory_associations",
                                           "memory_belief_relations", "memory_jobs", "memory_feedback_contributions"))
    brain.observe("工作时我希望先被倾听。", key="edited-source", revision=2)
    assert_cleared(brain, before, "suppress_recall")
    assert not brain.rows("memory_access_state")
    brain.work()
    assert recalled(brain, "倾听")[1]


@pytest.mark.parametrize("upload", [False, True])
def test_an_export_of_an_old_brain_restores_and_is_then_erasable(brain, upload):
    texts, _, _, _ = filled(brain)
    exported = brain.export()
    data = exported["document"]
    assert data["cognitive_views"]["episodes"] and data["belief_relations"]
    result = brain.restore(exported, upload=upload)
    assert result["read_enabled"] is True
    restored = sources(brain)
    assert set(restored) == set(texts)
    if upload:
        # An uploaded archive cannot assert local verification: interpretations are quarantined, sources restored.
        assert not semantic(brain) and not brain.rows("memory_episodes") and not brain.rows("memory_belief_relations")
    else:
        assert len(semantic(brain)) >= 4 and brain.rows("memory_episodes") and brain.rows("memory_belief_relations")
    for text in (CLAIM_SOURCE, EXCEPTION):
        target = restored[text]
        before = dependent(brain, target["event_id"])
        brain.forget("events", [target["event_id"]])
        assert_cleared(brain, before, "erase_content")
    assert not [row for row in brain.rows("memory_belief_relations") if row["document"] is not None]
    recalled(brain)


@pytest.mark.parametrize("name", ["views", "views_revised", "episode_transition", "noncurrent_parent"])
def test_every_fixture_archive_restores_locally_and_by_upload(brain, name):
    document = fixture(name)
    result, _ = legacy_brain(brain, name)
    assert result["read_enabled"] is True and result["quarantined_event_count"] == 0
    assert len(brain.rows("memory_events")) == len(document["events"])
    if document["cognitive_views"]["episodes"]:
        assert brain.rows("memory_episodes")
    result, _ = legacy_brain(brain, name, upload=True)
    assert result["read_enabled"] is True
    assert not brain.rows("memory_episodes")


def test_rows_an_older_runtime_left_keep_principal_isolation(brain):
    filled(brain)
    tables = ("memory_assertions", "memory_episodes", "memory_episode_members", "memory_associations",
              "memory_belief_relations", "memory_jobs", "memory_cognitive_operations", "memory_cognitive_budgets",
              "memory_cognitive_budget_changes", "memory_feedback_contributions", "memory_access_state",
              "memory_archives")
    stranger = Principal(uid(), uid())
    with brain.database.transaction(stranger) as conn:
        for table in tables:
            assert conn.execute(f"SELECT count(*) AS value FROM {table} WHERE brain_id=%s",
                                (brain.brain_id,)).fetchone()["value"] == 0, table
    other = Brain(brain.database)
    assert other.service.memory_status(other.principal, other.brain_id)["pending_jobs"] == 0
