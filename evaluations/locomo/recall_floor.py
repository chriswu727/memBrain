"""Where the per-prompt recall block's lines come from, and what candidate relevance floors would cost.

A measurement, not a product change: no source file is changed and no model is called. The real service runs in
this process (no recall worker pool, as ``results-2026-11-11/cue_sweep.py`` does) over the installations that
``retrieval_recall.py`` stored, so the scores the host never sees can be recorded while the request is answered:
the cosine similarity of every meaning-route candidate and the lexical score of every keyword-route candidate.

For every question it builds the context exactly as the plugin path does (``host.session_context`` then
``host.prompt_context``, as ``retrieval_recall.py``), and records each line of the recall block: which message it
shows, how that message got there (keyword, meaning only, cue, or as the message following a recalled one), its
scores and rank, and whether it is evidence for the question. It also asks the deliberate search
(``host.recall_context(..., deliberate=True, notes=True)``, what ``memory_recall`` returns) with the question.

Each candidate rule (``RULES``) is applied in memory to the service's response before the host's own selection
(``host._sources``), by removing the route signal a line would have entered on; the block is then assembled by the
unchanged ``host.recall_context`` with the same limit and cues the plugin path used.

    python recall_floor.py collect --data locomo10.json --brains RUN_DIR --out OUT.jsonl \
        --conversations 0,1,2 --rules all
    python recall_floor.py report --out OUT.jsonl        # evidence recall and block size per rule
    python recall_floor.py separation --out OUT.jsonl    # evidence share of block lines by route and score band
    python recall_floor.py collect ... --prompts FILE    # prompts with nothing to find; then `unmatched`
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import math
import sys
import threading
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CAPTURE: dict = {}
CACHED: dict = {}


def _install_service_probes():
    """Record the scores the service computes but does not return. Only wraps functions in this process."""
    import membrain.candidates as candidates

    pools, direct = candidates._semantic_pools, candidates._direct_candidates

    def semantic_pools(*args, **kwargs):
        found = pools(*args, **kwargs)
        distances = CAPTURE.setdefault("distance", {})
        for rows in found.values():
            for row in rows:
                if row["distance"] is not None and math.isfinite(row["distance"]):
                    key = (row["document"]["memory_id"], row["document"]["revision"])
                    distances[key] = min(row["distance"], distances.get(key, 2.0))
        return found

    def direct_candidates(rankings, versions, lexical_scores, cue_scores=None, *, limit):
        CAPTURE["lexical"] = dict(lexical_scores)
        CAPTURE["cue"] = dict(cue_scores or {})
        return direct(rankings, versions, lexical_scores, cue_scores, limit=limit)

    candidates._semantic_pools, candidates._direct_candidates = semantic_pools, direct_candidates


def install_follow_switch():
    """``host.FOLLOW_ONLY`` (None: unchanged) limits which recalled messages get their following message shown."""
    from membrain import host

    replies = host._replies
    host.FOLLOW_ONLY = None

    def limited(client, messages, limit=host.MAX_REPLIES):
        if host.FOLLOW_ONLY is not None:
            messages = [message for message in messages if message.get("event_id") in host.FOLLOW_ONLY]
        return replies(client, messages, limit)

    host._replies = limited


# Rules ----------------------------------------------------------------------------------------------------------

def _signal(item, method):
    return max((signal.get("score") or 0 for signal in item.get("rank_signals") or []
                if signal.get("method") == method), default=0)


def _drop(item, method):
    for signal in item.get("rank_signals") or []:
        if signal.get("method") == method:
            signal["score"] = 0.0


def _key(item):
    memory = item.get("memory") or {}
    return memory.get("memory_id"), memory.get("revision")


def _events(item):
    return [ref["event_id"] for ref in (item.get("memory") or {}).get("evidence_refs") or []
            if ref.get("relationship") == "supports" and isinstance(ref.get("event_id"), str)]


class Context:
    """What a rule may look at for one query: the captured scores and this brain's term frequencies."""

    def __init__(self, query, capture, frequencies, documents):
        from membrain import cognition

        self.query_terms = cognition._terms(query)
        self.distance = capture.get("distance", {})
        self.lexical = capture.get("lexical", {})
        self.best_lexical = max(self.lexical.values(), default=0.0)
        self.top_similarity = max((1 - value for value in self.distance.values()), default=None)
        self.frequencies, self.documents = frequencies, documents

    def similarity(self, item):
        distance = self.distance.get(_key(item))
        return None if distance is None else 1 - distance

    def matched(self, item):
        """The query terms this statement shares with the query (words, character pairs, single characters)."""
        from membrain import cognition

        terms = cognition._terms(((item.get("memory") or {}).get("statement")) or "")
        return [part & query for part, query in zip(terms, self.query_terms, strict=True)]

    def rarest_share(self, item):
        """The memory-wide document share of the rarest query term this statement matches (1.0 if none)."""
        shares = [self.frequencies[index][term] / max(1, self.documents)
                  for index, part in enumerate(self.matched(item)) for term in part]
        return min(shares, default=1.0)

    def idf_coverage(self, item):
        """Share of the query's memory-wide inverse document frequency that this statement matches."""
        def idf(index, term):
            return math.log((1 + self.documents) / (1 + self.frequencies[index][term]))

        whole = sum(idf(index, term) for index, part in enumerate(self.query_terms) for term in part
                    if index < 2 or len(self.query_terms[2]) >= 2)
        got = sum(idf(index, term) for index, part in enumerate(self.matched(item)) for term in part
                  if index < 2 or len(self.query_terms[2]) >= 2)
        return got / whole if whole > 0 else 0.0


