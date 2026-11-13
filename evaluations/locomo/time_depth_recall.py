"""LoCoMo evidence recall with memories at their real ages: what does age weighting do to recall? No model call.

Every earlier LoCoMo run stored a whole history within minutes, so the age weight in ranking
(``dynamics.rank_weight``, applied in ``candidates.collect_candidates``) was the same for every message and could not
matter. This harness stores each conversation as the plugin path stores it (``run_locomo.ingest``: one conversation
per session, every turn a ``user`` message with its date and speaker prefix, delivered with ``host.deliver``), but
with every message recorded at its session's date, and then asks every question at two "now" times: one day after
the conversation's last session and 365 days after it.

How the dates are applied: the supported scenario clock (``src/membrain/evaluation_clock.py``). Each new
installation is marked as a disposable evaluation profile, ``MEMBRAIN_EVALUATION_CLOCK`` names the clock file in it,
and the service the plugin path starts (a separate process) reads ``helpers.now()`` from that file. Before each
session is delivered the clock is advanced to the session's date and time (read as UTC); the clock then runs at wall
speed, so the turns of a session are seconds apart. The service stamps each event's ``system_time.recorded_at``
from that clock, and each captured statement copies the event's ``system_time`` (``cognition`` capture), which is
the time ``dynamics.access_state`` measures age from. After storing, the recorded times are read back through the
timeline and compared with the session dates (``events-<conversation>.json``, ``dates-check.json``).

Questions are asked with the service inside this process (``recall_processes=0``, as in ``block_sweep.py``) so that
settings can be varied between requests without changing any source file. The same scenario clock is enabled in
this process and advanced to the asking time before each phase; ``helpers.now()`` at each question is recorded.

Arms, for every question (categories 1-4) and each "now":

- ``auto``: the automatic recall block as shipped, ``host.recall_context(client, question,
  current_conversation=..., limit=CONTEXT_CHARACTERS)`` (what ``host.prompt_context`` adds for a new session with
  no notes and no earlier prompt; ``prompt_context`` would subtract the length of its notices from the limit).
- ``auto_flat``: the same with the age weight off: ``rank_weight`` returns 1.0 for every candidate (patched in
  ``candidates`` and ``dynamics`` in this process only).
- ``tool``: a deliberate search as the plugin's ``memory_recall`` tool makes it without ``my_replies``:
  ``host.recall_context(client, scrub(query), replies=False)``, the question as the query.
- ``tool_replies``: the same tool with ``my_replies`` set: the request is made with intent ``episode``, which
  ``candidates`` treats as direct (weight 1.0).
- ``searches`` / ``searches_flat``: where the host model searched in the 2026-11-11 plain answer run (runtime
  ``933f4d8``, ``answers-plain-all.jsonl.gz``), its recorded queries are replayed through the ``tool`` path, as
  shipped and with the weight off. Replaying recorded queries calls no model.

For ``auto`` the weight given to every candidate statement is recorded (with its tier and recorded time), so the mean
weight of evidence statements can be compared with that of the other candidates.

Usage::

    python evaluations/locomo/time_depth_recall.py --data locomo10.json --out RUN_DIR \
        --model-cache MODEL_DIR [--conversations 0,1,2] [--searches answers-plain-all.jsonl.gz]
    python evaluations/locomo/time_depth_recall.py --data locomo10.json --out RUN_DIR --report
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import gzip
import json
import os
import socket
import statistics
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_recall import evidence_ids, needles, present, stored_turns  # noqa: E402
from run_locomo import (  # noqa: E402
    install_model,
    log,
    questions,
    sessions,
    start,
    turn_text,
    wait_for_embeddings,
)

NOWS = (("+1d", 1), ("+365d", 365))
ARMS = ("auto", "auto_flat", "tool", "tool_replies")
SESSION_FORMAT = "%I:%M %p on %d %B, %Y"
DAY = 86400.0


def session_time(text: str) -> dt.datetime:
    """A LoCoMo session date ("1:56 pm on 8 May, 2023"), read as UTC."""
    return dt.datetime.strptime(text, SESSION_FORMAT).replace(tzinfo=dt.UTC)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.UTC)


# Storing ------------------------------------------------------------------------------------------------------------

def store(sample: dict, directory: Path, cache: Path) -> dict:
    """Store every turn at its session's date as the plugin path stores it. Idempotent; returns the event map."""
    from membrain import desktop, evaluation_clock, host
    from membrain.embedded_database import default_engine
    from membrain.local_profile import ensure_profile

    events_path = directory / "events.json"
    if (directory / "ingested.json").exists() and events_path.exists():
        return json.loads(events_path.read_text(encoding="utf-8"))
    dated = [(number, date, session_time(date), turns) for number, date, turns in sessions(sample)]
    if any(a[2] >= b[2] for a, b in zip(dated, dated[1:])):
        raise SystemExit(f"{sample['sample_id']}: sessions are not in date order")
    if not (directory / "profile.json").exists():
        directory.mkdir(parents=True, exist_ok=True)
        ensure_profile(directory, api_port=free_port(), database_port=free_port(), database_engine=default_engine())
    host.ensure_installation(directory)
    evaluation_clock.mark_disposable(directory)
    evaluation_clock.advance(directory, dated[0][2], run=directory.name)
    os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
    evaluation_clock.enable(directory)
    install_model(directory, cache)
    try:
        start(directory)
        if "evaluation_clock_enabled" not in (directory / "service.log").read_text(encoding="utf-8"):
            raise SystemExit("the service did not enable the scenario clock")
        stored = 0
        with host.ready_client(directory) as client:
            for number, date, moment, turns in dated:
                in_force = evaluation_clock.advance(directory, moment, run=directory.name)
                if in_force > moment + dt.timedelta(minutes=10):
                    log("warning: clock already past session", number, in_force.isoformat())
                for turn in turns:
                    session = f"locomo-{sample['sample_id']}-s{number}"
                    record = host.message_record(session, "user", turn_text(date, turn),
                                                 turn_id=turn["dia_id"], producer="locomo-ingest")
                    stored += host.deliver(directory, client, record)
        host.pause(directory)  # Questions must never become memories.
        status = wait_for_embeddings(directory)
        events = read_back(sample, directory)
        events_path.write_text(json.dumps(events), encoding="utf-8")
        (directory / "ingested.json").write_text(json.dumps({
            "messages": stored, "semantic": True, "candidate_index": status.get("candidate_index"),
            "dated": "session dates via the evaluation clock"}), encoding="utf-8")
        return events
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
        evaluation_clock.disable()


