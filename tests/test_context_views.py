import copy
import json

import pytest
from test_belief_recall import recall, relation, scenario
from test_cognition import STAMP, budget, event, prepare_payload, request, scope, state, working

from membrain import cognition
from membrain.belief_resolution import factor_relations, relation_assessments
from membrain.context_views import (
    context_view,
    reasoning_context_view,
    recall_context_view,
    serialized,
)
from membrain.contracts import validate
from membrain.helpers import DomainError


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(cognition, "now", lambda: STAMP)


def test_compact_views_intern_certificates_and_keep_inspectable_versions():
    sources, memories, current = scenario(kind="exception")
    result = recall(sources, memories, current)
    assert len(result["belief_relations"]) == 1
    assert all("relations" not in item["belief_resolution"] for item in result["items"])
    assert all(item["memory"] in memories for item in result["items"])
    view = recall_context_view(result)
    assert len(view["relations"]) == 1
    for memory in view["memories"]:
        version = view["memory_versions"][memory["memory_ref"]]
        assert any(value["memory_id"] == version["memory_id"] and value["revision"] == version["revision"]
                   for value in memories)
        assert all(reference in view["sources"] for reference in memory["sources"])
    certificate = next(iter(view["relations"].values()))
    assert certificate["source"] in view["memory_versions"]
    assert all(target in view["memory_versions"] for target in certificate["targets"])
    assert certificate["conditions"] == current["belief_relations"][0]["conditions"]
    assert certificate["valid_during"] == current["belief_relations"][0]["valid_during"]
    assert "source_content_sha256" not in cognition.render_recall(result)
    assert "principal_binding_id" not in cognition.render_recall(result)
    assert result["usage"]["context_tokens"] == len(cognition.render_recall(result).encode())
    assert len(cognition.render_recall(result).encode()) < cognition.estimate_tokens(result)
    validate("RecallResult", result)


def test_factoring_historical_inline_certificates_preserves_exact_model_budget():
    sources, memories, current = scenario()
    result = recall(sources, memories, current)
    inline = copy.deepcopy(result)
    for item in inline["items"]:
        resolution = item["belief_resolution"]
        resolution["relations"] = relation_assessments(resolution, inline["belief_relations"])
        resolution.pop("relation_refs")
        resolution.pop("evidence_refs")
    inline.pop("belief_relations")
    validate("RecallResult", inline)
    before = cognition.render_recall(inline)
    assert before == cognition.render_recall(result)
    factor_relations(inline)
    assert cognition.render_recall(inline) == before


def test_prepare_relation_certificate_is_once_and_source_ids_are_resolvable():
    sources, memories, current = scenario()
    recalled = recall(sources, memories, current)
    packet = cognition.prepare(scope(), prepare_payload(), working(), recalled, current)
    view = context_view(packet)
    assert len(view["relations"]) == 1
    for block in view["blocks"]:
        assert all(identifier in view["sources"] for identifier in block["sources"])
    for block in packet["blocks"]:
        content = json.loads(block["text"])
        assert "relations" not in content.get("belief_resolution", {})
    assert packet["usage"]["context_tokens"] == len(cognition.render_context(packet).encode())


def test_literal_old_preference_remains_history_while_current_rule_is_conditional():
    source = event("My old preference was detailed responses.")
    literal = cognition.extract_event(source)[0]
    semantic = copy.deepcopy(literal)
    semantic.update(memory_id="semantic-rule", memory_kind="semantic", conditions={"op": "unresolved", "label": "silver"},
                    valid_during={"kind": "unknown"})
    recalled = cognition.recall(scope(), request("preference"), [literal, semantic], [source], state())
    packet = cognition.prepare(scope(), prepare_payload(), working(), recalled, state())
    contents = [block["content"] for block in context_view(packet)["blocks"]
                if block["section"] in {"relevant_memory", "conditional_memory"}]
    assert {content["use"] for content in contents} == {
        "historical_report_not_current_rule", "conditional_memory_not_current_rule"}
    assert any(content.get("conditions") == {"op": "unresolved", "label": "silver"} for content in contents)


def test_independent_small_memory_survives_oversized_connected_group():
    sources, memories, current = scenario()
    memories[1]["statement"] *= 1000
    current["belief_relations"] = [relation(memories[1], memories[:1])]
    standalone = event("routine independent observation", 3)
    sources.append(standalone)
    memories.append(cognition.extract_event(standalone)[0])
    current.update(durable_sequence=3, indexed_sequence=3)
    current["working_event_metadata"][standalone["event_id"]] = standalone
    recalled = recall(sources, memories, current, budget={**request()["budget"], "max_context_tokens": 3000})
    assert [item["memory"]["memory_id"] for item in recalled["items"]] == [memories[-1]["memory_id"]]
    assert recalled["belief_relations"] == []
    assert recalled["usage"]["context_tokens"] <= 3000


