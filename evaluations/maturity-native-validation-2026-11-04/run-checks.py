import contextlib
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from membrain import embedded_database
from membrain.cli import bootstrap
from membrain.local_profile import ensure_profile

root = Path(__file__).parent
repository = Path('/Users/yichen/tmp/membrain-review-20261029')
label = sys.argv[1]
selection = sys.argv[2:] or [
    'tests/test_storage.py::test_source_edits_do_not_rewrite_invalid_receipts_or_change_replay_semantics',
    'tests/test_recovery_quarantine.py::test_quarantine_invalidates_valid_receipts_without_rewriting_invalid_ones',
]
profile = ensure_profile(root / 'native-regression', database_engine='embedded')
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_'))
               and not key.endswith(('_API_KEY', '_API_TOKEN'))}
environment.update(MEMORY_DATABASE_URL=profile.database_url,
                   MEMORY_MIGRATION_DATABASE_URL=profile.migration_database_url,
                   PYTHON_DOTENV_DISABLED='1', MEMBRAIN_SEMANTIC='0')
for dsn in (profile.database_url, profile.migration_database_url):
    target = urlsplit(dsn)
    assert target.hostname == '127.0.0.1' and target.port == profile.database_port
files = ['src/membrain/contracts.py', 'src/membrain/native_contracts.py', 'tests/test_native_contracts.py', 'pyproject.toml', 'uv.lock', 'src/membrain/lexical_candidates.py', 'tests/test_lexical_candidates.py', 'tests/test_lexical_channel_merge.py', 'src/membrain/service.py', 'src/membrain/recovery.py',
         'tests/test_storage.py', 'tests/test_recovery_quarantine.py',
         'tests/test_response_validation.py', 'src/membrain/memory_map.py', 'src/membrain/companion_map.py', 'tests/test_memory_map.py', 'tests/test_structure_map.py', 'tests/test_companion_map.py']
hashes = {name: hashlib.sha256((repository / name).read_bytes()).hexdigest() for name in files}
report = {'purpose': 'real PostgreSQL native-response regression; not an R5 performance run',
          'label': label, 'model_calls': 0, 'source_sha256': hashes, 'selection': selection}
started = False
try:
    embedded_database.start(profile)
    started = True
    with contextlib.redirect_stdout(io.StringIO()):
        bootstrap(profile.settings(), app_password=profile.app_password)
    command = [sys.executable, '-m', 'pytest', '-q', '--tb=short', *selection]
    with (root / f'native-{label}.log').open('w') as log:
        result = subprocess.run(command, cwd=repository, env=environment, stdout=log,
                                stderr=subprocess.STDOUT, check=False)
    report['exit_code'] = result.returncode
finally:
    if started:
        embedded_database.stop(profile)
    report['source_unchanged'] = all(
        hashlib.sha256((repository / name).read_bytes()).hexdigest() == value
        for name, value in hashes.items())
    closed = []
    for port in (profile.api_port, profile.database_port):
        with socket.socket() as connection:
            connection.settimeout(.2)
            closed.append(connection.connect_ex(('127.0.0.1', port)) != 0)
    report['both_ports_closed'] = all(closed)
    (root / f'native-{label}.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
assert report['source_unchanged'] and report['both_ports_closed']
sys.exit(report['exit_code'])
