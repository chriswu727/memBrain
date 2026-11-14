import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EVALUATIONS = Path(__file__).parents[1] / "evaluations"
PRIVATE = "SYNTHETIC-CONTENT-MUST-NOT-LEAK"


def environment():
    return {k: v for k, v in os.environ.items() if not k.startswith("C5_") and not k.endswith("_API_KEY")}


def scenario_file(root):
    path = root / "private scenarios" / "nested.py"
    path.parent.mkdir(parents=True)
    path.write_text(f'SESSIONS_LONG = [("{PRIVATE}", ["one", "two"])]\n')
    return path


def write_run(run, arm="P", scenario="nested", missing=False):
    run.mkdir()
    rows = [{"arm": arm, "scenario": scenario, "session": PRIVATE, "turn": turn,
             "reply": PRIVATE, "usage": {"prompt_tokens": 12}} for turn in range(1 if missing else 2)]
    (run / f"results_{scenario}_{arm}.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
    (run / "run.log").write_text(f"12:00:00 {arm} {scenario} finished\n")
    (run / "persona.json").write_text(json.dumps({"arm": arm, "source": "seeded", "seed": "x", "preset": "enfp",
                                                  "card_sha256": "c", "version": 1}))
    start = 10.0 if arm == "P" else 30.0
    (run / "supervisor.log").write_text(f"started {start}\nfinished {start + 5}\ncleaned {start + 6}\n")


def write_runs(root, scenario="nested"):
    """Both arms' run directories, as a complete attempt has them."""
    runs = [root / "run-P", root / "run-F"]
    write_run(runs[0], "P", scenario)
    write_run(runs[1], "F", scenario)
    return runs


@pytest.mark.parametrize("command", ["validity", "diagnose"])
def test_nested_scenario_cli_uses_explicit_path_without_disclosing_content(tmp_path, command):
    scenario = scenario_file(tmp_path)
    runs = write_runs(tmp_path)
    result = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), command,
                             *map(str, runs), "--scenario", str(scenario)], env=environment(),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert PRIVATE not in result.stdout + result.stderr
    if command == "validity":
        assert json.loads(result.stdout)["valid"]
    else:
        assert "2 of 2 turns done" in result.stdout


@pytest.mark.parametrize("damage", ["missing_turn", "wrong_identity", "degradation"])
def test_explicit_scenario_does_not_relax_validity(tmp_path, damage):
    scenario = scenario_file(tmp_path)
    run = tmp_path / "run"
    write_run(run, scenario="other" if damage == "wrong_identity" else "nested", missing=damage == "missing_turn")
    if damage == "degradation":
        (run / "harness-events.jsonl").write_text(json.dumps({"kind": "extraction_unfinished", "reason": PRIVATE}))
    result = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), "validity",
                             str(run), "--scenario", str(scenario)], env=environment(),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert PRIVATE not in result.stdout + result.stderr
    assert not json.loads(result.stdout)["valid"]


def test_diagnose_reports_expected_turns_even_when_no_results_exist(tmp_path):
    scenario = scenario_file(tmp_path)
    run = tmp_path / "run"
    run.mkdir()
    result = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), "diagnose",
                             str(run), "--scenario", str(scenario)], env=environment(),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert "0 of 2 turns done" in result.stdout
    assert PRIVATE not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["validity", "diagnose"])
@pytest.mark.parametrize("source,error", [(f'SESSIONS_LONG = [("{PRIVATE}", [)]', "SyntaxError"),
                                         (f'raise RuntimeError("{PRIVATE}")', "RuntimeError"),
                                         (f'raise SystemExit("{PRIVATE}")', "SystemExit")])
def test_scenario_load_errors_never_disclose_content(tmp_path, command, source, error):
    scenario = scenario_file(tmp_path)
    scenario.write_text(source)
    run = tmp_path / "run"
    write_run(run)
    result = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), command,
                             str(run), "--scenario", str(scenario)], env=environment(),
                            capture_output=True, text=True, timeout=15)
    assert PRIVATE not in result.stdout + result.stderr
    assert error in result.stdout
    if command == "validity":
        assert result.returncode == 1
        assert not json.loads(result.stdout)["valid"]


