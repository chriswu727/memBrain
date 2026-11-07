import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import tempfile
import time

os.environ.update(MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
from membrain import desktop, embedded_database
from membrain.helpers import Principal, uid
from membrain.local_profile import ensure_profile, load_profile
from membrain.mood import mood_state
from membrain.notes import store_note
from membrain.relationship import relationship
from membrain.service import MemoryService
from membrain.storage import Database

ROOT = Path(__file__).parent

def measure():
    database = Database(os.environ['MEMORY_DATABASE_URL'])
    principal = Principal(sys.argv[2], sys.argv[3])
    brain = MemoryService(database), principal, sys.argv[4]
    results = {}
    try:
        for name, reader in [('mood', mood_state), ('relationship', relationship)]:
            times = []
            for i in range(21):
                started = time.perf_counter(); result = reader(*brain)
                elapsed = (time.perf_counter()-started)*1000
                if i: times.append(elapsed)
            ordered = sorted(times)
            results[name] = {'n':len(times),'median_ms':round(statistics.median(times),2),'p95_ms':round(ordered[int(.95*(len(ordered)-1))],2),'max_ms':round(max(times),2),'raw_ms':times}
            if name == 'mood':
                results[name]['private_reason_count'] = sum('private_topic_' in x['reason'] for x in result['triggers'])
    finally:
        database.close()
    print(json.dumps(results))

if len(sys.argv)>1 and sys.argv[1]=='measure':
    measure();raise SystemExit

baseline = '/Users/yichen/tmp/membrain-affect-checks-20261106/installed-env/bin/python'
report = {'scope':'direct service reads, synthetic companion-heavy fixture; not canonical recall, network latency, semantic quality or R5','model_calls':0,'fixture':{'affect':500,'completed_plans':200,'shared_moments':200,'sensitive_source_every':10}}
with tempfile.TemporaryDirectory(prefix='companion-perf-',dir=ROOT) as tmp:
    directory=Path(tmp)/'installation';profile=ensure_profile(directory,database_engine='embedded');database=None
    try:
        desktop._prepare_database(profile);profile=load_profile(directory)
        database=Database(profile.database_url);service=MemoryService(database);principal=Principal(uid(),uid())
        ident=service.create_brain(principal,'Synthetic companion performance')['id']
        started=time.perf_counter()
        for i in range(900):
            topic=('private_topic_' if i%10==0 else 'public_topic_')+str(i)
            response=service.handle(principal,{'message_type':'request','contract_version':'1.0.0-draft','request_id':uid(),'action':'observe','target':{'brain_ref':ident,'conversation_ref':'synthetic','branch_ref':'main'},'payload':{'idempotency_key':uid(),'events':[{'source_event_key':uid(),'source_revision':1,'producer_ref':'companion-perf','actor_ref':'user','actor_role':'user','event_kind':'message','content':{'media_type':'text/plain','text':'I am glad about '+topic},'occurred_time':{'start':None,'end':None,'precision':'unknown','basis':'unknown'},'interpretation_hint':'unknown','delivery_state':'received','parent_source_event_keys':[]}]}})
            assert response['outcome']=='completed'
            source=response['result']['accepted_event_ids'][0]
            fields={'request_id':uid(),'text':topic+' was completed.','source_event_ids':[source]}
            if i<500: fields['affect']={'label':'glad','valence':1,'intensity':1,'basis':'reported','topic':topic}
            elif i<700: fields.update(kind='plan',status='done')
            else: fields.update(kind='milestone',shared=True)
            store_note(service,principal,ident,fields)
            if i%10==0:store_note(service,principal,ident,{'request_id':uid(),'text':topic+' is private.','source_event_ids':[source],'sensitive':True})
        report['fixture_seconds']=round(time.perf_counter()-started,2)
        database.close();database=None
        env={**os.environ,'MEMORY_DATABASE_URL':profile.database_url}
        for name,python in [('before',baseline),('after',sys.executable)]:
            result=subprocess.run([python,str(Path(__file__)),'measure',principal.tenant_id,principal.principal_id,ident],env=env,check=True,capture_output=True,text=True)
            report[name]=json.loads(result.stdout)
            print(name,'measured',flush=True)
    finally:
        if database: database.close()
        embedded_database.stop(load_profile(directory))
        with socket.socket() as sock:
            sock.settimeout(1);report['database_port_closed']=sock.connect_ex(('127.0.0.1',profile.database_port))!=0
        assert report['database_port_closed']
report['synthetic_profile_removed']=not directory.exists()
(ROOT/'performance.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('before','after')},indent=2))
for phase in ('before','after'):
 print(phase,json.dumps({name:{k:v for k,v in values.items() if k!='raw_ms'} for name,values in report[phase].items()}))
