"""A correction is visible as a correction, and a deletion reaches everything shown of it: the trust checks.

Each test plays the Tidepool correction on its own real local installation through the plugin's hooks and MCP tools
on the scenario clock (``resume_correction_world``'s harness, no model call): day 1 the decision and its note A,
day 3 the correction and note B replacing A, and with ``chain`` day 5 a second change and note C replacing B. Then
it does one thing the user or the host can do (delete the day-1 or the day-3 message, delete the replaced note,
delete the current note, hide instead of delete, restore an archive taken before or after, erase everything) and
reads what every reader shows on day 8: the host's notes block and history, the per-prompt recall block, the recall
tool, the page's notes (their lineage and source lists), conversations and search results as the page reads them
from the service, an export and the brain map. After each it checks:

- nothing of a deleted record is shown: no sentence, and no lineage clause, earlier-note line or mark that names its
  date;
- no mark points at a note that is not current, and every mark names the current note heading the chain;
- no message is listed as the support of a note it did not support: a note's own messages are the ones it was
  saved from, the messages behind the notes it replaced are listed as theirs, and the map links them the same way;
- what the stated rules say survives does: the dependency model below.
"""
from __future__ import annotations

import datetime
import json
import re
from contextlib import contextmanager
from pathlib import Path

import pytest
from resume_correction_world import (
    CORRECTION,
    DAY,
    DECISION,
    NOTE_CORRECTED,
    NOTE_DECISION,
    NOTE_THIRD,
    THIRD,
    _source,
    block,
    call,
    free_port,
    harness,
    history_lines,
    note_lines,
)

from membrain import embedded_database, evaluation_clock, host, plugin
from membrain.helpers import local_date
from membrain.notes import NOTES_CONVERSATION

pytestmark = pytest.mark.integration

MESSAGES = {"day1": DECISION, "day3": CORRECTION, "day5": THIRD}
NOTES = {"A": NOTE_DECISION, "B": NOTE_CORRECTED, "C": NOTE_THIRD}
SAID_IN = {"A": "day1", "B": "day3", "C": "day5"}  # The message each note was saved from, in the same turn.
REPLACES = {"B": "A", "C": "B"}
QUERIES = ("database", "local install", "PostgreSQL")
PROMPT = "Which database should the local install use?"


