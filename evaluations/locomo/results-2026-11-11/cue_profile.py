"""Where the cue route spends its time: wraps functions in process; no source change."""
import collections
import dataclasses
import json
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "evaluations/locomo")

def main():
    import uvicorn
    from run_locomo import questions

    import membrain.candidates as candidates
    from membrain import desktop, embedded_database, host, message_cues
    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.local_profile import load_profile
    data = json.loads(Path(sys.argv[1]).read_text())
    sample = data[0]
    directory = Path(sys.argv[2]) / f"brain-{sample['sample_id']}"
    profile = load_profile(directory)
    desktop._prepare_database(profile)
    settings = dataclasses.replace(profile.settings(), recall_processes=0)
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    spent = collections.defaultdict(list)
    def timed(module, name):
        original = getattr(module, name)
        def wrapper(*a, **k):
            started = time.perf_counter()
            try:
                return original(*a, **k)
            finally:
                spent[name].append((time.perf_counter() - started) * 1000)
        setattr(module, name, wrapper)
    timed(message_cues, "ranked_events")
    timed(candidates, "_cued_statements")
    timed(candidates, "collect_candidates")
    try:
        while not server.started:
            time.sleep(0.1)
        with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
            qs = [qa for _, qa in questions(sample, {1, 2, 3, 4})][:80]
            for label, kw, vec in (("off", 0, 0), ("on", 1.0, 0.5), ("off", 0, 0), ("on", 1.0, 0.5)):
                message_cues.KEYWORD_WEIGHT, message_cues.VECTOR_WEIGHT = kw, vec
                spent.clear()
                total = []
                for qa in qs:
                    started = time.perf_counter()
                    host.recall_context(client, qa["question"], current_conversation="profile")
                    total.append((time.perf_counter() - started) * 1000)
                print(label, "recall_context p50", round(statistics.median(total), 1),
                      {name: round(statistics.median(values), 1) for name, values in spent.items()}, flush=True)
    finally:
        server.should_exit = True
        thread.join(timeout=20)
        embedded_database.stop(profile)

if __name__ == "__main__":
    main()
