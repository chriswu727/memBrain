"""Release install check: the launchers users get, run as their hosts run them, on a clean home directory.

Part "upgrade" (basic memory; the previous baseline has no Phase C API, so no companion state is written with it):
1. Install the previous pinned runtime (d0d7a03) with its own Claude Code hooks and record a turn.
2. Upgrade by running the current hooks (the pinned runtime from this checkout): the old memory must survive and the
   service must run the new build.
3. A new session recalls the earlier turn through the hooks.
4. The MCP launcher (.claude-mcp.json, and the Codex and WorkBuddy ones) starts and lists the memory tools; a note is
   saved, corrected, recalled and deleted through it.
5. Restart: stop the service, start it with the hooks, recall again.
6. Backup, restore into a fresh installation, activate it, recall from it.
7. The memory proxy from the installed runtime adds memory for a bot user (stub upstream, no model key) and records
   the reply. It runs before step 6, while the upgraded installation is still the active one.

Part "companion" (companion state across upgrade and restore), in a second fresh home:
1. Install a frozen baseline that has the Phase C layers (19e894c, by its own hooks) and record two turns.
2. Through that baseline's own MCP launcher and SDK, write a persona card with a baseline mood, a mood pin, a reported
   feeling on a note, a shared moment, a boundary with an alias and a support style; read them back.
3. Upgrade through the current hooks, then check through the candidate's API and hooks that every item is still there
   and still effective.
4. Back up, restore, activate, and check every item again in the restored installation.

Usage: python evaluations/release-install-2026-11-01.py OUT_DIR [--old d0d7a03...] [--companion-old 19e894c...]
       [--parts upgrade,companion]
Everything runs under OUT_DIR (HOME, uv tools and cache); nothing outside it is touched. Needs uv and network access
to GitHub and PyPI. No paid text-model API or subscription-backed host is used; the plugin's local embedding model
may download and run normally.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "membrain"
OLD = "d0d7a0379f7ac5f1b81dad04504601bb6606f1b0"
# main after PR #26: persona, feelings, mood and relationship, but not persona growth (P2).
COMPANION_OLD = "19e894ca9e08cf65fa071e8019789499953478d0"
PARTS = ("upgrade", "companion")
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


class StepFailed(Exception):
    """A step the rest of its part depends on failed; the failure is already recorded."""


def require(name: str, ok: bool, detail="") -> None:
    """Record a step; if it failed, stop its part (later steps would only test something that never happened)."""
    check(name, ok, detail)
    if not ok:
        raise StepFailed(name)


def run_part(name: str, function, *args) -> bool:
    """Run one part. A failure is recorded and stops only that part, so the other part still runs."""
    try:
        function(*args)
        return True
    except StepFailed as stopped:
        check("acceptance execution completed", False, {"part": name, "stopped_after": str(stopped)})
    except Exception as error:
        check("acceptance execution completed", False,
              {"part": name, "type": type(error).__name__, "error": str(error)})
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--old", default=OLD, help="The previous pin, for the basic upgrade (part 'upgrade')")
    parser.add_argument("--companion-old", default=COMPANION_OLD,
                        help="A frozen commit with the Phase C layers, for the companion upgrade (part 'companion')")
    parser.add_argument("--parts", default=",".join(PARTS), help="Comma-separated parts to run: " + ", ".join(PARTS))
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.companion_old):
        parser.error("--companion-old must be a full 40-character commit hash (a frozen baseline)")
    parts = [part.strip() for part in args.parts.split(",") if part.strip()]
    if not parts or any(part not in PARTS for part in parts) or len(set(parts)) != len(parts):
        parser.error(f"--parts must list some of: {', '.join(PARTS)}")
    args.parts = [part for part in PARTS if part in parts]
    args.parser = parser
    return args


class Home:
    def __init__(self, base: Path, cache: Path | None = None):
        self.base = base
        self.home = base / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("MEMBRAIN_", "VIRTUAL_ENV", "UV_TOOL", "XDG_"))}
        self.env.update(HOME=str(self.home), XDG_DATA_HOME=str(self.home / ".local" / "share"),
                        UV_TOOL_DIR=str(base / "uv-tools"), UV_TOOL_BIN_DIR=str(base / "bin"),
                        UV_CACHE_DIR=str(cache or base / "uv-cache"), PATH=f"{base / 'bin'}:{os.environ['PATH']}")
        self.env.pop("PYTHONPATH", None)

    def run(self, command: str, payload: dict | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
        return subprocess.run(["sh", "-c", command], input=json.dumps(payload) if payload is not None else "",
                              capture_output=True, text=True, env=self.env, cwd=self.home, timeout=timeout)

    def membrain(self, *args: str, timeout: int = 600) -> subprocess.CompletedProcess:
        return self.run("uvx --offline --python 3.12 --from membrain-ai membrain " + shlex.join(args), timeout=timeout)

    def runtime_python(self) -> Path:
        """The interpreter of the runtime the hooks installed with ``uv tool install`` (the one the service runs)."""
        return self.base / "uv-tools" / "membrain-ai" / "bin" / "python"


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


def status(home: Home, directory: Path | None = None) -> dict:
    result = home.membrain("plugin", "status", *(["--directory", str(directory)] if directory else []))
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {"error": (result.stdout + result.stderr)[-500:]}


def wait_recorded(home: Home, count: int, timeout: float = 120, directory: Path | None = None) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        state = status(home, directory)
        if state.get("ready") and not state.get("pending_records"):
            return state
        if time.monotonic() > deadline:
            return state
        home.membrain("plugin", "start", *(["--directory", str(directory)] if directory else []))
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


def stub_upstream(reply=None) -> tuple[str, list]:
    """A chat-completions upstream that answers without a model. ``reply(body, count)`` gives the reply's text."""
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            seen.append(body)
            text = reply(body, len(seen)) if reply is not None else "Noted."
            answer = json.dumps({"id": "x", "object": "chat.completion", "model": body.get("model", "stub"),
                                 "choices": [{"index": 0, "finish_reason": "stop",
                                              "message": {"role": "assistant", "content": text}}]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/v1", seen


# The installed runtime's own SDK, run by its own interpreter. Each call is a MemoryClient method on the
# installation's brain; "list_notes" and "export_user" are the module functions the hosts use, and "methods" lists
# which of the named MemoryClient methods the runtime has. A missing method is
# reported by name, so an older runtime fails with a clear message instead of a traceback.
SDK_SCRIPT = r"""
import json, sys
from pathlib import Path
request = json.load(sys.stdin)
from membrain import host
directory = host.profile_directory(Path(request["directory"]) if request.get("directory") else None)
def answer(value):
    print(json.dumps(value, default=str))
    raise SystemExit(0)
results = []
for name, args, kwargs in request["calls"]:
    if name == "wait_model_activation":
        import time
        deadline = time.monotonic() + (args[0] if args else 180)
        while True:
            state = host.installation_status(directory)
            if not host._download_marker(directory).exists() and state.get("ready"):
                results.append({"ready": True, "semantic_recall": state.get("semantic_recall")})
                break
            if time.monotonic() >= deadline:
                answer({"error": "the baseline did not finish model activation", "results": results})
            time.sleep(0.1)
        continue
    if name == "methods":
        from membrain.client import MemoryClient
        results.append([method for method in args if callable(getattr(MemoryClient, method, None))])
        continue
    if name == "export_user":
        try:
            results.append(host.export_user(directory, *args, **kwargs))
        except Exception as error:
            answer({"error": f"export_user failed: {type(error).__name__}: {error}", "results": results})
        continue
    client = host.ready_client(directory)
    if client is None:
        answer({"error": f"the service for {directory} is not ready", "results": results})
    with client:
        if name == "list_notes":
            from membrain.notes import list_notes
            method = lambda *a, **k: list_notes(client, *a, **k)
        else:
            method = getattr(client, name, None)
        if not callable(method):
            answer({"error": f"the installed runtime's SDK has no MemoryClient.{name}", "results": results})
        try:
            results.append(method(*args, **kwargs))
        except Exception as error:
            body = getattr(getattr(error, "response", None), "text", "") or ""
            answer({"error": f"{name} failed: {type(error).__name__}: {error} {body[:500]}", "results": results})
answer({"results": results})
"""


def sdk(home: Home, calls: list, directory: Path | None = None, timeout: int = 300) -> list:
    """Run SDK calls with the installed runtime; raises RuntimeError with the runtime's own message on failure."""
    python = home.runtime_python()
    if not python.exists():
        raise RuntimeError(f"no installed runtime at {python}: the hooks did not install one")
    request = {"directory": str(directory) if directory else None, "calls": calls}
    result = subprocess.run([str(python), "-I", "-c", SDK_SCRIPT], input=json.dumps(request), capture_output=True,
                            text=True, env=home.env, cwd=home.home, timeout=timeout)
    failed = RuntimeError(f"installed SDK call failed (exit {result.returncode}): "
                          f"{(result.stdout + result.stderr)[-800:]}")
    # A non-zero exit fails even when stdout already ends in a valid-looking answer: the process crashed after it.
    if result.returncode != 0:
        raise failed
    lines = result.stdout.strip().splitlines()
    try:
        answer = json.loads(lines[-1])
    except (IndexError, ValueError):
        raise failed from None
    if "error" in answer:
        raise RuntimeError(answer["error"])
    return answer["results"]


def missing(offered, needed) -> list[str]:
    return sorted(set(needed) - set(offered))


def backup_and_restore(home: Home, prefix: str, label: str, api_port: int, database_port: int):
    """Back up the active installation, restore it into a fresh one, activate and start it.

    Returns ``(target, activation)`` once the restore succeeded, or None (the failed step is recorded)."""
    directory = Path(status(home).get("profile", ""))
    backup = home.base / "backup"
    result = home.membrain("desktop", "backup", "--directory", str(directory), "--output", str(backup),
                           "--request-id", f"{label}-backup")
    check(f"{prefix}a backup completes", result.returncode == 0, (result.stdout + result.stderr)[-300:])
    if result.returncode != 0:
        return None
    made = json.loads(result.stdout[:result.stdout.rindex("}") + 1])
    target = home.base / "restored"
    cleanup.append((home, target))
    restored = home.membrain("desktop", "restore-backup", "--directory", str(target), "--backup", str(backup),
                             "--registry", made["registry_path"], "--request-id", f"{label}-restore",
                             "--api-port", str(api_port), "--database-port", str(database_port))
    check(f"{prefix}the backup restores into a fresh, quarantined installation", restored.returncode == 0
          and '"quarantined"' in restored.stdout, (restored.stdout + restored.stderr)[-300:])
    state = json.loads(home.membrain("desktop", "recovery-status", "--directory", str(target)).stdout)
    activated = home.membrain(
        "desktop", "activate-recovery", "--directory", str(target), "--recovery-epoch", state["recovery_epoch"],
        "--backup-id", state["backup_id"], "--checkpoint-at", state["checkpoint"]["checkpoint_at"],
        "--retire-installation-id", state["registry"]["installation_id"],
        "--expected-sequence", str(state["registry"]["sequence"]),
        "--expected-head-hash", state["registry"]["head_hash"], "--acknowledge-host-reconciliation")
    home.membrain("plugin", "start", "--directory", str(target))
    return target, activated


# Gap 19: the installed proxy ------------------------------------------------------------------------------------

PROXY_USER = "release-bot-user"
PROXY_FACT = "My cat is called Biscuit and she is nine years old."
PROXY_QUESTION = "What is my cat called, and how old is she?"
PROXY_REPLY = "Noted: Biscuit, nine years old (stub reply {count})."


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def chat(port: int, content: str, session_id: str) -> dict:
    body = json.dumps({"model": "stub", "user": PROXY_USER, "messages": [{"role": "user", "content": content}]})
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=body.encode(),
                                     headers={"content-type": "application/json", "x-membrain-session": session_id})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # Never through an HTTP proxy.
    with opener.open(request, timeout=300) as response:
        return json.loads(response.read())


def latest_user_text(body: dict) -> str:
    messages = [message for message in body.get("messages", []) if message.get("role") == "user"]
    content = messages[-1].get("content") if messages else ""
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content if isinstance(content, str) else ""


def proxy_findings(seen: list[dict], replies: list[dict], export: str) -> list[tuple[str, bool, object]]:
    """The proxy step's checks from what the stub received, what the bot got back and the bot user's export."""
    first = PROXY_REPLY.format(count=1)
    returned = [((reply.get("choices") or [{}])[0].get("message") or {}).get("content") for reply in replies]
    question = latest_user_text(seen[1]) if len(seen) > 1 else ""
    return [
        ("the proxy forwards chat completions to the upstream and returns its reply",
         len(seen) == 2 and returned == [first, PROXY_REPLY.format(count=2)],
         {"upstream_requests": len(seen), "replies": returned}),
        ("the proxy adds memory from an earlier recorded turn for a bot user",
         "Biscuit" in question and PROXY_QUESTION in question and question != PROXY_QUESTION,
         {"request_the_upstream_received": question[-600:]}),
        ("the proxy records the bot user's message and the upstream's reply",
         PROXY_FACT in export and first in export, {"message_recorded": PROXY_FACT in export,
                                                    "reply_recorded": first in export}),
    ]


def proxy_step(home: Home) -> None:
    upstream, seen = stub_upstream(lambda body, count: PROXY_REPLY.format(count=count))
    port = free_port()
    log = home.base / "proxy.log"
    command = ["uvx", "--offline", "--python", "3.12", "--from", "membrain-ai", "membrain", "proxy",
               "--upstream", upstream, "--port", str(port)]
    with log.open("w") as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                   env=home.env, cwd=home.home, start_new_session=True)
    try:
        deadline, listening = time.monotonic() + 180, False
        while time.monotonic() < deadline and process.poll() is None and not listening:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                listening = True
            except OSError:
                time.sleep(1)
        require("the installed proxy starts against a stub upstream with no model key", listening,
                {"exit_code": process.poll(), "log": log.read_text()[-800:]} if not listening else {"port": port})
        replies = [chat(port, PROXY_FACT, "release-proxy-1")]
        wait_recorded(home, 0)
        replies.append(chat(port, PROXY_QUESTION, "release-proxy-2"))
        wait_recorded(home, 0)
        export = json.dumps(sdk(home, [["export_user", ["api:" + PROXY_USER], {}]])[0], ensure_ascii=False)
        for name, ok, detail in proxy_findings(seen, replies, export):
            check(name, ok, detail)
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(30)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


