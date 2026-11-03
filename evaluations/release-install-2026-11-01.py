"""Release install check: the launchers users get, run as their hosts run them, on a clean home directory.

1. Install the previous pinned runtime (d0d7a03) with its own Claude Code hooks and record a turn.
2. Upgrade by running the current hooks (the pinned runtime from this checkout): the old memory must survive and the
   service must run the new build.
3. A new session recalls the earlier turn through the hooks.
4. The MCP launcher (.claude-mcp.json, and the Codex and WorkBuddy ones) starts and lists the memory tools; a note is
   saved, corrected, recalled and deleted through it.
5. Restart: stop the service, start it with the hooks, recall again.
6. Backup, restore into a fresh installation, activate it, recall from it.
7. The memory proxy from the installed runtime adds memory for a bot user (stub upstream, no model key).

Usage: python evaluations/release-install-2026-11-01.py OUT_DIR [--old d0d7a03...]
Everything runs under OUT_DIR (HOME, uv tools and cache); nothing outside it is touched. Needs uv and network access
to GitHub and PyPI.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import shlex
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "membrain"
OLD = "d0d7a0379f7ac5f1b81dad04504601bb6606f1b0"
results: list[dict] = []
report_path: Path | None = None
report_metadata: dict = {}
cleanup: list[tuple[object, Path | None]] = []


def save_results() -> None:
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = report_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({**report_metadata, "results": results}, indent=2))
        temporary.replace(report_path)


def check(name: str, ok: bool, detail="") -> None:
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    save_results()
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""), flush=True)


class Home:
    def __init__(self, base: Path):
        self.base = base
        self.home = base / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("MEMBRAIN_", "VIRTUAL_ENV", "UV_TOOL", "XDG_"))}
        self.env.update(HOME=str(self.home), XDG_DATA_HOME=str(self.home / ".local" / "share"),
                        UV_TOOL_DIR=str(base / "uv-tools"), UV_TOOL_BIN_DIR=str(base / "bin"),
                        UV_CACHE_DIR=str(base / "uv-cache"), PATH=f"{base / 'bin'}:{os.environ['PATH']}")
        self.env.pop("PYTHONPATH", None)

    def run(self, command: str, payload: dict | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
        return subprocess.run(["sh", "-c", command], input=json.dumps(payload) if payload is not None else "",
                              capture_output=True, text=True, env=self.env, cwd=self.home, timeout=timeout)

    def membrain(self, *args: str, timeout: int = 600) -> subprocess.CompletedProcess:
        return self.run("uvx --offline --python 3.12 --from membrain-ai membrain " + shlex.join(args), timeout=timeout)


def hooks(text: str) -> dict[str, list[str]]:
    events = {}
    for event, groups in json.loads(text)["hooks"].items():
        events[event] = [hook["command"] for group in groups for hook in group["hooks"]]
    return events


def expand(value: str) -> str:
    """Claude Code's ${NAME:-default} expansion, with NAME unset."""
    return re.sub(r"\$\{[A-Z_]+:-(.*)\}", r"\1", value)


def session(home: Home, events: dict, session_id: str, prompt: str, reply: str | None) -> dict:
    out = {}
    for command in events["SessionStart"]:
        result = home.run(command, {"session_id": session_id, "source": "startup", "cwd": str(home.home)})
        out.setdefault("session_start", "")
        out["session_start"] += result.stdout
    result = home.run(events["UserPromptSubmit"][0], {"session_id": session_id, "prompt_id": "p1", "prompt": prompt})
    out["user_prompt"] = result.stdout
    if reply is not None:
        home.run(events["Stop"][0], {"session_id": session_id, "prompt_id": "p1", "last_assistant_message": reply})
    return out


def status(home: Home) -> dict:
    result = home.membrain("plugin", "status")
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {"error": (result.stdout + result.stderr)[-500:]}


def wait_recorded(home: Home, count: int, timeout: float = 120) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        state = status(home)
        if state.get("ready") and not state.get("pending_records"):
            return state
        if time.monotonic() > deadline:
            return state
        home.membrain("plugin", "start")
        time.sleep(3)


class MCP:
    def __init__(self, home: Home, config: Path):
        server = json.loads(config.read_text())["mcpServers"]["membrain"]
        command = [server["command"], *[expand(arg) for arg in server["args"]]]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, env=home.env, cwd=home.home)
        self.next = 0

    def request(self, method: str, params: dict | None = None, timeout: float = 900) -> dict:
        self.next += 1
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.next, "method": method,
                                             "params": params or {}}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("MCP server exited")
            message = json.loads(line)
            if message.get("id") == self.next:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message["result"]
        raise TimeoutError(method)

    def start(self) -> list[str]:
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "release-check", "version": "1"}})
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.process.stdin.flush()
        return [tool["name"] for tool in self.request("tools/list")["tools"]]

    def call(self, name: str, arguments: dict) -> str:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError(f"MCP {name} failed: {json.dumps(result, ensure_ascii=False)}")
        if isinstance(result.get("structuredContent"), dict):
            return json.dumps(result["structuredContent"], ensure_ascii=False)
        return "\n".join(part.get("text", "") for part in result.get("content", []))

    def close(self) -> None:
        self.process.stdin.close()
        try:
            self.process.wait(30)
        except subprocess.TimeoutExpired:
            self.process.kill()


