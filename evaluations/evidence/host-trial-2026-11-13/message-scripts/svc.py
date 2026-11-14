"""svc.py start|stop|status <brain>...: start (host.start, as the plugin's start hook does) or stop trial services."""
import json
import sys
from pathlib import Path

from membrain import desktop, host

T = Path("$TRIAL")
action = sys.argv[1]
for name in sys.argv[2:]:
    directory = T / name
    if action == "start":
        result = host.start(directory)
        print(name, "started", {k: result.get(k) for k in ("state", "ready", "semantic_recall", "spool_replayed")})
    elif action == "stop":
        print(name, "stop", desktop.stop(directory))
    else:
        print(name, json.dumps(desktop.status(directory))[:300])
