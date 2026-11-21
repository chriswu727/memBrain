"""Stopping memBrain, seeing what it put on the computer, and taking it off again, through the commands a user runs.

The installation is real (an embedded database and the service, started as a plugin starts them); uv is a fake that
answers where its directories are and records what it was asked to remove, so no real uv tool is touched. The engine
cache is redirected into the test's own directory (XDG_CACHE_HOME), so the shared cache is never removed.
"""
import json
import os
import pty
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, host, lifecycle, native_bundle, plugin
from membrain.mcp_server import create_server

needs_service = pytest.mark.skipif(not embedded_database.available(),
                                   reason="embedded PostgreSQL binaries are not installed")
FAKE_UV = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_UV_LOG"
case "$*" in
  "tool dir") printf '%s\\n' "$UV_TOOL_DIR" ;;
  "tool dir --bin") printf '%s\\n' "$UV_TOOL_BIN_DIR" ;;
  "cache dir") printf '%s\\n' "$UV_CACHE_DIR" ;;
  "python dir") printf '%s\\n' "$FAKE_UV_PYTHON" ;;
  "tool uninstall membrain-ai") rm -rf "$UV_TOOL_DIR/membrain-ai" "$UV_TOOL_BIN_DIR/membrain" ;;
  "cache clean membrain-ai") : ;;
  *) exit 2 ;;
