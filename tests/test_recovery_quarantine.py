import copy
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from psycopg.types.json import Jsonb
from service_harness import harness as harness
from test_deletion_registry import acknowledgement

from membrain import cognition
from membrain.client import MemoryClient
from membrain.deletion_registry import DeletionRegistry, RegistryError
from membrain.helpers import DomainError, digest, uid
from membrain.jobs import JobStore
from membrain.recovery import activate_database, quarantine
from membrain.recovery_authority import RecoveryAuthority
from membrain.runtime import BrainRuntime, RuntimeBlocked
from membrain.turns import TurnStore

pytestmark = pytest.mark.integration


@pytest.fixture
def restored(harness, tmp_path):
    source_installation = uid()
    registry = DeletionRegistry.create(tmp_path / "authority", source_installation)
    RecoveryAuthority(registry, source_installation).initialize(harness.database, harness.principal)
    options = {
        "source_installation_id": source_installation, "installation_id": uid(), "registry_id": registry.registry_id,
        "recovery_epoch": uid(), "manifest_hash": digest("immutable backup manifest"),
        "checkpoint": {"backup_id": uid(), "checkpoint_at": "2026-10-25T00:00:00Z"},
    }
    return SimpleNamespace(harness=harness, registry=registry, options=options,
                           jobs=JobStore(harness.database))


def apply_quarantine(case, **changes):
    quarantine(case.harness.database, case.harness.principal, **{**case.options, **changes})


def test_quarantine_invalidates_valid_receipts_without_rewriting_invalid_ones(restored):
    harness = restored.harness
    harness.observe("The retained location is the library.", source_key="location")
    harness.observe("The corrected location is the cafe.", source_key="location", revision=2)

    def receipts():
        with harness.database.transaction(harness.principal) as conn:
            return {row["key"]: row for row in conn.execute(
                "SELECT brain_id,action,key,request_hash,response,xmin::text AS version FROM memory_requests "
                "WHERE tenant_id=%s AND owner_id=%s",
                (harness.principal.tenant_id, harness.principal.principal_id),
            )}

    before = receipts()
    invalid = {key: row for key, row in before.items() if row["response"] is None}
    assert invalid and any(row["response"] is not None for row in before.values())
    apply_quarantine(restored)
    after = receipts()
    assert set(after) == set(before)
    assert all(row["response"] is None for row in after.values())
    for key, row in invalid.items():
        assert after[key] == row
    apply_quarantine(restored)
    assert receipts() == after


def test_quarantine_removes_bounded_read_responses_and_cleanup_cursors(restored):
    from test_response_validation import recall_request

    harness = restored.harness
    harness.observe("The library appointment is beside the blue fountain.")
    harness.memory.work()
    request = recall_request(harness.brain)
    response = harness.service.handle(harness.principal, request)
    assert response["outcome"] == "completed"
    assert records(restored, "memory_read_cache")
    apply_quarantine(restored)
    assert records(restored, "memory_read_cache") == []
    assert records(restored, "memory_cache_maintenance") == []
    activate(restored)
    assert harness.service.handle(harness.principal, request)["error"]["code"] == "version_conflict"


def activate(case):
    harness = case.harness
    case.registry.activate(case.options["recovery_epoch"], case.options["installation_id"],
                           case.options["manifest_hash"], **acknowledgement(case.registry.head()))
    authority = RecoveryAuthority(case.registry, case.options["installation_id"], restoring=True)
    harness.database.recovery_authority = authority
    authority.reconcile(harness.database, harness.principal)
    activate_database(harness.database, harness.principal, authority,
                      recovery_epoch=case.options["recovery_epoch"], manifest_hash=case.options["manifest_hash"])
    harness.database.recovery_authority = RecoveryAuthority(case.registry, case.options["installation_id"])


def records(case, table):
    harness = case.harness
    with harness.database.transaction(harness.principal) as conn:
        return conn.execute(f"SELECT * FROM {table} WHERE tenant_id=%s AND owner_id=%s ORDER BY ctid",
                            (harness.principal.tenant_id, harness.principal.principal_id)).fetchall()