class Play:
    """One installation, played through the hooks Claude Code calls and the plugin's MCP server."""

    def __init__(self, memory, chain: bool):
        self.memory, self.chain, self.ids, self.archives = memory, chain, {}, {}

    @property
    def directory(self) -> Path:
        return self.memory.directory

    def day(self, number: int) -> None:
        self.memory.clock.advance(self.directory, DAY[number], run=self.directory.name)

    def turn(self, session: str, text: str, reply: str, note: str | None = None) -> None:
        client, server, _schemas, _instructions = self.memory.tools()
        try:
            plugin.session_start({"session_id": session}, self.directory)
            context = plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": "t0"}, self.directory)
            if note:
                references, capture = _source(context)
                arguments = {"text": NOTES[note], "source_messages": references, "recording_capture": capture,
                             "kind": "other"}
                if note in REPLACES:
                    arguments["replaces"] = [self.ids[REPLACES[note]]]
                result = call(server, "memory_note", arguments)
                assert result.get("note_id"), result
                self.ids[note] = result["note_id"]
            plugin.stop({"session_id": session, "prompt_id": "t0", "last_assistant_message": reply}, self.directory)
        finally:
            client.close()

    def messages(self) -> dict[str, dict]:
        with self.memory.client() as client:
            items = client.timeline(roles=("user",), max_characters=200_000, max_item_characters=20_000,
                                    limit=1000)["items"]
        return {item["text"]: item for item in items if item["conversation_id"] != NOTES_CONVERSATION}

    def export(self, name: str) -> None:
        """The user's own copy, as the page's export downloads it: kept as it was then."""
        with self.memory.client() as client:
            self.archives[name] = client.download_archive(client.export()["result"]["archive_id"])["document"]

    def restore(self, name: str) -> None:
        """That copy uploaded and restored into the same memory."""
        with self.memory.client() as client:
            uploaded = client.upload_archive(self.archives[name])
            generation = client.dashboard()["brain"]["scope_generation"]
            result = client.restore(uploaded["archive_id"], expected_manifest_sha256=uploaded["manifest_sha256"],
                                    expected_scope_generation=generation)
        assert result.get("outcome") == "completed", result

    def forget(self, ids, *, mode="erase_content", conversation=None, tool=False) -> None:
        """As the memory page's Delete sends it, or (``tool``) as the host's memory_forget tool does."""
        client, server, _schemas, _instructions = self.memory.tools()
        try:
            generation = client.dashboard()["brain"]["scope_generation"]
            if tool:
                result = call(server, "memory_forget", {"ids": list(ids), "kind": "events", "mode": mode,
                                                        "expected_scope_generation": generation,
                                                        "conversation_id": conversation})
            else:
                result = client.forget(list(ids), kind="events", mode=mode, expected_scope_generation=generation,
                                       conversation_id=conversation)
        finally:
            client.close()
        assert result.get("outcome") == "completed", result

    def observe(self) -> dict:
        """Everything each reader shows on day 8."""
        self.day(8)
        session = f"tidepool-day8-{len(self.archives)}-{datetime.datetime.now().timestamp()}"
        opening = plugin.session_start({"session_id": session}, self.directory) or ""
        prompt = plugin.user_prompt({"session_id": session, "prompt": "finish the local install", "prompt_id": "t0"},
                                    self.directory) or ""
        client, server, _schemas, _instructions = self.memory.tools()
        try:
            recall_tool = {query: call(server, "memory_recall", {"query": query}).get("context") or ""
                           for query in QUERIES}
            # The per-prompt recall block, as the prompt hook writes it when the history is not complete.
            recall_block = host.recall_context(client, PROMPT, current_conversation=session) or ""
            notes_page = client.timeline(roles=("user", "assistant"), conversation_id=NOTES_CONVERSATION,
                                         max_characters=200_000, max_item_characters=20_000, limit=1000)["items"]
            messages_page = [item for item in client.timeline(
                roles=("user", "assistant"), max_characters=200_000, max_item_characters=20_000,
                limit=1000)["items"] if item["conversation_id"] != NOTES_CONVERSATION]
            graph = client.memory_map()
        finally:
            client.close()
        plugin.stop({"session_id": session, "prompt_id": "t0", "last_assistant_message": "On it."}, self.directory)
        exported = host.export_user(self.directory, None)
        return {"opening": opening, "prompt": prompt, "recall_tool": recall_tool, "recall_block": recall_block,
                "notes_page": notes_page, "messages_page": messages_page, "map": graph, "export": exported}


@contextmanager
def played(tmp_path_factory, name: str, chain: bool):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    patch = pytest.MonkeyPatch()
    patch.setenv("MEMBRAIN_SEMANTIC", "0")
    patch.setenv("PYTHON_DOTENV_DISABLED", "1")
    patch.setenv(evaluation_clock.ENV, "")
    patch.setattr(harness, "STUB", True)
    directory = tmp_path_factory.mktemp(name) / "brain"
    try:
        memory = harness.Memory(directory, None, (free_port(), free_port()), DAY[1])
        play = Play(memory, chain)
        play.turn("tidepool-day1", DECISION, "PostgreSQL it is.", note="A")
        play.export("before")  # Before the correction.
        play.day(3)
        play.turn("tidepool-day3", CORRECTION, "Server on PostgreSQL, local on SQLite.", note="B")
        if chain:
            play.day(5)
            play.turn("tidepool-day5", THIRD, "DuckDB locally, PostgreSQL on the server.", note="C")
        play.export("after")  # After the last correction.
        messages = play.messages()
        play.ids.update({key: messages[text]["event_id"] for key, text in MESSAGES.items() if text in messages})
        yield play
    finally:
        from membrain import desktop

        try:
            if directory in harness.STARTED:
                harness.STARTED.remove(directory)
                desktop.stop(directory)
        finally:
            evaluation_clock.disable()
            patch.undo()


# The rules, as a model: each record's dependencies, and what deleting or hiding one reaches -------------------------

def edges(chain: bool) -> set[tuple[str, str]]:
    """(input, output): a note on its message, a replacement on its predecessor's messages (kept as its own deletion
    dependencies) and the replaced note on the note that replaced it."""
    found = {("day1", "A"), ("day1", "B"), ("day3", "B"), ("B", "A")}
    if chain:
        found |= {("day1", "C"), ("day3", "C"), ("day5", "C"), ("C", "B")}
    return found


def reached(chain: bool, start: str) -> set[str]:
    found, frontier = {start}, {start}
    while frontier:
        frontier = {output for source, output in edges(chain) if source in frontier} - found
        found |= frontier
    return found


