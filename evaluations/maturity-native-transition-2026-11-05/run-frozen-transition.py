import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029')
def frozen():
 return {str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('src','tests','scripts') for p in (repo/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
before=frozen()
with (root/'local-reused.log').open('xb') as output:
 result=subprocess.run([sys.executable,str(repo/'scripts/check_native_transition.py'),'--directory',str(root/'local-reused'),'--cache-directory','/Users/yichen/tmp/membrain-native-cache-20261104/acl-cold-install-check/cache','--legacy-upgrade','--reuse-source',str(root/'source-fixture.json'),'--archive-completed-failed-fixture'],cwd=repo,stdout=output,stderr=subprocess.STDOUT)
report={'returncode':result.returncode,'frozen_files':len(before),'source_and_checks_unchanged':before==frozen()}
(root/'local-frozen-result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert result.returncode==0 and report['source_and_checks_unchanged']
