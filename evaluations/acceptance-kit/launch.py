#!/usr/bin/env python3
"""Start ONE isolated scenario author, reviewer or fixer session and print only hashes and counts.

  launch.py --role author|reviewer|fixer --key KEY --private PRIVATE_ROOT --tool claude|codex --model MODEL
            --allowed-models FILE --workdir-root DIR [--gate R4|C5] [--assignment FILE] [--brief FILE]
            [--python PATH] [--accept-risk RISK] [--session-command TEMPLATE] [--timeout S]

--gate (default R4) chooses the scenario kind. R4: the briefs author-brief.md, reviewer-brief.md and fixer-brief.md
and `c5-precheck.py --r4`, exactly as before the option existed. C5: c5-author-brief.md, c5-reviewer-brief.md and
c5-fixer-brief.md and `c5-precheck.py --c5`; a C5 reviewer's approval receipt also records "gate": "C5", which
`freeze.py --gate C5` requires (and `freeze.py` for R4 refuses).

Isolation (decision 7 of the sixth maturity attempt: isolated sessions launched by a script, never the largest model,
so that only hashes and counts reach the lead):
- **Model.** MODEL must be listed in FILE, a JSON list the lead writes into the private control directory before the
  first launch (freeze.py requires and freezes it). The lead lists only models that are not the provider's largest;
  this kit names none.
- **Directory.** Each session runs in a new, empty directory WORKDIR_ROOT/KEY-ROLE-N (mode 700) that must lie
  outside every git checkout (no .git in it or any parent) and outside PRIVATE_ROOT; this is checked before anything
  is created. It receives only its brief (an author also its assignment; a reviewer or fixer the scenario under
  review; a fixer the reviewer's findings) as plain files.
- **The tool** (session-commands.json, an argument list per tool). The Claude Code command runs with `--safe-mode`
  (no CLAUDE.md, skills, installed plugins, hooks, MCP servers or custom agents, subscription login kept),
  `--restricted` (no code-running tool, no WebFetch, no user/project/local settings files, and the file tools
  confined to the working directory), `--strict-mcp-config` (no MCP server), `--no-session-persistence` (no
  transcript on disk), `--tools Read,Write,Edit` and web search disallowed. The Codex command is marked
  non-isolating (its sandbox limits writes and network, not reads, and it always has a shell) and is refused unless
  `--accept-risk reads-outside-the-session-directory` names that risk.
- **Environment.** The session gets PATH, HOME, USER, LOGNAME, LANG, LC_ALL, TERM and TMPDIR, plus MEMBRAIN_DIRECTORY
  set to an empty, read-only throwaway directory: no provider credential (*_API_KEY), no other memBrain or attempt
  variable. The plugin's hook commands resolve their installation from MEMBRAIN_DIRECTORY (host.profile_directory),
  so even if a memBrain plugin loaded despite --safe-mode its hooks would find no installation, could not create one,
  and could neither show the owner's memory nor record the session. The tool uses its own stored login.
- **Outputs.** The session writes, in its directory: an author or fixer `scenario.py` (a fixer also `fixes.json`
  {"applied": N}); a reviewer `review.json` {"approved": bool, "findings": N, "blocking": N} and `findings.md`.
  They are moved to PRIVATE_ROOT/KEY/ (mode 600): `scenario_KEY.py` (author, fixer; the earlier version is kept as
  `scenario_KEY.vN.py`), `findings-N.md`, `review-N.json`, `fixes-N.json`. The session's own output goes to
  PRIVATE_ROOT/logs/, which the lead never opens. A reviewer's approval writes the receipt
  PRIVATE_ROOT/control/KEY-review-approved.json {"key", "sha256", "sessions", "turns", "cases", "approved",
  "findings"} that freeze.py checks.
- **Nothing a session wrote runs here.** The scenario is read with scenario_literals.py (literal assignments only;
  anything else is the code `not_literal`), and `c5-precheck.py --r4` (or `--c5` for the C5 gate) runs in a
  subprocess with the repository's interpreter (REPO/.venv/bin/python unless --python). Only the precheck's own codes
  are relayed.
- **A version that fails the precheck (C5 only, since 2026-11-17).** After an author or fixer session whose
  scenario fails `c5-precheck.py --c5`, the JSON says so with the codes (as before) and the launcher writes
  PRIVATE_ROOT/KEY/precheck-findings-<sha256 of that version>.md (mode 600): a fixed header, then the precheck's own
  failure lines (a known code, then fixed field names, indexes and positions; any other line is dropped), and
  reports `precheck_findings` (the count) and its sha256. A fixer started next for that key, while the current
  version is the failing one, gets that file as its findings.md (`findings_from` "precheck") instead of the latest
  reviewer findings; no reviewer round is needed in between. Otherwise a fixer gets the latest reviewer findings
  (`findings_from` "reviewer"), as before. R4 launches are unchanged.
- **What is printed.** One JSON line: role, key, the output files' sha256, counts (sessions, turns, cases; a
  reviewer's findings and approval; a fixer's applied count) and fixed codes. Never a message, a criterion, a fact,
  a name, an exception's text or the session's output.

`--session-command` replaces the tool's argument list with TEMPLATE, split with shlex before {workdir}, {role},
{brief}, {model} and {prompt} are substituted into whole arguments; it is the offline dry mode the tests use with a
fake session. Exit 0 when the session produced its outputs, 1 when it did not, 2 on a refusal before anything ran.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
EVALUATIONS = KIT.parent
REPOSITORY = EVALUATIONS.parent
ROLES = ("author", "reviewer", "fixer")
GATES = ("R4", "C5")
BRIEFS = {"author": "author-brief.md", "reviewer": "reviewer-brief.md", "fixer": "fixer-brief.md"}
C5_BRIEFS = {"author": "c5-author-brief.md", "reviewer": "c5-reviewer-brief.md", "fixer": "c5-fixer-brief.md"}
PRECHECK_MODE = {"R4": "--r4", "C5": "--c5"}
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


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside_checkout(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in (path, *path.parents))


def counts(scenario: Path, python: Path, gate: str = "R4") -> dict:
    """Session, turn and case counts (the file read without running it) and the gate's precheck codes."""
    literals = _module("scenario_literals_for_launch", EVALUATIONS / "scenario_literals.py")
    try:
        module = literals.read(scenario)
        sessions = list(getattr(module, "SESSIONS_LONG", None) or [])
        result = {"sessions": len(sessions), "turns": sum(len(turns) for _, turns in sessions),
                  "cases": len(list(getattr(module, "CASES", None) or [])), "loads": True}
    except (literals.NotLiteral, TypeError, ValueError):
        return {"sessions": 0, "turns": 0, "cases": 0, "loads": False,
                "precheck": {"ok": False, "codes": ["not_literal"]}}
    known = set(_module("c5_precheck_codes_for_launch", EVALUATIONS / "c5-precheck.py").CODES)
    try:
        done = subprocess.run([str(python), str(EVALUATIONS / "c5-precheck.py"), PRECHECK_MODE[gate], str(scenario)],
                              capture_output=True, text=True, timeout=300)
        summary = json.loads(done.stdout.strip().splitlines()[-1])
        codes = summary.get("codes") if isinstance(summary.get("codes"), list) else ["precheck_unreadable"]
        result["precheck"] = {"ok": summary.get("ok") is True and done.returncode == 0,
                              "codes": sorted({code if code in known else "unknown_code" for code in codes})}
        result["failure_lines"] = [line for line in done.stdout.splitlines() if _failure_line(line, known)]
    except (OSError, ValueError, IndexError, AttributeError, subprocess.TimeoutExpired):
        result["precheck"] = {"ok": False, "codes": ["precheck_unreadable"]}
    return result


