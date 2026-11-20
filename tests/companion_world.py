"""Test helper: a coding user's casual, mixed and returning sessions on Claude Code, on a real local installation.

Played through the Claude Code plugin's own entry points (``plugin.session_start``, ``plugin.user_prompt``,
``plugin.stop`` and the plugin's MCP server) on the scenario clock of a disposable evaluation profile
(``evaluations/c5-harness.py``'s ``Memory``), with no model call of any kind, like ``resume_correction_world``. The
host's part is scripted: where a host model following the server instructions would call a memory tool (a note with
a feeling, a shared moment), the script makes that call with the turn's own source and recording capture.

Worlds:

- ``first_coding``: a new user whose first session is work from the first message.
- ``first_casual``: a new user who opens casually, then asks for work.
- ``returning``: one user over twelve days. Day 1 starts casually (a feeling the user said, a shared joke saved as a
  playful shared moment) and then turns to work; day 3 is a mixed session (work, then "ugh, long day", then work);
  day 4 is work with a bare "thanks"; day 12, after eight days away, opens with a greeting.
- ``returning_openclaw``, ``returning_chat_bot``, ``returning_roleplay``: the same user on OpenClaw's hooks, on a chat
  bot (the ``ChatMemory`` adapter, which asks for the whole context before every message) and in a chat bot's
  role-play, whose companion is unchanged.
- ``tool_mark``: a message with no cue of its own, after which the host saves a shared moment, then work.
- ``agreements``: in a work session the user confirms a "from now on" change and sets a topic boundary; then a new
  work session.

Everything the host receives is kept verbatim in ``World.captures`` by session: the session start's context and each
prompt's context, in order. With ``COMPANION_WORLD_DUMP`` set to a directory, each world writes its captures there as
JSON, in the shape ``resume_correction_world`` uses. All data is fictional.
"""
from __future__ import annotations

import datetime
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from resume_correction_world import DECISION, PNPM, _source, call, free_port, harness

from membrain import embedded_database, evaluation_clock, host, plugin

UTC = datetime.UTC
DAY = {1: datetime.datetime(2026, 11, 2, 18, 0, tzinfo=UTC), 3: datetime.datetime(2026, 11, 4, 18, 0, tzinfo=UTC),
       4: datetime.datetime(2026, 11, 5, 10, 0, tzinfo=UTC), 12: datetime.datetime(2026, 11, 13, 9, 30, tzinfo=UTC)}

