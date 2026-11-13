"""Shared (read-only) brain accesses stay read-only with semantic processing and embeddings on (R5, gap 20).

Inside ``reading()`` the brain row is only shared, so a read path that created a job, advanced a generation or
appended an event would raise from ``_writable()``, and one that wrote anything else would do it beside other
readers. These tests drive every read path with the deterministic semantic processor of ``test_learning`` and a fake
embedding provider, record each statement executed while a read is in progress, and allow only the writes audited
as safe beside other readers.
"""
import hashlib
import re
import uuid

import psycopg
import pytest
from test_learning import delivered
from test_learning import learning as learning
from test_recovery_erasure import pending, raw_event
from test_recovery_erasure import recovery as recovery

import membrain.service as service_module
from membrain import cognition
from membrain.affect import affect_records
from membrain.client import default_budget, default_read_fence
from membrain.contracts import CONTRACT_VERSION
from membrain.embeddings import EmbeddingResult, EmbeddingSpace
from membrain.mood import mood_state
from membrain.persona import current_persona, persona_versions
from membrain.relationship import relationship
from membrain.runtime import BrainRuntime
from membrain.service import reading

pytestmark = pytest.mark.integration

WRITE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|COPY)\b|\bFOR\s+(NO\s+KEY\s+)?UPDATE\b",
                   re.IGNORECASE)
# Audited writes a shared read may make (see the brain-lock review): rows of other tables, each keyed so that no two
# concurrent readers can touch the same row without serialization: receipts use the request-key lock, bounded
# response-cache publication uses a per-brain cache lock, and query results use this request's own key.
ALLOWED = (
    re.compile(r"^INSERT INTO memory_requests\("),
    re.compile(r"^INSERT INTO memory_traces\("),
    re.compile(r"^INSERT INTO memory_read_cache\("),
    re.compile(r"^DELETE FROM memory_read_cache WHERE "),
    re.compile(r"^INSERT INTO memory_cache_maintenance\("),
    re.compile(r"^UPDATE memory_cache_maintenance SET request_action=%s,request_key=%s,trace_id=%s,"),
    re.compile(r"^UPDATE memory_requests SET response=NULL WHERE .* AND response IS NOT NULL AND \(action,key\) IN "),
    re.compile(r"^DELETE FROM memory_traces WHERE .* AND id=ANY\(%s::text\[\]\) AND document->>'kind'='candidate_hit'$"),
    re.compile(r"^UPDATE memory_assertions a SET source_han_majority=projection.majority FROM unnest\("),
)


def vector(text):
    digest = hashlib.sha256(text.lower().encode()).digest()
    return [1.0] + [byte / 255 for byte in digest[:7]]


class fake_embeddings:  # noqa: N801 - used like the provider factory it replaces
    """An in-process stand-in for the local embedding model that records each batch it embeds."""

    space = EmbeddingSpace("fake-vector", "unit-v1", 8)

    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def __call__(self, request):
        self.calls.append(list(request.texts))
        return EmbeddingResult(self.space, tuple(tuple(vector(text)) for text in request.texts), None, "fake", 0)


class Statements:
    """Every statement run while a read is marked in progress, and every write a read attempted through the guard."""

    def __init__(self, monkeypatch):
        self.reads, self.refused = [], []
        execute, writable = psycopg.Cursor.execute, service_module._writable

        def recorded(cursor, query, params=None, **kwargs):
            if service_module._READING.get():
                self.reads.append(query if isinstance(query, str) else query.as_string(cursor.connection))
            return execute(cursor, query, params, **kwargs)

        def guarded():
            try:
                writable()
            except RuntimeError as error:
                self.refused.append(error)
                raise

        monkeypatch.setattr(psycopg.Cursor, "execute", recorded)
        monkeypatch.setattr(service_module, "_writable", guarded)

    def writes(self):
        return [" ".join(text.split()) for text in self.reads if WRITE.search(text)]

    def unexpected(self):
        return [text for text in self.writes() if not any(pattern.search(text) for pattern in ALLOWED)]


def recall_request(harness, query, *, conversation="chat", request_id=None):
    return {"message_type": "request", "contract_version": CONTRACT_VERSION,
            "request_id": request_id or str(uuid.uuid4()), "action": "recall",
            "target": {"brain_ref": harness.brain, "conversation_ref": conversation, "branch_ref": "main"},
            "payload": {"query": query, "intent": "explore", "cue_event_ids": [], "additional_cues": [],
                        "read_fence": default_read_fence(),
                        "budget": {**default_budget(16000), "max_embedding_calls": 1, "max_cost_microunits": 1000,
                                   "max_wall_time_ms": 20000}}}


def drain(harness):
    for _ in range(40):
        try:
            if not harness.service.work_once(harness.principal, harness.brain):
                return
        except Exception:  # noqa: BLE001 - a semantic job the fake cannot satisfy fails and is retried later
            continue


