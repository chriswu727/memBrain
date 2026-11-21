"""Host launchers on a sandboxed PATH: uv and uvx, uv alone, or neither. Fake uv commands record what they were asked.

Nothing here installs or runs the real runtime, and no service is started.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "plugins" / "membrain"
WRAPPER = PLUGIN / "bin" / "membrain-hook"
WINDOWS_WRAPPER = PLUGIN / "bin" / "membrain-hook.cmd"
REQUIREMENT = re.compile(r"membrain-ai\[embedded,semantic\] @ https://github\.com/chriswu727/membrain/archive/"
                         r"[0-9a-f]{40}\.zip")
RUN = ["--offline", "--python", "3.12", "--from", "membrain-ai", "membrain", "plugin"]
NO_UV = ("memBrain is installed but cannot run: uv was not found on this computer, so nothing is remembered or "
         "recalled. In your first reply, tell the user this once and ask them to install uv from "
         "https://docs.astral.sh/uv/ and then start a new session.")
NOT_READY = ("memBrain is installed but its runtime is not ready yet, so nothing is remembered or recalled until it "
             "is. It installs in the background; the first time needs an internet connection and takes a few "
             "minutes. Memory then starts by itself; no new session is needed. In your first reply, tell the user "
             "this once, and that if they see it again in a later session the installation is failing, for example "
             "without an internet connection.")
SHELLS = [shell for shell in ("/bin/sh", "/bin/dash", "/bin/bash") if os.access(shell, os.X_OK)]
FAKE = """#!/bin/sh
{ printf '%s' "${0##*/}"; for argument in "$@"; do printf '\\t%s' "$argument"; done; printf '\\n'; } >> "$FAKE_LOG"
printf '%s\\n' "${UV_LOCK_TIMEOUT-unset}" >> "$FAKE_LOG.lock-timeout"
cat > /dev/null
printf '%s' "$FAKE_STDOUT"
exit "${FAKE_EXIT:-0}"
"""


def notice(text):
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def requirement():
    (pinned,) = set(REQUIREMENT.findall((PLUGIN / "hooks" / "claude-hooks.json").read_text()))
    return pinned


class Sandbox:
    """A PATH holding only the fake uv commands asked for and the few utilities the fakes use."""

    def __init__(self, root: Path, commands=("uv", "uvx")):
        self.bin = root / "bin"
        tools = root / "tools"
        self.bin.mkdir()
        tools.mkdir()
        for name in commands:
            (self.bin / name).write_text(FAKE)
            (self.bin / name).chmod(0o755)
        for utility in ("cat",):
            os.symlink(shutil.which(utility), tools / utility)
        self.log = root / "calls.log"
        self.env = {"PATH": f"{self.bin}:{tools}", "FAKE_LOG": str(self.log), "HOME": str(root),
                    "CLAUDE_PLUGIN_DATA": str(root / "data")}

    def calls(self):
        if not self.log.exists():
            return []
        return [line.split("\t") for line in self.log.read_text().splitlines()]

    def run(self, argv, payload=None, **env):
        return subprocess.run(argv, input=json.dumps(payload or {"session_id": "s1", "prompt": "hi"}), text=True,
                              capture_output=True, env={**self.env, **env}, timeout=30)


def hook_commands(name):
    hooks = json.loads((PLUGIN / "hooks" / name).read_text())["hooks"]
    commands = {}
    for event, groups in hooks.items():
        for group in groups:
            for hook in group["hooks"]:
                key = "start" if "plugin start" in hook["command"] else event
                commands[key] = hook
    return commands


HOOK_FILES = [("claude-hooks.json", []), ("codex-hooks.json", ["--host", "codex"])]
EVENTS = {"SessionStart": "session-start", "UserPromptSubmit": "user-prompt", "Stop": "stop"}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("hooks_file,host", HOOK_FILES)
@pytest.mark.parametrize("commands,runner", [(("uv", "uvx"), ["uvx"]), (("uv",), ["uv", "tool", "run"])])
def test_hook_commands_run_the_runtime_with_uvx_or_with_uv_alone(tmp_path, shell, hooks_file, host, commands, runner):
    sandbox = Sandbox(tmp_path, commands)
    hooks = hook_commands(hooks_file)
    for event, name in EVENTS.items():
        result = sandbox.run([shell, "-c", hooks[event]["command"]], FAKE_STDOUT='{"hookSpecificOutput":{}}')
        assert result.returncode == 0 and result.stderr == ""
        assert result.stdout == '{"hookSpecificOutput":{}}'  # The runtime's answer, unchanged and alone.
        assert sandbox.calls()[-1] == [*runner, *RUN, "hook", name, *host]
    sandbox.log.unlink()
    result = sandbox.run([shell, "-c", hooks["start"]["command"]])
    assert result.returncode == 0 and result.stdout == "" and result.stderr == ""
    assert sandbox.calls() == [["uv", "tool", "install", "--quiet", "--python", "3.12", requirement()],
                               [*runner, *RUN, "start"]]
    assert hooks["start"].get("async") is True and hooks["SessionStart"]["timeout"] == 10


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("hooks_file,host", HOOK_FILES)
def test_hook_commands_say_once_at_session_start_that_uv_is_missing(tmp_path, shell, hooks_file, host):
    sandbox = Sandbox(tmp_path, commands=())
    hooks = hook_commands(hooks_file)
    for key, hook in hooks.items():
        result = sandbox.run([shell, "-c", hook["command"]])
        assert result.returncode == 0 and result.stderr == "", key
        if key == "SessionStart":
            assert result.stdout.endswith("\n") and result.stdout.count("\n") == 1
            assert json.loads(result.stdout) == notice(NO_UV)
        else:
            assert result.stdout == "", key
    assert sandbox.calls() == []
    assert not (tmp_path / "data").exists()  # Nothing of the hook input is kept by the shell.


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("hooks_file,host", HOOK_FILES)
@pytest.mark.parametrize("commands", [("uv",), ("uv", "uvx")])
def test_hook_commands_say_when_the_runtime_cannot_run_yet(tmp_path, shell, hooks_file, host, commands):
    sandbox = Sandbox(tmp_path, commands)
    hooks = hook_commands(hooks_file)
    for key, hook in hooks.items():
        result = sandbox.run([shell, "-c", hook["command"]], FAKE_EXIT="2")  # uv: the tool is not installed.
        assert result.returncode == 0 and result.stderr == "", key
        if key == "SessionStart":
            assert json.loads(result.stdout) == notice(NOT_READY)
        else:
            assert result.stdout == "", key


def run_wrapper(sandbox, event, **env):
    return sandbox.run(["/bin/sh", str(WRAPPER), event], **env)


def wait_for_calls(sandbox, count):
    deadline = time.monotonic() + 10
    while len(sandbox.calls()) < count and time.monotonic() < deadline:
        time.sleep(0.05)
    return sandbox.calls()


@pytest.mark.parametrize("commands,runner", [(("uv", "uvx"), ["uvx"]), (("uv",), ["uv", "tool", "run"])])
def test_workbuddy_wrapper_runs_the_runtime_with_uvx_or_with_uv_alone(tmp_path, commands, runner):
    sandbox = Sandbox(tmp_path, commands)
    for name in EVENTS.values():
        result = run_wrapper(sandbox, name, FAKE_STDOUT='{"hookSpecificOutput":{}}')
        assert (result.returncode, result.stdout, result.stderr) == (0, '{"hookSpecificOutput":{}}', "")
        assert sandbox.calls()[-1] == [*runner, *RUN, "hook", name, "--host", "workbuddy"]
    sandbox.log.unlink()
    result = run_wrapper(sandbox, "start")
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    assert wait_for_calls(sandbox, 2) == [["uv", "tool", "install", "--quiet", "--python", "3.12", requirement()],
                                          [*runner, *RUN, "start"]]


def test_workbuddy_wrapper_says_once_at_session_start_that_uv_is_missing(tmp_path):
    sandbox = Sandbox(tmp_path, commands=())
    for event in ("start", "session-start", "user-prompt", "stop"):
        result = run_wrapper(sandbox, event)
        assert result.returncode == 0 and result.stderr == "", event
        if event == "session-start":
            assert result.stdout.count("\n") == 1 and json.loads(result.stdout) == notice(NO_UV)
        else:
            assert result.stdout == "", event
    assert sandbox.calls() == []


@pytest.mark.parametrize("commands", [("uv",), ("uv", "uvx")])
def test_workbuddy_wrapper_says_when_the_runtime_cannot_run_yet(tmp_path, commands):
    sandbox = Sandbox(tmp_path, commands)
    for event in ("session-start", "user-prompt", "stop"):
        result = run_wrapper(sandbox, event, FAKE_EXIT="2")
        assert result.returncode == 0 and result.stderr == "", event
        assert (json.loads(result.stdout) == notice(NOT_READY)) if event == "session-start" else result.stdout == ""


def test_workbuddy_wrapper_with_uvx_but_no_uv_runs_hooks_and_skips_installation(tmp_path):
    sandbox = Sandbox(tmp_path, commands=("uvx",))
    assert run_wrapper(sandbox, "start").stdout == "" and sandbox.calls() == []
    result = run_wrapper(sandbox, "session-start", FAKE_STDOUT="{}")
    assert result.stdout == "{}" and sandbox.calls() == [["uvx", *RUN, "hook", "session-start", "--host", "workbuddy"]]


def test_windows_wrapper_follows_the_same_order_by_inspection():
    """cmd.exe is not available here: the .cmd is checked line by line against the shell wrapper's behaviour."""
    lines = [line for line in WINDOWS_WRAPPER.read_text().splitlines() if line.strip()]
    assert lines.index('set "RUN=uvx"') < lines.index("where uvx >nul 2>nul && goto found") \
        < lines.index('set "RUN=uv tool run"') < lines.index("where uv >nul 2>nul && goto found") < lines.index(":found")
    missing = lines[lines.index("where uv >nul 2>nul && goto found") + 1:lines.index(":found")]
    assert missing[-1] == "exit /b 0" and len(missing) == 2
    prefix = 'if "%~1"=="session-start" echo '
    assert missing[0].startswith(prefix) and json.loads(missing[0][len(prefix):]) == notice(NO_UV)
    assert lines[-3] == ("%RUN% --offline --python 3.12 --from membrain-ai membrain plugin hook %1 --host workbuddy "
                         "2>nul && exit /b 0")
    assert lines[-2].startswith(prefix) and json.loads(lines[-2][len(prefix):]) == notice(NOT_READY)
    assert lines[-1] == "exit /b 0"
    start = lines[lines.index('if "%~1"=="start" ('):lines.index(")") + 1]
    assert start[1].strip() == "where uv >nul 2>nul || exit /b 0"
    assert "& %RUN% --offline --python 3.12 --from membrain-ai membrain plugin start" in start[2]
    assert not any(line.lstrip().startswith("uvx ") or "& uvx " in line for line in lines)
    assert all(line.split("exit /b")[1].strip() == "0" for line in lines if "exit /b" in line)
    # cmd.exe would act on these characters in an echoed message; the messages use none of them.
    for message in (NO_UV, NOT_READY):
        assert not set(message) & set("&|<>^%()!\"'`$\\")
    # A hook gives up on uv's tool lock after 2 seconds; the installation started under "start" waits for it.
    assert lines[-4] == 'set "UV_LOCK_TIMEOUT=2"' and lines.index(")") < len(lines) - 4
    assert sum("UV_LOCK_TIMEOUT" in line for line in lines if not line.startswith("rem ")) == 1


