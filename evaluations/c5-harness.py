"""C5 (Phase C companion) harness: plugin path (P), proxy with note extraction (E) and whole history (F).

Built on the Phase B harness (v1-2026-10-29-phase-b-harness.py), with what companion scenarios need:
- **Scenario clock.** P and E run on a disposable evaluation profile whose local service reads the scenario clock
  (src/membrain/evaluation_clock.py): every session states its date and time ("Today is Tuesday, March 3, 21:00"),
  and the clock is set to it before the session starts, so events are recorded, the mood decays and familiarity
  counts days on the scenario's timeline. The clock runs in UTC (TZ=UTC for the harness and the service) and never
  moves backwards. F has no service and needs no clock.
- **Persona.** A scenario's PERSONA card is set by the host at the start of P and E (made_by "host", as the host's
  default). F gets the same card as the `<membrain-persona>` block in its system prompt, rendered by the product's own
  renderer, and every page action that changes the card changes F's block the same way.
- **Tools.** P offers memory_recall, memory_note (with its `affect` and `shared` fields), memory_boundary,
  memory_pause and memory_resume, with the plugin's own schemas and descriptions. E has no tools (the proxy).
- **Page actions.** PAGE_ACTIONS = [(session, before_turn, action), ...] are the user's actions on the memory page,
  applied before that turn through the public API (the MemoryClient SDK, the same routes the page calls), in P and
  E, logged to run.log and page-actions.jsonl with what each one removed. An action may name "arms" ("P", "E") to
  apply to only some arms (for example a boundary that P sets by tool and the proxy user sets on the page).
- **Reference world.** F's earlier history drops a message only when a page action deletes that message (the product
  erases it); resets, cleared feelings, deleted feelings and notes, and mood or persona actions never delete the
  conversation, so they never change F's history. Within the session in progress every arm keeps its own
  transcript, as a host app does.
- **Dry run.** `C5_STUB=1` replaces the host model and the extraction model with deterministic local stubs (an
  httpx MockTransport answering from the scenario's STUB_HOST and STUB_EXTRACT scripts) and refuses every
  non-loopback connection, so the whole run makes no network call. Only practice scenarios carry stub scripts.

Usage: MEMBRAIN_MODEL_CACHE=... MEMBRAIN_PORTS=api,db python c5-harness.py ARM SCENARIO_FILE OUT_DIR
A run directory is never resumed: existing results are refused.
"""
import asyncio
import datetime
import importlib.util
import json
import logging
import os
import re
import signal
import socket
import sys
import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import httpx

SOURCE = Path(os.environ.get("MEMBRAIN_SRC", Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(SOURCE))

BASE_URL, MODEL = "https://api.deepseek.com", os.environ.get("HOST_MODEL", "deepseek-v4-pro")
YEAR = 2026
STUB = os.environ.get("C5_STUB") == "1"
TOOLS = ("memory_recall", "memory_note", "memory_boundary", "memory_pause", "memory_resume")
PROXY_USER = ("api", "person")  # The proxy's speaker: E's memory is this person's brain.
MONTHS = {name: number for number, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
     "december"], 1)}
MESES = {name: number for number, name in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
     "diciembre"], 1)}
MONATE = {name: number for number, name in enumerate(
    ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november",
     "dezember"], 1)}
# What each page action is allowed to remove. Only these delete conversation messages, so only these change F.
DELETES_MESSAGES = {"delete_message"}
PERSONA_ACTIONS = {"set_persona", "restore_persona", "reset_persona", "delete_persona_history",
                   "accept_persona_proposal"}
ACTIONS = PERSONA_ACTIONS | DELETES_MESSAGES | {
    "reject_persona_proposal", "add_boundary", "remove_boundary", "clear_feelings", "delete_feeling", "delete_note",
    "reset_relationship", "reset_mood", "pin_mood"}
PROPOSAL_ACTIONS = {"accept_persona_proposal", "reject_persona_proposal"}
STARTED: list[Path] = []  # Installations this process started, stopped on the way out even after an error.
BILLING = None
logging.getLogger("httpx").setLevel(logging.WARNING)  # Per-request lines would bury the run log.


def billing_transport(*, allow_stopped=False):
    path = os.environ.get("C5_BILLING_LEDGER")
    if not path:
        raise SystemExit("A live evaluation needs the approved run's shared C5_BILLING_LEDGER.")
    ident, policy = os.environ.get("C5_ATTEMPT_ID"), os.environ.get("C5_BILLING_POLICY_SHA256")
    if not ident or not policy:
        raise SystemExit("A live evaluation needs its frozen C5_ATTEMPT_ID and C5_BILLING_POLICY_SHA256.")
    return billing_module().GuardedTransport(Path(path), run_id=ident, policy_sha256=policy,
                                            allow_stopped=allow_stopped)


@lru_cache
def billing_module():
    return load(str(Path(__file__).with_name("evaluation_budget.py")))


def check_live_environment():
    if any(value and (key.startswith(("MEMORY_", "MEMBRAIN_EXTRACT", "MEMBRAIN_UPSTREAM"))
                      or key.endswith("_API_KEY") and key != "DEEPSEEK_API_KEY") for key, value in os.environ.items()):
        raise SystemExit("Live evaluation refuses unrelated provider or memory configuration in the environment.")


