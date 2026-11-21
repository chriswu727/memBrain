"""A new user's first minutes: hooks and the tool server while memory is still starting, through the host entry points
(``membrain plugin hook ...`` and ``membrain plugin mcp`` in their own processes, as a host runs them) on a real local
installation.

A first start holds the profile for 10 to 30 seconds while it prepares the database. Here another process holds the
same locks that preparation holds, so the hooks and the tool server meet exactly what they meet then. The background
start a hook asks for is held off (``last-start-attempt``), so no service starts behind a test's back.
"""
from __future__ import annotations

import datetime
import json
import os
import select
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, host, host_recording, plugin
from membrain.local_profile import ensure_profile, load_profile

STARTING = "memBrain is starting, so nothing can be recalled yet; new messages are queued for memory meanwhile."
TOOL_STARTING = {"error": "memBrain is still starting; try again in a moment."}
HOLD = """
import sys
from pathlib import Path
from membrain.local_profile import profile_lock
directory = Path(sys.argv[1])
with profile_lock(directory / "lifecycle", timeout=5), profile_lock(directory, timeout=5):
    print("held", flush=True)
    sys.stdin.read()
"""


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def environment():
    return {**os.environ, "MEMBRAIN_SEMANTIC": "0", "PYTHONDONTWRITEBYTECODE": "1"}


class Holder:
    """Another process holding the profile as a first start's database preparation does."""

    def __init__(self, directory: Path):
        self.process = subprocess.Popen([sys.executable, "-c", HOLD, str(directory)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, text=True, env=environment())
        assert self.process.stdout.readline().strip() == "held"

    def release(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=30)


def hook(directory: Path, event: str, payload: dict) -> tuple[float, dict | None]:
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-m", "membrain.cli", "plugin", "hook", event, "--directory",
                             str(directory)], input=json.dumps(payload), capture_output=True, text=True, timeout=60,
                            env=environment())
    assert result.returncode == 0, result.stderr
    return time.monotonic() - started, json.loads(result.stdout) if result.stdout else None


def context(output: dict | None) -> str | None:
    return (output or {}).get("hookSpecificOutput", {}).get("additionalContext")


def hold_off_background_starts(directory: Path):
    """``host.start_in_background`` starts at most once a minute: a fresh attempt marker keeps it from starting."""
    marker = host.state_directory(directory) / "last-start-attempt"
    marker.touch()
    os.utime(marker, (time.time() + 600, time.time() + 600))


def a_new_installation(tmp_path: Path) -> Path:
    if not embedded_database.available():
        pytest.fail("the embedded PostgreSQL binaries are required")
    directory = tmp_path / "brain"
    ensure_profile(directory, database_engine=embedded_database.default_engine())
    return directory


def recorded(directory: Path, word: str, timeout: float = 60) -> bool:
    """Whether recall finds ``word``, allowing the service a moment to index what it just received."""
    deadline = time.monotonic() + timeout
    while True:
        with host.ready_client(directory) as client:
            if word in (host.recall_context(client, word, deliberate=True, notes=True) or ""):
                return True
        if time.monotonic() > deadline:
            return False
        time.sleep(1)


class Foreign:
    """Another program listening on a port: it answers every connection with 404."""

    def __init__(self, port: int):
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", port))
        self.server.listen(16)
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            with connection:
                try:
                    connection.settimeout(2)
                    connection.recv(65536)
                    connection.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                except OSError:
                    pass

    def close(self):
        self.server.close()


def test_hooks_queue_a_message_at_once_while_a_first_start_holds_the_profile(tmp_path):
    directory = a_new_installation(tmp_path)
    hold_off_background_starts(directory)
    holder = Holder(directory)
    try:
        seconds, output = hook(directory, "session-start", {"session_id": "s1"})
        assert seconds < 6 and "memBrain is starting or unavailable" in context(output)
        assert context(output).endswith(STARTING)
        payload = {"session_id": "s1", "prompt_id": "p1", "prompt": "My dog is called Biscuit."}
        seconds, output = hook(directory, "user-prompt", payload)
        assert seconds < 6 and context(output) == STARTING  # Not stopped by the host at 15 seconds.
        seconds, output = hook(directory, "stop", {**payload, "last_assistant_message": "Noted: Biscuit."})
        assert seconds < 6 and output is None
        spooled = [json.loads(line) for line in (directory / "plugin" / "spool.jsonl").read_text().splitlines()]
        assert [(record["role"], record["text"]) for record in spooled] == [
            ("user", "My dog is called Biscuit."), ("assistant", "Noted: Biscuit.")]
    finally:
        holder.release()
    try:
        host.start(directory)  # The queued exchange is recorded once the service runs.
        assert recorded(directory, "Biscuit")
        assert not (directory / "plugin" / "spool.jsonl").read_text().strip()
    finally:
        desktop.stop(directory)


