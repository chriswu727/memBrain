"""Test helper: a small real memory for looking at the memory page, recorded as a user would make it.

Played through the Claude Code plugin's own entry points (``plugin.session_start``, ``plugin.user_prompt``,
``plugin.stop`` and the plugin's MCP server) on the scenario clock of a disposable evaluation profile, with no model
call of any kind, as ``resume_correction_world`` and ``companion_world`` do. Where a host model following the server
instructions would save a note (a person, a plan, a feeling, a shared moment, a replacement), the script makes that
call with the turn's own source and recording capture.

``small``: six days, about thirty user messages and their replies, a dozen notes: a person, plans (one of them
replaced), a preference, a constraint with a feeling the user said, a note with a feeling the agent inferred, a shared
moment, a routine, a decision corrected by a later note, a Chinese conversation and ordinary project talk. Several
first messages are longer than a conversation summary, so the page has to shorten them.

``large``: the same, plus enough project talk for about three hundred records in all (messages and notes).

All data is fictional.
"""
from __future__ import annotations

import datetime
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from resume_correction_world import (
    CORRECTION,
    DECISION,
    FILLER_TOPICS,
    PNPM,
    _source,
    call,
    free_port,
    harness,
)

from membrain import embedded_database, evaluation_clock, host, plugin

UTC = datetime.UTC
DAY = {number: datetime.datetime(2026, 11, number + 1, 18, 0, tzinfo=UTC) for number in range(1, 9)}

TRIP = ("My sister Mira and I are finally planning the Dolomites trip for next July; we want to hike the Alta Via 1 "
        "from hut to hut over nine days.")
HEADACHE = "I get altitude headaches above about 2,500 metres, so the route should stay lower where it can."
JOKE = "Ha, your joke about the huts having better Wi-Fi than my flat made my day."
HUT = "Please remember to book the first hut, Rifugio Biella, for the night of 5 July."
MOVED = "Change of plan: we start the Alta Via 1 on 3 July instead, so the first hut is for the night of 3 July."
HANGZHOU = ("下个月我们要去杭州看望外婆，顺便在西湖边走走，记得提醒我提前订好高铁票和酒店，最好是靠近断桥的那一家。"
            "外婆腿脚不太方便，所以每天的行程不要排得太满，中午最好能回酒店休息一下，晚上再一起去河坊街吃小吃。")
TRAIN = "ugh, the train home was cancelled again and I lost the whole afternoon waiting at the station."
CLIMB = "I go bouldering every Tuesday and Thursday evening at the gym near work, so keep those evenings free."

NOTE_MIRA = "Mira is the user's sister; she is planning the Dolomites trip with the user."
NOTE_TRIP = "Hike the Alta Via 1 in the Dolomites with Mira, hut to hut over nine days, next July."
NOTE_HUT = "Book Rifugio Biella, the first hut of the Alta Via 1, for the night of 5 July."
NOTE_MOVED = "Book Rifugio Biella, the first hut of the Alta Via 1, for the night of 3 July (start moved from 5 July)."
NOTE_HEADACHE = "Gets altitude headaches above about 2,500 metres; prefers routes that stay lower."
NOTE_JOKE = "Laughed together at a joke about the huts having better Wi-Fi than the user's flat."
NOTE_HANGZHOU = "下个月去杭州看望外婆，要提前订好高铁票和靠近断桥的酒店。"
NOTE_TRAIN = "The train home was cancelled on 2026-11-06; lost an afternoon waiting at the station."
NOTE_CLIMB = "Goes bouldering every Tuesday and Thursday evening at the gym near work; keep those evenings free."
NOTE_DECISION = "Tidepool decision: use PostgreSQL as the project's database."
NOTE_CORRECTED = "Tidepool database: PostgreSQL on the server only; local development stays on SQLite."
NOTE_PNPM = "Prefers pnpm over npm for frontend packages."

