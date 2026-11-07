import pytest
from psycopg.types.json import Jsonb
from test_candidates import candidates as candidates
from test_candidates import key, query_vector

pytestmark = pytest.mark.integration


def speech(candidates, text, kind, *, identifier=None):
    fields = {"memory_id": identifier} if identifier else {}
    if kind is not None:
        fields.update(claim_kind=kind, statement=text)
    memory = candidates.add(text, role="assistant", **fields)
    if kind is None:
        memory.pop("claim_kind", None)
        with candidates.database.transaction(candidates.principal) as conn:
            conn.execute("UPDATE memory_assertions SET document=%s "
                         "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s AND revision=%s",
                         (Jsonb(memory), *candidates.params, *key(memory)))
    return memory


@pytest.mark.parametrize("text", ["I always choose chamomile.", "我平时选择菊花茶。"])
@pytest.mark.parametrize("kind", [None, "agent_said", "proposal_offered", "commitment_expressed"])
def test_ineligible_speech_cannot_consume_semantic_or_cross_script_scan_budget(candidates, text, kind):
    owned = candidates.add(text)
    candidates.embed(owned, [1.0, 0.2, 0.0])
    assert key(owned) in candidates.query("zygomatic", budget=2048, query_embedding=query_vector())[1]["candidate_versions"]
    suggestions = []
    for _ in range(17):
        memory = speech(candidates, text, kind)
        suggestions.append(key(memory))
        candidates.embed(memory, [1.0, 0.0, 0.0])
    memories, state = candidates.query("zygomatic", budget=2048, query_embedding=query_vector(),
                                       cues=["Which beverage did you recommend?"])
    assert state["candidate_versions"] == [key(owned)]
    assert list(map(key, memories)) == [key(owned)]
    assert not state["candidate_truncated"]
    _, explicit = candidates.query("你推荐过什么？", budget=2048, query_embedding=query_vector())
    assert set(explicit["candidate_versions"]) & set(suggestions)
    assert len(explicit["candidate_versions"]) <= 4


@pytest.mark.parametrize("kind", ["agent_said", "proposal_offered", "commitment_expressed"])
def test_ineligible_speech_cannot_consume_lexical_scan_budget(candidates, kind):
    owned = candidates.add("I saw the turquoise lighthouse beside the harbour, the gardens, the mountains and the beach.")
    for index in range(17):
        speech(candidates, "turquoise lighthouse", kind, identifier=f"speech-{index:02}")
    memories, state = candidates.query("turquoise lighthouse", budget=2048)
    assert state["candidate_versions"] == [key(owned)]
    assert list(map(key, memories)) == [key(owned)]
    assert not state["candidate_truncated"]
    _, explicit = candidates.query("turquoise lighthouse", budget=2048, intent="exact_quote")
    assert any(identifier.startswith("speech-") for identifier, _ in explicit["candidate_versions"])


@pytest.mark.parametrize("route", ["association", "episode"])
def test_ineligible_speech_cannot_consume_neighborhood_budget(candidates, route):
    seed = candidates.add("turquoise lighthouse", memory_id="seed")
    owned = candidates.add("I always choose chamomile.", memory_id="zz-owned")
    suggestions = [speech(candidates, "Try peppermint.", "proposal_offered", identifier=f"aa-speech-{index}")
                   for index in range(5)]
    if route == "association":
        for memory in [owned, *suggestions]:
            candidates.edge(seed, memory)
    else:
        with candidates.database.transaction(candidates.principal) as conn:
            conn.execute("INSERT INTO memory_episodes(tenant_id,owner_id,brain_id,id,revision,conversation_id,branch_id,state,document) "
                         "VALUES(%s,%s,%s,'episode',1,'current','main','closed','{}')", candidates.params)
            for position, memory in enumerate([seed, owned, *suggestions]):
                conn.execute("INSERT INTO memory_episode_members(tenant_id,owner_id,brain_id,episode_id,episode_revision,"
                             "memory_id,memory_revision,role,position) VALUES(%s,%s,%s,'episode',1,%s,%s,'fragment',%s)",
                             (*candidates.params, *key(memory), position))
    memories, state = candidates.query("turquoise lighthouse", budget=2048)
    assert set(state["candidate_versions"]) == {key(seed), key(owned)}
    assert set(map(key, memories)) == {key(seed), key(owned)}
    assert {signal["method"] for signal in state["rank_signals"][key(owned)]} == {"association"}
