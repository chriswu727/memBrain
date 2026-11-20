"""Behavioural acceptance harness (R4, and C5 companion scenarios): plugin path (P) and whole history (F).

Two arms only, from the sixth maturity attempt on. The proxy with note extraction (arm E of attempts 1 to 5) is
gone: its note-extraction model was removed from the product, and its code was removed from this harness (the E
branch, the extraction watch, the stub extractor and the extraction events), so nothing here imports a removed
module. Built on the Phase B harness (v1-2026-10-29-phase-b-harness.py), with:
- **Scenario clock.** P runs on a disposable evaluation profile whose local service reads the scenario clock
  (src/membrain/evaluation_clock.py): every session states its date and time ("Today is Tuesday, March 3, 21:00"),
  and the clock is set to it before the session starts, so events are recorded, the mood decays and familiarity
  counts days on the scenario's timeline. The clock runs in UTC (TZ=UTC for the harness and the service) and never
  moves backwards. F has no service and needs no clock.
- **Persona.** The companion layer is always on, so both arms carry a persona. Every run, R4 and C5 alike, starts
  from one fixed personality type drawn from a recorded seed (acceptance_persona.py: the attempt id in a live run);
  a scenario PERSONA card is refused in every run. P saves the type before the first session as the product saves a
  type (made_by "host", action "preset"), so the product never assigns a random first type and never shows its
  one-time announcement. Each arm writes persona.json (seed, type, card hash) into its run directory; validity
  compares them. After that the persona changes only as a user changes it: in conversation (the host's
  memory_persona tool) or by a page action.
- **F mirrors P's persona turn by turn.** Each P row records the persona in effect at the start of the turn, read
  from the product after the prompt hook: ``persona_block`` (the product-rendered `<membrain-persona>` block, "" for
  none) and ``persona_turn`` ({"format": 1, "version", "sha256"}: the version and the sha256 of the block's UTF-8,
  None for none). F, which runs after P, gives its host exactly P's block for the same turn and records the same
  ``persona_turn`` beside it (``reference_persona``), so a change made by the host's tool, by an accepted
  suggestion or by a random pick reaches F as it reached P. Validity checks every F turn against P's. Claude Code
  is a coding host (since 2026-11-19): each P session starts with the companion's quiet form (the persona's voice,
  the user's agreements and the boundaries; no mood, familiarity or shared moments) and is handed the rest by the
  prompt hook at its first casual or emotional message, or the first after the host used a companion tool in it, as
  a real user's session is. Until then the block in effect, and so F's, is the quiet form.
- **What a plugin host gives its model unasked.** P drives the plugin's own hook functions
  (membrain.plugin.session_start, user_prompt and stop, with Claude Code's tool names) and offers every tool the
  plugin's MCP server lists, with its own schemas and descriptions. One server per session, as a host keeps one MCP
  connection, so memory_consolidate's batch survives between its two calls. The system prompt holds the scenario's
  HOST text, the date, the server's instructions and the session context; NOT the skill body, which a host loads
  only when its model opens the skill (never, in 86 turns of the 2026-11-13 trial). Two differences from a real
  host remain: Claude Code may defer tool descriptions until the model looks a tool up, while P gets them all up
  front, and the host model is DeepSeek through this emulation, not Claude Code (no hook subprocess, no stdio MCP,
  no Claude Code system prompt).
- **Page actions.** PAGE_ACTIONS = [(session, before_turn, action), ...] are the user's actions on the memory page,
  applied before that turn through the public API (the MemoryClient SDK, the same routes the page calls) in P, and
  mirrored in F's world, logged to page-actions.jsonl (format 2) with what each one removed. R4 scenarios have none
  (c5-precheck.py --r4 refuses them). Only what the page still offers is an action (PAGE_ACTIONS_FORMAT 3, since
  2026-11-18): the page has no text entry, so a boundary, a support style, a familiarity cap and a card of the
  user's own are no page actions; a boundary or a persona change is something the user says to the agent. An
  action's target is known from the scenario itself (a message by its scenario position, a boundary topic in the
  scenario's own words) or from the product's state by kind (the open suggestion, by origin and order); never from
  text the host model wrote. An action whose target does not exist because of what the host did or did not do (no
  open suggestion, no note from that message, a turn its pause left unrecorded, no boundary saved by the scenario's
  words) is recorded as ``not_applicable`` with a fixed reason code and the run goes on: that is the plugin path's
  behaviour and is scored. So is an action of LIMITED the service refuses with a validation error (4xx)
  (``page_refused``: a type switch whose card and the user's agreements no longer fit together). Only a real fault
  (any other refusal, a server error, an exception, a deletion the harness cannot mirror) is ``failed``, the harness
  event page_action_failed.
  A ``random`` personality switch is picked by the harness from the attempt's seed (``seeded_random_preset``), so a
  rerun agrees. F applies P's outcome of each action, read from P's page-actions.jsonl.
- **Reference world.** F's earlier history drops a message only when a page action deletes that message (the product
  erases it); resets, cleared feelings, deleted feelings and notes, and mood or persona actions never delete the
  conversation, so they never change F's history. Within the session in progress every arm keeps its own
  transcript, as a host app does. What the page did that the conversation does not show (a boundary removed on the
  page, a relationship reset, cleared feelings, the mood pin) reaches F as one fixed-format line in its system
  prompt (``Reference.page_line``, PAGE_LINE_FORMAT).
- **Dry run.** `C5_STUB=1` replaces the host model with a deterministic local stub (an httpx MockTransport answering
  from the scenario's STUB_HOST script, which can also answer a consolidation batch, make calls in later rounds of a
  turn and pass a field of an earlier call's result on) and refuses every non-loopback connection, so the whole run
  makes no network call. Only practice scenarios carry stub scripts.
- **Provider interruptions** (since 2026-11-17). A host send that ends in a transport timeout or a connection or
  protocol error, with HTTP 429, 500, 502, 503 or 504, or with a complete 2xx body that holds no billing JSON, is
  charged by the billing guard at a bound true for that request and leaves the ledger open; the host client sends
  the same request again after 30 and then 120 seconds, three sends at most (``INTERRUPTION_WAITS``), and records
  each interrupted send in provider-interruptions.jsonl (position, codes, sizes and seconds only). It is not a
  harness event: a retried interruption leaves the run valid. A third interruption blocks the ledger and stops the
  arm, as every provider failure did before.
- **What the host model is sent of its reasoning.** Within one turn's tool rounds, an assistant message with tool
  calls is sent back with its ``reasoning_content``. Every earlier turn of the session in progress (``current``) is
  sent without it, and so is every final reply; earlier sessions are not sent to P at all, and F is never offered
  tools. The provider's thinking-mode guide says that with ``tools`` the reasoning must be passed back in all
  subsequent requests or the API answers 400; that is not done here, and it is kept so (the call shape is frozen).
  A 400 is fatal; if enforced, it would come at P's first request after a turn with a tool call (at a session's
  second turn already if it covers every earlier assistant message): early in the first scenario, after a few
  turns' spend, with the refused request keeping its whole reservation on the guard's count.

The harness's own log and events name positions by index and carry kinds, codes and counts only: never a session
id, a scenario's words, a tool argument or a reply.

Usage: MEMBRAIN_MODEL_CACHE=... MEMBRAIN_PORTS=api,db python c5-harness.py ARM SCENARIO_FILE OUT_DIR
       python c5-harness.py --cleanup RUN_DIR      stop every profile this harness made under RUN_DIR, check its ports
A run directory is never resumed: existing results are refused.
"""
import asyncio
import datetime
import hashlib
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
ARMS = ("P", "F")
HOST_NAME = "claude-code"  # The plugin host whose hook functions and tool names arm P uses.
MONTHS = {name: number for number, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
     "december"], 1)}
MESES = {name: number for number, name in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
     "diciembre"], 1)}
MONATE = {name: number for number, name in enumerate(
    ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november",
     "dezember"], 1)}
# The page-action vocabulary (PAGE_ACTIONS_FORMAT 3): kind -> (required arguments, optional arguments). Every action
# may also carry "arms" naming only P (F follows P). Only delete_message deletes conversation messages, so only it
# changes F's history. Format 3 (2026-11-18) is what the page still offers: format 2's add_boundary, set_support_style,
# cap_familiarity and set_persona are gone (the page has no text entry, and support style and the familiarity cap
# left the product), and remove_boundary takes any boundary in force, as the host saved it.
PAGE_ACTIONS_FORMAT = 3
REMOVED_ACTIONS = ("add_boundary", "set_support_style", "cap_familiarity", "set_persona")  # Format 2 only.
ACTION_ARGUMENTS = {
    "delete_message": ({"session", "turn"}, {"role"}),
    "delete_note_from": ({"session", "turn"}, {"role"}),
    "delete_feeling_from": ({"session", "turn"}, {"role"}),
    "clear_feelings": (set(), set()),
    "reset_relationship": (set(), set()),
    "reset_mood": (set(), set()),
    "pin_mood": (set(), {"pinned"}),
    "remove_boundary": ({"topic"}, set()),
    "switch_persona": ({"preset"}, set()),
    "delete_persona_history": (set(), set()),
    "accept_proposal": (set(), {"origin", "position", "kind"}),
    "reject_proposal": (set(), {"origin", "position", "kind"}),
}
ACTIONS = set(ACTION_ARGUMENTS)
DELETES_MESSAGES = {"delete_message"}
BY_SOURCE = {"delete_message", "delete_note_from", "delete_feeling_from"}  # Target: a message by scenario position.
PROPOSAL_ACTIONS = {"accept_proposal", "reject_proposal"}
PROPOSAL_ORIGINS = ("any", "feedback", "host")  # feedback: made from repeated manner feedback; host: the host AI's.
# A proposal decision may also name a manner kind (an id of the product's persona_growth.KINDS table, never host
# text): it then takes the open feedback suggestion of that kind.
# Actions a 4xx validation refusal of which is caused by what the host saved before it (a type switch whose card and
# the agreements the user made with the host no longer fit together), so it is not_applicable ("page_refused") and
# scored, not a fault.
LIMITED = {"switch_persona"}
# The page-actions.jsonl record (PAGE_RECORD_FORMAT 2): every record has "status" done, not_applicable or failed.
PAGE_RECORD_FORMAT = 2
# Why an action had no target, because of what the host did or did not do: scored with the arm, never a fault.
NOT_APPLICABLE = ("message_not_recorded", "message_already_removed", "no_note_from_message",
                  "no_feeling_from_message", "boundary_not_present", "no_open_proposal", "page_refused")
