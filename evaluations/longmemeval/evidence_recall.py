"""LongMemEval evidence recall without any model call, on the system as it stands.

LongMemEval (Wu et al., ICLR 2025) gives every question its own history of about fifty user-assistant chat
sessions and marks the turns that hold the answer (``has_answer``). This harness stores one question's history as
the plugin's hooks would (each user message with the reply that answered it), then builds the context of a new
session for the question exactly as the plugin path does (``host.session_context`` plus ``host.prompt_context``)
and checks which evidence turns that context shows. Nothing is generated or judged.

It exists as a test the system was not tuned on: every ranking weight, the recall block and the cue rules were
chosen on LoCoMo. No setting is changed for this benchmark, and no cues are written, because in an installation
only a host AI writes them and none runs here.

Arms, as in ``evaluations/locomo/retrieval_recall.py``:

- ``M``: memBrain through the plugin path, with the local embedding model.
- ``R``: plain retrieval over the same stored turns: reciprocal-rank fusion of BM25 and cosine similarity under the
  same embedding model, each turn cut to ``RAW_TURN_CHARACTERS``, taken in rank order while they fit the size of
  the ``M`` context for that question.

A turn counts as shown when any ``SLICE``-character piece of it, taken every ``STEP`` characters, occurs in the
context. For a long turn that means part of it is shown, not necessarily the part with the answer; the dataset
does not mark the span.

    python evaluations/longmemeval/evidence_recall.py --data longmemeval_s_cleaned.json --out RUN_DIR \
        --model-cache MODEL_DIR --per-type 10 --shard 0/2
    python evaluations/longmemeval/evidence_recall.py --data longmemeval_s_cleaned.json --out RUN_DIR --report

Sets drawn so far, all with the seed in this file: ``--per-type 10`` is the first test sample (2026-11-12);
``--skip 10 --per-type 5 --keep`` is a development set whose stored histories are kept, so that a change to recall
can be checked in minutes by asking again under a new ``--label``. Questions from position 15 on are untouched.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import socket
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "locomo"))
from retrieval_recall import RawIndex  # noqa: E402
from run_locomo import install_model, log, start, wait_for_embeddings  # noqa: E402

SEED = 20261112
SLICE, STEP = 50, 200
RAW_TURN_CHARACTERS = 700  # What memBrain shows of one long message at most (host.MESSAGE_CHARACTERS).
RAW_EMBED_CHARACTERS = 1500
PRODUCER = "longmemeval-ingest"


def sample(data: list[dict], per_type: int, skip: int = 0) -> list[dict]:
    """``per_type`` questions of each type, chosen with a fixed seed, after the first ``skip`` of each type in that
    order (so later sets never overlap earlier ones); abstention questions have no evidence."""
    chosen, generator = [], random.Random(SEED)
    for kind in sorted({item["question_type"] for item in data}):
        items = [item for item in data if item["question_type"] == kind and not item["question_id"].endswith("_abs")
                 and any(turn.get("has_answer") for session in item["haystack_sessions"] for turn in session)]
        generator.shuffle(items)
        chosen.extend(items[skip:skip + per_type])
    return chosen


def turns_of(item: dict) -> list[dict]:
    """Every turn with its stored text, its session, the exchange it belongs to and whether it is evidence."""
    result = []
    for number, (session_id, date, session) in enumerate(zip(item["haystack_session_ids"], item["haystack_dates"],
                                                             item["haystack_sessions"], strict=True)):
        exchange, previous = 0, None
        for position, turn in enumerate(session):
            # A reply shares its exchange with the message it answers; anything else starts a new one.
            if turn["role"] != "assistant" or previous != "user":
                exchange += 1
            previous = turn["role"]
            result.append({"key": f"s{number}-t{position}", "session": f"lme-{item['question_id']}-s{number}",
                           "role": "assistant" if turn["role"] == "assistant" else "user",
                           "exchange": f"x{exchange}", "text": f"({date}) {turn['content']}",
                           "evidence": bool(turn.get("has_answer")), "answer_session": session_id in
                           item["answer_session_ids"]})
    return result


def pieces(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [flat[offset:offset + SLICE] for offset in range(0, max(1, len(flat) - SLICE + 1), STEP)] or [flat]


def shown(context: str, turn: dict) -> bool:
    flat = " ".join(context.split())
    return any(piece and piece in flat for piece in pieces(turn["text"]))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ingest(item: dict, directory: Path, cache: Path) -> dict:
    from membrain import host
    from membrain.embedded_database import default_engine
    from membrain.local_profile import ensure_profile

    marker = directory / "ingested.json"
    if marker.exists():
        start(directory)
        return json.loads(marker.read_text(encoding="utf-8"))
    if not (directory / "profile.json").exists():
        ensure_profile(directory, api_port=free_port(), database_port=free_port(), database_engine=default_engine())
    host.ensure_installation(directory)
    install_model(directory, cache)
    start(directory)
    started, stored = time.monotonic(), 0
    with host.ready_client(directory) as client:
        for turn in turns_of(item):
            record = host.message_record(turn["session"], turn["role"], turn["text"], turn_id=turn["exchange"],
                                         producer=PRODUCER)
            stored += host.deliver(directory, client, record)
    host.pause(directory)  # The question must never become a memory.
    waited = time.monotonic()
    wait_for_embeddings(directory, timeout=7200)
    summary = {"stored": stored, "store_seconds": round(waited - started, 1),
               "embed_seconds": round(time.monotonic() - waited, 1)}
    marker.write_text(json.dumps(summary), encoding="utf-8")
    return summary


def raw_context(index: RawIndex, turns: list[dict], query: str, budget: int) -> list[str]:
    lines, used = [], 0
    for position in index.rank(query):
        text = " ".join(turns[position]["text"].split())[:RAW_TURN_CHARACTERS]
        if used + len(text) + 1 > budget:
            continue
        lines.append(text)
        used += len(text) + 1
    return lines


def run(args) -> None:
    from membrain import desktop, host
    from membrain.local_embeddings import LocalEmbeddingProvider, installed

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    chosen = sample(data, args.per_type, args.skip)
    if args.extra:
        known = {item["question_id"] for item in chosen}
        chosen = [item for item in data if item["question_id"] in args.extra.split(",") and item["question_id"] not in known]
    part, parts = map(int, args.shard.split("/"))
    out, cache = Path(args.out), Path(args.model_cache)
    out.mkdir(parents=True, exist_ok=True)
    provider = LocalEmbeddingProvider(installed(cache), threads=2)
    path = out / f"recall-{args.label}-{part}.jsonl"
    done = {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
    for position, item in enumerate(chosen):
        if position % parts != part or item["question_id"] in done:
            continue
        directory = out / f"brain-{item['question_id']}"
        turns = turns_of(item)
        try:
            summary = ingest(item, directory, cache)
            session = f"question-{item['question_id']}"
            first = time.perf_counter()
            opening = host.session_context(directory, session)
            second = time.perf_counter()
            recalled = host.prompt_context(directory, session, item["question"]) or ""
            third = time.perf_counter()
        finally:
            try:
                desktop.stop(directory)
            except desktop.DesktopError:
                pass
        context = opening + "\n\n" + recalled
        index = RawIndex({turn["key"]: turn["text"][:RAW_EMBED_CHARACTERS] for turn in turns}, provider)
        baseline = "\n".join(raw_context(index, turns, item["question"], len(context)))
        block = "\n".join(raw_context(index, turns, item["question"], len(recalled)))
        evidence = [turn for turn in turns if turn["evidence"]]
        row = {"id": item["question_id"], "type": item["question_type"], "turns": len(turns),
               "evidence": [turn["key"] for turn in evidence],
               "evidence_roles": [turn["role"] for turn in evidence],
               "M": [turn["key"] for turn in evidence if shown(context, turn)],
               "M_recall_only": [turn["key"] for turn in evidence if shown(recalled, turn)],
               "R": [turn["key"] for turn in evidence if shown(baseline, turn)],
               "R_block": [turn["key"] for turn in evidence if shown(block, turn)],
               "characters": len(context), "recall_characters": len(recalled), "raw_characters": len(baseline),
               "session_ms": round((second - first) * 1000, 1), "prompt_ms": round((third - second) * 1000, 1),
               **summary}
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        log(item["question_id"], item["question_type"], "evidence", len(evidence), "M", len(row["M"]),
            "block", len(row["M_recall_only"]), "R", len(row["R"]), "R block", len(row["R_block"]), summary)
        if not args.keep:
            shutil.rmtree(directory / "postgres", ignore_errors=True)  # The stopped synthetic database.
            (directory / "ingested.json").unlink(missing_ok=True)


def report(args) -> None:
    rows = []
    for path in sorted(Path(args.out).glob(f"recall-{args.label}-*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    arms = ("M_recall_only", "R_block", "M", "R")

    def block(items):
        return [f"{sum(len(row[arm]) == len(row['evidence']) for row in items) / len(items):8.1%}" for arm in arms] + [
            f"{statistics.fmean(len(row[arm]) / len(row['evidence']) for row in items):8.1%}" for arm in arms[:2]]

    print(f"{'':28}{'n':>5}" + "".join(f"{name:>9}" for name in ("M block", "R block", "M all", "R all", "M share", "R share")))
    print(f"{'all':28}{len(rows):>5} " + " ".join(block(rows)))
    for kind in sorted({row["type"] for row in rows}):
        items = [row for row in rows if row["type"] == kind]
        print(f"{kind:28}{len(items):>5} " + " ".join(block(items)))
    for name, keep in (("evidence in user turns only", lambda row: set(row["evidence_roles"]) == {"user"}),
                       ("some evidence by assistant", lambda row: "assistant" in row["evidence_roles"])):
        items = [row for row in rows if keep(row)]
        if items:
            print(f"{name:28}{len(items):>5} " + " ".join(block(items)))
    gained = sum(len(row["M_recall_only"]) == len(row["evidence"]) > len(row["R_block"]) for row in rows)
    lost = sum(len(row["R_block"]) == len(row["evidence"]) > len(row["M_recall_only"]) for row in rows)
    print(f"block, M against R: M complete where R is not {gained}, R complete where M is not {lost}")
    print("mean characters: context", round(statistics.fmean(row["characters"] for row in rows)), "recall block",
          round(statistics.fmean(row["recall_characters"] for row in rows)), "| median ms: session",
          statistics.median(row["session_ms"] for row in rows), "prompt", statistics.median(row["prompt_ms"] for row in rows),
          "| median seconds to store and embed one history:",
          statistics.median(row["store_seconds"] + row["embed_seconds"] for row in rows))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", required=True, help="longmemeval_s_cleaned.json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model-cache", default="", help="Directory holding the pinned embedding model")
    parser.add_argument("--per-type", type=int, default=10, help="Questions of each of the six types")
    parser.add_argument("--skip", type=int, default=0, help="Leave out the first N of each type in the seeded order")
    parser.add_argument("--extra", default="", help="Run only these question ids, outside the sample (a pilot)")
    parser.add_argument("--shard", default="0/1", help="This worker's part of the sample, as part/parts")
    parser.add_argument("--label", default="current")
    parser.add_argument("--keep", action="store_true", help="Keep each stored history's database after measuring")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if not args.report:
        run(args)
    report(args)


if __name__ == "__main__":
    main()