def turn_at(case, stage):
    harness = case.harness
    store = TurnStore(harness.database, service=harness.service)
    turn_id = "phase-" + stage
    row = store.begin(harness.principal, harness.brain, turn_id=turn_id, conversation_id=stage,
                       branch_id="main", input_fingerprint=digest([stage, "original input"]))
    row = store.claim(harness.principal, harness.brain, turn_id, worker_id="old-host")
    token = row["lease_token"]

    def advance(target, **kwargs):
        nonlocal row
        row = store.advance(harness.principal, harness.brain, turn_id, lease_token=token,
                             expected_revision=row["revision"], stage=target, **kwargs)

    def output(state):
        nonlocal row
        row = store.record_output(harness.principal, harness.brain, turn_id, lease_token=token,
                                   expected_revision=row["revision"], text="Actual reply for " + stage, delivery_state=state)

    if stage == "failed":
        row = store.fail(harness.principal, harness.brain, turn_id, lease_token=token,
                          expected_revision=row["revision"], failure_code="generation_failed")
    elif stage != "started":
        event = harness.observe("Original input for " + stage, conversation=stage)["accepted_event_ids"][0]
        advance("captured", input_event_refs=[{"event_id": event, "revision": 1}])
        if stage != "captured":
            advance("prepared", context_event_refs=[], context_fingerprint=digest(stage),
                    context_generation=store.status(harness.principal, harness.brain)["dependency_generation"],
                    working_revision=0, context_tokens=50, selection_omitted_reason="custom_context")
            if stage != "prepared":
                advance("generating")
                if stage != "generating":
                    output("draft")
                    if stage != "generated":
                        advance("delivering")
                        if stage != "delivering":
                            output("delivered")
                            if stage == "committed":
                                with harness.database.transaction(harness.principal) as conn:
                                    conn.execute("UPDATE memory_runtime_turns SET stage='committed' WHERE tenant_id=%s "
                                                 "AND owner_id=%s AND brain_id=%s AND turn_id=%s", (
                                                     harness.principal.tenant_id, harness.principal.principal_id,
                                                     harness.brain, turn_id,
                                                 ))
                                row = store.get(harness.principal, harness.brain, turn_id)
                            elif stage == "completed":
                                row = store.finish(harness.principal, harness.brain, turn_id, lease_token=token,
                                                    expected_revision=row["revision"])
    assert row["stage"] == stage
    return {"row": row, "lease_token": token}


def seeded_job(case, state="running", *, kind="consolidate"):
    """A job in the state a worker of an older runtime left it: learning jobs (``consolidate``) are no longer run,
    so they are written here as that runtime wrote them; a running one holds a live lease."""
    harness = case.harness
    identifier, token = uid(), uid()
    claimed = state != "queued"
    with harness.database.transaction(harness.principal) as conn:
        conn.execute(
            "INSERT INTO memory_jobs(tenant_id,owner_id,brain_id,id,kind,payload,state,attempts,fence,worker_id,"
            "lease_token_digest,lease_expires_at,last_error,completed_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
            "CASE WHEN %s THEN clock_timestamp()+interval '2 minutes' END,%s,CASE WHEN %s THEN clock_timestamp() END)", (
                harness.principal.tenant_id, harness.principal.principal_id, harness.brain, identifier, kind,
                Jsonb({"target": {"conversation_ref": "chat", "branch_ref": "main"},
                       "from_sequence": 1, "through_sequence": 2}),
                state, int(claimed), int(claimed), "old-worker" if state == "running" else None,
                hashlib.sha256(token.encode()).hexdigest() if state == "running" else None, state == "running",
                "provider_failed" if state in {"failed", "cancelled"} else None, state == "completed",
            ))
    return {"id": identifier, "state": state, "lease_token": token, "fence": int(claimed)}


