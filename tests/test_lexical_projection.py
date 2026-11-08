import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_candidates import Candidates, key
from test_candidates import candidates as candidates

from membrain import storage
from membrain.build_identity import MIGRATIONS
from membrain.config import Settings
from membrain.helpers import Principal, uid
from membrain.lexical_candidates import lexical_rows
from membrain.storage import Database, SchemaCompatibilityError

pytestmark = pytest.mark.integration


class Recomputed:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        return self.connection.execute(query.replace("a.search_lexemes", "to_tsvector('simple',a.search_text)"), params)


def test_stored_projection_matches_recomputed_channels_under_all_filters(candidates):
    first = candidates.add("I keep an amber map and a notebook labelled zeta00940.")
    second = candidates.add("Mara carried a green cup when she married Theo.")
    candidates.add("银杏树旁的小学有蓝色地图。")
    candidates.add("Las gafas de repuesto están en la caja roja.")
    candidates.add("An amber map is private to another conversation.", conversation="other", visibility="conversation")
    candidates.add("The amber map is on a private fork.", branch="fork")
    candidates.add("The amber map was withdrawn.", lifecycle="dormant")
    candidates.add("Try a green notebook.", role="assistant")
    foreign = Candidates(candidates.database)
    foreign.add("A foreign owner's amber map must never be returned.")
    queries = ["amber map", "marry green", "zeta00940", "银杏树", "gafas repuesto", "unknown", "x" * 257,
               "label' | !('private'); --", " ".join(f"term{number}" for number in range(130))]
    options = [{}, {"include_speech": False}, {"through_sequence": 1}, {"through_sequence": 0},
               {"excluded_versions": [key(first)]},
               {"independent_of_event_ids": [first["evidence_refs"][0]["event_id"]]},
               {"through_sequence": 2, "excluded_versions": [key(second)]}]
    with candidates.database.transaction(candidates.principal) as conn:
        conn.execute("UPDATE memory_assertions SET embedding=NULL WHERE tenant_id=%s AND owner_id=%s "
                     "AND brain_id=%s AND id=%s", (*candidates.params, second["memory_id"]))
        for query in queries:
            for limit in (0, 1, 2, 16):
                for option in options:
                    actual = lexical_rows(conn, candidates.params, candidates.target, query, limit=limit, **option)
                    expected = lexical_rows(Recomputed(conn), candidates.params, candidates.target, query,
                                            limit=limit, **option)
                    assert actual == expected, (query, limit, option)


def test_projection_follows_text_updates_and_content_erasure(candidates):
    memory = candidates.add("The secret label is copperlabel.")
    with candidates.database.transaction(candidates.principal) as conn:
        row = conn.execute("UPDATE memory_assertions SET search_text='The replacement is amberlabel.' "
                           "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s "
                           "RETURNING search_lexemes @@ to_tsquery('simple','copperlabel') AS old, "
                           "search_lexemes @@ to_tsquery('simple','amberlabel') AS new",
                           (*candidates.params, memory["memory_id"])).fetchone()
        assert row == {"old": False, "new": True}
    result = candidates.service.handle(candidates.principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(),
        "action": "forget", "target": candidates.target,
        "payload": {"idempotency_key": uid(), "selector": {"kind": "all_authorized_scope", "ids": []},
                    "mode": "erase_content", "expected_scope_generation": 1},
    })
    assert result["outcome"] == "completed", result
    with candidates.database.transaction(candidates.principal) as conn:
        rows = conn.execute("SELECT document,search_text,search_lexemes::text AS lexemes FROM memory_assertions "
                            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s", candidates.params).fetchall()
    assert rows and all(row == {"document": None, "search_text": "", "lexemes": ""} for row in rows)


def test_projection_upgrade_preserves_records_and_rebuilds_index(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = "lexical_upgrade_" + uid().replace("-", "")
    database = Database(make_conninfo(admin, options="-c search_path=" + namespace + ",public"))
    principal, brain = Principal(uid(), uid()), uid()
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        conn.execute(sql.SQL("CREATE TABLE {}.memory_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
                     .format(sql.Identifier(namespace)))
    old = tuple(item for item in MIGRATIONS if item[0] < "030_")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", old)
            database.migrate()
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_brains(id,tenant_id,owner_id,name) VALUES(%s,%s,%s,'upgrade')",
                         (brain, principal.tenant_id, principal.principal_id))
            conn.execute("INSERT INTO memory_assertions(tenant_id,owner_id,brain_id,id,revision,document,search_text) "
                         "SELECT %s,%s,%s,n::text,1,jsonb_build_object('statement','原始记忆 amber '||n), "
                         "CASE WHEN n %% 3=0 THEN '' ELSE '原始记忆 amber '||n END FROM generate_series(1,300) n",
                         (principal.tenant_id, principal.principal_id, brain))
            before = conn.execute("SELECT to_jsonb(a) AS row FROM memory_assertions a ORDER BY id").fetchall()
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", (*old, (MIGRATIONS[-1][0], MIGRATIONS[-1][1] + b"\nSELECT 1/0;")))
            with pytest.raises(psycopg.errors.DivisionByZero):
                database.migrate()
        with database.transaction(principal) as conn:
            assert conn.execute("SELECT to_jsonb(a) AS row FROM memory_assertions a ORDER BY id").fetchall() == before
            assert conn.execute("SELECT count(*) AS n FROM memory_migrations WHERE name=%s",
                                (MIGRATIONS[-1][0],)).fetchone()["n"] == 0
            index = conn.execute("SELECT pg_get_indexdef('memory_assertions_search'::regclass) AS definition").fetchone()["definition"]
            assert "to_tsvector" in index
        database.migrate()
        database.migrate()
        assert database.check_compatibility(require_current=True)["pending_count"] == 0
        with database.transaction(principal) as conn:
            assert conn.execute("SELECT to_jsonb(a)-'search_lexemes' AS row FROM memory_assertions a ORDER BY id").fetchall() == before
            assert conn.execute("SELECT count(*) AS n FROM memory_assertions "
                                "WHERE search_lexemes IS DISTINCT FROM to_tsvector('simple',search_text)").fetchone()["n"] == 0
            index = conn.execute("SELECT pg_get_indexdef('memory_assertions_search'::regclass) AS definition").fetchone()["definition"]
            assert "USING gin (search_lexemes)" in index
            assert conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                                "WHERE oid='memory_assertions'::regclass").fetchone() == {
                                    "relrowsecurity": True, "relforcerowsecurity": True}
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", old)
            with pytest.raises(SchemaCompatibilityError):
                database.check_compatibility()
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))
