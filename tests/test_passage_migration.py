import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_candidates import Candidates

from membrain import storage
from membrain.build_identity import MIGRATIONS
from membrain.config import Settings
from membrain.helpers import uid
from membrain.storage import Database, SchemaCompatibilityError

pytestmark = pytest.mark.integration


def test_real_passage_upgrade_preserves_legacy_vectors_and_refuses_downgrade(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = 'passage_upgrade_' + uid().replace('-', '')
    database = Database(make_conninfo(admin, options='-c search_path=' + namespace + ',public'))
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(namespace)))
        conn.execute(sql.SQL('CREATE TABLE {}.memory_migrations '
                             '(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
                     .format(sql.Identifier(namespace)))
    old = tuple(item for item in MIGRATIONS if item[0] < '026_')
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, 'MIGRATIONS', old)
            database.migrate()
        candidates = Candidates(database)
        memory = candidates.add('My passport is in the blue kitchen drawer.')
        candidates.embed(memory, [1.0, 0.0, 0.0])
        with database.transaction(candidates.principal) as conn:
            before = conn.execute('SELECT *,embedding::text AS vector_text FROM memory_embeddings').fetchone()
        assert database.check_compatibility()['pending_count'] == len(MIGRATIONS) - len(old)
        database.migrate()
        database.migrate()
        assert database.check_compatibility(require_current=True)['pending_count'] == 0
        with database.transaction(candidates.principal) as conn:
            after = conn.execute('SELECT *,embedding::text AS vector_text FROM memory_embeddings').fetchone()
            assert after.pop('document_index_version') == 'single-vector-v1'
            assert after == before
            assert conn.execute('SELECT count(*) AS n FROM memory_embedding_passages').fetchone()['n'] == 0
            policy = conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class '
                                  "WHERE oid='memory_embedding_passages'::regclass").fetchone()
            assert policy == {'relrowsecurity': True, 'relforcerowsecurity': True}
        with monkeypatch.context() as patch:
            patch.setattr(storage, 'MIGRATIONS', old)
            with pytest.raises(SchemaCompatibilityError):
                database.migrate()
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(namespace)))