def reservation(case, job, outcome="reserved", *, usage=None):
    """A model-call reservation of the removed cognition pipeline, settled or not, as it was stored."""
    harness = case.harness
    identifier = "semantic:proposal:" + uid()
    with harness.database.transaction(harness.principal) as conn:
        conn.execute(
            "INSERT INTO memory_cognitive_operations(tenant_id,owner_id,brain_id,job_id,operation_id,request_fingerprint,"
            "input_bytes,fence,outcome,usage,response_fingerprint,completed_at) VALUES(%s,%s,%s,%s,%s,%s,123,%s,%s,%s,%s,"
            "CASE WHEN %s THEN clock_timestamp() END)", (
                harness.principal.tenant_id, harness.principal.principal_id, harness.brain, job["id"], identifier,
                digest(identifier), job["fence"], outcome, Jsonb(usage) if usage is not None else None,
                digest([outcome, identifier]) if outcome != "reserved" else None, outcome != "reserved",
            ))
        conn.execute("UPDATE memory_jobs SET model_calls=model_calls+1,input_bytes=input_bytes+123,max_model_calls=10,"
                     "max_input_bytes=1230 WHERE tenant_id=%s AND brain_id=%s AND id=%s",
                     (harness.principal.tenant_id, harness.brain, job["id"]))
    return identifier


def budget(case):
    """An explicitly configured cognitive budget, as the removed budget commands stored it."""
    harness = case.harness
    with harness.database.transaction(harness.principal) as conn:
        conn.execute(
            "INSERT INTO memory_cognitive_budgets(tenant_id,owner_id,brain_id,window_seconds,max_model_calls,"
            "max_input_bytes,revision,is_explicit) VALUES(%s,%s,%s,3600,20,10000,1,true)",
            (harness.principal.tenant_id, harness.principal.principal_id, harness.brain))
        conn.execute(
            "INSERT INTO memory_cognitive_budget_changes(tenant_id,owner_id,brain_id,request_id,request_fingerprint,"
            "expected_revision,revision,window_seconds,max_model_calls,max_input_bytes) "
            "VALUES(%s,%s,%s,%s,%s,0,1,3600,20,10000)",
            (harness.principal.tenant_id, harness.principal.principal_id, harness.brain, uid(), digest("budget")))


def outcomes(case):
    counts = {}
    for row in records(case, "memory_cognitive_operations"):
        counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
    return counts


