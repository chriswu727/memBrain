#!/usr/bin/env python3
"""The free, zero-network rehearsal of a two-arm R4 attempt, end to end, with the stub host.

  python evaluations/r4-stub-rehearsal.py OUT_ROOT [--keep]

OUT_ROOT must not exist and must lie outside the repository. Nothing here calls a model: the harness runs with
C5_STUB=1 (its stub host answers from r4-practice-scenario.py's script, and every non-loopback connection is refused
and recorded), and the driver runs offline. It refuses to start when any provider credential (*_API_KEY),
C5_BILLING_LEDGER or C5_ATTEMPT_ID is set, because the driver would then be live. Steps:

1. Two copies of the public practice scenario (distinct case prefixes) go into a private root inside the repository,
   evaluations/.r4-rehearsal-<id>/ (removed afterwards), as held-out scenarios would.
2. acceptance-kit/freeze.py writes the manifest (--no-receipts: practice only), with the persona draw of the attempt id.
3. A billing ledger is created from the attempt's policy file (one model, 80 CNY) and given to the driver read-only.
4. The real driver runs the real run script per scenario: P, cleanup of P (installation stopped, ports checked), then
   F; then strict validity on both run directories.
5. c5-dry-run-check.py checks each scenario's two arms (persona in both, tools, server instructions, consolidation,
   pause and resume, dates, sequence, cleanup, no network).
6. The review pipeline runs on synthetic reviewer outputs (no reviewer, no model): blind sheets for "PF", first-review
   verdicts, split, second reviews, R5 inputs and checks, an empty resolution, tallies bound to the manifest,
   attribution inputs and answers, and the gate. One gated reply carries a host-caused critical mark and one
   reference reply a critical mark, so the attribution and the host-caused comparison are exercised.
7. It checks that no run's harness process attempted a network connection (the local service subprocess is outside
   that check, and the summary says so), that the ledger is byte-for-byte unchanged with no request,
   and that P's ports are closed; then it deletes the stopped synthetic databases (brain-* directories) unless --keep.

The last stdout line is one JSON summary. Exit 0 only when every step passed. Practice content only.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALUATIONS = REPO / "evaluations"
PRACTICE = EVALUATIONS / "r4-practice-scenario.py"
POLICY = EVALUATIONS / "maturity-provider-policy-2026-11-14.json"
MODEL_CACHE = Path(os.environ.get("MEMBRAIN_MODEL_CACHE") or Path.home() / ".cache/membrain/eval-embedding-model")
P_PORTS = (8893, 55533)
KEYS = ("s1", "s2")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False))
    return path


def port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def review_cli(*arguments, check=True) -> subprocess.CompletedProcess:
    done = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), *map(str, arguments)],
                          capture_output=True, text=True, cwd=REPO)
    if check and done.returncode != 0:
        raise RuntimeError(f"acceptance_review.py {arguments[0]} failed: {done.stdout[-400:]} {done.stderr[-400:]}")
    return done


def synthetic_reviews(review: Path, blind: Path, scenario: Path, key: str, gated_critical: bool,
                      reference_critical: bool) -> None:
    """Reviewer outputs as fresh reviewers would write them, made by this script. It reads the sealed mapping only to
    place the planted marks on a chosen arm; a real reviewer never sees it."""
    module = _module(f"rehearsal_{key}", scenario)
    sealed = json.loads((blind / f"sealed_{scenario.stem}.json").read_text())
    labels = sorted(next(iter(sealed.values())))
    cases = [case for _, _, case, _ in module.CASES]
    marks = {}
    if gated_critical:  # A type 4 mark on P's reply in the first case: attributed to the host by both attributors.
        marks[(cases[0], next(label for label, arm in sealed[cases[0]].items() if arm == "P"))] = [4]
    if reference_critical:  # A type 1 mark on F's reply in the second case.
        marks[(cases[1], next(label for label, arm in sealed[cases[1]].items() if arm == "F"))] = [1]
    verdicts = {case: {label: {"score_ignoring_critical": 1, "critical": marks.get((case, label), []),
                               "conditions": [], "reason": "Synthetic rehearsal verdict."} for label in labels}
                for case in cases}
    put(review / f"verdicts-{key}.json", verdicts)
    review_cli("verdicts", review / f"verdicts-{key}.json", scenario)
    review_cli("split", blind / f"blind_{scenario.stem}.md", review / f"verdicts-{key}.json", blind, scenario,
               review / f"recheck-{key}")
    for case in cases:
        put(review / f"recheck-{key}" / f"{case}.json", {label: {
            "critical": marks.get((case, label), []), "confirmed": marks.get((case, label), []), "rejected": [],
            "added": [], "evidence": "Synthetic rehearsal evidence." if marks.get((case, label)) else ""}
            for label in labels})
    review_cli("r5-inputs", review, blind, scenario, key, review / f"r5-inputs-{key}")
    answers = review / f"r5-answers-{key}"
    answers.mkdir(parents=True, exist_ok=True)
    for source in sorted((review / f"r5-inputs-{key}").glob("*.md")):
        for checker in ("1", "2"):
            put(answers / f"{source.stem}.{checker}.json", {
                "claims": [{"quote": "synthetic", "kind": "user_fact", "supported": None, "entry": ""}],
                "type4_cleared": False})
    review_cli("r5-check", review / f"r5-inputs-{key}", answers, review / f"r5-{key}")
    put(review / f"resolution-{key}.json", {})


def run(out: Path, keep: bool, summary: dict) -> dict:
    summary.update(ok=False, steps={})
    for name in os.environ:
        if name.endswith("_API_KEY") or name in ("C5_BILLING_LEDGER", "C5_ATTEMPT_ID"):
            raise SystemExit(f"refused: {name} is set; the rehearsal runs only with every provider variable unset")
    if out.exists() or REPO in out.resolve().parents:
        raise SystemExit("refused: OUT_ROOT must be new and outside the repository")
    if not MODEL_CACHE.is_dir():
        raise SystemExit("refused: the local embedding model cache (MEMBRAIN_MODEL_CACHE) is missing")
    if any(port_open(port) for port in P_PORTS):
        raise SystemExit(f"refused: ports {P_PORTS} are in use")
    attempt = "r4-stub-rehearsal-" + time.strftime("%Y%m%d") + "-" + secrets.token_hex(3)
    private_rel = f"evaluations/.r4-rehearsal-{attempt}"
    private = REPO / private_rel
    out.mkdir(parents=True)
    control = out / "control"
    control.mkdir()
    try:
        private.mkdir(mode=0o700)
        paths = []
        for index, key in enumerate(KEYS):
            target = private / key / f"r4_practice_{key}.py"
            target.parent.mkdir(mode=0o700)
            text = PRACTICE.read_text()
            if index:
                text = text.replace('"R4P', '"R4Q')  # CASE_PREFIX and every case id.
            target.write_text(text)
            target.chmod(0o600)
            paths.append(target)
        manifest = control / "manifest.json"
        (private / "control").mkdir(mode=0o700)
        allowed = private / "control" / "allowed-models.json"
        allowed.write_text(json.dumps(["practice-model-not-used"]))  # No session is launched in a rehearsal.
        frozen = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance-kit" / "freeze.py"), "--repo", str(REPO),
                                 "--attempt-id", attempt, "--private-root", private_rel, "--out", str(manifest),
                                 "--no-receipts", "--python", sys.executable,
                                 "--allowed-models", allowed.relative_to(REPO).as_posix(),
                                 *[item for key, path in zip(KEYS, paths)
                                   for item in ("--scenario", f"{key}={path.relative_to(REPO).as_posix()}")]],
                                capture_output=True, text=True)
        summary["steps"]["freeze"] = json.loads(frozen.stdout.strip().splitlines()[-1])
        if frozen.returncode != 0:
            raise RuntimeError("freeze refused")
        summary["steps"]["freeze"]["manifest_marked_practice"] = json.loads(manifest.read_text()).get("practice")
        budget = _module("evaluation_budget_for_rehearsal", EVALUATIONS / "evaluation_budget.py")
        policy = json.loads(POLICY.read_text())
        models = {name: {key: value for key, value in rate.items()} for name, rate in policy["models"].items()}
        ledger = control / "ledger.json"
        bound = budget.create_ledger(ledger, run_id=attempt, limit_cny=policy["proposed_limit_cny"],
                                     endpoint=policy["endpoint"], models=models)
        before = sha(ledger)
        environment = {key: value for key, value in os.environ.items()
                       if not key.endswith("_API_KEY") and not key.startswith(("C5_", "MEMBRAIN_", "MEMORY_"))}
        environment.update(C5_STUB="1", C5_PYTHON=sys.executable, MEMBRAIN_MODEL_CACHE=str(MODEL_CACHE),
                           PYTHON_DOTENV_DISABLED="1")
        runs = out / "runs"
        driver = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance-attempt-driver.py"), "run",
                                 "--manifest", str(manifest), "--out", str(runs), "--repo", str(REPO),
                                 "--ledger", str(ledger), "--grace", "60"],
                                capture_output=True, text=True, env=environment, cwd=REPO)
        summary["steps"]["driver"] = json.loads(driver.stdout.strip().splitlines()[-1])
        if driver.returncode != 0:
            raise RuntimeError("the driver stopped")
        checks, remarks, review, blind_root = {}, {}, out / "review", out / "blind"
        for key, path in zip(KEYS, paths):
            done = subprocess.run([sys.executable, str(EVALUATIONS / "c5-dry-run-check.py"), str(path), str(runs), key],
                                  capture_output=True, text=True, cwd=REPO)
            report = json.loads(done.stdout)
            checks[key] = {"ok": report["ok"], "checks": report["checks"],
                           "failures": [failure for layer in report.values() if isinstance(layer, dict)
                                        for failure in layer.get("failures", [])]}
            blind = blind_root / key
            blind.mkdir(parents=True)
            for arm in ("P", "F"):
                shutil.copy(runs / f"{key}-{arm}" / f"results_{path.stem}_{arm}.jsonl", blind)
            subprocess.run([sys.executable, str(EVALUATIONS / "v1-2026-10-29-phase-b-blind.py"), str(blind), str(path),
                            "PF"], check=True, capture_output=True, text=True, cwd=REPO)
            synthetic_reviews(review, blind, path, key, gated_critical=key == KEYS[0],
                              reference_critical=key == KEYS[0])
            review_cli("tally", review, blind, path, key, "--manifest", manifest)
            remarks[key] = json.loads(review_cli("remarks", blind, path).stdout)["arms"]
            review_cli("attribution-inputs", review, blind, path, key, review / f"attribution-inputs-{key}")
            for source in sorted((review / f"attribution-inputs-{key}").glob("*.md")):
                for number in ("1", "2"):
                    put(review / f"attribution-{key}" / f"{source.stem}.{number}.json", {"cause": "host", "per_type": {
                        "4": {"cause": "host", "evidence": "Synthetic rehearsal attribution."}}})
        summary["steps"]["dry_run_check"] = checks
        gate = review_cli("gate", review, *KEYS, "--manifest", manifest, check=False)
        result = json.loads((review / "gate.json").read_text())
        summary["steps"]["gate"] = {"exit": gate.returncode, "R4": result["R4"], "arms": {
            arm: {key: value for key, value in item.items() if key in (
                "total", "reference", "not_worse", "memory_caused", "host_caused", "reference_critical", "passes")}
            for arm, item in result["arms"].items()}, "gated": result["gated"], "frozen_arms": result["frozen_arms"]}
        network = sum(json.loads(line).get("kind") == "network_refused"
                      for events in runs.glob("*/harness-events.jsonl") for line in events.read_text().splitlines())
        state = json.loads(ledger.read_text())
        summary["steps"]["memory_remarks"] = remarks
        summary["steps"]["no_network"] = {"network_refused_events": network,
                                          "scope": "the harness process only: the local memory service runs as a "
                                                   "separate process the harness does not police; it has no provider "
                                                   "key and no model download in a dry run (the model is copied from "
                                                   "the local cache)",
                                          "run_dirs": sorted(path.name for path in runs.iterdir() if path.is_dir()
                                                             and path.name != "driver-logs")}
        summary["steps"]["ledger"] = {"unchanged": sha(ledger) == before, "requests": len(state["requests"]),
                                      "blocked": state["blocked"], "policy_sha256": bound["policy_sha256"]}
        summary["steps"]["ports_closed"] = not any(port_open(port) for port in P_PORTS)
        summary["ok"] = (summary["steps"]["driver"]["result"] == "complete"
                         and summary["steps"]["freeze"]["manifest_marked_practice"] is True
                         and all(item["ok"] for item in checks.values())
                         and result["R4"] is True and gate.returncode == 0 and network == 0
                         and summary["steps"]["ledger"]["unchanged"] and not state["requests"]
                         and summary["steps"]["ports_closed"])
        if summary["ok"] and not keep:
            removed = 0
            for database in runs.glob("*/brain-*"):
                shutil.rmtree(database)
                removed += 1
            summary["steps"]["databases_removed"] = removed
        return summary
    finally:
        shutil.rmtree(private, ignore_errors=True)


def main(argv: list[str]) -> int:
    if not argv or len(argv) > 2 or (len(argv) == 2 and argv[1] != "--keep"):
        print(__doc__)
        return 2
    summary: dict = {}
    try:
        run(Path(argv[0]).absolute(), "--keep" in argv, summary)
    except RuntimeError as error:
        summary.update(ok=False, stopped=str(error))
        print(json.dumps(summary, sort_keys=True))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
