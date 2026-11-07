import hashlib
import importlib.util
import json
import socket
import sys
import zipfile
from pathlib import Path

ROOT = Path('/Users/yichen/tmp/membrain-native-environment-20261105')
REPO = Path('/Users/yichen/tmp/membrain-review-20261029')
TARGET = ROOT / 'wheel-installed'
wheel = next((ROOT / 'dist').glob('*.whl'))
TARGET.mkdir(exist_ok=False)
with zipfile.ZipFile(wheel) as archive:
    archive.extractall(TARGET)
sys.path.insert(0, str(TARGET))
from membrain import build_identity, embedded_database, native_maintenance
from membrain.local_profile import load_profile

def frozen():
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests', 'scripts') for p in (REPO / folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}

def closed(port):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(('127.0.0.1', port)) != 0

report = {'completed': False, 'model_calls': 0,
          'scope': 'installed wheel SQL maintenance repeated against previously qualified fixture; no API or default startup adoption'}
before = frozen()
source = build_identity.package_manifest(REPO / 'src/membrain', REPO)
installed = build_identity.package_manifest(TARGET / 'membrain', TARGET)
assert source == installed
assert Path(native_maintenance.__file__).is_relative_to(TARGET)
report.update(exact_runtime_files=len(source), build_id=build_identity.BUILD_ID,
              native_resource_files=sum(n.startswith('resources/native/') for n in installed),
              native_maintenance_from_installed_wheel=True)
spec = importlib.util.spec_from_file_location('qualifier', REPO / 'scripts/check_native_maintenance.py')
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)
cache = Path('/Users/yichen/tmp/membrain-native-cache-20261104/acl-cold-install-check/cache')
qualifier.choose(cache)
profile = load_profile(Path('/Users/yichen/tmp/membrain-native-maintenance-20261105/local-check-v5/profile'))
layout = embedded_database._layout(profile)
journal = json.loads((layout.data.parent / '.native-maintenance/catalog.json').read_text())
assert closed(profile.api_port) and closed(profile.database_port)
try:
    embedded_database.start(profile)
    flags = qualifier.flags(profile)
    fingerprint = qualifier.fingerprint(profile)
    status = native_maintenance.maintain(profile, layout, Path('/Users/yichen/tmp/membrain-native-maintenance-20261105/local-check-v5/snapshot'),
                                        journal['snapshot_receipt_sha256'], journal['operation_id'])
    assert status['state'] == 'complete' and status['database_count'] == 5
    assert flags == qualifier.flags(profile) and fingerprint == qualifier.fingerprint(profile)
    assert qualifier.statistics_visible(profile) == [0, 0]
    embedded_database.stop(profile)
    embedded_database.start(profile)
    assert flags == qualifier.flags(profile) and fingerprint == qualifier.fingerprint(profile)
    assert qualifier.statistics_visible(profile) == [0, 0]
    report.update(completed=True, complete_rows_and_nearest_results_preserved=True,
                  catalog_role_protection_verified=True, repeat_and_restart_verified=True)
finally:
    embedded_database.stop(profile)
    report['ports_closed'] = closed(profile.api_port) and closed(profile.database_port)
    report['source_and_checks_unchanged'] = before == frozen()
    report['frozen_files'] = len(before)
    assert report['source_and_checks_unchanged'] and report['ports_closed']
    report['distributions'] = [{'name': p.name, 'bytes': p.stat().st_size,
                                'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                               for p in sorted((ROOT / 'dist').iterdir())]
    (ROOT / 'wheel-parity.json').write_text(json.dumps(report, indent=2) + '\n')
assert report['completed']
print(json.dumps(report))
