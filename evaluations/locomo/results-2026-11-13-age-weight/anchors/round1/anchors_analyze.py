"""Tables for anchor_arms.py.   python anchors_analyze.py OUT_DIR [COMPARE_WEIGHTS_DEV_DIR]"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

SIDS = ("conv-26", "conv-30", "conv-41")
SETS = ("turn", "session")
OFFSET = {"+1d": 1, "+365d": 365}
out = Path(sys.argv[1])
rows = [json.loads(line) for sid in SIDS for line in (out / f"anchors-{sid}.jsonl").read_text().splitlines()]
meta = {sid: json.loads((out / f"meta-{sid}.json").read_text()) for sid in SIDS}
lines, summary = [], {}


def full(r, a):
    return set(r[a]) >= set(r["evidence"])


def oldest_bucket(r, offset):
    return t.bucket_of(max(r["evidence_age_days"].values()), offset)


lines.append("Meta: " + "; ".join(f"{sid} floor {m['rank_floor']} cues {m['cue_rows']} anchored events "
                                    f"{m['anchored_events']} of anchor turns {m['anchor_turns']}" for sid, m in meta.items()))
by_label = {label: [r for r in rows if r["now_label"] == label] for label in OFFSET}
for label, offset in OFFSET.items():
    items = by_label[label]
    recent_name = t.buckets(offset)[0][0]
    arms = ["auto", "flat"] + [f"{s}_{k}" for s in SETS for k in ("direct", "fresh", "floor")]
    lines.append(f"\n## {label} (n = {len(items)}): all evidence shown % / mean evidence share %\n")
    lines.append("| group | n | " + " | ".join(arms) + " |")
    lines.append("|---|---|" + "---|" * len(arms))
    groups = [("all", items), ("one evidence", [r for r in items if len(r["evidence"]) == 1]),
              ("several", [r for r in items if len(r["evidence"]) > 1])]
    groups += [(f"oldest {name}", [r for r in items if oldest_bucket(r, offset) == name]) for name, _, _ in t.buckets(offset)]
    for name, chosen in groups:
        cells = []
        for arm in arms:
            a = sum(full(r, arm) for r in chosen) / len(chosen)
            s = statistics.fmean(len(r[arm]) / len(r["evidence"]) for r in chosen)
            cells.append(f"{a:.1%} / {s:.1%}")
            summary.setdefault(label, {}).setdefault(name, {})[arm] = [len(chosen), round(a, 4), round(s, 4)]
        lines.append(f"| {name} | {len(chosen)} | " + " | ".join(cells) + " |")
    lines.append(f"\n{label}: paired against auto (gained / lost), overall and in the {recent_name} bucket\n")
    lines.append("| arm | all | net | " + recent_name + " |\n|---|---|---|---|")
    for arm in arms[1:]:
        g = [r for r in items if full(r, arm) and not full(r, "auto")]
        lo = [r for r in items if full(r, "auto") and not full(r, arm)]
        gr = sum(oldest_bucket(r, offset) == recent_name for r in g)
        lr = sum(oldest_bucket(r, offset) == recent_name for r in lo)
        summary.setdefault(f"{label} paired", {})[arm] = {"gained": len(g), "lost": len(lo), "gained_recent": gr,
                                                          "lost_recent": lr}
        lines.append(f"| {arm} | +{len(g)}/-{len(lo)} | {len(g) - len(lo):+d} | +{gr}/-{lr} |")
    for s in SETS:
        set_arms = ["auto", "flat", f"{s}_direct", f"{s}_fresh", f"{s}_floor"]
        lines.append(f"\n{label}: evidence turns shown, {s} anchors: anchored vs not anchored, by the turn's age\n")
        lines.append("| evidence turns | pairs | " + " | ".join(set_arms) + " |")
        lines.append("|---|---|" + "---|" * len(set_arms))
        for flag, fname in ((True, "anchored"), (False, "not anchored")):
            pairs = [(r, d) for r in items for d in r["evidence"] if r["evidence_anchor"][s][d] is flag]
            groups = [("all ages", pairs)] + [(name, [(r, d) for r, d in pairs if d in r["evidence_age_days"] and
                                                     t.bucket_of(r["evidence_age_days"][d], offset) == name])
                                              for name, _, _ in t.buckets(offset)]
            if offset == 1:
                groups.append(("older than 90 d", [(r, d) for r, d in pairs if r["evidence_age_days"].get(d, 0) >= 90]))
            for gname, sub in groups:
                if not sub:
                    continue
                shares = {arm: sum(d in r[arm] for r, d in sub) / len(sub) for arm in set_arms}
                summary.setdefault(f"{label} turns {s}", {})[f"{fname} {gname}"] = {"pairs": len(sub), **{
                    arm: round(v, 4) for arm, v in shares.items()}}
                lines.append(f"| {fname}, {gname} | {len(sub)} | " + " | ".join(f"{shares[a]:.1%}" for a in set_arms) + " |")

cands = [r["candidates"] for r in by_label["+1d"] if "candidates" in r]
lines.append("\n## Candidates at +1 d under auto\n")
lines.append(f"- {len(cands)} questions, {statistics.fmean(c['n'] for c in cands):.1f} candidates per question, "
             f"mean age {statistics.fmean(c['mean_age'] for c in cands if c['mean_age'] is not None):.1f} d")
for s in SETS:
    share = [c[s] / c["n"] for c in cands if c["n"]]
    ages = [c[f"{s}_mean_age"] for c in cands if c[f"{s}_mean_age"] is not None]
    lines.append(f"- {s} anchors: share of candidates anchored, mean per question {statistics.fmean(share):.1%} "
                 f"(median {statistics.median(share):.1%}, pooled {sum(c[s] for c in cands)}/{sum(c['n'] for c in cands)}); "
                 f"mean age of anchored candidates {statistics.fmean(ages):.1f} d")

lines.append("\n## Rule (fixed in advance)\n")
for s in SETS:
    for kind in ("direct", "fresh", "floor"):
        arm = f"{s}_{kind}"
        p1, p365 = summary["+1d paired"][arm], summary["+365d paired"][arm]
        acceptable = p1["lost_recent"] <= 1 and p365["gained"] - p365["lost"] >= -1
        turns = summary[f"+1d turns {s}"]
        a_old = turns["anchored older than 90 d"][arm] - turns["anchored older than 90 d"]["auto"]
        n_old = turns["not anchored older than 90 d"][arm] - turns["not anchored older than 90 d"]["auto"]
        n_all = turns["not anchored all ages"][arm] - turns["not anchored all ages"]["auto"]
        net1 = p1["gained"] - p1["lost"]
        worth = acceptable and (net1 >= 4 or (a_old >= 0.05 and n_old >= -0.01))
        summary.setdefault("rule", {})[arm] = {"acceptable": acceptable, "worth_building": worth}
        lines.append(f"- {arm}: +1d recent lost {p1['lost_recent']}, +365d net {p365['gained'] - p365['lost']:+d} -> "
                     f"{'ACCEPTABLE' if acceptable else 'not acceptable'}; +1d net {net1:+d}; anchored >90 d shown "
                     f"{a_old:+.1%}, not anchored >90 d {n_old:+.1%} (all ages {n_all:+.1%}) -> "
                     f"{'WORTH BUILDING' if worth else 'not worth building'}")
if len(sys.argv) > 2:
    dev = Path(sys.argv[2])
    old = {}
    for sid in SIDS:
        for line in (dev / f"weights-{sid}.jsonl").read_text().splitlines():
            r = json.loads(line)
            old[r["id"]] = r
    plus1 = by_label["+1d"]
    lines.append("\n## Check against Part 1 of the floor run (same brains, +1 d)\n")
    lines.append(f"- auto (floor 0.30 shipped) vs f030 then: identical sets in "
                 f"{sum(set(r['auto']) == set(old[r['id']]['f030']) for r in plus1)} of {len(plus1)}")
    lines.append(f"- flat vs flat then: identical sets in {sum(set(r['flat']) == set(old[r['id']]['flat']) for r in plus1)}"
                 f" of {len(plus1)}")
text = "\n".join(lines)
(out / "report.md").write_text(text + "\n", encoding="utf-8")
(out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(text)
