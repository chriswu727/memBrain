"""Development-split sweep of host selection limits (no source change: module constants are patched in process)."""
import json, sys, time, statistics
from pathlib import Path
sys.path.insert(0, "evaluations/locomo")  # Run from the repository root.
from retrieval_recall import stored_turns, needles, evidence_ids, present
from run_locomo import ingest, questions
from membrain import host, desktop

data = json.loads(Path(sys.argv[1]).read_text())
root, cache = Path(sys.argv[2]), Path(sys.argv[3])
CONFIGS = [("baseline 12 msgs / 10 vec / 8 replies / 32k", 12, 10, 8, 32000),
           ("24 msgs", 24, 10, 8, 32000), ("40 msgs", 40, 10, 8, 32000),
           ("40 msgs / 30 vec", 40, 30, 8, 32000), ("40 msgs / 30 vec / 0 replies", 40, 30, 0, 32000),
           ("40 msgs / 30 vec / 64k", 40, 30, 8, 64000), ("60 msgs / 50 vec / 96k", 60, 50, 8, 96000)]
results = {name: {"all": 0, "share": 0.0, "chars": [], "ms": [], "n": 0, "multi_all": 0, "multi_n": 0} for name, *_ in CONFIGS}
for index in (0, 1, 2):
    sample = data[index]
    directory = root / f"brain-{sample['sample_id']}"
    ingest(sample, directory, cache, None, None)
    turns, identify = stored_turns(sample), needles(sample)
    try:
        with host.ready_client(directory) as client:
            for qid, qa in questions(sample, {1, 2, 3, 4}):
                wanted = evidence_ids(qa, turns)
                if not wanted:
                    continue
                for name, messages, vectors, replies, tokens in CONFIGS:
                    host.MAX_MESSAGES, host.VECTOR_ONLY_STATEMENTS, host.MAX_REPLIES, host.RECALL_TOKENS = messages, vectors, replies, tokens
                    host.recall_budget.__defaults__ = (tokens,)
                    host._replies.__defaults__ = (replies,)
                    started = time.perf_counter()
                    context = host.recall_context(client, qa["question"], current_conversation="sweep") or ""
                    elapsed = (time.perf_counter() - started) * 1000
                    got = present(context, wanted, identify)
                    r = results[name]
                    r["n"] += 1; r["all"] += len(got) == len(wanted); r["share"] += len(got) / len(wanted)
                    r["chars"].append(len(context)); r["ms"].append(elapsed)
                    if len(wanted) > 1:
                        r["multi_n"] += 1; r["multi_all"] += len(got) == len(wanted)
    finally:
        desktop.stop(directory)
print(f"{'config':46}{'n':>5}{'all':>8}{'share':>8}{'multi all':>11}{'chars':>8}{'p50 ms':>8}{'p95 ms':>8}")
for name, r in results.items():
    ms = sorted(r["ms"])
    print(f"{name:46}{r['n']:>5}{r['all'] / r['n']:>8.1%}{r['share'] / r['n']:>8.1%}{r['multi_all'] / max(1, r['multi_n']):>11.1%}"
          f"{round(statistics.fmean(r['chars'])):>8}{ms[len(ms) // 2]:>8.0f}{ms[int(len(ms) * .95)]:>8.0f}")
