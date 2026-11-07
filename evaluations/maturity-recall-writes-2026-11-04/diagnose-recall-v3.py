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
archive = root / 'canonical-profile-e749a24-v3.tar.gz'
directory = root / 'perf-e749a24-installation'
prefix = directory.name + '/'
assert not directory.exists()
assert shutil.disk_usage(root).free > 2_000_000_000
assert hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == 'fce8152396794b4d973ca88e949241ca471f7cbb957453cf3434cb3117e8d543'
expected = json.loads((root / 'cold-profile-files.sha256.json').read_text())
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
report = {'prior_attempts': ['v1: optional local provider directory is present despite absent weights; stopped before DB start', 'v2: concurrent cProfile instances conflict in this Python runtime; SQL rollback evidence retained, instrumentation run failed, API/DB stopped; modified copy removed before fresh hash-verified restore'], 'purpose': 'instrumented SQL/cProfile attribution on the retained failed corpus, not R5 qualification',
          'model_calls': 0, 'restored_profile_files_verified': len(files),
          'registry_unchanged_before_start': True, 'completed': False, 'source_sha256': hashes,
          'limitations': 'SQL timers add overhead in 16 concurrent core recalls, CPU profiling only in two separate serial recalls; explicit host keyword-fallback budget/cutoff; omits boundary/timeline/reply/trace API calls, initial unavailable-embedding attempt and browser. Not R5 qualification.',
          'rollback_order': ['original', 'filtered', 'filtered', 'original']}
process = None
api_log = None
started = False
trace_path = root / 'recall-profile-v3.jsonl'
assert not trace_path.exists()
try:
    embedded_database.start(profile)
    started = True
    scope = (profile.tenant_id, profile.principal_id, host.user_brain_id('bench-user-0'))
    report['previous_rollback_sql_evidence'] = 'recall-diagnosis-v2.json'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    api_log = (root / 'recall-profile-v3-api.log').open('w')
    process = subprocess.Popen([sys.executable, str(root / 'profile-recall-worker-v3.py'), str(directory),
                                str(port), str(trace_path)], env=environment, cwd=repository,
                               stdout=api_log, stderr=subprocess.STDOUT)
    with httpx.Client(trust_env=False, timeout=.5) as health:
        deadline = time.monotonic() + 30
        while True:
            assert process.poll() is None, 'profile API exited before readiness'
            try:
                if health.get(base + '/health').status_code == 200:
                    break
            except httpx.TransportError:
                pass
            assert time.monotonic() < deadline, 'readiness timeout'
            time.sleep(.1)

    def run(index):
        with MemoryClient(base, profile.api_key, brain_id=host.user_brain_id(f'bench-user-{index}')) as client:
            records = []
            for query_index in range(2):
                request_id = f'profile-{index}-{query_index}'
                response = client.recall(f'What is the appointment for project{query_index:04d}?',
                                         budget=host.recall_budget(embeddings=0), evidence_cutoff={'mode': 'through_sequence', 'through_sequence': 2**53}, request_id=request_id)
                assert response['outcome'] == 'completed' and response['result']['items']
                records.append({'request_id': request_id, 'items': len(response['result']['items'])})
            return records

    with ThreadPoolExecutor(max_workers=8) as pool:
        report['responses'] = [record for rows in pool.map(run, range(8)) for record in rows]
    with MemoryClient(base, profile.api_key, brain_id=host.user_brain_id('bench-user-0')) as serial:
        for index in range(2):
            response = serial.recall(f'What is the appointment for project{index:04d}?', budget=host.recall_budget(embeddings=0), evidence_cutoff={'mode': 'through_sequence', 'through_sequence': 2**53}, request_id=f'serial-profile-{index}')
            assert response['outcome'] == 'completed' and response['result']['items']
    report['profile_records'] = sum(1 for _ in trace_path.open())
    assert report['profile_records'] == 18 and len(report['responses']) == 16
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
    report['source_unchanged'] = all(hashlib.sha256((repository / name).read_bytes()).hexdigest() == value
                                     for name, value in hashes.items())
    if report['completed'] and report['ports_closed']:
        shutil.rmtree(directory)
        report['restored_diagnostic_copy_removed'] = True
    (root / 'recall-diagnosis-v3.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: value for key, value in report.items()
                  if key not in ('source_sha256', 'rollback_plans', 'responses')}, indent=2))
assert report['completed'] and report['source_unchanged'] and report['ports_closed']
