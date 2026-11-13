"""Per-message recording receipts from host turn completion (``host.finish_turn(receipt=...)``)."""
import asyncio
import json

import httpx
import pytest
from test_chatbot_adapter import Event, _load_astrbot_plugin
from test_host import Client
from test_host_recording import connected as connected
from test_server_recording import policy
from test_server_recording import turns as turns

from membrain import host, host_queue, host_receipts, host_recording
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.client import MemoryActionError, MemoryClient

QUESTION, ANSWER = "Synthetic receipt question 6031", "Synthetic receipt answer 6031"


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)


def online(monkeypatch, client):
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)
    return client


def queued(directory):
    path = directory / "plugin" / "spool.jsonl"
    return [json.loads(line) for line in host_queue.unacknowledged(path) if line.strip()] if path.exists() else []


def finish(directory, session="s", reply=ANSWER, **options):
    receipt = {}
    records = host.finish_turn(directory, session, reply, receipt=receipt, **{"turn_id": "t", **options})
    assert QUESTION not in json.dumps(receipt) and ANSWER not in json.dumps(receipt)  # References, never text.
    return records, receipt


def states(receipt):
    return [(item["role"], item["state"], item.get("reason")) for item in receipt["messages"]]


def confirmation(accepted=(), duplicates=()):
    return {"outcome": "completed", "result": {"accepted_event_ids": list(accepted),
                                               "duplicate_event_ids": list(duplicates)}}


class Confirming(Client):
    def __init__(self, duplicate=False):
        super().__init__()
        self.duplicate = duplicate

    def observe(self, **record):
        super().observe(**record)
        event = f"event-{len(self.observed)}"
        return confirmation(duplicates=[event]) if self.duplicate else confirmation(accepted=[event])