def lock_timeouts(sandbox):
    path = Path(str(sandbox.log) + ".lock-timeout")
    return path.read_text().splitlines() if path.exists() else []


@pytest.mark.parametrize("hooks_file,host", HOOK_FILES)
@pytest.mark.parametrize("commands", [("uv",), ("uv", "uvx")])
def test_hooks_never_wait_on_uvs_tool_lock_but_the_installation_does(tmp_path, hooks_file, host, commands):
    sandbox = Sandbox(tmp_path, commands)
    hooks = hook_commands(hooks_file)
    for event in EVENTS:
        sandbox.run(["/bin/sh", "-c", hooks[event]["command"]], FAKE_STDOUT="{}")
    assert lock_timeouts(sandbox) == ["2"] * 3
    Path(str(sandbox.log) + ".lock-timeout").unlink()
    sandbox.run(["/bin/sh", "-c", hooks["start"]["command"]])
    assert lock_timeouts(sandbox) == ["unset", "unset"]  # uv tool install, then plugin start: both wait.
    (tmp_path / "wrapper").mkdir()
    sandbox = Sandbox(tmp_path / "wrapper", commands)
    for name in EVENTS.values():
        run_wrapper(sandbox, name, FAKE_STDOUT="{}")
    assert lock_timeouts(sandbox) == ["2"] * 3
    run_wrapper(sandbox, "start")
    assert len(wait_for_calls(sandbox, 5)) == 5 and lock_timeouts(sandbox)[3:] == ["unset", "unset"]