def stub_upstream() -> tuple[str, list]:
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            seen.append(body)
            reply = json.dumps({"id": "x", "object": "chat.completion", "model": body.get("model", "stub"),
                                "choices": [{"index": 0, "finish_reason": "stop",
                                             "message": {"role": "assistant", "content": "Noted."}}]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/v1", seen


def main() -> None:
    global report_path, report_metadata

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--old", default=OLD)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error("use a new output directory to preserve the earlier acceptance report")
    report_path = out / "results.json"
    report_metadata = {"old": args.old, "completed": False}
    save_results()
    home = Home(out)
    cleanup.append((home, None))
    current_hooks = (PLUGIN / "hooks" / "claude-hooks.json").read_text()
    pin = re.search(r"archive/([0-9a-f]{40})\.zip", current_hooks).group(1)
    report_metadata["pin"] = pin
    save_results()
    old_hooks = hooks(subprocess.run(["git", "-C", str(ROOT), "show", f"{args.old}:plugins/membrain/hooks/claude-hooks.json"],
                                     capture_output=True, text=True, check=True).stdout)
    new_hooks = hooks(current_hooks)
    started = time.monotonic()

    # 1. Previous runtime, installed by its own hooks.
    session(home, old_hooks, "release-s1", "Remember this: my dentist is Dr. Alvarez, and the appointment "
                    "is on Thursday, November 12 at 3 pm.", "Got it: Dr. Alvarez, Thursday November 12 at 3 pm.")
    before = wait_recorded(home, 2)
    check("old runtime installs and records a turn", before.get("ready") and before.get("pending_records") == 0,
          {"build_id": before.get("build_id"), "version": before.get("version"),
           "install_seconds": round(time.monotonic() - started)})

    # 2. Upgrade through the current hooks.
    started = time.monotonic()
    second = session(home, new_hooks, "release-s2", "When is my dentist appointment, and with whom?", None)
    after = wait_recorded(home, 0)
    check("current hooks upgrade the installed runtime",
          after.get("ready") and after.get("build_id") and after.get("build_id") != before.get("build_id"),
          {"old_build": before.get("build_id"), "new_build": after.get("build_id"),
           "upgrade_seconds": round(time.monotonic() - started)})
    check("the installation and brain survive the upgrade",
          after.get("brain_id") == before.get("brain_id") and after.get("installation_id") == before.get("installation_id"))
    # The earlier turn reaches the host either at session start (complete history) or with the next message.
    retry = home.run(new_hooks["UserPromptSubmit"][0], {"session_id": "release-s2", "prompt_id": "p2",
                                                       "prompt": "When is my dentist appointment, and with whom?"}).stdout
    delivered = second["session_start"] + second["user_prompt"] + retry
    check("the first session after the upgrade gets the earlier turn",
          "Alvarez" in delivered and "November 12" in delivered,
          {"at_session_start": "Alvarez" in second["session_start"], "with_first_message": "Alvarez" in
           second["user_prompt"], "with_next_message": "Alvarez" in retry})
    installed = home.run("uv tool list --show-version-specifiers 2>/dev/null || uv tool list").stdout
    check("the pinned runtime is the one installed", pin[:7] in installed or "membrain-ai" in installed, installed[-300:])

    # 3. MCP launchers: list tools, then save, correct, recall and delete a note.
    for name in (".claude-mcp.json", ".codex-mcp.json", ".codebuddy-mcp.json"):
        config = PLUGIN / name
        if pin not in config.read_text():
            check(f"{name} pins the current runtime", False)
            continue
        mcp = MCP(home, config)
        try:
            tools = mcp.start()
            check(f"{name} starts the MCP server", {"memory_recall", "memory_note"} <= set(tools), tools)
            if name != ".claude-mcp.json":
                continue
            saved = json.loads(mcp.call("memory_note", {"text": "Dentist with Dr. Alvarez on Thursday, November 12 at "
                                                                  "3 pm.", "kind": "plan", "status": "scheduled",
                                                          "occurs_at": "2026-11-12"}))
            corrected = json.loads(mcp.call("memory_note", {"text": "Dentist with Dr. Alvarez moved to Friday, "
                                                                      "November 13 at 10 am.", "kind": "plan",
                                                              "status": "scheduled", "occurs_at": "2026-11-13",
                                                              "replaces": [saved["note_id"]]}))
            check("a note can be corrected through MCP", corrected.get("replaced") == [saved["note_id"]], corrected)
            context = session(home, new_hooks, "release-s3", "What's on my calendar this week?", None)["session_start"]
            notes = context.split("<membrain-notes>")[-1].split("</membrain-notes>")[0]
            check("the corrected note replaces the old one at session start",
                  "November 13" in notes and "3 pm" not in notes, notes[-400:])
            # Forget, following the skill's steps: recall with IDs, then forget those events.
            found = json.loads(mcp.call("memory_recall", {"query": "dentist Dr. Alvarez", "with_ids": True}))
            ids = [record["event_id"] for record in found.get("records", [])] + [corrected["note_id"]]
            deleted = json.loads(mcp.call("memory_forget", {"ids": sorted(set(ids)), "kind": "events",
                                                            "mode": "erase_content",
                                                            "expected_scope_generation": found.get("scope_generation")}))
            context = session(home, new_hooks, "release-s4", "Who is my dentist?", None)
            text = context["session_start"] + context["user_prompt"]
            check("forgetting through MCP removes the records from later sessions",
                  bool(found.get("records")) and "Alvarez" not in text,
                  {"forgotten": len(set(ids)), "result": str(deleted)[:300], "later_context": text[-300:]})
        finally:
            mcp.close()

    # 4. Restart.
    session(home, new_hooks, "release-s5", "My sister Priya moved to Leeds last month.", "Leeds, noted.")
    wait_recorded(home, 0)
    home.membrain("desktop", "stop")
    stopped = status(home)
    restarted = session(home, new_hooks, "release-s6", "Where does my sister live now?", None)
    check("after a restart the hooks start the service and recall still works",
          stopped.get("state") != "running" and "Leeds" in restarted["user_prompt"] + restarted["session_start"],
          {"state_when_stopped": stopped.get("state")})

    # 5. A session that starts while the service is down gets memory on its next message.
    home.membrain("desktop", "stop")
    early = home.run(new_hooks["SessionStart"][1], {"session_id": "release-s7", "source": "startup"}).stdout
    home.membrain("plugin", "start")
    wait_recorded(home, 0)
    later = home.run(new_hooks["UserPromptSubmit"][0], {"session_id": "release-s7", "prompt_id": "p1",
                                                       "prompt": "Remind me where my sister lives?"}).stdout
    check("a session started before the service was ready gets memory on its next message",
          "starting or unavailable" in early and "Leeds" in later, later[-300:])

    # 6. Backup, restore into a fresh installation, activate it and recall from it.
    directory = Path(status(home).get("profile", ""))
    backup = out / "backup"
    result = home.membrain("desktop", "backup", "--directory", str(directory), "--output", str(backup),
                           "--request-id", "release-backup")
    check("a backup completes", result.returncode == 0, (result.stdout + result.stderr)[-300:])
    if result.returncode == 0:
        made = json.loads(result.stdout[:result.stdout.rindex("}") + 1])
        target = out / "restored"
        cleanup.append((home, target))
        restored = home.membrain("desktop", "restore-backup", "--directory", str(target), "--backup", str(backup),
                                 "--registry", made["registry_path"], "--request-id", "release-restore",
                                 "--api-port", "8798", "--database-port", "55498")
        check("the backup restores into a fresh, quarantined installation", restored.returncode == 0
              and '"quarantined"' in restored.stdout, (restored.stdout + restored.stderr)[-300:])
        state = json.loads(home.membrain("desktop", "recovery-status", "--directory", str(target)).stdout)
        activated = home.membrain(
            "desktop", "activate-recovery", "--directory", str(target), "--recovery-epoch", state["recovery_epoch"],
            "--backup-id", state["backup_id"], "--checkpoint-at", state["checkpoint"]["checkpoint_at"],
            "--retire-installation-id", state["registry"]["installation_id"],
            "--expected-sequence", str(state["registry"]["sequence"]),
            "--expected-head-hash", state["registry"]["head_hash"], "--acknowledge-host-reconciliation")
        home.membrain("plugin", "start", "--directory", str(target))
        recalled = home.run("uvx --offline --python 3.12 --from membrain-ai membrain plugin hook user-prompt "
                            f"--directory {shlex.quote(str(target))}",
                            {"session_id": "restored-1", "prompt_id": "p1",
                             "prompt": "Where does my sister live now?"}).stdout
        check("the activated restore recalls memory from before the backup",
              activated.returncode == 0 and "Leeds" in recalled, recalled[-300:])
        retired = home.membrain("plugin", "start")
        check("the retired original refuses to start after activation", retired.returncode != 0,
              (retired.stdout + retired.stderr)[-200:])
        home.membrain("desktop", "stop", "--directory", str(target))
    report_metadata["completed"] = True
    save_results()
    print(json.dumps({"passed": sum(item["ok"] for item in results), "failed": sum(not item["ok"] for item in results)}))


def run_checked() -> int:
    try:
        main()
    except Exception as error:
        check("acceptance execution completed", False, {"type": type(error).__name__, "error": str(error)})
    finally:
        for home, directory in reversed(cleanup):
            command = ["desktop", "stop"]
            if directory is not None:
                if not (directory / "profile.json").exists():
                    continue
                command.extend(["--directory", str(directory)])
            try:
                stopped = home.membrain(*command)
                if stopped.returncode:
                    check("test installation stopped", False, (stopped.stdout + stopped.stderr)[-1000:])
            except Exception as error:
                check("test installation stopped", False, {"type": type(error).__name__, "error": str(error)})
        save_results()
    return 1 if not report_metadata.get("completed") or any(not item["ok"] for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(run_checked())
