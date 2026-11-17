#!/usr/bin/env python3
"""Start ONE isolated scenario author, reviewer, fixer or (C5) verifier session and print only hashes and counts.

  launch.py --role author|reviewer|fixer|verifier --key KEY --private PRIVATE_ROOT --tool claude|codex --model MODEL
            --allowed-models FILE --workdir-root DIR [--gate R4|C5] [--assignment FILE] [--brief FILE]
            [--python PATH] [--accept-risk RISK] [--session-command TEMPLATE] [--timeout S]

--gate (default R4) chooses the scenario kind. R4: the briefs author-brief.md, reviewer-brief.md and fixer-brief.md
and `c5-precheck.py --r4`, exactly as before the option existed (no verifier role). C5: c5-author-brief.md,
c5-reviewer-brief.md, c5-fixer-brief.md, c5-verifier-brief.md and `c5-precheck.py --c5`; an approval receipt also
records "gate": "C5", which `freeze.py --gate C5` requires (and `freeze.py` for R4 refuses), and the role and round
that approved.

C5 review converges by rounds (since 2026-11-17, after the public authoring diagnostic):
- **The assignment** names the scenario's coverage items on one strict line (assignment.py: `- Coverage items: a,
  b`). The author's assignment is kept as PRIVATE_ROOT/KEY/assignment.md; every later session of the key gets that
  copy and the C5 author brief (`author-brief.md`, with its criteria templates), and every precheck of the key runs
  `--c5 --require` with its items. A later --assignment must be byte-identical to the stored copy.
- **Round 1 is the one full review** (`--role reviewer`): refused when the key already has a review. A restart is a
  new key with a new author, whose own version line gets its own one review.
- **Every later round is a verification** (`--role verifier`): refused without a full review, on a version already
  reviewed or verified (a fixer comes first), and after MAX_VERIFICATIONS rounds. A verifier gets the current
  scenario, the author brief and assignment, every earlier round's findings (`findings-R.md`), every fix record
  (`fixes-N.json`) and `rounds.md` (the steps in order, names and counts only). It writes review.json and
  findings.md like a reviewer; its approval writes the same receipt.
- A reviewer or verifier is refused on a version that fails the precheck (a fixer applies its precheck findings
  first). A fixer applies the latest round's findings only when they are for the current version, and is refused
  on an approved version.
- The launcher's record of the steps (author, rounds, fixes; hashes, counts, file names) is PRIVATE_ROOT/KEY/
  rounds.json. A C5 round's files are named by round (`review-R.json`, `findings-R.md`; round 1 is the review); an
  R4 review's by its session, as before.

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
ROLES = ("author", "reviewer", "fixer", "verifier")
GATES = ("R4", "C5")
BRIEFS = {"author": "author-brief.md", "reviewer": "reviewer-brief.md", "fixer": "fixer-brief.md"}
C5_BRIEFS = {"author": "c5-author-brief.md", "reviewer": "c5-reviewer-brief.md", "fixer": "c5-fixer-brief.md",
             "verifier": "c5-verifier-brief.md"}
PRECHECK_MODE = {"R4": "--r4", "C5": "--c5"}
MAX_VERIFICATIONS = 3  # C5: one full review, then at most three verification rounds.
LEDGER = "rounds.json"  # C5: the launcher's own record of a key's review, verification and fix steps.
KEPT_ENVIRONMENT = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR")
PROMPTS = {
    "author": "Read brief.md and assignment.md in this directory and do what they say. Write scenario.py in this "
              "directory. Do not read, list or search anything outside this directory.",
    "reviewer": "Read brief.md in this directory and review scenario.py as it says. Write review.json and findings.md "
                "in this directory. Do not read, list or search anything outside this directory.",
    "fixer": "Read brief.md in this directory and apply findings.md to scenario.py as it says. Write scenario.py and "
             "fixes.json in this directory. Do not read, list or search anything outside this directory.",
    "verifier": "Read brief.md in this directory and verify scenario.py as it says. Write review.json and findings.md "
                "in this directory. Do not read, list or search anything outside this directory.",
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


def counts(scenario: Path, python: Path, gate: str = "R4", required=None) -> dict:
    """Session, turn and case counts (the file read without running it) and the gate's precheck codes. For C5,
    ``required`` is the assignment's coverage items, passed to the precheck as --require."""
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
        extra = ["--require", ",".join(required)] if gate == "C5" and required else []
        done = subprocess.run([str(python), str(EVALUATIONS / "c5-precheck.py"), PRECHECK_MODE[gate], *extra,
                               str(scenario)], capture_output=True, text=True, timeout=300)
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


def read_ledger(folder: Path) -> dict:
    """C5: the key's steps in order, as the launcher recorded them (names, hashes and counts only)."""
    try:
        ledger = json.loads((folder / LEDGER).read_text())
    except (OSError, ValueError):
        return {"steps": []}
    return ledger if isinstance(ledger, dict) and isinstance(ledger.get("steps"), list) else {"steps": []}


