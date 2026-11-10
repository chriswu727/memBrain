"""Compare two LoCoMo evidence-recall runs (retrieval_recall.py rows), e.g. a baseline and a new runtime label.

Usage: python compare_labels.py <baseline recall-*.jsonl[.gz]> <new recall-*.jsonl[.gz]>

A question "has all evidence" for an arm when every annotated evidence turn was found. Questions with no
evidence are left out of every rate. Character means and latency percentiles use every row, as
retrieval_recall.py's summary does (p50 = sorted[n // 2], p95 = sorted[min(n - 1, int(n * .95))]).
Development split: conv-26, conv-30, conv-41; every other conversation is held out.
"""
import gzip
import json
import statistics
import sys
from math import comb
from pathlib import Path

DEVELOPMENT = ("conv-26-", "conv-30-", "conv-41-")
CATEGORIES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop"}


def load(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return {row["id"]: row for row in map(json.loads, filter(str.strip, handle))}


def held_out(row):
    return not row["id"].startswith(DEVELOPMENT)


def complete(row, arm):
    return len(row[arm]) == len(row["evidence"])


def rate(rows, arm):
    scored = [row for row in rows if row["evidence"]]
    if not scored:
        return "n/a"
    hits = sum(complete(row, arm) for row in scored)
    return f"{100 * hits / len(scored):5.1f}% ({hits}/{len(scored)})"


def percentile(values, which):
    values = sorted(values)
    index = len(values) // 2 if which == 50 else min(len(values) - 1, int(len(values) * .95))
    return values[index]


def exact_mcnemar(gained, lost):
    n = gained + lost
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(gained, lost) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def report(label, rows):
    everything = list(rows.values())
    held = [row for row in everything if held_out(row)]
    development = [row for row in everything if not held_out(row)]
    print(f"== {label} ({len(everything)} rows, {sum(bool(r['evidence']) for r in everything)} with evidence)")
    print("a) all-evidence rate")
    for arm in ("M_recall_only", "M"):
        print(f"  {arm}")
        print(f"    overall      {rate(everything, arm)}")
        print(f"    development  {rate(development, arm)}")
        print(f"    held-out     {rate(held, arm)}")
        for category, name in CATEGORIES.items():
            print(f"    held-out {name:<12} {rate([r for r in held if r['category'] == category], arm)}")
        print(f"    held-out one evidence turn  {rate([r for r in held if len(r['evidence']) == 1], arm)}")
        print(f"    held-out several turns      {rate([r for r in held if len(r['evidence']) > 1], arm)}")
    print("b) mean characters (all rows)")
    for name, subset in (("overall", everything), ("held-out", held)):
        print(f"  {name:<9} recall_characters {statistics.fmean(r['recall_characters'] for r in subset):8.0f}"
              f"   characters {statistics.fmean(r['characters'] for r in subset):8.0f}")
    print("c) latency, overall (ms)")
    print(f"  prompt_ms p50 {percentile([r['prompt_ms'] for r in everything], 50)}"
          f"  p95 {percentile([r['prompt_ms'] for r in everything], 95)}"
          f"   session_ms p50 {percentile([r['session_ms'] for r in everything], 50)}")
    print("e) R (raw retrieval at this label's whole-context size) all-evidence rate")
    print(f"  overall  {rate(everything, 'R')}")
    print(f"  held-out {rate(held, 'R')}")
    print()


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    baseline_path, new_path = sys.argv[1], sys.argv[2]
    baseline, new = load(baseline_path), load(new_path)
    label = lambda path: Path(path).name.split(".")[0]
    print(f"ids: baseline {len(baseline)}, new {len(new)}, identical sets: {set(baseline) == set(new)}")
    mismatched = [i for i in baseline.keys() & new.keys() if baseline[i]["evidence"] != new[i]["evidence"]]
    print(f"questions whose evidence list differs between files: {len(mismatched)}")
    print()
    report(label(baseline_path), baseline)
    report(label(new_path), new)
    print("d) paired, held-out, M_recall_only all-evidence (baseline -> new)")
    shared = [i for i in baseline.keys() & new.keys() if baseline[i]["evidence"] and held_out(baseline[i])]
    gained = sum(not complete(baseline[i], "M_recall_only") and complete(new[i], "M_recall_only") for i in shared)
    lost = sum(complete(baseline[i], "M_recall_only") and not complete(new[i], "M_recall_only") for i in shared)
    both = sum(complete(baseline[i], "M_recall_only") and complete(new[i], "M_recall_only") for i in shared)
    neither = len(shared) - gained - lost - both
    print(f"  questions {len(shared)}: gained {gained}, lost {lost}, both {both}, neither {neither}")
    print(f"  exact two-sided McNemar (binomial) p = {exact_mcnemar(gained, lost):.3g}")


if __name__ == "__main__":
    main()
