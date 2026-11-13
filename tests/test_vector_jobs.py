import copy
import json

import pytest
from test_turns import turns as turns

from membrain.client import default_budget, default_read_fence
from membrain.embeddings import EmbeddingResult, EmbeddingSpace
from membrain.helpers import DomainError, digest, uid

pytestmark = pytest.mark.integration


class provider:  # noqa: N801 - used like the provider factory it replaces
    """An in-process stand-in for the local model. Each call proves the brain row is not locked while it embeds."""

    space = EmbeddingSpace("fake-vector", "unit-v1", 3)

    def __init__(self, turns, calls, mutate=None):
        self.turns, self.calls, self.mutate = turns, calls, mutate

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def __call__(self, request):
        self.calls.append(list(request.texts))
        with self.turns.database.transaction(self.turns.principal) as conn:
            conn.execute("SET LOCAL lock_timeout='200ms'")
            conn.execute("SELECT id FROM memory_brains WHERE id=%s FOR UPDATE", (self.turns.brain,)).fetchone()
        if self.mutate:
            self.mutate()
        return EmbeddingResult(self.space, tuple((1.0, 0.0, 0.0) for _ in request.texts), None,
                               digest(list(request.texts)), 0)


def recall_request(turns, text="meeting spot", embedding_calls=1):
    return {"contract_version": "1.0.0-draft", "message_type": "request", "request_id": uid(),
            "action": "recall", "target": {"brain_ref": turns.brain, "conversation_ref": turns.conversation,
            "branch_ref": turns.branch}, "payload": {"query": text, "intent": "explore", "cue_event_ids": [],
            "additional_cues": [], "read_fence": default_read_fence(),
            "budget": {**default_budget(16000), "max_embedding_calls": embedding_calls, "max_cost_microunits": 1000}}}


def drain(turns):
    for _ in range(20):
        if not turns.service.work_once(turns.principal, turns.brain):
            return
    pytest.fail("Unexpected endless jobs")


def test_embedding_jobs_and_paraphrase_recall_execute_outside_database_lock(turns):
    calls = []
    with provider(turns, calls) as vectors:
        turns.service.embedding_provider = vectors
        turns.observe("The rendezvous is beneath the crimson canopy.")
        drain(turns)
        assert len(calls) == 1
        result = turns.service.handle(turns.principal, recall_request(turns))
        assert result["outcome"] == "completed", result
        assert any("crimson canopy" in item["memory"]["statement"] for item in result["result"]["items"])
        assert any(signal["method"] == "vector" for item in result["result"]["items"] for signal in item["rank_signals"])
        assert result["result"]["usage"]["embedding_calls"] == 1
        assert result["result"]["usage"]["actual_cost_microunits"] is None
        assert len(calls) == 2
    with turns.database.transaction(turns.principal) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_embeddings WHERE brain_id=%s", (turns.brain,)).fetchone()["n"] == 1
        # The query vector is computed in process and kept nowhere: no query job is written for it.
        assert conn.execute("SELECT 1 FROM memory_jobs WHERE brain_id=%s AND kind='query_embedding'", (turns.brain,)).fetchone() is None


def test_query_idempotency_and_zero_embedding_budget(turns):
    calls = []
    with provider(turns, calls) as vectors:
        turns.service.embedding_provider = vectors
        turns.observe("My favourite tree is a willow.")
        drain(turns)
        count = len(calls)
        zero = turns.service.handle(turns.principal, recall_request(turns, "willow", 0))
        assert zero["outcome"] == "completed" and len(calls) == count
        request = recall_request(turns)
        first = turns.service.handle(turns.principal, request)
        repeated = turns.service.handle(turns.principal, request)
        assert first == repeated and len(calls) == count + 1
        changed = copy.deepcopy(request)
        changed["payload"]["query"] = "another question"
        assert turns.service.handle(turns.principal, changed)["error"]["code"] == "idempotency_conflict"
        assert len(calls) == count + 1


