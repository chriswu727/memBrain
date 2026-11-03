"""The frozen-manifest acceptance attempt driver, with synthetic files and fake runner and validity scripts only.

No test here runs the real run script, the real validity check or any model.
"""
import copy
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

DRIVER = Path(__file__).parents[1] / "evaluations" / "acceptance-attempt-driver.py"
SECRET = "PLANTED-SCENARIO-CONTENT-7f3a9c"
ORDER = ["alpha", "beta", "gamma", "delta"]

RUNNER = r'''
import json, os, pathlib, subprocess, sys, time
scenario, out, key = sys.argv[1:4]
config = json.loads(pathlib.Path(os.environ["FAKE_CONFIG"]).read_text())
with open(config["calls"], "a") as calls:
    calls.write(json.dumps(["runner", key, scenario, out]) + "\n")
text = pathlib.Path(scenario).read_text()
print(text)  # A careless runner: its own output carries the scenario's content.
print(text, file=sys.stderr)
for arm in "PEF":
    run = pathlib.Path(out) / f"{key}-{arm}"
    run.mkdir()
    (run / "run.log").write_text(text + f"\n{arm} finished\n")
for path in config.get("touch", {}).get(key, []):
    pathlib.Path(path).mkdir(parents=True)
for path in config.get("modify", {}).get(key, []):
    with open(path, "a") as file:
        file.write("changed\n")
if key in config.get("block_ledger", []):
    pathlib.Path(config["ledger"]).write_text(json.dumps({"version": 1, "blocked": True}))
if key == config.get("hang"):
    import signal
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    def supervise(number, frame):  # Like the run script's supervisor: block first, then stop the arms.
        pathlib.Path(config["stopped"]).write_text(json.dumps({"arm_alive": child.poll() is None}))
        child.terminate()
        child.wait()
        sys.exit(143)
    if config.get("hang_mode") == "supervise":
        signal.signal(signal.SIGTERM, supervise)
    elif config.get("hang_mode") == "ignore":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pathlib.Path(config["pids"]).write_text(json.dumps([os.getpid(), child.pid]))
    time.sleep(300)
sys.exit(3 if key in config.get("fail", []) else 0)
'''

VALIDITY = r'''
import json, os, pathlib, sys
config = json.loads(pathlib.Path(os.environ["FAKE_CONFIG"]).read_text())
runs = [pathlib.Path(arg) for arg in sys.argv[1:]]
key = runs[0].name.rsplit("-", 1)[0]
with open(config["calls"], "a") as calls:
    calls.write(json.dumps(["validity", key, [run.name for run in runs]]) + "\n")
print((runs[0] / "run.log").read_text())
sys.exit(1 if key in config.get("invalid", []) else 0)
'''


