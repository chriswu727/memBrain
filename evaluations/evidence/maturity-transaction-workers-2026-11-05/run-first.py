import hashlib,json,os,socket,subprocess,sys
from pathlib import Path
from membrain import embedded_database
from membrain.local_profile import load_profile
root=Path(__file__).parent
repo=Path('/Users/yichen/tmp/membrain-review-20261029')
profile=load_profile(Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation'))
paths=[p for d in ('src','tests','.github') for p in (repo/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths.append(Path(__file__))
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
env={k:v for k,v in os.environ.items() if not k.startswith(('MEMORY_','MEMBRAIN_')) and not k.endswith(('_API_KEY','_API_TOKEN'))}
env.update(PYTHON_DOTENV_DISABLED='1',MEMBRAIN_SEMANTIC='0',MEMORY_DATABASE_URL=profile.database_url)
report={'source_sha256':hashes,'completed':False,'scope':'Transaction worker, deadline, vector handoff, response validation, HTTP lifecycle, owner isolation and idempotency guards on real PostgreSQL; model transports stubbed; no model evaluation.'}
started=False
try:
 for port in (profile.database_port,profile.api_port):
  with socket.socket() as s: assert s.connect_ex(('127.0.0.1',port))!=0
 embedded_database.start(profile);started=True
 command=[sys.executable,"-m","pytest","-q",'tests/test_recall_service_executor.py','tests/test_recall_service_transactions.py','tests/test_recall_readiness.py','tests/test_recall_executor.py','tests/test_api.py','tests/test_response_validation.py','tests/test_http_workflow.py','tests/test_vector_jobs.py','tests/test_database_isolation.py']
 with (root/'integration-guards.txt').open('w') as f:
  result=subprocess.run(command,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
 report.update(completed=True,exit_code=result.returncode)
finally:
 if started: embedded_database.stop(profile)
 report['inputs_unchanged']=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
 report['ports_closed']=True
 for port in (profile.database_port,profile.api_port):
  with socket.socket() as s: report['ports_closed'] &= s.connect_ex(('127.0.0.1',port))!=0
 (root/'integration-guards.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'}))
assert report['inputs_unchanged'] and report['ports_closed']
sys.exit(result.returncode)