def test_embedding_response_cannot_republish_a_deleted_source(turns):
    calls = []
    ref = turns.observe("Private forgotten phrase")
    with provider(turns, calls) as vectors:
        turns.service.embedding_provider = vectors
        assert turns.service.work_once(turns.principal, turns.brain) == 1
    def erase():
        turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [ref["event_id"]]},
                                "mode": "erase_content", "expected_scope_generation": 1})
    with provider(turns, calls, erase) as vectors:
        turns.service.embedding_provider = vectors
        with pytest.raises(DomainError):
            turns.service.work_once(turns.principal, turns.brain)
    with turns.database.transaction(turns.principal) as conn:
        assert not conn.execute("SELECT 1 FROM memory_embeddings WHERE brain_id=%s", (turns.brain,)).fetchone()
        source = conn.execute("SELECT deleted,document FROM memory_events WHERE brain_id=%s AND id=%s",
                              (turns.brain, ref["event_id"])).fetchone()
        assert source["deleted"] and source["document"] is None


def test_a_failing_local_model_is_reported_without_its_error_and_nothing_is_charged(turns):
    class Failing:
        space = EmbeddingSpace("fake-vector", "v1", 3)
        calls = 0

        def __call__(self, request):
            Failing.calls += 1
            raise RuntimeError("private model message")

    turns.service.embedding_provider = Failing()
    request = recall_request(turns)
    first = turns.service.handle(turns.principal, request)
    repeated = turns.service.handle(turns.principal, request)
    assert first["outcome"] in {"failed", "rejected"} and repeated["outcome"] in {"failed", "rejected"}
    assert first["error"]["code"] == "dependency_unavailable" and first["error"]["retryable"] is True
    assert "private model" not in str(first) + str(repeated)
    assert Failing.calls == 2  # Nothing was reserved, so a retry asks the model again.
    with turns.database.transaction(turns.principal) as conn:
        assert conn.execute("SELECT 1 FROM memory_jobs WHERE brain_id=%s AND kind='query_embedding'",
                            (turns.brain,)).fetchone() is None


def test_memories_written_before_a_provider_are_backfilled_once(turns):
    from membrain import vector_jobs

    turns.observe("The spare key is under the blue flowerpot.")
    turns.observe("My dentist appointment moved to Thursday.")
    drain(turns)
    calls, now = [], [1000.0]
    with provider(turns, calls) as vectors:
        turns.service.embedding_provider = vectors
        assert vector_jobs.backfill_embeddings(turns.service, turns.principal, turns.brain, clock=lambda: now[0]) >= 2
        drain(turns)
        with turns.database.transaction(turns.principal) as conn:
            embedded = conn.execute("SELECT count(*) AS n FROM memory_embeddings WHERE brain_id=%s",
                                    (turns.brain,)).fetchone()["n"]
            current = conn.execute("SELECT count(*) AS n FROM memory_assertions WHERE brain_id=%s AND is_current "
                                   "AND NOT deleted AND NOT suppressed AND NOT invalidated AND document IS NOT NULL",
                                   (turns.brain,)).fetchone()["n"]
        assert embedded == current >= 2
        count = len(calls)
        assert vector_jobs.backfill_embeddings(turns.service, turns.principal, turns.brain, clock=lambda: now[0]) == 0
        now[0] += vector_jobs.BACKFILL_RESCAN_SECONDS + 1
        assert vector_jobs.backfill_embeddings(turns.service, turns.principal, turns.brain, clock=lambda: now[0]) == 0
        assert len(calls) == count
        result = turns.service.handle(turns.principal, recall_request(turns, "where is the house key hidden"))
        assert any("flowerpot" in item["memory"]["statement"] for item in result["result"]["items"])


def test_local_models_do_not_consume_the_background_budget(turns):
    from membrain.embeddings import EmbeddingResult, EmbeddingSpace

    class Local:
        space = EmbeddingSpace("local-test", "v1", 3)

        def __init__(self):
            self.calls = 0

        def request_metadata(self, request):
            raise AssertionError("local models are not reserved")

        def __call__(self, request):
            self.calls += 1
            return EmbeddingResult(self.space, tuple((1.0, 0.0, 0.0) for _ in request.texts), None, "local", 0)

    local = Local()
    turns.service.embedding_provider = local
    for index in range(3):
        turns.observe(f"Local memory number {index} about the canal boat.")
    drain(turns)
    result = turns.service.handle(turns.principal, recall_request(turns, "canal boat"))
    assert result["outcome"] == "completed" and local.calls == 2
    with turns.database.transaction(turns.principal) as conn:
        assert conn.execute("SELECT coalesce(sum(model_calls),0) AS n FROM memory_jobs WHERE brain_id=%s "
                            "AND kind IN ('embed','query_embedding')", (turns.brain,)).fetchone()["n"] == 0


