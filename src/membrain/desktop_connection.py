from __future__ import annotations

import sys
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
