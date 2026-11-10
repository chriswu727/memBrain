"""A pause of "this conversation" belongs to that conversation: another one neither inherits nor ends it."""
import asyncio
import json
import os
import time

import pytest
from test_hermes_adapter import Client as HermesClient
from test_hermes_adapter import provider
from test_host import Client

from membrain import host, host_recording
from membrain.mcp_server import create_server


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


@pytest.fixture
def client(monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    return client


def _texts(client):
    return [record["text"] for record in client.observed]


def _off_the_record(directory, session="A"):
    host.prompt_context(directory, session, "Off the record: I'm job hunting.", turn_id="t1")
    host.finish_turn(directory, session, "Okay, not keeping that.", turn_id="t1")


def _age_session(directory, session, seconds):
    marker = host._session_marker(directory, session)
    old = time.time() - seconds
    os.utime(marker, (old, old))


def test_a_second_conversation_does_not_end_the_first_ones_pause(tmp_path, client):
    _off_the_record(tmp_path)
    opening = host.session_context(tmp_path, "B")  # A second window opens while the first is still in use.
    assert "paused for another conversation only" in opening and "has ended" not in opening
    assert "Recording is currently paused" not in opening
    assert host.paused(tmp_path, session="A") and not host.paused(tmp_path, session="B")
    host.prompt_context(tmp_path, "A", "The offer is 185k from Initech.", turn_id="t2")
    receipt = {}
    assert host.finish_turn(tmp_path, "A", "Understood.", turn_id="t2", receipt=receipt) == []
    assert client.observed == []
    assert {message["state"] for message in receipt["messages"]} == {"excluded"}
    assert {message["scope"] for message in receipt["messages"]} == {"conversation"}
    stored = "".join(path.read_text(encoding="utf-8") for path in (tmp_path / "plugin").rglob("*") if path.is_file())
    assert "Initech" not in stored and "job hunting" not in stored


def test_the_second_conversation_is_recorded_while_the_first_stays_paused(tmp_path, client):
    _off_the_record(tmp_path)
    host.session_context(tmp_path, "B")
    context = host.prompt_context(tmp_path, "B", "My sister moved to Leeds.", turn_id="t1", include_source=True)
    assert "Recording is currently paused" not in (context or "") and "recording_capture=" in context
    host.finish_turn(tmp_path, "B", "Noted.", turn_id="t1")
    assert _texts(client) == ["My sister moved to Leeds.", "Noted."]
    assert host.paused(tmp_path, session="A")


def test_the_pause_ends_once_its_own_conversations_are_over(tmp_path, client):
    _off_the_record(tmp_path)
    host.session_context(tmp_path, "B")
    assert host.paused(tmp_path)
    _age_session(tmp_path, "A", 7 * 3600)  # Nothing has happened in the paused conversation for hours.
    opening = host.session_context(tmp_path, "C")
    assert "paused for an earlier conversation only" in opening and not host.paused(tmp_path)
    assert not host._pause_file(tmp_path).exists()


def test_an_unfinished_turn_keeps_its_conversation_paused_however_old(tmp_path, client):
    _off_the_record(tmp_path)
    host.prompt_context(tmp_path, "A", "Still off the record.", turn_id="t2")  # Staged; its reply has not come.
    _age_session(tmp_path, "A", 7 * 3600)
    assert not host.end_conversation_pause(tmp_path, "C")
    assert host.paused(tmp_path, session="A")


def test_a_pause_that_identified_no_conversation_covers_all_until_the_next_one_starts(tmp_path, client):
    host.pause(tmp_path, conversation=True)
    assert json.loads(host._pause_file(tmp_path).read_text(encoding="utf-8"))["conversations"] == []
    # The conversation that asked is unknown, so it may be any of them: none is recorded.
    assert host.paused(tmp_path) and host.paused(tmp_path, session="asking")
    host.prompt_context(tmp_path, "asking", "Still private.", turn_id="t1")
    assert host.finish_turn(tmp_path, "asking", "Okay.", turn_id="t1") == [] and client.observed == []
    assert host.end_conversation_pause(tmp_path, "next") and not host.paused(tmp_path)


@pytest.mark.parametrize("change", [{"hours": 2}, {}])
def test_a_timed_or_open_pause_covers_every_conversation(tmp_path, client, change):
    host.pause(tmp_path, **change)
    assert host.paused(tmp_path, session="A") and host.paused(tmp_path, session="B")
    assert not host.end_conversation_pause(tmp_path, "B") and host.paused(tmp_path, session="B")


def test_unreadable_pause_metadata_blocks_every_conversation(tmp_path, client):
    host.pause(tmp_path, conversation=True, session="A")
    host._pause_file(tmp_path).write_text("{not json", encoding="utf-8")
    assert host.paused(tmp_path, session="A") and host.paused(tmp_path, session="B") and host.paused(tmp_path)


def test_one_persons_conversation_pause_is_scoped_the_same_way(tmp_path, client):
    host.prompt_context(tmp_path, "alice-1", "Off the record: about my health.", turn_id="t1", user_id="alice")
    host.finish_turn(tmp_path, "alice-1", "Okay.", turn_id="t1", user_id="alice")
    host.session_context(tmp_path, "alice-2", user_id="alice")
    assert host.paused(tmp_path, "alice", "alice-1") and not host.paused(tmp_path, "alice", "alice-2")
    assert not host.paused(tmp_path, "bob", "bob-1")
    # Her role-play in the paused conversation is covered; a role-play conversation outside it is not.
    assert host.paused(tmp_path, host.roleplay_user("alice", "Mira"), "alice-1")
    assert not host.paused(tmp_path, host.roleplay_user("alice", "Mira"), "alice-3")


def test_another_persons_conversation_pause_is_neither_inherited_nor_mentioned(tmp_path, client, monkeypatch):
    monkeypatch.setattr(host, "use_brain", lambda *args: None)  # The double has one brain for everyone.
    _off_the_record(tmp_path)  # The installation's owner, in their own conversation.
    opening = host.session_context(tmp_path, "bob-1", user_id="bob")
    assert "paused" not in opening.split("memBrain memory is active", 1)[0] and "off the record" not in opening
    host.prompt_context(tmp_path, "bob-1", "I moved to Leeds.", turn_id="t1", user_id="bob")
    host.finish_turn(tmp_path, "bob-1", "Noted.", turn_id="t1", user_id="bob")
    assert _texts(client) == ["I moved to Leeds.", "Noted."]
    assert host.paused(tmp_path, session="A")


def test_memory_writes_follow_the_conversation_of_their_capture(tmp_path, client):
    _off_the_record(tmp_path)
    host.session_context(tmp_path, "B")
    context = host.prompt_context(tmp_path, "B", "I am allergic to sesame.", turn_id="t1", include_source=True)
    capture = json.loads(context.split("recording_capture=", 1)[1].split(". Never", 1)[0])
    assert host_recording.capture_marker(capture) == host._session_marker(tmp_path, "B").stem
    assert host_recording.note_revision(tmp_path, client, capture) == 0
    server = create_server(Client(), directory=tmp_path)
    # A write that cannot name its conversation is still refused while any conversation is off the record.
    _, refused = asyncio.run(server.call_tool("memory_note", {"text": "A write that names no conversation."}))
    assert refused == {"error": "Recording is paused. Resume before saving agent notes."}
    forged = host._session_marker(tmp_path, "A").stem + "." + capture.split(".", 1)[1]
    with pytest.raises(ValueError, match="Recording is paused"):
        host_recording.note_revision(tmp_path, client, forged)


def test_erasing_a_person_removes_their_refused_records(tmp_path):
    def refuse(user, text):
        record = {"text": text, "role": "user", **({"_user": user} if user else {})}
        host._reject(tmp_path, json.dumps(record), TypeError("refused"))

    refuse("alice", "synthetic text refused for alice")
    refuse("bob", "synthetic text refused for bob")
    refuse(None, "synthetic text refused for the owner")
    path = host.state_directory(tmp_path) / "spool-rejected.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"text": "a torn line with no owner\n')
    assert host._erase_rejected(tmp_path, "alice") == 2  # Her record and the line nobody can attribute.
    kept = path.read_text(encoding="utf-8")
    assert "alice" not in kept and "torn" not in kept and "for bob" in kept and "for the owner" in kept
    assert host._erase_rejected(tmp_path, None) == 1 and "for the owner" not in path.read_text(encoding="utf-8")
    assert host._erase_rejected(tmp_path, "bob") == 1 and not path.exists()
    assert host._erase_rejected(tmp_path, "bob") == 0


def test_erase_user_clears_refused_records(tmp_path, monkeypatch):
    class Erasing(Client):
        def dashboard(self):
            return {"brain": {"scope_generation": 1}}

        def forget(self, ids, **options):
            return {"outcome": "applied"}

    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: Erasing())
    host._reject(tmp_path, json.dumps({"text": "synthetic refused text", "_user": "alice"}), TypeError("refused"))
    host._reject(tmp_path, json.dumps({"text": "another person's text", "_user": "bob"}), TypeError("refused"))
    assert host.erase_user(tmp_path, "alice") == {"erased": "applied", "queued_records_dropped": 0}
    kept = (host.state_directory(tmp_path) / "spool-rejected.jsonl").read_text(encoding="utf-8")
    assert "synthetic refused text" not in kept and "another person's text" in kept


