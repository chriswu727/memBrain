import ctypes
import hashlib
import json
import os
import shutil
import socket
from pathlib import Path

from membrain.local_profile import load_profile

root = Path(__file__).parent
owners = [root / 'install-final']
expected = 'f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193'
clonefile = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True).clonefile
clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
clonefile.restype = ctypes.c_int


def clone(source, target):
    assert not target.exists()
    if clonefile(os.fsencode(source), os.fsencode(target), 0) != 0:
        raise OSError(ctypes.get_errno(), 'clonefile failed')


probe = root / 'cow-probe'
probe.mkdir(exist_ok=False)
source, target = probe / 'source', probe / 'target'
source.write_bytes(b'original independent contents')
clone(source, target)
target.write_bytes(b'modified independent contents')
assert source.read_bytes() == b'original independent contents'
shutil.rmtree(probe)
files, profiles = [], []
for owner in owners:
    result = json.loads((owner / 'results.json').read_text())
    assert len(result['results']) == 49 and all(row['ok'] for row in result['results'])
    for path in owner.rglob('profile.json'):
        if 'installation_id' not in json.loads(path.read_text()):
            continue
        profile = load_profile(path.parent)
        for port in (profile.database_port, profile.api_port):
            with socket.socket() as connection:
                assert connection.connect_ex(('127.0.0.1', port)) != 0
        assert not (profile.directory / 'postgres/postmaster.pid').exists()
        profiles.append(str(profile.directory))
    for path in owner.rglob('model_quantized.onnx'):
        assert path.resolve().is_relative_to(owner) and not path.is_symlink()
        assert path.stat().st_size == 118308185
        assert hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() == expected
        files.append(path)
assert len(files) == 4
before = shutil.disk_usage(root).free
canonical = next(Path('/Users/yichen/tmp/membrain-release-qualification-20261104/install-final').rglob('model_quantized.onnx'))
assert hashlib.file_digest(canonical.open('rb'), 'sha256').hexdigest() == expected
replaced = []
for path in files:
    temporary = path.with_name(path.name + '.membrain-clone')
    previous = path.stat()
    assert previous.st_uid == canonical.stat().st_uid and previous.st_gid == canonical.stat().st_gid
    try:
        clone(canonical, temporary)
        shutil.copystat(path, temporary)
        assert temporary.stat().st_ino != canonical.stat().st_ino
        assert hashlib.file_digest(temporary.open('rb'), 'sha256').hexdigest() == expected
        os.replace(temporary, path)
        current = path.stat()
        assert current.st_uid == previous.st_uid and current.st_gid == previous.st_gid
        assert current.st_mode == previous.st_mode and current.st_mtime_ns == previous.st_mtime_ns
        assert hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() == expected
        replaced.append(str(path))
    finally:
        temporary.unlink(missing_ok=True)
after = shutil.disk_usage(root).free
report = {'purpose': 'share identical public model blocks only in the newly completed owned recall-cache acceptance environment',
          'method': 'APFS clonefile copy-on-write; independently mutable files retained, no hard links',
          'expected_sha256': expected, 'bytes_per_file': 118308185,
          'paths_retained_and_verified': len(files), 'replaced_with_cow_clones': len(replaced),
          'stopped_profiles_checked': len(profiles), 'free_before': before, 'free_after': after,
          'measured_free_increase': after-before, 'same_modes_ownership_mtimes_and_contents': True,
          'copy_on_write_independence_probe_passed': True, 'packages_profiles_registries_and_logs_retained': True}
(root / 'model-block-sharing-native.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