@pytest.mark.parametrize("args", [["validity", "--scenario"],
                                  ["validity", "--scenario", "one", "--scenario", "two"],
                                  ["gate", "--scenario", "one"]])
def test_scenario_option_rejects_malformed_usage(args):
    result = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), *args],
                            env=environment(), capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert "--scenario PATH is valid once for validity or diagnose" in result.stderr


def test_legacy_scenario_lookup_remains_supported(tmp_path):
    scenario = scenario_file(tmp_path)
    review = scenario.parent / "acceptance_review.py"
    shutil.copyfile(EVALUATIONS / review.name, review)
    runs = write_runs(tmp_path)
    result = subprocess.run([sys.executable, str(review), "validity", *map(str, runs)], env=environment(),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"]


@pytest.mark.parametrize("carried", ["seeded draw", "scenario card"])
def test_driver_runs_real_validity_for_a_nested_manifest_scenario(tmp_path, carried):
    import importlib.util

    spec = importlib.util.spec_from_file_location("acceptance_persona_path", EVALUATIONS / "acceptance_persona.py")
    persona = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(persona)
    draw = persona.draw("synthetic-path-test")
    source = "seeded" if carried == "seeded draw" else "scenario"
    repo = tmp_path / "repo"
    scenario = scenario_file(repo)
    review = repo / "evaluations" / "acceptance_review.py"
    review.parent.mkdir()
    shutil.copyfile(EVALUATIONS / review.name, review)
    runner = tmp_path / "runner.py"
    runner.write_text(f'''import json, pathlib, sys
scenario, out, key = sys.argv[1:]
for number, arm in enumerate("PF"):
    run = pathlib.Path(out) / f"{{key}}-{{arm}}"
    run.mkdir()
    rows = [{{"arm": arm, "scenario": pathlib.Path(scenario).stem, "session": "SYNTHETIC-CONTENT-MUST-NOT-LEAK",
             "turn": turn, "reply": "Synthetic reply", "usage": {{"prompt_tokens": 12}}}} for turn in range(2)]
    (run / f"results_nested_{{arm}}.jsonl").write_text("\\n".join(map(json.dumps, rows)) + "\\n")
    (run / "run.log").write_text(f"12:00:00 {{arm}} nested finished\\n")
    (run / "persona.json").write_text(json.dumps({{"arm": arm, "source": "{source}", "seed": "synthetic-path-test",
                                                  "preset": "{draw}", "card_sha256": "c", "version": 1}}))
    (run / "supervisor.log").write_text(f"started {{10 + 20 * number}}\\nfinished {{15 + 20 * number}}\\n"
                                        f"cleaned {{16 + 20 * number}}\\n")
''')
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "attempt_id": "synthetic-path-test", "files": {
        "evaluations/acceptance_review.py": hashlib.sha256(review.read_bytes()).hexdigest()},
        "pairs": [{"gate": "R4", "scenarios": [{"key": "first", "path": scenario.relative_to(repo).as_posix(),
                    "sha256": hashlib.sha256(scenario.read_bytes()).hexdigest()}]}], "order": ["first"],
        "persona": {"seed": "synthetic-path-test", "preset": draw}}))
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance-attempt-driver.py"), "run",
                             "--repo", str(repo), "--manifest", str(manifest), "--out", str(out),
                             "--runner", f"{sys.executable} {runner}"], env=environment(),
                            capture_output=True, text=True, timeout=20)
    state = json.loads((out / "attempt-state.json").read_text())
    if carried == "scenario card":  # The driver gave validity the manifest's draw: a scenario's card is invalid.
        assert result.returncode == 1 and state["scenarios"]["first"]["status"] == "invalid"
        return
    assert result.returncode == 0, result.stderr
    assert state["scenarios"]["first"]["status"] == "valid"
    assert state["validity"][-1] == "validity"
    assert state["mode"] == "offline"
    assert PRIVATE not in result.stdout + result.stderr