@contextmanager
def local_environment():
    allowed = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "LC_CTYPE",
               "TZ", "SYSTEMROOT", "WINDIR", "COMSPEC", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA", "HOMEDRIVE",
               "HOMEPATH", "SSL_CERT_FILE", "SSL_CERT_DIR", "MEMBRAIN_EVALUATION_CLOCK", "MEMBRAIN_SEMANTIC"}
    previous = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update({key: value for key, value in previous.items() if key in allowed})
        os.environ["PYTHON_DOTENV_DISABLED"] = "1"
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def check_billing():
    if BILLING is not None:
        BILLING.check()


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


class DegradedRun(SystemExit):
    """A live arm stopped by a harness event: its results are invalid, so it spends nothing more. A SystemExit, so no
    ``except Exception`` on the way out swallows it and the main block's cleanup still stops the services."""

    def __init__(self, kind: str):
        super().__init__(3)
        self.kind = kind


def harness_event(out: Path, kind: str, **data) -> None:
    """Record something that may have degraded a run, so it is reported with the results. ``data`` holds only kinds,
    positions and counts, never the scenario's words. Every recorded event makes the run invalid
    (acceptance_review.py validity), so a live arm stops here, after blocking the shared billing ledger as an
    interrupted arm does; a dry run records the event and goes on, so its checks see every event."""
    with (out / "harness-events.jsonl").open("a") as stream:
        stream.write(json.dumps({"time": time.time(), "kind": kind, **data}) + "\n")
    log("harness event", kind, data)
    if not STUB:
        log("live run stopped: harness event", kind)
        try:
            if BILLING is not None:
                BILLING.stop("harness_degraded")
        finally:
            raise DegradedRun(kind)


def failure_code(result: dict) -> str:
    """A failed page action's reason as a fixed code: its message names the scenario's topic, label or text."""
    if "differing_fields" in result:
        return "card_differs"
    if "unknown_removed" in result:
        return "unknown_removed"
    return "not_found"


def session_start(text: str, year: int = YEAR) -> datetime.datetime:
    """The scenario date and time stated in a session's first message ("Today is Tuesday, March 3, 21:00"; Spanish,
    German or Chinese), in UTC. A session without a date, or without a time, is an error."""
    if match := re.search(r"Today is \w+, (\w+) (\d+)", text):
        day = datetime.date(year, MONTHS[match[1].lower()], int(match[2]))
    elif match := re.search(r"Hoy es \w+, (\d+) de (\w+)", text):
        day = datetime.date(year, MESES[match[2].lower()], int(match[1]))
    elif match := re.search(r"Heute ist \w+, (?:der )?(\d+)\. (\w+)", text):
        day = datetime.date(year, MONATE[match[2].lower()], int(match[1]))
    elif match := re.search(r"今天是(\d+)月(\d+)日", text):
        day = datetime.date(year, int(match[1]), int(match[2]))
    else:
        raise ValueError(f"no scenario date in: {text[:80]!r}")
    clock = re.search(r"\b([01]?\d|2[0-3])[:：]([0-5]\d)\b", text[match.end():match.end() + 40])
    if clock is None:
        raise ValueError(f"no scenario time after the date in: {text[:80]!r}")
    return datetime.datetime.combine(day, datetime.time(int(clock[1]), int(clock[2])), datetime.UTC)


def simulate_today(today: datetime.date) -> None:
    """Older source trees without the scenario clock: their notes and extraction modules see the scenario date."""
    import importlib
    import types

    for name in ("membrain.notes", "membrain.extraction"):
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        if not hasattr(module, "_datetime") or hasattr(module, "_clock_today"):
            continue

        class ScenarioDate(datetime.date):
            @classmethod
            def today(cls):
                return today

        shim = types.ModuleType("datetime")
        shim.__dict__.update(datetime.__dict__)
        shim.date = ScenarioDate
        module._datetime = shim


# Stubs for the zero-network dry run --------------------------------------------------------------------------------

def refuse_network(out: Path) -> None:
    """Dry run: every connection that is not to this machine fails, and is reported."""
    original = socket.socket.connect

    def connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if self.family in (socket.AF_INET, socket.AF_INET6) and host not in ("127.0.0.1", "::1", "localhost"):
            harness_event(out, "network_refused")
            raise OSError(f"dry run: network connection to {host} refused")
        return original(self, address)

    socket.socket.connect = connect
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(name, None)


