import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import pytest
from test_host import Client
from test_host_recording import connected as connected
from test_server_recording import policy
from test_server_recording import turns as turns

from membrain import host, host_recording


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)


def queued(directory):
    path = directory / "plugin" / "spool.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def test_full_queue_does_not_report_delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "SPOOL_BYTES", 1)
    assert host.deliver(tmp_path, None, host.message_record("s", "user", "Unqueued")) is False
    assert queued(tmp_path) == []


def test_capacity_covers_the_encoded_record_and_does_not_overshoot(tmp_path, monkeypatch):
    record = host.message_record("s", "user", "中文" * 20)
    size = len((json.dumps(record, ensure_ascii=False) + "\n").encode())
    monkeypatch.setattr(host, "SPOOL_BYTES", size - 1)
    assert host.spool(tmp_path, record) is False
    assert queued(tmp_path) == []
    monkeypatch.setattr(host, "SPOOL_BYTES", size)
    assert host.spool(tmp_path, record) is True
    assert host.spool(tmp_path, record) is False
    assert queued(tmp_path) == [record]


def test_full_queue_keeps_the_turn_available_for_a_later_callback(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    monkeypatch.setattr(host, "SPOOL_BYTES", 1)
    assert host.finish_turn(tmp_path, "s", "Answer", turn_id="t") == []
    assert not next(iter(host.session_state(tmp_path, "s")["turns"].values())).get("done")
    monkeypatch.setattr(host, "SPOOL_BYTES", 10000)
    assert len(host.finish_turn(tmp_path, "s", "Answer", turn_id="t")) == 2
    assert [r["text"] for r in queued(tmp_path)] == ["Question", "Answer"]


def test_exit_after_completion_marker_leaves_the_complete_turn_replayable(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    write = host._write_session_state

    def crash(directory, session, state):
        write(directory, session, state)
        if any(entry.get("done") for entry in state["turns"].values()):
            raise SystemExit("process exited after marking the turn complete")

    monkeypatch.setattr(host, "_write_session_state", crash)
    with pytest.raises(SystemExit):
        host.finish_turn(tmp_path, "s", "Answer", turn_id="t")
    client = Client()
    assert host.flush(client, tmp_path) == 2
    assert [r["text"] for r in client.observed] == ["Question", "Answer"]


def test_sync_failure_does_not_complete_the_turn(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")

    def fail(*args):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(host.os, "fsync", fail)
    with pytest.raises(OSError, match="synthetic disk failure"):
        host.finish_turn(tmp_path, "s", "Answer", turn_id="t")
    assert not next(iter(host.session_state(tmp_path, "s")["turns"].values())).get("done")
    assert queued(tmp_path) == []


def test_torn_utf8_tail_cannot_corrupt_the_next_queued_record(tmp_path):
    path = host.state_directory(tmp_path) / "spool.jsonl"
    path.write_bytes(b'{"text":"\xe4')
    record = host.message_record("s", "user", "Intact")
    host.spool(tmp_path, record)
    client = Client()
    host.flush(client, tmp_path)
    assert [r["text"] for r in client.observed] == ["Intact"]


def test_queue_capacity_cannot_accept_only_half_a_turn(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    entry = next(iter(host.session_state(tmp_path, "s")["turns"].values()))
    user_bytes = len((json.dumps(entry["record"], ensure_ascii=False) + "\n").encode())
    monkeypatch.setattr(host, "SPOOL_BYTES", user_bytes + 1)
    assert host.finish_turn(tmp_path, "s", "Answer", turn_id="t") == []
    assert queued(tmp_path) == []
    assert not next(iter(host.session_state(tmp_path, "s")["turns"].values())).get("done")


def test_partial_append_is_rolled_back_and_never_acknowledged(tmp_path, monkeypatch):
    first = host.message_record("s", "user", "First")
    assert host.spool(tmp_path, first)
    fdopen = host.os.fdopen

    class ShortWrite:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def write(self, value):
            return self.stream.write(value[:10])

    monkeypatch.setattr(host.os, "fdopen", lambda *args, **kwargs: ShortWrite(fdopen(*args, **kwargs)))
    with pytest.raises(OSError, match="Incomplete queue write"):
        host.spool(tmp_path, host.message_record("s", "assistant", "Second"))
    assert queued(tmp_path) == [first]


def test_nonfinite_corrupt_queue_metadata_cannot_block_a_healthy_turn(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    corrupt = host.message_record("old", "user", "Corrupt authority")
    corrupt["_recording"] = {"revision": float("nan"), "target": None}
    host.spool(tmp_path, corrupt)
    assert len(host.finish_turn(tmp_path, "s", "Answer", turn_id="t")) == 2
    assert [r["text"] for r in client.observed] == ["Question", "Answer"]
    assert queued(tmp_path) == []


@pytest.mark.parametrize("full", [False, True])
def test_abandoned_turn_is_queued_before_its_staging_copy_is_removed(tmp_path, monkeypatch, offline, full):
    host.prompt_context(tmp_path, "s", "Unanswered", turn_id="t")
    state = host.session_state(tmp_path, "s")
    next(iter(state["turns"].values()))["started"] = 0
    host._write_session_state(tmp_path, "s", state)
    if full:
        monkeypatch.setattr(host, "SPOOL_BYTES", 1)
        assert host._finish_abandoned(tmp_path, Client()) == 0
        assert not next(iter(host.session_state(tmp_path, "s")["turns"].values())).get("done")
    else:
        write = host._write_session_marker

        def crash(path, state):
            write(path, state)
            raise SystemExit("after abandoned turn completion")

        monkeypatch.setattr(host, "_write_session_marker", crash)
        with pytest.raises(SystemExit):
            host._finish_abandoned(tmp_path, Client())
        client = Client()
        assert host.flush(client, tmp_path) == 1
        assert [r["text"] for r in client.observed] == ["Unanswered"]


@pytest.mark.parametrize("boundary", ["before_marker", "after_marker", "first_observation", "second_observation", "queue_ack"])
def test_recovery_after_each_commit_boundary_does_not_duplicate_real_records(turns, connected, tmp_path, monkeypatch, boundary):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    write, observe, replace = host._write_session_state, host_recording.observe, host.os.replace
    observed = []

    def crash_marker(directory, session, state):
        if boundary == "before_marker":
            raise SystemExit(boundary)
        write(directory, session, state)
        if boundary == "after_marker":
            raise SystemExit(boundary)

    def crash_observation(client, record):
        result = observe(client, record)
        observed.append(record)
        if (boundary == "first_observation" and len(observed) == 1
                or boundary == "second_observation" and len(observed) == 2):
            raise SystemExit(boundary)
        return result

    def crash_ack(source, target):
        if boundary == "queue_ack" and target.name == "spool.jsonl":
            raise SystemExit(boundary)
        return replace(source, target)

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host, "_write_session_state", crash_marker)
        interrupted.setattr(host_recording, "observe", crash_observation)
        interrupted.setattr(host.os, "replace", crash_ack)
        with pytest.raises(SystemExit):
            host.finish_turn(tmp_path, "s", "Answer", turn_id="t")
    with connected(tmp_path) as client:
        assert host.flush(client, tmp_path) == 2
    before = {r["event_id"] for r in turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"]}
    host.finish_turn(tmp_path, "s", "Answer", turn_id="t")
    rows = turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"]
    assert len(rows) == 2 and {r["event_id"] for r in rows} == before
    assert {r["text"] for r in rows} == {"Question", "Answer"}
    assert queued(tmp_path) == []


@pytest.mark.parametrize("control", ["server_pause_resume", "erase"])
def test_recovered_queue_cannot_revive_revoked_or_erased_records(turns, connected, tmp_path, monkeypatch, control):
    host.prompt_context(tmp_path, "s", "Old question", turn_id="t")
    write = host._write_session_state

    def crash(directory, session, state):
        write(directory, session, state)
        raise SystemExit("before delivery")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host, "_write_session_state", crash)
        with pytest.raises(SystemExit):
            host.finish_turn(tmp_path, "s", "Old answer", turn_id="t")
    if control == "erase":
        assert host.erase_user(tmp_path, None)["queued_records_dropped"] == 2
    else:
        policy(turns, True, 0)
        policy(turns, False, 1)
    with connected(tmp_path) as client:
        host.flush(client, tmp_path)
    assert turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"] == []
    assert queued(tmp_path) == []
    assert "Old question" not in json.dumps(host.session_state(tmp_path, "s"))
    assert host.finish_turn(tmp_path, "s", "Old answer", turn_id="t") == []


@pytest.mark.parametrize("completed", [False, True])
def test_erasure_revokes_manual_capture_without_blocking_new_turns(turns, connected, tmp_path, completed):
    from test_manual_recording_capture import capture

    token = capture(host.prompt_context(tmp_path, "s", "Old detail", turn_id="old", include_source=True))
    if completed:
        host.finish_turn(tmp_path, "s", "Understood", turn_id="old")
    host.erase_user(tmp_path, None)
    with connected(tmp_path) as client:
        result = host_recording.save_note(tmp_path, client, "Old detail", recording_capture=token)
    assert "error" in result
    assert turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"] == []
    new_token = capture(host.prompt_context(tmp_path, "s", "New detail", turn_id="new", include_source=True))
    with connected(tmp_path) as client:
        result = host_recording.save_note(tmp_path, client, "New detail", recording_capture=new_token)
    assert result["note_id"]


def test_abrupt_process_exit_preserves_both_messages_for_a_fresh_process(tmp_path):
    script = '''
import os, sys
from pathlib import Path
from membrain import host
root = Path(sys.argv[1])
host.ready_client = lambda *args: None
host.start_in_background = lambda *args: None
host.prompt_context(root, "s", "Question", turn_id="t")
write = host._write_session_state
def exit_after_marker(directory, session, state):
    write(directory, session, state)
    os._exit(37)
host._write_session_state = exit_after_marker
host.finish_turn(root, "s", "Answer", turn_id="t")
'''
    child = subprocess.run([sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True, timeout=20)
    assert child.returncode == 37, child.stderr
    client = Client()
    assert host.flush(client, tmp_path) == 2
    assert [r["text"] for r in client.observed] == ["Question", "Answer"]


def test_a_slow_replay_does_not_block_admission_of_a_new_turn(tmp_path, monkeypatch, offline):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    host.spool(tmp_path, host.message_record("old", "user", "Older queued input"))
    entered, release = threading.Event(), threading.Event()

    class Slow(Client):
        def observe(self, **record):
            super().observe(**record)
            entered.set()
            assert release.wait(10)

    with ThreadPoolExecutor(max_workers=2) as workers:
        replay = workers.submit(host.flush, Slow(), tmp_path)
        try:
            assert entered.wait(5)
            finish = workers.submit(host.finish_turn, tmp_path, "s", "Answer", turn_id="t")
            assert len(finish.result(timeout=1)) == 2
        finally:
            release.set()
        assert replay.result(timeout=5) == 1
    assert [r["text"] for r in queued(tmp_path)] == ["Question", "Answer"]


def test_erase_serializes_with_turn_journaling_and_cannot_leave_a_revival_queue(turns, connected, tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    written, release, erasing = threading.Event(), threading.Event(), threading.Event()
    spool = host._spool_records

    def block(directory, records):
        result = spool(directory, records)
        written.set()
        assert release.wait(10)
        return result

    def erase():
        erasing.set()
        return host.erase_user(tmp_path, None)

    monkeypatch.setattr(host, "_spool_records", block)
    with ThreadPoolExecutor(max_workers=2) as workers:
        finishing = workers.submit(host.finish_turn, tmp_path, "s", "Answer", turn_id="t")
        try:
            assert written.wait(5)
            erased = workers.submit(erase)
            assert erasing.wait(5)
            with pytest.raises(TimeoutError):
                erased.result(timeout=0.05)
        finally:
            release.set()
        finishing.result(timeout=10)
        erased.result(timeout=10)
    with connected(tmp_path) as client:
        host.flush(client, tmp_path)
    assert queued(tmp_path) == []
    assert turns.service.timeline(turns.principal, turns.brain, roles=("user", "assistant"))["items"] == []
