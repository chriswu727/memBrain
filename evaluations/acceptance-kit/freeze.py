#!/usr/bin/env python3
"""Freeze an R4 behavioural-acceptance attempt: hash every frozen file and the held-out scenarios into the manifest
the attempt driver validates (acceptance-attempt-driver.md, "Manifest").

  freeze.py --repo REPO --attempt-id ID --private-root REL --out MANIFEST --allowed-models REL
            --scenario KEY=REL_PATH [--scenario KEY=REL_PATH ...]
            [--receipt KEY=REL_PATH ...] [--control REL_PATH ...] [--binding REL] [--python PATH] [--no-receipts]

- Every scenario is read without running it (scenario_literals.py); every held-out scenario must pass
  `c5-precheck.py --r4`, run in a subprocess with the repository's interpreter (REPO/.venv/bin/python unless
  --python), and only the precheck's own codes are relayed.
- The lead's allowed-models file (the session models launch.py accepted) is required and frozen.
- With --binding (the committed execution binding), the binding must name the attempt id in backquotes: the persona
  seed is the attempt id fixed there before the draw is computed.
- Errors never print a traceback or any text from a scenario.

- REPO is the execution clone. Paths are repo-relative; scenarios, receipts and control files must lie inside the
  private root REL (git-excluded in the execution clone) and scenarios must not be tracked by git: a held-out
  scenario is never committed.
- Frozen files: every git-tracked file under src/, migrations/, plugins/, scripts/, sdk/, integrations/ and
  architecture/; every tracked top-level evaluations/*.py and *.sh; evaluations/acceptance-review/*.md;
  evaluations/acceptance-kit/*; evaluations/maturity-*.md and evaluations/maturity-provider-policy-*.json;
  AGENTS.md, pyproject.toml and uv.lock; plus every --control and --receipt file, and the scenarios.
- The working tree must be clean outside the private root (no tracked change, no untracked file elsewhere).
- Each scenario needs its review receipt (KEY=path of a JSON {"key", "sha256", "cases", "turns", "approved": true,
  ...} written by launch.py for the approving reviewer), whose hash, case count and turn count must match the
  scenario file. --no-receipts is for the public stub rehearsal only: every scenario must be a practice copy (its file
  name contains "practice"), the manifest records "practice": true (the live driver refuses it), and the summary
  says so. A practice copy is never frozen with receipts.
- The manifest has one R4 pair with the scenarios in the given order, "order" the same, and "persona" the draw of
  the attempt id (acceptance_persona.py). It is validated with both the review pipeline's load_manifest and the
  driver's validate_manifest before it is written; an existing MANIFEST is refused.

It prints one JSON line: attempt id, manifest sha256, file count, each scenario's key, sha256, session, turn and case
counts, and the persona type. It never prints a scenario's content (loading a scenario discards its output).
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

TRACKED_TREES = ("src/", "migrations/", "plugins/", "scripts/", "sdk/", "integrations/", "architecture/")
TOP_FILES = ("AGENTS.md", "pyproject.toml", "uv.lock")


class Refused(Exception):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *arguments) -> list[str]:
    done = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused(f"git {arguments[0]} failed")
    return [line for line in done.stdout.split("\0" if "-z" in arguments else "\n") if line]


def _relative(repo: Path, value: str, what: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts) or "/".join(path.parts) != value:
        raise Refused(f"{what} must be a normalised repo-relative path")
    resolved = (repo / value).resolve()
    if repo not in resolved.parents:
        raise Refused(f"{what} leaves the repository")
    if not resolved.is_file():
        raise Refused(f"{what} is not a file")
    return value


def frozen_tracked(repo: Path) -> list[str]:
    tracked = _git(repo, "ls-files", "-z")
    chosen = []
    for path in tracked:
        top = path.count("/") == 1 and path.startswith("evaluations/")
        if (path.startswith(TRACKED_TREES) or path in TOP_FILES
                or (top and path.endswith((".py", ".sh")))
                or (path.startswith("evaluations/acceptance-review/") and path.endswith(".md"))
                or path.startswith("evaluations/acceptance-kit/")
                or (top and PurePosixPath(path).name.startswith("maturity-")
                    and (path.endswith(".md") or PurePosixPath(path).name.startswith("maturity-provider-policy-")))):
            if (repo / path).is_file():
                chosen.append(path)
    return sorted(chosen)


def check_clean(repo: Path, private_root: str) -> None:
    prefix = private_root.rstrip("/") + "/"
    for entry in _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        code, path = entry[:2], entry[3:]
        if code == "??" and (path + "/").startswith(prefix):
            continue
        raise Refused("the working tree is not clean outside the private root")


def scenario_counts(path: Path, evaluations: Path) -> dict:
    """Counts from the scenario read without running it (literal assignments only); never its text."""
    literals = _module("scenario_literals_for_freeze", evaluations / "scenario_literals.py")
    try:
        module = literals.read(path)
        sessions = list(getattr(module, "SESSIONS_LONG", None) or [])
        return {"sessions": len(sessions), "turns": sum(len(turns) for _, turns in sessions),
                "cases": len(list(getattr(module, "CASES", None) or []))}
    except literals.NotLiteral as error:
        raise Refused(f"a scenario is not literal assignments only ({error.code})") from None
    except (TypeError, ValueError):
        raise Refused("a scenario's sessions are malformed") from None


def precheck(python: Path, evaluations: Path, path: Path) -> list[str]:
    """`c5-precheck.py --r4` in a subprocess with the repository's interpreter: [] when ok, else its codes (only
    codes the precheck itself defines are relayed)."""
    known = set(_module("c5_precheck_codes_for_freeze", evaluations / "c5-precheck.py").CODES)
    done = subprocess.run([str(python), str(evaluations / "c5-precheck.py"), "--r4", str(path)],
                          capture_output=True, text=True, timeout=300)
    try:
        summary = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return ["precheck_unreadable"]
    if done.returncode == 0 and summary.get("ok") is True:
        return []
    codes = summary.get("codes") if isinstance(summary.get("codes"), list) else []
    return sorted({code if code in known else "unknown_code" for code in codes}) or ["precheck_failed"]


def is_practice(path: str) -> bool:
    return "practice" in PurePosixPath(path).name


def _pairs(values: list[str], what: str) -> list[tuple[str, str]]:
    pairs = []
    for value in values:
        key, separator, path = value.partition("=")
        if not separator or not key or not path:
            raise Refused(f"{what} takes KEY=PATH")
        pairs.append((key, path))
    if len({key for key, _ in pairs}) != len(pairs):
        raise Refused(f"{what} names a key twice")
    return pairs


def freeze(args) -> dict:
    repo = Path(args.repo).resolve()
    out = Path(args.out).absolute()
    if out.exists():
        raise Refused("the manifest already exists: it is written once")
    private = args.private_root.strip("/")
    if not private or PurePosixPath(private).is_absolute() or ".." in PurePosixPath(private).parts:
        raise Refused("--private-root must be a repo-relative directory")
    scenarios = _pairs(args.scenario, "--scenario")
    receipts = dict(_pairs(args.receipt, "--receipt"))
    if not scenarios:
        raise Refused("at least one --scenario is required")
    if args.no_receipts and receipts:
        raise Refused("--no-receipts and --receipt exclude each other")
    if args.no_receipts and not all(is_practice(path) for _, path in scenarios):
        raise Refused("--no-receipts is for practice copies only (a file name containing 'practice')")
    if not args.no_receipts and any(is_practice(path) for _, path in scenarios):
        raise Refused("a practice scenario is never frozen as a held-out one")
    python = Path(args.python) if args.python else repo / ".venv" / "bin" / "python"
    if not python.is_file():
        raise Refused("the repository's interpreter is missing (give --python)")
    if not args.no_receipts and set(receipts) != {key for key, _ in scenarios}:
        raise Refused("every scenario needs exactly one --receipt (or --no-receipts for the stub rehearsal)")
    tracked = set(_git(repo, "ls-files", "-z"))
    for what, path in [*((f"scenario {key}", path) for key, path in scenarios),
                       *((f"receipt {key}", path) for key, path in receipts.items()),
                       *(("control file", path) for path in args.control),
                       ("the allowed-models file", args.allowed_models)]:
        _relative(repo, path, what)
        if not path.startswith(private + "/"):
            raise Refused(f"{what} must lie inside the private root")
    if any(path in tracked for _, path in scenarios):
        raise Refused("a held-out scenario is tracked by git")
    check_clean(repo, private)
    try:
        models = json.loads((repo / args.allowed_models).read_text())
    except (OSError, ValueError):
        models = None
    if not isinstance(models, list) or not models or not all(isinstance(name, str) and name for name in models):
        raise Refused("the allowed-models file must be a non-empty JSON list of model names")
    if args.binding:
        _relative(repo, args.binding, "the binding")
        if args.binding not in tracked:
            raise Refused("the binding must be committed before freezing")
        if f"`{args.attempt_id}`" not in (repo / args.binding).read_text(encoding="utf-8"):
            raise Refused("the binding does not name this attempt id: the persona seed is fixed by the binding")

    evaluations = repo / "evaluations"
    files = {path: sha256(repo / path) for path in frozen_tracked(repo)}
    for path in [*args.control, *receipts.values(), args.allowed_models]:
        files[path] = sha256(repo / path)
    entries, printed = [], []
    for key, path in scenarios:
        digest = sha256(repo / path)
        counts = scenario_counts(repo / path, evaluations)
        if not is_practice(path):
            codes = precheck(python, evaluations, repo / path)
            if codes:
                raise Refused(f"scenario {key} fails the R4 precheck: {', '.join(codes)}")
        if key in receipts:
            receipt = json.loads((repo / receipts[key]).read_text())
            if not isinstance(receipt, dict) or receipt.get("approved") is not True or receipt.get("key") != key:
                raise Refused(f"the receipt for {key} is not an approval of that scenario")
            if receipt.get("sha256") != digest:
                raise Refused(f"the receipt for {key} approves other bytes than the scenario file")
            if receipt.get("cases") != counts["cases"] or receipt.get("turns") != counts["turns"]:
                raise Refused(f"the receipt for {key} gives other counts than the scenario file")
        files[path] = digest
        entries.append({"key": key, "path": path, "sha256": digest})
        printed.append({"key": key, "sha256": digest, **counts})
    drawing = _module("acceptance_persona_for_freeze", evaluations / "acceptance_persona.py")
    manifest = {"version": 1, "attempt_id": args.attempt_id, "files": dict(sorted(files.items())),
                "pairs": [{"gate": "R4", "scenarios": entries}], "order": [key for key, _ in scenarios],
                "persona": drawing.record(args.attempt_id)}
    if args.no_receipts:
        manifest["practice"] = True  # Frozen without review receipts: the live driver refuses it.
    data = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8")
    temporary = out.with_name(out.name + ".partial")
    temporary.write_bytes(data)
    try:
        review = _module("acceptance_review_for_freeze", evaluations / "acceptance_review.py")
        driver = _module("acceptance_driver_for_freeze", evaluations / "acceptance-attempt-driver.py")
        try:
            review.load_manifest(temporary)
            driver.validate_manifest(json.loads(data))
        except ValueError as error:
            raise Refused(f"the manifest does not validate: {error}") from None
        os.link(temporary, out)  # Exclusive: never replaces a manifest.
    finally:
        temporary.unlink(missing_ok=True)
    return {"attempt_id": args.attempt_id, "manifest_sha256": hashlib.sha256(data).hexdigest(),
            "files": len(manifest["files"]), "scenarios": printed, "persona": manifest["persona"]["preset"],
            "receipts": "none (stub rehearsal)" if args.no_receipts else len(receipts)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--receipt", action="append", default=[])
    parser.add_argument("--control", action="append", default=[])
    parser.add_argument("--no-receipts", action="store_true", help="the public stub rehearsal only")
    parser.add_argument("--allowed-models", required=True,
                        help="the lead's allowed-models.json in the private root (frozen as a control file)")
    parser.add_argument("--binding", help="the committed execution binding; it must name the attempt id")
    parser.add_argument("--python", help="the repository's interpreter for the precheck (default REPO/.venv/bin/python)")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(freeze(args), sort_keys=True))
    except Refused as error:
        print(json.dumps({"refused": str(error)}))
        return 2
    except Exception as error:  # noqa: BLE001 - never a traceback: it could quote a scenario's lines.
        print(json.dumps({"refused": f"internal error ({type(error).__name__})"}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
