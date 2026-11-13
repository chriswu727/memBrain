"""Tables for weight_arms.py.   python weights_analyze.py OUT_DIR SIDS ARMS [RULE_ARMS] [COMPARE_DIR]

RULE_ARMS: the arms the fixed selection rule applies to (default: all but auto/flat).
COMPARE_DIR: an earlier results dir (importance_arms.py) whose auto/flat at +1d are compared question by question."""
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import time_depth_recall as t  # noqa: E402

out = Path(sys.argv[1])
sids, arms = sys.argv[2].split(","), sys.argv[3].split(",")
rule_arms = sys.argv[4].split(",") if len(sys.argv) > 4 and sys.argv[4] else [a for a in arms if a not in ("auto", "flat")]
compare = Path(sys.argv[5]) if len(sys.argv) > 5 else None
rows = [json.loads(line) for sid in sids for line in (out / f"weights-{sid}.jsonl").read_text().splitlines()]
meta = {sid: json.loads((out / f"meta-{sid}.json").read_text()) for sid in sids}
lines, summary = [], {"n": len(rows)}
RECENT = "under 30 d"


def ratios():
    import weight_arms

    from membrain import dynamics

    m = {"system_time": {"recorded_at": "2023-01-01T00:00:00Z"}, "dynamics": {}}
    t0 = dt.datetime(2023, 1, 1, tzinfo=dt.UTC)
    result = {}
    for arm in arms:
        if arm == "flat":
            result[arm] = 1.0
            continue
        policy = weight_arms.parse_arm(arm, dynamics.DEFAULT_POLICY) or dynamics.DEFAULT_POLICY

        def weight(days):
            return dynamics.rank_weight(dynamics.access_state(m, None, at=t0 + dt.timedelta(days=days), policy=policy),
                                        policy=policy)
        result[arm] = weight(1) / weight(180)
    return result


def full(row, arm):
    return set(row[arm]) >= set(row["evidence"])


def oldest(row):
    return max(row["evidence_age_days"].values())


def bucket(row):
    return t.bucket_of(oldest(row), 1)


ratio = ratios()
summary["ratio_1d_180d"] = {a: round(r, 3) for a, r in ratio.items()}
lines.append(f"Questions: {len(rows)} ({', '.join(f'{sid} {sum(r['id'].startswith(sid + '-') for r in rows)}' for sid in sids)})\n")
for sid in sids:
    m = meta[sid]
    msgs = m["messages"]
    lines.append(f"- {sid}: user messages {len(msgs)}, with cue {sum(x['cued'] for x in msgs)} "
                 f"({sum(x['cued'] for x in msgs) / len(msgs):.1%}); cue rows {m['cue_rows']} "
                 f"(vector {m['cue_rows_with_vector']}); cue write {m.get('cue_write')}; weight calls {m['weight_calls']}")
msgs = [x for sid in sids for x in meta[sid]["messages"]]
ev_turns = {}
for r in rows:
    for d in r["evidence"]:
        ev_turns[(r["id"].rsplit("-q", 1)[0], d)] = r["evidence_cued"][d]
pairs = [(r, d) for r in rows for d in r["evidence"]]
lines.append(f"\nCue coverage: user messages {sum(x['cued'] for x in msgs)}/{len(msgs)} = "
             f"{sum(x['cued'] for x in msgs) / len(msgs):.1%}; unique evidence turns {sum(ev_turns.values())}/{len(ev_turns)}"
             f" = {sum(ev_turns.values()) / len(ev_turns):.1%}; evidence turn-question pairs "
             f"{sum(r['evidence_cued'][d] for r, d in pairs)}/{len(pairs)}")
summary["coverage"] = {"messages": round(sum(x['cued'] for x in msgs) / len(msgs), 4),
                       "evidence_turns": round(sum(ev_turns.values()) / len(ev_turns), 4)}

groups = [("all", rows), ("one evidence", [r for r in rows if len(r["evidence"]) == 1]),
          ("several", [r for r in rows if len(r["evidence"]) > 1])]
for name, _, _ in t.buckets(1):
    groups.append((f"oldest {name}", [r for r in rows if r["evidence_age_days"] and bucket(r) == name]))
