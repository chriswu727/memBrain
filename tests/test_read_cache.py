import copy
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_response_validation import recall_request
from test_turns import turns as turns
from test_vector_jobs import drain

from membrain import read_cache
from membrain.helpers import Principal, uid

pytestmark = pytest.mark.integration


def seed(turns):
    turns.observe("The library appointment is beside the blue fountain.")
    drain(turns)


def cached(turns):
    with turns.database.transaction(turns.principal) as conn:
        return conn.execute("SELECT * FROM memory_read_cache WHERE brain_id=%s ORDER BY created_at,key",
                            (turns.brain,)).fetchall()


@pytest.mark.parametrize("workers", [1, 8])
def test_count_bound_retains_fingerprints_and_exact_recent_replays(turns, monkeypatch, workers):
    seed(turns)
    requests = [recall_request(turns.brain) for _ in range(read_cache.MAX_RESPONSES + 16)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = list(pool.map(lambda request: turns.service.handle(turns.principal, request), requests))
    assert all(response["outcome"] == "completed" for response in responses)
    rows = cached(turns)
    assert len(rows) == read_cache.MAX_RESPONSES
    assert sum(row["response_bytes"] for row in rows) <= read_cache.MAX_RESPONSE_BYTES
    with turns.database.transaction(turns.principal) as conn:
        receipts = conn.execute("SELECT key,response FROM memory_requests WHERE brain_id=%s AND action='recall'",
                                (turns.brain,)).fetchall()
    assert len(receipts) == len(requests) and all(row["response"] is None for row in receipts)
    monkeypatch.setattr(turns.service, "_recall", lambda *args, **kwargs: pytest.fail("Replay executed recall again"))
    kept = {row["key"] for row in rows}
    for request, response in zip(requests, responses, strict=True):
        replay = turns.service.handle(turns.principal, request)
        if request["request_id"] in kept:
            assert replay == response
        else:
            assert replay["error"]["code"] == "version_conflict"
        changed = copy.deepcopy(request)
        changed["payload"]["query"] = "different"
        assert turns.service.handle(turns.principal, changed)["error"]["code"] == "idempotency_conflict"


def test_age_expiry_is_enforced_before_background_cleanup(turns):
    seed(turns)
    request = recall_request(turns.brain)
    assert turns.service.handle(turns.principal, request)["outcome"] == "completed"
    with turns.database.transaction(turns.principal) as conn:
        conn.execute("UPDATE memory_read_cache SET created_at=clock_timestamp()-interval '25 hours' WHERE brain_id=%s",
                     (turns.brain,))
    assert turns.service.handle(turns.principal, request)["error"]["code"] == "version_conflict"
    assert len(cached(turns)) == 1
    assert turns.service.work_once(turns.principal, turns.brain) == 0
    assert cached(turns) == []


def test_byte_bound_and_oversized_response_keep_request_identity(turns, monkeypatch):
    seed(turns)
    first = recall_request(turns.brain)
    assert turns.service.handle(turns.principal, first)["outcome"] == "completed"
    size = cached(turns)[0]["response_bytes"]
    monkeypatch.setattr(read_cache, "MAX_RESPONSE_BYTES", size * 3)
    for _ in range(8):
        assert turns.service.handle(turns.principal, recall_request(turns.brain))["outcome"] == "completed"
    assert 1 <= len(cached(turns)) <= 3
    assert sum(row["response_bytes"] for row in cached(turns)) <= size * 3
    monkeypatch.setattr(read_cache, "MAX_RESPONSE_BYTES", 1)
    large = recall_request(turns.brain)
    assert turns.service.handle(turns.principal, large)["outcome"] == "completed"
    assert cached(turns) == []
    assert turns.service.handle(turns.principal, large)["error"]["code"] == "version_conflict"


def test_legacy_cleanup_is_batched_and_preserves_prepare_and_selected_traces(turns):
    seed(turns)
    request = recall_request(turns.brain)
    response = turns.service.handle(turns.principal, request)
    with turns.database.transaction(turns.principal) as conn:
        conn.execute("DELETE FROM memory_cache_maintenance WHERE brain_id=%s", (turns.brain,))
        for action in ("recall", "inspect", "prepare"):
            conn.execute("INSERT INTO memory_requests(tenant_id,owner_id,brain_id,action,key,request_hash,response) "
                         "SELECT %s,%s,%s,%s,'legacy-'||lpad(n::text,5,'0'),'fingerprint',%s "
                         "FROM generate_series(1,300) n",
                         (turns.principal.tenant_id, turns.principal.principal_id, turns.brain, action, Jsonb(response)))
        for kind in ("candidate_hit", "context_selected", "quoted", "user_confirmed"):
            conn.execute("INSERT INTO memory_traces(tenant_id,owner_id,brain_id,id,document) "
                         "SELECT %s,%s,%s,%s||lpad(n::text,5,'0'),%s FROM generate_series(1,300) n",
                         (turns.principal.tenant_id, turns.principal.principal_id, turns.brain, kind, Jsonb({"kind": kind})))
    def counts():
        with turns.database.transaction(turns.principal) as conn:
            requests = conn.execute("SELECT action,count(response) AS n FROM memory_requests WHERE brain_id=%s GROUP BY action",
                                    (turns.brain,)).fetchall()
            traces = conn.execute("SELECT document->>'kind' AS kind,count(*) AS n FROM memory_traces WHERE brain_id=%s GROUP BY 1",
                                  (turns.brain,)).fetchall()
            return {row["action"]: row["n"] for row in requests}, {row["kind"]: row["n"] for row in traces}
    before = counts()
    assert turns.service.work_once(turns.principal, turns.brain) == 0
    after = counts()
    assert 0 < before[0]["inspect"] - after[0]["inspect"] <= read_cache.MAINTENANCE_BATCH
    assert 0 < before[1]["candidate_hit"] - after[1]["candidate_hit"] <= read_cache.MAINTENANCE_BATCH
    for _ in range(5):
        assert turns.service.work_once(turns.principal, turns.brain) == 0
    requests, traces = counts()
    assert requests["recall"] == requests["inspect"] == 0 and requests["prepare"] == 300
    assert traces == {"context_selected": 300, "quoted": 300, "user_confirmed": 300}
    assert turns.service.handle(turns.principal, request) == response


def test_cache_rows_are_private_to_owner_and_tenant(turns):
    seed(turns)
    request = recall_request(turns.brain)
    assert turns.service.handle(turns.principal, request)["outcome"] == "completed"
    for outsider in (Principal(turns.principal.tenant_id, uid()), Principal(uid(), turns.principal.principal_id)):
        with turns.database.transaction(outsider) as conn:
            assert conn.execute("SELECT * FROM memory_read_cache WHERE brain_id=%s", (turns.brain,)).fetchall() == []
            assert conn.execute("SELECT * FROM memory_cache_maintenance WHERE brain_id=%s", (turns.brain,)).fetchall() == []
        assert turns.service.handle(outsider, request)["error"]["code"] == "not_found_or_forbidden"


def test_interrupted_maintenance_rolls_back_rows_and_cursor_together(turns, monkeypatch):
    seed(turns)
    request = recall_request(turns.brain)
    response = turns.service.handle(turns.principal, request)
    with turns.database.transaction(turns.principal) as conn:
        conn.execute("DELETE FROM memory_cache_maintenance WHERE brain_id=%s", (turns.brain,))
        conn.execute("UPDATE memory_requests SET response=%s WHERE brain_id=%s AND key=%s",
                     (Jsonb(response), turns.brain, request["request_id"]))
        conn.execute("INSERT INTO memory_traces(tenant_id,owner_id,brain_id,id,document) VALUES(%s,%s,%s,%s,%s)",
                     (turns.principal.tenant_id, turns.principal.principal_id, turns.brain, uid(), Jsonb({"kind": "candidate_hit"})))
    execute = psycopg.Connection.execute
    def interrupted(conn, query, *args, **kwargs):
        result = execute(conn, query, *args, **kwargs)
        if isinstance(query, str) and query.startswith("UPDATE memory_cache_maintenance"):
            raise RuntimeError("interrupted cleanup transaction")
        return result
    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "execute", interrupted)
        with pytest.raises(RuntimeError, match="interrupted cleanup transaction"):
            turns.service.work_once(turns.principal, turns.brain)
    with turns.database.transaction(turns.principal) as conn:
        assert conn.execute("SELECT response FROM memory_requests WHERE brain_id=%s AND key=%s",
                            (turns.brain, request["request_id"])).fetchone()["response"] == response
        assert conn.execute("SELECT count(*) AS n FROM memory_traces WHERE brain_id=%s", (turns.brain,)).fetchone()["n"] == 1
        assert conn.execute("SELECT * FROM memory_cache_maintenance WHERE brain_id=%s", (turns.brain,)).fetchall() == []
    assert turns.service.work_once(turns.principal, turns.brain) == 0
    with turns.database.transaction(turns.principal) as conn:
        assert conn.execute("SELECT response FROM memory_requests WHERE brain_id=%s AND key=%s",
                            (turns.brain, request["request_id"])).fetchone()["response"] is None
        assert conn.execute("SELECT * FROM memory_traces WHERE brain_id=%s", (turns.brain,)).fetchall() == []


def test_recall_and_inspect_share_one_bound_without_evicting_another_brain(turns, monkeypatch):
    seed(turns)
    monkeypatch.setattr(read_cache, "MAX_RESPONSES", 3)
    other = turns.service.create_brain(turns.principal, "Separate replay cache")["id"]
    other_request = recall_request(other)
    other_response = turns.service.handle(turns.principal, other_request)
    first = turns.service.handle(turns.principal, recall_request(turns.brain))
    memory_id = first["result"]["items"][0]["memory"]["memory_id"]
    for _ in range(6):
        request = recall_request(turns.brain)
        assert turns.service.handle(turns.principal, request)["outcome"] == "completed"
        inspect = {**request, "request_id": uid(), "action": "inspect", "payload": {
            "memory_ids": [memory_id], "evidence_refs": [], "include_successors": True,
            "include_corrections": True, "budget": request["payload"]["budget"],
        }}
        inspected = turns.service.handle(turns.principal, inspect)
        assert inspected["outcome"] == "completed", inspected
        assert turns.service.handle(turns.principal, inspect) == inspected
    assert len(cached(turns)) == 3
    assert {row["action"] for row in cached(turns)} == {"recall", "inspect"}
    assert turns.service.handle(turns.principal, other_request) == other_response
