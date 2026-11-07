import json
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, host
from membrain.adapters import hermes


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


class Client:
    brain_id = "brain"

    def __init__(self, notes=()):
        self.observed, self.notes, self.forgotten = [], list(notes), []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def observe(self, text, **options):
        event_id = f"e{len(self.observed) + 1}"
        self.observed.append({"text": text, **options})
        if options.get("conversation_id") == "membrain-notes":
            self.notes.insert(0, {"event_id": event_id, "text": text, "actor_role": "assistant",
                                  "producer": options.get("producer_ref"), "recorded_at": "2026-10-28T00:00:00Z"})
        return {"result": {"accepted_event_ids": [event_id]}}

    def timeline(self, **options):
        if options.get("conversation_id") == "membrain-notes":
            return {"complete": True, "items": [note for note in self.notes if note["event_id"] not in self.forgotten]}
        return {"complete": True, "items": []}

    def recall(self, query, **options):
        return {"result": {"items": []}}

    def dashboard(self):
        return {"brain": {"scope_generation": 3}}

    def forget(self, ids, **options):
        self.forgotten.extend(ids)


def provider(tmp_path, monkeypatch, client, **kwargs):
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    instance = hermes.MembrainProvider()
    instance.initialize("h1", hermes_home=str(tmp_path / "home"), platform="cli", **kwargs)
    return instance


def test_page_deletion_is_reflected_when_the_host_requests_its_block_again(tmp_path, monkeypatch):
    client = Client(notes=[{"event_id": "n1", "text": "Jordan and the user hiked together.",
                            "actor_role": "assistant", "recorded_at": "2026-04-01T00:00:00Z"}])
    instance = provider(tmp_path, monkeypatch, client)
    assert "Jordan" in instance.system_prompt_block()
    client.forgotten.append("n1")
    assert "Jordan" not in instance.system_prompt_block()


def test_register_hands_hermes_a_new_provider_each_time():
    registered = []

    class Context:
        def register_memory_provider(self, value):
            registered.append(value)

    hermes.register(Context())
    hermes.register(Context())
    assert all(isinstance(value, hermes.MembrainProvider) for value in registered)
    assert registered[0] is not registered[1] and registered[0].name == "membrain" and registered[0].is_available()
    assert [tool["name"] for tool in registered[0].get_tool_schemas()] == [
        "membrain_note", "membrain_search", "membrain_boundary", "membrain_pause", "membrain_resume"]


def test_profiles_get_their_own_installation_unless_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MEMBRAIN_DIRECTORY", str(tmp_path / "shared"))
    assert hermes._default_directory(str(tmp_path / ".hermes")) == tmp_path / "shared"
    assert hermes._default_directory(str(tmp_path / "work-profile")) == tmp_path / "work-profile" / "membrain"
    instance = hermes.MembrainProvider()
    (tmp_path / "work-profile").mkdir()
    instance.save_config({"directory": str(tmp_path / "chosen")}, str(tmp_path / "work-profile"))
    assert hermes._default_directory(str(tmp_path / "work-profile")) == tmp_path / "chosen"


def test_a_turn_is_recalled_before_and_stored_after_the_reply(tmp_path, monkeypatch):
    client = Client(notes=[{"event_id": "n1", "text": "Mom uses a walker.", "actor_role": "assistant",
                            "recorded_at": "2026-04-01T00:00:00Z"}])
    instance = provider(tmp_path, monkeypatch, client, agent_context="primary")
    block = instance.system_prompt_block()
    assert "membrain_note tool" in block and "membrain_pause" in block and "Mom uses a walker. (id: n1)" in block
    assert instance.system_prompt_block() == block
    instance.prefetch("Plan Sunday dinner for Mom.", session_id="h1")
    assert client.observed == []
    instance.sync_turn("Plan Sunday dinner for Mom.", "A seated menu.", session_id="h1")
    assert [(record["role"], record["text"]) for record in client.observed] == [
        ("user", "Plan Sunday dinner for Mom."), ("assistant", "A seated menu.")]
    instance.sync_turn("A turn Hermes did not prefetch for.", "Answered.", session_id="h1")
    assert [record["text"] for record in client.observed][-2:] == ["A turn Hermes did not prefetch for.", "Answered."]