HIKE = "Hi! Just got back from a long hike with my sister and I'm so happy."
PUN = "Ha, your pun about tide pools made my day. That one's a keeper."
LONG_DAY = "ugh, long day. my manager moved the deadline up again."
# Each turn: (user message, reply, the host's tool calls as (tool, arguments without source and capture)).
WORLDS = {
    "first_coding": [("coding-day1", 1, [
        (DECISION, "Sounds good: PostgreSQL for Tidepool.", [
            ("memory_note", {"text": "Tidepool decision: use PostgreSQL as the project's database.", "kind": "other"})]),
        (PNPM[1], "Noted, pnpm for the frontend.", [
            ("memory_note", {"text": "Prefers pnpm over npm for frontend packages.", "kind": "preference"})]),
        ("Set up a users table and a projects table to start with.", "Done: users and projects tables.", []),
    ])],
    "first_casual": [("casual-day1", 1, [
        ("Hey there! How's it going?", "Hi! Going well, thanks. What are we up to?", []),
        ("Can you help me set up a Python project for a small CLI tool?", "Sure: here is a layout with uv.", []),
    ])],
    "returning": [
        ("chat-day1", 1, [
            (HIKE, "That sounds lovely! Where did you go?", [
                ("memory_note", {"text": "Went on a long hike with his sister on 2026-11-02.", "kind": "milestone",
                                 "affect": {"label": "happy", "valence": 2, "intensity": 2, "basis": "reported",
                                            "topic": "the hike"}})]),
            (PUN, "Glad it landed!", [
                ("memory_note", {"text": "Laughed together at a pun about tide pools.", "kind": "milestone",
                                 "shared": True, "moment": "play"})]),
            (DECISION, "Sounds good: PostgreSQL for Tidepool.", [
                ("memory_note", {"text": "Tidepool decision: use PostgreSQL as the project's database.",
                                 "kind": "other"})]),
        ]),
        ("mixed-day3", 3, [
            ("Let's write the migration for the projects table next.", "Here is the migration.", []),
            (LONG_DAY, "That sounds draining. Want to keep going or call it a day?", []),
            ("ok, back to it: add an index on projects.owner_id.", "Added the index.", []),
        ]),
        ("work-day4", 4, [
            ("Can you look at the login form validation? Empty passwords get through.", "Fixed.", []),
            ("Thanks, that works.", "Good to hear.", []),
        ]),
        ("return-day12", 12, [
            ("Hi again! Back from a week off.", "Welcome back! Ready when you are.", []),
            ("Let's pick up the Tidepool backend where we left it.", "Picking up with the migrations.", []),
        ]),
    ],
    # A message with no cue of its own, after which the host saves a shared moment.
    "tool_mark": [("moment-day1", 1, [
        ("Save the tide pool pun you made earlier as a moment of ours.", "Saved.", [
            ("memory_note", {"text": "Laughed together at a pun about tide pools.", "kind": "milestone",
                             "shared": True, "moment": "play"})]),
        ("Next, add an index on projects.owner_id.", "Added the index.", []),
        ("Now the migration for the users table.", "Here it is.", []),
    ])],
    # A "from now on" change the user confirms, and a topic boundary, both in a work session; then a new session.
    "agreements": [
        ("rules-day1", 1, [
            ("From now on, walk me through database migrations step by step.", "Shall I keep to that from now on?", [
                ("memory_persona", {"action": "propose",
                                    "changes": {"values": ["Walks the user through database migrations step by step"]},
                                    "reason": "The user asked for this from now on."})]),
            ("Yes, do that.", "Will do.", [("memory_persona", {"action": "confirm", "proposal_id": "$proposal"})]),
            ("Please don't bring up my ex, ever.", "Understood.", [("memory_boundary", {"topic": "my ex"})]),
        ]),
        ("work-day3", 3, [("Let's write the migration for the projects table next.", "Here is the migration.", [])]),
    ],
}
SOURCED = ("memory_note", "memory_manner_feedback", "memory_persona")  # The tools that take the turn's source.


# The same returning user on the other hosts, whose companion is unchanged: OpenClaw's hooks, a chat bot (the
# ``ChatMemory`` adapter AstrBot uses) and a chat bot's role-play.
WORLDS.update({f"returning_{kind}": WORLDS["returning"] for kind in ("openclaw", "chat_bot", "roleplay")})
CHAT_TOOLS = {"memory_note": "note", "memory_manner_feedback": "manner_feedback", "memory_persona": "persona"}