def read_back(sample: dict, directory: Path) -> dict:
    """``event_id`` to ``dia_id``, recorded time and session date, read back through the timeline."""
    from membrain import host

    identify = needles(sample)
    events = {}
    with host.ready_client(directory) as client:
        for number, date, turns in sessions(sample):
            session = f"locomo-{sample['sample_id']}-s{number}"
            found = client.timeline(roles=("user",), conversation_id=session, max_characters=200_000,
                                    max_item_characters=20_000, limit=1000)
            by_needle = {identify[turn["dia_id"]]: turn["dia_id"] for turn in turns}
            for item in found.get("items", []):
                flat = " ".join((item.get("text") or "").split())
                matches = [dia for needle, dia in by_needle.items() if flat.startswith(needle)]
                if len(matches) == 1:
                    events[item["event_id"]] = {"dia_id": matches[0], "recorded_at": item.get("recorded_at"),
                                                "session": number, "session_date": session_time(date).isoformat()}
    return events


# Asking -------------------------------------------------------------------------------------------------------------

class Weights:
    """Wraps ``access_state`` and ``rank_weight`` where ``candidates`` calls them: records each candidate's weight,
    and with ``flat`` makes every weight 1.0 (also for the unindexed-tail path in ``cognition``)."""

    def __init__(self):
        from membrain import candidates, dynamics

        self.candidates, self.dynamics = candidates, dynamics
        self.original_state, self.original_weight = dynamics.access_state, dynamics.rank_weight
        self.flat, self.rows, self.last = False, None, None
        candidates.access_state = self.access_state
        candidates.rank_weight = self.rank_weight
        dynamics.rank_weight = self.tail_weight

    def restore(self):
        self.candidates.access_state, self.candidates.rank_weight = self.original_state, self.original_weight
        self.dynamics.rank_weight = self.original_weight

    def access_state(self, memory, usage, *, at, policy=None):
        state = self.original_state(memory, usage, at=at, **({"policy": policy} if policy else {}))
        self.last = (memory, state)
        return state

    def rank_weight(self, state, *, direct=False, policy=None):
        weight = 1.0 if self.flat else self.original_weight(state, direct=direct,
                                                            **({"policy": policy} if policy else {}))
        if self.rows is not None and self.last is not None and self.last[1] is state:
            memory = self.last[0]
            self.rows.append({"events": [ref["event_id"] for ref in memory.get("evidence_refs", [])],
                              "recorded_at": memory["system_time"]["recorded_at"], "weight": weight,
                              "tier": state["tier"], "activation": state["activation"], "direct": direct})
        return weight

    def tail_weight(self, state, *, direct=False, policy=None):
        return 1.0 if self.flat else self.original_weight(state, direct=direct,
                                                          **({"policy": policy} if policy else {}))


