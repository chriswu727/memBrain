import hashlib
import json
import os
import socket
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import psycopg
from psycopg.rows import dict_row
from membrain import embedded_database, host
from membrain.client import MemoryClient
from membrain.local_profile import load_profile

root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029')
profile=load_profile(Path('/Users/yichen/tmp/membrain-attribution-d4f-20261104/failed-corpus-copy'))
layout=embedded_database._layout(profile)
settings=profile.settings()
assert settings.cognition_base_url is None and settings.embedding_base_url is None
hashes={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (repo/'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
config_hash=hashlib.sha256((layout.data/'postgresql.conf').read_bytes()).hexdigest()
report={'purpose':'fixed 32/128/128/32 MB buffer ABBA on retained isolated failed corpus; not full R5 qualification','completed':False,'model_calls':0,'source_sha256':hashes,'arms':[],'limitations':'Normal host variation and increasing trace/receipt volume remain. No browser. Instrumentation observes request CPU/native hits/GC; settings changed only through owned postmaster command options, not application/config files.'}
environment={k:v for k,v in os.environ.items() if not k.startswith(('MEMORY_','MEMBRAIN_')) and not k.endswith(('_API_KEY','_API_TOKEN'))};environment.update(MEMBRAIN_SEMANTIC='0',PYTHON_DOTENV_DISABLED='1')
def closed(port):
 with socket.socket() as s:s.settimeout(.2);return s.connect_ex(('127.0.0.1',port))!=0

def pg_stats():
 with psycopg.connect(profile.migration_database_url,autocommit=True,row_factory=dict_row) as conn:
  conn.execute('SELECT pg_stat_clear_snapshot()')
  return {'shared_buffers':conn.execute('SHOW shared_buffers').fetchone()['shared_buffers'],'tables':conn.execute('SELECT relname,heap_blks_read,heap_blks_hit,idx_blks_read,idx_blks_hit,toast_blks_read,toast_blks_hit FROM pg_statio_user_tables ORDER BY relname').fetchall(),'wal':conn.execute('SELECT wal_records,wal_fpi,wal_bytes FROM pg_stat_wal').fetchone()}

assert closed(profile.api_port) and closed(profile.database_port)
process=None;started=False;api_log=None;port=None
try:
 expected=None
 for arm,megabytes in enumerate((32,128,128,32)):
  result=embedded_database._run(layout,'pg_ctl','start','-D',str(layout.data),'-l',str(layout.log),'-o',f'-c shared_buffers={megabytes}MB','-w','-t','90',timeout=120)
  assert result.returncode==0;started=True
  assert pg_stats()['shared_buffers']==f'{megabytes}MB'
  with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
  base=f'http://127.0.0.1:{port}';api_log=(root/f'api-{arm}.log').open('w')
  process=subprocess.Popen([sys.executable,str(root/'worker.py'),str(profile.directory),str(port),'1'],cwd=repo,env=environment,stdout=api_log,stderr=subprocess.STDOUT)
  with httpx.Client(trust_env=False,timeout=30) as control:
   deadline=time.monotonic()+30
   while True:
    assert process.poll() is None
    try:
     if control.get(base+'/health',timeout=.5).status_code==200:break
    except httpx.TransportError:pass
    assert time.monotonic()<deadline;time.sleep(.1)
   clients=[MemoryClient(base,profile.api_key,brain_id=host.user_brain_id(f'bench-user-{i}'),trust_env=False) for i in range(8)]
   def workload(rounds):
    def worker(index):
     rows=[]
     for query_index in range(rounds):
      wall=time.perf_counter();context=host.recall_context(clients[index],f'What is the appointment for project{query_index:04d}?',current_conversation='benchmark')
      assert context
      rows.append({'brain_index':index,'query_index':query_index,'wall_ms':(time.perf_counter()-wall)*1000,'context_sha256':hashlib.sha256(context.encode()).hexdigest()})
     return rows
    with ThreadPoolExecutor(max_workers=8) as pool:return [row for part in pool.map(worker,range(8)) for row in part]
   try:
    warmup=workload(4)
    before=control.get(base+'/__diagnostic/snapshot?reset=true').json();pg_before=pg_stats()
    began=time.perf_counter();rows=workload(20);elapsed=time.perf_counter()-began
    after=control.get(base+'/__diagnostic/snapshot').json()
   finally:
    for client in clients:client.close()
  process.terminate();process.wait(timeout=20);api_exit=process.returncode;process=None
  api_log.close();api_log=None
  pg_after=pg_stats()
  embedded_database.stop(profile);started=False
  assert closed(profile.database_port) and closed(port)
  received=[r for r in after['requests'] if r['action']=='recall' and r['outcome']=='completed']
  assert len(rows)==160 and len(received)==160 and all(r['items']>0 for r in received)
  assert after['native_hits']==160
  assert all(not (r.get('usage') or {}).get('model_calls') and not (r.get('usage') or {}).get('embedding_calls') for r in received)
  signatures={(row['brain_index'],row['query_index']):row['context_sha256'] for row in rows}
  if expected is None:expected=signatures
  assert signatures==expected
  sorted_times=sorted(row['wall_ms'] for row in rows)
  report['arms'].append({'arm':arm,'shared_buffers_mb':megabytes,'seconds':elapsed,'p95_ms':sorted_times[151],'median_ms':statistics.median(sorted_times),'process_cpu_ms':after['process_cpu_ms']-before['process_cpu_ms'],'event_loop_cpu_ms':after['event_loop_cpu_ms']-before['event_loop_cpu_ms'],'warmup_nonempty':len(warmup),'measured_nonempty':len(rows),'all_context_hashes_match':True,'native_hits':after['native_hits'],'rows':rows,'requests':received,'gc_collections':after['collections'],'pg_before':pg_before,'pg_after':pg_after,'api_exit_code':api_exit,'ports_closed':True})
  (root/'buffer-abba.json').write_text(json.dumps(report,default=str,indent=2)+'\n')
 report['completed']=True
finally:
 if process is not None:
  process.terminate()
  try:process.wait(timeout=20)
  except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
 if api_log is not None:api_log.close()
 if started:embedded_database.stop(profile)
 report['ports_closed']=closed(profile.database_port) and closed(profile.api_port) and (port is None or closed(port))
 report['source_unchanged']=all(hashlib.sha256((repo/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
 report['configuration_unchanged']=hashlib.sha256((layout.data/'postgresql.conf').read_bytes()).hexdigest()==config_hash
 (root/'buffer-abba.json').write_text(json.dumps(report,default=str,indent=2)+'\n')
assert report['completed'] and report['ports_closed'] and report['source_unchanged'] and report['configuration_unchanged']
print(json.dumps({'completed':True,'arms':[{k:a[k] for k in ('arm','shared_buffers_mb','p95_ms','median_ms','process_cpu_ms','seconds','all_context_hashes_match')} for a in report['arms']],'ports_closed':True,'source_unchanged':True,'configuration_unchanged':True}))
