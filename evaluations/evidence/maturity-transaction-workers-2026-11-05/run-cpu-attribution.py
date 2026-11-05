import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psycopg
from psycopg.rows import dict_row

from membrain import embedded_database, host
from membrain.client import MemoryClient
from membrain.local_profile import load_profile

root = Path(__file__).parent
repository = Path('/Users/yichen/tmp/membrain-review-20261029')
directory = Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation')
profile = load_profile(directory)
settings = profile.settings()
assert settings.cognition_base_url is None and settings.embedding_base_url is None
from membrain.local_embeddings import complete
assert not complete(Path(settings.embedding_local_directory))
for dsn in (profile.database_url, profile.migration_database_url):
    target = urlsplit(dsn)
    assert target.hostname == '127.0.0.1' and target.port == profile.database_port
for port in (profile.database_port, profile.api_port):
    with socket.socket() as connection:
        assert connection.connect_ex(('127.0.0.1', port)) != 0
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_'))
               and not key.endswith(('_API_KEY', '_API_TOKEN'))}
environment.update(PYTHON_DOTENV_DISABLED='1', MEMBRAIN_SEMANTIC='0')
hashes = {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in (repository / 'src').rglob('*')
          if path.is_file() and '__pycache__' not in path.parts}
report = {'purpose': 'Concurrent full request stage attribution on retained synthetic corpus; not R5 qualification',
          'reuses_owned_failed_synthetic_corpus': True, 'postgres_version': '16.15', 'model_calls': 0, 'source_sha256': hashes, 'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip(),
          'limitations': 'Instrumentation adds overhead; SQL wall includes scheduling and server waits; inclusive categories overlap. No browser, no release timing bar. GC policy is unchanged.',
          'completed': False, 'groups': [], 'driver_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.py')}}
process = None
api_log = None
started = False
try:
    embedded_database.start(profile)
    started = True
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    api_log = (root / 'cpu-attribution-api.log').open('w')
    process = subprocess.Popen([sys.executable, str(root / 'cpu-attribution-worker.py'), str(directory), str(port)],
                               env=environment, cwd=repository, stdout=api_log, stderr=subprocess.STDOUT)
    with httpx.Client(trust_env=False, timeout=30) as control:
        deadline = time.monotonic() + 30
        while True:
            assert process.poll() is None, 'instrumented API exited before readiness'
            try:
                if control.get(base + '/health', timeout=.5).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            assert time.monotonic() < deadline, 'API readiness timed out'
            time.sleep(.1)
        clients = [MemoryClient(base, profile.api_key, brain_id=host.user_brain_id(f'bench-user-{i}'),trust_env=False) for i in range(8)]
        try:
            for label, indices, rounds in [('warmup_serial', [0], 3), ('eight_brain_1', list(range(8)), 20), ('eight_brain_2', list(range(8)), 20)]:
                before = control.get(base + '/__diagnostic/snapshot?reset=true').json()
                begin = time.perf_counter()
                def worker(index):
                    records = []
                    for query_index in range(rounds):
                        wall = time.perf_counter()
                        context = host.recall_context(clients[index], f'What is the appointment for project{query_index:04d}?', current_conversation='benchmark')
                        assert context
                        records.append({'brain_index': index, 'query_index': query_index, 'wall_ms': (time.perf_counter()-wall)*1000,
                                        'context_sha256': hashlib.sha256(context.encode()).hexdigest(), 'context_characters': len(context)})
                    return records
                with ThreadPoolExecutor(max_workers=len(indices)) as pool:
                    records = [row for part in pool.map(worker, indices) for row in part]
                after = control.get(base + '/__diagnostic/snapshot').json()
                group = {'name': label, 'seconds': time.perf_counter()-begin, 'client_results': records,
                         'process_cpu_ms': after['process_cpu_ms']-before['process_cpu_ms'],
                         'event_loop_cpu_ms': after['event_loop_cpu_ms']-before['event_loop_cpu_ms'],
                         'metrics': after['metrics'], 'requests': after['requests'], 'gc_stats': after['gc_stats'],
                         'gc_thresholds': after['gc_thresholds'], 'function_profile': after['function_profile']}
                completed = [x for x in after['requests'] if x['action']=='recall' and x['outcome']=='completed']
                assert len(completed)==len(records) and all(x['items']>0 for x in completed)
                assert all(not (x.get('usage') or {}).get('model_calls') and not (x.get('usage') or {}).get('embedding_calls') for x in completed)
                report['groups'].append(group)
                (root / 'cpu-attribution.json').write_text(json.dumps(report, indent=2)+'\n')
        finally:
            for client in clients:
                client.close()
    report['completed'] = True
finally:
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        report['api_exit_code'] = process.returncode
    if api_log is not None:
        api_log.close()
    if started:
        embedded_database.stop(profile)
    report['ports_closed'] = True
    for port in {profile.database_port, profile.api_port, locals().get('port', profile.api_port)}:
        with socket.socket() as connection:
            report['ports_closed'] &= connection.connect_ex(('127.0.0.1', port)) != 0
    report['source_unchanged'] = all(hashlib.sha256((repository / name).read_bytes()).hexdigest()==value for name,value in hashes.items())
    report['owned_profile_preserved'] = directory.is_dir()
    (root / 'cpu-attribution.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items() if key not in ('source_sha256','groups')}))
assert report['completed'] and report['ports_closed'] and report['source_unchanged']