# Part "upgrade" -------------------------------------------------------------------------------------------------

def upgrade_part(out: Path, old: str, pin: str, current_hooks: str) -> None:
    home = Home(out)
    cleanup.append((home, None))
    old_hooks = hooks(subprocess.run(["git", "-C", str(ROOT), "show", f"{old}:plugins/membrain/hooks/claude-hooks.json"],
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

    # 7. The installed proxy, while this installation is still the active one (a failure here is recorded and the
    # backup steps still run).
    try:
        proxy_step(home)
    except StepFailed:
        pass
    except Exception as error:
        check("the proxy step ran to the end", False, {"type": type(error).__name__, "error": str(error)})

    # 6. Backup, restore into a fresh installation, activate it and recall from it.
    restored = backup_and_restore(home, "", "release", 8798, 55498)
    if restored is not None:
        target, activated = restored
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


# Part "companion" (gap 16) --------------------------------------------------------------------------------------

COMPANION = {
    "persona": {"name": "Wren", "traits": ["curious", "steady"], "voice": {"register": "warm", "length": "short"},
                "values": ["Honesty over flattery"], "baseline_mood": {"label": "cheerful", "valence": 1, "energy": 2}},
    "feeling": {"text": "Job interview at Northwind Labs next Monday.", "kind": "plan", "status": "scheduled",
                "affect": {"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported",
                           "topic": "job interview"}},
    "moment": {"text": "Our first conversation: we planned the Lisbon trip together.", "kind": "milestone",
               "shared": True},
    "boundary": {"topic": "my ex", "aliases": ["Jordan"]},
    "support_style": "Listen first; give advice only when asked.",
    # Recorded through the baseline's hooks. The first is about the boundary topic (by its alias); the second is not.
    "turns": [("companion-s1", "I used to go hiking at Lake Tahoe with Jordan every summer.", "Noted."),
              ("companion-s2", "Last weekend I went hiking at Mount Rainier with my brother Sam.", "Noted.")],
    "unraised": "Where have I gone hiking?", "raised": "Where did I go hiking with Jordan?",
    "kept_out": "Tahoe", "control": "Rainier",
}
COMPANION_TOOLS = ("memory_note", "memory_boundary")
COMPANION_SDK = ("set_persona", "persona", "pin_mood", "mood", "set_support_style", "relationship", "affect_records")
COMPANION_READS = ("persona", "affect_records", "list_notes", "relationship", "mood")


def companion_findings(written: dict, seen: dict) -> list[tuple[str, bool, object]]:
    """Whether each item written on the baseline is still there and still effective, from what the API returned
    (``persona``, ``affect``, ``notes``, ``relationship``, ``mood``) and what the hooks delivered (``session_start``,
    and the recall for a message that does not raise the boundary topic, ``unraised``, and one that does,
    ``raised``)."""
    persona, relationship, mood = seen["persona"], seen["relationship"], seen["mood"]
    context = seen["session_start"]
    version, baseline = written["persona_version"], written["baseline_mood"]
    feelings = [record for record in seen["affect"].get("records") or []
                if record.get("note_id") == written["feeling_note_id"] and record.get("label") == written["feeling"]
                and record.get("basis") == "reported"]
    note_ids = {item.get("event_id") for item in seen["notes"].get("items") or []}
    boundaries = [boundary for boundary in relationship.get("boundaries") or []
                  if boundary.get("topic") == written["boundary_topic"]
                  and set(written["boundary_aliases"]) <= set(boundary.get("aliases") or [])]
    moments = [moment for moment in relationship.get("shared_moments") or []
               if moment.get("id") == written["moment_note_id"] and written["moment_text"] in (moment.get("text") or "")]
    support = (relationship.get("support_style") or {}).get("text")
    unraised, raised = seen["unraised"], seen["raised"]
    return [
        ("the persona block is in session context with its version",
         persona.get("version") == version and (persona.get("card") or {}).get("name") == written["persona_name"]
         and f'<membrain-persona version="{version}">' in context and f"Name: {written['persona_name']}" in context
         and f"Baseline mood: {baseline}" in context,
         {"written_version": version, "current_version": persona.get("version"),
          "in_session_context": f'<membrain-persona version="{version}">' in context}),
        ("the feeling is listed with its note",
         bool(feelings) and written["feeling_note_id"] in note_ids
         and f"the user said they felt {written['feeling']}" in context,
         {"records": feelings[:1], "note_listed": written["feeling_note_id"] in note_ids,
          "on_the_note_at_session_start": f"the user said they felt {written['feeling']}" in context}),
        ("the boundary keeps its topic out of recall until the user raises it",
         bool(boundaries) and written["kept_out"] not in unraised and written["control"] in unraised
         and written["kept_out"] in raised,
         {"boundary": boundaries[:1], "topic_record_without_raising": written["kept_out"] in unraised,
          "other_record_recalled": written["control"] in unraised,
          "topic_record_when_raised": written["kept_out"] in raised}),
        ("the shared moment is in the relationship",
         bool(moments) and written["moment_text"] in context,
         {"moments": moments[:1], "in_session_context": written["moment_text"] in context}),
        ("the mood is still pinned at the persona's baseline",
         mood.get("pinned") is True and mood.get("label") == baseline and (mood.get("baseline") or {}).get("label")
         == baseline,
         {key: mood.get(key) for key in ("label", "pinned", "pinned_at", "baseline", "at_baseline")}),
        ("the support style is kept",
         support == written["support_style"]
         and f"How they like to be supported: {written['support_style']}" in context,
         {"support_style": support,
          "in_session_context": f"How they like to be supported: {written['support_style']}" in context}),
    ]


def delivered(output: str) -> str:
    """The context a hook hands the host: its JSON ``additionalContext`` decoded (so quotes and newlines read as
    the host sees them), or the output itself when it is plain text."""
    try:
        return json.loads(output)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError, TypeError):
        return output


def companion_context(home: Home, events: dict, directory: Path | None, tag: str) -> dict:
    """What the hooks deliver: through the launchers' own commands, or with ``--directory`` for a restored copy."""
    def hook(event: str, payload: dict) -> str:
        if directory is None:
            index = {"session-start": 1, "user-prompt": 0}[event]
            command = events["SessionStart" if event == "session-start" else "UserPromptSubmit"][index]
        else:
            command = ("uvx --offline --python 3.12 --from membrain-ai membrain plugin hook "
                       f"{event} --directory {shlex.quote(str(directory))}")
        return delivered(home.run(command, payload).stdout)

    def start(session_id: str) -> str:
        return hook("session-start", {"session_id": session_id, "source": "startup", "cwd": str(home.home)})

    def ask(session_id: str, prompt: str) -> str:
        return hook("user-prompt", {"session_id": session_id, "prompt_id": "p1", "prompt": prompt})

    context = start(f"{tag}-context")
    unraised = start(f"{tag}-unraised") + ask(f"{tag}-unraised", COMPANION["unraised"])
    raised = ask(f"{tag}-raised", COMPANION["raised"])
    return {"session_start": context, "unraised": unraised, "raised": raised}


def observe_companion(home: Home, events: dict, directory: Path | None, tag: str) -> dict:
    answers = sdk(home, [[name, [], {}] for name in COMPANION_READS], directory)
    seen = dict(zip(("persona", "affect", "notes", "relationship", "mood"), answers))
    return {**seen, **companion_context(home, events, directory, tag)}


def companion_checks(home: Home, events: dict, written: dict, directory: Path | None, phase: str) -> None:
    try:
        seen = observe_companion(home, events, directory, phase.replace(" ", "-"))
    except Exception as error:
        check(f"{phase}: the candidate's API answers", False, {"type": type(error).__name__, "error": str(error)})
        return
    for name, ok, detail in companion_findings(written, seen):
        check(f"{phase}: {name}", ok, detail)


def companion_part(out: Path, baseline: str, current_hooks: str) -> None:
    home = Home(out / "companion", cache=out / "uv-cache")  # A fresh home; only the download cache is shared.
    cleanup.append((home, None))
    short = baseline[:7]
    prefix = "companion: "
    try:
        files = {name: subprocess.run(["git", "-C", str(ROOT), "show", f"{baseline}:plugins/membrain/{name}"],
                                      capture_output=True, text=True, check=True).stdout
                 for name in ("hooks/claude-hooks.json", ".claude-mcp.json")}
        old_hooks = hooks(files["hooks/claude-hooks.json"])
        runtime = re.search(r"archive/([0-9a-f]{40})\.zip", files["hooks/claude-hooks.json"]).group(1)
    except (subprocess.CalledProcessError, AttributeError, KeyError, ValueError) as error:
        require(f"{prefix}baseline {short} launchers are readable from this checkout", False,
                f"{type(error).__name__}: {getattr(error, 'stderr', '') or error} (fetch the commit first)")
    report_metadata["companion_runtime"] = runtime
    save_results()
    new_hooks = hooks(current_hooks)

    # 1. The baseline, installed by its own hooks, records two turns.
    started = time.monotonic()
    for session_id, prompt, reply in COMPANION["turns"]:
        session(home, old_hooks, session_id, prompt, reply)
    # The frozen baseline restarts after its asynchronous model download; wait before writing its fixtures.
    activation = sdk(home, [["wait_model_activation", [], {}]])[0]
    before = wait_recorded(home, 0)
    require(f"{prefix}baseline {short} installs through its own hooks and records turns",
            before.get("ready") and before.get("pending_records") == 0 and home.runtime_python().exists(),
            {"build_id": before.get("build_id"), "runtime": runtime, "model_activation": activation,
             "install_seconds": round(time.monotonic() - started),
             "error": before.get("error")})

    # 2. Write the companion state through the baseline's own MCP launcher and SDK; never with the candidate.
    config = home.base / "baseline-mcp" / ".claude-mcp.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(files[".claude-mcp.json"])
    written: dict = {"baseline": baseline, "runtime": runtime}
    mcp = MCP(home, config)
    try:
        tools = mcp.start()
        require(f"{prefix}the baseline's MCP launcher offers the note and boundary tools",
                not missing(tools, COMPANION_TOOLS), {"missing": missing(tools, COMPANION_TOOLS), "tools": tools})
        offered = sdk(home, [["methods", list(COMPANION_SDK), {}]])[0]
        require(f"{prefix}the baseline's SDK offers the persona, mood and relationship calls",
                not missing(offered, COMPANION_SDK), {"missing": missing(offered, COMPANION_SDK)})
        persona = sdk(home, [["set_persona", [COMPANION["persona"]], {"made_by": "user", "reason": "release check"}]])[0]
        written.update(persona_version=persona.get("version"), persona_name=COMPANION["persona"]["name"],
                       baseline_mood=COMPANION["persona"]["baseline_mood"]["label"])
        require(f"{prefix}a persona card with a baseline mood is written on the baseline",
                isinstance(persona.get("version"), int) and persona["version"] >= 1, {"version": persona.get("version")})
        pinned = sdk(home, [["pin_mood", [True], {}]])[0]
        require(f"{prefix}the mood is pinned on the baseline", pinned.get("pinned") is True,
                {key: pinned.get(key) for key in ("label", "pinned")})
        feeling = json.loads(mcp.call("memory_note", COMPANION["feeling"]))
        written.update(feeling_note_id=feeling.get("note_id"), feeling=COMPANION["feeling"]["affect"]["label"])
        require(f"{prefix}a reported feeling on a note is written on the baseline", bool(feeling.get("note_id")), feeling)
        moment = json.loads(mcp.call("memory_note", COMPANION["moment"]))
        written.update(moment_note_id=moment.get("note_id"), moment_text=COMPANION["moment"]["text"])
        require(f"{prefix}a shared moment is written on the baseline", bool(moment.get("note_id")), moment)
        boundary = json.loads(mcp.call("memory_boundary", COMPANION["boundary"]))
        written.update(boundary_topic=COMPANION["boundary"]["topic"], boundary_aliases=COMPANION["boundary"]["aliases"],
                       kept_out=COMPANION["kept_out"], control=COMPANION["control"])
        require(f"{prefix}a boundary with an alias is written on the baseline",
                any(item.get("topic") == COMPANION["boundary"]["topic"] for item in boundary.get("boundaries") or []),
                boundary)
    finally:
        mcp.close()
    support = sdk(home, [["set_support_style", [COMPANION["support_style"]], {}]])[0]
    written["support_style"] = COMPANION["support_style"]
    require(f"{prefix}a support style is written on the baseline",
            (support.get("support_style") or {}).get("text") == COMPANION["support_style"]
            or support.get("text") == COMPANION["support_style"], support)
    report_metadata["companion_written"] = written
    save_results()
    wait_recorded(home, 0)
    # Read back through the baseline itself, so a later failure cannot be a write that never landed.
    persona, affect, notes, relationship, mood = sdk(home, [[name, [], {}] for name in COMPANION_READS])
    require(f"{prefix}the baseline reads back everything written",
            persona.get("version") == written["persona_version"]
            and any(record.get("note_id") == written["feeling_note_id"] for record in affect.get("records") or [])
            and any(moment.get("id") == written["moment_note_id"] for moment in relationship.get("shared_moments") or [])
            and any(item.get("topic") == written["boundary_topic"] for item in relationship.get("boundaries") or [])
            and (relationship.get("support_style") or {}).get("text") == written["support_style"]
            and mood.get("pinned") is True and mood.get("label") == written["baseline_mood"],
            {"persona_version": persona.get("version"), "feelings": len(affect.get("records") or []),
             "shared_moments": len(relationship.get("shared_moments") or []),
             "boundaries": len(relationship.get("boundaries") or []),
             "support_style": (relationship.get("support_style") or {}).get("text"),
             "mood": {key: mood.get(key) for key in ("label", "pinned")}})

    # 3. Upgrade through the current hooks, then check every item through the candidate.
    started = time.monotonic()
    session(home, new_hooks, "companion-upgrade", "Hello again.", None)
    after = wait_recorded(home, 0)
    require(f"{prefix}current hooks upgrade the baseline runtime",
            after.get("ready") and after.get("build_id") and after.get("build_id") != before.get("build_id")
            and after.get("brain_id") == before.get("brain_id")
            and after.get("installation_id") == before.get("installation_id"),
            {"old_build": before.get("build_id"), "new_build": after.get("build_id"),
             "upgrade_seconds": round(time.monotonic() - started)})
    companion_checks(home, new_hooks, written, None, "companion after upgrade")

    # 4. Back up, restore, activate, and check every item in the restored installation.
    restored = backup_and_restore(home, prefix, "companion", 8799, 55499)
    require(f"{prefix}the backup restores", restored is not None)
    target, activated = restored
    require(f"{prefix}the restored installation activates", activated.returncode == 0,
            (activated.stdout + activated.stderr)[-300:])
    state = wait_recorded(home, 0, directory=target)
    require(f"{prefix}the restored installation is ready", state.get("ready"), {"state": state.get("state"),
                                                                                 "error": state.get("error")})
    companion_checks(home, new_hooks, written, target, "companion after restore")
    home.membrain("desktop", "stop", "--directory", str(target))


def main() -> None:
    global report_path, report_metadata

    args = parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        args.parser.error("use a new output directory to preserve the earlier acceptance report")
    report_path = out / "results.json"
    report_metadata = {"old": args.old, "companion_old": args.companion_old, "parts": args.parts, "completed": False}
    save_results()
    current_hooks = (PLUGIN / "hooks" / "claude-hooks.json").read_text()
    pin = re.search(r"archive/([0-9a-f]{40})\.zip", current_hooks).group(1)
    report_metadata["pin"] = pin
    save_results()
    finished = []
    if "upgrade" in args.parts:
        finished.append(run_part("upgrade", upgrade_part, out, args.old, pin, current_hooks))
    if "companion" in args.parts:
        finished.append(run_part("companion", companion_part, out, args.companion_old, current_hooks))
    report_metadata["completed"] = all(finished)
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
