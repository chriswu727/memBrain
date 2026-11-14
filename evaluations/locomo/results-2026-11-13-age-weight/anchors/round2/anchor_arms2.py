"""Anchors that cancel sinking without outranking relevance: evidence recall per arm at +1 d and +365 d. No model.

    python anchor_arms2.py RUN_DIR locomo10.json anchors2.json OUT_DIR SID

anchors2.json: {set name: {conversation: [dia ids]}}; sets real_turn, real_session, matched_turn, matched_session.
"As shipped" is the current source tree. A candidate is anchored when one of its evidence_refs is an anchor message.

Arms: auto, flat; <set>_top for every set; <set>_fresh for the real sets.
- top: in ``candidates`` the weighting loop multiplies each item's score by its shipped weight, sorts, and passes the
  list to ``source_context.source_unit_candidates(..., expand=True)``. That call is wrapped: the shipped weight of
  every item of THIS candidate list was recorded in the loop; each anchored item's score (and its rank signals) is
  multiplied by max_weight / its_weight, i.e. it ends with the highest shipped weight of the list; the list is re-sorted
  with the same key and handed on. One pass, per candidate list.
- fresh: activation set to the memory's undecayed activation (as round 1).
"""
import dataclasses
import datetime as dt
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
import time_depth_recall as t  # noqa: E402

REAL = ("real_turn", "real_session")
MATCHED = ("matched_turn", "matched_session")
SETS = REAL + MATCHED
ARMS = ("auto", "flat") + tuple(f"{s}_top" for s in SETS) + tuple(f"{s}_fresh" for s in REAL)
NOWS = (("+1d", 1), ("+365d", 365))
LIMIT = 9000
DAY = 86400.0


class Weights:
    def __init__(self, anchored):
        from membrain import candidates, dynamics, source_context

        self.candidates, self.dynamics, self.source_context = candidates, dynamics, source_context
        self.original_state, self.original_weight = dynamics.access_state, dynamics.rank_weight
        self.original_units = source_context.source_unit_candidates
        self.policy = dynamics.DEFAULT_POLICY
        self.anchored = anchored
        self.arm, self.rows, self.last = "auto", None, None
        self.records = {}  # (memory_id, revision) -> (shipped weight, flags), for the current candidate list
        self.top_stats = {"lists": 0, "lifted": 0, "max_factor": 1.0}
        candidates.access_state = dynamics.access_state = self.access_state
        candidates.rank_weight = self.rank_weight
        dynamics.rank_weight = self.tail_weight
        source_context.source_unit_candidates = self.units

    def restore(self):
        self.candidates.access_state = self.dynamics.access_state = self.original_state
        self.candidates.rank_weight = self.dynamics.rank_weight = self.original_weight
        self.source_context.source_unit_candidates = self.original_units

    def flags(self, memory):
        events = {ref.get("event_id") for ref in memory.get("evidence_refs", []) or [] if isinstance(ref, dict)}
        return {name: bool(events & ids) for name, ids in self.anchored.items()}

    def access_state(self, memory, usage, *, at, policy=None):
        state = self.original_state(memory, usage, at=at, **({"policy": policy} if policy else {}))
        flags = self.flags(memory)
        fresh = False
        if self.arm.endswith("_fresh") and flags[self.arm[:-6]]:
            activation = max(state["activation"], float((memory.get("dynamics") or {}).get("activation", 0.5)))
            tier = ("everyday" if activation >= self.policy.everyday_threshold else
                    "cue" if activation >= self.policy.cue_threshold else "deep")
            state = {**state, "activation": activation, "tier": tier}
            fresh = True
        self.last = (memory, state, flags, fresh, at)
        return state

    def rank_weight(self, state, *, direct=False, policy=None):
        weight = 1.0 if self.arm == "flat" else self.original_weight(state, direct=direct,
                                                                     **({"policy": policy} if policy else {}))
        if self.last is not None and self.last[1] is state:
            memory = self.last[0]
            self.records[(memory["memory_id"], memory["revision"])] = (weight, self.last[2])
            if self.rows is not None:
                age = (t.stamp(self.last[4] if isinstance(self.last[4], str) else self.last[4].isoformat())
                       - t.stamp(memory["system_time"]["recorded_at"])).total_seconds() / DAY
                self.rows.append({**self.last[2], "age": age, "weight": weight})
        return weight

    def tail_weight(self, state, *, direct=False, policy=None):
        return 1.0 if self.arm == "flat" else self.original_weight(state, direct=direct,
                                                                   **({"policy": policy} if policy else {}))

    def units(self, ranked, documents, *, limit, expand=False):
        if expand and self.arm.endswith("_top"):
            name = self.arm[:-4]
            known = [(item, self.records[(item["memory_id"], item["revision"])]) for item in ranked
                     if (item["memory_id"], item["revision"]) in self.records]
            if known:
                top = max(weight for _, (weight, _) in known)
                self.top_stats["lists"] += 1
                for item, (weight, flags) in known:
                    if flags[name] and weight > 0 and weight < top:
                        factor = top / weight
                        item["score"] *= factor
                        for signal in item["rank_signals"]:
                            signal["score"] *= factor
                        self.top_stats["lifted"] += 1
                        self.top_stats["max_factor"] = max(self.top_stats["max_factor"], factor)
                ranked.sort(key=lambda item: (-item["score"], item["memory_id"], item["revision"]))
        if expand:
            self.records = {}
        return self.original_units(ranked, documents, limit=limit, expand=expand)


