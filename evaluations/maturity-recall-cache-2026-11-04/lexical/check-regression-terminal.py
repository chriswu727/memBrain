import hashlib,json,socket
from pathlib import Path
from membrain.local_profile import load_profile
root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029')
log=(root/'final-regressions.log').read_text();assert '268 passed in 19.73s' in log and 'skipped' not in log
ports=[];checked=[]
for path in (root/'pytest-final').rglob('profile.json'):
 if not (path.parent/'postgres/PG_VERSION').is_file():continue
 p=load_profile(path.parent);assert not (p.directory/'postgres/postmaster.pid').exists();ports.extend((p.database_port,p.api_port));checked.append(str(p.directory))
p=load_profile(Path('/Users/yichen/tmp/membrain-attribution-d4f-20261104/failed-corpus-copy'));ports.extend((p.database_port,p.api_port));assert not (p.directory/'postgres/postmaster.pid').exists()
for port in ports:
 with socket.socket() as s:s.settimeout(.2);assert s.connect_ex(('127.0.0.1',port))!=0
report={'purpose':'independent terminal inspection after pytest completed successfully but wrapper failed reading a deliberately malformed no-database profile','pytest_passed':268,'pytest_skipped':0,'pytest_seconds':19.73,'original_wrapper_exit_code':1,'postcheck_completed':True,'owned_database_profiles_checked':len(checked)+1,'owned_port_checks':len(ports),'ports_closed':True,'pre_run_hash_receipt':'original wrapper did not persist it before its postcheck error; not reconstructed as proof','post_run_source_sha256':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('src','tests') for p in (repo/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}}
(root/'final-regression-terminal.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='post_run_source_sha256'}))
