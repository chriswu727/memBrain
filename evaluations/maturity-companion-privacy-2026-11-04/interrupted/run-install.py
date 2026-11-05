import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent
repository = Path('/Users/yichen/tmp/membrain-review-20261029')
script = repository / 'evaluations/release-install-2026-11-01.py'
cache = Path('/Users/yichen/tmp/membrain-tail-attribution-20261104/install-final/uv-cache')
out = root / 'install-final'
for name in list(os.environ):
    if name.startswith(('MEMORY_', 'MEMBRAIN_')) or name.endswith(('_API_KEY', '_API_TOKEN')):
        del os.environ[name]
os.environ.pop('PYTHONPATH', None)
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
spec = importlib.util.spec_from_file_location('release_install_current', script)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
original_home = module.Home


class SharedDownloadCacheHome(original_home):
    def __init__(self, base, cache=None):
        super().__init__(base, cache=Path('/Users/yichen/tmp/membrain-tail-attribution-20261104/install-final/uv-cache'))


module.Home = SharedDownloadCacheHome
metadata = {'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
            'runtime_pin': 'd4f0c03689459f84a2e3d25358e74479d1aa2968',
            'harness_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
            'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'shared_download_cache': str(cache), 'changes': 'download cache location only; fresh homes and frozen baselines unchanged',
            'provider_credentials_removed': True, 'model_evaluation_calls': 0, 'completed': False}
(root / 'install-run-meta.json').write_text(json.dumps(metadata, indent=2) + '\n')
sys.argv = [str(script), str(out)]
code = module.run_checked()
metadata.update(completed=True, exit_code=code)
(root / 'install-run-meta.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata))
raise SystemExit(code)