# Why an action failed (a real fault: the run is invalid): page_action_failed carries one of these as its reason.
FAILURE_CODES = ("not_found", "unknown_removed", "service_refused", "exception", "card_differs",
                 "ambiguous_proposal")
PERSONA_TURN_FORMAT = 1  # {"format", "version", "sha256"} in each row: the persona in effect at the turn's start.
PAGE_LINE_FORMAT = 2  # The line F is given about page-only settings (Reference.page_line); 2 since 2026-11-18.
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


# Variables that would change the host model or the code a live run executes: HOST_MODEL replaces the frozen model
# (the guard would then refuse the first request and block the ledger); MEMBRAIN_SRC puts another source tree first on
# sys.path. The run script's preflight also refuses PREFLIGHT_OVERRIDES.
LIVE_OVERRIDES = ("HOST_MODEL", "MEMBRAIN_SRC")
# Refused before any arm starts, by `--preflight` only (tests run the arms in-process with them set): PYTHONPATH can
# shadow the frozen package, MEMBRAIN_SEMANTIC=0 turns off the meaning route the product ships with, and
# MEMBRAIN_EVALUATION_CLOCK is the harness's own, set per disposable profile.
PREFLIGHT_OVERRIDES = ("PYTHONPATH", "MEMBRAIN_SEMANTIC", "MEMBRAIN_EVALUATION_CLOCK")


def check_live_environment():
    if any(value and (key.startswith(("MEMORY_", "MEMBRAIN_EXTRACT", "MEMBRAIN_UPSTREAM"))
                      or key.endswith("_API_KEY") and key != "DEEPSEEK_API_KEY") for key, value in os.environ.items()):
        raise SystemExit("Live evaluation refuses unrelated provider or memory configuration in the environment.")
    found = [name for name in LIVE_OVERRIDES if name in os.environ]
    if found:
        raise SystemExit(f"Live evaluation refuses override variables: {', '.join(found)}.")


def check_preflight_environment():
    check_live_environment()
    found = [name for name in PREFLIGHT_OVERRIDES if name in os.environ]
    if found:
        raise SystemExit(f"Live evaluation refuses override variables: {', '.join(found)}.")


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


def billing_halt(stopping: list):
    """A shared billing stop met after this turn's paid host call, returned instead of raised: the turn's row is
    written first (``"stopped_after": "billing_stop"``), then the stop is raised. Nothing is spent in between."""
    try:
        check_billing()
    except Exception as error:  # A blocked or unreadable ledger: the run stops either way.
        stopping.append("billing_stop")
        log("billing stopped: this turn's row is written first", type(error).__name__)
        return error
    return None


@contextmanager
def bookkeeping_errors(out: Path, session: str, turn: int, stopping: list):
    errors = []
    try:
        yield errors
    except Exception as error:
        errors.append(error)
        harness_event(out, "bookkeeping_failed", session=session, turn=turn)
        if "bookkeeping_failed" not in stopping:
            stopping.append("bookkeeping_failed")


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


class DegradedRun(SystemExit):
    """A live arm stopped by a harness event: its results are invalid, so it spends nothing more. A SystemExit, so no
    ``except Exception`` on the way out swallows it and the main block's cleanup still stops the services."""

    def __init__(self, kind: str):
        super().__init__(3)
        self.kind = kind


_DEFERRED: list | None = None  # While a turn's reply is being recorded: the stopping events, raised after its row.


def stops_on_events() -> bool:
    """A live arm stops on its first harness event; a dry run records every event and goes on."""
    return not STUB


@contextmanager
def deferred_stop(kinds: list):
    """After a turn's reply was paid for: a live arm's stop waits until the turn's results row is written, so the
    paid reply is never lost. The ledger is still blocked at once."""
    global _DEFERRED
    _DEFERRED = kinds
    try:
        yield kinds
    finally:
        _DEFERRED = None


def stop_run(kind: str):
    log("live run stopped: harness event", kind)
    raise DegradedRun(kind)


def harness_event(out: Path, kind: str, **data) -> None:
    """Record something that may have degraded a run, so it is reported with the results. ``data`` holds only kinds,
    positions and counts, never the scenario's words. Every recorded event makes the run invalid
    (acceptance_review.py validity), so a live arm stops here, after blocking the shared billing ledger as an
    interrupted arm does (within ``deferred_stop``, after the turn's row); a dry run records the event and goes on,
    so its checks see every event."""
    with (out / "harness-events.jsonl").open("a") as stream:
        stream.write(json.dumps({"time": time.time(), "kind": kind, **data}) + "\n")
    log("harness event", kind, data)
    if not stops_on_events():
        return
    try:
        if BILLING is not None:
            BILLING.stop("harness_degraded")
    except Exception as error:  # The stop still happens; the run script's --stop blocks the ledger again.
        log("ledger stop failed", type(error).__name__)
    if _DEFERRED is not None:
        _DEFERRED.append(kind)
        log("live run stops after this turn's row: harness event", kind)
        return
    stop_run(kind)


def failure_code(result: dict) -> str:
    """A failed page action's reason as a fixed code (FAILURE_CODES): its message may name the scenario's topic,
    label or text, so it is never the reason."""
    if result.get("code") in FAILURE_CODES:
        return result["code"]
    if "differing_fields" in result:
        return "card_differs"
    if "unknown_removed" in result:
        return "unknown_removed"
    if result.get("ambiguous"):
        return "ambiguous_proposal"
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


STUB_CUE = "user practice facts"  # The cue the stub host writes when it answers a consolidation batch.


class StubHost:
    """A deterministic host model. In each round of a turn it makes the scenario's scripted tool calls for that round
    (when tools are offered): a step with ``"round": N`` (default 0) is made in the turn's round N, after the results
    of the earlier rounds; then it replies with a fixed template naming the memory blocks it was given.

    A step's argument may take a field of an earlier call's result, in this turn or an earlier one:
    ``{"$result": [session, turn, index, field]}`` is replaced by ``field`` of the JSON result of the ``index``-th
    scripted call (counting from 0 over the turn's steps) made at that (session, turn), and the argument is left out
    when there is no such result (the tool then answers with an error, as it would to a host). The stub keeps every
    result it is shown, so a propose in one turn can be confirmed in a later one.

    A consolidation batch is answered as a host is asked to: when the last tool result is a batch that
    memory_consolidate handed out (it carries instructions and messages), the stub calls memory_consolidate once more
    with one cue for the batch's first message. ``consolidations`` counts the batches it answered."""

    def __init__(self, script: dict):
        self.script, self.key, self.consolidations = script, None, 0
        self.text = None  # The user's own words in this turn: a scripted pause without request quotes them.
        self.instructions = None  # The server instructions whose presence in the system prompt the reply reports.
        self.issued: dict[str, tuple] = {}  # call id -> (session, turn, index) of the scripted call it made
        self.results: dict[tuple, object] = {}  # (session, turn, index) -> the call's result, as JSON when it is
        self.counter = 0

    def _observe(self, messages) -> None:
        """Keep the result of every scripted call this stub made that the conversation now shows."""
        for item in messages:
            where = self.issued.get(item.get("tool_call_id")) if item.get("role") == "tool" else None
            if where is not None:
                try:
                    self.results[where] = json.loads(item.get("content") or "")
                except ValueError:
                    self.results[where] = item.get("content")

    def _resolve(self, arguments: dict) -> dict:
        resolved = {}
        for name, value in arguments.items():
            if isinstance(value, dict) and set(value) == {"$result"}:
                session, turn, index, field = value["$result"]
                found = self.results.get((session, turn, index))
                if not isinstance(found, dict) or found.get(field) is None:
                    continue
                value = found[field]
            resolved[name] = value
        return resolved

    def _batch(self, messages) -> dict | None:
        """The consolidation batch in the last tool result, when the call that produced it handed one out."""
        if messages[-1]["role"] != "tool":
            return None
        calls = {call["id"]: call["function"] for item in messages if item.get("role") == "assistant"
                 for call in item.get("tool_calls") or ()}
        call = calls.get(messages[-1].get("tool_call_id"))
        if not call or call["name"] != "memory_consolidate" or json.loads(call["arguments"] or "{}"):
            return None
        try:
            batch = json.loads(messages[-1]["content"])
        except ValueError:
            return None
        return batch if isinstance(batch, dict) and batch.get("instructions") and batch.get("messages") else None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        messages = body["messages"]
        schemas = {tool["function"]["name"]: tool["function"] for tool in body.get("tools") or ()}
        offered = set(schemas)
        self._observe(messages)
        last_user = max(index for index, item in enumerate(messages) if item["role"] == "user")
        round_ = sum(1 for item in messages[last_user + 1:] if item.get("role") == "assistant" and item.get("tool_calls"))
        steps = list(enumerate(self.script.get(self.key, [])))
        planned = [(index, step) for index, step in steps if int(step.get("round", 0)) == round_]
        if round_ and messages[-1]["role"] != "tool":
            planned = []
        batch = self._batch(messages) if "memory_consolidate" in offered else None
        if batch is not None:
            self.consolidations += 1
            planned = [(None, {"tool": "memory_consolidate",
                               "arguments": {"cues": [{"id": batch["messages"][0]["id"], "cues": [STUB_CUE]}]}})]
        calls = []
        user = messages[last_user]["content"]
        for index, step in planned:
            if step["tool"] not in offered:
                continue
            arguments = self._resolve(dict(step.get("arguments") or {}))
            accepts = (schemas[step["tool"]].get("parameters") or {}).get("properties") or {}
            if (step["tool"] in ("memory_note", "memory_observe") or "recording_capture" in accepts) \
                    and "recording_capture" not in arguments:
                captured = re.search(r'recording_capture=("[a-f0-9.]+")', user)
                if captured:
                    arguments["recording_capture"] = json.loads(captured[1])
            if step.get("source") == "current":
                found = re.search(r"source_messages=(\[.*?\])\. ", user)
                if found:
                    arguments["source_messages"] = json.loads(found[1])
            if step["tool"] == "memory_pause" and "request" not in arguments and self.text is not None:
                # The pause tool requires the user's words; scripts written before it (one of them sealed) pass none.
                arguments["request"] = self.text
            self.counter += 1
            ident = f"call-{self.counter}"
            if index is not None and self.key is not None:
                self.issued[ident] = (self.key[0], self.key[1], index)
            calls.append({"id": ident, "type": "function",
                          "function": {"name": step["tool"], "arguments": json.dumps(arguments)}})
        if calls:
            message = {"role": "assistant", "content": "", "tool_calls": calls}
        else:
            seen = "\n".join(str(item.get("content") or "") for item in (messages[0], messages[-1]))
            tags = sorted(set(re.findall(r"<(membrain-[a-z-]+)", seen)))
            given = bool(self.instructions) and self.instructions in str(messages[0].get("content") or "")
            message = {"role": "assistant",
                       "content": f"(stub reply, {self.key[0]} turn {self.key[1] + 1}) Thanks for telling me. "
                                  f"Memory blocks given: {', '.join(tags) or 'none'}. "
                                  f"server instructions: {'given' if given else 'none'}."}
        size = len(request.content) // 4
        return httpx.Response(200, json={"choices": [{"message": message}], "usage": {
            "prompt_tokens": size, "completion_tokens": 20, "total_tokens": size + 20}})


