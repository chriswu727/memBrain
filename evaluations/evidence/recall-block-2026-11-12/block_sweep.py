"""Sweep of cue-sibling recall and recall-block size, with the service inside this process; no source change.

    python sibling_sweep.py locomo10.json BRAINS_DIR conversation-indexes OUT.json
"""
import dataclasses
import json
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "evaluations/locomo")

CONFIGS = [  # name, block characters, messages, recall tokens, replies shown, characters per message
    ("0 current 9000", 9000, 40, 32000, 8, 700),
    ("1 9000, no replies", 9000, 40, 32000, 0, 700),
    ("2 9000, 400 per message", 9000, 40, 32000, 8, 400),
    ("3 9000, no replies, 400", 9000, 50, 32000, 0, 400),
    ("4 block 12000", 12000, 55, 48000, 8, 700),
    ("5 block 15000", 15000, 70, 48000, 8, 700),
    ("6 block 18000", 18000, 85, 64000, 8, 700),
]


def main():
    import uvicorn
    from retrieval_recall import evidence_ids, needles, present, stored_turns
    from run_locomo import questions

    from membrain import desktop, embedded_database, host, message_cues
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.local_profile import load_profile

    data = json.loads(Path(sys.argv[1]).read_text())
    root = Path(sys.argv[2])
    selected = [int(i) for i in sys.argv[3].split(",")]
    rows = []
    for index in selected:
        sample = data[index]
        directory = root / f"brain-{sample['sample_id']}"
        profile = load_profile(directory)
        desktop._prepare_database(profile)
        settings = dataclasses.replace(profile.settings(), recall_processes=0)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                               log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(0.1)
            turns, identify = stored_turns(sample), needles(sample)
            with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
                for qid, qa in questions(sample, {1, 2, 3, 4}):
                    wanted = evidence_ids(qa, turns)
                    if not wanted:
                        continue
                    row = {"id": qid, "evidence": wanted}
                    for name, characters, messages, tokens, replies, per_message in CONFIGS:
                        message_cues.SIBLING_WEIGHT = 0.0
                        host._replies.__defaults__ = (replies,)
                        host._window.__defaults__ = (per_message,)
                        host.MAX_MESSAGES = messages
                        host.recall_budget.__defaults__ = (tokens,)
                        started = time.perf_counter()
                        context = host.recall_context(client, qa["question"], current_conversation="sweep",
                                                      limit=characters) or ""
                        row[name] = {"found": present(context, wanted, identify), "chars": len(context),
                                     "ms": round((time.perf_counter() - started) * 1000, 1)}
                    rows.append(row)
            print(sample["sample_id"], "done", len(rows), flush=True)
        finally:
            server.should_exit = True
            thread.join(timeout=20)
            embedded_database.stop(profile)
    Path(sys.argv[4]).write_text(json.dumps(rows))
    print(f"{'config':32}{'all':>8}{'one':>8}{'several':>9}{'sev share':>11}{'chars':>8}{'p50 ms':>8}")
    one = [r for r in rows if len(r["evidence"]) == 1]
    several = [r for r in rows if len(r["evidence"]) > 1]
    for name, *_ in CONFIGS:
        def rate(items):
            return sum(len(r[name]["found"]) == len(r["evidence"]) for r in items) / max(1, len(items))
        share = statistics.fmean(len(r[name]["found"]) / len(r["evidence"]) for r in several)
        print(f"{name:32}{rate(rows):>8.1%}{rate(one):>8.1%}{rate(several):>9.1%}{share:>11.1%}"
              f"{round(statistics.fmean(r[name]['chars'] for r in rows)):>8}"
              f"{statistics.median(r[name]['ms'] for r in rows):>8.0f}")
    print("questions", len(rows), "one", len(one), "several", len(several))


if __name__ == "__main__":
    main()
