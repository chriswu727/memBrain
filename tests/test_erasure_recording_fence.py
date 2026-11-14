from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import Mock

import pytest
from service_harness import harness as harness
from test_host_recording import connected as connected
from test_host_recording import local_text
from test_recovery_erasure import recovery as recovery
from test_runtime import memory as memory
from test_server_recording import observation
from test_server_recording import turns as turns

from membrain import host
from membrain.helpers import DomainError, uid
from membrain.notes import store_note
from membrain.recording_control import recording_status, set_recording
from membrain.runtime import BrainRuntime, DeliveryReceipt, RuntimeBlocked
from membrain.service import MemoryService

pytestmark = pytest.mark.integration


def test_runtime_revokes_input_if_erasure_wins_after_last_lease_check(memory, monkeypatch):
    runtime = BrainRuntime(memory, Mock(return_value="Public fresh response."),
                           deliver=Mock(return_value=DeliveryReceipt("delivered")))
    original = memory.observe

    def delayed(*args, **kwargs):
        memory.forget([], kind="all_authorized_scope", mode="erase_content", expected_scope_generation=1)
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(memory, "observe", delayed)
        with pytest.raises(RuntimeBlocked, match="context_stale"):
            runtime.respond("Public delayed input.", message_id="old", conversation_id="chat")
    row = runtime.journal.list()[0]
    assert row["stage"] == "failed" and not row["scope_reserved"] and row["input_event_refs"] == []
    runtime.generate.assert_not_called()
    runtime.deliver.assert_not_called()
    assert runtime.respond("Public fresh input.", message_id="new", conversation_id="chat").stage == "completed"


def test_runtime_keeps_delivery_receipt_without_saving_post_erasure_text(memory):
    calls = []

    def deliver(request):
        calls.append(request)
        if len(calls) == 1:
            memory.forget([uid()], kind="events", mode="erase_content", expected_scope_generation=1)
        return DeliveryReceipt("partially_delivered", "Public actual external reply.")

    runtime = BrainRuntime(memory, lambda _: "Public original draft.", deliver=deliver)
    with pytest.raises(RuntimeBlocked, match="context_stale"):
        runtime.respond("Public original input.", message_id="old", conversation_id="chat")
    row = runtime.journal.list()[0]
    assert row["stage"] == "failed" and not row["scope_reserved"]
    assert row["delivery_receipt"]["state"] == "partially_delivered"
    assert row["delivery_receipt"]["disposition"] == "content_withheld"
    assert "recording_changed" in row["delivery_receipt"]["stale_reasons"]
    events = runtime.journal.sources(row["turn_id"])["output_events"]
    assert len(events) == 1 and events[0]["revision"] == 1
    assert events[0]["observed"]["content"]["text"] == "Public original draft."
    assert runtime.respond("Public new input.", message_id="new", conversation_id="chat").stage == "completed"
    assert len(calls) == 2


def erase(turns, *, mode="erase_content", kind="all_authorized_scope", ids=()):
    generation = turns.store.status(turns.principal, turns.brain)["scope_generation"]
    return turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": kind, "ids": list(ids)},
                                  "mode": mode, "expected_scope_generation": generation})


def captured(turns, revision=0):
    request = observation(turns)
    request["payload"]["expected_recording_revision"] = revision
    return request


@pytest.mark.parametrize("mode", ["erase_content", "suppress_recall"])
@pytest.mark.parametrize("kind", ["events", "conversation", "all_authorized_scope"])
def test_erasure_rejects_old_capture_and_accepts_new_input(turns, mode, kind):
    event = turns.observe("Public source to forget.")
    request = captured(turns)
    ids = [event["event_id"]] if kind == "events" else [turns.conversation]
    erase(turns, mode=mode, kind=kind, ids=ids if kind != "all_authorized_scope" else [])
    rejected = turns.service.handle(turns.principal, request)
    assert rejected["error"]["code"] == "recording_stale"
    with turns.database.transaction(turns.principal) as conn:
        assert not conn.execute("SELECT 1 FROM memory_requests WHERE brain_id=%s AND key=%s",
                                (turns.brain, request["payload"]["idempotency_key"])).fetchone()
    restarted = MemoryService(turns.database)
    assert recording_status(restarted, turns.principal, turns.brain) == {"paused": False, "revision": 1}
    assert restarted.handle(turns.principal, captured(turns, 1))["result"]["accepted_event_ids"]