# The host model ---------------------------------------------------------------------------------------------------

# A host call whose send the billing guard settled as interrupted (a transport timeout or connection or protocol
# error, HTTP 429, 500, 502, 503 or 504, or a complete 2xx body without billing JSON:
# evaluation_budget.ProviderInterrupted) is sent again, the same request, after these waits in seconds: at most two
# retries, three sends in all. Each send reserves and settles under the guard and counts against the host call cap. A
# third interruption, or one the cap leaves no send for, blocks the ledger with the interruption's kind and stops the
# arm. Every interrupted send is one line of provider-interruptions.jsonl, never a harness event: a retried
# interruption leaves the run valid. Separate from the retries for an empty reply. INTERRUPTION_FORMAT 2 (since
# 2026-11-17's review; format 1 had no sizes or durations): format, time, session, turn, round, kind, the cause
# (error_class; http_status; or http_status and body), request_bytes (the body's size as the guard recorded it),
# send_seconds (how long the failed send took), wait_seconds (the wait before the next send, 0 without one), send and
# retried.
INTERRUPTION_WAITS = (30, 120)
INTERRUPTIONS = "provider-interruptions.jsonl"
INTERRUPTION_FORMAT = 2


def interruption_code(failure: dict) -> str:
    """An interruption's cause as a fixed code (evaluation_budget.interruption_code): the guard's allowlisted class
    name, ``http_<status>`` or ``body_<reason>``; ``other`` for anything else."""
    return billing_module().interruption_code(failure)