ACTS = ["delete_day1", "delete_day3", "delete_replaced", "delete_middle", "delete_current", "hide_current",
        "hide_day1", "restore_before", "restore_after_deleting_current", "erase_everything", "nothing"]


def perform(play: Play, act: str) -> tuple[set[str], set[str]]:
    """Do ``act``; the records it erases and the ones it hides, by the model."""
    chain, current = play.chain, "C" if play.chain else "B"
    if act == "nothing":
        return set(), set()
    if act in ("delete_day1", "delete_day3"):
        key = act.split("_")[1]
        play.forget([play.ids[key]], conversation=f"tidepool-{key}")
        return reached(chain, key), set()
    if act == "delete_replaced":  # The oldest note: the page does not show it, so the host forgets it by its id.
        play.forget([play.ids["A"]], conversation=NOTES_CONVERSATION, tool=True)
        return reached(chain, "A"), set()
    if act == "delete_middle":  # B: replaced in a chain, current otherwise.
        play.forget([play.ids["B"]], conversation=NOTES_CONVERSATION, tool=chain)
        return reached(chain, "B"), set()
    if act == "delete_current":  # The page's Delete on the note it shows.
        play.forget([play.ids[current]], conversation=NOTES_CONVERSATION)
        return reached(chain, current), set()
    if act == "hide_current":
        play.forget([play.ids[current]], mode="suppress_recall", conversation=NOTES_CONVERSATION, tool=True)
        return set(), reached(chain, current)
    if act == "hide_day1":
        play.forget([play.ids["day1"]], mode="suppress_recall", conversation="tidepool-day1", tool=True)
        return set(), reached(chain, "day1")
    if act == "restore_before":  # An archive from before the correction brings nothing back.
        play.restore("before")
        return set(), set()
    if act == "restore_after_deleting_current":
        play.forget([play.ids[current]], conversation=NOTES_CONVERSATION)
        play.restore("after")
        return reached(chain, current), set()
    assert act == "erase_everything"
    host.erase_user(play.directory, None)
    return {"day1", "day3", "day5", "A", "B", "C"}, set()


def chain_of(key: str) -> list[str]:
    """The notes ``key`` replaced, newest first."""
    found = []
    while key in REPLACES:
        key = REPLACES[key]
        found.append(key)
    return found


def text_of(key: str) -> str:
    return MESSAGES.get(key) or NOTES[key]


def everything(seen: dict) -> str:
    return "\n".join([seen["opening"], seen["prompt"], *seen["recall_tool"].values(), seen["recall_block"],
                      json.dumps(seen["notes_page"], ensure_ascii=False),
                      json.dumps(seen["messages_page"], ensure_ascii=False), json.dumps(seen["map"], ensure_ascii=False),
                      json.dumps(seen["export"], ensure_ascii=False)])


def lines(seen: dict) -> list[str]:
    """Every line a host reads: notes block, history, recall block, recall tool."""
    found = note_lines(seen["opening"]) + history_lines(seen["opening"])
    for text in (seen["prompt"], seen["recall_block"], *seen["recall_tool"].values()):
        found += [line for line in block(text, "membrain-memory").splitlines() if line.startswith("- [")]
    return found


