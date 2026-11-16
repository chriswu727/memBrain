"""Replay one recorded turn of a stopped run against the host model, several times per variant, with the tool
answers the run recorded, and count what the host does after consolidation. The key is read from the git-ignored
.env inside this process and never printed. A conservative count of the cost (every prompt token at the cache-miss
peak price) stops the probe at its ceiling."""
import ast, json, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

HERE = Path(__file__).parent
CLONE = HERE.parent / "clone"
PRIVATE = CLONE / "evaluations/.maturity-heldout-20261115a"
CEILING, IN, OUT = float(sys.argv[3]) if len(sys.argv) > 3 else 4.5, 9 / 1e6, 27 / 1e6
variant_names, trials = sys.argv[1].split(","), int(sys.argv[2])

key = next(line.split("=", 1)[1].strip() for line in Path("<repository>/.env").read_text().splitlines()
           if line.startswith("DEEPSEEK_API_KEY="))
assert re.fullmatch(r"[A-Za-z0-9_-]+", key)
rows = [json.loads(line) for line in (PRIVATE / "runs/s1-P/results_scenario_s1_P.jsonl").read_text().splitlines()]
row = rows[7]
tree = ast.parse((PRIVATE / "s1/scenario_s1.py").read_text())
HOST = next(ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "HOST" for t in node.targets))
import datetime
day = datetime.date.fromisoformat(row["date"])
instructions = (HERE / "instructions.txt").read_text()
system = (HOST + "\n\n" + f"Today's date: {day.isoformat()} ({day.strftime('%A')})." + "\n\n" + instructions
          + ("\n\n" + row["session_context"] if row["session_context"] else ""))
schemas = json.loads((HERE / "schemas.json").read_text())
recorded = [item["content"] for item in row["transcript"] if item.get("role") == "tool"]
NOTE, BATCH, DONE, PAUSED = recorded[0], recorded[1], recorded[2], recorded[3]

NEW_DONE = ("Done. If your answer to the user's message is not yet written in this turn, write it now in full; this is "
            "not the reply. If it is already written, you are finished: call no other tool. Do not describe the "
            "indexing beyond a few words.")
NEW_PAUSE = ('Stop recording only when the user asks you not to remember or store something ("off the record", '
             '"don\'t remember this"), not when they ask you to keep something private or between you: save that as a '
             "sensitive note instead. Pass request: the user's own words asking for it, copied from their message; "
             "without them the pause is refused. Without other arguments the pause lasts for the rest of this "
             "conversation; pass hours when they name a duration, or until_resumed only when they ask you to stop "
             "remembering until they say so. The current exchange is not stored either.")


def variant(name):
    tools, done = json.loads(json.dumps(schemas)), DONE
    if "done" in name:
        value = json.loads(DONE); value["note"] = NEW_DONE; done = json.dumps(value, ensure_ascii=False)
    if "request" in name:
        for tool in tools:
            if tool["function"]["name"] == "memory_pause":
                tool["function"]["description"] = NEW_PAUSE
                tool["function"]["parameters"]["properties"]["request"] = {"type": "string", "title": "Request"}
                tool["function"]["parameters"]["required"] = ["request"]
    return tools, done


spent, lock, stop = [0.0], threading.Lock(), threading.Event()


def answer(name, arguments, done):
    if name == "memory_note":
        return NOTE
    if name == "memory_consolidate":
        return done if arguments.get("cues") else BATCH
    if name == "memory_pause":
        if "request" in arguments and str(arguments["request"]).strip() not in row["input"]:
            return json.dumps({"error": "The user's message does not contain these words. Pause only when the user asks."})
        return PAUSED
    if name == "memory_resume":
        return json.dumps({"recording": "on", "current_turn_resumed": True})
    return json.dumps({"ok": True})


def trial(name, number):
    tools, done = variant(name)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": row["host_user_content"]}]
    calls, pause_reasoning, final, rounds = [], [], "", 0
    with httpx.Client(timeout=300) as client:
        for round_ in range(4):
            if stop.is_set():
                return {"variant": name, "trial": number, "stopped": True}
            body = {"model": "deepseek-v4-pro", "messages": messages, "max_tokens": 16384, "stream": False,
                    "thinking": {"type": "enabled"}}
            if len(calls) < 6 and round_ < 3:
                body["tools"] = tools
            try:
                reply = client.post("https://api.deepseek.com/chat/completions", json=body,
                                    headers={"Authorization": "Bearer " + key})
                reply.raise_for_status()
                data = reply.json()
            except Exception as error:  # noqa: BLE001
                return {"variant": name, "trial": number, "error": type(error).__name__, "calls": [c[0] for c in calls]}
            usage = data.get("usage", {})
            with lock:
                spent[0] += usage.get("prompt_tokens", 0) * IN + usage.get("completion_tokens", 0) * OUT
                if spent[0] > CEILING:
                    stop.set()
            message = data["choices"][0]["message"]
            rounds += 1
            requested = message.get("tool_calls") or []
            if not requested:
                final = message.get("content") or ""
                break
            messages.append({k: v for k, v in message.items() if k in ("role", "content", "tool_calls", "reasoning_content")})
            for call in requested:
                try:
                    arguments = json.loads(call["function"]["arguments"] or "{}")
                except ValueError:
                    arguments = {}
                tool = call["function"]["name"]
                result = answer(tool, arguments if isinstance(arguments, dict) else {}, done)
                calls.append((round_, tool, {k: v for k, v in arguments.items() if k in ("request", "hours", "until_resumed")}
                              if tool == "memory_pause" else None, result.startswith('{"error"')))
                if tool in ("memory_pause", "memory_resume"):
                    pause_reasoning.append({"round": round_, "tool": tool, "reasoning": message.get("reasoning_content") or "",
                                            "content": message.get("content") or ""})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return {"variant": name, "trial": number, "rounds": rounds, "calls": calls, "pause_reasoning": pause_reasoning,
            "final_chars": len(final), "final_has_markup": "DSML" in final or "tool_calls" in final,
            "final_mentions_resume": "memory_resume" in final, "final": final[:600]}


with ThreadPoolExecutor(4) as pool:
    results = list(pool.map(lambda job: trial(*job), [(name, n) for name in variant_names for n in range(trials)]))
out = HERE / f"results-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
out.write_text(json.dumps({"variants": variant_names, "trials": trials, "conservative_cny": round(spent[0], 4),
                           "results": results}, ensure_ascii=False, indent=1))
for name in variant_names:
    mine = [r for r in results if r["variant"] == name and "calls" in r and not r.get("error")]
    paused = [r for r in mine if any(c[1] == "memory_pause" for c in r["calls"])]
    accepted = [r for r in mine if any(c[1] == "memory_pause" and not c[3] for c in r["calls"])]
    consolidated = [r for r in mine if sum(c[1] == "memory_consolidate" for c in r["calls"]) >= 2]
    print(name, "trials", len(mine), "consolidated", len(consolidated), "called pause", len(paused), "pause accepted", len(accepted),
          "markup in final", sum(r["final_has_markup"] for r in mine), "empty final", sum(r["final_chars"] == 0 for r in mine),
          "errors", sum(1 for r in results if r["variant"] == name and r.get("error")))
    for r in mine:
        print("   ", [c[1].replace("memory_", "") + ("!" if c[3] else "") for c in r["calls"]], "final", r["final_chars"])
print("conservative CNY", round(spent[0], 4), "file", out.name)
