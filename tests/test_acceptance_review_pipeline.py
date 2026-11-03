import copy
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def pipeline():
    path = Path(__file__).parents[1] / "evaluations" / "acceptance_review.py"
    spec = importlib.util.spec_from_file_location("acceptance_review_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def practice(tmp_path):
    scenario = tmp_path / "practice.py"
    scenario.write_text('CASES = [(0, 0, "S01-practice", "A public synthetic practice case")]\n')
    verdict = {label: {"score_ignoring_critical": 1, "critical": []} for label in "ABC"}
    return scenario, {"S01-practice": verdict}


@pytest.mark.parametrize("bad", [
    {"score_ignoring_critical": True, "critical": []},
    {"score_ignoring_critical": 1, "critical": [True]},
    {"score_ignoring_critical": 2, "critical": []},
    {"score_ignoring_critical": 1, "critical": [6]},
])
def test_first_verdicts_refuse_bad_numeric_scores_and_critical_types(pipeline, practice, tmp_path, bad):
    scenario, verdict = practice
    verdict["S01-practice"]["A"] = bad
    path = put(tmp_path / "verdicts.json", verdict)
    with pytest.raises(SystemExit, match="bad score or critical list"):
        pipeline.verdicts(path, str(scenario))


def test_valid_prefix_keys_are_expanded_without_losing_the_original_file(pipeline, practice, tmp_path):
    scenario, verdict = practice
    original = {"S01": verdict["S01-practice"]}
    path = put(tmp_path / "verdicts.json", original)
    pipeline.verdicts(path, str(scenario))
    assert json.loads(path.read_text()) == verdict
    assert json.loads((tmp_path / "verdicts.raw.json").read_text()) == original


def test_tally_applies_written_resolutions_without_rewriting_literal_scores(pipeline, practice, tmp_path):
    scenario, verdict = practice
    review, blind = tmp_path / "review", tmp_path / "blind"
    verdict["S01-practice"]["A"]["critical"] = [4]
    put(review / "verdicts-practice.json", verdict)
    put(review / "recheck-practice" / "S01-practice.json", {"A": {"confirmed": [4]}, "B": {}, "C": {}})
    put(review / "resolution-practice.json", {"S01-practice/A": {"remove": [4], "reason": "practice evidence"}})
    put(blind / "sealed_practice.json", {"S01-practice": {"A": "P", "B": "E", "C": "F"}})
    pipeline.tally(review, blind, str(scenario), "practice")
    result = json.loads((review / "tally-practice.json").read_text())
    assert result["totals"] == {"literal": {"P": 0, "E": 1, "F": 1}, "resolved": {"P": 1, "E": 1, "F": 1}}
    assert result["rows"][0]["literal"] == [4] and result["rows"][0]["resolved"] == []


def test_r5_malformed_checker_is_rejected_and_cannot_clear_a_critical_mark(pipeline, tmp_path):
    inputs, answers, results = tmp_path / "inputs", tmp_path / "answers", tmp_path / "results"
    inputs.mkdir()
    (inputs / "S01-A.md").write_text("Public synthetic practice; no earlier assistant entries.\n")
    put(answers / "S01-A.1.json", {"claims": [], "type4_cleared": True})
    put(answers / "S01-A.2.json", {"claims": [{"kind": "user_fact"}], "type4_cleared": False})
    pipeline.r5_check(inputs, answers, results)
    assert (answers / "S01-A.1.rejected.json").exists()
    assert not (results / "S01-A.json").exists()
    put(answers / "S01-A.1.json", {"claims": [{"kind": "user_fact"}], "type4_cleared": False})
    pipeline.r5_check(inputs, answers, results)
    assert json.loads((results / "S01-A.json").read_text()) == {"type4_cleared": False}


def tally():
    return {"totals": {"resolved": {"P": 1, "E": 1, "F": 1}}, "rows": [
        {"case": "S01-practice", "label": label, "arm": arm, "base": 1, "literal": [], "resolved": []}
        for label, arm in zip("ABC", "PEF", strict=True)]}


@pytest.mark.parametrize("bad", [
    {"totals": {"resolved": {}}, "rows": []},
    {"totals": {"resolved": {"P": 1, "E": 1}}, "rows": []},
    {"totals": {"resolved": {"P": 0, "E": 0, "F": 0}}, "rows": []},
])
def test_gate_refuses_missing_evidence_or_reference_arm(pipeline, tmp_path, bad):
    put(tmp_path / "tally-practice.json", bad)
    with pytest.raises(SystemExit, match="invalid tally"):
        pipeline.gate(tmp_path, ["practice"])
    assert not (tmp_path / "gate.json").exists()


def test_gate_counts_disagreeing_attributions_as_memory_caused(pipeline, tmp_path):
    data = tally()
    data["totals"]["resolved"]["P"] = 0
    data["rows"][0]["resolved"] = [4]
    put(tmp_path / "tally-practice.json", data)
    put(tmp_path / "attribution-practice" / "S01-A.1.json", {"cause": "host"})
    put(tmp_path / "attribution-practice" / "S01-A.2.json", {"cause": "memory"})
    pipeline.gate(tmp_path, ["practice"])
    result = json.loads((tmp_path / "gate.json").read_text())
    assert result["R4"] is False
    assert result["arms"]["P"]["memory_caused"] == ["S01-practice/A"]
    assert result["attributions"]["S01-practice/A"]["cause"] == "memory"


def test_gate_accepts_only_a_complete_noncritical_practice_result(pipeline, tmp_path):
    data = tally()
    original = copy.deepcopy(data)
    put(tmp_path / "tally-practice.json", data)
    pipeline.gate(tmp_path, ["practice"])
    assert json.loads((tmp_path / "gate.json").read_text())["R4"] is True
    assert json.loads((tmp_path / "tally-practice.json").read_text()) == original


@pytest.mark.parametrize("change", [
    lambda data: data["rows"].pop(),
    lambda data: data["rows"].append(copy.deepcopy(data["rows"][0])),
    lambda data: data["rows"][0].update(arm="F"),
    lambda data: data["rows"][0].update(base=True),
    lambda data: data["rows"][0].update(resolved=[True]),
    lambda data: data["totals"]["resolved"].update(P=True),
    lambda data: data["totals"]["resolved"].update(P=2),
    lambda data: data["totals"]["resolved"].update(P=float("nan")),
])
def test_gate_rejects_inconsistent_or_malformed_evidence(pipeline, tmp_path, change):
    data = tally()
    change(data)
    put(tmp_path / "tally-practice.json", data)
    with pytest.raises(SystemExit, match="invalid tally"):
        pipeline.gate(tmp_path, ["practice"])
    assert not (tmp_path / "gate.json").exists()


@pytest.mark.parametrize("keys", [[], ["practice", "practice"]])
def test_gate_refuses_empty_or_duplicate_scenario_keys(pipeline, tmp_path, keys):
    put(tmp_path / "tally-practice.json", tally())
    with pytest.raises(SystemExit, match="invalid tally"):
        pipeline.gate(tmp_path, keys)


def test_gate_counts_nonobject_attribution_as_memory_caused(pipeline, tmp_path):
    data = tally()
    data["totals"]["resolved"]["P"] = 0
    data["rows"][0]["resolved"] = [4]
    put(tmp_path / "tally-practice.json", data)
    put(tmp_path / "attribution-practice" / "S01-A.1.json", ["host"])
    put(tmp_path / "attribution-practice" / "S01-A.2.json", {"cause": "host"})
    pipeline.gate(tmp_path, ["practice"])
    result = json.loads((tmp_path / "gate.json").read_text())
    assert result["R4"] is False
    assert result["attributions"]["S01-practice/A"]["answers"] == [None, "host"]