class StubHost:
    """A deterministic host model. On the first call of a turn it makes the scenario's scripted tool calls (when tools
    are offered); then it replies with a fixed template naming the memory blocks it was given."""

    def __init__(self, script: dict):
        self.script, self.key = script, None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        messages, offered = body["messages"], {tool["function"]["name"] for tool in body.get("tools") or ()}
        planned = self.script.get(self.key, []) if messages[-1]["role"] == "user" else []
        calls = []
        for index, step in enumerate(planned):
            if step["tool"] not in offered:
                continue
            arguments = dict(step.get("arguments") or {})
            if step.get("source") == "current":
                found = re.search(r"source_messages=(\[.*?\])\. ", messages[-1]["content"])
                if found:
                    arguments["source_messages"] = json.loads(found[1])
            calls.append({"id": f"call-{index}", "type": "function",
                          "function": {"name": step["tool"], "arguments": json.dumps(arguments)}})
        if calls:
            message = {"role": "assistant", "content": "", "tool_calls": calls}
        else:
            seen = "\n".join(str(item.get("content") or "") for item in (messages[0], messages[-1]))
            tags = sorted(set(re.findall(r"<(membrain-[a-z-]+)", seen)))
            message = {"role": "assistant",
                       "content": f"(stub reply, {self.key[0]} turn {self.key[1] + 1}) Thanks for telling me. "
                                  f"Memory blocks given: {', '.join(tags) or 'none'}."}
        size = len(request.content) // 4
        return httpx.Response(200, json={"choices": [{"message": message}], "usage": {
            "prompt_tokens": size, "completion_tokens": 20, "total_tokens": size + 20}})


class StubExtractor:
    """A deterministic extraction model: the scenario's scripted notes for the turn being read."""

    def __init__(self, script: dict):
        self.script, self.key = script, None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        notes = self.script.get(self.key, [])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"notes": notes})}}]})


# The host model ---------------------------------------------------------------------------------------------------

class Host:
    def __init__(self, cap, transport=None):
        self.calls, self.cap = 0, cap
        self.client = httpx.Client(timeout=600, transport=transport)

    def call(self, messages, tools=None):
        if self.calls >= self.cap:
            raise RuntimeError("host call cap reached")
        body = {"model": MODEL, "messages": messages, "max_tokens": 16384, "stream": False,
                "thinking": {"type": "enabled"}}
        if tools:
            body["tools"] = tools
        key = "stub" if STUB else os.environ["DEEPSEEK_API_KEY"]
        for attempt in range(4):
            self.calls += 1
            try:
                response = self.client.post(BASE_URL + "/chat/completions", json=body,
                                             headers={"Authorization": "Bearer " + key})
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                if not message.get("tool_calls") and not (message.get("content") or "").strip():
                    raise ValueError("empty reply")
                return message, data.get("usage", {})
            except (httpx.HTTPError, KeyError, ValueError) as error:
                log("host error", type(error).__name__, str(error)[:300])
                if attempt == 3 or self.calls >= self.cap:
                    raise
                time.sleep(0 if STUB else 10 * (attempt + 1))


def add_usage(total, usage):
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens"):
        total[key] = total.get(key, 0) + int(usage.get(key, 0) or 0)


# Memory (P and E) ---------------------------------------------------------------------------------------------------

class Memory:
    """One disposable evaluation installation on the scenario clock, with the plugin's hooks and MCP tools."""

    def __init__(self, directory: Path, model_cache: Path | None, ports, start: datetime.datetime, user=None):
        import shutil

        if not STUB:
            check_live_environment()

        from membrain import evaluation_clock, host
        from membrain.embedded_database import default_engine
        from membrain.local_profile import ensure_profile

        if directory.exists():
            raise SystemExit(f"{directory} exists: an installation is never reused")
        self.host, self.directory, self.user, self.clock = host, directory, user, evaluation_clock
        self.positions: dict[str, tuple] = {}  # event id -> (session, turn, role), recorded as each turn is written
        ensure_profile(directory, **({"api_port": ports[0], "database_port": ports[1]} if ports else {}),
                       database_engine=default_engine())
        evaluation_clock.mark_disposable(directory)
        evaluation_clock.advance(directory, start, run=directory.name)
        os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
        evaluation_clock.enable(directory)  # This process too: notes, coming-up dates and extraction read it.
        with local_environment():
            host.ensure_installation(directory)
        if model_cache is not None:  # The local embedding model, as the plugin would fetch it.
            from membrain.local_embeddings import download, installed, model_directory

            if not installed(directory):
                if not installed(model_cache):
                    download(model_cache)
                shutil.copytree(model_directory(model_cache), model_directory(directory), dirs_exist_ok=True)
        from membrain import desktop

        STARTED.append(directory)
        try:
            with local_environment():
                host.start(directory)
        except desktop.DesktopError:  # A slow start on a loaded machine is waited for, not fatal.
            deadline = time.monotonic() + 600
            while not desktop.status(directory).get("ready"):
                if time.monotonic() > deadline:
                    raise
                time.sleep(5)
        if "evaluation_clock_enabled" not in (directory / "service.log").read_text():
            raise SystemExit("the service did not enable the scenario clock")
        skill = SOURCE.parent / "plugins" / "membrain" / "skills" / "membrain" / "SKILL.md"
        self.skill = skill.read_text().split("---", 2)[2].strip()

    def client(self):
        client = self.host.ready_client(self.directory, self.user)
        if client is None:
            raise RuntimeError("memory service is not ready")
        return client

    def tools(self):
        from membrain.mcp_server import create_server

        client = self.client()
        server = create_server(client, directory=self.directory)
        listed = {tool.name: tool for tool in asyncio.run(server.list_tools())}
        schemas = [{"type": "function", "function": {
            "name": name, "description": listed[name].description or "", "parameters": listed[name].inputSchema}}
            for name in TOOLS if name in listed]
        return client, server, schemas

    def call(self, server, name, arguments) -> str:
        try:
            result = asyncio.run(server.call_tool(name, arguments))
        except Exception as error:  # The host sees tool errors, as it would through MCP.
            return json.dumps({"error": str(error)[:500]})
        if isinstance(result, tuple):
            result = result[1] if result[1] is not None else result[0]
        if isinstance(result, list):
            return "\n".join(getattr(part, "text", str(part)) for part in result)
        return json.dumps(result, ensure_ascii=False)

    def wait_until_indexed(self, timeout=600):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            client = self.host.ready_client(self.directory, self.user)
            if client is not None:
                with client:
                    dashboard = client.dashboard()
                # The runtime's own count over every job of the brain that can still run (the job list holds only
                # the latest 100, so counting it could miss an older queued job).
                if dashboard["status"]["pending_jobs"] == 0 and dashboard["status"].get("index_lag", 0) == 0:
                    return
            time.sleep(2)
        harness_event(self.directory.parent, "index_wait_timed_out")

    def now(self) -> str:
        return self.clock.current(self.directory).isoformat().replace("+00:00", "Z")

    def record_turn(self, session: str, index: int, *, recorded: bool = True) -> None:
        """Name the messages this turn wrote by their scenario position, so a page deletion finds them by identity,
        never by text (two turns may say the same thing). Recorded turns add one user message and one reply;
        intentionally unrecorded turns add none. Any other result invalidates the run rather than guessing."""
        with self.client() as client:
            fresh = [item for item in _messages(client).values() if item["event_id"] not in self.positions]
        if not recorded:
            if fresh:
                harness_event(self.directory.parent, "unexpected_recording", session=session, turn=index,
                              new_messages=len(fresh))
            return
        for role in ("user", "assistant"):
            mine = [item for item in fresh if item["actor_role"] == role]
            if len(mine) == 1:
                self.positions[mine[0]["event_id"]] = (session, index, role)
            else:
                harness_event(self.directory.parent, "message_identity_unknown", session=session, turn=index,
                              role=role, new_messages=len(mine))


