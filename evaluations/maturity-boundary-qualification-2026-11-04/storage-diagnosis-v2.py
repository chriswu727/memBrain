import hashlib
import json
import shutil
import socket
import tarfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from membrain import embedded_database
from membrain.local_profile import load_profile

root = Path(__file__).parent
archive = root / 'canonical-profile-e749a24-v3.tar.gz'
directory = root / 'perf-e749a24-installation'
prefix = directory.name + '/'
assert directory.is_dir() and not directory.is_symlink()
assert not (directory / 'postgres/postmaster.pid').exists()
directory.chmod(0o700)
(directory / 'postgres').chmod(0o700)
report = {'purpose': 'metadata-only diagnosis of the retained failed fixture; not another R5 run',
          'model_calls': 0, 'completed': False, 'restored_file_hashes_verified_before_first_start': 1485,
          'prior_start_error': 'tar data filter dropped directory mode; diagnostic copy directories repaired to0700'}
started = False
try:
    profile = load_profile(directory)
    embedded_database.start(profile)
    started = True
    settings = profile.settings()
    from urllib.parse import urlsplit
    target = urlsplit(settings.migration_database_url)
    assert target.hostname == '127.0.0.1' and target.port == profile.database_port
    with psycopg.connect(settings.migration_database_url, autocommit=True, row_factory=dict_row) as conn:
        conn.execute('SET default_transaction_read_only=on')
        report['database'] = conn.execute('SELECT current_database() AS name, pg_database_size(current_database()) AS bytes').fetchone()
        report['relations'] = conn.execute("SELECT n.nspname,c.relname,c.relkind,pg_relation_size(c.oid) AS main_bytes,pg_total_relation_size(c.oid) AS total_bytes FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','m') ORDER BY total_bytes DESC").fetchall()
        report['maintenance'] = conn.execute('SELECT relname,n_live_tup,n_dead_tup,last_analyze,last_autoanalyze,analyze_count,autoanalyze_count,last_vacuum,last_autovacuum FROM pg_stat_user_tables ORDER BY relname').fetchall()
        report['wal'] = conn.execute('SELECT * FROM pg_stat_wal').fetchone()
        report['checkpoints'] = conn.execute('SELECT * FROM pg_stat_bgwriter').fetchone()
        report['settings'] = conn.execute("SELECT name,setting,unit FROM pg_settings WHERE name IN ('autovacuum','autovacuum_naptime','checkpoint_timeout','max_wal_size','min_wal_size','shared_buffers','effective_cache_size','jit','default_toast_compression') ORDER BY name").fetchall()
    report['completed'] = True
finally:
    if started:
        embedded_database.stop(profile)
        assert not (directory / 'postgres/postmaster.pid').exists()
        with socket.socket() as listener:
            listener.settimeout(.2)
            assert listener.connect_ex(('127.0.0.1', profile.database_port)) != 0
        report['database_stopped'] = True
    if report['completed'] and report.get('database_stopped'):
        shutil.rmtree(directory)
        report['restored_diagnostic_copy_removed'] = True
    (root / 'storage-diagnosis-v2.json').write_text(json.dumps(report, indent=2, default=str) + '\n')
print(json.dumps({'completed': report['completed'], 'database_bytes': report.get('database', {}).get('bytes'),
                  'top_relations': report.get('relations', [])[:5], 'model_calls': 0}))