def test_quarantine_preserves_sources_assertions_receipts_and_all_accounting(restored):
    case, harness = restored, restored.harness
    event_id = harness.observe("This retained original statement is not a restored instruction.")["accepted_event_ids"][0]
    with harness.database.transaction(harness.principal) as conn:
        brain = harness.service._brain(conn, harness.principal, harness.brain)
        event, = harness.service._events(conn, harness.principal, brain, event_ids=[event_id])
        harness.service._publish(conn, harness.principal, brain, cognition.extract_event(event)[0])
    phases = ("started", "captured", "prepared", "generating", "generated", "delivering", "delivered",
              "committed", "completed", "failed")
    turns = {phase: turn_at(case, phase) for phase in phases}
    recalled = harness.memory.recall("retained original statement", conversation_id="chat", branch_id="main")
    # Snapshots from older runtimes can contain durable candidate diagnostics.
    with harness.database.transaction(harness.principal) as conn:
        harness.service._save_traces(conn, harness.principal, {"id": harness.brain}, recalled["result"]["recall_traces"])
    for state in ("queued", "running", "failed", "cancelled", "superseded", "completed"):
        seeded_job(case, state)
    running = seeded_job(case)
    budget(case)
    reservation(case, running)
    reservation(case, running, "completed", usage={"input_tokens": 30, "output_tokens": 12, "total_tokens": 42})
    reservation(case, running, "failed", usage={"input_tokens": 2, "output_tokens": 0, "total_tokens": 2})
    reservation(case, running, "uncertain")
    tables = ("memory_events", "memory_assertions", "memory_event_dependencies", "memory_cognitive_budgets",
              "memory_cognitive_budget_changes", "memory_runtime_turns", "memory_jobs", "memory_cognitive_operations",
              "memory_brains", "memory_working_states", "memory_traces", "memory_requests")
    before = {table: records(case, table) for table in tables}
    assert before["memory_working_states"] and before["memory_traces"]
    assert outcomes(case) == {"reserved": 1, "completed": 1, "failed": 1, "uncertain": 1}
    apply_quarantine(case)
    after = {table: records(case, table) for table in tables}
    for table in tables[:5]:
        assert after[table] == before[table], table
    for old in before["memory_runtime_turns"]:
        current = next(row for row in after["memory_runtime_turns"] if row["turn_id"] == old["turn_id"])
        if old["stage"] in {"completed", "failed"}:
            assert current == old
            continue
        assert current["stage"] == "failed" and current["failure_code"] == "cancelled"
        assert current["fence"] == old["fence"] + 1 and current["revision"] == old["revision"] + 1
        assert not current["scope_reserved"]
        for key in ("worker_id", "lease_token_digest", "lease_expires_at", "prepared_memory_selection", "recall_plan",
                    "orientation_route", "orientation_preflight", "response_review", "last_transition_hash"):
            assert current[key] is None
        for key in ("delivery_receipt", "input_event_refs", "output_event_refs", "context_event_refs",
                    "claim_count", "generation_count", "recall_model_calls", "recall_input_bytes", "response_review_calls"):
            assert current[key] == old[key], (old["stage"], key)
    assert turns["delivered"]["row"]["delivery_receipt"] is not None
    for old in before["memory_jobs"]:
        current = next(row for row in after["memory_jobs"] if row["id"] == old["id"])
        if old["state"] == "completed":
            assert current == old
            continue
        assert current["state"] == current["last_error"] == "cancelled"
        assert current["fence"] == old["fence"] + 1
        assert current["worker_id"] is current["lease_token_digest"] is current["lease_expires_at"] is None
        for key in ("model_calls", "input_bytes", "max_model_calls", "max_input_bytes", "attempts", "payload", "result"):
            assert current[key] == old[key]
    for old in before["memory_cognitive_operations"]:
        current = next(row for row in after["memory_cognitive_operations"] if row["operation_id"] == old["operation_id"])
        if old["outcome"] == "reserved":
            assert current["outcome"] == "uncertain" and current["completed_at"] is not None
            assert {key: value for key, value in current.items() if key not in {"outcome", "completed_at"}} == {
                key: value for key, value in old.items() if key not in {"outcome", "completed_at"}}
        else:
            assert current == old
    assert after["memory_working_states"] == after["memory_traces"] == []
    assert all(row["response"] is None for row in after["memory_requests"])
    for old in before["memory_brains"]:
        current = next(row for row in after["memory_brains"] if row["id"] == old["id"])
        assert current["scope_generation"] == old["scope_generation"] + 1
        assert current["dependency_generation"] == old["dependency_generation"] + 1
        assert current["durable_sequence"] == old["durable_sequence"]
    ledger = records(case, "memory_recovery_quarantine")
    assert {(row["object_id"], row["prior_state"]) for row in ledger if row["object_kind"] == "turn"} == {
        (item["row"]["turn_id"], stage) for stage, item in turns.items() if stage not in {"completed", "failed"}}
    assert {row["object_id"] for row in ledger if row["object_kind"] == "job"} == {
        row["id"] for row in before["memory_jobs"]}
    assert outcomes(case) == {"completed": 1, "failed": 1, "uncertain": 2}


def snapshot(case):
    return {table: records(case, table) for table in (
        "memory_recovery_installations", "memory_recovery_quarantine", "memory_runtime_turns",
        "memory_runtime_turn_transitions", "memory_jobs", "memory_cognitive_operations", "memory_brains",
    )}


def test_quarantine_reentry_is_exactly_idempotent_and_wrong_binding_rolls_back(restored):
    case = restored
    turn_at(case, "captured")
    before = snapshot(case)
    for changes in ({"source_installation_id": uid()}, {"registry_id": uid()}):
        with pytest.raises(RegistryError):
            apply_quarantine(case, **changes)
        assert snapshot(case) == before
    apply_quarantine(case)
    first = snapshot(case)
    apply_quarantine(case)
    assert snapshot(case) == first
    for changes in ({"installation_id": uid()}, {"manifest_hash": digest("different")},
                    {"recovery_epoch": uid()}, {"registry_id": uid()}):
        with pytest.raises(RegistryError):
            apply_quarantine(case, **changes)
        assert snapshot(case) == first


