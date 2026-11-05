import ast,hashlib,importlib.util,json,socket,time
from pathlib import Path
from membrain import embedded_database,native_snapshot
from membrain.build_identity import BUILD_ID,package_manifest,manifest_digest
from membrain.local_profile import _private,load_profile
root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029');installed=root/'wheel-installed'
assert Path(native_snapshot.__file__).is_relative_to(installed)
source=package_manifest(repo/'src/membrain',repo);wheel=package_manifest(installed/'membrain',installed)
assert source==wheel and manifest_digest(source)==BUILD_ID
hashes={p.relative_to(repo).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('src','tests','scripts') for p in (repo/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.json','.gz'} and '__pycache__' not in p.parts}
profile=load_profile(root/'local-legacy-check/profile');source_result=json.loads((root/'local-legacy-check/result.json').read_text())
receipt=json.loads((root/'local-legacy-check/snapshot/receipt.json').read_text());commitment=source_result['snapshot_receipt_sha256']
def closed(port):
 with socket.socket() as stream:
  stream.settimeout(.2);return stream.connect_ex(('127.0.0.1',port))!=0
assert closed(profile.api_port) and closed(profile.database_port)
work=root/'wheel-check';work.mkdir(mode=0o700,exist_ok=False);_private(work,directory=True)
legacy=Path(next(iter(importlib.util.find_spec('pgserver').submodule_search_locations)))/'pginstall'
layout=embedded_database._Layout(legacy/'bin',work/'staged',work/'postgres.log',None)
report={'completed':False,'model_calls':0,'scope':'installed wheel offline snapshot component only; no API or automatic upgrade acceptance','build_id':BUILD_ID,'exact_runtime_files':len(source),'native_snapshot_from_installed_wheel':True,'phase':'verify'}
tree=ast.parse((repo/'scripts/check_native_snapshot.py').read_text());function=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='fingerprint')
namespace={'embedded_database':embedded_database,'profile':profile,'hashlib':hashlib,'json':json}
exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(repo/'scripts/check_native_snapshot.py'),'exec'),namespace)
try:
 manifest=native_snapshot.verify(root/'local-legacy-check/snapshot',commitment)
 report['phase']='restore';start=time.perf_counter()
 assert native_snapshot.restore(root/'local-legacy-check/snapshot',commitment,layout)['verified']
 report['restore_ms']=(time.perf_counter()-start)*1000
 assert native_snapshot._inventory(layout.data,native_snapshot.DEFAULT_MAX_BYTES)==(manifest['root'],manifest['entries'])
 report['phase']='start_restored';result=embedded_database._run(layout,'pg_ctl','start','-D',str(layout.data),'-l',str(layout.log),'-w','-t','90',timeout=120);assert result.returncode==0
 assert namespace['fingerprint']()==source_result['original_fingerprint']
 with embedded_database._admin_connection(profile,'agent_memory') as connection:
  assert connection.execute('SHOW server_version').fetchone()[0]=='16.2'
  assert connection.execute('SHOW work_mem').fetchone()[0]=='8MB'
 report.update(completed=True,complete_snapshot_metadata_matches=True,original_engine_rows_roles_second_database_and_indexes_match=True)
except BaseException as error:
 report.update(error_type=type(error).__name__,error_code=getattr(error,'code',None));raise
finally:
 try:
  if (layout.data/'PG_VERSION').exists() and embedded_database._run(layout,'pg_ctl','status','-D',str(layout.data),timeout=30).returncode==0:
   assert embedded_database._run(layout,'pg_ctl','stop','-D',str(layout.data),'-m','fast','-w','-t','60',timeout=90).returncode==0
 except Exception as error:report.update(completed=False,cleanup_error_type=type(error).__name__)
 report['ports_closed']=closed(profile.api_port) and closed(profile.database_port)
 report['source_and_checks_unchanged']=all(hashlib.sha256((repo/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
 report['frozen_files']=len(hashes);report['completed']=report['completed'] and report['ports_closed'] and report['source_and_checks_unchanged'];report['phase']='complete' if report['completed'] else report['phase']
 (work/'result.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'];print(json.dumps(report))
