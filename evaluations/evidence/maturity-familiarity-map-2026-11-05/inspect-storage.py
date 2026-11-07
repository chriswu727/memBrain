import json
import socket
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from membrain import embedded_database
from membrain.local_profile import load_profile

root = Path(__file__).parent
profile = load_profile(Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation'))
for port in (profile.api_port, profile.database_port):
    with socket.socket() as sock:
        assert sock.connect_ex(('127.0.0.1', port)) != 0
embedded_database.start(profile)
try:
    with psycopg.connect(profile.migration_database_url, row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        report = {
            'scope': 'Post-run metadata only, not causal attribution or a new latency qualification.',
            'database_bytes': conn.execute('SELECT pg_database_size(current_database()) AS value').fetchone()['value'],
            'relations': conn.execute(
                "SELECT relname,n_live_tup,n_dead_tup,last_autovacuum,last_autoanalyze,"
                "pg_total_relation_size(relid) AS bytes FROM pg_stat_user_tables "
                "ORDER BY pg_total_relation_size(relid) DESC LIMIT 15").fetchall(),
            'database_stats': conn.execute(
                "SELECT blks_read,blks_hit,temp_files,temp_bytes,deadlocks,blk_read_time,blk_write_time "
                "FROM pg_stat_database WHERE datname=current_database()").fetchone(),
            'writer_stats': conn.execute('SELECT * FROM pg_stat_bgwriter').fetchone(),
        }
finally:
    embedded_database.stop(profile)
report['ports_closed'] = True
for port in (profile.api_port, profile.database_port):
    with socket.socket() as sock:
        report['ports_closed'] &= sock.connect_ex(('127.0.0.1', port)) != 0
(root/'storage-diagnostic.json').write_text(json.dumps(report, default=str, indent=2))
print(json.dumps({'database_mib':round(report['database_bytes']/2**20,2),'largest':[
    {'table':x['relname'],'mib':round(x['bytes']/2**20,2),'live':x['n_live_tup'],'dead':x['n_dead_tup']}
    for x in report['relations'][:5]],'ports_closed':report['ports_closed']}))
