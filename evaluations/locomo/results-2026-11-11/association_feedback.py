"""Development split, message level: does a second pass seeded by the first-pass hits find more of the evidence?

Plain index only (BM25 and whole-message embeddings); no service. Reports questions with all evidence in the first N
messages and the mean share of evidence found, for questions with one and with several evidence turns.
"""
import collections
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, "evaluations/locomo")


def main():
    import numpy
    from retrieval_recall import WORD, RawIndex, evidence_ids, stored_turns
    from run_locomo import questions

    from membrain.local_embeddings import LocalEmbeddingProvider, installed

    data = json.loads(Path(sys.argv[1]).read_text())
    provider = LocalEmbeddingProvider(installed(Path(sys.argv[2])), threads=4)
    cut = 40
    stats = collections.defaultdict(lambda: collections.defaultdict(list))
    for index in (0, 1, 2):
        sample = data[index]
        turns = stored_turns(sample)
        raw = RawIndex(turns, provider)
        position = {dia: i for i, dia in enumerate(raw.ids)}
        total = len(raw.ids)

        def rrf(orders, weights=None):
            score = collections.defaultdict(float)
            for number, order in enumerate(orders):
                weight = 1.0 if weights is None else weights[number]
                for rank, item in enumerate(order):
                    score[item] += weight / (61 + rank)
            return sorted(score, key=lambda item: (-score[item], item))

        for qid, qa in questions(sample, {1, 2, 3, 4}):
            wanted = [position[e] for e in evidence_ids(qa, turns)]
            if not wanted:
                continue
            query = qa["question"]
            lexical = raw._bm25(query)
            vector = raw._embed([query], "query")[0]
            semantic = [int(i) for i in numpy.argsort(-(raw.vectors @ vector))]
            first = rrf([lexical, semantic])
            variants = {"0 first pass (BM25 + embedding)": first}
            for seeds in (3, 5, 10):
                centre = raw.vectors[first[:seeds]].mean(axis=0)
                for alpha in (0.5, 1.0):
                    moved = vector + alpha * centre
                    moved = moved / max(numpy.linalg.norm(moved), 1e-9)
                    second = [int(i) for i in numpy.argsort(-(raw.vectors @ moved))]
                    variants[f"1 + vector feedback, {seeds} seeds, alpha {alpha}"] = rrf([lexical, semantic, second])
            # Each seed as its own cue: what is close to a remembered message, not to their average.
            for seeds in (3, 5):
                orders = [lexical, semantic]
                for seed in first[:seeds]:
                    orders.append([int(i) for i in numpy.argsort(-(raw.vectors @ raw.vectors[seed])) if int(i) != seed])
                for weight in (0.3, 0.5):
                    variants[f"2 + each of {seeds} seeds as a cue, weight {weight}"] = rrf(
                        orders, [1.0, 1.0] + [weight] * seeds)
            # Lexical feedback: the distinctive words of the first hits join the query.
            for seeds, terms in ((5, 5), (5, 10), (10, 10)):
                counts = collections.Counter(word for seed in first[:seeds] for word in set(raw.tokens[seed]))
                asked = set(WORD.findall(query.lower()))
                scored = sorted(((count * math.log(1 + total / (1 + raw.frequency[word])), word)
                                 for word, count in counts.items() if word not in asked and len(word) > 2
                                 and raw.frequency[word] < total * 0.2), reverse=True)
                expanded = query + " " + " ".join(word for _, word in scored[:terms])
                variants[f"3 + lexical feedback, {seeds} seeds, {terms} terms"] = rrf(
                    [lexical, semantic, raw._bm25(expanded)], [1.0, 1.0, 0.5])
            group = "one" if len(wanted) == 1 else "several"
            for name, order in variants.items():
                top = set(order[:cut])
                found = sum(item in top for item in wanted)
                stats[name][group].append((found == len(wanted), found / len(wanted)))
    print(f"{'variant (first ' + str(cut) + ' messages)':52}{'one: all':>10}{'several: all':>14}{'several: share':>16}")
    for name in sorted(stats):
        one, several = stats[name]["one"], stats[name]["several"]
        print(f"{name:52}{sum(a for a, _ in one) / len(one):>10.1%}{sum(a for a, _ in several) / len(several):>14.1%}"
              f"{sum(s for _, s in several) / len(several):>16.1%}")
    print("questions: one", len(stats["0 first pass (BM25 + embedding)"]["one"]),
          "several", len(stats["0 first pass (BM25 + embedding)"]["several"]))


if __name__ == "__main__":
    main()
