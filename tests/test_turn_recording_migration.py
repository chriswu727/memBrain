import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from membrain import storage
from membrain.build_identity import MIGRATIONS
from membrain.config import Settings
from membrain.helpers import DomainError, Principal, digest, uid
from membrain.storage import Database
from membrain.turns import TurnStore


def test_upgrade_preserves_turns_without_refreshing_legacy_capture_authority(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = "turn_recording_" + uid().replace("-", "")
    database = Database(make_conninfo(admin, options="-c search_path=" + namespace + ",public"))
    principal, brain = Principal(uid(), uid()), uid()
    params = principal.tenant_id, principal.principal_id, brain
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        conn.execute(sql.SQL("CREATE TABLE {}.memory_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
                     .format(sql.Identifier(namespace)))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", tuple(item for item in MIGRATIONS if item[0] < "033_"))
            database.migrate()
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_brains(tenant_id,owner_id,id,name,recording_revision) "
                         "VALUES(%s,%s,%s,'legacy',2)", params)
            conn.execute("INSERT INTO memory_runtime_turns(tenant_id,owner_id,brain_id,turn_id,conversation_id,"
                         "branch_id,input_fingerprint,scope_reserved) VALUES(%s,%s,%s,'old','chat','main',%s,true)",
                         (*params, digest("old input")))
            before = conn.execute("SELECT * FROM memory_runtime_turns WHERE brain_id=%s", (brain,)).fetchone()
        database.migrate()
        database.migrate()
        with database.transaction(principal) as conn:
            after = conn.execute("SELECT * FROM memory_runtime_turns WHERE brain_id=%s", (brain,)).fetchone()
            assert after.pop("ephemeral_delivery_state") is None
            assert after.pop("ephemeral") is False
            assert after.pop("recording_revision") == 0 and after == before
            assert conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                                "WHERE oid='memory_runtime_turns'::regclass").fetchone() == {
                                    "relrowsecurity": True, "relforcerowsecurity": True}
        store = TurnStore(database)
        old = store.claim(principal, brain, "old", worker_id=uid())
        with pytest.raises(DomainError) as rejected:
            store.renew(principal, brain, "old", lease_token=old["lease_token"])
        assert rejected.value.code == "context_stale"
        fresh = store.begin(principal, brain, turn_id="new", conversation_id="new-chat", branch_id="main",
                            input_fingerprint=digest("new input"))
        assert fresh["recording_revision"] == 2
        with pytest.raises(psycopg.errors.CheckViolation), database.transaction(principal) as conn:
            conn.execute("UPDATE memory_runtime_turns SET recording_revision=-1 WHERE turn_id='new'")
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))