class ExtractionWatch(logging.Handler):
    """Arm E: whether note extraction failed since the last look. The extractor's worker catches every error and
    only logs it, and extract_turn counts provider failures and skipped turns in the installation's extraction
    status; both are read here as counts, never the error text."""

    FAILURES = ("note extraction failed: %s", "note extraction queue full; turn skipped", "note not saved: %s")

    def __init__(self, directory: Path):
        import threading

        super().__init__(logging.WARNING)
        self.directory, self.logged, self.guard = directory, 0, threading.Lock()
        self.seen = self.counts()

    def emit(self, record: logging.LogRecord) -> None:
        if record.msg in self.FAILURES:
            with self.guard:
                self.logged += 1

    def counts(self) -> tuple[int, int]:
        from membrain.extraction import extraction_status

        status = extraction_status(self.directory) or {}
        with self.guard:
            logged = self.logged
        return int(status.get("turns_failed") or 0) + int(status.get("turns_skipped") or 0), logged

    def failed(self) -> bool:
        counts = self.counts()
        failed, self.seen = counts != self.seen, counts
        return failed


def watch_extraction(directory: Path) -> ExtractionWatch:
    watch = ExtractionWatch(directory)
    logger = logging.getLogger("membrain.extraction")
    logger.addHandler(watch)
    if not logger.isEnabledFor(logging.WARNING):
        logger.setLevel(logging.WARNING)
    return watch


# Page actions -------------------------------------------------------------------------------------------------------

def proposals_supported() -> bool:
    from membrain.client import MemoryClient

    return callable(getattr(MemoryClient, "persona_proposals", None))


def check_actions(module) -> list:
    """The scenario's page actions, checked before any model call."""
    actions = list(getattr(module, "PAGE_ACTIONS", []))
    positions = {(session, index) for session, turns in module.SESSIONS_LONG for index in range(len(turns))}
    for session, before, action in actions:
        if (session, before) not in positions or action.get("do") not in ACTIONS:
            raise SystemExit(f"bad page action at {session} {before}: {action.get('do')}")
        if action["do"] == "accept_persona_proposal" and "card" not in action:
            raise SystemExit("an accepted proposal states the card it leads to, for the reference arm")
        if action["do"] in PROPOSAL_ACTIONS and not proposals_supported() and not STUB:
            raise SystemExit("this runtime has no persona proposals (P2): the scenario cannot run on it")
    return actions


