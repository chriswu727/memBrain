"""state.py <brain> [label]: persona (version, type, card), proposals, relationship, mood, notes; appended to
<brain>-state.jsonl and printed."""
import json
import sys
import time
from pathlib import Path

from membrain import host
from membrain.notes import list_notes

T = Path("$TRIAL")
name = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else ""
client = host.ready_client(T / name)
if client is None:
    sys.exit("service not ready")
with client:
    def safe(fn):
        try:
            return fn()
        except Exception as error:
            return {"error": f"{type(error).__name__}: {error}"}
    persona = safe(client.persona)
    state = {
        "label": label, "at": time.strftime("%H:%M:%S"),
        "persona": persona,
        "versions": safe(client.persona_versions),
        "proposals": safe(client.persona_proposals),
        "relationship": safe(client.relationship),
        "mood": safe(client.mood),
        "notes": [{k: item.get(k) for k in ("event_id", "text", "role", "metadata", "recorded_at") if k in item}
                  for item in (safe(lambda: list_notes(client)).get("items") or [])],
    }
with open(T / f"{name}-state.jsonl", "a") as stream:
    stream.write(json.dumps(state, ensure_ascii=False) + "\n")
print(json.dumps(state, ensure_ascii=False, indent=1)[:int(sys.argv[3]) if len(sys.argv) > 3 else 6000])
