"""Recall of a memory with a short view (a recall summary) and retention priority, as older runtimes stored them.

Background learning, which wrote and verified such summaries, was removed; recall still reads the ones stored and
erasure still removes them. The memory here is the one the runtime at 2600219b published (fixture
``legacy_cognition/recall_summary_document.json``).
"""
import copy
import json
from types import SimpleNamespace

import pytest
from legacy_cognition import FIXTURES
from test_cognition import STAMP, event, prepare_payload, request, scope, state, working

from membrain import cognition
from membrain.context_views import recall_context_view
from membrain.contracts import validate

TEXT = ("Grandma lit a lantern during power cuts and let me sort buttons into a tea tin beside her. "
        "She used the tin with the faded yellow lid and kept the lantern on the low shelf. "
        "That little ritual made the frightening dark house feel safe.")
SHORT = "The user reported that Grandma's power-cut ritual made the dark house feel safe."


def memory_case():
    """The source and the memory with a verified short view that the runtime at 2600219b published from it."""
    data = json.loads((FIXTURES / "recall_summary_document.json").read_text(encoding="utf-8"))
    return copy.deepcopy(data["source"]), copy.deepcopy(data["memory"])


def read(source, memory, query="Grandma safe", *, at="2036-10-22T12:00:00Z", **options):
    return cognition.recall(scope(), request(query, **options),
                            [memory, *cognition.extract_event(source)], [source], state(), access_at=at)


def visible(result):
    return [item for item in result["items"] if item["display_mode"] != "do_not_surface"]


def test_old_memory_uses_short_view_without_erasing_full_record_or_duplicate_literal():
    source, memory = memory_case()
    original = copy.deepcopy((source, memory))
    recalled = read(source, memory)
    assert len(visible(recalled)) == 1
    item = visible(recalled)[0]
    assert item["memory"] == memory and item["presentation"]["level"] == "summary"
    assert recall_context_view(recalled)["memories"][0]["statement"] == SHORT
    assert "yellow lid" not in recalled["model_context"]
    assert any(item.get("deferred_by", {}).get("memory_id") == memory["memory_id"] for item in recalled["items"])
    assert (source, memory) == original
    validate("RecallResult", recalled)
    packet = cognition.prepare(scope(), prepare_payload(), working(), recalled, state())
    assert "yellow lid" not in packet["model_context"] and SHORT in packet["model_context"]


@pytest.mark.parametrize("cue", ["Grandma lantern", "Grandma shelf", "Grandma yellow lid"])
def test_specific_cues_recover_detail_including_source_detail_not_in_cue_list(cue):
    source, memory = memory_case()
    recalled = read(source, memory, cue)
    assert any(item.get("presentation", {}).get("level") == "full" for item in visible(recalled))
    assert "yellow lid" in recalled["model_context"]
    assert all("deferred_by" not in item for item in recalled["items"])


@pytest.mark.parametrize("options", [
    {"intent": "episode"}, {"intent": "exact_quote"},
    {"intent": "cue_recovery", "evidence_cutoff": {"mode": "through_sequence", "through_sequence": 1}},
    {"detail_level": "full"},
])
def test_explicit_expansion_preserves_the_original_details_at_old_age(options):
    source, memory = memory_case()
    recalled = read(source, memory, **options)
    assert "yellow lid" in recalled["model_context"]
    assert next(item for item in recalled["items"] if item["memory"]["memory_id"] == memory["memory_id"])["presentation"]["level"] == "full"


def test_current_memory_remains_detailed_and_short_view_reduces_only_model_context():
    source, memory = memory_case()
    fresh, aged = read(source, memory, at=STAMP), read(source, memory)
    assert "yellow lid" in fresh["model_context"] and "yellow lid" not in aged["model_context"]
    assert aged["usage"]["context_tokens"] < fresh["usage"]["context_tokens"]
    assert aged["usage"]["model_calls"] == fresh["usage"]["model_calls"] == 0
    assert next(item["memory"] for item in aged["items"] if item["memory"]["memory_id"] == memory["memory_id"]) == memory


@pytest.mark.parametrize("broken", ["source_hash", "deleted", "superseded", "scope"])
def test_summary_cannot_bypass_the_original_evidence_guards(broken):
    source, memory = memory_case()
    current = state()
    sources = [source]
    if broken == "source_hash":
        source["content_sha256"] = "0" * 64
    elif broken == "deleted":
        sources = []
    elif broken == "superseded":
        current["superseded_evidence_refs"] = memory["evidence_refs"]
    else:
        memory["scope"]["brain_id"] = "other-brain"
    result = cognition.recall(scope(), request("Grandma safe"), [memory], sources, current,
                              access_at="2036-10-22T12:00:00Z")
    assert not result["items"] and SHORT not in result["model_context"]


def test_a_summary_for_another_source_cannot_hide_the_original_episode():
    source, memory = memory_case()
    other = event("Grandma's yellow lid belonged to a different episode.", 2)
    recalled = cognition.recall(scope(), request("Grandma safe"),
                                [memory, *cognition.extract_event(other)], [source, other], state(2),
                                access_at="2036-10-22T12:00:00Z")
    assert "different episode" in recalled["model_context"]


def test_pinned_detail_is_not_deferred_and_stable_budget_keeps_the_summary_with_its_raw_sources():
    source, memory = memory_case()
    memory["dynamics"]["user_pinned"] = True
    assert "yellow lid" in read(source, memory)["model_context"]
    memory["dynamics"]["user_pinned"] = False
    result = read(source, memory)
    tiny = read(source, memory, budget={**request()["budget"], "max_context_tokens": result["usage"]["context_tokens"] - 1})
    assert not any(item.get("deferred_by") for item in tiny["items"])
    assert tiny["usage"]["context_tokens"] <= result["usage"]["context_tokens"] - 1


def test_external_use_can_keep_old_details_active_without_rewriting_the_memory():
    source, memory = memory_case()
    original = copy.deepcopy(memory)
    current = state(access_usage={(memory["memory_id"], memory["revision"]): {
        "external_uses": 20, "successes": 20, "failures": 0,
        "last_reinforcement_at": "2036-10-22T12:00:00Z"}})
    result = cognition.recall(scope(), request("Grandma safe"), [memory], [source], current,
                              access_at="2036-10-22T12:00:00Z")
    assert result["items"][0]["presentation"]["level"] == "full"
    assert "yellow lid" in result["model_context"] and memory == original


@pytest.mark.parametrize("character", ['"', '\\', '\n', '🙂'])
def test_host_budget_accounts_for_instructions_and_escaped_memory_before_retrieval(character):
    from membrain.runtime import BrainRuntime, RuntimePolicy

    runtime = BrainRuntime(SimpleNamespace(brain_id="budget-test"), lambda _: pytest.fail("No model call"),
                           policy=RuntimePolicy(memory_context_tokens=16000, max_input_tokens=24000))
    budget = runtime._memory_budget("turn", "Continue the task")
    context = json.dumps({"text": character * (budget // 8)}, ensure_ascii=False)
    assert len(context.encode()) <= budget < 16000
    prompt = runtime._prompt("turn", "Continue the task", {"model_context": context})
    assert prompt.input_tokens_estimate <= 24000
