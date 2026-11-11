"""Development-split diagnostic: at which stage of the service's ranking is each evidence turn lost?

Runs the real service in this process (one thread, no recall worker pool) so the candidate stages can be observed.
No source file is changed; module functions are wrapped in memory only.
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
    from retrieval_recall import evidence_ids, stored_turns
    from run_locomo import questions

    import membrain.candidates as candidates
    from membrain import desktop, embedded_database, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.local_profile import load_profile
    from membrain.service import MemoryService

    data = json.loads(Path(sys.argv[1]).read_text())
    root = Path(sys.argv[2])
    capture, events_of = {}, {}
    original_direct, original_collect, original_bind = (candidates._direct_candidates, candidates.collect_candidates,
                                                        MemoryService._bind_document)

    def direct(rankings, versions, lexical_scores, *, limit):
        capture["keyword"] = list(rankings.get("keyword", []))
        capture["vector"] = list(rankings.get("vector", []))
        capture["lexical_scores"] = dict(lexical_scores)
        ranked = original_direct(rankings, versions, lexical_scores, limit=limit)
        capture["direct"] = [(item["memory_id"], item["revision"]) for item in ranked]
        return ranked

    def collect(*args, **kwargs):
        memories, state = original_collect(*args, **kwargs)
        capture["roots"] = list(state["candidate_versions"])
        return memories, state

    def bind(self, document, principal, brain):
        bound = original_bind(self, document, principal, brain)
        if "memory_id" in bound and "evidence_refs" in bound:  # Events are bound by the same method.
            events_of[(bound["memory_id"], bound["revision"])] = {
                ref["event_id"] for ref in bound["evidence_refs"] if ref["relationship"] == "supports"}
        return bound

    candidates._direct_candidates, candidates.collect_candidates, MemoryService._bind_document = direct, collect, bind
    stages = ["keyword", "vector", "direct", "roots", "response", "selected"]
    cut = {"keyword": (10, 62, 248), "vector": (10, 62, 248), "direct": (10, 62, 248), "roots": (62,)}
    counts, total = collections.Counter(), 0
    simulated = collections.defaultdict(collections.Counter)
    meaning_only = collections.defaultdict(collections.Counter)
    lost = collections.Counter()
    lexical_gold, lexical_top = [], []
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
                    response = host.recall(client, qa["question"])
                    items = (response.get("result") or {}).get("items", [])
                    in_response = {ref["event_id"] for item in items
                                   for ref in (item.get("memory") or {}).get("evidence_refs") or []}
                    selected = {event for event, _ in host._sources(response, "diagnostic")}

                    def rank(name, event):
                        for position, key in enumerate(capture.get(name, [])):
                            if event in events_of.get(key, ()):
                                return position
                        return None

                    scores = capture.get("lexical_scores", {})
                    best = max(scores.values(), default=0.0)
                    keyword_list, vector_list = capture.get("keyword", []), capture.get("vector", [])

                    def fused(keyword_weight, vector_weight=1.0):
                        totals = collections.defaultdict(float)
                        seen = set()
                        for position, key in enumerate(k for k in keyword_list if not (k in seen or seen.add(k))):
                            totals[key] += keyword_weight(key) / (61 + position)
                        seen = set()
                        for position, key in enumerate(k for k in vector_list if not (k in seen or seen.add(k))):
                            totals[key] += vector_weight / (61 + position)
                        return sorted(totals, key=lambda key: (-totals[key], key))

                    def proportional(floor, power=1.0):
                        # In proportion to the best lexical match; all of it scaled down when even the best is weak.
                        damp = min(1.0, best / floor) ** 2 if best else 0.0
                        return lambda key: ((scores.get(key, 0.0) / best) ** power if best else 0.0) * damp

                    variants = {
                        "A before (score/max(1,best), vector 1)": fused(lambda key: scores.get(key, 0.0) / max(1.0, best)),
                        "S saturating 0.2 squared, vector 0.5": fused(lambda key: min(1.0, (scores.get(key, 0.0) / 0.2) ** 2), 0.5),
                        "Y1 proportional floor 0.3, vector 0.5": fused(proportional(0.3), 0.5),
                        "Y3 proportional floor 0.3, vector 0.35": fused(proportional(0.3), 0.35),
                        "Y4 proportional floor 0.3, vector 0.25": fused(proportional(0.3), 0.25),
                        "Y8 proportional floor 0.3, vector 0.15": fused(proportional(0.3), 0.15),
                    }
                    keyword_events = set().union(*(events_of.get(key, set()) for key in keyword_list)) if keyword_list else set()
                    for name, order in variants.items():
                        for event in wanted:
                            position = next((i for i, key in enumerate(order) if event in events_of.get(key, ())), None)
                            for limit in (10, 25, 62):
                                simulated[name][limit] += position is not None and position < limit
                            if event not in keyword_events:  # Reachable by meaning only.
                                meaning_only[name]["n"] += 1
                                for limit in (10, 25, 62):
                                    meaning_only[name][limit] += position is not None and position < limit
                        # distinct source messages reached within the first 62 statements
                    for event in wanted:
                        total += 1
                        positions = {name: rank(name, event) for name in ("keyword", "vector", "direct", "roots")}
                        for name, limits in cut.items():
                            for limit in limits:
                                counts[f"{name}<{limit}"] += positions[name] is not None and positions[name] < limit
                            counts[f"{name} any"] += positions[name] is not None
                        counts["response"] += event in in_response
                        counts["selected"] += event in selected
                        gold_score = max((score for key, score in scores.items() if event in events_of.get(key, ())), default=0.0)
                        lexical_gold.append(gold_score)
                        lexical_top.append(best)
                        if event not in selected:
                            if positions["keyword"] is None and positions["vector"] is None:
                                lost["in neither channel's list"] += 1
                            elif positions["direct"] is not None and positions["direct"] >= 62:
                                lost["fused rank beyond 62"] += 1
                            elif positions["roots"] is None:
                                lost["fused within 62 but not kept as a root (source-unit / neighbours / weighting)"] += 1
                            elif event not in in_response:
                                lost["root but cut by the token budget"] += 1
                            else:
                                lost["in response but dropped by the host"] += 1
        finally:
            server.should_exit = True
            thread.join(timeout=20)
            embedded_database.stop(profile)
    print("evidence turns:", total)
    for name in sorted(counts):
        print(f"  {name:16}{counts[name] / total:7.1%}")
    print("simulated fusion of the captured channel lists (evidence turns ranked within N statements):")
    for name in sorted(simulated):
        print(f"  {name:44}" + "".join(f"  <{limit}: {simulated[name][limit] / total:6.1%}" for limit in (10, 25, 62)))
    print("evidence turns with no keyword match (reachable by meaning only), ranked within N statements:")
    for name in sorted(meaning_only):
        n = meaning_only[name]["n"]
        print(f"  {name:44} n={n}" + "".join(f"  <{limit}: {meaning_only[name][limit] / max(1, n):6.1%}" for limit in (10, 25, 62)))
    print("where the unselected ones were lost:")
    for name, count in lost.most_common():
        print(f"  {count:4} ({count / total:5.1%})  {name}")
    import statistics
    print("lexical score of the gold statement: mean %.3f, zero for %.1f%%; best lexical score in the list: mean %.3f" % (
        statistics.fmean(lexical_gold), 100 * sum(score == 0 for score in lexical_gold) / len(lexical_gold),
        statistics.fmean(lexical_top)))


if __name__ == "__main__":
    main()
