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


def attribution(cause, marks=(4,)):
    return {"cause": cause, "per_type": {
        str(mark): {"cause": cause, "evidence": "Public synthetic evidence."} for mark in marks}}


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


@pytest.mark.parametrize("reply", [None, 7, {}, [], "", "  "])
def test_validity_reports_invalid_reply_without_crashing(pipeline, tmp_path, monkeypatch, capsys, reply):
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": reply}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row], [("s1", 0)], "12:00:00 P practice finished"))
    result = pipeline.validity([tmp_path])
    assert result["valid"] is False
    assert any("reply at turn 1 of 1" in item for item in result["problems"])
    assert json.loads(capsys.readouterr().out) == result


def test_validity_refuses_duplicate_turns_even_when_the_row_count_matches(pipeline, tmp_path, monkeypatch, capsys):
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello"}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row, row], [("s1", 0), ("s1", 1)],
                                                    "12:00:00 P practice finished"))
    pipeline.validity([tmp_path])
    assert not json.loads(capsys.readouterr().out)["valid"]


def test_validity_refuses_a_single_complete_arm(pipeline, tmp_path, monkeypatch, capsys):
    """One complete arm is not an attempt: a missing arm is refused (two complete arms: two_arm_runs below)."""
    row = {"arm": "P", "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello"}
    monkeypatch.setattr(pipeline, "_run", lambda _: ([row], [("s1", 0)], "12:00:00 P practice finished"))
    pipeline.validity([tmp_path])
    report = json.loads(capsys.readouterr().out)
    assert not report["valid"] and any("not exactly the frozen arms" in item for item in report["problems"])


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
    verdict = {label: {"score_ignoring_critical": 1, "critical": []} for label in "AB"}
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
              for label in "AB"}
    second["A"].update(critical=[4], confirmed=[4], evidence="Public practice evidence.")
    put(review / "recheck-practice" / "S01-practice.json", second)
    put(review / "resolution-practice.json", {"S01-practice/A": {"remove": [4], "reason": "practice evidence"}})
    put(blind / "sealed_practice.json", {"S01-practice": {"A": "P", "B": "F"}})
    pipeline.tally(review, blind, str(scenario), "practice")
    result = json.loads((review / "tally-practice.json").read_text())
    assert result["totals"] == {"literal": {"P": 0, "F": 1}, "resolved": {"P": 1, "F": 1}}
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
    return {"totals": {"resolved": {"P": 1, "F": 1}}, "rows": [
        {"case": "S01-practice", "label": label, "arm": arm, "base": 1, "literal": [], "resolved": []}
        for label, arm in zip("AB", "PF", strict=True)]}


@pytest.mark.parametrize("companion,marks", [(False, [1, 4]), (True, [4, 6])])
@pytest.mark.parametrize("damage", ["missing", "contradiction", "missing_type", "empty_evidence"])
def test_gate_cannot_pass_with_incomplete_or_contradictory_host_attribution(
        pipeline, tmp_path, companion, marks, damage):
    data = tally()
    if companion:
        data["gate"] = "C5"
    for index in (0, 1):
        row = data["rows"][index]
        row["resolved"] = marks
        data["totals"]["resolved"][row["arm"]] = 0
    put(tmp_path / "tally-practice.json", data)
    answer = {"cause": "host", "per_type": {
        str(mark): {"cause": "host", "evidence": "Public synthetic evidence."} for mark in marks}}
    if damage == "missing":
        answer.pop("per_type")
    elif damage == "contradiction":
        answer["per_type"][str(marks[0])]["cause"] = "memory"
    elif damage == "missing_type":
        answer["per_type"].pop(str(marks[0]))
    else:
        answer["per_type"][str(marks[0])]["evidence"] = "  "
    for number in (1, 2):
        put(tmp_path / "attribution-practice" / f"S01-A.{number}.json", answer)
    result = pipeline.gate(tmp_path, ["practice"], companion=companion)
    assert result["C5" if companion else "R4"] is False
    assert result["arms"]["P"]["memory_caused"] == ["S01-practice/A"]
    assert result["attributions"]["S01-practice/A"]["answers"] == [None, None]


