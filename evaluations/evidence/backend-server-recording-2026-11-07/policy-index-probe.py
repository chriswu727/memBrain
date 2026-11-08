import json,time,statistics
from pathlib import Path
from membrain import embedded_database
from membrain.local_profile import load_profile
from membrain.storage import Database
from membrain.helpers import Principal,uid
from membrain.service import MemoryService
from membrain.recording_control import set_recording
profile=load_profile(Path('/private/tmp/membrain-server-recording-db'))
try:
    embedded_database.start(profile)
    database=Database(profile.database_url)
    service=MemoryService(database)
    principal=Principal(uid(),uid())
    brain=service.create_brain(principal,'Synthetic policy index probe')['id']
    params=service._params(principal,brain)
    with database.transaction(principal) as conn:
        conn.execute("INSERT INTO memory_runtime_turns(tenant_id,owner_id,brain_id,turn_id,conversation_id,branch_id,input_fingerprint,stage) SELECT %s,%s,%s,'history-'||i,'history','main',repeat('a',64),'completed' FROM generate_series(1,20000) i",params)
    query="SELECT turn_id FROM memory_runtime_turns WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND stage NOT IN ('delivered','committed','completed','failed')"
    samples=[]; revision=0
    for sample in range(10):
        with database.transaction(principal) as conn:
            conn.execute("INSERT INTO memory_runtime_turns(tenant_id,owner_id,brain_id,turn_id,conversation_id,branch_id,input_fingerprint,scope_reserved) SELECT %s,%s,%s,%s||i,'live-'||i,'main',repeat('b',64),true FROM generate_series(1,8) i",(*params,'active-'+str(sample)+'-'))
            if sample==0:
                plan=[row['QUERY PLAN'] for row in conn.execute('EXPLAIN (ANALYZE,BUFFERS) '+query,params)]
        before=time.perf_counter()
        result=set_recording(service,principal,brain,paused=True,expected_revision=revision)
        samples.append((time.perf_counter()-before)*1000)
        revision=result['revision']
        with database.transaction(principal) as conn:
            counts={r['stage']:r['n'] for r in conn.execute('SELECT stage,count(*) AS n FROM memory_runtime_turns WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s GROUP BY stage',params)}
            assert counts=={'completed':20000,'failed':8*(sample+1)},counts
        revision=set_recording(service,principal,brain,paused=False,expected_revision=revision)['revision']
    print(json.dumps({'historical_completed_turns':20000,'active_turns_per_pause':8,'pause_samples_ms':samples,'pause_median_ms':statistics.median(samples),'pause_max_ms':max(samples),'candidate_scan_plan':plan,'historical_turns_unchanged':True,'closed_active_turns':80},indent=2))
finally:
    embedded_database.stop(profile)
