import hashlib,importlib.util,json,socket,sys,tarfile,zipfile
from pathlib import Path
root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029');target=root/'wheel-installed'
target.mkdir(exist_ok=False)
with zipfile.ZipFile(next((root/'dist').glob('*.whl'))) as z:z.extractall(target)
sys.path.insert(0,str(target))
from membrain import build_identity,embedded_database,native_transition
from membrain.local_profile import load_profile
def frozen():
 return {str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('src','tests','scripts') for p in (repo/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def closed(port):
 with socket.socket() as s:s.settimeout(.2);return s.connect_ex(('127.0.0.1',port))!=0
before=frozen();source=build_identity.package_manifest(repo/'src/membrain',repo);installed=build_identity.package_manifest(target/'membrain',target)
assert source==installed and Path(native_transition.__file__).is_relative_to(target)
with tarfile.open(next((root/'dist').glob('*.tar.gz')),'r:gz') as archive:
 prefix=archive.getnames()[0].split('/')[0]
 for name,value in source.items():
  relative='architecture/memory-contract.schema.json' if name=='resources/memory-contract.schema.json' else 'migrations/'+name.removeprefix('resources/migrations/') if name.startswith('resources/migrations/') else 'src/membrain/'+name
  assert archive.extractfile(prefix+'/'+relative).read()==value
metadata=json.loads((root/'source-fixture.json').read_text());profile=load_profile(Path(metadata['profile']));layout=native_transition.recorded_layout(profile)
spec=importlib.util.spec_from_file_location('qualifier',repo/'scripts/check_native_transition.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
report={'completed':False,'model_calls':0,'scope':'installed wheel admitted-state replay/readiness and no-rollback guard; default selector/installer handoff not adopted','build_id':build_identity.BUILD_ID,'exact_runtime_files':len(source),'native_resource_files':sum(p.is_file() for p in (target/'membrain/resources/native').iterdir()),'all_sdist_runtime_inputs_match':True,'native_transition_from_installed_wheel':True}
assert closed(profile.api_port) and closed(profile.database_port)
try:
 with native_transition.session(profile) as handle:
  assert handle.prepare()['state']=='admitted';first=q.fingerprint(profile)
  try:handle.rollback();raise AssertionError('Admission must block rollback')
  except native_transition.NativeTransitionError as e:assert e.code=='native_transition_admitted'
  assert q.fingerprint(profile)==first
 report.update(completed=True,role_catalog_vector_and_schema_certificate_verified=True,post_admission_rows_and_nearest_preserved=True,rollback_forbidden=True)
finally:
 q.stop(layout);report.update(ports_closed=closed(profile.api_port) and closed(profile.database_port),source_and_checks_unchanged=before==frozen(),frozen_files=len(before),distributions=[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((root/'dist').iterdir()) if p.name.endswith(('.whl','.tar.gz'))])
 (root/'wheel-parity.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'] and report['ports_closed'] and report['source_and_checks_unchanged']
print(json.dumps(report))
