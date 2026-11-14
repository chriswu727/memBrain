import copy
import json

import pytest
from test_cognition import STAMP, event, prepare_payload, request, scope, state, working

from membrain import cognition
from membrain.contracts import validate

CONDITION = {
    "op": "holds", "subject_ref": "user",
    "predicate_ref": {"id": "core.activity", "version": 1},
    "value": {"type": "concept", "id": "activity:exam_preparation"},
}
UNBOUNDED = {"kind": "interval", "start": {"kind": "unbounded"}, "end": {"kind": "unbounded"}}


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(cognition, "now", lambda: STAMP)


def observation(source, *, polarity="positive", validity=None):
    return {
        "observation_id": f"observation-{source['sequence']}",
        "subject_ref": CONDITION["subject_ref"],
        "predicate_ref": copy.deepcopy(CONDITION["predicate_ref"]),
        "value": copy.deepcopy(CONDITION["value"]), "polarity": polarity,
        "valid_during": copy.deepcopy(UNBOUNDED if validity is None else validity),
        "evidence_refs": cognition.extract_event(source)[0]["evidence_refs"],
    }


def case(kind="positive"):
    original = event("备考期间，我希望回答简短。")
    memory = cognition.extract_event(original)[0]
    memory["memory_kind"] = "semantic"
    memory["conditions"] = copy.deepcopy(CONDITION)
    memory["valid_during"] = copy.deepcopy(UNBOUNDED)
    sources, observations = [original], []
    if kind != "missing":
        context_source = event("我现在没有备考。" if kind == "negative" else "我正在备考。", 2)
        sources.append(context_source)
        validity = copy.deepcopy(UNBOUNDED)
        if kind == "expired":
            validity["end"] = {"kind": "instant", "at": STAMP}
        elif kind == "future":
            validity["start"] = {"kind": "instant", "at": "2026-10-23T00:00:00Z"}
        elif kind == "unknown_time":
            validity = {"kind": "unknown"}
        observations.append(observation(
            context_source, polarity="negative" if kind == "negative" else "positive", validity=validity,
        ))
        if kind == "conflict":
            contrary = event("我现在没有备考。", 3)
            sources.append(contrary)
            observations.append(observation(contrary, polarity="negative"))
    current = state(
        max(source["sequence"] for source in sources), context_observations=observations,
        working_event_metadata={source["event_id"]: source for source in sources},
    )
    return memory, sources, current


def recall(memory, sources, current, **changes):
    return cognition.recall(scope(), request("回答简短", **changes), [memory], sources, current)


def memory_blocks(packet):
    return [(block, json.loads(block["text"])) for block in packet["blocks"]
            if block["section"] in {"relevant_memory", "conditional_memory"}]


def assert_conditional(packet, memory, value, conflict=False):
    blocks = memory_blocks(packet)
    assert len(blocks) == 1
    block, content = blocks[0]
    assert block["section"] == "conditional_memory"
    assert content["statement"] == memory["statement"]
    assert content["use"] == "conditional_memory_not_current_rule"
    assert content["applicability"]["value"] == value
    assert content["applicability"]["conflict"] is conflict
    assert content["conditions"] == memory["conditions"]
    assert memory["statement"] in cognition.render_context(packet)
    assert "conditional_memory_not_current_rule" in cognition.render_context(packet)
    assert packet["usage"]["context_tokens"] == cognition.estimate_tokens(cognition.render_context(packet))
    validate("ContextPacket", packet)


def test_legacy_string_context_cannot_promote_an_untyped_condition_to_current_rule():
    memory, sources, current = case("missing")
    memory["conditions"] = {"op": "eq", "key": "activity", "value": "exam_preparation"}
    current["situation_context"] = {"activity": "exam_preparation"}
    recalled = recall(memory, sources, current)
    applicability = recalled["items"][0]["applicability"]
    assert applicability["value"] == "unknown"
    assert "legacy_condition" in applicability["reasons"]
    packet = cognition.prepare(scope(), prepare_payload(), working(), recalled, current)
    assert_conditional(packet, memory, "unknown")


def test_context_evidence_does_not_replace_a_missing_historical_memory_source():
    memory, sources, current = case()
    current["working_event_metadata"].pop(sources[0]["event_id"])
    recalled = recall(memory, sources[1:], current)
    assert recalled["items"] == []
    assert memory["statement"] not in json.dumps(recalled, ensure_ascii=False)


@pytest.mark.parametrize("kind", ["positive", "negative", "conflict", "missing"])
def test_context_observations_no_longer_decide_a_condition(kind):
    """Context observations came only from the orientation of the removed runtime mode. Recall no longer reads any
    in its state: a conditional memory is shown as conditional data with unknown applicability, whatever is there."""
    memory, sources, current = case(kind)
    recalled = recall(memory, sources, current)
    applicability = recalled["items"][0]["applicability"]
    assert applicability["value"] == "unknown" and applicability["supporting_observation_ids"] == []
    packet = cognition.prepare(scope(), prepare_payload(), working(), recalled, current)
    assert_conditional(packet, memory, "unknown")
