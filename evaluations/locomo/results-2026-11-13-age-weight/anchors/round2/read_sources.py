"""Read every current note and the messages it cites from COPIES of the consolidation brains. No model, no API.

    python read_sources.py COPIES_DIR locomo10.json OUT.json

For each brain <arm>-<conversation> (arm turn|session): start its database (``desktop._prepare_database``), read the
current notes of the notes conversation with their linked sources (``memory_event_dependencies``, as the timeline
reports ``source_event_ids``) and any unresolved ``source_references``, map cited events to LoCoMo turn ids through
the stored turns' source keys (``host.message_record`` as the harness stores them), stop the database.
"""
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

BRAINS = [f"{arm}-{sid}" for arm in ("turn", "session") for sid in ("conv-26", "conv-30", "conv-41")]


def port_open(port):
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main():
    from membrain import desktop, embedded_database, host
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.notes import NOTES_CONVERSATION
    from membrain.storage import Database

    copies, out = Path(sys.argv[1]), Path(sys.argv[3])
    assert "locomo-consolidation-copies-" in str(copies), copies
    data = {s["sample_id"]: s for s in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))}
    result = json.loads(out.read_text()) if out.exists() else {}
    for name in BRAINS:
        if name in result:
            continue
        sid = name.split("-", 1)[1]
        sample = data[sid]
        keys = {}
        for number, date, turns in t.sessions(sample):
            for turn in turns:
                record = host.message_record(f"locomo-{sid}-s{number}", "user", t.turn_text(date, turn),
                                             turn_id=turn["dia_id"], producer="locomo-ingest")
                keys[record["source_event_key"]] = turn["dia_id"]
        directory = copies / name
        profile = load_profile(directory)
        busy = [port for port in (profile.api_port, profile.database_port) if port_open(port)]
        if busy:
            raise SystemExit(f"{name}: ports in use {busy}; not starting")
        desktop._prepare_database(profile)
        try:
            database = Database(profile.database_url)
            try:
                with database.transaction(Principal(profile.tenant_id, profile.principal_id)) as conn:
                    messages = conn.execute(
                        "SELECT id,source_key,producer_ref FROM memory_events WHERE brain_id=%s AND is_current "
                        "AND document IS NOT NULL AND document->'observed'->>'event_kind'='message' "
                        "AND document->'observed'->>'actor_role'='user'", (profile.brain_id,)).fetchall()
                    notes = conn.execute(
                        "SELECT e.id,e.sequence,e.document #>> '{observed,content,text}' AS text,"
                        "e.document->'observed'->'source_references' AS refs,"
                        "ARRAY(SELECT d.input_event_id FROM memory_event_dependencies d WHERE d.tenant_id=e.tenant_id "
                        "AND d.owner_id=e.owner_id AND d.brain_id=e.brain_id AND d.output_event_id=e.id "
                        "ORDER BY d.input_event_id) AS sources "
                        "FROM memory_events e WHERE e.brain_id=%s AND e.conversation_id=%s AND e.is_current "
                        "AND NOT e.deleted AND NOT e.suppressed AND NOT e.retired AND e.document IS NOT NULL "
                        "AND e.document->'observed'->>'event_kind'='message' ORDER BY e.sequence",
                        (profile.brain_id, NOTES_CONVERSATION)).fetchall()
                    all_notes = conn.execute(
                        "SELECT count(*) AS n FROM memory_events WHERE brain_id=%s AND conversation_id=%s",
                        (profile.brain_id, NOTES_CONVERSATION)).fetchone()["n"]
            finally:
                database.close()
        finally:
            embedded_database.stop(profile)
        dia_of_event = {row["id"]: keys.get(row["source_key"]) for row in messages}
        rows = []
        for note in notes:
            linked = [dia_of_event.get(event) for event in note["sources"]]
            pending = []
            for ref in note["refs"] or []:
                if isinstance(ref, dict) and ref.get("source_event_key") in keys:
                    pending.append(keys[ref["source_event_key"]])
            rows.append({"event_id": note["id"], "text": note["text"], "linked_events": note["sources"],
                         "linked_turns": linked, "reference_turns": pending,
                         "raw_references": note["refs"]})
        result[name] = {"user_messages": len(messages), "notes_current": len(notes), "note_events_all": all_notes,
                        "notes": rows}
        out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        print(name, "messages", len(messages), "current notes", len(notes), "with linked source",
              sum(bool(r["linked_events"]) for r in rows), "with reference", sum(bool(r["reference_turns"]) for r in rows),
              flush=True)


if __name__ == "__main__":
    main()
