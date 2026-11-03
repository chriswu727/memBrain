"""Measure synthetic local brain-map requests during indexing, without model calls or retries.

Usage: uv run python evaluations/maturity-map-benchmark.py NEW_OUTPUT_DIRECTORY
Every request, including the first failed one, is retained in report.json. This measures map HTTP latency, not
whole-hook latency, rendering, semantic recall, or a capacity guarantee. The isolated installation is stopped on exit.
"""
import argparse
import json
import math
import os
import platform
import socket
import statistics
import time
from pathlib import Path

from membrain import desktop, host
from membrain.build_identity import BUILD_ID
from membrain.client import MemoryClient
from membrain.helpers import uid
from membrain.local_profile import ensure_profile


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def measure(out, counts, notes, samples):
    out.mkdir(parents=True, exist_ok=False)
    report = {"build_id": BUILD_ID, "platform": platform.platform(), "completed": False, "stopped": False,
              "scope": "Local HTTP map with synthetic messages and notes, background indexing active, no model calls",
              "percentile": "nearest rank: sorted samples[ceil(0.95*n)-1]", "requests": [], "summaries": []}

    def save():
        pending = out / "report.json.tmp"
        pending.write_text(json.dumps(report, indent=2) + "\n")
        pending.replace(out / "report.json")

    directory = out / "installation"
    save()
    try:
        os.environ.update(MEMBRAIN_SEMANTIC="0", PYTHON_DOTENV_DISABLED="1")
        profile = ensure_profile(directory, api_port=free_port(), database_port=free_port(), database_engine="embedded")
        assert profile.cognition is None
        host.start(directory)
        with MemoryClient(profile.base_url, profile.api_key, profile.brain_id, timeout=120) as client:
            sources, have = [], 0
            for count in counts:
                for start in range(have, count, 500):
                    events = [{"source_event_key": f"message-{index}", "source_revision": 1,
                               "producer_ref": "map-benchmark", "actor_ref": "user", "actor_role": "user",
                               "event_kind": "message", "content": {"media_type": "text/plain",
                               "text": f"Fictional memory {index}: Mira and Theo plan a planetarium visit."},
                               "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                               "interpretation_hint": "unknown", "delivery_state": "received",
                               "parent_source_event_keys": []} for index in range(start, min(start + 500, count))]
                    observed = client.action("observe", {"idempotency_key": uid(), "events": events},
                                             conversation_id="synthetic-map", branch_id="main")
                    if observed["outcome"] != "completed":
                        raise RuntimeError(f"ingestion failed: {observed}")
                    sources.extend(observed["result"]["accepted_event_ids"])
                if have == 0:
                    for index in range(notes):
                        client.write_note(f"Fictional plan {index}: visit the planetarium.", kind="plan",
                                          status="intended", source_event_ids=sources[index * 5:index * 5 + 5],
                                          sensitive=index % 10 == 0)
                have = count
                for nodes, edges in ((200, 400), (500, 1000)):
                    timings = []
                    for number in range(samples):
                        request = {"messages": count, "notes": notes, "max_nodes": nodes, "max_edges": edges,
                                   "sample": number, "ok": False}
                        began = time.perf_counter()
                        try:
                            value = client.memory_map(max_nodes=nodes, max_edges=edges)
                            if len(value["nodes"]) > nodes or len(value["edges"]) > edges:
                                raise RuntimeError("map exceeded its requested bounds")
                            request.update(ok=True, nodes=len(value["nodes"]), edges=len(value["edges"]))
                        except Exception as error:
                            request.update(error_type=type(error).__name__, error=str(error)[:1000],
                                           response=getattr(getattr(error, "response", None), "text", "")[:1000])
                            raise
                        finally:
                            request["milliseconds"] = round((time.perf_counter() - began) * 1000, 3)
                            report["requests"].append(request)
                            save()
                        timings.append(request["milliseconds"])
                    summary = {"messages": count, "notes": notes, "max_nodes": nodes, "samples": samples,
                               "median_ms": statistics.median(timings),
                               "p95_ms": sorted(timings)[math.ceil(0.95 * samples) - 1], "max_ms": max(timings)}
                    report["summaries"].append(summary)
                    save()
                    print(json.dumps(summary), flush=True)
        report["completed"] = True
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)[:1000]}
    finally:
        try:
            if (directory / "profile.json").exists():
                desktop.stop(directory)
            report["stopped"] = True
        except Exception as error:
            report["cleanup_failure"] = {"type": type(error).__name__, "message": str(error)[:1000]}
        save()
    return 0 if report["completed"] and report["stopped"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--messages", type=int, nargs="+", default=[1000, 10000])
    parser.add_argument("--notes", type=int, default=100)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    if (not args.messages or any(value < 1 for value in args.messages)
            or args.messages != sorted(set(args.messages)) or args.notes < 0 or args.samples < 1):
        parser.error("message counts must be positive and increasing; notes nonnegative; samples positive")
    raise SystemExit(measure(args.output.resolve(), args.messages, args.notes, args.samples))
