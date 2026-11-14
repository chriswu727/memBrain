"""Start the plugin's MCP server as Claude Code does (stdio) and print the instructions in its initialize result."""
import json
import os
import subprocess
import sys

R = "$ROUND2"
env = {**os.environ, "MEMBRAIN_DIRECTORY": f"{R}/{sys.argv[1]}"}
p = subprocess.Popen([f"{R}/venv/bin/python", "-m", "membrain.cli", "plugin", "mcp"], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, text=True)
p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "trial", "version": "0"}}}) + "\n")
p.stdin.flush()
line = p.stdout.readline()
p.kill()
print(json.dumps(json.loads(line)["result"].get("instructions"), ensure_ascii=False))
