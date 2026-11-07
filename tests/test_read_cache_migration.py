import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from membrain import storage
from membrain.build_identity import MIGRATIONS
from membrain.config import Settings
from membrain.helpers import Principal, uid
from membrain.storage import Database, SchemaCompatibilityError

pytestmark = pytest.mark.integration


def test_upgrade_adds_empty_cache_without_rewriting_legacy_history(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = "cache_upgrade_" + uid().replace("-", "")
    database = Database(make_conninfo(admin, options="-c search_path=" + namespace + ",public"))
    principal = Principal(uid(), uid())
    brain = uid()
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        conn.execute(sql.SQL("CREATE TABLE {}.memory_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
                     .format(sql.Identifier(namespace)))
    old = tuple(item for item in MIGRATIONS if item[0] < "027_")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", old)
            database.migrate()
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_brains(id,tenant_id,owner_id,name) VALUES(%s,%s,%s,'upgrade')",
                         (brain, principal.tenant_id, principal.principal_id))
            conn.execute("INSERT INTO memory_requests(tenant_id,owner_id,brain_id,action,key,request_hash,response) "
                         "SELECT %s,%s,%s,'recall',n::text,'fingerprint',jsonb_build_object('legacy',n) FROM generate_series(1,300) n",
                         (principal.tenant_id, principal.principal_id, brain))
            before = conn.execute("SELECT * FROM memory_requests ORDER BY key").fetchall()
        database.migrate()
        database.migrate()
        with database.transaction(principal) as conn:
            assert conn.execute("SELECT * FROM memory_requests ORDER BY key").fetchall() == before
            for table in ("memory_read_cache", "memory_cache_maintenance"):
                assert conn.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))).fetchall() == []
                row = conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass",
                                   (table,)).fetchone()
                assert row == {"relrowsecurity": True, "relforcerowsecurity": True}
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", old)
            with pytest.raises(SchemaCompatibilityError):
                database.check_compatibility()
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))
