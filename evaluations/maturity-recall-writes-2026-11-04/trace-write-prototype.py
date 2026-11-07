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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from psycopg.types.json import Jsonb
from membrain.contracts import validate
from membrain.helpers import Principal, uid
from membrain.service import MemoryService
from membrain.storage import Database
import copy
import statistics
import threading

report = {'purpose': 'trace persistence A/B prototype, actual retained trace documents, not R5 qualification',
          'model_calls': 0, 'restored_profile_files_verified': len(files), 'phases': [],
          'source_sha256': hashes, 'completed': False,
          'protocol': 'A/B/B/A, eight brains concurrently, 10 batches of 51 actual trace documents per worker; no timed samples discarded; all batches validated before timing; transaction and commit included; no read, HTTP, host context or renderer workload'}
started = False
try:
    embedded_database.start(profile)
    started = True
    database = Database(profile.database_url, pool=True)
    service = MemoryService(database)
    principal = Principal(profile.tenant_id, profile.principal_id)
    brain_ids = [host.user_brain_id(f'bench-user-{i}') for i in range(8)]
    templates = []
    with database.transaction(principal) as conn:
        for brain_id in brain_ids:
            rows = conn.execute("SELECT document FROM memory_traces WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s ORDER BY id LIMIT 51", (principal.tenant_id, principal.principal_id, brain_id)).fetchall()
            assert len(rows) == 51
            templates.append([row['document'] for row in rows])
    report['template_json_bytes'] = [len(json.dumps(rows).encode()) for rows in templates]
    def batched(conn, brain, traces):
        if traces:
            conn.execute("INSERT INTO memory_traces(tenant_id,owner_id,brain_id,id,document) SELECT %s,%s,%s,trace.document->>'trace_id',trace.document FROM jsonb_array_elements(%s::jsonb) AS trace(document) ON CONFLICT(tenant_id,brain_id,id) DO NOTHING", (*service._params(principal, brain['id']), Jsonb(traces)))
    totals = [0] * 8
    for phase_index, variant in enumerate(('pipeline', 'jsonb_set', 'jsonb_set', 'pipeline')):
        batches = [[[{**copy.deepcopy(row), 'trace_id': uid()} for row in templates[index]] for _ in range(10)] for index in range(8)]
        for worker in batches:
            for batch in worker:
                for trace in batch:
                    validate('RecallTrace', trace)
        barrier = threading.Barrier(8)
        def worker(index):
            brain = {'id': brain_ids[index]}
            samples = []
            barrier.wait(timeout=15)
            for batch in batches[index]:
                before = time.perf_counter()
                with database.transaction(principal) as conn:
                    if variant == 'pipeline':
                        service._save_traces(conn, principal, brain, batch, validated=True)
                    else:
                        batched(conn, brain, batch)
                samples.append((time.perf_counter() - before) * 1000)
            return samples
        with ThreadPoolExecutor(max_workers=8) as pool:
            raw = list(pool.map(worker, range(8)))
        values = sorted(value for part in raw for value in part)
        phase = {'index': phase_index, 'variant': variant, 'n': len(values), 'median_ms': statistics.median(values), 'p95_ms': values[int(.95 * (len(values)-1))], 'max_ms': max(values), 'raw_ms': raw}
        with database.transaction(principal) as conn:
            verified = 0
            for index, worker_batches in enumerate(batches):
                expected_documents = {row['trace_id']: row for batch in worker_batches for row in batch}
                saved = {row['id']: row['document'] for row in conn.execute("SELECT id,document FROM memory_traces WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=ANY(%s::text[])", (principal.tenant_id, principal.principal_id, brain_ids[index], list(expected_documents)))}
                assert saved == expected_documents
                verified += len(saved)
        phase['exact_documents_verified'] = verified
        report['phases'].append(phase)
    report['completed'] = True
finally:
    if 'database' in locals():
        database.close()
    if started:
        embedded_database.stop(profile)
    report['ports_closed'] = True
    for port in (profile.database_port, profile.api_port):
        with socket.socket() as connection:
            report['ports_closed'] &= connection.connect_ex(('127.0.0.1', port)) != 0
    report['source_unchanged'] = all(hashlib.sha256((repository / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
    if report['completed'] and report['ports_closed']:
        shutil.rmtree(directory)
        report['restored_diagnostic_copy_removed'] = True
    (root / 'trace-write-prototype.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: value for key, value in report.items() if key not in ('source_sha256', 'phases')}))
for phase in report['phases']:
    print(json.dumps({key: value for key, value in phase.items() if key != 'raw_ms'}))
assert report['completed'] and report['source_unchanged'] and report['ports_closed']