def test_missing_relation_certificate_fails_closed():
    sources, memories, current = scenario()
    result = recall(sources, memories, current)
    result["belief_relations"] = []
    with pytest.raises(DomainError, match="certificate is unavailable"):
        recall_context_view(result)


def test_arbitrary_working_value_is_preserved_without_interpreting_embedded_metadata():
    value = {"evidence_refs": ["this is user data"], "registry_fingerprint": "literal value",
             "belief_resolution": {"user_authored": True}, "memory_version": "plain text"}
    packet = {"blocks": [{"section": "working_state", "text": json.dumps({"value": value}), "evidence_refs": []}]}
    assert context_view(packet)["blocks"][0]["content"]["value"] == value


def test_reasoner_projection_keeps_decision_ids_and_compacts_shared_relations():
    sources, memories, current = scenario()
    result = recall(sources, memories, current)
    candidates = []
    for item in result["items"]:
        resolution = copy.deepcopy(item["belief_resolution"])
        resolution["relations"] = relation_assessments(resolution, result["belief_relations"])
        resolution.pop("relation_refs")
        candidates.append({**item["memory"], "belief_resolution": resolution})
    view = reasoning_context_view([], candidates)
    assert [value["memory_id"] for value in view["candidates"]] == [item["memory"]["memory_id"] for item in result["items"]]
    assert len(view["relations"]) == 1
    assert all(reference in view["sources"] for candidate in view["candidates"] for reference in candidate["evidence_refs"])


@pytest.mark.parametrize("start,end,value", [
    ("2026-10-23T00:00:00Z", None, "false"),
    (None, "2026-10-20T00:00:00Z", "false"),
    ("2026-10-20T00:00:00Z", "2026-10-23T00:00:00Z", "true"),
])
def test_legacy_semantic_valid_time_cannot_bypass_current_rule_guard(start, end, value):
    source = event("My preference is concise answers.")
    memory = cognition.extract_event(source)[0]
    memory.update(memory_kind="semantic", valid_time={"start": start, "end": end, "precision": "exact", "basis": "source_explicit"})
    recalled = cognition.recall(scope(), request("preference"), [memory], [source], state())
    assert recalled["items"][0]["applicability"]["value"] == value
    packet = cognition.prepare(scope(), prepare_payload(), working(), recalled, state())
    block = next(block for block in context_view(packet)["blocks"] if block["section"] != "uncertainty")
    assert block["section"] == ("conditional_memory" if value == "false" else "relevant_memory")
    assert block["content"]["use"] == ("conditional_memory_not_current_rule" if value == "false"
                                         else "source_attributed_applicable_memory")
    if value == "false":
        assert "outside_recorded_valid_time" in block["content"]["applicability"]["reasons"]


def test_authoritative_serialized_context_preserves_numeric_bytes_and_exact_budget():
    current = state(0, candidate_total=0)
    recalled = cognition.recall(scope(), request("unmatched"), [], [], current)
    working_state = working()
    working_state["items"] = [{"key": "numbers", "value": [1e20] * 100, "knowledge_state": "unknown",
                               "evidence_refs": [], "expires_at": None, "updated_at": STAMP}]
    packet = cognition.prepare(scope(), prepare_payload(1500), working_state, recalled, current)
    assert packet["working_state"]["items"] == working_state["items"]
    assert "1e+20" in packet["model_context"]
    assert packet["model_context"] == cognition.render_context(packet)
    assert len(packet["model_context"].encode()) == packet["usage"]["context_tokens"] <= 1500
    assert recalled["model_context"] == cognition.render_recall(recalled)
    assert len(recalled["model_context"].encode()) == recalled["usage"]["context_tokens"]
    validate("ContextPacket", packet)
    validate("RecallResult", recalled)
    packet["model_context"] = "stale external copy"
    assert cognition.render_context(packet) != "stale external copy"
    recalled["model_context"] = "stale external copy"
    assert cognition.render_recall(recalled) != "stale external copy"


