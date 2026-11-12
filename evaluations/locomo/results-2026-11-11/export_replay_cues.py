"""Read the cues the replay left in the stored held-out brains and write them as cues-<conversation>.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "evaluations/locomo")


def main():
    from run_locomo import sessions, start, turn_text

    from membrain import desktop, host
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.storage import Database

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    brains, out = Path(sys.argv[2]), Path(sys.argv[3])
    for index in (3, 4, 5, 6, 7, 8, 9):
        sample = data[index]
        directory = brains / f"brain-{sample['sample_id']}"
        keys = {}
        for number, date, turns in sessions(sample):
            session = f"locomo-{sample['sample_id']}-s{number}"
            for turn in turns:
                record = host.message_record(session, "user", turn_text(date, turn), turn_id=turn["dia_id"],
                                             producer="locomo-ingest")
                keys[record["source_event_key"]] = turn["dia_id"]
        start(directory)
        try:
            profile = load_profile(directory)
            database = Database(profile.database_url)
            with database.transaction(Principal(profile.tenant_id, profile.principal_id)) as conn:
                rows = conn.execute(
                    "SELECT e.source_key,c.cue_text,c.model_version FROM memory_message_cues c JOIN memory_events e "
                    "ON e.tenant_id=c.tenant_id AND e.brain_id=c.brain_id AND e.id=c.event_id AND e.is_current").fetchall()
            database.close()
        finally:
            desktop.stop(directory)
        cues = {keys[row["source_key"]]: row["cue_text"].split("; ") for row in rows if row["source_key"] in keys}
        versions = sorted({row["model_version"] for row in rows})
        (out / f"cues-{sample['sample_id']}.json").write_text(json.dumps({"cues": cues}, ensure_ascii=False, indent=1))
        print(sample["sample_id"], len(rows), "cue rows,", len(cues), "matched to turns, written by", versions, flush=True)


if __name__ == "__main__":
    main()
