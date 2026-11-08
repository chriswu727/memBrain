import asyncio
import io
import json
import threading
from contextlib import contextmanager

import psycopg
import pytest
from psycopg import sql
from test_host import Client
from test_proxy import Upstream, _client

from membrain import desktop, embedded_database, host, plugin
from membrain.adapters.chatbot import TOOLS, ChatMemory, Speaker
from membrain.local_profile import load_profile
from membrain.mcp_server import create_server
from membrain.recording_policy import requests_pause

PUBLIC_GAP_PROMPTS = [
    "Off the record: the rehearsal prop is a cobalt paper kite. Do not keep this in memory.",
    "请不要记录这一段：排练道具是一只钴蓝色纸风筝。只在这次聊天里说说，不要保存。",
]


@pytest.mark.parametrize("prompt", [
    *PUBLIC_GAP_PROMPTS,
    "Off-the-record: a private rehearsal.",
    "This is off the record. A private rehearsal.",
    "Please, don't remember this: a private rehearsal.",
    "Please don’t store this in your memory. A private rehearsal.",
    "Do not save the following: a private rehearsal.",
    "Don't keep this in memory: a private rehearsal.",
    "Pause recording. A private rehearsal.",
    "Stop saving this conversation: a private rehearsal.",
    "  请不要保存这条消息：私人排练。",
    "不要记住这件事。私人排练。",
    "别记录：私人排练。",
    "请暂停记录。私人排练。",
])
def test_direct_controls_are_recognized(prompt):
    assert requests_pause(prompt)


@pytest.mark.parametrize("prompt", [
    "", "My rehearsal is on Tuesday.",
    'Translate "off the record" into Chinese.',
    'She said "do not record this" yesterday.',
    '"Off the record: a line in the play."',
    "> Off the record: quoted example.",
    "```\nOff the record: a code sample.\n```",
    "If I say off the record, what happens?",
    "What does off the record mean?",
    "Off the record is the title of a book.",
    "Don't remember this song's lyrics?",
    "Do not record this album until next week.",
    "Don't stop recording.", "Do not pause recording.",
    "Keep this between us: I like jazz.", "Please remember this privately: I like jazz.",
    "请解释不要记录是什么意思。", "她说不要记录这一段。",
    "“不要记录这一段”：这是书名。", "请不要记录这首歌。",
    "不要停止记录。", "请保密：我喜欢爵士乐。",
])
def test_quotes_discussion_negation_and_confidential_notes_do_not_change_recording(prompt):
    assert not requests_pause(prompt)


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args, **kwargs: None)


@pytest.mark.parametrize("prompt", PUBLIC_GAP_PROMPTS)
@pytest.mark.parametrize("tools", [None, TOOLS])
@pytest.mark.parametrize("roleplay", [None, "rehearsal"])
@pytest.mark.parametrize("stage", [False, True])
def test_excluded_turn_never_reaches_staging_spool_or_extraction(
        tmp_path, offline, prompt, tools, roleplay, stage):
    class Extractor:
        def submit(self, task):
            pytest.fail("An excluded turn must not schedule extraction")

    memory = ChatMemory(tmp_path, tools=tools, roleplay=roleplay, extractor=Extractor())
    speaker = Speaker("public-recording-regression", "synthetic-user")
    if stage:
        context = memory.context(speaker, prompt, session="synthetic-session", turn_id="private-turn")
        assert "Recording is currently paused" in context
    memory.record(speaker, "Private synthetic reply.", session="synthetic-session",
                  turn_id="private-turn", prompt=prompt)
    memory = ChatMemory(tmp_path, tools=tools, roleplay=roleplay)
    memory.context(speaker, "Another private synthetic detail.", session="synthetic-session")
    memory.record(speaker, "Another private reply.", session="synthetic-session")
    stored = "\n".join(p.read_text(errors="replace") for p in tmp_path.rglob("*") if p.is_file())
    assert prompt not in stored and "private synthetic" not in stored.lower()
    assert "private reply" not in stored.lower()
    assert not (tmp_path / "plugin" / "spool.jsonl").exists()
    assert host.paused(tmp_path, memory.memory_user(speaker))


