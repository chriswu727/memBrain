"""Real anchors from the notes' cited sources, coverage, and a grade of round 1's matching. No database.

    python build_anchors2.py sources.json ../matches.json ../anchors.json WEIGHTS_DEV_DIR OUT_DIR
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

SIDS = ("conv-26", "conv-30", "conv-41")
sources = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
matches = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
matched_anchors = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
dev, out = Path(sys.argv[4]), Path(sys.argv[5])
THRESHOLD = 0.844

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


def body(text):
    text = re.sub(r"^\s*\[[^\]]*\]\s*", "", text or "")
    return " ".join(text.split()).lower()


anchors = {f"matched_{arm}": matched_anchors[arm] for arm in ("turn", "session")}
lines = ["## Real anchors (the notes' cited source messages)\n",
         "| set | current notes | notes with a cited source turn | anchor turns | user messages anchored | "
         "evidence turns anchored | enrichment | <30 d | 30-90 d | 90-180 d | >180 d |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
grade_lines = ["\n## Round 1 matching graded against the real sources\n"]
for arm in ("turn", "session"):
    anchors[f"real_{arm}"] = {}
    notes = with_source = 0
    graded = {"paired": 0, "right": 0, "kept": 0, "kept_right": 0, "unpaired": 0}
    for sid in SIDS:
        brain = sources[f"{arm}-{sid}"]
        turns = set()
        db_notes = []
        for note in brain["notes"]:
            cited = {d for d in note["linked_turns"] + note["reference_turns"] if d}
            notes += 1
            with_source += bool(cited)
            turns |= cited
            db_notes.append((body(note["text"]), cited))
        anchors[f"real_{arm}"][sid] = sorted(turns)
        for entry in matches[f"{arm}-{sid}"]:
            text = body(entry["note"])
            found = [cited for b, cited in db_notes if b == text] or \
                    [cited for b, cited in db_notes if text[:80] and (text[:80] in b or b[:80] in text)]
            if not found or not found[0]:
                graded["unpaired"] += 1
                continue
            cited = found[0]
            right = entry["both"]["dia_id"] in cited
            graded["paired"] += 1
            graded["right"] += right
            if entry["both"]["similarity"] >= THRESHOLD:
                graded["kept"] += 1
                graded["kept_right"] += right
    flags = {(sid, d) for sid in SIDS for d in anchors[f"real_{arm}"][sid]}
    base = sum(key in flags for key in msg_age) / len(msg_age)
    ev = sum(key in flags for key in evidence) / len(evidence)
    cells = []
    for name, _, _ in t.buckets(1):
        sub = [key for key, age in evidence.items() if age is not None and t.bucket_of(age, 1) == name]
        cells.append(f"{sum(k in flags for k in sub)}/{len(sub)} = {sum(k in flags for k in sub) / len(sub):.1%}")
    lines.append(f"| real_{arm} | {notes} | {with_source} | {len(flags)} | {sum(k in flags for k in msg_age)}/{len(msg_age)} "
                 f"= {base:.1%} | {sum(k in flags for k in evidence)}/{len(evidence)} = {ev:.1%} | {ev / base:.1f}x | "
                 + " | ".join(cells) + " |")
    matched_flags = {(sid, d) for sid in SIDS for d in anchors[f"matched_{arm}"][sid]}
    overlap = len(flags & matched_flags)
    grade_lines.append(
        f"- {arm}: {graded['paired']} matched notes paired with a stored note that cites a turn "
        f"({graded['unpaired']} could not be paired or cite nothing); the match is one of the note's cited turns for "
        f"{graded['right']}/{graded['paired']} = {graded['right'] / max(1, graded['paired']):.1%}; among matches kept at "
        f"similarity >= {THRESHOLD}: {graded['kept_right']}/{graded['kept']} = "
        f"{graded['kept_right'] / max(1, graded['kept']):.1%}. Anchor sets: matched {len(matched_flags)}, real "
        f"{len(flags)}, in both {overlap}.")
(out / "anchors2.json").write_text(json.dumps(anchors, indent=1), encoding="utf-8")
text = "\n".join(lines + grade_lines)
(out / "anchors2-coverage.md").write_text(text + "\n", encoding="utf-8")
print(text)
