"""Sparing note anchors from the age weight: evidence recall per arm at +1 d and +365 d. No model call.

    python anchor_arms.py RUN_DIR locomo10.json anchors.json OUT_DIR SID

RUN_DIR holds the development copies with cues (brain-<sid>). The service runs in this process
(``recall_processes=0``); the clock is pinned with ``helpers._scenario_clock``. "As shipped" is the current source
tree (rank floor 0.30). A candidate is anchored when one of its evidence_refs is an anchor message of the set.
Arms: auto, flat, and for each set S in (turn, session): S_direct (weight 1.0), S_fresh (activation set to the
memory's undecayed activation, as if recorded now), S_floor (activation floored at explicit_activation_floor 0.4).
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

SETS = ("turn", "session")
ARMS = ("auto", "flat") + tuple(f"{s}_{kind}" for s in SETS for kind in ("direct", "fresh", "floor"))
NOWS = (("+1d", 1), ("+365d", 365))
LIMIT = 9000
DAY = 86400.0


class AnchorWeights:
    def __init__(self, anchored):  # anchored: set name -> event ids
        from membrain import candidates, dynamics

        self.candidates, self.dynamics = candidates, dynamics
        self.original_state, self.original_weight = dynamics.access_state, dynamics.rank_weight
        self.policy = dynamics.DEFAULT_POLICY
        self.anchored = anchored
        self.arm, self.rows, self.last = "auto", None, None
        candidates.access_state = dynamics.access_state = self.access_state
        candidates.rank_weight = self.rank_weight
        dynamics.rank_weight = self.tail_weight

    def restore(self):
        self.candidates.access_state = self.dynamics.access_state = self.original_state
        self.candidates.rank_weight = self.dynamics.rank_weight = self.original_weight

    def flags(self, memory):
        events = {ref.get("event_id") for ref in memory.get("evidence_refs", []) or [] if isinstance(ref, dict)}
        return {name: bool(events & ids) for name, ids in self.anchored.items()}

    def _tier(self, activation):
        return ("everyday" if activation >= self.policy.everyday_threshold else
                "cue" if activation >= self.policy.cue_threshold else "deep")

    def access_state(self, memory, usage, *, at, policy=None):
        state = self.original_state(memory, usage, at=at, **({"policy": policy} if policy else {}))
        flags = self.flags(memory)
        kind = None
        if self.arm not in ("auto", "flat"):
            name, kind = self.arm.split("_")
            if not flags[name]:
                kind = None
        if kind == "fresh":
            start = float((memory.get("dynamics") or {}).get("activation", 0.5))
            activation = max(state["activation"], start)
            state = {**state, "activation": activation, "tier": self._tier(activation)}
        elif kind == "floor":
            activation = max(state["activation"], self.policy.explicit_activation_floor)
            state = {**state, "activation": activation, "tier": self._tier(activation)}
        self.last = (memory, state, flags, kind, at)
        return state

    def _weight(self, state, direct, policy):
        kind = self.last[3] if self.last is not None and self.last[1] is state else None
        if self.arm == "flat" or kind == "direct":
            return 1.0
        return self.original_weight(state, direct=direct, **({"policy": policy} if policy else {}))

    def rank_weight(self, state, *, direct=False, policy=None):
        weight = self._weight(state, direct, policy)
        if self.rows is not None and self.last is not None and self.last[1] is state:
            memory, at = self.last[0], self.last[4]
            age = (t.stamp(at if isinstance(at, str) else at.isoformat())
                   - t.stamp(memory["system_time"]["recorded_at"])).total_seconds() / DAY
            self.rows.append({**self.last[2], "age": age, "weight": weight})
        return weight

    def tail_weight(self, state, *, direct=False, policy=None):
        return self._weight(state, direct, policy)


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
                meta["cue_rows"] = conn.execute("SELECT count(*) AS n FROM memory_message_cues WHERE brain_id=%s",
                                                (profile.brain_id,)).fetchone()["n"]
        finally:
            database.close()
        event_of = {keys[row["source_key"]]: row["id"] for row in message_rows if row["source_key"] in keys}
        turn_time = {keys[row["source_key"]]: row["recorded_at"] for row in message_rows if row["source_key"] in keys}
        anchored = {name: {event_of[d] for d in dias if d in event_of} for name, dias in anchor_turns.items()}
        meta["anchored_events"] = {name: len(ids) for name, ids in anchored.items()}
        meta["anchor_turns"] = {name: len(dias) for name, dias in anchor_turns.items()}
        weights = AnchorWeights(anchored)
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
                                                 "mean_age": statistics.fmean(c["age"] for c in cands) if cands else None}
                    weights.rows = None
                    rows.append(row)
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