def test_prepare_refreshes_nested_recall_authoritative_text_after_applicability_changes():
    sources, memories, current = scenario(kind="exception", valid_during={
        "kind": "interval", "start": {"kind": "unbounded"},
        "end": {"kind": "instant", "at": "2026-10-23T00:00:00Z"}})
    recalled = recall(sources, memories, current)
    original = recalled["model_context"]
    current["applicability_at"] = "2026-10-24T00:00:00Z"
    packet = cognition.prepare(scope(), prepare_payload(), working(), recalled, current)
    nested = packet["recall_results"][0]
    assert nested["model_context"] != original
    assert nested["model_context"] == cognition.render_recall(nested)
    assert nested["usage"]["context_tokens"] == len(nested["model_context"].encode())
    assert packet["model_context"] == cognition.render_context(packet)
    assert packet["usage"]["context_tokens"] == len(packet["model_context"].encode())
    assert recalled["model_context"] == original


def test_evaluation_timestamps_stay_in_diagnostics_without_changing_model_context():
    sources, memories, current = scenario(kind="exception")
    for memory in memories:
        memory.update(conditions={"op": "always"}, valid_during={"kind": "unknown"})
    current["belief_relations"] = [relation(memories[1], memories[:1], kind="exception")]
    current["applicability_at"] = "2026-10-22T12:00:00Z"
    earlier = recall(sources, memories, current)
    earlier_packet = cognition.prepare(scope(), prepare_payload(), working(), earlier, current)
    current["applicability_at"] = "2026-10-22T12:01:00Z"
    later = recall(sources, memories, current)
    later_packet = cognition.prepare(scope(), prepare_payload(), working(), later, current)
    assert earlier["items"][0]["applicability"]["evaluated_at"] != later["items"][0]["applicability"]["evaluated_at"]
    assert earlier["belief_relations"][0]["applicability"]["evaluated_at"] != later["belief_relations"][0]["applicability"]["evaluated_at"]
    assert earlier["model_context"] == later["model_context"]
    assert earlier_packet["model_context"] == later_packet["model_context"]
    certificate = next(iter(context_view(later_packet)["relations"].values()))
    assert certificate["valid_during"] == current["belief_relations"][0]["valid_during"]
    assert "evaluated_at" not in certificate["applicability"]


def test_user_authored_evaluation_metadata_is_not_removed_from_working_values():
    value = {"applicability": {"evaluated_at": "A timestamp mentioned by the user"}}
    packet = {"blocks": [{"section": "working_state", "text": json.dumps({"value": value}), "evidence_refs": []}]}
    assert context_view(packet)["blocks"][0]["content"]["value"] == value


def test_recall_context_and_its_measured_size_do_not_depend_on_usage():
    sources, memories, current = scenario()
    result = recall(sources, memories, current)
    without = {key: value for key, value in result.items() if key != "usage"}
    changed = {**result, "usage": {**result["usage"], "context_tokens": 1, "elapsed_ms": 99}}
    assert cognition.render_recall(without) == cognition.render_recall(changed) == result["model_context"]
    assert result["usage"]["context_tokens"] == len(result["model_context"].encode())


def test_packed_recall_counts_exactly_the_context_it_returns():
    sources, memories, current = scenario()
    memories[1]["statement"] *= 1000
    current["belief_relations"] = [relation(memories[1], memories[:1])]
    standalone = event("routine independent observation", 3)
    sources.append(standalone)
    memories.append(cognition.extract_event(standalone)[0])
    current.update(durable_sequence=3, indexed_sequence=3)
    current["working_event_metadata"][standalone["event_id"]] = standalone
    recalled = recall(sources, memories, current, budget={**request()["budget"], "max_context_tokens": 3000})
    assert recalled["usage"]["stopped_by"] == "context_limit"
    assert recalled["usage"]["context_tokens"] == len(recalled["model_context"].encode()) <= 3000
    assert recalled["model_context"] == cognition.render_recall(recalled)


def containers(value, found=None):
    found = {} if found is None else found
    if isinstance(value, (dict, list)):
        found[id(value)] = value
        for item in value.values() if isinstance(value, dict) else value:
            containers(item, found)
    return found


@pytest.mark.parametrize("kind", ["exception", None])
def test_a_kept_recall_view_shares_nothing_and_rendering_changes_nothing(kind):
    sources, memories, current = scenario(kind=kind) if kind else scenario()
    result = recall(sources, memories, current)
    before = copy.deepcopy(result)
    view = recall_context_view(result)
    # Only the lists it has always passed through are shared; every memory, source and relation is a copy.
    passed = containers([result["unknowns"], result["ambiguities"], result["conflicts"],
                         result["coverage"]["limitations"]])
    assert containers(view).keys() & containers(result).keys() <= passed.keys()
    rendered = cognition.render_recall(result)
    assert result == before
    assert rendered == serialized(view) == result["model_context"]


