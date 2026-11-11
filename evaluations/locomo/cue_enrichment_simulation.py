"""Simulation: consolidation as cues attached to the original messages. PAID for the cue generation only.

A model reads each finished session once and names, for each turn that holds a lasting fact, the kind of fact and
whom it is about ("Melanie hobbies and activities", "Caroline country of origin"). The cues never reach a host;
they join the turn's indexed text. The question is whether recall then finds the evidence of questions whose
wording the conversation never uses. Scored without a model, at message level with a plain index (BM25 and
whole-message embeddings), as in ``results-2026-11-11/association_feedback.py``.

    python evaluations/locomo/cue_enrichment_simulation.py --data locomo10.json --out RUN_DIR \
        --model-cache MODEL_DIR --conversations 0,1,2 --ceiling 85
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from consolidation_experiment import ENDPOINT, Ledger, MeteredTransport, read_key  # noqa: E402
from retrieval_recall import RawIndex, evidence_ids, stored_turns  # noqa: E402
from run_locomo import Model, log, questions, sessions  # noqa: E402

CUE_MODEL = "deepseek-flash"
CUE_RULES = """You index a conversation for later recall. For each turn of the session below that states a lasting \
fact about a person, give one to four short cue phrases that name WHOM the fact is about and WHAT KIND of fact it is, \
in the words someone would use to ask about it later. Examples: "Melanie hobbies and activities", "Caroline \
relationship status", "Caroline country of origin", "Melanie children's interests", "Jon reasons for starting his \
business", "Gina ways to relax", "John places visited", "Maria volunteering".

Rules:
- Name the category, do not restate the detail: for "I signed up for a pottery class" write "Melanie hobbies and \
activities", not "Melanie pottery class".
- Use the person's name, never "I" or "she".
- Skip greetings, reactions and turns with no lasting fact.

