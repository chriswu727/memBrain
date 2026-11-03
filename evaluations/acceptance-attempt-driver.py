#!/usr/bin/env python3
"""Run one frozen paid acceptance attempt from a manifest, scenario by scenario, and stop at the first problem.

  acceptance-attempt-driver.py run --manifest M --out OUT_ROOT [--repo ROOT] [--runner CMD] [--validity CMD]
                                   [--ledger LEDGER] [--grace SECONDS]

The manifest freezes every input by sha256 and binds each scenario key to its gate (format in
acceptance-attempt-driver.md; the same format as acceptance_review.py's manifest). The driver:
- validates the manifest and every hash before anything, and refuses an OUT_ROOT that already has a driver state or
  any of the attempt's run directories;
- before each scenario, in manifest order: re-verifies every hash, reads the billing ledger's `blocked` flag (read
  only, when --ledger is given) and refuses existing run directories;
- runs RUNNER SCENARIO OUT_ROOT KEY, then VALIDITY OUT_ROOT/KEY-P OUT_ROOT/KEY-E OUT_ROOT/KEY-F;
- stops at the first non-zero exit (any runner exit but 0 is a scenario failure, including the run script's
  supervisor exits after a failed or refused arm), invalid scenario, changed input or blocked ledger. It never
  starts another scenario after that, and it never resumes, reuses or retries anything.

OUT_ROOT/attempt-state.json is replaced atomically after every step. It records statuses, times, exit codes and log
paths only: never a scenario's content and never a child's output (children write to log files). A pair is
`complete` when all its scenarios are valid, and stays complete when a later scenario fails; the driver reports
which gates have a complete pair and never decides R4 or C5. The last stdout line is a one-line JSON summary.

Exit codes: 0 every scenario ran and was valid; 1 stopped; 2 refused before any scenario started; 128 + signal
number after SIGINT or SIGTERM. A signal goes first to the runner alone, so the run script's supervisor can block the
billing ledger before it stops its arms; after --grace seconds the runner's whole process group gets SIGTERM, and
after twice that SIGKILL. The driver only ever reads the ledger.
Standard library only; runs on the system Python 3 of macOS.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

STATE = "attempt-state.json"
LOGS = "driver-logs"
ARMS = ("P", "E", "F")
GATES = ("R4", "C5")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class Refused(Exception):
    """A problem found before the first scenario started: nothing was run and no state was written."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(value, what: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError(f"{what} must be a non-empty repo-relative path")
    parts = value.split("/")
    if value.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"{what} {value!r} must be a normalised repo-relative path")
    return value


