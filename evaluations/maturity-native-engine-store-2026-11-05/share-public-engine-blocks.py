import ctypes
import hashlib
import json
import os
import secrets
from pathlib import Path

from membrain import embedded_database

root = Path(__file__).parent
original = embedded_database._installation()
system = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
system.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
system.clonefile.restype = ctypes.c_int
count = total = 0

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

for attempt in ('preserved-rollback', 'preserved-rollback-v2'):
    directory = root / attempt
    assert json.loads((directory/'result.json').read_text())['ports_closed'] is True
    for copy in (directory/'offline-engine', *list((directory/'preserved-engine').glob('postgres-*'))):
        for source_root, target_root in ((original, copy/'pgserver/pginstall'),
                                         (original.parent/'.dylibs', copy/'pgserver/.dylibs')):
            if not target_root.exists():
                continue
            for source in source_root.rglob('*'):
                target = target_root/source.relative_to(source_root)
                if source.is_symlink() or target.is_symlink() or not source.is_file() or not target.is_file():
                    continue
                before = target.stat()
                assert before.st_uid == os.getuid() and before.st_nlink == 1
                if source.stat().st_size != before.st_size:
                    continue
                expected = digest(target)
                if digest(source) != expected:
                    continue
                temporary = target.with_name('.cow-' + secrets.token_hex(12))
                if system.clonefile(os.fsencode(source), os.fsencode(temporary), 0):
                    raise OSError(ctypes.get_errno(), 'Public native clone failed')
                temporary.chmod(before.st_mode & 0o777)
                os.utime(temporary, ns=(before.st_atime_ns, before.st_mtime_ns))
                assert digest(temporary) == expected and digest(target) == expected
                assert temporary.stat().st_nlink == 1 and source.stat().st_ino != temporary.stat().st_ino
                assert target.stat().st_ino == before.st_ino
                os.replace(temporary, target)
                assert digest(target) == expected and target.stat().st_nlink == 1
                count += 1
                total += before.st_size

report = {'public_native_files_cloned': count, 'logical_bytes_verified': total,
          'same_contents_before_and_after': True, 'independently_writable_APFS_clones': True,
          'hardlinks_introduced': 0, 'no_packages_models_profiles_journals_or_archives_removed': True}
(root/'engine-block-sharing.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
