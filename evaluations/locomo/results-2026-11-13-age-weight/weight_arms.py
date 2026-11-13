"""Strength of the age weight, the same for every candidate: evidence recall per arm at last session + 1 day. No model.

    python weight_arms.py RUN_DIR locomo10.json OUT_DIR ARMS SIDS [CUES_DIR]

ARMS: comma-separated names. ``auto`` (shipped functions untouched), ``flat`` (1.0), or ``f<floor*100>[h<mult>]``,
e.g. ``f030`` = rank floor 0.30, ``f015h2`` = floor 0.15 with every half-life x2, ``f030h4``.
SIDS: comma-separated conversation ids (brain-<sid> in RUN_DIR).
CUES_DIR: optional directory of cues-<sid>.json ({"cues": {dia_id: [phrases]}}) attached first through
``client.write_message_cues`` (as ``retrieval_recall.write_cues``); without it the brain's existing cues are used.
The service runs in this process (``recall_processes=0``); the clock is pinned with ``helpers._scenario_clock``.
"""
import dataclasses
import datetime as dt
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

LIMIT = 9000
DAY = 86400.0


def parse_arm(name, default):
    if name in ("auto", "flat"):
        return None
    match = re.fullmatch(r"f(\d{3})(?:h(\d+))?", name)
    if not match:
        raise SystemExit(f"unknown arm {name}")
    floor, mult = int(match.group(1)) / 100, int(match.group(2) or 1)
    return dataclasses.replace(default, rank_floor=floor, distinctive_rank_floor=max(floor, default.distinctive_rank_floor),
                               half_life_days={k: v * mult for k, v in default.half_life_days.items()})


class Weights:
    def __init__(self, arms):
        from membrain import candidates, dynamics

        self.candidates, self.dynamics = candidates, dynamics
        self.original_state, self.original_weight = dynamics.access_state, dynamics.rank_weight
        self.policies = {arm: parse_arm(arm, dynamics.DEFAULT_POLICY) for arm in arms}
        self.arm = "auto"
        self.calls = 0
        candidates.access_state = dynamics.access_state = self.access_state
        candidates.rank_weight = dynamics.rank_weight = self.rank_weight

    def restore(self):
        self.candidates.access_state = self.dynamics.access_state = self.original_state
        self.candidates.rank_weight = self.dynamics.rank_weight = self.original_weight

    def access_state(self, memory, usage, *, at, policy=None):
        chosen = self.policies.get(self.arm) or policy
        return self.original_state(memory, usage, at=at, **({"policy": chosen} if chosen else {}))

    def rank_weight(self, state, *, direct=False, policy=None):
        self.calls += 1
        if self.arm == "flat":
            return 1.0
        chosen = self.policies.get(self.arm) or policy
        return self.original_weight(state, direct=direct, **({"policy": chosen} if chosen else {}))


