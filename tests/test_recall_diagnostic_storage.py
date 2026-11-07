import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_response_validation import recall_request
from test_turns import turns as turns
from test_vector_jobs import drain

from membrain.helpers import uid

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("workers", [1, 4])
def test_repeated_recall_keeps_diagnostics_in_receipts_without_duplicate_trace_rows(turns, workers):
    turns.observe("The library appointment is beside the blue fountain.")
    drain(turns)
    requests = [recall_request(turns.brain) for _ in range(16)]
    with turns.database.transaction(turns.principal) as conn:
        memories = conn.execute("SELECT id,revision,document FROM memory_assertions WHERE brain_id=%s ORDER BY id",
                                (turns.brain,)).fetchall()
        traces_before = conn.execute("SELECT count(*) AS n FROM memory_traces WHERE brain_id=%s",
                                     (turns.brain,)).fetchone()["n"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = list(pool.map(lambda request: turns.service.handle(turns.principal, request), requests))
    trace_ids = set()
    for request, response in zip(requests, responses, strict=True):
        assert response["outcome"] == "completed", response
        assert response["result"]["items"]
        traces = response["result"]["recall_traces"]
        assert traces and all(trace["kind"] == "candidate_hit" for trace in traces)
        assert all(trace["allowed_effect"] == "none" for trace in traces)
        trace_ids.update(trace["trace_id"] for trace in traces)
        assert turns.service.handle(turns.principal, request) == response
        changed = copy.deepcopy(request)
        changed["payload"]["query"] = "different query"
        assert turns.service.handle(turns.principal, changed)["error"]["code"] == "idempotency_conflict"
    assert len(trace_ids) >= len(requests)
    with turns.database.transaction(turns.principal) as conn:
        stored = conn.execute("SELECT key,response FROM memory_requests WHERE brain_id=%s AND action='recall'",
                              (turns.brain,)).fetchall()
        assert {row["key"]: row["response"] for row in stored} == {
            request["request_id"]: response for request, response in zip(requests, responses, strict=True)}
        assert conn.execute("SELECT id,revision,document FROM memory_assertions WHERE brain_id=%s ORDER BY id",
                            (turns.brain,)).fetchall() == memories
        assert conn.execute("SELECT count(*) AS n FROM memory_access_state WHERE brain_id=%s",
                            (turns.brain,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM memory_traces WHERE brain_id=%s",
                            (turns.brain,)).fetchone()["n"] == traces_before


def test_source_erasure_invalidates_cached_candidate_diagnostics(turns):
    source = turns.observe("The library appointment is beside the blue fountain.")
    drain(turns)
    request = recall_request(turns.brain)
    response = turns.service.handle(turns.principal, request)
    assert response["outcome"] == "completed" and response["result"]["recall_traces"]
    turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [source["event_id"]]},
                            "mode": "erase_content", "expected_scope_generation": response["server_scope"]["scope_generation"]})
    assert turns.service.handle(turns.principal, request)["error"]["code"] == "version_conflict"
    fresh = turns.service.handle(turns.principal, {**request, "request_id": uid()})
    assert fresh["outcome"] == "completed"
    assert fresh["result"]["recall_traces"] == []
