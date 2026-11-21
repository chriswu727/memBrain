"""A host forgets what the user asks with one call of ``memory_forget``, using only what a host has.

Real-host trial, 2026-11-19 (Claude Code): the user had said "For the frontend packages I prefer pnpm over npm." and the
host had saved a preference note from it. In a later session the user said "Forget what I told you about pnpm. I don't
want that kept." The host looked the tool up, passed the note's id from the notes block as a "memory" with a scope
generation of 0 (a bare HTTP 422), looked the generation up with memory_inspect ("not found"), and was then told
"completed" with zero objects affected. The note and the message stayed, and the note stayed in the notes block.

These tests play that sequence and its neighbours through the plugin's hooks and tool server on a real local service,
with nothing a host would not have: the notes block's ids, the tool's own description and its answers. No skill.
"""
import asyncio
import json
import re

import httpx
import pytest

from membrain import desktop, embedded_database, host, host_forget, plugin
from membrain.client import MemoryActionError
from membrain.helpers import local_date
from membrain.mcp_server import create_server
from membrain.notes import NOTES_CONVERSATION

PNPM = "For the frontend packages I prefer pnpm over npm."
PNPM_REPLY = "Noted, I'll use pnpm for the frontend."
NOTE_PNPM = "Prefers pnpm over npm for frontend packages."
DECISION = "Let's get the Tidepool backend going. Decision: we'll use PostgreSQL as the database for the project."
NOTE_DECISION = "Tidepool project: uses PostgreSQL as its database."
FORGET = "Forget what I told you about pnpm. I don't want that kept."
STOP = "Do not keep using it from earlier in this conversation."
NOTE_ID = re.compile(r"\(id: ([0-9a-f-]{36})\)")
HTTPISH = re.compile(r"\b[45]\d\d\b|https?://|Unprocessable|Client error")

needs_service = pytest.mark.skipif(not embedded_database.available(),
                                   reason="embedded PostgreSQL binaries are not installed")


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def call(server, name, arguments):
    _, result = asyncio.run(server.call_tool(name, arguments))
    return result


def turn(directory, session, number, text, reply, server=None, note=None, **fields):
    """One exchange as Claude Code's hooks report it; with ``note`` the host saves that note from this message, as
    the source block of the prompt context tells it to. Returns the note's id."""
    context = plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": f"t{number}"}, directory)
    note_id = None
    if note:
        references, _ = json.JSONDecoder().raw_decode(context.split("source_messages=", 1)[1])
        capture, _ = json.JSONDecoder().raw_decode(context.split("recording_capture=", 1)[1])
        saved = call(server, "memory_note", {"text": note, "source_messages": references,
                                             "recording_capture": capture, **fields})
        assert saved.get("note_id"), saved
        note_id = saved["note_id"]
    plugin.stop({"session_id": session, "prompt_id": f"t{number}", "last_assistant_message": reply}, directory)
    return note_id


def note_id_in(block: str, sentence: str) -> str:
    """The id a host reads off the notes block line of ``sentence``."""
    line = next(line for line in block.splitlines() if sentence in line)
    return NOTE_ID.search(line)[1]


def everything(client) -> list[dict]:
    """Every stored message and note, as the memory page reads them."""
    return client.timeline(roles=("user", "assistant"), max_characters=200_000, max_item_characters=20_000,
                           limit=1000)["items"]


def day_of(client, text: str) -> str:
    return local_date(next(item for item in everything(client) if item["text"] == text)["recorded_at"])


def id_of(client, text: str) -> str:
    return next(item for item in everything(client) if item["text"] == text)["event_id"]


def stopped(directory):
    try:
        desktop.stop(directory)
    except desktop.DesktopError:
        pass


# What a plugin host is handed, without a service -----------------------------------------------------------------

class Configured:
    brain_id = "brain"