def world(client) -> dict:
    """What the memory page shows, in counts, so each action's removals can be checked against its scope."""
    from membrain.notes import list_notes

    items = client.timeline(roles=("user", "assistant"), max_characters=200_000, max_item_characters=20000,
                            limit=1000)["items"]
    messages = [item for item in items if not str(item.get("conversation_id") or "").startswith("membrain-")]
    relationship, mood, persona = client.relationship(), client.mood(), client.persona()
    return {"messages": len(messages), "notes": len(list_notes(client).get("items", [])),
            "feelings": len(client.affect_records()["records"]),
            "boundaries": sorted(entry["topic"] for entry in relationship["boundaries"]),
            "shared_moments": len(relationship["shared_moments"]),
            "familiarity": relationship["familiarity"]["level"],
            "familiarity_days": relationship["familiarity"]["days"],
            "mood": "baseline" if mood.get("at_baseline") else mood.get("label"), "mood_pinned": bool(mood.get("pinned")),
            "persona_version": persona.get("version", 0)}


def _messages(client) -> dict:
    """Conversation messages (not notes or other reserved records) by event id."""
    items = client.timeline(roles=("user", "assistant"), max_characters=200_000, max_item_characters=20000,
                            limit=1000)["items"]
    return {item["event_id"]: item for item in items
            if not str(item.get("conversation_id") or "").startswith("membrain-")}


def _forget(client, ids, conversation):
    generation = client.dashboard()["brain"]["scope_generation"]
    client.forget(list(ids), kind="events", mode="erase_content", expected_scope_generation=generation,
                  conversation_id=conversation)


def _card_differs(actual, expected) -> list:
    """The top-level card fields where the stored card differs from the scenario's, both in the stored form."""
    from membrain.persona import normalize_card

    if not isinstance(actual, dict):
        return ["card"]
    actual, expected = normalize_card(actual), normalize_card(expected)
    return sorted(key for key in {*actual, *expected} if actual.get(key) != expected.get(key))


def apply_page_action(memory: Memory, action: dict, turns: dict) -> dict:
    """One page action through the API, as the memory page performs it. Returns what it did."""

    kind, done = action["do"], {}
    with memory.client() as client:
        if kind == "set_persona":
            done = {"version": client.set_persona(action["card"], made_by="user")["version"]}
        elif kind == "restore_persona":
            done = {"version": client.restore_persona(action["version"], made_by="user")["version"]}
        elif kind == "reset_persona":
            done = {"version": client.reset_persona(made_by="user")["version"]}
        elif kind == "delete_persona_history":
            done = {"deleted_versions": client.delete_persona_history()["deleted_versions"]}
        elif kind in PROPOSAL_ACTIONS:
            listed = client.persona_proposals().get("proposals", [])
            open_ = [item for item in listed if item.get("status") == "open"
                     and action["match"].casefold() in json.dumps(item, ensure_ascii=False).casefold()]
            if not open_:
                return {"failed": f"no open proposal matching {action['match']!r}", "listed": len(listed)}
            decide = client.accept_persona_proposal if kind == "accept_persona_proposal" else \
                client.reject_persona_proposal
            result = decide(open_[0]["id"])
            done = {"proposal": open_[0]["id"], "version": (result.get("persona") or result).get("version")}
            if kind == "accept_persona_proposal":
                # F is given the scenario's card; the run is only valid if P's accepted card is that same card.
                differs = _card_differs(client.persona().get("card"), action["card"])
                if differs:
                    return {**done, "failed": "the accepted card differs from the scenario's card",
                            "differing_fields": differs}
        elif kind == "add_boundary":
            client.add_boundary(action["topic"], action.get("aliases", ()))
        elif kind == "remove_boundary":
            found = [entry for entry in client.relationship()["boundaries"] if entry["topic"] == action["topic"]]
            if not found:
                return {"failed": f"no boundary {action['topic']!r}"}
            client.remove_boundary(found[0]["id"])
        elif kind == "clear_feelings":
            client.clear_affect()
        elif kind == "delete_feeling":
            found = [entry for entry in client.affect_records()["records"] if entry["label"] == action["label"]]
            if not found:
                return {"failed": f"no feeling {action['label']!r}"}
            _forget(client, [entry["id"] for entry in found], "membrain-affect")
            done = {"deleted": len(found)}
        elif kind == "delete_note":
            from membrain.notes import NOTES_CONVERSATION, list_notes

            found = [item for item in list_notes(client)["items"] if action["contains"] in item["text"]]
            if not found:
                return {"failed": f"no note containing {action['contains']!r}"}
            _forget(client, [item["event_id"] for item in found], NOTES_CONVERSATION)
            done = {"deleted": len(found)}
        elif kind == "delete_message":
            # The message at this scenario position, by the identity recorded when its turn was written.
            position = (action["session"], action["turn"], action.get("role", "user"))
            before = _messages(client)
            found = [before[event] for event, at in memory.positions.items() if at == position and event in before]
            if not found:
                return {"failed": "message not found"}
            for item in found:
                _forget(client, [item["event_id"]], item["conversation_id"])
            # What the API actually removed, cascades included, named by scenario position so that F drops exactly
            # the same messages. A removed message without a recorded position cannot be mirrored: that fails.
            after = _messages(client)
            gone = [item for key, item in before.items() if key not in after]
            unknown = [item["event_id"] for item in gone if item["event_id"] not in memory.positions]
            done = {"deleted": len(found), "removed": sorted(
                list(memory.positions[item["event_id"]]) for item in gone if item["event_id"] in memory.positions)}
            if unknown:
                return {**done, "failed": "the deletion removed messages with no recorded position",
                        "unknown_removed": len(unknown)}
        elif kind == "reset_relationship":
            client.reset_relationship()
        elif kind == "reset_mood":
            client.reset_mood()
        elif kind == "pin_mood":
            client.pin_mood(action.get("pinned", True))
    return done


