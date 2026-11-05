import json,socket
from pathlib import Path
import psycopg
from membrain import embedded_database
from membrain.local_profile import load_profile
root=Path(__file__).parent;profile=load_profile(root/'local-check-v2/profile')
for port in (profile.api_port,profile.database_port):
 with socket.socket() as connection:
  connection.settimeout(.2);assert connection.connect_ex(('127.0.0.1',port))!=0
report={}
try:
 embedded_database.start(profile)
 with embedded_database._admin_connection(profile,'agent_memory') as connection:
  report['views']=dict(connection.execute("SELECT relname,pg_get_viewdef(oid) FROM pg_class WHERE oid IN('pg_catalog.pg_stats_ext'::regclass,'pg_catalog.pg_stats_ext_exprs'::regclass)").fetchall())
  report['statistics']=connection.execute("SELECT s.stxname,s.stxowner::regrole::text,c.relowner::regrole::text,d.stxdmcv IS NOT NULL,d.stxdexpr IS NOT NULL FROM pg_statistic_ext s JOIN pg_class c ON c.oid=s.stxrelid JOIN pg_statistic_ext_data d ON d.stxoid=s.oid WHERE s.stxname IN('maintenance_stat','maintenance_expr') ORDER BY 1").fetchall()
  report['admin_counts']=[connection.execute("SELECT count(*) FROM pg_stats_ext WHERE statistics_name='maintenance_stat'").fetchone()[0],connection.execute("SELECT count(*) FROM pg_stats_ext_exprs WHERE statistics_name='maintenance_expr'").fetchone()[0]]
 with psycopg.connect(host='127.0.0.1',port=profile.database_port,user='maintenance_probe',password=profile.app_password,dbname='agent_memory',connect_timeout=5) as connection:
  report['probe_role_checks']=connection.execute("SELECT pg_has_role('maintenance_probe','USAGE'),pg_has_role('postgres','USAGE'),has_table_privilege('maintenance_private','SELECT')").fetchone()
  report['probe_counts']=[connection.execute("SELECT count(*) FROM pg_stats_ext WHERE statistics_name='maintenance_stat'").fetchone()[0],connection.execute("SELECT count(*) FROM pg_stats_ext_exprs WHERE statistics_name='maintenance_expr'").fetchone()[0]]
finally:embedded_database.stop(profile)
(root/'statistics-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='views'}))
for name,text in report['views'].items():print(name,text[text.index('WHERE'):])
