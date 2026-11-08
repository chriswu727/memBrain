import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from membrain import storage
from membrain.build_identity import MIGRATIONS
from membrain.config import Settings
from membrain.helpers import Principal, uid
from membrain.jobs import JobStore
from membrain.storage import Database


def test_upgrade_preserves_task_authority_and_binds_only_unstarted_work_to_current_policy(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = "learning_recording_" + uid().replace("-", "")
    database = Database(make_conninfo(admin, options="-c search_path=" + namespace + ",public"))
    principal, brain = Principal(uid(), uid()), uid()
    params = principal.tenant_id, principal.principal_id, brain
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        conn.execute(sql.SQL("CREATE TABLE {}.memory_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
                     .format(sql.Identifier(namespace)))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", tuple(item for item in MIGRATIONS if item[0] < "032_"))
            database.migrate()
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_brains(tenant_id,owner_id,id,name,recording_revision) "
                         "VALUES(%s,%s,%s,'legacy',2)", params)
            for name, attempts in (("unstarted", 0), ("interrupted", 1)):
                conn.execute("INSERT INTO memory_jobs(tenant_id,owner_id,brain_id,id,kind,payload,attempts) "
                             "VALUES(%s,%s,%s,%s,'consolidate','{\"original\":true}',%s)",
                             (*params, name, attempts))
            before = conn.execute("SELECT * FROM memory_jobs ORDER BY id").fetchall()
        database.migrate()
        database.migrate()
        with database.transaction(principal) as conn:
            after = conn.execute("SELECT * FROM memory_jobs ORDER BY id").fetchall()
            assert all(row.pop("recording_revision") is None for row in after)
            assert after == before
            assert conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                                "WHERE oid='memory_jobs'::regclass").fetchone() == {
                                    "relrowsecurity": True, "relforcerowsecurity": True}
        store = JobStore(database)
        for name, expected in (("unstarted", 2), ("interrupted", 0)):
            row = store.claim(principal, brain, worker_id=uid(), job_id=name)
            assert row["recording_revision"] == expected
            assert row["payload"] == {"original": True}
        with pytest.raises(psycopg.errors.CheckViolation), database.transaction(principal) as conn:
            conn.execute("UPDATE memory_jobs SET recording_revision=-1 WHERE id='unstarted'")
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))
