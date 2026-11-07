import cProfile
import functools
import gc
import pstats
import sys
import threading
import time
from pathlib import Path
import uvicorn
from membrain import api, candidates
from membrain.local_profile import load_profile
from membrain.service import MemoryService

profile=load_profile(Path(sys.argv[1]))
lock=threading.RLock()
requests=[]
candidate_profiles=[]
original_collect=candidates.collect_candidates

@functools.wraps(original_collect)
def profile_collect(*args,**kwargs):
    profiler=cProfile.Profile(timer=time.thread_time)
    result=profiler.runcall(original_collect,*args,**kwargs)
    stats=pstats.Stats(profiler).stats
    rows=[{'file':filename,'line':line,'function':name,'primitive_calls':values[0],'calls':values[1],
           'own_cpu_seconds':values[2],'inclusive_cpu_seconds':values[3]}
          for (filename,line,name),values in stats.items()]
    with lock:candidate_profiles.append(rows)
    return result

candidates.collect_candidates=profile_collect
original_respond=MemoryService.respond

@functools.wraps(original_respond)
def respond(self,principal,request):
    wall,cpu=time.perf_counter_ns(),time.thread_time_ns()
    result=original_respond(self,principal,request)
    envelope=result[0]
    row={'action':request.get('action'),'outcome':envelope['outcome'],
         'items':len(envelope.get('result',{}).get('items',[])),
         'usage':envelope.get('result',{}).get('usage'),
         'wall_ms':(time.perf_counter_ns()-wall)/1e6,'cpu_ms':(time.thread_time_ns()-cpu)/1e6,'metrics':{}}
    with lock:requests.append(row)
    return result

MemoryService.respond=respond
app=api.create_app(profile.settings())

@app.get('/__diagnostic/snapshot')
async def snapshot(reset:bool=False):
    with lock:
        result={'process_cpu_ms':time.process_time_ns()/1e6,'event_loop_cpu_ms':time.thread_time_ns()/1e6,
                'requests':list(requests),'candidate_profiles':list(candidate_profiles),
                'metrics':{},'gc_thresholds':gc.get_threshold(),'gc_stats':gc.get_stats()}
        if reset:requests.clear();candidate_profiles.clear()
    return result

uvicorn.run(app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
