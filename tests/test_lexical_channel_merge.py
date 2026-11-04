import copy

import pytest
from psycopg.types.json import Jsonb
from test_candidates import Candidates, key
from test_candidates import candidates as candidates

from membrain import cognition
from membrain.candidates import _eligible, _scope_clause
from membrain.lexical_candidates import (
    MAX_QUERY_TERMS,
    MAX_TERM_LENGTH,
    _prefixes,
    historical_support_filter,
    lexical_rows,
)
from membrain.service import _vector


def _separate_channels(conn, params, target, text, *, limit, through_sequence=None, excluded_versions=(),
                       independent_of_event_ids=()):
    clause, scope_params = _scope_clause("a", target)
    where = _eligible() + clause
    where += "AND a.embedding_model='lexical-feature-hash' AND a.embedding_version='v1-d256-blake2s' "
    support, support_params = historical_support_filter(independent_of_event_ids)
    where += support
    values = (*params, *scope_params, *support_params)
    if excluded_versions:
        where += "AND (a.id,a.revision) NOT IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) "
        values += ([key[0] for key in excluded_versions], [key[1] for key in excluded_versions])
    if through_sequence is not None:
        where += (
            "AND NOT EXISTS (SELECT 1 FROM memory_events future WHERE future.tenant_id=a.tenant_id "
            "AND future.owner_id=a.owner_id AND future.brain_id=a.brain_id AND future.id=ANY(a.event_ids) "
            "AND future.is_current AND future.sequence>%s) "
        )
        values += (through_sequence,)
    select = "SELECT a.document,a.event_ids,a.is_current FROM memory_assertions a WHERE " + where
    order = "ORDER BY a.embedding <=> %s::vector NULLS LAST,a.id,a.revision LIMIT %s"
    vector = _vector(text)
    hashed = conn.execute(select + order, (*values, vector, limit + 1)).fetchall()
    words = sorted(cognition._terms(text)[0])
    terms = [word for word in words if len(word) <= MAX_TERM_LENGTH][:MAX_QUERY_TERMS]
    truncated = len(hashed) > limit or len(terms) != len(words)
    exact = []
    if terms:
        exact = conn.execute(select + "AND to_tsvector('simple',a.search_text) @@ to_tsquery('simple',%s) " + order,
                             (*values, " | ".join(_prefixes(terms)), vector, limit + 1)).fetchall()
        truncated |= len(exact) > limit
    unique = {}
    for row in exact[:limit] + hashed[:limit]:
        unique.setdefault(key(row["document"]), row)
    return list(unique.values()), truncated


@pytest.mark.integration
def test_merged_channels_match_independent_reads_with_all_filters_and_limits(candidates):
    first = candidates.add("The amber map belongs to Mara.")
    second = candidates.add("The green cup belongs to Leo.")
    candidates.add("The amber map is beside the silver lantern.")
    candidates.add("银杏树旁的小学有蓝色地图。")
    candidates.add("The amber map has another owner.", conversation="hidden", visibility="conversation")
    candidates.add("The amber map is on a private fork.", branch="fork")
    candidates.add("The amber map has been withdrawn.", lifecycle="dormant")
    foreign = Candidates(candidates.database)
    foreign.add("The amber map contains another person's secret.")
    queries = ["amber map", "银杏树", "missing", "label' | !('private'); --", "x" * 257,
               " ".join(f"word{number:04d}" for number in range(MAX_QUERY_TERMS + 1))]
    options = [{}, {"through_sequence": 1}, {"through_sequence": 0}, {"excluded_versions": [key(first)]},
               {"independent_of_event_ids": [first["evidence_refs"][0]["event_id"]]},
               {"through_sequence": 2, "excluded_versions": [key(second)],
                "independent_of_event_ids": [first["evidence_refs"][0]["event_id"]]}]
    with candidates.database.transaction(candidates.principal) as conn:
        for query in queries:
            for limit in (0, 1, 2, 16):
                for option in options:
                    actual = lexical_rows(conn, candidates.params, candidates.target, query, limit=limit, **option)
                    expected = _separate_channels(conn, candidates.params, candidates.target, query, limit=limit, **option)
                    assert actual == expected, (query, limit, option)


@pytest.mark.integration
def test_channel_overlap_preserves_sentinel_and_first_document(candidates):
    first = candidates.add("The amber map belongs to Mara.")
    alias = candidates.add("The amber map belongs to Leo.")
    duplicate = copy.deepcopy(alias)
    duplicate.update(memory_id=first["memory_id"], revision=first["revision"])
    with candidates.database.transaction(candidates.principal) as conn:
        conn.execute("UPDATE memory_assertions SET document=%s WHERE tenant_id=%s AND owner_id=%s "
                     "AND brain_id=%s AND id=%s AND revision=%s", (Jsonb(duplicate), *candidates.params, *key(alias)))
        for limit in (1, 2, 8):
            actual = lexical_rows(conn, candidates.params, candidates.target, "amber map", limit=limit)
            expected = _separate_channels(conn, candidates.params, candidates.target, "amber map", limit=limit)
            assert actual == expected
            assert len(actual[0]) == 1
            assert actual[1] is (limit == 1)


@pytest.mark.integration
def test_channel_merge_orders_null_distances_last_and_keeps_hash_only_rows(candidates):
    memories = [candidates.add(text) for text in (
        "The amber map belongs to Mara.", "The green cup belongs to Leo.", "The silver lantern is upstairs.")]
    with candidates.database.transaction(candidates.principal) as conn:
        conn.execute("UPDATE memory_assertions SET embedding=NULL WHERE tenant_id=%s AND owner_id=%s "
                     "AND brain_id=%s AND id=%s", (*candidates.params, memories[0]["memory_id"]))
        for query in ("amber map", "missing", "银杏树"):
            for limit in (1, 2, 3):
                assert lexical_rows(conn, candidates.params, candidates.target, query, limit=limit) == _separate_channels(
                    conn, candidates.params, candidates.target, query, limit=limit)