def test_old_turn_and_job_leases_cannot_publish_reserve_or_send_after_activation(restored):
    case, harness = restored, restored.harness
    turns = {stage: turn_at(case, stage) for stage in ("started", "captured", "generating", "generated", "delivering")}
    job = seeded_job(case, kind="rebuild")
    reservation(case, job)
    apply_quarantine(case)
    activate(case)
    store = TurnStore(harness.database)
    publish = Mock()
    for item in turns.values():
        identifier, old = item["row"]["turn_id"], item["row"]
        for action, kwargs in (
            ("renew", {}), ("claim", {"worker_id": "new-host"}),
            ("record_output", {"expected_revision": old["revision"], "text": "must not append", "delivery_state": "draft"}),
            ("advance", {"expected_revision": old["revision"], "stage": "generating"}),
        ):
            if action != "claim":
                kwargs["lease_token"] = item["lease_token"]
            with pytest.raises(DomainError):
                getattr(store, action)(harness.principal, harness.brain, identifier, **kwargs)
    for action, kwargs in (("renew", {}), ("complete", {"publish": publish})):
        with pytest.raises(DomainError):
            getattr(case.jobs, action)(harness.principal, harness.brain, job["id"],
                                       lease_token=job["lease_token"], fence=job["fence"], **kwargs)
    publish.assert_not_called()
    assert case.jobs.claim(harness.principal, harness.brain, worker_id="new-worker", max_attempts=100) is None
    generate, send = Mock(), Mock()
    runtime = BrainRuntime(harness.memory, generate, deliver=send, generation_is_idempotent=True)
    with pytest.raises(httpx.HTTPStatusError) as unacknowledged:
        runtime.resume(turns["captured"]["row"]["turn_id"])
    assert unacknowledged.value.response.json()["error"]["code"] == "recovery_acknowledgement_required"
    with MemoryClient("http://testserver", "service-test", harness.brain,
                      transport=harness.memory._http._transport,
                      recovery_epoch=case.options["recovery_epoch"]) as reconciled:
        runtime = BrainRuntime(reconciled, generate, deliver=send, generation_is_idempotent=True)
        for stage, item in turns.items():
            with pytest.raises(RuntimeBlocked, match="source_unavailable" if stage == "started" else "cancelled"):
                runtime.resume(item["row"]["turn_id"])
        generate.assert_not_called()
        send.assert_not_called()
        assert harness.service.work_once(harness.principal, harness.brain) == 0
        fresh = reconciled.observe("A new explicitly received input after activation.",
                                    source_event_key=uid(), conversation_id="chat", branch_id="main")
        assert fresh["result"]["accepted_event_ids"]
        assert case.jobs.claim(harness.principal, harness.brain, worker_id="fresh-worker") is not None


def test_activation_requires_exact_epoch_manifest_and_live_registry_installation(restored):
    case, harness = restored, restored.harness
    turn_at(case, "captured")
    apply_quarantine(case)
    restoring = RecoveryAuthority(case.registry, case.options["installation_id"], restoring=True)
    arguments = {key: case.options[key] for key in ("recovery_epoch", "manifest_hash")}
    with pytest.raises(RegistryError):
        activate_database(harness.database, harness.principal, restoring, **arguments)
    case.registry.activate(case.options["recovery_epoch"], case.options["installation_id"],
                           case.options["manifest_hash"], **acknowledgement(case.registry.head()))
    before = snapshot(case)
    for changes in ({"recovery_epoch": uid()}, {"manifest_hash": digest("wrong manifest")}):
        with pytest.raises(RegistryError):
            activate_database(harness.database, harness.principal, restoring, **{**arguments, **changes})
        assert snapshot(case) == before
    harness.database.recovery_authority = RecoveryAuthority(case.registry, case.options["installation_id"])
    with pytest.raises(RegistryError):
        case.jobs.claim(harness.principal, harness.brain, worker_id="before-acknowledgement")
    activate_database(harness.database, harness.principal, restoring, **arguments)
    active = copy.deepcopy(records(case, "memory_recovery_installations"))
    activate_database(harness.database, harness.principal, restoring, **arguments)
    assert records(case, "memory_recovery_installations") == active