def test_remembered_handles_are_exactly_the_hashed_ones():
    from membrain.context_views import Handles, _handle

    handles = Handles()
    values = [{"memory_id": "m", "revision": 1}, {"memory_id": "m", "revision": True}, {"memory_id": "m", "revision": 1.0},
              {"revision": 1, "memory_id": "m"}, {"x": 0.0}, {"x": -0.0}, {"x": 1e16}, {"x": 10**16},
              {"span": {"start": 0, "end": 4}}, {"span": {"end": 4, "start": 0}}, {"x": [1, "1", None, [True]]},
              {"x": "é"}, {"x": "é"}, {"x": None}, {"x": [{}]}, {1: "integer key"}, {"1": "string key"}]
    for _ in range(2):  # computed, then remembered
        for value in values:
            for kind in ("m", "s", "r"):
                assert handles(kind, value) == _handle(kind, value), (kind, value)
    assert handles("s", {"x": (1, 2)}) == _handle("s", {"x": (1, 2)})  # not keyable: hashed every time
    with pytest.raises(ValueError):
        handles("s", {"x": float("nan")})
    value = {"event_id": "e", "span": {"start": 0, "end": 4}}
    before = handles("s", value)
    value["span"]["end"] = 5  # a changed value is a new key, never the remembered handle
    assert handles("s", value) == _handle("s", value) != before


@pytest.mark.parametrize("kind", ["exception", "supersedes"])
def test_a_recall_renders_the_same_context_with_remembered_handles(kind, monkeypatch):
    from membrain.context_views import Handles

    sources, memories, current = scenario(kind=kind)
    result = recall(sources, memories, current)
    shared = Handles()
    assert cognition.render_recall(result, shared) == cognition.render_recall(result) == result["model_context"]
    fewer = {**result, "items": result["items"][1:]}
    assert cognition.render_recall(fewer, shared) == cognition.render_recall(fewer)
    renders = []
    original = cognition.render_recall
    monkeypatch.setattr(cognition, "render_recall", lambda *args: renders.append(len(args)) or original(*args))
    again = recall(sources, memories, current)
    assert again["model_context"] == result["model_context"]
    assert renders and set(renders) == {2}  # every render of the recall used its own handles


def fitting_scenarios():
    sources, memories, current = scenario()  # a connected group with a belief relation, and an oversized member
    memories[1]["statement"] *= 1000
    current["belief_relations"] = [relation(memories[1], memories[:1])]
    standalone = event("routine independent observation", 3)
    sources.append(standalone)
    memories.append(cognition.extract_event(standalone)[0])
    current.update(durable_sequence=3, indexed_sequence=3)
    current["working_event_metadata"][standalone["event_id"]] = standalone
    yield "belief_group", sources, memories, current, request("routine", budget=budget(3000))
    for kind in ("exception", "supersedes", "contradicts"):
        sources, memories, current = scenario(kind=kind)
        yield kind, sources, memories, current, request("routine", budget=budget(1500))
    # Whole source passages that cover their literal captures, more of them than the budget holds.
    sources = [event(f"Map number {i} has a blue border. " + "x" * 300 + ". This is only a reported scene.", i + 1)
               for i in range(8)]
    memories = [memory for source in sources for memory in cognition.extract_event(source)]
    yield "passages", sources, memories, state(8), request("blue map", budget=budget(4000))
    sources = [event(f"Note {i}: the green folder holds project {i}.", i + 1) for i in range(30)]
    memories = [memory for source in sources for memory in cognition.extract_event(source)]
    yield "many_small", sources, memories, state(30), request("green folder project", budget=budget(2500))


