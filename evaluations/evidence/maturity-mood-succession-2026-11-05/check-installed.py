import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from membrain.build_identity import BUILD_ID, SCHEMA_ID, package_manifest

repo = Path('/Users/yichen/tmp/membrain-review-20261029')
root = Path(__file__).parent
site = root / 'installed/site'
source = package_manifest(repo / 'src/membrain', repo)
installed = package_manifest(site / 'membrain', site)
assert source == installed
paths = [p for base in (repo / 'src', repo / 'tests', site) for p in base.rglob('*')
         if p.is_file() and '__pycache__' not in p.parts]
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
probe = root / 'installed/test_installed_identity.py'
probe.write_text(f'''from pathlib import Path
import membrain
from membrain.build_identity import BUILD_ID, SCHEMA_ID

def test_installed_identity():
    assert Path(membrain.__file__).parent == Path({str(site / 'membrain')!r})
    assert BUILD_ID == {BUILD_ID!r}
    assert SCHEMA_ID == {SCHEMA_ID!r}
''')
environment = {k:v for k,v in os.environ.items() if not k.startswith(('MEMORY_', 'MEMBRAIN_'))}
environment.update(PYTHONPATH=str(site), PYTHON_DOTENV_DISABLED='1')
files = ['test_recall_executor.py','test_recall_readiness.py','test_desktop_startup_failures.py','test_mood_successions.py']
with (root / 'installed-tests.txt').open('w') as output:
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', str(probe),
                             *(str(repo / 'tests' / name) for name in files)],
                            cwd=root / 'installed', env=environment, stdout=output, stderr=subprocess.STDOUT)
report = {'runtime_commit':'c7db08733e09bb30e90b2200458cefeb105811db',
          'build_id':BUILD_ID, 'schema_id':SCHEMA_ID, 'runtime_files_equal':len(source),
          'installed_path':str(site / 'membrain'), 'exit_code':result.returncode,
          'source_and_installed_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items()),
          'scope':'Installed wheel with existing read-only development dependencies; not a clean dependency install, launcher upgrade or R1 qualification.',
          'artifacts':[{'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((root/'installed/dist').iterdir())]}
(root / 'installed-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert result.returncode==0 and report['source_and_installed_unchanged']
