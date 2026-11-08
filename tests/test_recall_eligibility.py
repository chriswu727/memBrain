import copy
from itertools import product

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
from test_candidates import Candidates
from test_candidates import candidates as candidates

from membrain import storage
from membrain.build_identity import MIGRATIONS
from membrain.candidates import _eligible, _scope_clause
from membrain.config import Settings
from membrain.helpers import Principal, uid
from membrain.lexical_candidates import lexical_rows
from membrain.storage import Database, SchemaCompatibilityError

pytestmark = pytest.mark.integration

ORIGINAL = (
    "coalesce({alias}.document->>'claim_kind','') NOT IN "
    "('agent_said','proposal_offered','commitment_expressed') "
    "AND NOT (coalesce({alias}.document #>> '{{derivation,method}}','')='direct_capture' "
    "AND left({alias}.document->>'statement',10)='assistant ')"
)


def test_projection_preserves_original_sql_truth_values(candidates):
    missing = object()
    documents = [None, True, 17, "assistant scalar", [], ["assistant array"]]
    for kind, derivation, statement in product(
        (missing, None, "agent_said", "proposal_offered", "commitment_expressed", "reported_fact", True, {}, []),
        (missing, None, {}, {"method": None}, {"method": "direct_capture"}, {"method": "semantic"}, [], "direct_capture"),
        (missing, None, "", "assistant ", "assistant hello", "Assistant hello", "assistant\thello", "user assistant hello", "我说 assistant hello", 17, {}, []),
    ):
        documents.append({k: v for k, v in (("claim_kind", kind), ("derivation", derivation), ("statement", statement))
                          if v is not missing})
    with candidates.database.transaction(candidates.principal) as conn:
        conn.cursor().executemany(
            "INSERT INTO memory_assertions(tenant_id,owner_id,brain_id,id,revision,document) VALUES(%s,%s,%s,%s,1,%s)",
            [(*candidates.params, str(i), Jsonb(document)) for i, document in enumerate(documents)]
            + [(*candidates.params, "sql-null", None)],
        )
        rows = conn.execute("SELECT id,recall_non_speech AS projected,(" + ORIGINAL.format(alias="a")
                            + ") AS original FROM memory_assertions a WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s",
                            candidates.params).fetchall()
    assert len(rows) == len(documents) + 1
    assert all(row["projected"] is row["original"] for row in rows)
    assert {row["projected"] for row in rows} == {True, False, None}


def test_projection_keeps_owner_scope_and_lifecycle_filters(candidates):
    owned = candidates.add("The amber map is mine.")
    speech = candidates.add("Try an amber map.", role="assistant")
    historical = candidates.add("The previous amber map was green.")
    hidden = [candidates.add("A private amber map.", conversation="other", visibility="conversation"),
              candidates.add("An amber map on another branch.", branch="fork")]
    flags = {name: candidates.add("The excluded amber map is " + name) for name in ("invalidated", "deleted", "suppressed")}
    foreign = Candidates(candidates.database)
    foreign.add("Another owner's amber map.")
    with candidates.database.transaction(candidates.principal) as conn:
        conn.execute("UPDATE memory_assertions SET is_current=false WHERE tenant_id=%s AND brain_id=%s AND id=%s",
                     (candidates.principal.tenant_id, candidates.brain_id, historical["memory_id"]))
        for flag, memory in flags.items():
            conn.execute(sql.SQL("UPDATE memory_assertions SET {}=true WHERE tenant_id=%s AND brain_id=%s AND id=%s")
                         .format(sql.Identifier(flag)), (candidates.principal.tenant_id, candidates.brain_id, memory["memory_id"]))
        for alias, current, include_speech in product(("a", "m"), (True, False), (True, False)):
            scope, params = _scope_clause(alias, candidates.target)
            projected = _eligible(alias, current=current, include_speech=include_speech)
            original = _eligible(alias, current=current) + ("" if include_speech else "AND " + ORIGINAL.format(alias=alias) + " ")
            outputs = [conn.execute(f"SELECT {alias}.id FROM memory_assertions {alias} WHERE " + predicate + scope
                                    + f"ORDER BY {alias}.id", (*candidates.params, *params)).fetchall()
                       for predicate in (projected, original)]
            assert outputs[0] == outputs[1]
            expected = {owned["memory_id"]} | ({speech["memory_id"]} if include_speech else set())
            if not current:
                expected.add(historical["memory_id"])
            assert {row["id"] for row in outputs[0]} == expected
            assert not {row["id"] for row in outputs[0]} & {row["memory_id"] for row in hidden}


