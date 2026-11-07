import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from membrain.local_profile import load_profile

root = Path(__file__).parent
repository = Path('/Users/yichen/tmp/membrain-review-20261029')
directory = root / 'perf-native-installation'
assert not directory.exists()
assert shutil.disk_usage(root).free > 1_800_000_000
paths = [path for folder in ('src', 'tests', 'plugins', 'integrations')
         for path in (repository / folder).rglob('*')
         if path.is_file() and '__pycache__' not in path.parts and 'node_modules' not in path.parts]
paths += [repository / name for name in ('pyproject.toml', 'uv.lock',
                                        'evaluations/recall-concurrency-benchmark.py')]
hashes = {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
listeners = [socket.socket(), socket.socket()]
for listener in listeners:
    listener.bind(('127.0.0.1', 0))
ports = [listener.getsockname()[1] for listener in listeners]
command = [sys.executable, 'evaluations/recall-concurrency-benchmark.py',
           '--directory', str(directory), '--database-port', str(ports[0]),
           '--api-port', str(ports[1]), '--output', str(root / 'canonical-native.json'), '--bulk-to', '0']
metadata = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
            'runtime_pin': '1ca3cb23381650e245c8320906b9c467a9e3ecd7', 'command': command,
            'source_sha256': hashes, 'disk_free_before': shutil.disk_usage(root).free}
output = root / 'canonical-command.json'
output.write_text(json.dumps(metadata, indent=2) + '\n')
for listener in listeners:
    listener.close()
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_'))
               and not key.endswith(('_API_KEY', '_API_TOKEN')) and key != 'PYTHONPATH'}
environment.update(MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
result = subprocess.run(command, cwd=repository, env=environment)
metadata['exit_code'] = result.returncode
metadata['source_unchanged'] = all(hashlib.sha256((repository / name).read_bytes()).hexdigest() == value
                                     for name, value in hashes.items())
closed = []
for port in ports:
    with socket.socket() as connection:
        connection.settimeout(.2)
        closed.append(connection.connect_ex(('127.0.0.1', port)) != 0)
metadata['both_ports_closed'] = all(closed)
metadata['disk_free_after'] = shutil.disk_usage(root).free
output.write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps({key: value for key, value in metadata.items() if key != 'source_sha256'}))
assert metadata['source_unchanged'] and metadata['both_ports_closed']
sys.exit(result.returncode)
