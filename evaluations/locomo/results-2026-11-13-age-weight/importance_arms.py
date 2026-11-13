"""Protecting host-judged "important" (cued) memories from the age weight: evidence recall per arm. No model call.

    python importance_arms.py RUN_DIR locomo10.json cues.json.gz OUT_DIR [conv-26,conv-30,conv-41]

RUN_DIR holds COPIES of the time-depth brains (brain-<conversation>). For each brain, in one process:

1. the service runs in this process (``recall_processes=0``) with the scenario clock pinned by setting
   ``helpers._scenario_clock`` directly (the stored clock files are a year on and never move back);
2. the 2026-11-11 session-written cues (``cues.json.gz``, deepseek-flash standing in for the host) are attached to
   the stored turns through ``client.write_message_cues`` (by producer_ref / source_event_key, as
   ``retrieval_recall.write_cues`` does); the cued event ids are then read back from ``memory_message_cues``;
3. every question (categories 1-4 with evidence) is asked through ``host.recall_context(client, question,
   current_conversation=..., limit=9000)`` at last session + 1 day and + 365 days under each arm, patching
   ``access_state`` / ``rank_weight`` where ``candidates`` (and the unindexed tail in ``cognition``) call them.

Arms (a candidate is "cued" when one of its evidence_refs is a message with a cue):
  auto            as shipped
  flat            weight 1.0 for every candidate
  cued_direct     1.0 for cued candidates, shipped weight for the rest
  cued_floor_040  cued: activation floored at 0.4 (explicit_activation_floor, as a user-pinned memory)
  cued_floor_025  cued: rank floor 0.25 instead of 0.15 (distinctive_rank_floor)
  cued_slow       cued: half-lives x4
"""
import dataclasses
import datetime as dt
import gzip
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

HARNESS = Path("REPOSITORY/evaluations/locomo")
sys.path.insert(0, str(HARNESS))
import time_depth_recall as t  # noqa: E402

ARMS = ("auto", "flat", "cued_direct", "cued_floor_040", "cued_floor_025", "cued_slow")
NOWS = (("+1d", 1), ("+365d", 365))
LIMIT = 9000
DAY = 86400.0


class ArmWeights:
    def __init__(self, cued_events):
        from membrain import candidates, dynamics

        self.candidates, self.dynamics = candidates, dynamics
        self.original_state, self.original_weight = dynamics.access_state, dynamics.rank_weight
        self.default = dynamics.DEFAULT_POLICY
        self.slow = dataclasses.replace(self.default, half_life_days={
            key: value * 4 for key, value in self.default.half_life_days.items()})
        self.floor025 = dataclasses.replace(self.default, rank_floor=0.25)
        self.cued_events = set(cued_events)
        self.arm, self.rows, self.last = "auto", None, None
        self.calls = {"candidates": 0, "tail": 0}
        candidates.access_state = self.access_state
        candidates.rank_weight = self.rank_weight
        dynamics.access_state = self.access_state
        dynamics.rank_weight = self.tail_weight

    def restore(self):
        self.candidates.access_state, self.candidates.rank_weight = self.original_state, self.original_weight
        self.dynamics.access_state, self.dynamics.rank_weight = self.original_state, self.original_weight

    def is_cued(self, memory):
        return any(isinstance(ref, dict) and ref.get("event_id") in self.cued_events
                   for ref in memory.get("evidence_refs", []) or [])

    def access_state(self, memory, usage, *, at, policy=None):
        options = {"policy": policy} if policy else {}
        state = self.original_state(memory, usage, at=at, **options)
        cued = self.is_cued(memory)
        if cued and self.arm == "cued_slow":
            state = self.original_state(memory, usage, at=at, policy=self.slow)
        elif cued and self.arm == "cued_floor_040":
            activation = max(state["activation"], self.default.explicit_activation_floor)
            tier = ("everyday" if activation >= self.default.everyday_threshold else
                    "cue" if activation >= self.default.cue_threshold else "deep")
            state = {**state, "activation": activation, "tier": tier}
        self.last = (memory, state, cued, at)
        return state

    def _weight(self, state, direct, policy):
        options = {"policy": policy} if policy else {}
        cued = self.last is not None and self.last[1] is state and self.last[2]
        if self.arm == "flat":
            return 1.0, cued
        if cued and self.arm == "cued_direct":
            return 1.0, cued
        if cued and self.arm == "cued_floor_025":
            return self.original_weight(state, direct=direct, policy=self.floor025), cued
        return self.original_weight(state, direct=direct, **options), cued

    def rank_weight(self, state, *, direct=False, policy=None):
        self.calls["candidates"] += 1
        weight, cued = self._weight(state, direct, policy)
        if self.rows is not None and self.last is not None and self.last[1] is state:
            memory, at = self.last[0], self.last[3]
            age = (t.stamp(at if isinstance(at, str) else at.isoformat()) - t.stamp(memory["system_time"]["recorded_at"])
                   ).total_seconds() / DAY
            self.rows.append({"events": [ref["event_id"] for ref in memory.get("evidence_refs", []) or []
                                         if isinstance(ref, dict) and "event_id" in ref],
                              "cued": cued, "age": age, "weight": weight, "tier": state["tier"], "direct": direct})
        return weight

    def tail_weight(self, state, *, direct=False, policy=None):
        self.calls["tail"] += 1
        return self._weight(state, direct, policy)[0]


