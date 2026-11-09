import json
import os
import time

import pytest

from membrain import desktop, embedded_database, host


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


class Client:
    brain_id = "brain"

    def __init__(self):
        self.observed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def observe(self, **record):
        self.observed.append(record)

    def recall(self, query, **options):
        return {"result": {"items": []}}


@pytest.mark.parametrize("secret", [
    "sk-ant-api03-" + "a" * 40, "sk-proj-" + "b" * 30, "ghp_" + "c" * 36, "github_pat_" + "d" * 50,
    "AKIA" + "E" * 16, "xoxb-1234567890-abcdefghij", "AIza" + "f" * 35,
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
])
def test_credentials_are_scrubbed(secret):
    assert host.scrub(f"my key is {secret} ok") == f"my key is {host.SECRET_MARK} ok"


def test_assignments_and_private_spans_are_scrubbed_but_ordinary_text_is_kept():
    text = ('password: hunter2hunter2 and api_key="abc123def456" then '
            "<private>my diagnosis</private> visible <PRIVATE>until the end")
    assert host.scrub(text) == (f"password: {host.SECRET_MARK} and api_key={host.SECRET_MARK} then "
                                f"{host.PRIVATE_MARK} visible {host.PRIVATE_MARK}")
    ordinary = "My sister's password manager is 1Password; the token ring game is fun. 我对虾过敏。"
    assert host.scrub(ordinary) == ordinary
    key = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----"
    assert host.scrub(f"here {key} done") == f"here {host.SECRET_MARK} done"


