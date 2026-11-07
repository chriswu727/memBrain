import hashlib
import json
import socket
import statistics
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from membrain import cognition, embedded_database, host
from membrain.candidates import _eligible, _scope_clause
from membrain.lexical_candidates import _merged_rows, _prefixes
from membrain.local_profile import load_profile
from membrain.service import _vector


def deferred_rows(conn, where, values, vector, terms, limit):
    select = ('SELECT a.id,a.revision,a.embedding <=> %s::vector AS distance '
              'FROM memory_assertions a WHERE ')
    order = 'ORDER BY distance NULLS LAST,a.id,a.revision LIMIT %s'
    return conn.execute(
        'WITH hashed AS MATERIALIZED (' + select + where + order + '), '
        'exact AS MATERIALIZED (' + select + where
        + "AND to_tsvector('simple',a.search_text) @@ to_tsquery('simple',%s) " + order + '), '
        'ranked AS (SELECT *,0 AS channel,row_number() OVER (ORDER BY distance NULLS LAST,id,revision) AS position '
        'FROM exact UNION ALL SELECT *,1 AS channel,'
        'row_number() OVER (ORDER BY distance NULLS LAST,id,revision) AS position FROM hashed), '
        "selected AS (SELECT DISTINCT ON (a.document->'memory_id',a.document->'revision') "
        'a.document,a.event_ids,a.is_current,r.channel,r.position '
        'FROM ranked r JOIN memory_assertions a ON a.id=r.id AND a.revision=r.revision '
        'AND a.tenant_id=%s AND a.owner_id=%s AND a.brain_id=%s WHERE r.position<=%s '
        "ORDER BY a.document->'memory_id',a.document->'revision',r.channel,r.position) "
        'SELECT document,event_ids,is_current,'
        '((SELECT count(*) FROM hashed)>%s OR (SELECT count(*) FROM exact)>%s) AS truncated '
        'FROM selected ORDER BY channel,position',
        (vector, *values, limit + 1, vector, *values, ' | '.join(_prefixes(terms)), limit + 1,
         *values[:3], limit, limit, limit),
    ).fetchall()


if __name__ == '__main__':
    root = Path(__file__).parent
    profile = load_profile(Path('/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation'))
    report = {'purpose': 'Read-only paired query prototype; no release qualification', 'completed': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'pairs': []}
    for port in (profile.api_port, profile.database_port):
        with socket.socket() as sock:
            assert sock.connect_ex(('127.0.0.1', port)) != 0
    embedded_database.start(profile)
    try:
        with psycopg.connect(profile.migration_database_url, row_factory=dict_row) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            conn.execute('SET statement_timeout = 30000')
            for brain_index in range(8):
                brain = conn.execute('SELECT tenant_id,owner_id,id FROM memory_brains WHERE id=%s',
                                    (host.user_brain_id(f'bench-user-{brain_index}'),)).fetchone()
                params = (brain['tenant_id'], brain['owner_id'], brain['id'])
                clause, scope_params = _scope_clause('a', {'conversation_ref': 'benchmark'})
                where = _eligible() + clause
                where += "AND a.embedding_model='lexical-feature-hash' AND a.embedding_version='v1-d256-blake2s' "
                values = (*params, *scope_params)
                for query_index in (0, 7, 19):
                    text = f'What is the appointment for project{query_index:04d}?'
                    vector, terms = _vector(text), sorted(cognition._terms(text)[0])
                    for repetition in range(4):
                        results, timing = {}, {}
                        for name, function in ([('original', _merged_rows), ('deferred', deferred_rows)]
                                               if repetition % 2 == 0 else [('deferred', deferred_rows), ('original', _merged_rows)]):
                            start = time.perf_counter()
                            results[name] = function(conn, where, values, vector, terms, 128)
                            timing[name] = (time.perf_counter() - start) * 1000
                        assert results['original'] == results['deferred']
                        report['pairs'].append({'brain': brain_index, 'query': query_index, 'repetition': repetition,
                                                'rows': len(results['original']), 'exact_equality': True, **timing})
            conn.rollback()
            report['completed'] = True
    finally:
        embedded_database.stop(profile)
        report['ports_closed'] = True
        for port in (profile.api_port, profile.database_port):
            with socket.socket() as sock:
                report['ports_closed'] &= sock.connect_ex(('127.0.0.1', port)) != 0
        (root/'channel_probe.json').write_text(json.dumps(report, indent=2)+'\n')
    for name in ('original','deferred'):
        print(name, 'median_ms', statistics.median(r[name] for r in report['pairs']),
              'total_ms', sum(r[name] for r in report['pairs']))
    assert report['completed'] and report['ports_closed']
