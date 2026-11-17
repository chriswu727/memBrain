#!/usr/bin/env python3
"""The free, zero-network rehearsal of a two-arm C5 (companion) attempt, end to end, with the stub host.

  python evaluations/c5-stub-rehearsal.py OUT_ROOT [--keep]

OUT_ROOT must not exist and must lie outside the repository. Nothing here calls a model: the harness runs with
C5_STUB=1 (its stub host answers from c5-practice-scenario.py's script, and every non-loopback connection is refused
and recorded), and the driver runs offline. It refuses to start when any provider credential (*_API_KEY),
C5_BILLING_LEDGER or C5_ATTEMPT_ID is set, because the driver would then be live. Steps, as r4-stub-rehearsal.py
with the C5 pair:

1. Two copies of the public practice scenario (distinct case prefixes) go into a private root inside the repository,
   evaluations/.c5-rehearsal-<id>/ (removed afterwards), as held-out scenarios would.
2. acceptance-kit/freeze.py --gate C5 writes the manifest with the C5 pair (--no-receipts: practice only), with the
   persona draw of the attempt id, validated by both loaders (acceptance_review.load_manifest and the driver's
   validate_manifest) before it is written. Practice copies are not prechecked (they are not of the held-out shape).
3. A billing ledger is created from the attempt's policy file and given to the driver read-only.
4. The real driver runs the real run script per scenario: P, cleanup of P (installation stopped, ports checked), then
   F; then strict validity on both run directories, which checks the page actions and F's persona turn by turn
   (the scenario has PAGE_ACTIONS).
5. c5-dry-run-check.py checks each scenario's two arms (every companion layer, the page actions and their outcomes,
   F's persona and page line, tools, pause and resume, dates, sequence, cleanup, no network).
6. The review pipeline runs in companion mode on synthetic reviewer outputs (no reviewer, no model): blind sheets for
   "PF" from the results and each arm's page-actions.jsonl (the sheet shows, before each case, the page actions so
   far with their outcomes and the persona in effect; the rehearsal checks both blocks are there for every case),
   first-review verdicts, split, second reviews, R5 inputs and checks, the actions digest, an empty
   resolution, tallies bound to the manifest, attribution inputs and answers, remarks, and gate --companion. One
   gated reply carries a host-caused critical mark and one reference reply a critical mark, so the attribution and
   the host-caused comparison are exercised; one gated reply carries a type 8 mark the second reviewer rejects, so
   the actions digest is made for it and checked, and nothing type 7 or 8 stands.
7. It checks that no run's harness process attempted a network connection (the local service subprocess is outside
   that check, and the summary says so), that the ledger is byte-for-byte unchanged with no request, and that P's
   ports are closed; then it deletes the stopped synthetic databases (brain-* directories) unless --keep.

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
PRACTICE = EVALUATIONS / "c5-practice-scenario.py"
POLICY = EVALUATIONS / "maturity-provider-policy-2026-11-14.json"
MODEL_CACHE = Path(os.environ.get("MEMBRAIN_MODEL_CACHE") or Path.home() / ".cache/membrain/eval-embedding-model")
P_PORTS = (8893, 55533)
KEYS = ("c1", "c2")


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


def module_cases(scenario: Path) -> list:
    return list(_module(f"c5_rehearsal_cases_{scenario.stem}", scenario).CASES)


def synthetic_reviews(review: Path, blind: Path, scenario: Path, key: str, runs: list[Path], marked: bool) -> None:
    """Reviewer outputs as fresh reviewers would write them, made by this script. It reads the sealed mapping only to
    place the planted marks on a chosen arm; a real reviewer never sees it."""
    module = _module(f"c5_rehearsal_{key}", scenario)
    sealed = json.loads((blind / f"sealed_{scenario.stem}.json").read_text())
    labels = sorted(next(iter(sealed.values())))
    cases = [case for _, _, case, _ in module.CASES]

    def label(case, arm):
        return next(name for name, which in sealed[case].items() if which == arm)

    first, second = {}, {}
    if marked:
        first[(cases[0], label(cases[0], "P"))] = second[(cases[0], label(cases[0], "P"))] = [4]  # host-caused
        first[(cases[1], label(cases[1], "F"))] = second[(cases[1], label(cases[1], "F"))] = [1]
        first[(cases[2], label(cases[2], "P"))] = [8]  # A deletion case: rejected by the second reviewer.
    verdicts = {case: {name: {"score_ignoring_critical": 1, "critical": first.get((case, name), []),
                              "conditions": [], "reason": "Synthetic rehearsal verdict."} for name in labels}
                for case in cases}
    put(review / f"verdicts-{key}.json", verdicts)
    review_cli("verdicts", review / f"verdicts-{key}.json", scenario, "--companion")
    review_cli("split", blind / f"blind_{scenario.stem}.md", review / f"verdicts-{key}.json", blind, scenario,
               review / f"recheck-{key}")
    for case in cases:
        put(review / f"recheck-{key}" / f"{case}.json", {name: {
            # The second review's critical list is what stands after it: the confirmed marks and the added ones.
            "critical": second.get((case, name), []), "confirmed": second.get((case, name), []),
            "rejected": sorted(set(first.get((case, name), [])) - set(second.get((case, name), []))), "added": [],
            "evidence": "Synthetic rehearsal evidence." if first.get((case, name)) else ""} for name in labels})
    review_cli("r5-inputs", review, blind, scenario, key, review / f"r5-inputs-{key}")
    answers = review / f"r5-answers-{key}"
    answers.mkdir(parents=True, exist_ok=True)
    for source in sorted((review / f"r5-inputs-{key}").glob("*.md")):
        for checker in ("1", "2"):
            put(answers / f"{source.stem}.{checker}.json", {
                "claims": [{"quote": "synthetic", "kind": "user_fact", "supported": None, "entry": ""}],
                "type4_cleared": False})
    review_cli("r5-check", review / f"r5-inputs-{key}", answers, review / f"r5-{key}")
    review_cli("actions-digest", review, blind, scenario, key, *runs)
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
    attempt = "c5-stub-rehearsal-" + time.strftime("%Y%m%d") + "-" + secrets.token_hex(3)
    private_rel = f"evaluations/.c5-rehearsal-{attempt}"
    private = REPO / private_rel
    out.mkdir(parents=True)
    control = out / "control"
    control.mkdir()
    try:
        private.mkdir(mode=0o700)
        paths = []
        for index, key in enumerate(KEYS):
            target = private / key / f"c5_practice_{key}.py"
            target.parent.mkdir(mode=0o700)
            text = PRACTICE.read_text()
            if index:
                text = text.replace('"P0', '"Q0')  # Every case id.
            target.write_text(text)
            target.chmod(0o600)
            paths.append(target)
        manifest = control / "manifest.json"
        (private / "control").mkdir(mode=0o700)
        allowed = private / "control" / "allowed-models.json"
        allowed.write_text(json.dumps(["practice-model-not-used"]))  # No session is launched in a rehearsal.
        frozen = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance-kit" / "freeze.py"), "--repo", str(REPO),
                                 "--attempt-id", attempt, "--private-root", private_rel, "--out", str(manifest),
                                 "--gate", "C5", "--no-receipts", "--python", sys.executable,
                                 "--allowed-models", allowed.relative_to(REPO).as_posix(),
                                 *[item for key, path in zip(KEYS, paths)
                                   for item in ("--scenario", f"{key}={path.relative_to(REPO).as_posix()}")]],
                                capture_output=True, text=True)
        summary["steps"]["freeze"] = json.loads(frozen.stdout.strip().splitlines()[-1])
        if frozen.returncode != 0:
            raise RuntimeError("freeze refused")
        frozen_manifest = json.loads(manifest.read_text())
        summary["steps"]["freeze"].update(manifest_marked_practice=frozen_manifest.get("practice"),
                                          manifest_gate=[pair["gate"] for pair in frozen_manifest["pairs"]])
        budget = _module("evaluation_budget_for_c5_rehearsal", EVALUATIONS / "evaluation_budget.py")
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
        validity = {}
        for key, path in zip(KEYS, paths):
            log = (runs / "driver-logs" / f"{key}.validity.log").read_text().strip().splitlines()
            report = json.loads(log[-1])
            validity[key] = {"valid": report["valid"], "page_actions": report["page_actions"],
                             "persona_mirroring": report["persona_mirroring"],
                             "host_pauses": report["unrecorded_by_the_hosts_own_pause"],
                             "host_diligence_items": sum(len(items) for items in
                                                         (report.get("host_diligence") or {}).values())}
        summary["steps"]["validity"] = validity
        checks, remarks, review, blind_root = {}, {}, out / "review", out / "blind"
        for number, (key, path) in enumerate(zip(KEYS, paths)):
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
                shutil.copy(runs / f"{key}-{arm}" / "page-actions.jsonl", blind / f"page-actions_{path.stem}_{arm}.jsonl")
            subprocess.run([sys.executable, str(EVALUATIONS / "v1-2026-10-29-phase-b-blind.py"), str(blind), str(path),
                            "PF"], check=True, capture_output=True, text=True, cwd=REPO)
            sheet = (blind / f"blind_{path.stem}.md").read_text()
            checks[key]["sheet"] = {"cases": sheet.count("\n**Criteria:**"),
                                    "page_action_blocks": sheet.count("**Page actions so far**"),
                                    "persona_blocks": sheet.count("**Persona in effect at this message:**"),
                                    "persona_history_blocks": sheet.count("**Persona versions so far**"),
                                    "not_applicable_lines": sheet.count("**not_applicable (")}
            coverage = json.loads(review_cli("coverage-report", path, runs / f"{key}-P").stdout.strip().splitlines()[-1])
            checks[key]["coverage_report"] = {"items": len(coverage["items"]),
                                              "made": sum(item["made"] for item in coverage["items"])}
            arm_runs = [runs / f"{key}-P", runs / f"{key}-F"]
            synthetic_reviews(review, blind, path, key, arm_runs, marked=number == 0)
            digest = json.loads((review / f"actions-{key}.json").read_text())["replies"]
            review_cli("tally", review, blind, path, key, "--companion", "--manifest", manifest)
            remarks[key] = json.loads(review_cli("remarks", blind, path).stdout)["arms"]
            review_cli("attribution-inputs", review, blind, path, key, review / f"attribution-inputs-{key}")
            for source in sorted((review / f"attribution-inputs-{key}").glob("*.md")):
                for answer in ("1", "2"):
                    put(review / f"attribution-{key}" / f"{source.stem}.{answer}.json", {"cause": "host", "per_type": {
                        "4": {"cause": "host", "evidence": "Synthetic rehearsal attribution."}}})
            checks[key]["actions_digest_replies"] = len(digest)
        summary["steps"]["dry_run_check"] = checks
        gate = review_cli("gate", review, *KEYS, "--companion", "--manifest", manifest, check=False)
        result = json.loads((review / "gate-c5.json").read_text())
        summary["steps"]["gate"] = {"exit": gate.returncode, "C5": result["C5"], "arms": {
            arm: {key: value for key, value in item.items() if key in (
                "total", "reference", "not_worse", "memory_caused", "host_caused", "reference_critical",
                "boundary_or_deletion_errors", "passes")}
            for arm, item in result["arms"].items()}, "gated": result["gated"], "frozen_arms": result["frozen_arms"],
            "r4_gate_written": (review / "gate.json").exists()}
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
                         and summary["steps"]["driver"]["eligible"] == ["C5"]
                         and frozen_manifest.get("practice") is True
                         and [pair["gate"] for pair in frozen_manifest["pairs"]] == ["C5"]
                         and all(item["valid"] for item in validity.values())
                         and all(item["ok"] for item in checks.values())
                         and all(item["sheet"]["cases"] == item["sheet"]["page_action_blocks"]
                                 == item["sheet"]["persona_blocks"] == item["sheet"]["persona_history_blocks"]
                                 == len(module_cases(path))
                                 and item["coverage_report"]["items"] == item["coverage_report"]["made"] > 0
                                 and item["sheet"]["not_applicable_lines"] > 0
                                 for item, path in zip(checks.values(), paths))
                         and checks[KEYS[0]]["actions_digest_replies"] == 1
                         and result["C5"] is True and gate.returncode == 0
                         and not summary["steps"]["gate"]["r4_gate_written"] and network == 0
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