@pytest.mark.parametrize("bad", [
    {"totals": {"resolved": {}}, "rows": []},
    {"totals": {"resolved": {"P": 1, "E": 1}}, "rows": []},
    {"totals": {"resolved": {"P": 0, "E": 0, "F": 0}}, "rows": []},
    {"totals": {"resolved": {"P": 0, "F": 0}}, "rows": []},
])
def test_gate_refuses_missing_evidence_or_reference_arm(pipeline, tmp_path, bad):
    put(tmp_path / "tally-practice.json", bad)
    with pytest.raises(SystemExit, match="invalid tally"):
        pipeline.gate(tmp_path, ["practice"])
    assert not (tmp_path / "gate.json").exists()


@pytest.mark.parametrize("cause,passes", [("host", True), ("memory", False)])
def test_gate_uses_complete_consistent_attribution_without_always_failing(pipeline, tmp_path, cause, passes):
    data = tally()
    for index in (0, 1):
        row = data["rows"][index]
        row["resolved"] = [1, 4]
        data["totals"]["resolved"][row["arm"]] = 0
    put(tmp_path / "tally-practice.json", data)
    for number in (1, 2):
        put(tmp_path / "attribution-practice" / f"S01-A.{number}.json", attribution(cause, [1, 4]))
    result = pipeline.gate(tmp_path, ["practice"])
    assert result["R4"] is passes
    assert result["attributions"]["S01-practice/A"]["answers"] == [cause, cause]


def test_gate_counts_disagreeing_attributions_as_memory_caused(pipeline, tmp_path):
    data = tally()
    data["totals"]["resolved"]["P"] = 0
    data["rows"][0]["resolved"] = [4]
    put(tmp_path / "tally-practice.json", data)
    put(tmp_path / "attribution-practice" / "S01-A.1.json", attribution("host"))
    put(tmp_path / "attribution-practice" / "S01-A.2.json", attribution("memory"))
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
    put(tmp_path / "attribution-practice" / "S01-A.2.json", attribution("host"))
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
              for label in "AB"}
    second["A"].update(critical=marks, confirmed=marks, evidence="Synthetic public evidence.")
    path = put(tmp_path / "recheck-practice" / "S01-practice.json", second)
    blind = tmp_path / "blind"
    put(blind / "sealed_practice.json", {"S01-practice": {"A": "P", "B": "F"}})
    return scenario, path, second, blind


@pytest.mark.parametrize("damage", ["missing_label", "missing_fields", "unjudged", "inconsistent", "boolean", "no_evidence"])
def test_tally_refuses_incomplete_or_inconsistent_second_reviews(pipeline, practice, tmp_path, damage):
    scenario, path, second, blind = review_files(practice, tmp_path, [4])
    if damage == "missing_label":
        second.pop("B")
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
    put(tmp_path / "resolution-practice.json", {"S01-practice/A": {"remove": [4], "rules": {"4": "R5"},
                                                                   "reason": "R5 practice result"}})
    put(tmp_path / "r5-practice" / "S01-A.json", {"type4_cleared": True})
    pipeline.tally(tmp_path, blind, str(scenario), "practice", companion=True)
    data = json.loads((tmp_path / "tally-practice.json").read_text())
    assert data["gate"] == "C5"
    assert data["rows"][0]["literal"] == [4, 8] and data["rows"][0]["resolved"] == [8]
    assert data["totals"]["resolved"]["P"] == 0


@pytest.mark.parametrize("arm_index", [0])
@pytest.mark.parametrize("mark", [7, 8])
def test_companion_boundary_and_deletion_fail_even_when_both_attributors_say_host(pipeline, tmp_path, arm_index, mark):
    data = tally()
    data["gate"] = "C5"
    for index in (arm_index, 1):
        row = data["rows"][index]
        row["resolved"] = [mark]
        data["totals"]["resolved"][row["arm"]] = 0
    put(tmp_path / "tally-practice.json", data)
    label = data["rows"][arm_index]["label"]
    for number in (1, 2):
        put(tmp_path / "attribution-practice" / f"S01-{label}.{number}.json", attribution("host", [mark]))
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
    for index in (0, 1):
        row = data["rows"][index]
        row["resolved"] = [4]
        data["totals"]["resolved"][row["arm"]] = 0
    for key, cause in (("one", "memory"), ("two", "host")):
        put(tmp_path / f"tally-{key}.json", data)
        for number in (1, 2):
            put(tmp_path / f"attribution-{key}" / f"S01-A.{number}.json", attribution(cause))
    with pytest.raises(SystemExit, match="invalid tally: duplicate case"):
        pipeline.gate(tmp_path, ["one", "two"])
    assert not (tmp_path / "gate.json").exists()