class Mcp:
    """``membrain plugin mcp`` as a host starts it, spoken to over standard input and output."""

    def __init__(self, directory: Path):
        self.process = subprocess.Popen([sys.executable, "-m", "membrain.cli", "plugin", "mcp", "--directory",
                                         str(directory)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, env=environment())
        self.buffer, self.ident = b"", 0

    def request(self, method: str, params: dict, timeout: float = 60) -> dict:
        self.ident += 1
        self.process.stdin.write((json.dumps({"jsonrpc": "2.0", "id": self.ident, "method": method,
                                              "params": params}) + "\n").encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            while b"\n" not in self.buffer:
                remaining = deadline - time.monotonic()
                ready, _, _ = select.select([self.process.stdout], [], [], max(0, remaining))
                assert ready, f"no answer to {method} within {timeout} s"
                chunk = os.read(self.process.stdout.fileno(), 65536)
                assert chunk, f"the tool server exited ({self.process.poll()})"
                self.buffer += chunk
            line, self.buffer = self.buffer.split(b"\n", 1)
            message = json.loads(line)
            if message.get("id") == self.ident:
                return message

    def initialize(self) -> float:
        started = time.monotonic()
        response = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                               "clientInfo": {"name": "test", "version": "0"}}, timeout=30)
        assert "instructions" in response["result"]
        self.process.stdin.write(b'{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        self.process.stdin.flush()
        return time.monotonic() - started

    def recall(self, query: str) -> dict:
        response = self.request("tools/call", {"name": "memory_recall", "arguments": {"query": query}}, timeout=120)
        return json.loads(response["result"]["content"][0]["text"])

    def until_working(self, query: str, timeout: float = 240) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.recall(query)
            if "error" not in result:
                return result
            time.sleep(1)
        pytest.fail(f"the tools never worked: {result}")

    def close(self) -> int:
        self.process.stdin.close()
        return self.process.wait(timeout=60)


def test_the_tool_server_answers_at_once_and_works_once_a_busy_first_start_ends(tmp_path):
    directory = a_new_installation(tmp_path)
    hold_off_background_starts(directory)
    holder = Holder(directory)
    mcp = Mcp(directory)
    try:
        assert mcp.initialize() < 20  # Before: no answer until the start finished, or a crash at 30 seconds.
        tools = mcp.request("tools/list", {})["result"]["tools"]
        assert len(tools) == 9  # The plugin's nine (the low-level contract tools are not offered to plugin hosts).
        assert mcp.recall("Biscuit") == TOOL_STARTING
        time.sleep(35)  # Longer than any profile wait: the server does not give up.
        assert mcp.process.poll() is None and mcp.recall("Biscuit") == TOOL_STARTING
        holder.release()
        assert mcp.until_working("Biscuit") == {"context": "No matching records."}
        assert mcp.process.poll() is None
    finally:
        holder.release()
        assert mcp.close() == 0
        desktop.stop(directory)


def test_the_tool_server_names_a_taken_port_and_keeps_running_until_it_is_free(tmp_path):
    directory = a_new_installation(tmp_path)
    port = load_profile(directory).api_port
    listener = Foreign(port)
    mcp = Mcp(directory)
    try:
        assert mcp.initialize() < 20
        expected = {"error": f"memBrain cannot start: another program is using port {port}, which it needs. "
                             "Ask the user to close that program, then try again."}
        deadline = time.monotonic() + 60
        while (answer := mcp.recall("anything")) != expected and time.monotonic() < deadline:
            time.sleep(1)
        assert answer == expected and mcp.process.poll() is None
        # The hooks name it too, with each message.
        payload = {"session_id": "s1", "prompt_id": "p1", "prompt": "Note: the word is lighthouse."}
        hold_off_background_starts(directory)
        _, output = hook(directory, "user-prompt", payload)
        assert context(output) == (f"memBrain cannot start: another program is using port {port}, which it "
                                   "needs. New messages are queued, but nothing can be recalled until that program "
                                   "is closed; tell the user once.")
        listener.close()
        assert mcp.until_working("anything") == {"context": "No matching records."}
    finally:
        listener.close()
        assert mcp.close() == 0
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_two_starts_after_an_update_restart_the_service_once(tmp_path, monkeypatch):
    """The session's own start and a tool server's start arrive together after an update: only the first restarts;
    the second finds the new service ready (before, each restarted it: two restarts within 9 seconds)."""
    directory = tmp_path / "brain"
    state = {"current": False}
    calls = []

    def status(path):
        return {"state": "ready" if state["current"] else "restart_required", "ready": state["current"]}

    def restart(path):
        calls.append("restart")
        time.sleep(0.5)
        state["current"] = True
        return {"state": "ready", "ready": True}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(desktop, "status", status)
    monkeypatch.setattr(desktop, "restart", restart)
    monkeypatch.setattr(desktop, "start", lambda path: calls.append("start") or {"state": "ready", "ready": True})
    monkeypatch.setattr("membrain.desktop_connection.open_client", lambda *args, **kwargs: Client())
    monkeypatch.setattr(host, "flush", lambda client, path: 0)
    monkeypatch.setattr(host_recording, "control_status", lambda path: {})
    threads = [threading.Thread(target=host.start, args=(directory,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert calls == ["restart", "start"]


def transcript(path: Path, *messages: tuple[str, str, float]):
    with open(path, "w", encoding="utf-8") as stream:
        for role, text, when in messages:
            stamp = datetime.datetime.fromtimestamp(when, datetime.UTC).isoformat().replace("+00:00", "Z")
            stream.write(json.dumps({"type": role, "message": {"role": role, "content": text},
                                     "timestamp": stamp}) + "\n")


def test_earlier_messages_memory_never_saw_are_counted_from_the_transcript(tmp_path):
    now = time.time()
    path = tmp_path / "s1.jsonl"
    transcript(path, ("user", "A message from three weeks ago.", now - 21 * 86400),
               ("assistant", "A reply.", now - 21 * 86400),
               ("user", "Hi, my dog is called Biscuit.", now - 120), ("assistant", "Hello!", now - 118),
               ("user", "<command-name>/clear</command-name>", now - 100),
               ("user", "[Request interrupted by user]", now - 90),
               ("user", "Note for later: marmalade.", now - 60), ("assistant", "Noted.", now - 58),
               ("user", "And trombone.", now - 1))
    payload = {"session_id": "s1", "transcript_path": str(path), "prompt": "And trombone."}
    # The current message is the last one when the host wrote it already; older than a session's state is kept, a
    # message may have been seen, so it is not counted; commands and interruptions are not messages.
    assert plugin.unkept_messages(payload, tmp_path, "s1") == 2
    assert plugin.unkept_messages({**payload, "prompt": "Something new."}, tmp_path, "s1") == 3
    assert plugin.unkept_messages({**payload, "transcript_path": str(tmp_path / "none.jsonl")}, tmp_path, "s1") == 0
    # A stop hook that found nothing staged (the message came before the runtime could run) leaves state behind,
    # and so does a session start that reached the runtime; neither means a message of this conversation was kept.
    host._mark_history(tmp_path, "s1", False)
    plugin.stop({"session_id": "s1", "prompt_id": "p0", "last_assistant_message": "Hello!"}, tmp_path)
    assert host.session_state(tmp_path, "s1") and plugin.unkept_messages(payload, tmp_path, "s1") == 2
    host._stage(tmp_path, "s1", host.message_record("s1", "user", "And trombone.", turn_id="p5"), "And trombone.")
    assert plugin.unkept_messages(payload, tmp_path, "s1") == 0  # From its first staged message on, it saw them.


def test_the_first_message_memory_sees_says_once_that_earlier_ones_were_not_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda directory: None)
    path = tmp_path / "s1.jsonl"
    now = time.time()
    transcript(path, ("user", "Hi, my dog is called Biscuit.", now - 120), ("assistant", "Hello!", now - 118),
               ("user", "Note for later: marmalade.", now - 60), ("assistant", "Noted.", now - 58))
    payload = {"session_id": "s1", "prompt_id": "p3", "transcript_path": str(path), "prompt": "And trombone."}
    first = plugin.user_prompt(payload, tmp_path)
    unkept = ("memBrain was not running yet for this conversation's 2 earlier messages, so they were not kept; "
              "tell the user if it matters.")
    assert first == STARTING + " " + unkept
    assert plugin.user_prompt({**payload, "prompt_id": "p4", "prompt": "And cobalt."}, tmp_path) == STARTING
    assert host.unkept_notice(1) == ("memBrain was not running yet for this conversation's earlier message, so it "
                                     "was not kept; tell the user if it matters.")
    assert host.unkept_notice(0) == ""


def test_what_the_host_is_told_while_memory_starts_is_short_and_names_the_cause():
    unknown = {"paused": False, "revision": 0, "target": None, "availability": "unknown"}
    assert host_recording.notice(unknown, {"cause": "starting"}) == STARTING
    assert host_recording.notice(unknown, {"cause": "restarting"}) == (
        "memBrain is restarting after an update, so nothing can be recalled yet; new messages are queued for memory "
        "meanwhile.")
    assert "port 58461" in host_recording.notice(unknown, {"cause": "port_conflict", "port": 58461})
    assert host_recording.notice(unknown) == ("memBrain cannot confirm its recording state right now; new messages "
                                              "may be queued for memory.")
    for cause in ({"cause": "starting"}, {"cause": "restarting"}, {"cause": "port_conflict", "port": 58461}, None):
        assert len(host_recording.notice(unknown, cause)) < 192  # The line it replaces had 192 characters.
    # A pause that may still hold keeps its fail-closed words; a known state says nothing.
    assert "Local capture remains blocked" in host_recording.notice({**unknown, "paused": True}, {"cause": "starting"})
    assert host_recording.notice({**unknown, "availability": "current"}, {"cause": "starting"}) == ""
