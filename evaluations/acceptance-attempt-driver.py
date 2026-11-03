#!/usr/bin/env python3
"""Run one frozen paid acceptance attempt from a manifest, scenario by scenario, and stop at the first problem.

  acceptance-attempt-driver.py run --manifest M --out OUT_ROOT [--repo ROOT] [--runner CMD] [--validity CMD]
                                   [--ledger LEDGER] [--grace SECONDS] [--live]

The manifest freezes every input by sha256 and binds each scenario key to its gate (format in
acceptance-attempt-driver.md; the same format as acceptance_review.py's manifest). The driver:
- validates the manifest and every hash before anything, and refuses an OUT_ROOT that already has a driver state or
  any of the attempt's run directories;
- before each scenario, in manifest order: re-verifies every hash, reads the billing ledger (read only, when one is
  given: `blocked` must be false, `run_id` the attempt_id, and `policy_sha256` C5_BILLING_POLICY_SHA256 when set) and
  refuses existing run directories;
- runs RUNNER SCENARIO OUT_ROOT KEY, then VALIDITY OUT_ROOT/KEY-P OUT_ROOT/KEY-E OUT_ROOT/KEY-F;
- stops at the first non-zero exit (any runner exit but 0 is a scenario failure, including the run script's
  supervisor exits after a failed or refused arm), invalid scenario, changed input or blocked ledger. It never
  starts another scenario after that, and it never resumes, reuses or retries anything.

Live mode is on with --live, or whenever C5_BILLING_LEDGER, C5_ATTEMPT_ID or any provider credential (*_API_KEY) is
set. It refuses --runner and --validity: it runs only the repository's evaluations/c5-run-scenario.sh and `<this
python> evaluations/acceptance_review.py validity`, which must be frozen in the manifest's files together with
evaluations/c5-harness.py. It requires C5_ATTEMPT_ID equal to the attempt_id and a 64-hex C5_BILLING_POLICY_SHA256
equal to the ledger's policy_sha256. Its ledger is C5_BILLING_LEDGER (required, absolute; a different --ledger is
refused). On a
stop the driver decides itself (invalid, hash_mismatch including inputs changed during a scenario, run_dir_exists,
driver_error) it blocks the shared billing run for every future provider call by running the harness's own entry
point, `<C5_PYTHON or uv run python> evaluations/c5-harness.py --stop`, exactly as the run script's supervisor does.
That entry point takes no reason, so the ledger records the harness's own reason ("arm_failed" unless already set);
the driver's reason is in its state file. Without live mode (offline tests), overrides are allowed, no shared
stop runs, and the state file and summary say "mode": "offline", "evidence": "offline_test_only".

OUT_ROOT/attempt-state.json is replaced atomically after every step. It records statuses, times, exit codes and log
paths only: never a scenario's content and never a child's output (children write to log files). A pair is
`complete` when all its scenarios are valid, and stays complete when a later scenario fails; the driver reports
which gates have a complete pair and never decides R4 or C5. The last stdout line is a one-line JSON summary.

Exit codes: 0 every scenario ran and was valid; 1 stopped; 2 refused before any scenario started; 128 + signal
number after SIGINT or SIGTERM. A signal goes first to the runner alone, so the run script's supervisor can block the
billing ledger before it stops its arms; after --grace seconds the runner's whole process group gets SIGTERM, and
after twice that SIGKILL. A signal never cuts the shared stop short. The driver itself only ever reads the ledger.
Standard library only; runs on the system Python 3 of macOS.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

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
    """As acceptance_review.py's _repo_path: a normalised POSIX path, not absolute, with no empty, "." or ".." part.
    (A NUL byte passes here as it does there; the containment check before any hashing refuses it.)"""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{what} must be a non-empty repo-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts) or "/".join(path.parts) != value:
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
    """The shared manifest format: raises ValueError naming the first structural problem. It accepts and rejects
    exactly what acceptance_review.py's load_manifest does (structure only, not the files on disk)."""
    _exact(manifest, {"version", "attempt_id", "files", "pairs", "order"}, "the manifest")
    if type(manifest["version"]) is not int or manifest["version"] != 1:
        raise ValueError("version must be 1")
    attempt = manifest["attempt_id"]
    if not isinstance(attempt, str) or not attempt.strip():
        raise ValueError("attempt_id must be a non-empty string")
    files = manifest["files"]
    if not isinstance(files, dict):
        raise ValueError("files must be an object of path to sha256")
    for path, digest in files.items():
        _digest(digest, f"files[{_relative(path, 'a files entry')!r}]")
    pairs = manifest["pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("pairs must be a non-empty list")
    keys, paths, stems, gates = set(), set(), set(), set()
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
            if not path.endswith(".py"):
                raise ValueError(f"scenario {key}'s path must be a .py file")
            if path in paths:
                raise ValueError(f"scenario path {path!r} appears more than once")
            paths.add(path)
            stem = PurePosixPath(path).stem
            if stem in stems:
                raise ValueError(f"scenario file stem {stem!r} appears more than once")
            stems.add(stem)
            _digest(scenario["sha256"], f"scenario {key}'s sha256")
            if path in files and files[path] != scenario["sha256"]:
                raise ValueError(f"scenario {key}'s sha256 differs from its entry in files")
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
        manifest = json.loads(data.decode("utf-8"))
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


def ledger_problem(path: Path, attempt_id: str, policy_sha256: str | None) -> tuple[str, str] | None:
    """(reason, detail) when the billing ledger stops the attempt; it is only read, never written. Anything but an
    explicit `blocked: false` stops it, and so does a `run_id` other than the manifest's attempt_id or, when
    C5_BILLING_POLICY_SHA256 is given, a `policy_sha256` other than it."""
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return "ledger_blocked", f"the billing ledger is unreadable: {type(error).__name__}"
    if not isinstance(state, dict) or state.get("blocked") is not False:
        return "ledger_blocked", ("the billing ledger is blocked" if isinstance(state, dict) and state.get("blocked")
                                  is True else "the billing ledger has no explicit blocked=false")
    if state.get("run_id") != attempt_id:
        return "ledger_mismatch", "the billing ledger's run_id differs from the manifest's attempt_id"
    if policy_sha256 is not None and state.get("policy_sha256") != policy_sha256:
        return "ledger_mismatch", "the billing ledger's policy_sha256 differs from C5_BILLING_POLICY_SHA256"
    return None


MAX_GRACE_SECONDS = 600.0
LIVE_RUNNER = "evaluations/c5-run-scenario.sh"
LIVE_VALIDITY = "evaluations/acceptance_review.py"
LIVE_STOPPER = "evaluations/c5-harness.py"
SHARED_STOP_SECONDS = 300.0
# Stops the driver decides itself. On these, in live mode, it blocks the shared billing run for every future provider
# call through the harness's own `--stop` entry point. A failed runner is left to the run script's supervisor, which
# blocks the ledger itself after any arm started; a ledger already blocked or bound elsewhere needs nothing.
SHARED_STOPS = ("invalid", "hash_mismatch", "run_dir_exists", "driver_error")


def _grace(text) -> float:
    """A finite, positive grace period of at most MAX_GRACE_SECONDS: NaN or infinity would disable escalation."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        value = math.nan
    if not (math.isfinite(value) and 0 < value <= MAX_GRACE_SECONDS):
        raise Refused("usage", f"--grace must be a finite number of seconds above 0 and at most {MAX_GRACE_SECONDS:g}")
    return value


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


def is_live(args, environ=None) -> bool:
    """Live mode: --live, any C5_BILLING_LEDGER or C5_ATTEMPT_ID, or any provider credential (a *_API_KEY variable,
    whatever its value). With a credential present a provider call is possible, so the full binding is required;
    offline test runs must clear such keys."""
    environ = os.environ if environ is None else environ
    return bool(args.live or "C5_BILLING_LEDGER" in environ or "C5_ATTEMPT_ID" in environ
                or any(name.endswith("_API_KEY") for name in environ))


def evidence(live: bool) -> dict:
    """Marks every summary: an offline run (overridable commands, no billing binding) is never attempt evidence."""
    return {"mode": "live" if live else "offline", "evidence": "live_attempt" if live else "offline_test_only"}


class Driver:
    def __init__(self, args):
        self.repo = Path(args.repo).resolve()
        self.out = Path(args.out).absolute()
        self.manifest_path = Path(args.manifest).absolute()
        self.live = is_live(args)
        if self.live and (args.runner or args.validity):
            raise Refused("live_override", "a live attempt runs only the repository's own run script and validity "
                                           "check: --runner and --validity are for offline tests")
        self.ledger = Path(args.ledger).absolute() if args.ledger else None
        if self.live:
            billing = os.environ.get("C5_BILLING_LEDGER", "")
            if not billing or not os.path.isabs(billing):
                raise Refused("ledger_required", "a live attempt needs an absolute C5_BILLING_LEDGER")
            if self.ledger is not None and self.ledger != Path(billing):
                raise Refused("environment", "--ledger differs from C5_BILLING_LEDGER")
            self.ledger = Path(billing)
        self.policy_sha256 = os.environ.get("C5_BILLING_POLICY_SHA256") or None
        self.runner = _command(args.runner or LIVE_RUNNER, self.repo)
        self.validity = (_command(args.validity, self.repo) if args.validity
                         else [sys.executable, str(self.repo / LIVE_VALIDITY), "validity"])
        # The run script's own interpreter choice, so the harness can load its billing guard.
        python = [os.environ["C5_PYTHON"]] if os.environ.get("C5_PYTHON") else ["uv", "run", "python"]
        self.stopper = python + [str(self.repo / LIVE_STOPPER), "--stop"] if self.live else None
        self.child: subprocess.Popen | None = None
        self.protected = False  # The running child is the shared billing stop, which a signal must not cut short.
        self.terminated: int | None = None  # The child pid that has been sent SIGTERM for a signal.
        self.signalled_at = 0.0
        self.grace = _grace(args.grace)
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
        if self.live and (not os.environ.get("C5_ATTEMPT_ID") or os.environ["C5_ATTEMPT_ID"] != attempt):
            raise Refused("attempt_binding", "a live attempt needs C5_ATTEMPT_ID equal to the manifest's attempt_id")
        if self.live and not _SHA256.fullmatch(self.policy_sha256 or ""):
            raise Refused("policy_binding", "a live attempt needs C5_BILLING_POLICY_SHA256: 64 lowercase hex "
                                            "characters, matching the ledger's policy_sha256")
        billing = os.environ.get("C5_BILLING_LEDGER")
        if self.ledger and billing and Path(billing).absolute() != self.ledger:
            raise Refused("environment", "--ledger differs from C5_BILLING_LEDGER")
        frozen = set(self.manifest["files"])
        if self.live:
            missing = [path for path in (LIVE_RUNNER, LIVE_VALIDITY, LIVE_STOPPER) if path not in frozen]
            if missing:
                raise Refused("unfrozen_command", f"a live attempt needs these in the manifest's files: "
                                                  f"{', '.join(missing)}")
        driver = Path(__file__).resolve()
        unfrozen = unfrozen_command_files(self.runner + self.validity, self.repo, frozen)
        if self.repo in driver.parents and driver.relative_to(self.repo).as_posix() not in frozen:
            unfrozen.append(driver.relative_to(self.repo).as_posix())
        if unfrozen:
            raise Refused("unfrozen_command", f"not frozen in the manifest's files: {', '.join(sorted(unfrozen))}")
        problem = verify(self.repo, self.manifest, self.manifest_path, self.manifest_sha256)
        if problem:
            raise Refused("hash_mismatch", problem)
        if self.ledger and (problem := ledger_problem(self.ledger, attempt, self.policy_sha256)):
            raise Refused(*problem)
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
            **evidence(self.live),
            "shared_stop": None,
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
        if not self.protected:
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

    def spawn(self, argv: list[str], log: Path, *, protect: float | None = None) -> int:
        """Run a child in its own process group with its output going to LOG only, and return its exit code.
        Polls (never `wait -n`). On SIGINT/SIGTERM: SIGTERM to the leader; after the grace period SIGTERM to the
        whole group; after another, SIGKILL to the group. After the leader exits, for any reason, whatever is left of
        its group gets SIGTERM and, if still there after the grace period, SIGKILL. With PROTECT (seconds), a signal
        does not stop the child; it gets that long, then its group gets SIGKILL and the exit code is -9."""
        self.protected = protect is not None
        with log.open("ab") as output:
            try:
                self.child = subprocess.Popen(argv, cwd=self.repo, stdin=subprocess.DEVNULL, stdout=output,
                                              stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as error:
                output.write(f"driver: could not start {argv[0]}: {type(error).__name__}\n".encode())
                self.protected = False
                return 127
        pgid = self.child.pid
        deadline = None if protect is None else time.monotonic() + protect
        try:
            while True:
                if deadline is not None and time.monotonic() > deadline:
                    self.kill_group(pgid, signal.SIGKILL)
                elif self.signal is not None and protect is None:  # Also a signal from just before the start.
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
            self.child, self.protected = None, False

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
        if self.ledger and (problem := ledger_problem(self.ledger, self.manifest["attempt_id"], self.policy_sha256)):
            self.stop(key, *problem)
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

    def shared_stop(self) -> None:
        """Block the shared billing run for every future provider call, through the harness's own entry point (the
        one the run script's supervisor uses). The driver never writes the ledger itself. A signal does not cut this
        short; a stopper still running after SHARED_STOP_SECONDS is killed and recorded as failed."""
        log = self.out / LOGS / "shared-stop.log"
        record = {"reason": self.state["stop"]["reason"], "command": self.stopper, "exit": None,
                  "started_at": _now(), "finished_at": None, "log": str(log)}
        self.state["shared_stop"] = record
        self.save()
        try:
            record["exit"] = self.spawn(self.stopper, log, protect=SHARED_STOP_SECONDS)
        except Exception as error:  # Recorded as a failed stop; the attempt is stopped either way.
            print(f"driver: shared stop error: {type(error).__name__}", file=sys.stderr)
        record["finished_at"] = _now()
        if record["exit"] != 0:
            print(f"driver: the shared billing stop FAILED (exit {record['exit']}): block the ledger by hand",
                  file=sys.stderr)
        else:
            print("driver: the shared billing run is stopped", file=sys.stderr)

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
        if self.live and self.state["stop"] and self.state["stop"]["reason"] in SHARED_STOPS:
            self.shared_stop()
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
    return {**{key: state[key] for key in ("mode", "evidence")},
            "attempt_id": state["attempt_id"], "result": state["result"],
            "stop": state["stop"]["reason"] if state["stop"] else None,
            "scenarios": {key: record["status"] for key, record in state["scenarios"].items()},
            "pairs": {pair["gate"]: pair["status"] for pair in state["pairs"]},
            "eligible": sorted(gate for gate, ok in state["eligible"].items() if ok),
            "shared_stop": (None if not state.get("shared_stop")
                            else "blocked" if state["shared_stop"]["exit"] == 0 else "failed")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run every scenario of a frozen manifest in order")
    run.add_argument("--manifest", required=True)
    run.add_argument("--out", required=True, help="OUT_ROOT for run directories and attempt-state.json")
    run.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    run.add_argument("--runner", help="offline tests only; refused in live mode (default: "
                                      "evaluations/c5-run-scenario.sh)")
    run.add_argument("--validity", help="offline tests only; refused in live mode (default: this Python, "
                                        "evaluations/acceptance_review.py validity)")
    run.add_argument("--ledger", help="billing ledger JSON whose blocked flag is read before each scenario; in live "
                                      "mode it is C5_BILLING_LEDGER")
    run.add_argument("--live", action="store_true",
                     help="live mode (also on whenever C5_BILLING_LEDGER, C5_ATTEMPT_ID or any *_API_KEY is "
                          "set): no command override, a required attempt, ledger and policy binding, and a shared "
                          "billing stop on every stop the driver decides")
    run.add_argument("--grace", default="60",
                     help="seconds a child gets after each stop signal before the next escalation (default 60, "
                          "finite, above 0, at most 600)")
    args = parser.parse_args(argv)
    try:
        return Driver(args).run()
    except Refused as error:
        print(f"driver: refused: {error.reason}: {error}", file=sys.stderr)
        print(json.dumps({**evidence(is_live(args)), "result": "refused", "stop": error.reason}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
