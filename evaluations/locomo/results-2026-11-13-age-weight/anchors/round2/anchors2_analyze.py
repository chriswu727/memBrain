"""Tables for anchor_arms2.py.   python anchors2_analyze.py OUT_DIR [ROUND1_RESULTS_DIR]"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

SIDS = ("conv-26", "conv-30", "conv-41")
REAL = ("real_turn", "real_session")
SETS = REAL + ("matched_turn", "matched_session")
ARMS = ["auto", "flat"] + [f"{s}_top" for s in SETS] + [f"{s}_fresh" for s in REAL]
OFFSET = {"+1d": 1, "+365d": 365}
out = Path(sys.argv[1])
rows = [json.loads(line) for sid in SIDS for line in (out / f"anchors-{sid}.jsonl").read_text().splitlines()]
meta = {sid: json.loads((out / f"meta-{sid}.json").read_text()) for sid in SIDS}
lines, summary = [], {}


def full(r, a):
    return set(r[a]) >= set(r["evidence"])


def oldest_bucket(r, offset):
    return t.bucket_of(max(r["evidence_age_days"].values()), offset)


for sid, m in meta.items():
    lines.append(f"- {sid}: floor {m['rank_floor']}; anchored events {m['anchored_events']} (anchor turns "
                 f"{m['anchor_turns']}); top lifts +1d {m['top_stats_+1d']}, +365d {m['top_stats_+365d']}")
by_label = {label: [r for r in rows if r["now_label"] == label] for label in OFFSET}
for label, offset in OFFSET.items():
    items = by_label[label]
    recent = t.buckets(offset)[0][0]
    lines.append(f"\n## {label} (n = {len(items)}): all evidence shown % / mean evidence share %\n")
    lines.append("| group | n | " + " | ".join(ARMS) + " |")
    lines.append("|---|---|" + "---|" * len(ARMS))
    groups = [("all", items), ("one evidence", [r for r in items if len(r["evidence"]) == 1]),
              ("several", [r for r in items if len(r["evidence"]) > 1])]
    groups += [(f"oldest {name}", [r for r in items if oldest_bucket(r, offset) == name]) for name, _, _ in t.buckets(offset)]
    for name, chosen in groups:
        cells = []
        for arm in ARMS:
            a = sum(full(r, arm) for r in chosen) / len(chosen)
            s = statistics.fmean(len(r[arm]) / len(r["evidence"]) for r in chosen)
            cells.append(f"{a:.1%} / {s:.1%}")
            summary.setdefault(label, {}).setdefault(name, {})[arm] = [len(chosen), round(a, 4), round(s, 4)]
        lines.append(f"| {name} | {len(chosen)} | " + " | ".join(cells) + " |")
    lines.append(f"\n{label}: paired against auto (gained / lost), overall and in the {recent} bucket; "
                 "identical evidence sets\n")
    lines.append(f"| arm | all | net | {recent} | identical sets |\n|---|---|---|---|---|")
    for arm in ARMS[1:]:
        g = [r for r in items if full(r, arm) and not full(r, "auto")]
        lo = [r for r in items if full(r, "auto") and not full(r, arm)]
        gr = sum(oldest_bucket(r, offset) == recent for r in g)
        lr = sum(oldest_bucket(r, offset) == recent for r in lo)
        same = sum(set(r[arm]) == set(r["auto"]) for r in items)
        summary.setdefault(f"{label} paired", {})[arm] = {"gained": len(g), "lost": len(lo), "gained_recent": gr,
                                                          "lost_recent": lr, "identical": same}
        lines.append(f"| {arm} | +{len(g)}/-{len(lo)} | {len(g) - len(lo):+d} | +{gr}/-{lr} | {same}/{len(items)} |")
    for s in SETS:
        set_arms = ["auto", "flat", f"{s}_top"] + ([f"{s}_fresh"] if s in REAL else [])
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
             f"mean age {statistics.fmean(c['mean_age'] for c in cands if c['mean_age'] is not None):.1f} d, mean of the "
             f"per-question highest weight {statistics.fmean(c['max_weight'] for c in cands if c['max_weight']):.3f}")
for s in SETS:
    share = [c[s] / c["n"] for c in cands if c["n"]]
    ages = [c[f"{s}_mean_age"] for c in cands if c[f"{s}_mean_age"] is not None]
    lines.append(f"- {s}: share of candidates anchored, mean per question {statistics.fmean(share):.1%} "
                 f"(pooled {sum(c[s] for c in cands)}/{sum(c['n'] for c in cands)}); mean age of anchored candidates "
                 f"{statistics.fmean(ages):.1f} d")

lines.append("\n## Rule (fixed in advance)\n")
for arm in ARMS[2:]:
    s = arm.rsplit("_", 1)[0]
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

lines.append("\n## +365 d: top arms against auto, question by question\n")
for s in SETS:
    differ = [r["id"] for r in by_label["+365d"] if set(r[f"{s}_top"]) != set(r["auto"])]
    lines.append(f"- {s}_top differs from auto in {len(differ)} of {len(by_label['+365d'])}: {differ[:12]}")
if len(sys.argv) > 2:
    old = {}
    for sid in SIDS:
        for line in (Path(sys.argv[2]) / f"anchors-{sid}.jsonl").read_text().splitlines():
            r = json.loads(line)
            old[(r["id"], r["now_label"])] = r
    for arm in ("auto", "flat"):
        same = sum(set(r[arm]) == set(old[(r["id"], r["now_label"])][arm]) for r in rows)
        lines.append(f"- {arm} identical to round 1 in {same} of {len(rows)} question-times")
text = "\n".join(lines)
(out / "report.md").write_text(text + "\n", encoding="utf-8")
(out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(text)
