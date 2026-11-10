"""Reproductions for two findings of the 2026-11-10 status audit. Both tests FAIL on runtime d6aa3d5 by design
and pass from runtime ede5769 (see ../../backend-conversation-pause-scope-2026-11-10.md).

Run from the repository root; no database or model is needed:

    uv run pytest evaluations/evidence/status-audit-2026-11-10/reproductions.py -q -s -p no:cacheprovider

The assertions state the expected behaviour, so a later fix turns them green. They are evidence, not part of the
test suite, and are not collected by the default ``testpaths``.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
from test_host import Client  # noqa: E402

from membrain import host  # noqa: E402
from membrain.mcp_server import create_server  # noqa: E402


def test_second_window_ends_first_windows_pause(tmp_path, monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    host.prompt_context(tmp_path, "A", "Off the record: I'm job hunting.", turn_id="t1")
    server = create_server(Client(), directory=tmp_path)
    asyncio.run(server.call_tool("memory_pause", {}))
    host.finish_turn(tmp_path, "A", "Okay, not keeping that.", turn_id="t1")
    assert host.paused(tmp_path) and client.observed == []
    host.session_context(tmp_path, "B")  # A second window opens while A is still in use.
    still_paused = host.paused(tmp_path)
    host.prompt_context(tmp_path, "A", "The offer is 185k from Initech.", turn_id="t2")
    host.finish_turn(tmp_path, "A", "Understood.", turn_id="t2")
    print("paused after B opened:", still_paused)
    print("recorded:", [record["text"] for record in client.observed])
    assert still_paused, "window B ended window A's conversation pause"
    assert client.observed == []


def test_rejected_spool_survives_erasure(tmp_path, monkeypatch):
    class Erasing(Client):
        def dashboard(self):
            return {"brain": {"scope_generation": 1}}

        def forget(self, ids, **options):
            return {"outcome": "applied"}

    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: Erasing())
    line = '{"_user": "alice", "text": "synthetic text of a refused record", "role": "user"}'
    host._reject(tmp_path, line, TypeError("refused"))
    path = host.state_directory(tmp_path) / "spool-rejected.jsonl"
    assert "synthetic text of a refused record" in path.read_text(encoding="utf-8")
    host.erase_user(tmp_path, "alice")
    remaining = path.read_text(encoding="utf-8") if path.exists() else ""
    print("refused text still on disk after erasure:", "synthetic text" in remaining)
    assert "synthetic text of a refused record" not in remaining, "erase_user left the refused record on disk"