def test_empty_erasure_revokes_captures_without_resuming_or_touching_other_brains(turns):
    other = turns.service.create_brain(turns.principal, "Separate brain")["id"]
    set_recording(turns.service, turns.principal, turns.brain, paused=True, expected_revision=0)
    erase(turns)
    assert recording_status(turns.service, turns.principal, turns.brain) == {"paused": True, "revision": 2}
    assert recording_status(turns.service, turns.principal, other) == {"paused": False, "revision": 0}
    with pytest.raises(DomainError) as stale:
        set_recording(turns.service, turns.principal, turns.brain, paused=False, expected_revision=1)
    assert stale.value.code == "version_conflict"
    set_recording(turns.service, turns.principal, turns.brain, paused=False, expected_revision=2)
    assert turns.service.handle(turns.principal, captured(turns, 0))["error"]["code"] == "recording_stale"


def test_delayed_note_cannot_reintroduce_content_after_empty_erasure(turns):
    request = {"request_id": uid(), "text": "Public delayed note.", "expected_recording_revision": 0}
    erase(turns)
    with pytest.raises(DomainError) as rejected:
        store_note(turns.service, turns.principal, turns.brain, request)
    assert rejected.value.code == "recording_stale"
    assert store_note(turns.service, turns.principal, turns.brain,
                      {**request, "expected_recording_revision": 1})["note_id"]


def test_erasure_retry_does_not_revoke_new_input_twice(turns):
    request = observation(turns)
    request.update(action="forget", payload={"idempotency_key": uid(),
                   "selector": {"kind": "all_authorized_scope", "ids": []},
                   "mode": "erase_content", "expected_scope_generation": 1})
    first = turns.service.handle(turns.principal, request)
    assert first["outcome"] == "completed"
    assert turns.service.handle(turns.principal, captured(turns, 1))["outcome"] == "completed"
    assert turns.service.handle(turns.principal, request)["result"] == first["result"]
    assert recording_status(turns.service, turns.principal, turns.brain)["revision"] == 1


def test_rejected_erasure_does_not_change_capture_authority(turns):
    request = observation(turns)
    request.update(action="forget", payload={"idempotency_key": uid(),
                   "selector": {"kind": "all_authorized_scope", "ids": []},
                   "mode": "erase_content", "expected_scope_generation": 99})
    assert turns.service.handle(turns.principal, request)["error"]["code"] == "version_conflict"
    assert turns.service.handle(turns.principal, captured(turns))["outcome"] == "completed"


@pytest.mark.parametrize("stage", ["started", "prepared", "generating", "delivering"])
def test_erasure_fences_active_content_but_preserves_delivery_facts(turns, stage):
    if stage == "started":
        turns.begin()
        turns.claim()
    elif stage == "delivering":
        turns.generate()
        turns.advance("delivering")
    else:
        turns.prepare()
        if stage == "generating":
            turns.advance("generating")
    erase(turns, kind="events", ids=[uid()])
    if stage != "delivering":
        with pytest.raises(DomainError) as stale:
            turns.call("renew", lease_token=turns.token, expected_revision=turns.row["revision"])
        assert stale.value.code == "context_stale"
    if stage == "delivering":
        turns.call("renew", lease_token=turns.token, expected_revision=turns.row["revision"])
        before = turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))
        row = turns.record_output("Public externally delivered output.", "delivered")
        assert row["stage"] == "failed" and not row["scope_reserved"]
        assert row["delivery_receipt"]["state"] == "delivered"
        assert row["delivery_receipt"]["disposition"] == "content_withheld"
        assert "recording_changed" in row["delivery_receipt"]["stale_reasons"]
        assert turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant")) == before
    elif stage == "generating":
        with pytest.raises(DomainError):
            turns.record_output("Public delayed draft.")
    else:
        assert turns.service.handle(turns.principal, captured(turns))["error"]["code"] == "recording_stale"