def test_subagents_and_paused_recording_store_nothing(tmp_path, monkeypatch):
    client = Client()
    sub = provider(tmp_path, monkeypatch, client, agent_context="subagent")
    sub.prefetch("internal task", session_id="h1")
    sub.sync_turn("internal task", "done", session_id="h1")
    assert "cannot change memory" in sub.handle_tool_call("membrain_boundary", {"topic": "my ex"})
    instance = provider(tmp_path, monkeypatch, client)
    assert json.loads(instance.handle_tool_call("membrain_pause", {}))["recording"] == "paused"
    instance.sync_turn("Off the record: I'm job hunting.", "Understood.", session_id="h1")
    assert client.observed == []
    assert json.loads(instance.handle_tool_call("membrain_resume", {})) == {"recording": "on"}


def test_tools_save_and_replace_notes_and_search(tmp_path, monkeypatch):
    client = Client()
    instance = provider(tmp_path, monkeypatch, client)
    first = json.loads(instance.handle_tool_call("membrain_note", {"text": "Dinner on Sat May 9."}))
    second = json.loads(instance.handle_tool_call("membrain_note", {"text": "Dinner moved to Sun May 17.",
                                                                    "replaces": [first["note_id"]]}))
    assert second["replaced"] == [first["note_id"]] and client.forgotten == [first["note_id"]]
    assert "error" in json.loads(instance.handle_tool_call("membrain_note", {"text": "x" * 400}))
    assert json.loads(instance.handle_tool_call("membrain_search", {"query": "dinner"})) == {
        "context": "No matching records."}
    assert "Unknown tool" in instance.handle_tool_call("other", {})


def test_builtin_memory_writes_are_mirrored_as_notes(tmp_path, monkeypatch):
    client = Client()
    instance = provider(tmp_path, monkeypatch, client)
    instance.on_memory_write("add", "user", "Prefers short replies.")
    instance.on_memory_write("replace", "user", "Prefers short replies, signed Hao.",
                             {"previous_content": "Prefers short replies."})
    assert [note["text"] for note in client.timeline(conversation_id="membrain-notes")["items"]] == [
        "Prefers short replies, signed Hao."]
    instance.on_memory_write("remove", "user", "", {"previous_content": "Prefers short replies, signed Hao."})
    assert client.timeline(conversation_id="membrain-notes")["items"] == []


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_hermes_sessions_share_memory_through_a_real_service(tmp_path, monkeypatch):
    directory = tmp_path / "brain"
    monkeypatch.setenv("MEMBRAIN_DIRECTORY", str(directory))
    monkeypatch.setenv("HOME", str(tmp_path))
    try:
        host.start(directory)
        first = hermes.MembrainProvider()
        first.initialize("session-1", hermes_home=str(Path(tmp_path) / ".hermes"), platform="telegram", user_id="42")
        first.system_prompt_block()
        first.prefetch("My cat Biscuit is allergic to chicken.", session_id="session-1")
        first.sync_turn("My cat Biscuit is allergic to chicken.", "Noted, no chicken treats.", session_id="session-1")
        assert "note_id" in json.loads(first.handle_tool_call("membrain_note", {"text": "Cat Biscuit: chicken allergy."}))
        second = hermes.MembrainProvider()
        second.initialize("session-2", hermes_home=str(Path(tmp_path) / ".hermes"), platform="telegram", user_id="42")
        block = second.system_prompt_block()
        assert "Cat Biscuit: chicken allergy." in block and "allergic to chicken" in block
        shared = json.loads(first.handle_tool_call("membrain_note", {
            "text": "We planned Biscuit's meals together.", "kind": "milestone", "shared": True}))
        assert "note_id" in shared
        readonly = hermes.MembrainProvider()
        readonly.initialize("readonly", hermes_home=str(Path(tmp_path) / ".hermes"), platform="telegram",
                            user_id="42", agent_context="subagent")
        assert "Cat Biscuit: chicken allergy." in readonly.system_prompt_block()
        assert "cannot change memory" in readonly.handle_tool_call("membrain_note", {
            "text": "Unauthorized synthetic replacement.", "replaces": [shared["note_id"]]})
        assert "cannot change memory" in readonly.handle_tool_call("membrain_pause", {"until_resumed": True})
        assert not host.paused(directory, first._user)
        host.pause(directory, user_id=first._user)
        assert "cannot change memory" in readonly.handle_tool_call("membrain_resume", {})
        assert host.paused(directory, first._user)
        host.resume(directory, user_id=first._user)
        boundary = json.loads(first.handle_tool_call("membrain_boundary", {"topic": "my cat", "aliases": ["Biscuit", "小饼干"]}))
        assert boundary["boundaries"][0]["aliases"] == ["Biscuit", "小饼干"]
        with host.ready_client(directory, first._user) as client:
            assert client.relationship()["shared_moments"][0]["id"] == shared["note_id"]
        hidden = first.system_prompt_block()
        assert "Cat Biscuit: chicken allergy." not in hidden and "allergic to chicken" not in hidden
        blocked = json.loads(second.handle_tool_call("membrain_search", {"query": "chicken allergy"}))["context"]
        assert "allergic to chicken" not in blocked
        raised = json.loads(second.handle_tool_call("membrain_search", {"query": "Biscuit chicken allergy"}))["context"]
        assert "allergic to chicken" in raised
        # Someone else on the gateway, and the owner at the command line, each have their own memory.
        stranger = hermes.MembrainProvider()
        stranger.initialize("session-3", hermes_home=str(Path(tmp_path) / ".hermes"), platform="telegram", user_id="999")
        assert "Biscuit" not in stranger.system_prompt_block()
        assert "Biscuit" not in json.loads(stranger.handle_tool_call("membrain_search", {"query": "Biscuit cat allergy"}))[
            "context"]
        owner = hermes.MembrainProvider()
        owner.initialize("session-4", hermes_home=str(Path(tmp_path) / ".hermes"), platform="cli")
        assert "Biscuit" not in owner.system_prompt_block()
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_hermes_user_file_is_imported_once_and_not_repeated_in_hermes(tmp_path, monkeypatch):
    memories = tmp_path / "home" / "memories"
    memories.mkdir(parents=True)
    (memories / "USER.md").write_text("Allergic to sesame.\n§\nSister Mei, birthday 14 November.", encoding="utf-8")
    client = Client(notes=[{"event_id": "n1", "text": "Prefers short replies.", "actor_role": "assistant",
                            "producer": "membrain-notes", "recorded_at": "2026-04-01T00:00:00Z"}])
    instance = provider(tmp_path, monkeypatch, client)
    block = instance.system_prompt_block()
    assert [note["text"] for note in client.notes if note.get("producer") == "membrain-import:hermes"] == [
        "Sister Mei, birthday 14 November.", "Allergic to sesame."]
    assert "Prefers short replies." in block and "Allergic to sesame" not in block  # Hermes shows its own file.
    again = provider(tmp_path, monkeypatch, client)
    again.system_prompt_block()
    assert len(client.notes) == 3  # Unchanged file: no second import.
    instance.on_memory_write("add", "memory", "Server runs Ubuntu.")
    assert len(client.notes) == 3  # Environment memory stays in Hermes.