def test_a_plugin_host_is_offered_the_simple_forget_tool_and_none_of_the_low_level_ones(tmp_path):
    listed = {tool.name: tool for tool in asyncio.run(create_server(Configured(), directory=tmp_path).list_tools())}
    assert set(listed) == {"memory_recall", "memory_note", "memory_consolidate", "memory_boundary", "memory_pause",
                           "memory_resume", "memory_manner_feedback", "memory_persona", "memory_forget"}
    forget = listed["memory_forget"]
    assert forget.description == host_forget.TOOL_DESCRIPTION and len(host_forget.TOOL_DESCRIPTION) == 465
    assert forget.inputSchema["properties"] == {"ids": host_forget.IDS_FIELD, "query": host_forget.QUERY_FIELD}
    assert not forget.inputSchema.get("required") and forget.annotations.destructiveHint
    # The description alone says what to pass and what goes with it: what the trial's host lacked.
    for words in ("notes block", "query", "nothing is erased", "asking the user first", "Tell the user"):
        assert words in forget.description
    # A standalone MCP client keeps the low-level tools: for it they are the only interface.
    tools_only = {tool.name for tool in asyncio.run(
        create_server(Configured(), directory=tmp_path, require_turn_capture=False).list_tools())}
    assert {"memory_capabilities", "memory_inspect", "memory_observe", "memory_prepare", "memory_checkpoint",
            "memory_forget"} <= tools_only
    generic = {tool.name: tool for tool in asyncio.run(create_server(Configured()).list_tools())}
    assert {"kind", "mode", "expected_scope_generation"} <= set(generic["memory_forget"].inputSchema["properties"])


def test_the_review_reads_the_tools_a_plugin_host_is_offered_and_those_it_was_offered_before(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "acceptance_review_tools", Path(__file__).parents[1] / "evaluations" / "acceptance_review.py")
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    listed = [tool.name for tool in asyncio.run(create_server(Configured(), directory=tmp_path).list_tools())]
    assert review._PLUGIN_TOOLS == set(listed) and len(listed) == 9
    assert review._tool_code({"name": "memory_inspect", "arguments": {}}) == "memory_inspect"  # An earlier run's.


@pytest.mark.parametrize("arguments,message", [
    ({}, "Nothing was erased: pass ids (a note's id from the notes block, or a message's id) or query (a few words "
         "about what to forget)."),
    ({"ids": [], "query": "  "}, "Nothing was erased: pass ids (a note's id from the notes block, or a message's id) "
                                 "or query (a few words about what to forget)."),
    # The arguments of the earlier low-level form are ignored, not refused: a host repeating them still gets through.
    ({"kind": "memories", "mode": "erase_content", "expected_scope_generation": 0},
     "Nothing was erased: pass ids (a note's id from the notes block, or a message's id) or query (a few words "
     "about what to forget)."),
    ({"ids": ["a"], "query": "pnpm"}, "Nothing was erased: pass either ids or query, not both."),
    ({"ids": [str(number) for number in range(21)]}, "Nothing was erased: pass at most 20 ids in one call."),
    ({"ids": [7]}, "Nothing was erased: each id must be an id as the notes block or a search shows it."),
    ({"query": ["pnpm"]}, "Nothing was erased: query must be a few words of text."),
    ({"query": "pnpm " * 70}, "Nothing was erased: keep query to a few words."),
])
def test_a_call_the_tool_cannot_use_is_refused_with_a_sentence(tmp_path, arguments, message):
    result = call(create_server(Configured(), directory=tmp_path), "memory_forget", arguments)
    assert result == {"outcome": "refused", "message": message}
    assert not HTTPISH.search(message)


def test_a_refusal_or_failure_of_the_service_reaches_the_host_as_a_sentence_without_an_http_status(tmp_path):
    request = httpx.Request("POST", "http://127.0.0.1:53785/v1/actions")

    class Refusing(Configured):
        def timeline(self, **options):
            response = httpx.Response(422, request=request, json={"error": {
                "code": "validation_failed", "message": "Timeline event IDs are not valid identifiers."}})
            response.raise_for_status()

        def recall(self, query, **options):
            self.timeline()

    result = call(create_server(Refusing(), directory=tmp_path), "memory_forget", {"ids": ["x"]})
    assert result == {"outcome": "error", "message": "Nothing was erased: timeline event IDs are not valid "
                                                     "identifiers. Try again in a moment."}

    class Unreachable(Configured):
        def timeline(self, **options):
            raise httpx.ConnectError("connection refused", request=request)

    result = call(create_server(Unreachable(), directory=tmp_path), "memory_forget", {"ids": ["x"]})
    assert result == {"outcome": "error", "message": "Nothing was erased: memory is not reachable right now. Try "
                                                     "again in a moment."}

    class Bare(Configured):  # A status without a JSON body still gives no status or link.
        def timeline(self, **options):
            httpx.Response(500, request=request, text="oops").raise_for_status()

    result = call(create_server(Bare(), directory=tmp_path), "memory_forget", {"ids": ["x"]})
    assert result == {"outcome": "error", "message": "Nothing was erased: memory could not do it right now. Try "
                                                     "again in a moment."}
    # The search with ids that the forget path names answers the same way.
    found = call(create_server(Refusing(), directory=tmp_path), "memory_recall", {"query": "pnpm", "with_ids": True})
    assert not HTTPISH.search(found["error"])


