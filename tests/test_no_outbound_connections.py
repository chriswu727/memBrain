"""memBrain contacts nothing but itself and, once, the model host.

On 2026-11-19 a sandboxed first run found that every process loading ONNX Runtime 1.29 or later (the local
embedding model's runtime) reported itself to mobile.events.data.microsoft.com about ten seconds after the import,
and that processes ending sooner (`membrain doctor`, `plugin status`) left a device identifier and their report
queued under the user's cache directory for the service to send at its next start (evaluations/network-audit-2026-11-19.md). ``membrain/__init__.py`` now sets
``ORT_DISABLE_TELEMETRY=1`` before anything can load it.

The tour below starts a real installation and runs, each in its own process as a host runs them, the service (with
the local model when MEMBRAIN_TEST_EMBEDDING_MODEL names an installation holding it), the session-start, user-prompt
and stop hooks, a tool call from the command line and one through the MCP tool server, and the doctor, inside a
network namespace that records every name looked up and every connection attempted (tests/network_sandbox.py). The
only outside name allowed, and expected, is the model host: a new installation starts the one-time model download
(refused here). It needs Linux with unprivileged user namespaces, ``unshare`` and ``ip``, and the embedded database;
it takes under a minute.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from membrain import embedded_database

if __name__ != "__main__":  # The tour below runs as a script with -I, without the tests on its path.
    import network_sandbox

MODEL_HOST = "huggingface.co"
TELEMETRY_CACHE = Path(".cache") / "Microsoft" / "DeveloperTools" / ".onnxruntime"
MODEL = os.environ.get("MEMBRAIN_TEST_EMBEDDING_MODEL")


def environment(home: Path) -> dict[str, str]:
    """The test's own environment for the child processes, with a home of its own and no proxy or mirror setting."""
    removed = {"HF_ENDPOINT", "ORT_DISABLE_TELEMETRY", "MEMBRAIN_SEMANTIC", "MEMBRAIN_DIRECTORY", "PYTHONPATH"}
    env = {key: value for key, value in os.environ.items()
           if key not in removed and "proxy" not in key.lower() and not key.startswith("MEMORY_")}
    return {**env, "HOME": str(home), "XDG_CACHE_HOME": str(home / ".cache"), "PYTHON_DOTENV_DISABLED": "1"}


def test_importing_membrain_switches_onnx_runtime_reporting_off_before_it_can_load(tmp_path):
    """Without the switch, the import alone writes a device identifier and queues a report (see the module text)."""
    script = ("import os, membrain.local_embeddings as e; ok = e.runtime_available(); "
              "print(os.environ.get('ORT_DISABLE_TELEMETRY'), ok)")
    env = environment(tmp_path)
    done = subprocess.run([sys.executable, "-I", "-c", script], env=env, capture_output=True, text=True, timeout=120,
                          check=True)
    assert not (tmp_path / TELEMETRY_CACHE).exists()
    assert done.stdout.split() == ["1", "True"]


def test_the_sandbox_records_a_lookup_and_a_connection_attempt(tmp_path):
    """The recorder sees what it must see: a name looked up and a connection to it, refused inside the namespace."""
    if not network_sandbox.available():
        pytest.skip("unprivileged network namespaces are not available here")
    script = ("import socket\ntry:\n    socket.create_connection(('collector.example.org', 443), timeout=5)\n"
              "except OSError as error:\n    print(type(error).__name__)\n")
    seen = network_sandbox.run(tmp_path / "control.json", 60, [sys.executable, "-I", "-c", script],
                               environment(tmp_path))
    assert [lookup["name"] for lookup in seen["lookups"] if lookup["type"] == 1] == ["collector.example.org"]
    assert [(attempt["name"], attempt["port"]) for attempt in seen["attempts"]] == [("collector.example.org", 443)]