class Reference:
    """Arm F's view of the same world: the persona block it is given and its earlier history."""

    def __init__(self, card):
        from membrain.persona import EMPTY_CARD, normalize_card

        self.normalize, self.empty = normalize_card, dict(EMPTY_CARD)
        self.versions: list[dict] = []  # {"version", "card", "host_default"}
        self.history: list[tuple[tuple, dict]] = []  # ((session, turn, role), message)
        self.deleted: set[tuple] = set()  # Every position a page deletion removed, in any session.
        if card:
            self._save(card, host_default=True)

    def _save(self, card, host_default=False):
        card = self.normalize(card)
        current = self.versions[-1] if self.versions else None
        if current and current["card"] == card and current["host_default"] == host_default:
            return
        number = (current["version"] if current else 0) + 1
        self.versions.append({"version": number, "card": card, "host_default": host_default})

    def block(self) -> str | None:
        from membrain.persona import render_persona

        return render_persona(self.versions[-1]) if self.versions else None

    def apply(self, action: dict) -> dict:
        kind = action["do"]
        if kind in ("set_persona", "accept_persona_proposal"):
            self._save(action["card"])
        elif kind == "restore_persona":
            kept = next((entry for entry in self.versions if entry["version"] == action["version"]), None)
            if kept is None:
                return {"failed": f"no persona version {action['version']}"}
            self._save(kept["card"])
        elif kind == "reset_persona":
            default = next((entry for entry in reversed(self.versions) if entry["host_default"]), None)
            self._save(default["card"] if default else self.empty)
        elif kind == "delete_persona_history":
            self.versions = []
        elif kind == "delete_message":
            # Exactly the messages the product removed in P (``removed``: [session, turn, role] each).
            removed = {tuple(entry) for entry in action["removed"]}
            self.deleted |= removed  # Also kept out when the session in progress is added to the history.
            before = len(self.history)
            self.history = [(entry, message) for entry, message in self.history if entry not in removed]
            return {"deleted": before - len(self.history), "removed": sorted(map(list, removed))}
        return {}

    def end_session(self, current: list) -> None:
        """Add the finished session to the history, without the messages a page deletion removed during it. Within
        the session the host's own transcript kept them, as a host app does."""
        self.history += [(entry, message) for entry, message in current if entry not in self.deleted]

    def contains(self, keys) -> int:
        keys = {tuple(key) for key in keys}
        return sum(entry in keys for entry, _ in self.history)

    def summary(self) -> dict:
        return {"history_items": len(self.history),
                "persona_version": self.versions[-1]["version"] if self.versions else 0}


