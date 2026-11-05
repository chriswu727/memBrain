import copy
import time

import pytest
from test_recall_executor import canonical
from test_response_validation import recall_request
from test_turns import turns as turns
from test_vector_jobs import drain, provider

from membrain.config import Settings
from membrain.deletion_registry import DeletionRegistry
from membrain.helpers import Principal, now, uid
from membrain.recall_service_executor import RecallServiceExecutor
from membrain.recovery_authority import RecoveryAuthority

pytestmark = pytest.mark.integration


@pytest.fixture
def executor(turns):
    runner = RecallServiceExecutor(2, Settings(database_url=turns.database.dsn))
    runner.start()
    processes = list(runner._pool._processes.values())
    try:
        yield runner
    finally:
        runner.close()
    assert all(not process.is_alive() for process in processes)


def prepare(turns):
    source = turns.observe("The library appointment is beside the blue fountain.")
    drain(turns)
    return source


def receipts(turns, request):
    with turns.database.transaction(turns.principal) as conn:
        return conn.execute("SELECT request_hash,response FROM memory_requests WHERE brain_id=%s AND key=%s",
                            (turns.brain, request["request_id"])).fetchall()


def test_worker_preserves_result_receipt_and_idempotency(turns, executor):
    prepare(turns)
    stamp = now()
    turns.service.access_time_provider = lambda: stamp
    request = recall_request(turns.brain)
    original = copy.deepcopy(request)
    baseline = turns.service.handle(turns.principal, {**request, "request_id": uid()})
    turns.service.request_runner = executor.respond
    response = turns.service.handle(turns.principal, request)
    assert response["outcome"] == "completed" and response["result"]["items"]
    assert canonical(response["result"]) == canonical(baseline["result"])
    assert request == original
    stored = receipts(turns, request)
    assert len(stored) == 1 and stored[0]["response"] == response
    assert turns.service.handle(turns.principal, request) == response
    conflict = turns.service.handle(turns.principal, {**request, "payload": {**request["payload"], "query": "changed"}})
    assert conflict["error"]["code"] == "idempotency_conflict"
    assert receipts(turns, request) == stored


def test_worker_owner_isolation_and_deletion_invalidate_cached_reply(turns, executor):
    source = prepare(turns)
    turns.service.request_runner = executor.respond
    request = recall_request(turns.brain)
    first = turns.service.handle(turns.principal, request)
    for outsider in (Principal(turns.principal.tenant_id, uid()), Principal(uid(), turns.principal.principal_id)):
        rejected = turns.service.handle(outsider, request)
        assert rejected["error"]["code"] == "not_found_or_forbidden"
        assert "blue fountain" not in str(rejected)
    turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [source["event_id"]]},
                            "mode": "erase_content", "expected_scope_generation": first["server_scope"]["scope_generation"]})
    invalidated = turns.service.handle(turns.principal, request)
    assert invalidated["error"]["code"] == "version_conflict"
    fresh = turns.service.handle(turns.principal, {**request, "request_id": uid()})
    assert fresh["outcome"] == "completed" and not fresh["result"]["items"]


def test_worker_timeout_rolls_back_before_same_request_can_retry(turns, executor):
    prepare(turns)
    turns.service.request_runner = executor.respond
    request = recall_request(turns.brain)
    request["payload"]["budget"]["max_wall_time_ms"] = 200
    with turns.database.transaction(turns.principal) as conn:
        conn.execute("SELECT id FROM memory_brains WHERE id=%s FOR UPDATE", (turns.brain,)).fetchone()
        rejected = turns.service.handle(turns.principal, request)
        assert rejected["error"]["code"] == "budget_exceeded"
    until = time.monotonic()+5
    while executor._slots._value != executor.workers*4 and time.monotonic() < until:
        time.sleep(.01)
    assert executor._slots._value == executor.workers*4
    assert receipts(turns, request) == []
    repeated = turns.service.handle(turns.principal, request)
    assert repeated["outcome"] == "completed", repeated
    assert len(receipts(turns, request)) == 1


