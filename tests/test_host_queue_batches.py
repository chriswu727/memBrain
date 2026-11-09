import json
import logging
import subprocess
import sys
import threading
import time

import pytest
from test_desktop_supervisor import supervisor as supervisor
from test_host import Client
from test_host_recording import connected as connected
from test_server_recording import turns as turns

from membrain import host


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")


def fill(directory, count=50):
    records = [host.message_record("queue", "user", f"message {index}", turn_id=str(index))
               for index in range(count)]
    assert host._spool_records(directory, records)
    return records


def test_default_replay_stops_at_one_bounded_batch(tmp_path):
    fill(tmp_path)
    client = Client()
    assert host.flush(client, tmp_path) == 16
    assert [record["text"] for record in client.observed] == [f"message {i}" for i in range(16)]
    assert host.flush(client, tmp_path) == 16
    assert host.flush(client, tmp_path) == 16
    assert host.flush(client, tmp_path) == 2
    assert [record["text"] for record in client.observed] == [f"message {i}" for i in range(50)]
    assert (tmp_path / "plugin/spool.jsonl").read_bytes() == b""


def test_replay_time_budget_stops_between_requests(tmp_path, monkeypatch):
    fill(tmp_path)
    clock = [0.0]
    monkeypatch.setattr(host.time, "monotonic", lambda: clock[0])

    class Slow(Client):
        def observe(self, **record):
            clock[0] += 0.6
            super().observe(**record)

    client = Slow()
    assert host.flush(client, tmp_path) == 2
    assert len(client.observed) == 2


def test_transient_failure_checkpoints_confirmed_prefix(tmp_path):
    fill(tmp_path, 10)

    class Failing(Client):
        def observe(self, **record):
            if record["text"] == "message 3":
                raise ConnectionError("unavailable")
            super().observe(**record)

    with pytest.raises(ConnectionError):
        host.flush(Failing(), tmp_path)
    restarted = Client()
    assert host.flush(restarted, tmp_path) == 7
    assert [r["text"] for r in restarted.observed] == [f"message {i}" for i in range(3, 10)]


def test_checkpoint_does_not_rewrite_the_backlog_and_status_excludes_it(tmp_path):
    from membrain import host_queue

    fill(tmp_path)
    queue = tmp_path / "plugin/spool.jsonl"
    original = queue.read_bytes()
    assert host.flush(Client(), tmp_path, max_records=2) == 2
    assert queue.read_bytes() == original
    assert host_queue.pending(queue) == 48
    checkpoint = host_queue.cursor_path(queue).read_text()
    assert "message" not in checkpoint and len(checkpoint) < 150


def test_policy_rejected_content_is_removed_from_disk_before_returning(tmp_path):
    from membrain.client import MemoryActionError

    fill(tmp_path)

    class Paused(Client):
        def observe(self, **record):
            raise MemoryActionError({"error": {"code": "recording_paused", "message": "Paused", "retryable": False}})

    assert host.flush(Paused(), tmp_path, max_records=2) == 2
    queue = tmp_path / "plugin/spool.jsonl"
    physical = [json.loads(line) for line in queue.read_bytes().splitlines()]
    assert len(physical) == 48 and physical[0]["text"] == "message 2"
    assert not (tmp_path / "plugin/spool-rejected.jsonl").exists()


@pytest.mark.parametrize("cursor", [{}, [], {"offset": -1}, {"offset": True},
                                   {"offset": 99999999, "sha256": "bad"},
                                   {"offset": 100, "sha256": "bad"}])
def test_invalid_checkpoint_never_skips_records(tmp_path, cursor):
    from membrain import host_queue

    fill(tmp_path, 5)
    host_queue.cursor_path(tmp_path / "plugin/spool.jsonl").write_text(json.dumps(cursor))
    client = Client()
    assert host.flush(client, tmp_path) == 5
    assert [r["text"] for r in client.observed] == [f"message {i}" for i in range(5)]


def test_failed_checkpoint_write_keeps_unacknowledged_records(tmp_path, monkeypatch):
    from membrain import host_queue

    fill(tmp_path, 5)

    def fail(*args):
        raise OSError("synthetic checkpoint failure")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host_queue, "acknowledge", fail)
        with pytest.raises(OSError):
            host.flush(Client(), tmp_path, max_records=2)
    client = Client()
    assert host.flush(client, tmp_path) == 5
    assert len(client.observed) == 5


