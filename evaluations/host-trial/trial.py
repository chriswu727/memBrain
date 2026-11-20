#!/usr/bin/env python3
"""A real-host trial in one command: prepare a frozen trial, play a scenario through headless Claude Code, report.

  trial.py lint SCENARIO                          the wording lint and the format check
  trial.py hash SCENARIO                          the SHA-256 an approval names
  trial.py prepare SCENARIO --commit C --root DIR [--continue-from EARLIER_TRIAL] [--model-from INSTALLATION]
                   [--repository REPO] [--offline]
  trial.py run TRIAL --approval FILE [--ledger FILE] [--keep-service] [--turn-timeout SECONDS]
  trial.py report TRIAL
  trial.py service start|stop|status TRIAL

**prepare** makes one new directory under DIR (outside every checkout) holding everything the trial uses: the
runtime at commit C (``runtime/``: the commit's package files and an environment with the package installed from
them, not editable, locked by the commit's ``uv.lock``); ``plugin/``, the commit's Claude Code plugin with its
launchers pointed at that runtime (the difference in ``plugin-diff.txt``); ``bin/membrain`` (on the session's PATH,
as ``uv tool install`` puts it in an installation); ``brain/``, a new memory with ports of its own and the local
embedding model copied from INSTALLATION, or, when the scenario continues an earlier one, a clone of that trial's
stopped memory (the earlier trial is only read); ``work/``, the synthetic project; and the memory's service, started.

**run** refuses to start unless the approval file is a JSON object with ``approved_by``, ``date`` (ISO, not in the
future), ``model`` (only ``sonnet`` or ``haiku`` are ever accepted), ``max_turns`` (at least the scenario's turns,
at most MAX_TURNS) and ``scenario_sha256`` (the trial's scenario), optionally ``commit``, ``scenario`` and ``notes``.
It refuses a trial that already ran, an approval already used and a scenario that already ran on the same commit
(the ledger beside the trials; a stub rehearsal is marked and never counts). Each turn is one ``claude -p`` process
with exactly the arguments and the clean environment of the hand-made trial of 2026-11-18; a turn is never retried.
After each turn the memory is read through the service and the turn's checks run; with ``stop_on_failure`` the
first failed check stops the trial and leaves everything as it is (service included). A host turn that fails
(non-zero exit, no result event, an error result, a timeout) always stops it. Cost per turn is the host's own.

The host runs under the owner's own login: an isolated host configuration has no login. Nothing here reads, copies
or prints a credential file; the session gets HOME so that the host finds its own login.
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import trial_report as report  # noqa: E402
import trial_scenario as scenarios  # noqa: E402

REPOSITORY = HERE.parents[1]
ALLOWED_MODELS = frozenset({"sonnet", "haiku"})
MAX_TURNS = 20
APPROVAL_REQUIRED = {"approved_by", "date", "model", "max_turns", "scenario_sha256"}
APPROVAL_OPTIONAL = {"commit", "scenario", "notes"}
ALLOWED_TOOLS = ("mcp__plugin_membrain_membrain", "Read", "Glob", "Grep", "Edit", "Write",
                 "Bash(membrain plugin ui:*)")
RUNTIME_PATHS = ("pyproject.toml", "uv.lock", "README.md", "LICENSE", ".python-version", "src", "plugins",
                 "migrations", "architecture/memory-contract.schema.json")
UV_SYNC = ("sync", "--frozen", "--no-dev", "--extra", "embedded", "--extra", "semantic", "--no-editable")
STUB_MARKER = b"membrain-host-trial-stub"
DEFAULT_MODEL_CACHE = Path.home() / ".cache" / "membrain" / "eval-embedding-model"
LEDGER = "host-trial-ledger.jsonl"
TURN_TIMEOUT = 900


class Refused(Exception):
    pass


def _json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def inside_checkout(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in (path, *path.parents))


# The trial's own processes -----------------------------------------------------------------------------------------

def session_environment(trial: Path, **extra) -> dict:
    """The clean environment of the hand-made trial's turn.sh: the trial's bin first on PATH, the login's HOME."""
    environment = {"PATH": f"{trial / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}", "HOME": str(Path.home()),
                   "USER": os.environ.get("USER", ""), "LOGNAME": os.environ.get("LOGNAME", ""),
                   "LANG": os.environ.get("LANG") or "C.UTF-8", "TERM": os.environ.get("TERM") or "xterm",
                   "MEMBRAIN_DIRECTORY": str(trial / "brain")}
    environment.update(extra)
    return environment