def test_other_script_neighbours_are_interleaved_without_duplicates():
    from membrain.candidates import _interleave

    def row(name):
        return {"document": {"memory_id": name, "revision": 1}}

    primary = [row(f"en{index}") for index in range(7)]
    merged = _interleave(primary, [row("zh0"), row("en1"), row("zh1"), row("zh2"), row("zh3")])
    assert [item["document"]["memory_id"] for item in merged] == [
        "en0", "en1", "en2", "zh0", "en3", "en4", "en5", "zh1", "en6", "zh2", "zh3"]


def test_local_indexing_batches_inference_without_consuming_paid_budgets(turns):
    from membrain.embeddings import EmbeddingResult, EmbeddingSpace
    from membrain.helpers import digest

    class Local:
        space = EmbeddingSpace("local-batch-test", "v1", 3)

        def __init__(self):
            self.calls = []

        def __call__(self, request):
            self.calls.append(request.texts)
            with turns.database.transaction(turns.principal) as conn:
                conn.execute("SET LOCAL lock_timeout='200ms'")
                conn.execute("SELECT id FROM memory_brains WHERE id=%s FOR UPDATE", (turns.brain,))
            return EmbeddingResult(self.space, tuple((1.0, 0.0, 0.0) for _ in request.texts), {},
                                   digest(request.texts), sum(len(text.encode()) for text in request.texts))

    vectors = Local()
    turns.service.embedding_provider = vectors
    for text in ("The appointment is on Monday.", "The meeting is at the blue cafe.", "My sister lives in Lisbon."):
        turns.observe(text)
    drain(turns)
    assert any(len(batch) > 1 for batch in vectors.calls)
    with turns.database.transaction(turns.principal) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_embeddings WHERE brain_id=%s", (turns.brain,)).fetchone()["n"] >= 3
        assert conn.execute("SELECT sum(model_calls) AS n FROM memory_jobs WHERE brain_id=%s AND kind='embed'",
                            (turns.brain,)).fetchone()["n"] == 0


def test_erasure_during_a_local_batch_does_not_publish_erased_content_or_cancel_other_sources(turns):
    from membrain.embeddings import EmbeddingResult, EmbeddingSpace

    first = turns.observe("A private appointment is on Monday.")
    turns.observe("The meeting is at the blue cafe.")
    drain(turns)

    class Local:
        space = EmbeddingSpace("local-erasure-batch", "v1", 3)

        def __call__(self, request):
            turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [first["event_id"]]},
                                    "mode": "erase_content", "expected_scope_generation": 1})
            return EmbeddingResult(self.space, tuple((1.0, 0.0, 0.0) for _ in request.texts), None, "local", 0)

    turns.service.embedding_provider = Local()
    with pytest.raises(DomainError):
        turns.service.work_once(turns.principal, turns.brain)
    with turns.database.transaction(turns.principal) as conn:
        rows = conn.execute("SELECT a.document FROM memory_embeddings v JOIN memory_assertions a ON "
                            "a.tenant_id=v.tenant_id AND a.owner_id=v.owner_id AND a.brain_id=v.brain_id "
                            "AND a.id=v.memory_id AND a.revision=v.memory_revision WHERE v.brain_id=%s",
                            (turns.brain,)).fetchall()
        assert rows and all("private appointment" not in row["document"]["statement"] for row in rows)


