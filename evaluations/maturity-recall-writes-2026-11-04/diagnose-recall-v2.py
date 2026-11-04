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
assert directory.is_dir() and not directory.is_symlink()
assert not (directory / 'postgres/postmaster.pid').exists()
expected = json.loads((root / 'cold-profile-files.sha256.json').read_text())
files = {str(path.relative_to(root)): hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
         for path in directory.rglob('*') if path.is_file() and not path.is_symlink()}
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
report = {'prior_attempt': 'diagnose-recall.py stopped before DB start because the optional local provider directory exists even when weights are absent; restored files reused only after complete hash revalidation', 'purpose': 'instrumented SQL/cProfile attribution on the retained failed corpus, not R5 qualification',
          'model_calls': 0, 'restored_profile_files_verified': len(files),
          'registry_unchanged_before_start': True, 'completed': False, 'source_sha256': hashes,
          'limitations': 'cProfile and SQL timers add overhead; 16 core recall actions only, explicit host keyword-fallback budget/cutoff; omits boundary/timeline/reply/trace API calls, initial unavailable-embedding attempt and browser; timings cannot satisfy R5',
          'rollback_order': ['original', 'filtered', 'filtered', 'original']}
process = None
api_log = None
started = False
trace_path = root / 'recall-profile.jsonl'
assert not trace_path.exists()
try:
    embedded_database.start(profile)
    started = True
    scope = (profile.tenant_id, profile.principal_id, host.user_brain_id('bench-user-0'))
    with psycopg.connect(profile.migration_database_url, autocommit=True, row_factory=dict_row) as conn:
        conn.execute('SET statement_timeout=30000')
        conn.execute('SET lock_timeout=5000')
        counts = 'SELECT count(*) AS total,count(response) AS valid FROM memory_requests WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s'
        report['receipt_counts'] = conn.execute(counts, scope).fetchone()
        report['rollback_plans'] = []
        for variant in report['rollback_order']:
            conn.execute('BEGIN')
            try:
                query = 'UPDATE memory_requests SET response=NULL WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s'
                if variant == 'filtered':
                    query += ' AND response IS NOT NULL'
                plan = conn.execute('EXPLAIN (ANALYZE,BUFFERS,WAL,FORMAT JSON) ' + query, scope).fetchone()
                report['rollback_plans'].append({'variant': variant, 'plan': plan['QUERY PLAN']})
            finally:
                conn.execute('ROLLBACK')
            assert conn.execute(counts, scope).fetchone() == report['receipt_counts']
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    api_log = (root / 'recall-profile-api.log').open('w')
    process = subprocess.Popen([sys.executable, str(root / 'profile-recall-worker.py'), str(directory),
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
    report['profile_records'] = sum(1 for _ in trace_path.open())
    assert report['profile_records'] == len(report['responses']) == 16
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
    (root / 'recall-diagnosis-v2.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: value for key, value in report.items()
                  if key not in ('source_sha256', 'rollback_plans', 'responses')}, indent=2))
assert report['completed'] and report['source_unchanged'] and report['ports_closed']
