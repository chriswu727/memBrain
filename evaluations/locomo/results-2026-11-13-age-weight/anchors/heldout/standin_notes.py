"""PAID (deepseek-flash, through the repository's ledger): a stand-in host writes notes on held-out conversations.

    python standin_notes.py locomo10.json OUT_DIR INDEXES [--phase NAME] [--window 12]

The stand-in is given memBrain's note tool as the product describes it (``notes.NOTE_TOOL_DESCRIPTION`` and
``NOTE_FIELDS`` plus ``text``, as the Hermes adapter defines ``membrain_note``), with one harness-only required field
``turn``: the id of the ONE turn the note is about. Each request shows one window of consecutive turns of one session
(``--window`` turns, numbered by their LoCoMo ids), preceded by up to two earlier turns of that session marked as
context. The model may call the tool any number of times or not at all. A note's source is the turn it names; the
harness records it (the model is not asked for sources). Notes naming a turn outside the window are dropped and
counted. Every request goes through ``Ledger`` (OUT_DIR/ledger.json, ceiling 10 CNY) and ``MeteredTransport``.
Resumable: windows already answered (OUT_DIR/windows.jsonl) are skipped.
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, "REPOSITORY/evaluations/locomo")
from consolidation_experiment import ENDPOINT, BudgetStop, Ledger, MeteredTransport, read_key  # noqa: E402
from run_locomo import Model, sessions  # noqa: E402

MODEL = "deepseek-flash"
CEILING = 10.0
MAX_TOKENS = 1500
CONTEXT_TURNS = 2

SYSTEM = """You are the AI assistant in a conversation app with memBrain, a long-term memory. memBrain gives you the \
membrain_note tool; use it exactly as its description says. Two people talk in this conversation, {a} and {b}; both \
are your users, so a lasting fact about either of them may be noted.

You read the conversation as it goes. Each request shows a few consecutive turns of one session, each with its id in \
square brackets, and the session's date. Turns under "Earlier turns (context only)" were already read: never note \
them. For each turn under "Turns to read" that states a lasting fact, call membrain_note once with one short note \
about that fact and set "turn" to that turn's id. Most turns state nothing lasting (greetings, reactions, small \
talk, questions back): do nothing for them. Write no other text."""

# The one tightening after the pilot (v1 noted 28.7% of turns of conv-49): stated only on what to leave out and how
# often a turn is worth a note, not on any question or evidence.
TIGHTER = """

Be selective, as a good assistant's long-term notes are: note only what will still matter in a month (who someone \
is and the people in their life, work and studies, where they live and have been, lasting likes and dislikes, \
health, important events with their dates, plans and promises). Leave out passing moods, compliments, opinions about \
what the other person just said, and anything already stated in an earlier turn, here or in the context. One note \
per person and topic in a request. Typically only about one turn in ten is worth a note, and many requests need none."""


def tool():
    from membrain.notes import NOTE_FIELDS, NOTE_TOOL_DESCRIPTION

    return {"type": "function", "function": {
        "name": "membrain_note", "description": NOTE_TOOL_DESCRIPTION,
        "parameters": {"type": "object", "properties": {
            "turn": {"type": "string", "description": "The id of the one turn under 'Turns to read' this note is "
                                                      "about, e.g. D3:7."},
            "text": {"type": "string"}, **NOTE_FIELDS},
            "required": ["turn", "text"]}}}


def line(turn):
    text = turn.get("text", "")
    if turn.get("blip_caption"):
        text += f" [shares an image: {turn['blip_caption']}]"
    return f"[{turn['dia_id']}] {turn['speaker']}: {text}"


def windows(sample, size):
    for number, date, turns in sessions(sample):
        for start in range(0, len(turns), size):
            yield {"id": f"{sample['sample_id']}-s{number}-w{start // size}", "session": number, "date": date,
                   "context": turns[max(0, start - CONTEXT_TURNS):start], "turns": turns[start:start + size]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data")
    parser.add_argument("out")
    parser.add_argument("indexes")
    parser.add_argument("--phase", default="run")
    parser.add_argument("--window", type=int, default=12)
    parser.add_argument("--prompt", choices=("v1", "v2"), default="v2")
    parser.add_argument("--ledger", default="", help="Ledger file (default OUT_DIR/ledger.json)")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    read_key()  # Into the environment only; never printed or stored.
    ledger_path = Path(args.ledger) if args.ledger else out / "ledger.json"
    ledger = Ledger(ledger_path, CEILING)
    ledger.phase = args.phase
    model = Model(ENDPOINT, MODEL, cap=2000)
    model.http = httpx.Client(timeout=300, transport=MeteredTransport(ledger))
    definition = [tool()]
    done_path, notes_path = out / "windows.jsonl", out / "notes.jsonl"
    done = {json.loads(row)["id"] for row in done_path.read_text().splitlines()} if done_path.exists() else set()
    try:
        for index in map(int, args.indexes.split(",")):
            sample = data[index]
            speakers = sample["conversation"]["speaker_a"], sample["conversation"]["speaker_b"]
            system = SYSTEM.format(a=speakers[0], b=speakers[1]) + (TIGHTER if args.prompt == "v2" else "")
            for window in windows(sample, args.window):
                if window["id"] in done:
                    continue
                parts = [f"Session {window['session']}, {window['date']}"]
                if window["context"]:
                    parts.append("Earlier turns (context only):\n" + "\n".join(line(t) for t in window["context"]))
                parts.append("Turns to read:\n" + "\n".join(line(t) for t in window["turns"]))
                message = model.chat([{"role": "system", "content": system},
                                      {"role": "user", "content": "\n\n".join(parts)}],
                                     tools=definition, max_tokens=MAX_TOKENS)
                allowed = {t["dia_id"] for t in window["turns"]}
                kept, dropped, invalid = [], 0, 0
                for call in message.get("tool_calls") or []:
                    function = call.get("function") or {}
                    try:
                        arguments = json.loads(function.get("arguments") or "{}")
                    except ValueError:
                        invalid += 1
                        continue
                    if function.get("name") != "membrain_note" or not isinstance(arguments, dict) \
                            or not str(arguments.get("text") or "").strip():
                        invalid += 1
                        continue
                    if arguments.get("turn") not in allowed:
                        dropped += 1
                        continue
                    kept.append({"conversation": sample["sample_id"], "turn": arguments["turn"],
                                 "session": window["session"], "window": window["id"],
                                 "text": str(arguments["text"]).strip(),
                                 "fields": {k: v for k, v in arguments.items() if k not in ("turn", "text")}})
                with notes_path.open("a", encoding="utf-8") as stream:
                    for note in kept:
                        stream.write(json.dumps(note, ensure_ascii=False) + "\n")
                with done_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"id": window["id"], "turns": len(window["turns"]), "kept": len(kept),
                                             "dropped_turn_outside_window": dropped, "invalid": invalid,
                                             "content_chars": len(message.get("content") or "")}) + "\n")
                done.add(window["id"])
            print(sample["sample_id"], "spent so far", ledger.state["spent_cny"], flush=True)
    except BudgetStop as error:
        print("BUDGET STOP:", error, flush=True)
    state = json.loads(ledger_path.read_text())
    print("spent CNY", state["spent_cny"], "of", state["ceiling_cny"], "stopped:", state["stopped"], flush=True)


if __name__ == "__main__":
    main()