def main():
    import uvicorn

    from membrain import desktop, embedded_database, evaluation_clock, helpers, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.helpers import Principal
    from membrain.local_profile import load_profile
    from membrain.storage import Database

    run, data_path, anchors_path, out, sid = (Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]),
                                              sys.argv[5])
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / f"anchors-{sid}.jsonl"
    if result_path.exists():
        print("skip", sid, flush=True)
        return
    sample = next(s for s in json.loads(Path(data_path).read_text(encoding="utf-8")) if s["sample_id"] == sid)
    anchor_turns = {name: set(value[sid]) for name, value in json.loads(anchors_path.read_text()).items()}
    directory = run / f"brain-{sid}"
    assert "locomo-time-depth-cues-" in str(directory.resolve()), directory
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
    weights, rows, meta = None, [], {"sid": sid}
    try:
        while not server.started:
            if not thread.is_alive():
                raise SystemExit("the in-process service did not start")
            time.sleep(0.1)
        from membrain import dynamics
        meta["rank_floor"] = dynamics.DEFAULT_POLICY.rank_floor
        database = Database(profile.database_url)
        try:
            with database.transaction(Principal(profile.tenant_id, profile.principal_id)) as conn:
                message_rows = conn.execute(
                    "SELECT id,source_key,document #>> '{system_time,recorded_at}' AS recorded_at "
                    "FROM memory_events WHERE brain_id=%s AND is_current AND NOT deleted AND NOT suppressed "
                    "AND NOT retired AND document IS NOT NULL AND document->'observed'->>'event_kind'='message' "
                    "AND document->'observed'->>'actor_role'='user'", (profile.brain_id,)).fetchall()
        finally:
            database.close()
        event_of = {keys[row["source_key"]]: row["id"] for row in message_rows if row["source_key"] in keys}
        turn_time = {keys[row["source_key"]]: row["recorded_at"] for row in message_rows if row["source_key"] in keys}
        anchored = {name: {event_of[d] for d in dias if d in event_of} for name, dias in anchor_turns.items()}
        meta["anchored_events"] = {name: len(ids) for name, ids in anchored.items()}
        meta["anchor_turns"] = {name: len(dias) for name, dias in anchor_turns.items()}
        weights = Weights(anchored)
        with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
            for label, offset in NOWS:
                moment["value"] = last + dt.timedelta(days=offset)
                for qid, qa in todo:
                    wanted = t.evidence_ids(qa, turns)
                    now = helpers.now()
                    at = t.stamp(now)
                    row = {"id": qid, "now_label": label, "category": qa["category"], "evidence": wanted, "now": now,
                           "evidence_anchor": {name: {d: d in anchor_turns[name] for d in wanted} for name in SETS},
                           "evidence_age_days": {d: round((at - t.stamp(turn_time[d])).total_seconds() / DAY, 3)
                                                 for d in wanted if d in turn_time}}
                    for arm in ARMS:
                        weights.arm = arm
                        weights.rows = [] if (arm == "auto" and label == "+1d") else None
                        context = host.recall_context(client, qa["question"], current_conversation=f"time-depth-{qid}",
                                                      limit=LIMIT) or ""
                        row[arm] = t.present(context, wanted, identify)
                        if weights.rows is not None:
                            cands = weights.rows
                            row["candidates"] = {"n": len(cands), **{name: sum(c[name] for c in cands) for name in SETS},
                                                 **{f"{name}_mean_age": statistics.fmean([c["age"] for c in cands if c[name]])
                                                    if any(c[name] for c in cands) else None for name in SETS},
                                                 "mean_age": statistics.fmean(c["age"] for c in cands) if cands else None,
                                                 "max_weight": max((c["weight"] for c in cands), default=None)}
                    weights.rows = None
                    rows.append(row)
                meta[f"top_stats_{label}"] = dict(weights.top_stats)
                weights.top_stats = {"lists": 0, "lifted": 0, "max_factor": 1.0}
                print(sid, label, "done", round(time.monotonic() - started_at, 1), "s", flush=True)
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