# A precheck failure line as c5-precheck.py prints it: a known code, then fixed field names with indexes, fixed
# requirement and part names or "index:index" positions. Anything else is never relayed to a fixer.
_FAILURE_LINE = re.compile(r"FAIL code=([a-z0-9_]+)((?: [a-z]+=[A-Za-z0-9_]+(?::[0-9]+)?)*)")


def _failure_line(line: str, known: set) -> bool:
    match = _FAILURE_LINE.fullmatch(line)
    return bool(match) and match[1] in known


PRECHECK_FINDINGS_HEADER = """# Findings of the automatic check (not of a reviewer)

The automatic check refused this version of `scenario.py`. Each line below is one failure, as the check prints it:
a fixed code (see the table of codes in your brief), then where it is: `session=N` and `turn=N` count from 0 in
`SESSIONS_LONG` order, `case=N` and `action=N` and `entry=N` are 0-based positions in `CASES`, `PAGE_ACTIONS` and
`EXPECT_RECORDING_P`, `at=S:T` is a session index and turn index, `field=` and `part=` name a `COVERAGE` requirement
and its key (or a missing name). Nothing else about the scenario is given here. Resolve every line with the smallest
change that removes it and keeps every rule of your brief.

"""


def precheck_findings_path(folder: Path, sha: str) -> Path:
    """The precheck findings written for the scenario version with this sha256 (C5 only)."""
    return folder / f"precheck-findings-{sha}.md"


def session_command(args, workdir: Path) -> list[str]:
    """The session's argument list: the template's arguments with the values substituted into whole arguments (a
    value is never split or re-quoted). Refuses a non-isolating tool unless --accept-risk names its risk."""
    if args.session_command:
        template = shlex.split(args.session_command)
    else:
        command = json.loads((KIT / "session-commands.json").read_text())[args.tool]
        if not command.get("isolating") and args.accept_risk != command.get("risk"):
            raise Refused(f"the {args.tool} command does not isolate the session ({command.get('risk')}): pass "
                          f"--accept-risk {command.get('risk')} to use it anyway")
        template = list(command["argv"])
    values = {"workdir": str(workdir), "role": args.role, "brief": str(workdir / "brief.md"), "model": args.model,
              "prompt": PROMPTS[args.role]}
    return [part.format(**values) for part in template]