def test_with_real_uv_a_hook_gives_up_on_the_tool_lock_in_seconds(tmp_path):
    """While ``uv tool install`` holds uv's tool lock (held here directly, as uv takes it: an exclusive flock on the
    tool directory's .lock), the real uv gives up after 2 seconds: session start says the runtime is not ready, and
    the prompt and stop hooks return with nothing, instead of waiting until the host stops them at 10 and 15 seconds.
    Offline and with no runtime installed; nothing is downloaded."""
    import fcntl

    uv = shutil.which("uv")
    assert uv, "uv must be on the PATH for this test"
    sandbox = Sandbox(tmp_path, commands=())
    os.symlink(uv, sandbox.bin / "uv")  # uv alone: the hooks fall back to `uv tool run`.
    os.symlink(sys.executable, sandbox.bin / "python3.12")  # The Python 3.12 the hooks ask for, found on the PATH.
    tools = tmp_path / "uv-tools"
    tools.mkdir()
    env = {"UV_TOOL_DIR": str(tools), "UV_CACHE_DIR": str(tmp_path / "uv-cache"), "UV_NO_CONFIG": "1",
           "UV_PYTHON_DOWNLOADS": "never"}
    with open(tools / ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for hooks_file, _ in HOOK_FILES:
            hooks = hook_commands(hooks_file)
            for event in EVENTS:
                started = time.monotonic()
                result = sandbox.run(["/bin/sh", "-c", hooks[event]["command"]], **env)
                assert 1.5 < time.monotonic() - started < 6, (hooks_file, event)
                assert result.returncode == 0 and result.stderr == ""
                if event == "SessionStart":
                    assert json.loads(result.stdout) == notice(NOT_READY)
                else:
                    assert result.stdout == ""
        started = time.monotonic()
        result = run_wrapper(sandbox, "session-start", **env)
        assert 1.5 < time.monotonic() - started < 6 and json.loads(result.stdout) == notice(NOT_READY)


def test_every_launcher_says_the_same_words():
    texts = {path.name: path.read_text() for path in (PLUGIN / "hooks" / "claude-hooks.json", PLUGIN / "hooks" /
                                                      "codex-hooks.json", WRAPPER, WINDOWS_WRAPPER)}
    for name, text in texts.items():
        text = text.replace('\\"', '"')
        assert text.count(NO_UV) == 1 and text.count(NOT_READY) == 1, name
    openclaw = (ROOT / "integrations" / "openclaw" / "membrain" / "index.js").read_text()
    block = openclaw[openclaw.index("export const NO_UV = "):openclaw.index(";", openclaw.index("export const NO_UV"))]
    assert "".join(re.findall(r'"([^"]*)"', block)) == NO_UV


def expand(value):
    """Claude Code's ${NAME:-default} expansion, with NAME unset."""
    return re.sub(r"\$\{[A-Z_]+:-(.*)\}", r"\1", value)


@pytest.mark.parametrize("name", [".claude-mcp.json", ".codex-mcp.json", ".codebuddy-mcp.json"])
@pytest.mark.parametrize("commands", [("uv",), ("uv", "uvx")])
def test_tool_server_starts_through_uv_tool_run(tmp_path, name, commands):
    server = json.loads((PLUGIN / name).read_text())["mcpServers"]["membrain"]
    assert server["command"] == "uv"
    sandbox = Sandbox(tmp_path, commands)
    executable = shutil.which(server["command"], path=sandbox.env["PATH"])
    assert executable == str(sandbox.bin / "uv")  # Found on a PATH without uvx, as a bare executable name.
    result = sandbox.run([executable, *[expand(argument) for argument in server["args"]]], payload={})
    assert result.returncode == 0
    # `uv tool run` is the command uvx stands for: the same options as the earlier uvx entry, after "tool run".
    assert sandbox.calls() == [["uv", "tool", "run", "--python", "3.12", "--from", requirement(), "membrain",
                                "plugin", "mcp"]]


OPENCLAW = """
import { createMembrain } from %s;
const memory = createMembrain();
const out = [];
for (const session of ["s1", "s1", "s2"]) {
  out.push(await memory.beforePromptBuild({ prompt: "hi" }, { sessionId: session }) ?? null);
}
console.log(JSON.stringify(out));
"""


def run_openclaw(sandbox, **env):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the OpenClaw plugin")
    index = (ROOT / "integrations" / "openclaw" / "membrain" / "index.js").as_uri()
    result = sandbox.run([node, "--input-type=module", "-e", OPENCLAW % json.dumps(index)], payload={}, **env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("commands,runner", [(("uv", "uvx"), ["uvx"]), (("uv",), ["uv", "tool", "run"])])
def test_openclaw_runs_the_runtime_with_uvx_or_with_uv_alone(tmp_path, commands, runner):
    sandbox = Sandbox(tmp_path, commands)
    answer = json.dumps({"hookSpecificOutput": {"additionalContext": "notes"}})
    results = run_openclaw(sandbox, FAKE_STDOUT=answer)
    assert results == [{"appendSystemContext": "notes", "prependContext": "notes"}] * 3
    calls = sandbox.calls()
    assert calls[0] == [*runner, *RUN, "hook", "session-start", "--host", "openclaw"]
    assert {tuple(call[:len(runner)]) for call in calls} == {tuple(runner)}


def test_openclaw_says_once_per_session_that_uv_is_missing(tmp_path):
    sandbox = Sandbox(tmp_path, commands=())
    assert run_openclaw(sandbox) == [{"appendSystemContext": NO_UV}, None, {"appendSystemContext": NO_UV}]
    assert sandbox.calls() == []


def test_openclaw_says_nothing_when_uv_exists_but_the_runtime_fails(tmp_path):
    sandbox = Sandbox(tmp_path, commands=("uv",))
    assert run_openclaw(sandbox, FAKE_EXIT="2") == [None, None, None]


def load_pin_runtime():
    spec = importlib.util.spec_from_file_location("pin_runtime_under_test", ROOT / "scripts" / "pin_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pin_runtime_round_trip_rewrites_every_launcher(tmp_path, monkeypatch):
    pin_runtime = load_pin_runtime()
    assert len(pin_runtime.LAUNCHERS) == 9
    copies = {}
    for path in pin_runtime.LAUNCHERS:
        copy = tmp_path / path.relative_to(ROOT)
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(path.read_bytes())
        copies[copy] = path.read_bytes()
    monkeypatch.setattr(pin_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(pin_runtime, "LAUNCHERS", list(copies))
    monkeypatch.setattr(pin_runtime.subprocess, "run", lambda *args, **kwargs: None)  # No git: a made-up commit.
    original = requirement().split("/archive/")[1].removesuffix(".zip")
    made_up = "0123456789abcdef0123456789abcdef01234567"
    for target in (made_up, original):
        monkeypatch.setattr("sys.argv", ["pin_runtime.py", target])
        assert pin_runtime.main() == 0
        for copy, before in copies.items():
            text = copy.read_text(encoding="utf-8")
            assert len(pin_runtime.PINNED.findall(text)) == 1, copy
            assert re.findall(r"/archive/([0-9a-f]{40})\.zip", text) == [target], copy
            if target == made_up:
                assert copy.read_bytes() != before, copy
    for copy, before in copies.items():
        assert copy.read_bytes() == before, copy  # Line endings included.
    monkeypatch.setattr("sys.argv", ["pin_runtime.py", "--pypi", "0.1.0"])
    assert pin_runtime.main() == 0
    for copy in copies:
        assert pin_runtime.PINNED.findall(copy.read_text(encoding="utf-8")) == ["membrain-ai[embedded,semantic]==0.1.0"]
