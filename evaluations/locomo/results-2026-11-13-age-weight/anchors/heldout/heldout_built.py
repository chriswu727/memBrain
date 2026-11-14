"""The built anchor rule on held-out brains with stand-in notes. No model.

    python heldout_built.py COPIES_DIR locomo10.json NOTES_JSONL OUT_DIR SID

Modelled on the build agent's ``anchor_built.py``; runs the repository's current code (main working tree). The brain
copy holds dated messages and host-batch cues but no notes. Three passes, each asking every question at last
session + 1 d and + 365 d through ``host.recall_context`` (the automatic block):
- ``before`` (a): no notes yet;
- then every stand-in note of this conversation is saved with ``client.write_note`` citing its one source message
  (``source_event_ids`` = the event of the turn the note names; typed fields from the tool call), and the service's
  jobs are run so the notes are indexed;
- ``notes_plain`` (b): notes present, ``candidates.anchored_events`` patched to return nothing;
- ``built`` (c): the built code as it is.
"""
import dataclasses
import datetime as dt
import json
import os
import sys
import threading
import time
from pathlib import Path

REPO = Path("REPOSITORY")
sys.path.insert(0, str(REPO / "evaluations/locomo"))
import time_depth_recall as t  # noqa: E402

import membrain  # noqa: E402

PASSES = ("before", "notes_plain", "built")
NOWS = (("+1d", 1), ("+365d", 365))
LIMIT = 9000
DAY = 86400.0
TYPED = ("kind", "about", "aliases", "status", "due", "occurs_at", "sensitive")