def test_document_update_immediately_changes_recall_eligibility(candidates):
    memory = candidates.add("The amber map is mine.")
    with candidates.database.transaction(candidates.principal) as conn:
        for kind, admitted in (("agent_said", False), ("reported_fact", True), ("proposal_offered", False)):
            changed = copy.deepcopy(memory)
            changed["claim_kind"] = kind
            row = conn.execute("UPDATE memory_assertions SET document=%s WHERE tenant_id=%s AND owner_id=%s "
                               "AND brain_id=%s AND id=%s RETURNING recall_non_speech",
                               (Jsonb(changed), *candidates.params, memory["memory_id"])).fetchone()
            assert row["recall_non_speech"] is admitted
            rows, _ = lexical_rows(conn, candidates.params, candidates.target, "amber map", limit=4, include_speech=False)
            assert bool(rows) is admitted
        conn.execute("UPDATE memory_assertions SET document=NULL,search_text='' WHERE tenant_id=%s AND owner_id=%s "
                     "AND brain_id=%s AND id=%s", (*candidates.params, memory["memory_id"]))
        for include_speech in (True, False):
            assert lexical_rows(conn, candidates.params, candidates.target, "amber map", limit=4,
                                include_speech=include_speech) == ([], False)


def test_eligibility_upgrade_is_atomic_and_preserves_records(monkeypatch):
    settings = Settings.from_env()
    admin = settings.migration_database_url or settings.database_url
    namespace = "eligibility_upgrade_" + uid().replace("-", "")
    database = Database(make_conninfo(admin, options="-c search_path=" + namespace + ",public"))
    principal, brain = Principal(uid(), uid()), uid()
    current = tuple(item for item in MIGRATIONS if item[0] < "032_")
    old = tuple(item for item in current if item[0] < "031_")
    monkeypatch.setattr(storage, "MIGRATIONS", current)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
        conn.execute(sql.SQL("CREATE TABLE {}.memory_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
                     .format(sql.Identifier(namespace)))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", old)
            database.migrate()
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_brains(id,tenant_id,owner_id,name) VALUES(%s,%s,%s,'upgrade')",
                         (brain, principal.tenant_id, principal.principal_id))
            conn.execute("INSERT INTO memory_assertions(tenant_id,owner_id,brain_id,id,revision,document,search_text) "
                         "SELECT %s,%s,%s,n::text,1,CASE WHEN n %% 3=0 THEN NULL ELSE "
                         "jsonb_build_object('statement','assistant amber '||n,'derivation',jsonb_build_object('method','direct_capture')) END, "
                         "'amber '||n FROM generate_series(1,300) n", (principal.tenant_id, principal.principal_id, brain))
            before = conn.execute("SELECT to_jsonb(a) AS row FROM memory_assertions a ORDER BY id").fetchall()
        with monkeypatch.context() as patch:
            patch.setattr(storage, "MIGRATIONS", (*old, (current[-1][0], current[-1][1] + b"\nSELECT 1/0;")))
            with pytest.raises(psycopg.errors.DivisionByZero):
                database.migrate()
        with database.transaction(principal) as conn:
            assert conn.execute("SELECT to_jsonb(a) AS row FROM memory_assertions a ORDER BY id").fetchall() == before
            assert conn.execute("SELECT count(*) AS n FROM memory_migrations WHERE name=%s", (current[-1][0],)).fetchone()["n"] == 0
        database.migrate()
        database.migrate()
        assert database.check_compatibility(require_current=True)["pending_count"] == 0
        with database.transaction(principal) as conn:
            assert conn.execute("SELECT to_jsonb(a)-'recall_non_speech' AS row FROM memory_assertions a ORDER BY id").fetchall() == before
            assert conn.execute("SELECT count(*) AS n FROM memory_assertions a WHERE recall_non_speech IS DISTINCT FROM ("
                                + ORIGINAL.format(alias="a") + ")").fetchone()["n"] == 0
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
