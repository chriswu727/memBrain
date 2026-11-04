import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
python = Path('/Users/yichen/tmp/membrain-tail-attribution-20261104/install-final/uv-tools/membrain-ai/bin/python')
directory = root / 'sdk-live-installation'
connection = root / 'sdk-live-connection.json'
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_')) and not key.endswith(('_API_KEY', '_API_TOKEN'))}
environment.pop('PYTHONPATH', None)
environment.update(MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
boot = '''
import json,os,sys
from pathlib import Path
from membrain import host
from membrain.local_profile import load_profile
directory=Path(sys.argv[1])
host.start(directory)
profile=load_profile(directory)
descriptor=os.open(sys.argv[2],os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(descriptor,'w') as stream:
    json.dump({'baseUrl':profile.base_url,'apiKey':profile.api_key,'brainId':profile.brain_id},stream)
'''
report = {'runtime_pin': 'd4d71262ab1c7d76600082b9c53b10144bb08a00', 'completed': False,
          'sdk_sha256': hashlib.sha256(Path('sdk/typescript/index.ts').read_bytes()).hexdigest()}
try:
    subprocess.run([str(python), '-c', boot, str(directory), str(connection)], env=environment, check=True)
    result = subprocess.run(['node', str(root / 'sdk-live.mjs'), str(connection), str(root / 'sdk-live-checks.json')],
                            env=environment, timeout=180)
    report['node_returncode'] = result.returncode
    report['completed'] = result.returncode == 0
finally:
    stopped = subprocess.run([str(python), '-m', 'membrain.cli', 'desktop', 'stop', '--directory', str(directory)],
                             env=environment, capture_output=True, text=True)
    report['stop_returncode'] = stopped.returncode
    from membrain.local_profile import load_profile

    profile = load_profile(directory)
    report['ports_closed'] = {}
    for name, port in [('api', profile.api_port), ('database', profile.database_port)]:
        with socket.socket() as listener:
            listener.settimeout(.2)
            report['ports_closed'][name] = listener.connect_ex(('127.0.0.1', port)) != 0
    (root / 'sdk-live-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
raise SystemExit(0 if report['completed'] and stopped.returncode == 0 and all(report['ports_closed'].values()) else 1)
