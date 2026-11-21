"""Test helper: one user, two projects, a third directory; what a new session in each receives on day 8.

Built on ``resume_correction_world`` (the same evaluation installation, scenario clock and plugin entry points: the
hook functions with the payloads Claude Code sends, and the plugin's MCP server). What differs is where each session
runs: every hook payload carries ``cwd`` as Claude Code sends it, and the MCP server of a session is created with that
directory as its working directory, as the host starts it there.

- Project Tidepool (a git repository): day 1 PostgreSQL is decided; day 3, in a session run from a git worktree of
  Tidepool, it is corrected to "only the server uses PostgreSQL; local stays SQLite".
- Project Harbor (another repository; its sessions run in its ``app`` subdirectory): day 2 "we use MySQL here,
  locally too", ordinary talk, and personal facts.
- Personal, project-independent facts, said in either: pnpm over npm, a laptop low on disk space, "call me Sam".
- Day 8: "finish the local install" in a new session in Harbor, in Tidepool, and in a directory never seen before.

The diligent host saves notes as the server instructions ask; ``named`` notes name the project in their text (as the
host of the 2026-11-18 trial happened to write "Tidepool database: ..."), unnamed ones do not. ``busy`` adds three
days of ordinary talk (two in Tidepool, one in Harbor), so a new session's history block cannot hold everything and
the prompt hook recalls. Everything a day-8 session receives before answering is kept verbatim in ``captures``; with
``TWO_PROJECT_DUMP`` set to a directory, each world writes them there as JSON in the shape of the resume-correction
captures (``captures.day8.<directory>.session_start`` and ``user_prompt``), with each session's searches beside them.
All data is fictional.
"""
from __future__ import annotations

import datetime
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from resume_correction_world import (
    CORRECTION,
    DAY,
    DECISION,
    DISK,
    FILLER_OPENINGS,
    FILLER_TOPICS,
    INFERRED_AFFECT,
    MODEL,
    NOTE_INFERRED,
    NOTE_PNPM,
    PNPM,
    _source,
    block,
    call,
    free_port,
    harness,
)

from membrain import embedded_database, evaluation_clock, host, plugin
from membrain.notes import list_notes

UTC = datetime.UTC
DAYS = {**DAY, 2: datetime.datetime(2026, 11, 3, 10, 0, tzinfo=UTC)}

HARBOR_DB = "For the database, we use MySQL here, locally too."
NAME = "By the way, call me Sam."
CSV = "Can you add a CSV export to the orders page?"

# (directory key, session, day, [(user message, reply)]), oldest first. ``tidepool-worktree`` is a git worktree of
# Tidepool; ``harbor`` sessions run in Harbor's ``app`` subdirectory.
CONVERSATIONS = [
    ("tidepool", "tidepool-day1", 1, [
        (DECISION, "Sounds good: PostgreSQL for Tidepool. I'll start with a connection config and a first migration."),
        (PNPM[1], "Noted, I'll use pnpm for the frontend."),
        ("Set up a users table and a projects table to start with.",
         "Done: users and projects tables, with a foreign key from projects to users."),
    ]),
    ("harbor", "harbor-day2", 2, [
        (HARBOR_DB, "Understood: MySQL everywhere, including local development."),
        (DISK, "That's frustrating. Let's prune the old images before the next build."),
        (NAME, "Sure, Sam."),
        (CSV, "Added a CSV export button to the orders page; it streams the rows so large exports stay fast."),
    ]),
    ("tidepool-worktree", "tidepool-day3", 3, [
        (CORRECTION, "Got it: PostgreSQL on the server, SQLite for local development."),
        (PNPM[3], "pnpm it is."),
        ("Let's write the migration for the projects table next.", "Here is the migration for the projects table."),
    ]),
    ("harbor", "harbor-day5", 5, [
        (PNPM[5], "Will do."),
        ("Can you look at the login form validation? Empty passwords get through.",
         "Fixed: the form now rejects empty passwords and shows a message under the field."),
    ]),
]
FILLER_PLACES = {4: "tidepool", 6: "harbor", 7: "tidepool"}

# The diligent host's notes: (key, message it is saved on, text when named, text when not, fields).
NOTES = [
    ("decision", DECISION, "Tidepool decision: use PostgreSQL as the project's database.",
     "Decision: use PostgreSQL as the project's database.", {"kind": "other"}),
    ("corrected", CORRECTION, "Tidepool database: PostgreSQL on the server only; local development stays on SQLite.",
     "Database: PostgreSQL on the server only; local development stays on SQLite.",
     {"kind": "other", "replaces": "decision"}),
    ("harbor_db", HARBOR_DB, "Harbor database: MySQL everywhere, local development included.",
     "Database: MySQL everywhere, local development included.", {"kind": "other"}),
    ("pnpm", PNPM[1], NOTE_PNPM, NOTE_PNPM, {"kind": "preference"}),
    ("inferred", DISK, NOTE_INFERRED, NOTE_INFERRED, {"kind": "constraint", "affect": INFERRED_AFFECT}),
    # Named: typed as a preference. Unnamed: a plain note without a kind, as a host may well save it.
    ("name", NAME, "Wants to be called Sam.", "Wants to be called Sam.", {"kind": "preference", "plain": True}),
]
CUES = {DECISION: ["user Tidepool database choice"], CORRECTION: ["user Tidepool database choice"],
        HARBOR_DB: ["user Harbor database choice"], **{text: ["user frontend package manager preference"]
                                                        for text in PNPM.values()},
        DISK: ["user laptop disk space"], NAME: ["user preferred name"]}