def _keyword_events(items):
    keyword = {event for item in items if _signal(item, "keyword") > 0 or _signal(item, "entity") > 0
               for event in _events(item)}
    return keyword


def rule_function(name):
    """``name`` -> function(items, context) that edits the items in place and returns host limits to override
    (``{"VECTOR_ONLY_STATEMENTS": n}``, ``{"MAX_MESSAGES": n}``) or None."""
    kind, _, value = name.partition(":")

    def meaning(keep):
        def apply(items, context):
            keyword = _keyword_events(items)
            for item in items:
                if _signal(item, "vector") > 0 and not set(_events(item)) <= keyword and not keep(item, context):
                    _drop(item, "vector")
        return apply

    def keyword(keep):
        def apply(items, context):
            for item in items:
                if _signal(item, "keyword") > 0 and not keep(item, context):
                    _drop(item, "keyword")
        return apply

    if kind == "nofollow":  # The following message is shown only for messages recalled by keyword or cue.
        return lambda items, context: {"FOLLOW_ONLY": _keyword_events(items)}
    if kind == "none":
        return lambda items, context: None
    if kind == "cap":  # At most N meaning-only messages.
        return lambda items, context: {"VECTOR_ONLY_STATEMENTS": int(value)}
    if kind == "max":  # At most N recalled messages offered to the block (MAX_MESSAGES, 40 today).
        return lambda items, context: {"MAX_MESSAGES": int(value)}
    if kind == "abs":  # Meaning-only lines need cosine similarity >= value.
        return meaning(lambda item, context: (context.similarity(item) or 0) >= float(value))
    if kind == "rel":  # Meaning-only lines need similarity >= the query's best similarity - value.
        return meaning(lambda item, context: context.top_similarity is not None
                       and (context.similarity(item) or 0) >= context.top_similarity - float(value))
    if kind == "gap":  # Meaning-only lines: cut after the largest drop among the ten closest, if >= value.
        def apply(items, context):
            keyword_events = _keyword_events(items)
            best = {}
            for item in items:
                if _signal(item, "vector") > 0:
                    for event in _events(item):
                        if event not in keyword_events:
                            best[event] = max(best.get(event, -1), context.similarity(item) or 0)
            order = sorted(best.values(), reverse=True)[:10]
            gaps = [(order[index] - order[index + 1], index) for index in range(len(order) - 1)]
            size, index = max(gaps, default=(-1, 0))
            cut = order[index] if gaps and size >= float(value) else -1
            for item in items:
                if _signal(item, "vector") > 0 and (context.similarity(item) or 0) < cut \
                        and not set(_events(item)) <= keyword_events:
                    _drop(item, "vector")
        return apply
    if kind == "kwcap":  # N meaning-only messages when the best keyword match covers >= 0.3 of the query, else 10.
        return lambda items, context: {"VECTOR_ONLY_STATEMENTS": int(value)} if context.best_lexical >= 0.3 else None
    if kind == "lex":  # Keyword lines need a lexical score (share of the query's weighted terms) >= value.
        return keyword(lambda item, context: context.lexical.get(_key(item), 0.0) >= float(value))
    if kind == "lexrel":  # Keyword lines need a lexical score >= value * the query's best.
        return keyword(lambda item, context: context.lexical.get(_key(item), 0.0) >= float(value) * context.best_lexical)
    if kind == "df":  # Keyword lines need one matched term in fewer than value of this memory's messages.
        return keyword(lambda item, context: context.rarest_share(item) < float(value))
    if kind == "dfn":  # "dfn:S/N": as df, but a term is common only if it is also in at least N messages.
        share, count = (float(part) for part in value.split("/"))
        return keyword(lambda item, context: context.rarest_share(item) < share
                       or context.rarest_share(item) * context.documents < count)
    if kind == "idf":  # Keyword lines need a memory-wide IDF coverage of the query >= value.
        return keyword(lambda item, context: context.idf_coverage(item) >= float(value))
    if kind == "both":  # "both:A+B+...": apply the rules in turn (keyword rules first); limits are merged.
        parts = [rule_function(part) for part in value.split("+")]

        def apply(items, context):
            limits = {}
            for part in parts:
                limits.update(part(items, context) or {})
            return limits or None
        return apply
    raise SystemExit(f"unknown rule {name}")