def test_turns_are_stored_with_the_reply_and_private_text_never_reaches_disk(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    prompt = "My token is sk-proj-" + "x" * 30 + " and <private>I was fired today</private>. Plan my week."
    host.prompt_context(tmp_path, "s1", prompt, turn_id="t1")
    stored_state = "".join(path.read_text() for path in (tmp_path / "plugin" / "sessions").glob("*.json"))
    assert "fired" not in stored_state and "x" * 30 not in stored_state and client.observed == []
    host.finish_turn(tmp_path, "s1", "Here is a calm week.", turn_id="t1")
    assert [(record["role"], record["source_event_key"]) for record in client.observed] == [
        ("user", "s1:t1:user"), ("assistant", "s1:t1:assistant")]
    assert "fired" not in client.observed[0]["text"] and host.PRIVATE_MARK in client.observed[0]["text"]
    assert client.observed[1]["parent_source_event_keys"] == ["s1:t1:user"]


def test_pausing_during_a_turn_keeps_that_turn_and_later_ones_out(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    host.prompt_context(tmp_path, "s1", "Don't remember this: I'm job hunting.", turn_id="t1")
    host.pause(tmp_path)
    host.finish_turn(tmp_path, "s1", "Understood, I won't keep it.", turn_id="t1")
    host.prompt_context(tmp_path, "s1", "Still secret.", turn_id="t2")
    host.finish_turn(tmp_path, "s1", "Okay.", turn_id="t2")
    assert client.observed == [] and host.paused(tmp_path)
    assert not (tmp_path / "plugin" / "spool.jsonl").exists()
    assert "Recording is currently paused" in host.session_context(tmp_path, "s2")
    host.resume(tmp_path)
    host.prompt_context(tmp_path, "s1", "Back to normal.", turn_id="t3")
    host.finish_turn(tmp_path, "s1", "Welcome back.", turn_id="t3")
    assert [record["text"] for record in client.observed] == ["Back to normal.", "Welcome back."]


def test_timed_pause_expires(tmp_path):
    assert host.pause(tmp_path, hours=1)["until"] > time.time()
    assert host.paused(tmp_path)
    path = tmp_path / "plugin" / "paused.json"
    path.write_text(json.dumps({"since": 0, "until": time.time() - 1}))
    assert not host.paused(tmp_path) and not path.exists()
    with pytest.raises(ValueError):
        host.pause(tmp_path, hours=0)


def test_spooled_records_are_scrubbed_when_the_service_is_down(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: None)
    monkeypatch.setattr(host, "start_in_background", lambda directory, user_id=None: None)
    host.prompt_context(tmp_path, "s1", "password=correcthorsebattery remember my dog Biscuit", turn_id="t1")
    host.finish_turn(tmp_path, "s1", "Biscuit noted.", turn_id="t1")
    spooled = (tmp_path / "plugin" / "spool.jsonl").read_text()
    assert "correcthorse" not in spooled and "Biscuit" in spooled


def test_an_unfinished_turn_is_preserved_until_abandoned(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    host.prompt_context(tmp_path, "s1", "First, never answered.", turn_id="t1")
    host.prompt_context(tmp_path, "s1", "Second.", turn_id="t2")
    assert client.observed == []
    host.prompt_context(tmp_path, "crashed", "Left mid-turn.", turn_id="t9")
    marker = next(path for path in (tmp_path / "plugin" / "sessions").glob("*.json")
                  if "Left mid-turn." in path.read_text())
    state = json.loads(marker.read_text())
    for entry in state["turns"].values():
        entry["started"] = 0
    host._write_session_marker(marker, state)
    monkeypatch.setattr(host, "_history", lambda client, session, budget: (None, False))
    monkeypatch.setattr("membrain.notes.list_notes", lambda client: {"items": []})
    host.session_context(tmp_path, "s3")
    assert [record["text"] for record in client.observed][-1] == "Left mid-turn."


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_colon_turn_ids_store_distinct_conversations(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        receipts = []
        for session, turn in (("a", "b:c"), ("a:b", "c")):
            host.prompt_context(directory, session, f"Question {session}", turn_id=turn)
            receipts.extend(host.finish_turn(directory, session, f"Reply {session}", turn_id=turn))
        assert len({r["source_event_key"] for r in receipts}) == 4
        with host.ready_client(directory) as client:
            rows = client.timeline(roles=("user", "assistant"), max_characters=20000)["items"]
        assert {(row["conversation_id"], row["text"]) for row in rows} == {
            (session, f"{role} {session}") for session in ("a", "a:b") for role in ("Question", "Reply")}
        spool = directory / "plugin" / "spool.jsonl"
        assert not spool.exists() or not spool.read_text().strip()
    finally:
        desktop.stop(directory)


def test_mcp_offers_pause_tools_only_for_a_local_installation(tmp_path):
    import asyncio

    from membrain.mcp_server import create_server

    def tools(server):
        return {tool.name for tool in asyncio.run(server.list_tools())}

    assert {"memory_pause", "memory_resume"} <= tools(create_server(Client(), directory=tmp_path))
    assert not {"memory_pause", "memory_resume"} & tools(create_server(Client()))


def test_mcp_recall_for_a_local_installation_is_the_compact_hook_recall(tmp_path, monkeypatch):
    import asyncio

    from membrain.mcp_server import create_server

    seen = []
    monkeypatch.setattr(host, "recall_context", lambda client, query, **options: seen.append(query) or "<recalled>")
    server = create_server(Client(), directory=tmp_path)
    tool = {tool.name: tool for tool in asyncio.run(server.list_tools())}["memory_recall"]
    assert set(tool.inputSchema["properties"]) == {"query", "with_ids"}
    _, result = asyncio.run(server.call_tool("memory_recall", {"query": "Mei's allergy"}))
    assert result == {"context": "<recalled>"} and seen == ["Mei's allergy"]
    generic = {tool.name: tool for tool in asyncio.run(create_server(Client()).list_tools())}["memory_recall"]
    assert "intent" in generic.inputSchema["properties"]


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_private_text_never_reaches_the_database(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        host.session_context(directory, "a")
        host.prompt_context(directory, "a", "Remember Biscuit. <private>My PIN is 4821</private> "
                                            "token=ghp_" + "z" * 36, turn_id="1")
        host.finish_turn(directory, "a", "Biscuit, got it.", turn_id="1")
        with host.ready_client(directory) as client:
            stored = json.dumps(client.timeline(roles=("user", "assistant"), max_characters=200_000))
        assert "Biscuit" in stored and "4821" not in stored and "z" * 36 not in stored
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_memory_page_codes_are_single_use_and_expire(tmp_path):
    code = host.issue_ui_code(tmp_path)
    assert host.consume_ui_code(tmp_path, code) and not host.consume_ui_code(tmp_path, code)
    stale = host.issue_ui_code(tmp_path)
    codes = json.loads((tmp_path / "plugin" / "ui-codes.json").read_text())
    (tmp_path / "plugin" / "ui-codes.json").write_text(json.dumps({key: 0 for key in codes}))
    assert not host.consume_ui_code(tmp_path, stale)
    assert not host.consume_ui_code(tmp_path, "short") and not host.consume_ui_code(tmp_path, None)
    assert code not in (tmp_path / "plugin" / "ui-codes.json").read_text()


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_memory_page_signs_in_once_and_controls_recording(tmp_path):
    import httpx

    from membrain.local_profile import load_profile

    directory = tmp_path / "brain"
    try:
        host.start(directory)
        base = load_profile(directory).base_url
        assert "memory.js" in httpx.get(base + "/memory").text
        code = host.issue_ui_code(directory)
        session = httpx.post(base + "/v1/local/ui-session", json={"code": code})
        assert session.status_code == 200 and session.json()["brain_id"] == load_profile(directory).brain_id
        assert httpx.post(base + "/v1/local/ui-session", json={"code": code}).status_code == 401
        headers = {"Authorization": "Bearer " + session.json()["api_key"]}
        assert httpx.get(base + "/v1/local/recording").status_code == 401
        assert httpx.post(base + "/v1/local/recording", json={"paused": True, "hours": 2}, headers=headers).json()[
            "recording"] == "paused" and host.paused(directory)
        assert httpx.post(base + "/v1/local/recording", json={"paused": False}, headers=headers).json() == {
            "recording": "on"}
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_one_users_pause_does_not_stop_others(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    monkeypatch.setattr(host, "use_brain", lambda client, user_id: client)
    host.pause(tmp_path, user_id="qq:1001")
    assert host.paused(tmp_path, "qq:1001") and not host.paused(tmp_path, "qq:2002") and not host.paused(tmp_path)
    for user in ("qq:1001", "qq:2002"):
        host.prompt_context(tmp_path, f"group:{user}", f"hello from {user}", turn_id="t1", user_id=user)
        host.finish_turn(tmp_path, f"group:{user}", "hi", turn_id="t1", user_id=user)
    assert [record["text"] for record in client.observed] == ["hello from qq:2002", "hi"]
    assert host.user_brain_id("qq:1001") == host.user_brain_id("qq:1001") != host.user_brain_id("qq:2002")
    with pytest.raises(ValueError):
        host.user_brain_id("")


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_users_of_a_shared_bot_keep_separate_memories(tmp_path, monkeypatch):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        turns = {"telegram:alice": "I'm allergic to peanuts.", "telegram:bob": "I just adopted a greyhound named Sardina."}
        for user, text in turns.items():
            host.session_context(directory, f"chat:{user}", user_id=user)
            host.prompt_context(directory, f"chat:{user}", text, turn_id="1", user_id=user)
            host.finish_turn(directory, f"chat:{user}", "Noted.", turn_id="1", user_id=user)
        with monkeypatch.context() as offline:
            offline.setattr(host, "ready_client", lambda directory, user_id=None: None)
            offline.setattr(host, "start_in_background", lambda directory: None)
            host.prompt_context(directory, "chat:telegram:alice", "My sister is called Mei.",
                                turn_id="2", user_id="telegram:alice")
            host.finish_turn(directory, "chat:telegram:alice", "Spooled reply.", turn_id="2",
                             prompt="My sister is called Mei.", user_id="telegram:alice")
        with host.ready_client(directory) as client:
            assert host.flush(client, directory) == 2
        for user, own in turns.items():
            with host.ready_client(directory, user) as client:
                stored = json.dumps(client.timeline(roles=("user", "assistant"), max_characters=200_000))
            other = next(text for name, text in turns.items() if name != user)
            assert own in stored and other not in stored
        with host.ready_client(directory, "telegram:alice") as client:
            assert "Mei" in json.dumps(client.timeline(max_characters=200_000))
        with host.ready_client(directory) as client:
            assert json.loads(json.dumps(client.timeline(max_characters=200_000)))["items"] == []
        context = host.prompt_context(directory, "chat2:telegram:bob", "what is my dog's name again", user_id="telegram:bob")
        assert "Sardina" in (context or "") and "peanuts" not in (context or "")
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_mcp_from_a_uv_cache_environment_hands_over_to_the_installed_tool(tmp_path, monkeypatch):
    import argparse
    import subprocess

    from membrain import plugin_cli

    tools = tmp_path / "tools"
    python = tools / "membrain-ai" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.write_text("")
    monkeypatch.setenv("UV_TOOL_DIR", str(tools))
    monkeypatch.setattr(host.shutil, "which", lambda name: None)
    monkeypatch.delenv("UV", raising=False)
    assert host.installed_tool_python() == python
    monkeypatch.setattr(host.sys, "prefix", str(tmp_path / ".cache" / "uv" / "archive-v0" / "abc"))
    assert host.running_from_uv_cache()
    calls = []
    monkeypatch.setattr(host, "installed_tool_matches", lambda candidate: candidate == python)
    monkeypatch.setattr(subprocess, "call", lambda command: calls.append(command) or 0)
    args = argparse.Namespace(plugin_command="mcp", directory=tmp_path / "brain")
    with pytest.raises(SystemExit) as stopped:
        plugin_cli.dispatch(args)
    assert stopped.value.code == 0
    assert calls == [[str(python), "-m", "membrain.cli", "plugin", "mcp", "--directory", str(tmp_path / "brain")]]
    monkeypatch.setattr(host.sys, "prefix", str(tools / "membrain-ai"))
    assert not host.running_from_uv_cache()


@pytest.mark.parametrize("result", ["same", "stale", "failed", "missing", "timeout"])
def test_installed_tool_handoff_requires_exact_build_identity(tmp_path, monkeypatch, result):
    import subprocess
    from types import SimpleNamespace

    from membrain.build_identity import BUILD_ID

    python = tmp_path / "python"
    calls = []

    def run(command, **options):
        calls.append((command, options))
        if result == "missing":
            raise FileNotFoundError()
        if result == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        return SimpleNamespace(returncode=1 if result == "failed" else 0,
                               stdout=BUILD_ID + "\n" if result == "same" else "old-build\n")

    monkeypatch.setattr(subprocess, "run", run)
    assert host.installed_tool_matches(python) is (result == "same")
    command, options = calls[0]
    assert command[:3] == [str(python), "-I", "-c"]
    assert options["timeout"] == 10 and options["capture_output"] and options["check"] is False


def test_mcp_never_delegates_to_a_stale_installed_runtime(tmp_path, monkeypatch, capsys):
    import argparse
    import subprocess

    from membrain import plugin, plugin_cli

    monkeypatch.setattr(host, "running_from_uv_cache", lambda: True)
    monkeypatch.setattr(host, "installed_tool_python", lambda: tmp_path / "old-python")
    monkeypatch.setattr(host, "installed_tool_matches", lambda candidate: False)
    monkeypatch.setattr(subprocess, "call", lambda *args: pytest.fail("Do not launch the old runtime"))
    monkeypatch.setattr(plugin, "ensure_installation", lambda *args: pytest.fail("Do not touch the profile"))
    with pytest.raises(SystemExit) as stopped:
        plugin_cli.dispatch(argparse.Namespace(plugin_command="mcp", directory=tmp_path / "brain"))
    assert stopped.value.code == 1 and not (tmp_path / "brain").exists()
    output = capsys.readouterr()
    assert output.out == "" and "Update the tool" in output.err


@pytest.mark.parametrize("user_id", [None, "alice", "alice|roleplay:Ada"])
def test_paused_prompts_never_reach_session_files_or_future_recall(tmp_path, monkeypatch, user_id):
    client, cues = Client(), []
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    monkeypatch.setattr("membrain.notes.list_notes", lambda client: {"items": []})
    monkeypatch.setattr(host, "recall_context", lambda *args, **kwargs: cues.extend(kwargs.get("cues", ())))
    host.prompt_context(tmp_path, "s", "unfinished confidential", user_id=user_id)
    host.pause(tmp_path, user_id=host.real_life_user(user_id))
    assert "unfinished confidential" not in host._session_marker(tmp_path, "s").read_text()
    host.prompt_context(tmp_path, "s", "paused confidential", user_id=user_id)
    assert "paused confidential" not in host._session_marker(tmp_path, "s").read_text()
    host.resume(tmp_path, user_id=host.real_life_user(user_id))
    host.prompt_context(tmp_path, "s", "ordinary", user_id=user_id)
    assert "paused confidential" not in cues and "unfinished confidential" not in cues
    assert client.observed == []


def test_pausing_one_user_preserves_another_users_pending_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)
    host.prompt_context(tmp_path, "alice-session", "alice private", user_id="alice")
    host.prompt_context(tmp_path, "bob-session", "bob pending", user_id="bob")
    bob_modified = host._session_marker(tmp_path, "bob-session").stat().st_mtime_ns
    host.pause(tmp_path, user_id="alice")
    assert host._session_marker(tmp_path, "bob-session").stat().st_mtime_ns == bob_modified
    assert "alice private" not in host._session_marker(tmp_path, "alice-session").read_text()
    assert [entry["record"]["text"] for entry in host.session_state(tmp_path, "bob-session")["turns"].values()
            if "record" in entry] == ["bob pending"]


@pytest.mark.parametrize("fail", [False, True])
def test_spool_append_during_replay_survives_success_and_failure(tmp_path, fail):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    started, appended = Event(), Event()
    host.spool(tmp_path, host.message_record("s", "user", "first"))

    class ReplayClient(Client):
        def observe(self, **record):
            started.set()
            assert appended.wait(5), "spooling must not wait for a network request"
            if fail:
                raise ConnectionError("offline")
            super().observe(**record)

    with ThreadPoolExecutor() as pool:
        replay = pool.submit(host.flush, ReplayClient(), tmp_path)
        assert started.wait(5)
        host.spool(tmp_path, host.message_record("s", "user", "second"))
        appended.set()
        if fail:
            with pytest.raises(ConnectionError):
                replay.result(timeout=5)
        else:
            assert replay.result(timeout=5) == 1
    client = Client()
    host.flush(client, tmp_path)
    assert [item["text"] for item in client.observed] == (["first", "second"] if fail else ["second"])


@pytest.mark.parametrize("pause_before_prompt", [True, False])
def test_resuming_before_a_paused_turn_finishes_does_not_store_it(tmp_path, monkeypatch, pause_before_prompt):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    if pause_before_prompt:
        host.pause(tmp_path, user_id="alice")
    host.prompt_context(tmp_path, "s", "confidential", user_id="alice")
    if not pause_before_prompt:
        host.pause(tmp_path, user_id="alice")
    host.session_context(tmp_path, "s", user_id="alice")
    host.resume(tmp_path, user_id="alice")
    host.finish_turn(tmp_path, "s", "confidential reply", prompt="confidential")
    assert client.observed == []
    assert "confidential" not in host._session_marker(tmp_path, "s").read_text()



@pytest.mark.parametrize("user", [None, "alice"])
def test_the_message_that_asks_to_go_back_on_the_record_is_stored(tmp_path, monkeypatch, user):
    """An agent resuming at the user's request stores that message, which was sent while paused."""
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    host.pause(tmp_path, user_id=user, conversation=True)
    prompt = "Back on the record. My flight home moved to Tuesday 28 September."
    host.prompt_context(tmp_path, "s", prompt, turn_id="t2", user_id=user)
    assert "Tuesday" not in host._session_marker(tmp_path, "s").read_text()  # Not kept while paused.
    assert not host.turn_resumed(tmp_path, "s")
    host.resume(tmp_path, user_id=user, current_turn=True, session="s")
    assert host.turn_resumed(tmp_path, "s")
    host.finish_turn(tmp_path, "s", "Noted the new return date.", turn_id="t2", prompt=prompt, user_id=user)
    assert [(item["role"], item["text"]) for item in client.observed] == [
        ("user", prompt), ("assistant", "Noted the new return date.")]
    assert not host.turn_resumed(tmp_path, "s")
    client.observed.clear()
    host.prompt_context(tmp_path, "s", "Next message", turn_id="t3", user_id=user)
    host.finish_turn(tmp_path, "s", "reply", turn_id="t3", user_id=user)
    assert [item["text"] for item in client.observed] == ["Next message", "reply"]


def test_a_turn_paused_and_resumed_in_the_same_message_stays_unstored(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    host.pause(tmp_path)
    host.prompt_context(tmp_path, "s", "off the record: secret", turn_id="t1")
    host.pause(tmp_path)  # Paused again during this turn.
    host.resume(tmp_path, current_turn=True, session="s")
    assert not host.turn_resumed(tmp_path, "s")
    host.finish_turn(tmp_path, "s", "ok", turn_id="t1", prompt="off the record: secret")
    host.prompt_context(tmp_path, "s2", "off the record: other secret", turn_id="t1")
    host.pause(tmp_path)  # A turn that began on the record and was paused cannot be brought back either.
    host.resume(tmp_path, current_turn=True, session="s2")
    host.finish_turn(tmp_path, "s2", "ok", turn_id="t1", prompt="off the record: other secret")
    assert client.observed == []


def test_resuming_for_one_user_does_not_store_another_users_paused_turn(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    host.pause(tmp_path, user_id="alice")
    host.pause(tmp_path, user_id="bob")
    host.prompt_context(tmp_path, "a", "alice secret", turn_id="t1", user_id="alice")
    host.prompt_context(tmp_path, "b", "bob secret", turn_id="t1", user_id="bob")
    host.resume(tmp_path, user_id="alice", current_turn=True, session="a")
    assert host.turn_resumed(tmp_path, "a") and not host.turn_resumed(tmp_path, "b")


def test_resuming_brings_back_only_the_turn_that_asked_not_the_same_users_other_conversation(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    host.pause(tmp_path, user_id="alice")
    host.prompt_context(tmp_path, "private", "off the record: my diagnosis", turn_id="t1", user_id="alice")
    host.prompt_context(tmp_path, "asks", "Back on the record: flight moved to the 28th.", turn_id="t1",
                        user_id="alice")
    # A host that knows the conversation can resume that turn without reviving another private exchange.
    host.resume(tmp_path, user_id="alice", current_turn=True, session="asks")
    assert host.turn_resumed(tmp_path, "asks") and not host.turn_resumed(tmp_path, "private")
    host.finish_turn(tmp_path, "private", "ok", turn_id="t1", prompt="off the record: my diagnosis", user_id="alice")
    assert client.observed == []

    host.pause(tmp_path, user_id="alice")
    host.prompt_context(tmp_path, "private2", "off the record: other secret", turn_id="t2", user_id="alice")
    monkeypatch.setattr(host.time, "time", lambda: 10 ** 10)  # The asking turn starts later.
    host.prompt_context(tmp_path, "asks2", "Back on the record please.", turn_id="t2", user_id="alice")
    result = host.resume(tmp_path, user_id="alice", current_turn=True)
    assert result["reason"] == "session_required"
    assert not host.turn_resumed(tmp_path, "asks2") and not host.turn_resumed(tmp_path, "private2")


def test_a_conversation_pause_holds_in_the_role_play_where_it_was_asked(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    role = host.roleplay_user("alice", "Merlin")
    host.prompt_context(tmp_path, "rp", "Merlin, off the record: I'm moving out.", turn_id="t1", user_id=role)
    host.pause(tmp_path, user_id="alice", conversation=True)  # Hosts pause the real-life person.
    host.finish_turn(tmp_path, "rp", "Understood.", turn_id="t1", user_id=role)
    host.session_context(tmp_path, "rp", user_id="alice", roleplay="Merlin")  # Same role-play continues.
    assert host.paused(tmp_path, role)
    host.prompt_context(tmp_path, "rp", "It's because of my landlord.", turn_id="t2", user_id=role)
    host.finish_turn(tmp_path, "rp", "I see.", turn_id="t2", user_id=role)
    assert client.observed == []


def test_the_stop_hook_stores_a_resumed_turn_from_the_transcript(tmp_path, monkeypatch):
    from membrain import plugin

    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    monkeypatch.setattr(plugin, "_import_host_queue", lambda *args: None)
    prompt = "Back on the record: the party moved to the 21st."
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("\n".join(json.dumps(entry) for entry in [
        {"type": "user", "message": {"role": "user", "content": prompt}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "1"}]}},
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1"}]}},
        {"type": "user", "isMeta": True, "message": {"role": "user", "content": "Caveat: local command output"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Noted."}]}},
    ]))
    assert plugin.last_user_message(str(transcript)) == prompt
    host.pause(tmp_path, conversation=True)
    payload = {"session_id": "s", "prompt": prompt, "transcript_path": str(transcript)}
    plugin.user_prompt(payload, tmp_path)
    host.resume(tmp_path, current_turn=True, session="s")
    plugin.stop(payload, tmp_path)
    assert [(item["role"], item["text"]) for item in client.observed] == [("user", prompt), ("assistant", "Noted.")]

@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_a_note_saved_before_the_reply_links_back_to_the_current_user_message(tmp_path, unused_tcp_port):
    from membrain.local_profile import ensure_profile
    from membrain.notes import NOTES_CONVERSATION, save_note

    directory = tmp_path / "brain"
    ensure_profile(directory, database_engine="embedded", api_port=unused_tcp_port)
    try:
        host.start(directory)
        context = host.prompt_context(directory, "current", "My appointment is on November 4.",
                                      turn_id="one", include_source=True)
        references, _ = json.JSONDecoder().raw_decode(context.split("source_messages=", 1)[1])
        with host.ready_client(directory) as client:
            note = save_note(client, "Appointment on November 4.", source_messages=references, kind="plan",
                             status="scheduled", occurs_at="2026-11-04")
            assert note["pending_source_count"] == 1
        host.finish_turn(directory, "current", "Noted.", turn_id="one")
        with host.ready_client(directory) as client:
            stored = client.timeline(roles=("assistant",), conversation_id=NOTES_CONVERSATION)["items"][0]
            original = client.timeline(event_ids=stored["source_event_ids"])["items"][0]
            assert original["text"] == "My appointment is on November 4." and stored["pending_source_count"] == 0
        assert "Appointment on November 4" in host.session_context(directory, "next")
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_a_rejected_spooled_record_is_set_aside_instead_of_blocking_the_rest(tmp_path):
    import httpx

    from membrain.client import MemoryActionError

    for text in ("first", "refused", "bad request", "third"):
        host.spool(tmp_path, host.message_record("s", "user", text))

    class Picky(Client):
        def observe(self, **record):
            if record["text"] == "refused":
                raise MemoryActionError({"outcome": "rejected", "error": {"code": "invalid_request", "retryable": False}})
            if record["text"] == "bad request":
                raise httpx.HTTPStatusError("400", request=httpx.Request("POST", "http://x"),
                                            response=httpx.Response(400))
            super().observe(**record)

    client = Picky()
    assert host.flush(client, tmp_path) == 4
    assert [item["text"] for item in client.observed] == ["first", "third"]
    assert (tmp_path / "plugin" / "spool.jsonl").read_text() == ""
    rejected = (tmp_path / "plugin" / "spool-rejected.jsonl").read_text().splitlines()
    assert [json.loads(line)["text"] for line in rejected] == ["refused", "bad request"]
    assert oct((tmp_path / "plugin" / "spool-rejected.jsonl").stat().st_mode & 0o777) == "0o600"

    host.spool(tmp_path, host.message_record("s", "user", "busy"))

    class Busy(Client):
        def observe(self, **record):
            raise MemoryActionError({"outcome": "failed", "error": {"code": "dependency_unavailable", "retryable": True}})

    with pytest.raises(MemoryActionError):
        host.flush(Busy(), tmp_path)
    assert "busy" in (tmp_path / "plugin" / "spool.jsonl").read_text()  # Kept for the next replay.


def test_the_spool_stops_growing_when_memory_has_been_down_too_long(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "SPOOL_BYTES", 200)
    for index in range(20):
        host.spool(tmp_path, host.message_record("s", "user", f"message number {index}"))
    assert (tmp_path / "plugin" / "spool.jsonl").stat().st_size < 600


def test_hooks_do_not_load_the_agent_runtime_or_cognition():
    import subprocess
    import sys

    code = ("import sys, membrain.plugin; print([m for m in ('membrain.runtime', 'membrain.chat_provider', "
            "'membrain.cognition', 'membrain.semantic', 'membrain.service') if m in sys.modules])")
    loaded = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert loaded == "[]"  # Every hook is a short process; loading the runtime would slow every message.


@pytest.mark.parametrize("secret", [
    "sk_live_" + "a1" * 12, "rk_test_" + "b2" * 10, "glpat-" + "c" * 20, "hf_" + "d" * 34, "npm_" + "e" * 36,
])
def test_more_key_formats_are_scrubbed(secret):
    assert host.scrub(f"use {secret} please") == f"use {host.SECRET_MARK} please"


def test_passwords_in_urls_assignments_and_words_are_scrubbed():
    assert host.scrub("db is postgresql://app:s3cretPass@db.internal:5432/main") == (
        f"db is postgresql://app:{host.SECRET_MARK}@db.internal:5432/main")
    assert host.scrub("aws_secret_access_key = wJalrXUtnFEMI/K7MDENG") == (
        f"aws_secret_access_key = {host.SECRET_MARK}")
    assert host.scrub("My password is Tr0ub4dor&3 so remember it") == (
        f"My password is {host.SECRET_MARK} so remember it")
    assert host.scrub("我的银行卡密码是884213，别忘了") == f"我的银行卡密码是{host.SECRET_MARK}"


def test_card_and_identity_numbers_are_removed_but_ordinary_numbers_are_kept():
    from membrain.privacy import NUMBER_MARK

    assert host.scrub("card 4111 1111 1111 1111 exp 12/29") == f"card {NUMBER_MARK} exp 12/29"
    assert host.scrub("身份证号11010519491231002X，请记住") == f"身份证号{NUMBER_MARK}，请记住"
    assert host.scrub("SSN 078-05-1120 on file") == f"SSN {NUMBER_MARK} on file"
    ordinary = ("Order 4111111111111112 shipped on 2026-10-29 at 14:05; call 13812345678 or +44 20 7946 0958; "
                "ID 110105194912310021 is not valid; max_tokens: 16384; the token ring game.")
    assert host.scrub(ordinary) == ordinary


def test_contacts_are_removed_only_when_asked(monkeypatch):
    from membrain.privacy import CONTACT_MARK

    text = "Email mei@example.com or call 13812345678 / +1 (415) 555-0134."
    assert host.scrub(text) == text
    monkeypatch.setenv("MEMBRAIN_REDACT_CONTACTS", "1")
    assert host.scrub(text) == f"Email {CONTACT_MARK} or call {CONTACT_MARK} / {CONTACT_MARK}."


def test_mcp_observations_are_scrubbed_before_they_are_stored(tmp_path):
    import asyncio

    from membrain.mcp_server import create_server

    class Observing(Client):
        def observe(self, text, **record):
            self.observed.append({"text": text, **record})
            return {"outcome": "accepted"}

    client = Observing()
    server = create_server(client, directory=tmp_path, require_turn_capture=False)
    asyncio.run(server.call_tool("memory_observe", {
        "text": "Deploy key sk-proj-" + "z" * 30 + " and card 4111 1111 1111 1111.", "conversation_id": "c",
        "branch_id": "main", "source_event_key": "k1"}))
    stored = client.observed[-1]["text"]
    assert "z" * 30 not in stored and "4111" not in stored and host.SECRET_MARK in stored


def test_erasing_a_person_waits_for_a_replay_and_keeps_other_peoples_queued_records(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    events, started, release = [], Event(), Event()
    host.spool(tmp_path, host.message_record("s", "user", "alice's message", user_id="alice"))
    host.spool(tmp_path, host.message_record("s", "user", "bob's message", user_id="bob"))

    class Replay(Client):
        def ensure_brain(self, brain, name):
            pass

        def observe(self, **record):
            started.set()
            assert release.wait(5)
            events.append("deliver " + record["text"])

    class Eraser(Client):
        def dashboard(self):
            return {"brain": {"scope_generation": 1}}

        def forget(self, ids, **options):
            events.append("erase")
            return {"outcome": "completed"}

    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: Eraser())
    with ThreadPoolExecutor() as pool:
        replay = pool.submit(host.flush, Replay(), tmp_path)
        assert started.wait(5)
        erase = pool.submit(host.erase_user, tmp_path, "alice")
        host.spool(tmp_path, host.message_record("s", "user", "bob's later message", user_id="bob"))
        assert not erase.done()  # The erase waits for the replay already under way.
        release.set()
        replay.result(timeout=10)
        erase.result(timeout=10)
    assert events == ["deliver alice's message", "deliver bob's message", "erase"]
    remaining = (tmp_path / "plugin" / "spool.jsonl").read_text()
    assert "bob's later message" in remaining and "alice" not in remaining


def test_an_export_replaces_an_existing_readable_file_with_an_owner_only_one(tmp_path, monkeypatch):
    import types

    from membrain import plugin_cli

    target = tmp_path / "export.json"
    target.write_text("old")
    target.chmod(0o644)
    monkeypatch.setattr(host, "export_user", lambda directory, user: {"messages": ["private words"]})
    args = types.SimpleNamespace(plugin_command="export-user", platform=None, user=None, group=None,
                                 user_id="qq:1", yes=True, out=target)
    assert plugin_cli._person(args, tmp_path) == 0
    assert "private words" in target.read_text() and oct(target.stat().st_mode & 0o777) == "0o600"


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_a_plugin_host_can_forget_a_message_and_its_note_by_following_the_skill(tmp_path):
    import asyncio

    from membrain.mcp_server import create_server
    from membrain.notes import list_notes

    directory = tmp_path / "brain"
    try:
        host.start(directory)
        context = host.prompt_context(directory, "first", "My dentist is Dr. Alvarez, Thursday at 3 pm.", turn_id="1",
                                      include_source=True)
        references, _ = json.JSONDecoder().raw_decode(context.split("source_messages=", 1)[1])
        host.finish_turn(directory, "first", "Noted.", turn_id="1")
        capture, _ = json.JSONDecoder().raw_decode(context.split("recording_capture=", 1)[1])
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            _, saved = asyncio.run(server.call_tool("memory_note", {"text": "Dentist: Dr. Alvarez, Thursday 3 pm.", "kind": "plan",
                                                         "source_messages": references, "recording_capture": capture}))
            assert saved["note_id"]
            _, found = asyncio.run(server.call_tool("memory_recall", {"query": "dentist Alvarez", "with_ids": True}))
            assert isinstance(found["scope_generation"], int)
            original = [record for record in found["records"] if record["text"] == "My dentist is Dr. Alvarez, "
                        "Thursday at 3 pm." and record["conversation_id"] == "first"]
            assert original and "memory_forget" in found["how_to_forget"]
            _, result = asyncio.run(server.call_tool("memory_forget", {
                "ids": [original[0]["event_id"]], "kind": "events", "mode": "erase_content",
                "expected_scope_generation": found["scope_generation"]}))
            assert result.get("outcome") not in ("rejected", "conflict", "failed"), result
            assert list_notes(client)["items"] == []  # The note drawn from the message went with it.
        later = host.prompt_context(directory, "second", "Who is my dentist?", turn_id="1")
        assert "Alvarez" not in (later or "") and "Alvarez" not in host.session_context(directory, "third")
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_a_pause_the_agent_starts_on_its_own_ends_with_the_conversation(tmp_path, monkeypatch):
    import asyncio

    from membrain.mcp_server import create_server

    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    host.prompt_context(tmp_path, "s1", "Off the record: I'm job hunting.", turn_id="t1")
    server = create_server(Client(), directory=tmp_path)
    _, result = asyncio.run(server.call_tool("memory_pause", {}))
    assert result["scope"] == "this conversation"
    host.finish_turn(tmp_path, "s1", "Okay, not keeping that.", turn_id="t1")
    host.session_context(tmp_path, "s1")  # The same conversation continuing (for example after compaction).
    assert host.paused(tmp_path) and client.observed == []
    resumed = host.session_context(tmp_path, "s2")
    assert "paused for an earlier conversation only" in resumed and not host.paused(tmp_path)
    host.prompt_context(tmp_path, "s2", "My sister moved to Leeds.", turn_id="t1")
    host.finish_turn(tmp_path, "s2", "Noted.", turn_id="t1")
    assert [record["text"] for record in client.observed] == ["My sister moved to Leeds.", "Noted."]

    asyncio.run(server.call_tool("memory_pause", {"until_resumed": True}))
    assert "Recording is currently paused" in host.session_context(tmp_path, "s3") and host.paused(tmp_path)
    host.resume(tmp_path)
    tool = {tool.name: tool for tool in asyncio.run(server.list_tools())}["memory_pause"]
    assert "between you" in tool.description and "sensitive note" in tool.description
