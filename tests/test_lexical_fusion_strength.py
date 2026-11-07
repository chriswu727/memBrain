import pytest
from test_candidates import candidates as candidates
from test_candidates import key, query_vector

from membrain.candidates import _direct_candidates


@pytest.mark.parametrize("strength,winner", [(.005, "meaning"), (1.0, "literal")])
def test_fusion_preserves_lexical_strength_instead_of_promoting_every_local_maximum(strength, winner):
    ranked = _direct_candidates(
        {"keyword": [("literal", 1)], "vector": [("meaning", 1), ("literal", 1)]},
        {"keyword": "literal-test", "vector": "vector-test"}, {("literal", 1): strength}, limit=2)
    assert ranked[0]["memory_id"] == winner


@pytest.mark.integration
def test_weak_partial_word_matches_do_not_displace_the_best_semantic_source(candidates):
    for number in range(20):
        memory = candidates.add(f"A marble ornament on display number {number}.")
        candidates.embed(memory, [1.0, (number + 1) * .05, 0.0])
    target = candidates.add("出国用的证件收在柜子里。")
    candidates.embed(target, [1.0, 0.0, 0.0])

    _, state = candidates.query("passport visa consulate marble", budget=2048, query_embedding=query_vector())

    assert key(target) in state["candidate_versions"]
    assert any(signal['method'] == 'vector' for signal in state['rank_signals'][key(target)])