PROMPT = "finish the local install"
QUERIES = ("local database", "which database")
DAY8 = ("harbor", "tidepool", "scratch")


def filler_conversations():
    return [(FILLER_PLACES[day], f"{FILLER_PLACES[day]}-day{day}", day, [
        (f"{opening} {topic}. Draft a first pass and tell me what you would change before we merge anything "
         f"(round {day}.{index}).", f"Here is a first pass on that ({day}.{index}).")
        for index, topic in enumerate(FILLER_TOPICS)]) for day, opening in FILLER_OPENINGS.items()]


def make_directories(root: Path) -> dict[str, Path]:
    """Tidepool and Harbor as git repositories (the layout ``git init`` and ``git worktree add`` leave), a worktree of
    Tidepool beside it, and a scratch directory that is no repository."""
    tidepool, harbor = root / "code" / "Tidepool", root / "code" / "Harbor"
    worktree = root / "code" / "Tidepool-fix-db"
    for repository in (tidepool, harbor):
        (repository / ".git").mkdir(parents=True)
        (repository / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    linked = tidepool / ".git" / "worktrees" / "Tidepool-fix-db"
    linked.mkdir(parents=True)
    (linked / "commondir").write_text("../..\n")
    (linked / "gitdir").write_text(str(worktree / ".git") + "\n")
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {linked}\n")
    (harbor / "app").mkdir()
    (root / "scratch").mkdir()
    return {"tidepool": tidepool, "tidepool-worktree": worktree, "harbor": harbor / "app",
            "scratch": root / "scratch"}


@contextmanager
def working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


@dataclass
class World:
    host_kind: str  # "diligent" or "lazy"
    named: bool
    busy: bool
    model: bool
    places: dict = field(default_factory=dict)
    memory: object = None
    note_ids: dict = field(default_factory=dict)
    note_results: dict = field(default_factory=dict)
    captures: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return (f"{self.host_kind}-{'named' if self.named else 'unnamed'}-{'busy' if self.busy else 'short'}"
                f"-{'model' if self.model else 'keywords'}")

    @property
    def directory(self) -> Path:
        return self.memory.directory

    def client(self):
        return self.memory.client()

    def payload(self, place: str, session: str, **values) -> dict:
        return {"session_id": session, "cwd": str(self.places[place]), "transcript_path": None, **values}

    def _server(self, place: str):
        with working_directory(self.places[place]):  # The host starts its MCP server in the session's directory.
            client, server, _schemas, instructions = self.memory.tools()
        self.captures.setdefault("server_instructions", instructions)
        return client, server

    def _call(self, server, name, arguments):
        result = call(server, name, arguments)
        self.tool_calls.append({"tool": name, "arguments": arguments, "result": result})
        return result

    def _consolidate(self, server, notice: str) -> None:
        if "memory_consolidate tool without arguments" not in notice:
            return
        batch = self._call(server, "memory_consolidate", {})
        cues = [{"id": message["id"], "cues": CUES[message["text"]]} for message in batch.get("messages") or []
                if message["text"] in CUES]
        self._call(server, "memory_consolidate", {"cues": cues})

    def _notes_for(self, server, text: str, context: str | None) -> None:
        for key, said, named, unnamed, fields in NOTES:
            if said != text:
                continue
            fields = dict(fields)
            if fields.pop("plain", False) and not self.named:
                fields.pop("kind")
            if "replaces" in fields:
                fields["replaces"] = [self.note_ids[fields["replaces"]]]
            references, capture = _source(context)
            result = self._call(server, "memory_note", {"text": named if self.named else unnamed,
                                                        "source_messages": references,
                                                        "recording_capture": capture, **fields})
            assert result.get("note_id"), result
            self.note_ids[key], self.note_results[key] = result["note_id"], result

    def conversation(self, place: str, session: str, turns: list) -> None:
        diligent = self.host_kind == "diligent"
        client, server = self._server(place) if diligent else (None, None)
        try:
            notice = plugin.session_start(self.payload(place, session, hook_event_name="SessionStart",
                                                       source="startup"), self.directory) or ""
            if diligent:
                self._consolidate(server, notice)
            for index, (text, reply) in enumerate(turns):
                context = plugin.user_prompt(self.payload(place, session, hook_event_name="UserPromptSubmit",
                                                          prompt=text, prompt_id=f"t{index}"), self.directory)
                if diligent:
                    self._notes_for(server, text, context)
                plugin.stop(self.payload(place, session, hook_event_name="Stop", prompt_id=f"t{index}",
                                         last_assistant_message=reply), self.directory)
        finally:
            if client is not None:
                client.close()

    def day8(self) -> None:
        """A new session in each directory with the same words. They are only received, never answered or recorded,
        so each sees memory as it was before day 8."""
        captures = self.captures.setdefault("day8", {})
        for place in DAY8:
            session = f"{place}-day8"
            opening = plugin.session_start(self.payload(place, session, hook_event_name="SessionStart",
                                                        source="startup"), self.directory)
            prompt = plugin.user_prompt(self.payload(place, session, hook_event_name="UserPromptSubmit",
                                                     prompt=PROMPT, prompt_id="t0"), self.directory)
            client, server = self._server(place)
            try:
                recall = {query: call(server, "memory_recall", {"query": query}).get("context") for query in QUERIES}
            finally:
                client.close()
            captures[place] = {"cwd": str(self.places[place]), "session_start": opening, "user_prompt": prompt,
                               "recall": recall}
        self.captures["recall"] = captures["harbor"]["recall"]

    # Reading back ---------------------------------------------------------------------------------------------------

    def messages(self) -> dict[str, dict]:
        with self.client() as client:
            items = client.timeline(roles=("user", "assistant"), max_characters=200_000, max_item_characters=20_000,
                                    limit=1000)["items"]
        return {item["text"]: item for item in items if item.get("conversation_id") != "membrain-notes"}

    def notes(self) -> list[dict]:
        with self.client() as client:
            return list_notes(client)["items"]

    def dump(self) -> None:
        target = os.environ.get("TWO_PROJECT_DUMP")
        if not target:
            return
        Path(target).mkdir(parents=True, exist_ok=True)
        keys = ("event_id", "conversation_id", "actor_role", "recorded_at", "producer", "workspaces")
        document = {"world": self.name, "captures": self.captures, "tool_calls": self.tool_calls,
                    "note_ids": self.note_ids, "note_results": self.note_results, "notes": self.notes(),
                    "messages": {text: {key: item.get(key) for key in keys} for text, item in self.messages().items()}}
        (Path(target) / f"{self.name}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")


@contextmanager
def built_world(tmp_path_factory, host_kind: str, *, named: bool = True, busy: bool = False, model: bool = False):
    """A two-project world played through day 8, then stopped (as ``resume_correction_world.built_world``)."""
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    from membrain import local_embeddings

    if model and not (MODEL and local_embeddings.runtime_available() and local_embeddings.installed(Path(MODEL))):
        pytest.skip("set MEMBRAIN_TEST_EMBEDDING_MODEL to an installation directory containing the model")
    world = World(host_kind, named, busy, model)
    patch = pytest.MonkeyPatch()
    patch.setenv("MEMBRAIN_SEMANTIC", "0")
    patch.setenv("PYTHON_DOTENV_DISABLED", "1")
    patch.setenv(evaluation_clock.ENV, "")
    patch.setattr(harness, "STUB", True)
    patch.setenv("PATH", str(host._entry_point().parent) + os.pathsep + os.environ.get("PATH", ""))
    root = tmp_path_factory.mktemp(world.name)
    world.places = make_directories(root / "home")
    directory = root / "brain"
    try:
        world.memory = harness.Memory(directory, Path(MODEL) if model else None, (free_port(), free_port()), DAYS[1])
        conversations = list(CONVERSATIONS) + (filler_conversations() if busy else [])
        for place, session, day, turns in sorted(conversations, key=lambda entry: entry[2]):
            world.memory.clock.advance(directory, DAYS[day], run=directory.name)
            world.conversation(place, session, turns)
        world.memory.wait_until_indexed(timeout=900)
        world.memory.clock.advance(directory, DAYS[8], run=directory.name)
        world.day8()
        world.dump()
        yield world
    finally:
        from membrain import desktop

        try:
            if directory in harness.STARTED:
                harness.STARTED.remove(directory)
                desktop.stop(directory)
        finally:
            evaluation_clock.disable()
            patch.undo()


def lines(text: str | None, tag: str) -> list[str]:
    return [line for line in block(text, tag).splitlines() if line.startswith("- [")]


def line_with(text: str | None, tag: str, words: str) -> str | None:
    """The first line of a block that holds ``words``; None when there is none."""
    return next((line for line in lines(text, tag) if words in line), None)


__all__ = ["CONVERSATIONS", "CSV", "DAY8", "HARBOR_DB", "NAME", "NOTES", "PROMPT", "QUERIES", "World", "built_world",
           "line_with", "lines"]
