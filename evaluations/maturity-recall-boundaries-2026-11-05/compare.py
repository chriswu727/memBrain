import hashlib
import json
import math
import os
import socket
import subprocess
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from membrain import embedded_database, host, lexical_candidates
from membrain.candidates import collect_candidates
from membrain.client import default_budget, default_read_fence
from membrain.helpers import Principal, now
from membrain.local_profile import load_profile
from membrain.service import MemoryService
from membrain.storage import Database

ROOT = Path(__file__).parent
REPO = Path('/Users/yichen/tmp/membrain-review-20261029')
PROFILE = Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation')
profile = load_profile(PROFILE)
assert profile.settings().cognition_base_url is None and profile.settings().embedding_base_url is None
baseline = types.ModuleType('membrain._baseline_lexical')
exec(compile((ROOT / 'baseline_lexical.py').read_text(), str(ROOT / 'baseline_lexical.py'), 'exec'), baseline.__dict__)
current = lexical_candidates.LexicalScorer
paths = [p for folder in ('src', 'tests') for p in (REPO / folder).rglob('*')
         if p.is_file() and '__pycache__' not in p.parts]
paths += [ROOT / 'compare.py', ROOT / 'baseline_lexical.py']
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report = {'purpose': 'Read-only candidate collection ABBA: exact document/order/signal/budget equivalence; not full HTTP or fullscreen R5.',
          'completed': False, 'source_sha256': hashes, 'model_calls': 0, 'groups': []}
principal = Principal(profile.tenant_id, profile.principal_id)
fixed_time = now()
expected = {}
database = None
started = False


def stable(value):
    if isinstance(value, dict):
        return sorted([(stable(k), stable(v)) for k, v in value.items()], key=repr)
    if isinstance(value, (set, frozenset)):
        return sorted((stable(x) for x in value), key=repr)
    if isinstance(value, (tuple, list)):
        return [stable(x) for x in value]
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def worker(index, rounds):
    rows = []
    target = {'brain_ref': host.user_brain_id(f'bench-user-{index}'), 'conversation_ref': 'benchmark', 'branch_ref': None}
    for number in range(rounds):
        query = {'query': f'What is the appointment for project{number:04d}?', 'intent': 'explore',
                 'budget': default_budget(16000), 'read_fence': default_read_fence(),
                 'cue_event_ids': [], 'additional_cues': []}
        wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
        with database.transaction(principal) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            brain = conn.execute('SELECT * FROM memory_brains WHERE tenant_id=%s AND owner_id=%s AND id=%s',
                                 (principal.tenant_id, principal.principal_id, target['brain_ref'])).fetchone()
            assert brain is not None
            memories, state = collect_candidates(conn, service, principal, brain, target, query, access_at=fixed_time)
        elapsed, used = (time.perf_counter_ns()-wall)/1e6, (time.thread_time_ns()-cpu)/1e6
        assert memories and state['candidate_versions']
        value = hashlib.sha256(json.dumps(stable((memories, state)), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        rows.append({'brain': index, 'query': number, 'wall_ms': elapsed, 'cpu_ms': used,
                     'sha256': value, 'candidate_count': len(state['candidate_versions'])})
    return rows


try:
    for port in (profile.database_port, profile.api_port):
        with socket.socket() as s:
            assert s.connect_ex(('127.0.0.1', port)) != 0
    embedded_database.start(profile)
    started = True
    database = Database(profile.database_url, pool=True)
    service = MemoryService(database)
    assert service.embedding_provider is None and service.semantic_processor is None
    for phase, scorer in [('before', baseline.LexicalScorer), ('after', current), ('after', current), ('before', baseline.LexicalScorer)]:
        lexical_candidates.LexicalScorer = scorer
        worker(0, 2)
        for kind, indices, rounds in [('serial', [0], 12), ('eight_brains', list(range(8)), 12)]:
            with ThreadPoolExecutor(max_workers=len(indices)) as pool:
                rows = [row for result in pool.map(lambda i: worker(i, rounds), indices) for row in result]
            for row in rows:
                key = row['brain'], row['query']
                assert expected.setdefault(key, row['sha256']) == row['sha256'], f'Candidate mismatch at {key}'
            ordered = sorted(r['wall_ms'] for r in rows)
            group = {'phase': phase, 'kind': kind, 'p95_ms': ordered[math.ceil(len(rows)*.95)-1],
                     'cpu_ms': sum(r['cpu_ms'] for r in rows), 'results': rows}
            report['groups'].append(group)
            (ROOT / 'comparison.json').write_text(json.dumps(report, indent=2))
            print(json.dumps({k:v for k,v in group.items() if k!='results'}), flush=True)
    report['exact_equivalent_queries'] = len(expected)
    report['completed'] = True
finally:
    lexical_candidates.LexicalScorer = current
    if database is not None:
        database.close()
    if started:
        embedded_database.stop(profile)
    report['ports_closed'] = True
    for port in (profile.database_port, profile.api_port):
        with socket.socket() as s:
            report['ports_closed'] &= s.connect_ex(('127.0.0.1', port)) != 0
    report['source_and_driver_unchanged'] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    (ROOT / 'comparison.json').write_text(json.dumps(report, indent=2))
assert report['completed'] and report['ports_closed'] and report['source_and_driver_unchanged']