@pytest.fixture
def driver():
    spec = importlib.util.spec_from_file_location("acceptance_attempt_driver_test", DRIVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Attempt:
    """A synthetic repository, a manifest over it, fake runner and validity scripts, and an OUT_ROOT."""

    def __init__(self, root: Path):
        self.root, self.repo, self.out = root, root / "repo", root / "out"
        self.frozen = self.repo / "evaluations" / "harness.py"
        self.frozen.parent.mkdir(parents=True)
        self.frozen.write_text("HARNESS = 1\n")
        pairs = []
        for gate, keys in (("R4", ORDER[:2]), ("C5", ORDER[2:])):
            scenarios = []
            for key in keys:
                path = self.repo / "held" / f"{key}.py"
                path.parent.mkdir(exist_ok=True)
                path.write_text(f"CASES = []  # {SECRET} {key}\n")
                scenarios.append({"key": key, "path": f"held/{key}.py", "sha256": sha(path)})
            pairs.append({"gate": gate, "scenarios": scenarios})
        self.manifest = {"version": 1, "attempt_id": "attempt-test-1",
                         "files": {"evaluations/harness.py": sha(self.frozen)}, "pairs": pairs, "order": list(ORDER)}
        self.manifest_path = root / "manifest.json"
        self.write_manifest()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        (bin_dir / "runner.py").write_text(RUNNER)
        (bin_dir / "validity.py").write_text(VALIDITY)
        self.runner = f"{sys.executable} {bin_dir / 'runner.py'}"
        self.validity = f"{sys.executable} {bin_dir / 'validity.py'}"
        self.calls_path = root / "calls.jsonl"
        self.config = {"calls": str(self.calls_path), "ledger": str(root / "ledger.json"), "pids": str(root / "pids"),
                       "stopped": str(root / "stopped.json")}

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def argv(self, *extra):
        return [sys.executable, str(DRIVER), "run", "--manifest", str(self.manifest_path), "--out", str(self.out),
                "--repo", str(self.repo), "--runner", self.runner, "--validity", self.validity, "--grace", "1", *extra]

    def env(self):
        (self.root / "config.json").write_text(json.dumps(self.config))
        env = {k: v for k, v in os.environ.items() if not k.startswith("C5_")}
        env["FAKE_CONFIG"] = str(self.root / "config.json")
        return env

    def run(self, *extra, env=None):
        return subprocess.run(self.argv(*extra), env=env or self.env(), capture_output=True, text=True, timeout=120)

    def calls(self):
        if not self.calls_path.exists():
            return []
        return [json.loads(line) for line in self.calls_path.read_text().splitlines()]

    def runner_keys(self):
        return [call[1] for call in self.calls() if call[0] == "runner"]

    def state(self):
        return json.loads((self.out / "attempt-state.json").read_text())


@pytest.fixture
def attempt(tmp_path):
    return Attempt(tmp_path)


def summary(result):
    return json.loads(result.stdout.strip().splitlines()[-1])


def assert_no_content(attempt, result):
    assert SECRET not in result.stdout and SECRET not in result.stderr
    if (attempt.out / "attempt-state.json").exists():
        assert SECRET not in (attempt.out / "attempt-state.json").read_text()


# Happy path ---------------------------------------------------------------------------------------------------------

def test_happy_path_runs_every_scenario_in_manifest_order_and_validates_each(attempt):
    result = attempt.run()
    assert result.returncode == 0, result.stderr
    assert attempt.calls() == [
        item for key in ORDER for item in (
            ["runner", key, str(attempt.repo / "held" / f"{key}.py"), str(attempt.out)],
            ["validity", key, [f"{key}-P", f"{key}-E", f"{key}-F"]])]
    state = attempt.state()
    assert state["result"] == "complete" and state["stop"] is None
    assert state["attempt_id"] == "attempt-test-1" and state["manifest_sha256"] == sha(attempt.manifest_path)
    assert {key: record["status"] for key, record in state["scenarios"].items()} == dict.fromkeys(ORDER, "valid")
    assert [(pair["gate"], pair["status"]) for pair in state["pairs"]] == [("R4", "complete"), ("C5", "complete")]
    record = state["scenarios"]["alpha"]
    assert record["runner_exit"] == 0 and record["validity_exit"] == 0 and record["gate"] == "R4"
    assert record["started_at"] and record["runner_finished_at"] and record["validity_finished_at"]
    assert str(attempt.out / "alpha-P" / "run.log") in record["logs"]
    assert summary(result) == {"attempt_id": "attempt-test-1", "result": "complete", "stop": None,
                               "scenarios": dict.fromkeys(ORDER, "valid"),
                               "pairs": {"R4": "complete", "C5": "complete"}, "eligible": ["C5", "R4"]}


def test_order_comes_from_the_manifest_not_from_the_pairs(attempt):
    attempt.manifest["order"] = ["delta", "alpha", "gamma", "beta"]
    attempt.write_manifest()
    assert attempt.run().returncode == 0
    assert attempt.runner_keys() == ["delta", "alpha", "gamma", "beta"]


def test_no_scenario_content_reaches_the_state_file_or_stdout(attempt):
    attempt.config["fail"] = ["beta"]
    for result in (attempt.run(),):
        assert_no_content(attempt, result)
    assert SECRET in (attempt.out / "driver-logs" / "alpha.runner.log").read_text()  # The runner did leak it.
    assert SECRET in (attempt.out / "alpha-P" / "run.log").read_text()


def test_no_scenario_content_on_success(attempt):
    result = attempt.run()
    assert result.returncode == 0
    assert_no_content(attempt, result)


# Hashes -------------------------------------------------------------------------------------------------------------

def test_hash_mismatch_before_start_refuses_and_runs_nothing(attempt):
    attempt.frozen.write_text("HARNESS = 2\n")
    result = attempt.run()
    assert result.returncode == 2 and summary(result) == {"result": "refused", "stop": "hash_mismatch"}
    assert attempt.calls() == [] and not attempt.out.exists()


def test_scenario_hash_mismatch_before_start_refuses(attempt):
    (attempt.repo / "held" / "delta.py").write_text("CASES = [1]\n")
    result = attempt.run()
    assert result.returncode == 2 and "delta.py" in result.stderr and attempt.calls() == []
    assert_no_content(attempt, result)


def test_missing_frozen_file_refuses(attempt):
    attempt.frozen.unlink()
    assert attempt.run().returncode == 2 and attempt.calls() == []


def test_a_file_changed_during_a_scenario_stops_before_the_next(attempt):
    attempt.config["modify"] = {"gamma": [str(attempt.frozen)]}
    result = attempt.run()
    assert result.returncode == 1
    assert attempt.runner_keys() == ["alpha", "beta", "gamma"]
    state = attempt.state()
    assert state["stop"]["reason"] == "hash_mismatch" and "evaluations/harness.py" in state["stop"]["detail"]
    assert [state["scenarios"][key]["status"] for key in ORDER] == ["valid", "valid", "inputs_changed", "not_run"]
    assert summary(result)["pairs"] == {"R4": "complete", "C5": "incomplete"}
    assert summary(result)["eligible"] == ["R4"]


def test_a_file_changed_between_scenarios_is_caught_by_the_check_before_the_next(driver, attempt):
    args = driver.main.__globals__["argparse"].Namespace(
        manifest=str(attempt.manifest_path), out=str(attempt.out), repo=str(attempt.repo),
        runner=attempt.runner, validity=attempt.validity, ledger=None, grace=1)
    run = driver.Driver(args)
    run.prepare()
    attempt.out.mkdir()
    run.state = run.initial_state()
    attempt.frozen.write_text("HARNESS = 3\n")
    assert run.scenario("beta") is False
    assert run.state["stop"]["reason"] == "hash_mismatch" and run.state["scenarios"]["beta"]["status"] == "pending"
    assert attempt.calls() == [] and not (attempt.out / "beta-P").exists()


def test_a_changed_manifest_stops_the_attempt(attempt):
    attempt.config["modify"] = {"alpha": [str(attempt.manifest_path)]}
    result = attempt.run()
    assert result.returncode == 1 and attempt.runner_keys() == ["alpha"]
    assert attempt.state()["stop"]["reason"] == "hash_mismatch"


def test_runner_inside_the_repo_must_be_frozen(attempt):
    script = attempt.repo / "evaluations" / "run.py"
    script.write_text(RUNNER)
    attempt.runner = f"{sys.executable} evaluations/run.py"
    result = attempt.run()
    assert result.returncode == 2 and summary(result)["stop"] == "unfrozen_command"
    assert "evaluations/run.py" in result.stderr and attempt.calls() == []
    attempt.manifest["files"]["evaluations/run.py"] = sha(script)
    attempt.write_manifest()
    assert attempt.run().returncode == 0 and attempt.runner_keys() == ORDER


# Failures keep earlier pairs -----------------------------------------------------------------------------------------

def test_runner_failure_in_the_third_scenario_never_starts_the_fourth(attempt):
    attempt.config["fail"] = ["gamma"]
    result = attempt.run()
    assert result.returncode == 1
    assert attempt.runner_keys() == ["alpha", "beta", "gamma"]
    assert [call[1] for call in attempt.calls() if call[0] == "validity"] == ["alpha", "beta"]
    assert not any((attempt.out / f"delta-{arm}").exists() for arm in "PEF")
    state = attempt.state()
    assert [state["scenarios"][key]["status"] for key in ORDER] == ["valid", "valid", "runner_failed", "not_run"]
    assert state["scenarios"]["gamma"]["runner_exit"] == 3 and state["scenarios"]["gamma"]["validity_exit"] is None
    assert state["result"] == "stopped" and state["stop"]["key"] == "gamma"
    assert summary(result) == {"attempt_id": "attempt-test-1", "result": "stopped", "stop": "runner_failed",
                               "scenarios": {"alpha": "valid", "beta": "valid", "gamma": "runner_failed",
                                             "delta": "not_run"},
                               "pairs": {"R4": "complete", "C5": "incomplete"}, "eligible": ["R4"]}
    assert_no_content(attempt, result)


def test_validity_failure_in_the_third_scenario_never_starts_the_fourth(attempt):
    attempt.config["invalid"] = ["gamma"]
    result = attempt.run()
    assert result.returncode == 1
    assert attempt.runner_keys() == ["alpha", "beta", "gamma"]
    state = attempt.state()
    assert [state["scenarios"][key]["status"] for key in ORDER] == ["valid", "valid", "invalid", "not_run"]
    assert state["scenarios"]["gamma"]["validity_exit"] == 1
    assert summary(result)["pairs"] == {"R4": "complete", "C5": "incomplete"}
    assert summary(result)["eligible"] == ["R4"] and summary(result)["stop"] == "invalid"
    assert_no_content(attempt, result)


def test_failure_in_the_first_pair_leaves_the_second_not_run(attempt):
    attempt.config["fail"] = ["beta"]
    result = attempt.run()
    assert result.returncode == 1 and attempt.runner_keys() == ["alpha", "beta"]
    assert summary(result)["pairs"] == {"R4": "incomplete", "C5": "not_run"} and summary(result)["eligible"] == []


def test_runner_that_cannot_start_counts_as_a_failure(attempt):
    attempt.runner = str(attempt.root / "missing-runner")
    result = attempt.run()
    assert result.returncode == 1 and summary(result)["scenarios"]["alpha"] == "runner_failed"
    assert attempt.state()["scenarios"]["alpha"]["runner_exit"] == 127


# Never resume or reuse ------------------------------------------------------------------------------------------------

def test_an_existing_run_directory_is_refused_before_start(attempt):
    (attempt.out / "delta-E").mkdir(parents=True)
    result = attempt.run()
    assert result.returncode == 2 and summary(result)["stop"] == "run_dir_exists" and "delta-E" in result.stderr
    assert attempt.calls() == [] and not (attempt.out / "attempt-state.json").exists()


def test_a_run_directory_that_appears_during_the_attempt_stops_it(attempt):
    attempt.config["touch"] = {"alpha": [str(attempt.out / "beta-F")]}
    result = attempt.run()
    assert result.returncode == 1 and attempt.runner_keys() == ["alpha"]
    assert attempt.state()["stop"]["reason"] == "run_dir_exists"
    assert summary(result)["scenarios"] == {"alpha": "valid", "beta": "not_run", "gamma": "not_run",
                                            "delta": "not_run"}


@pytest.mark.parametrize("earlier", ["attempt-test-1", "another-attempt"])
def test_an_existing_driver_state_is_never_overwritten(attempt, earlier):
    attempt.out.mkdir()
    text = json.dumps({"attempt_id": earlier, "result": "stopped"})
    (attempt.out / "attempt-state.json").write_text(text)
    result = attempt.run()
    assert result.returncode == 2 and summary(result)["stop"] == "state_exists"
    assert ("a different attempt" in result.stderr) == (earlier != "attempt-test-1")
    assert (attempt.out / "attempt-state.json").read_text() == text and attempt.calls() == []


def test_a_completed_attempt_cannot_be_rerun_into_the_same_out_root(attempt):
    assert attempt.run().returncode == 0
    before = (attempt.out / "attempt-state.json").read_text()
    assert attempt.run().returncode == 2
    assert (attempt.out / "attempt-state.json").read_text() == before and len(attempt.runner_keys()) == 4


# Ledger ---------------------------------------------------------------------------------------------------------------

def test_a_ledger_blocked_during_the_attempt_stops_before_the_next_scenario(attempt):
    ledger = Path(attempt.config["ledger"])
    ledger.write_text(json.dumps({"version": 1, "blocked": False, "requests": {}}))
    attempt.config["block_ledger"] = ["alpha"]
    result = attempt.run("--ledger", str(ledger))
    assert result.returncode == 1 and attempt.runner_keys() == ["alpha"]
    assert summary(result)["stop"] == "ledger_blocked"
    assert summary(result)["pairs"] == {"R4": "incomplete", "C5": "not_run"}
    assert json.loads(ledger.read_text()) == {"version": 1, "blocked": True}  # Only the fake guard wrote it.


@pytest.mark.parametrize("content", [{"blocked": True}, {"requests": {}}, {"blocked": "false"}, None])
def test_a_blocked_missing_or_malformed_ledger_refuses_before_start(attempt, content):
    ledger = Path(attempt.config["ledger"])
    if content is not None:
        ledger.write_text(json.dumps(content))
    before = ledger.read_bytes() if ledger.exists() else None
    result = attempt.run("--ledger", str(ledger))
    assert result.returncode == 2 and summary(result)["stop"] == "ledger_blocked" and attempt.calls() == []
    assert (ledger.read_bytes() if ledger.exists() else None) == before


def test_an_unblocked_ledger_is_only_read(attempt):
    ledger = Path(attempt.config["ledger"])
    ledger.write_text(json.dumps({"version": 1, "blocked": False}))
    before = (ledger.read_bytes(), ledger.stat().st_mtime_ns)
    assert attempt.run("--ledger", str(ledger)).returncode == 0
    assert (ledger.read_bytes(), ledger.stat().st_mtime_ns) == before


# Environment binding --------------------------------------------------------------------------------------------------

def test_a_different_c5_attempt_id_refuses(attempt):
    env = attempt.env() | {"C5_ATTEMPT_ID": "some-other-attempt"}
    result = attempt.run(env=env)
    assert result.returncode == 2 and summary(result)["stop"] == "environment" and attempt.calls() == []
    assert attempt.run(env=attempt.env() | {"C5_ATTEMPT_ID": "attempt-test-1"}).returncode == 0


# Signals --------------------------------------------------------------------------------------------------------------

def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            return stat.read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except (OSError, IndexError):
            return False
    return True


@pytest.mark.parametrize("number, mode", [(signal.SIGTERM, "default"), (signal.SIGINT, "default"),
                                          (signal.SIGTERM, "supervise"), (signal.SIGTERM, "ignore")])
def test_a_signal_kills_the_runner_group_and_records_interrupted(attempt, number, mode):
    attempt.config["hang"], attempt.config["hang_mode"] = "beta", mode
    process = subprocess.Popen(attempt.argv(), env=attempt.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
    pids_path = Path(attempt.config["pids"])
    deadline = time.monotonic() + 60
    while not pids_path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    runner, grandchild = json.loads(pids_path.read_text())
    try:
        process.send_signal(number)
        stdout, _ = process.communicate(timeout=30)
        assert process.returncode == 128 + number
        deadline = time.monotonic() + 10
        while (alive(runner) or alive(grandchild)) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not alive(runner) and not alive(grandchild)
    finally:
        for pid in (runner, grandchild):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
    line = json.loads(stdout.strip().splitlines()[-1])
    assert line["result"] == "interrupted" and line["stop"] == "interrupted"
    assert line["scenarios"] == {"alpha": "valid", "beta": "interrupted", "gamma": "not_run", "delta": "not_run"}
    assert line["pairs"] == {"R4": "incomplete", "C5": "not_run"}
    state = attempt.state()
    assert state["result"] == "interrupted" and state["stop"]["key"] == "beta"
    assert attempt.runner_keys() == ["alpha", "beta"]
    if mode == "supervise":  # The runner alone got the first SIGTERM, while its arm was still running.
        assert json.loads(Path(attempt.config["stopped"]).read_text()) == {"arm_alive": True}
        assert state["scenarios"]["beta"]["runner_exit"] == 143


# Manifest structure ---------------------------------------------------------------------------------------------------

def _pair(gate, *keys):
    return {"gate": gate, "scenarios": [{"key": key, "path": f"held/{key}.py", "sha256": "a" * 64} for key in keys]}


VALID = {"version": 1, "attempt_id": "x", "files": {"evaluations/run.sh": "b" * 64},
         "pairs": [_pair("R4", "one", "two"), _pair("C5", "three", "four")], "order": ["one", "two", "three", "four"]}


def _broken(change):
    manifest = copy.deepcopy(VALID)
    change(manifest)
    return manifest


STRUCTURE_ERRORS = {
    "not an object": lambda m: m.clear(),
    "version 2": lambda m: m.update(version=2),
    "version true": lambda m: m.update(version=True),
    "version string": lambda m: m.update(version="1"),
    "extra top-level key": lambda m: m.update(extra=1),
    "missing order": lambda m: m.pop("order"),
    "empty attempt": lambda m: m.update(attempt_id=""),
    "padded attempt": lambda m: m.update(attempt_id=" x"),
    "empty files": lambda m: m.update(files={}),
    "absolute file": lambda m: m.update(files={"/etc/passwd": "b" * 64}),
    "parent file": lambda m: m.update(files={"../outside": "b" * 64}),
    "dot file path": lambda m: m.update(files={"./run.sh": "b" * 64}),
    "short sha": lambda m: m.update(files={"run.sh": "b" * 63}),
    "upper sha": lambda m: m.update(files={"run.sh": "B" * 64}),
    "empty pairs": lambda m: m.update(pairs=[]),
    "unknown gate": lambda m: m["pairs"][1].update(gate="R5"),
    "duplicate gate": lambda m: m["pairs"][1].update(gate="R4"),
    "extra pair key": lambda m: m["pairs"][0].update(name="core"),
    "empty scenarios": lambda m: m["pairs"][0].update(scenarios=[]),
    "duplicate key": lambda m: m["pairs"][1]["scenarios"][0].update(key="one", path="held/x.py"),
    "duplicate path": lambda m: m["pairs"][1]["scenarios"][0].update(path="held/one.py"),
    "key with slash": lambda m: (m["pairs"][0]["scenarios"][0].update(key="a/b"),
                                 m.update(order=["a/b", "two", "three", "four"])),
    "key dots": lambda m: (m["pairs"][0]["scenarios"][0].update(key=".."),
                           m.update(order=["..", "two", "three", "four"])),
    "scenario bad sha": lambda m: m["pairs"][0]["scenarios"][0].update(sha256="z" * 64),
    "scenario extra key": lambda m: m["pairs"][0]["scenarios"][0].update(note="n"),
    "order missing key": lambda m: m["order"].pop(),
    "order unknown key": lambda m: m["order"].append("five"),
    "order duplicate": lambda m: m.update(order=["one", "two", "three", "four", "one"]),
    "order not list": lambda m: m.update(order="one"),
}


def test_the_reference_manifest_is_valid(driver):
    assert driver.validate_manifest(copy.deepcopy(VALID)) == VALID
    single = _broken(lambda m: (m["pairs"].pop(), m.update(order=["one", "two"])))
    assert driver.validate_manifest(single)["order"] == ["one", "two"]


@pytest.mark.parametrize("name", sorted(STRUCTURE_ERRORS))
def test_manifest_structure_errors_are_refused(driver, name):
    with pytest.raises(ValueError):
        driver.validate_manifest(_broken(STRUCTURE_ERRORS[name]))


@pytest.mark.parametrize("text", ["{not json", "[]", json.dumps(_broken(STRUCTURE_ERRORS["order missing key"]))])
def test_a_malformed_manifest_file_is_refused_by_the_cli(attempt, text):
    attempt.manifest_path.write_text(text)
    result = attempt.run()
    assert result.returncode == 2 and summary(result) == {"result": "refused", "stop": "manifest"}
    assert attempt.calls() == [] and not attempt.out.exists()


def test_a_scenario_path_through_a_symlink_out_of_the_repo_is_refused(attempt):
    outside = attempt.root / "outside.py"
    outside.write_text("X = 1\n")
    (attempt.repo / "link.py").symlink_to(outside)
    attempt.manifest["files"]["link.py"] = sha(outside)
    attempt.write_manifest()
    result = attempt.run()
    assert result.returncode == 2 and summary(result)["stop"] == "manifest" and attempt.calls() == []
