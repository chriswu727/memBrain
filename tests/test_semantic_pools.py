import math

import pytest
from test_candidates import SPACE
from test_candidates import candidates as candidates

from membrain.candidates import _semantic_pools

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("query,other_han", [("parcel", True), ("包裹", False)])
@pytest.mark.parametrize("projected", [True, False])
def test_exact_pools_keep_independent_limits_ties_and_best_passage(candidates, query, other_han, projected):
    expected = []
    for index in range(12):
        han = bool(index % 2)
        memory = candidates.add(("普通包裹记录" if han else "Ordinary parcel record ") + str(index))
        offset = (index // 2 + 1) / 10
        candidates.embed(memory, [1, offset, 0])
        expected.append((1 - 1 / math.sqrt(1 + offset * offset), memory["memory_id"], han, None, None))
    passage = candidates.add("The distant archive contains a useful tail passage.")
    candidates.embed(passage, [0, 1, 0])
    with candidates.database.transaction(candidates.principal) as conn:
        conn.execute(
            "INSERT INTO memory_embedding_passages(tenant_id,owner_id,brain_id,memory_id,memory_revision,"
            "model,model_version,passage_index,start_offset,end_offset,embedding) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,0,5,15,'[1,0,0]'::vector)",
            (*candidates.params, passage["memory_id"], passage["revision"], SPACE.model, SPACE.model_version),
        )
        if not projected:
            conn.execute("UPDATE memory_assertions SET source_han_majority=NULL "
                         "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s", candidates.params)
        pools = _semantic_pools(conn, candidates.params, candidates.target, query, "[1,0,0]", SPACE, 4, 2,
                                include_speech=False)
    expected.append((0, passage["memory_id"], False, 5, 15))
    ordered = sorted(expected)
    for name, wanted in (("primary", ordered[:5]),
                         ("other", [row for row in ordered if row[2] is other_han][:3])):
        rows = pools[name]
        assert [row["document"]["memory_id"] for row in rows] == [row[1] for row in wanted]
        assert [row["distance"] for row in rows] == pytest.approx([row[0] for row in wanted], abs=1e-6)
        assert [(row["start_offset"], row["end_offset"]) for row in rows] == [(row[3], row[4]) for row in wanted]
