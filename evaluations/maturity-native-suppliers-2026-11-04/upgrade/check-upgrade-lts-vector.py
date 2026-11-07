import hashlib
import json
import socket
import subprocess
from pathlib import Path

import psycopg
from psycopg import sql
from membrain import embedded_database
from membrain.local_profile import load_profile

root=Path(__file__).parent
source=Path('/Users/yichen/tmp/membrain-companion-privacy-recheck-20261104/perf-privacy-installation')
clone=root/'upgrade-copy'
old_installation=embedded_database._installation
new_installation=root/'lts-macos-relocated/pginstall'
profile=load_profile(source)
report={'purpose':'relocated CI-built PostgreSQL 16.15, pgvector 0.8.6 and OpenSSL 3.5.9 upgrade on the existing isolated APFS clone; no default integration or R5 pass','completed':False,'model_calls':0,'stages':[],'fingerprint_algorithm':'sort SHA256 of every complete row, preserving duplicates; no server-side text sort'}

def closed(port):
 with socket.socket() as connection:
  connection.settimeout(.2)
  return connection.connect_ex(('127.0.0.1',port)) != 0

def fingerprint():
 with psycopg.connect(profile.migration_database_url,autocommit=True) as conn:
  conn.execute("SET timezone='UTC'")
  conn.execute('SET default_transaction_read_only=on')
  rows={}
  tables=conn.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1,2").fetchall()
  for schema,table in tables:
   query=sql.SQL('COPY (SELECT row_to_json(t)::text FROM {}.{} t) TO STDOUT').format(sql.Identifier(schema),sql.Identifier(table))
   digests=[]
   with conn.cursor().copy(query) as copy:
    copy.set_types(['text'])
    for row in copy.rows():
     assert len(row)==1 and type(row[0]) is str
     digests.append(hashlib.sha256(row[0].encode('utf-8')).digest())
   rows[table]={'rows':len(digests),'sha256':hashlib.sha256(b''.join(sorted(digests))).hexdigest()}
  return {'version':conn.execute('SHOW server_version').fetchone()[0],'tables':rows,'extensions':conn.execute('SELECT extname,extversion FROM pg_extension ORDER BY 1').fetchall(),'vector_distance':conn.execute("SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector").fetchone()[0],'invalid_indexes':conn.execute('SELECT indexrelid::regclass::text FROM pg_index WHERE NOT indisvalid OR NOT indisready ORDER BY 1').fetchall(),'protected_views':conn.execute("SELECT c.relname,pg_get_viewdef(c.oid) LIKE '%%pg_has_role(c.relowner, ''USAGE''%%' FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='pg_catalog' AND c.relname IN ('pg_stats_ext','pg_stats_ext_exprs') ORDER BY 1").fetchall()}

started=False
try:
 assert closed(profile.api_port) and closed(profile.database_port)
 assert clone.is_dir() and not (clone/'postgres/postmaster.pid').exists()
 profile=load_profile(clone)
 embedded_database.start(profile);started=True
 before=fingerprint();report['stages'].append({'stage':'old_16_2_clone','result':before})
 embedded_database.stop(profile);started=False
 embedded_database._installation=lambda:new_installation
 embedded_database.start(profile);started=True
 with embedded_database._admin_connection(profile,'agent_memory') as target:
  target.execute("ALTER EXTENSION vector UPDATE TO '0.8.6'")
 after=fingerprint();report['stages'].append({'stage':'new_16_15_before_catalog_repair','result':after})
 assert before['tables']==after['tables']
 assert before['extensions']==[('plpgsql','1.0'),('vector','0.6.2')]
 assert after['extensions']==[('plpgsql','1.0'),('vector','0.8.6')]
 assert before['vector_distance']==after['vector_distance']
 report['openssl']=subprocess.check_output([str(new_installation/'bin/openssl'),'version'],text=True).strip()
 assert report['openssl'].startswith('OpenSSL 3.5.9 ')
 assert len(before['tables'])==27 and sum(t['rows'] for t in before['tables'].values())==273827
 assert after['version']=='16.15' and not after['invalid_indexes']
 script=(new_installation/'share/fix-CVE-2024-4317.sql').read_text()
 report['catalog_script_sha256']=hashlib.sha256(script.encode()).hexdigest()
 with embedded_database._admin_connection(profile,'postgres') as conn:
  databases=conn.execute("SELECT datname,datallowconn FROM pg_database WHERE datname NOT LIKE 'pg_%' ORDER BY datname").fetchall()
  repaired=[]
  for database,allowed in databases:
   if not allowed:
    conn.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(database)))
   try:
    with embedded_database._admin_connection(profile,database) as target:
     target.execute(script,prepare=False)
     target.execute(script,prepare=False)
    repaired.append(database)
   finally:
    if not allowed:
     conn.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(database)))
  assert databases==conn.execute("SELECT datname,datallowconn FROM pg_database WHERE datname NOT LIKE 'pg_%' ORDER BY datname").fetchall()
 report['catalog_repair_databases']=repaired
 fixed=fingerprint();report['stages'].append({'stage':'new_16_15_after_repeated_catalog_repair','result':fixed})
 assert fixed['tables']==before['tables'] and all(row[1] for row in fixed['protected_views'])
 embedded_database.stop(profile);started=False
 embedded_database.start(profile);started=True
 restarted=fingerprint();report['stages'].append({'stage':'new_16_15_restarted','result':restarted})
 assert restarted==fixed
 report.update(completed=True,all_user_rows_identical=True,vector_upgraded_from_0_6_2_to_0_8_6=True,invalid_indexes=0,original_cluster_not_started_or_modified=True)
finally:
 if started:embedded_database.stop(profile)
 embedded_database._installation=old_installation
 report['ports_closed']=closed(profile.api_port) and closed(profile.database_port)
 (root/'upgrade-lts-vector-result.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'] and report['ports_closed']
print(json.dumps({'completed':True,'tables':len(before['tables']),'rows':sum(t['rows'] for t in before['tables'].values()),'catalog_repair_databases':repaired,'all_user_rows_identical':True,'ports_closed':True}))
