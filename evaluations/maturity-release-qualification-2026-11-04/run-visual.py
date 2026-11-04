import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from membrain.local_profile import load_profile

root = Path(__file__).parent
repository = Path('/Users/yichen/tmp/membrain-review-20261029')
canonical = json.loads((root / 'canonical-command.json').read_text())
assert canonical['exit_code'] == 0 and canonical['source_unchanged'] and canonical['both_ports_closed']
hashes = canonical['source_sha256']
assert all(hashlib.sha256((repository / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
script = root / 'compare-visual-permissions.py'
script_hash = hashlib.sha256(script.read_bytes()).hexdigest()
metadata = {'source_commit': canonical['source_commit'], 'runtime_pin': canonical['runtime_pin'],
            'script_sha256': script_hash, 'completed': False,
            'protocol': 'unchanged complete closed/open/open/closed workload; added phase API port to output for independent shutdown checks'}
path = root / 'visual-command.json'
path.write_text(json.dumps(metadata, indent=2) + '\n')
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_'))
               and not key.endswith(('_API_KEY', '_API_TOKEN')) and key != 'PYTHONPATH'}
environment.update(MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
result = subprocess.run([sys.executable, str(script)], cwd=repository, env=environment)
metadata.update(completed=True, exit_code=result.returncode)
metadata['source_unchanged'] = all(hashlib.sha256((repository / name).read_bytes()).hexdigest() == value
                                   for name, value in hashes.items())
metadata['script_unchanged'] = hashlib.sha256(script.read_bytes()).hexdigest() == script_hash
profile = load_profile(root / 'perf-b994ec8-installation')
report = json.loads((root / 'visual-permissions-abba.json').read_text())
ports = {profile.api_port, profile.database_port} | {phase['api_port'] for phase in report['phases']}
metadata['all_ports_closed'] = True
for port in ports:
    with socket.socket() as connection:
        connection.settimeout(.2)
        metadata['all_ports_closed'] &= connection.connect_ex(('127.0.0.1', port)) != 0
path.write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata))
assert metadata['source_unchanged'] and metadata['script_unchanged'] and metadata['all_ports_closed']
sys.exit(result.returncode)
