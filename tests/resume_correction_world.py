"""Test helper: the "said last week, corrected midway, continue today" scenario on a real local installation.

Played through the Claude Code plugin's own entry points (``plugin.session_start``, ``plugin.user_prompt``,
``plugin.stop`` and the plugin's MCP server, created as ``membrain plugin mcp`` creates it) on the scenario clock of a
disposable evaluation profile (``evaluations/c5-harness.py``'s ``Memory``), with no model call of any kind. A test
plays the host's part in one of two ways:

- ``diligent``: it does what the server instructions and the session notices ask. It saves the day-1 decision as a
  note, replaces it on day 3 with ``replaces``, notes a preference once and a fact it inferred, indexes earlier
  messages when the session notice asks for it, and searches with ``memory_recall`` on day 8.
- ``lazy``: it calls no memBrain tool at all. Only the hooks record the conversation.

``busy`` adds ordinary project talk on days 4, 6 and 7, enough that a new session's history block no longer holds
every earlier message, as it would not after a working week. ``model`` copies the local embedding model into the
installation (``MEMBRAIN_TEST_EMBEDDING_MODEL``), as the plugin downloads it after the first start; without it recall is
by keywords only, as on a fresh installation before the download finishes.

Everything the host receives on day 8 before it answers is kept verbatim in ``World.captures``. With
``RESUME_CORRECTION_DUMP`` set to a directory, each world also writes its captures there as JSON (for the report).
All data is fictional.
"""
from __future__ import annotations

import asyncio
import datetime
import importlib.util
import json
import os
import re
import socket
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from membrain import embedded_database, evaluation_clock, host, plugin
from membrain.notes import list_notes

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.environ.get("MEMBRAIN_TEST_EMBEDDING_MODEL")
UTC = datetime.UTC


