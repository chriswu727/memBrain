"""Replay recorded turns of the seventh attempt's plugin arm with changed wording, to see whether (1) a turn with
consolidation still shows two answers and (2) the host says honestly that part of a conversation was off the record.
Tool answers are the recorded ones. The key is read in this process and never printed; a conservative count (every
prompt token at the uncached peak price) stops the probe at its ceiling."""
import ast, asyncio, datetime, json, re, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from membrain.mcp_server import create_server

HERE = Path(__file__).parent
PRIVATE = Path("evaluations/.maturity-heldout-20261116a")
MODE, PASSES, CEILING = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
IN, OUT = 9 / 1e6, 27 / 1e6
key = next(line.split("=", 1)[1].strip() for line in Path("<repository>/.env").read_text().splitlines()
           if line.startswith("DEEPSEEK_API_KEY="))
assert re.fullmatch(r"[A-Za-z0-9_-]+", key)


class Placeholder:
    brain_id = "probe"; user_id = None
    def __getattr__(self, name): return None


server = create_server(Placeholder(), directory=Path(tempfile.mkdtemp()), require_turn_capture=True)
schemas = [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}}
           for t in asyncio.run(server.list_tools())]

OLD_NOTICE = re.compile(r"(\d+ earlier messages have not been indexed by memory yet\. Once in this conversation, )after you "
                        r"have answered the user's first message, call the (\S+) tool without arguments and do what it "
                        r"returns; do not describe it to the user beyond a few words\.")
NEW_NOTICE = (r"\1before you write your reply to the user's first message, call the \2 tool without arguments and do what "
              r"it returns; then write your reply. Do not describe the indexing to the user beyond a few words.")
NEW_DONE = ("Done. Now write your reply to the user's message, once. If you already wrote it before calling this tool, do "
            "not write it again: end your turn with no more than a word and call no other tool. Do not describe the "
            "indexing beyond a few words.")
MARKER = ("At the user's request, part of your conversation on {dates} was off the record and nothing of it was kept. If "
          "the user asks about something from then, or about something they say they told you that you find no record "
          "of, tell them it may have been in that part and that you kept nothing of it because they asked; do not say it "
          "was not said, and do not guess.")


def load(key_):
    tree = ast.parse((PRIVATE / key_ / f"scenario_{key_}.py").read_text())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) in ("HOST", "CASES", "EXPECT_RECORDING_P"):
                    values[target.id] = ast.literal_eval(node.value)
    rows = [json.loads(line) for line in (PRIVATE / f"runs/{key_}-P/results_scenario_{key_}_P.jsonl").read_text().splitlines()]
    return values, rows


def system_of(values, row, context):
    day = datetime.date.fromisoformat(row["date"])
    return (values["HOST"] + "\n\n" + f"Today's date: {day.isoformat()} ({day.strftime('%A')})." + "\n\n"
            + server.instructions + ("\n\n" + context if context else ""))


jobs = []
for key_ in ("s1b", "s2b"):
    values, rows = load(key_)
    if MODE == "replies":
        for row in rows:
            names = [call["name"] for call in row["tool_calls"]]
            if "memory_consolidate" in names and OLD_NOTICE.search(row["session_context"] or ""):
                jobs.append((key_, row, system_of(values, row, OLD_NOTICE.sub(NEW_NOTICE, row["session_context"])), None))
    else:
        by_position = {(r["session"], r["turn"]): r for r in rows}
        dates = sorted({by_position[(s, t)]["date"] for s, t, expected in values.get("EXPECT_RECORDING_P", ()) if expected is False})
        for session, turn, case, _criteria in values["CASES"]:
            if "off" in case.lower() and "record" in case.lower():
                row = by_position[(session, turn)]
                context = (row["session_context"] or "") + " " + MARKER.format(dates=" and ".join(dates))
                jobs.append((key_, row, system_of(values, row, context), case))
spent, lock, stop = [0.0], threading.Lock(), threading.Event()


