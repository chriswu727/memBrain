import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from test_server_recording import policy
from test_server_recording import turns as turns

from membrain import host, host_recording
from membrain.api import create_app
from membrain.client import MemoryClient
from membrain.config import Settings


@pytest.fixture
def connected(turns, monkeypatch):
    key = "capture-policy-test"
    settings = Settings(database_url=turns.database.dsn,
                        api_keys={hashlib.sha256(key.encode()).hexdigest(): turns.principal}, recall_processes=0)
    with TestClient(create_app(settings, turns.service)) as api:
        def transport(request):
            response = api.request(request.method, request.url.path, headers=request.headers, content=request.content)
            return httpx.Response(response.status_code, json=response.json())

        def factory(directory, user_id=None):
            return host.use_brain(MemoryClient("http://testserver", key, turns.brain,
                                  transport=httpx.MockTransport(transport)), user_id)

        monkeypatch.setattr(host, "ready_client", factory)
        monkeypatch.setattr(host, "start_in_background", lambda *args: None)
        yield factory


def local_text(directory):
    return "\n".join(p.read_text() for p in (directory / "plugin").rglob("*") if p.is_file())


def test_server_paused_input_cannot_be_revived_by_local_resume(turns, connected, tmp_path):
    policy(turns, True, 0)
    notice = host.prompt_context(tmp_path, "s", "Confidential draft", turn_id="private", include_source=True)
    assert "server recording controls" in notice and "membrain-source" not in notice
    assert "Confidential draft" not in local_text(tmp_path)
    host.resume(tmp_path, session="s", current_turn=True)
    policy(turns, False, 1)
    assert host.finish_turn(tmp_path, "s", "Confidential reply", prompt="Confidential draft", turn_id="private") == []
    host.prompt_context(tmp_path, "s", "Public draft", turn_id="public")
    assert len(host.finish_turn(tmp_path, "s", "Public reply", turn_id="public")) == 2
    assert "Confidential" not in local_text(tmp_path)
    assert len(turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"]) == 2


def test_pause_resume_between_stage_and_callback_rejects_both_records(turns, connected, tmp_path):
    host.prompt_context(tmp_path, "s", "Old draft", turn_id="old")
    policy(turns, True, 0)
    policy(turns, False, 1)
    assert host.finish_turn(tmp_path, "s", "Old reply", turn_id="old") == []
    assert not turns.service.timeline(turns.principal, turns.brain)["items"]
    assert "Old draft" not in local_text(tmp_path) and "Old reply" not in local_text(tmp_path)


def test_offline_replay_keeps_capture_revision_and_drops_stale_content(turns, connected, tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", "Queued draft", turn_id="old")
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    records = host.finish_turn(tmp_path, "s", "Queued reply", turn_id="old")
    assert [r["_recording"]["revision"] for r in records] == [0, 0]
    policy(turns, True, 0)
    policy(turns, False, 1)
    with connected(tmp_path) as client:
        assert host.flush(client, tmp_path) == 2
    assert "Queued" not in local_text(tmp_path)
    assert not turns.service.timeline(turns.principal, turns.brain)["items"]


def test_known_server_pause_applies_offline_and_survives_local_resume(turns, connected, tmp_path, monkeypatch):
    policy(turns, True, 0)
    host.prompt_context(tmp_path, "s", "Private online", turn_id="one")
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    host.resume(tmp_path)
    notice = host.prompt_context(tmp_path, "s", "Private offline", turn_id="two")
    assert "last known policy" in notice
    assert host.finish_turn(tmp_path, "s", "Private reply", turn_id="two") == []
    assert "Private" not in local_text(tmp_path)
    policy(turns, False, 1)
    monkeypatch.setattr(host, "ready_client", connected)
    host.prompt_context(tmp_path, "s", "Resumed draft", turn_id="three")
    records = host.finish_turn(tmp_path, "s", "Resumed reply", turn_id="three")
    assert [r["_recording"]["revision"] for r in records] == [2, 2]


def test_host_control_result_matches_actual_capture_and_server_scope(turns, connected, tmp_path):
    policy(turns, True, 0)
    host_recording.pause(tmp_path, 1)
    result = host_recording.resume(tmp_path)
    assert result["recording"] == "paused" and result["local_recording"] == "on"
    assert result["controls"]["server"]["revision"] == 1
    host.prompt_context(tmp_path, "s", "Excluded synthetic input", turn_id="excluded")
    assert host.finish_turn(tmp_path, "s", "Excluded synthetic reply", turn_id="excluded") == []
    assert not turns.service.timeline(turns.principal, turns.brain)["items"]
    assert "Excluded synthetic" not in local_text(tmp_path)
    policy(turns, False, 1)
    assert host_recording.control_status(tmp_path)["recording"] == "on"
    host.prompt_context(tmp_path, "s", "Public synthetic input", turn_id="public")
    host.finish_turn(tmp_path, "s", "Public synthetic reply", turn_id="public")
    assert len(turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"]) == 2


@pytest.mark.parametrize("revision", [0, 2])
def test_legacy_queue_is_only_accepted_before_policy_changes(turns, connected, tmp_path, revision):
    if revision:
        policy(turns, True, 0)
        policy(turns, False, 1)
    host.spool(tmp_path, host.message_record("s", "user", "Legacy draft", turn_id="old"))
    with connected(tmp_path) as client:
        assert host.flush(client, tmp_path) == 1
    assert len(turns.service.timeline(turns.principal, turns.brain)["items"]) == (0 if revision else 1)
    assert "Legacy draft" not in local_text(tmp_path)


def test_local_current_turn_resume_retains_original_server_revision(turns, connected, tmp_path):
    host.pause(tmp_path)
    host.prompt_context(tmp_path, "s", "Resume recording please", turn_id="old")
    host.resume(tmp_path, current_turn=True, session="s")
    policy(turns, True, 0)
    policy(turns, False, 1)
    with connected(tmp_path) as client:
        assert host_recording.status(tmp_path, client)["revision"] == 2
    assert host.finish_turn(tmp_path, "s", "Old reply", prompt="Resume recording please", turn_id="old") == []
    assert not turns.service.timeline(turns.principal, turns.brain)["items"]


def test_whole_turn_capture_reads_current_policy(turns, connected, tmp_path):
    policy(turns, True, 0)
    assert host.finish_turn(tmp_path, "s", "Private reply", prompt="Private draft", turn_id="one") == []
    policy(turns, False, 1)
    records = host.finish_turn(tmp_path, "s", "Public reply", prompt="Public draft", turn_id="two")
    assert [r["_recording"]["revision"] for r in records] == [2, 2]


def test_recording_cache_is_per_owner_and_roleplay(turns, connected, tmp_path):
    alice, bob = "alice-" + turns.brain, "bob-" + turns.brain
    owners = [alice, bob, host.roleplay_user(alice, "Merlin")]
    for owner in owners:
        with connected(tmp_path, owner) as client:
            if owner == alice:
                client.set_recording(paused=True, expected_revision=0)
            result = host_recording.status(tmp_path, client, owner)
            assert result["paused"] is (owner == alice)
    for owner in owners:
        assert host_recording.status(tmp_path, user_id=owner)["paused"] is (owner == alice)
    assert not host_recording.status(tmp_path)["paused"]


def test_rebound_target_cannot_receive_an_old_capture(turns, connected, tmp_path):
    host.prompt_context(tmp_path, "s", "Original target draft", turn_id="old")
    record = next(iter(host.session_state(tmp_path, "s")["turns"].values()))["record"]
    with connected(tmp_path) as client:
        client._http.headers["X-Memory-Recovery-Epoch"] = "00000000-0000-4000-8000-000000000001"
        assert not host.deliver(tmp_path, client, record)
    assert not (tmp_path / "plugin" / "spool.jsonl").exists()


def test_invalid_cache_fails_closed(tmp_path):
    path = tmp_path / "plugin" / "recording-policies" / (host_recording.digest([None]) + ".json")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"paused": False, "revision": True, "target": "invalid"}))
    assert host_recording.status(tmp_path)["paused"]


