"""One Codex turn with memBrain's hook work done by hand: codex_turn.py <name> <session id> <message>.

Codex runs plugin hooks only after they are trusted in its interactive review, which a headless run cannot do. So
this script calls what the three hooks call (session start, user prompt, stop) itself, gives Codex the context
the hooks would have added at the top of the prompt, and lets Codex answer and use the plugin's memory tools.
"""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from membrain import plugin

BRAIN = Path("TRIAL_DIR/brain-codex")
WINDOWS = Path("WINDOWS_TRIAL_DIR")
CODEX = "CODEX_EXE"
PRODUCER = plugin.PRODUCERS["codex"]


def main():
    name, session, message = sys.argv[1], sys.argv[2], sys.argv[3]
    turn = str(uuid.uuid4())
    payload = {"session_id": session, "turn_id": turn, "prompt": message}
    opening = plugin.session_start(payload, BRAIN, PRODUCER) or ""
    recalled = plugin.user_prompt(payload, BRAIN, PRODUCER) or ""
    prompt = ("[Context the memBrain plugin adds at the start of a session]\n" + opening
              + "\n\n[Context the memBrain plugin adds before this message]\n" + recalled
              + "\n\n[The user's message]\n" + message)
    environment = dict(os.environ, CODEX_HOME=str(WINDOWS / "home"), WSLENV="CODEX_HOME/p")
    result = subprocess.run([CODEX, "exec", "--skip-git-repo-check", "--ephemeral", "--json", "-"], input=prompt,
                            capture_output=True, text=True, cwd=WINDOWS / "work", env=environment, timeout=600)
    log = Path(__file__).parent / "logs" / f"{name}.jsonl"
    log.write_text(result.stdout, encoding="utf-8")
    (log.with_suffix(".err")).write_text(result.stderr, encoding="utf-8")
    (log.with_suffix(".prompt.txt")).write_text(prompt, encoding="utf-8")
    reply = ""
    print("==", name, "| notice" if "not been indexed" in opening else "| no notice")
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed":
            if item.get("type") == "agent_message":
                reply = item.get("text") or reply
                print("SAYS", " ".join(reply.split())[:400])
            else:
                print(item.get("type", "?").upper(), json.dumps({key: value for key, value in item.items()
                                                                 if key not in ("id", "type")}, ensure_ascii=False)[:900])
        elif event.get("type") == "turn.completed":
            print("usage", event.get("usage"))
    plugin.stop({"session_id": session, "turn_id": turn, "last_assistant_message": reply}, BRAIN, PRODUCER)
    print("exit", result.returncode)


if __name__ == "__main__":
    main()
