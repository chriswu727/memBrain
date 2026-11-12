"""The host's own AI indexes earlier messages: memBrain hands it a batch and saves the cues it returns.

memBrain calls no model for this. A new session is told, in one sentence, that earlier messages await indexing;
the consolidation tool hands the AI a batch with instructions; its second call saves cues and records how far it
read. Afterwards recall reaches a message through its cue and the sentence is gone.
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
            _turn(directory, "monday", POTTERY, "That sounds fun.", "1")
            _turn(directory, "monday", THANKS, "Any time.", "2")

            opening = host.session_context(directory, "tuesday")
            assert "2 earlier messages have not been indexed by memory yet." in opening
            assert "memory_consolidate" in opening
            assert "not been indexed" not in host.session_context(directory, "tuesday", tools=None)

            batch = _call(server, "memory_consolidate", {})
            assert [message["text"] for message in batch["messages"]] == [POTTERY, THANKS]
            assert all(type(message["id"]) is int and len(message["date"]) == 10 for message in batch["messages"])
            assert batch["remaining"] == 2 and batch["reviewed_through"] == batch["messages"][-1]["id"]
            assert "WHAT KIND of fact" in batch["instructions"]

            # What a host AI sends back: a cue for the fact, none for the thanks.
            for wrong in ({"cues": [{"id": batch["messages"][0]["id"], "cues": ["x"]}]},
                          {"cues": [{"id": "one", "cues": ["x"]}], "reviewed_through": batch["reviewed_through"]},
                          {"cues": [{"id": 10_000, "cues": ["x"]}], "reviewed_through": batch["reviewed_through"]}):
                assert "error" in _call(server, "memory_consolidate", wrong)
            saved = _call(server, "memory_consolidate", {
                "cues": [{"id": batch["messages"][0]["id"], "cues": ["user hobbies and activities"]}],
                "reviewed_through": batch["reviewed_through"]})
            assert saved == {"indexed": 1, "skipped": 0, "remaining": 0}
            assert _call(server, "memory_consolidate", {})["messages"] == []
            assert "not been indexed" not in host.session_context(directory, "wednesday")

            found = _call(server, "memory_recall", {"query": "What are my hobbies?", "with_ids": True})
            assert any(record["text"] == POTTERY for record in found["records"])
            assert "hobbies and activities" not in str(found)

            host.pause(directory)
            assert "paused" in _call(server, "memory_consolidate", {})["error"]
            assert "not been indexed" not in host.session_context(directory, "thursday")
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