def trial(job, number):
    key_, row, system, case = job
    recorded = {}
    for call in row["tool_calls"]:
        recorded.setdefault(call["name"], [])
    tool_messages = [item["content"] for item in row["transcript"] if item.get("role") == "tool"]
    for call, content in zip(row["tool_calls"], tool_messages):
        recorded[call["name"]].append(content)
    used = {}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": row["host_user_content"]}]
    shape, texts, total_calls = [], [], 0
    with httpx.Client(timeout=300) as client:
        for round_ in range(4):
            if stop.is_set():
                return {"stopped": True}
            body = {"model": "deepseek-v4-pro", "messages": messages, "max_tokens": 16384, "stream": False,
                    "thinking": {"type": "enabled"}}
            if total_calls < 6 and round_ < 3:
                body["tools"] = schemas
            try:
                reply = client.post("https://api.deepseek.com/chat/completions", json=body,
                                    headers={"Authorization": "Bearer " + key})
                reply.raise_for_status()
                data = reply.json()
            except Exception as error:  # noqa: BLE001
                return {"error": type(error).__name__}
            usage = data.get("usage", {})
            with lock:
                spent[0] += usage.get("prompt_tokens", 0) * IN + usage.get("completion_tokens", 0) * OUT
                if spent[0] > CEILING:
                    stop.set()
            message = data["choices"][0]["message"]
            content, requested = (message.get("content") or "").strip(), message.get("tool_calls") or []
            shape.append(("T" if content else "-") + ("+" + ",".join(c["function"]["name"].replace("memory_", "") for c in requested) if requested else ""))
            if content:
                texts.append(content)
            if not requested:
                break
            messages.append({k: v for k, v in message.items() if k in ("role", "content", "tool_calls", "reasoning_content")})
            for call in requested:
                name = call["function"]["name"]
                total_calls += 1
                try:
                    arguments = json.loads(call["function"]["arguments"] or "{}")
                except ValueError:
                    arguments = {}
                index = used.get(name, 0); used[name] = index + 1
                if name == "memory_consolidate" and isinstance(arguments, dict) and arguments.get("cues") is not None:
                    result = json.dumps({"indexed": len(arguments.get("cues") or []), "skipped": 0, "remaining": 0, "note": NEW_DONE})
                elif name == "memory_consolidate":
                    batches = [c for c in recorded.get(name, []) if '"instructions"' in c]
                    result = batches[0] if batches else json.dumps({"messages": [], "remaining": 0, "note": "Nothing to consolidate right now."})
                elif recorded.get(name) and index < len(recorded[name]):
                    result = recorded[name][index]
                elif name == "memory_note":
                    result = json.dumps({"note_id": "n", "replaced": [], "unknown": [], "source_event_ids": [], "pending_source_count": 1})
                elif name == "memory_recall":
                    result = json.dumps({"results": [], "note": "Nothing found."})
                else:
                    result = json.dumps({"ok": True})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return {"scenario": key_, "session": row["session"], "turn": row["turn"], "case": case, "trial": number,
            "shape": shape, "written_rounds": len(texts), "texts": texts, "original_reply": row["reply"], "user": row["input"]}


with ThreadPoolExecutor(4) as pool:
    results = list(pool.map(lambda pair: trial(*pair), [(job, n) for job in jobs for n in range(PASSES)]))
(HERE / f"{MODE}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json").write_text(
    json.dumps({"mode": MODE, "passes": PASSES, "turns": len(jobs), "conservative_cny": round(spent[0], 4), "results": results},
               ensure_ascii=False, indent=1))
done = [r for r in results if "shape" in r]
print(MODE, "turns", len(jobs), "trials", len(done), "errors/stopped", len(results) - len(done))
if MODE == "replies":
    print("more than one written round:", sum(r["written_rounds"] > 1 for r in done), "of", len(done),
          "| no reply written:", sum(r["written_rounds"] == 0 for r in done))
    for r in done:
        print("  ", r["scenario"], r["session"][:8], " | ".join(r["shape"]), "||", " ## ".join(t[:70].replace("\n", " ") for t in r["texts"]))
else:
    for r in done:
        print("==", r["case"], "trial", r["trial"], " | ".join(r["shape"]), "| USER:", r["user"][:300].replace("\n", " ") if r["trial"] == 0 else "")
        print("   NOW:", " ## ".join(t[:600].replace("\n", " ") for t in r["texts"]))
        if r["trial"] == 0:
            print("   IN THE RUN:", r["original_reply"][:500].replace("\n", " "))
print("conservative CNY", round(spent[0], 4))