def write_ledger(folder: Path, ledger: dict) -> None:
    path = folder / LEDGER
    path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    path.chmod(0o600)


def rounds(ledger: dict) -> list[dict]:
    """The review and verification rounds (round 1 is the full review)."""
    return [step for step in ledger["steps"] if step.get("kind") in ("review", "verification")]


def rounds_table(ledger: dict) -> str:
    """rounds.md for a verifier: which file came from which step, in order. Names and counts only."""
    lines = ["# The steps so far, in order (written by the launcher)", "",
             "| Step | What | File | Result |", "| --- | --- | --- | --- |"]
    for number, step in enumerate(ledger["steps"], 1):
        kind = step.get("kind")
        if kind == "author":
            lines.append(f"| {number} | the author wrote the scenario | | |")
        elif kind in ("review", "verification"):
            what = "full review (round 1)" if kind == "review" else f"verification (round {step['round']})"
            verdict = "approved" if step.get("approved") else f"not approved, {step.get('blocking')} blocking"
            lines.append(f"| {number} | {what} | {step.get('findings') or ''} | {verdict} |")
        elif kind == "fix":
            source = {"precheck": "the automatic check's findings"}.get(
                step.get("findings_from"), f"the findings of round {step.get('applied_round')}")
            lines.append(f"| {number} | a fixer applied {source} | {step.get('record') or ''} | "
                         f"applied {step.get('applied')} |")
    return "\n".join(lines) + "\n"


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
    if args.role == "verifier" and gate != "C5":
        raise Refused("the verifier role is for the C5 gate only")
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
    folder = private / args.key
    scenario = folder / f"scenario_{args.key}.py"
    if args.role == "author" and scenario.exists():
        raise Refused("this key already has a scenario: an author writes it once")
    if args.role != "author" and not scenario.exists():
        raise Refused("there is no scenario for this key yet")
    if args.role == "author" and not (args.assignment and Path(args.assignment).is_file()):
        raise Refused("an author needs --assignment (case prefix and languages)")
    # C5: the assignment names the coverage items this scenario covers (assignment.py). The author's copy is kept as
    # PRIVATE_ROOT/KEY/assignment.md, and every later session of the key is given that copy and prechecks with it.
    required, stored = None, folder / "assignment.md"
    if gate == "C5":
        parser = _module("c5_assignment_for_launch", KIT / "assignment.py")
        source = Path(args.assignment) if args.role == "author" else stored
        if args.role != "author" and not stored.is_file():
            raise Refused("this key has no stored assignment: it was not written with this kit")
        if args.role != "author" and args.assignment and (not Path(args.assignment).is_file()
                                                          or Path(args.assignment).read_bytes() != stored.read_bytes()):
            raise Refused("the assignment differs from the one this key's author was given")
        try:
            required = parser.read(source)
        except parser.AssignmentError as error:
            raise Refused(str(error)) from None
    ledger = read_ledger(folder) if gate == "C5" else {"steps": []}
    current = sha256(scenario) if scenario.exists() else None
    failing = gate == "C5" and current is not None and precheck_findings_path(folder, current).exists()
    done_rounds = rounds(ledger)
    applied_round, findings_source = None, None
    if gate == "C5" and args.role == "reviewer":
        # One full review per scenario version line; every later round is a verification. A restart is a new key
        # with a new author (and its own one review).
        if done_rounds or sorted(folder.glob("review-*.json")):
            raise Refused("this key already has its full review: later rounds are verifications (--role verifier); "
                          "a restart is a new key with a new author")
        if failing:
            raise Refused("the current version fails the precheck: a fixer applies its precheck findings first")
    if args.role == "verifier":
        if not any(step["kind"] == "review" for step in done_rounds):
            raise Refused("a verification needs the full review first (--role reviewer)")
        if failing:
            raise Refused("the current version fails the precheck: a fixer applies its precheck findings first")
        if done_rounds[-1].get("reviewed_sha256") == current:
            raise Refused("the current version was already reviewed or verified: a fixer comes first")
        if sum(step["kind"] == "verification" for step in done_rounds) >= MAX_VERIFICATIONS:
            raise Refused(f"this key has had its {MAX_VERIFICATIONS} verification rounds")
    # C5: a version that failed the precheck has its own findings (written below, after its session); a fixer then
    # applies those, without a reviewer round. Otherwise a fixer applies the latest round's findings, which must be
    # for the current version.
    precheck_findings = precheck_findings_path(folder, current) if failing and args.role == "fixer" else None
    if args.role == "fixer" and precheck_findings is None:
        if gate == "C5" and done_rounds:
            latest = done_rounds[-1]
            if latest.get("approved"):
                raise Refused("the current version is approved: there is nothing to fix")
            if latest.get("reviewed_sha256") != current:
                raise Refused("the latest findings are for an earlier version: verify this one first "
                              "(--role verifier)")
            if not latest.get("findings") or not (folder / latest["findings"]).is_file():
                raise Refused("there are no findings to apply")
            findings_source, applied_round = folder / latest["findings"], latest["round"]
        else:
            candidates = sorted(folder.glob("findings-*.md")) if folder.is_dir() else []
            if not candidates:
                raise Refused("there are no findings to apply")
            findings_source = candidates[-1]
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.mkdir(mode=0o700, exist_ok=True)
    if gate == "C5" and args.role == "author":
        shutil.copyfile(args.assignment, stored)
        stored.chmod(0o600)
    number = 1 + len(list(root.glob(f"{args.key}-{args.role}-*")))
    workdir = root / f"{args.key}-{args.role}-{number}"
    workdir.mkdir(mode=0o700)
    brief = Path(args.brief) if args.brief else KIT / (C5_BRIEFS if gate == "C5" else BRIEFS)[args.role]
    shutil.copyfile(brief, workdir / "brief.md")
    if args.role == "author":
        shutil.copyfile(args.assignment, workdir / "assignment.md")
    if args.role in ("reviewer", "fixer", "verifier"):
        shutil.copyfile(scenario, workdir / "scenario.py")
    if gate == "C5" and args.role != "author":
        # Every later session sees what the author was given: the author brief (with its criteria templates) and the
        # assignment (with its coverage items).
        shutil.copyfile(KIT / C5_BRIEFS["author"], workdir / "author-brief.md")
        shutil.copyfile(stored, workdir / "assignment.md")
    if args.role == "fixer":
        shutil.copyfile(precheck_findings or findings_source, workdir / "findings.md")
    if args.role == "verifier":
        # Every earlier round's findings under its own name, every fix record, and the order they came in.
        for step in ledger["steps"]:
            for name in (step.get("findings"), step.get("record")):
                if name and (folder / name).is_file():
                    shutil.copyfile(folder / name, workdir / name)
        (workdir / "rounds.md").write_text(rounds_table(ledger))
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
        kind = next((step["kind"] for step in done_rounds if step["round"] == applied_round), "review")
        result["findings_from"] = "precheck" if precheck_findings is not None else \
            {"review": "reviewer", "verification": "verifier"}[kind]

    def keep(source: Path, target: Path) -> str:
        shutil.copyfile(source, target)
        target.chmod(0o600)
        return sha256(target)

    if args.role in ("author", "fixer"):
        written = workdir / "scenario.py"
        if not written.is_file():
            result["produced"] = False
            return result
        record = None
        if args.role == "fixer":
            version = 1 + len(list(folder.glob(f"scenario_{args.key}.v*.py")))
            shutil.move(scenario, folder / f"scenario_{args.key}.v{version}.py")
            fixes = workdir / "fixes.json"
            try:
                result["applied"] = int(json.loads(fixes.read_text()).get("applied"))
            except (OSError, ValueError, TypeError, AttributeError):
                result["applied"] = None
            if fixes.exists():
                record = f"fixes-{number}.json"
                keep(fixes, folder / record)
        result["sha256"] = keep(written, scenario)
        checked = counts(scenario, python, gate, required)
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
        if gate == "C5":
            step = {"kind": args.role.replace("fixer", "fix"), "session": number, "after_sha256": result["sha256"]}
            if args.role == "fixer":
                step.update(before_sha256=current, findings_from=result["findings_from"], applied_round=applied_round,
                            applied=result["applied"], record=record)
            ledger["steps"].append(step)
            write_ledger(folder, ledger)
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
        # R4 names a review's files by its session; C5 by its round (1 is the full review, then verifications).
        round_number = len(done_rounds) + 1 if gate == "C5" else number
        result["review_sha256"] = keep(verdict, folder / f"review-{round_number}.json")
        if findings.exists():
            result["findings_sha256"] = keep(findings, folder / f"findings-{round_number}.md")
        if gate == "C5":
            result["round"] = round_number
            ledger["steps"].append({
                "kind": "review" if args.role == "reviewer" else "verification", "round": round_number,
                "session": number, "reviewed_sha256": result["reviewed_sha256"], "approved": approved,
                "findings_count": found, "blocking": blocking, "verdict": f"review-{round_number}.json",
                "findings": f"findings-{round_number}.md" if findings.exists() else None})
            write_ledger(folder, ledger)
        if approved and blocking == 0:
            control = private / "control"
            control.mkdir(mode=0o700, exist_ok=True)
            receipt = control / f"{args.key}-review-approved.json"
            stats = counts(scenario, python, gate, required)
            stats.pop("failure_lines", None)
            approval = {"key": args.key, "sha256": result["reviewed_sha256"], "sessions": stats["sessions"],
                        "turns": stats["turns"], "cases": stats["cases"], "approved": True, "findings": found,
                        "review_session": number}
            if gate == "C5":  # An R4 receipt keeps its earlier fields exactly.
                approval.update(gate="C5", role=args.role, round=round_number)
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
    parser.add_argument("--assignment", help="author: a file with the case prefix and the two languages (C5: and the "
                                             "'Coverage items:' line); later C5 roles use the author's stored copy")
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
