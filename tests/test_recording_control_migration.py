import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from membrain import storage
from membrain.build_identity import MIGRATIONS
from membrain.config import Settings
from membrain.helpers import Principal, uid
from membrain.storage import Database


def test_upgrade_defaults_existing_brains_to_recording_without_rewriting_turns(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = "recording_upgrade_" + uid().replace("-", "")
    database = Database(make_conninfo(admin, options="-c search_path=" + namespace + ",public"))
    principal, brain = Principal(uid(), uid()), uid()
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        conn.execute(sql.SQL("CREATE TABLE {}.memory_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
                     .format(sql.Identifier(namespace)))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", tuple(item for item in MIGRATIONS if item[0] < "029_"))
            database.migrate()
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_brains(id,tenant_id,owner_id,name) VALUES(%s,%s,%s,'legacy')",
                         (brain, principal.tenant_id, principal.principal_id))
            conn.execute("INSERT INTO memory_runtime_turns(tenant_id,owner_id,brain_id,turn_id,conversation_id,"
                         "branch_id,input_fingerprint) VALUES(%s,%s,%s,'turn','session','main',%s)",
                         (principal.tenant_id, principal.principal_id, brain, "a" * 64))
            before = conn.execute("SELECT * FROM memory_runtime_turns").fetchall()
        database.migrate()
        database.migrate()
        with database.transaction(principal) as conn:
            assert conn.execute("SELECT * FROM memory_runtime_turns").fetchall() == before
            assert conn.execute("SELECT recording_paused,recording_revision FROM memory_brains").fetchone() == {
                "recording_paused": False, "recording_revision": 0}
            assert conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='memory_brains'::regclass").fetchone() == {
                "relrowsecurity": True, "relforcerowsecurity": True}
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))
