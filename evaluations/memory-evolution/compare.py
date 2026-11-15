"""Model-free, paired diagnostic: raw-record recall, notes, and notes plus scripted host cues.

All arms use the SAME memBrain recall endpoint, source, corpus, keyword-only configuration, sequential concurrency,
and final character cap. This isolates enrichment; it is not an independent BM25 implementation or an answer test.
The note arm reads its notes on every query (no session cache). Start-up and ingestion are outside query timing.
First queries are reported separately from warm repetitions; they do not imply a cleared OS/database cache.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import socket
import statistics
import subprocess
import time
from pathlib import Path

import psycopg
from psycopg import sql

from membrain import desktop, embedded_database, host
from membrain.client import default_budget, recalled_context
from membrain.local_profile import ensure_profile, load_profile
from membrain.notes import list_notes, render_notes, save_note

ARMS = ("raw", "notes", "notes_and_cues")
SOURCE = Path(__file__).resolve().parents[2]


def hashes():
    paths = sorted((SOURCE / "src").rglob("*")) + sorted((SOURCE / "migrations").glob("*.sql"))
    return {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def distribution(values):
    ordered = sorted(values)
    return {"n": len(values), "median": statistics.median(values),
            "p95": ordered[max(0, math.ceil(len(ordered) * .95) - 1)]}


def row_storage(profile, brain_id):
    # Per-brain logical tuple sizes, not disk allocation/index/TOAST or a production capacity estimate.
    result = {}
    with psycopg.connect(profile.migration_database_url) as conn:
        for table in ("memory_events", "memory_event_dependencies", "memory_message_cues", "memory_cue_progress"):
            if conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] is None:
                continue
            count, size = conn.execute(sql.SQL(
                "SELECT count(*),COALESCE(sum(pg_column_size(t)),0) FROM {} t WHERE brain_id=%s"
            ).format(sql.Identifier(table)), (brain_id,)).fetchone()
            result[table] = {"rows": count, "logical_tuple_bytes": size}
    return result


def run(out, repeats, cap):
    out.mkdir(parents=True, exist_ok=False)
    if os.statvfs(out).f_bavail * os.statvfs(out).f_frsize < 2 * 1024**3:
        raise RuntimeError("At least 2 GiB free is required.")
    os.environ.update(PYTHON_DOTENV_DISABLED="1", MEMBRAIN_SEMANTIC="0")
    os.environ.pop("MEMBRAIN_EVALUATION_CLOCK", None)
    fixture_path = Path(__file__).with_name("fixture.json")
    fixture = json.loads(fixture_path.read_text())
    snapshot = hashes()
    directory = out / "installation"
    ensure_profile(directory, database_engine="embedded", api_port=free_port(), database_port=free_port())
    report = {"schema": 1, "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip(),
              "runtime_tree_sha256": hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
              "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "environment": {"platform": platform.platform(), "python": platform.python_version(),
                              "semantic": False, "concurrency": 1, "context_cap_characters": cap,
                              "warm_repeats_per_query": repeats},
              "model_calls": 0, "arms": {}, "completed": False}
    (out / "source-diff.patch").write_text(subprocess.check_output(["git", "diff", "HEAD"], cwd=SOURCE, text=True))
    rows = []
    try:
        start = time.perf_counter()
        host.start(directory)
        report["service_start_ms"] = (time.perf_counter() - start) * 1000
        profile = load_profile(directory)
        with psycopg.connect(profile.migration_database_url) as conn:
            report["environment"]["postgresql"] = conn.execute("SELECT version()").fetchone()[0]
        with host.ready_client(directory) as client:
            for arm in ARMS:
                client.brain_id = client.create_brain("Synthetic evolution " + arm)["id"]
                ids = {}
                for index, item in enumerate(fixture["facts"] + [{"key": f"noise-{i}", "text": text}
                            for i, text in enumerate(fixture["distractors"])]):
                    result = client.observe(item["text"], conversation_id=f"session-{index // 4}", branch_id="main",
                                            source_event_key=item["key"], producer_ref="evolution-fixture")
                    ids[item["key"]] = result["result"]["accepted_event_ids"][0]
                start = time.perf_counter()
                if arm != "raw":
                    for fact in fixture["facts"]:
                        save_note(client, fact["note"], kind=fact["kind"], source_event_ids=[ids[fact["key"]]])
                notes_ms = (time.perf_counter() - start) * 1000 if arm != "raw" else 0
                cue_input, cue_output, cue_ms = 0, 0, 0
                if arm == "notes_and_cues":
                    while True:
                        state = {}
                        start = time.perf_counter()
                        batch = host.consolidate(client, handed_out=state)
                        if "error" in batch:
                            raise RuntimeError(batch)
                        if not batch["messages"]:
                            break
                        cue_input += len(json.dumps(batch, ensure_ascii=False))
                        by_text = {fact["text"]: fact["cues"] for fact in fixture["facts"]}
                        cues = [{"id": message["id"], "cues": by_text[message["text"]]} for message in batch["messages"]
                                if message["text"] in by_text]
                        cue_output += len(json.dumps(cues, ensure_ascii=False))
                        saved = host.consolidate(client, cues=cues, handed_out=state)
                        if "error" in saved:
                            raise RuntimeError(saved)
                        cue_ms += (time.perf_counter() - start) * 1000
                report["arms"][arm] = {"brain_id": client.brain_id, "storage": row_storage(profile, client.brain_id),
                                      "enrichment": {"notes_write_ms": notes_ms, "cue_batch_read_write_ms": cue_ms,
                                      "cue_input_characters": cue_input, "cue_output_characters": cue_output,
                                      "model_generation_cost": "not measured; scripted fixtures, zero model calls"}}
            # Rotate the arm order each repetition to avoid always assigning first position to one arm.
            rng = random.Random(20261114)
            for repeat in range(repeats + 1):
                order = list(ARMS)
                rng.shuffle(order)
                for fact in fixture["facts"]:
                    for arm in order:
                        client.brain_id = report["arms"][arm]["brain_id"]
                        start = time.perf_counter()
                        prefix = (render_notes(list_notes(client), budget=cap // 3, affect=False) or "") if arm != "raw" else ""
                        prefix = prefix[:cap]
                        response = client.recall(fact["query"], budget={**default_budget(600), "max_embedding_calls": 0},
                                                 ranking="relevance")
                        context = prefix + recalled_context(response)[:max(0, cap - len(prefix))]
                        elapsed = (time.perf_counter() - start) * 1000
                        rows.append({"arm": arm, "query": fact["key"], "phase": "first" if repeat == 0 else "warm",
                                     "repeat": repeat, "latency_ms": elapsed, "context_characters": len(context),
                                     **({"context": context} if repeat == 0 else {}),
                                     "evidence_present": all(word.casefold() in context.casefold() for word in fact["evidence"])})
            for arm in ARMS:
                for phase in ("first", "warm"):
                    selected = [row for row in rows if row["arm"] == arm and row["phase"] == phase]
                    report["arms"][arm][phase] = {"evidence_present": sum(row["evidence_present"] for row in selected),
                                                   "queries": len(selected),
                                                   "latency_ms": distribution([row["latency_ms"] for row in selected]),
                                                   "context_characters": distribution([row["context_characters"] for row in selected])}
            report["completed"] = True
    finally:
        desktop.stop(directory)
        report["database_stopped"] = not embedded_database.running(load_profile(directory))
        report["runtime_unchanged"] = snapshot == hashes()
        (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        (out / "queries.json").write_text(json.dumps(rows, indent=2) + "\n")
    assert report["runtime_unchanged"] and report["database_stopped"]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="A new disposable output directory; never an existing profile.")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--cap", type=int, default=2400)
    args = parser.parse_args()
    if args.repeats < 1 or args.cap < 1000:
        parser.error("Use at least one warm repetition and a 1,000-character context cap.")
    run(args.out.resolve(), args.repeats, args.cap)