def age_bucket(age, offset):
    return t.bucket_of(age, offset)


def main():
    import uvicorn

    from membrain import desktop, embedded_database, evaluation_clock, helpers, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.storage import Database

    run, data_path, cues_path, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
    chosen = sys.argv[5].split(",") if len(sys.argv) > 5 else ["conv-26", "conv-30", "conv-41"]
    out.mkdir(parents=True, exist_ok=True)
    data = {sample["sample_id"]: sample for sample in json.loads(Path(data_path).read_text(encoding="utf-8"))}
    with gzip.open(cues_path, "rt", encoding="utf-8") as stream:
        all_cues = json.load(stream)
    for sid in chosen:
        result_path = out / f"arms-{sid}.jsonl"
        if result_path.exists():
            print("skip", sid, flush=True)
            continue
        sample = data[sid]
        directory = run / f"brain-{sid}"
        assert "locomo-time-depth-cues-" in str(directory.resolve()), "refusing to work on anything but a copy"
        cues = all_cues[sid]["cues"]
        turns, identify = t.stored_turns(sample), t.needles(sample)
        todo = [(qid, qa) for qid, qa in t.questions(sample, {1, 2, 3, 4}) if t.evidence_ids(qa, turns)]
        last = max(t.session_time(date) for _, date, _ in t.sessions(sample))
        keys, items = {}, []
        for number, date, session_turns in t.sessions(sample):
            session = f"locomo-{sid}-s{number}"
            for turn in session_turns:
                record = host.message_record(session, "user", t.turn_text(date, turn), turn_id=turn["dia_id"],
                                             producer="locomo-ingest")
                keys[record["source_event_key"]] = turn["dia_id"]
                if turn["dia_id"] in cues:
                    items.append({"producer_ref": record["producer_ref"],
                                  "source_event_key": record["source_event_key"], "cues": cues[turn["dia_id"]][:6]})
        moment = {"value": last + dt.timedelta(days=1)}
        os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
        evaluation_clock.enable(directory)
        helpers._scenario_clock = lambda: moment["value"]  # The stored clock is a year on and never moves back.
        profile = load_profile(directory)
        started_at = time.monotonic()
        desktop._prepare_database(profile)
        settings = dataclasses.replace(profile.settings(), recall_processes=0)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                               log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        weights = None
        rows, meta = [], {"sid": sid, "directory": str(directory)}
        try:
            while not server.started:
                if not thread.is_alive():
                    raise SystemExit("the in-process service did not start")
                time.sleep(0.1)
            meta["started_s"] = round(time.monotonic() - started_at, 1)
            with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
                # Attach the cues (replaces any a message already has; idempotent).
                total = {"written": 0, "skipped": 0, "embedded": 0}
                for start in range(0, len(items), 200):
                    result = client.write_message_cues(items[start:start + 200], model_version="deepseek-flash")
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
                meta["cued_turns"] = sorted(cued_turns)
                meta["messages"] = [{"event_id": row["id"], "dia_id": keys.get(row["source_key"]),
                                     "recorded_at": row["recorded_at"], "cued": row["id"] in cued_events}
                                    for row in message_rows]
                turn_time = {m["dia_id"]: m["recorded_at"] for m in meta["messages"] if m["dia_id"]}
                weights = ArmWeights(cued_events)
                for label, offset in NOWS:
                    moment["value"] = last + dt.timedelta(days=offset)
                    for qid, qa in todo:
                        wanted = t.evidence_ids(qa, turns)
                        now = helpers.now()
                        at = t.stamp(now)
                        row = {"id": qid, "now_label": label, "category": qa["category"], "evidence": wanted,
                               "now": now, "evidence_cued": {dia: dia in cued_turns for dia in wanted},
                               "evidence_age_days": {dia: round((at - t.stamp(turn_time[dia])).total_seconds() / DAY, 3)
                                                     for dia in wanted if dia in turn_time}}
                        for arm in ARMS:
                            weights.arm = arm
                            weights.rows = [] if (arm == "auto" and label == "+1d") else None
                            context = host.recall_context(client, qa["question"], current_conversation=f"time-depth-{qid}",
                                                          limit=LIMIT) or ""
                            row[arm] = t.present(context, wanted, identify)
                            row[arm + "_chars"] = len(context)
                            if weights.rows is not None:
                                cands = weights.rows
                                cued_ages = [c["age"] for c in cands if c["cued"]]
                                plain_ages = [c["age"] for c in cands if not c["cued"]]
                                wanted_events = {e for e, info in ((m["event_id"], m["dia_id"]) for m in meta["messages"])
                                                 if info in wanted}
                                ev = [c for c in cands if set(c["events"]) & wanted_events]
                                row["candidates"] = {
                                    "n": len(cands), "cued": len(cued_ages),
                                    "cued_mean_age": statistics.fmean(cued_ages) if cued_ages else None,
                                    "uncued_mean_age": statistics.fmean(plain_ages) if plain_ages else None,
                                    "evidence_statements": len(ev), "evidence_cued": sum(c["cued"] for c in ev),
                                    "direct_any": any(c["direct"] for c in cands)}
                        weights.rows = None
                        rows.append(row)
                    print(sid, label, "done", round(time.monotonic() - started_at, 1), "s", flush=True)
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