def test_explicit_exclusion_cannot_be_revived_but_later_public_turn_can(tmp_path, offline):
    host.prompt_context(tmp_path, "s", "Off the record: confidential detail.", user_id="alice")
    host.resume(tmp_path, user_id="alice", current_turn=True, session="s")
    assert not host.turn_resumed(tmp_path, "s")
    assert host.finish_turn(tmp_path, "s", "Confidential reply.", user_id="alice",
                            prompt="Off the record: confidential detail.") == []
    assert not host.paused(tmp_path, "alice")
    host.prompt_context(tmp_path, "s", "Public rehearsal is Tuesday.", user_id="alice")
    records = host.finish_turn(tmp_path, "s", "Public reply.", user_id="alice")
    assert [r["text"] for r in records] == ["Public rehearsal is Tuesday.", "Public reply."]
    assert "Confidential" not in (tmp_path / "plugin" / "spool.jsonl").read_text()


def test_private_turn_survives_new_conversation_resume_without_revival(tmp_path, offline):
    host.prompt_context(tmp_path, "private", "Off the record: private detail.", user_id="alice")
    host.session_context(tmp_path, "private", user_id="alice")
    assert host.paused(tmp_path, "alice")
    host.session_context(tmp_path, "public", user_id="alice")
    assert not host.paused(tmp_path, "alice")
    assert host.finish_turn(tmp_path, "private", "Private reply.", user_id="alice") == []


@pytest.mark.parametrize("hours", [None, 2])
def test_natural_language_pause_does_not_shorten_existing_control(tmp_path, offline, hours):
    host.pause(tmp_path, user_id="alice", hours=hours)
    original = host._pause_file(tmp_path, "alice").read_text()
    host.prompt_context(tmp_path, "s", "Off the record: private detail.", user_id="alice")
    assert host._pause_file(tmp_path, "alice").read_text() == original
    host.session_context(tmp_path, "new", user_id="alice")
    assert host.paused(tmp_path, "alice")


def test_pause_keeps_other_users_and_group_memories_recording(tmp_path, offline):
    memory = ChatMemory(tmp_path, tools=None)
    alice = Speaker("test", "alice")
    memory.context(alice, PUBLIC_GAP_PROMPTS[0], session=memory.session(alice))
    for speaker in (Speaker("test", "bob"), Speaker("test", "alice", "group")):
        session = memory.session(speaker)
        memory.context(speaker, "Public rehearsal.", session=session)
        memory.record(speaker, "Public reply.", session=session)
    records = [json.loads(line) for line in (tmp_path / "plugin" / "spool.jsonl").read_text().splitlines()]
    assert len(records) == 4
    assert all(record["_user"] != memory.user_id(alice) for record in records)


@pytest.mark.parametrize("online", [False, True])
def test_finish_receipt_does_not_report_records_rejected_after_client_startup(tmp_path, offline, monkeypatch, online):
    client = Client()
    host.prompt_context(tmp_path, "s", "Synthetic prompt.", user_id="alice")

    def ready(*args):
        host.pause(tmp_path, user_id="alice")
        return client if online else None

    monkeypatch.setattr(host, "ready_client", ready)
    assert host.finish_turn(tmp_path, "s", "Synthetic reply.", user_id="alice") == []
    assert client.observed == []


def test_new_conversation_does_not_remove_a_concurrently_replaced_pause(tmp_path, offline, monkeypatch):
    host.pause(tmp_path, conversation=True, session="old")
    original_lock = host.profile_lock
    attempting = threading.Event()
    ended = []

    @contextmanager
    def tracked_lock(*args, **kwargs):
        if threading.current_thread().name == "end-conversation":
            attempting.set()
        with original_lock(*args, **kwargs) as value:
            yield value

    monkeypatch.setattr(host, "profile_lock", tracked_lock)
    worker = threading.Thread(name="end-conversation", target=lambda: ended.append(
        host.end_conversation_pause(tmp_path, "new")))
    with original_lock(host.state_directory(tmp_path) / "session-state-lock"):
        worker.start()
        assert attempting.wait(timeout=2)
        host.pause(tmp_path)
    worker.join(timeout=5)
    assert not worker.is_alive() and ended == [False]
    assert host.paused(tmp_path)


