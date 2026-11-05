import json
import socket
from pathlib import Path

from membrain import embedded_database
from membrain.local_profile import load_profile

root = Path(__file__).parent
profile = load_profile(root / 'upgrade-copy')
original = embedded_database._installation
embedded_database._installation = lambda: root / 'lts-macos-relocated/pginstall'
report = {'completed': False, 'scope': 'existing synthetic business database and control database only',
          'model_calls': 0, 'databases': {}}
try:
    embedded_database.start(profile)
    for database in ('agent_memory', 'postgres'):
        with embedded_database._admin_connection(profile, database) as connection:
            connection.execute('SET default_transaction_read_only=on')
            report['databases'][database] = {
                'server_version': connection.execute('SHOW server_version').fetchone()[0],
                'extensions': connection.execute('SELECT extname,extversion FROM pg_extension ORDER BY 1').fetchall(),
                'partitioned_tables': connection.execute('SELECT count(*) FROM pg_partitioned_table').fetchone()[0],
                'gist_brin_indexes': connection.execute("SELECT count(*) FROM pg_class c JOIN pg_am a ON a.oid=c.relam WHERE c.relkind='i' AND a.amname IN ('gist','brin')").fetchone()[0],
                'logical_replication_slots': connection.execute("SELECT count(*) FROM pg_replication_slots WHERE slot_type='logical'").fetchone()[0],
                'output_plugin_libraries': connection.execute('SHOW output_plugin_libraries').fetchone()[0],
                'application_role_privileges': connection.execute("SELECT rolsuper,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='memory_app'").fetchall(),
            }
    for result in report['databases'].values():
        assert result['server_version'] == '16.15'
        assert result['partitioned_tables'] == result['gist_brin_indexes'] == result['logical_replication_slots'] == 0
        assert not ({'pgcrypto', 'ltree', 'btree_gist'} & {name for name, _ in result['extensions']})
        assert result['application_role_privileges'] == [(False, False, False)]
    report['completed'] = True
finally:
    embedded_database.stop(profile)
    embedded_database._installation = original
    report['ports_closed'] = True
    for port in (profile.api_port, profile.database_port):
        with socket.socket() as connection:
            connection.settimeout(.2)
            report['ports_closed'] &= connection.connect_ex(('127.0.0.1', port)) != 0
    (root / 'migration-applicability.json').write_text(json.dumps(report, indent=2) + '\n')
assert report['completed'] and report['ports_closed']
print(json.dumps(report))
