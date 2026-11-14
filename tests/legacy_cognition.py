"""Brains that an older runtime's cognition pipeline filled, for tests of what still reads and erases their rows.

Background learning with a cognition model was removed: nothing writes semantic claims with model verification,
episodes and their members, associations between memories, belief relations, consolidation and orientation jobs,
cognitive operations, budgets, feedback contributions or access state any more. Brains, configured profiles and
archives from older runtimes still hold them, and the tables stay.

The archives in ``tests/fixtures/legacy_cognition`` were exported by the runtime at 2600219b from brains its
pipeline filled (a claim with an episode, a schema claim derived from it, an exception relation between two claims,
an episode that was created, continued and closed, a claim derived from a non-current parent revision). Each is
stored here as that runtime stored a local export, and restoring it fills a brain as restoring an old export does.
Rows that archives do not carry are written with plain SQL in the shape that runtime wrote them.
"""
import copy
import json
import os
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb

from membrain import cognition
from membrain.client import default_budget
from membrain.config import Settings
from membrain.contracts import CONTRACT_VERSION
from membrain.helpers import Principal, digest, uid
from membrain.service import MemoryService
from membrain.storage import Database

FIXTURES = Path(__file__).parent / "fixtures" / "legacy_cognition"
DERIVED_TABLES = ("memory_assertions", "memory_episodes", "memory_episode_members", "memory_associations",
                  "memory_belief_relations", "memory_pattern_views", "memory_jobs", "memory_cognitive_operations",
                  "memory_cognitive_budgets", "memory_cognitive_budget_changes", "memory_feedback_contributions",
                  "memory_access_state", "memory_working_states", "memory_archives")


class Brain:
    """One principal's brain on the service, with no model of memBrain's own (the only way the service runs now)."""

    def __init__(self, database):
        self.database = database
        self.service = MemoryService(database)
        self.principal = Principal(uid(), uid())
        self.brain_id = self.service.create_brain(self.principal, "Legacy cognition tests")["id"]

    def action(self, action, payload, *, conversation="test"):
        response = self.service.handle(self.principal, {
            "message_type": "request", "contract_version": CONTRACT_VERSION, "request_id": uid(),
            "action": action, "target": {"brain_ref": self.brain_id, "conversation_ref": conversation,
                                         "branch_ref": "main"},
            "payload": payload,
        })
        assert response["outcome"] == "completed", response
        return response["result"]

    def observe(self, text, key=None, revision=1, *, producer="test"):
        result = self.action("observe", {"idempotency_key": uid(), "events": [{
            "source_event_key": key or uid(), "source_revision": revision, "producer_ref": producer,
            "actor_ref": "user", "actor_role": "user", "event_kind": "message",
            "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "real_world_report", "delivery_state": "received",
        }]})
        return self.event(result["accepted_event_ids"][0])

    def event(self, event_id):
        with self.database.transaction(self.principal) as conn:
            brain = self.service._brain(conn, self.principal, self.brain_id)
            events = self.service._events(conn, self.principal, brain, event_ids=[event_id])
            return events[0] if events else None

    def rows(self, table, where="", parameters=()):
        assert table in DERIVED_TABLES or table == "memory_events"
        with self.database.transaction(self.principal) as conn:
            return conn.execute(
                "SELECT * FROM " + table + " WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s " + where,
                (*self.service._params(self.principal, self.brain_id), *parameters),
            ).fetchall()

    def export(self, **changes):
        exported = self.action("export", {
            "include_events": True, "include_assertions": True, "include_working_states": True,
            "include_provenance": True, "include_tombstones": True, "budget": default_budget(64000), **changes,
        })
        return self.service.download_archive(self.principal, exported["archive_id"])

    def restore(self, archive, *, new_brain=True, upload=False):
        if new_brain:
            self.brain_id = self.service.create_brain(self.principal, "Restored legacy archive")["id"]
        if upload:
            archive = self.service.upload_archive(self.principal, self.brain_id, archive["document"])
        return self.action("restore", {
            "uploaded_archive_ref": archive["archive_id"], "expected_manifest_sha256": archive["manifest_sha256"],
            "mode": "new_brain" if new_brain else "merge_authorized_brain", "apply_current_tombstones": True,
            "expected_scope_generation": self.service.dashboard(self.principal, self.brain_id)["brain"]["scope_generation"],
            "budget": default_budget(64000),
        })

    def forget(self, kind, ids, mode="erase_content"):
        scope = self.service.dashboard(self.principal, self.brain_id)["brain"]["scope_generation"]
        return self.action("forget", {"selector": {"kind": kind, "ids": list(ids)}, "mode": mode,
                                      "expected_scope_generation": scope, "idempotency_key": uid()})

    def work(self, limit=200):
        for _ in range(limit):
            if not self.service.work_once(self.principal, self.brain_id):
                return
        pytest.fail("The worker did not become idle")