def test_rejected_old_callback_does_not_clear_new_turn_cues(turns, connected, tmp_path):
    host.prompt_context(tmp_path, "s", "Old draft", turn_id="old")
    policy(turns, True, 0)
    policy(turns, False, 1)
    host.prompt_context(tmp_path, "s", "New draft", turn_id="new")
    assert host.finish_turn(tmp_path, "s", "Old reply", turn_id="old") == []
    assert host.session_state(tmp_path, "s")["last_prompt"] == "New draft"
    assert len(host.finish_turn(tmp_path, "s", "New reply", turn_id="new")) == 2


def test_replayed_prompt_observing_server_pause_scrubs_existing_stage(turns, connected, tmp_path):
    host.prompt_context(tmp_path, "s", "Private draft", turn_id="old")
    policy(turns, True, 0)
    host.prompt_context(tmp_path, "s", "Private draft", turn_id="old")
    assert "Private draft" not in local_text(tmp_path)
    policy(turns, False, 1)
    assert host.finish_turn(tmp_path, "s", "Private reply", turn_id="old") == []


def test_out_of_order_policy_response_cannot_clear_cached_pause(tmp_path):
    class Client:
        brain_id = "brain"

        def recording_status(self):
            return self.policy

    client = Client()
    client.policy = {"paused": True, "revision": 1}
    assert host_recording.status(tmp_path, client)["paused"]
    client.policy = {"paused": False, "revision": 0}
    assert host_recording.status(tmp_path, client)["paused"]
    client.policy = {"paused": False, "revision": 2}
    assert not host_recording.status(tmp_path, client)["paused"]