def test_a_replay_error_at_session_start_does_not_cost_the_session_its_context(tmp_path, client, monkeypatch):
    def failing(*args, **kwargs):
        raise ConnectionError("the service dropped the replay")

    monkeypatch.setattr(host, "flush", failing)
    opening = host.session_context(tmp_path, "A")
    assert "memBrain memory is active" in opening
    assert "replay failed at session start: ConnectionError" in (tmp_path / "plugin" / "hooks.log").read_text(
        encoding="utf-8")
    monkeypatch.undo()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    host.prompt_context(tmp_path, "A", "My sister moved to Leeds.", turn_id="t1")
    host.finish_turn(tmp_path, "A", "Noted.", turn_id="t1")
    assert _texts(client) == ["My sister moved to Leeds.", "Noted."]


def test_hermes_does_not_import_its_user_file_while_recording_is_paused(tmp_path, monkeypatch):
    memories = tmp_path / "home" / "memories"
    memories.mkdir(parents=True)
    (memories / "USER.md").write_text("Allergic to sesame.", encoding="utf-8")
    client = HermesClient()
    instance = provider(tmp_path, monkeypatch, client)
    host.pause(instance._directory)
    instance.system_prompt_block()
    assert [note for note in client.notes if note.get("producer") == "membrain-import:hermes"] == []
    host.resume(instance._directory)
    instance.system_prompt_block()  # The file is read again once recording is on.
    assert [note["text"] for note in client.notes if note.get("producer") == "membrain-import:hermes"] == [
        "Allergic to sesame."]
