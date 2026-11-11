"""Full-context control for consolidation_experiment.py: the whole dated conversation in the prompt. PAID.

Same answer model, judge, settings and ledger as the other arms; answers go to ``answers-full.jsonl`` in the same run
directory. Run it only when no other process is writing that directory's ledger.

    python evaluations/locomo/full_context_control.py --data locomo10.json --out RUN_DIR --conversations 0,1,2 --ceiling 85
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from consolidation_experiment import ANSWER_MODEL, ENDPOINT, Ledger, MeteredTransport, read_key  # noqa: E402
from retrieval_recall import evidence_ids, stored_turns  # noqa: E402
from run_locomo import Model, answer, full_transcript, judge, log, questions  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--conversations", default="0,1,2")
    parser.add_argument("--ceiling", type=float, required=True)
    parser.add_argument("--max-questions", type=int, default=0, help="Per conversation; 0 means all")
    args = parser.parse_args()
    read_key()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    out = Path(args.out)
    ledger = Ledger(out / "ledger.json", args.ceiling)
    ledger.phase = "answer:full"
    model = Model(ENDPOINT, ANSWER_MODEL, cap=100000)
    model.http = httpx.Client(timeout=300, transport=MeteredTransport(ledger))
    path = out / "answers-full.jsonl"
    done = {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
    for index in map(int, args.conversations.split(",")):
        sample = data[index]
        turns = stored_turns(sample)
        todo = [(qid, qa) for qid, qa in questions(sample, {1, 2, 3, 4}) if qid not in done]
        if args.max_questions:
            todo = todo[:args.max_questions]
        size = len(full_transcript(sample))
        for qid, qa in todo:
            started = time.monotonic()
            result = answer(model, "F", sample, out, qid, qa["question"])
            verdict = judge(model, qa["question"], qa["answer"], result["answer"])
            row = {"id": qid, "arm": "full", "category": qa["category"], "evidence": len(evidence_ids(qa, turns)),
                   "question": qa["question"], "gold": qa["answer"], **result, **verdict,
                   "context_characters": size, "searches": [], "seconds": round(time.monotonic() - started, 2)}
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        log("answered full", sample["sample_id"], len(todo), "spent", ledger.state["spent_cny"])


if __name__ == "__main__":
    main()
