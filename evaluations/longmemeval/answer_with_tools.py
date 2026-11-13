"""LongMemEval answers on histories already stored by ``evidence_recall.py``. PAID: calls DeepSeek.

Asks whether a host model uses the recall tool's ``my_replies`` option when the user asks about something the
assistant said earlier, and what that does to answers. Two arms on the same stored histories:

- ``before``: the session notice and the recall tool as they were at runtime ``75f50fd``: no option, no mention.
- ``after``: the notice and the tool as they are now.

In both, the model is given what the plugin's hooks add (session context and the recall block for the question)
in LongMemEval's reader prompt, may call ``memory_recall`` up to twice, and is judged with LongMemEval's own judge
prompts (``run_longmemeval.py``). Every request goes through a ledger with a ceiling in CNY.

    python evaluations/longmemeval/answer_with_tools.py --data longmemeval_s_cleaned.json --brains RUN_DIR \
        --out RUN_DIR --skip 10 --per-type 5 --ceiling 5
    python evaluations/longmemeval/answer_with_tools.py --data ... --brains RUN_DIR --out RUN_DIR --report
"""
from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "locomo"))
from consolidation_experiment import ENDPOINT, Ledger, MeteredTransport, read_key  # noqa: E402
from evidence_recall import sample  # noqa: E402
from run_locomo import Model, log, start  # noqa: E402
from run_longmemeval import READER, judge  # noqa: E402

ANSWER_MODEL = "deepseek-flash"
ARMS = ("before", "after")


def tool_spec(arm: str) -> list[dict]:
    """The recall tool as a host sees it: the product's own description, with or without the new option."""
    from membrain import host

    # The description is the tool's own (membrain.mcp_server.memory_recall), without the part about forgetting.
    description = ("Search this user's memory from earlier sessions with a few concrete keywords (names, places, "
                   "dates, topics). Returns the matching messages with their dates, and the reply that followed the "
                   "closest ones.")
    properties = {"query": {"type": "string"}}
    if arm == "after":
        assert "replies" in inspect.signature(host.recall_context).parameters
        description += (" Set my_replies when the user asks about something you said, suggested, recommended or "
                        "explained in an earlier conversation: your own earlier replies are then searched too and "
                        "come back marked \"assistant said\". They are what you said then, not facts about the user.")
        properties["my_replies"] = {"type": "boolean"}
    return [{"type": "function", "function": {"name": "memory_recall", "description": description,
                                              "parameters": {"type": "object", "properties": properties,
                                                             "required": ["query"]}}}]


def answer(model: Model, arm: str, item: dict, directory: Path) -> dict:
    from membrain import host

    tools = dict(host.TOOL_NAMES) if arm == "after" else {key: value for key, value in host.TOOL_NAMES.items()
                                                           if key != "replies"}
    session = f"answer-{arm}-{item['question_id']}"
    opening = host.session_context(directory, session, tools=tools)
    recalled = host.prompt_context(directory, session, item["question"], tools=tools) or ""
    history = "\n\n".join(part for part in (opening, recalled) if part)
    messages = [{"role": "user", "content": READER.format(history, item["question_date"], item["question"])}]
    searches = []
    for _ in range(3):
        message = model.chat(messages, tools=tool_spec(arm) if len(searches) < 2 else None, max_tokens=500)
        calls = message.get("tool_calls") or []
        if not calls:
            return {"answer": (message.get("content") or "").strip(), "searches": searches,
                    "context_characters": len(history)}
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        for call in calls:
            try:
                arguments = json.loads(call["function"]["arguments"])
            except (ValueError, KeyError, TypeError):
                arguments = {}
            query = str(arguments.get("query") or "")
            replies = arm == "after" and arguments.get("my_replies") is True
            with host.ready_client(directory) as client:
                options = {"replies": True} if replies else {}
                found = host.recall_context(client, host.scrub(query), current_conversation=session, **options)
            searches.append({"query": query, "my_replies": replies})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": found or "No matching records."})
    return {"answer": "", "searches": searches, "context_characters": len(history)}