def _digest(value, what: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{what} must be a lowercase hex sha256")
    return value


def _exact(value, keys: set, what: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{what} must be an object with exactly the keys {sorted(keys)}")
    return value


def validate_manifest(manifest) -> dict:
    """The shared manifest format: raises ValueError naming the first structural problem."""
    _exact(manifest, {"version", "attempt_id", "files", "pairs", "order"}, "the manifest")
    if type(manifest["version"]) is not int or manifest["version"] != 1:
        raise ValueError("version must be 1")
    attempt = manifest["attempt_id"]
    if not isinstance(attempt, str) or not attempt.strip() or attempt != attempt.strip() or not attempt.isprintable():
        raise ValueError("attempt_id must be a non-empty printable string")
    files = manifest["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("files must be a non-empty object of path to sha256")
    for path, digest in files.items():
        _digest(digest, f"files[{_relative(path, 'a files entry')!r}]")
    pairs = manifest["pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("pairs must be a non-empty list")
    keys, paths, gates = set(), set(), set()
    for pair in pairs:
        _exact(pair, {"gate", "scenarios"}, "a pair")
        if pair["gate"] not in GATES:
            raise ValueError(f"a pair's gate must be one of {list(GATES)}")
        if pair["gate"] in gates:
            raise ValueError(f"gate {pair['gate']} has more than one pair")
        gates.add(pair["gate"])
        if not isinstance(pair["scenarios"], list) or not pair["scenarios"]:
            raise ValueError(f"the {pair['gate']} pair needs a non-empty scenarios list")
        for scenario in pair["scenarios"]:
            _exact(scenario, {"key", "path", "sha256"}, "a scenario")
            key = scenario["key"]
            if not isinstance(key, str) or not _KEY.fullmatch(key):
                raise ValueError(f"scenario key {key!r} must match {_KEY.pattern}")
            if key in keys:
                raise ValueError(f"scenario key {key!r} appears more than once")
            keys.add(key)
            path = _relative(scenario["path"], f"scenario {key}'s path")
            if path in paths:
                raise ValueError(f"scenario path {path!r} appears more than once")
            paths.add(path)
            _digest(scenario["sha256"], f"scenario {key}'s sha256")
    order = manifest["order"]
    if not isinstance(order, list) or any(not isinstance(key, str) for key in order):
        raise ValueError("order must be a list of scenario keys")
    if len(order) != len(set(order)):
        raise ValueError("order names a key more than once")
    if set(order) != keys:
        raise ValueError("order must name every scenario key in the pairs exactly once, and nothing else")
    return manifest


def load_manifest(path: Path) -> tuple[dict, str]:
    """The validated manifest and the sha256 of its exact bytes."""
    data = path.read_bytes()
    try:
        manifest = json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(f"the manifest is not JSON: {error}") from None
    return validate_manifest(manifest), hashlib.sha256(data).hexdigest()


def _inside(repo: Path, relative: str) -> Path:
    path = (repo / relative).resolve()
    if path != repo and repo not in path.parents:
        raise ValueError(f"{relative!r} leaves the repository")
    return path


def frozen_inputs(manifest: dict) -> list[tuple[str, str]]:
    """(repo-relative path, sha256) for every frozen file and every scenario."""
    pairs = [(path, digest) for path, digest in manifest["files"].items()]
    pairs += [(s["path"], s["sha256"]) for pair in manifest["pairs"] for s in pair["scenarios"]]
    return pairs


def verify(repo: Path, manifest: dict, manifest_path: Path, manifest_sha256: str) -> str | None:
    """None when the manifest and every frozen input still match, otherwise a description naming the first path that
    does not (by path only, never content)."""
    try:
        if _sha256(manifest_path) != manifest_sha256:
            return f"the manifest {manifest_path} changed"
    except OSError:
        return f"the manifest {manifest_path} is unreadable"
    for relative, digest in frozen_inputs(manifest):
        try:
            path = _inside(repo, relative)
            if not path.is_file():
                return f"{relative} is missing or not a regular file"
            if _sha256(path) != digest:
                return f"{relative} does not match its frozen sha256"
        except (OSError, ValueError) as error:
            return f"{relative}: {error}"
    return None


def ledger_problem(path: Path) -> str | None:
    """Reads the billing ledger's `blocked` flag (never writes it). Anything but an explicit False stops the run."""
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return f"the billing ledger is unreadable: {type(error).__name__}"
    if not isinstance(state, dict) or state.get("blocked") is not False:
        return "the billing ledger is blocked" if isinstance(state, dict) and state.get("blocked") is True \
            else "the billing ledger has no explicit blocked=false"
    return None


def _command(text: str, repo: Path) -> list[str]:
    argv = shlex.split(text)
    if not argv:
        raise Refused("usage", "an empty command")
    if "/" in argv[0] and not os.path.isabs(argv[0]):
        argv[0] = str(repo / argv[0])
    return argv


def unfrozen_command_files(argv: list[str], repo: Path, frozen: set[str]) -> list[str]:
    """Command arguments that name a file inside the repository that the manifest does not freeze."""
    missing = []
    interpreter = Path(sys.executable).resolve()
    for token in argv:
        candidate = Path(token) if os.path.isabs(token) else repo / token
        try:
            candidate = candidate.resolve()
        except (OSError, RuntimeError):
            continue
        if candidate.is_file() and repo in candidate.parents and candidate != interpreter:
            relative = candidate.relative_to(repo).as_posix()
            if relative not in frozen:
                missing.append(relative)
    return missing


def write_state(out: Path, state: dict, *, create: bool = False) -> None:
    """Atomically replace OUT_ROOT/attempt-state.json; with create, fail if it already exists."""
    state["updated_at"] = _now()
    target = out / STATE
    descriptor, temporary = tempfile.mkstemp(prefix=STATE + ".", dir=out)
    try:
        with os.fdopen(descriptor, "w") as file:
            json.dump(state, file, indent=1, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        if create:
            os.link(temporary, target)  # Exclusive: refuses an existing state even from a concurrent driver.
        else:
            os.replace(temporary, target)
        directory = os.open(out, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Driver:
    def __init__(self, args):
        self.repo = Path(args.repo).resolve()
        self.out = Path(args.out).absolute()
        self.manifest_path = Path(args.manifest).absolute()
        self.ledger = Path(args.ledger).absolute() if args.ledger else None
        self.runner = _command(args.runner or "evaluations/c5-run-scenario.sh", self.repo)
        self.validity = (_command(args.validity, self.repo) if args.validity
                         else [sys.executable, str(self.repo / "evaluations" / "acceptance_review.py"), "validity"])
        self.child: subprocess.Popen | None = None
        self.terminated: int | None = None  # The child pid that has been sent SIGTERM for a signal.
        self.signalled_at = 0.0
        self.grace = args.grace
        self.signal: int | None = None
        self.current: str | None = None
        self.state: dict = {}

    # Before anything ------------------------------------------------------------------------------------------------

    def prepare(self) -> None:
        if not self.repo.is_dir():
            raise Refused("usage", f"--repo {self.repo} is not a directory")
        try:
            self.manifest, self.manifest_sha256 = load_manifest(self.manifest_path)
        except OSError as error:
            raise Refused("manifest", f"the manifest is unreadable: {type(error).__name__}") from None
        except ValueError as error:
            raise Refused("manifest", str(error)) from None
        try:
            for relative, _ in frozen_inputs(self.manifest):
                _inside(self.repo, relative)
        except ValueError as error:
            raise Refused("manifest", str(error)) from None
        attempt = self.manifest["attempt_id"]
        if os.environ.get("C5_ATTEMPT_ID") not in (None, attempt):
            raise Refused("environment", "C5_ATTEMPT_ID differs from the manifest's attempt_id")
        billing = os.environ.get("C5_BILLING_LEDGER")
        if self.ledger and billing and Path(billing).absolute() != self.ledger:
            raise Refused("environment", "--ledger differs from C5_BILLING_LEDGER")
        frozen = set(self.manifest["files"])
        driver = Path(__file__).resolve()
        unfrozen = unfrozen_command_files(self.runner + self.validity, self.repo, frozen)
        if self.repo in driver.parents and driver.relative_to(self.repo).as_posix() not in frozen:
            unfrozen.append(driver.relative_to(self.repo).as_posix())
        if unfrozen:
            raise Refused("unfrozen_command", f"not frozen in the manifest's files: {', '.join(sorted(unfrozen))}")
        problem = verify(self.repo, self.manifest, self.manifest_path, self.manifest_sha256)
        if problem:
            raise Refused("hash_mismatch", problem)
        if self.ledger and (problem := ledger_problem(self.ledger)):
            raise Refused("ledger_blocked", problem)
        if (self.out / STATE).exists():
            try:
                earlier = json.loads((self.out / STATE).read_text()).get("attempt_id")
            except (OSError, ValueError, AttributeError):
                earlier = None
            same = "this" if earlier == attempt else "a different"
            raise Refused("state_exists", f"{self.out / STATE} already records {same} attempt; it is never "
                                          "overwritten, resumed or reused")
        existing = [self.run_dir(key, arm).name for key in self.manifest["order"] for arm in ARMS
                    if self.run_dir(key, arm).exists()]
        if existing:
            raise Refused("run_dir_exists", f"run directories already exist: {', '.join(existing)}")

    def run_dir(self, key: str, arm: str) -> Path:
        return self.out / f"{key}-{arm}"

    def initial_state(self) -> dict:
        gate_of = {s["key"]: pair["gate"] for pair in self.manifest["pairs"] for s in pair["scenarios"]}
        path_of = {s["key"]: s["path"] for pair in self.manifest["pairs"] for s in pair["scenarios"]}
        return {
            "driver_state_version": 1,
            "attempt_id": self.manifest["attempt_id"],
            "manifest": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha256,
            "repo": str(self.repo),
            "out_root": str(self.out),
            "runner": self.runner,
            "validity": self.validity,
            "ledger": str(self.ledger) if self.ledger else None,
            "created_at": _now(),
            "result": "running",
            "stop": None,
            "order": list(self.manifest["order"]),
            "scenarios": {key: {"gate": gate_of[key], "path": path_of[key], "sha256_verified_at": None,
                                "status": "pending", "started_at": None, "runner_finished_at": None,
                                "runner_exit": None, "validity_finished_at": None, "validity_exit": None,
                                "run_dirs_created": None, "logs": []}
                          for key in self.manifest["order"]},
            "pairs": [{"gate": pair["gate"], "keys": [s["key"] for s in pair["scenarios"]], "status": "not_run"}
                      for pair in self.manifest["pairs"]],
            "eligible": {pair["gate"]: False for pair in self.manifest["pairs"]},
        }

    # Children and signals -------------------------------------------------------------------------------------------

    def on_signal(self, number, _frame) -> None:
        """Record the first signal and ask the running child to stop. Only the group leader (the runner) gets this
        first SIGTERM, so the run script's supervisor can block the billing ledger before it stops its arms."""
        if self.signal is None:
            self.signal = number
        self.terminate_leader()

    def terminate_leader(self) -> None:
        child = self.child
        if child is not None and self.terminated != child.pid:
            self.terminated = child.pid
            self.signalled_at = time.monotonic()
            try:
                os.kill(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def kill_group(self, pgid: int, number: int) -> bool:
        """Signal a process group; False when it no longer exists."""
        try:
            os.killpg(pgid, number)
        except ProcessLookupError:
            return False
        except PermissionError:
            pass
        return True

    def spawn(self, argv: list[str], log: Path) -> int:
        """Run a child in its own process group with its output going to LOG only, and return its exit code.
        Polls (never `wait -n`). On SIGINT/SIGTERM: SIGTERM to the leader; after the grace period SIGTERM to the
        whole group; after another, SIGKILL to the group. After the leader exits, for any reason, whatever is left of
        its group gets SIGTERM and, if still there after the grace period, SIGKILL."""
        with log.open("ab") as output:
            try:
                self.child = subprocess.Popen(argv, cwd=self.repo, stdin=subprocess.DEVNULL, stdout=output,
                                              stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as error:
                output.write(f"driver: could not start {argv[0]}: {type(error).__name__}\n".encode())
                return 127
        pgid = self.child.pid
        try:
            while True:
                if self.signal is not None:  # Also covers a signal that arrived just before the child started.
                    self.terminate_leader()
                    waited = time.monotonic() - self.signalled_at
                    if waited > 2 * self.grace:
                        self.kill_group(pgid, signal.SIGKILL)
                    elif waited > self.grace:
                        self.kill_group(pgid, signal.SIGTERM)
                try:
                    code = self.child.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
            # Never leave a straggler of the group running: a started arm always stops with its scenario.
            if self.kill_group(pgid, signal.SIGTERM):
                deadline = time.monotonic() + self.grace
                while time.monotonic() < deadline and self.kill_group(pgid, 0):
                    time.sleep(0.1)
                self.kill_group(pgid, signal.SIGKILL)
            return code
        finally:
            self.child = None

    # The attempt ----------------------------------------------------------------------------------------------------

    def save(self) -> None:
        write_state(self.out, self.state)

    def finish_pairs(self) -> None:
        statuses = self.state["scenarios"]
        for pair in self.state["pairs"]:
            done = [statuses[key]["status"] for key in pair["keys"]]
            if all(status == "valid" for status in done):
                pair["status"] = "complete"
            elif all(status in ("pending", "not_run") for status in done):
                pair["status"] = "not_run" if self.state["result"] != "running" else "pending"
            else:
                pair["status"] = "incomplete" if self.state["result"] != "running" else "in_progress"
            self.state["eligible"][pair["gate"]] = pair["status"] == "complete"

    def stop(self, key: str | None, reason: str, detail: str) -> None:
        self.state["stop"] = {"key": key, "reason": reason, "detail": detail, "at": _now()}
        print(f"driver: stopped{' at ' + key if key else ''}: {reason}: {detail}", file=sys.stderr)

    def scenario(self, key: str) -> bool:
        """Run one scenario; True when it ran and is valid."""
        record = self.state["scenarios"][key]
        self.current = key
        if self.ledger and (problem := ledger_problem(self.ledger)):
            self.stop(key, "ledger_blocked", problem)
            return False
        problem = verify(self.repo, self.manifest, self.manifest_path, self.manifest_sha256)
        if problem:
            self.stop(key, "hash_mismatch", problem)
            return False
        record["sha256_verified_at"] = _now()
        existing = [self.run_dir(key, arm).name for arm in ARMS if self.run_dir(key, arm).exists()]
        if existing:
            self.stop(key, "run_dir_exists", f"run directories already exist: {', '.join(existing)}")
            return False
        if self.signal is not None:
            return False
        scenario = str(_inside(self.repo, record["path"]))
        runner_log, validity_log = self.out / LOGS / f"{key}.runner.log", self.out / LOGS / f"{key}.validity.log"
        record.update(status="running", started_at=_now(), logs=[str(runner_log)])
        self.save()
        print(f"driver: {key} started", file=sys.stderr)
        code = self.spawn(self.runner + [scenario, str(self.out), key], runner_log)
        record.update(runner_exit=code, runner_finished_at=_now())
        record["run_dirs_created"] = [self.run_dir(key, arm).name for arm in ARMS if self.run_dir(key, arm).exists()]
        record["logs"] += [str(self.run_dir(key, arm) / "run.log") for arm in ARMS
                           if (self.run_dir(key, arm) / "run.log").is_file()]
        if self.signal is not None:
            record["status"] = "interrupted"
            return False
        if code != 0:
            record["status"] = "runner_failed"
            self.stop(key, "runner_failed", f"the runner exited {code}")
            return False
        record.update(status="validating")
        record["logs"].append(str(validity_log))
        self.save()
        code = self.spawn(self.validity + [str(self.run_dir(key, arm)) for arm in ARMS], validity_log)
        record.update(validity_exit=code, validity_finished_at=_now())
        if self.signal is not None:
            record["status"] = "interrupted"
            return False
        if code != 0:
            record["status"] = "invalid"
            self.stop(key, "invalid", f"validity exited {code}")
            return False
        problem = verify(self.repo, self.manifest, self.manifest_path, self.manifest_sha256)
        if problem:
            record["status"] = "inputs_changed"  # Changed while this scenario ran: it cannot count.
            self.stop(key, "hash_mismatch", problem)
            return False
        record["status"] = "valid"
        print(f"driver: {key} valid", file=sys.stderr)
        return True

    def run(self) -> int:
        self.prepare()
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / LOGS).mkdir(exist_ok=True)
        self.state = self.initial_state()
        self.finish_pairs()
        for number in (signal.SIGINT, signal.SIGTERM):
            signal.signal(number, self.on_signal)
        try:
            write_state(self.out, self.state, create=True)
        except FileExistsError:
            raise Refused("state_exists", f"{self.out / STATE} appeared concurrently") from None
        all_valid = True
        try:
            for key in self.manifest["order"]:
                if not self.scenario(key):
                    all_valid = False
                    break
                self.finish_pairs()
                self.save()
        except Exception as error:  # Record it and stop; never continue to another scenario.
            all_valid = False
            if self.child is not None:
                self.kill_group(self.child.pid, signal.SIGKILL)
            self.stop(self.current, "driver_error", type(error).__name__)
        if self.signal is not None:
            self.state["result"] = "interrupted"
            self.stop(self.current, "interrupted", f"signal {signal.Signals(self.signal).name}")
        else:
            self.state["result"] = "complete" if all_valid else "stopped"
        for record in self.state["scenarios"].values():
            if record["status"] == "pending":
                record["status"] = "not_run"
            elif record["status"] in ("running", "validating"):
                record["status"] = "interrupted"
        self.finish_pairs()
        self.save()
        print(json.dumps(summary(self.state), sort_keys=True))
        if self.signal is not None:
            return 128 + self.signal
        return 0 if all_valid else 1


def summary(state: dict) -> dict:
    """Statuses only: no paths, details or output."""
    return {"attempt_id": state["attempt_id"], "result": state["result"],
            "stop": state["stop"]["reason"] if state["stop"] else None,
            "scenarios": {key: record["status"] for key, record in state["scenarios"].items()},
            "pairs": {pair["gate"]: pair["status"] for pair in state["pairs"]},
            "eligible": sorted(gate for gate, ok in state["eligible"].items() if ok)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run every scenario of a frozen manifest in order")
    run.add_argument("--manifest", required=True)
    run.add_argument("--out", required=True, help="OUT_ROOT for run directories and attempt-state.json")
    run.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    run.add_argument("--runner", help="default: evaluations/c5-run-scenario.sh")
    run.add_argument("--validity", help="default: this Python, evaluations/acceptance_review.py validity")
    run.add_argument("--ledger", help="billing ledger JSON whose blocked flag is read before each scenario")
    run.add_argument("--grace", type=float, default=60.0,
                     help="seconds a child gets after each stop signal before the next escalation (default 60)")
    args = parser.parse_args(argv)
    try:
        return Driver(args).run()
    except Refused as error:
        print(f"driver: refused: {error.reason}: {error}", file=sys.stderr)
        print(json.dumps({"result": "refused", "stop": error.reason}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
