import json
import hashlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent
output = root / 'public-practice-v2'
output.mkdir(exist_ok=False)
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_', 'C5_'))
               and not key.endswith(('_API_KEY', '_API_TOKEN'))}
environment.update(C5_STUB='1', MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
report = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'runtime_pin': 'e749a24e86d45d25d1a06d9fcba223e9adf69fcb',
          'protocol': 'Public practice only; deterministic host/extractor stubs; keyword recall; no model cache, '
                      'provider credential or live request. Harness refuses non-loopback sockets.',
          'completed': False, 'arms': {}, 'tested_harness_sha256': hashlib.sha256(Path('evaluations/c5-harness.py').read_bytes()).hexdigest(), 'working_tree_change': 'remove obsolete private cache invalidation after page actions'}
processes, logs = {}, []
try:
    for arm in ('P', 'E', 'F'):
        directory = output / ('practice-' + arm)
        directory.mkdir()
        selected = dict(environment)
        if arm != 'F':
            listeners = [socket.socket(), socket.socket()]
            for listener in listeners:
                listener.bind(('127.0.0.1', 0))
            ports = [listener.getsockname()[1] for listener in listeners]
            for listener in listeners:
                listener.close()
            selected['MEMBRAIN_PORTS'] = ','.join(map(str, ports))
        log = (directory / 'run.log').open('w')
        logs.append(log)
        command = [sys.executable, '-u', 'evaluations/c5-harness.py', arm,
                   'evaluations/c5-practice-scenario.py', str(directory)]
        processes[arm] = subprocess.Popen(command, env=selected, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 600
    while any(process.poll() is None for process in processes.values()):
        if any(process.poll() not in (None, 0) for process in processes.values()):
            raise RuntimeError('A public stub arm failed; sibling work stops')
        if time.monotonic() > deadline:
            raise RuntimeError('Public stub rehearsal timed out')
        time.sleep(.2)
    assert all(process.returncode == 0 for process in processes.values())
    report['completed'] = True
finally:
    for arm, process in processes.items():
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        report['arms'][arm] = {'returncode': process.returncode}
    for log in logs:
        log.close()
    (root / 'public-practice-v2-result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
raise SystemExit(0 if report['completed'] else 1)
