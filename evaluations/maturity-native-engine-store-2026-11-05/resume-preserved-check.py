import ast
import hashlib
import importlib.util
import json
import socket
from pathlib import Path

from membrain import embedded_database, native_bundle, native_engine_store, native_snapshot
from membrain.local_profile import load_profile

ROOT = Path(__file__).parent
REPO = Path('/Users/yichen/tmp/membrain-review-20261029')
attempt = ROOT / 'preserved-rollback-v2'
profile = load_profile(attempt / 'profile')
previous = json.loads((attempt / 'result.json').read_text())
assert previous['error_code'] == 'native_snapshot_space_low' and previous['ports_closed'] is True
capsule = next((attempt / 'preserved-engine').glob('postgres-*'))
saved = native_engine_store.verify(capsule, previous['original_engine_commitment'])
assert not list((attempt / 'replaceable-engine').glob('postgres-*'))
source_prefix = saved.prefix
native_bundle._cache_directory = lambda: Path('/Users/yichen/tmp/membrain-native-cache-20261104/acl-cold-install-check/cache')
target_prefix = native_bundle.prepare()
source = embedded_database._Layout(source_prefix / 'bin', profile.directory / 'postgres', profile.directory / 'postgres.log', None)
restored = embedded_database._Layout(source.binaries, profile.directory / 'snapshot-restored', profile.directory / 'restored.log', None)
spec = importlib.util.spec_from_file_location('snapshot_qualifier', REPO/'scripts/check_native_snapshot.py')
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)
tree = ast.parse((REPO/'scripts/check_native_snapshot.py').read_text())
check = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'check')
function = next(node for node in check.body if isinstance(node, ast.FunctionDef) and node.name == 'fingerprint')
environment = {'embedded_database': embedded_database, 'profile': profile, 'hashlib': hashlib, 'json': json}
exec(compile(ast.Module(body=[function], type_ignores=[]), '<unchanged qualifier fingerprint>', 'exec'), environment)
fingerprint = environment['fingerprint']

def frozen():
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests', 'scripts') for p in (REPO/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}

def closed(port):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(('127.0.0.1', port)) != 0

before_files = frozen()
original = embedded_database._installation
report = {'completed': False, 'model_calls': 0, 'phase': 'resume_initialized_owned_fixture',
          'scope': 'preserved original engine, actual upgrade and staged rollback after prior space refusal; no automatic lifecycle/admission',
          'original_engine_commitment': saved.commitment, 'original_engine_files': saved.files,
          'original_engine_bytes': saved.bytes, 'replaceable_source_unavailable': True}
assert closed(profile.api_port) and closed(profile.database_port)
try:
    embedded_database._installation = lambda: source_prefix
    embedded_database.start(profile)
    with embedded_database._admin_connection(profile, 'agent_memory') as connection:
        assert connection.execute('SHOW server_version').fetchone()[0] == '16.2'
        assert connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == '0.6.2'
        assert connection.execute('SHOW work_mem').fetchone()[0] == '8MB'
    before = fingerprint()
    embedded_database.stop(profile)
    baseline = native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES)
    configuration = (source.data/'postgresql.conf').read_bytes()
    report['phase'] = 'cold_snapshot'
    receipt = native_snapshot.create(source, attempt/'snapshot-resumed')
    assert native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES) == baseline
    report['phase'] = 'target_upgrade_and_mutation'
    embedded_database._installation = lambda: target_prefix
    embedded_database.start(profile)
    with embedded_database._admin_connection(profile, 'agent_memory') as connection:
        assert connection.execute('SHOW server_version').fetchone()[0] == '16.15'
        connection.execute("ALTER EXTENSION vector UPDATE TO '0.8.6'")
        connection.execute("UPDATE snapshot_fixture SET payload='\"changed after backup\"' WHERE id=1")
    with embedded_database._admin_connection(profile, 'postgres') as connection:
        connection.execute('ALTER ROLE snapshot_owner NOLOGIN')
    with embedded_database._admin_connection(profile, 'snapshot_secondary') as connection:
        connection.execute("UPDATE other_database SET value='changed after backup'")
    assert fingerprint() != before
    embedded_database.stop(profile)
    changed = native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES)
    report['phase'] = 'verified_stage'
    result = native_snapshot.restore(attempt/'snapshot-resumed', receipt['receipt_sha256'], restored)
    assert result['verified'] is True
    assert native_snapshot._inventory(restored.data, native_snapshot.DEFAULT_MAX_BYTES) == baseline
    assert native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES) == changed
    assert (restored.data/'postgresql.conf').read_bytes() == configuration
    report['phase'] = 'preserved_original_engine_restart'
    process = embedded_database._run(restored, 'pg_ctl', 'start', '-D', str(restored.data), '-l', str(restored.log), '-w', '-t', '90')
    assert process.returncode == 0
    assert fingerprint() == before
    with embedded_database._admin_connection(profile, 'agent_memory') as connection:
        assert connection.execute('SHOW server_version').fetchone()[0] == '16.2'
        assert connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == '0.6.2'
        assert connection.execute('SHOW work_mem').fetchone()[0] == '8MB'
    assert native_engine_store.verify(saved.directory, saved.commitment) == saved
    report.update(completed=True, phase='complete', snapshot_receipt_sha256=receipt['receipt_sha256'],
                  full_rows_roles_second_database_vector_indexes_and_nearest_restored=True,
                  complete_snapshot_metadata_verified=True, original_engine_starts_without_replaceable_source=True,
                  original_unchanged_during_snapshot=True, upgraded_cluster_preserved_during_restore=True,
                  original_sql_fingerprint=before)
except BaseException as error:
    report.update(error_type=type(error).__name__, error_code=getattr(error, 'code', None))
    raise
finally:
    qualifier.stop(restored)
    qualifier.stop(source)
    embedded_database._installation = original
    report['ports_closed'] = closed(profile.api_port) and closed(profile.database_port)
    report['source_and_checks_unchanged'] = before_files == frozen()
    report['frozen_files'] = len(before_files)
    (ROOT/'resume-result.json').write_text(json.dumps(report, indent=2)+'\n')
assert report['completed'] and report['ports_closed'] and report['source_and_checks_unchanged']
print(json.dumps(report))