def new_brain():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("A dedicated PostgreSQL database is required")
    database = Database(os.environ.get("MEMORY_TEST_DATABASE_URL", settings.database_url),
                        settings.migration_database_url)
    database.migrate()
    return Brain(database)


@pytest.fixture
def brain():
    return new_brain()


# The names the retired test_consolidation.py and test_cognitive_archives.py gave the same harness.
@pytest.fixture
def memory():
    return new_brain()


@pytest.fixture
def archive():
    return new_brain()


def reference(source, relationship="supports"):
    """An evidence reference to the whole text of a source, in the form stored memories and working state use."""
    return {"event_id": source["event_id"], "event_revision": source["revision"],
            "source_content_sha256": source["content_sha256"], "relationship": relationship,
            "span": {"start": 0, "end": len(cognition._content_text(source["observed"]["content"])),
                     "unit": "unicode_code_point"}}


def fixture(name):
    """The archive document of one fixture, as the runtime at 2600219b exported it."""
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    assert data["document"]["archive_origin"] == "local_export"
    return copy.deepcopy(data["document"])


def stored_archive(brain, name):
    """Store a fixture as a local export of the brain's current brain, the way the older runtime stored one."""
    document = fixture(name)
    archive_id, manifest = uid(), digest(document)
    with brain.database.transaction(brain.principal) as conn:
        conn.execute(
            "INSERT INTO memory_archives(tenant_id,owner_id,brain_id,id,manifest_hash,document) VALUES(%s,%s,%s,%s,%s,%s)",
            (*brain.service._params(brain.principal, brain.brain_id), archive_id, manifest, Jsonb(document)),
        )
    return {"archive_id": archive_id, "manifest_sha256": manifest, "document": document}


def legacy_brain(brain, name="views", *, upload=False):
    """Move the harness to a new brain restored from a fixture archive; return the restore result and the archive."""
    archive = stored_archive(brain, name)
    return brain.restore(archive, upload=upload), archive


