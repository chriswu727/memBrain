"""One principal's brain on a real service behind the HTTP API, with an SDK client: the harness many tests share.

It replaces the harness of the retired ``test_learning.py``, which also gave the service a deterministic cognition
model; background learning was removed, so the service here runs as every installation now does, with no model.
"""
import hashlib

import httpx
import pytest
from fastapi.testclient import TestClient

from membrain.api import create_app
from membrain.client import MemoryClient
from membrain.config import Settings
from membrain.helpers import Principal, digest, uid
from membrain.runtime import DeliveryReceipt
from membrain.runtime_client import RuntimeClient
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

    def capture(self, text="现在我要制定复习计划。", *, conversation="chat", branch="main"):
        journal = RuntimeClient(self.memory)
        turn_id = "turn-" + uid()
        row = journal.begin(turn_id=turn_id, conversation_id=conversation, branch_id=branch,
                            input_fingerprint=digest(text))
        row = journal.claim(turn_id, worker_id=uid(), expected_revision=row["revision"])
        token = row["lease_token"]
        receipt = self.observe(text, conversation=conversation, branch=branch, source_key=turn_id)
        row = journal.advance(turn_id, lease_token=token, expected_revision=row["revision"], stage="captured",
                              input_event_refs=[{"event_id": receipt["accepted_event_ids"][0], "revision": 1}],
                              durable_sequence=receipt["durable_through_sequence"])
        return journal, row, token

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


def delivered(_):
    return DeliveryReceipt("delivered")
