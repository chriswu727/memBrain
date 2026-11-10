"""Raw-record retrieval at other budgets, from the stored baseline rows (no service needed)."""
import json, sys, statistics
from pathlib import Path
sys.path.insert(0, "evaluations/locomo")  # Run from the repository root.
from retrieval_recall import RawIndex, stored_turns, needles, present, CATEGORIES
from membrain.local_embeddings import LocalEmbeddingProvider, installed

data = json.loads(Path(sys.argv[1]).read_text())
rows = {}
for line in Path(sys.argv[2]).read_text().splitlines():
    row = json.loads(line); rows[row["id"]] = row
provider = LocalEmbeddingProvider(installed(Path(sys.argv[3])), threads=4)
out = []
for sample in data:
    turns, identify = stored_turns(sample), needles(sample)
    index = RawIndex(turns, provider)
    lexical = RawIndex(turns, None)
    for i, qa in enumerate(sample["qa"]):
        qid = f"{sample['sample_id']}-q{i}"
        row = rows.get(qid)
        if not row or not row["evidence"]:
            continue
        order = index.rank(qa["question"])
        def at(budget, order=order, idx=index):
            used, lines = 0, []
            for j in order:
                size = len(idx.texts[j]) + 1
                if used + size > budget: break
                lines.append(idx.texts[j]); used += size
            return present("\n".join(lines), row["evidence"], identify)
        ranks = {index.ids[j]: pos for pos, j in enumerate(order)}
        out.append({"id": qid, "category": row["category"], "n": len(row["evidence"]),
                    "M": len(row["M"]), "Mr": len(row["M_recall_only"]),
                    "R_same_recall": len(at(max(row["recall_characters"], 1))),
                    "R_5000": len(at(5000)), "R_9000": len(at(9000)), "R_total": len(at(row["characters"])),
                    "BM25_9000": len(present(lexical.context(qa["question"], 9000), row["evidence"], identify)),
                    "worst_rank": max(ranks[e] for e in row["evidence"])})
Path(sys.argv[4]).write_text(json.dumps(out))
def show(name, items):
    line = f"{name:22}{len(items):>6}"
    for key in ("Mr", "M", "R_same_recall", "R_5000", "R_9000", "BM25_9000", "R_total"):
        line += f"{sum(r[key] == r['n'] for r in items) / len(items):>10.1%}"
    print(line)
print(f"{'':22}{'n':>6}{'M recall':>10}{'M total':>10}{'R=recall':>10}{'R 5000':>10}{'R 9000':>10}{'BM25 9k':>10}{'R total':>10}")
show("all", out)
for c, name in CATEGORIES.items():
    show(name, [r for r in out if r["category"] == c])
show("one evidence turn", [r for r in out if r["n"] == 1])
show("several", [r for r in out if r["n"] > 1])
single = sorted(r["worst_rank"] for r in out if r["n"] == 1)
print("single-evidence gold rank in raw hybrid: top1 %.1f%% top5 %.1f%% top12 %.1f%% top20 %.1f%% top50 %.1f%%" % tuple(
    100 * sum(x < k for x in single) / len(single) for k in (1, 5, 12, 20, 50)))
