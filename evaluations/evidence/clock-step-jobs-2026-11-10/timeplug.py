"""Pytest plugin: log wall/monotonic time per test, outcome, live threads and children."""
import os, threading, time, json
import pytest

_LOG = None

def _log(rec):
    global _LOG
    if _LOG is None:
        _LOG = open(os.environ['TIMEPLUG_LOG'], 'a', buffering=1)
    _LOG.write(json.dumps(rec) + '\n')

def _children():
    try:
        with open(f'/proc/{os.getpid()}/task/{os.getpid()}/children') as f:
            return f.read().split()
    except OSError:
        return []

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    w0, m0 = time.time(), time.monotonic()
    _log({'ev': 'start', 'id': item.nodeid, 'wall': w0, 'mono': m0, 'off': w0 - m0,
          'threads': [t.name for t in threading.enumerate()], 'children': _children()})
    yield
    w1, m1 = time.time(), time.monotonic()
    _log({'ev': 'end', 'id': item.nodeid, 'wall': w1, 'mono': m1, 'off': w1 - m1,
          'offdelta_ms': ((w1 - m1) - (w0 - m0)) * 1000})

def pytest_runtest_logreport(report):
    if report.when == 'call' or report.outcome != 'passed':
        _log({'ev': 'report', 'id': report.nodeid, 'when': report.when, 'outcome': report.outcome,
              'wall': time.time(), 'mono': time.monotonic()})
