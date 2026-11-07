import json,socket
from pathlib import Path
from uuid import uuid4
from membrain import embedded_database,native_bundle,native_maintenance
from membrain.local_profile import load_profile
root=Path(__file__).parent;directory=root/'local-check-v3';profile=load_profile(directory/'profile')
for port in (profile.api_port,profile.database_port):
 with socket.socket() as connection:
  connection.settimeout(.2);assert connection.connect_ex(('127.0.0.1',port))!=0
native_bundle._cache_directory=lambda:Path('/Users/yichen/tmp/membrain-native-cache-20261104/acl-cold-install-check/cache')
prefix=native_bundle.prepare();embedded_database._installation=lambda:prefix
report={}
try:
 embedded_database.start(profile);layout=embedded_database._layout(profile)
 with embedded_database._admin_connection(profile,'postgres') as connection:
  row=connection.execute("SELECT current_setting('server_version_num')::integer,system_identifier::text,current_setting('data_directory'),current_setting('is_superuser'),inet_server_addr()::text,inet_server_port(),pg_is_in_recovery(),current_user FROM pg_control_system()").fetchone();report['identity']=row
 path=layout.data.parent/'.native-maintenance/catalog.json'
 operation=json.loads(path.read_text())['operation_id'] if path.exists() else str(uuid4())
 receipt=json.loads((directory/'snapshot/receipt.json').read_text())
 import hashlib
 commitment=hashlib.sha256((directory/'snapshot/receipt.json').read_bytes()).hexdigest()
 try:report['result']=native_maintenance._run(profile,layout,directory/'snapshot',commitment,operation)
 except Exception as error:
  report['error_type']=type(error).__name__;report['error_code']=getattr(error,'code',None);report['sqlstate']=getattr(error,'sqlstate',None)
  text=str(error)
  for secret in (profile.api_key,profile.admin_password,profile.app_password):text=text.replace(secret,'[redacted]')
  report['detail']=text
finally:embedded_database.stop(profile)
(root/'maintenance-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