def test_a_server_waiting_for_its_service_answers_a_lost_connection_with_its_own_sentence(tmp_path):
    """Before anything is erased, a connection that cannot be made reaches the tool server's guard, which reconnects
    and answers with the service's state, as every other tool does (``create_server(pending=...)``)."""
    request = httpx.Request("GET", "http://127.0.0.1:9/v1/brains/brain/timeline")

    class Gone(Configured):
        def timeline(self, **options):
            raise httpx.ConnectError("connection refused", request=request)

    class Pending:
        client, lost_calls = Gone(), []

        def wake(self):
            pass

        def lost(self):
            self.lost_calls.append(True)
            self.client = None

        def refusal(self):
            return {"error": "Memory is starting; try again in a moment."}

    pending = Pending()
    server = create_server(None, directory=tmp_path, pending=pending)
    assert call(server, "memory_forget", {"ids": ["x"]}) == {"error": "Memory is starting; try again in a moment."}
    assert pending.lost_calls == [True]


# The trial, on a real service ------------------------------------------------------------------------------------

@needs_service
def test_the_trials_request_forgets_the_pnpm_note_and_its_message_in_one_call(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            plugin.session_start({"session_id": "day1"}, directory)
            turn(directory, "day1", 1, DECISION, "PostgreSQL it is.", server, NOTE_DECISION, kind="other")
            turn(directory, "day1", 2, PNPM, PNPM_REPLY, server, NOTE_PNPM, kind="preference")
            day = day_of(client, PNPM)

        # A later session: the host has the notes block, and the user asks.
        opening = plugin.session_start({"session_id": "day2"}, directory)
        pnpm_note = note_id_in(opening, NOTE_PNPM)
        context = plugin.user_prompt({"session_id": "day2", "prompt": FORGET, "prompt_id": "t1"}, directory)
        assert context is not None
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)  # The host's connection for this session.
            result = call(server, "memory_forget", {"ids": [pnpm_note]})
            assert result == {
                "outcome": "forgotten", "notes_erased": 1, "messages_erased": 2,
                "message": f"Forgotten for good: the note of {day}; the message it came from, said on {day}; your "
                           f"reply to it. {STOP}"}
            assert not HTTPISH.search(result["message"]) and "pnpm" not in result["message"]
            # Asked again in the same conversation: truthful, and nothing more happens.
            again = call(server, "memory_forget", {"ids": [pnpm_note]})
            assert again == {"outcome": "already_forgotten", "not_found": [pnpm_note],
                             "message": "Nothing more was erased: this was already forgotten earlier in this "
                                        f"conversation. {STOP}"}
        plugin.stop({"session_id": "day2", "prompt_id": "t1", "last_assistant_message": "Done, it's forgotten."},
                    directory)

        # The next message of the same session gets the refreshed notes, without the note.
        later = plugin.user_prompt({"session_id": "day2", "prompt": "Which package manager should the frontend use?",
                                    "prompt_id": "t2"}, directory)
        assert "<membrain-updates>" in later and NOTE_DECISION in later
        assert "pnpm" not in later
        plugin.stop({"session_id": "day2", "prompt_id": "t2", "last_assistant_message": "Any you like."}, directory)

        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)  # A new session's connection.
            recalled = call(server, "memory_recall", {"query": "pnpm npm frontend packages"})
            with_ids = call(server, "memory_recall", {"query": "pnpm npm frontend packages", "with_ids": True})
            stored = everything(client)
            page = json.dumps({"timeline": stored, "affect": client.affect_records(),
                               "map": client.memory_map(include_sensitive=True)}, ensure_ascii=False)
            # Not "completed" for nothing: an id that matches nothing now is refused, with what to do next.
            gone = call(server, "memory_forget", {"ids": [pnpm_note]})
            assert gone == {"outcome": "not_found", "not_found": [pnpm_note], "message": (
                f"Nothing was erased. No note or message with the id {pnpm_note} is stored now; it may have been "
                "forgotten already. To find what the user means, call memory_forget with query: a few words about it.")}
        exported = json.dumps(host.export_user(directory, None), ensure_ascii=False)
        opening = plugin.session_start({"session_id": "day3"}, directory)
        for seen in (recalled["context"], json.dumps(with_ids), page, exported, opening):
            assert "pnpm" not in seen
        assert NOTE_DECISION in opening and DECISION in [item["text"] for item in stored]
        # The request to forget, said in the turn that erased, is not kept either: the erasure revoked that turn's
        # recording capture, so the hooks drop it when the turn ends.
        assert FORGET not in [item["text"] for item in stored]
        assert "off the record" not in opening  # Nor is it reported as an off-the-record stretch.
    finally:
        stopped(directory)


