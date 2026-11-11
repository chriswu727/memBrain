"""Would a message-level meaning route help? Development split, message-level ranks, no source change.

Each route is reduced to an ordered list of source messages. The service's own routes come from the captured
statement rankings; the message-level meaning route is the pinned model over whole stored messages.
"""
import collections
import dataclasses
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "evaluations/locomo")


def main():
    import uvicorn
    from retrieval_recall import RawIndex, evidence_ids, stored_turns
    from run_locomo import questions

    import membrain.candidates as candidates
    from membrain import desktop, embedded_database, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.local_embeddings import LocalEmbeddingProvider, installed
    from membrain.local_profile import load_profile
    from membrain.service import MemoryService

    data = json.loads(Path(sys.argv[1]).read_text())
    root = Path(sys.argv[2])
    provider = LocalEmbeddingProvider(installed(Path(sys.argv[3])), threads=4)
    capture, events_of = {}, {}
    original_direct, original_bind = candidates._direct_candidates, MemoryService._bind_document

    def direct(rankings, versions, lexical_scores, *, limit):
        capture["keyword"] = list(rankings.get("keyword", []))
        capture["vector"] = list(rankings.get("vector", []))
        capture["lexical_scores"] = dict(lexical_scores)
        ranked = original_direct(rankings, versions, lexical_scores, limit=limit)
        capture["direct"] = [(item["memory_id"], item["revision"]) for item in ranked]
        return ranked

    def bind(self, document, principal, brain):
        bound = original_bind(self, document, principal, brain)
        if "memory_id" in bound and "evidence_refs" in bound:
            events_of[(bound["memory_id"], bound["revision"])] = [
                ref["event_id"] for ref in bound["evidence_refs"] if ref["relationship"] == "supports"]
        return bound

    candidates._direct_candidates, MemoryService._bind_document = direct, bind
    limits = (10, 25, 40)
    counts, total = collections.defaultdict(collections.Counter), 0
    for index in (0, 1, 2):
        sample = data[index]
        directory = root / f"brain-{sample['sample_id']}"
        profile = load_profile(directory)
        desktop._prepare_database(profile)
        settings = dataclasses.replace(profile.settings(), recall_processes=0)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                               log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(0.1)
            turns = stored_turns(sample)
            raw = RawIndex(turns, provider)
            lexical_raw = RawIndex(turns, None)
            with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
                found, before = {}, None
                while True:
                    page = client.timeline(roles=("user",), max_characters=200_000, max_item_characters=2000, limit=200,
                                           **({"before_sequence": before} if before else {}))
                    for item in page.get("items", []):
                        found[" ".join((item.get("text") or "").split())[:120]] = item["event_id"]
                    before = page.get("next_before_sequence")
                    if page.get("complete", True) or before is None:
                        break
                by_dia = {dia: found[" ".join(text.split())[:120]] for dia, text in turns.items()
                          if " ".join(text.split())[:120] in found}
                for qid, qa in questions(sample, {1, 2, 3, 4}):
                    wanted = [by_dia[e] for e in evidence_ids(qa, turns) if e in by_dia]
                    if not wanted:
                        continue
                    capture.clear()
                    host.recall(client, qa["question"])
                    scores = capture.get("lexical_scores", {})
                    best = max(scores.values(), default=0.0)

                    def messages(keys):
                        order, strength = [], {}
                        for key in keys:
                            for event in events_of.get(key, ()):
                                if event not in strength:
                                    order.append(event)
                                strength[event] = max(strength.get(event, 0.0), scores.get(key, 0.0))
                        return order, strength

                    keyword_messages, strength = messages(capture.get("keyword", []))
                    statement_vector_messages, _ = messages(capture.get("vector", []))
                    fused_now, _ = messages(capture.get("direct", []))
                    import numpy
                    similarity = raw.vectors @ raw._embed([qa["question"]], "query")[0]
                    message_vector = [by_dia[raw.ids[i]] for i in numpy.argsort(-similarity) if raw.ids[i] in by_dia]
                    bm25_messages = [by_dia[lexical_raw.ids[i]] for i in lexical_raw._bm25(qa["question"])
                                     if lexical_raw.ids[i] in by_dia]

                    def fuse(lists):
                        totals = collections.defaultdict(float)
                        for order, weight in lists:
                            for position, event in enumerate(order):
                                totals[event] += weight(event) / (61 + position)
                        return sorted(totals, key=lambda event: (-totals[event], event))

                    damp = min(1.0, best / 0.3) ** 2 if best else 0.0
                    keyword_weight = lambda event: (strength.get(event, 0.0) / best if best else 0.0) * damp  # noqa: E731
                    one = lambda event: 1.0  # noqa: E731
                    variants = {
                        "1 service fused order (this runtime)": fused_now,
                        "2 keyword route, messages": keyword_messages,
                        "3 statement meaning route, messages": statement_vector_messages,
                        "4 message meaning route (whole messages)": message_vector,
                        "5 keyword + statement meaning x0.5": fuse([(keyword_messages, keyword_weight), (statement_vector_messages, lambda e: 0.5)]),
                        "6 keyword + message meaning x0.5": fuse([(keyword_messages, keyword_weight), (message_vector, lambda e: 0.5)]),
                        "7 keyword + message meaning x1.0": fuse([(keyword_messages, keyword_weight), (message_vector, one)]),
                        "8 keyword + message x1.0 + statement x0.5": fuse([(keyword_messages, keyword_weight), (message_vector, one), (statement_vector_messages, lambda e: 0.5)]),
                        "9 raw BM25 + message meaning (baseline)": fuse([(bm25_messages, one), (message_vector, one)]),
                        "10 raw BM25, messages": bm25_messages,
                    }
                    for event in wanted:
                        total += 1
                        for name, order in variants.items():
                            position = order.index(event) if event in order else None
                            for limit in limits:
                                counts[name][limit] += position is not None and position < limit
        finally:
            server.should_exit = True
            thread.join(timeout=20)
            embedded_database.stop(profile)
    print("evidence turns:", total, "(share whose source message ranks within N messages)")
    for name in sorted(counts, key=lambda value: int(value.split()[0])):
        print(f"  {name:46}" + "".join(f"  <{limit}: {counts[name][limit] / total:6.1%}" for limit in limits))


if __name__ == "__main__":
    main()
