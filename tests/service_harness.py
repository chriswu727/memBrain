"""Harnesses many tests share: one principal's brain on a real service, directly or behind the HTTP API.

``harness`` replaces the harness of the retired ``test_learning.py``, which also gave the service a deterministic
cognition model; background learning was removed, so the service here runs as every installation now does, with no
model. ``turns`` replaces the harness of the retired ``test_turns.py``, whose turn lifecycle store went with runtime
mode; the fixture keeps its old name so the tests that only used its brain, ``action`` and ``observe`` read as before.
"""
import hashlib

import httpx
import pytest
from fastapi.testclient import TestClient

from membrain.api import create_app
from membrain.client import MemoryClient
from membrain.config import Settings
from membrain.contracts import CONTRACT_VERSION
from membrain.helpers import Principal, uid
from membrain.service import MemoryService
from membrain.storage import Database


class Harness:
    def __init__(self, database):
        self.database = database
        self.principal = Principal(uid(), uid())
        self.service = MemoryService(database)
        self.brain = self.service.create_brain(self.principal, "Service integration")["id"]
        self.memory = None

    def observe(self, text, *, conversation="chat", branch="main", source_key=None, revision=1):
        return self.memory.observe(
            text, conversation_id=conversation, branch_id=branch, source_event_key=source_key or uid(),
            producer_ref="service-test", source_revision=revision, interpretation_hint="real_world_report",
        )["result"]

    def job(self, job_id):
        with self.database.transaction(self.principal) as conn:
            return conn.execute("SELECT * FROM memory_jobs WHERE tenant_id=%s AND brain_id=%s AND id=%s",
                                (self.principal.tenant_id, self.brain, job_id)).fetchone()

    def working(self, conversation="chat", branch="main"):
        with self.database.transaction(self.principal) as conn:
            row = conn.execute("SELECT document FROM memory_working_states WHERE tenant_id=%s AND brain_id=%s "
                               "AND conversation_id=%s AND branch_id=%s",
                               (self.principal.tenant_id, self.brain, conversation, branch)).fetchone()
            return row["document"] if row else None


@pytest.fixture
def harness():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("A dedicated PostgreSQL database is required")
    value = Harness(Database(settings.database_url))
    settings = Settings(database_url=settings.database_url, api_keys={
        hashlib.sha256(b"service-test").hexdigest(): value.principal,
    })
    with TestClient(create_app(settings, service=value.service)) as server:
        def forward(request):
            response = server.request(request.method, request.url.path, headers=dict(request.headers),
                                      content=request.content)
            return httpx.Response(response.status_code, content=response.content, headers=dict(response.headers))

        with MemoryClient("http://testserver", "service-test", value.brain,
                          transport=httpx.MockTransport(forward)) as memory:
            value.memory = memory
            yield value


class Conversation:
    """A brain with one conversation branch, driven through ``MemoryService.handle``."""

    def __init__(self, database):
        self.database = database
        self.service = MemoryService(database)
        self.principal = Principal(uid(), uid())
        self.brain = self.service.create_brain(self.principal, "Lifecycle journal tests")["id"]
        self.turn_id = uid()
        self.conversation = "测试会话"
        self.branch = "main"

    def action(self, action, payload, conversation=None):
        response = self.service.handle(self.principal, {
            "contract_version": CONTRACT_VERSION, "message_type": "request", "request_id": uid(),
            "action": action, "target": {"brain_ref": self.brain,
                "conversation_ref": conversation or self.conversation, "branch_ref": self.branch},
            "payload": payload,
        })
        assert response["outcome"] == "completed", response
        return response["result"]

    def observe(self, text="Private input never belongs in monitoring.", role="user", delivery="received",
                source_key=None, revision=1, conversation=None):
        result = self.action("observe", {"idempotency_key": uid(), "events": [{
            "producer_ref": "turn-test", "source_event_key": source_key or uid(), "source_revision": revision,
            "actor_ref": role, "actor_role": role, "event_kind": "message",
            "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "real_world_report", "delivery_state": delivery,
        }]}, conversation)
        event_id = (result["accepted_event_ids"] + result["duplicate_event_ids"])[0]
        return {"event_id": event_id, "revision": revision}

    def scope_generation(self):
        """Read without the service, so a test that holds the service's brain lock is not affected."""
        with self.database.transaction(self.principal) as conn:
            return conn.execute("SELECT scope_generation FROM memory_brains WHERE tenant_id=%s AND owner_id=%s AND id=%s",
                                self.service._params(self.principal, self.brain)).fetchone()["scope_generation"]


@pytest.fixture
def turns():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("MEMORY_DATABASE_URL must point to the dedicated test database")
    return Conversation(Database(settings.database_url))
