from __future__ import annotations

import multiprocessing
import threading
import time
from concurrent.futures import CancelledError, ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timedelta

from . import cognition, helpers
from .helpers import DomainError


def _compute(args, options, deadline, clock):
    previous_clock = helpers._scenario_clock
    try:
        if clock is not None:
            moment, sent = clock
            origin = datetime.fromisoformat(moment.replace("Z", "+00:00"))
            helpers._scenario_clock = lambda: origin + timedelta(seconds=time.monotonic() - sent)
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise DomainError("budget_exceeded", "Recall computation deadline exceeded.", retryable=True)
        scope, request, memories, events, state = args
        request = {**request, "budget": {**request["budget"], "max_wall_time_ms": remaining}}
        result = cognition.recall(scope, request, memories, events, state, **options)
        return {"result": result}
    except DomainError as error:
        return {"error": error.as_dict()}
    except Exception:
        return {"error": {"code": "internal_error", "message": "Recall computation failed.", "retryable": False}}
    finally:
        helpers._scenario_clock = previous_clock


class RecallExecutor:
    def __init__(self, workers=2):
        if type(workers) is not int or not 1 <= workers <= 4:
            raise ValueError("Recall workers must be an integer from 1 to 4.")
        self.workers = workers
        self._slots = threading.BoundedSemaphore(workers * 4)
        self._lock = threading.Lock()
        self._pool = None
        self._closed = False

    def _executor(self):
        with self._lock:
            if self._closed:
                raise DomainError("dependency_unavailable", "Recall computation is stopping.", retryable=True)
            if self._pool is None:
                self._pool = ProcessPoolExecutor(max_workers=self.workers,
                                                 mp_context=multiprocessing.get_context("spawn"))
            return self._pool

    def __call__(self, scope, request, memories, events, state, **options):
        started = time.monotonic()
        deadline = started + request["budget"]["max_wall_time_ms"] / 1000
        if not self._slots.acquire(blocking=False):
            raise DomainError("dependency_unavailable", "Recall computation is busy. Retry it.", retryable=True)
        future, pool = None, None
        try:
            clock = (helpers.now(), time.monotonic()) if helpers._scenario_clock is not None else None
            pool = self._executor()
            future = pool.submit(_compute, (scope, request, memories, events, state), options, deadline, clock)
            # A timed-out task may still be running; its slot remains occupied until its computation ends.
            future.add_done_callback(lambda _: self._slots.release())
            value = future.result(timeout=max(0, deadline - time.monotonic()))
            if "error" in value:
                raise DomainError(**value["error"])
            result = value["result"]
            result["usage"]["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            return result
        except TimeoutError:
            if future is not None:
                future.cancel()
            raise DomainError("budget_exceeded", "Recall computation deadline exceeded.", retryable=True) from None
        except CancelledError:
            raise DomainError("dependency_unavailable", "Recall computation is stopping.", retryable=True) from None
        except BrokenProcessPool:
            with self._lock:
                if self._pool is pool:
                    self._pool = None
            if pool is not None:
                pool.shutdown(wait=False, cancel_futures=True)
            raise DomainError("dependency_unavailable", "Recall computation restarted. Retry it.", retryable=True) from None
        except (OSError, RuntimeError):
            raise DomainError("dependency_unavailable", "Recall computation is unavailable. Retry it.", retryable=True) from None
        finally:
            if future is None:
                self._slots.release()

    def close(self):
        with self._lock:
            self._closed = True
            pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
