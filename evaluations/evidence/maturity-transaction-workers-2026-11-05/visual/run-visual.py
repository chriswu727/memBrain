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
profile = load_profile(Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation'))
paths = [p for folder in ('src', 'tests', 'plugins', 'integrations', 'scripts', 'migrations', 'architecture', '.github')
         for p in (repository/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'node_modules' not in p.parts]
paths += [repository/'pyproject.toml', repository/'uv.lock', Path(__file__), root/'compare-visual-permissions.py']
paths += [Path('/Users/yichen/tmp/membrain-working-map-20261105/seed-visual-working.json'), Path('/Users/yichen/tmp/membrain-working-map-20261105/seed-visual-working.py')]
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
metadata = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
            'runtime_pin': 'f7662854dec82df6251c695fb7cd7a18878e4bed', 'source_sha256': hashes,
            'completed': False, 'reuses_owned_synthetic_corpus': True,
            'protocol': 'Existing closed/open/open/closed driver; output root/runtime updated; retained fixture still includes the same four stored working nodes and five membership/evidence edges from the preceding run. Fresh API per phase, three cycles per phase, hardware renderer and normal polling; all failures retained.'}
path = root/'visual-command.json'
path.write_text(json.dumps(metadata, indent=2))
for port in (profile.api_port, profile.database_port):
    with socket.socket() as s:
        assert s.connect_ex(('127.0.0.1', port)) != 0
environment = {k:v for k,v in os.environ.items() if not k.startswith(('MEMORY_', 'MEMBRAIN_'))
               and not k.endswith(('_API_KEY', '_API_TOKEN')) and k != 'PYTHONPATH'}
environment.update(MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
result = subprocess.run([sys.executable, str(root/'compare-visual-permissions.py')], cwd=repository, env=environment)
metadata.update(completed=True, exit_code=result.returncode)
metadata['source_and_driver_unchanged'] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
report = json.loads((root/'visual-permissions-abba.json').read_text())
ports = {profile.api_port, profile.database_port} | {phase['api_port'] for phase in report['phases']}
metadata['all_ports_closed'] = True
for port in ports:
    with socket.socket() as s:
        metadata['all_ports_closed'] &= s.connect_ex(('127.0.0.1', port)) != 0
path.write_text(json.dumps(metadata, indent=2))
print(json.dumps({k:v for k,v in metadata.items() if k!='source_sha256'}))
assert metadata['source_and_driver_unchanged'] and metadata['all_ports_closed']
sys.exit(result.returncode)
