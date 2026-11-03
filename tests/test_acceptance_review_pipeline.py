import copy
import importlib.util
import json
import subprocess
import sys
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


@pytest.mark.parametrize("event", ["page_action_failed", "extraction_unfinished", "clock_already_past",
                                    "page_action_unsupported", "network_refused", "future_error"])
def test_validity_refuses_every_reported_harness_degradation(pipeline, tmp_path, monkeypatch, capsys, event):
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello"}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row], [("s1", 0)], "12:00:00 P practice finished"))
    put(tmp_path / "harness-events.jsonl", {"kind": event, "reason": "PRIVATE PRACTICE DETAIL"})
    pipeline.validity([tmp_path])
    report = json.loads(capsys.readouterr().out)
    assert not report["valid"] and any(event in item for item in report["problems"])
    assert "PRIVATE PRACTICE DETAIL" not in json.dumps(report)


@pytest.mark.parametrize("event", ["{broken", "[]", '{"kind": true}'])
def test_validity_refuses_malformed_harness_event_evidence(pipeline, tmp_path, monkeypatch, capsys, event):
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello"}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row], [("s1", 0)], "12:00:00 P practice finished"))
    (tmp_path / "harness-events.jsonl").write_text(event + "\n")
    pipeline.validity([tmp_path])
    assert not json.loads(capsys.readouterr().out)["valid"]


def test_validity_refuses_duplicate_turns_even_when_the_row_count_matches(pipeline, tmp_path, monkeypatch, capsys):
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello"}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row, row], [("s1", 0), ("s1", 1)],
                                                    "12:00:00 P practice finished"))
    pipeline.validity([tmp_path])
    assert not json.loads(capsys.readouterr().out)["valid"]


def test_validity_accepts_a_complete_practice_run_without_harness_events(pipeline, tmp_path, monkeypatch, capsys):
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello"}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row], [("s1", 0)], "12:00:00 P practice finished"))
    pipeline.validity([tmp_path])
    assert json.loads(capsys.readouterr().out)["valid"]


@pytest.mark.parametrize("changed", [{"arm": "E"}, {"scenario": "another-practice"}])
def test_validity_refuses_mixed_run_identities(pipeline, tmp_path, monkeypatch, capsys, changed):
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello"}
    second = {**row, "turn": 1, **changed}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row, second], [("s1", 0), ("s1", 1)],
                                                    "12:00:00 P practice finished"))
    pipeline.validity([tmp_path])
    assert not json.loads(capsys.readouterr().out)["valid"]


@pytest.mark.parametrize("with_directory", [False, True])
def test_invalid_validity_cli_writes_its_report_and_exits_nonzero(pipeline, tmp_path, with_directory):
    result = subprocess.run([sys.executable, pipeline.__file__, "validity",
                             *([str(tmp_path)] if with_directory else [])], capture_output=True, text=True)
    assert result.returncode == 1
    assert not json.loads(result.stdout)["valid"]


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
    second = {label: {"critical": [], "confirmed": [], "rejected": [], "added": [], "evidence": ""}
              for label in "ABC"}
    second["A"].update(critical=[4], confirmed=[4], evidence="Public practice evidence.")
    put(review / "recheck-practice" / "S01-practice.json", second)
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


@pytest.mark.parametrize("mark", [6, 7, 8, 9])
def test_companion_verdicts_require_explicit_mode(pipeline, practice, tmp_path, mark):
    scenario, verdict = practice
    verdict["S01-practice"]["A"]["critical"] = [mark]
    path = put(tmp_path / "verdicts.json", verdict)
    with pytest.raises(SystemExit, match="bad score or critical list"):
        pipeline.verdicts(path, str(scenario))
    pipeline.verdicts(path, str(scenario), companion=True)


@pytest.mark.parametrize("mark", [0, 10, True, "7"])
def test_companion_verdicts_still_reject_invalid_types(pipeline, practice, tmp_path, mark):
    scenario, verdict = practice
    verdict["S01-practice"]["A"]["critical"] = [mark]
    path = put(tmp_path / "verdicts.json", verdict)
    with pytest.raises(SystemExit, match="bad score or critical list"):
        pipeline.verdicts(path, str(scenario), companion=True)


def review_files(practice, tmp_path, marks):
    scenario, verdict = practice
    verdict["S01-practice"]["A"]["critical"] = marks
    put(tmp_path / "verdicts-practice.json", verdict)
    second = {label: {"critical": [], "confirmed": [], "rejected": [], "added": [], "evidence": ""}
              for label in "ABC"}
    second["A"].update(critical=marks, confirmed=marks, evidence="Synthetic public evidence.")
    path = put(tmp_path / "recheck-practice" / "S01-practice.json", second)
    blind = tmp_path / "blind"
    put(blind / "sealed_practice.json", {"S01-practice": {"A": "P", "B": "E", "C": "F"}})
    return scenario, path, second, blind