@pytest.mark.parametrize("erase_first", [True, False])
def test_erasure_and_delayed_writes_share_the_brain_lock(turns, monkeypatch, erase_first):
    request = captured(turns)
    entered, release = Event(), Event()
    original = turns.service._brain

    def hold(*args, **kwargs):
        brain = original(*args, **kwargs)
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return brain

    monkeypatch.setattr(turns.service, "_brain", hold)
    def deletion():
        return erase(turns)

    def write():
        return turns.service.handle(turns.principal, request)

    first, second = (deletion, write) if erase_first else (write, deletion)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(first)
        assert entered.wait(5)
        second_future = pool.submit(second)
        try:
            with pytest.raises(TimeoutError):
                second_future.result(timeout=0.1)
        finally:
            release.set()
        first_result, second_result = first_future.result(), second_future.result()
    if erase_first:
        assert second_result["error"]["code"] == "recording_stale"
    else:
        assert first_result["result"]["accepted_event_ids"]
    assert turns.service.timeline(turns.principal, turns.brain)["items"] == []


def test_registry_preserves_revocation_floor_across_rollback_and_repeated_replay(recovery):
    harness, authority = recovery
    for revision in range(6):
        set_recording(harness.service, harness.principal, harness.brain,
                      paused=revision % 2 == 0, expected_revision=revision)
    harness.memory.forget([], kind="all_authorized_scope", mode="erase_content", expected_scope_generation=1)
    intent = authority.registry.intent(1)
    assert intent["recording_revision_floor"] == 7
    with harness.database.transaction(harness.principal) as conn:
        conn.execute("DELETE FROM memory_erasure_receipts WHERE brain_id=%s", (harness.brain,))
        conn.execute("UPDATE memory_brains SET recording_revision=0 WHERE id=%s", (harness.brain,))
    authority.reconcile(harness.database, harness.principal)
    assert harness.memory.recording_status() == {"paused": False, "revision": 7}
    authority.reconcile(harness.database, harness.principal)
    assert harness.memory.recording_status()["revision"] == 7
    from membrain.client import MemoryActionError

    with pytest.raises(MemoryActionError) as rejected:
        harness.memory.observe("Public pre-erasure delayed input.", conversation_id="chat", branch_id="main",
                               source_event_key=uid(), expected_recording_revision=6)
    assert rejected.value.code == "recording_stale"
    assert harness.memory.observe("Public new input.", conversation_id="chat", branch_id="main",
                                  source_event_key=uid(), expected_recording_revision=7)["result"]["accepted_event_ids"]


def test_pending_registry_intent_revokes_capture_before_next_write(recovery, monkeypatch):
    harness, authority = recovery
    from membrain.client import MemoryActionError
    from membrain.deletion_registry import RegistryError

    with monkeypatch.context() as patch:
        patch.setattr(authority, "apply", lambda *args, **kwargs: (_ for _ in ()).throw(RegistryError()))
        with pytest.raises(MemoryActionError):
            harness.memory.forget([], kind="all_authorized_scope", mode="erase_content", expected_scope_generation=1)
    with pytest.raises(MemoryActionError) as rejected:
        harness.memory.observe("Public interrupted-erasure input.", conversation_id="chat", branch_id="main",
                               source_event_key=uid(), expected_recording_revision=0)
    assert rejected.value.code == "recording_stale"
    assert harness.memory.recording_status()["revision"] == 1