@needs_service
def test_a_message_id_or_a_description_finds_and_forgets_without_erasing_anything_by_guess(tmp_path):
    directory = tmp_path / "brain"
    workspaces = "Does pnpm work with workspaces?"
    dentist, note_dentist = "My dentist is Dr. Alvarez, Thursday at 3 pm.", "Dentist: Dr. Alvarez, Thursday 3 pm."
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            plugin.session_start({"session_id": "s1"}, directory)
            dentist_note = turn(directory, "s1", 1, dentist, "Noted.", server, note_dentist, kind="plan")
            turn(directory, "s1", 2, workspaces, "Yes, pnpm supports workspaces.")
            pnpm_note = turn(directory, "s1", 3, PNPM, PNPM_REPLY, server, NOTE_PNPM, kind="preference")
            day = day_of(client, PNPM)
            before = len(everything(client))

            # No match: nothing erased, and the host is told to try other words.
            assert call(server, "memory_forget", {"query": "kayaking trip"}) == {
                "outcome": "no_match", "candidates": [],
                "message": "Nothing was erased, and nothing in memory matches those words. Try other words (a name, "
                           "place, date or topic), or ask the user what they mean."}
            # Several matches: the note (its message goes with it, so it is not listed apart) and another message.
            several = call(server, "memory_forget", {"query": "pnpm"})
            assert several["outcome"] == "candidates"
            assert [(item["kind"], item["id"]) for item in several["candidates"]] == [
                ("note", pnpm_note), ("message", id_of(client, workspaces))]
            assert several["candidates"][0] == {"id": pnpm_note, "kind": "note", "date": day, "starts": NOTE_PNPM}
            assert several["candidates"][1] == {"id": id_of(client, workspaces), "kind": "message", "said_by": "user",
                                                "date": day, "starts": workspaces}
            assert several["message"] == (
                "Nothing was erased yet. 2 possible matches below. Call memory_forget again with the id of what the "
                "user meant; if more than one could be meant, ask the user first. Forgetting a note also erases the "
                "messages it came from; forgetting a message also erases the notes drawn from it.")
            # One match.
            one = call(server, "memory_forget", {"query": "Alvarez dentist"})
            assert [(item["kind"], item["id"]) for item in one["candidates"]] == [("note", dentist_note)]
            assert one["message"].startswith("Nothing was erased yet. 1 possible match below.")
            assert len(everything(client)) == before  # Searching erased nothing.

            # A message's id from a search with ids: the message, the reply and the note drawn from it go.
            records = call(server, "memory_recall", {"query": "frontend packages pnpm npm", "with_ids": True})
            assert records["how_to_forget"] == "To forget records, call memory_forget with their event_id values as ids."
            message = next(record["event_id"] for record in records["records"] if record["text"] == PNPM)
            result = call(server, "memory_forget", {"ids": [message]})
            assert result == {"outcome": "forgotten", "notes_erased": 1, "messages_erased": 2, "message": (
                f"Forgotten for good: the message of {day}; the note drawn from it, of {day}; your reply to it. {STOP}")}
            texts = "\n".join(item["text"] for item in everything(client))  # Notes carry their header.
            assert PNPM not in texts and NOTE_PNPM not in texts and PNPM_REPLY not in texts and workspaces in texts

            # Another person's record (a multi-user host keeps each person's memory apart) is not found from here.
            host.prompt_context(directory, "alice-1", "Alice here: my locker code is 4471.", turn_id="1",
                                user_id="alice")
            host.finish_turn(directory, "alice-1", "Got it, Alice.", turn_id="1", user_id="alice")
            with host.ready_client(directory, "alice") as alice:
                theirs = id_of(alice, "Alice here: my locker code is 4471.")
                refused = call(server, "memory_forget", {"ids": [theirs]})
                assert refused["outcome"] == "not_found" and theirs in refused["message"]
                assert "Alice here: my locker code is 4471." in [item["text"] for item in everything(alice)]

            # While recording is paused, forgetting still works: a pause stops new records, not deletion.
            host.pause(directory)
            paused = call(server, "memory_forget", {"ids": [dentist_note]})
            assert paused["outcome"] == "forgotten" and paused["notes_erased"] == 1 and paused["messages_erased"] == 2
            assert dentist not in [item["text"] for item in everything(client)]
            host.resume(directory)
    finally:
        stopped(directory)