SWEEP = (["none", "cap:0", "cap:3", "cap:5", "kwcap:0", "kwcap:3", "kwcap:5"]
         + [f"abs:{value / 100:.2f}" for value in range(78, 91)]
         + [f"rel:{value}" for value in ("0.01", "0.02", "0.03", "0.04", "0.05", "0.07", "0.10")]
         + [f"gap:{value}" for value in ("0", "0.01", "0.02")]
         + [f"lex:{value}" for value in ("0.05", "0.1", "0.15", "0.2", "0.3")]
         + [f"lexrel:{value}" for value in ("0.2", "0.3", "0.5")]
         + [f"df:{value}" for value in ("0.02", "0.05", "0.1", "0.2", "0.25", "0.3", "0.4", "0.5")]
         + [f"dfn:{value}/5" for value in ("0.2", "0.25", "0.3")]
         + [f"idf:{value}" for value in ("0.1", "0.15", "0.2", "0.3")]
         + [f"max:{value}" for value in (15, 20, 25, 30)]
         + ["both:dfn:0.25/5+kwcap:3", "both:dfn:0.25/5+kwcap:0", "both:dfn:0.25/5+rel:0.03",
            "both:dfn:0.25/5+rel:0.02", "both:dfn:0.25/5+cap:3", "both:dfn:0.2/5+rel:0.03", "both:dfn:0.3/5+kwcap:3",
            "both:idf:0.1+rel:0.03", "both:lex:0.05+rel:0.03", "both:kwcap:3+rel:0.03",
            "both:dfn:0.25/5+kwcap:3+rel:0.03"])


# Collection -----------------------------------------------------------------------------------------------------

def _brain_terms(client):
    """Per-message term frequencies over this brain's user messages, and event id -> text."""
    from membrain import cognition

    texts, before = {}, None
    while True:
        page = client.timeline(roles=("user",), max_characters=200_000, max_item_characters=20_000, limit=200,
                               **({"before_sequence": before} if before else {}))
        for item in page.get("items", []):
            texts[item["event_id"]] = item.get("text") or ""
        before = page.get("next_before_sequence")
        if page.get("complete", True) or before is None:
            break
    frequencies = [Counter(), Counter(), Counter()]
    for text in texts.values():
        for index, part in enumerate(cognition._terms(text)):
            frequencies[index].update(part)
    return texts, frequencies