def main():
    import uvicorn

    from membrain import desktop, embedded_database, evaluation_clock, helpers, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.storage import Database

    run, data_path, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    arms, sids = sys.argv[4].split(","), sys.argv[5].split(",")
    cues_dir = Path(sys.argv[6]) if len(sys.argv) > 6 else None
    out.mkdir(parents=True, exist_ok=True)
    data = {sample["sample_id"]: sample for sample in json.loads(Path(data_path).read_text(encoding="utf-8"))}
    for sid in sids:
        result_path = out / f"weights-{sid}.jsonl"
        if result_path.exists():
            print("skip", sid, flush=True)
            continue
        sample = data[sid]
        directory = run / f"brain-{sid}"
        resolved = str(directory.resolve())
        assert "locomo-time-depth-cues-" in resolved or "locomo-time-depth-heldout-" in resolved, resolved
        turns, identify = t.stored_turns(sample), t.needles(sample)
        todo = [(qid, qa) for qid, qa in t.questions(sample, {1, 2, 3, 4}) if t.evidence_ids(qa, turns)]
        last = max(t.session_time(date) for _, date, _ in t.sessions(sample))
        cues = json.loads((cues_dir / f"cues-{sid}.json").read_text(encoding="utf-8"))["cues"] if cues_dir else {}
        keys, items = {}, []
        for number, date, session_turns in t.sessions(sample):
            session = f"locomo-{sid}-s{number}"
            for turn in session_turns:
                record = host.message_record(session, "user", t.turn_text(date, turn), turn_id=turn["dia_id"],
                                             producer="locomo-ingest")
                keys[record["source_event_key"]] = turn["dia_id"]
                if cues.get(turn["dia_id"]):
                    items.append({"producer_ref": record["producer_ref"],
                                  "source_event_key": record["source_event_key"], "cues": cues[turn["dia_id"]][:6]})
        moment = last + dt.timedelta(days=1)
        os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
        evaluation_clock.enable(directory)
        helpers._scenario_clock = lambda: moment  # The stored clock is ahead and never moves back.
        profile = load_profile(directory)
        started_at = time.monotonic()
        desktop._prepare_database(profile)
        settings = dataclasses.replace(profile.settings(), recall_processes=0)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                               log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        weights = None
        rows, meta = [], {"sid": sid, "directory": resolved, "arms": arms, "cues_dir": str(cues_dir) if cues_dir else None}
        try:
            while not server.started:
                if not thread.is_alive():
                    raise SystemExit("the in-process service did not start")
                time.sleep(0.1)
            with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
                if items:
                    total = {"written": 0, "skipped": 0, "embedded": 0}
                    for start in range(0, len(items), 200):
                        result = client.write_message_cues(items[start:start + 200], model_version="host-batch")
                        for key in total:
                            total[key] += result[key]
                    meta["cue_items"], meta["cue_write"] = len(items), total
                database = Database(profile.database_url)
                try:
                    with database.transaction(Principal(profile.tenant_id, profile.principal_id)) as conn:
                        cue_rows = conn.execute(
                            "SELECT c.event_id,e.source_key,c.embedding IS NOT NULL AS has_vector "
                            "FROM memory_message_cues c JOIN memory_events e ON e.tenant_id=c.tenant_id "
                            "AND e.brain_id=c.brain_id AND e.id=c.event_id AND e.is_current "
                            "WHERE c.brain_id=%s", (profile.brain_id,)).fetchall()
                        message_rows = conn.execute(
                            "SELECT id,source_key,document #>> '{system_time,recorded_at}' AS recorded_at "
                            "FROM memory_events WHERE brain_id=%s AND is_current AND NOT deleted AND NOT suppressed "
                            "AND NOT retired AND document IS NOT NULL "
                            "AND document->'observed'->>'event_kind'='message' "
                            "AND document->'observed'->>'actor_role'='user'", (profile.brain_id,)).fetchall()
                finally:
                    database.close()
                cued_events = {row["event_id"] for row in cue_rows}
                cued_turns = {keys[row["source_key"]] for row in cue_rows if row["source_key"] in keys}
                meta["cue_rows"] = len(cue_rows)
                meta["cue_rows_with_vector"] = sum(bool(row["has_vector"]) for row in cue_rows)
                meta["messages"] = [{"dia_id": keys.get(row["source_key"]), "recorded_at": row["recorded_at"],
                                     "cued": row["id"] in cued_events} for row in message_rows]
                turn_time = {m["dia_id"]: m["recorded_at"] for m in meta["messages"] if m["dia_id"]}
                weights = Weights(arms)
                for qid, qa in todo:
                    wanted = t.evidence_ids(qa, turns)
                    now = helpers.now()
                    at = t.stamp(now)
                    row = {"id": qid, "now_label": "+1d", "category": qa["category"], "evidence": wanted, "now": now,
                           "evidence_cued": {dia: dia in cued_turns for dia in wanted},
                           "evidence_age_days": {dia: round((at - t.stamp(turn_time[dia])).total_seconds() / DAY, 3)
                                                 for dia in wanted if dia in turn_time}}
                    for arm in arms:
                        weights.arm = arm
                        context = host.recall_context(client, qa["question"], current_conversation=f"time-depth-{qid}",
                                                      limit=LIMIT) or ""
                        row[arm] = t.present(context, wanted, identify)
                        row[arm + "_chars"] = len(context)
                    rows.append(row)
                meta["weight_calls"] = weights.calls
        finally:
            if weights is not None:
                weights.restore()
            server.should_exit = True
            thread.join(timeout=30)
            embedded_database.stop(profile)
            evaluation_clock.disable()
            helpers._scenario_clock = None
        (out / f"meta-{sid}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        result_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        print(sid, len(rows), "rows", round(time.monotonic() - started_at, 1), "s", flush=True)


if __name__ == "__main__":
    main()
