"""User-facing control results must not mistake a local mutation for server authority."""
import io
import json
import time

import pytest

from membrain import host, host_recording, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker


class PolicyClient:
    brain_id = "synthetic-brain"

    def __init__(self, paused=False, revision=0):
        self.policy = {"paused": paused, "revision": revision}
        self.reads = 0
        self.closed = False

    def recording_status(self):
        self.reads += 1
        return self.policy

    def close(self):
        self.closed = True


@pytest.fixture
def client(monkeypatch):
    client = PolicyClient()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "start_in_background", lambda *args: pytest.fail("No service launch"))
    return client


def test_local_resume_reports_server_pause_without_changing_it(tmp_path, client):
    client.policy = {"paused": True, "revision": 7}
    host.pause(tmp_path)
    result = host_recording.resume(tmp_path)
    assert result["local_recording"] == "on"
    assert result["recording"] == "paused" and result["capture_blocked"]
    assert result["controls"]["server"] == {
        "scope": "brain", "state": "paused", "availability": "current",
        "last_known_paused": True, "revision": 7}
    assert client.reads == 1 and client.closed
    assert not host.paused(tmp_path)


def test_user_resume_does_not_resume_installation_or_other_user(tmp_path, client):
    host.pause(tmp_path, 1)
    host.pause(tmp_path, user_id="alice", conversation=True, session="alice-session")
    host.pause(tmp_path, user_id="bob")
    result = host_recording.resume(tmp_path, "alice")
    assert result["recording"] == "paused"
    assert result["controls"]["local"][0]["scope"] == "installation"
    assert result["controls"]["local"][1] == {"scope": "user", "state": "on"}
    assert host.paused(tmp_path, "bob")
    assert client.policy == {"paused": False, "revision": 0}


def test_conversation_pause_reports_its_scope_without_server_mutation(tmp_path, client):
    result = host_recording.pause(tmp_path, user_id="alice", conversation=True, session="s")
    control = result["controls"]["local"][1]
    assert control == {"scope": "conversations", "applies_to": "user", "state": "paused", "until": None}
    assert result["scope"] == "this conversation"
    assert result["controls"]["server"]["state"] == "on"
    assert not host.paused(tmp_path, "bob")


@pytest.mark.parametrize("cached_pause", [True, False, None])
def test_offline_resume_reports_unknown_and_keeps_cached_protection(tmp_path, client, monkeypatch, cached_pause):
    if cached_pause is not None:
        client.policy = {"paused": cached_pause, "revision": 2}
        host_recording.status(tmp_path, client)
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    host.pause(tmp_path)
    result = host_recording.resume(tmp_path)
    assert result["recording"] == "unknown"
    assert result["capture_blocked"] is (cached_pause is True)
    assert result["controls"]["server"]["last_known_paused"] is cached_pause
    assert "unknown" in host_recording.notice(host_recording.status(tmp_path))


def test_unreadable_local_state_is_unknown_but_blocks_capture(tmp_path, client):
    host._pause_file(tmp_path).write_text('{broken', encoding="utf-8")
    result = host_recording.control_status(tmp_path)
    assert result["recording"] == "unknown" and result["capture_blocked"]
    assert result["controls"]["local"] == [
        {"scope": "installation", "state": "unknown", "reason": "local_state_unreadable"}]
    assert host_recording.resume(tmp_path)["recording"] == "on"


def test_expired_local_pause_no_longer_blocks_capture(tmp_path, client):
    host._pause_file(tmp_path).write_text(json.dumps({"until": time.time() - 10}), encoding="utf-8")
    result = host_recording.control_status(tmp_path)
    assert result["recording"] == "on" and not result["capture_blocked"]


def test_roleplay_reports_inherited_real_person_pause(tmp_path, client):
    host.pause(tmp_path, user_id="alice", conversation=True, session="s")
    result = host_recording.resume(tmp_path, host.roleplay_user("alice", "Wren"))
    assert result["recording"] == "paused"
    assert any(item["scope"] == "conversations" for item in result["controls"]["local"])


def test_stale_response_does_not_claim_current_state(tmp_path, client):
    client.policy = {"paused": True, "revision": 2}
    host_recording.status(tmp_path, client)
    client.policy = {"paused": False, "revision": 1}
    result = host_recording.control_status(tmp_path)
    assert result["recording"] == "unknown" and result["capture_blocked"]
    assert result["controls"]["server"]["revision"] == 2


def test_plugin_tool_exposes_effective_state(tmp_path, client, capsys):
    client.policy = {"paused": True, "revision": 1}
    plugin.run_tool("resume", tmp_path, io.BytesIO(b'{}'))
    result = json.loads(capsys.readouterr().out)
    assert result["recording"] == "paused"
    assert result["local_recording"] == "on"
    assert result["reason"] == "session_required"


def test_chat_adapter_exposes_effective_state(tmp_path, client):
    client.policy = {"paused": True, "revision": 1}
    memory = ChatMemory(directory=tmp_path)
    result = memory.resume(Speaker("test", "alice"))
    assert result["recording"] == "paused"
    assert result["local_recording"] == "on"


def test_service_failure_does_not_hide_successful_local_mutation(tmp_path, client, monkeypatch):
    def failed(*args):
        raise ConnectionError("synthetic unavailable service")

    host.pause(tmp_path)
    monkeypatch.setattr(host, "ready_client", failed)
    result = host_recording.resume(tmp_path)
    assert result["local_recording"] == "on" and result["recording"] == "unknown"
    assert not host.paused(tmp_path)


def test_legacy_local_callers_keep_their_result_contract(tmp_path):
    host.pause(tmp_path)
    assert host.resume(tmp_path) == {"recording": "on"}


def test_chat_roleplay_checks_the_story_brain_after_resuming_real_person(tmp_path, client, monkeypatch):
    selected = []

    def ready(directory, owner=None):
        selected.append(owner)
        client.policy = {"paused": host.is_roleplay(owner), "revision": 3}
        return client

    monkeypatch.setattr(host, "ready_client", ready)
    memory = ChatMemory(tmp_path, roleplay="Wren")
    speaker = Speaker("test", "alice")
    host.pause(tmp_path, user_id=memory.user_id(speaker))
    result = memory.resume(speaker)
    assert selected == [memory.memory_user(speaker)]
    assert result["recording"] == "paused" and result["local_recording"] == "on"
    assert not host.paused(tmp_path, memory.memory_user(speaker))


def test_installation_status_does_not_report_cached_on_as_current(tmp_path, client, monkeypatch):
    host_recording.status(tmp_path, client)
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    result = host.installation_status(tmp_path)
    assert result["recording"] == "unknown"
    assert result["controls"]["server"]["last_known_paused"] is False


def test_corrupt_server_cache_is_unknown_not_a_confirmed_pause(tmp_path, client, monkeypatch):
    host_recording.status(tmp_path, client)
    path = next((tmp_path / "plugin" / "recording-policies").glob("*.json"))
    path.write_text('{broken', encoding="utf-8")
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    result = host_recording.control_status(tmp_path)
    assert result["recording"] == "unknown" and result["capture_blocked"]
    assert result["controls"]["server"]["last_known_paused"] is None
