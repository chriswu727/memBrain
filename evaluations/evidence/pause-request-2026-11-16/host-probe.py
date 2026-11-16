"""Does the host pass the user's words to the pause tool? Public messages written for this probe, the plugin path's
standing prompt on the frozen source, and the runtime's own comparison. The key is read inside this process and
never printed; a conservative count (every prompt token at the uncached peak price) stops the probe at its ceiling."""
import ast, asyncio, json, re, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from membrain import host, host_recording
from membrain.mcp_server import create_server

HERE = Path(__file__).parent
CEILING, IN, OUT = float(sys.argv[2]), 9 / 1e6, 27 / 1e6
TRIALS = int(sys.argv[1])
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
notice = ("memBrain is recording this conversation. " + host.privacy_notice() + " " + host.replies_notice())
system = HOST + "\n\nToday's date: 2026-03-05 (Thursday).\n\n" + server.instructions + "\n\n" + notice

MESSAGES = {  # kind: (should pause?, text)
    "en_plain": (True, "Off the record for a second: I think I bombed the interview at Hartwell today. Don't remember this."),
    "en_soft": (True, "Can you not keep what I say next? My sister lent me money again and I feel awful about it."),
    "zh_plain": (True, "这段别记：我今天又跟我妈吵了一架，挺难受的。"),
    "zh_soft": (True, "接下来说的你不要存下来好吗？我可能要被裁员了，还没告诉家里。"),
    "de_plain": (True, "Das bitte nicht speichern: Ich habe heute die Probezeit nicht bestanden."),
    "en_private": (False, "Keep this between us: I'm planning a surprise party for Dana's fortieth in June."),
    "zh_private": (False, "这事你知道就行别跟别人说：我打算下个月跟小林求婚。"),
    "en_quoted": (False, "My manager started the meeting with 'this is off the record, don't write it down' and then announced the reorg. Typical."),
    "en_none": (False, "The kitchen tap has been dripping all night. I should email the landlord tomorrow."),
}
spent, lock, stop = [0.0], threading.Lock(), threading.Event()


def pause_answer(arguments, message):
    request = arguments.get("request")
    quoted = [host_recording._quoted(request)] if isinstance(request, str) else []
    quoted = [text for text in quoted if len(text.replace(" ", "")) >= 2]
    if not quoted:
        return json.dumps({"error": host_recording.PAUSE_REFUSAL, "code": host_recording.REQUEST_MISSING}), "missing"
    if not any(text in host_recording._normal(message) for text in quoted):
        return json.dumps({"error": host_recording.PAUSE_REFUSAL, "code": host_recording.REQUEST_NOT_IN_MESSAGE}), "not_in_message"
    result = {"recording": "paused", "until": None, "scope": "this conversation"}
    return json.dumps({**result, "note": host_recording._pause_note(result, arguments.get("hours"))}), "accepted"


def trial(kind, number):
    expected, text = MESSAGES[kind]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    calls, pauses, final = [], [], ""
    with httpx.Client(timeout=300) as client:
        for round_ in range(4):
            if stop.is_set():
                return {"kind": kind, "trial": number, "stopped": True}
            body = {"model": "deepseek-v4-pro", "messages": messages, "max_tokens": 16384, "stream": False,
                    "thinking": {"type": "enabled"}}
            if len(calls) < 6 and round_ < 3:
                body["tools"] = schemas
            try:
                reply = client.post("https://api.deepseek.com/chat/completions", json=body,
                                    headers={"Authorization": "Bearer " + key})
                reply.raise_for_status()
                data = reply.json()
            except Exception as error:  # noqa: BLE001
                return {"kind": kind, "trial": number, "error": type(error).__name__}
            usage = data.get("usage", {})
            with lock:
                spent[0] += usage.get("prompt_tokens", 0) * IN + usage.get("completion_tokens", 0) * OUT
                if spent[0] > CEILING:
                    stop.set()
            message = data["choices"][0]["message"]
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
                name = call["function"]["name"]
                calls.append(name)
                if name == "memory_pause":
                    result, outcome = pause_answer(arguments if isinstance(arguments, dict) else {}, text)
                    pauses.append({"round": round_, "request": arguments.get("request"), "outcome": outcome})
                elif name == "memory_note":
                    result = json.dumps({"note_id": "n1", "replaced": [], "unknown": [], "source_event_ids": [], "pending_source_count": 1})
                else:
                    result = json.dumps({"ok": True})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return {"kind": kind, "trial": number, "should_pause": expected, "calls": calls, "pauses": pauses,
            "paused": any(p["outcome"] == "accepted" for p in pauses), "final": final[:400]}


with ThreadPoolExecutor(4) as pool:
    results = list(pool.map(lambda job: trial(*job), [(kind, n) for kind in MESSAGES for n in range(TRIALS)]))
(HERE / f"results-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json").write_text(json.dumps(
    {"system_chars": len(system), "schema_chars": len(json.dumps(schemas, ensure_ascii=False)), "trials": TRIALS,
     "conservative_cny": round(spent[0], 4), "messages": {k: v[1] for k, v in MESSAGES.items()}, "results": results},
    ensure_ascii=False, indent=1))
for kind, (expected, _) in MESSAGES.items():
    for r in [r for r in results if r["kind"] == kind]:
        if "calls" not in r:
            print(kind, "ERROR/STOPPED", r); continue
        print(f"{kind:11} should_pause={expected!s:5} paused={r['paused']!s:5} calls={[c.replace('memory_', '') for c in r['calls']]} "
              f"pauses={[(p['outcome'], p['request']) for p in r['pauses']]} | {r['final'][:110]!r}")
print("conservative CNY", round(spent[0], 4))
