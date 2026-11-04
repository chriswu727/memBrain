import hashlib
import json
import shutil
import socket
from pathlib import Path

from membrain.local_profile import load_profile

root = Path(__file__).parent
assert json.loads((root / 'install-run-meta.json').read_text())['exit_code'] == 0
prior = Path('/Users/yichen/tmp/membrain-final-audit-20261104')
trace = Path('/Users/yichen/tmp/membrain-trace-batch-20261104')
profiles = []
for name in ('membrain-final-audit-20261104', 'membrain-tail-attribution-20261104', 'membrain-sql-recall-20261104'):
    installation = Path('/Users/yichen/tmp') / name / 'install-final'
    result = json.loads((installation / 'results.json').read_text())
    assert result['completed'] and len(result['results']) == 49 and all(row['ok'] for row in result['results'])
    profiles.extend(installation / relative for relative in (
        'home/Library/Application Support/memBrain', 'restored',
        'companion/home/Library/Application Support/memBrain', 'companion/restored'))

report = {'scope': 'stopped, completed task-owned synthetic databases only; packages, profiles, registries, model weights and archives retained',
          'free_before': shutil.disk_usage(root).free, 'profiles': []}
inventory = {}
for directory in profiles:
    assert directory.is_relative_to(Path('/Users/yichen/tmp')) and directory.parent.name in {'restored', 'companion', 'Application Support', 'install-final'}
    profile = load_profile(directory)
    cluster = directory / 'postgres'
    if not cluster.exists():
        continue
    assert not cluster.is_symlink() and not (cluster / 'postmaster.pid').exists()
    for port in (profile.api_port, profile.database_port):
        with socket.socket() as connection:
            connection.settimeout(.2)
            assert connection.connect_ex(('127.0.0.1', port)) != 0
    size = 0
    for path in cluster.rglob('*'):
        assert not path.is_symlink()
        if path.is_file():
            with path.open('rb') as stream:
                inventory[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
            size += path.stat().st_size
    private = root / 'passed-install-database-files.private.json'
    private.write_text(json.dumps(inventory, indent=2) + '\n')
    private.chmod(0o600)
    item = {'directory': str(directory), 'database_bytes': size, 'ports_closed': True, 'removed': False}
    report['profiles'].append(item)
    (root / 'passed-install-database-cleanup.json').write_text(json.dumps(report, indent=2) + '\n')
    shutil.rmtree(cluster)
    item['removed'] = True
    (root / 'passed-install-database-cleanup.json').write_text(json.dumps(report, indent=2) + '\n')
report['free_after'] = shutil.disk_usage(root).free
(root / 'passed-install-database-cleanup.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'databases_removed': len(report['profiles']), 'bytes_removed': sum(item['database_bytes'] for item in report['profiles']),
                  'free_before': report['free_before'], 'free_after': report['free_after'], 'no_model_weights_removed': True}))
