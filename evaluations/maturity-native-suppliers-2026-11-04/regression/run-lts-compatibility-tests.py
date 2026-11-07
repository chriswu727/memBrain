import hashlib
import json
import os
import socket
from pathlib import Path

import pytest
from membrain import embedded_database, local_profile

root=Path(__file__).parent
repo=Path('/Users/yichen/tmp/membrain-review-20261029')
assert json.loads((root/'upgrade-lts-vector-result.json').read_text())['completed']
for name in list(os.environ):
 if name.startswith(('MEMORY_', 'MEMBRAIN_')) or name.endswith(('_API_KEY','_API_TOKEN')):
  del os.environ[name]
os.environ.update(MEMBRAIN_SEMANTIC='0',PYTHON_DOTENV_DISABLED='1',MEMORY_DESKTOP_E2E='1')
original_installation=embedded_database._installation
embedded_database._installation=lambda:root/'lts-macos-relocated/pginstall'
original_ensure=local_profile.ensure_profile

def ensure(*args,**kwargs):
 kwargs.setdefault('database_engine','embedded')
 return original_ensure(*args,**kwargs)

local_profile.ensure_profile=ensure
from membrain import desktop

def no_docker(profile,*args):
 assert args==('down','--volumes'),args
 embedded_database.stop(profile)

desktop._compose=no_docker
profile=ensure(root/'lts-native-regression')
paths=[p for p in (repo/'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += list((repo/'tests').glob('test_*.py'))
hashes={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report={'purpose':'existing backend/companion and complete recovery checks with PostgreSQL 16.15 native binaries selected in the harness; not unchanged Docker CI or distributed-wheel acceptance','engine':'16.15','vector':'0.8.6','openssl':'3.5.9','bundle_sha256':'ddd1718406bd4bd7a9ead19afc01a63fa29687264df81be6db90eb7ab89f558c','model_calls':0,'source_sha256':hashes,'completed':False,'tests':[],'adaptations':['harness selects locally built pginstall and defaults newly created profiles to embedded','Docker down cleanup stops only the owned embedded cluster; no Docker command or source test edited']}
(root/'lts-compatibility-pre-run.json').write_text(json.dumps(report,indent=2)+'\n')
started=False
try:
 desktop._prepare_database(profile);started=True
 os.environ.update(MEMORY_DATABASE_URL=profile.database_url,MEMORY_MIGRATION_DATABASE_URL=profile.migration_database_url)
 targets=['tests/test_storage.py','tests/test_database_isolation.py','tests/test_http_workflow.py','tests/test_companion_map.py','tests/test_persona.py','tests/test_persona_growth.py','tests/test_affect.py','tests/test_mood.py','tests/test_relationship.py','tests/test_recovery_erasure.py','tests/test_recovery_quarantine.py','tests/test_desktop_recovery_e2e.py','tests/test_embedded_database.py::test_embedded_installation_starts_without_docker_and_keeps_memory_across_restarts']
 results=report
 class Results:
  def pytest_runtest_logreport(self,report):
   result=report
   if result.when=='call' or result.failed or result.skipped:
    results['tests'].append({'id':result.nodeid,'when':result.when,'outcome':result.outcome})
 code=pytest.main(['-q','--basetemp',str(root/'pytest-lts-native-16_15'),*targets],plugins=[Results()])
 report.update(completed=True,exit_code=int(code),source_unchanged=all(hashlib.sha256((repo/name).read_bytes()).hexdigest()==value for name,value in hashes.items()))
finally:
 if started:embedded_database.stop(profile)
 local_profile.ensure_profile=original_ensure
 embedded_database._installation=original_installation
 ports=[]
 for path in (root/'pytest-lts-native-16_15').rglob('profile.json'):
  test_profile=local_profile.load_profile(path.parent)
  ports.extend([test_profile.api_port,test_profile.database_port])
 ports += [profile.api_port,profile.database_port]
 report['all_owned_ports_closed']=True
 for port in ports:
  with socket.socket() as connection:
   connection.settimeout(.2)
   report['all_owned_ports_closed'] &= connection.connect_ex(('127.0.0.1',port)) != 0
 report['owned_port_checks']=len(ports)
 (root/'lts-compatibility-result.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'] and report['exit_code']==0 and report['source_unchanged'] and report['all_owned_ports_closed']