@pytest.mark.parametrize("name", [name for name, *_ in fitting_scenarios()])
def test_fitting_measures_exactly_what_a_whole_render_measures(name, monkeypatch):
    """Every measurement of a recall's budget fitting equals the length of the whole render it replaces, and the
    recall comes out exactly as it does when every measurement renders the whole context."""
    from membrain.context_views import FittingMeasure

    _, sources, memories, current, query = next(value for value in fitting_scenarios() if value[0] == name)
    measured, projected = [], []

    class Checked(FittingMeasure):
        def __call__(self, result):
            value = super().__call__(result)
            assert value == len(cognition.render_recall(result).encode())
            measured.append(bool(result.get("source_passages")))
            return value

        def _record(self, project, assessments):
            projected.append(project)
            return super()._record(project, assessments)

    def rendering(handles):
        return lambda result: len(cognition.render_recall(result, handles).encode())

    def outcome(result):  # all but generated identities and the measured duration
        result["retrieval_snapshot"].pop("snapshot_id")
        return ({key: value for key, value in result.items() if key not in {"recall_id", "recall_traces", "usage"}},
                {key: value for key, value in result["usage"].items() if key != "elapsed_ms"},
                [trace["memory_id"] for trace in result["recall_traces"]])

    with monkeypatch.context() as patch:
        patch.setattr(cognition, "FittingMeasure", rendering)
        expected = outcome(cognition.recall(scope(), copy.deepcopy(query), copy.deepcopy(memories),
                                            copy.deepcopy(sources), copy.deepcopy(current)))
    monkeypatch.setattr(cognition, "FittingMeasure", Checked)
    result = cognition.recall(scope(), query, memories, sources, current)
    assert len(measured) > 2 and result["usage"]["stopped_by"] == "context_limit"
    if name == "passages":
        assert any(measured)
    if name in {"passages", "many_small"}:  # no belief resolutions: each item and passage is projected once
        assert len(projected) <= len(memories) + len(sources) < len(measured) * len(result["items"])
    assert outcome(result) == expected
    assert result["usage"]["context_tokens"] == len(result["model_context"].encode())


def test_fitting_reuses_only_metadata_lengths_and_remeasures_changed_values(monkeypatch):
    from collections import Counter

    from membrain import context_views

    sources, memories, current = scenario(kind="exception")
    result = cognition.recall(scope(), request("routine"), memories, sources, current)
    original, calls = context_views.serialized, Counter()
    names = {"format", "trust", "memories", "status", "next_step", "unknowns", "ambiguities", "conflicts",
             "limitations", "historical_evidence_status", "sources", "relations", "memory_versions"}

    def serialized(value):
        if isinstance(value, str) and value in names:
            calls[value] += 1
        return original(value)

    monkeypatch.setattr(context_views, "serialized", serialized)
    measure = context_views.FittingMeasure(context_views.Handles())
    first = measure(result)
    assert first == len(cognition.render_recall(result).encode()) and all(calls[key] == 1 for key in names)
    result["coverage"]["limitations"].append("A new limitation: 青色文件夹 🧠")
    second = measure(result)
    assert second > first and second == len(cognition.render_recall(result).encode())
    assert all(calls[key] == 1 for key in names)
    fresh = context_views.FittingMeasure(context_views.Handles())
    assert fresh(result) == second and all(calls[key] == 2 for key in names)


def test_a_fitting_measure_follows_changed_resolutions_items_and_passages():
    from test_source_context import recall as source_recall

    from membrain.context_views import FittingMeasure, Handles

    def whole(result):
        return len(cognition.render_recall(result).encode())

    sources, memories, current = scenario(kind="exception")
    result = cognition.recall(scope(), request("routine"), memories, sources, current)
    for item in result["items"]:  # resolutions with their relations inline, as the fitting sees them
        item["belief_resolution"]["relations"] = relation_assessments(item["belief_resolution"],
                                                                      result["belief_relations"])
        item["belief_resolution"].pop("relation_refs")
    result.pop("belief_relations")
    measure = FittingMeasure(Handles())
    assert measure(result) == whole(result)
    first = result["items"][0]
    first["belief_resolution"] = {**first["belief_resolution"], "state": "uncertain", "complete": False}
    assert measure(result) == whole(result)
    first.pop("belief_resolution")
    assert measure(result) == whole(result)
    result["items"] = result["items"][1:]
    assert measure(result) == whole(result)
    result["items"] = []
    assert measure(result) == whole(result)

    _, _, passages = source_recall()
    measure = FittingMeasure(Handles())
    assert passages["source_passages"] and measure(passages) == whole(passages)
    kept = passages["source_passages"]
    passages["source_passages"] = []
    assert measure(passages) == whole(passages)
    passages["source_passages"] = kept
    assert measure(passages) == whole(passages)


@pytest.mark.parametrize("colliding", ["m", "s"])
def test_a_fitting_measure_raises_the_collision_a_whole_render_raises(colliding):
    from membrain.context_views import FittingMeasure, _handle

    def handles(kind, value):
        return f"{kind}:collision" if kind == colliding else _handle(kind, value)

    sources, memories, current = scenario(kind="exception")
    result = cognition.recall(scope(), request("routine"), memories, sources, current)
    with pytest.raises(DomainError) as rendered:
        cognition.render_recall(result, handles)
    with pytest.raises(DomainError) as measured:
        FittingMeasure(handles)(result)
    assert (measured.value.code, str(measured.value)) == (rendered.value.code, str(rendered.value))
