import contextvars
import time
from contextlib import contextmanager

from .helpers import DomainError

_WINDOW = contextvars.ContextVar("membrain_recall_window", default=None)


@contextmanager
def window(started, deadline):
    token = _WINDOW.set((started, deadline))
    try:
        remaining(30000)
        yield
    finally:
        _WINDOW.reset(token)


def remaining(milliseconds):
    current = _WINDOW.get()
    if current is None:
        return milliseconds
    value = min(milliseconds, int((current[1] - time.monotonic()) * 1000))
    if value <= 0:
        raise DomainError("budget_exceeded", "Recall transaction deadline exceeded.", retryable=True)
    return value


def elapsed(fallback):
    current = _WINDOW.get()
    return fallback if current is None else int((time.monotonic() - current[0]) * 1000)
