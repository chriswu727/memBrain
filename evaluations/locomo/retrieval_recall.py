"""LoCoMo evidence recall without any model call: is the evidence in the context a host would be given?

LoCoMo marks, for every question, the turns that hold its answer (``evidence``, a list of ``dia_id``). This harness
stores each conversation as the hooks would (the same ingestion as ``run_locomo.py``), builds the context of a new
session for every question exactly as the plugin path does (``host.session_context`` plus ``host.prompt_context``),
and checks which evidence turns that context contains. No answer is generated and nothing is judged, so the run is
free and repeatable; it measures retrieval, the step the 2026-10-29 answer run found responsible for most wrong
answers, and says nothing about what a host model does with the context.

Arms:

- ``M``: memBrain through the plugin path, with the local embedding model (``--no-semantic`` for keywords only).
- ``R``: raw-record retrieval at the same size. The stored turns are ranked by reciprocal-rank fusion of BM25 and
  cosine similarity under the same embedding model, and taken in rank order until the character count of the
  ``M`` context for that question is reached. It has no notes, history, cue or adjacency logic: it is the plain
  alternative a memory engine has to beat at equal budget.

A turn counts as present when its stored text, cut to ``MATCH_CHARACTERS`` characters after its date and speaker
prefix, occurs in the context. Reported per category: the share of questions with every evidence turn present, the
mean share of evidence turns present, the context size, and the time the two context calls took.

Usage (downloads nothing itself; pass the dataset and a directory holding the pinned embedding model)::

    python evaluations/locomo/retrieval_recall.py --data locomo10.json --out RUN_DIR --model-cache MODEL_DIR
    python evaluations/locomo/retrieval_recall.py --out RUN_DIR --report
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_locomo import CATEGORIES, ingest, log, questions, sessions, turn_text  # noqa: E402

MATCH_CHARACTERS = 60
WORD = re.compile(r"[a-z0-9]+")


def stored_turns(sample: dict) -> dict[str, str]:
    """``dia_id`` to the text stored for that turn."""
    return {turn["dia_id"]: turn_text(date, turn) for _, date, turns in sessions(sample) for turn in turns}


def needle(date: str, turn: dict) -> str:
    """The part of a stored turn that identifies it in a context: its prefix and the start of what was said."""
    prefix = f"({date}) {turn['speaker']}: "
    return " ".join((prefix + turn.get("text", "")[:MATCH_CHARACTERS]).split())


def needles(sample: dict) -> dict[str, str]:
    return {turn["dia_id"]: needle(date, turn) for _, date, turns in sessions(sample) for turn in turns}


def evidence_ids(qa: dict, known: dict) -> list[str]:
    """The evidence turns of a question that exist in the conversation (a few annotations name several per entry)."""
    found = []
    for entry in qa.get("evidence") or []:
        for value in re.findall(r"D\d+:\d+", str(entry)):
            if value in known and value not in found:
                found.append(value)
    return found


def present(context: str, wanted: list[str], identify: dict) -> list[str]:
    flat = " ".join(context.split())
    return [value for value in wanted if identify[value] in flat]


# Raw-record retrieval ----------------------------------------------------------------------------------------------

class RawIndex:
    """BM25 and embedding ranks over one conversation's stored turns, fused by reciprocal rank."""

    def __init__(self, turns: dict[str, str], provider):
        self.ids = list(turns)
        self.texts = [turns[value] for value in self.ids]
        self.tokens = [WORD.findall(text.lower()) for text in self.texts]
        self.frequency = Counter(word for tokens in self.tokens for word in set(tokens))
        self.average = sum(map(len, self.tokens)) / max(1, len(self.tokens))
        self.provider = provider
        self.vectors = self._embed(self.texts, "document") if provider is not None else None

    def _embed(self, texts, purpose):
        import numpy

        vectors = []
        for start in range(0, len(texts), 32):
            result = self.provider.embed(texts[start:start + 32], timeout_seconds=120.0, purpose=purpose)
            vectors.extend(result.vectors)
        matrix = numpy.asarray(vectors, dtype="float32")
        return matrix / numpy.maximum(numpy.linalg.norm(matrix, axis=1, keepdims=True), 1e-9)

    def _bm25(self, query: str) -> list[int]:
        words, total = WORD.findall(query.lower()), len(self.ids)
        scores = []
        for tokens in self.tokens:
            counts, score = Counter(tokens), 0.0
            for word in words:
                if counts[word]:
                    idf = math.log(1 + (total - self.frequency[word] + 0.5) / (self.frequency[word] + 0.5))
                    score += idf * counts[word] * 2.2 / (
                        counts[word] + 1.2 * (0.25 + 0.75 * len(tokens) / self.average))
            scores.append(score)
        return sorted(range(total), key=lambda index: (-scores[index], index))

    def rank(self, query: str) -> list[int]:
        lexical = self._bm25(query)
        if self.vectors is None:
            return lexical
        scores = self.vectors @ self._embed([query], "query")[0]
        semantic = sorted(range(len(self.ids)), key=lambda index: (-float(scores[index]), index))
        fused = defaultdict(float)
        for order in (lexical, semantic):
            for position, index in enumerate(order):
                fused[index] += 1.0 / (60 + position)
        return sorted(fused, key=lambda index: (-fused[index], index))

    def context(self, query: str, budget: int) -> str:
        lines, used = [], 0
        for index in self.rank(query):
            size = len(self.texts[index]) + 1
            if used + size > budget:
                break
            lines.append(self.texts[index])
            used += size
        return "\n".join(lines)


# Runner ---------------------------------------------------------------------------------------------------------

