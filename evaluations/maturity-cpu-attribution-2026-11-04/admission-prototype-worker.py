import functools
import gc
import json
import resource
import sys
import threading
import time
from pathlib import Path

import uvicorn

from membrain.api import create_app
from membrain.local_profile import load_profile
from membrain.service import MemoryService

profile = load_profile(Path(sys.argv[1]))
slots = int(sys.argv[3])
gate = threading.BoundedSemaphore(slots) if slots else None
lock = threading.RLock()
requests = []
active = peak = 0
gc_start = {}
collections = []
respond = MemoryService.respond


@functools.wraps(respond)
def limited(self, principal, request):
    global active, peak
    began, cpu = time.perf_counter_ns(), time.thread_time_ns()
    if gate is not None:
        gate.acquire()
    admitted = time.perf_counter_ns()
    with lock:
        active += 1
        peak = max(peak, active)
    try:
        result = respond(self, principal, request)
        elapsed, used = (time.perf_counter_ns()-began)/1e6, (time.thread_time_ns()-cpu)/1e6
        envelope = result[0]
        row = {'action': request.get('action'), 'outcome': envelope['outcome'], 'wall_ms': elapsed,
               'cpu_ms': used, 'queue_ms': (admitted-began)/1e6,
               'items': len(envelope.get('result', {}).get('items', [])),
               'usage': envelope.get('result', {}).get('usage')}
        with lock:
            requests.append(row)
        return result
    finally:
        with lock:
            active -= 1
        if gate is not None:
            gate.release()


MemoryService.respond = limited


def collect(phase, info):
    key = threading.get_ident(), info['generation']
    if phase == 'start':
        gc_start[key] = time.perf_counter_ns(), time.thread_time_ns()
    else:
        before = gc_start.pop(key, None)
        if before:
            with lock:
                collections.append({'generation': info['generation'],
                                    'wall_ms': (time.perf_counter_ns()-before[0])/1e6,
                                    'cpu_ms': (time.thread_time_ns()-before[1])/1e6})


gc.callbacks.append(collect)
app = create_app(profile.settings())


@app.get('/__diagnostic/snapshot')
async def snapshot(reset: bool = False):
    global peak
    with lock:
        result = {'process_cpu_ms': time.process_time_ns()/1e6, 'event_loop_cpu_ms': time.thread_time_ns()/1e6,
                  'requests': list(requests), 'collections': list(collections), 'peak_active': peak,
                  'max_rss_platform_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        if reset:
            requests.clear()
            collections.clear()
            peak = active
    return result


uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
