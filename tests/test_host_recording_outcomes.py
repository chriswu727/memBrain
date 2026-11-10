"""Queryable recording outcomes for host exchanges (``membrain.host_outcomes``): hooks, the proxy and Hermes."""
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from test_host import Client
from test_host_recording import connected as connected
from test_host_recording_receipts import ANSWER, QUESTION, Confirming, confirmation, online, queued
from test_host_recording_receipts import offline as offline
from test_proxy import Upstream
from test_server_recording import policy
from test_server_recording import turns as turns

from membrain import (
    cli,
    desktop,
    embedded_database,
    host,
    host_outcomes,
    host_queue,
    host_recording,
    host_turns,
    plugin,
)
from membrain.adapters import hermes
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.client import MemoryActionError, MemoryClient
from membrain.local_profile import ensure_profile
from membrain.proxy import EXCHANGE_HEADER, create_proxy_app


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def look(directory, turn="t", session="s", **options):
    result = host_outcomes.lookup(directory, session=session, turn_id=turn, **options)
    assert QUESTION not in json.dumps(result) and ANSWER not in json.dumps(result)  # References, never text.
    return result


def states(result):
    return [(item["role"], item["state"], item.get("reason"), item["observed_by"]) for item in result["messages"]]


def exchange(directory, turn="t", session="s", reply=ANSWER, **options):
    host.prompt_context(directory, session, QUESTION, turn_id=turn, **options)
    return host.finish_turn(directory, session, reply, turn_id=turn, **options)


def ledger_text(directory):
    return "".join(path.read_text() for path in sorted((directory / "plugin" / "sessions").glob("*.json")))


def kept(directory):
    """Everything the outcome bookkeeping itself stores (the ledger also keeps the turn state it always kept)."""
    stored = []
    for path in sorted((directory / "plugin" / "sessions").glob("*.json")):
        state = json.loads(path.read_text())
        stored.append([state.get("callbacks"), [entry.get("outcome") for entry in state.get("turns", {}).values()]])
    return json.dumps(stored)


