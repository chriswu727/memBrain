"""Recall concurrency benchmark for R5 (gap 20 of the maturity test matrix). No model calls of any kind.

Builds the 1,000-message keyword fixture in a new, disposable local installation (embedded PostgreSQL, semantic model
off), waits until the message index has caught up, then measures:

- serial recall p95 (bar: under 500 ms);
- 8 concurrent recalls on one brain, p95 (proposed bar: at most 1,000 ms);
- 8 concurrent recalls spread over 8 brains, p95 (proposed bar: at most 600 ms);
- memory map p95 at 200 and 500 nodes (1,000 messages and 100 notes);
- a "busy after bulk" probe: bulk-add messages, reading the map while they are written and immediately after.

A recall is ``host.recall_context`` (the plugin's per-message recall: boundaries, recall, the recalled messages and
their replies), excluding client start-up (``ready_client``) and reply generation. Each worker runs 21 rounds of one
query; the first round is warm-up and is discarded. While it runs, a sampler polls ``pg_stat_activity`` and
``pg_blocking_pids`` to record which transactions made others wait on a lock, and for how long they were open.

Prints machine information, every raw sample and the summary as JSON, and exits 1 when a bar is not met. Timing is
not stable in CI; run it on the reference machine before a release.
"""

import argparse
import atexit
import json
import os
import platform
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["MEMBRAIN_SEMANTIC"] = "0"
for _name in list(os.environ):
    # No provider of any kind may be reachable from the benchmark or the service it starts.
    if _name.endswith("_API_KEY") or _name.startswith(("MEMBRAIN_EXTRACTION", "MEMBRAIN_CHAT", "MEMORY_SEMANTIC")):
        del os.environ[_name]

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from membrain import desktop, host  # noqa: E402
from membrain.local_profile import ensure_profile  # noqa: E402

BARS = {"serial_p95_ms": 500, "one_brain_8_concurrent_p95_ms": 1000, "eight_brains_8_concurrent_p95_ms": 600}
QUERIES = [f"What is the appointment for project{i % 50:04d}?" for i in range(20)]


def message(i):
    return (f"For project{i % 50:04d}, my appointment {i} is at the Vancouver library on Friday. "
            "Bring the blue notebook and arrive at ten.")


def stats(samples):
    values = sorted(samples)
    if not values:
        return {"n": 0}
    return {"n": len(values), "median_ms": round(statistics.median(values), 2),
            "p95_ms": round(values[int(0.95 * (len(values) - 1))], 2), "max_ms": round(max(values), 2)}


def machine(database_url):
    cpu = platform.processor() or ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        version = conn.execute("SELECT version()").fetchone()[0]
    return {"cpu": cpu, "cores": os.cpu_count(), "os": platform.platform(), "python": platform.python_version(),
            "postgresql": version}


