import json,socket
from pathlib import Path
from membrain import embedded_database,host
from membrain.config import configured_service
from membrain.contracts import validate
from membrain.helpers import Principal,now
from membrain.local_profile import load_profile
from membrain.local_embeddings import installed
from membrain.structure_map import structure_map
root=Path(__file__).parent
profile=load_profile(Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation'))
settings=profile.settings()
assert settings.cognition_base_url is None and settings.embedding_base_url is None and installed(profile.directory) is None
for port in (profile.api_port,profile.database_port):
 with socket.socket() as s:assert s.connect_ex(('127.0.0.1',port))!=0
embedded_database.start(profile)
try:
 with configured_service(settings) as service:
  principal=Principal(profile.tenant_id,profile.principal_id);brain_id=host.user_brain_id('bench-user-0')
  before=structure_map(service,principal,brain_id)
  identifier=next(node['id'][4:] for node in before['nodes'] if node['id'].startswith('msg:'))
  target={'conversation_ref':'synthetic-working-map','branch_ref':'hologram-fixture'}
  with service.database.transaction(principal) as conn:
   brain=service._brain(conn,principal,brain_id)
   assert not conn.execute('SELECT 1 FROM memory_working_states WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND conversation_id=%s AND branch_id=%s',(*service._params(principal,brain_id),*target.values())).fetchone()
   source=service._events(conn,principal,brain,event_ids=[identifier])[0]
   ref={'event_id':source['event_id'],'event_revision':source['revision'],'source_content_sha256':source['content_sha256'],'relationship':'supports','span':None}
   stamp=now()
   state={'scope':service._scope(principal,brain,target),'revision':1,'through_sequence':brain['durable_sequence'],'updated_at':stamp,
    'items':[{'key':'current_goal','value':'Review the recorded appointment schedule','knowledge_state':'inferred','evidence_refs':[ref],'expires_at':None,'updated_at':stamp},
             {'key':'confirmed_attendance','value':None,'knowledge_state':'unknown','evidence_refs':[],'expires_at':None,'updated_at':stamp}],
    'open_loops':[{'loop_id':'review_schedule','description':'Review the appointment schedule','state':'planned','due_time':{'start':None,'end':None,'precision':'unknown','basis':'unknown'},'evidence_refs':[ref],'last_updated_at':stamp}]}
   validate('WorkingState',state);service._working_save(conn,principal,brain,target,state)
  after=structure_map(service,principal,brain_id)
  working=[node for node in after['nodes'] if node['region']=='working']
  assert len(working)==4 and {node['kind'] for node in working}=={'working_state','working_item','open_loop'}
  result={'purpose':'One stored fictional working state added to the retained benchmark brain; no messages or notes removed, no model calls. Isolated branch is not the benchmark recall conversation.','before_nodes':len(before['nodes']),'after_nodes':len(after['nodes']),'before_edges':len(before['edges']),'after_edges':len(after['edges']),'working':working,'working_edges':[e for e in after['edges'] if e['type'].startswith('working_')],'state':state}
  (root/'seed-visual-working.json').write_text(json.dumps(result,indent=2));print({k:v for k,v in result.items() if k not in {'working','working_edges','state'}})
finally:embedded_database.stop(profile)
