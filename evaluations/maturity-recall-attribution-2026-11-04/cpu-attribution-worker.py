import contextvars
import functools
import gc
import json
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

import psycopg
import uvicorn
from starlette.responses import JSONResponse

from membrain import api, candidates, context_views, contracts
from membrain.local_profile import load_profile
from membrain.service import MemoryService

profile = load_profile(Path(sys.argv[1]))
local = threading.local()
lock = threading.RLock()
path = contextvars.ContextVar('diagnostic_path', default='')
metrics = defaultdict(lambda: {'calls': 0, 'wall_ms': 0., 'cpu_ms': 0., 'max_wall_ms': 0.})
requests = []
gc_starts = {}


def record(name, wall, cpu):
    target = getattr(local, 'metrics', None)
    if target is not None:
        row = target[name]
        row['calls'] += 1
        row['wall_ms'] += wall
        row['cpu_ms'] += cpu
        row['max_wall_ms'] = max(row['max_wall_ms'], wall)
    else:
        with lock:
            row = metrics[name]
            row['calls'] += 1
            row['wall_ms'] += wall
            row['cpu_ms'] += cpu
            row['max_wall_ms'] = max(row['max_wall_ms'], wall)


def measured(function, name):
    @functools.wraps(function)
    def call(*args, **kwargs):
        wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
        try:
            return function(*args, **kwargs)
        finally:
            record(name, (time.perf_counter_ns() - wall) / 1e6, (time.thread_time_ns() - cpu) / 1e6)
    return call


original_validate = contracts.validate


@functools.wraps(original_validate)
def validate(definition, value):
    return measured(original_validate, 'validate:' + str(definition))(definition, value)


for module in list(sys.modules.values()):
    if getattr(module, '__name__', '').startswith('membrain') and getattr(module, 'validate', None) is original_validate:
        module.validate = validate

MemoryService._bind_document = measured(MemoryService._bind_document, 'bind_document')
MemoryService._recall = measured(MemoryService._recall, 'core_recall')
MemoryService._save_traces = measured(MemoryService._save_traces, 'save_traces')
candidates.collect_candidates = measured(candidates.collect_candidates, 'collect_candidates')
context_views.FittingMeasure._measure = measured(context_views.FittingMeasure._measure, 'context_measure')
execute = psycopg.Connection.execute


@functools.wraps(execute)
def sql_execute(self, query, *args, **kwargs):
    label = ' '.join(query.split()[:40]) if isinstance(query, str) else type(query).__name__
    return measured(execute, 'SQL:' + label)(self, query, *args, **kwargs)


psycopg.Connection.execute = sql_execute
psycopg.Cursor.fetchall = measured(psycopg.Cursor.fetchall, 'decode_rows')
psycopg.Cursor.fetchone = measured(psycopg.Cursor.fetchone, 'decode_one')
original_respond = MemoryService.respond


@functools.wraps(original_respond)
def respond(self, principal, request):
    local.metrics = defaultdict(lambda: {'calls': 0, 'wall_ms': 0., 'cpu_ms': 0., 'max_wall_ms': 0.})
    wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
    try:
        result = original_respond(self, principal, request)
        elapsed, used = (time.perf_counter_ns() - wall) / 1e6, (time.thread_time_ns() - cpu) / 1e6
        envelope = result[0]
        row = {'request_id': request['request_id'], 'action': request.get('action'), 'wall_ms': elapsed,
               'cpu_ms': used, 'outcome': envelope['outcome'], 'error_code': envelope.get('error', {}).get('code'),
               'items': len(envelope.get('result', {}).get('items', [])),
               'traces': len(envelope.get('result', {}).get('recall_traces', [])),
               'usage': envelope.get('result', {}).get('usage'), 'metrics': dict(local.metrics)}
        with lock:
            requests.append(row)
        return result
    finally:
        del local.metrics


MemoryService.respond = respond
render = JSONResponse.render


@functools.wraps(render)
def encode(self, content):
    if path.get().startswith('/__diagnostic'):
        return render(self, content)
    return measured(render, 'encode:' + path.get())(self, content)


JSONResponse.render = encode


def collected(phase, info):
    key = threading.get_ident(), info['generation']
    if phase == 'start':
        gc_starts[key] = time.perf_counter_ns(), time.thread_time_ns()
    else:
        before = gc_starts.pop(key, None)
        if before:
            record('GC:' + str(info['generation']), (time.perf_counter_ns() - before[0]) / 1e6,
                   (time.thread_time_ns() - before[1]) / 1e6)


gc.callbacks.append(collected)
app = api.create_app(profile.settings())


@app.middleware('http')
async def diagnostic_path(request, call_next):
    token = path.set(request.url.path)
    try:
        return await call_next(request)
    finally:
        path.reset(token)


@app.get('/__diagnostic/snapshot')
async def snapshot(reset: bool = False):
    with lock:
        result = {'process_cpu_ms': time.process_time_ns() / 1e6,
                  'event_loop_cpu_ms': time.thread_time_ns() / 1e6,
                  'metrics': dict(metrics), 'requests': list(requests),
                  'gc_thresholds': gc.get_threshold(), 'gc_stats': gc.get_stats()}
        if reset:
            metrics.clear()
            requests.clear()
    return result


uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
