"""Paired comparison of persona_cost.py states: which questions lose or gain all-evidence, and where the evidence was."""
import json
import statistics
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"
rows = [json.loads(line) for line in (OUT / "rows.jsonl").read_text().splitlines()]
by = {(row["state"], row["id"]): row for row in rows}
ids = sorted({row["id"] for row in rows if row["state"] == "A" and row["evidence"]})


def full(row, arm="M"):
    return len(row[arm]) == len(row["evidence"])


def table():
    print(f"{'state':6}{'n':>5}{'whole all':>10}{'whole sh':>9}{'sess all':>9}{'sess sh':>8}{'recall all':>11}"
          f"{'recall sh':>10}{'hist all':>9}{'sess ch':>9}{'hist ch':>8}{'hist msg':>9}{'persona':>8}{'mood':>6}"
          f"{'rel':>6}{'recall ch':>10}")
    for state in ("A", "B", "C"):
        items = [by[(state, qid)] for qid in ids if (state, qid) in by]
        if not items:
            continue
        everything = [row for row in rows if row["state"] == state]

        def share(arm):
            return statistics.fmean(len(row[arm]) / len(row["evidence"]) for row in items)

        def rate(arm):
            return sum(full(row, arm) for row in items) / len(items)

        def mean(name):
            return statistics.fmean(row[name] for row in everything)

        print(f"{state:6}{len(items):>5}{rate('M'):>10.1%}{share('M'):>9.1%}{rate('session_only'):>9.1%}"
              f"{share('session_only'):>8.1%}{rate('M_recall_only'):>11.1%}{share('M_recall_only'):>10.1%}"
              f"{rate('history_only'):>9.1%}{mean('session_characters'):>9.0f}{mean('history_characters'):>8.0f}"
              f"{mean('history_messages'):>9.1f}{mean('persona_characters'):>8.0f}{mean('mood_characters'):>6.0f}"
              f"{mean('relationship_characters'):>6.0f}{mean('recall_characters'):>10.0f}")


def paired(base, other):
    lost = [qid for qid in ids if (other, qid) in by and full(by[(base, qid)]) and not full(by[(other, qid)])]
    gained = [qid for qid in ids if (other, qid) in by and not full(by[(base, qid)]) and full(by[(other, qid)])]
    print(f"\n{base} -> {other}: all-evidence in {base} not {other}: {len(lost)}; in {other} not {base}: {len(gained)}")
    where = Counter()
    turn_lost = turn_gained = 0
    for qid in ids:
        if (other, qid) not in by:
            continue
        a, b = by[(base, qid)], by[(other, qid)]
        for turn in set(a["M"]) - set(b["M"]):
            turn_lost += 1
            place = ("history" if turn in a["history_only"] else "session-other" if turn in a["session_only"]
                     else "recall-only")
            where[place + (", also in recall" if turn in a["M_recall_only"] and place != "recall-only" else "")] += 1
        turn_gained += len(set(b["M"]) - set(a["M"]))
    print(f"  evidence turns lost {turn_lost}, gained {turn_gained}; where the lost turns were in {base}: {dict(where)}")
    recall_changed = sum(1 for qid in ids if (other, qid) in by
                         and set(by[(base, qid)]["M_recall_only"]) != set(by[(other, qid)]["M_recall_only"]))
    print(f"  questions whose recall-block evidence set differs: {recall_changed}")
    for qid in lost[:40]:
        a, b = by[(base, qid)], by[(other, qid)]
        missing = sorted(set(a["M"]) - set(b["M"]))
        print(f"  lost {qid}: missing {missing}; in {base} history {[t in a['history_only'] for t in missing]}")
    deltas = [by[(base, qid)]["history_characters"] - by[(other, qid)]["history_characters"] for qid in ids
              if (other, qid) in by]
    msgs = [by[(base, qid)]["history_messages"] - by[(other, qid)]["history_messages"] for qid in ids
            if (other, qid) in by]
    print(f"  history shorter by {statistics.fmean(deltas):.0f} characters, {statistics.fmean(msgs):.2f} messages "
          f"on average (min/max messages {min(msgs)}/{max(msgs)})")
    for conversation in sorted({row["conversation"] for row in rows}):
        items = [qid for qid in ids if qid.startswith(conversation + "-") and (other, qid) in by]
        if items:
            print(f"   {conversation}: history msgs {base} {statistics.fmean(by[(base, q)]['history_messages'] for q in items):.1f}"
                  f" {other} {statistics.fmean(by[(other, q)]['history_messages'] for q in items):.1f};"
                  f" whole all-evidence {base} {sum(full(by[(base, q)]) for q in items)}/{len(items)}"
                  f" {other} {sum(full(by[(other, q)]) for q in items)}/{len(items)}")


table()
paired("A", "B")
paired("A", "C")
paired("B", "C")