def _memory_block(text):
    """The ``<membrain-memory>`` block alone: what recall added, without notices before it."""
    start, end = (text or "").find("<membrain-memory>"), (text or "").find("</membrain-memory>")
    return text[start:end + len("</membrain-memory>")] if start >= 0 and end > start else ""


def _block_lines(block):
    return [line for line in (block or "").splitlines() if line.startswith("- [")]


def _provenance(response, context, current):
    """event id -> provenance, scores and rank among the messages ``host._sources`` offers, for one response."""
    from membrain import host

    items = (response.get("result") or {}).get("items", [])
    keyword = _keyword_events(items)
    info = {}
    for position, (event, _) in enumerate(host._sources(response, current)):
        info[event] = {"rank": position}
    for item in items:
        for event in _events(item):
            if event not in info:
                continue
            entry = info[event]
            entry["keyword"] = entry.get("keyword", False) or _signal(item, "keyword") > 0
            entry["cue"] = entry.get("cue", False) or _signal(item, "entity") > 0
            similarity = context.similarity(item)
            if similarity is not None:
                entry["similarity"] = max(similarity, entry.get("similarity", -1))
            if _signal(item, "keyword") > 0:
                entry["lexical"] = max(context.lexical.get(_key(item), 0.0), entry.get("lexical", 0.0))
                entry["rarest_share"] = min(context.rarest_share(item), entry.get("rarest_share", 1.0))
                entry["idf_coverage"] = max(context.idf_coverage(item), entry.get("idf_coverage", 0.0))
    meaning_rank = 0
    for event, entry in sorted(info.items(), key=lambda pair: pair[1]["rank"]):
        entry["route"] = "keyword" if entry.get("keyword") else "cue" if entry.get("cue") else (
            "meaning" if event not in keyword else "other")
        if entry["route"] == "meaning":
            entry["meaning_rank"] = meaning_rank
            meaning_rank += 1
    return info


