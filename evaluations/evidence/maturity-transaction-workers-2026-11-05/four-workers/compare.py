import hashlib
import json
import os
import socket
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from membrain import embedded_database, host
from membrain.client import MemoryClient
from membrain.local_profile import load_profile

ROOT = Path(__file__).parent
REPO = Path('/Users/yichen/tmp/membrain-review-20261029')
DIRECTORY = Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation')
profile = load_profile(DIRECTORY)
assert profile.settings().cognition_base_url is None and profile.settings().embedding_base_url is None
environment = {k:v for k,v in os.environ.items() if not k.startswith(('MEMORY_', 'MEMBRAIN_'))
               and not k.endswith(('_API_KEY', '_API_TOKEN'))}
environment.update(PYTHON_DOTENV_DISABLED='1', MEMBRAIN_SEMANTIC='0')
BOOT = '''
import sys
from pathlib import Path
import uvicorn
from membrain.api import create_app
from membrain.local_profile import load_profile
uvicorn.run(create_app(load_profile(Path(sys.argv[1])).settings()), host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
'''
paths = [p for folder in ('src', 'tests') for p in (REPO/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths.extend([Path(__file__), ROOT/'worker.py'])
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report = {'purpose': 'Experimental complete recall transaction in four initialized service processes versus the current API-thread collection and two compute workers; full HTTP ABBA; not R5 or production implementation. Prototype lacks production queue-deadline, worker-recovery and lifecycle interfaces; no production adoption implied.',
          'completed': False, 'model_calls': 0, 'source_sha256': hashes, 'groups': []}
expected = {}
original = host._boundaries
process = None
started = False
log = None
port = None


def full_relationship(client):
    return list((host._relationship(client) or {}).get('boundaries') or [])


def worker(index):
    rows = []
    with MemoryClient(base, profile.api_key, brain_id=host.user_brain_id(f'bench-user-{index}'), trust_env=False) as client:
        for n in range(21):
            query = n % 20
            begin = time.perf_counter()
            context = host.recall_context(client, f'What is the appointment for project{query:04d}?', current_conversation='benchmark')
            elapsed = (time.perf_counter()-begin)*1000
            assert context
            rows.append({'brain': index, 'query': query, 'warmup': n == 0, 'wall_ms': elapsed,
                         'context_sha256': hashlib.sha256(context.encode()).hexdigest(), 'characters': len(context)})
    return rows


try:
    for p in (profile.database_port, profile.api_port):
        with socket.socket() as s:
            assert s.connect_ex(('127.0.0.1', p)) != 0
    embedded_database.start(profile)
    started = True
    for phase, mode in [('before', 'inline'), ('after', 'process'), ('after', 'process'), ('before', 'inline')]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        log = (ROOT/f'api-{len(report["groups"])}-{mode}.log').open('w')
        process = subprocess.Popen([sys.executable, str(ROOT/'worker.py'), str(DIRECTORY), str(port), mode],
                                   env=environment, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
        with httpx.Client(trust_env=False) as control:
            deadline = time.monotonic()+45
            while True:
                assert process.poll() is None
                try:
                    if control.get(base+'/health', timeout=.5).status_code==200:
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic()<deadline
                time.sleep(.1)
        for kind, indices in [('serial', [0]), ('same_brain', [0]*8), ('eight_brains', list(range(8)))]:
            with ThreadPoolExecutor(max_workers=len(indices)) as pool:
                rows = [row for part in pool.map(worker, indices) for row in part]
            for row in rows:
                key = row['brain'], row['query']
                assert expected.setdefault(key, row['context_sha256'])==row['context_sha256'], f'Context changed at {key}'
            samples = sorted(row['wall_ms'] for row in rows if not row['warmup'])
            processes = [tuple(map(int, line.split())) for line in subprocess.check_output(['ps', '-axo', 'pid=,ppid=,rss='], text=True).splitlines()]
            owned = {process.pid}
            while True:
                extra = {pid for pid, parent, rss in processes if parent in owned} - owned
                if not extra: break
                owned.update(extra)
            rss_kib = sum(rss for pid, parent, rss in processes if pid in owned)
            group = {'api_and_worker_rss_kib': rss_kib, 'phase': phase, 'kind': kind, 'n': len(samples), 'p95_ms': samples[int(.95*(len(samples)-1))],
                     'median_ms': statistics.median(samples), 'results': rows}
            report['groups'].append(group)
            (ROOT/'process-comparison.json').write_text(json.dumps(report, indent=2))
            print(json.dumps({k:v for k,v in group.items() if k!='results'}), flush=True)
        process.terminate()
        process.wait(timeout=20)
        log.close()
        with socket.socket() as s:
            assert s.connect_ex(('127.0.0.1', port)) != 0
    report['equivalent_contexts'] = len(expected)
    report['completed'] = True
finally:
    host._boundaries = original
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        report['api_exit_code'] = process.returncode
    if log is not None:
        log.close()
    if started:
        embedded_database.stop(profile)
    report['ports_closed'] = True
    for p in {profile.database_port, profile.api_port, port} - {None}:
        with socket.socket() as s:
            report['ports_closed'] &= s.connect_ex(('127.0.0.1', p)) != 0
    report['source_and_driver_unchanged'] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    (ROOT/'process-comparison.json').write_text(json.dumps(report, indent=2))
assert report['completed'] and report['ports_closed'] and report['source_and_driver_unchanged']
