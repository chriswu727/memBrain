import hashlib
import json
import socket
import subprocess
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from membrain import embedded_database
from membrain.local_profile import load_profile

root = Path(__file__).parent
repo = Path('/Users/yichen/tmp/membrain-review-20261029')
profile = load_profile(Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation'))
report = {'purpose': 'Lossless trace storage experiment on temporary copies only; not recall qualification',
          'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'completed': False, 'runs': []}
for port in (profile.api_port, profile.database_port):
    with socket.socket() as sock:
        assert sock.connect_ex(('127.0.0.1', port)) != 0
embedded_database.start(profile)
try:
    with psycopg.connect(profile.migration_database_url, row_factory=dict_row) as conn:
        conn.execute('SET statement_timeout = 60000')
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute('CREATE TEMP TABLE sample AS SELECT * FROM memory_traces TABLESAMPLE SYSTEM (2) REPEATABLE (711) LIMIT 10000')
        report['sample'] = conn.execute('SELECT count(*) AS rows, avg(pg_column_size(document)) AS stored_document_bytes, '
            'avg(octet_length(document::text)) AS json_text_bytes, '
            'min(octet_length(document::text)) AS min_json_bytes,max(octet_length(document::text)) AS max_json_bytes FROM sample').fetchone()
        assert report['sample']['rows'] == 10000
        report['compression'] = conn.execute('SHOW default_toast_compression').fetchone()
        modes = [('default', None, 'EXTENDED'), ('main_1024', 1024, 'MAIN'),
                 ('main_512', 512, 'MAIN'), ('extended_512', 512, 'EXTENDED')]
        for repetition in range(3):
            for name, target, storage in (modes if repetition % 2 == 0 else modes[::-1]):
                conn.execute('CREATE TEMP TABLE trial (LIKE memory_traces INCLUDING ALL)')
                if target:
                    conn.execute(f'ALTER TABLE trial SET (toast_tuple_target={target})')
                conn.execute(f'ALTER TABLE trial ALTER COLUMN document SET STORAGE {storage}')
                start = time.perf_counter()
                conn.execute('INSERT INTO trial SELECT tenant_id,owner_id,brain_id,id,document::text::jsonb,applied_at FROM sample')
                write_ms = (time.perf_counter() - start) * 1000
                size = conn.execute("SELECT pg_total_relation_size('trial') AS total_bytes,pg_relation_size('trial') AS heap_bytes,"
                    "pg_indexes_size('trial') AS index_bytes,avg(pg_column_size(document)) AS stored_document_bytes FROM trial").fetchone()
                start = time.perf_counter()
                equal = conn.execute('SELECT count(*) AS rows, bool_and(t.document=s.document AND t.owner_id=s.owner_id '
                    'AND t.applied_at IS NOT DISTINCT FROM s.applied_at) AS equal '
                    'FROM trial t JOIN sample s USING(tenant_id,brain_id,id)').fetchone()
                compare_ms = (time.perf_counter() - start) * 1000
                assert equal['equal'] and equal['rows'] == 10000
                row = {'mode': name, 'repetition': repetition, 'write_ms': write_ms,
                       'compare_ms': compare_ms, 'equality': equal, **size}
                report['runs'].append(row)
                print(json.dumps(row, default=float), flush=True)
                conn.execute('DROP TABLE trial')
        conn.rollback()
        report['completed'] = True
finally:
    embedded_database.stop(profile)
    report['ports_closed'] = True
    for port in (profile.api_port, profile.database_port):
        with socket.socket() as sock:
            report['ports_closed'] &= sock.connect_ex(('127.0.0.1', port)) != 0
    (root/'probe.json').write_text(json.dumps(report, default=float, indent=2)+'\n')
assert report['completed'] and report['ports_closed']