@needs_service
def test_a_corrected_note_takes_the_notes_it_replaced_and_every_message_behind_them(tmp_path):
    directory = tmp_path / "brain"
    first, second = "For the frontend I use npm.", "Actually switch the frontend to pnpm, not npm."
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            plugin.session_start({"session_id": "s1"}, directory)
            old = turn(directory, "s1", 1, first, "npm it is.", server, "Uses npm for the frontend.", kind="preference")
            turn(directory, "s1", 2, second, "Switching to pnpm.", server, "Uses pnpm for the frontend, not npm.",
                 kind="preference", replaces=[old])
            day = day_of(client, first)
        opening = plugin.session_start({"session_id": "s2"}, directory)
        current = note_id_in(opening, "Uses pnpm for the frontend, not npm.")
        assert "(replaces your note of" in opening
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            result = call(server, "memory_forget", {"ids": [current]})
            assert result == {"outcome": "forgotten", "notes_erased": 2, "messages_erased": 4, "message": (
                f"Forgotten for good: the note of {day}; the earlier note it replaced, of {day}; the 2 messages it "
                f"came from, said on {day}; your 2 replies to them. {STOP}")}
            assert "npm" not in json.dumps(everything(client))
        assert "npm" not in json.dumps(host.export_user(directory, None))
        assert "npm" not in plugin.session_start({"session_id": "s3"}, directory)
    finally:
        stopped(directory)