def main():
    import uvicorn

    from membrain import candidates, desktop, embedded_database, evaluation_clock, helpers, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.notes import NOTE_FIELDS, NOTE_PRODUCER, NOTES_CONVERSATION
    from membrain.storage import Database

    print("membrain from", membrain.__file__, "ANCHOR_NOTE_SOURCES", candidates.ANCHOR_NOTE_SOURCES, flush=True)
    assert Path(membrain.__file__).resolve().is_relative_to(REPO / "src"), membrain.__file__
    copies, data_path, notes_path, out, sid = (Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]),
                                               sys.argv[5])
    assert "locomo-time-depth-heldout-notes-" in str(copies.resolve()), "refusing to work on anything but the copies"
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / f"built-{sid}.jsonl"
    if result_path.exists():
        print("skip", sid, flush=True)
        return
    sample = next(s for s in json.loads(Path(data_path).read_text(encoding="utf-8")) if s["sample_id"] == sid)
    notes = [n for n in (json.loads(line) for line in notes_path.read_text(encoding="utf-8").splitlines())
             if n["conversation"] == sid]
    directory = copies / f"brain-{sid}"
    turns, identify = t.stored_turns(sample), t.needles(sample)
    todo = [(qid, qa) for qid, qa in t.questions(sample, {1, 2, 3, 4}) if t.evidence_ids(qa, turns)]
    last = max(t.session_time(date) for _, date, _ in t.sessions(sample))
    keys = {}
    for number, date, session_turns in t.sessions(sample):
        for turn in session_turns:
            record = host.message_record(f"locomo-{sid}-s{number}", "user", t.turn_text(date, turn),
                                         turn_id=turn["dia_id"], producer="locomo-ingest")
            keys[record["source_event_key"]] = turn["dia_id"]
    moment = {"value": last + dt.timedelta(days=1)}
    os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
    evaluation_clock.enable(directory)
    helpers._scenario_clock = lambda: moment["value"]
    profile = load_profile(directory)
    started_at = time.monotonic()
    desktop._prepare_database(profile)
    settings = dataclasses.replace(profile.settings(), recall_processes=0)
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                           log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    original = candidates.anchored_events
    rows = {}
    meta = {"sid": sid, "membrain": membrain.__file__, "anchor_note_sources": candidates.ANCHOR_NOTE_SOURCES,
            "notes_in_file": len(notes)}
    database = None
    try:
        while not server.started:
            if not thread.is_alive():
                raise SystemExit("the in-process service did not start")
            time.sleep(0.1)
        database = Database(profile.database_url)
        principal = Principal(profile.tenant_id, profile.principal_id)
        params = (profile.tenant_id, profile.principal_id, profile.brain_id)
        with database.transaction(principal) as conn:
            message_rows = conn.execute(
                "SELECT id,source_key,document #>> '{system_time,recorded_at}' AS recorded_at FROM memory_events "
                "WHERE brain_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
                "AND document IS NOT NULL AND document->'observed'->>'event_kind'='message' "
                "AND document->'observed'->>'actor_role'='user'", (profile.brain_id,)).fetchall()
            meta["notes_before"] = conn.execute(
                "SELECT count(*) AS n FROM memory_events WHERE brain_id=%s AND conversation_id=%s",
                (profile.brain_id, NOTES_CONVERSATION)).fetchone()["n"]
        event_of = {keys[row["source_key"]]: row["id"] for row in message_rows if row["source_key"] in keys}
        dia_of = {event: dia for dia, event in event_of.items()}
        turn_time = {keys[row["source_key"]]: row["recorded_at"] for row in message_rows if row["source_key"] in keys}
        meta["user_messages"] = len(event_of)
        meta["message_times"] = turn_time
        anchor_turns = set()
        with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
            for name in PASSES:
                if name == "notes_plain":
                    outcome = {"written": 0, "written_reduced_fields": 0, "written_plain": 0, "refused": 0,
                               "no_source_event": 0}
                    refusals = []
                    for index, note in enumerate(notes):
                        event = event_of.get(note["turn"])
                        if event is None:
                            outcome["no_source_event"] += 1
                            continue
                        full = {k: v for k, v in note["fields"].items() if k in NOTE_FIELDS
                                and v not in (None, "", [], False)}
                        reduced = {k: v for k, v in full.items() if k in TYPED}
                        for attempt, fields in (("written", full), ("written_reduced_fields", reduced),
                                                ("written_plain", {})):
                            try:
                                result = client.write_note(note["text"], replaces=[], producer=NOTE_PRODUCER,
                                                           source_event_ids=[event], source_messages=[],
                                                           request_id=f"heldout-{sid}-{index}-{attempt}", **fields)
                            except Exception as error:  # noqa: BLE001 - a refusal is counted, the next form tried
                                refusals.append({"index": index, "attempt": attempt, "error": str(error)[:200]})
                                continue
                            assert result["source_event_ids"] == [event], (note, result)
                            outcome[attempt] += 1
                            break
                        else:
                            outcome["refused"] += 1
                    meta["note_writes"], meta["refusals"] = outcome, refusals[:20]
                    processed = 0
                    while processed < 5000 and client.work()["processed"]:
                        processed += 1
                    meta["jobs_processed_after_notes"] = processed
                    with database.transaction(principal) as conn:
                        anchored = original(conn, params, list(event_of.values()))
                    anchor_turns = {dia_of[event] for event in anchored if event in dia_of}
                    meta["anchored_events"] = len(anchored)
                    meta["anchor_turns"] = sorted(anchor_turns)
                    candidates.anchored_events = lambda conn, params, event_ids: set()
                else:
                    candidates.anchored_events = original
                for label, offset in NOWS:
                    moment["value"] = last + dt.timedelta(days=offset)
                    for qid, qa in todo:
                        wanted = t.evidence_ids(qa, turns)
                        context = host.recall_context(client, qa["question"], current_conversation=f"time-depth-{qid}",
                                                      limit=LIMIT) or ""
                        now = helpers.now()
                        row = rows.setdefault((qid, label), {
                            "id": qid, "now_label": label, "evidence": wanted, "now": now,
                            "evidence_age_days": {d: round((t.stamp(now) - t.stamp(turn_time[d])).total_seconds() / DAY, 3)
                                                  for d in wanted if d in turn_time}})
                        row[name] = t.present(context, wanted, identify)
                    print(sid, name, label, "done", round(time.monotonic() - started_at, 1), "s", flush=True)
        for row in rows.values():
            row["evidence_anchor"] = {d: d in anchor_turns for d in row["evidence"]}
    finally:
        candidates.anchored_events = original
        if database is not None:
            database.close()
        server.should_exit = True
        thread.join(timeout=30)
        embedded_database.stop(profile)
        evaluation_clock.disable()
        helpers._scenario_clock = None
    (out / f"meta-{sid}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    result_path.write_text("".join(json.dumps(row) + "\n" for row in rows.values()), encoding="utf-8")
    print(sid, len(rows), "rows", meta.get("note_writes"), "anchored", meta.get("anchored_events"),
          round(time.monotonic() - started_at, 1), "s", flush=True)


if __name__ == "__main__":
    main()
