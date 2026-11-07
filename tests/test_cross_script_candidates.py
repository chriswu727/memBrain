import pytest
from test_candidates import candidates as candidates
from test_candidates import key, query_vector

from membrain.candidates import _interleave


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
