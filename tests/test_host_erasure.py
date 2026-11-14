import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_erasure_recording_fence import erase
from test_host_recording import connected as connected
from test_server_recording import turns as turns

from membrain import host, host_erasure, host_queue, host_recording
from membrain.helpers import digest


def files(root):
    return "\n".join(path.read_text() for path in root.rglob("*") if path.is_file())


def capture(turns, connected, root):
    host.prompt_context(root, "s", "Deleted synthetic prompt.", turn_id="deleted")
    records = host.finish_turn(root, "s", "Deleted synthetic reply.", turn_id="deleted")
    host.prompt_context(root, "s", "Surviving synthetic prompt.", turn_id="control")
    control = host.finish_turn(root, "s", "Surviving synthetic reply.", turn_id="control")
    for record in [*records, *control]:
        host.spool(root, record)
    # A historical permanent rejection kept a second plaintext copy.
    (root / "plugin" / "spool-rejected.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in [*records, *control]))
    items = turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"]
    target = next(item["event_id"] for item in items if item["text"] == "Deleted synthetic prompt.")
    erase(turns, kind="events", ids=[target])
    return records, control


def test_external_erasure_clears_host_files_on_policy_contact(turns, connected, tmp_path):
    removed, control = capture(turns, connected, tmp_path)
    with connected(tmp_path) as client:
        host_recording.status(tmp_path, client)
    text = files(tmp_path)
    for record in removed:
        assert record["text"] not in text
        assert digest([record["text"]]) not in text
    assert all(record["text"] in text for record in control)
    assert [json.loads(line) for line in host_queue.unacknowledged(tmp_path / "plugin" / "spool.jsonl")] == control
    assert digest([control[0]["text"]]) in text
    state = host.session_state(tmp_path, "s")
    entry = state["turns"][host_erasure.host_turns.key(removed[0])]
    assert entry["exclusion"]["reason"] == "erased"
    assert "fingerprint" not in entry and "note_capture" not in entry
    assert host.spool(tmp_path, removed[0]) is False
    host.prompt_context(tmp_path, "s", removed[0]["text"], turn_id="deleted")
    assert removed[0]["text"] not in files(tmp_path)


def test_reconciliation_preserves_unknown_and_other_target_queues(turns, connected, tmp_path):
    removed, _ = capture(turns, connected, tmp_path)
    unrelated = host.message_record("offline", "user", "Not yet sent.", turn_id="new")
    with connected(tmp_path) as client:
        host_recording.stamp(unrelated, {"revision": 0, "target": host_recording._target(client)})
        foreign = {**removed[0], "text": "Another account's copy.",
                   "_recording": {"revision": 0, "target": "other-target"}}
        other_owner = {**removed[0], "_user": "another-user", "text": "Another user's copy."}
        for record in (unrelated, foreign, other_owner):
            host.spool(tmp_path, record)
        host_erasure.reconcile(tmp_path, client)
    text = files(tmp_path)
    assert all(record["text"] in text for record in (unrelated, foreign, other_owner))
    assert removed[0]["text"] not in text


def test_reconciliation_serializes_with_journal_admission(turns, connected, tmp_path):
    removed, control = capture(turns, connected, tmp_path)
    entered, release = Event(), Event()
    with connected(tmp_path) as client:
        reader = client.recording_erasures

        def held(references):
            response = reader(references)
            entered.set()
            assert release.wait(4)
            return response

        client.recording_erasures = held
        with ThreadPoolExecutor(max_workers=3) as pool:
            reconcile = pool.submit(host_erasure.reconcile, tmp_path, client)
            assert entered.wait(4)
            erased_append = pool.submit(host.spool, tmp_path, removed[0])
            kept_append = pool.submit(host.spool, tmp_path, control[0])
            release.set()
            assert reconcile.result()
            assert erased_append.result() is False
            assert kept_append.result() is True
    text = files(tmp_path)
    assert removed[0]["text"] not in text and control[0]["text"] in text


def test_failed_contact_does_not_clear_local_content_or_checkpoint(turns, connected, tmp_path):
    removed, _ = capture(turns, connected, tmp_path)
    with connected(tmp_path) as client:
        def offline(_):
            raise ConnectionError("unavailable")
        client.recording_erasures = offline
        with pytest.raises(ConnectionError):
            host_erasure.reconcile(tmp_path, client)
    assert removed[0]["text"] in files(tmp_path)
    with connected(tmp_path) as client:
        assert host_erasure.reconcile(tmp_path, client)
    assert removed[0]["text"] not in files(tmp_path)


def test_legacy_recovery_evidence_loses_input_digest_but_keeps_other_owners(tmp_path):
    from legacy_runtime import old_chat_files

    from membrain.legacy_erasure import REDACTED_DIGEST
    from membrain.local_profile import ensure_profile

    profile = ensure_profile(tmp_path)
    pending = old_chat_files(profile, text="Legacy deleted synthetic text.")
    other = {**pending, "identity": {**pending["identity"], "principal_id": "someone-else"}}
    evidence = tmp_path / "recovery-sessions.jsonl"
    evidence.write_text("\n".join(json.dumps(item) for item in (pending, other)) + "\n")
    host_erasure._redact_legacy(tmp_path, profile.brain_id)
    rows = [json.loads(line) for line in evidence.read_text().splitlines()]
    assert rows[0]["input_fingerprint"] == REDACTED_DIGEST
    assert rows[1] == other
    original = json.loads(next((tmp_path / "sessions").glob("*/pending.json")).read_text())
    assert original["input_fingerprint"] == REDACTED_DIGEST


@pytest.mark.parametrize("turn_id", ["last", "host:opaque-turn-id"])
def test_erased_last_prompt_and_receipt_linked_digest_identity_are_removed(
        turns, connected, tmp_path, turn_id, monkeypatch):
    prompt = "Last synthetic private prompt."
    with connected(tmp_path) as client:
        target = host_recording._target(client)
    monkeypatch.setattr(host_recording, "local_target", lambda *args: target)
    # There is no installed profile in this HTTP fixture, so do not invoke the legacy-installation file reader.
    monkeypatch.setattr(host_erasure, "_redact_legacy", lambda *args: None)
    host.prompt_context(tmp_path, "last-session", prompt, turn_id=turn_id)
    host.finish_turn(tmp_path, "last-session", "Last private reply.", turn_id=turn_id)
    event = next(item for item in turns.service.timeline(turns.principal, turns.brain)["items"]
                 if item["text"] == prompt)
    erase(turns, kind="events", ids=[event["event_id"]])
    with connected(tmp_path) as client:
        host_recording.status(tmp_path, client)
    text = files(tmp_path)
    assert prompt not in text and digest([prompt]) not in text
    assert "Last private reply." not in text
    assert "last_prompt" not in host.session_state(tmp_path, "last-session")


def test_erasure_query_requires_authorization_and_is_bounded(turns, connected, tmp_path):
    import httpx

    from membrain.helpers import uid

    with connected(tmp_path) as client:
        assert client.recording_erasures([])["has_erasures"] is False
        with pytest.raises(httpx.HTTPStatusError) as error:
            client.recording_erasures([{"producer_ref": "p", "source_event_key": "s"}] * 129)
        assert error.value.response.status_code == 422
        client.brain_id = uid()
        with pytest.raises(httpx.HTTPStatusError) as error:
            client.recording_erasures([])
        assert error.value.response.status_code == 404


def test_legacy_completed_digest_without_event_receipt_is_discarded_conservatively(turns, connected, tmp_path):
    prompt = "Old implicit synthetic prompt."
    host.prompt_context(tmp_path, "legacy", prompt)
    host.finish_turn(tmp_path, "legacy", "Old implicit reply.")
    event = next(item for item in turns.service.timeline(turns.principal, turns.brain)["items"]
                 if item["text"] == prompt)
    erase(turns, kind="events", ids=[event["event_id"]])
    with connected(tmp_path) as client:
        host_recording.status(tmp_path, client)
    assert prompt not in files(tmp_path)
    assert digest([prompt]) not in files(tmp_path)
    assert host.session_state(tmp_path, "legacy")["turns_require_staging"]


def test_deleting_only_reply_preserves_user_prompt(turns, connected, tmp_path, monkeypatch):
    with connected(tmp_path) as client:
        target = host_recording._target(client)
    monkeypatch.setattr(host_recording, "local_target", lambda *args: target)
    monkeypatch.setattr(host_erasure, "_redact_legacy", lambda *args: None)
    host.prompt_context(tmp_path, "reply", "Keep the user's message.", turn_id="t")
    records = host.finish_turn(tmp_path, "reply", "Erase just the reply.", turn_id="t")
    for record in records:
        host.spool(tmp_path, record)
    event = next(item for item in turns.service.timeline(turns.principal, turns.brain, roles=("assistant",))["items"]
                 if item["text"] == "Erase just the reply.")
    erase(turns, kind="events", ids=[event["event_id"]])
    with connected(tmp_path) as client:
        host_recording.status(tmp_path, client)
    assert "Erase just the reply." not in files(tmp_path)
    assert "Keep the user's message." in files(tmp_path)
    entry = next(iter(host.session_state(tmp_path, "reply")["turns"].values()))
    assert next(item for item in entry["outcome"]["messages"] if item["role"] == "assistant")["reason"] == "erased"