def collect(args):
    import uvicorn
    from retrieval_recall import evidence_ids, needles, present, stored_turns
    from run_locomo import questions

    from membrain import desktop, embedded_database, host
    from membrain.api import create_app
    from membrain.local_profile import load_profile

    _install_service_probes()
    install_follow_switch()
    rules = SWEEP if args.rules == "all" else ([] if not args.rules else args.rules.split(","))
    if "none" not in rules:
        rules = ["none", *rules]
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    out = Path(args.out)
    done = {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    original = {name: getattr(host, name) for name in ("recall", "_trace", "recall_context")}
    status = desktop.status
    desktop.status = lambda directory=None: {"ready": True, "state": "ready"}  # The service runs in this process.

    def recall(client, query, cues=(), **options):
        if "response" in CACHED:
            return copy.deepcopy(CACHED["response"])
        CAPTURE.clear()
        response = original["recall"](client, query, cues, **options)
        CACHED["last"] = (copy.deepcopy(response), copy.deepcopy(CAPTURE))
        return response

    def trace(client, event_ids):
        CACHED["trace"] = list(event_ids)

    def recall_context(client, query, **options):
        CACHED["call"] = (query, dict(options))
        return original["recall_context"](client, query, **options)

    host.recall, host._trace, host.recall_context = recall, trace, recall_context
    try:
        for index in [int(value) for value in args.conversations.split(",")]:
            sample = data[index]
            todo = [(qid, qa) for qid, qa in questions(sample, {1, 2, 3, 4}) if qid not in done]
            if args.prompts:  # Prompts with nothing to find in these conversations, instead of the questions.
                prompts = Path(args.prompts).read_text(encoding="utf-8").splitlines()
                todo = [(f"{sample['sample_id']}-p{number}", {"question": prompt, "category": 0, "evidence": []})
                        for number, prompt in enumerate(prompts) if prompt.strip()
                        and f"{sample['sample_id']}-p{number}" not in done]
            if args.max_questions:
                todo = todo[:args.max_questions]
            if not todo:
                continue
            directory = Path(args.brains) / f"brain-{sample['sample_id']}"
            profile = load_profile(directory)
            desktop._prepare_database(profile)
            settings = dataclasses.replace(profile.settings(), recall_processes=0)
            server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                                   log_level="error"))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            started = time.monotonic()
            try:
                while not server.started:
                    time.sleep(0.1)
                turns, identify = stored_turns(sample), needles(sample)
                with host.ready_client(directory) as client:
                    texts, frequencies = _brain_terms(client)
                    by_text = {}
                    for event, text in texts.items():
                        by_text.setdefault(" ".join(text.split()), event)
                    dia_of = {by_text[" ".join(text.split())]: dia for dia, text in turns.items()
                              if " ".join(text.split()) in by_text}
                    for qid, qa in todo:
                        wanted = evidence_ids(qa, turns)
                        session = f"floor-{qid}"
                        CACHED.clear()
                        opening = host.session_context(directory, session)
                        first = time.perf_counter()
                        recalled = host.prompt_context(directory, session, qa["question"]) or ""
                        elapsed = time.perf_counter() - first
                        row = {"id": qid, "category": qa["category"], "evidence": wanted, "conversation": index,
                               "session_characters": len(opening or ""), "prompt_ms": round(elapsed * 1000, 1)}
                        if "call" not in CACHED or "last" not in CACHED:  # No recall was made.
                            row["arms"] = {rule: {"found": [], "characters": len(_memory_block(recalled)), "lines": 0}
                                           for rule in rules}
                            row["note"] = "no recall"
                            with out.open("a") as stream:
                                stream.write(json.dumps(row) + "\n")
                            continue
                        query, options = CACHED["call"]
                        response, capture = CACHED["last"]
                        context = Context(query, capture, frequencies, len(texts))
                        baseline_trace = CACHED.get("trace", [])
                        info = _provenance(response, context, options.get("current_conversation"))
                        lines = _block_lines(recalled)
                        evidence_events = {event for event, dia in dia_of.items() if dia in wanted}
                        row["lines"] = []
                        for event, line in zip(baseline_trace, lines, strict=False):
                            entry = dict(info.get(event, {"route": "following"}))
                            entry.pop("keyword", None), entry.pop("cue", None)
                            entry.update(dia=dia_of.get(event), evidence=event in evidence_events,
                                         characters=len(line))
                            row["lines"].append(entry)
                        row["trace_matches_lines"] = len(baseline_trace) == len(lines)
                        row["top_similarity"] = context.top_similarity
                        row["best_lexical"] = context.best_lexical
                        row["query_terms"] = [sorted(part) for part in context.query_terms]
                        row["query_term_shares"] = {term: round(frequencies[i][term] / max(1, len(texts)), 4)
                                                    for i, part in enumerate(context.query_terms) for term in part}
                        row["arms"] = {}
                        for rule in rules:
                            if rule == "none":
                                block = recalled
                            else:
                                transformed = copy.deepcopy(response)
                                override = rule_function(rule)(
                                    (transformed.get("result") or {}).get("items", []), context)
                                CACHED["response"] = transformed
                                CACHED.pop("trace", None)
                                saved = {name: getattr(host, name) for name in (override or {})}
                                for name, limit in (override or {}).items():
                                    setattr(host, name, limit)
                                try:
                                    block = original["recall_context"](client, query, **options) or ""
                                finally:
                                    for name, limit in saved.items():
                                        setattr(host, name, limit)
                                    CACHED.pop("response", None)
                            row["arms"][rule] = {"found": present(block, wanted, identify), "characters": len(_memory_block(block)),
                                                 "lines": len(_block_lines(block))}
                        if args.deliberate:
                            CACHED.pop("trace", None)
                            deliberate = original["recall_context"](client, query, deliberate=True, notes=True) or ""
                            row["deliberate"] = {"found": present(deliberate, wanted, identify),
                                                 "characters": len(_memory_block(deliberate)),
                                                 "lines": len(_block_lines(deliberate))}
                        with out.open("a") as stream:
                            stream.write(json.dumps(row) + "\n")
                print(sample["sample_id"], len(todo), "questions", round(time.monotonic() - started), "s", flush=True)
            finally:
                server.should_exit = True
                thread.join(timeout=30)
                embedded_database.stop(profile)
    finally:
        host.recall, host._trace, host.recall_context = original["recall"], original["_trace"], original["recall_context"]
        desktop.status = status


