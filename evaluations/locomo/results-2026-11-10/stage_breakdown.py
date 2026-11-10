"""Where does memBrain lose evidence that raw hybrid retrieval finds? Development conversations only."""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, "evaluations/locomo")  # Run from the repository root.
from retrieval_recall import stored_turns, needles, evidence_ids
from run_locomo import ingest, questions
from membrain import host, desktop

data = json.loads(Path(sys.argv[1]).read_text())
root, cache = Path(sys.argv[2]), Path(sys.argv[3])
stage = collections.Counter()
ranks, sizes, signal_mix = [], [], collections.Counter()
for index in (0, 1, 2):
    sample = data[index]
    directory = root / f"brain-{sample['sample_id']}"
    ingest(sample, directory, cache, None, None)
    turns, identify = stored_turns(sample), needles(sample)
    try:
        with host.ready_client(directory) as client:
            # event id of every stored turn
            events, before = {}, None
            while True:
                page = client.timeline(roles=("user",), max_characters=200_000, max_item_characters=2000, limit=200,
                                       **({"before_sequence": before} if before else {}))
                items = page.get("items", [])
                for item in items:
                    flat = " ".join((item.get("text") or "").split())
                    events[flat[:120]] = item["event_id"]
                if page.get("complete", True) or not items:
                    break
                before = min(item["sequence"] for item in items)
            by_dia = {}
            for dia, text in turns.items():
                key = " ".join(text.split())[:120]
                if key in events:
                    by_dia[dia] = events[key]
            for qid, qa in questions(sample, {1, 2, 3, 4}):
                wanted = [e for e in evidence_ids(qa, turns) if e in by_dia]
                if not wanted:
                    continue
                response = host.recall(client, qa["question"])
                items = (response.get("result") or {}).get("items", [])
                sizes.append(len(items))
                # rank of each event among response items (first statement citing it)
                first = {}
                for position, item in enumerate(items):
                    signals = {s.get("method"): s.get("score") or 0 for s in item.get("rank_signals") or []}
                    for ref in (item.get("memory") or {}).get("evidence_refs") or []:
                        if ref.get("event_id") not in first:
                            first[ref["event_id"]] = (position, signals, item.get("display_mode"))
                sources = [event for event, _ in host._sources(response, "question")]
                for dia in wanted:
                    event = by_dia[dia]
                    if event in sources:
                        stage["selected (within 12)"] += 1
                        ranks.append(sources.index(event))
                    elif event not in first:
                        stage["not in service response"] += 1
                    else:
                        position, signals, mode = first[event]
                        kw, vec = signals.get("keyword", 0) > 0, signals.get("vector", 0) > 0
                        stage["in response, dropped by host selection"] += 1
                        signal_mix[("keyword" if kw else "") + ("+vector" if vec else "") + f" mode={mode} pos<{(position // 25 + 1) * 25}"] += 1
    finally:
        desktop.stop(directory)
total = sum(stage.values())
print("evidence turns:", total)
for name, count in stage.most_common():
    print(f"  {name}: {count} ({count / total:.1%})")
print("response size p50/max:", sorted(sizes)[len(sizes) // 2], max(sizes))
print("dropped-by-host breakdown:")
for name, count in signal_mix.most_common(12):
    print("   ", name, count)
