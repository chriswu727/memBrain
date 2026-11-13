"""How much of the evidence reply does the recall tool show, at different lengths for asked-for replies? No model.

    python evaluations/longmemeval/reply_length_sweep.py OUT.jsonl RUN_DIR[,RUN_DIR...] DATA.json

RUN_DIR holds histories stored by ``evidence_recall.py --keep``; where ``answer_with_tools.py`` ran in RUN_DIR/answers,
the search the answer model made is asked as well as the question. ``share`` is the part of the evidence reply's
text that the tool's result shows.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "locomo"))
from evidence_recall import pieces, turns_of  # noqa: E402
from run_locomo import start  # noqa: E402

VARIANTS = {"700": (700, 0), "3000x1": (3000, 1), "3000x2": (3000, 2), "3000x3": (3000, 3), "2000x3": (2000, 3),
            "4000x2": (4000, 2), "2000x2": (2000, 2)}


def share(context: str, text: str) -> float:
    flat = " ".join(context.split())
    parts = pieces(text)
    return sum(1 for part in parts if part and part in flat) / len(parts)


def main():
    from membrain import desktop, host

    out = Path(sys.argv[1])
    data = {item["question_id"]: item for item in json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))}
    done = {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    queries = {}
    for run in sys.argv[2].split(","):
        answers = Path(run) / "answers" / "answers.jsonl"
        if answers.exists():
            for row in map(json.loads, answers.read_text().splitlines()):
                if row["arm"] == "after":
                    queries[row["id"]] = [search["query"] for search in row["searches"] if search["my_replies"]]
    for run in sys.argv[2].split(","):
        for directory in sorted(Path(run).glob("brain-*")):
            qid = directory.name[6:]
            item = data[qid]
            if item["question_type"] != "single-session-assistant" or qid in done or not (directory / "ingested.json").exists():
                continue
            evidence = [turn for turn in turns_of(item) if turn["evidence"] and turn["role"] == "assistant"]
            if not evidence:
                continue
            row = {"id": qid, "evidence_characters": [len(" ".join(turn["text"].split())) for turn in evidence], "asked": {}}
            start(directory)
            try:
                with host.ready_client(directory) as client:
                    for kind, query in [("question", item["question"])] + [("model", text) for text in queries.get(qid, [])[:1]]:
                        found = {}
                        for name, (size, count) in VARIANTS.items():
                            host.REPLY_CHARACTERS, host.REPLIES_AT_LENGTH = size, count
                            text = host.recall_context(client, host.scrub(query), current_conversation="sweep", replies=True) or ""
                            found[name] = {"share": [round(share(text, turn["text"]), 3) for turn in evidence],
                                           "characters": len(text), "lines": text.count("\n- [")}
                        row["asked"][kind] = found
            finally:
                try:
                    desktop.stop(directory)
                except desktop.DesktopError:
                    pass
            with out.open("a") as stream:
                stream.write(json.dumps(row) + "\n")
            print(qid, row["evidence_characters"], {k: v["3000x2"]["share"] for k, v in row["asked"].items()}, flush=True)


if __name__ == "__main__":
    main()