def test_read_failure_uses_last_known_policy_without_relabeling_records(tmp_path):
    class Client:
        brain_id = "brain"

        def recording_status(self):
            if self.fail:
                raise ConnectionError("offline")
            return {"paused": True, "revision": 3}

    client = Client()
    client.fail = False
    host_recording.status(tmp_path, client)
    client.fail = True
    assert host_recording.status(tmp_path, client)["paused"]
    assert host_recording.status(tmp_path, client)["revision"] == 3


def test_previous_prompt_from_old_policy_is_not_used_as_a_recall_cue(turns, connected, tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", "Old private cue", turn_id="old")
    policy(turns, True, 0)
    policy(turns, False, 1)
    cues = []

    def recall(*args, **kwargs):
        cues.extend(kwargs["cues"])
        return None

    monkeypatch.setattr(host, "recall_context", recall)
    host.prompt_context(tmp_path, "s", "Fresh question", turn_id="new")
    assert "Old private cue" not in cues


def test_server_exclusion_cannot_be_downgraded_to_local_prompt_pause():
    from membrain import host_turns

    state = {}
    record = host.message_record("s", "user", "Private draft", turn_id="t")
    host_turns.stage(state, record, "server", 1)
    host_turns.stage(state, record, "prompt", 2)
    entry = state["turns"][host_turns.key(record)]
    entry["resumed"] = True
    assert host_turns.take(state, owner=None, producer=record["producer_ref"],
                           source=record["source_event_key"], prompt=record)[1]


@pytest.mark.parametrize("malformed", [[], None, "invalid", 3])
def test_malformed_queue_entry_does_not_block_later_valid_input(tmp_path, malformed):
    from test_host import Client

    host.spool(tmp_path, malformed)
    host.spool(tmp_path, host.message_record("s", "user", "Valid queued input"))
    client = Client()
    assert host.flush(client, tmp_path) == 2
    assert [item["text"] for item in client.observed] == ["Valid queued input"]
    assert not (tmp_path / "plugin" / "spool.jsonl").read_text()