def _load_harness():
    spec = importlib.util.spec_from_file_location("c5_harness_resume", ROOT / "evaluations" / "c5-harness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load_harness()

# The scenario's days (Monday 2 November 2026 is day 1).
DAY = {1: datetime.datetime(2026, 11, 2, 10, 0, tzinfo=UTC), 3: datetime.datetime(2026, 11, 4, 15, 0, tzinfo=UTC),
       4: datetime.datetime(2026, 11, 5, 10, 0, tzinfo=UTC), 5: datetime.datetime(2026, 11, 6, 11, 0, tzinfo=UTC),
       6: datetime.datetime(2026, 11, 7, 10, 0, tzinfo=UTC), 7: datetime.datetime(2026, 11, 8, 10, 0, tzinfo=UTC),
       8: datetime.datetime(2026, 11, 9, 9, 30, tzinfo=UTC)}
DATE = {number: moment.date().isoformat() for number, moment in DAY.items()}

DECISION = ("Let's get the Tidepool backend going today. Decision: we'll use PostgreSQL as the database for the "
            "project.")
CORRECTION = "Quick correction on the database: only the server uses PostgreSQL; local stays SQLite."
PNPM = {1: "For the frontend packages I prefer pnpm over npm.", 3: "And again, pnpm please, not npm.",
        5: "As always, use pnpm for everything in the frontend."}
DISK = "Ugh, the Docker build ate another 20 GB and my laptop is almost full again."

# (session, day, [(user message, reply)]): the scenario's own conversations, oldest first.
CONVERSATIONS = [
    ("tidepool-day1", 1, [
        (DECISION, "Sounds good: PostgreSQL for Tidepool. I'll start with a connection config and a first migration."),
        (PNPM[1], "Noted, I'll use pnpm for the frontend."),
        (DISK, "That's frustrating. Let's prune the old images before the next build."),
        ("Set up a users table and a projects table to start with.",
         "Done: users and projects tables, with a foreign key from projects to users."),
    ]),
    ("tidepool-day3", 3, [
        (CORRECTION, "Got it: PostgreSQL on the server, SQLite for local development."),
        (PNPM[3], "pnpm it is."),
        ("Let's write the migration for the projects table next.", "Here is the migration for the projects table."),
    ]),
    ("tidepool-day5", 5, [
        (PNPM[5], "Will do."),
        ("Can you look at the login form validation? Empty passwords get through.",
         "Fixed: the form now rejects empty passwords and shows a message under the field."),
    ]),
]

# Ordinary project talk for the busy worlds. It avoids the words the day-8 requests and the correction share
# (local, install, database, SQLite, PostgreSQL, machine), so what reaches day 8 is decided by the scenario's own
# messages, not by filler that happens to match.
FILLER_TOPICS = (
    "the landing page hero: the headline wraps badly on narrow phones and the call-to-action button sits too close "
    "to the fold, so the first screen looks crowded",
    "the onboarding email copy: it reads stiff, and the second paragraph repeats the pricing details that the page "
    "already shows just above it",
    "the billing tests: two cases are flaky because they depend on the current hour and fail near midnight, which "
    "keeps blocking merges late in the evening",
    "the dark mode colours: the muted grey on the cards fails contrast checks and the links are hard to spot against "
    "the background",
    "the changelog for the next release: group the fixes by area and keep each entry to one plain sentence that a "
    "customer would understand",
    "the API rate limits: the public endpoints should allow sixty requests a minute and answer with a clear "
    "retry-after header when they refuse one",
    "the image upload flow: large photos time out on slow connections, so they should be resized in the browser "
    "before they are sent",
    "the search box on the projects page: typing fast fires too many requests, so it needs a debounce and a small "
    "spinner while results load",
    "the settings form: two toggles have no labels for screen readers and the keyboard focus order jumps around "
    "between the sections",
    "the weekly report layout: put the summary first, then the charts, and move the raw numbers into an appendix at "
    "the end",
)
FILLER_OPENINGS = {4: "Next up is", 6: "Can we revisit", 7: "One more pass over"}


def filler_conversations():
    """Three days of ten exchanges each, about 9,000 characters of the user's words in all."""
    return [(f"tidepool-day{day}", day, [
        (f"{opening} {topic}. Draft a first pass and tell me what you would change before we merge anything "
         f"(round {day}.{index}).", f"Here is a first pass on that ({day}.{index}).")
        for index, topic in enumerate(FILLER_TOPICS)]) for day, opening in FILLER_OPENINGS.items()]


# The diligent host's notes, as a host model following NOTE_TOOL_DESCRIPTION would write them.
NOTE_DECISION = "Tidepool decision: use PostgreSQL as the project's database."
NOTE_CORRECTED = "Tidepool database: PostgreSQL on the server only; local development stays on SQLite."
NOTE_PNPM = "Prefers pnpm over npm for frontend packages."
# With ``chain``, a second change on day 5, saved as a note replacing the corrected one: A -> B -> C.
THIRD = "One more change: local development uses DuckDB now, not SQLite; the server stays on PostgreSQL."
NOTE_THIRD = "Tidepool database: PostgreSQL on the server; local development uses DuckDB."
# Inferred: the user said the laptop is nearly full, not that installs should be kept light. memory_note has no field
# that says a note was inferred; only a feeling (affect) can say so.
NOTE_INFERRED = "Laptop is low on disk space; keep local installs light and avoid large Docker images."
INFERRED_AFFECT = {"label": "frustrated", "valence": -1, "intensity": 2, "basis": "inferred",
                   "topic": "laptop disk space"}

# Day 8, each in a new session with nothing in its context.
PROMPTS = {"finish": "finish the local install", "dev_machine": "set up my dev machine",
           "chinese": "继续把本地环境装完"}
QUERIES = ("local install", "database for local", "which database")
DAY8_REPLY = "Finishing the local install on SQLite now; PostgreSQL stays on the server, as you said on 4 November."

# Cue phrases the diligent host writes when the session notice asks it to index earlier messages: the category of
# each lasting fact, as CONSOLIDATION_INSTRUCTIONS asks. Only the correction itself is about the local setup.
CUES = {DECISION: ["user Tidepool database choice"],
        CORRECTION: ["user Tidepool database choice", "user Tidepool local and server setup"],
        **{text: ["user frontend package manager preference"] for text in PNPM.values()},
        DISK: ["user laptop disk space"]}

BLOCK = re.compile(r"<(membrain-[a-z-]+)>.*?</\1>", re.DOTALL)


def blocks(text: str | None) -> dict[str, list[str]]:
    """The tagged blocks of a hook's context by tag, each verbatim; ``notice`` is the text outside every block."""
    text = text or ""
    found: dict[str, list[str]] = {}
    for match in BLOCK.finditer(text):
        found.setdefault(match.group(1), []).append(match.group(0))
    found["notice"] = [BLOCK.sub("", text).strip()]
    return found


def block(text: str | None, tag: str) -> str:
    return "\n".join(blocks(text).get(tag, []))


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _source(context: str | None) -> tuple[list | None, str | None]:
    """The note references and recording capture of a user_prompt context's membrain-source block."""
    if not context or "source_messages=" not in context:
        return None, None
    decoder = json.JSONDecoder()
    references, _ = decoder.raw_decode(context.split("source_messages=", 1)[1])
    capture, _ = decoder.raw_decode(context.split("recording_capture=", 1)[1])
    return references, capture


def call(server, name: str, arguments: dict):
    """One MCP tool call as the host makes it; the structured result."""
    result = asyncio.run(server.call_tool(name, arguments))
    if isinstance(result, tuple):
        return result[1] if result[1] is not None else result[0]
    return result


@dataclass
class World:
    host_kind: str  # "diligent" or "lazy"
    busy: bool
    model: bool
    chain: bool = False
    memory: object = None
    note_ids: dict = field(default_factory=dict)
    note_results: dict = field(default_factory=dict)
    captures: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return (f"{self.host_kind}-{'busy' if self.busy else 'short'}-{'model' if self.model else 'keywords'}"
                + ("-chain" if self.chain else ""))

    @property
    def directory(self) -> Path:
        return self.memory.directory

    def client(self):
        return self.memory.client()

    # Host play -----------------------------------------------------------------------------------------------------

    def _server(self):
        client, server, _schemas, instructions = self.memory.tools()
        self.captures.setdefault("server_instructions", instructions)
        return client, server

    def _call(self, server, name, arguments):
        result = call(server, name, arguments)
        self.tool_calls.append({"tool": name, "arguments": arguments, "result": result})
        return result

    def _consolidate(self, server, notice: str) -> None:
        """What the session notice asks: fetch a batch, then answer it with cues (diligent host only)."""
        if "memory_consolidate tool without arguments" not in notice:
            return
        batch = self._call(server, "memory_consolidate", {})
        cues = []
        for message in batch.get("messages") or []:
            if message["text"] in CUES:
                cues.append({"id": message["id"], "cues": CUES[message["text"]]})
        self._call(server, "memory_consolidate", {"cues": cues})

    def _note(self, server, key, context, text, **fields):
        references, capture = _source(context)
        arguments = {"text": text, "source_messages": references, "recording_capture": capture, **fields}
        result = self._call(server, "memory_note", arguments)
        assert result.get("note_id"), result
        self.note_ids[key] = result["note_id"]
        self.note_results[key] = result

    def conversation(self, session: str, turns: list) -> None:
        diligent = self.host_kind == "diligent"
        client, server = self._server() if diligent else (None, None)
        try:
            notice = plugin.session_start({"session_id": session}, self.directory) or ""
            if diligent:
                self._consolidate(server, notice)
            for index, (text, reply) in enumerate(turns):
                context = plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": f"t{index}"},
                                             self.directory)
                if diligent:
                    if text == DECISION:
                        self._note(server, "decision", context, NOTE_DECISION, kind="other")
                    elif text == CORRECTION:
                        self._note(server, "corrected", context, NOTE_CORRECTED, kind="other",
                                   replaces=[self.note_ids["decision"]])
                    elif text == THIRD:
                        self._note(server, "third", context, NOTE_THIRD, kind="other",
                                   replaces=[self.note_ids["corrected"]])
                    elif text == PNPM[1]:
                        self._note(server, "pnpm", context, NOTE_PNPM, kind="preference")
                    elif text == DISK:
                        self._note(server, "inferred", context, NOTE_INFERRED, kind="constraint",
                                   affect=INFERRED_AFFECT)
                plugin.stop({"session_id": session, "prompt_id": f"t{index}", "last_assistant_message": reply},
                            self.directory)
        finally:
            if client is not None:
                client.close()

    def day8(self) -> None:
        """Every day-8 request in its own new session. The other wordings are only received, never answered or
        recorded, so each sees memory as it was before day 8; "finish" comes last, is answered and recorded."""
        captures = self.captures.setdefault("day8", {})
        for key in ("dev_machine", "chinese", "finish"):
            session = f"tidepool-day8-{key}"
            opening = plugin.session_start({"session_id": session}, self.directory)
            prompt = plugin.user_prompt({"session_id": session, "prompt": PROMPTS[key], "prompt_id": "t0"},
                                        self.directory)
            captures[key] = {"session_start": opening, "user_prompt": prompt}
        client, server = self._server()
        try:
            # What memory_recall returns to these searches. Only the diligent host makes them; the lazy host never
            # does, so for it this is what the tool would have returned.
            self.captures["recall"] = {query: call(server, "memory_recall", {"query": query}).get("context")
                                       for query in QUERIES}
            self.captures["recall_records"] = {
                query: call(server, "memory_recall", {"query": query, "with_ids": True}).get("records")
                for query in QUERIES}
            if self.host_kind == "diligent":
                self._consolidate(server, captures["finish"]["session_start"] or "")
                for query in QUERIES:
                    self._call(server, "memory_recall", {"query": query})
        finally:
            client.close()
        plugin.stop({"session_id": "tidepool-day8-finish", "prompt_id": "t0", "last_assistant_message": DAY8_REPLY},
                    self.directory)

    # Reading back ---------------------------------------------------------------------------------------------------

    def messages(self) -> dict[str, dict]:
        """Every recorded message by its text (scenario texts are unique)."""
        with self.client() as client:
            items = client.timeline(roles=("user", "assistant"), max_characters=200_000, max_item_characters=20_000,
                                    limit=1000)["items"]
        return {item["text"]: item for item in items if item.get("conversation_id") != "membrain-notes"}

    def notes(self) -> list[dict]:
        with self.client() as client:
            return list_notes(client)["items"]

    def dump(self) -> None:
        target = os.environ.get("RESUME_CORRECTION_DUMP")
        if not target:
            return
        Path(target).mkdir(parents=True, exist_ok=True)
        document = {"world": self.name, "captures": self.captures, "tool_calls": self.tool_calls,
                    "note_ids": self.note_ids, "note_results": self.note_results,
                    "notes": self.notes(),
                    "messages": {text: {key: item.get(key) for key in ("event_id", "conversation_id", "actor_role",
                                                                       "recorded_at")}
                                 for text, item in self.messages().items()}}
        (Path(target) / f"{self.name}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")


