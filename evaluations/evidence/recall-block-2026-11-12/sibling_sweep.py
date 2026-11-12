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

CONFIGS = [  # name, sibling weight, sibling members cap, block characters, messages, recall tokens
    ("0 current", 0.0, 12, 9000, 40, 32000),
    ("1 siblings 0.5, cap 12", 0.5, 12, 9000, 40, 32000),
    ("2 siblings 0.25, cap 12", 0.25, 12, 9000, 40, 32000),
    ("3 siblings 0.5, cap 30", 0.5, 30, 9000, 40, 32000),
    ("4 siblings 1.0, cap 12", 1.0, 12, 9000, 40, 32000),
    ("5 block 12000", 0.0, 12, 12000, 55, 48000),
    ("6 block 12000 + siblings 0.5", 0.5, 12, 12000, 55, 48000),
    ("7 block 15000", 0.0, 12, 15000, 70, 48000),
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
                    for name, weight, members, characters, messages, tokens in CONFIGS:
                        message_cues.SIBLING_WEIGHT, message_cues.SIBLING_MEMBERS = weight, members
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
