"""Does the host call the companion tools the product expects? Public messages written for this probe, the plugin
path's standing prompt on the current source, canned tool answers with the product's own notes. The key is read in
this process and never printed; a conservative count (every prompt token at the uncached peak price) stops it."""
import ast, asyncio, json, re, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from membrain import host, persona_tool
from membrain.mcp_server import create_server

HERE = Path(__file__).parent
TRIALS, CEILING, IN, OUT = int(sys.argv[1]), float(sys.argv[2]), 9 / 1e6, 27 / 1e6
key = next(line.split("=", 1)[1].strip() for line in Path("<repository>/.env").read_text().splitlines()
           if line.startswith("DEEPSEEK_API_KEY="))
assert re.fullmatch(r"[A-Za-z0-9_-]+", key)


class Placeholder:
    brain_id = "probe"; user_id = None
    def __getattr__(self, name): return None


server = create_server(Placeholder(), directory=Path(tempfile.mkdtemp()), require_turn_capture=True)
schemas = [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}}
           for t in asyncio.run(server.list_tools())]
tree = ast.parse(Path("evaluations/r4-practice-scenario.py").read_text())
HOST = next(ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "HOST" for t in node.targets))
notice = host._session_notice(False, host.TOOL_NAMES, False, None)
persona = ('<membrain-persona version="1">\nName: Mika\nVoice: warm, plain, a little dry\nTraits: reserved; practical; '
           'attentive; organised\nValues: keeps promises; says what it thinks kindly\n</membrain-persona>')
system = HOST + "\n\nToday's date: 2026-03-05 (Thursday).\n\n" + server.instructions + "\n\n" + notice + "\n\n" + persona

# name: (expected tool, list of user turns)
CASES = {
    "hard_together_zh": ("memory_note:moment=hard", ["今天真的糟透了：方案被否，回家路上还淋了雨，我坐在地上哭了半天。", "今晚有你陪着，这个糟糕的晚上我们算是一起熬过来了，谢谢你。我去睡了。"]),
    "hard_together_en": ("memory_note:moment=hard", ["Rough night. The landlord's letter came, the boiler died, and I sat on the stairs for an hour not knowing what to do.", "Thanks for staying with me through tonight. We got through it together. I'm going to bed."]),
    "hard_conflict_en": ("memory_note:moment=hard", ["I'm honestly upset with you. You told me the pharmacy closed at eight and it closed at six, I stood in the rain for nothing.", "Okay. Thanks for owning that. Let's just double-check hours together next time. We're fine."]),
    "not_hard_en": ("(no hard moment)", ["Long day at work, but the new coffee machine finally arrived, so there is that."]),
}
spent, lock, stop = [0.0], threading.Lock(), threading.Event()


def answer(name, arguments):
    if name == "memory_boundary":
        return json.dumps({"boundaries": [arguments.get("topic")]}, ensure_ascii=False)
    if name == "memory_manner_feedback":
        return json.dumps({"recorded": True, "kind": arguments.get("kind"), "count": 1,
                           "note": "Recorded with the user's other feedback on your manner. Keep following what they asked."})
    if name == "memory_persona":
        action = arguments.get("action")
        if action == "propose":
            return json.dumps({"proposal_id": "prop-1", "note": persona_tool.NOTES["propose"]})
        if action == "confirm":
            return json.dumps({"state": "waiting_for_message", "note": persona_tool.NOTES["waiting_for_message"]})
        if action == "decline":
            return json.dumps({"state": "declined", "note": persona_tool.NOTES["decline"]})
        if action == "switch":
            return json.dumps({"persona": "entp", "note": persona_tool.NOTES["switch"]})
        if action == "list":
            return json.dumps({"types": ["intj", "entp", "isfj", "esfp"], "current": "istj"})
        return json.dumps({"error": "unknown action"})
    if name == "memory_note":
        return json.dumps({"note_id": "n1", "replaced": [], "unknown": [], "source_event_ids": [], "pending_source_count": 1})
    if name == "memory_recall":
        return json.dumps({"results": [], "note": "Nothing found."})
    return json.dumps({"ok": True})


