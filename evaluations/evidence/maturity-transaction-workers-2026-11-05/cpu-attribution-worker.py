import contextvars
import functools
import gc
import re
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path


def main():
    import fastapi.encoders
    import fastapi.routing
    import psycopg
    import uvicorn
    from starlette.responses import JSONResponse
    from membrain import api, relationship
    from membrain.local_profile import load_profile
    from membrain.service import MemoryService

    local = threading.local()
    lock = threading.Lock()
    path = contextvars.ContextVar('diagnostic_path', default='')
    metrics = defaultdict(lambda: {'calls': 0, 'wall_ms': 0., 'cpu_ms': 0., 'max_wall_ms': 0.})
    requests = []

    def record(name, wall, cpu):
        with lock:
            row = metrics[path.get() + ':' + name]
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
                record(name, (time.perf_counter_ns()-wall)/1e6, (time.thread_time_ns()-cpu)/1e6)
        return call

    original = MemoryService.respond
    @functools.wraps(original)
    def respond(self, principal, request):
        result = measured(original, 'service.respond')(self, principal, request)
        envelope = result[0]
        with lock:
            requests.append({'action':request.get('action'),'outcome':envelope['outcome'],
                             'items':len(envelope.get('result',{}).get('items',[])),
                             'usage':envelope.get('result',{}).get('usage'),
                             'error_code':envelope.get('error',{}).get('code')})
        return result
    MemoryService.respond = respond
    for name in ('timeline','following','_retrieval','_brain','_save_traces'):
        setattr(MemoryService,name,measured(getattr(MemoryService,name),'service.'+name))
    relationship.relationship_boundaries = measured(relationship.relationship_boundaries,'relationship_boundaries')
    from membrain import candidates
    candidates.collect_candidates = measured(candidates.collect_candidates,'collect_candidates')
    from membrain.recall_executor import RecallExecutor
    RecallExecutor.__call__ = measured(RecallExecutor.__call__,'compute_queue_transfer')
    psycopg.Connection.execute = measured(psycopg.Connection.execute,'sql_execute')
    psycopg.Cursor.fetchall = measured(psycopg.Cursor.fetchall,'decode_all')
    psycopg.Cursor.fetchone = measured(psycopg.Cursor.fetchone,'decode_one')
    JSONResponse.render = measured(JSONResponse.render,'json_encode')

    original_encoder = fastapi.encoders.jsonable_encoder
    @functools.wraps(original_encoder)
    def encoder(*args, **kwargs):
        if getattr(local,'encoding',False):
            return original_encoder(*args,**kwargs)
        local.encoding = True
        try:
            return measured(original_encoder,'jsonable_encoder')(*args,**kwargs)
        finally:
            local.encoding = False
    fastapi.encoders.jsonable_encoder = fastapi.routing.jsonable_encoder = encoder

    app = api.create_app(load_profile(Path(sys.argv[1])).settings())
    @app.get('/__diagnostic/snapshot')
    async def snapshot(reset: bool = False):
        with lock:
            result={'process_cpu_ms':time.process_time_ns()/1e6,'event_loop_cpu_ms':time.thread_time_ns()/1e6,
                    'metrics':{key:dict(value) for key,value in metrics.items() if not key.startswith('/__diagnostic')},
                    'requests':list(requests),'gc_thresholds':gc.get_threshold(),'gc_stats':gc.get_stats(), 'function_profile':[]}
            if reset: metrics.clear();requests.clear()
        return result

    class Diagnostic:
        async def __call__(self, scope, receive, send):
            if scope['type']!='http': return await app(scope,receive,send)
            route=re.sub(r'/brains/[^/]+','/brains/{brain}',scope['path'])
            token=path.set(route)
            wall=time.perf_counter_ns()
            try:
                return await app(scope,receive,send)
            finally:
                record('http',(time.perf_counter_ns()-wall)/1e6,0)
                path.reset(token)
    uvicorn.run(Diagnostic(),host='127.0.0.1',port=int(sys.argv[2]),log_level='error')


if __name__=='__main__':
    main()