@contextmanager
def built_world(tmp_path_factory, host_kind: str, *, busy: bool = False, model: bool = False, chain: bool = False):
    """A world played through day 8, then stopped. Skipped (as the other service tests are) without the embedded
    database, or for ``model`` without the test embedding model. ``chain`` adds a second change on day 5."""
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    from membrain import local_embeddings

    if model and not (MODEL and local_embeddings.runtime_available() and local_embeddings.installed(Path(MODEL))):
        pytest.skip("set MEMBRAIN_TEST_EMBEDDING_MODEL to an installation directory containing the model")
    world = World(host_kind, busy, model, chain)
    patch = pytest.MonkeyPatch()
    patch.setenv("MEMBRAIN_SEMANTIC", "0")  # Never download; the model, when wanted, is copied in.
    patch.setenv("PYTHON_DOTENV_DISABLED", "1")
    patch.setenv(evaluation_clock.ENV, "")  # Restored afterwards; the harness sets it for its profile.
    patch.setattr(harness, "STUB", True)
    directory = tmp_path_factory.mktemp(world.name) / "brain"
    try:
        world.memory = harness.Memory(directory, Path(MODEL) if model else None, (free_port(), free_port()), DAY[1])
        # The hook functions use the default tool names when the plugin's host is Claude Code.
        assert plugin.HOST_TOOLS["claude-code"]["note"] == "memory_note"
        conversations = list(CONVERSATIONS)
        if busy:
            conversations += filler_conversations()
        if chain:
            conversations.append(("tidepool-day5-change", 5, [(THIRD, "DuckDB locally, PostgreSQL on the server.")]))
        for session, day, turns in sorted(conversations, key=lambda entry: entry[1]):
            world.memory.clock.advance(directory, DAY[day], run=directory.name)
            world.conversation(session, turns)
        world.memory.wait_until_indexed(timeout=900)
        world.memory.clock.advance(directory, DAY[8], run=directory.name)
        world.day8()
        world.dump()
        yield world
    finally:
        from membrain import desktop

        try:
            if directory in harness.STARTED:  # Only this world's service: another world may still be in use.
                harness.STARTED.remove(directory)
                desktop.stop(directory)
        finally:
            evaluation_clock.disable()
            patch.undo()


def history_lines(text: str) -> list[str]:
    return [line for line in block(text, "membrain-history").splitlines() if line.startswith("- [")]


def note_lines(text: str) -> list[str]:
    return [line for line in block(text, "membrain-notes").splitlines() if line.startswith("- [")]


def received(capture: dict) -> str:
    """Everything the host received before answering: the session start and the prompt's context."""
    return "\n\n".join(part for part in (capture.get("session_start"), capture.get("user_prompt")) if part)


__all__ = ["CONVERSATIONS", "CORRECTION", "DATE", "DAY", "DAY8_REPLY", "DECISION", "DISK", "INFERRED_AFFECT", "MODEL",
           "NOTE_CORRECTED", "NOTE_DECISION", "NOTE_INFERRED", "NOTE_PNPM", "NOTE_THIRD", "PNPM", "PROMPTS", "QUERIES",
           "THIRD", "World",
           "block", "blocks", "built_world", "call", "harness", "history_lines", "host", "note_lines", "received"]
