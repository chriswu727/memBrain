import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

root=Path(__file__).parent
package=root/'wheel-venv/lib/python3.12/site-packages/membrain_postgres'
manifest=json.loads((package/'manifest.json').read_text())
report={'purpose':'installed native wheel relocation and actual recovery/companion checks with build prefix absent; not release acceptance','completed':False,'model_calls':0,'manifest_files_checked':0,'tools':[]}
original=root/'wheel-build-v2';hidden=root/'wheel-build-v2-hidden'
assert original.exists() and not hidden.exists()
for entry in manifest['files']:
 p=package/'pginstall'/entry['path']
 assert p.stat().st_size==entry['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256']
 assert stat.S_IMODE(p.stat().st_mode)==entry['mode'],entry['path']
 report['manifest_files_checked']+=1
try:
 original.rename(hidden)
 assert not original.exists()
 for name in ('postgres','pg_ctl','initdb','pg_dump','pg_restore','psql','pg_config'):
  path=package/'pginstall/bin'/name
  result=subprocess.run([str(path),'--version'],capture_output=True,text=True,check=True)
  report['tools'].append({'name':name,'version':result.stdout.strip()})
 report['build_prefix_absent_during_execution']=True
 result=subprocess.run([sys.executable,str(root/'run-installed-compatibility-tests.py')],cwd='/Users/yichen/tmp/membrain-review-20261029',check=False)
 report['tests_exit_code']=result.returncode
 report['build_prefix_absent_after_tests']=not original.exists()
 report['completed']=True
finally:
 hidden.rename(original)
 report['build_prefix_restored']=original.is_dir() and not hidden.exists()
 (root/'installed-wheel-result.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'] and report['tests_exit_code']==0 and report['build_prefix_absent_after_tests'] and report['build_prefix_restored']
print(json.dumps(report))
