import json,os,platform,socket,statistics,time
from pathlib import Path
os.environ['MEMBRAIN_SEMANTIC']='0'
os.environ['PYTHON_DOTENV_DISABLED']='1'
from membrain import desktop,host,host_recording
from membrain.build_identity import BUILD_ID
from membrain.local_profile import ensure_profile
root=Path('/private/tmp/membrain-recording-fence-probe-profile')
profile=ensure_profile(root,database_engine='embedded')
result={'build_id':BUILD_ID,'machine':platform.machine(),'model_calls':0,'transport':'real loopback HTTP with embedded PostgreSQL'}
def timed(fn):
    start=time.perf_counter();fn();return (time.perf_counter()-start)*1000

def summary(values):
    values=sorted(values)
    return {'count':len(values),'median_ms':round(statistics.median(values),3),'p95_ms':round(values[int(.95*(len(values)-1))],3),'max_ms':round(max(values),3)}
try:
    assert host.start(root)['ready']
    with host.ready_client(root) as client:
        assert client.recording_status()=={'paused':False,'revision':0}
        for _ in range(10): host_recording.status(root,client)
        raw,cached=[],[]
        for _ in range(100):
            raw.append(timed(client.recording_status))
            cached.append(timed(lambda:host_recording.status(root,client)))
        result['policy_read']=summary(raw)
        result['policy_read_and_cache']=summary(cached)
        a,b=[],[]
        for i in range(100):
            operations=[('unfenced',a,{}),('fenced',b,{'expected_recording_revision':0})]
            if i%2:operations.reverse()
            for label,values,kwargs in operations:
                values.append(timed(lambda:client.observe(f'Synthetic sample {i}',conversation_id='probe',branch_id='main',source_event_key=f'{label}-{i}',**kwargs)))
        result['observation_unfenced']=summary(a)
        result['observation_fenced']=summary(b)
        captured=host_recording.status(root,client)
        for i in range(500):
            record=host.message_record('queued','user',f'Synthetic discarded capture {i}',turn_id=str(i))
            host_recording.stamp(record,captured)
            host.spool(root,record)
        client.set_recording(paused=True,expected_revision=0)
        client.set_recording(paused=False,expected_revision=1)
        start=time.perf_counter()
        assert host.flush(client,root)==500
        elapsed=time.perf_counter()-start
        assert not (root/'plugin/spool.jsonl').read_text()
        assert not (root/'plugin/spool-rejected.jsonl').exists()
        events=client.timeline(roles=('user','assistant'),limit=1000,max_characters=200000)['items']
        assert len(events)==200 and all('discarded capture' not in x['text'] for x in events)
        result['stale_queue']={'records':500,'seconds':round(elapsed,3),'records_per_second':round(500/elapsed,1),'queued_content_stored':False,'rejected_archive_created':False}
finally:
    desktop.stop(root)
    closures={}
    for label,port in [('api',profile.api_port),('database',profile.database_port)]:
        with socket.socket() as connection:
            connection.settimeout(.2)
            closures[label]=connection.connect_ex(('127.0.0.1',port))!=0
    result['ports_closed']=closures
assert all(result['ports_closed'].values())
print(json.dumps(result,indent=2))
