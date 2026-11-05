import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx
from membrain import embedded_database, host
from membrain.client import MemoryClient, MemoryActionError, recalled_context
from membrain.local_profile import load_profile

ROOT=Path(__file__).parent
REPO=Path('/Users/yichen/tmp/membrain-review-20261029')
DIRECTORY=Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation')
profile=load_profile(DIRECTORY)
assert profile.settings().cognition_base_url is None and profile.settings().embedding_base_url is None
paths=[p for base in (REPO/'src',REPO/'tests',ROOT/'baseline47') for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths.extend([Path(__file__),ROOT/'cold-worker.py'])
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
env={k:v for k,v in os.environ.items() if not k.startswith(('MEMORY_','MEMBRAIN_')) and not k.endswith(('_API_KEY','_API_TOKEN'))}
env.update(PYTHON_DOTENV_DISABLED='1',MEMBRAIN_SEMANTIC='0',MEMBRAIN_RECALL_PROCESSES='2')
report={'completed':False,'scope':'Cold startup using an import-safe production API worker; four process launches in ABBA order, one first recall and one subsequent recall each. Direct SDK calls, no host fallback or retries; not R5.','model_calls':0,'source_sha256':hashes,'runs':[]}
process=None
log=None
started=False
ports={profile.api_port,profile.database_port}
try:
    for port in ports:
        with socket.socket() as s: assert s.connect_ex(('127.0.0.1',port))!=0
    embedded_database.start(profile)
    started=True
    for index,mode in enumerate(('baseline','ready','ready','baseline')):
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
        ports.add(port)
        local_env={**env,'PYTHONPATH':str((ROOT/'baseline47' if mode=='baseline' else REPO)/'src')}
        log=(ROOT/f'cold-{index}-{mode}.log').open('w')
        begin=time.perf_counter()
        process=subprocess.Popen([sys.executable,str(ROOT/'cold-worker.py'),str(DIRECTORY),str(port)],cwd=REPO,env=local_env,stdout=log,stderr=subprocess.STDOUT)
        with httpx.Client(trust_env=False) as control:
            deadline=time.monotonic()+40
            while True:
                assert process.poll() is None, f'API startup failed: {mode}'
                try:
                    if control.get(f'http://127.0.0.1:{port}/health',timeout=.5).status_code==200: break
                except httpx.TransportError: pass
                assert time.monotonic()<deadline
                time.sleep(.025)
        row={'mode':mode,'ready_ms':(time.perf_counter()-begin)*1000,'recalls':[]}
        with MemoryClient(f'http://127.0.0.1:{port}',profile.api_key,brain_id=host.user_brain_id('bench-user-0'),trust_env=False) as client:
            for attempt in ('first','subsequent'):
                begin=time.perf_counter()
                try:
                    response=client.recall('What is the appointment for project0000?',budget=host.recall_budget(embeddings=0),evidence_cutoff={'mode':'through_sequence','through_sequence':2**53})
                except MemoryActionError as error:
                    response=error.response
                elapsed=(time.perf_counter()-begin)*1000
                context=recalled_context(response) if response['outcome']=='completed' else ''
                row['recalls'].append({'attempt':attempt,'wall_ms':elapsed,'outcome':response['outcome'],'error_code':response.get('error',{}).get('code'),'context_characters':len(context),'context_sha256':hashlib.sha256(context.encode()).hexdigest()})
        report['runs'].append(row)
        print(json.dumps(row),flush=True)
        process.terminate(); process.wait(timeout=20); log.close()
    report['completed']=True
finally:
    if process is not None and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=20)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    if log is not None: log.close()
    if started: embedded_database.stop(profile)
    report['inputs_unchanged']=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==value for p,value in hashes.items())
    report['ports_closed']=True
    for port in ports:
        with socket.socket() as s: report['ports_closed'] &= s.connect_ex(('127.0.0.1',port))!=0
    (ROOT/'cold-probe.json').write_text(json.dumps(report,indent=2))
assert report['completed'] and report['inputs_unchanged'] and report['ports_closed']
