"""Where do the evidence turns that the first pass misses rank, and what do they look like? Development split."""
import collections, json, sys
from pathlib import Path
sys.path.insert(0, "evaluations/locomo")

def main():
    import numpy
    from retrieval_recall import RawIndex, evidence_ids, stored_turns
    from run_locomo import questions, CATEGORIES
    from membrain.local_embeddings import LocalEmbeddingProvider, installed
    data = json.loads(Path(sys.argv[1]).read_text())
    provider = LocalEmbeddingProvider(installed(Path(sys.argv[2])), threads=4)
    buckets, shown = collections.Counter(), 0
    by_category = collections.defaultdict(lambda: [0, 0])
    session_spread = collections.Counter()
    for index in (0, 1, 2):
        sample = data[index]
        turns = stored_turns(sample)
        raw = RawIndex(turns, provider)
        position = {dia: i for i, dia in enumerate(raw.ids)}
        for qid, qa in questions(sample, {1, 2, 3, 4}):
            wanted = evidence_ids(qa, turns)
            if len(wanted) < 2:
                continue
            order = raw.rank(qa["question"])
            rank = {raw.ids[i]: r for r, i in enumerate(order)}
            ranks = sorted(rank[e] for e in wanted)
            sessions = {e.split(":")[0] for e in wanted}
            session_spread[min(len(sessions), 4)] += 1
            by_category[CATEGORIES[qa["category"]]][0] += ranks[-1] < 40
            by_category[CATEGORIES[qa["category"]]][1] += 1
            for r in ranks:
                buckets["<40" if r < 40 else "40-79" if r < 80 else "80-159" if r < 160 else "160-319" if r < 320 else "320+"] += 1
            if ranks[-1] >= 40 and shown < 7 and index == 0:
                shown += 1
                print(f"\nQ: {qa['question']}   A: {qa['answer']}   ({CATEGORIES[qa['category']]})")
                for e in wanted:
                    print(f"   rank {rank[e]:>3}  {turns[e][:150]}")
    print("\nranks of evidence turns for several-evidence questions:", dict(buckets))
    print("worst rank < 40 by category:", {k: f"{a}/{b}" for k, (a, b) in by_category.items()})
    print("distinct sessions holding the evidence (4 = four or more):", dict(session_spread))

if __name__ == "__main__":
    main()
