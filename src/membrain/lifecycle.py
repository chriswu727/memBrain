"""What an installation put on this computer, and how to stop it and take it off again.

``membrain plugin stop`` stops the service; ``plugin status`` lists what is on the computer (``footprint``);
``plugin uninstall`` stops everything and removes what memBrain owns: with ``--keep-data`` the program and caches
only, otherwise also the memory, after offering an export. Removal asks for a typed confirmation unless ``--yes``
and never runs inside an agent session (``agent_session``): an agent may tell the user the command, not run it.
memBrain never edits a host's configuration; it prints the host's own command for taking the plugin out.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .helpers import DomainError

TOOL = "membrain-ai"
# Each host's name, its command for turning the plugin off (None: none known to memBrain) and for removing it.
AGENTS = {
    "claude-code": ("Claude Code", "claude plugin disable membrain@membrain",
                    "claude plugin uninstall membrain@membrain"),
    "codex": ("Codex", None, "remove the memBrain plugin in Codex (it was added with codex plugin add "
                             "membrain@membrain)"),
    "workbuddy": ("WorkBuddy or CodeBuddy", None, "remove memBrain from the plugins (Skills, then Plugins)"),
    "openclaw": ("OpenClaw", None, "remove the membrain plugin from OpenClaw's plugins"),
}
# Set by Claude Code, Codex and CodeBuddy in the hooks and shells they run. Removal never runs under any of them.
AGENT_VARIABLES = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "PLUGIN_ROOT",
                   "PLUGIN_DATA", "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEBUDDY_PLUGIN_ROOT")
# Where a hook says the host keeps the plugin and the plugin's own data (``record_host``).
PLUGIN_ROOTS = ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "CODEBUDDY_PLUGIN_ROOT")
PLUGIN_DATA = ("CLAUDE_PLUGIN_DATA", "PLUGIN_DATA")
HOSTS_FILE = "hosts.json"
# What memBrain writes at the top of a data directory. A directory chosen with MEMBRAIN_DIRECTORY or --directory
# loses only these; anything else in it is left and named.
OWN_ENTRIES = {
    ".profile.lock", ".native-maintenance", "profile.json", "recovery.json", "recovery-maintenance.json", "restore.json",
    "chat.json", "plugin", "postgres", "postgres.log", "postgres-cluster", "models", "mcp.json", "compose.yaml",
    "compose.env", "native-engines", "native-transition.json", "native-source.json", "lifecycle", "supervisor",
    "Cache", "service.log",
}
# Work directories of an engine transition, earlier journals, temporary profile files and rotated logs.
OWN_PREFIXES = ("transition-", ".profile-", "service.log.")
# What stopping or exporting can raise: the service's own errors (DesktopError, a RuntimeError; RegistryError, a
# DomainError), an unreadable profile (ValueError) and local files or processes.
FAILURES = (RuntimeError, ValueError, OSError, DomainError)
ROLES = {"service": "the memory service", "database": "its database", "tool server": "a tool server of an open "
         "agent session", "installer": "uv installing memBrain", "command": "a memBrain command"}


# Hosts ---------------------------------------------------------------------------------------------------------

def record_host(directory: Path, host_name: str) -> None:
    """Keep where this host has the plugin, as its hook sees it, so ``status`` and ``uninstall`` can say so.

    Only directories the host names in the hook's environment; written only when they change."""
    from .host import state_directory

    entry = {"plugin": next((value for name in PLUGIN_ROOTS if (value := os.environ.get(name))
                             and Path(value).is_dir()), None),
             "plugin_data": next((value for name in PLUGIN_DATA if (value := os.environ.get(name))
                                  and Path(value).is_dir()), None)}
    hosts = recorded_hosts(directory)
    if hosts.get(host_name) == entry:
        return
    hosts[host_name] = entry
    path = state_directory(directory) / HOSTS_FILE
    temporary = path.with_name(f".{HOSTS_FILE}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(hosts, stream)
    os.replace(temporary, path)


def recorded_hosts(directory: Path) -> dict:
    try:
        hosts = json.loads((Path(directory) / "plugin" / HOSTS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {name: value for name, value in hosts.items() if name in AGENTS and isinstance(value, dict)} \
        if isinstance(hosts, dict) else {}


def agent_session() -> str | None:
    """The variable that shows this command runs inside an agent's session (its shell or a hook), if any."""
    return next((name for name in AGENT_VARIABLES if os.environ.get(name)), None)


# Paths and sizes -----------------------------------------------------------------------------------------------

def _uv() -> str | None:
    return os.environ.get("UV") or shutil.which("uv")


def _uv_output(*arguments: str) -> str | None:
    uv = _uv()
    if uv is None:
        return None
    try:
        result = subprocess.run([uv, *arguments], capture_output=True, text=True, timeout=20, check=False,
                                stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def size(path: Path, *, skip: Path | None = None) -> int:
    """Bytes of the regular files under ``path``, without following links (and without ``skip``)."""
    total = 0
    stack = [Path(path)]
    while stack:
        current = stack.pop()
        if skip is not None and current == skip:
            continue
        try:
            metadata = current.lstat()
        except OSError:
            continue
        if current.is_dir() and not current.is_symlink():
            try:
                stack.extend(current.iterdir())
            except OSError:
                pass
        elif not current.is_symlink():
            total += metadata.st_size
    return total


def human(count: int) -> str:
    for unit, scale in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if count >= scale:
            value = count / scale
            return f"{value:.1f} {unit}" if value < 10 else f"{value:.0f} {unit}"
    return f"{count} bytes"


def show(path) -> str:
    """A path as the user can type it: under ``~`` when it is in the home directory."""
    text = str(path)
    try:
        home = str(Path.home())
    except (RuntimeError, KeyError):
        return text
    return "~" + text[len(home):] if home and (text == home or text.startswith(home + os.sep)) else text


def _recovery_record(directory: Path) -> Path | None:
    """The record of what was erased, kept beside the data directory so a restored backup cannot bring it back."""
    try:
        binding = json.loads((directory / "recovery.json").read_text(encoding="utf-8"))
        path = Path(binding["registry_path"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    # Only where memBrain puts it: next to this installation, named after it.
    if path.parent.name != ".agent-memory-recovery" or path.parent.parent != directory.parent:
        return None
    return path


def _tool_paths() -> tuple[Path | None, Path | None]:
    from .host import _uv_tool_directory

    tools = _uv_tool_directory()
    root = tools / TOOL if tools is not None else None
    found = _uv_output("tool", "dir", "--bin")
    binary = Path(found) if found else (Path(os.environ["UV_TOOL_BIN_DIR"]) if os.environ.get("UV_TOOL_BIN_DIR")
                                        else Path.home() / ".local" / "bin")
    program = binary / ("membrain.exe" if os.name == "nt" else "membrain")
    return root, program


def _onnxruntime_cache() -> Path | None:
    roots = {Path.home() / ".cache"}
    if os.environ.get("XDG_CACHE_HOME"):
        roots.add(Path(os.environ["XDG_CACHE_HOME"]))
    return next((path for root in sorted(roots) if (path := root / "Microsoft" / "DeveloperTools" / ".onnxruntime")
                 .exists()), None)


def _uv_pythons() -> list[str]:
    found = _uv_output("python", "dir")
    if not found:
        return []
    try:
        return sorted(str(path) for path in Path(found).glob("cpython-3.12*") if path.is_dir())
    except OSError:
        return []


# Processes -----------------------------------------------------------------------------------------------------

def _postmaster(directory: Path) -> int | None:
    data = directory / "postgres"
    try:
        recorded = json.loads((directory / "native-transition.json").read_text(encoding="utf-8")).get("data")
        if isinstance(recorded, str):
            data = Path(recorded)
    except (OSError, ValueError, AttributeError):
        pass
    try:
        pid = int((data / "postmaster.pid").read_text(encoding="utf-8").split("\n", 1)[0])
    except (OSError, ValueError):
        return None
    return pid if _alive(pid) else None


def _alive(pid: int) -> bool:
    if os.name == "nt":
        return True  # Not checked: the database's own lock file says it runs.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _role(argv: list[str]) -> str | None:
    """What a process of memBrain's is doing, from its command line; None for anything else."""
    names = [Path(argument).name for argument in argv]
    if names and names[0] in ("uv", "uvx", "uv.exe", "uvx.exe"):
        return "installer" if "install" in argv and any(TOOL in argument for argument in argv) else None
    if "membrain.cli" in argv:
        rest = argv[argv.index("membrain.cli") + 1:]
    elif any(name in ("membrain", "membrain.exe") for name in names[:2]):
        index = next(position for position, name in enumerate(names) if name in ("membrain", "membrain.exe"))
        rest = argv[index + 1:]
    else:
        return None
    if rest[:2] == ["desktop", "_run"]:
        return "service"
    if "mcp" in rest[:2]:
        return "tool server"
    if rest[:2] == ["plugin", "hook"]:
        return None  # A hook ends within seconds.
    return "command"


def _same_directory(argv: list[str], environment: dict | None, directory: Path) -> bool:
    if "--directory" in argv[:-1]:
        return os.path.abspath(argv[argv.index("--directory") + 1]) == os.path.abspath(directory)
    if environment is None:
        return True  # macOS does not show other processes' environments: counted, so nothing running is missed.
    configured = environment.get("MEMBRAIN_DIRECTORY") or environment.get("AGENT_MEMORY_DIRECTORY")
    if configured:
        return os.path.abspath(configured) == os.path.abspath(directory)
    data = environment.get("XDG_DATA_HOME") or (os.path.join(environment["HOME"], ".local", "share")
                                                 if environment.get("HOME") else None)
    if data is None:
        return True
    return os.path.abspath(directory) in (os.path.join(os.path.abspath(data), "membrain"),
                                          os.path.join(os.path.abspath(data), "agent-memory"))


def _process_table() -> list[tuple[int, int, list[str], dict | None]] | None:
    """(pid, parent, argv, environment or None) of this user's processes; None where not listed (Windows)."""
    table = []
    if sys.platform.startswith("linux"):
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid != os.getuid():
                    continue
                argv = [part.decode("utf-8", "replace")
                        for part in (entry / "cmdline").read_bytes().split(b"\0") if part]
                parent = int((entry / "stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                continue
            try:
                environment = dict(item.decode("utf-8", "replace").split("=", 1)
                                   for item in (entry / "environ").read_bytes().split(b"\0") if b"=" in item)
            except OSError:
                continue  # Only processes that are not dumpable (systemd --user): never memBrain's.
            table.append((int(entry.name), parent, argv, environment))
        return table
    if sys.platform == "darwin":
        try:
            result = subprocess.run(["ps", "-axww", "-o", "pid=,ppid=,uid=,command="], capture_output=True,
                                    text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        for line in result.stdout.splitlines():
            fields = line.split(None, 3)
            if len(fields) == 4 and fields[2] == str(os.getuid()):
                table.append((int(fields[0]), int(fields[1]), fields[3].split(), None))
        return table
    return None


def processes(directory: Path) -> list[dict] | None:
    """memBrain's processes for this installation, besides this one: ``{"pid", "role"}``. None where processes are
    not listed (Windows), so the caller says it could not check."""
    directory = Path(directory)
    table = _process_table()
    if table is None:
        return None
    parents = {pid: parent for pid, parent, _, _ in table}
    mine, current = set(), os.getpid()
    while current and current not in mine:  # This command and whatever started it.
        mine.add(current)
        current = parents.get(current, 0)
    found = {}
    for pid, parent, argv, environment in table:
        role = _role(argv)
        if role and pid not in mine and _same_directory(argv, environment, directory):
            found[pid] = (parent, role)
    # A process started by another of the same role (uv running memBrain, a tool server handing over) is one.
    listed = [{"pid": pid, "role": role} for pid, (parent, role) in sorted(found.items())
              if found.get(parent, (None, None))[1] != role]
    database = _postmaster(directory)
    if database is not None and database not in found:
        listed.append({"pid": database, "role": "database"})
    return listed


# What is on this computer --------------------------------------------------------------------------------------

def footprint(directory: Path) -> dict:
    """Every place an installation has files, with sizes, and what runs: for ``status`` and ``uninstall``."""
    from .native_bundle import _cache_directory

    directory = Path(directory)
    engine = _cache_directory()
    tool, program = _tool_paths()
    record = _recovery_record(directory)

    def place(path):
        if path is None:
            return None
        exists = path.exists()
        return {"path": str(path), "exists": exists,
                "bytes": size(path, skip=engine if engine != path and engine.is_relative_to(path) else None)
                if exists else 0}

    hosts = recorded_hosts(directory)
    try:
        engine_name = json.loads((directory / "profile.json").read_text(encoding="utf-8")).get(
            "database_engine", "docker")  # A Docker profile does not name its engine.
    except (OSError, ValueError, AttributeError):
        engine_name = None
    return {
        "memory": place(directory),
        "database_engine": engine_name,
        "erasure_record": place(record),
        "program": {**place(tool), "command": str(program)} if tool is not None else None,
        "engine_cache": place(engine),
        "uv_cache": _uv_output("cache", "dir"),
        "uv_python": _uv_pythons(),
        "onnxruntime_cache": str(found) if (found := _onnxruntime_cache()) else None,
        "processes": processes(directory),
        "agents": [{"host": name, **entry} for name, entry in sorted(hosts.items())],
    }


def _agent_lines(found: dict, *, disable: bool) -> list[str]:
    names = [agent["host"] for agent in found["agents"]] or list(AGENTS)
    lines = []
    for name in names:
        label, off, remove = AGENTS[name]
        lines.append(f"    {label}: {off if disable and off else remove}")
    return lines


def _running(found: dict) -> str:
    listed = found["processes"]
    if listed is None:
        return "Running processes are not listed on this system."
    if not listed:
        return "No memBrain process is running."
    return "Running: " + "; ".join(f"{ROLES[item['role']]} (process {item['pid']})" for item in listed) + "."


def describe(found: dict) -> list[str]:
    """What is on this computer, in plain lines (``plugin status`` in a terminal)."""
    lines = ["memBrain on this computer:"]
    memory = found["memory"]
    lines.append(f"  Your memory (messages, notes, database, local model, logs): {show(memory['path'])}"
                 + (f", {human(memory['bytes'])}" if memory["exists"] else " (none yet)"))
    if found["erasure_record"] and found["erasure_record"]["exists"]:
        lines.append(f"  Its record of what you erased: {show(found['erasure_record']['path'])}")
    program = found["program"]
    if program and program["exists"]:
        lines.append(f"  The memBrain program, installed by uv: {show(program['path'])}, {human(program['bytes'])}"
                     f" (command {show(program['command'])})")
    if found["engine_cache"]["exists"]:
        lines.append(f"  The database engine cache: {show(found['engine_cache']['path'])}, "
                     f"{human(found['engine_cache']['bytes'])}")
    for agent in found["agents"]:
        label = AGENTS[agent["host"]][0]
        if agent.get("plugin"):
            lines.append(f"  {label}'s copy of the plugin: {show(agent['plugin'])}")
        if agent.get("plugin_data"):
            lines.append(f"  {label}'s folder for the plugin: {show(agent['plugin_data'])}")
    lines.append(f"  {_running(found)}")
    lines.append("Stop for now: membrain plugin stop. Remove: membrain plugin uninstall (asks first; --keep-data "
                 "keeps your memory).")
    return lines


def status_lines(status: dict) -> list[str]:
    """``membrain plugin status`` for a person: the service, recording and recall, then ``describe``."""
    state = {"ready": "running", "stopped": "stopped", "not_installed": "not installed yet"}.get(
        status.get("state"), str(status.get("state", "unknown")).replace("_", " "))
    recording = status.get("recording")
    lines = [f"Service: {state}." + (f" Recording: {recording}." if isinstance(recording, str) else "")
             + f" Semantic recall: {str(status.get('semantic_recall', 'unknown')).replace('_', ' ')}."
             + (f" Messages waiting to be stored: {status['pending_records']}." if status.get("pending_records")
                else "")]
    return lines + describe(status["on_this_computer"])


def leftovers(found: dict, *, keep_data: bool) -> list[str]:
    """What memBrain does not remove, and where the user finds it."""
    lines = ["Not removed by memBrain:",
             "  Your agent's plugin. Remove it there, or the agent's next session installs memBrain again:",
             *_agent_lines(found, disable=False),
             "  Your agent's own conversation history and memory files (Claude Code keeps them under ~/.claude, "
             "Codex under ~/.codex), and anything the agent wrote into your projects."]
    if found["uv_cache"]:
        lines.append(f"  uv's download cache, shared with other programs, with the packages memBrain used: "
                     f"{show(found['uv_cache'])} (uv cache clean empties it for every program)")
    for python in found["uv_python"]:
        lines.append(f"  uv's Python 3.12, which other uv tools may use: {show(python)}")
    if found["onnxruntime_cache"]:
        lines.append(f"  ONNX Runtime's folder, written by memBrain releases before 2026-11-19 and perhaps by other "
                     f"programs: {show(found['onnxruntime_cache'])}")
    if not keep_data:
        lines.append("  Backups you made with membrain desktop backup: restoring one brings back what it holds.")
    return lines


# Stop ----------------------------------------------------------------------------------------------------------

def stop_lines(directory: Path) -> tuple[int, list[str]]:
    from .desktop import stop

    if not (Path(directory) / "profile.json").exists():
        return 0, [f"memBrain is not installed in {show(directory)}; nothing to stop."]
    try:
        stop(directory)
    except FAILURES as error:
        return 1, [f"{getattr(error, 'code', type(error).__name__)}: {error}"]
    found = {"agents": [{"host": name, **entry} for name, entry in recorded_hosts(directory).items()]}
    return 0, ["memBrain's service is stopped. Your memory is kept.",
               "The memBrain plugin starts it again with your agent's next message or session. To keep it stopped, "
               "turn the plugin off in your agent, or remove it:",
               *_agent_lines(found, disable=True)]


# Uninstall -----------------------------------------------------------------------------------------------------

def _owned(directory: Path) -> bool:
    """Whether the whole directory is memBrain's: its default location, or nothing but what memBrain writes."""
    from .local_profile import _platform_data_directory

    if os.path.abspath(directory) in {os.path.abspath(_platform_data_directory("memBrain", "membrain")),
                                      os.path.abspath(_platform_data_directory("Agent Memory", "agent-memory"))}:
        return True
    try:
        return all(_own(entry.name) for entry in directory.iterdir())
    except OSError:
        return False


def _own(name: str) -> bool:
    return name in OWN_ENTRIES or name.startswith(OWN_PREFIXES)


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def remove_memory(directory: Path) -> list[str]:
    """Remove the data directory, or only memBrain's entries in a directory it does not own. Returns the names
    of what was left there."""
    directory = Path(directory)
    if not directory.exists():
        return []
    if _owned(directory):
        shutil.rmtree(directory)
        return []
    left = []
    for entry in sorted(directory.iterdir()):
        if _own(entry.name):
            _remove(entry)
        else:
            left.append(entry.name)
    return left


def plan_lines(found: dict, *, keep_data: bool) -> list[str]:
    lines = [("membrain plugin uninstall --keep-data removes:" if keep_data else
              "membrain plugin uninstall removes from this computer:")]
    memory = found["memory"]
    if not keep_data and memory["exists"]:
        lines.append(f"  Your memory: messages, notes, the database, the local model and logs. {show(memory['path'])}"
                     f", {human(memory['bytes'])}")
        if found["erasure_record"] and found["erasure_record"]["exists"]:
            lines.append(f"  Its record of what you erased. {show(found['erasure_record']['path'])}")
        if found["database_engine"] == "docker":
            lines.append("  Its database, which Docker keeps in a volume (docker compose down --volumes).")
    program = found["program"]
    if program and program["exists"]:
        lines.append(f"  The memBrain program that uv installed. {show(program['path'])}, {human(program['bytes'])}")
    if found["engine_cache"]["exists"]:
        lines.append(f"  The database engine cache. {show(found['engine_cache']['path'])}, "
                     f"{human(found['engine_cache']['bytes'])}")
    if found["uv_cache"]:
        lines.append("  memBrain's own files in uv's download cache (uv cache clean membrain-ai).")
    if keep_data:
        lines.append(f"It keeps your memory in {show(memory['path'])}"
                     + (f", {human(memory['bytes'])}" if memory["exists"] else "")
                     + ". Install the plugin again and its next session finds it; to delete it, run membrain plugin "
                     "uninstall without --keep-data instead.")
    return lines


def _busy(found: dict) -> list[dict]:
    """Processes that would start memBrain again or install it while it is removed: everything but the service
    and its database, which uninstall stops itself."""
    return [item for item in found["processes"] or () if item["role"] not in ("service", "database")]


def uninstall(directory: Path, *, keep_data: bool, export: Path | None, yes: bool, say=print, ask=input,
              interactive: bool | None = None) -> int:
    """Stop memBrain and remove what it owns; returns the exit status. ``say`` prints a line, ``ask`` reads one."""
    directory = Path(directory)
    variable = agent_session()
    if variable:
        say(f"memBrain is not removed from inside an agent session ({variable} is set). Run this yourself, in a "
            f"terminal of your own: membrain plugin uninstall{' --keep-data' if keep_data else ''}")
        return 2
    if interactive is None:
        interactive = sys.stdin.isatty()
    if not yes and not interactive:
        say("Nothing was removed: confirm in a terminal, or add --yes to remove without asking.")
        return 2
    found = footprint(directory)
    busy = _busy(found)
    if busy:
        say("Nothing was removed: memBrain is in use. Close your agent's sessions, or wait for its installation to "
            "finish, then run this again. Still running: "
            + "; ".join(f"{ROLES[item['role']]} (process {item['pid']})" for item in busy) + ".")
        return 1
    for line in plan_lines(found, keep_data=keep_data):
        say(line)
    for line in leftovers(found, keep_data=keep_data):
        say(line)
    if found["processes"] is None:
        say("Close your agent's sessions before you continue: running processes are not listed on this system.")
    installed = (directory / "profile.json").exists()
    if not keep_data and installed and export is None and not yes:
        answer = ask("Save an export of your memory first? Type a file name, or press Enter to skip: ").strip()
        export = Path(answer).expanduser() if answer else None
    if not yes:
        token = "UNINSTALL" if keep_data else "ERASE"
        what = "remove memBrain and keep your memory" if keep_data else "remove your memory and memBrain for good"
        if ask(f"Type {token} to {what}: ").strip() != token:
            say("Nothing was removed.")
            return 1
    try:
        if export is not None and installed:
            written = _export(directory, export)
            say(f"Exported your memory to {written}. It holds your original messages; keep it somewhere safe.")
        if installed:
            _stop_everything(directory, keep_data=keep_data)
    except FAILURES as error:
        say(f"Nothing was removed: {getattr(error, 'code', type(error).__name__)}: {error}")
        return 1
    removed, failed, left = [], [], []
    steps = []
    if not keep_data:
        steps.append(("your memory", lambda: left.extend(remove_memory(directory)), found["memory"]))
        record = _recovery_record(directory) if installed else None
        if record is not None:
            steps.append(("its record of what you erased", lambda: _remove_record(record), found["erasure_record"]))
    steps.append(("the database engine cache", lambda: _remove_engine_cache(), found["engine_cache"]))
    for label, action, where in steps:
        if where is not None and not where["exists"]:
            continue
        try:
            action()
            removed.append(label)
        except OSError as error:
            failed.append(f"{label} ({show(where['path']) if where else ''}: {type(error).__name__})")
    if found["uv_cache"] and _uv() is not None:
        _uv_run("cache", "clean", TOOL, timeout=120)
    program = found["program"]
    if program and program["exists"]:
        if os.name == "nt" or _uv() is None:
            failed.append(f"the memBrain program: run uv tool uninstall {TOOL} once this window is closed")
        elif _uv_run("tool", "uninstall", TOOL, timeout=180):
            removed.append("the memBrain program")
        else:
            failed.append(f"the memBrain program: uv tool uninstall {TOOL} did not finish")
    say(("Removed: " + ", ".join(removed) + ".") if removed else "Nothing needed removing.")
    if left:
        say(f"Left in {show(directory)}, which memBrain did not create: {', '.join(left)}.")
    if failed:
        say("Not removed: " + "; ".join(failed) + ".")
    if keep_data:
        say(f"Your memory is kept in {show(directory)}.")
    after = processes(directory)
    if after:
        say(_running({"processes": after}))
    say("Last step, in your agent: remove the plugin, or its next session installs memBrain again:")
    for line in _agent_lines(found, disable=False):
        say(line)
    return 1 if failed else 0


def _uv_run(*arguments: str, timeout: float) -> bool:
    try:
        return subprocess.run([_uv(), *arguments], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=timeout, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _remove_record(record: Path) -> None:
    shutil.rmtree(record)
    try:
        record.parent.rmdir()  # Only when no other installation keeps its record there.
    except OSError:
        pass


def _remove_engine_cache() -> None:
    from .native_bundle import _cache_directory

    cache = _cache_directory()
    shutil.rmtree(cache)
    try:
        cache.parent.rmdir()  # ~/.cache/membrain, once nothing else of memBrain's is in it.
    except OSError:
        pass


def _export(directory: Path, path: Path) -> Path:
    """Write the owner's memory to ``path`` as a new owner-only file, starting the service for it if needed."""
    from . import desktop, host
    from .desktop_connection import open_client
    from .plugin_cli import write_private

    if not desktop.status(directory).get("ready"):
        desktop.start(directory)
    with open_client(directory, start_service=False, timeout=30) as client:
        host.flush(client, directory)  # Records still queued are part of the memory.
    document = json.dumps(host.export_user(directory, None), ensure_ascii=False, indent=2)
    write_private(path, document)
    return path


def _stop_everything(directory: Path, *, keep_data: bool) -> None:
    from . import desktop
    from .local_profile import load_profile

    desktop.stop(directory)
    if not keep_data and load_profile(directory).database_engine == "docker":
        desktop._compose(load_profile(directory), "down", "--volumes")  # The database lives in a Docker volume.