# Report ---------------------------------------------------------------------------------------------------------

def report(args):
    from run_locomo import CATEGORIES

    rows = [json.loads(line) for line in Path(args.out).read_text().splitlines()]
    rows = [row for row in rows if row["evidence"]]
    print(len(rows), "questions with evidence")
    names = list(rows[0]["arms"])

    def quantile(values, share):
        values = sorted(values)
        return values[min(len(values) - 1, int(share * len(values)))] if values else 0

    def full(row, name):
        return len(row["arms"][name]["found"]) == len(row["evidence"])

    print(f"{'rule':34}{'all':>7}" + "".join(f"{CATEGORIES[c][:9]:>10}" for c in (4, 2, 1, 3))
          + f"{'chars':>7}{'p90':>7}{'lines':>6}{'p90':>5}{'empty':>7}{'lost':>6}{'gained':>7}{'asked':>7}")
    for name in names:
        def rate(items):
            items = [row for row in items if name in row["arms"]]
            return sum(full(row, name) for row in items) / max(1, len(items))
        chars = [row["arms"][name]["characters"] for row in rows if name in row["arms"]]
        lines = [row["arms"][name]["lines"] for row in rows if name in row["arms"]]
        lost = [row for row in rows if name in row["arms"] and full(row, "none") and not full(row, name)]
        gained = sum(1 for row in rows if name in row["arms"] and full(row, name) and not full(row, "none"))
        # Lost questions whose evidence the deliberate search (memory_recall with the question) has in full.
        asked = sum(1 for row in lost if "deliberate" in row
                    and len(row["deliberate"]["found"]) == len(row["evidence"]))
        print(f"{name:34}{rate(rows):>7.1%}" + "".join(
            f"{rate([row for row in rows if row['category'] == c]):>10.1%}" for c in (4, 2, 1, 3))
            + f"{sum(chars) / len(chars):>7.0f}{quantile(chars, .9):>7}{sum(lines) / len(lines):>6.1f}"
            f"{quantile(lines, .9):>5}{sum(value == 0 for value in lines) / len(lines):>7.1%}"
            f"{len(lost):>6}{gained:>7}{asked:>7}")
    if any("deliberate" in row for row in rows):
        print(f"{'deliberate search (memory_recall)':34}"
              f"{sum(len(row['deliberate']['found']) == len(row['evidence']) for row in rows) / len(rows):>7.1%}")


def unmatched(args):
    """Block size per rule for prompts that have nothing to find (every recalled line is unrelated)."""
    rows = [json.loads(line) for line in Path(args.out).read_text().splitlines()]
    print(len(rows), "prompts")
    print(f"{'rule':34}{'chars':>7}{'p90':>7}{'lines':>6}{'empty':>7}")
    for name in rows[0]["arms"]:
        chars = sorted(row["arms"][name]["characters"] for row in rows)
        lines = [row["arms"][name]["lines"] for row in rows]
        print(f"{name:34}{sum(chars) / len(chars):>7.0f}{chars[min(len(chars) - 1, int(.9 * len(chars)))]:>7}"
              f"{sum(lines) / len(lines):>6.1f}{sum(value == 0 for value in lines) / len(lines):>7.1%}")


