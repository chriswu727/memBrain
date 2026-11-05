import ast
import hashlib
import importlib.util
import json
import socket
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
REPO = Path('/Users/yichen/tmp/membrain-review-20261029')
TARGET = ROOT/'wheel-installed'
TARGET.mkdir(exist_ok=False)
with zipfile.ZipFile(next((ROOT/'dist-guard').glob('*.whl'))) as archive:
    archive.extractall(TARGET)
sys.path.insert(0, str(TARGET))
from membrain import build_identity, embedded_database, native_engine_store
from membrain.local_profile import load_profile

def frozen():
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src','tests','scripts') for p in (REPO/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}

def closed(port):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(('127.0.0.1',port)) != 0

before = frozen()
source = build_identity.package_manifest(REPO/'src/membrain', REPO)
installed = build_identity.package_manifest(TARGET/'membrain', TARGET)
assert source == installed and Path(native_engine_store.__file__).is_relative_to(TARGET)
previous = json.loads((ROOT/'resume-result.json').read_text())
attempt = ROOT/'preserved-rollback-v2'
capsule = next((attempt/'preserved-engine').glob('postgres-*'))
saved = native_engine_store.verify(capsule, previous['original_engine_commitment'])
profile = load_profile(attempt/'profile')
layout = embedded_database._Layout(saved.prefix/'bin', profile.directory/'snapshot-restored', profile.directory/'installed-store.log', None)
spec = importlib.util.spec_from_file_location('qualifier', REPO/'scripts/check_native_snapshot.py')
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)
tree = ast.parse((REPO/'scripts/check_native_snapshot.py').read_text())
check = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == 'check')
function = next(n for n in check.body if isinstance(n,ast.FunctionDef) and n.name == 'fingerprint')
environment = {'profile':profile,'embedded_database':embedded_database,'hashlib':hashlib,'json':json}
exec(compile(ast.Module(body=[function],type_ignores=[]),'<unchanged qualifier fingerprint>','exec'),environment)
assert closed(profile.api_port) and closed(profile.database_port)
report = {'completed':False,'model_calls':0,
          'scope':'installed wheel engine verification and real preserved-engine restart; no automatic transition or final installation acceptance',
          'build_id':build_identity.BUILD_ID,'exact_runtime_files':len(source),
          'native_resource_files':sum(p.is_file() for p in (TARGET/'membrain/resources/native').iterdir()),
          'engine_store_from_installed_wheel':True,'original_engine_files':saved.files,
          'original_engine_commitment':saved.commitment}
try:
    result = embedded_database._run(layout,'pg_ctl','start','-D',str(layout.data),'-l',str(layout.log),'-w','-t','90')
    assert result.returncode == 0
    assert environment['fingerprint']() == previous['original_sql_fingerprint']
    with embedded_database._admin_connection(profile,'agent_memory') as connection:
        assert connection.execute('SHOW server_version').fetchone()[0] == '16.2'
        assert connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == '0.6.2'
        assert connection.execute('SHOW work_mem').fetchone()[0] == '8MB'
    report.update(completed=True,original_engine_restart_and_complete_sql_fingerprint_verified=True)
finally:
    qualifier.stop(layout)
    report.update(ports_closed=closed(profile.api_port) and closed(profile.database_port),
                  source_and_checks_unchanged=before==frozen(),frozen_files=len(before),
                  distributions=[{'name':p.name,'bytes':p.stat().st_size,
                    'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in sorted((ROOT/'dist-guard').iterdir()) if p.name.endswith(('.whl','.tar.gz'))])
    (ROOT/'wheel-parity.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'] and report['ports_closed'] and report['source_and_checks_unchanged']
print(json.dumps(report))
