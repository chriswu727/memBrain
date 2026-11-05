import hashlib
import json
import os
import socket
from pathlib import Path
import pytest
from membrain import embedded_database
from membrain.local_profile import load_profile

root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029')
profile=load_profile(Path('/Users/yichen/tmp/membrain-attribution-d4f-20261104/failed-corpus-copy'))
paths=[p for folder in ('src','tests') for p in (repo/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
hashes={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report={'purpose':'PostgreSQL-backed lexical/runtime/privacy and embedded-default upgrade regressions','completed':False,'tests':[],'source_sha256':hashes,'model_calls':0}
for key in list(os.environ):
 if key.startswith(('MEMORY_','MEMBRAIN_')) or key.endswith(('_API_KEY','_API_TOKEN')):del os.environ[key]
os.environ.update(MEMBRAIN_SEMANTIC='0',PYTHON_DOTENV_DISABLED='1',MEMORY_DATABASE_URL=profile.database_url,MEMORY_MIGRATION_DATABASE_URL=profile.migration_database_url)
class Results:
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed or report.skipped:results.append({'id':report.nodeid,'when':report.when,'outcome':report.outcome})
results=report['tests'];started=False
try:
 embedded_database.start(profile);started=True
 targets=['tests/test_embedded_database.py','tests/test_lexical_candidates.py','tests/test_cognition.py','tests/test_candidates.py','tests/test_retrieval.py','tests/test_source_context.py','tests/test_source_passages.py','tests/test_source_candidates.py','tests/test_native_contracts.py','tests/test_contracts.py','tests/test_storage.py','tests/test_database_isolation.py','tests/test_companion_map.py']
 targets=[name for name in targets if (repo/name).is_file()]
 report['targets']=targets
 code=pytest.main(['-q','--basetemp',str(root/'pytest-final'),*targets],plugins=[Results()])
 report.update(completed=True,exit_code=int(code),source_unchanged=all(hashlib.sha256((repo/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items()))
finally:
 if started:embedded_database.stop(profile)
 ports=[profile.database_port,profile.api_port]
 for p in (root/'pytest-final').rglob('profile.json'):
  from membrain.local_profile import load_profile
  p=load_profile(p.parent);ports.extend([p.database_port,p.api_port])
 report['owned_port_checks']=len(ports);report['ports_closed']=True
 for port in ports:
  with socket.socket() as s:report['ports_closed'] &= s.connect_ex(('127.0.0.1',port))!=0
 (root/'final-regressions.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'] and report['exit_code']==0 and report['source_unchanged'] and report['ports_closed'] and not any(row['outcome']=='skipped' for row in results)
