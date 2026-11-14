"""The built anchor rule, measured on copies of the development brains with real notes written into them. No model.

    python anchor_built.py COPIES_DIR locomo10.json sources.json consolidation-notes.json.gz OUT_DIR SID

Model on ``round2/anchor_arms2.py``. The brain copy holds dated messages and cues but no notes. Three passes:
- ``before``: no notes yet, the built code (equals the shipped ranking: there is nothing to anchor).
- then every current ``turn`` note of that conversation (sources.json, written turn by turn by a stand-in host) is
  saved through the client's note call with ``source_event_ids`` = its cited messages (turn id -> event id through the
  stored turns' source keys);
- ``notes_plain``: notes present and indexed (the worker's jobs run through the API), ``candidates.anchored_events``
  patched to return nothing: what the notes change on their own;
- ``built``: notes present, the built code as it is.
Each pass asks every question at last session + 1 d and + 365 d through ``host.recall_context`` (the automatic block).
"""
import dataclasses
import datetime as dt
import gzip
import json
import os
import sys
import threading
import time
from pathlib import Path

WORKTREE = Path("REPOSITORY/.claude/worktrees/agent-a0159cd7022bd14fa")
sys.path.insert(0, str(WORKTREE / "evaluations/locomo"))
import time_depth_recall as t  # noqa: E402

import membrain  # noqa: E402

PASSES = ("before", "notes_plain", "built")
NOWS = (("+1d", 1), ("+365d", 365))
LIMIT = 9000


def main():
    print("membrain from", membrain.__file__, flush=True)
    assert Path(membrain.__file__).resolve().is_relative_to(WORKTREE / "src"), membrain.__file__
    import uvicorn

    from membrain import candidates, desktop, embedded_database, evaluation_clock, helpers, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.notes import NOTE_PRODUCER, NOTES_CONVERSATION, parse_note
    from membrain.storage import Database

    copies, data_path, sources_path, notes_path, out, sid = (Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]),
                                                             Path(sys.argv[4]), Path(sys.argv[5]), sys.argv[6])
    assert "locomo-time-depth-notes-" in str(copies.resolve()), "refusing to work on anything but the copies"
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / f"built-{sid}.jsonl"
    if result_path.exists():
        print("skip", sid, flush=True)
        return
    sample = next(s for s in json.loads(Path(data_path).read_text(encoding="utf-8")) if s["sample_id"] == sid)
    notes = json.loads(sources_path.read_text(encoding="utf-8"))[f"turn-{sid}"]["notes"]
    with gzip.open(notes_path, "rt", encoding="utf-8") as stream:
        texts = set(json.load(stream)[f"turn-{sid}"]["notes"])
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
    rows, meta = {}, {"sid": sid, "membrain": membrain.__file__}
    database = None
    try:
        while not server.started:
            if not thread.is_alive():
                raise SystemExit("the in-process service did not start")
            time.sleep(0.1)
        database = Database(profile.database_url)
        principal = Principal(profile.tenant_id, profile.principal_id)
        with database.transaction(principal) as conn:
            message_rows = conn.execute(
                "SELECT id,source_key FROM memory_events WHERE brain_id=%s AND is_current AND NOT deleted "
                "AND NOT suppressed AND NOT retired AND document IS NOT NULL "
                "AND document->'observed'->>'event_kind'='message' AND document->'observed'->>'actor_role'='user'",
                (profile.brain_id,)).fetchall()
            meta["notes_before"] = conn.execute(
                "SELECT count(*) AS n FROM memory_events WHERE brain_id=%s AND conversation_id=%s",
                (profile.brain_id, NOTES_CONVERSATION)).fetchone()["n"]
        event_of = {keys[row["source_key"]]: row["id"] for row in message_rows if row["source_key"] in keys}
        with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
            for name in PASSES:
                if name == "notes_plain":
                    written, cited = 0, []
                    meta["note_texts_in_consolidation_file"] = sum(note["text"] in texts for note in notes)
                    for index, note in enumerate(notes):
                        dias = list(dict.fromkeys(d for d in note["linked_turns"] + note["reference_turns"] if d))
                        ids = [event_of[d] for d in dias]
                        # The stored text carries its typed header; split it back into fields, as save_note does.
                        fields, sentence = parse_note(note["text"])
                        result = client.write_note(sentence, replaces=[], producer=NOTE_PRODUCER,
                                                   source_event_ids=ids, source_messages=[],
                                                   request_id=f"anchor-built-{sid}-{index}", **fields)
                        assert sorted(result["source_event_ids"]) == sorted(ids), (note, result)
                        written += 1
                        cited.append(len(ids))
                    meta["notes_written"], meta["cited_per_note"] = written, cited
                    # Index the notes as the service's worker would, so they are in the brain as a host leaves them.
                    processed = 0
                    while processed < 5000 and client.work()["processed"]:
                        processed += 1
                    meta["jobs_processed_after_notes"] = processed
                    with database.transaction(principal) as conn:
                        meta["anchored_events"] = len(original(conn, (profile.tenant_id, profile.principal_id,
                                                                      profile.brain_id), list(event_of.values())))
                        meta["explain"] = [row["QUERY PLAN"] for row in conn.execute(
                            "EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) SELECT DISTINCT d.input_event_id "
                            "FROM memory_event_dependencies d JOIN memory_events n "
                            "ON n.tenant_id=d.tenant_id AND n.owner_id=d.owner_id AND n.brain_id=d.brain_id "
                            "AND n.id=d.output_event_id WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s "
                            "AND d.input_event_id=ANY(%s::text[]) AND n.conversation_id=%s AND n.is_current "
                            "AND NOT n.deleted AND NOT n.suppressed AND NOT n.retired AND n.document IS NOT NULL "
                            "AND GREATEST(jsonb_array_length(coalesce(n.document #> '{observed,source_references}',"
                            "'[]'::jsonb)),(SELECT count(*) FROM memory_event_dependencies s "
                            "WHERE s.tenant_id=d.tenant_id AND s.owner_id=d.owner_id AND s.brain_id=d.brain_id "
                            "AND s.output_event_id=d.output_event_id))<=%s",
                            (profile.tenant_id, profile.principal_id, profile.brain_id,
                             sorted(event_of.values())[:300], NOTES_CONVERSATION,
                             candidates.ANCHOR_NOTE_SOURCES)).fetchall()]
                    candidates.anchored_events = lambda conn, params, event_ids: set()
                else:
                    candidates.anchored_events = original
                for label, offset in NOWS:
                    moment["value"] = last + dt.timedelta(days=offset)
                    for qid, qa in todo:
                        wanted = t.evidence_ids(qa, turns)
                        context = host.recall_context(client, qa["question"], current_conversation=f"time-depth-{qid}",
                                                      limit=LIMIT) or ""
                        row = rows.setdefault((qid, label), {"id": qid, "now_label": label, "evidence": wanted,
                                                             "now": helpers.now()})
                        row[name] = t.present(context, wanted, identify)
                    print(sid, name, label, "done", round(time.monotonic() - started_at, 1), "s", flush=True)
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
    print(sid, len(rows), "rows", round(time.monotonic() - started_at, 1), "s", flush=True)


if __name__ == "__main__":
    main()