def test_local_mcp_cannot_bypass_pause_with_an_observation(tmp_path, offline):
    client = Client()
    host.prompt_context(tmp_path, "s", "Off the record: private synthetic detail.")
    server = create_server(client, directory=tmp_path)
    for name, arguments in (
        ("memory_observe", {"text": "Private synthetic detail.", "conversation_id": "s",
                            "branch_id": "main", "source_event_key": "private"}),
        ("memory_note", {"text": "Private synthetic detail."}),
    ):
        _, result = asyncio.run(server.call_tool(name, arguments))
        assert "Recording is paused" in result["error"]
    assert client.observed == []


@pytest.mark.parametrize("error", [OSError("synthetic disk failure"), TimeoutError("synthetic lock timeout")])
def test_failed_prompt_hook_cannot_store_an_orphan_reply(tmp_path, offline, monkeypatch, error):
    def unavailable(*args):
        raise error

    monkeypatch.setattr(host, "_stage", unavailable)
    payload = {"session_id": "s", "prompt": "Off the record: confidential rehearsal."}
    assert plugin.run_hook("user-prompt", tmp_path, stream=io.BytesIO(json.dumps(payload).encode())) == 0
    plugin.stop({"session_id": "s", "last_assistant_message": "The confidential rehearsal is tomorrow."}, tmp_path)
    assert not (tmp_path / "plugin" / "spool.jsonl").exists()


def test_late_duplicate_reply_does_not_revive_an_excluded_exchange(tmp_path, offline):
    host.prompt_context(tmp_path, "s", "Off the record: confidential rehearsal.", turn_id="private")
    assert host.finish_turn(tmp_path, "s", "Confidential reply.", turn_id="private") == []
    host.resume(tmp_path)
    assert host.finish_turn(tmp_path, "s", "Confidential reply.", turn_id="private") == []
    assert not (tmp_path / "plugin" / "spool.jsonl").exists()


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
@pytest.mark.parametrize("stream", [False, True])
def test_real_proxy_storage_and_next_session_exclude_private_exchange(tmp_path, monkeypatch, stream):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    directory = tmp_path / "brain"
    memory = ChatMemory(directory, tools=None)
    upstream = Upstream("The private rehearsal prop is a cobalt paper kite.")
    try:
        host.start(directory)
        with _client(memory, upstream) as client:
            for prompt in PUBLIC_GAP_PROMPTS:
                response = client.post("/v1/chat/completions", headers={"X-Membrain-Session": "private"},
                                       json={"model": "synthetic", "stream": stream, "user": "alice",
                                             "messages": [{"role": "user", "content": prompt}]})
                assert response.status_code == 200
                assert "Recording is currently paused" in upstream.requests[-1]["body"]["messages"][-1]["content"]
        speaker = Speaker("api", "alice")
        with host.ready_client(directory, memory.user_id(speaker)) as client:
            assert client.timeline(roles=("user", "assistant"))["items"] == []
        with psycopg.connect(load_profile(directory).migration_database_url) as conn:
            tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
            for (table,) in tables:
                rows = conn.execute(sql.SQL("SELECT to_jsonb(t)::text FROM {} t").format(sql.Identifier(table)))
                for (row,) in rows:
                    assert "cobalt paper kite" not in row and "钴蓝色纸风筝" not in row, table
        context = memory.context(speaker, "What do you remember?", session="public")
        assert "cobalt" not in context and "钴蓝色" not in context
        memory.record(speaker, "A public reply.", session="public")
        with host.ready_client(directory, memory.user_id(speaker)) as client:
            records = client.timeline(roles=("user", "assistant"))["items"]
        assert {r["text"] for r in records} == {"What do you remember?", "A public reply."}
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