@pytest.mark.parametrize("damage", ["missing_label", "missing_fields", "unjudged", "inconsistent", "boolean", "no_evidence"])
def test_tally_refuses_incomplete_or_inconsistent_second_reviews(pipeline, practice, tmp_path, damage):
    scenario, path, second, blind = review_files(practice, tmp_path, [4])
    if damage == "missing_label":
        second.pop("C")
    elif damage == "missing_fields":
        second["A"] = {}
    elif damage == "unjudged":
        second["A"].update(critical=[], confirmed=[])
    elif damage == "inconsistent":
        second["A"]["critical"] = []
    elif damage == "boolean":
        second["A"]["added"] = [True]
    else:
        second["A"]["evidence"] = ""
    put(path, second)
    with pytest.raises(SystemExit, match="invalid (second review|review marks)"):
        pipeline.tally(tmp_path, blind, str(scenario), "practice")
    assert not (tmp_path / "tally-practice.json").exists()


def test_tally_refuses_a_resolution_without_a_reason(pipeline, practice, tmp_path):
    scenario, _, _, blind = review_files(practice, tmp_path, [4])
    put(tmp_path / "resolution-practice.json", {"S01-practice/A": {"remove": [4]}})
    with pytest.raises(SystemExit, match="invalid review marks"):
        pipeline.tally(tmp_path, blind, str(scenario), "practice")


def test_companion_tally_keeps_type8_when_type4_is_cleared(pipeline, practice, tmp_path):
    scenario, _, _, blind = review_files(practice, tmp_path, [4, 8])
    put(tmp_path / "resolution-practice.json", {"S01-practice/A": {"remove": [4], "reason": "R5 practice result"}})
    pipeline.tally(tmp_path, blind, str(scenario), "practice", companion=True)
    data = json.loads((tmp_path / "tally-practice.json").read_text())
    assert data["gate"] == "C5"
    assert data["rows"][0]["literal"] == [4, 8] and data["rows"][0]["resolved"] == [8]
    assert data["totals"]["resolved"]["P"] == 0


@pytest.mark.parametrize("arm_index", [0, 1])
@pytest.mark.parametrize("mark", [7, 8])
def test_companion_boundary_and_deletion_fail_even_when_both_attributors_say_host(pipeline, tmp_path, arm_index, mark):
    data = tally()
    data["gate"] = "C5"
    for index in (arm_index, 2):
        row = data["rows"][index]
        row["resolved"] = [mark]
        data["totals"]["resolved"][row["arm"]] = 0
    put(tmp_path / "tally-practice.json", data)
    label = data["rows"][arm_index]["label"]
    for number in (1, 2):
        put(tmp_path / "attribution-practice" / f"S01-{label}.{number}.json", {"cause": "host"})
    pipeline.gate(tmp_path, ["practice"], companion=True)
    result = json.loads((tmp_path / "gate-c5.json").read_text())
    arm = data["rows"][arm_index]["arm"]
    assert result["arms"][arm]["host_caused"] == [f"S01-practice/{label}"]
    assert result["arms"][arm]["not_worse"] is True
    assert result["arms"][arm]["boundary_or_deletion_errors"] == [f"S01-practice/{label}"]
    assert result["C5"] is False and "R4" not in result
    assert not (tmp_path / "gate.json").exists()


def test_companion_gate_is_separate_and_cannot_overwrite_an_r4_result(pipeline, tmp_path):
    put(tmp_path / "tally-core.json", tally())
    pipeline.gate(tmp_path, ["core"])
    original = (tmp_path / "gate.json").read_bytes()
    data = {**tally(), "gate": "C5"}
    put(tmp_path / "tally-companion.json", data)
    with pytest.raises(SystemExit, match="different gate"):
        pipeline.gate(tmp_path, ["companion"])
    with pytest.raises(SystemExit, match="different gate"):
        pipeline.gate(tmp_path, ["core", "companion"], companion=True)
    pipeline.gate(tmp_path, ["companion"], companion=True)
    assert json.loads((tmp_path / "gate-c5.json").read_text())["C5"] is True
    assert (tmp_path / "gate.json").read_bytes() == original


def test_companion_cli_writes_a_failed_result_and_exits_nonzero(pipeline, practice, tmp_path):
    scenario, _, _, blind = review_files(practice, tmp_path, [8])
    script = pipeline.__file__
    for arguments in (("verdicts", str(tmp_path / "verdicts-practice.json"), str(scenario)),
                      ("tally", str(tmp_path), str(blind), str(scenario), "practice")):
        result = subprocess.run([sys.executable, script, *arguments, "--companion"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    result = subprocess.run([sys.executable, script, "gate", str(tmp_path), "practice", "--companion"],
                            capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert json.loads((tmp_path / "gate-c5.json").read_text())["C5"] is False


def test_gate_refuses_cross_scenario_case_collisions_that_overwrite_attribution(pipeline, tmp_path):
    data = tally()
    for index in (0, 2):
        row = data["rows"][index]
        row["resolved"] = [4]
        data["totals"]["resolved"][row["arm"]] = 0
    for key, cause in (("one", "memory"), ("two", "host")):
        put(tmp_path / f"tally-{key}.json", data)
        for number in (1, 2):
            put(tmp_path / f"attribution-{key}" / f"S01-A.{number}.json", {"cause": cause})
    with pytest.raises(SystemExit, match="invalid tally: duplicate case"):
        pipeline.gate(tmp_path, ["one", "two"])
    assert not (tmp_path / "gate.json").exists()
