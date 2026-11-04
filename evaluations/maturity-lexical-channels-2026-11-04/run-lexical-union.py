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
archive = root / 'canonical-profile-b994ec8.tar.gz'
directory = root / 'perf-b994ec8-installation'
prefix = directory.name + '/'
assert not directory.exists()
assert shutil.disk_usage(root).free > 2_000_000_000
assert hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == '18924505bb3ee0851800646740135430c9667d668ecb382c431495c3347b6ddd'
expected = json.loads((root / 'failing-profile-files.private.json').read_text())
files = {}
with tarfile.open(archive, 'r|gz') as saved:
    for member in saved:
        if not member.name.startswith(prefix):
            continue
        target = root / member.name
        assert target.is_relative_to(directory) and '..' not in Path(member.name).parts
        if member.isdir():
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.chmod(0o700)
        else:
            assert member.isfile(), member.name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with saved.extractfile(member) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o600)
            files[member.name] = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
            assert files[member.name] == expected[member.name]
assert files == {name: value for name, value in expected.items() if name.startswith(prefix)}
for name, value in expected.items():
    if not name.startswith(prefix):
        assert hashlib.file_digest((root / name).open('rb'), 'sha256').hexdigest() == value
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

import math

arms = [0, 1, 1, 0]
report = {'purpose': 'ABBA candidate SQL union experiment; not R5 qualification',
          'restored_files_verified': len(files), 'model_calls': 0, 'source_sha256': hashes,
          'arms_predeclared': arms, 'queries_per_brain': 20,
          'limitations': 'One shared restored database; arms accumulate normal receipts/traces. Fresh API per arm. Instrumentation adds overhead. Original core concurrency policy retained; no admission limit. No browser.',
          'completed': False, 'arms': []}
process = None
api_log = None
started = False
expected_contexts = None
ports = {profile.database_port, profile.api_port}
def save():
    (root / 'lexical-union-abba.json').write_text(json.dumps(report, indent=2)+'\n')
def stop_api():
    global process, api_log
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        assert process.returncode in (0, -15), process.returncode
        process = None
    if api_log is not None:
        api_log.close()
        api_log = None
try:
    embedded_database.start(profile)
    started = True
    for arm_index, slots in enumerate(arms):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        ports.add(port)
        base = f'http://127.0.0.1:{port}'
        api_log = (root / f'lexical-union-arm-{arm_index}.log').open('w')
        process = subprocess.Popen([sys.executable, str(root / 'lexical-union-worker.py'), str(directory), str(port), str(slots)],
                                   env=environment, cwd=repository, stdout=api_log, stderr=subprocess.STDOUT)
        with httpx.Client(trust_env=False, timeout=30) as control:
            deadline = time.monotonic() + 30
            while True:
                assert process.poll() is None, 'API exited before readiness'
                try:
                    if control.get(base + '/health', timeout=.5).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic() < deadline, 'API readiness timed out'
                time.sleep(.1)
            clients = [MemoryClient(base, profile.api_key, brain_id=host.user_brain_id(f'bench-user-{i}')) for i in range(8)]
            try:
                for client in clients:
                    assert host.recall_context(client, 'What is the appointment for project0019?', current_conversation='benchmark')
                before = control.get(base + '/__diagnostic/snapshot?reset=true').json()
                begin = time.perf_counter()
                def worker(index):
                    records = []
                    for query_index in range(20):
                        wall = time.perf_counter()
                        context = host.recall_context(clients[index], f'What is the appointment for project{query_index:04d}?', current_conversation='benchmark')
                        elapsed = (time.perf_counter()-wall)*1000
                        assert context
                        records.append({'brain_index': index, 'query_index': query_index, 'wall_ms': elapsed,
                                        'context_sha256': hashlib.sha256(context.encode()).hexdigest(), 'context_characters': len(context)})
                    return records
                with ThreadPoolExecutor(max_workers=8) as pool:
                    records = [row for part in pool.map(worker, range(8)) for row in part]
                seconds = time.perf_counter()-begin
                after = control.get(base + '/__diagnostic/snapshot').json()
                contexts = {(x['brain_index'], x['query_index']): x['context_sha256'] for x in records}
                if expected_contexts is None:
                    expected_contexts = contexts
                mismatches = [list(key) for key in contexts if contexts[key] != expected_contexts[key]]
                completed = [x for x in after['requests'] if x['action']=='recall' and x['outcome']=='completed']
                assert len(completed)==len(records)==160 and all(x['items']>0 for x in completed)
                assert all(not (x.get('usage') or {}).get('model_calls') and not (x.get('usage') or {}).get('embedding_calls') for x in completed)
                samples = sorted(row['wall_ms'] for row in records)
                arm = {'index': arm_index, 'slots': slots, 'seconds': seconds, 'client_results': records,
                       'p95_ms': samples[math.ceil(.95*len(samples))-1], 'mean_ms': sum(samples)/len(samples),
                       'max_ms': samples[-1], 'context_mismatches': mismatches,
                       'process_cpu_ms': after['process_cpu_ms']-before['process_cpu_ms'],
                       'event_loop_cpu_ms': after['event_loop_cpu_ms']-before['event_loop_cpu_ms'],
                       'requests': after['requests'], 'collections': after['collections'],
                       'peak_active': after['peak_active'], 'max_rss_platform_units': after['max_rss_platform_units']}
                report['arms'].append(arm)
                save()
                print(json.dumps({key:value for key,value in arm.items() if key not in ('client_results','requests','collections')}), flush=True)
                assert not mismatches, 'Returned contexts changed across arms'
            finally:
                for client in clients:
                    client.close()
        stop_api()
    report['completed'] = True
finally:
    stop_api()
    if started:
        embedded_database.stop(profile)
    report['ports_closed'] = True
    for port in ports:
        with socket.socket() as connection:
            report['ports_closed'] &= connection.connect_ex(('127.0.0.1', port)) != 0
    report['source_unchanged'] = all(hashlib.sha256((repository / name).read_bytes()).hexdigest()==value for name,value in hashes.items())
    if report['completed'] and report['ports_closed']:
        shutil.rmtree(directory)
        report['restored_copy_removed'] = True
    save()
assert report['completed'] and report['ports_closed'] and report['source_unchanged']
