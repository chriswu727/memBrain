import copy
import json

import pytest
from test_cognition import event as old_event
from test_cognition import request, scope, state

from membrain import cognition
from membrain.context_views import memory_content
from membrain.lexical_candidates import LexicalScorer

BLACKOUT = (
    "When our power went out, Grandma would light a lantern and put buttons in a tea tin "
    "for us to sort."
)
CARD = (
    "I'm writing Grandma a thank-you card. I don't want it to be generic. "
    "Is there something I've told you about her that I could use as a starting point?"
)


def event(*args, **kwargs):
    source = old_event(*args, **kwargs)
    source["segmentation_rule_version"] = cognition.RULE_VERSION
    source["utterance_segments"] = cognition.classify_segments(source["observed"]["content"])
    return source


def legacy_blackout():
    source = event(BLACKOUT + " Could you help me write a caption?")
    source.pop("segmentation_rule_version")
    source["utterance_segments"] = cognition.classify_segments(
        source["observed"]["content"], rule_version="literal-episodes-v2"
    )
    return source


def test_contractions_and_source_labels_do_not_create_spurious_search_terms():
    words, _, _ = cognition._terms("I'm writing Grandma’s card; I've said I don't want it generic.")
    assert {"grandma", "writ", "card", "not", "generic"} <= words
    assert not words & {"m", "ve", "don", "t", "s", "i"}
    assert cognition._terms("don't")[0] == {"not"}
    assert cognition._terms("can't")[0] == {"not"}


def test_distinctive_family_cue_outranks_repeated_generic_phrasing():
    distractors = [
        f"I don't want it generic. I'm writing a friendly note about project {index}."
        for index in range(40)
    ]
    texts = distractors + [BLACKOUT]
    scorer = LexicalScorer(CARD, texts)
    assert scorer(CARD, BLACKOUT) > max(scorer(CARD, text) for text in distractors)
    assert scorer(CARD, "The fountain is dry.") == 0
    assert LexicalScorer("not unless", ["not unless"])("not unless", "not unless") == 1


@pytest.mark.parametrize("intent", ["explore", "cue_recovery"])
def test_assistant_caption_is_not_available_as_independent_personal_recollection(intent):
    user = legacy_blackout()
    assistant = event("Your grandma put the lantern on the kitchen table.", 2, "assistant")
    memories = cognition.extract_event(user) + cognition.extract_event(assistant)
    quoted = copy.deepcopy(memories[-1])
    quoted.update(
        memory_id="assistant-caption-summary",
        claim_kind="agent_said",
        epistemic_status="derived_inference",
        memory_kind="semantic",
    )
    memories.append(quoted)
    before = copy.deepcopy(memories)
    query = request(
        "Grandma lantern",
        intent=intent,
        evidence_cutoff={"mode": "through_sequence", "through_sequence": 2},
    )
    result = cognition.recall(
        scope(), query, memories, [user, assistant], state(2, candidate_total=len(memories))
    )
    assert result["items"]
    assert all(
        item["memory"]["evidence_refs"][0]["event_id"] == user["event_id"]
        for item in result["items"]
    )
    assert "kitchen" not in cognition.render_recall(result)
    exact = cognition.recall(
        scope(),
        request("lantern", intent="exact_quote"),
        memories,
        [user, assistant],
        state(2, candidate_total=len(memories)),
    )
    speech = [
        memory_content(item)
        for item in exact["items"]
        if item["memory"]["evidence_refs"][0]["event_id"] == assistant["event_id"]
    ]
    assert len(speech) == 2
    assert all(item["use"] == "assistant_speech_not_user_experience" for item in speech)
    assert memories == before
    json.loads(cognition.render_recall(exact))


def test_unindexed_generic_tail_uses_the_same_rank_scale_as_indexed_recollection():
    source = event(BLACKOUT)
    tail = event("I did not finish an unrelated errand.", 2)
    memory = cognition.extract_event(source)[0]
    key = (memory["memory_id"], memory["revision"])
    current = state(
        2,
        indexed_sequence=1,
        candidate_versions=[key],
        rank_signals={
            key: [
                {
                    "method": "keyword",
                    "score": 1 / 61,
                    "meaning": "ranking_only_not_probability",
                    "model_or_index_version": "bounded-idf-passage-v1",
                }
            ]
        },
    )
    result = cognition.recall(
        scope(), request("Grandma not generic"), [memory], [source, tail], current
    )
    assert result["items"][0]["memory"]["memory_id"] == memory["memory_id"]
    assert len(result["items"]) == 2
    assert result["items"][1]["retrieved_from"] == "unindexed_tail"


def test_legacy_recollection_exposes_corrected_source_act_without_changing_stored_literal():
    source = legacy_blackout()
    memories = cognition.extract_event(source)
    original = copy.deepcopy(memories)
    result = cognition.recall(
        scope(),
        request("Grandma lantern"),
        memories,
        [source],
        state(candidate_total=len(memories)),
    )
    item = next(item for item in result["items"] if "Grandma would" in item["memory"]["statement"])
    assert "(inquiry)" in item["memory"]["statement"]
    assert item["source_act"] == {"act": "direct_statement", "rule_version": cognition.RULE_VERSION}
    assert memory_content(item)["source_act"] == item["source_act"]
    assert memories == original