def run(args) -> None:
    from membrain import desktop, host

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    selected = [data[int(index)] for index in args.conversations.split(",")] if args.conversations else data
    categories = {int(value) for value in args.categories.split(",")}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = None if args.no_semantic else Path(args.model_cache)
    ports = tuple(map(int, args.ports.split(","))) if args.ports else None
    provider = None
    if cache is not None:
        from membrain.local_embeddings import LocalEmbeddingProvider, installed

        provider = LocalEmbeddingProvider(installed(cache), threads=4)
        if not provider.ready:
            raise SystemExit("The pinned embedding model is not in --model-cache.")
    path = out / f"recall-{args.label}.jsonl"
    done = {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
    for position, sample in enumerate(selected):
        todo = [(qid, qa) for qid, qa in questions(sample, categories) if qid not in done]
        if args.max_questions:
            todo = todo[:args.max_questions]
        if not todo:
            continue
        directory = out / f"brain-{sample['sample_id']}"
        own = (ports[0] + 10 * position, ports[1] + 10 * position) if ports else None
        started = time.monotonic()
        stored = ingest(sample, directory, cache, None, own)
        log("ingest", sample["sample_id"], stored, "messages", round(time.monotonic() - started, 1), "s")
        turns, identify = stored_turns(sample), needles(sample)
        raw = RawIndex(turns, provider)
        try:
            for qid, qa in todo:
                wanted = evidence_ids(qa, turns)
                session = f"question-{qid}"
                first = time.perf_counter()
                opening = host.session_context(directory, session)
                second = time.perf_counter()
                recalled = host.prompt_context(directory, session, qa["question"]) or ""
                third = time.perf_counter()
                context = opening + "\n\n" + recalled
                baseline = raw.context(qa["question"], len(context))
                row = {"id": qid, "category": qa["category"], "evidence": wanted,
                       "M": present(context, wanted, identify), "M_recall_only": present(recalled, wanted, identify),
                       "R": present(baseline, wanted, identify),
                       "characters": len(context), "recall_characters": len(recalled),
                       "raw_characters": len(baseline),
                       "session_ms": round((second - first) * 1000, 1),
                       "prompt_ms": round((third - second) * 1000, 1)}
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row) + "\n")
        finally:
            try:
                desktop.stop(directory)
            except desktop.DesktopError:
                pass
        log("done", sample["sample_id"], len(todo), "questions", round(time.monotonic() - started, 1), "s")


def summarize(rows: list[dict]) -> dict:
    def block(items):
        scored = [row for row in items if row["evidence"]]
        result = {"questions": len(items), "with_evidence": len(scored)}
        for arm in ("M", "M_recall_only", "R"):
            result[arm] = {
                "all_evidence": round(sum(len(row[arm]) == len(row["evidence"]) for row in scored) / len(scored), 4),
                "any_evidence": round(sum(bool(row[arm]) for row in scored) / len(scored), 4),
                "evidence_share": round(statistics.fmean(len(row[arm]) / len(row["evidence"]) for row in scored), 4)}
        result["mean_characters"] = round(statistics.fmean(row["characters"] for row in items))
        result["mean_raw_characters"] = round(statistics.fmean(row["raw_characters"] for row in items))
        for name in ("session_ms", "prompt_ms"):
            values = sorted(row[name] for row in items)
            result[name] = {"p50": values[len(values) // 2], "p95": values[min(len(values) - 1, int(len(values) * .95))]}
        return result

    summary = {"all": block(rows)}
    for category, name in CATEGORIES.items():
        items = [row for row in rows if row["category"] == category]
        if items:
            summary[name] = block(items)
    by_size = defaultdict(list)
    for row in rows:
        by_size["one evidence turn" if len(row["evidence"]) == 1 else "several evidence turns"
                if row["evidence"] else "no evidence listed"].append(row)
    for name, items in by_size.items():
        if name != "no evidence listed":
            summary[name] = block(items)
    return summary


def report(args) -> None:
    path = Path(args.out) / f"recall-{args.label}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    summary = summarize(rows)
    (Path(args.out) / f"summary-{args.label}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{'':24}{'n':>6}{'M all':>8}{'M share':>9}{'recall':>8}{'R all':>8}{'R share':>9}{'chars':>8}"
          f"{'sess p50':>10}{'prompt p50/p95':>16}")
    for name, block in summary.items():
        print(f"{name:24}{block['with_evidence']:>6}{block['M']['all_evidence']:>8.1%}"
              f"{block['M']['evidence_share']:>9.1%}{block['M_recall_only']['all_evidence']:>8.1%}"
              f"{block['R']['all_evidence']:>8.1%}{block['R']['evidence_share']:>9.1%}{block['mean_characters']:>8}"
              f"{block['session_ms']['p50']:>10}{block['prompt_ms']['p50']:>8}/{block['prompt_ms']['p95']:<7}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", help="locomo10.json from snap-research/locomo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model-cache", default="", help="Directory holding the pinned embedding model")
    parser.add_argument("--no-semantic", action="store_true", help="Keyword recall only, and BM25 only for R")
    parser.add_argument("--conversations", default="", help="Comma-separated indexes; default all ten")
    parser.add_argument("--categories", default="1,2,3,4")
    parser.add_argument("--max-questions", type=int, default=0, help="Per conversation; 0 means all")
    parser.add_argument("--label", default="current", help="Names the result file, e.g. the runtime commit")
    parser.add_argument("--ports", default="", help="API and database ports for new installations, e.g. 8891,55601")
    parser.add_argument("--report", action="store_true", help="Only summarize existing results")
    args = parser.parse_args()
    if not args.report:
        if not args.data or not (args.no_semantic or args.model_cache):
            parser.error("--data and --model-cache (or --no-semantic) are required to run")
        run(args)
    report(args)


if __name__ == "__main__":
    main()