def launch(args) -> dict:
    if args.role not in ROLES:
        raise Refused("unknown role")
    gate = getattr(args, "gate", "R4")
    if gate not in GATES:
        raise Refused("the gate is R4 or C5")
    private = Path(args.private).resolve()
    if not private.is_dir():
        raise Refused("the private root does not exist")
    try:
        allowed = json.loads(Path(args.allowed_models).read_text())
    except (OSError, ValueError):
        raise Refused("the allowed-models file is unreadable") from None
    if not isinstance(allowed, list) or args.model not in allowed:
        raise Refused("the model is not in the lead's list of allowed (not largest) models")
    session_command(args, Path("/nonexistent"))  # A non-isolating tool is refused before anything is created.

    def argv(workdir: Path) -> list[str]:
        return session_command(args, workdir)

    python = Path(args.python) if args.python else REPOSITORY / ".venv" / "bin" / "python"
    if not python.is_file():
        raise Refused("the repository's interpreter is missing (give --python)")
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
    # C5: a version that failed the precheck has its own findings (written below, after its session); a fixer then
    # applies those, without a reviewer round. Otherwise a fixer applies the latest reviewer findings, as before.
    precheck_findings = precheck_findings_path(folder, sha256(scenario)) \
        if gate == "C5" and args.role == "fixer" and scenario.exists() else None
    if precheck_findings is not None and not precheck_findings.exists():
        precheck_findings = None
    if args.role == "fixer" and precheck_findings is None and not sorted(folder.glob("findings-*.md")):
        raise Refused("there are no findings to apply")
    number = 1 + len(list(root.glob(f"{args.key}-{args.role}-*")))
    workdir = root / f"{args.key}-{args.role}-{number}"
    workdir.mkdir(mode=0o700)
    brief = Path(args.brief) if args.brief else KIT / (C5_BRIEFS if gate == "C5" else BRIEFS)[args.role]
    shutil.copyfile(brief, workdir / "brief.md")
    if args.role == "author":
        shutil.copyfile(args.assignment, workdir / "assignment.md")
    if args.role in ("reviewer", "fixer"):
        shutil.copyfile(scenario, workdir / "scenario.py")
    if args.role == "fixer":
        findings = [precheck_findings] if precheck_findings is not None else sorted(folder.glob("findings-*.md"))
        if not findings:
            raise Refused("there are no findings to apply")
        shutil.copyfile(findings[-1], workdir / "findings.md")
    # A second barrier behind --safe-mode: a memBrain plugin, if one loaded, would look for its installation here,
    # find none and be unable to create one.
    nomemory = root / f"nomemory-{args.key}-{args.role}-{number}"
    nomemory.mkdir(mode=0o500)
    environment = {name: os.environ[name] for name in KEPT_ENVIRONMENT if name in os.environ}
    environment["MEMBRAIN_DIRECTORY"] = str(nomemory)
    logs = private / "logs"
    logs.mkdir(mode=0o700, exist_ok=True)
    log = logs / f"{args.key}-{args.role}-{number}.log"
    with log.open("ab") as output:
        try:
            done = subprocess.run(argv(workdir), cwd=workdir, env=environment,
                                  stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                  timeout=args.timeout)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
        except OSError:
            code = "not_started"
    log.chmod(0o600)
    result = {"role": args.role, "key": args.key, "session": number, "session_exit": code}
    if args.role == "fixer" and gate == "C5":
        result["findings_from"] = "precheck" if precheck_findings is not None else "reviewer"

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
        checked = counts(scenario, python, gate)
        lines = checked.pop("failure_lines", [])
        result.update(checked)
        if gate == "C5" and not checked["precheck"]["ok"]:
            # The precheck findings for this version: codes and positions only, as the precheck prints them, for a
            # fixer session started next (launch.py --role fixer), without a reviewer round.
            # A file that could not be read (not literal) has no positions: its code alone.
            lines = lines or [f"FAIL code={code}" for code in checked["precheck"]["codes"]]
            target = precheck_findings_path(folder, result["sha256"])
            target.write_text(PRECHECK_FINDINGS_HEADER + "".join(f"- `{line}`\n" for line in lines))
            target.chmod(0o600)
            result.update(precheck_findings=len(lines), precheck_findings_sha256=sha256(target))
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
            stats = counts(scenario, python, gate)
            stats.pop("failure_lines", None)
            approval = {"key": args.key, "sha256": result["reviewed_sha256"], "sessions": stats["sessions"],
                        "turns": stats["turns"], "cases": stats["cases"], "approved": True, "findings": found,
                        "review_session": number}
            if gate == "C5":  # An R4 receipt keeps its earlier fields exactly.
                approval["gate"] = "C5"
            receipt.write_text(json.dumps(approval, sort_keys=True))
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
    parser.add_argument("--gate", default="R4", choices=GATES,
                        help="R4 (default) or C5: the briefs and the precheck mode of that gate")
    parser.add_argument("--brief")
    parser.add_argument("--assignment", help="author only: a file with the case prefix and the two languages")
    parser.add_argument("--session-command", help="offline dry mode: a fake session command template")
    parser.add_argument("--accept-risk", help="use a non-isolating tool command anyway, naming its risk exactly")
    parser.add_argument("--python", help="the repository's interpreter for the precheck (default REPO/.venv/bin/python)")
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