def test_model_is_called_once_in_parent_and_worker_preserves_vector_space(turns, executor):
    calls = []
    with provider(turns, calls) as vectors:
        turns.service.embedding_provider = vectors
        prepare(turns)
        assert len(calls) == 1
        turns.service.request_runner = executor.respond
        request = recall_request(turns.brain)
        request["payload"]["budget"].update(max_embedding_calls=1, max_cost_microunits=1000)
        response = turns.service.handle(turns.principal, request)
        assert response["outcome"] == "completed", response
        assert len(calls) == 2
        assert response["result"]["usage"]["embedding_calls"] == 1
        assert any(signal["method"] == "vector" for item in response["result"]["items"] for signal in item["rank_signals"])
        assert turns.service.handle(turns.principal, request) == response
        assert len(calls) == 2
        with turns.database.transaction(turns.principal) as conn:
            row = conn.execute("SELECT result FROM memory_jobs WHERE brain_id=%s AND kind='query_embedding'",
                               (turns.brain,)).fetchone()
            assert row["result"] is None


def test_crashed_transaction_worker_is_not_replayed_and_next_request_recovers(turns, executor):
    prepare(turns)
    turns.service.request_runner = executor.respond
    process = next(iter(executor._pool._processes.values()))
    process.terminate()
    process.join(timeout=5)
    request = recall_request(turns.brain)
    failed = turns.service.handle(turns.principal, request)
    assert failed["error"]["code"] == "dependency_unavailable"
    assert receipts(turns, request) == []
    recovered = turns.service.handle(turns.principal, request)
    assert recovered["outcome"] == "completed", recovered
    assert recovered["result"]["items"] and len(receipts(turns, request)) == 1


def delayed_receipt(principal, request):
    import psycopg

    from membrain.recall_service_executor import _respond

    original = psycopg.Connection.execute
    inserted = []
    def execute(conn, query, *args, **kwargs):
        result = original(conn, query, *args, **kwargs)
        if isinstance(query, str) and query.startswith("INSERT INTO memory_requests"):
            inserted.append(True)
            time.sleep(1.1)
        return result
    psycopg.Connection.execute = execute
    started = time.monotonic()
    try:
        result = _respond(principal, request, (None, None, 0), None, started, started+1, None)
        return result, inserted
    finally:
        psycopg.Connection.execute = original


def test_deadline_after_receipt_write_rolls_back_receipt_and_traces(turns, executor):
    prepare(turns)
    request = recall_request(turns.brain)
    def trace_count():
        with turns.database.transaction(turns.principal) as conn:
            return conn.execute("SELECT count(*) AS n FROM memory_traces WHERE brain_id=%s",
                                (turns.brain,)).fetchone()["n"]
    before = trace_count()
    result, inserted = executor._executor().submit(delayed_receipt, turns.principal, request).result(timeout=10)
    assert inserted == [True]
    assert result["response"][0]["error"]["code"] == "budget_exceeded"
    assert receipts(turns, request) == [] and trace_count() == before


def test_registered_recovery_owner_is_retained_without_credentials(turns, tmp_path):
    prepare(turns)
    installation = uid()
    registry = DeletionRegistry.create(tmp_path / "registry", installation)
    authority = RecoveryAuthority(registry, installation)
    authority.initialize(turns.database, turns.principal)
    turns.database.recovery_authority = authority
    settings = Settings(database_url=turns.database.dsn, api_keys={"private-auth-hash": turns.principal},
                        recovery_registry_path=registry.directory, recovery_registry_id=registry.registry_id,
                        recovery_installation_id=installation)
    runner = RecallServiceExecutor(2, settings)
    try:
        assert not runner._settings.api_keys
        assert runner._principals == (turns.principal,)
        runner.start()
        turns.service.request_runner = runner.respond
        response = turns.service.handle(turns.principal, recall_request(turns.brain))
        assert response["outcome"] == "completed" and response["result"]["items"], response
    finally:
        runner.close()