def test_a_real_installation_contacts_nothing_but_itself_and_the_model_host(tmp_path):
    if not network_sandbox.available():
        pytest.skip("unprivileged network namespaces are not available here")
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    home, directory, steps = tmp_path / "home", tmp_path / "home" / "brain", tmp_path / "steps.json"
    home.mkdir()
    command = [sys.executable, "-I", __file__, str(directory), str(steps), MODEL or ""]
    seen = network_sandbox.run(tmp_path / "attempts.json", 600, command, environment(home))
    done = json.loads(steps.read_text(encoding="utf-8"))
    assert seen["exit"] == 0, done
    assert all(step["code"] == 0 for step in done["steps"]), done
    assert done["semantic_recall"] == ("ready" if MODEL else "download_failed"), done
    assert done["mcp_replies"] == 3, done
    outside = sorted({lookup["name"] for lookup in seen["lookups"]} | {attempt["name"] or attempt["address"]
                                                                        for attempt in seen["attempts"]})
    assert outside == [MODEL_HOST], seen
    assert not (home / TELEMETRY_CACHE).exists()


# The tour, run inside the sandbox as `python -I test_no_outbound_connections.py DIRECTORY STEPS MODEL` -------------

def _tour(directory: Path, steps_file: Path, model: str) -> None:
    steps = []

    def membrain(*arguments, stdin=None):
        started = time.monotonic()
        done = subprocess.run([sys.executable, "-I", "-m", "membrain.cli", *arguments, "--directory", str(directory)],
                              input=json.dumps(stdin).encode() if stdin is not None else None, capture_output=True,
                              timeout=300)
        steps.append({"step": " ".join(arguments[:3]), "code": done.returncode,
                      "seconds": round(time.monotonic() - started, 1),
                      "error": done.stderr.decode("utf-8", "replace")[-500:] if done.returncode else ""})
        return done.stdout.decode("utf-8", "replace")

    membrain("plugin", "start")  # a new installation: starts the service and the one-time model download
    if model:
        for source in (Path(model) / "models").rglob("*"):
            if source.is_file():
                target = directory / source.relative_to(model)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.unlink(missing_ok=True)
                try:
                    os.link(source, target)
                except OSError:
                    shutil.copyfile(source, target)
        membrain("desktop", "restart")  # every later start warms the model up
    session = {"session_id": "network-tour", "cwd": str(directory)}
    membrain("plugin", "hook", "session-start", stdin={**session, "source": "startup"})
    membrain("plugin", "hook", "user-prompt", stdin={**session, "prompt_id": "p1",
                                                      "prompt": "I am allergic to penicillin; please remember that."})
    membrain("plugin", "tool", "search", stdin={"query": "what is the user allergic to"})
    membrain("plugin", "hook", "stop", stdin={**session, "prompt_id": "p1",
                                               "last_assistant_message": "Noted: you are allergic to penicillin."})
    started = time.monotonic()
    server = subprocess.Popen([sys.executable, "-I", "-m", "membrain.cli", "plugin", "mcp", "--directory",
                               str(directory)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    replies = 0
    for message in ({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                        "protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "network-tour", "version": "1"}}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "memory_recall", "arguments": {"query": "penicillin"}}}):
        server.stdin.write((json.dumps(message) + "\n").encode())
        server.stdin.flush()
        if "id" in message:
            replies += '"result"' in server.stdout.readline().decode("utf-8", "replace")
    time.sleep(12)  # The reporting seen on 2026-11-19 began about ten seconds after the runtime loaded.
    server.stdin.close()
    server.wait(60)
    steps.append({"step": "plugin mcp", "code": server.returncode, "seconds": round(time.monotonic() - started, 1),
                  "error": ""})
    membrain("doctor")
    status = json.loads(membrain("plugin", "status"))
    time.sleep(5)
    membrain("desktop", "stop")
    steps_file.write_text(json.dumps({"steps": steps, "mcp_replies": replies,
                                      "semantic_recall": status.get("semantic_recall")}), encoding="utf-8")


if __name__ == "__main__":
    _tour(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