class LockSampler(threading.Thread):
    """Polls who waits on a lock and which transaction holds it; keeps the longest-open holder per statement."""

    QUERY = (
        "SELECT w.pid AS waiter, w.wait_event, left(w.query, 160) AS waiter_query, "
        "extract(epoch FROM clock_timestamp() - w.query_start) * 1000 AS waited_ms, "
        "b.pid AS blocker, b.state AS blocker_state, left(b.query, 200) AS blocker_query, "
        "b.xact_start::text AS blocker_xact_start, "
        "extract(epoch FROM clock_timestamp() - b.xact_start) * 1000 AS blocker_xact_ms "
        "FROM pg_stat_activity w CROSS JOIN LATERAL unnest(pg_blocking_pids(w.pid)) AS blocking(pid) "
        "JOIN pg_stat_activity b ON b.pid = blocking.pid WHERE w.wait_event_type = 'Lock'"
    )

    def __init__(self, database_url, raw_path):
        super().__init__(daemon=True)
        self.database_url = database_url
        self.raw = raw_path.open("w")
        self.phase = "setup"
        self.stopped = threading.Event()
        self.summary = {}

    def run(self):
        with psycopg.connect(self.database_url, row_factory=dict_row, autocommit=True) as conn:
            while not self.stopped.is_set():
                rows = conn.execute(self.QUERY).fetchall()
                stamp = round(time.time(), 3)
                for row in rows:
                    row = {key: round(value, 1) if isinstance(value, float) else value for key, value in row.items()}
                    self.raw.write(json.dumps({"t": stamp, "phase": self.phase, **{
                        key: float(value) if hasattr(value, "is_finite") else value for key, value in row.items()
                    }}) + "\n")
                    phase = self.summary.setdefault(self.phase, {"samples": 0, "max_wait_ms": 0, "holders": {}})
                    phase["samples"] += 1
                    phase["max_wait_ms"] = max(phase["max_wait_ms"], float(row["waited_ms"] or 0))
                    holder = phase["holders"].setdefault(
                        (row["blocker_query"] or "").split(" WHERE ")[0][:120],
                        {"waiting_samples": 0, "max_open_ms": 0, "transactions": set(), "states": set()})
                    holder["waiting_samples"] += 1
                    holder["max_open_ms"] = max(holder["max_open_ms"], float(row["blocker_xact_ms"] or 0))
                    holder["transactions"].add((row["blocker"], row["blocker_xact_start"]))
                    holder["states"].add(row["blocker_state"])
                self.stopped.wait(0.05)
        self.raw.close()

    def report(self):
        return {phase: {"waiting_samples": value["samples"], "max_wait_ms": round(value["max_wait_ms"], 1),
                        "holders": sorted(({"last_statement": key, "waiting_samples": item["waiting_samples"],
                                            "max_open_ms": round(item["max_open_ms"], 1),
                                            "transactions": len(item["transactions"]),
                                            "states": sorted(s for s in item["states"] if s)}
                                           for key, item in value["holders"].items()),
                                          key=lambda item: -item["waiting_samples"])[:8]}
                for phase, value in self.summary.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--directory", type=Path, required=True, help="a new, dedicated installation directory")
    parser.add_argument("--database-port", type=int, required=True)
    parser.add_argument("--api-port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--messages", type=int, default=1000)
    parser.add_argument("--notes", type=int, default=100)
    parser.add_argument("--brains", type=int, default=8)
    parser.add_argument("--bulk-to", type=int, default=10000, help="messages in brain 0 after the bulk probe; 0 skips it")
    parser.add_argument("--bulk-batch", type=int, default=100)
    args = parser.parse_args()
    root = args.directory
    if root.exists():
        parser.error("--directory must be a new, dedicated benchmark directory")
    profile = ensure_profile(root, database_engine="embedded", database_port=args.database_port,
                             api_port=args.api_port)
    atexit.register(lambda: desktop.stop(root))
    host.start(root)
    users = [f"bench-user-{index}" for index in range(args.brains)]
    clients = {}

    def client(user):
        if user not in clients:
            clients[user] = host.ready_client(root, user)
        return clients[user]

    sampler = LockSampler(profile.database_url, args.output.with_suffix(".locks.jsonl"))
    sampler.start()
    result = {"machine": machine(profile.database_url), "bars": BARS, "conditions": {
        "fixture": f"{args.messages} keyword messages per brain, {args.brains} brains, {args.notes} notes in brain 0",
        "semantic": "off", "model_calls": 0, "index": "caught up before measuring",
        "excludes": "client start-up (ready_client) and reply generation",
        "rounds": "21 per worker; the first is warm-up and discarded", "service": "one local service",
    }}

    def ingest(user, start, stop, batch, prefix):
        c = client(user)
        scope = c._scope("history", "main")
        for first in range(start, stop, batch):
            events = []
            for i in range(first, min(stop, first + batch)):
                events.append({
                    "source_event_key": f"{prefix}-{i}", "source_revision": 1, "producer_ref": "sdk",
                    "actor_ref": "user", "actor_role": "user", "event_kind": "message",
                    "content": {"media_type": "text/plain", "text": message(i)},
                    "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                    "interpretation_hint": "unknown", "delivery_state": "received", "speech_act_hint": "unknown",
                    "parent_source_event_keys": [],
                })
            c.action("observe", {"idempotency_key": f"{prefix}-{first}", "events": events}, target=scope)

    started = time.perf_counter()
    for user in users:
        ingest(user, 0, args.messages, 50, "fixture")
    for i in range(args.notes):
        client(users[0]).write_note(f"Note {i}: project{i % 50:04d} uses the green folder.", kind="preference")
    deadline = time.monotonic() + 3600
    while True:
        lag = {user: client(user).dashboard()["status"] for user in users}
        if not any(status.get("pending_jobs") or status.get("index_lag") for status in lag.values()):
            break
        if time.monotonic() > deadline:
            raise RuntimeError(f"Index backlog: {lag}")
        time.sleep(2)
    result["fixture_seconds"] = round(time.perf_counter() - started, 1)
    for user in users:
        client(user)  # Every worker's client is ready before any timing starts.

    def recall(user, round_index, worker):
        c = client(user) if worker == 0 else worker_clients[(user, worker)]
        begin = time.perf_counter()
        context = host.recall_context(c, QUERIES[round_index % len(QUERIES)], current_conversation="benchmark")
        return (time.perf_counter() - begin) * 1000, bool(context)

    worker_clients = {}
    for worker in range(1, 8):
        for user in users[:1]:
            worker_clients[(user, worker)] = host.ready_client(root, user)

    def run_worker(user, worker):
        samples = [recall(user, round_index, worker) for round_index in range(21)]
        return samples[1:]

    def phase(name, assignments):
        sampler.phase = name
        with ThreadPoolExecutor(max_workers=len(assignments)) as executor:
            outcome = list(executor.map(lambda pair: run_worker(*pair), assignments))
        samples = [value for worker in outcome for value in worker]
        result[name] = {**stats([value for value, _ in samples]),
                        "nonempty": sum(found for _, found in samples),
                        "raw_ms": [[round(value, 2) for value, _ in worker] for worker in outcome]}
        print(json.dumps({name: {key: value for key, value in result[name].items() if key != "raw_ms"}}), flush=True)

    phase("serial", [(users[0], 0)])
    phase("one_brain_8_concurrent", [(users[0], worker) for worker in range(8)])
    phase("eight_brains_8_concurrent", [(user, 0) for user in users])

    def map_sample(c, nodes):
        begin = time.perf_counter()
        try:
            c.memory_map(max_nodes=nodes)
            return (time.perf_counter() - begin) * 1000, None
        except Exception as error:  # The service answers 503 "Memory is busy updating" on a lock timeout.
            return (time.perf_counter() - begin) * 1000, f"{type(error).__name__}: {str(error)[:160]}"

    for nodes in (200, 500):
        sampler.phase = f"map_{nodes}"
        samples = [map_sample(client(users[0]), nodes) for _ in range(21)][1:]
        result[f"map_{nodes}"] = {**stats([value for value, error in samples if error is None]),
                                  "errors": [error for _, error in samples if error],
                                  "raw_ms": [round(value, 2) for value, _ in samples]}
        print(json.dumps({f"map_{nodes}": {k: v for k, v in result[f"map_{nodes}"].items() if k != "raw_ms"}}),
              flush=True)

    if args.bulk_to > args.messages:
        sampler.phase = "bulk"
        during, stop = [], threading.Event()
        reader = host.ready_client(root, users[0])

        def watch():
            while not stop.is_set():
                during.append(map_sample(reader, 200))
                stop.wait(0.5)

        thread = threading.Thread(target=watch, daemon=True)
        thread.start()
        begin = time.perf_counter()
        ingest(users[0], args.messages, args.bulk_to, args.bulk_batch, "bulk")
        bulk_seconds = time.perf_counter() - begin
        stop.set()
        thread.join()
        sampler.phase = "after_bulk"
        after = [map_sample(reader, 200) for _ in range(10)]
        recalls = [recall(users[0], i, 0) for i in range(10)]
        result["busy_after_bulk"] = {
            "bulk_messages": args.bulk_to - args.messages, "batch": args.bulk_batch,
            "bulk_seconds": round(bulk_seconds, 1),
            "map_during_bulk": {**stats([v for v, e in during if e is None]), "requests": len(during),
                                "errors": [e for _, e in during if e]},
            "first_map_after_bulk": {"ms": round(after[0][0], 2), "error": after[0][1]},
            "map_after_bulk": {**stats([v for v, e in after if e is None]), "errors": [e for _, e in after if e]},
            "recall_after_bulk": stats([v for v, _ in recalls]),
        }
        print(json.dumps({"busy_after_bulk": result["busy_after_bulk"]}), flush=True)
    sampler.stopped.set()
    sampler.join()
    result["lock_waits"] = sampler.report()
    result["met"] = {
        "serial_p95_ms": result["serial"]["p95_ms"] < BARS["serial_p95_ms"],
        "one_brain_8_concurrent_p95_ms": result["one_brain_8_concurrent"]["p95_ms"]
        <= BARS["one_brain_8_concurrent_p95_ms"],
        "eight_brains_8_concurrent_p95_ms": result["eight_brains_8_concurrent"]["p95_ms"]
        <= BARS["eight_brains_8_concurrent_p95_ms"],
    }
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({key: result[key] for key in ("machine", "met", "lock_waits")}, indent=2), flush=True)
    return 0 if all(result["met"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