# Two frozen arms (sixth maturity attempt): P is gated against F; anything else is refused --------------------------

def test_the_pipeline_freezes_two_arms_and_gates_only_the_plugin_path(pipeline):
    assert pipeline.ARMS == ("P", "F") and pipeline.GATED == ("P",) and pipeline.REFERENCE == "F"
    assert pipeline.LABELS == ("A", "B")


THREE_ARMS = {"totals": {"resolved": {"P": 1, "E": 1, "F": 1}}, "rows": [
    {"case": "S01-practice", "label": label, "arm": arm, "base": 1, "literal": [], "resolved": []}
    for label, arm in zip("ABC", "PEF", strict=True)]}


@pytest.mark.parametrize("change", [
    lambda data: None,  # A three-arm tally of attempts 1 to 5.
    lambda data: (data["rows"].pop(), data["totals"]["resolved"].pop("F")),  # P and E: the reference is missing.
    lambda data: (data["rows"].pop(), data["totals"]["resolved"].pop("E")),  # Totals P and F, rows P and E.
], ids=["three arms", "E instead of F", "rows with E under totals for F"])
def test_a_tally_with_arm_e_or_three_arms_is_refused(pipeline, tmp_path, change):
    data = copy.deepcopy(THREE_ARMS)
    change(data)
    put(tmp_path / "tally-practice.json", data)
    with pytest.raises(SystemExit, match="invalid tally"):
        pipeline.gate(tmp_path, ["practice"])
    assert not (tmp_path / "gate.json").exists()


def test_a_tally_missing_the_gated_arm_cannot_pass_as_zero(pipeline, tmp_path):
    data = tally()
    data["rows"] = [row for row in data["rows"] if row["arm"] == "F"]
    data["totals"]["resolved"] = {"F": 1}
    put(tmp_path / "tally-practice.json", data)
    with pytest.raises(SystemExit, match="invalid tally"):
        pipeline.gate(tmp_path, ["practice"])


