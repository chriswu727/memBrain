import hashlib
import json
import time
import zipfile
from pathlib import Path

from membrain import native_bundle

root = Path(__file__).parent
repo = Path('/Users/yichen/tmp/membrain-review-20261029')
inputs = Path('/Users/yichen/tmp/membrain-engine-suppliers-20261104')
index = json.loads((repo / 'src/membrain/resources/native/index.json').read_text())
key = native_bundle.platform_key()
entry = index['platforms'][key]
source = root / 'supplier'
source.mkdir(exist_ok=False)
with zipfile.ZipFile(inputs / entry['supplier']['filename']) as saved:
    name = next(name for name in saved.namelist() if name.endswith('.tar.gz'))
    archive = source / Path(name).name
    archive.write_bytes(saved.read(name))
native_bundle._source = lambda: (key, entry, archive)
native_bundle._cache_directory = lambda: root / 'cache'
paths = list((repo / 'src').rglob('*.py')) + list((repo / 'src/membrain/resources/native').iterdir())
hashes = {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in paths if path.is_file() and '__pycache__' not in path.parts}
report = {'completed': False, 'source_sha256': hashes, 'phases': [], 'model_calls': 0}
try:
    for phase in ('cold', 'warm', 'repair_corrupt_cache'):
        if phase == 'repair_corrupt_cache':
            damaged = prefix / 'lib/vector.dylib'
            damaged.write_bytes(damaged.read_bytes() + b'corrupt synthetic test')
        started = time.perf_counter()
        prefix = native_bundle.prepare()
        elapsed = (time.perf_counter() - started) * 1000
        assert native_bundle._validate_tree(prefix, native_bundle._manifest(entry))
        report['phases'].append({'phase': phase, 'ms': elapsed, 'verified_files': entry['native_files']})
    assert len(list((root / 'cache').glob('.quarantine-*'))) == 1
    assert not list((root / 'cache').glob('.staging-*'))
    with archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['supplier']['archive_sha256']
    report.update(completed=True, supplier_unchanged=True,
                  source_unchanged=all(hashlib.sha256((repo / name).read_bytes()).hexdigest() == digest
                                       for name, digest in hashes.items()),
                  corrupt_engine_retained_in_quarantine=True, no_database_started=True)
finally:
    (root / 'real-cache-result.json').write_text(json.dumps(report, indent=2) + '\n')
assert report['completed'] and report['source_unchanged']
print(json.dumps({key: value for key, value in report.items() if key != 'source_sha256'}))
