from pathlib import Path
import json,sys,types,subprocess,dataclasses
from membrain import desktop,embedded_database,local_profile,native_transition
from membrain.desktop_connection import open_client
from membrain.recovery_profile import read_document
p=Path('/Users/yichen/tmp/membrain-native-engine-store-20261105/preserved-rollback-v2/profile')
profile=local_profile.load_profile(p);layout=native_transition.recorded_layout(profile)
assert layout is not None and layout.data.name=='snapshot-restored'
assert read_document(p/'native-transition.json')['phase']=='admitted'
report={'completed':False,'model_calls':0,'scope':'ordinary default desktop start on previously admitted nondefault data path'}
try:
 assert desktop.start(p)['ready']
 current=local_profile.load_profile(p);assert current.native_engine=='16.15'
 assert current==dataclasses.replace(profile,native_engine='16.15')
 with embedded_database._admin_connection(current,'agent_memory') as c:
  assert c.execute('SHOW server_version').fetchone()[0]=='16.15'
  assert c.execute('SELECT count(*) FROM transition_fixture').fetchone()[0]==1000
 with open_client(p,start_service=False) as client:
  observed=client.observe('My cat is called Biscuit and she hates thunder.',conversation_id='native-adoption',branch_id='main',source_event_key='default-forward-v2')
  assert observed['outcome']=='completed'
 assert desktop.stop(p)['state']=='stopped'
 assert desktop.start(p)['ready']
 with open_client(p,start_service=False) as client:
  assert 'Biscuit' in json.dumps(client.recall('what is my cat called'))
 name='membrain._frozen_9f_profile_loader';module=types.ModuleType(name);sys.modules[name]=module
 source=subprocess.check_output(['git','show','9f7536110a95dfd02b382382dc97d0991121632f:src/membrain/local_profile.py'],text=True)
 exec(compile(source,name,'exec'),module.__dict__)
 try:module.load_profile(p)
 except module.LocalProfileError:report['old_runtime_rejects_profile']=True
 else:raise AssertionError('Old runtime accepted adopted profile')
 report.update(completed=True,ordinary_api_ready=True,real_http_memory_after_cold_restart=True,existing_vector_rows=1000,adopted_profile_preserves_other_fields=True)
finally:
 desktop.stop(p)
 report['owned_ports_closed']=not desktop._port_open(profile.api_port) and not desktop._port_open(profile.database_port)
 Path('/Users/yichen/tmp/membrain-native-adoption-20261105/admitted-default-forward-v2.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
