"""Re-ask the brains stored by ``time_depth_recall.py`` one day after the last session, with the search arm. No model.

    python evaluations/locomo/time_depth_deliberate.py RUN_DIR locomo10.json [answers-plain-all.jsonl.gz]

``tool_deliberate`` is what a host's search tool sends (``host.recall_context(..., deliberate=True)``); ``auto`` and
``auto_flat`` repeat the automatic block with the age weight on and off.
"""
import dataclasses
import datetime as dt
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import time_depth_recall as t  # noqa: E402

RUN = Path(sys.argv[1])
DATA = sys.argv[2]
SEARCHES = t.recorded_searches(sys.argv[3]) if len(sys.argv) > 3 else {}


def main():
    import uvicorn

    from membrain import desktop, embedded_database, evaluation_clock, helpers, host
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.local_profile import load_profile

    data = json.loads(Path(DATA).read_text(encoding="utf-8"))
    for index in (0, 1, 2):
        sample = data[index]
        sid = sample["sample_id"]
        directory = RUN / f"brain-{sid}"
        path = RUN / f"recall-{sid}-+1d-deliberate.jsonl"
        if path.exists():
            continue
        turns, identify = t.stored_turns(sample), t.needles(sample)
        todo = [(qid, qa) for qid, qa in t.questions(sample, {1, 2, 3, 4}) if t.evidence_ids(qa, turns)]
        last = max(t.session_time(date) for _, date, _ in t.sessions(sample))
        moment = last + dt.timedelta(days=1)
        os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
        evaluation_clock.enable(directory)
        helpers._scenario_clock = lambda: moment  # The stored clock is a year on and never moves back.
        profile = load_profile(directory)
        desktop._prepare_database(profile)
        settings = dataclasses.replace(profile.settings(), recall_processes=0)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                               log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        weights = t.Weights()
        rows = []
        try:
            while not server.started:
                time.sleep(0.1)
            with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
                for qid, qa in todo:
                    wanted = t.evidence_ids(qa, turns)
                    row = {"id": qid, "category": qa["category"], "evidence": wanted, "now": helpers.now()}

                    def measure(name, query, **options):
                        context = host.recall_context(client, query, **options) or ""
                        row[name] = t.present(context, wanted, identify)

                    weights.flat, weights.rows = False, None
                    measure("auto", qa["question"], current_conversation=f"time-depth-{qid}")
                    weights.flat = True
                    measure("auto_flat", qa["question"], current_conversation=f"time-depth-{qid}")
                    weights.flat = False
                    measure("tool_deliberate", host.scrub(qa["question"]), deliberate=True)
                    if qid in SEARCHES:
                        for name, options in (("searches", {}), ("searches_deliberate", {"deliberate": True})):
                            found = set()
                            for query in SEARCHES[qid]:
                                found.update(t.present(host.recall_context(client, host.scrub(query), **options) or "",
                                                       wanted, identify))
                            row[name] = [dia for dia in wanted if dia in found]
                    rows.append(row)
        finally:
            weights.restore()
            server.should_exit = True
            thread.join(timeout=30)
            embedded_database.stop(profile)
            evaluation_clock.disable()
            helpers._scenario_clock = None
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        print(sid, len(rows), flush=True)
    rows = [json.loads(line) for index in (0, 1, 2) for line in
            (RUN / f"recall-{data[index]['sample_id']}-+1d-deliberate.jsonl").read_text().splitlines()]
    def rate(name, chosen):
        chosen = [row for row in chosen if name in row]
        return f"{sum(set(row[name]) >= set(row['evidence']) for row in chosen) / len(chosen):.1%} ({len(chosen)})"
    for name in ("auto", "auto_flat", "tool_deliberate"):
        print(name, "all", rate(name, rows), "several", rate(name, [r for r in rows if len(r["evidence"]) > 1]))
    with_searches = [row for row in rows if "searches" in row]
    for name in ("auto", "searches", "searches_deliberate"):
        print("75:", name, rate(name, with_searches))
    def both(a, b):
        return f"{sum(set(r[a]) | set(r[b]) >= set(r['evidence']) for r in with_searches) / len(with_searches):.1%}"
    print("75: auto+searches", both("auto", "searches"), "auto+searches_deliberate", both("auto", "searches_deliberate"))
    print("deliberate != flat:", sum(set(r["tool_deliberate"]) != set(r["auto_flat"]) for r in rows))


main()