def legacy_jobs(brain, sources):
    """Learning jobs as the older runtime left them: queued, failed, running with an expired lease, deferred and
    completed consolidation, a queued and a completed orientation, an operation still reserved, and a budget."""
    params = brain.service._params(brain.principal, brain.brain_id)
    target = {"conversation_ref": "test", "branch_ref": "main"}
    texts = [source["observed"]["content"]["text"] for source in sources]
    ids = [source["event_id"] for source in sources]
    window = {"target": target, "from_sequence": 1, "through_sequence": len(sources) + 8,
              "learning_contract_version": "encoding-integration-v1", "learning_phase": "encoding",
              "allocation_policy": "encoding-integration-budget-v1",
              "allocation_budget": {"max_model_calls": 4, "max_input_bytes": 393216},
              "phase_budget": {"max_model_calls": 2, "max_input_bytes": 196608}}
    result = {"status": "completed", "scope": {"conversation_id": "test", "branch_id": "main"},
              "claims": [{"statement": text} for text in texts], "situation_updates": [],
              "source_snapshot": [{"event_id": source["event_id"], "revision": source["revision"],
                                   "content_sha256": source["content_sha256"]} for source in sources]}
    jobs = {
        "queued": ("consolidate", "queued", window, None, [], None),
        "failed": ("consolidate", "failed", window, {**result, "status": "provider_unavailable"}, ids, "provider_failed"),
        "running": ("consolidate", "running", window, None, ids, None),
        "deferred": ("consolidate", "deferred", window, {**result, "status": "budget_exhausted"}, ids, "budget_exceeded"),
        "completed": ("consolidate", "completed", window, result, ids, None),
        "orient_queued": ("orient", "queued", {"turn_id": "turn-" + uid(), "target": target, "through_sequence": 4},
                          None, [], None),
        "orient_completed": ("orient", "completed", {"turn_id": "turn-" + uid(), "target": target,
                                                     "through_sequence": 4}, result, ids, None),
    }
    identifiers = {}
    with brain.database.transaction(brain.principal) as conn:
        for name, (kind, state, payload, stored, sources_ids, error) in jobs.items():
            job_id = f"{kind}:legacy-{name}-" + uid()
            identifiers[name] = job_id
            payload = copy.deepcopy(payload)
            if kind == "consolidate":
                payload["authorization_root_job_id"] = job_id
            conn.execute(
                "INSERT INTO memory_jobs(tenant_id,owner_id,brain_id,id,kind,state,payload,result,source_event_ids,"
                "source_memory_ids,attempts,last_error,fence,lease_expires_at,model_calls,input_bytes,max_model_calls,"
                "max_input_bytes,recording_revision,completed_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "CASE WHEN %s='running' THEN clock_timestamp()-interval '1 hour' END,%s,%s,2,196608,0,"
                "CASE WHEN %s='completed' THEN clock_timestamp() END)",
                (*params, job_id, kind, state, Jsonb(payload), Jsonb(stored) if stored is not None else None,
                 sources_ids, [], 0 if state == "queued" else 1, error, 0 if state == "queued" else 1, state,
                 1 if state != "queued" else 0, 4096 if state != "queued" else 0, state),
            )
        conn.execute(
            "INSERT INTO memory_cognitive_operations(tenant_id,owner_id,brain_id,job_id,operation_id,request_fingerprint,"
            "input_bytes,fence) VALUES(%s,%s,%s,%s,%s,%s,%s,1)",
            (*params, identifiers["running"], "1:proposal", digest(["legacy-request"]), 4096),
        )
        conn.execute(
            "INSERT INTO memory_cognitive_budgets(tenant_id,owner_id,brain_id,window_seconds,max_model_calls,"
            "max_input_bytes,revision,is_explicit) VALUES(%s,%s,%s,3600,100,2000000,1,true)", params,
        )
        conn.execute(
            "INSERT INTO memory_cognitive_budget_changes(tenant_id,owner_id,brain_id,request_id,request_fingerprint,"
            "expected_revision,revision,window_seconds,max_model_calls,max_input_bytes) "
            "VALUES(%s,%s,%s,%s,%s,0,1,3600,100,2000000)", (*params, "legacy-budget", digest(["legacy-budget"])),
        )
    return identifiers


def legacy_feedback(brain, memory, feedback_source, delivery_source):
    """A feedback contribution and the access state recomputed from it, as the frozen chat runtime wrote them."""
    params = brain.service._params(brain.principal, brain.brain_id)
    with brain.database.transaction(brain.principal) as conn:
        conn.execute(
            "INSERT INTO memory_feedback_contributions(tenant_id,owner_id,brain_id,memory_id,memory_revision,"
            "feedback_event_id,feedback_event_revision,feedback_content_hash,delivery_event_id,delivery_event_revision,"
            "delivery_content_hash,selection_trace_id,recall_id,turn_id,conversation_id,branch_id,kind,"
            "attribution_version,source_event_refs,source_event_ids,source_memory_ids,observed_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'test','main','user_confirmed',"
            "'sole-exact-statement-v1',%s,%s,%s,clock_timestamp())",
            (*params, memory["memory_id"], memory["revision"], feedback_source["event_id"], feedback_source["revision"],
             feedback_source["content_sha256"], delivery_source["event_id"], delivery_source["revision"],
             delivery_source["content_sha256"], "trace-" + uid(), "recall-" + uid(), "turn-" + uid(),
             Jsonb([{"event_id": feedback_source["event_id"], "revision": feedback_source["revision"]}]),
             [feedback_source["event_id"], delivery_source["event_id"]], [memory["memory_id"]]),
        )
        conn.execute(
            "INSERT INTO memory_access_state(tenant_id,owner_id,brain_id,memory_id,memory_revision,external_uses,"
            "successes,last_external_use_at,last_reinforcement_at,last_feedback_event_id,policy_version) "
            "VALUES(%s,%s,%s,%s,%s,1,1,clock_timestamp(),clock_timestamp(),%s,'contextual-access-v2')",
            (*params, memory["memory_id"], memory["revision"], feedback_source["event_id"]),
        )
