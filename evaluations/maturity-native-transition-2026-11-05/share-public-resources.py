import ctypes
import hashlib
import json
import os
import secrets
from pathlib import Path

root = Path(__file__).parent
source = Path('/Users/yichen/tmp/membrain-review-20261029/src/membrain/resources/native')
parents = [root.parent/name for name in ('membrain-native-cache-20261104','membrain-native-snapshot-20261104',
    'membrain-native-maintenance-20261105','membrain-native-environment-20261105','membrain-native-engine-store-20261105')]
library = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
library.clonefile.argtypes = [ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
library.clonefile.restype = ctypes.c_int
count = total = 0

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

for parent in parents:
    for installed in parent.glob('wheel-installed*'):
        target_root=installed/'membrain/resources/native'
        if not target_root.is_dir():
            continue
        for original in source.iterdir():
            target=target_root/original.name
            if not original.is_file() or not target.is_file() or original.is_symlink() or target.is_symlink():
                continue
            before=target.stat()
            assert before.st_uid==os.getuid() and before.st_nlink==1
            if before.st_size!=original.stat().st_size or digest(target)!=digest(original):
                continue
            expected=digest(target)
            temporary=target.with_name('.cow-'+secrets.token_hex(12))
            if library.clonefile(os.fsencode(original),os.fsencode(temporary),0):
                raise OSError(ctypes.get_errno(),'Public resource clone failed')
            temporary.chmod(before.st_mode&0o777)
            os.utime(temporary,ns=(before.st_atime_ns,before.st_mtime_ns))
            assert digest(temporary)==expected and digest(target)==expected and target.stat().st_ino==before.st_ino
            assert temporary.stat().st_nlink==1 and temporary.stat().st_ino!=original.stat().st_ino
            os.replace(temporary,target)
            assert digest(target)==expected and target.stat().st_nlink==1
            count+=1;total+=before.st_size

report={'public_resource_files_cloned':count,'logical_bytes_verified':total,'independently_writable_APFS_clones':True,
        'contents_unchanged':True,'hardlinks_introduced':0,'no_packages_models_profiles_journals_or_archives_removed':True}
(root/'resource-block-sharing.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
