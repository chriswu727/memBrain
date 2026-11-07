import pytest
from psycopg.types.json import Jsonb
from test_candidates import candidates as candidates
from test_candidates import key, query_vector

from membrain.candidates import _han_majority, _interleave, _other_script_clause


def test_other_script_candidate_already_in_global_pool_is_promoted_once():
    def row(name):
        return {"document": {"memory_id": name, "revision": 1}}

    primary = [row(f"primary-{i}") for i in range(9)] + [row("target")]
    result = _interleave(primary, [row("target")])
    names = [item["document"]["memory_id"] for item in result]
    assert names[:4] == ["primary-0", "primary-1", "primary-2", "target"]
    assert len(names) == len(set(names)) == len(primary)
    assert [name for name in names if name != "target"] == [f"primary-{i}" for i in range(9)]


@pytest.mark.integration
@pytest.mark.parametrize("query,primary_text,target_text", [
    ("zygomatic", "Routine office parcel", "护照放在抽屉里"),
    ("颧骨", "普通办公包裹", "The passport is in the drawer"),
])
def test_cross_script_candidate_survives_small_budget_when_already_globally_admitted(
        candidates, query, primary_text, target_text):
    for number in range(20):
        memory = candidates.add(f"{primary_text} {number}")
        candidates.embed(memory, [1.0, (number + 1) * .05, 0.0])
    target = candidates.add(target_text)
    candidates.embed(target, [1.0, .475, 0.0])

    _, state = candidates.query(query, budget=2048, query_embedding=query_vector())

    assert key(target) in state["candidate_versions"]
    assert any(signal["method"] == "vector" for signal in state["rank_signals"][key(target)])


@pytest.mark.integration
@pytest.mark.parametrize("text,expected", [
    ("护照在抽屉", True),
    ("我用Apple电脑写下明天的计划", True),
    ("The receipt from 京都 is in the drawer", False),
    ("Αθήνα 汉", False),
    ("Москва 汉", False),
    ("漢A", False),
    ("漢字A", True),
    ("1234!? 🐋", False),
    ("é 東京", True),
])
@pytest.mark.parametrize("query", ["Where is the parcel from 京都?", "我的包裹在哪里"])
def test_query_and_database_script_counts_agree_without_speaker_metadata(candidates, text, expected, query):
    assert _han_majority(text) is expected
    document = {"derivation": {"method": "direct_capture"}, "evidence_refs": [
        {"span": {"start": 100, "end": 100 + len(text), "unit": "unicode_code_point"}}]}
    statement = "user a-very-long-speaker-identifier-中文 (direct_statement): " + text
    clause, params = _other_script_clause(query)

    with candidates.database.transaction(candidates.principal) as conn:
        rows = conn.execute(
            "SELECT 1 FROM (SELECT %s::jsonb AS document,%s::text AS search_text,NULL::boolean AS source_han_majority) a WHERE true " + clause,
            (Jsonb(document), statement, *params),
        ).fetchall()

    assert bool(rows) is (expected != _han_majority(query))


@pytest.mark.integration
@pytest.mark.parametrize("query,primary_text,target_text", [
    ("zygomatic", "Routine office receipt from 京都 stationery", "护照放在抽屉里"),
    ("zygomatic diagnostic concerning 大阪", "Routine office parcel from 京都", "护照放在抽屉里"),
    ("颧骨的位置在哪里", "普通办公包裹来自Apple商店", "The passport is in the drawer beside 京都 postcards"),
])
def test_incidental_foreign_names_do_not_fill_the_other_script_pool(
        candidates, query, primary_text, target_text):
    for number in range(20):
        memory = candidates.add(f"{primary_text} {number}")
        candidates.embed(memory, [1.0, (number + 1) * .01, 0.0])
    target = candidates.add(target_text)
    candidates.embed(target, [1.0, .3, 0.0])

    _, state = candidates.query(query, budget=2048, query_embedding=query_vector())

    assert key(target) in state["candidate_versions"]
    assert len(state["candidate_versions"]) <= 4
    assert any(signal["method"] == "vector" for signal in state["rank_signals"][key(target)])