def _bands(rows, field, edges, select):
    """Evidence share of the block lines ``select`` keeps, by band of ``field``."""
    lines = [line for row in rows for line in row.get("lines", []) if select(line, row)]
    print(f"  {field:14}{'lines':>7}{'chars':>9}{'evidence':>10}{'share':>8}")
    for low, high in zip(edges, edges[1:]):
        band = [line for line in lines if field in line and low <= line[field] < high]
        if band:
            print(f"  [{low:5}, {high:5}){len(band):>7}{sum(line['characters'] for line in band):>9}"
                  f"{sum(line['evidence'] for line in band):>10}{sum(line['evidence'] for line in band) / len(band):>8.1%}")


def separation(args):
    rows = [json.loads(line) for line in Path(args.out).read_text().splitlines()]
    rows = [row for row in rows if row["evidence"] and "lines" in row]
    print(len(rows), "questions;", sum(not row["trace_matches_lines"] for row in rows), "with trace/line mismatch")
    lines = [line for row in rows for line in row["lines"]]
    total, characters = len(lines), sum(line["characters"] for line in lines)
    print(f"{'route':12}{'lines':>7}{'share':>7}{'chars':>9}{'share':>7}{'per q':>7}{'evidence':>9}{'precision':>10}")
    for route in ("keyword", "meaning", "cue", "following", "other"):
        part = [line for line in lines if line["route"] == route]
        if part:
            size = sum(line["characters"] for line in part)
            print(f"{route:12}{len(part):>7}{len(part) / total:>7.1%}{size:>9}{size / characters:>7.1%}"
                  f"{len(part) / len(rows):>7.1f}{sum(line['evidence'] for line in part):>9}"
                  f"{sum(line['evidence'] for line in part) / len(part):>10.1%}")
    def meaning(line, row):
        return line["route"] == "meaning"

    print("meaning-only lines by cosine similarity")
    _bands(rows, "similarity", [0, .78, .80, .81, .82, .83, .84, .85, .86, .88, .90, 1.01], meaning)
    for row in rows:
        for line in row["lines"]:
            if "similarity" in line and row.get("top_similarity") is not None:
                line["below_top"] = round(row["top_similarity"] - line["similarity"], 6)
    print("meaning-only lines by distance below the query's best similarity")
    _bands(rows, "below_top", [0, .005, .01, .02, .03, .04, .05, .07, .10, 1], meaning)
    print("meaning-only lines by rank among meaning-only lines")
    _bands(rows, "meaning_rank", list(range(11)), meaning)
    def keyword(line, row):
        return line["route"] == "keyword"

    print("keyword lines by lexical score (share of the query's weighted terms)")
    _bands(rows, "lexical", [0, .05, .1, .15, .2, .3, .4, .5, .75, 1.0, 3], keyword)
    print("keyword lines by memory-wide share of messages holding their rarest matched query term")
    _bands(rows, "rarest_share", [0, .005, .01, .02, .05, .1, .2, .3, .5, 1.01], keyword)
    print("keyword lines by memory-wide IDF coverage of the query")
    _bands(rows, "idf_coverage", [0, .1, .2, .3, .4, .5, .75, 1.01], keyword)
    print("keyword lines by rank in the offered list")
    _bands(rows, "rank", [0, 1, 3, 5, 10, 15, 20, 30, 41], keyword)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("collect", "report", "separation", "unmatched"))
    parser.add_argument("--data")
    parser.add_argument("--brains")
    parser.add_argument("--out", required=True)
    parser.add_argument("--conversations", default="0,1,2")
    parser.add_argument("--rules", default="all", help="'all' for the sweep, or comma-separated rule names")
    parser.add_argument("--max-questions", type=int, default=0)
    parser.add_argument("--deliberate", action="store_true", help="Also ask the deliberate search")
    parser.add_argument("--prompts", help="A file of prompts, one per line, asked instead of the questions")
    args = parser.parse_args()
    if args.command == "collect":
        collect(args)
    if args.command == "unmatched" or args.prompts:
        unmatched(args)
    elif args.command == "separation":
        separation(args)
    else:
        report(args)


if __name__ == "__main__":
    main()
