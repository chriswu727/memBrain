"""Development-split sweep of the cue route's weights. The real service runs in this process (no recall worker
pool) so module constants can be changed between requests; no source file is changed.

    python cue_sweep.py locomo10.json BRAINS_DIR CUES_DIR [conversation indexes]
"""
import dataclasses
import json
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "evaluations/locomo")

CONFIGS = [  # name, keyword weight, keyword power, vector weight, host treats a cue hit as (keyword|vector)
    ("0 no cues", 0, 2, 0),
    ("1 words p1", 1.0, 1, 0),
    ("2 words p2", 1.0, 2, 0),
    ("3 meaning 1.0", 0, 2, 1.0),
    ("4 meaning 0.5", 0, 2, 0.5),
    ("5 words p2 + meaning 1.0", 1.0, 2, 1.0),
    ("6 words p2 + meaning 0.5", 1.0, 2, 0.5),
    ("7 words p2 0.5 + meaning 0.5", 0.5, 2, 0.5),
    ("8 words p1 + meaning 1.0", 1.0, 1, 1.0),
]


def main():
    import uvicorn
    from retrieval_recall import evidence_ids, needles, present, stored_turns, write_cues
    from run_locomo import questions

    from membrain import desktop, embedded_database, host, message_cues
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.local_profile import load_profile

    data = json.loads(Path(sys.argv[1]).read_text())
    root, cue_dir = Path(sys.argv[2]), Path(sys.argv[3])
    selected = [int(i) for i in sys.argv[4].split(",")] if len(sys.argv) > 4 else [0, 1, 2]
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
            cues = json.loads((cue_dir / f"cues-{sample['sample_id']}.json").read_text())["cues"]
            original = host.ready_client
            host.ready_client = lambda directory, *a, **k: MemoryClient(profile.base_url, profile.api_key, profile.brain_id)
            try:
                print(sample["sample_id"], "cues", write_cues(sample, directory, cues), flush=True)
            finally:
                host.ready_client = original
            turns, identify = stored_turns(sample), needles(sample)
            with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
                for qid, qa in questions(sample, {1, 2, 3, 4}):
                    wanted = evidence_ids(qa, turns)
                    if not wanted:
                        continue
                    row = {"id": qid, "evidence": wanted}
                    for name, keyword, power, vector in CONFIGS:
                        message_cues.KEYWORD_WEIGHT, message_cues.KEYWORD_POWER, message_cues.VECTOR_WEIGHT = keyword, power, vector
                        started = time.perf_counter()
                        context = host.recall_context(client, qa["question"], current_conversation="sweep") or ""
                        row[name] = {"found": present(context, wanted, identify), "chars": len(context),
                                     "ms": round((time.perf_counter() - started) * 1000, 1)}
                    rows.append(row)
            print(sample["sample_id"], "done", len(rows), flush=True)
        finally:
            server.should_exit = True
            thread.join(timeout=20)
            embedded_database.stop(profile)
    Path(sys.argv[2], "cue-sweep.json").write_text(json.dumps(rows))
    print(f"{'config':34}{'all':>8}{'one':>8}{'several':>9}{'sev share':>11}{'chars':>8}{'p50 ms':>8}")
    for name, *_ in CONFIGS:
        def rate(items):
            return sum(len(r[name]["found"]) == len(r["evidence"]) for r in items) / max(1, len(items))
        one = [r for r in rows if len(r["evidence"]) == 1]
        several = [r for r in rows if len(r["evidence"]) > 1]
        share = statistics.fmean(len(r[name]["found"]) / len(r["evidence"]) for r in several)
        print(f"{name:34}{rate(rows):>8.1%}{rate(one):>8.1%}{rate(several):>9.1%}{share:>11.1%}"
              f"{round(statistics.fmean(r[name]['chars'] for r in rows)):>8}"
              f"{statistics.median(r[name]['ms'] for r in rows):>8.0f}")
    print("questions", len(rows), "one", len(one), "several", len(several))


if __name__ == "__main__":
    main()