def runtime_python(trial: Path) -> Path:
    return trial / "runtime" / ".venv" / "bin" / "python"


def memory_ops(trial: Path, *arguments, timeout: float = 600) -> dict:
    """Run the trial's copy of memory_ops.py with the frozen runtime's interpreter and a clean environment."""
    done = subprocess.run([str(runtime_python(trial)), "-I", str(trial / "tools" / "memory_ops.py"),
                           *map(str, arguments)], env=session_environment(trial), capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise Refused(f"memory_ops {arguments[0]} failed: {(done.stderr or done.stdout).strip()[-1500:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def runtime_digest(trial: Path) -> str:
    """A digest of the installed package's files, so that a run notices a runtime changed after preparation."""
    packages = sorted((trial / "runtime" / ".venv" / "lib").glob("python*/site-packages/membrain"))
    digest = hashlib.sha256()
    for package in packages:
        for path in sorted(package.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                digest.update(str(path.relative_to(package)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


# Prepare -----------------------------------------------------------------------------------------------------------

def _git(repository: Path, *arguments) -> str:
    done = subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused(f"git {arguments[0]}: {done.stderr.strip()}")
    return done.stdout.strip()


def _launcher(old: str, python: str) -> str:
    """The frozen runtime's form of one Claude Code hook command, as rewrite_plugin.py made it on 2026-11-18. The
    session-start launcher keeps its own "not ready" notice for when the runtime does not answer."""
    if "membrain plugin start" in old:
        return f"{python} -m membrain.cli plugin start >/dev/null 2>&1; true"
    for event in ("session-start", "user-prompt", "stop"):
        if f"membrain plugin hook {event}" in old:
            fallback = re.search(r"\|\| (printf '%s\\n' '[^']*')", old) if event == "session-start" else None
            tail = f" || {fallback.group(1)}" if fallback else ""
            return f"{python} -m membrain.cli plugin hook {event} 2>/dev/null{tail}; true"
    raise Refused(f"a plugin launcher of an unknown shape: {old[:120]}")


def rewrite_plugin(plugin: Path, python: Path) -> list[str]:
    quoted = shlex.quote(str(python))
    mcp = plugin / ".claude-mcp.json"
    data = _json(mcp)
    data["mcpServers"]["membrain"] = {"command": str(python), "args": ["-m", "membrain.cli", "plugin", "mcp"]}
    _write_json(mcp, data)
    hooks = plugin / "hooks" / "claude-hooks.json"
    data = _json(hooks)
    seen = []
    for event, groups in data["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                hook["command"] = _launcher(hook["command"], quoted)
                seen.append(f"{event}: {hook['command'].split('membrain.cli ', 1)[1].split(' 2>', 1)[0].split(' >', 1)[0]}")
    _write_json(hooks, data)
    return seen


def plugin_diff(original: Path, copy: Path, trial: Path) -> str:
    out = []
    for relative in (".claude-mcp.json", "hooks/claude-hooks.json"):
        before = (original / relative).read_text().replace(str(trial), "(trial)").splitlines(keepends=True)
        after = (copy / relative).read_text().replace(str(trial), "(trial)").splitlines(keepends=True)
        out += difflib.unified_diff(before, after, f"(trial)/runtime/plugins/membrain/{relative}",
                                    f"(trial)/plugin/{relative}")
    return "".join(out)


def prepare(scenario_path: Path, *, commit: str, root: Path, repository: Path = REPOSITORY,
            model_from: Path = DEFAULT_MODEL_CACHE, continue_from: Path | None = None, offline: bool = False) -> Path:
    scenario_path = Path(scenario_path).resolve()
    scenario = scenarios.load(scenario_path)
    problems = scenarios.lint(scenario)
    if problems:
        raise Refused("the scenario's messages do not pass the lint: " + "; ".join(problems))
    root = Path(root).resolve()
    if inside_checkout(root):
        raise Refused("the trials root must be outside every checkout")
    continues = scenario["memory"].get("continues")
    if continues and continue_from is None:
        raise Refused(f"the scenario continues {continues!r}: give --continue-from that trial's directory")
    if not continues and continue_from is not None:
        raise Refused("the scenario starts a new memory: --continue-from does not apply")
    if continue_from is not None:
        continue_from = Path(continue_from).resolve()
        earlier = scenarios.load(continue_from / "scenario.json") if (continue_from / "scenario.json").exists() else None
        if earlier is None or earlier["name"] != continues:
            raise Refused(f"{continue_from} is not a trial of scenario {continues!r}")
        if not (continue_from / "run.json").exists():
            raise Refused("the earlier trial never ran")
    full = _git(repository, "rev-parse", "--verify", f"{commit}^{{commit}}")
    uv = shutil.which("uv")
    if uv is None:
        raise Refused("uv is needed to build the runtime environment")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    trial = root / f"{scenario['name']}-{stamp}"
    trial.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(scenario_path, trial / "scenario.json")
    # The runtime: the commit's package files, and an environment with the package installed from them.
    archive = trial / "runtime.tar"
    _git(repository, "archive", "--format=tar", "-o", str(archive), full, "--", *RUNTIME_PATHS)
    with tarfile.open(archive) as stream:
        stream.extractall(trial / "runtime", filter="data")
    archive.unlink()
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "USER", "LANG", "UV_CACHE_DIR") if key in os.environ}
    done = subprocess.run([uv, *UV_SYNC, *(["--offline"] if offline else [])], cwd=trial / "runtime",
                          env=environment, capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused(f"uv sync failed: {done.stderr.strip()[-1500:]}")
    located = subprocess.run([str(runtime_python(trial)), "-I", "-c", "import membrain; print(membrain.__file__)"],
                             capture_output=True, text=True, env=environment)
    if located.returncode != 0 or not Path(located.stdout.strip()).is_relative_to(trial / "runtime" / ".venv"):
        raise Refused("the runtime environment does not hold the package")
    # The plugin, its launchers on the frozen runtime.
    shutil.copytree(trial / "runtime" / "plugins" / "membrain", trial / "plugin")
    launchers = rewrite_plugin(trial / "plugin", runtime_python(trial))
    (trial / "plugin-diff.txt").write_text(plugin_diff(trial / "runtime" / "plugins" / "membrain", trial / "plugin",
                                                       trial))
    (trial / "bin").mkdir()
    (trial / "bin" / "membrain").symlink_to(trial / "runtime" / ".venv" / "bin" / "membrain")
    (trial / "tools").mkdir()
    shutil.copyfile(HERE / "memory_ops.py", trial / "tools" / "memory_ops.py")
    # The memory and the project.
    if continue_from is None:
        memory = memory_ops(trial, "create", trial / "brain", "--model-from", Path(model_from).resolve())
    else:
        memory = memory_ops(trial, "clone", continue_from / "brain", trial / "brain")
    work = trial / "work"
    if scenario.get("project") == {"continues": True}:
        shutil.copytree(continue_from / "work", work, symlinks=True)
    else:
        work.mkdir()
        for relative, content in (scenario.get("project") or {"files": {}})["files"].items():
            path = work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    try:
        started = memory_ops(trial, "start", trial / "brain")
    except Refused:
        try:  # Leave no service of a trial that was never prepared.
            memory_ops(trial, "stop", trial / "brain")
        except Refused:
            pass
        raise
    _write_json(trial / "prepared.json", {
        "scenario": scenario["name"], "scenario_sha256": scenarios.sha256(trial / "scenario.json"),
        "commit": full, "prepared_at": _now(), "memory": "cloned" if continue_from else "new",
        "continues_trial": continue_from.name if continue_from else None,
        "continues_commit": _json(continue_from / "prepared.json").get("commit") if continue_from else None,
        "memory_result": memory, "service": started, "launchers": launchers, "runtime_digest": runtime_digest(trial),
        "uv": subprocess.run([uv, "--version"], capture_output=True, text=True).stdout.strip(),
        "offline": offline})
    return trial


# Run ---------------------------------------------------------------------------------------------------------------

def check_approval(path: Path | None, *, sha: str, turns: int, commit: str) -> dict:
    if path is None:
        raise Refused("no approval file: a real-host trial needs the owner's approval")
    try:
        approval = _json(path)
    except (OSError, ValueError):
        raise Refused("the approval file is unreadable") from None
    if not isinstance(approval, dict) or not APPROVAL_REQUIRED <= set(approval) or \
            not set(approval) <= APPROVAL_REQUIRED | APPROVAL_OPTIONAL:
        raise Refused(f"the approval states exactly {sorted(APPROVAL_REQUIRED)} (optionally {sorted(APPROVAL_OPTIONAL)})")
    if not isinstance(approval["approved_by"], str) or not approval["approved_by"].strip():
        raise Refused("the approval names who approved")
    try:
        day = datetime.date.fromisoformat(approval["date"])
    except (TypeError, ValueError):
        raise Refused("the approval's date is an ISO date") from None
    if day > datetime.date.today():
        raise Refused("the approval's date is in the future")
    if approval["model"] not in ALLOWED_MODELS:
        raise Refused(f"the model {approval['model']!r} is refused: only sonnet or haiku are ever accepted")
    limit = approval["max_turns"]
    if type(limit) is not int or not 1 <= limit <= MAX_TURNS:
        raise Refused(f"the approval's max_turns is a whole number from 1 to {MAX_TURNS}")
    if turns > limit:
        raise Refused(f"the scenario has {turns} turns, over the approved limit of {limit}")
    if approval["scenario_sha256"] != sha:
        raise Refused("the approval names another scenario hash: the scenario changed or another was approved")
    if "commit" in approval and not (isinstance(approval["commit"], str) and len(approval["commit"]) >= 7
                                     and commit.startswith(approval["commit"])):
        raise Refused("the approval names another commit")
    return approval


def is_stub(executable: Path) -> bool:
    try:
        with open(executable, "rb") as stream:
            return STUB_MARKER in stream.read(4096)
    except OSError:
        return False


def _ledger(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def _append(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _state_refs(scenario: dict, state: dict) -> dict:
    refs = {}
    for name, spec in (scenario.get("refs") or {}).items():
        found = [note["event_id"] for note in state["notes"]
                 if re.search(spec["note_matching"], note.get("text") or "", re.I)]
        if found:
            refs[name] = found[0] if len(found) == 1 else found
    return refs


def _read_state(trial: Path, label: str, checks: list[dict], refs: dict) -> dict | None:
    erased = sorted({value for check in checks if check["type"] == "erased"
                     for value in scenarios._ids(refs.get(check["ref"]))})
    try:
        state = memory_ops(trial, "state", trial / "brain", *(["--erased", *erased] if erased else []))
    except (Refused, subprocess.TimeoutExpired, ValueError) as error:
        state = None
        (trial / "states" / f"{label}.error.txt").write_text(str(error))
    if state is not None:
        _write_json(trial / "states" / f"{label}.json", state)
    return state


def _evaluate(trial: Path, label: str, checks: list[dict], *, parsed: dict | None, calls: list[dict],
              refs: dict) -> tuple[list[dict], dict | None]:
    results = []
    # Tool checks first: they save the ids later checks (and the erasure read) use.
    for check in [c for c in checks if c["type"] == "tool"]:
        results.append((check, scenarios.evaluate(check, turn=parsed, calls=calls, state=None,
                                                  project=trial / "work", refs=refs)))
    state = _read_state(trial, label, checks, refs)
    for check in [c for c in checks if c["type"] != "tool"]:
        results.append((check, scenarios.evaluate(check, turn=parsed, calls=calls, state=state,
                                                  project=trial / "work", refs=refs)))
    order = {id(check): index for index, check in enumerate(checks)}
    results.sort(key=lambda pair: order[id(pair[0])])
    return [{"turn": label, "label": check.get("label") or _describe(check), **verdict}
            for check, verdict in results], state


def _describe(check: dict) -> str:
    fields = {key: value for key, value in check.items() if key not in ("type", "label", "informational")}
    return check["type"] + " " + json.dumps(fields, ensure_ascii=False)[:160]


def capture_page(trial: Path, note: str) -> dict:
    """The lead's own look at the memory page at a note (not the host's): the note item's text and a screenshot."""
    done = subprocess.run([str(trial / "bin" / "membrain"), "plugin", "ui", "--no-browser", "--note", note,
                           "--directory", str(trial / "brain")], env=session_environment(trial),
                          capture_output=True, text=True, timeout=120)
    url = next((word for word in done.stdout.split() if word.startswith("http://")), None)
    if url is None:
        return {"captured": False, "reason": "the page command printed no link"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"captured": False, "reason": "playwright is not available to the tool's interpreter"}
    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 1500})
            page.goto(url)
            page.wait_for_selector(".addressed, .item-gone", timeout=20000)
            try:  # The note's source messages load after the note itself.
                page.wait_for_function("() => !/Loading original messages/.test(document.querySelector("
                                       "'.addressed, .item-gone').closest('article.item, p').innerText)",
                                       timeout=20000)
            except Exception:
                pass  # Captured as it stands; the text says it was still loading.
            text = page.evaluate("""() => {
              const gone = document.querySelector('.item-gone');
              const hit = document.querySelector('.addressed');
              const item = hit ? (hit.closest('article.item') || hit) : null;
              return item ? item.innerText : (gone ? gone.innerText : null); }""")
            page.screenshot(path=str(trial / "page-at-note.png"))
        finally:
            browser.close()
    return {"captured": True, "text": text}


def run(trial: Path, approval_path: Path | None, *, ledger_path: Path | None = None, keep_service: bool = False,
        turn_timeout: float = TURN_TIMEOUT) -> dict:
    trial = Path(trial).resolve()
    try:
        prepared = _json(trial / "prepared.json")
    except (OSError, ValueError):
        raise Refused("this is not a prepared trial directory") from None
    if (trial / "run.json").exists():
        raise Refused("this trial has already run: a trial is never rerun (prepare a new one)")
    scenario = scenarios.load(trial / "scenario.json")
    sha = scenarios.sha256(trial / "scenario.json")
    if sha != prepared["scenario_sha256"]:
        raise Refused("the trial's scenario changed after it was prepared")
    problems = scenarios.lint(scenario)
    if problems:
        raise Refused("the scenario's messages do not pass the lint: " + "; ".join(problems))
    plan = scenarios.turns(scenario)
    approval = check_approval(approval_path, sha=sha, turns=len(plan), commit=prepared["commit"])
    approval_sha = scenarios.sha256(approval_path)
    environment = session_environment(trial)
    claude = shutil.which("claude", path=environment["PATH"])
    if claude is None:
        raise Refused("no claude on the PATH")
    rehearsal = is_stub(Path(claude))
    ledger = Path(ledger_path) if ledger_path else trial.parent / LEDGER
    for entry in _ledger(ledger):
        if entry.get("rehearsal"):
            continue
        if entry.get("approval_sha256") == approval_sha:
            raise Refused("this approval was already used: one approval is one run")
        if entry.get("scenario_sha256") == sha and entry.get("commit") == prepared["commit"]:
            raise Refused(f"this scenario already ran on this commit ({entry.get('status')}): it is never rerun")
    if runtime_digest(trial) != prepared["runtime_digest"]:
        raise Refused("the trial's runtime changed after it was prepared")
    record = {"status": "started", "started_at": _now(), "rehearsal": rehearsal, "model": approval["model"],
              "approved_by": approval["approved_by"], "approval_date": approval["date"],
              "max_turns": approval["max_turns"], "scenario_sha256": sha, "approval_sha256": approval_sha,
              "commit": prepared["commit"], "host_login": "the owner's own (an isolated host configuration has no "
              "login); no credential file was read, copied or printed", "allowed_tools": list(ALLOWED_TOOLS)}
    _write_json(trial / "run.json", record)
    _append(ledger, {"trial": trial.name, "status": "started", "at": record["started_at"], "rehearsal": rehearsal,
                     "scenario": scenario["name"], "scenario_sha256": sha, "approval_sha256": approval_sha,
                     "commit": prepared["commit"]})
    (trial / "logs").mkdir(exist_ok=True)
    (trial / "states").mkdir(exist_ok=True)
    if not memory_ops(trial, "status", trial / "brain").get("ready"):
        memory_ops(trial, "start", trial / "brain")
    before = _read_state(trial, "before", [], {})
    refs = _state_refs(scenario, before) if before else {}
    sessions = {name: str(uuid.uuid4()) for name in dict.fromkeys(turn["session"] for turn in plan)}
    _write_json(trial / "sessions.json", sessions)
    results, turns, totals, every_call = [], [], {}, []
    status, reason, state = "completed", None, before
    for number, turn in enumerate(plan, start=1):
        if len(list((trial / "logs").glob("*.jsonl"))) >= approval["max_turns"]:
            status, reason = "stopped", f"the turn limit of {approval['max_turns']} was reached"
            break
        name = f"t{number:02d}-{turn['name']}"
        log = trial / "logs" / f"{name}.jsonl"
        if log.exists():
            raise Refused(f"{log.name} exists: a turn is never retried")
        (trial / "logs" / f"{name}.prompt.txt").write_text(turn["message"], encoding="utf-8")
        session = sessions[turn["session"]]
        argv = [claude, "-p", turn["message"], "--model", approval["model"], "--plugin-dir", str(trial / "plugin"),
                "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
                "--allowedTools", *ALLOWED_TOOLS, "--session-id" if turn["new_session"] else "--resume", session]
        with log.open("wb") as output, (trial / "logs" / f"{name}.err").open("wb") as errors:
            try:
                exit_code = subprocess.run(argv, cwd=trial / "work", env={**environment, "TRIAL_TURN": name},
                                           stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                           timeout=turn_timeout).returncode
            except subprocess.TimeoutExpired:
                exit_code = "timeout"
        parsed = report.parse_log(log, totals.get(session))
        if parsed["result"] and isinstance(parsed["result"].get("total_cost_usd"), (int, float)):
            totals[session] = parsed["result"]["total_cost_usd"]
        for call in parsed["calls"]:
            every_call.append({**call, "turn": name})
        checks = turn.get("checks", [])
        verdicts, state = _evaluate(trial, name, checks, parsed=parsed, calls=parsed["calls"], refs=refs)
        results += verdicts
        failed = [item for item in verdicts if item["verdict"] == "FAIL"]
        turns.append({"name": name, "session": turn["session"], "message": turn["message"], "exit": exit_code,
                      "cost_usd": parsed["cost"], "failed_checks": len(failed),
                      "host_error": bool(exit_code != 0 or parsed["result"] is None or parsed["result"]["is_error"])})
        _write_json(trial / "results.json", {"turns": turns, "checks": results, "refs": refs})
        if turns[-1]["host_error"]:
            status, reason = "stopped", f"the host turn {name} failed (exit {exit_code}); it is not retried"
            break
        if failed and scenario.get("stop_on_failure"):
            status, reason = "stopped", f"a check failed in {name} and the scenario stops on failure"
            break
    if status == "completed":
        final, state = _evaluate(trial, "final", scenario.get("final_checks", []), parsed=None, calls=every_call,
                                 refs=refs)
        results += final
        capture = scenario.get("page_capture")
        if capture:
            ids = scenarios._ids(refs.get(capture["note"]))
            try:
                page = capture_page(trial, ids[0]) if ids else {"captured": False, "reason": "the note was not found"}
            except Exception as error:  # The lead's look must not lose the run's results.
                page = {"captured": False, "reason": f"{type(error).__name__}: {error}"}
            _write_json(trial / "page-at-note.json", page)
    _write_json(trial / "results.json", {"turns": turns, "checks": results, "refs": refs})
    service = "left running"
    if status == "completed" and not keep_service:
        try:
            memory_ops(trial, "stop", trial / "brain")
            service = "stopped"
        except Refused as error:
            service = f"stop failed: {error}"
    costs = [turn["cost_usd"] for turn in turns if isinstance(turn["cost_usd"], (int, float))]
    record.update(status=status, reason=reason, finished_at=_now(), turns_used=len(turns),
                  total_cost_usd=round(sum(costs), 6) if costs else None, service=service,
                  failed_checks=sum(item["verdict"] == "FAIL" for item in results))
    _write_json(trial / "run.json", record)
    _append(ledger, {"trial": trial.name, "status": status, "at": record["finished_at"], "rehearsal": rehearsal,
                     "scenario": scenario["name"], "scenario_sha256": sha, "approval_sha256": approval_sha,
                     "commit": prepared["commit"], "failed_checks": record["failed_checks"]})
    write_report(trial)
    return record


# Report ------------------------------------------------------------------------------------------------------------

def _how_it_was_run(prepared: dict, run_record: dict, init: dict) -> list[str]:
    memory = ("a new, empty memory with ports of its own and the local embedding model copied from an existing "
              "cache, its service started beforehand as on a machine where memBrain is already installed"
              if prepared["memory"] == "new" else
              f"a clone of the stopped memory of the earlier trial `{prepared['continues_trial']}` (runtime "
              f"`{(prepared.get('continues_commit') or '')[:8]}`), with ports and a deletion registry of its own; "
              "the earlier trial was only read. An installation never clones a memory: the clone keeps the "
              "earlier memory's installation, brain and owner identities")
    return [
        f"- A frozen copy of runtime `{prepared['commit'][:8]}`: the commit's package files, with the package "
        "installed from them (not editable, the commit's `uv.lock`, extras `embedded` and `semantic`, no development "
        "tools). An installation installs the same package with `uv tool install` from the pinned archive.",
        "- A copy of the plugin whose hooks and tool server run that copy directly ([difference](plugin-diff.txt)), "
        "loaded with `--plugin-dir`; the launchers' uv and uvx steps are not exercised.",
        f"- {memory[0].upper() + memory[1:]}; a synthetic project directory.",
        "- **The host ran under the owner's own login**, because an isolated host configuration has no login. "
        "Nothing of the owner's configuration or memory was read or written by memBrain or by this tool, and no "
        "credential file was read, copied or printed. The trial's session records are in the host's own project "
        "history for the trial's project directory.",
        "- Headless: `claude -p`, sessions resumed with `--resume`; every resumed turn runs the session-start hook "
        "again, which an interactive session does not.",
        "- Allowed without asking: " + ", ".join(f"`{tool}`" for tool in run_record["allowed_tools"]) +
        ". A `membrain` command was put on the path, as `uv tool install` does in an installation.",
        f"- Host version {init.get('version')}; model `{run_record['model']}` as approved "
        f"(the host reported `{init.get('model')}`).",
    ]


def write_report(trial: Path) -> Path:
    trial = Path(trial).resolve()
    extra = (str(trial),)
    scenario = _json(trial / "scenario.json")
    prepared = _json(trial / "prepared.json")
    run_record = _json(trial / "run.json")
    results = _json(trial / "results.json") if (trial / "results.json").exists() else {"turns": [], "checks": []}
    out = trial / "report"
    (out / "summaries").mkdir(parents=True, exist_ok=True)
    plan = {f"t{n:02d}-{turn['name']}": turn for n, turn in enumerate(scenarios.turns(scenario), start=1)}
    sessions = _json(trial / "sessions.json") if (trial / "sessions.json").exists() else {}
    totals, parsed_turns, init = {}, {}, {}
    for turn in results["turns"]:
        session = sessions.get(turn["session"])
        parsed = report.parse_log(trial / "logs" / f"{turn['name']}.jsonl", totals.get(session))
        if parsed["result"] and isinstance(parsed["result"].get("total_cost_usd"), (int, float)):
            totals[session] = parsed["result"]["total_cost_usd"]
        parsed_turns[turn["name"]] = parsed
        init = init or parsed["init"] or {}
        (out / "summaries" / f"{turn['name']}.txt").write_text(
            report.summary(turn["name"], plan[turn["name"]]["message"], parsed, extra))
    (out / "checks.md").write_text(report.checks_table(results["checks"], extra))
    states = sorted((trial / "states").glob("*.json"), key=lambda path: path.stat().st_mtime)
    last_state = _json(states[-1]) if states else None
    (out / "memory-after.md").write_text(report.state_summary(last_state, extra))
    page = _json(trial / "page-at-note.json") if (trial / "page-at-note.json").exists() else None
    if page:
        (out / "page-at-note.txt").write_text(report.redact(json.dumps(page, indent=2, ensure_ascii=False), extra))
    shutil.copyfile(trial / "plugin-diff.txt", out / "plugin-diff.txt")
    (out / "messages.txt").write_text("".join(f"{name}: {turn['message']}\n" for name, turn in plan.items()))
    (out / "record-draft.md").write_text(_record(scenario, prepared, run_record, results, parsed_turns, init,
                                                 last_state, page, extra))
    return out


def _record(scenario, prepared, run_record, results, parsed_turns, init, state, page, extra) -> str:
    used = run_record.get("turns_used", len(results["turns"]))
    lines = []
    if run_record.get("rehearsal"):
        lines += ["**A stub rehearsal: no real host or model ran. Nothing below is evidence about a host.**", ""]
    lines += [f"# A real host on the {scenario['name']} scenario: {used} turns on Claude Code", "",
              f"Approved by {run_record['approved_by']} on {run_record['approval_date']}: `{run_record['model']}`, "
              f"at most {run_record['max_turns']} turns, scenario `{run_record['scenario_sha256'][:12]}`. "
              f"Claude Code {init.get('version')}, headless, against a frozen copy of runtime "
              f"`{prepared['commit'][:8]}`. {used} of {len(scenarios.turns(scenario))} turns were used"
              + (f"; the trial stopped: {run_record['reason']}" if run_record.get("status") == "stopped" else "")
              + ". It closes no release gate.", ""]
    if scenario.get("description"):
        lines += [scenario["description"], ""]
    if scenario.get("questions"):
        lines += ["The questions:", ""] + [f"- {question}" for question in scenario["questions"]] + [""]
    lines += ["## Checks", "", report.checks_table(results["checks"], extra), "## What happened, turn by turn", "",
              "_Draft from the logs: the lead rewrites this from the [summaries](summaries/)._", ""]
    for number, turn in enumerate(results["turns"], start=1):
        parsed = parsed_turns.get(turn["name"]) or {"calls": [], "reply": None}
        tools = [call["name"].rsplit("__", 1)[-1] + (f" `{call['input'].get('command')}`" if call["name"] == "Bash"
                                                     and isinstance(call.get("input"), dict) else "")
                 for call in parsed["calls"]]
        reply = " ".join((parsed["reply"] or "").split())
        lines.append(f"{number}. **\"{turn['message']}\"** Tools: {', '.join(tools) or 'none'}. Reply: "
                     f"\"{reply[:500]}{'...' if len(reply) > 500 else ''}\"")
    lines += ["", "## The memory afterwards", "", report.state_summary(state, extra)]
    if page:
        lines += ["The lead's own look at the page at the note (not the host's): " +
                  (f"\"{' '.join((page.get('text') or '').split())}\"" if page.get("captured") else
                   f"not captured ({page.get('reason')})"), ""]
    costs = [turn["cost_usd"] for turn in results["turns"] if isinstance(turn.get("cost_usd"), (int, float))]
    by_session = {}
    for turn in results["turns"]:
        if isinstance(turn.get("cost_usd"), (int, float)):
            by_session[turn["session"]] = by_session.get(turn["session"], 0) + turn["cost_usd"]
    lines += ["## Cost on the host", "",
              f"By the host's own accounting: {sum(costs):.2f} USD for {len(results['turns'])} turns ("
              + ", ".join(f"{name} {value:.2f}" for name, value in by_session.items()) + ").", "",
              "## How it was run, and how it differs from an installation", ""]
    lines += _how_it_was_run(prepared, run_record, init)
    lines += ["", "## Limits", "",
              f"One run, one model, {used} turns, one wording of each message; headless, where every resumed turn "
              "runs the session-start hook again; real time, so every day of the scenario fell on the day it was "
              "run; the project and its files were written for the trial."
              + (" The trial stopped early, so later turns and the final checks did not run."
                 if run_record.get("status") == "stopped" else ""), ""]
    return report.redact("\n".join(lines), extra)


# CLI ---------------------------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("lint", "hash"):
        commands.add_parser(name).add_argument("scenario", type=Path)
    prep = commands.add_parser("prepare")
    prep.add_argument("scenario", type=Path)
    prep.add_argument("--commit", required=True)
    prep.add_argument("--root", required=True, type=Path)
    prep.add_argument("--continue-from", type=Path)
    prep.add_argument("--model-from", type=Path, default=DEFAULT_MODEL_CACHE)
    prep.add_argument("--repository", type=Path, default=REPOSITORY)
    prep.add_argument("--offline", action="store_true", help="build the runtime environment from uv's cache only")
    play = commands.add_parser("run")
    play.add_argument("trial", type=Path)
    play.add_argument("--approval", type=Path)
    play.add_argument("--ledger", type=Path)
    play.add_argument("--keep-service", action="store_true")
    play.add_argument("--turn-timeout", type=float, default=TURN_TIMEOUT)
    commands.add_parser("report").add_argument("trial", type=Path)
    service = commands.add_parser("service")
    service.add_argument("action", choices=("start", "stop", "status"))
    service.add_argument("trial", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "lint":
            scenario = scenarios.load(args.scenario)
            problems = scenarios.lint(scenario)
            print(json.dumps({"turns": len(scenarios.turns(scenario)), "lint": problems}, indent=2))
            return 1 if problems else 0
        if args.command == "hash":
            scenarios.load(args.scenario)
            print(scenarios.sha256(args.scenario))
            return 0
        if args.command == "prepare":
            trial = prepare(args.scenario, commit=args.commit, root=args.root, repository=args.repository,
                            model_from=args.model_from, continue_from=args.continue_from, offline=args.offline)
            print(json.dumps({"trial": str(trial), "scenario_sha256": scenarios.sha256(trial / "scenario.json"),
                              "turns": len(scenarios.turns(_json(trial / "scenario.json")))}, indent=2))
            return 0
        if args.command == "run":
            record = run(args.trial, args.approval, ledger_path=args.ledger, keep_service=args.keep_service,
                         turn_timeout=args.turn_timeout)
            print(json.dumps({key: record.get(key) for key in ("status", "reason", "turns_used", "total_cost_usd",
                                                                "failed_checks", "service", "rehearsal")}, indent=2))
            return 0 if record["status"] == "completed" and not record["failed_checks"] else 1
        if args.command == "report":
            print(write_report(args.trial))
            return 0
        if args.command == "service":
            trial = Path(args.trial).resolve()
            print(json.dumps(memory_ops(trial, args.action, trial / "brain")))
            return 0
    except (Refused, scenarios.ScenarioError) as error:
        print(json.dumps({"refused": str(error)}))
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
