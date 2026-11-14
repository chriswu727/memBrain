"""Anchors (turns a note was matched to, similarity >= threshold) and their coverage. No database.

    python anchor_stats.py matches.json THRESHOLD locomo10.json WEIGHTS_DEV_DIR OUT_DIR
WEIGHTS_DEV_DIR supplies stored-message ages and per-question evidence ages at +1 d (weights-dev meta and rows).
Writes OUT_DIR/anchors.json and OUT_DIR/anchor-coverage.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

SIDS = ("conv-26", "conv-30", "conv-41")
matches = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
threshold = float(sys.argv[2])
dev, out = Path(sys.argv[4]), Path(sys.argv[5])
rows = [json.loads(line) for sid in SIDS for line in (dev / f"weights-{sid}.jsonl").read_text().splitlines()]
meta = {sid: json.loads((dev / f"meta-{sid}.json").read_text()) for sid in SIDS}
now = {sid: t.stamp(next(r["now"] for r in rows if r["id"].startswith(sid + "-"))) for sid in SIDS}
msg_age = {(sid, m["dia_id"]): (now[sid] - t.stamp(m["recorded_at"])).total_seconds() / 86400
           for sid in SIDS for m in meta[sid]["messages"] if m["dia_id"]}
evidence = {}
for r in rows:
    sid = r["id"].rsplit("-q", 1)[0]
    for d in r["evidence"]:
        evidence[(sid, d)] = r["evidence_age_days"].get(d)

anchors, lines = {}, [f"Similarity threshold {threshold} (window: sessions within 3 days either side of a note date)\n"]
lines.append("| set | notes | notes with anchor | anchors (turns) | user messages anchored | evidence turns anchored "
             "| ratio to base | <30 d | 30-90 d | 90-180 d | >180 d |")
lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
for arm in ("turn", "session"):
    anchors[arm] = {}
    notes = kept = 0
    for sid in SIDS:
        entries = matches[f"{arm}-{sid}"]
        notes += len(entries)
        chosen = [e["both"]["dia_id"] for e in entries if e["both"]["similarity"] >= threshold]
        kept += len(chosen)
        anchors[arm][sid] = sorted(set(chosen))
    flags = {(sid, d) for sid in SIDS for d in anchors[arm][sid]}
    base = sum(key in flags for key in msg_age) / len(msg_age)
    ev = sum(key in flags for key in evidence) / len(evidence)
    cells = []
    for name, _, _ in t.buckets(1):
        sub = [key for key, age in evidence.items() if age is not None and t.bucket_of(age, 1) == name]
        msgs = [key for key, age in msg_age.items() if t.bucket_of(age, 1) == name]
        cells.append(f"{sum(k in flags for k in sub)}/{len(sub)} = {sum(k in flags for k in sub) / len(sub):.1%} "
                     f"(msgs {sum(k in flags for k in msgs) / len(msgs):.1%})")
    lines.append(f"| {arm} | {notes} | {kept} | {len(flags)} | {sum(k in flags for k in msg_age)}/{len(msg_age)} = {base:.1%} "
                 f"| {sum(k in flags for k in evidence)}/{len(evidence)} = {ev:.1%} | {ev / base:.1f}x | " + " | ".join(cells) + " |")
lines.append("\nShares by bucket: anchored evidence turns of that age / evidence turns of that age (and anchored share "
             "of all stored user messages of that age). Ages at last session + 1 day.")
(out / "anchors.json").write_text(json.dumps(anchors, indent=1), encoding="utf-8")
(out / "anchor-coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