lines.append("\n### +1 d: all evidence shown % / mean evidence share %\n")
lines.append("| group | n | " + " | ".join(arms) + " |")
lines.append("|---|---|" + "---|" * len(arms))
lines.append("| ratio 1 d : 180 d | | " + " | ".join(f"{ratio[a]:.2f}" for a in arms) + " |")
for name, chosen in groups:
    cells = []
    for arm in arms:
        a = sum(full(r, arm) for r in chosen) / len(chosen)
        s = statistics.fmean(len(r[arm]) / len(r["evidence"]) for r in chosen)
        cells.append(f"{a:.1%} / {s:.1%}")
        summary.setdefault(name, {})[arm] = {"n": len(chosen), "all": round(a, 4), "share": round(s, 4)}
    lines.append(f"| {name} | {len(chosen)} | " + " | ".join(cells) + " |")

lines.append("\n### Evidence turns shown, by the turn's own age (turn-question pairs)\n")
lines.append("| turn age | pairs | " + " | ".join(arms) + " |")
lines.append("|---|---|" + "---|" * len(arms))
for name, _, _ in t.buckets(1):
    chosen = [(r, d) for r in rows for d, age in r["evidence_age_days"].items() if t.bucket_of(age, 1) == name]
    if chosen:
        lines.append(f"| {name} | {len(chosen)} | " + " | ".join(
            f"{sum(d in r[arm] for r, d in chosen) / len(chosen):.1%}" for arm in arms) + " |")

lines.append("\n### Paired counts (questions with all evidence only under the arm: gained / only under the reference: lost)\n")
lines.append("| arm | ratio | vs auto: all | net | < 30 d | vs flat: all | net | < 30 d |")
lines.append("|---|---|---|---|---|---|---|---|")
paired = {}
for arm in arms:
    cells = []
    for ref in ("auto", "flat"):
        g = [r for r in rows if full(r, arm) and not full(r, ref)]
        lo = [r for r in rows if full(r, ref) and not full(r, arm)]
        gr = sum(bucket(r) == RECENT for r in g)
        lr = sum(bucket(r) == RECENT for r in lo)
        paired[(arm, ref)] = (len(g), len(lo), gr, lr)
        cells += [f"+{len(g)}/-{len(lo)}", f"{len(g) - len(lo):+d}", f"+{gr}/-{lr}"]
    summary.setdefault("paired", {})[arm] = {ref: dict(zip(("gained", "lost", "gained_recent", "lost_recent"),
                                                           paired[(arm, ref)])) for ref in ("auto", "flat")}
    lines.append(f"| {arm} | {ratio[arm]:.2f} | " + " | ".join(cells) + " |")

n_recent = sum(bucket(r) == RECENT for r in rows)
lines.append(f"\nRecent questions (oldest evidence < 30 d): {n_recent}")
lines.append("\n### Selection rule (fixed in advance): vs auto, < 30 d loses at most 1 question and net gain >= 8; "
             "prefer the arm that favours recent memories most (largest 1 d : 180 d ratio)\n")
qualified = []
for arm in rule_arms:
    g, lo, gr, lr = paired[(arm, "auto")]
    ok = lr <= 1 and g - lo >= 8
    lines.append(f"- {arm}: ratio {ratio[arm]:.2f}, net {g - lo:+d}, recent lost {lr} -> {'QUALIFIES' if ok else 'no'}")
    if ok:
        qualified.append(arm)
chosen = max(qualified, key=lambda a: ratio[a]) if qualified else None
summary["qualified"], summary["selected"] = qualified, chosen
lines.append(f"\nQualified: {qualified or 'none'}; selected: {chosen}")

if compare:
    lines.append("\n### Against the earlier importance run (same brains with cues, +1 d)\n")
    old = {}
    for sid in sids:
        for line in (compare / f"arms-{sid}.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r["now_label"] == "+1d":
                old[r["id"]] = r
    for arm in ("auto", "flat"):
        if arm in arms:
            same = sum(set(r[arm]) == set(old[r["id"]][arm]) for r in rows)
            lines.append(f"- {arm}: identical evidence sets in {same} of {len(rows)} questions")
text = "\n".join(lines)
(out / "report.md").write_text(text + "\n", encoding="utf-8")
(out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(text)
