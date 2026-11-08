"""Measure local host-ledger overhead without a service, model, spool, or user data."""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from membrain import host, host_turns
from membrain.build_identity import BUILD_ID


def summary(samples):
    ordered = sorted(samples)
    return {"count": len(samples), "p50_ms": round(statistics.median(ordered), 3),
            "p95_ms": round(ordered[int((len(ordered) - 1) * .95)], 3), "max_ms": round(max(ordered), 3)}


def measure(iterations=1000):
    with tempfile.TemporaryDirectory(prefix="membrain-host-ledger-") as temporary:
        directory = Path(temporary).resolve()
        with (patch.object(host, "ready_client", return_value=None),
              patch.object(host, "start_in_background"), patch.object(host, "deliver", return_value=True)):
            for i in range(host_turns.MAX_FINISHED):
                host.prompt_context(directory, "serial", f"Warmup {i}", turn_id=str(i))
                host.finish_turn(directory, "serial", "Reply", turn_id=str(i))
            serial = []
            for i in range(iterations):
                turn = f"measured-{i}"
                started = time.perf_counter()
                host.prompt_context(directory, "serial", "Synthetic prompt " + str(i) + ". " * 200, turn_id=turn)
                records = host.finish_turn(directory, "serial", "Synthetic reply", turn_id=turn)
                serial.append((time.perf_counter() - started) * 1000)
                assert len(records) == 2

            def stage(i):
                host.prompt_context(directory, "parallel", f"Question {i}", turn_id=str(i))

            def finish(i):
                started = time.perf_counter()
                records = host.finish_turn(directory, "parallel", f"Answer {i}", turn_id=str(i))
                elapsed = (time.perf_counter() - started) * 1000
                assert [record["text"] for record in records] == [f"Question {i}", f"Answer {i}"]
                return elapsed

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(stage, range(host_turns.MAX_ACTIVE)))
                peak_bytes = host._session_marker(directory, "parallel").stat().st_size
                parallel = list(pool.map(finish, reversed(range(host_turns.MAX_ACTIVE))))
            state = host.session_state(directory, "serial")
            assert len(state["turns"]) == host_turns.MAX_FINISHED
            history = directory / "history"
            for i in range(500):
                host._write_session_state(history, str(i), state)
            full_scan, indexed_scan = [], []
            for _ in range(5):
                started = time.perf_counter()
                for marker in (history / "plugin" / "sessions").glob("*.json"):
                    with host.profile_lock(host.state_directory(history) / "session-state-lock", timeout=5):
                        saved = json.loads(marker.read_text())
                        assert all(entry.get("done") for entry in saved["turns"].values())
                full_scan.append((time.perf_counter() - started) * 1000)
                started = time.perf_counter()
                assert host._finish_abandoned(history, None) == 0
                indexed_scan.append((time.perf_counter() - started) * 1000)
            return {"build_id": BUILD_ID, "scope": "local ledger only; delivery mocked; no service or model calls",
                    "serial_prompt_and_finish": summary(serial), "eight_worker_finish": summary(parallel),
                    "serial_state_bytes": host._session_marker(directory, "serial").stat().st_size,
                    "peak_64_active_state_bytes": peak_bytes, "finished_markers": len(state["turns"]),
                    "500_completed_sessions_full_decode": summary(full_scan),
                    "500_completed_sessions_due_header": summary(indexed_scan)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    print(json.dumps(measure(args.iterations), indent=2))
