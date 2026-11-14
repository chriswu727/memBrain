"""Tables and the fixed verdict for heldout_built.py.   python heldout_analyze.py OUT_DIR WEIGHTS_HELDOUT_DIR"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

SIDS = ("conv-42", "conv-43", "conv-44", "conv-47", "conv-48", "conv-49", "conv-50")
PASSES = ("before", "notes_plain", "built")
LABEL = {"before": "(a) before notes", "notes_plain": "(b) notes, lookup off", "built": "(c) built"}
OFFSET = {"+1d": 1, "+365d": 365}
out, earlier = Path(sys.argv[1]), Path(sys.argv[2])
rows = [json.loads(line) for sid in SIDS for line in (out / f"built-{sid}.jsonl").read_text().splitlines()]
meta = {sid: json.loads((out / f"meta-{sid}.json").read_text()) for sid in SIDS}
lines, summary = [], {}


def full(r, a):
    return set(r[a]) >= set(r["evidence"])


def oldest_bucket(r, offset):
    return t.bucket_of(max(r["evidence_age_days"].values()), offset)


lines.append(f"membrain: {meta[SIDS[0]]['membrain']}; ANCHOR_NOTE_SOURCES = {meta[SIDS[0]]['anchor_note_sources']}\n")
lines.append("## Notes and anchors per conversation\n")
lines.append("| conversation | user messages | stand-in notes | written (full / reduced fields / plain) | refused "
             "| anchor turns | share of messages | jobs after notes |")
lines.append("|---|---|---|---|---|---|---|---|")
for sid in SIDS:
    m = meta[sid]
    w = m["note_writes"]
    lines.append(f"| {sid} | {m['user_messages']} | {m['notes_in_file']} | {w['written']} / {w['written_reduced_fields']} / "
                 f"{w['written_plain']} | {w['refused'] + w['no_source_event']} | {len(m['anchor_turns'])} | "
                 f"{len(m['anchor_turns']) / m['user_messages']:.1%} | {m['jobs_processed_after_notes']} |")
plus1 = [r for r in rows if r["now_label"] == "+1d"]
now = {sid: t.stamp(next(r["now"] for r in plus1 if r["id"].startswith(sid + "-"))) for sid in SIDS}
anchors = {(sid, d) for sid in SIDS for d in meta[sid]["anchor_turns"]}
msg_age = {(sid, d): (now[sid] - t.stamp(ts)).total_seconds() / 86400
           for sid in SIDS for d, ts in meta[sid]["message_times"].items()}
evidence = {}
for r in plus1:
    sid = r["id"].rsplit("-q", 1)[0]
    for d in r["evidence"]:
        evidence[(sid, d)] = r["evidence_age_days"].get(d)
base = sum(k in anchors for k in msg_age) / len(msg_age)
ev = sum(k in anchors for k in evidence) / len(evidence)
lines.append(f"\nAll: anchors {len(anchors)} of {len(msg_age)} user messages = {base:.1%}; unique evidence turns anchored "
             f"{sum(k in anchors for k in evidence)}/{len(evidence)} = {ev:.1%}; enrichment {ev / base:.1f}x\n")
lines.append("| age at +1 d | messages | anchored | evidence turns | anchored | enrichment |\n|---|---|---|---|---|---|")
for name, _, _ in t.buckets(1):
    msgs = [k for k, a in msg_age.items() if t.bucket_of(a, 1) == name]
    evs = [k for k, a in evidence.items() if a is not None and t.bucket_of(a, 1) == name]
    mb = sum(k in anchors for k in msgs) / len(msgs)
    eb = sum(k in anchors for k in evs) / len(evs)
    lines.append(f"| {name} | {len(msgs)} | {mb:.1%} | {len(evs)} | {eb:.1%} | {eb / mb:.1f}x |")
summary["coverage"] = {"messages": round(base, 4), "evidence": round(ev, 4), "anchors": len(anchors)}

for label, offset in OFFSET.items():
    items = [r for r in rows if r["now_label"] == label]
    recent = t.buckets(offset)[0][0]
    lines.append(f"\n## {label} (n = {len(items)}): all evidence shown % / mean evidence share %\n")
    lines.append("| group | n | " + " | ".join(LABEL[p] for p in PASSES) + " |")
    lines.append("|---|---|---|---|---|")
    groups = [("all", items), ("one evidence", [r for r in items if len(r["evidence"]) == 1]),
              ("several", [r for r in items if len(r["evidence"]) > 1])]
    groups += [(f"oldest {name}", [r for r in items if oldest_bucket(r, offset) == name]) for name, _, _ in t.buckets(offset)]
    for name, chosen in groups:
        cells = []
        for p in PASSES:
            a = sum(full(r, p) for r in chosen) / len(chosen)
            s = statistics.fmean(len(r[p]) / len(r["evidence"]) for r in chosen)
            cells.append(f"{a:.1%} / {s:.1%}")
            summary.setdefault(label, {}).setdefault(name, {})[p] = [len(chosen), round(a, 4), round(s, 4)]
        lines.append(f"| {name} | {len(chosen)} | " + " | ".join(cells) + " |")
    lines.append(f"\n{label}: paired against (a) (questions gained / lost), overall and in the {recent} bucket\n")
    lines.append(f"| pass | all | net | {recent} | identical sets |\n|---|---|---|---|---|")
    for p in PASSES[1:]:
        g = [r for r in items if full(r, p) and not full(r, "before")]
        lo = [r for r in items if full(r, "before") and not full(r, p)]
        gr = sum(oldest_bucket(r, offset) == recent for r in g)
        lr = sum(oldest_bucket(r, offset) == recent for r in lo)
        same = sum(set(r[p]) == set(r["before"]) for r in items)
        summary.setdefault(f"{label} paired", {})[p] = {"gained": len(g), "lost": len(lo), "gained_recent": gr,
                                                        "lost_recent": lr, "identical": same}
        lines.append(f"| {LABEL[p]} | +{len(g)}/-{len(lo)} | {len(g) - len(lo):+d} | +{gr}/-{lr} | {same}/{len(items)} |")
    lines.append(f"\n{label}: evidence turns shown, anchored vs not anchored, by the turn's age\n")
    lines.append("| evidence turns | pairs | " + " | ".join(LABEL[p] for p in PASSES) + " |\n|---|---|---|---|---|")
    for flag, fname in ((True, "anchored"), (False, "not anchored")):
        pairs = [(r, d) for r in items for d in r["evidence"] if r["evidence_anchor"][d] is flag]
        sub_groups = [("all ages", pairs)] + [(name, [(r, d) for r, d in pairs if d in r["evidence_age_days"] and
                                                     t.bucket_of(r["evidence_age_days"][d], offset) == name])
                                              for name, _, _ in t.buckets(offset)]
        if offset == 1:
            sub_groups.append(("older than 90 d", [(r, d) for r, d in pairs if r["evidence_age_days"].get(d, 0) >= 90]))
        for gname, sub in sub_groups:
            if not sub:
                continue
            shares = {p: sum(d in r[p] for r, d in sub) / len(sub) for p in PASSES}
            summary.setdefault(f"{label} turns", {})[f"{fname} {gname}"] = {"pairs": len(sub), **{
                p: round(v, 4) for p, v in shares.items()}}
            lines.append(f"| {fname}, {gname} | {len(sub)} | " + " | ".join(f"{shares[p]:.1%}" for p in PASSES) + " |")

# Checks.
old = {}
for sid in SIDS:
    for line in (earlier / f"weights-{sid}.jsonl").read_text().splitlines():
        r = json.loads(line)
        old[r["id"]] = r
same_f030 = sum(set(r["before"]) == set(old[r["id"]]["f030"]) for r in plus1)
lines.append(f"\n## Checks\n\n- (a) at +1 d equals the earlier held-out f030 rows in {same_f030} of {len(plus1)} questions")
plus365 = [r for r in rows if r["now_label"] == "+365d"]
lines.append(f"- (c) at +365 d identical to (a): {sum(set(r['built']) == set(r['before']) for r in plus365)} of {len(plus365)}")
lines.append(f"- (b) identical to (a): +1 d {sum(set(r['notes_plain']) == set(r['before']) for r in plus1)} of {len(plus1)}, "
             f"+365 d {sum(set(r['notes_plain']) == set(r['before']) for r in plus365)} of {len(plus365)}")

# Verdict (fixed in advance).
p1, p365 = summary["+1d paired"]["built"], summary["+365d paired"]["built"]
turns = summary["+1d turns"]
a_old = turns["anchored older than 90 d"]["built"] - turns["anchored older than 90 d"]["before"]
n_old = turns["not anchored older than 90 d"]["built"] - turns["not anchored older than 90 d"]["before"]
c1 = p1["lost_recent"] <= 3
c2 = p365["lost"] - p365["gained"] <= 1
c3a = p1["gained"] - p1["lost"] >= 12
c3b = a_old >= 0.05 and n_old >= -0.01
lines.append("\n## Verdict under the fixed rule\n")
lines.append(f"- recent questions (< 30 d) lost at +1 d: {p1['lost_recent']} (at most 3): {'pass' if c1 else 'FAIL'}")
lines.append(f"- +365 d net loss: {p365['lost'] - p365['gained']} (at most 1): {'pass' if c2 else 'FAIL'}")
lines.append(f"- +1 d net gain {p1['gained'] - p1['lost']:+d} (at least 12): {'pass' if c3a else 'fail'}; or anchored >90 d "
             f"{a_old:+.1%} (at least +5) with not anchored >90 d {n_old:+.1%} (no worse than -1): {'pass' if c3b else 'fail'}")
verdict = c1 and c2 and (c3a or c3b)
lines.append(f"- **{'VALIDATES' if verdict else 'DOES NOT VALIDATE'}**")
summary["verdict"] = {"validates": verdict, "recent_lost": p1["lost_recent"], "net365_loss": p365["lost"] - p365["gained"],
                      "net1": p1["gained"] - p1["lost"], "anchored_old_delta": round(a_old, 4),
                      "not_anchored_old_delta": round(n_old, 4)}
text = "\n".join(lines)
(out / "report.md").write_text(text + "\n", encoding="utf-8")
(out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(text)
