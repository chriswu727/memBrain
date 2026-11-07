import psycopg
import pytest

from membrain.config import Settings
from membrain.helpers import Principal, uid
from membrain.service import MemoryService
from membrain.storage import Database

pytestmark = pytest.mark.integration


def test_database_enforces_owner_isolation_even_without_application_filters():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("MEMORY_DATABASE_URL must point to the dedicated test database")
    database = Database(settings.database_url)
    owner = Principal(uid(), uid())
    same_tenant_other_owner = Principal(owner.tenant_id, uid())
    other_tenant = Principal(uid(), owner.principal_id)
    brain = MemoryService(database).create_brain(owner, "RLS isolation")['id']

    with database.transaction(owner) as connection:
        role = connection.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        assert role == {"rolsuper": False, "rolbypassrls": False}
        assert connection.execute("SELECT id FROM memory_brains WHERE id=%s", (brain,)).fetchone()
    for outsider in (same_tenant_other_owner, other_tenant):
        with database.transaction(outsider) as connection:
            assert connection.execute(
                "SELECT id FROM memory_brains WHERE id=%s", (brain,),
            ).fetchone() is None
            changed = connection.execute(
                "UPDATE memory_brains SET name='unauthorized' WHERE id=%s", (brain,),
            )
            assert changed.rowcount == 0
    with psycopg.connect(settings.database_url) as unscoped:
        assert unscoped.execute(
            "SELECT id FROM memory_brains WHERE id=%s", (brain,),
        ).fetchone() is None


def test_pooled_identity_is_transaction_local_after_success_and_rollback():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("MEMORY_DATABASE_URL must point to the dedicated test database")
    database = Database(settings.database_url, pool=True)
    owner, outsider = Principal(uid(), uid()), Principal(uid(), uid())
    try:
        brain = MemoryService(database).create_brain(owner, "Pooled identity isolation")["id"]
        for rolled_back in (False, True):
            try:
                with database.transaction(owner) as connection:
                    assert connection.execute(
                        "SELECT current_setting('app.tenant_id') AS tenant, "
                        "current_setting('app.principal_id') AS principal").fetchone() == {
                            "tenant": owner.tenant_id, "principal": owner.principal_id}
                    assert connection.execute("SELECT id FROM memory_brains WHERE id=%s", (brain,)).fetchone()
                    if rolled_back:
                        raise RuntimeError("Abort the scoped transaction")
            except RuntimeError:
                assert rolled_back
            with database.pool.connection() as connection:
                assert connection.execute("SELECT id FROM memory_brains WHERE id=%s", (brain,)).fetchone() is None
            with database.transaction(outsider) as connection:
                assert connection.execute("SELECT id FROM memory_brains WHERE id=%s", (brain,)).fetchone() is None
    finally:
        database.close()