def test_an_offline_turn_is_queued_not_saved_and_the_record_list_is_unchanged(tmp_path, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    records, receipt = finish(tmp_path)
    assert [record["text"] for record in records] == [QUESTION, ANSWER] == [r["text"] for r in queued(tmp_path)]
    assert receipt["version"] == host_receipts.VERSION and receipt["states"] == {"queued": 2}
    assert states(receipt) == [("user", "queued", "service_unavailable"), ("assistant", "queued", "service_unavailable")]
    assert [item["source"] for item in receipt["messages"]] == [
        {"producer_ref": host.PRODUCER, "source_event_key": "s:t:user", "source_revision": 1},
        {"producer_ref": host.PRODUCER, "source_event_key": "s:t:assistant", "source_revision": 1}]


@pytest.mark.parametrize("duplicate", [False, True])
def test_only_a_confirming_observation_receipt_counts_as_recorded(tmp_path, monkeypatch, duplicate):
    online(monkeypatch, Confirming(duplicate))
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    records, receipt = finish(tmp_path)
    assert len(records) == 2 and queued(tmp_path) == []
    assert [(item["state"], item["event_id"], item["duplicate"]) for item in receipt["messages"]] == [
        ("recorded", "event-1", duplicate), ("recorded", "event-2", duplicate)]


@pytest.mark.parametrize("answer", [
    None,  # Legacy clients and doubles return nothing.
    {"outcome": "completed", "result": {}},
    {"outcome": "completed"},
    confirmation(),
    confirmation(accepted=["a", "b"]),
    confirmation(accepted=["a"], duplicates=["b"]),
    confirmation(accepted=[7]),
    confirmation(accepted=[""]),
    confirmation(accepted=["x" * 257]),
    {"outcome": "completed", "result": {"accepted_event_ids": "a", "duplicate_event_ids": []}},
    {"outcome": "accepted", **{key: value for key, value in confirmation(accepted=["a"]).items() if key != "outcome"}},
])
def test_an_answer_without_one_confirmed_event_is_unknown_not_saved(tmp_path, monkeypatch, answer):
    class Unconfirmed(Client):
        def observe(self, **record):
            super().observe(**record)
            return answer

    online(monkeypatch, Unconfirmed())
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    records, receipt = finish(tmp_path)
    assert len(records) == 2 and queued(tmp_path) == []  # Replay keeps its legacy acknowledgement.
    assert states(receipt) == [("user", "unknown", "confirmation_missing"),
                               ("assistant", "unknown", "confirmation_missing")]


@pytest.mark.parametrize("result", [{}, {"accepted_event_ids": ["e1"], "duplicate_event_ids": []}])
def test_the_real_client_needs_the_observation_receipt_to_claim_storage(tmp_path, monkeypatch, result):
    def transport(request):
        envelope = json.loads(request.content)
        return httpx.Response(200, json={"request_id": envelope["request_id"], "action": envelope["action"],
                                         "outcome": "completed", "result": result})

    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    monkeypatch.setattr(host, "ready_client", lambda *args: MemoryClient(
        "http://synthetic.test", "synthetic-key", "brain", transport=httpx.MockTransport(transport)))
    _, receipt = finish(tmp_path)
    expected = "recorded" if result else "unknown"
    assert [item["state"] for item in receipt["messages"]] == [expected, expected]


def test_a_lost_answer_after_the_first_message_leaves_an_honest_partial_exchange(tmp_path, monkeypatch):
    class LostAnswer(Confirming):
        def observe(self, **record):
            answer = super().observe(**record)
            if len(self.observed) == 2:
                raise httpx.ReadTimeout("synthetic lost answer after commit")
            return answer

    online(monkeypatch, LostAnswer())
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    _, receipt = finish(tmp_path)
    assert states(receipt) == [("user", "recorded", None), ("assistant", "queued", "server_outcome_unknown")]
    assert receipt["states"] == {"recorded": 1, "queued": 1}
    assert [record["text"] for record in queued(tmp_path)] == [ANSWER]  # Kept for idempotent replay.


NOT_OBSERVED = [("user", "queued", "replay_not_observed"), ("assistant", "queued", "replay_not_observed")]


def test_records_behind_a_replay_backlog_are_not_reported_saved(tmp_path, monkeypatch, offline):
    for index in range(16):
        host.spool(tmp_path, host.message_record("old", "user", f"Older synthetic input {index}"))
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    client = online(monkeypatch, Confirming())
    _, receipt = finish(tmp_path)
    assert len(client.observed) == 16  # One bounded foreground batch, all older records.
    assert states(receipt) == NOT_OBSERVED
    assert [record["text"] for record in queued(tmp_path)] == [QUESTION, ANSWER]


def test_a_journal_drained_by_another_replay_worker_reports_admission_not_storage(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    worker, original = Confirming(), host.flush

    def raced(client, directory, **options):
        original(worker, directory)  # The service's replay thread drains the journal first.
        return original(client, directory, **options)

    monkeypatch.setattr(host, "flush", raced)
    client = online(monkeypatch, Confirming())
    _, receipt = finish(tmp_path)
    assert [record["text"] for record in worker.observed] == [QUESTION, ANSWER] and client.observed == []
    # Admission was confirmed and this call saw no confirmation; the receipt is not a queue-membership query.
    assert states(receipt) == NOT_OBSERVED and queued(tmp_path) == []


def test_a_replay_holding_the_journal_lock_leaves_storage_unconfirmed(tmp_path, monkeypatch, offline):
    import threading

    from membrain.local_profile import profile_lock

    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    held, release = threading.Event(), threading.Event()

    def replaying():
        with profile_lock(host.state_directory(tmp_path) / "spool-lock", timeout=5):
            held.set()
            assert release.wait(10)

    thread = threading.Thread(target=replaying)
    thread.start()
    try:
        assert held.wait(5)
        client = online(monkeypatch, Confirming())
        _, receipt = finish(tmp_path)
    finally:
        release.set()
        thread.join(10)
    assert client.observed == [] and states(receipt) == NOT_OBSERVED
    assert [record["text"] for record in queued(tmp_path)] == [QUESTION, ANSWER]


def test_a_failed_checkpoint_write_keeps_confirmations_and_the_replayable_copy(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")

    def fail(*args):
        raise OSError("synthetic cursor write failure")

    client = online(monkeypatch, Confirming())
    with monkeypatch.context() as broken:
        broken.setattr(host_queue, "acknowledge", fail)
        records, receipt = finish(tmp_path)
    assert len(records) == 2 and receipt["states"] == {"recorded": 2}  # The service confirmed both.
    assert [record["text"] for record in queued(tmp_path)] == [QUESTION, ANSWER]  # Not acknowledged locally.
    assert host.flush(client, tmp_path) == 2 and queued(tmp_path) == []  # Idempotent replay clears it.


def test_a_full_queue_is_a_definite_retryable_failure(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    monkeypatch.setattr(host, "SPOOL_BYTES", 1)
    records, receipt = finish(tmp_path)
    assert records == [] and queued(tmp_path) == []
    assert states(receipt) == [("user", "failed", "queue_full"), ("assistant", "failed", "queue_full")]
    assert all(item["retryable"] is True for item in receipt["messages"])
    monkeypatch.setattr(host, "SPOOL_BYTES", 10000)
    assert finish(tmp_path)[1]["states"] == {"queued": 2}


@pytest.mark.parametrize("code,reason", [("recording_paused", "server_paused"), ("recording_stale", "capture_stale")])
def test_a_server_policy_rejection_is_an_exclusion_at_brain_scope(tmp_path, monkeypatch, code, reason):
    class Refusing(Client):
        def observe(self, **record):
            raise MemoryActionError({"error": {"code": code, "retryable": False, "message": "Synthetic refusal."}})

    online(monkeypatch, Refusing())
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    records, receipt = finish(tmp_path)
    assert records == [] and queued(tmp_path) == []
    assert [(item["state"], item["reason"], item["scope"], item["evidence"]) for item in receipt["messages"]] == [
        ("excluded", reason, "brain", "write_rejected")] * 2


def test_a_permanently_rejected_record_is_a_definite_failure(tmp_path, monkeypatch):
    class Invalid(Client):
        def observe(self, **record):
            raise MemoryActionError({"error": {"code": "validation_failed", "retryable": False, "message": "Bad."}})

    online(monkeypatch, Invalid())
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    _, receipt = finish(tmp_path)
    assert [(item["state"], item["reason"], item["code"], item["retryable"]) for item in receipt["messages"]] == [
        ("failed", "rejected", "validation_failed", False)] * 2


def test_a_known_server_pause_at_staging_names_its_current_policy(tmp_path, monkeypatch):
    class Paused(Client):
        def recording_status(self):
            return {"paused": True, "revision": 3}

    online(monkeypatch, Paused())
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    records, receipt = finish(tmp_path)
    assert records == [] and queued(tmp_path) == []
    assert [(item["reason"], item["scope"], item["evidence"]) for item in receipt["messages"]] == [
        ("server_paused", "brain", "current_policy")] * 2


@pytest.mark.parametrize("staged_before_pause", [False, True])
@pytest.mark.parametrize("user,roleplay,pause_user,conversation,scope,applies_to", [
    (None, None, None, True, "conversation", "installation"),  # The default home brain's conversation pause.
    (None, None, None, False, "installation", "installation"),
    ("alice", None, "alice", True, "conversation", "user"),
    ("alice", None, "alice", False, "user", "user"),
    ("alice", "Captain", "alice", True, "conversation", "user"),  # A person's pause covers their role-play.
    ("alice", "Captain", None, True, "conversation", "installation"),
    (None, "Captain", None, True, "conversation", "installation"),
])
def test_a_local_pause_reports_its_scope_and_owner_without_changing_enforcement(
        tmp_path, offline, staged_before_pause, user, roleplay, pause_user, conversation, scope, applies_to):
    def pause():
        host.pause(tmp_path, user_id=pause_user, conversation=conversation, session="s")

    if not staged_before_pause:
        pause()
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t", user_id=user, roleplay=roleplay)
    if staged_before_pause:
        pause()
    records, receipt = finish(tmp_path, user_id=user, roleplay=roleplay)
    assert records == [] and queued(tmp_path) == []
    assert [(item["state"], item["reason"], item["scope"], item["applies_to"]) for item in receipt["messages"]] == [
        ("excluded", "local_pause", scope, applies_to)] * 2


@pytest.mark.parametrize("user,applies_to", [(None, "installation"), ("alice", "user")])
def test_a_pause_requested_in_the_message_is_a_conversation_exclusion(tmp_path, offline, user, applies_to):
    host.prompt_context(tmp_path, "s", "off the record: " + QUESTION, turn_id="t", user_id=user)
    records, receipt = finish(tmp_path, user_id=user)
    assert records == []
    assert [(item["reason"], item["scope"], item["applies_to"]) for item in receipt["messages"]] == [
        ("pause_requested", "conversation", applies_to)] * 2


def test_unmatched_and_repeated_callbacks_are_unknown_not_failed(tmp_path, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    assert finish(tmp_path, turn_id="other")[1]["states"] == {"unknown": 2}
    assert states(finish(tmp_path, turn_id="other")[1])[0] == ("user", "unknown", "turn_not_staged")
    assert finish(tmp_path)[1]["states"] == {"queued": 2}
    assert states(finish(tmp_path)[1]) == [("user", "unknown", "turn_already_finished"),
                                           ("assistant", "unknown", "turn_already_finished")]
    assert len(queued(tmp_path)) == 2  # Repeated completion never queues a second copy.


def test_an_unidentified_callback_never_borrows_another_turns_source(tmp_path, offline):
    host.prompt_context(tmp_path, "s", "First " + QUESTION, turn_id="a")
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="b")
    assert finish(tmp_path, turn_id="a")[1]["states"] == {"queued": 2}
    records, receipt = finish(tmp_path, turn_id=None)
    assert records == [] and len(queued(tmp_path)) == 2
    assert [(item["state"], item["reason"], item["source"]) for item in receipt["messages"]] == [
        ("unknown", "turn_ambiguous", None)] * 2


@pytest.mark.parametrize("paused,stored,expected", [
    ("server", {"reason": "not-a-reason", "scope": "brain"}, ("server_paused", "brain", "unspecified")),
    (True, "corrupt", ("local_pause", "local", None)),
    ("prompt", {"reason": "local_pause", "scope": "conversation", "applies_to": "everyone"},
     ("local_pause", "local", None)),
])
def test_damaged_stored_causes_fall_back_without_breaking_completion(tmp_path, offline, paused, stored, expected):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    state = host.session_state(tmp_path, "s")
    entry = next(iter(state["turns"].values()))
    entry.pop("record")
    entry.update(paused=paused, exclusion=stored)
    host._write_session_state(tmp_path, "s", state)
    records, receipt = finish(tmp_path)
    assert records == [] and queued(tmp_path) == []
    assert [(item["reason"], item["scope"], item.get("evidence")) for item in receipt["messages"]] == [expected] * 2
    state = host.session_state(tmp_path, "s")
    next(iter(state["turns"].values()))["exclusion"] = ["corrupt"]
    host._write_session_state(tmp_path, "s", state)
    assert states(finish(tmp_path)[1])[0] == ("user", "unknown", "turn_already_finished")


def test_a_resumed_turn_without_its_message_fails_definitely(tmp_path, offline):
    host.pause(tmp_path)
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    host.resume(tmp_path, current_turn=True, session="s")
    records, receipt = finish(tmp_path)
    assert records == []
    assert states(receipt) == [("user", "failed", "message_unavailable"),
                               ("assistant", "failed", "message_unavailable")]


def test_a_turn_erased_before_completion_reports_the_erasure(tmp_path, monkeypatch):
    class Erasing(Client):
        def dashboard(self):
            return {"brain": {"scope_generation": 1}}

        def forget(self, ids, **options):
            return {"outcome": "completed"}

    online(monkeypatch, Erasing())
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    host.erase_user(tmp_path, None)
    records, receipt = finish(tmp_path)
    assert records == [] and queued(tmp_path) == []
    assert [(item["state"], item["reason"], item["scope"]) for item in receipt["messages"]] == [
        ("excluded", "erased", "brain")] * 2


def test_a_reply_less_turn_reports_only_its_user_message(tmp_path, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    records, receipt = finish(tmp_path, reply=" ")
    assert [record["role"] for record in records] == ["user"]
    assert states(receipt) == [("user", "queued", "service_unavailable")]


def test_receipt_values_are_validated():
    with pytest.raises(ValueError):
        host_receipts.message("user", None, "recorded", "service_unavailable")
    with pytest.raises(ValueError):
        host_receipts.message("user", None, "excluded", "local_pause")  # An exclusion names its scope.
    with pytest.raises(ValueError):
        host_receipts.message("user", None, "queued", "replay_not_observed", scope="brain")
    with pytest.raises(ValueError):
        host_receipts.message("assistant", None, "unknown", "delivered")
    assert host_receipts.needs_attention(None) and not host_receipts.needs_attention(host_receipts.turn([]))


def test_chat_memory_returns_the_receipt(tmp_path, offline):
    memory, speaker = ChatMemory(tmp_path), Speaker("telegram", "42")
    session = memory.session(speaker)
    memory.context(speaker, QUESTION, session=session, turn_id="t")
    receipt = memory.record(speaker, ANSWER, session=session, turn_id="t")
    assert receipt["states"] == {"queued": 2} and QUESTION not in json.dumps(receipt)
    group = memory.record(Speaker("telegram", "42", "9"), ANSWER, session="g", prompt=QUESTION)
    assert group["states"] == {"queued": 2}  # Groups are recorded by default.
    unrecorded = ChatMemory(tmp_path, record_groups=False).record(Speaker("telegram", "42", "9"), ANSWER,
                                                                 session="g2", prompt=QUESTION)
    assert [(item["reason"], item["scope"]) for item in unrecorded["messages"]] == [
        ("group_recording_disabled", "adapter")] * 2
    anonymous = memory.record(Speaker("telegram", ""), None, session="g3", prompt=QUESTION)
    assert states(anonymous) == [("user", "excluded", "speaker_unidentified")]


def test_chat_memory_reports_no_receipt_through_a_wrapper_that_drops_it(tmp_path, monkeypatch, offline):
    original = host.finish_turn
    monkeypatch.setattr(host, "finish_turn", lambda *args, receipt=None, **kwargs: original(*args, **kwargs))
    memory, speaker = ChatMemory(tmp_path), Speaker("telegram", "42")
    assert memory.record(speaker, ANSWER, session="s", prompt=QUESTION) is None


@pytest.mark.parametrize("state,warned", [("queued", False), ("excluded", False), ("unknown", True), ("failed", True)])
def test_astrbot_warns_only_when_a_message_is_neither_kept_nor_deliberately_excluded(
        tmp_path, monkeypatch, state, warned):
    module, _ = _load_astrbot_plugin(monkeypatch, tmp_path)
    warnings = []
    instance = module.MembrainPlugin.__new__(module.MembrainPlugin)
    instance.logger = type("Logger", (), {"warning": staticmethod(warnings.append)})()
    reason = {"queued": "service_unavailable", "excluded": "local_pause", "unknown": "turn_not_staged",
              "failed": "queue_full"}[state]
    receipt = host_receipts.turn([host_receipts.message("user", None, state, reason,
                                                        scope="user" if state == "excluded" else None)])
    instance.memory = type("Memory", (), {"record": lambda self, *args, **kwargs: receipt})()
    event = Event("1001", QUESTION)
    event.set_extra("membrain", {"session": "s", "turn": "t", "prompt": QUESTION})
    asyncio.run(instance.store_turn(event, type("Response", (), {"role": "assistant", "completion_text": ANSWER})()))
    assert bool(warnings) == warned
    assert all(QUESTION not in warning and ANSWER not in warning for warning in warnings)


# Against the real service ---------------------------------------------------------------------------------------

def timeline(turns):
    return turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"]


def test_real_service_confirmation_names_the_stored_events(turns, connected, tmp_path):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    _, receipt = finish(tmp_path)
    assert receipt["states"] == {"recorded": 2}
    assert {item["event_id"] for item in receipt["messages"]} == {row["event_id"] for row in timeline(turns)}


def test_real_service_commit_with_a_lost_answer_is_queued_then_confirmed_once(
        turns, connected, tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    observe = host_recording.observe

    def lost(client, record):
        observe(client, record)  # Committed by the service ...
        raise httpx.ReadTimeout("synthetic lost answer")  # ... but the answer never arrives.

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host_recording, "observe", lost)
        _, receipt = finish(tmp_path)
    assert states(receipt) == [("user", "queued", "server_outcome_unknown"), ("assistant", "queued", "replay_not_observed")]
    committed = [row["event_id"] for row in timeline(turns)]
    assert len(committed) == 1  # The server already holds the user message the receipt could not confirm.
    outcomes = {}
    with connected(tmp_path) as client:
        assert host.flush(client, tmp_path, outcomes=outcomes) == 2
    # Idempotent replay returns the original answer, naming the event committed before the answer was lost.
    assert [value["state"] for value in outcomes.values()] == ["recorded", "recorded"]
    assert committed[0] in {value["event_id"] for value in outcomes.values()}
    assert {value["event_id"] for value in outcomes.values()} == {row["event_id"] for row in timeline(turns)}
    assert len(timeline(turns)) == 2 and queued(tmp_path) == []


def test_real_service_pause_after_staging_is_reported_from_the_write_rejection(turns, connected, tmp_path):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    policy(turns, True, 0)
    records, receipt = finish(tmp_path)
    assert records == [] and timeline(turns) == [] and queued(tmp_path) == []
    assert [(item["reason"], item["evidence"]) for item in receipt["messages"]] == [
        ("server_paused", "write_rejected")] * 2