def removed_in_p(out: Path, action: dict, earlier: list, timeout: float = 3600) -> list:
    """For F: the messages P's page action actually removed, read from P's page-action log (the arms run side by
    side; F waits for P to reach the action). F mirrors exactly that, so cascades match the product."""
    run = out.parent / (out.name[:-1] + "P") if out.name.endswith("F") else None
    deadline = time.monotonic() + timeout
    while run is not None and time.monotonic() < deadline:
        check_billing()
        log_path = run / "page-actions.jsonl"
        entries = [json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
        done = [entry for entry in entries if entry["action"] in DELETES_MESSAGES]
        if len(done) > len(earlier):
            entry = done[len(earlier)]
            if entry["detail"] != {key: value for key, value in action.items() if key not in ("do", "card")}:
                raise SystemExit("P's page actions are not this scenario's")
            if entry["result"].get("failed") or "removed" not in entry["result"]:
                raise SystemExit("P could not apply the deletion F must mirror")
            return entry["result"]["removed"]
        time.sleep(2)
    raise SystemExit("P never recorded the deletion F must mirror")


# The run --------------------------------------------------------------------------------------------------------------

def load(path: str):
    spec = importlib.util.spec_from_file_location("scenario", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(arm: str, scenario_path: str, out: Path) -> None:
    global BILLING
    if arm not in ("P", "E", "F"):
        raise SystemExit("arms: P, E, F")
    module = load(scenario_path)
    sessions = module.SESSIONS_LONG
    scenario = Path(scenario_path).stem
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"results_{scenario}_{arm}.jsonl"
    if path.exists():
        raise SystemExit(f"{path} exists: a run is never resumed")
    year = getattr(module, "YEAR", YEAR)
    starts = [session_start(turns[0], year) for _, turns in sessions]
    if starts != sorted(starts):
        raise SystemExit("sessions must be in time order")
    actions = check_actions(module)
    turns_text = {(session, index, "user"): text for session, turns in sessions for index, text in enumerate(turns)}
    os.environ["TZ"] = "UTC"
    time.tzset()
    stub_host = stub_extract = None
    if STUB:
        if not hasattr(module, "STUB_HOST"):
            raise SystemExit("the dry run needs a practice scenario with stub scripts")
        refuse_network(out)
        stub_host, stub_extract = StubHost(module.STUB_HOST), StubExtractor(getattr(module, "STUB_EXTRACT", {}))
    if not STUB:
        check_live_environment()
    BILLING = None if STUB else billing_transport()
    host = Host(cap=sum(len(turns) for _, turns in sessions) * 5,
                transport=httpx.MockTransport(stub_host) if stub_host else BILLING)
    memory = chat = speaker = reference = watch = None
    if arm in ("P", "E"):
        cache = os.environ.get("MEMBRAIN_MODEL_CACHE")
        ports = tuple(map(int, os.environ["MEMBRAIN_PORTS"].split(","))) if os.environ.get("MEMBRAIN_PORTS") else None
        user = None
        if arm == "E":
            from membrain.adapters.chatbot import ChatMemory, Speaker

            speaker, user = Speaker(*PROXY_USER), ":".join(PROXY_USER)
        memory = Memory(out / f"brain-{scenario}-{arm}", Path(cache) if cache else None, ports, starts[0], user)
        if getattr(module, "PERSONA", None):
            with memory.client() as client:
                client.set_persona(module.PERSONA, made_by="host", host_default=True)
        if arm == "E":
            from membrain.extraction import Extractor

            extractor = Extractor(BASE_URL, os.environ.get("EXTRACT_MODEL", "deepseek-flash"),
                                  "stub" if STUB else os.environ["DEEPSEEK_API_KEY"],
                                  transport=httpx.MockTransport(stub_extract) if stub_extract else billing_transport())
            chat = ChatMemory(memory.directory, producer="membrain-proxy", tools=None, extractor=extractor)
            watch = watch_extraction(memory.directory)
            if chat.user_id(speaker) != user:
                raise SystemExit("the proxy's memory is not the brain page actions are applied to")
    else:
        reference = Reference(getattr(module, "PERSONA", None))
    proposals = proposals_supported()
    log(arm, scenario, "start", "stub" if STUB else "live", "proposals" if proposals else "no proposals (P2 absent)")

    deletions: list[dict] = []

    def page_actions(session, before):
        for at_session, at_turn, action in actions:
            if (at_session, at_turn) != (session, before):
                continue
            if action["do"] in PROPOSAL_ACTIONS and not proposals:
                # Dry run on a runtime without P2: skipped in every arm alike, so the arms still see one world.
                harness_event(out, "page_action_unsupported", action=action["do"], session=session, turn=before)
                continue
            # An action limited to some arms applies to F when it applies to P, the arm F is the reference for.
            if action.get("arms") and ("P" if arm == "F" else arm) not in action["arms"]:
                continue
            record = {"session": session, "before_turn": before, "action": action["do"],
                      "detail": {key: value for key, value in action.items() if key not in ("do", "card")}}
            if memory is not None:
                with memory.client() as client:
                    record["before"] = world(client)
                record["result"] = apply_page_action(memory, action, turns_text)
                with memory.client() as client:
                    record["after"] = world(client)
                record["time"] = memory.now()
                if chat is not None:
                    chat._forget_blocks(memory.user)  # The next message reads the page's change.
            else:
                if action["do"] in DELETES_MESSAGES:
                    action = {**action, "removed": removed_in_p(out, action, deletions)}
                    deletions.append(action)
                record["before"] = reference.summary()
                record["result"] = reference.apply(action)
                record["after"] = reference.summary()
                if action["do"] in DELETES_MESSAGES:
                    record["after"]["removed_still_in_history"] = reference.contains(action["removed"])
            with (out / "page-actions.jsonl").open("a") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            log("page action", action["do"], "before", session, "turn", before, "result:", record["result"])
            if record["result"].get("failed"):
                harness_event(out, "page_action_failed", action=action["do"], session=session, turn=before,
                              reason=failure_code(record["result"]))

    for (session, turns), start in zip(sessions, starts):
        today = start.date()
        simulate_today(today)
        if memory is not None:
            effective = memory.clock.advance(memory.directory, start, run=memory.directory.name)
            if effective > start and session != sessions[0][0]:  # The first was set when the profile was made.
                harness_event(out, "clock_already_past", session=session,
                              behind_seconds=int((effective - start).total_seconds()))
        date_line = f"Today's date: {today.isoformat()} ({today.strftime('%A')})."
        page_actions(session, 0)
        session_context = None
        if memory is not None and chat is None:
            memory.wait_until_indexed()
            session_context = memory.host.session_context(memory.directory, session)
        elif chat is not None:
            memory.wait_until_indexed()
        current: list[tuple[tuple, dict]] = []
        for index, text in enumerate(turns):
            check_billing()
            if index:
                page_actions(session, index)
            if stub_host:
                stub_host.key = stub_extract.key = (session, index)
            system, prompt_context, schemas, client, server = module.HOST + "\n\n" + date_line, None, None, None, None
            persona_block = None
            if chat is not None:
                prompt_context = chat.context(speaker, text, session=session, turn_id=f"t{index}")
                session_context = session_context or prompt_context
            elif memory is not None:
                prompt_context = memory.host.prompt_context(memory.directory, session, text, turn_id=f"t{index}",
                                                            include_source=True)
                client, server, schemas = memory.tools()
                system += "\n\n" + memory.skill + ("\n\n" + session_context if session_context else "")
            else:
                persona_block = reference.block()
                system += "\n\n" + persona_block if persona_block else ""
            user_content = (prompt_context + "\n\n" if prompt_context else "") + text
            prior = [message for _, message in reference.history] if reference is not None else []
            messages = [{"role": "system", "content": system}, *prior, *(message for _, message in current),
                        {"role": "user", "content": user_content}]
            first = len(messages) - 1
            usage, started, tool_calls = {}, time.monotonic(), []
            scenario_time = memory.now() if memory is not None else start.isoformat().replace("+00:00", "Z")
            try:
                for round_ in range(4):  # At most three tool rounds, then a final answer without tools.
                    offer = schemas if schemas and len(tool_calls) < 6 and round_ < 3 else None
                    message, call_usage = host.call(messages, offer)
                    add_usage(usage, call_usage)
                    calls = message.get("tool_calls") or []
                    if not calls:
                        break
                    messages.append({k: v for k, v in message.items()
                                     if k in ("role", "content", "tool_calls", "reasoning_content")})
                    for call in calls:
                        try:
                            arguments = json.loads(call["function"]["arguments"] or "{}")
                        except ValueError:
                            arguments = {}
                        result = memory.call(server, call["function"]["name"], arguments)
                        tool_calls.append({"name": call["function"]["name"], "arguments": arguments,
                                           "result": result[:2000]})
                        messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            finally:
                if client is not None:
                    client.close()
            written = [item.get("content") for item in messages[first + 1:]
                       if item.get("role") == "assistant" and item.get("content")]
            reply = "\n\n".join([*written, message.get("content") or ""]).strip()
            if chat is not None:
                chat.record(speaker, reply, session=session, turn_id=f"t{index}", prompt=text)
                recorded = not memory.host.paused(memory.directory, memory.user)
                chat.extractor.wait(120)
                check_billing()
                if chat.extractor._queue.unfinished_tasks:
                    harness_event(out, "extraction_unfinished", session=session, turn=index)
                if watch.failed():
                    harness_event(out, "extraction_failed", session=session, turn=index)
            elif memory is not None:
                resumed = memory.host.turn_resumed(memory.directory, session)
                recorded = bool(memory.host.finish_turn(memory.directory, session, reply, turn_id=f"t{index}",
                                                        **({"prompt": text} if resumed else {})))
            if memory is not None:
                memory.record_turn(session, index, recorded=recorded)
            transcript = [{k: v for k, v in item.items() if k != "reasoning_content"} for item in messages[first:]]
            transcript.append({"role": "assistant", "content": message.get("content") or ""})
            row = {"arm": arm, "scenario": scenario, "session": session, "turn": index, "date": today.isoformat(),
                   "scenario_time": scenario_time, "input": text, "reply": reply, "usage": usage,
                   "seconds": round(time.monotonic() - started, 1), "host_user_content": user_content,
                   "session_context": session_context or "", "prompt_context_chars": len(prompt_context or ""),
                   "tool_calls": tool_calls, "transcript": transcript}
            if reference is not None:
                row["reference_persona"] = persona_block or ""
                row["reference_history_items"] = len(prior)
            if memory is not None:
                row["recorded"] = recorded
            with path.open("a") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            log(arm, scenario, session, index, usage.get("total_tokens"),
                "tools:", [(call["name"], str(call["arguments"])[:80]) for call in tool_calls])
            if reference is not None:  # F's history holds the user's words, not a memory block, and the reply.
                current += [((session, index, "user"), {"role": "user", "content": text}),
                            ((session, index, "assistant"), {"role": "assistant", "content": reply})]
                turns_text[(session, index, "assistant")] = reply
            else:
                current += [((session, index, "turn"), item) for item in transcript]
                turns_text[(session, index, "assistant")] = reply
        if reference is not None:
            reference.end_session(current)
    stop_started()
    log(arm, scenario, "finished")


def stop_started() -> None:
    from membrain import desktop

    while STARTED:
        desktop.stop(STARTED.pop())


def interrupted(signum, frame):
    try:
        if BILLING is not None:
            BILLING.stop("arm_interrupted")
    finally:
        raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    if sys.argv[1:] == ["--stop"]:
        guard = billing_transport(allow_stopped=True)
        guard.stop("arm_failed")
        guard.close()
        raise SystemExit(0)
    if sys.argv[1:] == ["--preflight"]:
        check_live_environment()
        guard = billing_transport()
        print(json.dumps({"ledger": str(guard.path), "attempt": guard.run_id, "policy_sha256": guard.policy_sha256}))
        guard.close()
        raise SystemExit(0)
    try:
        run(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
    finally:
        try:
            stop_started()
        except Exception as error:  # Reported, never hiding the run's own error.
            log("stop failed", type(error).__name__)