# Each turn: (user message, reply, [(note key, memory_note arguments without source and capture)]). ``replaces``
# names earlier notes by key.
SESSIONS = [
    ("trip-day1", 1, [
        (TRIP, "That sounds wonderful. Nine days on the Alta Via 1 is a classic; shall I sketch the stages?", [
            ("mira", {"text": NOTE_MIRA, "kind": "person", "about": "Mira"}),
            ("trip", {"text": NOTE_TRIP, "kind": "plan", "about": "Mira", "due": "2027-07"})]),
        (HEADACHE, "Understood. I'll keep the stages below 2,500 metres where the route allows.", [
            ("headache", {"text": NOTE_HEADACHE, "kind": "constraint",
                          "affect": {"label": "worried", "valence": -1, "intensity": 1, "basis": "reported",
                                     "topic": "altitude headaches"}})]),
        (JOKE, "Glad it landed! The huts really do have surprisingly good Wi-Fi.", [
            ("joke", {"text": NOTE_JOKE, "kind": "milestone", "shared": True, "moment": "play"})]),
        (HUT, "Noted: Rifugio Biella for the night of 5 July.", [
            ("hut", {"text": NOTE_HUT, "kind": "plan", "about": "Mira", "due": "2027-07-05"})]),
    ]),
    ("tidepool-day2", 2, [
        (DECISION, "Sounds good: PostgreSQL for Tidepool. I'll start with a connection config.", [
            ("decision", {"text": NOTE_DECISION, "kind": "other"})]),
        (PNPM[1], "Noted, I'll use pnpm for the frontend.", [
            ("pnpm", {"text": NOTE_PNPM, "kind": "preference"})]),
        ("Set up a users table and a projects table to start with.",
         "Done: users and projects tables, with a foreign key from projects to users.", []),
    ]),
    ("hangzhou-day3", 3, [
        (HANGZHOU, "好的，我会提醒你提前订高铁票和断桥附近的酒店。", [
            ("hangzhou", {"text": NOTE_HANGZHOU, "kind": "plan"})]),
        ("外婆喜欢龙井茶，我想带一盒新茶过去。", "好主意，新茶一般四月上市，现在可以买去年的明前龙井。", []),
    ]),
    ("tidepool-day3", 3, [
        (CORRECTION, "Got it: PostgreSQL on the server, SQLite for local development.", [
            ("corrected", {"text": NOTE_CORRECTED, "kind": "other", "replaces": ["decision"]})]),
        (PNPM[3], "pnpm it is.", []),
        ("Let's write the migration for the projects table next.", "Here is the migration for the projects table.", []),
    ]),
    ("evening-day5", 5, [
        (TRAIN, "That's a miserable way to lose an afternoon. Want to pick up anything light tonight?", [
            ("train", {"text": NOTE_TRAIN, "kind": "other",
                       "affect": {"label": "frustrated", "valence": -1, "intensity": 2, "basis": "inferred",
                                  "topic": "the cancelled train"}})]),
        (CLIMB, "Got it: Tuesday and Thursday evenings stay free for bouldering.", [
            ("climb", {"text": NOTE_CLIMB, "kind": "routine"})]),
    ]),
    ("trip-day6", 6, [
        (MOVED, "Updated: Rifugio Biella for the night of 3 July.", [
            ("moved", {"text": NOTE_MOVED, "kind": "plan", "about": "Mira", "due": "2027-07-03",
                       "replaces": ["hut"]})]),
        ("Which stage of the route is the longest?", "Stage 5, from Rifugio Lagazuoi to Rifugio Averau, is the "
         "longest in time, though not in distance.", []),
    ]),
]


def project_talk(days, rounds):
    """Ordinary project talk: ``rounds`` exchanges a day on each of ``days``, no notes."""
    return [(f"tidepool-talk-day{day}", day, [
        (f"Next up is {FILLER_TOPICS[index % len(FILLER_TOPICS)]} (round {day}.{index}).",
         f"Here is a first pass on that ({day}.{index}).", []) for index in range(rounds)]) for day in days]


WORLDS = {"small": SESSIONS + project_talk((4,), 8),
          "large": SESSIONS + project_talk((4, 7, 8), 40)}


@dataclass
class World:
    name: str
    memory: object = None
    note_ids: dict = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        return self.memory.directory

    def client(self):
        return self.memory.client()

    def conversation(self, session: str, turns: list) -> None:
        client, server, _schemas, _instructions = self.memory.tools()
        try:
            plugin.session_start({"session_id": session}, self.directory)
            for index, (text, reply, notes) in enumerate(turns):
                context = plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": f"t{index}"},
                                             self.directory)
                references, capture = _source(context)
                for key, arguments in notes:
                    arguments = {**arguments, "source_messages": references, "recording_capture": capture}
                    if "replaces" in arguments:
                        arguments["replaces"] = [self.note_ids[name] for name in arguments["replaces"]]
                    result = call(server, "memory_note", arguments)
                    assert result.get("note_id"), result
                    self.note_ids[key] = result["note_id"]
                plugin.stop({"session_id": session, "prompt_id": f"t{index}", "last_assistant_message": reply},
                            self.directory)
        finally:
            client.close()


@contextmanager
def built_world(tmp_path_factory, name: str):
    """A world played to its end, its service left running for the page; stopped afterwards. Skipped (as the other
    service tests are) without the embedded database."""
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
    try:
        world.memory = harness.Memory(directory, None, (free_port(), free_port()), DAY[1])
        for session, day, turns in sorted(WORLDS[name], key=lambda entry: entry[1]):
            world.memory.clock.advance(directory, DAY[day], run=directory.name)
            world.conversation(session, turns)
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


__all__ = ["CLIMB", "HANGZHOU", "HEADACHE", "HUT", "JOKE", "MOVED", "NOTE_CORRECTED", "NOTE_HANGZHOU", "NOTE_MOVED",
           "NOTE_TRIP", "TRAIN", "TRIP", "WORLDS", "World", "built_world"]