def gate_world(tmp_path, p_scores, f_scores, p_critical=(), f_critical=(), causes=None, p_label="A"):
    """A synthetic two-scenario R4 result: per case a P reply (label ``p_label``) and an F reply (the other label).
    ``p_critical`` and ``f_critical`` name case numbers (1-based) whose reply carries a standing type 4 mark;
    ``causes`` maps P's to the two attributors' answers (default: both host)."""
    f_label = "B" if p_label == "A" else "A"
    for key, start in (("one", 0), ("two", len(p_scores) // 2)):
        rows, totals = [], {"P": 0, "F": 0}
        for number in range(start + 1, start + len(p_scores) // 2 + 1):
            case = f"S{number:02d}-practice"
            for label, arm, scores, marked in ((p_label, "P", p_scores, p_critical),
                                               (f_label, "F", f_scores, f_critical)):
                resolved = [4] if number in marked else []
                base = scores[number - 1]
                rows.append({"case": case, "label": label, "arm": arm, "base": base, "literal": resolved,
                             "resolved": resolved})
                totals[arm] += 0 if resolved else base
                if arm == "P" and resolved:
                    for attempt, cause in zip("12", (causes or {}).get(number, ("host", "host")), strict=True):
                        put(tmp_path / f"attribution-{key}" / f"S{number:02d}-{p_label}.{attempt}.json",
                            attribution(cause))
        put(tmp_path / f"tally-{key}.json", {"totals": {"resolved": totals}, "rows": rows})
    return pipeline_gate(tmp_path)


def pipeline_gate(tmp_path):
    path = Path(__file__).parents[1] / "evaluations" / "acceptance_review.py"
    spec = importlib.util.spec_from_file_location("acceptance_review_gate_world", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.gate(tmp_path, ["one", "two"])


GATE_CASES = {
    # name: (P scores, F scores, P critical cases, F critical cases, causes, R4, failing condition)
    "P equals F": ([1] * 4, [1] * 4, (), (), None, True, None),
    "P exactly F minus 1": ([1, 1, 0.5, 0.5], [1] * 4, (), (), None, True, None),
    "P below F minus 1": ([1, 0.5, 0.5, 0], [1] * 4, (), (), None, False, "not_worse"),
    "P above F": ([1] * 4, [0.5] * 4, (), (), None, True, None),
    "a memory-caused critical reply": ([1] * 4, [1] * 4, (1,), (2,), {1: ("memory", "host")}, False, "memory"),
    "a host-caused critical reply within F's count": ([1] * 4, [1] * 4, (1,), (2,), None, True, None),
    "more host-caused critical replies than F has": ([1] * 4, [1] * 4, (1, 3), (2,), None, False, "host"),
    "host-caused critical replies with none in F": ([1] * 4, [1] * 4, (1,), (), None, False, "host"),
}


@pytest.mark.parametrize("name", GATE_CASES)
def test_the_gate_passes_r4_exactly_when_p_meets_each_condition_against_f(tmp_path, name):
    p, f, p_critical, f_critical, causes, passes, failing = GATE_CASES[name]
    result = gate_world(tmp_path, p, f, p_critical, f_critical, causes)
    arm = result["arms"]["P"]
    assert set(result["arms"]) == {"P"} and result["gated"] == ["P"] and result["reference_arm"] == "F"
    assert result["R4"] is passes and arm["passes"] is passes
    assert arm["reference"] == sum(0 if number in f_critical else score for number, score in enumerate(f, 1))
    assert arm["not_worse"] is (failing != "not_worse")
    assert (arm["memory_caused"] != []) is (failing == "memory")
    assert arm["host_within_reference"] is (failing != "host")
    assert arm["reference_critical"] == len(f_critical)


def test_a_sealed_mapping_with_three_labels_or_arm_e_is_refused(pipeline, practice, tmp_path):
    scenario, verdict = practice
    review, blind = tmp_path / "review", tmp_path / "blind"
    put(review / "verdicts-practice.json", verdict)
    put(review / "recheck-practice" / "S01-practice.json", {label: {
        "critical": [], "confirmed": [], "rejected": [], "added": [], "evidence": ""} for label in "AB"})
    for sealed in ({"S01-practice": {"A": "P", "B": "E", "C": "F"}}, {"S01-practice": {"A": "P", "B": "E"}},
                   {"S01-practice": {"A": "P", "B": "P"}}, {"S02-other": {"A": "P", "B": "F"}}):
        put(blind / "sealed_practice.json", sealed)
        with pytest.raises(SystemExit, match="invalid sealed mapping"):
            pipeline.tally(review, blind, str(scenario), "practice")
    assert not (review / "tally-practice.json").exists()


def test_first_verdicts_with_three_labels_are_refused(pipeline, practice, tmp_path):
    scenario, verdict = practice
    verdict["S01-practice"]["C"] = {"score_ignoring_critical": 1, "critical": []}
    with pytest.raises(SystemExit, match="exactly labels A and B"):
        pipeline.verdicts(put(tmp_path / "verdicts.json", verdict), str(scenario))


def test_a_second_review_with_a_third_label_is_refused(pipeline, practice, tmp_path):
    scenario, path, second, blind = review_files(practice, tmp_path, [])
    second["C"] = {"critical": [], "confirmed": [], "rejected": [], "added": [], "evidence": ""}
    put(path, second)
    with pytest.raises(SystemExit, match="must cover exactly A and B"):
        pipeline.tally(tmp_path, blind, str(scenario), "practice")


def test_the_split_refuses_a_sheet_with_a_third_reply(pipeline, tmp_path):
    scenario = tmp_path / "practice.py"
    scenario.write_text('CASES = [("s1", 0, "S01-practice", "Criteria: must greet")]\n')
    blind = tmp_path / "blind"
    put(blind / "sealed_practice.json", {"S01-practice": {"A": "P", "B": "F"}})
    for arm in "PF":
        (blind / f"results_practice_{arm}.jsonl").write_text(json.dumps(
            {"arm": arm, "session": "s1", "turn": 0, "reply": f"Reply from {arm}."}) + "\n")
    verdicts = put(tmp_path / "verdicts.json", {"S01-practice": {
        label: {"score_ignoring_critical": 1, "critical": []} for label in "AB"}})
    sheet = tmp_path / "blind_practice.md"
    body = "# practice\n\n## Ground truth\n\nFacts.\n\n## S01-practice\n\nCase.\n\n### A\n\nReply from P.\n\n### B\n\n" \
           "Reply from F.\n"
    sheet.write_text(body)
    pipeline.split(sheet, verdicts, blind, str(scenario), tmp_path / "ok")
    sheet.write_text(body + "\n### C\n\nA third reply.\n")
    with pytest.raises(SystemExit, match="outside A and B"):
        pipeline.split(sheet, verdicts, blind, str(scenario), tmp_path / "refused")




def two_arm_runs(pipeline, tmp_path, monkeypatch, arms=("P", "F"), persona="enfp", source="seeded", stamps=True):
    """Synthetic run directories, one per arm, with persona.json and supervisor stamps as the run script writes
    them; the results are stubbed through _run."""
    rows, runs = {}, []
    for number, arm in enumerate(arms):
        run = tmp_path / f"k-{arm}{number}"
        run.mkdir(parents=True)
        rows[run.name] = [{"arm": arm, "scenario": "practice", "session": "s1", "turn": 0, "reply": "Hello",
                           "usage": {"prompt_tokens": 1}}]
        if persona is not None:
            put(run / "persona.json", {"arm": arm, "source": source, "seed": "x", "preset": persona,
                                       "card_sha256": persona, "version": 1})
        if stamps:
            start = 10.0 + 20 * number
            (run / "supervisor.log").write_text(f"started {start}\nfinished {start + 5}\ncleaned {start + 6}\n")
        runs.append(run)
    monkeypatch.setattr(pipeline, "_run", lambda run: (rows[run.name], [("s1", 0)],
                                                       f"12:00:00 {rows[run.name][0]['arm']} practice finished"))
    return runs


def test_validity_accepts_two_complete_arms(pipeline, tmp_path, monkeypatch):
    result = pipeline.validity(two_arm_runs(pipeline, tmp_path, monkeypatch), persona_preset="enfp")
    assert result["valid"], result["problems"]


@pytest.mark.parametrize("arms, problem", [
    (("P",), "not exactly the frozen arms"), (("F",), "not exactly the frozen arms"),
    (("P", "F", "E"), "not one of the frozen arms"), (("P", "F", "P"), "a second run directory of arm P"),
], ids=["only P", "only F", "an arm E", "P twice"])
def test_validity_refuses_a_missing_extra_or_repeated_arm(pipeline, tmp_path, monkeypatch, arms, problem):
    result = pipeline.validity(two_arm_runs(pipeline, tmp_path, monkeypatch, arms))
    assert not result["valid"] and any(problem in item for item in result["problems"]), result["problems"]


def test_validity_refuses_runs_without_persona_or_supervisor_stamps(pipeline, tmp_path, monkeypatch):
    result = pipeline.validity(two_arm_runs(pipeline, tmp_path / "a", monkeypatch, persona=None))
    assert not result["valid"] and "a run directory has no persona.json" in result["problems"]
    result = pipeline.validity(two_arm_runs(pipeline, tmp_path / "b", monkeypatch, stamps=False))
    assert not result["valid"] and any("supervisor stamps" in item for item in result["problems"])


def test_validity_refuses_personas_that_differ_or_are_not_the_seeded_draw(pipeline, tmp_path, monkeypatch):
    runs = two_arm_runs(pipeline, tmp_path / "a", monkeypatch)
    put(runs[1] / "persona.json", {"arm": "F", "source": "seeded", "seed": "x", "preset": "intj",
                                   "card_sha256": "intj", "version": 1})
    result = pipeline.validity(runs)
    assert not result["valid"] and "the arms carried different personas" in result["problems"]
    runs = two_arm_runs(pipeline, tmp_path / "b", monkeypatch)
    result = pipeline.validity(runs, persona_preset="intj")  # The manifest drew another type.
    assert not result["valid"] and "the arms did not carry the attempt's seeded persona" in result["problems"]
    runs = two_arm_runs(pipeline, tmp_path / "c", monkeypatch, source="scenario")  # A scenario's own card.
    assert pipeline.validity(runs)["valid"]  # Without the manifest's draw, agreeing personas pass ...
    result = pipeline.validity(runs, persona_preset="enfp")  # ... with it, only the seeded type does.
    assert not result["valid"] and "the arms did not carry the attempt's seeded persona" in result["problems"]


def test_validity_refuses_arms_that_overlapped_in_time(pipeline, tmp_path, monkeypatch):
    runs = two_arm_runs(pipeline, tmp_path, monkeypatch)
    assert pipeline.validity(runs)["valid"]
    (runs[1] / "supervisor.log").write_text("started 15.5\nfinished 30.0\ncleaned 30.5\n")
    result = pipeline.validity(runs)
    assert not result["valid"] and "the arms overlapped in time" in result["problems"]


def test_validity_reports_tool_errors_without_refusing(pipeline, tmp_path, monkeypatch):
    runs = two_arm_runs(pipeline, tmp_path, monkeypatch)
    (runs[0] / "tool-errors.json").write_text(json.dumps({"memory_note": 2, "memory_recall": 1}))
    result = pipeline.validity(runs)
    assert result["valid"] and result["tool_errors_reported_to_the_host"] == {"k-P0 (P)": 3, "k-F1 (F)": 0}


def test_validity_cli_takes_the_manifests_persona(pipeline, tmp_path):
    result = subprocess.run([sys.executable, pipeline.__file__, "validity", str(tmp_path), "--persona"],
                            capture_output=True, text=True)
    assert result.returncode != 0 and "--persona PRESET is valid once for validity" in result.stderr


def test_remarks_counts_memory_wording_per_arm_without_printing_replies(pipeline, tmp_path, capsys):
    scenario = tmp_path / "practice.py"
    scenario.write_text('CASES = [("s1", 0, "S01-a", "x"), ("s1", 1, "S02-b", "x")]\n')
    replies = {"P": [f"{PLANT_REMARK} Saved.", "Fine.", "我记住了。"], "F": ["Fine.", "Fine.", "Sure."]}
    for arm, texts in replies.items():
        (tmp_path / f"results_practice_{arm}.jsonl").write_text("".join(json.dumps(
            {"arm": arm, "session": "s1", "turn": turn, "reply": text}) + "\n" for turn, text in enumerate(texts)))
    report = pipeline.remarks(tmp_path, str(scenario))
    assert report["arms"]["P"] == {"case_replies": 2, "case_with_remarks": 1, "case_share": 0.5, "all_replies": 3,
                                   "all_with_remarks": 2, "all_share": 0.667}
    assert report["arms"]["F"]["all_with_remarks"] == 0 and report["phrases"] == len(pipeline.MEMORY_REMARKS)
    assert PLANT_REMARK not in capsys.readouterr().out


PLANT_REMARK = "ZQ-REPLY-TEXT-41"


@pytest.mark.parametrize("p_label", ["A", "B"])
@pytest.mark.parametrize("name", ["P equals F", "a memory-caused critical reply",
                                  "more host-caused critical replies than F has", "P below F minus 1"])
def test_the_gate_reads_the_arm_not_the_label(tmp_path, name, p_label):
    p, f, p_critical, f_critical, causes, passes, failing = GATE_CASES[name]
    result = gate_world(tmp_path, p, f, p_critical, f_critical, causes, p_label=p_label)
    assert result["R4"] is passes and set(result["arms"]) == {"P"}