def recorded_searches(path: str | None) -> dict[str, list[str]]:
    if not path:
        return {}
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    return {row["id"]: [query for query in row.get("searches") or [] if isinstance(query, str) and query.strip()]
            for row in rows if row.get("searches")}


def candidate_summary(rows: list[dict], events: dict, wanted: list[str], at: dt.datetime) -> dict:
    evidence, other = [], []
    for row in rows:
        turns = {events[event]["dia_id"] for event in row["events"] if event in events}
        age = (at - stamp(row["recorded_at"])).total_seconds() / DAY
        entry = {"weight": round(row["weight"], 6), "tier": row["tier"], "age_days": round(age, 3)}
        if turns & set(wanted):
            evidence.append({**entry, "turns": sorted(turns & set(wanted))})
        else:
            other.append(entry)
    return {"candidates": len(rows), "evidence": evidence, "other_count": len(other),
            "other_mean_weight": round(statistics.fmean(e["weight"] for e in other), 6) if other else None,
            "other_mean_age": round(statistics.fmean(e["age_days"] for e in other), 3) if other else None,
            "other_tiers": {tier: sum(e["tier"] == tier for e in other) for tier in ("everyday", "cue", "deep")}}


def ask(sample: dict, directory: Path, events: dict, out: Path, searches: dict) -> None:
    import uvicorn

    from membrain import desktop, embedded_database, evaluation_clock, helpers, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.local_profile import load_profile

    sid = sample["sample_id"]
    paths = {label: out / f"recall-{sid}-{label}.jsonl" for label, _ in NOWS}
    done = {label: {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()}
            if path.exists() else set() for label, path in paths.items()}
    turns, identify = stored_turns(sample), needles(sample)
    todo = [(qid, qa) for qid, qa in questions(sample, {1, 2, 3, 4}) if evidence_ids(qa, turns)]
    if all(qid in done[label] for label, _ in NOWS for qid, _ in todo):
        return
    turn_time = {info["dia_id"]: info["recorded_at"] for info in events.values()}
    last = max(session_time(date) for _, date, _ in sessions(sample))
    os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
    evaluation_clock.enable(directory)
    profile = load_profile(directory)
    desktop._prepare_database(profile)
    settings = dataclasses.replace(profile.settings(), recall_processes=0)
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                           log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    weights = Weights()
    try:
        while not server.started:
            time.sleep(0.1)
        with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
            for label, offset in NOWS:
                evaluation_clock.advance(directory, last + dt.timedelta(days=offset), run=directory.name)
                for qid, qa in todo:
                    if qid in done[label]:
                        continue
                    wanted = evidence_ids(qa, turns)
                    now = helpers.now()
                    at = stamp(now)
                    row = {"id": qid, "category": qa["category"], "evidence": wanted, "now": now,
                           "evidence_age_days": {dia: round((at - stamp(turn_time[dia])).total_seconds() / DAY, 3)
                                                 for dia in wanted if dia in turn_time}}

                    def measure(name, query, **options):
                        started = time.perf_counter()
                        context = host.recall_context(client, query, **options) or ""
                        row[name] = present(context, wanted, identify)
                        row[name + "_chars"] = len(context)
                        row[name + "_ms"] = round((time.perf_counter() - started) * 1000, 1)

                    weights.flat, weights.rows = False, []
                    measure("auto", qa["question"], current_conversation=f"time-depth-{qid}")
                    row["weights"] = candidate_summary(weights.rows, events, wanted, at)
                    weights.rows = None
                    weights.flat = True
                    measure("auto_flat", qa["question"], current_conversation=f"time-depth-{qid}")
                    weights.flat = False
                    measure("tool", host.scrub(qa["question"]), replies=False)
                    measure("tool_replies", host.scrub(qa["question"]), replies=True)
                    measure("tool_deliberate", host.scrub(qa["question"]), deliberate=True)
                    if qid in searches:
                        for name, flat in (("searches", False), ("searches_flat", True)):
                            weights.flat, found = flat, set()
                            for query in searches[qid]:
                                context = host.recall_context(client, host.scrub(query), replies=False) or ""
                                found.update(present(context, wanted, identify))
                            row[name] = [dia for dia in wanted if dia in found]
                        weights.flat = False
                        row["search_queries"] = searches[qid]
                    with paths[label].open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(row) + "\n")
                log(sid, label, "done")
    finally:
        weights.restore()
        server.should_exit = True
        thread.join(timeout=30)
        embedded_database.stop(profile)
        evaluation_clock.disable()