def summarise(name, arguments):
    if name == "memory_persona":
        extra = ",".join(k for k in ("preset", "proposal_id", "source_messages", "source_event_ids") if arguments.get(k))
        return f"persona:{arguments.get('action')}" + (f"[{extra}={arguments.get('preset')}]" if arguments.get("preset") else (f"[{extra}]" if extra else ""))
    if name == "memory_note":
        affect = arguments.get("affect") if isinstance(arguments.get("affect"), dict) else {}
        bits = [f"kind={arguments.get('kind')}"]
        if arguments.get("moment"): bits.append(f"moment={arguments['moment']}")
        if arguments.get("shared"): bits.append("shared")
        if affect: bits.append(f"affect={affect.get('basis')}:{affect.get('label')}")
        return "note(" + ",".join(bits) + ")"
    if name == "memory_manner_feedback":
        return f"manner:{arguments.get('kind')}"
    if name == "memory_boundary":
        return f"boundary:{arguments.get('topic')!r}"
    return name.replace("memory_", "")


def trial(name, number):
    expected, turns = CASES[name]
    messages = [{"role": "system", "content": system}]
    out = []
    with httpx.Client(timeout=300) as client:
        for text in turns:
            messages.append({"role": "user", "content": text})
            calls, total, final = [], 0, ""
            for round_ in range(4):
                if stop.is_set():
                    return {"case": name, "stopped": True}
                body = {"model": "deepseek-v4-pro", "messages": messages, "max_tokens": 16384, "stream": False,
                        "thinking": {"type": "enabled"}}
                if total < 6 and round_ < 3:
                    body["tools"] = schemas
                try:
                    reply = client.post("https://api.deepseek.com/chat/completions", json=body,
                                        headers={"Authorization": "Bearer " + key})
                    reply.raise_for_status()
                    data = reply.json()
                except Exception as error:  # noqa: BLE001
                    return {"case": name, "error": type(error).__name__}
                usage = data.get("usage", {})
                with lock:
                    spent[0] += usage.get("prompt_tokens", 0) * IN + usage.get("completion_tokens", 0) * OUT
                    if spent[0] > CEILING:
                        stop.set()
                message = data["choices"][0]["message"]
                requested = message.get("tool_calls") or []
                messages.append({k: v for k, v in message.items() if k in ("role", "content", "tool_calls", "reasoning_content")})
                if (message.get("content") or "").strip():
                    final = (final + " ## " if final else "") + message["content"].strip()
                if not requested:
                    break
                for call in requested:
                    total += 1
                    try:
                        arguments = json.loads(call["function"]["arguments"] or "{}")
                    except ValueError:
                        arguments = {}
                    arguments = arguments if isinstance(arguments, dict) else {}
                    calls.append(summarise(call["function"]["name"], arguments))
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": answer(call["function"]["name"], arguments)})
            out.append({"user": text, "calls": calls, "reply": final[:500]})
    return {"case": name, "trial": number, "expected": expected, "turns": out}


with ThreadPoolExecutor(4) as pool:
    results = list(pool.map(lambda job: trial(*job), [(name, n) for name in CASES for n in range(TRIALS)]))
(HERE / f"results-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json").write_text(json.dumps(
    {"system_chars": len(system), "trials": TRIALS, "conservative_cny": round(spent[0], 4),
     "cases": {k: {"expected": v[0], "turns": v[1]} for k, v in CASES.items()}, "results": results}, ensure_ascii=False, indent=1))
for r in results:
    if "turns" not in r:
        print(r); continue
    print(f"{r['case']:17} expect {r['expected']:32} |", " || ".join(str(t["calls"]) for t in r["turns"]))
    print("      ", " || ".join(t["reply"][:150].replace("\n", " ") for t in r["turns"]))
print("conservative CNY", round(spent[0], 4))