@pytest.fixture
def semantic(recovery):
    harness, authority = recovery
    calls = []
    with fake_embeddings(calls) as provider:
        harness.service.embedding_provider = provider
        runtime = BrainRuntime(harness.memory, lambda request: "我们先安排今天的复习。", deliver=delivered)
        assert runtime.respond("现在我要制定复习计划。", message_id="first", conversation_id="chat").stage == "completed"
        harness.observe("The rendezvous is beneath the crimson canopy.")
        harness.observe("I prefer green tea in the afternoon.")
        drain(harness)
        with harness.database.transaction(harness.principal) as conn:
            embedded = conn.execute("SELECT count(*) AS n FROM memory_embeddings WHERE tenant_id=%s AND brain_id=%s",
                                    (harness.principal.tenant_id, harness.brain)).fetchone()["n"]
            oriented = conn.execute("SELECT count(*) AS n FROM memory_jobs WHERE tenant_id=%s AND brain_id=%s "
                                    "AND kind='orient' AND state='completed'",
                                    (harness.principal.tenant_id, harness.brain)).fetchone()["n"]
        assert embedded and oriented, "the semantic and embedding paths must have produced state for reads to use"
        yield harness, authority, calls


def test_semantic_recall_inspect_and_views_only_make_audited_writes(semantic, monkeypatch):
    harness, _, calls = semantic
    statements = Statements(monkeypatch)
    principal, brain = harness.principal, harness.brain
    before = len(calls)

    request = recall_request(harness, "where is the meeting spot")
    recalled = harness.service.handle(principal, request)
    assert recalled["outcome"] == "completed", recalled
    assert len(calls) == before + 1 and recalled["result"]["usage"]["embedding_calls"] == 1
    assert any(signal["method"] == "vector" for item in recalled["result"]["items"]
               for signal in item["rank_signals"]), "the recall must have used the embedding"
    assert harness.service.handle(principal, request) == recalled  # replay of the stored response
    plan = harness.service.handle(principal, recall_request(harness, "what is my current plan"))
    assert plan["outcome"] == "completed", plan

    items = recalled["result"]["items"] + plan["result"]["items"]
    memory_ids = sorted({item["memory"]["memory_id"] for item in items})
    evidence = [ref for item in items for ref in item["memory"]["evidence_refs"]][:4]
    assert memory_ids and evidence
    inspected = harness.memory.inspect(memory_ids, evidence_refs=[
        {key: ref[key] for key in ("event_id", "event_revision", "source_content_sha256", "relationship", "span")
         if key in ref} for ref in evidence])
    assert inspected["outcome"] == "completed" and inspected["result"]["memories"], inspected

    timeline = harness.service.timeline(principal, brain)
    event_ids = [item["event_id"] for item in timeline["items"]][:3]
    assert event_ids
    harness.service.following(principal, brain, event_ids)
    harness.service.memory_status(principal, brain)
    harness.service.dashboard(principal, brain)
    assert harness.memory.memory_map()["nodes"]
    for read in (affect_records, current_persona, persona_versions, relationship, mood_state):
        with reading():
            read(harness.service, principal, brain)
    harness.memory.affect_records()
    harness.memory.persona()
    harness.memory.persona_versions()
    harness.memory.relationship()
    harness.memory.mood()

    harness.observe("The museum opens at nine on Saturdays.")
    reads_before_worker = len(statements.reads)
    drain(harness)  # the index worker reads each new message under the shared lock
    assert len(statements.reads) > reads_before_worker

    assert statements.refused == []
    assert statements.unexpected() == []
    writes = statements.writes()
    assert any(text.startswith("INSERT INTO memory_requests(") for text in writes)
    assert not any("kind='query_embedding'" in text for text in writes)  # The local model writes no query job.


def test_a_semantic_recall_applies_a_pending_erasure_before_reading(semantic, monkeypatch):
    harness, authority, _ = semantic
    secret_text = "VAULT_ERASURE_SECRET_7721"
    stamp = "2026-11-04T17:29:20.177218Z"
    monkeypatch.setattr(cognition, "now", lambda: stamp)
    secret = harness.observe(f"The vault combination is {secret_text}.")["accepted_event_ids"][0]
    drain(harness)
    pending(harness, authority, secret)
    statements = Statements(monkeypatch)
    response = harness.service.handle(harness.principal, recall_request(harness, "vault combination"))
    assert response["outcome"] == "completed", response
    assert response["result"]["retrieval_snapshot"]["created_at"] == stamp
    assert secret_text not in str(response) and secret not in str(response)
    assert raw_event(harness, secret) == {"document": None, "deleted": True}
    assert statements.refused == []
    # The erasure itself runs as a write (outside the read marker); the read only took the row exclusively for it.
    assert [text for text in statements.unexpected()
            if not re.search(r"FROM memory_brains .* FOR UPDATE$", text)] == []