class Host:
    def __init__(self, cap, transport=None, guard=None, out: Path | None = None):
        self.calls, self.cap = 0, cap
        self.guard, self.out = guard, out  # The billing guard a final interruption blocks; the run directory.
        self.client = httpx.Client(timeout=600, transport=transport)

    def _interrupted(self, error, send: int, retried: bool, at: dict | None, seconds: float) -> None:
        at, failure = at or {}, error.failure
        if self.out is not None:
            if failure.get("kind") == "provider_transport":
                cause = {"error_class": interruption_code(failure)}
            elif failure.get("kind") == "provider_incomplete_body":
                cause = {"http_status": failure.get("http_status"), "body": failure.get("body")}
            else:
                cause = {"http_status": failure.get("http_status")}
            record = {"format": INTERRUPTION_FORMAT, "time": time.time(), "session": at.get("session"),
                      "turn": at.get("turn"), "round": at.get("round"), "kind": failure.get("kind"), **cause,
                      "request_bytes": error.request_bytes, "send_seconds": round(seconds, 3),
                      "wait_seconds": INTERRUPTION_WAITS[send - 1] if retried else 0,
                      "send": send, "retried": retried}
            with (self.out / INTERRUPTIONS).open("a") as stream:
                stream.write(json.dumps(record) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        then = (f"retry in {INTERRUPTION_WAITS[send - 1]} s" if retried
                else "no retry left: the ledger is blocked and the arm stops")
        log("provider interrupted", interruption_code(failure), "at",
            f"{at.get('where', 'an unknown turn')}, round {(at.get('round') or 0) + 1}:",
            f"send {send} of {len(INTERRUPTION_WAITS) + 1},", then)

    def call(self, messages, tools=None, at: dict | None = None):
        """One host call. ``at`` names its position for the interruption records: session, turn, round and
        ``where`` (the log's position text, never a session id)."""
        if self.calls >= self.cap:
            raise RuntimeError("host call cap reached")
        body = {"model": MODEL, "messages": messages, "max_tokens": 16384, "stream": False,
                "thinking": {"type": "enabled"}}
        if tools:
            body["tools"] = tools
        key = "stub" if STUB else os.environ["DEEPSEEK_API_KEY"]
        empty = interrupted = 0
        while True:
            self.calls += 1
            sent = time.monotonic()
            try:
                response = self.client.post(BASE_URL + "/chat/completions", json=body,
                                             headers={"Authorization": "Bearer " + key})
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                if not message.get("tool_calls") and not (message.get("content") or "").strip():
                    raise ValueError("empty reply")
                return message, data.get("usage", {})
            except billing_module().ProviderInterrupted as error:
                interrupted += 1
                retried = interrupted <= len(INTERRUPTION_WAITS) and self.calls < self.cap
                self._interrupted(error, interrupted, retried, at, time.monotonic() - sent)
                if not retried:
                    try:
                        if self.guard is not None:
                            self.guard.stop(error.failure.get("kind") or "provider_transport")
                    except Exception as failure:  # The run script's --stop blocks the ledger again.
                        log("ledger stop failed", type(failure).__name__)
                    if interrupted <= len(INTERRUPTION_WAITS):
                        raise RuntimeError("host call cap reached") from None
                    raise billing_module().BudgetStop(
                        "A provider request was interrupted on every send; the billing run is stopped.") from None
                time.sleep(INTERRUPTION_WAITS[interrupted - 1])
            except (httpx.HTTPError, KeyError, ValueError) as error:
                empty += 1
                log("host error", type(error).__name__, str(error)[:300])
                if empty == 4 or self.calls >= self.cap:
                    raise
                time.sleep(0 if STUB else 10 * empty)


def add_usage(total, usage):
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens"):
        total[key] = total.get(key, 0) + int(usage.get(key, 0) or 0)


# Memory (arm P) ------------------------------------------------------------------------------------------------------

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
        self.unrecorded: set[tuple] = set()  # (session, turn) of every turn that ended unrecorded
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
        except desktop.DesktopError as error:  # A slow start on a loaded machine is waited for, not fatal.
            if error.code != "service_start_timeout":
                raise
            deadline = time.monotonic() + 600
            while not desktop.status(directory).get("ready"):
                if time.monotonic() > deadline:
                    raise
                time.sleep(5)
        if "evaluation_clock_enabled" not in (directory / "service.log").read_text():
            raise SystemExit("the service did not enable the scenario clock")

    def client(self):
        client = self.host.ready_client(self.directory, self.user)
        if client is None:
            raise RuntimeError("memory service is not ready")
        return client

    def tools(self):
        """One MCP server for a session, as the plugin's host keeps one connection: its client, the server, the
        function schemas of every tool it lists (in its own order, with its own descriptions), and the instructions
        it gives the host. The caller closes the client when the session ends."""
        from membrain.mcp_server import create_server

        client = self.client()
        try:
            # As `membrain plugin mcp` creates it for an installation (plugin_cli: require_turn_capture=True).
            server = create_server(client, directory=self.directory, require_turn_capture=True)
            listed = asyncio.run(server.list_tools())
        except BaseException:
            client.close()
            raise
        schemas = [{"type": "function", "function": {
            "name": tool.name, "description": tool.description or "", "parameters": tool.inputSchema}}
            for tool in listed]
        instructions = getattr(server, "instructions", None) or self.host.server_instructions()
        return client, server, schemas, instructions

    # The plugin's own hook functions, with the payloads Claude Code sends ------------------------------------------

    def session_start(self, session: str) -> str | None:
        from membrain import plugin

        return plugin.session_start({"session_id": session}, self.directory)

    def user_prompt(self, session: str, index: int, text: str) -> str | None:
        from membrain import plugin

        return plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": f"t{index}"}, self.directory)

    def stop(self, session: str, index: int, text: str, reply: str) -> bool:
        """The plugin's Stop handler. It returns nothing, so the records its finish_turn call stored are observed
        (the call itself is unchanged): whether this turn was recorded."""
        from membrain import plugin

        stored, original = [], plugin.host.finish_turn

        def observed(*args, **kwargs):
            result = original(*args, **kwargs)
            stored.append(result)
            return result

        plugin.host.finish_turn = observed
        try:
            plugin.stop({"session_id": session, "prompt_id": f"t{index}", "prompt": text,
                         "last_assistant_message": reply}, self.directory)
        finally:
            plugin.host.finish_turn = original
        return bool(stored and stored[-1])

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

    def persona_in_effect(self, session: str) -> tuple[str, dict]:
        """The persona in effect now, as the product renders it for this session's host: its block ("" for none) and
        its content-free identity (persona_turn). Claude Code is a coding host, so until the session's conversation
        turns casual or emotional the block is the quiet form (``persona.render_manner``, since 2026-11-19)."""
        from membrain.persona import render_manner

        with self.client() as client:
            current = client.persona()
            brain = client.brain_id
        quiet = ((self.host.session_state(self.directory, session).get("memory_context") or {}).get("quiet")
                 and not self.host.companion_handed(self.directory, session, brain))
        block = (render_manner(current) if quiet else current.get("block")) or ""
        return block, persona_turn((current.get("version") or 0) if block else 0, block)

    def paused(self, session: str) -> bool:
        """Whether the product holds recording paused for this conversation now: its own pause state, read as the
        plugin's hooks read it (the harness's hook payloads name no user). A conversation pause covers only the
        conversations it was made in; a pause until resumed covers every conversation."""
        return self.host.paused(self.directory, None, session)

    def record_turn(self, session: str, index: int, *, recorded: bool = True) -> None:
        """Name the messages this turn wrote by their scenario position, so a page deletion finds them by identity,
        never by text (two turns may say the same thing). Recorded turns add one user message and one reply;
        intentionally unrecorded turns add none. Any other result invalidates the run rather than guessing."""
        with self.client() as client:
            fresh = [item for item in _messages(client).values() if item["event_id"] not in self.positions]
        if not recorded:
            self.unrecorded.add((session, index))
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


# Page actions -------------------------------------------------------------------------------------------------------

def proposals_supported() -> bool:
    from membrain.client import MemoryClient

    return callable(getattr(MemoryClient, "persona_proposals", None))


def application_order(actions: list, sessions: list) -> list:
    """The indexes of PAGE_ACTIONS in the order the harness applies them: by session, then before_turn, then their
    order in the list (the order actions_digest and validity read them in)."""
    order = [session for session, _ in sessions]
    return sorted(range(len(actions)), key=lambda index: (order.index(actions[index][0]), actions[index][1], index))


def _topic(text) -> str:
    """A boundary topic as the product compares topics: whitespace collapsed, case ignored."""
    return " ".join(str(text or "").split()).casefold()


def _argument_problem(kind: str, action: dict, sessions: list, at: tuple) -> str | None:
    """Why one action's arguments are not of its kind's shape, or None (never the scenario's words)."""
    required, optional = ACTION_ARGUMENTS[kind]
    given = set(action) - {"do", "arms"}
    if required - given or given - required - optional:
        return f"{kind} takes {sorted(required)} and optionally {sorted(optional)}"
    if kind in BY_SOURCE:
        order = [session for session, _ in sessions]
        turns = dict(sessions)
        session, turn, role = action["session"], action["turn"], action.get("role", "user")
        if session not in turns or type(turn) is not int or not 0 <= turn < len(turns[session]) \
                or role not in ("user", "assistant"):
            return "its message is not a message of the scenario"
        if (order.index(session), turn) >= (order.index(at[0]), at[1]):
            return "its message comes at or after the action"
    if kind == "pin_mood" and type(action.get("pinned", True)) is not bool:
        return "pinned is true or false"
    if kind == "remove_boundary" and not (isinstance(action["topic"], str) and _topic(action["topic"])):
        return "a boundary topic is a non-empty string"
    if kind == "switch_persona":
        from membrain import persona_presets

        if not isinstance(action["preset"], str) or action["preset"] not in (*persona_presets.IDS,
                                                                              persona_presets.RANDOM):
            return "the preset is a personality type id or random"
    if kind in PROPOSAL_ACTIONS and (action.get("origin", "any") not in PROPOSAL_ORIGINS
                                     or type(action.get("position", 1)) is not int or action.get("position", 1) < 1):
        return f"origin is one of {PROPOSAL_ORIGINS} and position a whole number from 1"
    if kind in PROPOSAL_ACTIONS and "kind" in action:
        from membrain import persona_growth

        if action["kind"] not in persona_growth.KINDS or action.get("origin", "any") == "host":
            return "kind is a manner kind of the product's table, naming a feedback suggestion"
    return None


def check_actions(module, only: int | None = None) -> list:
    """The scenario's page actions, checked before any model call: each a known kind (ACTION_ARGUMENTS) at a real
    position, with exactly its kind's arguments; a message named by position comes before the action. A kind the page
    no longer offers (REMOVED_ACTIONS) is refused by name. With ``only``, just the action at that index is checked,
    the others read as context (the precheck checks one at a time)."""
    actions = list(getattr(module, "PAGE_ACTIONS", []))
    sessions = [(session, list(turns)) for session, turns in module.SESSIONS_LONG]
    positions = {(session, index) for session, turns in sessions for index in range(len(turns))}
    for number, entry in enumerate(actions):
        if only is not None and number != only:
            continue
        session, before, action = entry
        if isinstance(action, dict) and action.get("do") in REMOVED_ACTIONS:
            # Its own message, which the precheck reads as the fixed code removed_action.
            raise SystemExit(f"removed page action at {session} {before}: {action['do']} is no longer on the page; "
                             "the user says it to the agent instead")
        if (session, before) not in positions or not isinstance(action, dict) or action.get("do") not in ACTIONS:
            raise SystemExit(f"bad page action at {session} {before}: "
                             f"{action.get('do') if isinstance(action, dict) else 'not an object'}")
        if action.get("arms") is not None and (not action["arms"] or set(action["arms"]) - {"P"}):
            raise SystemExit(f"bad page action at {session} {before}: arms may name only P (F follows P)")
        if problem := _argument_problem(action["do"], action, sessions, (session, before)):
            raise SystemExit(f"bad page action at {session} {before}: {problem}")
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


# Which records a page action removed: by their own ids, named by scenario position or a content hash, never by
# database id or content. One record per entry: {"kind", "ref", "sources", "established": true}, or
# {"kind", "established": false} for a drop in a count that no id diff accounts for.
COUNTED = {"messages": ("message",), "feelings": ("feeling",), "boundaries": ("boundary",),
           "shared_moments": ("shared_moment",), "notes": ("note", "shared_moment", "commitment")}


def record_ref(kind: str, sources=None, content=None) -> str:
    """A removed record's ref, the shared format the review side recomputes. Stable across arms: scenario positions
    (or, for a record with none, its normalized content) are the same in each arm. ``sources`` are
    [session_id, turn_index, role] triples; the content itself never reaches the file, only its hash."""
    if sources:
        triples = sorted([str(session), int(turn), str(role)] for session, turn, role in sources)
        return "src:" + hashlib.sha256(json.dumps([kind, triples], separators=(",", ":"), ensure_ascii=False)
                                       .encode("utf-8")).hexdigest()
    return "content:" + hashlib.sha256(json.dumps([kind, content if content is not None else {}],
                                                  separators=(",", ":"), ensure_ascii=False, sort_keys=True)
                                       .encode("utf-8")).hexdigest()


def layer_records(client, positions: dict) -> dict:
    """Every record of the layers a page action can remove, by its own id, through the SDK calls world() uses:
    {id: {"kind", "sources", "content"}}, keyed by id alone so that a record whose kind reads differently after the
    action (a commitment before a relationship reset is a plain note after it) is not taken for removed. ``sources``
    are the scenario positions of its source messages."""
    from membrain.notes import list_notes
    from membrain.persona import normalize_card

    def where(ids) -> list:
        return sorted({tuple(positions[event]) for event in ids or () if event in positions})

    def words(text) -> str:
        return " ".join(str(text or "").split())

    records = {}
    for event, item in _messages(client).items():
        records[event] = {"kind": "message", "sources": where([event]), "content": None}
    relationship = client.relationship()
    moments = {item["id"] for item in relationship.get("shared_moments") or ()}
    commitments = {item["note_id"] for bucket in (relationship.get("commitments") or {}).values()
                   for item in bucket}
    for item in list_notes(client).get("items", []):
        kind = ("shared_moment" if item["event_id"] in moments else
                "commitment" if item["event_id"] in commitments else "note")
        records[item["event_id"]] = {"kind": kind, "sources": where(item.get("source_event_ids")),
                                             "content": {"text": words(item.get("text"))}}
    for item in client.affect_records()["records"]:
        records[item["id"]] = {"kind": "feeling", "sources": where(item.get("source_event_ids")),
                                            "content": {key: item.get(key) for key in
                                                        ("label", "valence", "intensity", "basis", "topic")}}
    for item in relationship.get("boundaries") or ():
        records[item["id"]] = {"kind": "boundary", "sources": [], "content": {
            "topic": words(item.get("topic")), "aliases": sorted(words(alias) for alias in item.get("aliases") or ())}}
    if callable(getattr(client, "persona_versions", None)):
        for item in client.persona_versions().get("versions", []):
            records[item["event_id"]] = {"kind": "persona_version", "sources": [], "content": {
                "version": item.get("version"), "card": normalize_card(item.get("card") or {}),
                "host_default": bool(item.get("host_default"))}}
    return records


def removed_records(before: dict, after: dict, counts_before: dict | None = None,
                    counts_after: dict | None = None) -> list:
    """The records present before and gone after, plus one unestablished entry per unexplained drop in a count."""
    removed = []
    for key, entry in before.items():
        if key in after:
            continue
        if entry["kind"] == "message" and not entry["sources"]:
            removed.append({"kind": "message", "established": False})  # A message with no recorded position.
            continue
        removed.append({"kind": entry["kind"], "ref": record_ref(entry["kind"], entry["sources"], entry["content"]),
                        "sources": [list(source) for source in entry["sources"]], "established": True})
    def size(value) -> int:  # world() gives counts, and boundaries as a list of topics.
        return len(value) if isinstance(value, list) else int(value or 0)

    for field, kinds in COUNTED.items():
        if counts_before is None or counts_after is None or field not in counts_before:
            continue
        dropped = size(counts_before[field]) - size(counts_after.get(field))
        explained = sum(entry["kind"] in kinds for entry in removed)
        removed += [{"kind": kinds[0], "established": False}] * max(0, dropped - explained)
    return sorted(removed, key=lambda entry: (entry["kind"], entry.get("ref", ""), not entry["established"]))


def message_records(removed: list) -> list:
    """Arm F: the messages a deletion removed, as removed_records, with the same refs as P's."""
    return sorted(({"kind": "message", "ref": record_ref("message", [position]),
                    "sources": [list(position)], "established": True} for position in removed),
                  key=lambda entry: entry["ref"])


def seeded_random_preset(seed: str, index: int, current: str | None) -> str:
    """The type a page "pick another type at random" switch gets in this harness: the product picks uniformly among
    the types other than the current one (persona_presets._switch_in, random.choice); the harness makes the same
    kind of pick reproducible from the attempt's persona seed and the action's index in PAGE_ACTIONS:

        others = [type for type in persona_presets.IDS if type != current]   (the product's order)
        others[int(sha256(json.dumps(["switch_persona", seed, index], separators=(",", ":"))), 16) % len(others)]

    and asks the product for that type by name, so a rerun of the attempt, and both arms, agree. ``current`` is the
    current type's id, or None for a card that is not a type."""
    from membrain import persona_presets

    others = [ident for ident in persona_presets.IDS if ident != current]
    digest = hashlib.sha256(json.dumps(["switch_persona", seed, index], separators=(",", ":"),
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    return others[int(digest, 16) % len(others)]


def _source_ids(memory: Memory, action: dict) -> tuple[list, dict | None]:
    """The event ids recorded for the message an action names by scenario position, or (ids, outcome) when there
    are none: not_applicable when its turn ended unrecorded (the host's own pause, or a turn the scenario leaves
    unrecorded), else a failure (a recorded turn whose message was never identified: a harness fault)."""
    position = (action["session"], action["turn"], action.get("role", "user"))
    ids = [event for event, at in memory.positions.items() if at == position]
    if ids:
        return ids, None
    if (action["session"], action["turn"]) in memory.unrecorded:
        return [], {"not_applicable": "message_not_recorded"}
    return [], {"failed": "message not found"}


def boundary_named(boundaries, topic: str) -> dict | None:
    """The boundary in force that a remove_boundary action names, by the scenario's own topic. Since format 3 the
    host saved every boundary (memory_boundary, when the user asked in conversation) in its own words, so the topic
    is matched against each boundary's topic first and then against its other words, as the product compares topics
    (whitespace collapsed, case ignored); the first in the product's order wins. None when no boundary has it: the
    host did not save one by those words, or an earlier removal took it (a relationship reset keeps boundaries since
    2026-11-18)."""
    wanted = _topic(topic)
    listed = list(boundaries or ())
    for entry in listed:
        if _topic(entry.get("topic")) == wanted:
            return entry
    for entry in listed:
        if any(_topic(alias) == wanted for alias in entry.get("aliases") or ()):
            return entry
    return None


def _apply(memory: Memory, client, action: dict, page: dict) -> dict:
    kind = action["do"]
    if kind == "switch_persona":
        from membrain import persona_presets

        preset, picked = action["preset"], False
        if preset == persona_presets.RANDOM:
            current = (client.persona_presets().get("current") or {})
            now = (current.get("preset") or {}).get("id") if current.get("kind") == "preset" else None
            preset, picked = seeded_random_preset(page.get("seed") or "", page.get("index", 0), now), True
        saved = client.switch_persona_preset(preset, made_by="user")
        return {"preset": preset, "seeded_random": picked, "version": saved.get("version"),
                "unchanged": bool(saved.get("unchanged"))}
    if kind == "delete_persona_history":
        return {"deleted_versions": client.delete_persona_history()["deleted_versions"]}
    if kind in PROPOSAL_ACTIONS:
        # The page lists open suggestions first, newest first; the action takes the position-th open one of its
        # origin (and, when the action names one, of its manner kind), by the product's own order and kind, never by
        # any text.
        origin, position = action.get("origin", "any"), action.get("position", 1)
        listed = [item for item in client.persona_proposals().get("proposals", []) if item.get("status") == "open"
                  and (origin == "any" or (item.get("kind") == "host") == (origin == "host"))
                  and ("kind" not in action or item.get("kind") == action["kind"])]
        if len(listed) < position:
            return {"not_applicable": "no_open_proposal", "open": len(listed)}
        chosen = listed[position - 1]
        decide = client.accept_persona_proposal if kind == "accept_proposal" else client.reject_persona_proposal
        result = decide(chosen["id"])
        return {"proposal": chosen["id"], "kind": chosen.get("kind"),
                "version": (result.get("persona") or result).get("version")}
    if kind == "remove_boundary":
        found = boundary_named(client.relationship()["boundaries"], action["topic"])
        if found is None:
            return {"not_applicable": "boundary_not_present"}
        client.remove_boundary(found["id"])
        return {}
    if kind == "clear_feelings":
        client.clear_affect()
        return {}
    if kind == "reset_relationship":
        client.reset_relationship()
        return {}
    if kind == "reset_mood":
        client.reset_mood()
        return {}
    if kind == "pin_mood":
        client.pin_mood(action.get("pinned", True))
        return {}
    if kind in ("delete_note_from", "delete_feeling_from"):
        ids, outcome = _source_ids(memory, action)
        if outcome:
            return outcome
        if kind == "delete_note_from":
            from membrain.notes import NOTES_CONVERSATION, list_notes

            found = [item["event_id"] for item in list_notes(client)["items"]
                     if set(item.get("source_event_ids") or ()) & set(ids)]
            if not found:
                return {"not_applicable": "no_note_from_message"}
            _forget(client, found, NOTES_CONVERSATION)
        else:
            found = [item["id"] for item in client.affect_records()["records"]
                     if set(item.get("source_event_ids") or ()) & set(ids)]
            if not found:
                return {"not_applicable": "no_feeling_from_message"}
            _forget(client, found, "membrain-affect")
        return {"deleted": len(found)}
    # delete_message: the message at this scenario position, by the identity recorded when its turn was written.
    position = (action["session"], action["turn"], action.get("role", "user"))
    before = _messages(client)
    known = [event for event, at in memory.positions.items() if at == position]
    found = [before[event] for event in known if event in before]
    if not found:
        if known:  # Recorded, and already gone: an earlier deletion's cascade removed it.
            return {"not_applicable": "message_already_removed"}
        return _source_ids(memory, action)[1]
    for item in found:
        _forget(client, [item["event_id"]], item["conversation_id"])
    # What the API actually removed, cascades included, named by scenario position so that F drops exactly the same
    # messages. A removed message without a recorded position cannot be mirrored: that fails.
    after = _messages(client)
    gone = [item for key, item in before.items() if key not in after]
    unknown = [item["event_id"] for item in gone if item["event_id"] not in memory.positions]
    done = {"deleted": len(found), "removed": sorted(
        list(memory.positions[item["event_id"]]) for item in gone if item["event_id"] in memory.positions)}
    if unknown:
        return {**done, "failed": "the deletion removed messages with no recorded position",
                "unknown_removed": len(unknown)}
    return done


def apply_page_action(memory: Memory, action: dict, page: dict | None = None) -> dict:
    """One page action through the API, as the memory page performs it, in arm P. Returns what it did: a result with
    ``not_applicable`` (a NOT_APPLICABLE code) when its target does not exist, with ``failed`` on a real fault (the
    service refused it, or it raised: ``code`` service_refused or exception), else what it changed. ``page`` gives
    the attempt's persona ``seed`` and the action's ``index`` in PAGE_ACTIONS (a seeded random switch)."""
    import httpx

    page = page if isinstance(page, dict) else {}
    with memory.client() as client:
        try:
            return _apply(memory, client, action, page)
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if action["do"] in LIMITED and 400 <= status < 500 and _error_code(error.response) == "validation_failed":
                # The page's limits were reached through what the host saved (agreements that no longer fit beside
                # the type's card): the plugin path's behaviour, scored.
                return {"not_applicable": "page_refused", "status": status}
            return {"failed": "the service refused the action", "code": "service_refused", "status": status}
        except Exception as error:  # noqa: BLE001 - recorded by class as a fault; the run is invalid.
            return {"failed": "the action raised", "code": "exception", "error": type(error).__name__}


def _error_code(response) -> str | None:
    """The service's error code of a refused request ({"error": {"code": ...}}), or None; never its message."""
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return None
    return error.get("code") if isinstance(error, dict) and isinstance(error.get("code"), str) else None


def page_status(result: dict) -> tuple[str, str | None]:
    """A page action's status and reason code from its result: done, not_applicable (a NOT_APPLICABLE code) or
    failed (a FAILURE_CODES code)."""
    if result.get("failed"):
        return "failed", failure_code(result)
    if result.get("not_applicable"):
        reason = result["not_applicable"]
        return ("not_applicable", reason) if reason in NOT_APPLICABLE else ("failed", "not_found")
    return "done", None


def action_detail(action: dict) -> dict:
    """What page-actions.jsonl keeps of an action: its arguments, except a card (its hash instead; only format 2's
    set_persona carried one)."""
    detail = {key: value for key, value in action.items() if key not in ("do", "card")}
    if "card" in action:
        detail["card_sha256"] = hashlib.sha256(json.dumps(action["card"], sort_keys=True, ensure_ascii=False,
                                                          separators=(",", ":")).encode("utf-8")).hexdigest()
    return detail


def persona_turn(version: int, block: str) -> dict:
    """The content-free identity of the persona in effect at a turn (PERSONA_TURN_FORMAT): its version (0 for none)
    and the sha256 of its rendered block's UTF-8 (None for none)."""
    return {"format": PERSONA_TURN_FORMAT, "version": int(version or 0) if block else 0,
            "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest() if block else None}


PAGE_LINE_PREFIX = "Memory page changes the user made (not part of the conversation above): "


class Reference:
    """Arm F's view of the same world: its earlier history and the page-only settings it is told about. Its persona
    is P's, turn by turn (p_persona), never a card of its own."""

    def __init__(self):
        self.history: list[tuple[tuple, dict]] = []  # ((session, turn, role), message)
        self.deleted: set[tuple] = set()  # Every position a page deletion removed, in any session.
        # Page-only changes, from the scenario's own words: boundaries removed on the page, by topic (in the order
        # first removed), each with the date of its latest removal. The boundaries themselves the host saved when
        # the user asked in conversation, which F's history shows.
        self.removed_boundaries: dict[str, tuple[str, str | None]] = {}
        self.reset_on = self.cleared_on = None
        self.pinned = False

    def apply(self, action: dict, outcome: dict | None = None, today: datetime.date | None = None) -> dict:
        """One page action as P's outcome says it went (its page-actions.jsonl record): a not-applicable action
        changes nothing here either."""
        kind = action["do"]
        if outcome is not None and outcome.get("status") == "not_applicable":
            if kind == "delete_message" and outcome.get("reason") == "message_not_recorded":
                # P never recorded the message (off the record, or a turn a pause left unrecorded), so P had nothing
                # to delete; the user still deleted it, so F's history loses it too. The one asymmetry validity
                # accepts: F's record names it in reference_removed, and its removed_records stay empty.
                position = (action["session"], action["turn"], action.get("role", "user"))
                self.deleted.add(position)
                self.history = [(entry, message) for entry, message in self.history if entry != position]
                return {"not_applicable": outcome.get("reason"), "reference_removed": [list(position)]}
            return {"not_applicable": outcome.get("reason")}
        day = today.isoformat() if today else None
        if kind == "delete_message":
            # Exactly the messages the product removed in P (``removed``: [session, turn, role] each).
            removed = {tuple(entry) for entry in action["removed"]}
            self.deleted |= removed  # Also kept out when the session in progress is added to the history.
            before = len(self.history)
            self.history = [(entry, message) for entry, message in self.history if entry not in removed]
            return {"deleted": before - len(self.history), "removed": sorted(map(list, removed))}
        if kind == "remove_boundary":  # A topic removed again keeps its place and first words, with the new date.
            key = _topic(action["topic"])
            words = self.removed_boundaries.get(key, (" ".join(action["topic"].split()), None))[0]
            self.removed_boundaries[key] = (words, day)
        elif kind == "reset_relationship":  # Boundaries stay in force (relationship.py, since 2026-11-18).
            self.reset_on = day
        elif kind == "clear_feelings":
            self.cleared_on = day
        elif kind == "pin_mood":
            self.pinned = action.get("pinned", True)
        return {}

    def page_line(self) -> str | None:
        """What the page has done so far that the conversation history does not show, as one line of fixed format
        (PAGE_LINE_FORMAT 2), or None when there is nothing: PAGE_LINE_PREFIX, then the items present, in this order,
        joined by "; " and ended with ".":
          boundaries removed: "<topic>" on YYYY-MM-DD, ...   a boundary the user asked for in conversation and then
                                                             removed on the page (the latest removal of each topic)
          relationship reset on YYYY-MM-DD                   the latest reset
          feelings cleared on YYYY-MM-DD                     the latest "clear feelings"
          simulated mood held at its baseline                the mood pin
        Topics are the scenario's own words, JSON-quoted; nothing else is free text. Format 1 (until 2026-11-18) also
        listed boundaries added on the page, the support style and a familiarity limit, which the page no longer
        offers."""
        def quoted(text) -> str:
            return json.dumps(text, ensure_ascii=False)

        items = []
        if self.removed_boundaries:
            items.append("boundaries removed: " + ", ".join(
                quoted(topic) + (f" on {day}" if day else "") for topic, day in self.removed_boundaries.values()))
        if self.reset_on:
            items.append(f"relationship reset on {self.reset_on}")
        if self.cleared_on:
            items.append(f"feelings cleared on {self.cleared_on}")
        if self.pinned:
            items.append("simulated mood held at its baseline")
        return PAGE_LINE_PREFIX + "; ".join(items) + "." if items else None

    def end_session(self, current: list) -> None:
        """Add the finished session to the history, without the messages a page deletion removed during it. Within
        the session the host's own transcript kept them, as a host app does."""
        self.history += [(entry, message) for entry, message in current if entry not in self.deleted]

    def contains(self, keys) -> int:
        keys = {tuple(key) for key in keys}
        return sum(entry in keys for entry, _ in self.history)

    def summary(self) -> dict:
        return {"history_items": len(self.history)}


def _p_run(out: Path) -> Path | None:
    """Arm P's run directory beside F's (KEY-P beside KEY-F)."""
    return out.parent / (out.name[:-1] + "P") if out.name.endswith("F") else None


def _wait_for(out: Path, read, what: str, timeout: float):
    """Read something of P's run for F, waiting while P's files are still being written (the run script runs P to the
    end before F starts, so the wait is normally none)."""
    deadline = time.monotonic() + timeout
    while True:
        check_billing()
        found = read(_p_run(out)) if _p_run(out) is not None else None
        if found is not None:
            return found
        if time.monotonic() >= deadline:
            raise SystemExit(f"P never recorded {what} F must mirror")
        time.sleep(min(2, max(0.0, deadline - time.monotonic())))


def _jsonl(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def p_page_action(out: Path, index: int, action: dict, timeout: float = 3600) -> dict:
    """For F: P's page-actions.jsonl record of PAGE_ACTIONS[index]. It must be this scenario's action, and not a
    failed one (P's run would then be invalid and F is never run after it)."""
    def read(run):
        return next((entry for entry in _jsonl(run / "page-actions.jsonl") if entry.get("index") == index), None)

    entry = _wait_for(out, read, "the page action", timeout)
    if (entry.get("action") != action["do"] or entry.get("detail") != action_detail(action)
            or entry.get("format") != PAGE_RECORD_FORMAT):
        raise SystemExit("P's page actions are not this scenario's")
    if entry.get("status") not in ("done", "not_applicable"):
        raise SystemExit("P could not apply a page action F must mirror")
    if action["do"] in DELETES_MESSAGES and entry["status"] == "done" and "removed" not in entry.get("result", {}):
        raise SystemExit("P could not apply the deletion F must mirror")
    return entry


def p_persona(out: Path, scenario: str, session: str, turn: int, cache: dict, timeout: float = 3600) -> tuple:
    """For F: the persona block P's host was given at the start of this turn, and its persona_turn identity, from
    P's own results."""
    def read(run):
        if (session, turn) not in cache:
            for row in _jsonl(run / f"results_{scenario}_P.jsonl"):
                cache[(row.get("session"), row.get("turn"))] = row
        return cache.get((session, turn))

    row = _wait_for(out, read, "the persona of a turn", timeout)
    if not isinstance(row.get("persona_turn"), dict) or not isinstance(row.get("persona_block"), str):
        raise SystemExit("P's results record no persona for a turn F must mirror")
    if persona_turn(row["persona_turn"].get("version"), row["persona_block"]) != row["persona_turn"]:
        raise SystemExit("P's recorded persona block does not match its identity")
    return row["persona_block"], row["persona_turn"]


def p_persona_record(out: Path, timeout: float = 3600) -> dict:
    """For F: P's persona.json (the attempt's seeded starting type, which F's own draw must equal)."""
    def read(run):
        path = run / "persona.json"
        try:
            return json.loads(path.read_text()) if path.exists() else None
        except ValueError:
            return None

    return _wait_for(out, read, "its starting persona", timeout)


# Recording ----------------------------------------------------------------------------------------------------------

TIMED_PAUSE_REFUSED = ("Timed pauses are unavailable in this evaluation. Pause without hours (for the rest of this "
                       "conversation) and resume when the user asks.")


MEMORY_UNAVAILABLE = "memBrain is starting or unavailable"  # The session notice of a hook that found no service.


def tool_error(result: str) -> bool:
    """Whether a tool's answer to the host is an error (the host sees it, as it would through MCP)."""
    try:
        value = json.loads(result)
    except (TypeError, ValueError):
        return False
    return isinstance(value, dict) and "error" in value


def count_tool_error(out: Path, counts: dict, name: str) -> None:
    """Tool errors are the host's or the service's, not the harness's: counted by tool name only, in
    tool-errors.json, which validity reports without refusing (a host passing bad arguments is product behaviour;
    stopping a paid run on it would lose the attempt)."""
    counts[name] = counts.get(name, 0) + 1
    (out / "tool-errors.json").write_text(json.dumps(counts, sort_keys=True))


def call_tool(memory: Memory, server, name: str, arguments, out: Path, session: str, index: int) -> str:
    """One tool call of the host model. A timed pause is refused: its end is wall-clock time (host.pause), so on the
    scenario clock it would span scenario days, or nothing, depending on how fast the run goes. The refusal is the
    tool's answer to the host, as any tool error is, and the run counts it with the other tool errors
    (tool-errors.json); it is not a harness event and never stops the run (since 2026-11-17). Nothing was paused, so
    the turn is recorded as usual."""
    if name == "memory_pause" and isinstance(arguments, dict) and arguments.get("hours") is not None:
        return json.dumps({"error": TIMED_PAUSE_REFUSED})
    return memory.call(server, name, arguments)


HOST_PAUSE_KIND = "unrecorded_by_host_pause"  # The name dates from when only the host's own pause counted.


def host_pause_left_unrecorded(out: Path, session: str, turn: int, where: str) -> None:
    """A turn the scenario meant to be recorded, left unrecorded while a pause was in force: the host's own accepted
    pause made in that turn, or a pause the product held for this conversation as the turn began, whoever made it (the
    host's tool, or the product's own prompt hook on the user's words). That is the plugin path's behaviour, scored
    with the arm, not a harness event, so the run goes on. One line in host-pauses.jsonl with only the time, the
    position and the kind (validity and diagnose report it, never refusing); the log names the position by index,
    never the session id or any text."""
    with (out / "host-pauses.jsonl").open("a") as stream:
        stream.write(json.dumps({"time": time.time(), "session": session, "turn": turn, "kind": HOST_PAUSE_KIND})
                     + "\n")
    log("turn left unrecorded while recording was paused (scored with the arm):", where)


def intended_unrecorded(module) -> set:
    """Arm P's turns the scenario means to leave unrecorded: those EXPECT_RECORDING_P marks False, and each turn from
    an untimed memory_pause that STUB_HOST scripts up to (not including) the memory_resume that ends it in the same
    session. The resume turn itself is recorded (the user asked for it)."""
    intended = {(session, turn) for session, turn, expected in getattr(module, "EXPECT_RECORDING_P", ())
                if expected is False}
    script = getattr(module, "STUB_HOST", None) or {}
    for session, turns in module.SESSIONS_LONG:
        paused_at = None
        for turn in range(len(turns)):
            tools = {step.get("tool"): step for step in script.get((session, turn), ())}
            if "memory_resume" in tools and paused_at is not None:
                intended |= {(session, at) for at in range(paused_at, turn)}
                paused_at = None
            pause = tools.get("memory_pause")
            if pause is not None and (pause.get("arguments") or {}).get("hours") is None:
                paused_at = turn
    return intended


# The fixed persona -------------------------------------------------------------------------------------------------

def persona_module():
    return load_named("acceptance_persona_for_harness", str(Path(__file__).with_name("acceptance_persona.py")))


def persona_seed() -> tuple[str, str]:
    """The seed of the attempt's personality type and where it came from. A live run draws from its attempt id
    (C5_ATTEMPT_ID); a C5_PERSONA_SEED given beside it (the driver passes the manifest's) must be the same. A dry run
    takes C5_PERSONA_SEED, else the attempt id, else the fixed practice seed."""
    given, attempt = os.environ.get("C5_PERSONA_SEED") or None, os.environ.get("C5_ATTEMPT_ID") or None
    if not STUB:
        if not attempt:
            raise SystemExit("A live run draws its persona from C5_ATTEMPT_ID.")
        if given is not None and given != attempt:
            raise SystemExit("C5_PERSONA_SEED differs from the attempt id it must be.")
        return attempt, "attempt_id"
    if given:
        return given, "C5_PERSONA_SEED"
    if attempt:
        return attempt, "attempt_id"
    return persona_module().STUB_SEED, "practice_default"


def fixed_persona(module) -> dict:
    """The persona both arms start from: the seeded type, in every run (R4 and C5, live or dry). Refuses a scenario
    PERSONA card (a scenario changes the persona as a user does: in conversation or with a page action), a copy of
    the type table that differs from the product's, and a C5_PERSONA_PRESET (the manifest's draw, passed by the
    driver) that is not the draw of the seed."""
    from membrain import persona_presets
    from membrain.persona import normalize_card

    def digest(card) -> str:
        return hashlib.sha256(json.dumps(normalize_card(card), sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()

    if getattr(module, "PERSONA", None):
        raise SystemExit("every run starts from the attempt's seeded type: a scenario PERSONA card is refused "
                         "(change the persona in conversation or with a page action)")
    drawing = persona_module()
    if tuple(drawing.IDS) != tuple(persona_presets.IDS):
        raise SystemExit("acceptance_persona.IDS differs from the product's personality types")
    seed, source = persona_seed()
    preset = drawing.draw(seed)
    expected = os.environ.get("C5_PERSONA_PRESET")
    if expected and expected != preset:
        raise SystemExit("C5_PERSONA_PRESET is not the draw of the persona seed")
    card = persona_presets.card(preset)
    return {"source": "seeded", "seed": seed, "seed_source": source, "preset": preset, "card": card,
            "card_sha256": digest(card), "rule": drawing.RULE}


def set_fixed_persona(memory: "Memory", persona: dict) -> dict:
    """Arm P, before the first session: save the persona as the product saves it. A seeded type is picked the way a
    user picks one (a version made by the host with action "preset"), so the brain has a persona record and the
    product's random first assignment, with its one-time announcement, never runs."""
    from membrain.persona import normalize_card

    with memory.client() as client:
        saved = client.reset_persona(made_by="host", preset=persona["preset"])
        current = client.persona()
    if normalize_card(current.get("card") or {}) != normalize_card(persona["card"]):
        raise SystemExit("the persona saved in P is not the attempt's persona")
    return {"version": saved.get("version") or current.get("version")}


# The run --------------------------------------------------------------------------------------------------------------

def load(path: str):
    return load_named("scenario", path)


def load_named(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_scenario(path: str):
    """The scenario a run uses. A live run reads it without running it (scenario_literals.py: literal assignments
    only), so a held-out scenario's text can never execute code in the paid process; a dry run loads its public
    practice scenario as a module."""
    if STUB:
        return load(path)
    literals = load_named("scenario_literals_for_harness", str(Path(__file__).with_name("scenario_literals.py")))
    try:
        return literals.read(path)
    except literals.NotLiteral as error:
        raise SystemExit(f"a live scenario must hold only literal assignments ({error.code})") from None


def run(arm: str, scenario_path: str, out: Path) -> None:
    global BILLING
    if arm not in ARMS:
        raise SystemExit(f"arms: {', '.join(ARMS)} (the proxy-with-extraction arm E no longer exists)")
    module = load_scenario(scenario_path)
    sessions = module.SESSIONS_LONG
    scenario = Path(scenario_path).stem
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"results_{scenario}_{arm}.jsonl"
    for existing in (path, out / "host-rounds.jsonl", out / "persona.json", out / INTERRUPTIONS):
        if existing.exists():
            raise SystemExit(f"{existing} exists: a run is never resumed")
    year = getattr(module, "YEAR", YEAR)
    starts = [session_start(turns[0], year) for _, turns in sessions]
    if starts != sorted(starts):
        raise SystemExit("sessions must be in time order")
    actions = check_actions(module)
    intended = intended_unrecorded(module) if arm == "P" else set()
    os.environ["TZ"] = "UTC"
    time.tzset()
    for name in ("CLAUDE_PLUGIN_DATA", "PLUGIN_DATA"):  # The plugin hooks would import a real host's queue.
        os.environ.pop(name, None)
    stub_host = None
    if STUB:
        if not hasattr(module, "STUB_HOST"):
            raise SystemExit("the dry run needs a practice scenario with stub scripts")
        refuse_network(out)
        stub_host = StubHost(module.STUB_HOST)
    if not STUB:
        check_live_environment()
    persona = fixed_persona(module)
    BILLING = None if STUB else billing_transport()
    host = Host(cap=sum(len(turns) for _, turns in sessions) * 5,
                transport=httpx.MockTransport(stub_host) if stub_host else BILLING, guard=BILLING, out=out)
    memory = reference = None
    if arm == "P":
        cache = os.environ.get("MEMBRAIN_MODEL_CACHE")
        ports = tuple(map(int, os.environ["MEMBRAIN_PORTS"].split(","))) if os.environ.get("MEMBRAIN_PORTS") else None
        memory = Memory(out / f"brain-{scenario}-{arm}", Path(cache) if cache else None, ports, starts[0])
        saved = set_fixed_persona(memory, persona)
    else:
        reference = Reference()
        started = p_persona_record(out)  # F starts from the type P saved, which must be the same draw.
        if any(started.get(key) != persona.get(key) for key in ("source", "seed", "preset", "card_sha256")):
            raise SystemExit("P's starting persona is not the attempt's seeded type F draws")
        saved = {"version": started.get("version")}
    (out / "persona.json").write_text(json.dumps(
        {"arm": arm, **{key: persona.get(key) for key in ("source", "seed", "seed_source", "preset", "card_sha256",
                                                          "rule")}, "version": saved["version"]}, sort_keys=True))
    proposals = proposals_supported()
    log(arm, scenario, "start", "stub" if STUB else "live", "proposals" if proposals else "no proposals (P2 absent)")
    log(arm, scenario, "persona", persona["source"], persona.get("preset"), "seed from", persona.get("seed_source"))

    tool_errors: dict[str, int] = {}
    session_ids = [session for session, _ in sessions]
    p_rows: dict = {}  # Arm F: P's result rows, read as F reaches each turn (p_persona).

    def where(session, turn) -> str:
        return f"session {session_ids.index(session) + 1} of {len(session_ids)}, message {turn + 1}"

    def page_actions(session, before, today):
        for index, (at_session, at_turn, action) in enumerate(actions):
            if (at_session, at_turn) != (session, before):
                continue
            if action["do"] in PROPOSAL_ACTIONS and not proposals:
                # Dry run on a runtime without P2: skipped in every arm alike, so the arms still see one world.
                harness_event(out, "page_action_unsupported", action=action["do"], session=session, turn=before)
                continue
            # An action limited to some arms applies to F when it applies to P, the arm F is the reference for.
            if action.get("arms") and "P" not in action["arms"]:
                continue
            record = {"format": PAGE_RECORD_FORMAT, "index": index, "session": session, "before_turn": before,
                      "action": action["do"], "detail": action_detail(action)}
            if memory is not None:
                with memory.client() as client:
                    record["before"], held = world(client), layer_records(client, memory.positions)
                result = apply_page_action(memory, action, {"seed": persona["seed"], "index": index})
                with memory.client() as client:
                    record["after"], kept = world(client), layer_records(client, memory.positions)
                removed = removed_records(held, kept, record["before"], record["after"])
                result["removed_records"] = removed
                result["removed_records_complete"] = all(entry["established"] for entry in removed)
                record["time"] = memory.now()
            else:
                outcome = p_page_action(out, index, action)
                mirrored = action["do"] in DELETES_MESSAGES and outcome["status"] == "done"
                if mirrored:
                    action = {**action, "removed": outcome["result"]["removed"]}
                record["before"] = reference.summary()
                result = reference.apply(action, outcome, today)
                result["removed_records"] = message_records(result.get("removed", []))
                result["removed_records_complete"] = True  # F's only records are its messages.
                record["after"] = reference.summary()
                if mirrored or result.get("reference_removed"):
                    record["after"]["removed_still_in_history"] = reference.contains(
                        action["removed"] if mirrored else result["reference_removed"])
            record["status"], reason = page_status(result)
            if reason is not None:
                record["reason"] = reason
            record["result"] = result
            with (out / "page-actions.jsonl").open("a") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            log("page action", index + 1, "of", len(actions), action["do"], "before", where(session, before) + ":",
                record["status"], reason or "")
            if record["status"] == "failed":
                harness_event(out, "page_action_failed", action=action["do"], session=session, turn=before,
                              reason=failure_code(result))

    for (session, turns), start in zip(sessions, starts):
        today = start.date()
        if memory is not None:
            effective = memory.clock.advance(memory.directory, start, run=memory.directory.name)
            if effective > start and session != sessions[0][0]:  # The first was set when the profile was made.
                harness_event(out, "clock_already_past", session=session,
                              behind_seconds=int((effective - start).total_seconds()))
        date_line = f"Today's date: {today.isoformat()} ({today.strftime('%A')})."
        page_actions(session, 0, today)
        session_context, client, server, schemas, instructions = None, None, None, None, None
        if memory is not None:
            memory.wait_until_indexed()
            session_context = memory.session_start(session)
            if MEMORY_UNAVAILABLE in (session_context or ""):
                # The hook found no ready service: P would run this session without memory. That degrades the run.
                harness_event(out, "memory_unavailable", session=session)
            # One MCP server for the whole session, as a host keeps one connection.
            client, server, schemas, instructions = memory.tools()
            if not (out / "tools.json").exists():
                (out / "tools.json").write_text(json.dumps({
                    "offered": [schema["function"]["name"] for schema in schemas],
                    "schema_chars": len(json.dumps(schemas, ensure_ascii=False)),
                    "server_instructions_chars": len(instructions),
                    "server_instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
                    "skill_in_prompt": False, "host": HOST_NAME}, sort_keys=True))
        if stub_host:
            from membrain import host as product_host

            stub_host.instructions = instructions or product_host.server_instructions()
        offered_names = {schema["function"]["name"] for schema in schemas or ()}  # A log names only these tools.
        current: list[tuple[tuple, dict]] = []
        try:
            for index, text in enumerate(turns):
                check_billing()
                if index:
                    page_actions(session, index, today)
                if stub_host:
                    stub_host.key, stub_host.text = (session, index), text
                system, prompt_context = module.HOST + "\n\n" + date_line, None
                page_line = None
                # A pause holds this turn when the product's own pause state says recording is paused for this
                # conversation as the turn begins (read before the prompt hook), whoever made it: the host's tool, or
                # the product's hook on the user's words in an earlier turn (since 2026-11-17, for R4 and C5 alike).
                paused_at_start = memory is not None and memory.paused(session)
                paused_here = brought_back = False
                if memory is not None:
                    prompt_context = memory.user_prompt(session, index, text)
                    # What an MCP host gives its model without being asked: the MCP server's instructions, then the
                    # session's context (the hook's notice and memory). The skill body is not given: a host loads it
                    # only when the model opens the skill, which the 2026-11-13 trial never saw in 86 turns.
                    system += "\n\n" + instructions + ("\n\n" + session_context if session_context else "")
                    # The persona in effect as this turn starts, as the product renders it (after the prompt hook,
                    # which refreshes the host's snapshot when it changed): F is given exactly this block.
                    persona_block, identity = memory.persona_in_effect(session)
                else:
                    # P's persona at the start of the same turn, then what the page did that the history cannot show.
                    persona_block, identity = p_persona(out, scenario, session, index, p_rows)
                    page_line = reference.page_line()
                    system += "".join("\n\n" + part for part in (persona_block, page_line) if part)
                user_content = (prompt_context + "\n\n" if prompt_context else "") + text
                prior = [message for _, message in reference.history] if reference is not None else []
                messages = [{"role": "system", "content": system}, *prior, *(message for _, message in current),
                            {"role": "user", "content": user_content}]
                shown = bool(persona_block) and any(persona_block in str(item.get("content") or "")
                                                    for item in messages)
                first = len(messages) - 1
                usage, started, tool_calls = {}, time.monotonic(), []
                scenario_time = memory.now() if memory is not None else start.isoformat().replace("+00:00", "Z")
                for round_ in range(4):  # At most three tool rounds, then a final answer without tools.
                    offer = schemas if schemas and len(tool_calls) < 6 and round_ < 3 else None
                    message, call_usage = host.call(messages, offer, at={
                        "session": session, "turn": index, "round": round_, "where": where(session, index)})
                    with (out / "host-rounds.jsonl").open("a") as stream:
                        stream.write(json.dumps({"arm": arm, "scenario": scenario, "session": session,
                                                 "turn": index, "round": round_, "usage": call_usage,
                                                 "message": {k: v for k, v in message.items()
                                                             if k != "reasoning_content"}}, ensure_ascii=False) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    add_usage(usage, call_usage)
                    calls = message.get("tool_calls") or []
                    if not calls:
                        break
                    check_billing()
                    messages.append({k: v for k, v in message.items()
                                     if k in ("role", "content", "tool_calls", "reasoning_content")})
                    for call in calls:
                        try:
                            arguments = json.loads(call["function"]["arguments"] or "{}")
                        except ValueError:
                            arguments = {}
                        result = call_tool(memory, server, call["function"]["name"], arguments, out, session, index)
                        if tool_error(result):
                            count_tool_error(out, tool_errors, call["function"]["name"])
                        elif memory is not None and call["function"]["name"] == "memory_pause":
                            # Accepted (a refused or timed pause answers with an error and changes nothing). The
                            # current exchange is never stored after it, whatever follows in this turn.
                            paused_here = True
                        elif memory is not None and call["function"]["name"] == "memory_resume":
                            # A resume naming this conversation brings back a turn that began paused; any other
                            # resume leaves the turn already in progress unrecorded (the tool's own description).
                            brought_back = brought_back or (isinstance(arguments, dict)
                                                            and arguments.get("session_id") == session)
                        tool_calls.append({"name": call["function"]["name"], "arguments": arguments,
                                           "result": result[:2000]})
                        messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
                written = [item.get("content") for item in messages[first + 1:]
                           if item.get("role") == "assistant" and item.get("content")]
                reply = "\n\n".join([*written, message.get("content") or ""]).strip()
                stopping: list[str] = []
                halted, recorded = None, False
                # The reply is paid for: its row is written before any stop.
                with deferred_stop(stopping), bookkeeping_errors(out, session, index, stopping) as errors:
                    # A stop of the shared ledger during this turn's host call: then nothing more is recorded.
                    halted = billing_halt(stopping)
                    if halted is None and memory is not None:
                        recorded = memory.stop(session, index, text, reply)
                        memory.record_turn(session, index, recorded=recorded)
                        if not recorded and (session, index) not in intended:
                            if paused_here or (paused_at_start and not brought_back):
                                # The plugin path's own behaviour: scored with the arm, not a harness fault. Only a
                                # turn left unrecorded with no pause in force is turn_not_recorded.
                                host_pause_left_unrecorded(out, session, index, where(session, index))
                            else:
                                harness_event(out, "turn_not_recorded", session=session, turn=index)
                transcript = [{k: v for k, v in item.items() if k != "reasoning_content"} for item in messages[first:]]
                transcript.append({"role": "assistant", "content": message.get("content") or ""})
                row = {"arm": arm, "scenario": scenario, "session": session, "turn": index, "date": today.isoformat(),
                       "scenario_time": scenario_time, "input": text, "reply": reply, "usage": usage,
                       "seconds": round(time.monotonic() - started, 1), "host_user_content": user_content,
                       "session_context": session_context or "", "prompt_context_chars": len(prompt_context or ""),
                       "tool_calls": tool_calls, "transcript": transcript, "persona_turn": identity}
                if reference is not None:
                    row["reference_persona"] = persona_block or ""
                    row["reference_page_line"] = page_line or ""
                    row["reference_history_items"] = len(prior)
                if memory is not None:
                    row["persona_block"] = persona_block or ""
                    row["persona_shown_to_host"] = shown if persona_block else None
                    row["recorded"] = None if errors else recorded
                if stopping:
                    row["stopped_after"] = stopping[0]
                with path.open("a") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                log(arm, scenario, where(session, index), usage.get("total_tokens"),
                    "tools:", [call["name"] if call["name"] in offered_names else "other" for call in tool_calls])
                if errors or halted is not None:
                    raise errors[0] if errors else halted
                if stopping:
                    stop_run(stopping[0])
                if reference is not None:  # F's history holds the user's words, not a memory block, and the reply.
                    current += [((session, index, "user"), {"role": "user", "content": text}),
                                ((session, index, "assistant"), {"role": "assistant", "content": reply})]
                else:
                    current += [((session, index, "turn"), item) for item in transcript]
        finally:
            if client is not None:
                client.close()
        if reference is not None:
            reference.end_session(current)
    if stub_host is not None:
        log(arm, scenario, "stub consolidation batches answered", stub_host.consolidations)
    stop_started()
    log(arm, scenario, "finished")


def stop_started() -> None:
    from membrain import desktop

    while STARTED:
        desktop.stop(STARTED.pop())


STOP_REASON = re.compile(r"[a-z][a-z0-9_]{0,39}")


def stop_reason(arguments: list) -> str:
    """``--stop`` takes an optional ``--reason CODE``; without it the reason is ``arm_failed``. The ledger keeps the
    first reason it was given. A malformed reason is refused before the ledger is opened."""
    if not arguments:
        return "arm_failed"
    if len(arguments) == 2 and arguments[0] == "--reason" and STOP_REASON.fullmatch(arguments[1]):
        return arguments[1]
    raise SystemExit("usage: c5-harness.py --stop [--reason CODE], CODE matching [a-z][a-z0-9_]{0,39}")


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def cleanup(run_dir: Path, wait: float = 30) -> dict:
    """After an arm, whatever its result: stop every installation this harness made in RUN_DIR (``brain-*`` with a
    profile and the harness's disposable marker, so nothing else is ever stopped), then check that their ports are
    closed. Returns counts and ports only; ``ok`` is false when a stop failed or a port is still open."""
    from membrain import desktop, evaluation_clock
    from membrain.local_profile import load_profile

    run_dir = Path(run_dir).resolve()
    report = {"run_dir": run_dir.name, "profiles": 0, "stopped": 0, "failed": [], "ports_open": []}
    for directory in sorted(run_dir.glob("brain-*")):
        if directory.is_symlink():  # Never follow a link out of the run directory.
            report["failed"].append({"profile": directory.name, "error": "symlink"})
            continue
        marker = directory / evaluation_clock.MARKER
        if not directory.is_dir() or not marker.exists():
            continue  # Not a disposable evaluation profile this harness made.
        try:
            document = json.loads(marker.read_text()) if not marker.is_symlink() else None
            installation = evaluation_clock._installation_id(directory)
        except (OSError, ValueError):
            document, installation = None, None
        if (not isinstance(document, dict) or document.get("purpose") != evaluation_clock.PURPOSE
                or installation is None or document.get("installation_id") != installation):
            report["failed"].append({"profile": directory.name, "error": "not_this_installation"})
            continue
        report["profiles"] += 1
        try:
            profile = load_profile(directory)
            ports = [profile.api_port, profile.database_port]
        except Exception as error:  # noqa: BLE001 - reported by class, never stopped blindly.
            report["failed"].append({"profile": directory.name, "error": type(error).__name__})
            continue
        try:
            desktop.stop(directory)
            report["stopped"] += 1
        except Exception as error:  # noqa: BLE001
            report["failed"].append({"profile": directory.name, "error": type(error).__name__})
        deadline = time.monotonic() + wait
        while any(_port_open(port) for port in ports) and time.monotonic() < deadline:
            time.sleep(1)
        report["ports_open"] += [port for port in ports if _port_open(port)]
    report["ok"] = not report["failed"] and not report["ports_open"]
    return report


def interrupted(signum, frame):
    """SIGTERM: block the ledger, then exit. Not while this process is inside a guarded section (waiting for the
    ledger lock or holding it): stop() would take the lock again on another descriptor and wait for this process
    itself. Then the handler only exits; the request in flight keeps its whole reservation, and the run script's
    ``--stop`` (run on any nonzero arm exit, from another process) blocks the ledger."""
    try:
        if BILLING is not None and not billing_module().lock_held():
            BILLING.stop("arm_interrupted")
    finally:
        raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    if sys.argv[1:2] == ["--stop"]:
        reason = stop_reason(sys.argv[2:])
        guard = billing_transport(allow_stopped=True)
        guard.stop(reason)
        guard.close()
        raise SystemExit(0)
    if sys.argv[1:2] == ["--cleanup"]:
        if len(sys.argv) != 3:
            raise SystemExit("usage: c5-harness.py --cleanup RUN_DIR")
        result = cleanup(Path(sys.argv[2]))
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result["ok"] else 1)
    if sys.argv[1:] == ["--preflight"]:
        check_preflight_environment()
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
