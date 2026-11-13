"""The host's own AI indexes earlier messages: memBrain hands it a batch and saves the cues it returns.

memBrain calls no model for this. Once a handful of messages await indexing, a new session is told so in one
sentence; the consolidation tool hands the AI a batch with instructions; its second call saves the cues, and the
batch counts as read. Afterwards recall reaches a message through its cue and the sentence is gone.
"""
import asyncio

import pytest

from membrain import desktop, embedded_database, host
from membrain.mcp_server import create_server

pytestmark = pytest.mark.skipif(not embedded_database.available(),
                                reason="embedded PostgreSQL binaries are not installed")

POTTERY = "I signed up for a pottery class on Thursdays."
THANKS = "Thanks, that helps a lot!"


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def _turn(directory, session, text, reply, turn_id):
    host.prompt_context(directory, session, text, turn_id=turn_id, include_source=True)
    host.finish_turn(directory, session, reply, turn_id=turn_id)


def _call(server, name, arguments):
    _, result = asyncio.run(server.call_tool(name, arguments))
    return result


def test_the_host_ai_is_asked_once_to_index_earlier_messages_and_recall_then_finds_them(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            assert "not been indexed" not in host.session_context(directory, "first")  # Nothing stored yet.
            assert "error" in _call(server, "memory_consolidate", {"cues": []})  # No batch was handed out.
            _turn(directory, "monday", POTTERY, "That sounds fun.", "1")
            _turn(directory, "monday", THANKS, "Any time.", "2")
            # Two messages are not worth the host's model calls: it is asked once a handful have gathered.
            assert "not been indexed" not in host.session_context(directory, "monday-evening")
            for number, text in enumerate(("My sister Ana moved to Porto.", "What is 3 cups in millilitres?",
                                           "I am vegetarian."), start=3):
                _turn(directory, "monday", text, "Noted.", str(number))

            opening = host.session_context(directory, "tuesday")
            assert "5 earlier messages have not been indexed by memory yet." in opening
            assert "memory_consolidate" in opening and "beyond a few words" in opening
            assert "not been indexed" not in host.session_context(directory, "tuesday", tools=None)

            batch = _call(server, "memory_consolidate", {})
            assert [message["text"] for message in batch["messages"]][:2] == [POTTERY, THANKS]
            assert len(batch["messages"]) == 5 and batch["remaining"] == 5
            assert all(type(message["id"]) is int and len(message["date"]) == 10 for message in batch["messages"])
            assert "WHAT KIND of fact" in batch["instructions"] and "reviewed_through" not in batch

            # What a host AI sends back: cues for the facts, none for the thanks and the question. It does not
            # have to repeat which batch it is answering.
            first, sister = batch["messages"][0]["id"], batch["messages"][2]["id"]
            for wrong in ({"cues": [{"id": "one", "cues": ["x"]}]}, {"cues": [{"id": 10_000, "cues": ["x"]}]},
                          {"cues": [{"id": first}]}):
                assert "error" in _call(server, "memory_consolidate", wrong)
            saved = _call(server, "memory_consolidate", {"cues": [
                {"id": first, "cues": ["user hobbies and activities"]},
                {"id": sister, "cues": ["user's sister where she lives", "user family members"]}]})
            assert (saved["indexed"], saved["skipped"], saved["remaining"]) == (2, 0, 0)
            assert "few words" in saved["note"]
            assert _call(server, "memory_consolidate", {})["messages"] == []
            assert "not been indexed" not in host.session_context(directory, "wednesday")

            found = _call(server, "memory_recall", {"query": "What are my hobbies?", "with_ids": True})
            assert any(record["text"] == POTTERY for record in found["records"])
            assert "hobbies and activities" not in str(found)

            host.pause(directory)
            assert "paused" in _call(server, "memory_consolidate", {})["error"]
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_messages_about_a_topic_the_user_asked_not_to_have_raised_are_never_handed_out(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            _turn(directory, "monday", "My ex Jordan called again last night and it rattled me.", "I'm sorry.", "1")
            _turn(directory, "monday", POTTERY, "That sounds fun.", "2")
            _turn(directory, "monday", "Jordan still has my bike, by the way.", "Noted.", "3")
            for number, text in enumerate(("My sister Ana moved to Porto.", "I am vegetarian.", THANKS), start=4):
                _turn(directory, "monday", text, "Noted.", str(number))
            _call(server, "memory_boundary", {"topic": "my ex", "aliases": ["Jordan"]})

            batch = _call(server, "memory_consolidate", {})
            shown = [message["text"] for message in batch["messages"]]
            assert shown == [POTTERY, "My sister Ana moved to Porto.", "I am vegetarian.", THANKS]
            assert "Jordan" not in str(batch) and "My ex" not in str(batch)

            # An id the batch did not hand out is refused, even though it lies before the batch's end.
            hidden = client.pending_message_cues(limit=1)["items"][0]["sequence"]
            assert "error" in _call(server, "memory_consolidate", {"cues": [{"id": hidden, "cues": ["user's ex"]}]})
            saved = _call(server, "memory_consolidate", {"cues": [
                {"id": batch["messages"][0]["id"], "cues": ["user hobbies and activities"]}]})
            # The two messages about the boundary topic count as read with the batch and carry no cue.
            assert (saved["indexed"], saved["remaining"]) == (1, 0)
            assert _call(server, "memory_consolidate", {})["messages"] == []

            # A batch that is wholly about the boundary topic is passed over, not shown.
            for number in range(7, 13):
                _turn(directory, "tuesday", f"Jordan texted me {number} times today.", "Noted.", str(number))
            assert _call(server, "memory_consolidate", {})["messages"] == []
            assert client.pending_message_cues(limit=1)["remaining"] == 0
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
