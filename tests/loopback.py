"""A FastAPI app served on a real loopback TCP socket for the length of a ``with`` block, for tests.

Moved from ``examples/evaluation_host.py``, which was retired with the runtime-mode evaluation drivers that used it.
"""
import asyncio
import math
import socket
import sys
import threading
import time
from contextlib import contextmanager

import uvicorn


def _positive_seconds(value, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name} must be finite and positive")


class LoopbackServerError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"Loopback server failed: {code}")


@contextmanager
def loopback_server(app, *, startup_timeout_seconds=10, shutdown_timeout_seconds=10):
    _positive_seconds(startup_timeout_seconds, "startup_timeout_seconds")
    _positive_seconds(shutdown_timeout_seconds, "shutdown_timeout_seconds")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    state, stopped = {}, threading.Event()
    thread = None
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=0, log_level="critical", log_config=None,
            access_log=False, lifespan="on", loop="asyncio", http="h11", ws="none",
            timeout_graceful_shutdown=max(0.01, shutdown_timeout_seconds / 2),
        ))

        async def serve():
            state["loop"], state["task"] = asyncio.get_running_loop(), asyncio.current_task()
            try:
                await server.serve(sockets=[listener])
            except asyncio.CancelledError:
                pass

        def run():
            try:
                asyncio.run(serve())
            except BaseException:
                state["failed"] = True
            finally:
                stopped.set()

        thread = threading.Thread(target=run, name="memory-evaluation-http", daemon=True)
        thread.start()
        deadline = time.monotonic() + startup_timeout_seconds
        while not server.started:
            if stopped.is_set():
                raise LoopbackServerError("startup_failed")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LoopbackServerError("startup_timeout")
            stopped.wait(min(0.01, remaining))
        yield base_url
    finally:
        active_error = sys.exception()
        try:
            if thread is not None:
                deadline = time.monotonic() + shutdown_timeout_seconds
                server.should_exit = True
                thread.join(timeout=shutdown_timeout_seconds * 0.75)
                if thread.is_alive():
                    server.force_exit = True
                    loop, task = state.get("loop"), state.get("task")
                    if loop is not None and not loop.is_closed() and task is not None:
                        try:
                            loop.call_soon_threadsafe(task.cancel)
                        except RuntimeError:
                            pass
                    listener.close()
                    thread.join(timeout=max(0, deadline - time.monotonic()))
                if thread.is_alive():
                    if active_error is None:
                        raise LoopbackServerError("shutdown_timeout")
                    active_error.add_note("Loopback server cleanup failed: shutdown_timeout")
                elif state.get("failed") and active_error is None:
                    raise LoopbackServerError("server_failed")
        finally:
            listener.close()