esac
"""
MESSAGE = "For the frontend packages I prefer pnpm over npm."
REPLY = "Noted, I'll use pnpm."


class Machine:
    """A user's computer in miniature: home, uv's directories with an installed memBrain tool, the data directory."""

    def __init__(self, root: Path, monkeypatch):
        self.root = root
        self.home = root / "home"
        self.data = root / "data" / "membrain"
        self.cache = root / "cache"
        self.tools = root / "uv-tools"
        self.bin = root / "bin"
        self.uv_cache = root / "uv-cache"
        self.log = root / "uv-calls.log"
        for path in (self.home, self.cache, self.tools / "membrain-ai" / "bin", self.bin, self.uv_cache,
                     root / "uv-python" / "cpython-3.12.3-linux-x86_64-gnu"):
            path.mkdir(parents=True, exist_ok=True)
        (self.tools / "membrain-ai" / "bin" / "python").write_text("installed tool\n")
        (self.bin / "membrain").write_text("#!/bin/sh\n")
        (self.bin / "uv").write_text(FAKE_UV)
        (self.bin / "uv").chmod(0o755)
        self.env = {key: value for key, value in os.environ.items() if key not in lifecycle.AGENT_VARIABLES}
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}", XDG_CACHE_HOME=str(self.cache),
                        UV_TOOL_DIR=str(self.tools), UV_TOOL_BIN_DIR=str(self.bin), UV_CACHE_DIR=str(self.uv_cache),
                        FAKE_UV_LOG=str(self.log), FAKE_UV_PYTHON=str(root / "uv-python"), MEMBRAIN_SEMANTIC="0",
                        MEMBRAIN_DIRECTORY=str(self.data))
        self.env.pop("UV", None)
        for key, value in self.env.items():
            if os.environ.get(key) != value:
                monkeypatch.setenv(key, value)
        for key in lifecycle.AGENT_VARIABLES:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("UV", raising=False)

    def membrain(self, *arguments, **extra):
        return subprocess.run([sys.executable, "-m", "membrain.cli", "plugin", *arguments], capture_output=True,
                              text=True, env={**self.env, **extra}, timeout=600, stdin=subprocess.DEVNULL)

    def uv_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def files(self):
        """Everything left under the machine, as ``find`` lists it."""
        return sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))


def remember(directory: Path) -> None:
    plugin.start(directory)
    assert plugin.user_prompt({"session_id": "s1", "prompt": MESSAGE, "prompt_id": "t1"}, directory) is not None
    plugin.stop({"session_id": "s1", "prompt_id": "t1", "last_assistant_message": REPLY}, directory)
    settle(directory)


def settle(directory: Path) -> None:
    """Wait for any start a hook began in the background (a hook that found the service busy starts it again)."""
    deadline = time.monotonic() + 120
    while "command" in running(directory) and time.monotonic() < deadline:
        time.sleep(0.5)


def remembered(directory: Path) -> bool:
    with host.ready_client(directory) as client:
        items = client.timeline(roles=("user",), max_characters=20_000, max_item_characters=2_000, limit=50)["items"]
    return any(item["text"] == MESSAGE for item in items)


def running(directory: Path) -> list[str]:
    return [item["role"] for item in lifecycle.processes(directory)]


def stopped(directory):
    try:
        desktop.stop(directory)
    except Exception:  # Teardown: a test's hand-made profile cannot be stopped, and need not be.
        pass


@pytest.fixture
def machine(tmp_path, monkeypatch):
    found = Machine(tmp_path, monkeypatch)
    yield found
    if (found.data / "profile.json").exists():
        stopped(found.data)


# Stop ------------------------------------------------------------------------------------------------------------

@needs_service
def test_stop_stops_the_service_and_the_database_and_the_next_message_starts_them_again(machine):
    remember(machine.data)
    assert sorted(running(machine.data)) == ["database", "service"]
    result = machine.membrain("stop")
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "memBrain's service is stopped. Your memory is kept.\n"
        "The memBrain plugin starts it again with your agent's next message or session. To keep it stopped, turn "
        "the plugin off in your agent, or remove it:\n"
        "    Claude Code: claude plugin disable membrain@membrain\n"
        "    Codex: remove the memBrain plugin in Codex (it was added with codex plugin add membrain@membrain)\n"
        "    WorkBuddy or CodeBuddy: remove memBrain from the plugins (Skills, then Plugins)\n"
        "    OpenClaw: remove the membrain plugin from OpenClaw's plugins\n")
    assert desktop.status(machine.data)["state"] == "stopped"
    assert running(machine.data) == [], lifecycle.processes(machine.data)
    # The next message of a session with the plugin starts the service in the background.
    assert "starting or unavailable" in plugin.session_start({"session_id": "s2"}, machine.data)
    deadline = time.monotonic() + 120
    while not desktop.status(machine.data).get("ready") and time.monotonic() < deadline:
        time.sleep(0.5)
    assert remembered(machine.data)


def test_stop_without_an_installation_says_so(machine):
    result = machine.membrain("stop")
    assert (result.returncode, result.stdout) == (0, f"memBrain is not installed in {machine.data}; nothing to "
                                                     "stop.\n")


def test_stop_names_only_the_agents_whose_hooks_have_run(machine, monkeypatch):
    plugin_root = machine.root / "claude-plugin"
    plugin_root.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
    lifecycle.record_host(machine.data, "claude-code")
    before = (machine.data / "plugin" / "hosts.json").stat().st_mtime_ns
    lifecycle.record_host(machine.data, "claude-code")  # Unchanged: not written again.
    assert (machine.data / "plugin" / "hosts.json").stat().st_mtime_ns == before
    assert lifecycle.recorded_hosts(machine.data) == {"claude-code": {"plugin": str(plugin_root),
                                                                       "plugin_data": None}}
    found = {"agents": [{"host": "claude-code", "plugin": str(plugin_root), "plugin_data": None}]}
    assert lifecycle._agent_lines(found, disable=True) == ["    Claude Code: claude plugin disable membrain@membrain"]
    assert lifecycle._agent_lines(found, disable=False) == [
        "    Claude Code: claude plugin uninstall membrain@membrain"]


# What is on this computer ------------------------------------------------------------------------------------------

@needs_service
def test_status_lists_where_everything_is_and_what_runs(machine, monkeypatch):
    plugin_root = machine.root / "claude-plugin"
    plugin_root.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
    remember(machine.data)
    plugin.session_start({"session_id": "s2"}, machine.data)  # The hook notes where the host keeps the plugin.
    result = machine.membrain("status")
    assert result.returncode == 0, result.stderr
    found = json.loads(result.stdout)["on_this_computer"]
    assert found["memory"]["path"] == str(machine.data) and found["memory"]["bytes"] > 10_000_000
    assert found["erasure_record"]["exists"] and found["erasure_record"]["path"].startswith(
        str(machine.data.parent / ".agent-memory-recovery"))
    assert found["program"] == {"path": str(machine.tools / "membrain-ai"), "exists": True,
                                "bytes": len("installed tool\n"), "command": str(machine.bin / "membrain")}
    assert found["engine_cache"]["path"] == str(machine.cache / "membrain" / "native")
    assert found["engine_cache"]["bytes"] > 10_000_000
    assert found["uv_cache"] == str(machine.uv_cache)
    assert found["uv_python"] == [str(machine.root / "uv-python" / "cpython-3.12.3-linux-x86_64-gnu")]
    assert sorted(item["role"] for item in found["processes"]) == ["database", "service"]
    assert found["agents"] == [{"host": "claude-code", "plugin": str(plugin_root), "plugin_data": None}]
    lines = lifecycle.status_lines(json.loads(result.stdout))
    assert lines[0] == "Service: running. Recording: on. Semantic recall: not downloaded."
    assert lines[1] == "memBrain on this computer:"
    assert lines[2].startswith(f"  Your memory (messages, notes, database, local model, logs): {machine.data}, ")
    assert f"  Claude Code's copy of the plugin: {plugin_root}" in lines
    assert lines[-2].startswith("  Running: the memory service (process ")
    assert lines[-1] == ("Stop for now: membrain plugin stop. Remove: membrain plugin uninstall (asks first; "
                         "--keep-data keeps your memory).")


def test_status_in_a_terminal_is_plain_text_and_json_otherwise(machine):
    output, status = in_terminal(machine, ["status"], [])
    assert status == 0 and output.startswith("Service: not installed yet. ") and "{" not in output
    assert "memBrain on this computer:" in output and f"{machine.data} (none yet)" in output
    assert json.loads(machine.membrain("status").stdout)["state"] == "not_installed"


# Uninstall ---------------------------------------------------------------------------------------------------------

@needs_service
def test_uninstall_keeping_the_data_and_installing_again_brings_the_memory_back(machine):
    remember(machine.data)
    cache = machine.cache / "membrain" / "native"
    assert cache.is_dir()
    result = machine.membrain("uninstall", "--keep-data", "--yes")
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == "membrain plugin uninstall --keep-data removes:"
    assert lines[1].startswith(f"  The memBrain program that uv installed. {machine.tools / 'membrain-ai'}, ")
    assert lines[2].startswith(f"  The database engine cache. {cache}, ")
    assert lines[3] == "  memBrain's own files in uv's download cache (uv cache clean membrain-ai)."
    assert lines[4].startswith(f"It keeps your memory in {machine.data}, ")
    assert "Removed: the database engine cache, the memBrain program." in lines
    assert f"Your memory is kept in {machine.data}." in lines
    assert machine.uv_calls()[-2:] == ["cache clean membrain-ai", "tool uninstall membrain-ai"]
    assert not cache.exists() and not (machine.tools / "membrain-ai").exists() and not (machine.bin / "membrain").exists()
    assert (machine.data / "profile.json").exists() and running(machine.data) == []
    # Installing again (the plugin's next session): the engine is extracted again and the memory is there.
    plugin.start(machine.data)
    assert cache.is_dir() and remembered(machine.data)


@needs_service
def test_uninstall_removes_everything_after_an_export_once_the_word_is_typed(machine):
    remember(machine.data)
    record = Path(lifecycle.footprint(machine.data)["erasure_record"]["path"])
    assert record.is_dir()
    # A wrong word removes nothing.
    output, status = in_terminal(machine, ["uninstall"], ["", "erase"])
    assert status == 1 and output.rstrip().endswith("Nothing was removed.")
    assert "Type ERASE to remove your memory and memBrain for good: " in output
    assert desktop.status(machine.data).get("ready") and remembered(machine.data)
    export = machine.root / "my-memory.json"
    output, status = in_terminal(machine, ["uninstall"], [str(export), "ERASE"])
    assert status == 0, output
    assert "Save an export of your memory first? Type a file name, or press Enter to skip: " in output
    assert f"Exported your memory to {export}. It holds your original messages; keep it somewhere safe." in output
    assert ("Removed: your memory, its record of what you erased, the database engine cache, the memBrain program."
            in output)
    assert "Last step, in your agent: remove the plugin, or its next session installs memBrain again:" in output
    assert MESSAGE in export.read_text(encoding="utf-8") and export.stat().st_mode & 0o777 == 0o600
    assert running(machine.data) == []
    assert machine.files() == sorted([  # What find lists under the machine afterwards.
        "bin", "bin/uv", "cache", "data", "home", "my-memory.json", "uv-cache", "uv-calls.log", "uv-python",
        "uv-python/cpython-3.12.3-linux-x86_64-gnu", "uv-tools"])


def test_uninstall_refuses_inside_an_agent_session_even_with_yes(machine):
    machine.data.mkdir(parents=True)
    (machine.data / "profile.json").write_text("{}")
    for variable in ("CLAUDECODE", "CLAUDE_PLUGIN_ROOT", "PLUGIN_DATA", "CODEX_SANDBOX_NETWORK_DISABLED",
                     "CODEBUDDY_PLUGIN_ROOT"):
        result = machine.membrain("uninstall", "--yes", **{variable: "1"})
        assert result.returncode == 2
        assert result.stdout == (f"memBrain is not removed from inside an agent session ({variable} is set). Run this "
                                 "yourself, in a terminal of your own: membrain plugin uninstall\n")
    result = machine.membrain("uninstall")  # No terminal to confirm in, and no --yes.
    assert (result.returncode, result.stdout) == (
        2, "Nothing was removed: confirm in a terminal, or add --yes to remove without asking.\n")
    assert (machine.data / "profile.json").exists() and (machine.tools / "membrain-ai").exists()
    assert machine.uv_calls() == []


@needs_service
def test_uninstall_waits_until_the_agents_sessions_are_closed(machine):
    remember(machine.data)
    server = subprocess.Popen([sys.executable, "-m", "membrain.cli", "plugin", "mcp", "--directory",
                               str(machine.data)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=machine.env)
    try:
        deadline = time.monotonic() + 30
        while "tool server" not in running(machine.data) and time.monotonic() < deadline:
            time.sleep(0.2)
        result = machine.membrain("uninstall", "--yes")
        assert result.returncode == 1
        assert result.stdout == ("Nothing was removed: memBrain is in use. Close your agent's sessions, or wait for "
                                 "its installation to finish, then run this again. Still running: a tool server of "
                                 f"an open agent session (process {server.pid}).\n")
        assert (machine.data / "profile.json").exists()
        assert not {"tool uninstall membrain-ai", "cache clean membrain-ai"} & set(machine.uv_calls())
    finally:
        server.stdin.close()
        server.wait(timeout=30)
    result = machine.membrain("uninstall", "--yes")
    assert result.returncode == 0, result.stdout
    assert not machine.data.exists() and running(machine.data) == []


def in_terminal(machine, arguments, answers):
    """Run ``membrain plugin ...`` with a terminal on standard input and output, typing ``answers`` at its prompts."""
    pid, descriptor = pty.fork()
    if pid == 0:
        os.execve(sys.executable, [sys.executable, "-m", "membrain.cli", "plugin", *arguments], machine.env)
    output, pending = b"", list(answers)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        ready, _, _ = select.select([descriptor], [], [], 1)
        if ready:
            try:
                chunk = os.read(descriptor, 65536)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
            if pending and output.endswith(b": "):  # A prompt; a heading ends its line instead.
                os.write(descriptor, pending.pop(0).encode() + b"\n")
                output += b"\n"
    else:
        os.kill(pid, signal.SIGKILL)
    _, status = os.waitpid(pid, 0)
    return output.decode("utf-8", "replace").replace("\r\n", "\n"), os.waitstatus_to_exitcode(status)


# Removal is the user's, never the agent's --------------------------------------------------------------------------

def test_no_tool_hook_command_or_instruction_offers_removal(tmp_path):
    root = Path(__file__).parents[1]
    tools = {tool.name for tool in __import__("asyncio").run(create_server(type("C", (), {"brain_id": "b"})(),
                                                                           directory=tmp_path).list_tools())}
    assert not any("uninstall" in name or "stop" in name for name in tools)
    assert not {"stop", "uninstall"} & set(plugin.TOOLS)
    texts = [host.server_instructions(), (root / "plugins" / "membrain" / "skills" / "membrain" / "SKILL.md").read_text()]
    assert not any("uninstall" in text or "plugin stop" in text for text in texts)
    for path in (root / "plugins" / "membrain" / "commands").glob("*.md"):
        allowed = next((line for line in path.read_text().splitlines() if line.startswith("allowed-tools:")), "")
        # Exact commands only: no pattern such as Bash(membrain:*) that would let an agent run removal unasked.
        assert "*" not in allowed and "uninstall" not in allowed, path


# Pieces --------------------------------------------------------------------------------------------------------

def test_a_directory_memBrain_does_not_own_loses_only_what_memBrain_wrote(tmp_path):
    directory = tmp_path / "Documents"
    (directory / "plugin").mkdir(parents=True)
    (directory / "profile.json").write_text("{}")
    (directory / "service.log").write_text("")
    (directory / "thesis.docx").write_text("mine")
    assert lifecycle.remove_memory(directory) == ["thesis.docx"]
    assert sorted(path.name for path in directory.iterdir()) == ["thesis.docx"]
    owned = tmp_path / "memory"
    (owned / "postgres").mkdir(parents=True)
    (owned / "transition-5cc764ba-7f6a-474c-b293-6ddcf34ea480").mkdir()  # An engine transition's work directory.
    (owned / "service.log.2").write_text("")
    (owned / "profile.json").write_text("{}")
    assert lifecycle.remove_memory(owned) == [] and not owned.exists()


@pytest.mark.parametrize("argv,role", [
    (["/u/tools/membrain-ai/bin/python", "-m", "membrain.cli", "desktop", "_run", "--directory", "/d"], "service"),
    (["/u/tools/membrain-ai/bin/python", "/u/tools/membrain-ai/bin/membrain", "plugin", "mcp"], "tool server"),
    (["/u/tools/membrain-ai/bin/python", "-m", "membrain.cli", "plugin", "mcp", "--directory", "/d"], "tool server"),
    (["/u/bin/python", "/u/bin/membrain", "plugin", "hook", "user-prompt"], None),
    (["/u/bin/python", "/u/bin/membrain", "plugin", "start"], "command"),
    (["uv", "tool", "install", "--quiet", "--python", "3.12", "membrain-ai[embedded,semantic] @ https://x/a.zip"],
     "installer"),
    (["uv", "tool", "run", "--from", "membrain-ai", "membrain", "plugin", "mcp"], None),  # Its child is counted.
    (["/usr/bin/python3", "-m", "pytest"], None),
])
def test_processes_are_told_apart_by_their_command_line(argv, role):
    assert lifecycle._role(argv) == role


def test_a_process_belongs_to_the_installation_it_names_or_its_environment_gives(tmp_path):
    mine, other = tmp_path / "membrain", tmp_path / "other"
    assert lifecycle._same_directory(["membrain", "plugin", "mcp", "--directory", str(mine)], None, mine)
    assert not lifecycle._same_directory(["membrain", "plugin", "mcp", "--directory", str(other)], {}, mine)
    assert lifecycle._same_directory(["membrain"], {"MEMBRAIN_DIRECTORY": str(mine)}, mine)
    assert not lifecycle._same_directory(["membrain"], {"MEMBRAIN_DIRECTORY": str(other)}, mine)
    assert lifecycle._same_directory(["membrain"], {"XDG_DATA_HOME": str(tmp_path)}, mine)
    assert not lifecycle._same_directory(["membrain"], {"HOME": str(other)}, mine)


# Long paths --------------------------------------------------------------------------------------------------------

def test_the_longest_engine_path_is_computed_from_the_bundle():
    key, entry, archive = native_bundle._source()
    records = native_bundle._manifest(entry)
    root = Path("/c") / ("x" * 100)
    longest = native_bundle.longest_path(root, key, entry["manifest_sha256"], archive.name.removesuffix(".tar.gz"),
                                         records)
    deepest = max(len(name) for name in records)
    staging = len(str(root)) + 1 + len(".staging-") + 24 + 1 + len(archive.name.removesuffix(".tar.gz")) + 1 + deepest
    assert longest == staging and deepest == 63  # include/server/snowball/libstemmer/stem_ISO_8859_1_portuguese.h


def test_a_windows_cache_path_too_long_for_max_path_is_named_before_anything_is_extracted(tmp_path, monkeypatch):
    """Windows is not available here: the limit is supplied as Windows reports it without long path support."""
    cache = tmp_path / ("deep" * 30)
    monkeypatch.setattr(native_bundle, "_cache_directory", lambda: cache)
    monkeypatch.setattr(native_bundle, "path_limit", lambda: (259, True))
    with pytest.raises(native_bundle.NativeBundleError) as failure:
        native_bundle.prepare()
    assert failure.value.code == "embedded_database_path_too_long"
    assert str(failure.value).startswith("The embedded database cache could not be prepared: its files need paths "
                                         "of up to ")
    assert f"characters under {cache}, and this system allows 259." in str(failure.value)
    assert not cache.exists()


def test_a_failure_on_a_path_windows_may_not_allow_names_the_path_length(tmp_path, monkeypatch):
    """When Windows cannot say whether long paths are on, the check comes after a failed extraction."""
    cache = tmp_path / ("deep" * 30)
    monkeypatch.setattr(native_bundle, "_cache_directory", lambda: cache)
    monkeypatch.setattr(native_bundle, "path_limit", lambda: (259, False))

    def refuse(*args, **kwargs):
        raise FileNotFoundError("[WinError 3] The system cannot find the path specified")

    monkeypatch.setattr(native_bundle.tarfile.TarFile, "extractall", refuse)
    with pytest.raises(native_bundle.NativeBundleError) as failure:
        native_bundle.prepare()
    assert failure.value.code == "embedded_database_path_too_long"
    monkeypatch.setattr(native_bundle, "path_limit", lambda: (4095, True))
    with pytest.raises(native_bundle.NativeBundleError) as failure:
        native_bundle.prepare()
    assert failure.value.code == "embedded_database_cache_failed"  # Short paths: the cause is another.


def test_long_path_support_is_read_from_windows_and_paths_elsewhere_have_room():
    if os.name == "nt":
        assert native_bundle.path_limit()[0] in (None, 259)
    else:
        assert native_bundle.path_limit() in ((4095, True), (1023, True))


def test_the_embedded_database_makes_no_unix_socket_so_a_long_data_directory_cannot_exceed_its_limit():
    """Unix socket paths are limited to about 100 bytes; the cluster listens on 127.0.0.1 only and every client
    (psycopg, pg_dump, pg_restore) connects there, so the data directory's length never reaches a socket path."""
    import inspect

    configuration = embedded_database._configuration(type("P", (), {"database_port": 55433})())
    assert "unix_socket_directories = ''" in configuration and "listen_addresses = '127.0.0.1'" in configuration
    assert 'host="127.0.0.1"' in inspect.getsource(embedded_database._admin_connection)
    assert '"--host=127.0.0.1"' in inspect.getsource(embedded_database.client_command)
