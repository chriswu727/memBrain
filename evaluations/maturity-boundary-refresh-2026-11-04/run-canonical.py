import json
import socket
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
listeners = [socket.socket(), socket.socket()]
for listener in listeners:
    listener.bind(('127.0.0.1', 0))
ports = [listener.getsockname()[1] for listener in listeners]
command = [sys.executable, 'evaluations/recall-concurrency-benchmark.py',
           '--directory', str(root / 'perf-e749a24-installation'), '--database-port', str(ports[0]),
           '--api-port', str(ports[1]), '--output', str(root / 'canonical-e749a24.json'), '--bulk-to', '0']
metadata = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'runtime_pin': 'e749a24e86d45d25d1a06d9fcba223e9adf69fcb', 'command': command}
(root / 'canonical-command.json').write_text(json.dumps(metadata, indent=2) + '\n')
for listener in listeners:
    listener.close()
result = subprocess.run(command)
metadata['exit_code'] = result.returncode
(root / 'canonical-command.json').write_text(json.dumps(metadata, indent=2) + '\n')
raise SystemExit(result.returncode)
