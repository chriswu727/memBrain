from __future__ import annotations

import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path

import httpx

from .client import MemoryClient

# The longest request a client of the local service makes is one memory action. The service bounds each action's
# transaction to its wall-time budget, at most 30 seconds (``recall_deadline``, the statement and lock timeouts in
# ``MemoryService._respond``); a query embedding computed before it can first wait for the local model to load.
# 120 seconds covers both. (It was 615 for jobs of the removed cognition model, whose frozen policy allowed 600.)
_RPC_TIMEOUT = httpx.Timeout(30, connect=5, read=120, pool=5)


def mcp_config(directory: Path | None = None) -> dict:
    from .local_profile import load_profile

    profile = load_profile(directory)
    return {
        "mcpServers": {
            "membrain": {
                "command": str(Path(sys.executable).absolute()),
                "args": [
                    "-m", "membrain.cli", "desktop", "mcp",
                    "--directory", str(profile.directory.resolve()),
                ],
            },
        },
    }


def open_client(directory: Path | None = None, *, start_service: bool = True,
                timeout: float | httpx.Timeout = _RPC_TIMEOUT) -> MemoryClient:
    from .local_profile import load_profile
    from .recovery_profile import check_start_allowed, load_binding

    if start_service:
        from . import desktop

        desktop.start(directory)
    profile = load_profile(directory)
    check_start_allowed(profile)
    binding = load_binding(profile)
    kwargs = {"recovery_epoch": binding["recovery_epoch"]} if binding and binding["recovery_epoch"] else {}
    return MemoryClient(profile.base_url, profile.api_key, profile.brain_id, timeout=timeout, trust_env=False, **kwargs)


def run_mcp(directory: Path | None = None, *, require_turn_capture: bool = False) -> None:
    from .mcp_server import create_server

    with redirect_stdout(sys.stderr):
        client = open_client(directory)
    with client:
        with redirect_stdout(sys.stderr):
            server = create_server(client, directory=directory, require_turn_capture=require_turn_capture)
        server.run(transport="stdio")


class Updating(RuntimeError):
    """The installed runtime is not this tool server's own yet: an update is being installed."""


class PendingService:
    """The local service as a tool server sees it from its first moment, ready or not.

    A background thread waits for the service and starts it with ``start(directory)`` (which may also apply a restart
    an update left pending), retrying with growing pauses: a start that finds the profile busy, a port taken or an
    update still installing is tried again later, never ending the tool server. Until then each tool answers with
    ``refusal()``; ``client`` is set once the service is ready.
    """

    def __init__(self, directory: Path, start):
        self.directory = Path(directory)
        self.client: MemoryClient | None = None
        self._start = start
        self._guard = threading.Lock()
        self._thread = None
        self._updating = False
        self._asked = threading.Event()  # A tool call came while waiting: try again now, not after the pause.

    def wake(self) -> None:
        with self._guard:
            if self.client is None and (self._thread is None or not self._thread.is_alive()):
                self._thread = threading.Thread(target=self._run, name="memory-start", daemon=True)
                self._thread.start()

    def lost(self) -> None:
        """The service stopped answering (a restart elsewhere): wait for it again."""
        self.client = None
        self.wake()

    def _ready(self) -> MemoryClient | None:
        from . import desktop
        from .local_profile import LocalProfileBusy

        try:
            if (self.directory / "profile.json").exists() and desktop.status(self.directory).get("ready"):
                return open_client(self.directory, start_service=False)
        except LocalProfileBusy:
            pass
        return None

    def _run(self) -> None:
        from . import host

        pause = 1.0
        while True:
            try:
                with redirect_stdout(sys.stderr):  # The protocol owns stdout; nothing of a start may reach it.
                    client = self._ready()
                    if client is None:
                        try:
                            self._start(self.directory)
                            self._updating = False
                        except Updating:
                            self._updating = True
                        client = self._ready()
                if client is not None:
                    self.client, self._updating = client, False
                    return
            except Exception as error:  # Retried below; the cause the tools give is read from the status.
                host.log(self.directory, f"tool server start pending: {type(error).__name__}: {str(error)[:300]}")
            self._asked.wait(pause)
            self._asked.clear()
            pause = min(pause * 2, 30.0)

    def refusal(self) -> dict:
        from . import host
        from .local_profile import brief_profile_waits

        self.wake()
        self._asked.set()
        if self._updating:
            return {"error": "memBrain is being updated; try again in a moment."}
        with brief_profile_waits():
            cause = host.not_ready(self.directory)
        if cause["cause"] == "port_conflict":
            return {"error": f"memBrain cannot start: another program is using port {cause['port']}, which it "
                             "needs. Ask the user to close that program, then try again."}
        if cause["cause"] == "restarting":
            return {"error": "memBrain is restarting after an update; try again in a moment."}
        if cause["cause"] == "starting":
            return {"error": "memBrain is still starting; try again in a moment."}
        return {"error": "memBrain is not running; membrain doctor says why."}


def serve_pending(directory: Path, start, *, require_turn_capture: bool = True) -> None:
    """Serve the memory tools at once, whether or not the service is ready (``PendingService``)."""
    from .mcp_server import create_server

    pending = PendingService(directory, start)
    with redirect_stdout(sys.stderr):
        server = create_server(None, directory=directory, require_turn_capture=require_turn_capture, pending=pending)
    try:
        server.run(transport="stdio")
    finally:
        if pending.client is not None:
            pending.client.close()
