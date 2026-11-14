#!/usr/bin/env python3
"""Start ONE isolated scenario author, reviewer or fixer session and print only hashes and counts.

  launch.py --role author|reviewer|fixer --key KEY --private PRIVATE_ROOT --tool codex|claude --model MODEL
            --allowed-models FILE --workdir-root DIR [--brief FILE] [--session-command TEMPLATE] [--timeout S]

Isolation (decision 7 of the sixth maturity attempt: isolated sessions launched by a script, never the largest model,
so that only hashes and counts reach the lead):
- **Model.** MODEL must be listed in FILE, a JSON list the lead writes into the private control directory before the
  first launch (it is frozen with the attempt). The lead lists only models that are not the provider's largest; this
  kit names none.
- **Directory.** Each session runs in a new, empty directory WORKDIR_ROOT/KEY-ROLE-N (mode 700) that must lie
  outside every git checkout (no .git in it or any parent) and outside PRIVATE_ROOT. It receives only its brief (and,
  for a reviewer or fixer, the scenario under review, and for a fixer the reviewer's findings) as plain files.
- **No repository, no web.** The default session commands give the tool no extra directory, no shell, no web
  search or fetch, and write access to its own directory only (session-commands.json beside this file). Check them
  against the installed tool's --help before the first real launch: a flag a tool does not support is a refusal
  there, never a silent widening.
- **Environment.** The session gets PATH, HOME, USER, LOGNAME, LANG, LC_ALL, TERM and TMPDIR only: no provider
  credential (*_API_KEY), no memBrain or attempt variable. The tool uses its own stored subscription login.
- **Outputs.** The session writes, in its directory: an author or fixer `scenario.py` (a fixer also `fixes.json`
  {"applied": N}); a reviewer `review.json` {"approved": bool, "findings": N, "blocking": N} and `findings.md`.
  They are moved to PRIVATE_ROOT/KEY/ (mode 600): `scenario_KEY.py` (author, fixer; the earlier version is kept as
  `scenario_KEY.vN.py`), `findings-N.md`, `review-N.json`, `fixes-N.json`. The session's own output goes to
  PRIVATE_ROOT/logs/, which the lead never opens. A reviewer's approval writes the receipt
  PRIVATE_ROOT/control/KEY-review-approved.json {"key", "sha256", "sessions", "turns", "cases", "approved",
  "findings"} that freeze.py checks.
- **What is printed.** One JSON line: role, key, the output files' sha256, and counts (sessions, turns, cases; a
  reviewer's findings and approval; a fixer's applied count) plus the R4 precheck's result codes. Never a message,
  a criterion, a fact, a name or the session's output.

`--session-command` replaces the tool's command with TEMPLATE ({workdir}, {role}, {brief}, {model} are substituted),
for the offline dry mode the tests use with a fake session. Exit 0 when the session produced its outputs, 1 when it
did not, 2 on a refusal before anything ran.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
EVALUATIONS = KIT.parent
ROLES = ("author", "reviewer", "fixer")
BRIEFS = {"author": "author-brief.md", "reviewer": "reviewer-brief.md", "fixer": "fixer-brief.md"}
KEPT_ENVIRONMENT = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR")
PROMPTS = {
    "author": "Read brief.md and assignment.md in this directory and do what they say. Write scenario.py in this "
              "directory. Do not read, list or search anything outside this directory.",
    "reviewer": "Read brief.md in this directory and review scenario.py as it says. Write review.json and findings.md "
                "in this directory. Do not read, list or search anything outside this directory.",
    "fixer": "Read brief.md in this directory and apply findings.md to scenario.py as it says. Write scenario.py and "
             "fixes.json in this directory. Do not read, list or search anything outside this directory.",
}


class Refused(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside_checkout(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in (path, *path.parents))


def counts(scenario: Path) -> dict:
    """Session, turn and case counts and the R4 precheck's codes, from the scenario file; its output is discarded."""
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            spec = importlib.util.spec_from_file_location("scenario_for_launch", scenario)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
    except BaseException as error:  # noqa: BLE001 - never shown: it may quote the scenario.
        if isinstance(error, KeyboardInterrupt):
            raise
        return {"sessions": 0, "turns": 0, "cases": 0, "loads": False}
    sessions = list(getattr(module, "SESSIONS_LONG", None) or [])
    result = {"sessions": len(sessions), "turns": sum(len(turns) for _, turns in sessions),
              "cases": len(list(getattr(module, "CASES", None) or [])), "loads": True}
    precheck = subprocess.run([sys.executable, str(EVALUATIONS / "c5-precheck.py"), "--r4", str(scenario)],
                              capture_output=True, text=True)
    try:
        summary = json.loads(precheck.stdout.strip().splitlines()[-1])
        result["precheck"] = {"ok": summary.get("ok"), "codes": summary.get("codes")}
    except (ValueError, IndexError):
        result["precheck"] = {"ok": False, "codes": ["precheck_unreadable"]}
    return result


def session_command(args, workdir: Path) -> list[str]:
    if args.session_command:
        template = args.session_command
    else:
        commands = json.loads((KIT / "session-commands.json").read_text())
        template = commands[args.tool]
    values = {"workdir": str(workdir), "role": args.role, "brief": str(workdir / "brief.md"), "model": args.model,
              "prompt": PROMPTS[args.role]}
    return [part.format(**values) for part in shlex.split(template)]


