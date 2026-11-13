"""Tables for importance_arms.py results.   python analyze.py OUT_DIR ORIGINAL_RUN_DIR"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

ARMS = ("auto", "flat", "cued_direct", "cued_floor_040", "cued_floor_025", "cued_slow")
SIDS = ("conv-26", "conv-30", "conv-41")
OFFSET = {"+1d": 1, "+365d": 365}

out, original = Path(sys.argv[1]), Path(sys.argv[2])
rows = [json.loads(line) for sid in SIDS for line in (out / f"arms-{sid}.jsonl").read_text().splitlines()]
meta = {sid: json.loads((out / f"meta-{sid}.json").read_text()) for sid in SIDS}
lines, summary = [], {}


def full(row, arm):
    return set(row[arm]) >= set(row["evidence"])


def rate(items, arm):
    if not items:
        return None
    return (len(items), sum(full(r, arm) for r in items) / len(items),
            statistics.fmean(len(r[arm]) / len(r["evidence"]) for r in items))


def oldest(row):
    return max(row["evidence_age_days"].values())


def groups(items, offset):
    result = [("all", items), ("one evidence", [r for r in items if len(r["evidence"]) == 1]),
              ("several", [r for r in items if len(r["evidence"]) > 1])]
    for name, _, _ in t.buckets(offset):
        result.append((f"oldest {name}", [r for r in items if r["evidence_age_days"]
                                          and t.bucket_of(oldest(r), offset) == name]))
    return result


def table(label, items, arms):
    offset = OFFSET[label]
    lines.append(f"\n### {label}: all evidence shown % / mean evidence share % (n questions)\n")
    lines.append("| group | n | " + " | ".join(arms) + " |")
    lines.append("|---|---|" + "---|" * len(arms))
    for name, chosen in groups(items, offset):
        cells = []
        for arm in arms:
            n, a, s = rate(chosen, arm)
            cells.append(f"{a:.1%} / {s:.1%}")
            summary.setdefault(label, {}).setdefault(name, {})[arm] = {"n": n, "all": round(a, 4), "share": round(s, 4)}
        lines.append(f"| {name} | {len(chosen)} | " + " | ".join(cells) + " |")
    # Paired against auto.
    lines.append(f"\n{label}: paired against auto (questions with all evidence only under the arm / only under auto),"
                 " and the same split by oldest-evidence bucket\n")
    lines.append("| arm | gained | lost | net | " + " | ".join(n for n, _, _ in t.buckets(offset)) + " |")
    lines.append("|---|---|---|---|" + "---|" * 4)
    for arm in arms[1:]:
        gained = [r for r in items if full(r, arm) and not full(r, "auto")]
        lost = [r for r in items if full(r, "auto") and not full(r, arm)]
        per = []
        for name, _, _ in t.buckets(offset):
            g = sum(t.bucket_of(oldest(r), offset) == name for r in gained)
            lo = sum(t.bucket_of(oldest(r), offset) == name for r in lost)
            per.append(f"+{g}/-{lo}")
        summary.setdefault(label + " paired", {})[arm] = {"gained": len(gained), "lost": len(lost)}
        lines.append(f"| {arm} | {len(gained)} | {len(lost)} | {len(gained) - len(lost):+d} | " + " | ".join(per) + " |")
    # Evidence turns by their own age, and by cue.
    lines.append(f"\n{label}: evidence turns shown, by the turn's own age (turn-question pairs)\n")
    lines.append("| turn age | pairs | " + " | ".join(arms) + " |")
    lines.append("|---|---|" + "---|" * len(arms))
    for name, _, _ in t.buckets(offset):
        pairs = [(r, d) for r in items for d, age in r["evidence_age_days"].items() if t.bucket_of(age, offset) == name]
        if pairs:
            lines.append(f"| {name} | {len(pairs)} | " + " | ".join(
                f"{sum(d in r[arm] for r, d in pairs) / len(pairs):.1%}" for arm in arms) + " |")
    lines.append(f"\n{label}: evidence turns shown, cued vs uncued turns (turn-question pairs)\n")
    lines.append("| evidence turn | pairs | " + " | ".join(arms) + " |")
    lines.append("|---|---|" + "---|" * len(arms))
    for flag, name in ((True, "cued"), (False, "uncued")):
        pairs = [(r, d) for r in items for d in r["evidence"] if r["evidence_cued"][d] is flag]
        lines.append(f"| {name} | {len(pairs)} | " + " | ".join(
            f"{sum(d in r[arm] for r, d in pairs) / len(pairs):.1%}" for arm in arms) + " |")
        for bname, _, _ in t.buckets(offset):
            sub = [(r, d) for r, d in pairs if d in r["evidence_age_days"]
                   and t.bucket_of(r["evidence_age_days"][d], offset) == bname]
            if sub:
                lines.append(f"| {name}, {bname} | {len(sub)} | " + " | ".join(
                    f"{sum(d in r[arm] for r, d in sub) / len(sub):.1%}" for arm in arms) + " |")


# Coverage ------------------------------------------------------------------------------------------------------
lines.append("## Cue coverage (session-written cues, cues.json.gz, deepseek-flash)\n")
for sid in SIDS:
    m = meta[sid]
    lines.append(f"- {sid}: {m['cue_items']} cue items sent, write {m['cue_write']}, rows {m['cue_rows']} "
                 f"(with vector {m['cue_rows_with_vector']}), stored user messages {len(m['messages'])}, "
                 f"weight calls {m.get('weight_calls')}")
plus1 = [r for r in rows if r["now_label"] == "+1d"]
now_by_sid = {sid: t.stamp(next(r["now"] for r in plus1 if r["id"].startswith(sid + "-"))) for sid in SIDS}
msgs = [(sid, m) for sid in SIDS for m in meta[sid]["messages"]]
lines.append("\n| stored user messages | n | with cue |\n|---|---|---|")
lines.append(f"| all | {len(msgs)} | {sum(m['cued'] for _, m in msgs) / len(msgs):.1%} |")
for name, _, _ in t.buckets(1):
    sub = [m for sid, m in msgs if t.bucket_of((now_by_sid[sid] - t.stamp(m["recorded_at"])).total_seconds() / 86400, 1) == name]
    lines.append(f"| age {name} at +1 d | {len(sub)} | {sum(m['cued'] for m in sub) / len(sub):.1%} |")
evidence_turns = {}
for r in plus1:
    sid = r["id"].rsplit("-q", 1)[0]
    for d in r["evidence"]:
        evidence_turns[(sid, d)] = (r["evidence_cued"][d], r["evidence_age_days"].get(d))
lines.append("\n| unique evidence turns | n | with cue |\n|---|---|---|")
values = list(evidence_turns.values())
lines.append(f"| all | {len(values)} | {sum(c for c, _ in values) / len(values):.1%} |")
for name, _, _ in t.buckets(1):
    sub = [c for c, age in values if age is not None and t.bucket_of(age, 1) == name]
    lines.append(f"| age {name} at +1 d | {len(sub)} | {sum(sub) / len(sub):.1%} |")
pairs = [(r, d) for r in plus1 for d in r["evidence"]]
lines.append(f"\nEvidence turn-question pairs with a cue: {sum(r['evidence_cued'][d] for r, d in pairs)} of {len(pairs)}"
             f" ({sum(r['evidence_cued'][d] for r, d in pairs) / len(pairs):.1%}); questions with at least one cued "
             f"evidence turn: {sum(any(r['evidence_cued'].values()) for r in plus1)} of {len(plus1)}; with all evidence "
             f"cued: {sum(all(r['evidence_cued'].values()) for r in plus1)}")

# Tables ----------------------------------------------------------------------------------------------------------
lines.append("\n## Recall per arm")
table("+1d", plus1, ARMS)
plus365 = [r for r in rows if r["now_label"] == "+365d"]
table("+365d", plus365, ARMS)

# Candidates diagnostic ------------------------------------------------------------------------------------------
lines.append("\n## Candidates at +1 d under auto (before the cut to the candidate limit)\n")
cands = [r["candidates"] for r in plus1 if "candidates" in r]
share = [c["cued"] / c["n"] for c in cands if c["n"]]
ca = [c["cued_mean_age"] for c in cands if c["cued_mean_age"] is not None]
ua = [c["uncued_mean_age"] for c in cands if c["uncued_mean_age"] is not None]
pooled_c = sum(c["cued"] for c in cands)
pooled_n = sum(c["n"] for c in cands)
pooled_ca = sum(c["cued_mean_age"] * c["cued"] for c in cands if c["cued"]) / max(pooled_c, 1)
pooled_ua = sum(c["uncued_mean_age"] * (c["n"] - c["cued"]) for c in cands if c["n"] - c["cued"]) / max(pooled_n - pooled_c, 1)
ev_n = sum(c["evidence_statements"] for c in cands)
ev_c = sum(c["evidence_cued"] for c in cands)
lines.append(f"- questions {len(cands)}, candidates per question {statistics.fmean(c['n'] for c in cands):.1f}; "
             f"any direct-weighted candidate: {sum(c['direct_any'] for c in cands)}")
lines.append(f"- share of candidates that are cued: mean per question {statistics.fmean(share):.1%} "
             f"(median {statistics.median(share):.1%}); pooled {pooled_c}/{pooled_n} = {pooled_c / pooled_n:.1%}")
lines.append(f"- mean age, cued candidates: {statistics.fmean(ca):.1f} d (mean of per-question means), pooled {pooled_ca:.1f} d")
lines.append(f"- mean age, uncued candidates: {statistics.fmean(ua):.1f} d (mean of per-question means), pooled {pooled_ua:.1f} d")
lines.append(f"- evidence statements among candidates: {ev_n}, of which cued {ev_c} ({ev_c / max(ev_n, 1):.1%})")
shown = [(r, d) for r in plus1 for d in r["auto"]]
lines.append(f"- evidence turns shown under auto at +1 d: {len(shown)}; cued {sum(r['evidence_cued'][d] for r, d in shown)}, "
             f"uncued {sum(not r['evidence_cued'][d] for r, d in shown)}")

# Against the earlier no-cue run -----------------------------------------------------------------------------------
lines.append("\n## Against the original brains without cues (2026-11-12 run)\n")
for label in ("+1d", "+365d"):
    old = {}
    for sid in SIDS:
        for line in (original / f"recall-{sid}-{label}.jsonl").read_text().splitlines():
            row = json.loads(line)
            old[row["id"]] = row
    mine = [r for r in rows if r["now_label"] == label]
    for arm, old_arm in (("auto", "auto"), ("flat", "auto_flat")):
        a_old = sum(set(old[r["id"]][old_arm]) >= set(r["evidence"]) for r in mine) / len(mine)
        a_new = sum(full(r, arm) for r in mine) / len(mine)
        s_old = statistics.fmean(len(old[r["id"]][old_arm]) / len(r["evidence"]) for r in mine)
        s_new = statistics.fmean(len(r[arm]) / len(r["evidence"]) for r in mine)
        gained = sum(full(r, arm) and not set(old[r["id"]][old_arm]) >= set(r["evidence"]) for r in mine)
        lost = sum(not full(r, arm) and set(old[r["id"]][old_arm]) >= set(r["evidence"]) for r in mine)
        differ = sum(set(r[arm]) != set(old[r["id"]][old_arm]) for r in mine)
        lines.append(f"- {label} {arm}: without cues {a_old:.1%} / {s_old:.1%}, with cues {a_new:.1%} / {s_new:.1%} "
                     f"({a_new - a_old:+.1%}); questions gained {gained}, lost {lost}; evidence sets differ in {differ}")
        summary.setdefault("vs no cues", {})[f"{label} {arm}"] = {"without": round(a_old, 4), "with": round(a_new, 4),
                                                                  "gained": gained, "lost": lost}
    if label == "+1d":
        for arm in ARMS:
            pass

# Identity checks.
lines.append(f"\n- +1d flat equals +365d flat question for question: "
             f"{sum(set(a['flat']) == set(b['flat']) for a, b in zip(plus1, plus365))} of {len(plus1)}")
text = "\n".join(lines)
(out / "report.md").write_text(text + "\n", encoding="utf-8")
(out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(text)
