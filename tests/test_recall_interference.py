import pytest
from test_candidates import candidates as candidates
from test_candidates import key, query_vector

pytestmark = pytest.mark.integration


def test_repeated_reports_do_not_fill_all_semantic_admission_slots(candidates):
    repeated = []
    for number in range(28):
        memory = candidates.add(f"我在河畔活动室整理了{number + 100}张照片，放进绿色相册。")
        candidates.embed(memory, [1.0, (number + 1) * .005, 0.0])
        repeated.append(memory)
    distinct = candidates.add("我的雨伞放在玄关右边的柜子里。")
    candidates.embed(distinct, [1.0, .15, 0.0])

    memories, state = candidates.query("zygomatic", budget=8192, query_embedding=query_vector())

    assert key(distinct) in state["candidate_versions"][:10]
    assert len(state["candidate_versions"]) <= 16
    assert {key(memory) for memory in repeated[:2]} <= set(state["candidate_versions"])
    with candidates.database.transaction(candidates.principal) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_assertions WHERE brain_id=%s",
                            (candidates.brain_id,)).fetchone()["n"] == 29
    assert all(memory["evidence_refs"] for memory in memories)


def test_explicit_number_still_recovers_the_exact_report(candidates):
    target = None
    for number in range(28):
        memory = candidates.add(f"Shipment {number + 100} was delivered to the riverside loading dock on Tuesday.")
        candidates.embed(memory, [1.0, (number + 1) * .005, 0.0])
        if number == 25:
            target = memory

    _, state = candidates.query("shipment 125", budget=4096, query_embedding=query_vector())

    assert key(target) in state["candidate_versions"]
    assert any(signal["method"] == "keyword" for signal in state["rank_signals"][key(target)])