@pytest.mark.parametrize("offline", [False, True])
def test_host_drops_pre_erasure_callback_and_offline_replay(turns, connected, tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", "Public old draft.", turn_id="old")
    if offline:
        with monkeypatch.context() as patch:
            patch.setattr(host, "ready_client", lambda *args: None)
            queued = host.finish_turn(tmp_path, "s", "Public old reply.", turn_id="old")
        assert len(queued) == 2
    erase(turns)
    if offline:
        with connected(tmp_path) as client:
            assert host.flush(client, tmp_path) == 2
    else:
        assert host.finish_turn(tmp_path, "s", "Public old reply.", turn_id="old") == []
    assert "Public old" not in local_text(tmp_path)
    assert turns.service.timeline(turns.principal, turns.brain)["items"] == []
    host.prompt_context(tmp_path, "s", "Public new draft.", turn_id="new")
    assert len(host.finish_turn(tmp_path, "s", "Public new reply.", turn_id="new")) == 2


def test_real_backup_restore_rejects_pre_erasure_revision_above_checkpoint(tmp_path):
    from test_desktop_recovery_e2e import connection

    from membrain import desktop
    from membrain.client import MemoryActionError
    from membrain.desktop_backup import backup
    from membrain.desktop_restore import activate, restore
    from membrain.local_profile import ensure_profile, load_profile
    from membrain.recovery_profile import authority_for

    source = ensure_profile(tmp_path / "source", database_engine="embedded")
    target = tmp_path / "restored"
    restored = None
    try:
        desktop._prepare_database(source)
        with connection(source) as (client, _, _):
            client.observe("Public checkpoint source.", conversation_id="chat", branch_id="main",
                           source_event_key="checkpoint", expected_recording_revision=0)
        archive = tmp_path / "backup"
        saved = backup(source.directory, output=archive, request_id="erasure-fence")
        with connection(source) as (client, _, _):
            for revision in range(6):
                client.set_recording(paused=revision % 2 == 0, expected_revision=revision)
            client.forget([], kind="all_authorized_scope", mode="erase_content", expected_scope_generation=1)
            assert client.recording_status()["revision"] == 7
        authority = authority_for(source)
        result = restore(backup_path=archive, directory=target, registry_path=authority.registry.directory,
                         request_id="erasure-fence-restore")
        restored = load_profile(target)
        head = authority.registry.head()
        activate(target, recovery_epoch=result["recovery_epoch"], backup_id=saved["backup_id"],
                 checkpoint_at=result["checkpoint"]["checkpoint_at"], retire_installation_id=source.installation_id,
                 expected_sequence=head["sequence"], expected_head_hash=head["head_hash"],
                 acknowledge_host_reconciliation=True)
        with connection(restored, recovery_epoch=result["recovery_epoch"]) as (client, _, _):
            assert client.recording_status()["revision"] == 7
            with pytest.raises(MemoryActionError) as rejected:
                client.observe("Public delayed payload.", conversation_id="chat", branch_id="main",
                               source_event_key="delayed", expected_recording_revision=6)
            assert rejected.value.code == "recording_stale"
            assert client.observe("Public fresh payload.", conversation_id="chat", branch_id="main",
                                  source_event_key="fresh", expected_recording_revision=7)["result"]["accepted_event_ids"]
    finally:
        if restored is None and (target / "profile.json").exists():
            restored = load_profile(target)
        for profile in (restored, source):
            if profile is not None:
                desktop.stop(profile.directory)


def test_note_replacement_preserves_capture_but_explicit_suppression_revokes_it(turns):
    first = store_note(turns.service, turns.principal, turns.brain,
                       {"request_id": uid(), "text": "Public old note.", "expected_recording_revision": 0})
    second = store_note(turns.service, turns.principal, turns.brain,
                        {"request_id": uid(), "text": "Public replacement note.", "replaces": [first["note_id"]],
                         "expected_recording_revision": 0})
    assert recording_status(turns.service, turns.principal, turns.brain)["revision"] == 0
    assert turns.service.handle(turns.principal, captured(turns))["outcome"] == "completed"
    erase(turns, mode="suppress_recall", kind="events", ids=[second["note_id"]])
    assert turns.service.handle(turns.principal, captured(turns))["error"]["code"] == "recording_stale"


def test_replacement_intent_replays_without_revoking_recording(recovery):
    harness, authority = recovery
    original = harness.memory.write_note("Public old replacement note.")["note_id"]
    harness.memory.write_note("Public updated replacement note.", replaces=[original], expected_recording_revision=0)
    intent = authority.registry.intent(1)
    assert intent["revoke_recording"] is False and "recording_revision_floor" not in intent
    assert harness.memory.recording_status()["revision"] == 0
    with harness.database.transaction(harness.principal) as conn:
        conn.execute("DELETE FROM memory_erasure_receipts WHERE brain_id=%s", (harness.brain,))
        conn.execute("UPDATE memory_events SET suppressed=false WHERE id=%s", (original,))
    authority.reconcile(harness.database, harness.principal)
    authority.reconcile(harness.database, harness.principal)
    assert harness.memory.recording_status()["revision"] == 0
    with harness.database.transaction(harness.principal) as conn:
        assert conn.execute("SELECT suppressed FROM memory_events WHERE id=%s", (original,)).fetchone()["suppressed"]
    generation = harness.memory.dashboard()["brain"]["scope_generation"]
    harness.memory.forget([original], kind="events", mode="suppress_recall", expected_scope_generation=generation)
    assert harness.memory.recording_status()["revision"] == 1
    assert authority.registry.intent(2)["recording_revision_floor"] == 1