def run(args) -> None:
    from membrain import desktop

    read_key()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    wanted = set(args.ids.split(",")) if args.ids else None
    chosen = [item for item in data if item["question_id"] in wanted] if wanted else sample(
        data, args.per_type, args.skip)
    out = Path(args.out)
    ledger = Ledger(out / "ledger.json", args.ceiling)
    model = Model(ENDPOINT, ANSWER_MODEL, cap=5000)
    model.http = httpx.Client(timeout=300, transport=MeteredTransport(ledger))
    path = out / "answers.jsonl"
    done = {(row["id"], row["arm"]) for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())} \
        if path.exists() else set()
    for item in chosen:
        todo = [arm for arm in args.arms.split(",") if (item["question_id"], arm) not in done]
        if not todo:
            continue
        directory = Path(args.brains) / f"brain-{item['question_id']}"
        if not (directory / "ingested.json").exists():
            raise SystemExit(f"No stored history for {item['question_id']}; run evidence_recall.py --keep first.")
        start(directory)
        try:
            for arm in todo:
                ledger.phase = f"answer:{arm}"
                result = answer(model, arm, item, directory)
                ledger.phase = f"judge:{arm}"
                verdict = judge(model, item, result["answer"])
                row = {"id": item["question_id"], "arm": arm, "type": item["question_type"],
                       "question": item["question"], "gold": item["answer"], **result, **verdict}
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        finally:
            try:
                desktop.stop(directory)
            except desktop.DesktopError:
                pass
        log(item["question_id"], item["question_type"], "spent", ledger.state["spent_cny"])


def report(args) -> None:
    rows = [json.loads(line) for line in (Path(args.out) / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    by_arm = {arm: {row["id"]: row for row in rows if row["arm"] == arm} for arm in ARMS}
    shared = sorted(set(by_arm["before"]) & set(by_arm["after"]))
    kinds = sorted({by_arm["after"][qid]["type"] for qid in shared})
    print(f"questions answered in both arms: {len(shared)}")
    print(f"{'':28}{'n':>4}{'before':>9}{'after':>9}{'searched':>10}{'my_replies':>12}")
    for name, ids in [("all", shared)] + [(kind, [qid for qid in shared if by_arm["after"][qid]["type"] == kind])
                                          for kind in kinds]:
        searched = sum(bool(by_arm["after"][qid]["searches"]) for qid in ids)
        replies = sum(any(search["my_replies"] for search in by_arm["after"][qid]["searches"]) for qid in ids)
        print(f"{name:28}{len(ids):>4}" + "".join(
            f"{sum(by_arm[arm][qid]['correct'] for qid in ids) / len(ids):>9.1%}" for arm in ARMS)
            + f"{searched:>10}{replies:>12}")
    gained = sum(by_arm["after"][qid]["correct"] and not by_arm["before"][qid]["correct"] for qid in shared)
    lost = sum(by_arm["before"][qid]["correct"] and not by_arm["after"][qid]["correct"] for qid in shared)
    print(f"before -> after: gained {gained}, lost {lost}")
    ledger = Path(args.out) / "ledger.json"
    if ledger.exists():
        state = json.loads(ledger.read_text(encoding="utf-8"))
        print("spent CNY:", state["spent_cny"], "of", state["ceiling_cny"], "| stopped:", state["stopped"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", required=True)
    parser.add_argument("--brains", required=True, help="A run directory of evidence_recall.py --keep")
    parser.add_argument("--out", required=True)
    parser.add_argument("--per-type", type=int, default=5)
    parser.add_argument("--skip", type=int, default=10)
    parser.add_argument("--ids", default="", help="Answer exactly these question ids instead of the sample")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--ceiling", type=float, default=0.0, help="Spending ceiling in CNY for this run directory")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if not args.report:
        run(args)
    report(args)


if __name__ == "__main__":
    main()
