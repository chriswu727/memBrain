"""Compare the built passes with round 2's arms, question by question.  python analyze_built.py OUT_DIR ROUND2_RESULTS"""
import json
import sys
from pathlib import Path

SIDS = ("conv-26", "conv-30", "conv-41")
out, round2 = Path(sys.argv[1]), Path(sys.argv[2])
built = {(r["id"], r["now_label"]): r for sid in SIDS for r in map(json.loads, (out / f"built-{sid}.jsonl").open())}
old = {(r["id"], r["now_label"]): r for sid in SIDS for r in map(json.loads, (round2 / f"anchors-{sid}.jsonl").open())}
assert built.keys() == old.keys(), (len(built), len(old))
lines = []


def full(row, arm):
    return set(row[arm]) == set(row["evidence"])


for label in ("+1d", "+365d"):
    keys = [k for k in built if k[1] == label]
    lines.append(f"## {label} (n = {len(keys)})")
    for arm in ("before", "notes_plain", "built"):
        lines.append(f"- {arm}: all evidence shown {sum(full(built[k], arm) for k in keys) / len(keys):.1%}")
    for arm in ("auto", "real_turn_top", "flat"):
        lines.append(f"- round 2 {arm}: all evidence shown {sum(full(old[k], arm) for k in keys) / len(keys):.1%}")
    for mine, theirs in (("before", "auto"), ("notes_plain", "auto"), ("built", "auto"), ("built", "real_turn_top")):
        gained = [k[0] for k in keys if full(built[k], mine) and not full(old[k], theirs)]
        lost = [k[0] for k in keys if not full(built[k], mine) and full(old[k], theirs)]
        recent = [k for k in keys if max(old[k]["evidence_age_days"].values(), default=0) < (30 if label == "+1d" else 395)]
        recent_lost = [k[0] for k in recent if not full(built[k], mine) and full(old[k], theirs)]
        same = sum(set(built[k][mine]) == set(old[k][theirs]) for k in keys)
        lines.append(f"- {mine} vs round 2 {theirs}: +{len(gained)}/-{len(lost)} (net {len(gained) - len(lost):+d}); "
                     f"lost among the {len(recent)} questions whose oldest evidence is under "
                     f"{30 if label == '+1d' else 395} d: {len(recent_lost)}; identical evidence sets {same}/{len(keys)}"
                     + (f"; gained {gained}; lost {lost}" if gained or lost else ""))
    # Anchored evidence older than 90 days, the way round 2 counted it (real_turn anchors, evidence turns).
    if label == "+1d":
        for arm in ("before", "built"):
            pairs = [(k, d) for k in keys for d in built[k]["evidence"]
                     if old[k]["evidence_anchor"]["real_turn"].get(d) and old[k]["evidence_age_days"].get(d, 0) > 90]
            plain = [(k, d) for k in keys for d in built[k]["evidence"]
                     if not old[k]["evidence_anchor"]["real_turn"].get(d) and old[k]["evidence_age_days"].get(d, 0) > 90]
            lines.append(f"- {arm}: anchored evidence turns older than 90 d shown "
                         f"{sum(d in built[k][arm] for k, d in pairs) / len(pairs):.1%} of {len(pairs)}; not anchored "
                         f"{sum(d in built[k][arm] for k, d in plain) / len(plain):.1%} of {len(plain)}")
text = "\n".join(lines)
(out / "report.md").write_text(text + "\n", encoding="utf-8")
print(text)