Return JSON: {"cues": {"<turn id>": ["cue", "cue"]}} with only the turns that have cues."""


def generate(sample: dict, model: Model, out: Path) -> dict[str, list[str]]:
    """Cues for every turn of one conversation, one call per session; resumable."""
    path = out / f"cues-{sample['sample_id']}.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"sessions": {}, "cues": {}}
    for number, date, turns in sessions(sample):
        if str(number) in state["sessions"]:
            continue
        transcript = "\n".join(f"[{turn['dia_id']}] {turn['speaker']}: {turn.get('text', '')}"
                               + (f" [shares an image: {turn['blip_caption']}]" if turn.get("blip_caption") else "")
                               for turn in turns)
        message = model.chat([{"role": "system", "content": CUE_RULES},
                              {"role": "user", "content": f"Session {number}, {date}:\n{transcript}"}],
                             json_mode=True, max_tokens=2000)
        known, kept = {turn["dia_id"] for turn in turns}, 0
        try:
            proposed = json.loads(message.get("content") or "{}").get("cues") or {}
        except (ValueError, AttributeError):
            proposed = {}
        for turn_id, cues in proposed.items() if isinstance(proposed, dict) else ():
            if turn_id in known and isinstance(cues, list):
                clean = [" ".join(str(cue).split())[:80] for cue in cues[:4] if str(cue).strip()]
                if clean:
                    state["cues"][turn_id] = clean
                    kept += 1
        state["sessions"][str(number)] = {"turns": len(turns), "with_cues": kept}
        path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return state["cues"]


def rrf(orders, weights):
    score = collections.defaultdict(float)
    for order, weight in zip(orders, weights, strict=True):
        for rank, item in enumerate(order):
            score[item] += weight / (61 + rank)
    return sorted(score, key=lambda item: (-score[item], item))


def simulate(data, selected, cues_by_sample, provider, cut=40):
    import numpy

    stats = collections.defaultdict(lambda: collections.defaultdict(list))
    for index in selected:
        sample = data[index]
        turns = stored_turns(sample)
        cues = cues_by_sample[sample["sample_id"]]
        plain = RawIndex(turns, provider)
        enriched = RawIndex({key: text + (" [" + "; ".join(cues[key]) + "]" if key in cues else "")
                             for key, text in turns.items()}, provider)
        cue_ids = [key for key in turns if key in cues]
        cue_only = RawIndex({key: "; ".join(cues[key]) for key in cue_ids}, provider) if cue_ids else None
        position = {key: i for i, key in enumerate(plain.ids)}
        for _, qa in questions(sample, {1, 2, 3, 4}):
            wanted = [position[e] for e in evidence_ids(qa, turns)]
            if not wanted:
                continue
            query = qa["question"]
            vector = plain._embed([query], "query")[0]
            lexical = plain._bm25(query)
            semantic = [int(i) for i in numpy.argsort(-(plain.vectors @ vector))]
            rich_lexical = enriched._bm25(query)
            rich_semantic = [int(i) for i in numpy.argsort(-(enriched.vectors @ vector))]
            variants = {"0 first pass": rrf([lexical, semantic], [1, 1]),
                        "1 cues in the indexed text, both routes": rrf([rich_lexical, rich_semantic], [1, 1]),
                        "2 cues in the keyword route only": rrf([rich_lexical, semantic], [1, 1]),
                        "3 cues in the meaning route only": rrf([lexical, rich_semantic], [1, 1])}
            if cue_only is not None:
                cue_lexical = [position[cue_only.ids[i]] for i in cue_only._bm25(query)]
                cue_semantic = [position[cue_only.ids[int(i)]] for i in numpy.argsort(-(cue_only.vectors @ vector))]
                for weight in (0.5, 1.0):
                    variants[f"4 cues as two extra routes, weight {weight}"] = rrf(
                        [lexical, semantic, cue_lexical, cue_semantic], [1, 1, weight, weight])
                variants["5 cues as an extra meaning route, weight 1.0"] = rrf([lexical, semantic, cue_semantic], [1, 1, 1])
            group = "one" if len(wanted) == 1 else "several"
            for name, order in variants.items():
                top = set(order[:cut])
                found = sum(item in top for item in wanted)
                stats[name][group].append((found == len(wanted), found / len(wanted)))
    lines = [f"{'variant (first ' + str(cut) + ' messages)':46}{'one: all':>10}{'several: all':>14}{'several: share':>16}"]
    for name in sorted(stats):
        one, several = stats[name]["one"], stats[name]["several"]
        lines.append(f"{name:46}{sum(a for a, _ in one) / len(one):>10.1%}"
                     f"{sum(a for a, _ in several) / len(several):>14.1%}{sum(s for _, s in several) / len(several):>16.1%}")
    lines.append(f"questions: one {len(stats['0 first pass']['one'])}, several {len(stats['0 first pass']['several'])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model-cache", required=True)
    parser.add_argument("--conversations", default="0,1,2")
    parser.add_argument("--ceiling", type=float, required=True)
    parser.add_argument("--no-calls", action="store_true", help="Use only cues already generated")
    args = parser.parse_args()
    from membrain.local_embeddings import LocalEmbeddingProvider, installed

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    selected = [int(index) for index in args.conversations.split(",")]
    out = Path(args.out)
    cues = {}
    if args.no_calls:
        for index in selected:
            cues[data[index]["sample_id"]] = json.loads(
                (out / f"cues-{data[index]['sample_id']}.json").read_text(encoding="utf-8"))["cues"]
    else:
        read_key()
        ledger = Ledger(out / "ledger.json", args.ceiling)
        ledger.phase = "cues"
        model = Model(ENDPOINT, CUE_MODEL, cap=500)
        model.http = httpx.Client(timeout=300, transport=MeteredTransport(ledger))
        for index in selected:
            cues[data[index]["sample_id"]] = generate(data[index], model, out)
            log("cues", data[index]["sample_id"], len(cues[data[index]["sample_id"]]), "turns with cues; spent",
                ledger.state["spent_cny"])
    provider = LocalEmbeddingProvider(installed(Path(args.model_cache)), threads=4)
    table = simulate(data, selected, cues, provider)
    (out / "cue-simulation.txt").write_text(table + "\n", encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
