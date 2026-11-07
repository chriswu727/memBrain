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


def test_script_projection_upgrade_preserves_source_rows_without_heap_rewrite(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = "script_upgrade_" + uid().replace("-", "")
    database = Database(make_conninfo(admin, options="-c search_path=" + namespace + ",public"))
    principal, brain = Principal(uid(), uid()), uid()
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        conn.execute(sql.SQL("CREATE TABLE {}.memory_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
                     .format(sql.Identifier(namespace)))
    old = tuple(item for item in MIGRATIONS if item[0] < "028_")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", old)
            database.migrate()
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_brains(id,tenant_id,owner_id,name) VALUES(%s,%s,%s,'upgrade')",
                         (brain, principal.tenant_id, principal.principal_id))
            conn.execute("INSERT INTO memory_assertions(tenant_id,owner_id,brain_id,id,revision,document,search_text) "
                         "SELECT %s,%s,%s,n::text,1,jsonb_build_object('statement','原始记忆 '||n),'原始记忆 '||n "
                         "FROM generate_series(1,300) n", (principal.tenant_id, principal.principal_id, brain))
            before = conn.execute("SELECT id,document,xmin::text,ctid::text FROM memory_assertions ORDER BY id").fetchall()
        database.migrate()
        database.migrate()
        with database.transaction(principal) as conn:
            assert conn.execute("SELECT id,document,xmin::text,ctid::text FROM memory_assertions ORDER BY id").fetchall() == before
            assert conn.execute("SELECT count(*) AS n FROM memory_assertions WHERE source_han_majority IS NULL").fetchone()["n"] == 300
            assert conn.execute("SELECT to_regclass('memory_assertions_pending_script') AS name").fetchone()["name"]
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", old)
            with pytest.raises(SchemaCompatibilityError):
                database.check_compatibility()
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))