def test_gateway_senders_get_their_own_memory_unless_listed_as_the_owner():
    assert hermes.memory_user({"platform": "cli"}) is None
    assert hermes.memory_user({}) is None
    assert hermes.memory_user({"platform": "telegram", "user_id": "42"}) == "hermes:telegram:42"
    assert hermes.memory_user({"platform": "telegram", "user_id": "42", "chat_type": "group", "chat_id": "-100"}) == (
        "hermes:telegram:group:-100:42")
    assert hermes.memory_user({"platform": "discord", "gateway_session_key": "k"}) == "hermes:discord:chat:k"
    assert hermes.memory_user({"platform": "telegram", "user_id": "42"}, ["telegram:42"]) is None
    assert hermes.memory_user({"platform": "telegram", "user_id": "42", "chat_type": "group"}, ["telegram:42"]) is None


def test_a_gateway_session_reads_and_writes_only_its_senders_memory(tmp_path, monkeypatch):
    users = []
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: users.append(user_id) or client)
    home = tmp_path / "home"
    (home / "memories").mkdir(parents=True)
    (home / "memories" / "USER.md").write_text("The owner is allergic to sesame.\n", encoding="utf-8")
    instance = hermes.MembrainProvider()
    instance.initialize("g1", hermes_home=str(home), platform="telegram", user_id="999")
    instance.system_prompt_block()
    instance.handle_tool_call("membrain_search", {"query": "allergy"})
    instance.on_memory_write("add", "user", "Likes trains.")
    assert set(users) == {"hermes:telegram:999"}
    assert not any("sesame" in record["text"] or "trains" in record["text"] for record in client.observed)
