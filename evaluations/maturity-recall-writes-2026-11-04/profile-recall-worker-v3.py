import cProfile
import json
import sys
import threading
import time
from pathlib import Path

import psycopg
import uvicorn

from membrain.api import create_app
from membrain.local_profile import load_profile
from membrain.service import MemoryService

profile = load_profile(Path(sys.argv[1]))
destination = Path(sys.argv[3])
local = threading.local()
lock = threading.Lock()
execute = psycopg.Connection.execute
executemany = psycopg.Cursor.executemany
respond = MemoryService.respond


def sql_execute(self, query, *args, **kwargs):
    started = time.perf_counter()
    try:
        return execute(self, query, *args, **kwargs)
    finally:
        if hasattr(local, 'sql'):
            label = ' '.join(query.split()[:40]) if isinstance(query, str) else type(query).__name__
            local.sql.append({'kind': 'execute', 'query': label,
                              'ms': (time.perf_counter() - started) * 1000})


def sql_many(self, query, params, *args, **kwargs):
    started = time.perf_counter()
    try:
        return executemany(self, query, params, *args, **kwargs)
    finally:
        if hasattr(local, 'sql'):
            local.sql.append({'kind': 'executemany', 'query': ' '.join(query.split()[:40]),
                              'rows': len(params) if isinstance(params, (list, tuple)) else None,
                              'ms': (time.perf_counter() - started) * 1000})


def profiled(self, principal, request):
    if request.get('action') != 'recall':
        return respond(self, principal, request)
    local.sql = []
    profiler = cProfile.Profile() if request['request_id'].startswith('serial-profile-') else None
    started = time.perf_counter()
    try:
        result = (profiler.runcall(respond, self, principal, request) if profiler is not None
                  else respond(self, principal, request))
        if profiler is not None:
            profiler.create_stats()
        functions = sorted(({'file': key[0], 'line': key[1], 'name': key[2],
                             'calls': value[1], 'self_ms': value[2] * 1000,
                             'cumulative_ms': value[3] * 1000}
                            for key, value in (profiler.stats.items() if profiler is not None else ())),
                           key=lambda value: value['cumulative_ms'], reverse=True)
        envelope = result[0]
        record = {'request_id': request['request_id'], 'brain_id': request['target']['brain_ref'],
                  'profiled_ms': (time.perf_counter() - started) * 1000,
                  'outcome': envelope['outcome'], 'functions': functions[:60], 'cpu_profile': profiler is not None,
                  'sql': local.sql, 'items': len(envelope.get('result', {}).get('items', [])),
                  'traces': len(envelope.get('result', {}).get('recall_traces', [])),
                  'envelope_bytes': len(json.dumps(envelope).encode())}
        with lock, destination.open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        return result
    finally:
        del local.sql


psycopg.Connection.execute = sql_execute
psycopg.Cursor.executemany = sql_many
MemoryService.respond = profiled
uvicorn.run(create_app(profile.settings()), host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