@dataclass
class World:
    name: str
    memory: object = None
    captures: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)

    @property
    def directory(self) -> Path:
        return self.memory.directory

    @property
    def host_kind(self) -> str:
        return self.name.split("_", 1)[1] if self.name.startswith("returning_") else "claude-code"

    def client(self):
        if self.host_kind in ("chat_bot", "roleplay"):
            from membrain.adapters.chatbot import ChatMemory

            chat = ChatMemory(self.directory, roleplay="Captain Ada" if self.host_kind == "roleplay" else None)
            return host.ready_client(self.directory, chat.memory_user(self.speaker))
        return self.memory.client()

    @property
    def speaker(self):
        from membrain.adapters.chatbot import Speaker

        return Speaker(platform="test", user="sam")

    def conversation(self, session: str, turns: list) -> None:
        if self.host_kind in ("chat_bot", "roleplay"):
            return self._chat(session, turns)
        producer = plugin.PRODUCERS["openclaw" if self.host_kind == "openclaw" else "claude-code"]
        client, server, _schemas, instructions = self.memory.tools()
        self.captures.setdefault("server_instructions", instructions)
        record = self.captures.setdefault("sessions", {}).setdefault(session, {"prompts": []})
        try:
            record["session_start"] = plugin.session_start({"session_id": session}, self.directory, producer)
            for index, (text, reply, tools) in enumerate(turns):
                context = plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": f"t{index}"},
                                             self.directory, producer)
                record["prompts"].append({"prompt": text, "user_prompt": context})
                references, capture = _source(context)
                for tool, arguments in tools:
                    arguments = self._arguments(tool, arguments, references, capture)
                    result = call(server, tool, arguments)
                    self.tool_calls.append({"session": session, "turn": index, "tool": tool,
                                            "arguments": arguments, "result": result})
                plugin.stop({"session_id": session, "prompt_id": f"t{index}", "last_assistant_message": reply},
                            self.directory, producer)
        finally:
            client.close()

    def _arguments(self, tool: str, arguments: dict, references, capture) -> dict:
        """The scripted arguments with the turn's source and capture, and "$proposal" as the last proposal's id."""
        if arguments.get("proposal_id") == "$proposal":
            proposed = [entry["result"] for entry in self.tool_calls if isinstance(entry["result"], dict)
                        and entry["result"].get("proposal_id")]
            arguments = {**arguments, "proposal_id": proposed[-1]["proposal_id"]}
        if tool in SOURCED:
            arguments = {**arguments, "source_messages": references, "recording_capture": capture}
        return arguments

    def _chat(self, session: str, turns: list) -> None:
        """A chat bot asks for the whole context before every message; its tools are the adapter's methods."""
        from membrain.adapters.chatbot import ChatMemory

        chat = ChatMemory(self.directory, roleplay="Captain Ada" if self.host_kind == "roleplay" else None)
        bound = chat.session(self.speaker, session, today=self.memory.clock.current(self.directory).date())
        record = self.captures.setdefault("sessions", {}).setdefault(session, {"session_start": None, "prompts": []})
        for index, (text, reply, tools) in enumerate(turns):
            context = chat.context(self.speaker, text, session=bound, turn_id=f"t{index}")
            record["prompts"].append({"prompt": text, "user_prompt": context})
            references, capture = _source(context)
            for tool, arguments in tools:
                arguments = self._arguments(tool, arguments, references, capture)
                method = getattr(chat, CHAT_TOOLS[tool])
                if tool == "memory_note":
                    fields = {key: value for key, value in arguments.items() if key != "text"}
                    result = method(self.speaker, arguments["text"], **fields)
                else:
                    result = method(self.speaker, **arguments)
                self.tool_calls.append({"session": session, "turn": index, "tool": tool, "arguments": arguments,
                                        "result": result})
            chat.record(self.speaker, reply, session=bound, turn_id=f"t{index}")

    def dump(self) -> None:
        target = os.environ.get("COMPANION_WORLD_DUMP")
        if not target:
            return
        Path(target).mkdir(parents=True, exist_ok=True)
        with self.client() as client:
            state = {"persona": client.persona(), "mood": client.mood(), "relationship": client.relationship()}
        document = {"world": self.name, "captures": self.captures, "tool_calls": self.tool_calls,
                    "computed": {"persona_version": state["persona"].get("version"),
                                 "mood": None if state["mood"].get("at_baseline") else state["mood"].get("label"),
                                 "familiarity": state["relationship"]["familiarity"]["level"],
                                 "shared_moments": len(state["relationship"].get("shared_moments") or ())}}
        (Path(target) / f"{self.name}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")


@contextmanager
def built_world(tmp_path_factory, name: str):
    """A world played to its end, then stopped. Skipped (as the other service tests are) without the embedded
    database."""
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    world = World(name)
    patch = pytest.MonkeyPatch()
    patch.setenv("MEMBRAIN_SEMANTIC", "0")
    patch.setenv("PYTHON_DOTENV_DISABLED", "1")
    patch.setenv(evaluation_clock.ENV, "")
    patch.setattr(harness, "STUB", True)
    patch.setenv("PATH", str(host._entry_point().parent) + os.pathsep + os.environ.get("PATH", ""))
    directory = tmp_path_factory.mktemp(name) / "brain"
    sessions = WORLDS[name]
    try:
        world.memory = harness.Memory(directory, None, (free_port(), free_port()), DAY[sessions[0][1]])
        for session, day, turns in sessions:
            world.memory.clock.advance(directory, DAY[day], run=directory.name)
            world.conversation(session, turns)
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


__all__ = ["DAY", "HIKE", "LONG_DAY", "PUN", "SOURCED", "WORLDS", "World", "built_world"]
