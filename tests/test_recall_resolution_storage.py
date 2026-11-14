import json
from datetime import datetime, timedelta

import httpx
import pytest
from legacy_cognition import FIXTURES, stored_archive
from test_candidates import candidates as candidates
from test_recall_resolution import SHORT

from membrain.client import MemoryClient
from membrain.service import MemoryService
from membrain.storage import Database

pytestmark = pytest.mark.integration


def published(stored):
    """Restore the local archive the runtime at 2600219b exported after publishing a claim with a verified short view
    over one long message; move the harness to the restored brain and return that message and claim."""
    wrapper = json.loads((FIXTURES / "recall_summary.json").read_text(encoding="utf-8"))
    archive = stored_archive(stored, "recall_summary")
    fresh = stored.service.create_brain(stored.principal, "Restored recall summary")["id"]
    restored = client(stored, fresh).restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                                             expected_scope_generation=1, mode="new_brain", brain_id=fresh)["result"]
    assert restored["read_enabled"] and restored["quarantined_event_count"] == 0
    stored.brain_id = fresh
    stored.target = {**stored.target, "brain_ref": fresh}
    with stored.database.transaction(stored.principal) as conn:
        brain = stored.service._brain(conn, stored.principal, fresh)
        source = stored.service._events(conn, stored.principal, brain, event_ids=[wrapper["source_event_id"]])[0]
        memory = conn.execute("SELECT document FROM memory_assertions WHERE tenant_id=%s AND brain_id=%s AND id=%s "
                              "AND is_current", (stored.principal.tenant_id, fresh, wrapper["memory_id"])).fetchone()
    return source, stored.service._rebind(memory["document"], stored.principal, brain)


def client(stored, brain_id=None):
    def handle(request):
        return httpx.Response(200, json=stored.service.handle(stored.principal, json.loads(request.content)))

    return MemoryClient("http://memory.test", "test-key", brain_id or stored.brain_id,
                        transport=httpx.MockTransport(handle))


def test_database_recall_restart_and_expansion_preserve_the_same_source_and_memory(candidates):
    source, memory = published(candidates)
    future = (datetime.fromisoformat(memory["system_time"]["recorded_at"]) + timedelta(days=3650)).isoformat()
    candidates.service = MemoryService(Database(candidates.database.dsn), access_time_provider=lambda: future)
    memory_client = client(candidates)
    short = memory_client.recall("Grandma safe", conversation_id="current", branch_id="main")["result"]
    assert SHORT in short["model_context"] and "yellow lid" not in short["model_context"]
    inspected = memory_client.inspect([memory["memory_id"]], conversation_id="current", branch_id="main")["result"]
    assert inspected["memories"][0]["statement"] == memory["statement"]
    assert inspected["memories"][0]["recall_summary"] == memory["recall_summary"]
    assert inspected["events"][0]["observed"]["content"]["text"] == source["observed"]["content"]["text"]
    expanded = memory_client.recall("Grandma yellow lid", conversation_id="current", branch_id="main")["result"]
    assert "yellow lid" in expanded["model_context"]
    assert any(item["memory"]["memory_id"] == memory["memory_id"] for item in expanded["items"])
    assert memory_client.recall("Grandma safe", detail_level="full", conversation_id="current", branch_id="main")["result"]["usage"]["model_calls"] == 0
    again = memory_client.inspect([memory["memory_id"]], conversation_id="current", branch_id="main")["result"]
    assert again["memories"] == inspected["memories"]


def test_trusted_archive_keeps_both_views_and_explicit_erasure_removes_both(candidates):
    source, memory = published(candidates)
    memory_client = client(candidates)
    exported = memory_client.export()["result"]
    fresh = candidates.service.create_brain(candidates.principal, "Restored resolution test")["id"]
    restored = memory_client.restore(exported["archive_id"], expected_manifest_sha256=exported["manifest_sha256"],
                                     expected_scope_generation=1, mode="new_brain", brain_id=fresh)["result"]
    assert restored["read_enabled"]
    inspected = memory_client.inspect([memory["memory_id"]], brain_id=fresh)["result"]
    assert inspected["memories"][0]["statement"] == memory["statement"]
    assert inspected["memories"][0]["recall_summary"] == memory["recall_summary"]
    client(candidates, fresh).forget([source["event_id"]], kind="events", mode="erase_content",
                                    expected_scope_generation=restored["scope_generation"])
    erased = memory_client.inspect([memory["memory_id"]], brain_id=fresh)["result"]
    assert erased["memories"] == [] and erased["events"] == []


def test_runtime_without_resolution_migration_refuses_the_upgraded_database(candidates, monkeypatch):
    from membrain import storage
    from membrain.storage import SchemaCompatibilityError

    assert "024_recall_resolution.sql" in dict(storage.MIGRATIONS)
    monkeypatch.setattr(storage, "MIGRATIONS", tuple(
        migration for migration in storage.MIGRATIONS if migration[0] < "024_recall_resolution.sql"))
    with pytest.raises(SchemaCompatibilityError):
        candidates.database.check_compatibility(require_current=True)