def launch(args) -> dict:
    if args.role not in ROLES:
        raise Refused("unknown role")
    private = Path(args.private).resolve()
    if not private.is_dir():
        raise Refused("the private root does not exist")
    try:
        allowed = json.loads(Path(args.allowed_models).read_text())
    except (OSError, ValueError):
        raise Refused("the allowed-models file is unreadable") from None
    if not isinstance(allowed, list) or args.model not in allowed:
        raise Refused("the model is not in the lead's list of allowed (not largest) models")
    root = Path(args.workdir_root).absolute().resolve()  # Checked before anything is created there.
    if inside_checkout(root):
        raise Refused("the session directory must be outside every checkout")
    if root == private or private in root.parents or root in private.parents:
        raise Refused("the session directory must be outside the private root")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder = private / args.key
    folder.mkdir(mode=0o700, exist_ok=True)
    scenario = folder / f"scenario_{args.key}.py"
    if args.role == "author" and scenario.exists():
        raise Refused("this key already has a scenario: an author writes it once")
    if args.role != "author" and not scenario.exists():
        raise Refused("there is no scenario for this key yet")
    if args.role == "author" and not (args.assignment and Path(args.assignment).is_file()):
        raise Refused("an author needs --assignment (case prefix and languages)")
    if args.role == "fixer" and not sorted(folder.glob("findings-*.md")):
        raise Refused("there are no findings to apply")
    number = 1 + len(list(root.glob(f"{args.key}-{args.role}-*")))
    workdir = root / f"{args.key}-{args.role}-{number}"
    workdir.mkdir(mode=0o700)
    brief = Path(args.brief) if args.brief else KIT / BRIEFS[args.role]
    shutil.copyfile(brief, workdir / "brief.md")
    if args.role == "author":
        shutil.copyfile(args.assignment, workdir / "assignment.md")
    if args.role in ("reviewer", "fixer"):
        shutil.copyfile(scenario, workdir / "scenario.py")
    if args.role == "fixer":
        findings = sorted(folder.glob("findings-*.md"))
        if not findings:
            raise Refused("there are no findings to apply")
        shutil.copyfile(findings[-1], workdir / "findings.md")
    environment = {name: os.environ[name] for name in KEPT_ENVIRONMENT if name in os.environ}
    logs = private / "logs"
    logs.mkdir(mode=0o700, exist_ok=True)
    log = logs / f"{args.key}-{args.role}-{number}.log"
    with log.open("ab") as output:
        try:
            done = subprocess.run(session_command(args, workdir), cwd=workdir, env=environment,
                                  stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                  timeout=args.timeout)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
        except OSError:
            code = "not_started"
    log.chmod(0o600)
    result = {"role": args.role, "key": args.key, "session": number, "session_exit": code}

    def keep(source: Path, target: Path) -> str:
        shutil.copyfile(source, target)
        target.chmod(0o600)
        return sha256(target)

    if args.role in ("author", "fixer"):
        written = workdir / "scenario.py"
        if not written.is_file():
            result["produced"] = False
            return result
        if args.role == "fixer":
            version = 1 + len(list(folder.glob(f"scenario_{args.key}.v*.py")))
            shutil.move(scenario, folder / f"scenario_{args.key}.v{version}.py")
            fixes = workdir / "fixes.json"
            try:
                result["applied"] = int(json.loads(fixes.read_text()).get("applied"))
            except (OSError, ValueError, TypeError, AttributeError):
                result["applied"] = None
            if fixes.exists():
                keep(fixes, folder / f"fixes-{number}.json")
        result["sha256"] = keep(written, scenario)
        result.update(counts(scenario))
        result["produced"] = True
    else:
        verdict, findings = workdir / "review.json", workdir / "findings.md"
        try:
            review = json.loads(verdict.read_text())
            approved, found, blocking = review["approved"], int(review["findings"]), int(review["blocking"])
            if type(approved) is not bool:
                raise TypeError
        except (OSError, ValueError, KeyError, TypeError):
            result["produced"] = False
            return result
        result.update(approved=approved, findings=found, blocking=blocking, produced=True,
                      reviewed_sha256=sha256(scenario))
        result["review_sha256"] = keep(verdict, folder / f"review-{number}.json")
        if findings.exists():
            result["findings_sha256"] = keep(findings, folder / f"findings-{number}.md")
        if approved and blocking == 0:
            control = private / "control"
            control.mkdir(mode=0o700, exist_ok=True)
            receipt = control / f"{args.key}-review-approved.json"
            stats = counts(scenario)
            receipt.write_text(json.dumps({"key": args.key, "sha256": result["reviewed_sha256"],
                                           "sessions": stats["sessions"], "turns": stats["turns"],
                                           "cases": stats["cases"], "approved": True, "findings": found,
                                           "review_session": number}, sort_keys=True))
            receipt.chmod(0o600)
            result["receipt_sha256"] = sha256(receipt)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--role", required=True, choices=ROLES)
    parser.add_argument("--key", required=True)
    parser.add_argument("--private", required=True)
    parser.add_argument("--tool", required=True, choices=("codex", "claude"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--allowed-models", required=True)
    parser.add_argument("--workdir-root", required=True)
    parser.add_argument("--brief")
    parser.add_argument("--assignment", help="author only: a file with the case prefix and the two languages")
    parser.add_argument("--session-command", help="offline dry mode: a fake session command template")
    parser.add_argument("--timeout", type=float, default=3600)
    args = parser.parse_args(argv)
    if not args.key.replace("-", "").replace("_", "").isalnum():
        print(json.dumps({"refused": "the key must be letters, digits, - or _"}))
        return 2
    try:
        result = launch(args)
    except Refused as error:
        print(json.dumps({"refused": str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("produced") else 1


if __name__ == "__main__":
    sys.exit(main())