def local_files(directory):
    return {str(path.relative_to(directory)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in sorted(directory.rglob("*")) if path.is_file() and path.name != ".profile.lock"}


def log_text(directory):
    path = directory / "plugin" / "hooks.log"
    return path.read_text() if path.exists() else ""


class Erasing(Confirming):
    def dashboard(self):
        return {"brain": {"scope_generation": 1}}

    def forget(self, ids, **options):
        return {"outcome": "completed"}

    def ensure_brain(self, *args):
        pass


def refusal(code):
    return MemoryActionError({"error": {"code": code, "retryable": False, "message": "Synthetic refusal 7719."}})


# Admission versus confirmation ---------------------------------------------------------------------------------

def test_an_offline_exchange_stays_queued_until_a_later_replay_confirms_it(tmp_path, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    staged = look(tmp_path)
    assert (staged["status"], staged["completed"]) == ("awaiting_completion", False) and "messages" not in staged
    exchange(tmp_path)
    before = look(tmp_path, now=time.time() + 90)
    assert (before["status"], before["completed"], before["states"]) == ("observed", True, {"queued": 2})
    assert states(before) == [("user", "queued", "service_unavailable", "callback"),
                              ("assistant", "queued", "service_unavailable", "callback")]
    # An old observation is reported with its age, not as a current fact.
    assert before["basis"] == "last_observation" and 89 < before["age_seconds"] < 95
    assert [item["source"]["source_event_key"] for item in before["messages"]] == ["s:t:user", "s:t:assistant"]
    assert host_outcomes.lookup(tmp_path, exchange=before["exchange"])["messages"] == before["messages"]
    assert before["exchange"] == host_outcomes.exchange_id("s", "t")
    # Another process replays the journal later: the same lookup now reports what the service answered.
    assert host.flush(Confirming(), tmp_path) == 2
    after = look(tmp_path)
    assert states(after) == [("user", "recorded", None, "replay"), ("assistant", "recorded", None, "replay")]
    assert [(item["event_id"], item["duplicate"]) for item in after["messages"]] == [("event-1", False), ("event-2", False)]
    assert after["observed_at"] >= before["observed_at"] and QUESTION not in kept(tmp_path) and ANSWER not in kept(tmp_path)


def test_a_lookup_only_reads_local_files(tmp_path, offline, monkeypatch):
    exchange(tmp_path)
    host.prompt_context(tmp_path, "s", QUESTION + " again", turn_id="t2")
    monkeypatch.setattr(host, "ready_client", lambda *args: pytest.fail("A lookup must not open a client."))
    monkeypatch.setattr(host, "flush", lambda *args, **options: pytest.fail("A lookup must not replay."))
    before = local_files(tmp_path)
    assert look(tmp_path)["states"] == {"queued": 2} and look(tmp_path, "t2")["status"] == "awaiting_completion"
    assert len(host_outcomes.recent(tmp_path)["exchanges"]) == 2
    assert look(tmp_path, "never")["status"] == "not_found"
    assert local_files(tmp_path) == before and len(queued(tmp_path)) == 2  # Nothing written, nothing drained.


def test_a_bounded_replay_leaves_an_honest_partial_exchange(tmp_path, offline):
    exchange(tmp_path)
    assert host.flush(Confirming(), tmp_path, max_records=1) == 1
    partial = look(tmp_path)
    assert partial["states"] == {"recorded": 1, "queued": 1}
    assert states(partial) == [("user", "recorded", None, "replay"),
                               ("assistant", "queued", "service_unavailable", "callback")]


def test_a_lost_answer_is_unconfirmed_until_an_idempotent_replay_names_the_event(tmp_path, monkeypatch):
    class Interrupted(Client):
        def observe(self, **record):
            super().observe(**record)  # The service may have committed it ...
            raise httpx.ReadTimeout("synthetic lost answer 7719")  # ... but its answer never arrived.

    online(monkeypatch, Interrupted())
    exchange(tmp_path)
    lost = look(tmp_path)
    assert states(lost) == [("user", "queued", "server_outcome_unknown", "replay"),
                            ("assistant", "queued", "replay_not_observed", "callback")]
    assert len(queued(tmp_path)) == 2 and "7719" not in kept(tmp_path) + log_text(tmp_path)
    assert host.flush(Confirming(duplicate=True), tmp_path) == 2
    assert [(item["state"], item["duplicate"]) for item in look(tmp_path)["messages"]] == [("recorded", True)] * 2


@pytest.mark.parametrize("answer", [None, {"outcome": "completed", "result": {}}, confirmation(accepted=["a", "b"])])
def test_a_later_answer_without_one_confirmed_event_is_unknown_not_saved(tmp_path, offline, answer):
    class Unconfirmed(Client):
        def observe(self, **record):
            return answer

    exchange(tmp_path)
    assert host.flush(Unconfirmed(), tmp_path) == 2
    assert states(look(tmp_path)) == [("user", "unknown", "confirmation_missing", "replay"),
                                      ("assistant", "unknown", "confirmation_missing", "replay")]


def test_a_later_permanent_rejection_is_a_definite_failure_without_the_error_text(tmp_path, offline):
    class Invalid(Client):
        def observe(self, **record):
            raise refusal("validation_failed")

    exchange(tmp_path)
    assert look(tmp_path)["states"] == {"queued": 2}
    assert host.flush(Invalid(), tmp_path) == 2 and queued(tmp_path) == []
    failed = look(tmp_path)
    assert [(item["state"], item["reason"], item["code"], item["retryable"], item["observed_by"])
            for item in failed["messages"]] == [("failed", "rejected", "validation_failed", False, "replay")] * 2
    assert host_outcomes.needs_attention(failed)
    assert "Synthetic refusal" not in kept(tmp_path) + log_text(tmp_path) + json.dumps(failed)


@pytest.mark.parametrize("code,reason", [("recording_paused", "server_paused"), ("recording_stale", "capture_stale")])
def test_a_later_policy_rejection_is_an_exclusion_at_brain_scope(tmp_path, offline, code, reason):
    class Refusing(Client):
        def observe(self, **record):
            raise refusal(code)

    exchange(tmp_path)
    host.flush(Refusing(), tmp_path)
    excluded = look(tmp_path)
    assert [(item["state"], item["reason"], item["scope"], item["evidence"]) for item in excluded["messages"]] == [
        ("excluded", reason, "brain", "write_rejected")] * 2
    assert not host_outcomes.needs_attention(excluded) and queued(tmp_path) == []


def test_a_confirmed_message_is_never_downgraded_by_a_later_attempt(tmp_path, monkeypatch, offline):
    exchange(tmp_path)

    def fail(*args):
        raise OSError("synthetic cursor write failure")

    with monkeypatch.context() as broken:
        broken.setattr(host_queue, "acknowledge", fail)
        with pytest.raises(OSError):
            host.flush(Confirming(), tmp_path)
    assert look(tmp_path)["states"] == {"recorded": 2} and len(queued(tmp_path)) == 2  # Seen, not checkpointed.

    class Interrupted(Client):
        def observe(self, **record):
            raise httpx.ReadTimeout("synthetic")

    with pytest.raises(httpx.ReadTimeout):
        host.flush(Interrupted(), tmp_path)

    class Refusing(Client):
        def observe(self, **record):
            raise refusal("recording_stale")

    host.flush(Refusing(), tmp_path)
    kept = look(tmp_path)
    assert kept["states"] == {"recorded": 2} and [item["event_id"] for item in kept["messages"]] == ["event-1", "event-2"]


def test_an_abandoned_turn_reports_only_the_message_recovery_queued(tmp_path, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    state = host.session_state(tmp_path, "s")
    next(iter(state["turns"].values()))["started"] = 0
    host._write_session_state(tmp_path, "s", state)
    host._finish_abandoned(tmp_path, None)
    recovered = look(tmp_path)
    assert recovered["completed"] is True
    assert states(recovered) == [("user", "queued", "service_unavailable", "recovery")]
    host.flush(Confirming(), tmp_path)
    assert states(look(tmp_path)) == [("user", "recorded", None, "replay")]


# Unmatched, repeated and ambiguous callbacks -------------------------------------------------------------------

def test_a_repeated_callback_never_replaces_or_upgrades_the_first_outcome(tmp_path, offline):
    exchange(tmp_path)
    receipt = {}
    assert host.finish_turn(tmp_path, "s", ANSWER, turn_id="t", receipt=receipt) == []
    assert receipt["states"] == {"unknown": 2}
    repeated = look(tmp_path)
    assert repeated["states"] == {"queued": 2} and repeated["completed"] is True
    assert [[(item["state"], item["reason"]) for item in callback["messages"]]
            for callback in repeated["unsettled_callbacks"]] == [[("unknown", "turn_already_finished")] * 2]
    host.flush(Confirming(), tmp_path)
    host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    confirmed = look(tmp_path)
    assert confirmed["states"] == {"recorded": 2} and len(confirmed["unsettled_callbacks"]) == 2
    assert len(queued(tmp_path)) == 0  # The repeats queued nothing.


def test_an_unmatched_callback_is_an_unknown_outcome_not_a_success(tmp_path, offline):
    exchange(tmp_path)
    assert host.finish_turn(tmp_path, "s", ANSWER, turn_id="never-staged") == []
    unmatched = look(tmp_path, "never-staged")
    assert (unmatched["status"], unmatched["completed"], unmatched["states"]) == ("observed", False, {"unknown": 2})
    assert states(unmatched) == [("user", "unknown", "turn_not_staged", "callback"),
                                 ("assistant", "unknown", "turn_not_staged", "callback")]
    assert host_outcomes.needs_attention(unmatched) and len(queued(tmp_path)) == 2
    host.flush(Confirming(), tmp_path)
    assert look(tmp_path, "never-staged")["states"] == {"unknown": 2}  # Replay of other turns confirms nothing here.


def test_an_ambiguous_callback_is_listed_without_borrowing_a_turn(tmp_path, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="a")
    host.prompt_context(tmp_path, "s", QUESTION + " second", turn_id="b")
    assert host.finish_turn(tmp_path, "s", ANSWER) == []
    listed = host_outcomes.recent(tmp_path, session="s")["exchanges"]
    assert sorted(item["status"] for item in listed) == ["awaiting_completion", "awaiting_completion", "observed"]
    unidentified = next(item for item in listed if item["status"] == "observed")
    assert unidentified["exchange"] is None and unidentified["states"] == {"unknown": 2}
    assert [(item["reason"], item["source"]) for item in unidentified["messages"]] == [("turn_ambiguous", None)] * 2
    assert look(tmp_path, "a")["status"] == look(tmp_path, "b")["status"] == "awaiting_completion"


# Policy exclusions ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("user,options,scope,applies_to", [
    (None, {}, "installation", "installation"), (None, {"conversation": True}, "conversation", "installation"),
    ("qq:7", {"conversation": True}, "conversation", "user")])
def test_a_local_pause_is_reported_at_its_own_scope_never_the_brain(tmp_path, offline, user, options, scope, applies_to):
    host.pause(tmp_path, user_id=user, **({"session": "s", **options} if options else {}))
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t", user_id=user)
    staged = look(tmp_path, user_id=user)
    assert staged["status"] == "awaiting_completion"
    assert (staged["staged_exclusion"]["reason"], staged["staged_exclusion"]["scope"]) == ("local_pause", scope)
    host.finish_turn(tmp_path, "s", ANSWER, turn_id="t", user_id=user)
    excluded = look(tmp_path, user_id=user)
    assert [(item["state"], item["reason"], item["scope"], item["applies_to"]) for item in excluded["messages"]] == [
        ("excluded", "local_pause", scope, applies_to)] * 2
    assert queued(tmp_path) == [] and QUESTION not in kept(tmp_path)


def test_a_pause_requested_in_the_message_is_a_conversation_exclusion(tmp_path, offline):
    host.prompt_context(tmp_path, "s", "Off the record: " + QUESTION, turn_id="t")
    host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    assert [(item["state"], item["reason"], item["scope"]) for item in look(tmp_path)["messages"]] == [
        ("excluded", "pause_requested", "conversation")] * 2


# Admission failure and bookkeeping failure ---------------------------------------------------------------------

def test_a_full_queue_is_a_retryable_failure_until_the_retry_is_admitted(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    monkeypatch.setattr(host, "SPOOL_BYTES", 1)
    assert host.finish_turn(tmp_path, "s", ANSWER, turn_id="t") == []
    refused = look(tmp_path)
    assert (refused["status"], refused["completed"]) == ("observed", False)  # The stage is kept for a retry.
    assert [(item["state"], item["reason"], item["retryable"]) for item in refused["messages"]] == [
        ("failed", "queue_full", True)] * 2
    monkeypatch.setattr(host, "SPOOL_BYTES", 10000)
    assert len(host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")) == 2
    retried = look(tmp_path)
    assert (retried["completed"], retried["states"]) == (True, {"queued": 2}) and "unsettled_callbacks" not in retried


def test_a_whole_turn_callback_refused_by_a_full_queue_is_still_listed(tmp_path, monkeypatch, offline):
    monkeypatch.setattr(host, "SPOOL_BYTES", 1)
    assert host.finish_turn(tmp_path, "h", ANSWER, prompt=QUESTION, allow_unstaged=True, producer="membrain-hermes") == []
    (listed,) = host_outcomes.recent(tmp_path, session="h", producer="membrain-hermes")["exchanges"]
    assert (listed["completed"], listed["states"]) == (False, {"failed": 2})
    assert {item["reason"] for item in listed["messages"]} == {"queue_full"} and QUESTION not in kept(tmp_path)
    assert host_outcomes.lookup(tmp_path, exchange=listed["exchange"])["states"] == {"failed": 2}


def break_journal(monkeypatch, directory, *, rollback: bool):
    """The journal's first sync fails; with ``rollback=False`` removing the partial append fails too."""
    path = directory / "plugin" / "spool.jsonl"
    sync, opening, failed = os.fsync, os.fdopen, []

    def journal(descriptor):
        try:
            return os.path.samestat(os.fstat(descriptor), os.stat(path))
        except OSError:
            return False

    def failing_sync(descriptor):
        if journal(descriptor) and not failed:
            failed.append(descriptor)
            raise OSError("synthetic journal sync failure 7719")
        return sync(descriptor)

    class NoRollback:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *arguments):
            return self.stream.__exit__(*arguments)

        def truncate(self, *arguments):
            raise OSError("synthetic rollback failure 7719")

    def wrapped(descriptor, *arguments, **options):
        stream = opening(descriptor, *arguments, **options)
        return stream if rollback or not journal(descriptor) else NoRollback(stream)

    monkeypatch.setattr(os, "fsync", failing_sync)
    monkeypatch.setattr(os, "fdopen", wrapped)


def test_a_rolled_back_journal_write_failure_raises_and_is_a_definite_retryable_failure(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    with monkeypatch.context() as broken:
        break_journal(broken, tmp_path, rollback=True)
        with pytest.raises(OSError):
            host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    failed = look(tmp_path)
    assert (failed["completed"], [(item["state"], item["reason"], item["retryable"]) for item in failed["messages"]]) == (
        False, [("failed", "queue_write_failed", True)] * 2)
    assert queued(tmp_path) == [] and "7719" not in kept(tmp_path) + log_text(tmp_path)
    assert host.flush(Confirming(), tmp_path) == 0 and look(tmp_path)["states"] == {"failed": 2}
    assert len(host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")) == 2 and look(tmp_path)["states"] == {"queued": 2}


def test_a_journal_write_that_cannot_be_rolled_back_is_unknown_until_a_replay_observes_it(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    with monkeypatch.context() as broken:
        break_journal(broken, tmp_path, rollback=False)
        with pytest.raises(host.JournalAdmissionUncertain):
            host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    assert len(queued(tmp_path)) == 2  # The append survived its failed sync and its failed removal.
    uncertain = look(tmp_path)
    assert (uncertain["completed"], uncertain["states"]) == (False, {"unknown": 2})
    assert [(item["reason"], item.get("retryable")) for item in uncertain["messages"]] == [("admission_unconfirmed", None)] * 2
    assert host_outcomes.needs_attention(uncertain) and "7719" not in kept(tmp_path) + log_text(tmp_path)
    # A replay stores what was left in the journal; the outcome says so, and the failed callback stays unfinished.
    assert host.flush(Confirming(), tmp_path) == 2
    stored = look(tmp_path)
    assert (stored["completed"], stored["states"]) == (False, {"recorded": 2})
    assert {item["observed_by"] for item in stored["messages"]} == {"replay"}
    assert not next(iter(host.session_state(tmp_path, "s")["turns"].values())).get("done")
    # The host's retry completes the turn; the confirmation is kept while the second copy awaits its replay.
    assert len(host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")) == 2
    retried = look(tmp_path)
    assert (retried["completed"], retried["states"]) == (True, {"recorded": 2})
    assert host.flush(Confirming(duplicate=True), tmp_path) == 2
    assert [item["event_id"] for item in look(tmp_path)["messages"]] == ["event-1", "event-2"]


def test_an_unstaged_turn_with_an_uncertain_journal_write_is_refined_the_same_way(tmp_path, monkeypatch, offline):
    with monkeypatch.context() as broken:
        break_journal(broken, tmp_path, rollback=False)
        with pytest.raises(OSError):
            host.finish_turn(tmp_path, "h", ANSWER, prompt=QUESTION, allow_unstaged=True, producer="membrain-hermes")
    (listed,) = host_outcomes.recent(tmp_path, session="h")["exchanges"]
    assert (listed["completed"], listed["states"]) == (False, {"unknown": 2})
    assert host.flush(Confirming(), tmp_path) == 2
    assert host_outcomes.lookup(tmp_path, exchange=listed["exchange"])["states"] == {"recorded": 2}


def test_a_definite_refusal_is_not_refined_by_an_unrelated_replay_of_the_same_identity(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    monkeypatch.setattr(host, "SPOOL_BYTES", 1)
    host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    reference = host_outcomes.reference({"role": "user", "conversation_id": "s", "producer_ref": host.PRODUCER,
                                         "source_event_key": "s:t:user"})
    message = host._observed_message("user", None, {"state": "recorded", "event_id": "stray", "duplicate": False})
    assert host_outcomes.observe(tmp_path, [(reference, message)], lambda owner: None) == 0
    assert look(tmp_path)["states"] == {"failed": 2}


def test_a_failed_outcome_write_neither_breaks_the_turn_nor_claims_a_result(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")

    def fail(*args, **options):
        raise RuntimeError("synthetic outcome failure 7719 " + QUESTION)

    receipt = {}
    with monkeypatch.context() as broken:
        broken.setattr(host_outcomes, "settle", fail)
        records = host.finish_turn(tmp_path, "s", ANSWER, turn_id="t", receipt=receipt)
    assert len(records) == 2 and receipt["states"] == {"queued": 2} and len(queued(tmp_path)) == 2
    missing = look(tmp_path)
    assert (missing["status"], missing["reason"]) == ("unavailable", "outcome_not_retained") and "messages" not in missing
    assert "recording outcome not kept: RuntimeError" in log_text(tmp_path) and "7719" not in log_text(tmp_path)
    assert host.flush(Confirming(), tmp_path) == 2  # Replay has no outcome to update and must not invent one.
    assert look(tmp_path)["status"] == "unavailable"


def test_a_failed_outcome_update_keeps_replay_acknowledged_and_the_last_observation(tmp_path, monkeypatch, offline):
    exchange(tmp_path)

    def fail(*args, **options):
        raise OSError("synthetic ledger failure 7719")

    client = Confirming()
    with monkeypatch.context() as broken:
        broken.setattr(host, "_write_session_marker", fail)
        assert host.flush(client, tmp_path) == 2
    assert queued(tmp_path) == [] and len(client.observed) == 2  # Stored and acknowledged all the same.
    stale = look(tmp_path, now=time.time() + 3600)
    assert stale["states"] == {"queued": 2} and stale["age_seconds"] > 3599  # Still the admission, with its age.
    assert "recording outcome not updated: OSError" in log_text(tmp_path) and "7719" not in log_text(tmp_path)


def test_an_unreadable_store_is_reported_as_unavailable_not_missing(tmp_path, offline):
    exchange(tmp_path)
    (marker,) = (tmp_path / "plugin" / "sessions").glob("*.json")
    state = json.loads(marker.read_text())
    next(iter(state["turns"].values()))["outcome"]["messages"][0]["state"] = "saved"
    marker.write_text(json.dumps(state))
    damaged = look(tmp_path)
    assert (damaged["status"], damaged["reason"]) == ("unavailable", "outcome_unreadable") and "messages" not in damaged
    marker.write_text("{not json")
    assert look(tmp_path) == {"version": host_outcomes.VERSION, "status": "unavailable", "reason": "store_unreadable"}
    listing = host_outcomes.recent(tmp_path)
    assert listing["exchanges"] == [] and listing["unreadable_sessions"] == 1


# Scope: owner, producer, account and brain ---------------------------------------------------------------------

def test_another_owner_or_producer_cannot_find_an_exchange(tmp_path, offline):
    exchange(tmp_path, user_id="qq:1")
    exchange(tmp_path, session="r", user_id="qq:1", roleplay="Captain")
    mine = look(tmp_path, user_id="qq:1")
    absent = look(tmp_path, "never", user_id="qq:1")
    assert mine["states"] == {"queued": 2} and absent["status"] == "not_found"
    for other in ({}, {"user_id": "qq:2"}, {"user_id": "qq:1", "roleplay": "Captain"},
                  {"user_id": "qq:1", "producer": "membrain-codex"}):
        assert look(tmp_path, **other) == absent  # Indistinguishable from an exchange that never existed.
        by_handle = host_outcomes.lookup(tmp_path, exchange=mine["exchange"], **other)
        # A handle already names its producer; the owner is still required.
        assert by_handle["messages"] == mine["messages"] if "producer" in other else by_handle == absent
    assert host_outcomes.recent(tmp_path, user_id="qq:2")["exchanges"] == []
    assert host_outcomes.recent(tmp_path)["exchanges"] == []
    assert look(tmp_path, session="r", user_id="qq:1", roleplay="Captain")["states"] == {"queued": 2}
    assert look(tmp_path, session="r", user_id="qq:1")["status"] == "not_found"
    for malformed in ("", "x.y", mine["exchange"].upper(), mine["exchange"] + "0", "../" + mine["exchange"]):
        with pytest.raises(ValueError):
            host_outcomes.lookup(tmp_path, exchange=malformed, user_id="qq:1")
    with pytest.raises(ValueError):
        host_outcomes.lookup(tmp_path, session="s", user_id="qq:1")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _rewrite_profile(directory, **changes):
    path = directory / "profile.json"
    document = json.loads(path.read_text())
    previous = {key: document[key] for key in changes}
    path.write_text(json.dumps({**document, **changes}))
    return previous


@pytest.mark.parametrize("change", [lambda: {"api_key": "am_" + secrets.token_urlsafe(36)},
                                    lambda: {"brain_id": str(uuid.uuid4())}])
def test_an_account_or_brain_switch_does_not_expose_or_rewrite_earlier_outcomes(tmp_path, offline, change):
    ensure_profile(tmp_path, database_engine="embedded", api_port=_free_port(), database_port=_free_port())
    exchange(tmp_path)
    host.flush(Confirming(), tmp_path, max_records=1)
    original = look(tmp_path)
    assert original["states"] == {"recorded": 1, "queued": 1}
    absent = look(tmp_path, "never")
    kept = ledger_text(tmp_path)
    previous = _rewrite_profile(tmp_path, **change())
    assert look(tmp_path) == absent and host_outcomes.lookup(tmp_path, exchange=original["exchange"]) == absent
    assert host_outcomes.recent(tmp_path)["exchanges"] == []
    # A replay under the new account reaches the queued reply; the earlier owner's outcome is left as it was.
    assert host.flush(Confirming(), tmp_path) == 1 and ledger_text(tmp_path) == kept
    _rewrite_profile(tmp_path, **previous)
    restored = look(tmp_path)
    assert restored["messages"] == original["messages"]


def test_the_local_target_is_the_target_a_client_of_the_profile_stamps_on_captures(tmp_path):
    profile = ensure_profile(tmp_path, database_engine="embedded", api_port=_free_port(), database_port=_free_port())
    with MemoryClient(profile.base_url, profile.api_key, profile.brain_id, trust_env=False) as client:
        assert host_recording.local_target(tmp_path) == host_recording._target(client)
        client.brain_id = host.user_brain_id("qq:1")
        assert host_recording.local_target(tmp_path, "qq:1") == host_recording._target(client)
    assert host_recording.local_target(tmp_path) != host_recording.local_target(tmp_path, "qq:1")
    assert host_recording.local_target(tmp_path / "absent") is None
    captured = {"revision": 0, "target": "captured-under-this-target"}
    assert host_recording.outcome_target(tmp_path, None, captured) == "captured-under-this-target"
    assert host_recording.outcome_target(tmp_path, None, {"revision": 0, "target": None}) == host_recording.local_target(tmp_path)


def _bind_recovery_epoch(directory, epoch):
    profile = ensure_profile(directory, database_engine="embedded")
    path = directory / "recovery.json"
    path.write_text(json.dumps({"version": 1, "registry_path": str(directory.parent / "registry"),
                                "registry_id": str(uuid.uuid4()), "installation_id": profile.installation_id,
                                "state": "active", "recovery_epoch": epoch}))
    path.chmod(0o600)


def test_a_recovery_epoch_switch_hides_earlier_outcomes(tmp_path, offline):
    directory = tmp_path / "brain"
    ensure_profile(directory, database_engine="embedded", api_port=_free_port(), database_port=_free_port())
    _bind_recovery_epoch(directory, str(uuid.uuid4()))
    exchange(directory)
    assert look(directory)["states"] == {"queued": 2}
    _bind_recovery_epoch(directory, str(uuid.uuid4()))
    assert look(directory)["status"] == "not_found" and host_outcomes.recent(directory)["exchanges"] == []


def test_a_target_switch_hides_erased_awaiting_and_unretained_exchanges_too(tmp_path, monkeypatch):
    ensure_profile(tmp_path, database_engine="embedded", api_port=_free_port(), database_port=_free_port())
    client = online(monkeypatch, Erasing())
    exchange(tmp_path, "done")
    exchange(tmp_path, "erased", user_id="qq:1")
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="staged")
    with monkeypatch.context() as broken:
        broken.setattr(host_outcomes, "settle", lambda *args, **options: 1 / 0)
        exchange(tmp_path, "unretained")
    host.erase_user(tmp_path, "qq:1")
    assert client.observed and look(tmp_path, "done")["states"] == {"recorded": 2}
    assert look(tmp_path, "erased", user_id="qq:1")["status"] == "erased"  # Its own account still learns of it.
    assert look(tmp_path, "staged")["status"] == "awaiting_completion"
    assert look(tmp_path, "unretained")["reason"] == "outcome_not_retained"
    absent = look(tmp_path, "never")
    _rewrite_profile(tmp_path, api_key="am_" + secrets.token_urlsafe(36))
    for turn, user in (("done", None), ("erased", "qq:1"), ("staged", None), ("unretained", None)):
        assert look(tmp_path, turn, user_id=user) == absent
    assert host_outcomes.recent(tmp_path)["exchanges"] == host_outcomes.recent(tmp_path, user_id="qq:1")["exchanges"] == []


def test_outcomes_observed_before_installation_stay_readable_and_bind_on_first_confirmation(tmp_path, offline):
    exchange(tmp_path)  # No profile yet: plugin state holds no installation identity.
    ensure_profile(tmp_path, database_engine="embedded", api_port=_free_port(), database_port=_free_port())
    assert look(tmp_path)["states"] == {"queued": 2}
    host.flush(Confirming(), tmp_path)
    assert look(tmp_path)["states"] == {"recorded": 2}
    _rewrite_profile(tmp_path, brain_id=str(uuid.uuid4()))
    assert look(tmp_path)["status"] == "not_found"  # Confirmed against the first brain, so bound to it.


# Erasure and retention -----------------------------------------------------------------------------------------

def test_erasing_a_person_removes_their_outcomes_and_replay_cannot_bring_them_back(tmp_path, monkeypatch):
    client = online(monkeypatch, Erasing())
    exchange(tmp_path, user_id="qq:1")
    exchange(tmp_path, "t2", user_id="qq:2")
    with monkeypatch.context() as down:
        down.setattr(host, "ready_client", lambda *args: None)
        down.setattr(host, "start_in_background", lambda *args: None)
        exchange(tmp_path, "t3", user_id="qq:1")
        host.finish_turn(tmp_path, "s", ANSWER, turn_id="t", user_id="qq:1")  # A repeat, listed for qq:1.
    assert look(tmp_path, user_id="qq:1")["states"] == {"recorded": 2}
    assert look(tmp_path, "t3", user_id="qq:1")["states"] == {"queued": 2}
    survivor = look(tmp_path, "t2", user_id="qq:2")
    host.erase_user(tmp_path, "qq:1")
    for turn in ("t", "t3"):
        erased = look(tmp_path, turn, user_id="qq:1")
        assert erased["status"] == "erased" and "messages" not in erased and "unsettled_callbacks" not in erased
    stored = json.loads(ledger_text(tmp_path))
    assert all("outcome" not in entry for entry in stored["turns"].values() if entry["owner"] == "qq:1")
    assert all(item["owner"] != "qq:1" for item in stored.get("callbacks", []))
    assert host_outcomes.recent(tmp_path, user_id="qq:1")["exchanges"] == []
    assert look(tmp_path, "t2", user_id="qq:2")["messages"] == survivor["messages"]
    observed = len(client.observed)
    assert host.flush(client, tmp_path) == 0 and len(client.observed) == observed  # Its queued copy was dropped.
    # Even an observation for the erased exchange has nowhere to land.
    reference = host_outcomes.reference({"role": "user", "conversation_id": "s", "_user": "qq:1",
                                         "producer_ref": host.PRODUCER, "source_event_key": "s:t3:user"})
    message = host._observed_message("user", None, {"state": "recorded", "event_id": "late", "duplicate": False})
    assert host_outcomes.observe(tmp_path, [(reference, message)], lambda owner: None) == 0
    assert look(tmp_path, "t3", user_id="qq:1")["status"] == "erased" and "late" not in kept(tmp_path)


def test_erasing_one_person_keeps_another_persons_unsettled_callbacks_in_a_shared_session(tmp_path, monkeypatch):
    online(monkeypatch, Erasing())
    exchange(tmp_path, session="shared", user_id="alice")
    host.finish_turn(tmp_path, "shared", ANSWER, turn_id="bob-missing", user_id="bob")
    host.finish_turn(tmp_path, "shared", ANSWER, turn_id="alice-missing", user_id="alice")
    host.prompt_context(tmp_path, "shared", QUESTION, turn_id="t2", user_id="alice")  # The session's latest user.
    before = look(tmp_path, "bob-missing", session="shared", user_id="bob")
    assert before["states"] == {"unknown": 2}
    host.erase_user(tmp_path, "alice")
    assert look(tmp_path, "bob-missing", session="shared", user_id="bob")["messages"] == before["messages"]
    assert look(tmp_path, "alice-missing", session="shared", user_id="alice")["status"] == "not_found"
    assert look(tmp_path, session="shared", user_id="alice")["status"] == "erased"
    assert "alice" not in kept(tmp_path)


def test_a_lookup_waits_for_the_ledger_lock_and_reports_a_busy_store(tmp_path, monkeypatch, offline):
    from concurrent.futures import ThreadPoolExecutor

    from membrain.local_profile import profile_lock

    exchange(tmp_path)
    monkeypatch.setattr(host_outcomes, "LOOKUP_LOCK_SECONDS", 0.2)
    with ThreadPoolExecutor(1) as other:  # Another thread stands in for a host process writing the ledger.
        with profile_lock(tmp_path / "plugin" / "session-state-lock", timeout=5):
            busy = other.submit(look, tmp_path).result()
            listing = other.submit(host_outcomes.recent, tmp_path).result()
            absent = other.submit(look, tmp_path, "t", "no-such-session").result()
    assert busy == {"version": host_outcomes.VERSION, "status": "unavailable", "reason": "store_busy"}
    assert listing["exchanges"] == [] and listing["unreadable_sessions"] == 1
    assert absent["status"] == "not_found"  # No ledger exists, so nothing needed the lock.
    assert look(tmp_path)["states"] == {"queued": 2}


def test_outcomes_are_bounded_by_the_session_ledger(tmp_path, offline):
    for index in range(host_turns.MAX_FINISHED + 20):
        exchange(tmp_path, f"t{index}")
    for _ in range(host_outcomes.MAX_CALLBACKS + 9):
        host.finish_turn(tmp_path, "s", ANSWER, turn_id="never-staged")
    stored = json.loads(ledger_text(tmp_path))
    assert len(stored["turns"]) == host_turns.MAX_FINISHED and len(stored["callbacks"]) == host_outcomes.MAX_CALLBACKS
    assert look(tmp_path, "t0")["status"] == "not_found"  # Expired, and said so.
    assert look(tmp_path, f"t{host_turns.MAX_FINISHED + 19}")["states"] == {"queued": 2}
    listing = host_outcomes.recent(tmp_path, session="s", limit=3)
    assert len(listing["exchanges"]) == 3 and listing["truncated"] is True
    assert listing["retention"] == {"finished_exchanges_per_session": 256, "unsettled_callbacks_per_session": 16,
                                    "session_ledger_days": 14, "sessions_read_without_a_session": 32}
    for limit in (0, 51, "3", True):
        with pytest.raises(ValueError):
            host_outcomes.recent(tmp_path, limit=limit)


def test_a_listing_without_a_session_reads_only_the_newest_ledgers(tmp_path, offline):
    for index in range(host_outcomes.RECENT_SESSIONS + 4):
        exchange(tmp_path, session=f"s{index}")
        (marker,) = [path for path in (tmp_path / "plugin" / "sessions").glob("*.json")
                     if path.stem == host_outcomes._marker(f"s{index}")]
        os.utime(marker, (1_700_000_000 + index, 1_700_000_000 + index))
    listing = host_outcomes.recent(tmp_path, limit=50)
    keys = {item["messages"][0]["source"]["source_event_key"] for item in listing["exchanges"]}
    assert listing["truncated"] is True and len(listing["exchanges"]) == host_outcomes.RECENT_SESSIONS
    assert "s0:t:user" not in keys and "s3:t:user" not in keys and "s4:t:user" in keys
    assert look(tmp_path, session="s0")["states"] == {"queued": 2}  # Still found when named.


def test_an_expired_session_ledger_is_explicitly_not_found(tmp_path, offline):
    exchange(tmp_path)
    (marker,) = (tmp_path / "plugin" / "sessions").glob("*.json")
    old = time.time() - host.SESSION_MARKER_SECONDS - 60
    os.utime(marker, (old, old))
    host._mark_history(tmp_path, "another", False)  # The existing 14-day cleanup at a session start.
    assert not marker.exists() and look(tmp_path)["status"] == "not_found"
    assert host.flush(Confirming(), tmp_path) == 2  # Replay still stores the journal; there is no ledger to update.
    assert look(tmp_path)["status"] == "not_found"


def test_a_session_start_keeps_unsettled_callbacks(tmp_path, offline):
    exchange(tmp_path)
    host.finish_turn(tmp_path, "s", ANSWER, turn_id="never-staged")
    host._mark_history(tmp_path, "s", False)
    assert look(tmp_path, "never-staged")["states"] == {"unknown": 2}


# Plugin hooks --------------------------------------------------------------------------------------------------

def run_cli(monkeypatch, capsys, directory, *arguments):
    monkeypatch.setattr(sys, "argv", ["membrain", "plugin", "outcome", "--directory", str(directory), *arguments])
    capsys.readouterr()
    with pytest.raises(SystemExit) as stopped:
        cli.main()
    captured = capsys.readouterr()
    return stopped.value.code, (json.loads(captured.out) if captured.out else captured.err)


def hook(directory, event, payload, capsys, host_name="claude-code"):
    assert plugin.run_hook(event, directory, stream=io.BytesIO(json.dumps(payload).encode()), host_name=host_name) == 0
    return capsys.readouterr().out


def test_hook_exchanges_are_queryable_from_the_cli_and_hook_output_is_unchanged(tmp_path, offline, monkeypatch, capsys):
    hook(tmp_path, "user-prompt", {"session_id": "c1", "prompt_id": "p1", "prompt": QUESTION}, capsys)
    assert hook(tmp_path, "stop", {"session_id": "c1", "prompt_id": "p1", "last_assistant_message": ANSWER}, capsys) == ""
    assert "needs attention" not in log_text(tmp_path)  # Queued is not a failure.
    code, found = run_cli(monkeypatch, capsys, tmp_path, "--session", "c1", "--turn", "p1")
    assert code == 0 and found["states"] == {"queued": 2} and QUESTION not in json.dumps(found)
    # A second Stop for the same prompt and a Stop for an unknown one: logged without text, and queryable.
    assert hook(tmp_path, "stop", {"session_id": "c1", "prompt_id": "p1", "last_assistant_message": ANSWER}, capsys) == ""
    assert hook(tmp_path, "stop", {"session_id": "c1", "prompt_id": "p9", "last_assistant_message": ANSWER}, capsys) == ""
    assert log_text(tmp_path).count("recording outcome needs attention: user unknown (turn_") == 2
    assert ANSWER not in log_text(tmp_path)
    code, unknown = run_cli(monkeypatch, capsys, tmp_path, "--session", "c1", "--turn", "p9")
    assert code == 0 and unknown["states"] == {"unknown": 2}
    code, listing = run_cli(monkeypatch, capsys, tmp_path)
    assert code == 0 and [item["states"] for item in listing["exchanges"]] == [{"unknown": 2}, {"queued": 2}]
    code, by_handle = run_cli(monkeypatch, capsys, tmp_path, "--exchange", found["exchange"])
    assert code == 0 and by_handle["messages"] == found["messages"] and len(by_handle["unsettled_callbacks"]) == 1
    # Codex records under its own producer: the same ids name a different exchange there.
    assert run_cli(monkeypatch, capsys, tmp_path, "--session", "c1", "--turn", "p1", "--host", "codex")[0] == 1
    assert run_cli(monkeypatch, capsys, tmp_path, "--session", "c1", "--turn", "p1", "--user-id", "qq:9")[0] == 1
    code, message = run_cli(monkeypatch, capsys, tmp_path, "--exchange", "not-a-handle")
    assert code == 2 and "handle" in message
    assert run_cli(monkeypatch, capsys, tmp_path, "--platform", "qq")[0] == 2


def test_a_codex_exchange_for_one_person_is_found_under_its_host_and_user(tmp_path, offline, monkeypatch, capsys):
    payload = {"session_id": "x1", "turn_id": "7", "membrain_user": "discord:42"}
    hook(tmp_path, "user-prompt", {**payload, "prompt": QUESTION}, capsys, "codex")
    hook(tmp_path, "stop", {**payload, "last_assistant_message": ANSWER}, capsys, "codex")
    arguments = ("--session", "x1", "--turn", "7", "--host", "codex")
    assert run_cli(monkeypatch, capsys, tmp_path, *arguments)[0] == 1  # Not the installation owner's.
    code, found = run_cli(monkeypatch, capsys, tmp_path, *arguments, "--platform", "discord", "--user", "42")
    assert code == 0 and found["states"] == {"queued": 2}
    assert found["messages"][0]["source"]["producer_ref"] == "membrain-codex"


# OpenAI-compatible proxy ---------------------------------------------------------------------------------------

def proxy(directory, upstream, **options):
    memory = ChatMemory(directory, producer="membrain-proxy", tools=None)
    app = create_proxy_app(memory, "https://api.example.test/v1", transport=httpx.MockTransport(upstream), **options)
    return TestClient(app, base_url="http://127.0.0.1:8790")


def chat(client, user, text=QUESTION, **options):
    return client.post("/v1/chat/completions", headers=options.pop("headers", {}),
                       json={"model": "m", "user": user, "messages": [{"role": "user", "content": text}], **options})


def test_the_proxy_names_each_exchange_and_answers_for_its_person_only(tmp_path, offline):
    upstream = Upstream(ANSWER)
    with proxy(tmp_path, upstream) as client:
        answer = chat(client, "viewer-1")
        assert answer.json() == {"choices": [{"message": {"role": "assistant", "content": ANSWER}}]}  # Body unchanged.
        handle = answer.headers[EXCHANGE_HEADER]
        found = client.get(f"/v1/membrain/recording-outcomes/{handle}", params={"user": "viewer-1"})
        assert found.status_code == 200 and found.headers["cache-control"] == "no-store"
        assert found.json()["states"] == {"queued": 2} and QUESTION not in found.text and ANSWER not in found.text
        assert found.json()["messages"][0]["source"]["producer_ref"] == "membrain-proxy"
        same = client.get(f"/membrain/recording-outcomes/{handle}", headers={"X-Membrain-User": "viewer-1"})
        assert same.json()["messages"] == found.json()["messages"]
        missing = client.get(f"/v1/membrain/recording-outcomes/{'0' * 32}.{'0' * 64}", params={"user": "viewer-1"})
        other = client.get(f"/v1/membrain/recording-outcomes/{handle}", params={"user": "viewer-2"})
        anonymous = client.get(f"/v1/membrain/recording-outcomes/{handle}")
        assert other.status_code == anonymous.status_code == missing.status_code == 404
        assert other.json() == anonymous.json() == missing.json() and missing.json()["status"] == "not_found"
        assert client.get("/v1/membrain/recording-outcomes/guess", params={"user": "viewer-1"}).status_code == 400
        chat(client, "viewer-1", "Second synthetic question 6031")
        listing = client.get("/v1/membrain/recording-outcomes", params={"user": "viewer-1", "limit": "5"}).json()
        assert [item["states"] for item in listing["exchanges"]] == [{"queued": 2}] * 2
        assert client.get("/v1/membrain/recording-outcomes", params={"user": "viewer-2"}).json()["exchanges"] == []
        assert client.get("/v1/membrain/recording-outcomes", params={"limit": "many"}).status_code == 400
        assert client.get("/v1/models").status_code == 200
    # Lookups are answered locally: the provider saw only the two chat completions and the model list.
    assert [request["url"].rsplit("/", 1)[-1] for request in upstream.requests] == ["completions", "completions", "models"]


def test_a_streamed_exchange_is_named_before_it_is_recorded(tmp_path, offline):
    with proxy(tmp_path, Upstream(ANSWER)) as client:
        with client.stream("POST", "/v1/chat/completions", json={
                "model": "m", "stream": True, "user": "viewer-1",
                "messages": [{"role": "user", "content": QUESTION}]}) as response:
            handle = response.headers[EXCHANGE_HEADER]
            during = client.get(f"/v1/membrain/recording-outcomes/{handle}", params={"user": "viewer-1"}).json()
            body = "".join(response.iter_text())
        assert during["status"] == "awaiting_completion" and "data: [DONE]" in body
        after = client.get(f"/v1/membrain/recording-outcomes/{handle}", params={"user": "viewer-1"}).json()
        assert after["states"] == {"queued": 2}


def test_a_failed_provider_call_leaves_the_exchange_awaiting_not_recorded(tmp_path, offline):
    def failing(request):
        return httpx.Response(500, json={"error": "synthetic provider failure"})

    with proxy(tmp_path, failing) as client:
        answer = chat(client, "viewer-1")
        assert answer.status_code == 500
        found = client.get(f"/v1/membrain/recording-outcomes/{answer.headers[EXCHANGE_HEADER]}",
                           params={"user": "viewer-1"}).json()
        assert found["status"] == "awaiting_completion" and "messages" not in found


def test_proxy_tokens_keep_outcomes_inside_their_namespace(tmp_path, offline):
    tokens = {"t" * 20: "qq", "u" * 20: "tg"}
    with proxy(tmp_path, Upstream(ANSWER), upstream_key="provider-key", tokens=tokens) as client:
        qq, tg = {"Authorization": "Bearer " + "t" * 20}, {"Authorization": "Bearer " + "u" * 20}
        handle = chat(client, "42", headers=qq).headers[EXCHANGE_HEADER]
        path = f"/v1/membrain/recording-outcomes/{handle}"
        assert client.get(path, params={"user": "42"}, headers=qq).json()["states"] == {"queued": 2}
        assert client.get(path, params={"user": "42"}, headers=tg).status_code == 404  # Same id, another bot.
        assert client.get(path, params={"user": "42"}).status_code == 401
        assert client.get(path, headers=qq).status_code == 400  # A namespaced bot must name its person.
        assert client.get("/v1/membrain/recording-outcomes", params={"user": "42"}, headers=tg).json()["exchanges"] == []


def test_a_roleplay_exchange_is_found_only_with_its_character_and_session(tmp_path, offline):
    with proxy(tmp_path, Upstream(ANSWER)) as client:
        headers = {"X-Membrain-User": "viewer-1", "X-Membrain-Roleplay": "Captain", "X-Membrain-Session": "night-1"}
        handle = chat(client, "viewer-1", headers=headers).headers[EXCHANGE_HEADER]
        path = f"/v1/membrain/recording-outcomes/{handle}"
        assert client.get(path, headers=headers).json()["states"] == {"queued": 2}
        assert client.get(path, headers={"X-Membrain-User": "viewer-1"}).status_code == 404
        assert len(client.get("/v1/membrain/recording-outcomes", headers=headers).json()["exchanges"]) == 1
        assert client.get("/v1/membrain/recording-outcomes", headers={**headers, "X-Membrain-Session": "night-2"}
                          ).json()["exchanges"] == []


def test_an_unrecorded_group_gets_no_exchange_header(tmp_path, offline):
    memory = ChatMemory(tmp_path, producer="membrain-proxy", tools=None, record_groups=False)
    app = create_proxy_app(memory, "https://api.example.test/v1", transport=httpx.MockTransport(Upstream(ANSWER)))
    with TestClient(app, base_url="http://127.0.0.1:8790") as client:
        answer = chat(client, "viewer-1", headers={"X-Membrain-Group": "room-1"})
        assert answer.status_code == 200 and EXCHANGE_HEADER not in answer.headers
        assert memory.exchange(Speaker("api", "viewer-1", "room-1"), session="s", turn_id="t") is None


def test_chat_memory_reads_back_the_outcome_of_the_receipt_it_returned(tmp_path, offline):
    memory, speaker = ChatMemory(tmp_path), Speaker("telegram", "5")
    session = memory.session(speaker)
    memory.context(speaker, QUESTION, session=session, turn_id="m1")
    receipt = memory.record(speaker, ANSWER, session=session, turn_id="m1")
    found = memory.outcome(speaker, session=session, turn_id="m1")
    assert found["states"] == receipt["states"] == {"queued": 2}
    assert found["exchange"] == memory.exchange(speaker, session=session, turn_id="m1")
    assert [item["source"] for item in found["messages"]] == [item["source"] for item in receipt["messages"]]
    assert memory.outcome(Speaker("telegram", "6"), exchange=found["exchange"])["status"] == "not_found"
    assert len(memory.recent_outcomes(speaker, session=session)["exchanges"]) == 1


# Hermes --------------------------------------------------------------------------------------------------------

def hermes_provider(tmp_path, session="h1", **options):
    instance = hermes.MembrainProvider()
    instance.initialize(session, hermes_home=str(tmp_path / "home"), **{"platform": "cli", **options})
    return instance


def test_hermes_turns_are_queryable_through_the_provider_and_its_tool(tmp_path, offline):
    instance = hermes_provider(tmp_path)
    directory = instance._directory
    instance.sync_turn(QUESTION, ANSWER)
    (listed,) = instance.recording_outcomes()["exchanges"]
    assert listed["states"] == {"queued": 2} and listed["messages"][0]["source"]["producer_ref"] == "membrain-hermes"
    assert "membrain_recording_status" in [tool["name"] for tool in instance.get_tool_schemas()]
    answer = instance.handle_tool_call("membrain_recording_status", {})
    assert json.loads(answer)["exchanges"][0]["messages"] == listed["messages"] and QUESTION not in answer
    assert "error" in json.loads(instance.handle_tool_call("membrain_recording_status", {"limit": 500}))
    # A later replay confirms it; a new provider instance (a restarted Hermes) reads the same outcome.
    assert host.flush(Confirming(), directory) == 2
    restarted = hermes_provider(tmp_path)
    assert restarted.recording_outcomes()["exchanges"][0]["states"] == {"recorded": 2}
    assert "needs attention" not in log_text(directory)
    # A gateway sender is another person: they see nothing of the owner's session, even with the same session id.
    sender = hermes_provider(tmp_path, platform="telegram", user_id="77")
    assert sender.recording_outcomes()["exchanges"] == []
    assert host_outcomes.lookup(directory, exchange=listed["exchange"], user_id=sender._user)["status"] == "not_found"
    # The CLI reaches the same record for the operator.
    assert host_outcomes.recent(directory, session="h1", producer="membrain-hermes")["exchanges"][0]["exchange"] == listed["exchange"]


def test_hermes_prefetch_then_sync_reports_a_requested_pause_as_an_exclusion(tmp_path, offline):
    instance = hermes_provider(tmp_path)
    instance.prefetch("Off the record: " + QUESTION)
    instance.sync_turn("Off the record: " + QUESTION, ANSWER)
    (listed,) = instance.recording_outcomes()["exchanges"]
    assert [(item["state"], item["reason"], item["scope"]) for item in listed["messages"]] == [
        ("excluded", "pause_requested", "conversation")] * 2
    assert "needs attention" not in log_text(instance._directory) and queued(instance._directory) == []


def test_a_hermes_turn_that_cannot_be_matched_is_logged_and_listed_as_unknown(tmp_path, offline):
    instance = hermes_provider(tmp_path)
    directory = instance._directory
    # Whole-turn reporting without prefetch: the message's own request excludes it, and is reported as that.
    instance.sync_turn("Off the record: " + QUESTION, ANSWER)
    assert "needs attention" not in log_text(directory)
    instance.sync_turn(QUESTION, ANSWER)  # After an exclusion, an unstaged turn in this session cannot be matched.
    listed = instance.recording_outcomes()["exchanges"]
    assert [item["states"] for item in listed] == [{"unknown": 2}, {"excluded": 2}]
    assert {item["reason"] for item in listed[0]["messages"]} == {"turn_not_staged"}
    assert {(item["reason"], item["scope"]) for item in listed[1]["messages"]} == {("pause_requested", "conversation")}
    assert "recording outcome needs attention: user unknown (turn_not_staged)" in log_text(directory)
    assert QUESTION not in log_text(directory) and queued(directory) == []


def test_a_readonly_hermes_context_has_no_recording_tool(tmp_path, offline):
    instance = hermes_provider(tmp_path, agent_context="subagent")
    assert [tool["name"] for tool in instance.get_tool_schemas()] == ["membrain_search"]
    assert "cannot change memory" in instance.handle_tool_call("membrain_recording_status", {})


# Real service --------------------------------------------------------------------------------------------------

def timeline(turns):
    return turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"]


@pytest.fixture
def served(turns, connected, tmp_path, monkeypatch):
    """The fixture service is reached by a client that was not opened from a profile in ``tmp_path``; outcomes
    are bound to that client's target, so the lookup is told the same one. The installed-service test below
    derives it from a real profile instead."""
    with connected(tmp_path) as client:
        target = host_recording._target(client)
    monkeypatch.setattr(host_recording, "local_target", lambda directory, user_id=None: target)
    return connected


def test_real_service_outcomes_name_the_stored_events_after_a_later_replay(turns, served, tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    assert look(tmp_path)["status"] == "awaiting_completion"  # Staged online: bound to the client's target.
    with monkeypatch.context() as down:
        down.setattr(host, "ready_client", lambda *args: None)
        host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    assert look(tmp_path)["states"] == {"queued": 2} and timeline(turns) == []
    with served(tmp_path) as client:
        assert host.flush(client, tmp_path) == 2
    recorded = look(tmp_path)
    assert recorded["states"] == {"recorded": 2}
    assert {item["event_id"] for item in recorded["messages"]} == {row["event_id"] for row in timeline(turns)}


def test_real_service_commit_with_a_lost_answer_is_unconfirmed_then_confirmed_once(
        turns, served, tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    observe = host_recording.observe

    def lost(client, record):
        observe(client, record)  # Committed by the service ...
        raise httpx.ReadTimeout("synthetic lost answer")  # ... but the answer never arrives.

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host_recording, "observe", lost)
        host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    uncertain = look(tmp_path)
    assert states(uncertain) == [("user", "queued", "server_outcome_unknown", "replay"),
                                 ("assistant", "queued", "replay_not_observed", "callback")]
    committed = [row["event_id"] for row in timeline(turns)]
    assert len(committed) == 1  # The server already holds what the outcome honestly could not confirm.
    with served(tmp_path) as client:
        assert host.flush(client, tmp_path) == 2
    confirmed = look(tmp_path)
    assert confirmed["states"] == {"recorded": 2} and confirmed["messages"][0]["event_id"] == committed[0]
    assert len(timeline(turns)) == 2


def test_real_service_pause_after_queueing_is_an_exclusion_and_stores_nothing(turns, served, tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", QUESTION, turn_id="t")
    with monkeypatch.context() as down:
        down.setattr(host, "ready_client", lambda *args: None)
        host.finish_turn(tmp_path, "s", ANSWER, turn_id="t")
    policy(turns, True, 0)
    with served(tmp_path) as client:
        host.flush(client, tmp_path)
    excluded = look(tmp_path)
    assert [(item["state"], item["reason"], item["scope"], item["evidence"]) for item in excluded["messages"]] == [
        ("excluded", "server_paused", "brain", "write_rejected")] * 2
    assert timeline(turns) == [] and queued(tmp_path) == []


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_hook_processes_and_a_restarted_service_keep_outcomes_queryable(tmp_path):
    """Real processes end to end: hook commands, a stopped service, the service's own replay after a restart, and
    the CLI lookup, each in its own process."""
    directory = tmp_path / "brain"
    environment = {**os.environ, "MEMBRAIN_SEMANTIC": "0"}

    def run(*arguments, payload=None):
        return subprocess.run([sys.executable, "-m", "membrain.cli", "plugin", *arguments, "--directory", str(directory)],
                              input=json.dumps(payload).encode() if payload is not None else None,
                              capture_output=True, timeout=180, env=environment)

    def outcome(*arguments):
        done = run("outcome", *arguments)
        return done.returncode, json.loads(done.stdout)

    def turn(session, prompt_id):
        run("hook", "user-prompt", payload={"session_id": session, "prompt_id": prompt_id, "prompt": QUESTION})
        return run("hook", "stop", payload={"session_id": session, "prompt_id": prompt_id,
                                           "last_assistant_message": ANSWER})

    try:
        host.start(directory)
        assert turn("live", "p1").stdout == b""  # The Stop hook's output is unchanged.
        code, online_result = outcome("--session", "live", "--turn", "p1")
        assert code == 0 and online_result["states"] == {"recorded": 2}
        with host.ready_client(directory) as client:
            stored = {item["event_id"] for item in client.timeline(roles=("user", "assistant"),
                                                                   conversation_id="live")["items"]}
        assert {item["event_id"] for item in online_result["messages"]} == stored and len(stored) == 2

        desktop.stop(directory)
        # A hook may start the service at most once a minute; this keeps it down while the turn is queued.
        (directory / "plugin" / "last-start-attempt").touch()
        assert turn("live", "p2").stdout == b""
        code, offline_result = outcome("--session", "live", "--turn", "p2")
        assert code == 0 and offline_result["states"] == {"queued": 2}
        assert {item["reason"] for item in offline_result["messages"]} == {"service_unavailable"}
        assert outcome("--session", "live", "--turn", "p1")[1]["messages"] == online_result["messages"]

        desktop.start(directory)  # The restarted service drains the journal itself, in its own process.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            code, replayed = outcome("--session", "live", "--turn", "p2")
            if replayed.get("states") == {"recorded": 2}:
                break
            time.sleep(0.5)
        assert replayed["states"] == {"recorded": 2} and {item["observed_by"] for item in replayed["messages"]} == {"replay"}
        with host.ready_client(directory) as client:
            stored = {item["event_id"] for item in client.timeline(roles=("user", "assistant"),
                                                                   conversation_id="live")["items"]}
        assert {item["event_id"] for item in replayed["messages"]} < stored and len(stored) == 4
        code, listing = outcome("--session", "live")
        assert code == 0 and [item["states"] for item in listing["exchanges"]] == [{"recorded": 2}] * 2
        assert QUESTION not in json.dumps(listing) and outcome("--session", "live", "--turn", "p3")[0] == 1
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