def check(play: Play, act: str, seen: dict, erased: set[str], hidden: set[str]) -> None:
    ids = play.ids
    key_of = {value: key for key, value in ids.items()}
    notes = [key for key in ("A", "B", "C") if key in ids]
    gone = erased | hidden
    # Current: neither erased nor hidden, and not replaced by another note of this play.
    current = [key for key in notes if key not in gone and not any(REPLACES.get(other) == key for other in notes)]
    live = {key for key in notes if key not in erased}  # Content still stored (hidden or replaced included).
    shown = everything(seen)

    # 1. Nothing of an erased or hidden record: its sentence is in no reader, the export included.
    for key in gone:
        assert text_of(key) not in shown, (act, key)
    # 2. The notes the host and the page show are exactly the current ones.
    assert sorted(key_of[item["event_id"]] for item in seen["notes_page"]) == sorted(current)
    assert sorted(key_of[line.rsplit("(id: ", 1)[1].rstrip(")")] for line in note_lines(seen["opening"])) == sorted(current)
    note_days = {key_of[item["event_id"]]: local_date(item["recorded_at"]) for item in seen["notes_page"]}
    for item in seen["notes_page"]:
        key = key_of[item["event_id"]]
        predecessors = chain_of(key)
        entries = item.get("replaced", [])
        # 3. Lineage: every note it replaced, newest first; content only while stored, never once erased.
        assert [key_of[entry["event_id"]] for entry in entries] == predecessors
        for entry in entries:
            name = key_of[entry["event_id"]]
            if name in live:
                assert entry["text"].endswith(NOTES[name]) and "erased" not in entry
            else:
                assert set(entry) == {"event_id", "depth", "source_event_ids", "erased"}
        # 4. Sources: its own are the message it was said in; the earlier notes' are theirs, never presented as its.
        earlier = {key_of[source] for entry in entries for source in entry["source_event_ids"]}
        own = {key_of[source] for source in item["source_event_ids"]} - earlier
        assert own == {SAID_IN[key]}, (act, key, own)
        assert earlier == {SAID_IN[name] for name in predecessors}, (act, key, earlier)
        # The host's line names the day of the note it replaced while that one's content exists, and nothing else.
        line = next(line for line in note_lines(seen["opening"]) if ids[key] in line)
        direct = REPLACES.get(key)
        if direct in live:
            day = local_date(next(entry for entry in entries if key_of[entry["event_id"]] == direct)["recorded_at"])
            assert f"(replaces your note of {day})" in line
        else:
            assert "(replaces" not in line
    # 5. Marks: only on a message a live replaced note rests on, naming the current note that heads its chain.
    heads = {}
    for key in current:
        for name in chain_of(key):
            if name in live:
                heads.setdefault(SAID_IN[name], key)
    for item in seen["messages_page"]:
        name = key_of.get(item["event_id"])
        mark = item.get("superseded_by")
        expected = heads.get(name)
        assert (key_of[mark["note_id"]] if mark else None) == expected, (act, name, mark)
    for line in lines(seen):
        found = re.search(r"superseded by your note of (\d{4}-\d{2}-\d{2})", line)
        text = next((value for key, value in MESSAGES.items() if value[:60] in line), None)
        message = next((key for key, value in MESSAGES.items() if value == text), None)
        if message in heads:
            assert found and found.group(1) == note_days[heads[message]], (act, line)
        else:
            assert not found, (act, line)
    # 6. The map: a note links the message it was said in as its source, its predecessors' as theirs; a replaced
    # note is a label on its node, while its content exists, never a node.
    nodes = {node["id"]: node for node in seen["map"]["nodes"]}
    for key in notes:
        if key not in current:
            assert "note:" + ids[key] not in nodes
    for key in current:
        node = nodes["note:" + ids[key]]
        links = {(key_of[edge["target"].split(":", 1)[1]], edge["type"]) for edge in seen["map"]["edges"]
                 if edge["source"] == node["id"] and edge["target"].startswith("msg:")}
        predecessors = chain_of(key)
        visible = {name for name in (*MESSAGES,) if name in ids and name not in gone}
        assert links == ({(SAID_IN[key], "derived_from")}
                         | {(SAID_IN[name], "replaced_source") for name in predecessors}) & {
            (name, kind) for name in visible for kind in ("derived_from", "replaced_source")}
        direct = REPLACES.get(key)
        labels = [entry["label"] for entry in node.get("replaces", [])]
        assert labels == ([NOTES[direct][:79] + "…" if len(NOTES[direct]) > 80 else NOTES[direct]]
                          if direct in live else [])
    # 7. The recall tool leads with the current note that matches.
    if current:
        context = seen["recall_tool"]["database"]
        first = next(line for line in context.splitlines() if line.startswith("- ["))
        assert " · note] " in first and NOTES[current[0]] in first
    # 8. The export holds no erased record and every current one.
    exported = {event["event_id"] for event in seen["export"]["document"]["events"]} if "document" in seen["export"] \
        else {event["event_id"] for event in seen["export"]["events"]}
    assert not exported & {ids[key] for key in erased if key in ids}
    assert {ids[key] for key in current} <= exported


@pytest.mark.parametrize("act", ACTS)
@pytest.mark.parametrize("chain", [False, True], ids=["A-B", "A-B-C"])
def test_what_every_reader_shows_after_each_act(tmp_path_factory, chain, act):
    if act == "delete_middle" and not chain:
        pytest.skip("B is the current note without a chain: delete_current covers it")
    with played(tmp_path_factory, f"trust-{act}-{'chain' if chain else 'pair'}", chain) as play:
        erased, hidden = perform(play, act)
        seen = play.observe()
        check(play, act, seen, erased, hidden)