def test_vectors_an_older_runtime_stored_from_a_metered_provider_leave_no_brain_without_local_vectors(turns):
    """Vectors a metered provider stored (another model, version and size) are never compared with the local model's:
    recall reads only the configured space, the backfill embeds every current memory with the local model, and the
    old vectors and passages stay until their memory is edited or forgotten, which deletes them with the new ones."""
    from membrain import vector_jobs

    turns.observe("The spare key is under the blue flowerpot.")
    forgotten = turns.observe("My dentist appointment moved to Thursday.")
    drain(turns)  # Captured with no model, as before a provider was configured.
    params = turns.service._params(turns.principal, turns.brain)
    with turns.database.transaction(turns.principal) as conn:
        rows = conn.execute("SELECT id,revision,document FROM memory_assertions WHERE brain_id=%s AND is_current "
                            "AND NOT deleted AND NOT suppressed AND NOT invalidated AND document IS NOT NULL",
                            (turns.brain,)).fetchall()
        for row in rows:  # Written as an older runtime with a metered provider wrote them.
            conn.execute(
                "INSERT INTO memory_embeddings(tenant_id,owner_id,brain_id,memory_id,memory_revision,model,"
                "model_version,dimensions,content_hash,embedding) VALUES(%s,%s,%s,%s,%s,'old-remote-model',"
                "'release-1',4,%s,%s::vector)",
                (*params, row["id"], row["revision"], digest(row["document"]["statement"]), json.dumps([0, 0, 0, 1])))
            conn.execute(
                "INSERT INTO memory_embedding_passages(tenant_id,owner_id,brain_id,memory_id,memory_revision,model,"
                "model_version,passage_index,start_offset,end_offset,embedding) VALUES(%s,%s,%s,%s,%s,"
                "'old-remote-model','release-1',0,0,%s,%s::vector)",
                (*params, row["id"], row["revision"], len(row["document"]["statement"]), json.dumps([0, 0, 0, 1])))
        conn.execute(
            "INSERT INTO memory_jobs(tenant_id,owner_id,brain_id,id,kind,payload,state,source_event_ids) "
            "VALUES(%s,%s,%s,'query:legacy','query_embedding','{}'::jsonb,'queued',%s)",
            (*params, [forgotten["event_id"]]))
        conn.execute("UPDATE memory_jobs SET result=%s::jsonb WHERE brain_id=%s AND id='query:legacy'",
                     (json.dumps({"vector": [0, 0, 0, 1], "snapshot": {"source_snapshot": []}}), turns.brain))

    def count(conn, model):
        return conn.execute("SELECT count(*) AS n FROM memory_embeddings WHERE brain_id=%s AND model=%s",
                            (turns.brain, model)).fetchone()["n"]

    calls = []
    with provider(turns, calls) as vectors:
        turns.service.embedding_provider = vectors
        assert vector_jobs.backfill_embeddings(turns.service, turns.principal, turns.brain) == len(rows) >= 2
        drain(turns)
        with turns.database.transaction(turns.principal) as conn:
            assert count(conn, "fake-vector") == count(conn, "old-remote-model") == len(rows)
        result = turns.service.handle(turns.principal, recall_request(turns, "where is the house key hidden"))
        assert result["outcome"] == "completed", result
        assert any(signal["method"] == "vector" for item in result["result"]["items"] for signal in item["rank_signals"])
        assert any("flowerpot" in item["memory"]["statement"] for item in result["result"]["items"])
    turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [forgotten["event_id"]]},
                            "mode": "erase_content", "expected_scope_generation": 1})
    with turns.database.transaction(turns.principal) as conn:
        left = conn.execute(
            "SELECT v.model,a.document FROM memory_embeddings v JOIN memory_assertions a ON a.tenant_id=v.tenant_id "
            "AND a.brain_id=v.brain_id AND a.id=v.memory_id AND a.revision=v.memory_revision WHERE v.brain_id=%s",
            (turns.brain,)).fetchall()
        assert left and all("dentist" not in (row["document"] or {}).get("statement", "") for row in left)
        assert {row["model"] for row in left} == {"fake-vector", "old-remote-model"}
        assert conn.execute("SELECT count(*) AS n FROM memory_embedding_passages WHERE brain_id=%s",
                            (turns.brain,)).fetchone()["n"] == len(left) // 2
        assert conn.execute("SELECT result FROM memory_jobs WHERE brain_id=%s AND id='query:legacy'",
                            (turns.brain,)).fetchone()["result"] is None