def test_interrupted_compaction_cannot_apply_old_cursor_to_remainder(tmp_path, monkeypatch):
    from membrain import host_queue

    fill(tmp_path, 6)
    replace = host_queue.os.replace

    def crash(source, target):
        replace(source, target)
        if target.name == "spool.jsonl":
            raise SystemExit("after queue replacement")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host_queue.os, "replace", crash)
        with pytest.raises(SystemExit):
            host.flush(Client(), tmp_path, max_records=3)
    client = Client()
    assert host.flush(client, tmp_path) == 3
    assert [r["text"] for r in client.observed] == [f"message {i}" for i in range(3, 6)]


def test_a_process_exit_retains_completed_batch_progress(tmp_path):
    fill(tmp_path)
    script = """
import os,sys
from pathlib import Path
from membrain import host
class Client:
    brain_id='brain'
    def observe(self,**record): pass
assert host.flush(Client(),Path(sys.argv[1]))==16
os._exit(37)
"""
    assert subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=False).returncode == 37
    client = Client()
    assert host.flush(client, tmp_path) == 16
    assert client.observed[0]["text"] == "message 16"


def test_erasure_drops_only_pending_records_and_resets_checkpoint(turns, connected, tmp_path):
    from membrain import host_queue

    fill(tmp_path)
    with connected(tmp_path) as client:
        assert host.flush(client, tmp_path) == 16
    assert host.erase_user(tmp_path, None)["queued_records_dropped"] == 34
    assert host_queue.pending(tmp_path / "plugin/spool.jsonl") == 0
    with connected(tmp_path) as client:
        assert host.flush(client, tmp_path) == 0
    assert turns.service.timeline(turns.principal, turns.brain, roles=("user",))["items"] == []


def test_unrelated_replacement_queue_never_inherits_a_checkpoint(tmp_path):
    fill(tmp_path)
    assert host.flush(Client(), tmp_path) == 16
    queue = tmp_path / "plugin/spool.jsonl"
    replacement = host.message_record("new", "user", "New content", turn_id="new")
    queue.write_text(json.dumps(replacement) + "\n")
    client = Client()
    assert host.flush(client, tmp_path) == 1
    assert client.observed[0]["text"] == "New content"


def test_background_replay_drains_without_another_host_callback(tmp_path):
    from membrain import desktop, embedded_database
    from membrain.desktop_connection import open_client

    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    try:
        host.start(tmp_path)
        fill(tmp_path, 50)
        deadline = time.monotonic() + 20
        with open_client(tmp_path, start_service=False) as client:
            while time.monotonic() < deadline:
                rows = client.timeline(roles=("user",), limit=100)["items"]
                if len(rows) == 50:
                    break
                time.sleep(0.05)
        assert {row["text"] for row in rows} == {f"message {i}" for i in range(50)}
    finally:
        desktop.stop(tmp_path)


def test_supervisor_replay_thread_stops_cleanly(supervisor, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from membrain import desktop_connection

    supervisor.server = SimpleNamespace(started=True)
    fill(supervisor.profile.directory)
    client = Client()
    monkeypatch.setattr(desktop_connection, "open_client", lambda *args, **kwargs: client)
    worker = threading.Thread(target=supervisor.replay)
    worker.start()
    try:
        deadline = time.monotonic() + 5
        while len(client.observed) < 50 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(client.observed) == 50
    finally:
        supervisor.stopped.set()
        worker.join(5)
    assert not worker.is_alive()


def test_background_failure_backs_off_without_logging_content(supervisor, monkeypatch, caplog):
    from types import SimpleNamespace

    from membrain import desktop_connection

    delays = []
    supervisor.server = SimpleNamespace(started=True)
    supervisor.stopped = SimpleNamespace(is_set=lambda: len(delays) == 7, wait=delays.append)
    fill(supervisor.profile.directory)

    def unavailable(*args, **kwargs):
        raise ConnectionError("PRIVATE synthetic payload")

    monkeypatch.setattr(desktop_connection, "open_client", unavailable)
    with caplog.at_level(logging.INFO):
        supervisor.replay()
    assert delays == [2, 4, 8, 16, 30, 30, 30]
    assert "host_replay_failed" in caplog.text and "PRIVATE" not in caplog.text