# Report -------------------------------------------------------------------------------------------------------------

def buckets(offset: int) -> list[tuple[str, float, float]]:
    base = 0 if offset == 1 else 365
    edges = [(0, 30), (30, 90), (90, 180), (180, 10_000)]
    names = ["under 30 d", "30-90 d", "90-180 d", "over 180 d"] if base == 0 else [
        "365-395 d", "395-455 d", "455-545 d", "over 545 d"]
    return [(name, base + low, base + high) for name, (low, high) in zip(names, edges)]


def bucket_of(age: float, offset: int) -> str:
    for name, low, high in buckets(offset):
        if low <= age < high:
            return name
    return buckets(offset)[0][0]  # An age just under the base (the clock runs from the session time).


def rates(rows: list[dict], arm: str) -> tuple[int, float, float]:
    rows = [row for row in rows if arm in row]
    if not rows:
        return 0, float("nan"), float("nan")
    full = sum(len(row[arm]) == len(row["evidence"]) for row in rows) / len(rows)
    share = statistics.fmean(len(row[arm]) / len(row["evidence"]) for row in rows)
    return len(rows), full, share


def report(args) -> str:
    out = Path(args.out)
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    selected = [data[int(index)] for index in args.conversations.split(",")]
    lines = []
    summary = {}

    def table(title, groups, arms):
        lines.append(f"\n{title}")
        lines.append(f"{'':22}{'n':>5}" + "".join(f"{arm + ' all':>20}{'share':>8}" for arm in arms))
        for name, items in groups:
            if not items:
                continue
            cells, count = "", 0
            for arm in arms:
                n, full, share = rates(items, arm)
                count = max(count, n)
                cells += f"{full:>20.1%}{share:>8.1%}"
                summary.setdefault(title, {}).setdefault(name, {})[arm] = {"n": n, "all": round(full, 4),
                                                                           "share": round(share, 4)}
            lines.append(f"{name:22}{count:>5}{cells}")

    for label, offset in NOWS:
        rows = []
        for sample in selected:
            path = out / f"recall-{sample['sample_id']}-{label}.jsonl"
            if path.exists():
                rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if not rows:
            continue
        lines.append(f"\n===== now = last session {label} ({len(rows)} questions) =====")
        groups = [("all", rows), ("one evidence turn", [r for r in rows if len(r["evidence"]) == 1]),
                  ("several", [r for r in rows if len(r["evidence"]) > 1])]
        for name, low, high in buckets(offset):
            groups.append((f"oldest ev {name}", [r for r in rows if r["evidence_age_days"] and
                                                 bucket_of(max(r["evidence_age_days"].values()), offset) == name]))
        table(f"{label}: questions (all evidence shown / mean share shown)", groups, ARMS)
        # Evidence turns by their own age.
        lines.append(f"\n{label}: evidence turns shown, by the turn's age")
        lines.append(f"{'':22}{'turns':>7}" + "".join(f"{arm:>14}" for arm in ARMS))
        for name, _, _ in buckets(offset):
            counts = defaultdict(int)
            total = 0
            for row in rows:
                for dia, age in row["evidence_age_days"].items():
                    if bucket_of(age, offset) != name:
                        continue
                    total += 1
                    for arm in ARMS:
                        counts[arm] += dia in row[arm]
            if total:
                lines.append(f"{name:22}{total:>7}" + "".join(f"{counts[arm] / total:>14.1%}" for arm in ARMS))
                summary.setdefault(f"{label}: turns by age", {})[name] = {
                    "turns": total, **{arm: round(counts[arm] / total, 4) for arm in ARMS}}
        paired = {"auto only": sum(len(r["auto"]) == len(r["evidence"]) > len(r["auto_flat"]) for r in rows),
                  "flat only": sum(len(r["auto_flat"]) == len(r["evidence"]) > len(r["auto"]) for r in rows),
                  "auto != tool": sum(set(r["auto"]) != set(r["tool"]) for r in rows)}
        lines.append(f"\n{label}: questions with all evidence under one arm only: {paired}")
        summary[f"{label}: paired"] = paired
        searched = [r for r in rows if "searches" in r]
        if searched:
            for r in searched:
                r["auto+searches"] = sorted(set(r["auto"]) | set(r["searches"]))
                r["flat+searches_flat"] = sorted(set(r["auto_flat"]) | set(r["searches_flat"]))
            table(f"{label}: questions where the host searched in the recorded run",
                  [("searched", searched)],
                  ("auto", "auto_flat", "searches", "searches_flat", "auto+searches", "flat+searches_flat"))
        # Weights of candidates.
        evidence_weights = [e["weight"] for r in rows for e in r["weights"]["evidence"]]
        other_means = [r["weights"]["other_mean_weight"] for r in rows if r["weights"]["other_mean_weight"]]
        paired_rows = [r for r in rows if r["weights"]["evidence"] and r["weights"]["other_mean_weight"]]
        ratio = [statistics.fmean(e["weight"] for e in r["weights"]["evidence"]) / r["weights"]["other_mean_weight"]
                 for r in paired_rows]
        tiers = defaultdict(int)
        for r in rows:
            for e in r["weights"]["evidence"]:
                tiers[e["tier"]] += 1
        other_tiers = defaultdict(int)
        for r in rows:
            for tier, count in r["weights"]["other_tiers"].items():
                other_tiers[tier] += count
        weight_line = {
            "candidates per question": round(statistics.fmean(r["weights"]["candidates"] for r in rows), 1),
            "evidence statements among candidates": len(evidence_weights),
            "questions with evidence among candidates": len(paired_rows),
            "mean weight, evidence statements": round(statistics.fmean(evidence_weights), 4) if evidence_weights else None,
            "mean weight, other candidates (per-question means)": round(statistics.fmean(other_means), 4),
            "per-question ratio evidence/other, mean": round(statistics.fmean(ratio), 4) if ratio else None,
            "per-question ratio, median": round(statistics.median(ratio), 4) if ratio else None,
            "evidence tiers": dict(tiers), "other tiers": dict(other_tiers),
            "weight range, all evidence": [min(evidence_weights), max(evidence_weights)] if evidence_weights else None,
        }
        lines.append(f"\n{label}: rank weights in the auto candidate lists")
        for key, value in weight_line.items():
            lines.append(f"  {key}: {value}")
        summary[f"{label}: weights"] = weight_line
        ms = sorted(r["auto_ms"] for r in rows)
        lines.append(f"\n{label}: auto block p50 {ms[len(ms) // 2]} ms, mean characters "
                     f"{round(statistics.fmean(r['auto_chars'] for r in rows))} (flat "
                     f"{round(statistics.fmean(r['auto_flat_chars'] for r in rows))})")
    text = "\n".join(lines)
    (out / "report.txt").write_text(text + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return text


def check_dates(selected: list[dict], out: Path) -> dict:
    """Recorded time minus session date for every stored turn, per conversation."""
    result = {}
    for sample in selected:
        path = out / f"brain-{sample['sample_id']}" / "events.json"
        if not path.exists():
            continue
        events = json.loads(path.read_text(encoding="utf-8"))
        offsets = [(stamp(info["recorded_at"]) - stamp(info["session_date"])).total_seconds()
                   for info in events.values()]
        expected = sum(len(turns) for _, _, turns in sessions(sample))
        sample_rows = sorted(events.values(), key=lambda info: (info["session"], info["recorded_at"]))
        result[sample["sample_id"]] = {
            "turns": expected, "events_matched": len(events),
            "seconds_after_session_date": {"min": round(min(offsets), 1), "max": round(max(offsets), 1),
                                           "median": round(statistics.median(offsets), 1)},
            "examples": [{key: info[key] for key in ("dia_id", "session_date", "recorded_at")}
                         for info in (sample_rows[0], sample_rows[len(sample_rows) // 2], sample_rows[-1])]}
    (out / "dates-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", required=True, help="locomo10.json from snap-research/locomo")
    parser.add_argument("--out", required=True, help="A new run directory (brains are kept there)")
    parser.add_argument("--model-cache", default="", help="Directory holding the pinned embedding model")
    parser.add_argument("--conversations", default="0,1,2", help="Comma-separated indexes; development split")
    parser.add_argument("--searches", default="", help="Answer-run JSONL with the host's recorded recall queries")
    parser.add_argument("--report", action="store_true", help="Only summarize existing results")
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    selected = [data[int(index)] for index in args.conversations.split(",")]
    out = Path(args.out)
    if not args.report:
        if not args.model_cache:
            parser.error("--model-cache is required to run")
        out.mkdir(parents=True, exist_ok=True)
        searches = recorded_searches(args.searches)
        for sample in selected:
            directory = out / f"brain-{sample['sample_id']}"
            started = time.monotonic()
            events = store(sample, directory, Path(args.model_cache))
            log("stored", sample["sample_id"], len(events), "events", round(time.monotonic() - started, 1), "s")
            ask(sample, directory, events, out, searches)
            log("asked", sample["sample_id"], round(time.monotonic() - started, 1), "s")
        print(json.dumps(check_dates(selected, out), indent=2))
    print(report(args))


if __name__ == "__main__":
    main()