@needs_service
def test_a_message_that_also_supports_another_note_is_kept_and_named_until_the_user_says(tmp_path):
    directory = tmp_path / "brain"
    both = "I prefer pnpm over npm, and my sister Mei is allergic to sesame."
    pair = "I like dark mode in every editor, and my cat is called Miso."
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            plugin.session_start({"session_id": "s1"}, directory)
            context = plugin.user_prompt({"session_id": "s1", "prompt": both, "prompt_id": "t1"}, directory)
            references, _ = json.JSONDecoder().raw_decode(context.split("source_messages=", 1)[1])
            capture, _ = json.JSONDecoder().raw_decode(context.split("recording_capture=", 1)[1])
            pnpm_note = call(server, "memory_note", {"text": NOTE_PNPM, "kind": "preference", "source_messages":
                                                     references, "recording_capture": capture})["note_id"]
            mei_note = call(server, "memory_note", {"text": "Mei is the user's sister; allergic to sesame.",
                                                    "kind": "person", "about": "Mei", "source_messages": references,
                                                    "recording_capture": capture})["note_id"]
            plugin.stop({"session_id": "s1", "prompt_id": "t1", "last_assistant_message": "Noted both."}, directory)
            context = plugin.user_prompt({"session_id": "s1", "prompt": pair, "prompt_id": "t2"}, directory)
            references, _ = json.JSONDecoder().raw_decode(context.split("source_messages=", 1)[1])
            capture, _ = json.JSONDecoder().raw_decode(context.split("recording_capture=", 1)[1])
            dark = call(server, "memory_note", {"text": "Likes dark mode in editors.", "kind": "preference",
                                                "source_messages": references, "recording_capture": capture})["note_id"]
            miso = call(server, "memory_note", {"text": "Miso is the user's cat.", "kind": "person", "about": "Miso",
                                                "source_messages": references, "recording_capture": capture})["note_id"]
            plugin.stop({"session_id": "s1", "prompt_id": "t2", "last_assistant_message": "Nice."}, directory)
            day, message = day_of(client, both), id_of(client, both)

            # Forget the pnpm note: the message also holds the sister's allergy, so it is kept, and said so.
            result = call(server, "memory_forget", {"ids": [pnpm_note]})
            assert result == {
                "outcome": "forgotten", "notes_erased": 1, "messages_erased": 0,
                "kept": [{"id": message, "said_on": day, "also_behind": [mei_note]}],
                "message": f"Forgotten for good: the note of {day}. Kept the message of {day} it came from (id: "
                           f"{message}), because it also supports your note of {day} (id: {mei_note}); it still holds "
                           "what the user said. If they want it gone too, call memory_forget with its id: that also "
                           f"erases that note. {STOP}"}
            texts = "\n".join(item["text"] for item in everything(client))  # Notes carry their header.
            assert NOTE_PNPM not in texts and both in texts and "Mei is the user's sister; allergic to sesame." in texts

            # The user says yes: the message goes, with the note drawn from it and the reply.
            result = call(server, "memory_forget", {"ids": [message]})
            assert result == {"outcome": "forgotten", "notes_erased": 1, "messages_erased": 2, "message": (
                f"Forgotten for good: the message of {day}; the note drawn from it, of {day}; your reply to it. {STOP}")}
            assert "sesame" not in json.dumps(everything(client))

            # Both notes named together: nothing else rests on the message, so it goes too.
            result = call(server, "memory_forget", {"ids": [dark, miso]})
            assert result == {"outcome": "forgotten", "notes_erased": 2, "messages_erased": 2, "message": (
                f"Forgotten for good: the 2 notes of {day}; the message they came from, said on {day}; your reply to "
                f"it. {STOP}")}
            assert "Miso" not in json.dumps(everything(client))
    finally:
        stopped(directory)


@needs_service
def test_the_low_level_route_refuses_ids_that_match_nothing_and_still_answers_a_retry(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            plugin.session_start({"session_id": "s1"}, directory)
            note = turn(directory, "s1", 1, PNPM, PNPM_REPLY, server, NOTE_PNPM, kind="preference")
            generation = client.dashboard()["brain"]["scope_generation"]
            # The trial's second call: a note's id as a "memory". It used to complete with zero objects.
            with pytest.raises(MemoryActionError) as refused:
                client.forget([note], kind="memories", mode="erase_content", expected_scope_generation=generation)
            assert refused.value.code == "not_found_or_forbidden"
            assert str(refused.value) == ("not_found_or_forbidden: No memory with these ids is stored in this memory; "
                                          "nothing was erased.")
            with pytest.raises(MemoryActionError) as refused:
                client.forget(["0b5c8f9e-1111-4222-8333-944455556666"], kind="events", mode="erase_content",
                              expected_scope_generation=generation)
            assert refused.value.code == "not_found_or_forbidden"
            assert client.dashboard()["brain"]["scope_generation"] == generation  # Nothing was recorded.
            assert NOTE_PNPM in json.dumps(everything(client))
            # A real erasure, then the same request again (an uncertain client retrying): the same receipt.
            first = client.forget([note], kind="events", mode="erase_content", expected_scope_generation=generation,
                                  idempotency_key="retry-me")
            again = client.forget([note], kind="events", mode="erase_content", expected_scope_generation=generation,
                                  idempotency_key="retry-me")
            assert first["outcome"] == again["outcome"] == "completed"
            assert first["result"]["deletion_id"] == again["result"]["deletion_id"]
            # An id already erased still matches: deleting it again on the page is not an error.
            generation = client.dashboard()["brain"]["scope_generation"]
            assert client.forget([note], kind="events", mode="erase_content",
                                 expected_scope_generation=generation)["outcome"] == "completed"
            assert NOTE_PNPM not in json.dumps(everything(client))
            assert NOTES_CONVERSATION not in [item["conversation_id"] for item in everything(client)]
    finally:
        stopped(directory)
