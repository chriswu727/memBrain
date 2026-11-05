import hashlib,json,os,socket,subprocess
from pathlib import Path
from membrain.build_identity import BUILD_ID,SCHEMA_ID,package_manifest
from membrain.local_profile import load_profile
root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029');out=root/'install-final'
source=package_manifest(repo/'src/membrain',repo);expected={k:hashlib.sha256(v).hexdigest() for k,v in source.items()}
report={'source_build_id':BUILD_ID,'source_schema_id':SCHEMA_ID,'homes':[],'profiles':[],'completed':False}
code='''import json
from pathlib import Path
import membrain
from membrain.build_identity import BUILD_ID,SCHEMA_ID,package_manifest
import hashlib
p=Path(membrain.__file__).parent
print(json.dumps({'package':str(p),'build':BUILD_ID,'schema':SCHEMA_ID,'manifest':{k:hashlib.sha256(v).hexdigest() for k,v in package_manifest(p,p.parents[1]).items()}}))'''
env={k:v for k,v in os.environ.items() if not k.startswith(('MEMORY_','MEMBRAIN_')) and k not in ('PYTHONPATH','VIRTUAL_ENV')}
for home in (out,out/'companion'):
 python=home/'uv-tools/membrain-ai/bin/python'
 d=json.loads(subprocess.check_output([str(python),'-c',code],cwd=home,env=env,text=True))
 assert d['manifest']==expected and d['build']==BUILD_ID and d['schema']==SCHEMA_ID
 report['homes'].append({'home':str(home),'package':d['package'],'runtime_files_equal':len(expected),'build_id':d['build'],'schema_id':d['schema']})
for base in (out/'home',out/'restored',out/'companion/home',out/'companion/restored'):
 for p in base.rglob('profile.json'):
  profile=load_profile(p.parent);ports={}
  for name,port in [('api',profile.api_port),('database',profile.database_port)]:
   with socket.socket() as connection:ports[name]={'port':port,'closed':connection.connect_ex(('127.0.0.1',port))!=0}
  assert all(v['closed'] for v in ports.values())
  report['profiles'].append({'directory':str(p.parent),'ports':ports})
assert len(report['profiles'])==4
report['completed']=True;(root/'installed-and-ports.json').write_text(json.dumps(report,indent=2)+'\n')
print({'completed':True,'homes':len(report['homes']),'runtime_files_equal_per_home':len(expected),'profiles':len(report['profiles']),'all_ports_closed':True})
