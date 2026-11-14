"""Recover each consolidation note's source turn, model-free: best cosine match with the local embedding model.

    python match_notes.py locomo10.json consolidation-notes.json.gz MODEL_CACHE OUT.json

Note text is embedded without its bracketed header (purpose "query"); each stored user turn as "speaker: text"
(purpose "document"). Where the note carries a date (``on YYYY-MM-DD`` in the header, or a full date in the
sentence), candidates are restricted to turns of sessions dated within the date window, when that leaves any.
Window: a session dated from 3 days before to 3 days after a note date (``--window`` modes recorded side by side:
``before`` = session on or within 3 days before the date, ``after`` = session on or within 3 days after it, ``both``).
"""
import datetime as dt
import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
MONTH = "(" + "|".join(MONTHS) + ")"
STOP = set("the a an and or of to in on for with at by from her his she he they them their is was are were has have "
           "had be been as it its that this about into who which when what also very just more most some".split())
WORD = re.compile(r"[a-z0-9']+")


def note_dates(note):
    header = re.match(r"\s*\[([^\]]*)\]\s*", note)
    head, body = (header.group(1), note[header.end():]) if header else ("", note)
    dates = []
    for text in (head, body):
        for y, m, d in re.findall(r"(\d{4})-(\d{2})-(\d{2})", text):
            dates.append(dt.date(int(y), int(m), int(d)))
    low = body.lower()
    for d, m, y in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)? " + MONTH + r",? (\d{4})", low):
        dates.append(dt.date(int(y), MONTHS[m], int(d)))
    for m, d, y in re.findall(MONTH + r" (\d{1,2})(?:st|nd|rd|th)?, (\d{4})", low):
        dates.append(dt.date(int(y), MONTHS[m], int(d)))
    return body.strip(), sorted(set(dates))


def words(text):
    return {w for w in WORD.findall(text.lower()) if len(w) > 2 and w not in STOP}


def main():
    import numpy

    from membrain.local_embeddings import LocalEmbeddingProvider, installed

    data = {s["sample_id"]: s for s in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))}
    with gzip.open(sys.argv[2], "rt", encoding="utf-8") as stream:
        notes = json.load(stream)
    provider = LocalEmbeddingProvider(installed(Path(sys.argv[3])), threads=4)
    if not provider.ready:
        raise SystemExit("embedding model not ready")

    def embed(texts, purpose):
        vectors = []
        for start in range(0, len(texts), 32):
            vectors.extend(provider.embed(texts[start:start + 32], timeout_seconds=120.0, purpose=purpose).vectors)
        matrix = numpy.asarray(vectors, dtype="float32")
        return matrix / numpy.maximum(numpy.linalg.norm(matrix, axis=1, keepdims=True), 1e-9)

    out = {}
    turn_cache = {}
    for key, value in notes.items():
        arm, sid = key.split("-", 1)
        sample = data[sid]
        if sid not in turn_cache:
            ids, texts, session_of, session_date = [], [], {}, {}
            for number, date, turns in t.sessions(sample):
                session_date[number] = t.session_time(date).date()
                for turn in turns:
                    ids.append(turn["dia_id"])
                    texts.append(f"{turn['speaker']}: {turn.get('text', '')}")
                    session_of[turn["dia_id"]] = number
            turn_cache[sid] = (ids, texts, session_of, session_date, embed(texts, "document"))
        ids, texts, session_of, session_date, matrix = turn_cache[sid]
        bodies, dated = zip(*(note_dates(note) for note in value["notes"]))
        queries = embed(list(bodies), "query")
        rows = []
        for index, note in enumerate(value["notes"]):
            sims = matrix @ queries[index]
            entry = {"note": note, "body": bodies[index], "dates": [d.isoformat() for d in dated[index]]}
            for mode in ("none", "before", "after", "both"):
                allowed = list(range(len(ids)))
                if mode != "none" and dated[index]:
                    keep = []
                    for i, dia in enumerate(ids):
                        sd = session_date[session_of[dia]]
                        for d in dated[index]:
                            delta = (d - sd).days  # positive: the note date is after the session
                            if (mode == "before" and 0 <= delta <= 3) or (mode == "after" and -3 <= delta <= 0) or \
                                    (mode == "both" and -3 <= delta <= 3):
                                keep.append(i)
                                break
                    if keep:
                        allowed = keep
                best = max(allowed, key=lambda i: sims[i])
                order = sorted(allowed, key=lambda i: -sims[i])
                second = float(sims[order[1]]) if len(order) > 1 else None
                overlap = words(bodies[index]) & words(texts[best])
                entry[mode] = {"dia_id": ids[best], "similarity": round(float(sims[best]), 4),
                               "second": round(second, 4) if second is not None else None,
                               "restricted": len(allowed) < len(ids), "candidates": len(allowed),
                               "overlap": round(len(overlap) / max(1, len(words(bodies[index]))), 3),
                               "turn": texts[best]}
            rows.append(entry)
        out[key] = rows
        print(key, len(rows), "notes", flush=True)
    Path(sys.argv[4]).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
