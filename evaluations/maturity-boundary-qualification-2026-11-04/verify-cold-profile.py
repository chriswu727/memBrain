import hashlib
import json
import shutil
import socket
import tarfile
from pathlib import Path

from membrain.local_profile import load_profile

root = Path(__file__).parent
directory = root / 'perf-e749a24-installation'
archive = root / 'canonical-profile-e749a24-v3.tar.gz'
profile = load_profile(directory)
assert not (directory / 'postgres/postmaster.pid').exists()
for port in (profile.api_port, profile.database_port):
    with socket.socket() as listener:
        listener.settimeout(.2)
        assert listener.connect_ex(('127.0.0.1', port)) != 0
registry = Path(profile.settings().recovery_registry_path)
assert registry.is_relative_to(root) and registry != root
files = {}
for folder in [directory, registry]:
    for path in folder.rglob('*'):
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as stream:
                files[str(path.relative_to(root))] = hashlib.file_digest(stream, 'sha256').hexdigest()
verified = {}
with tarfile.open(archive, mode='r|gz') as saved:
    for member in saved:
        if member.isfile():
            with saved.extractfile(member) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        elif member.islnk():
            actual = verified[member.linkname]
        else:
            continue
        assert member.name not in verified
        assert actual == files[member.name], member.name
        verified[member.name] = actual
assert verified == files
(root / 'cold-profile-files.sha256.json').write_text(json.dumps(files, indent=2) + '\n')
shutil.rmtree(directory)
with archive.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
report = {'canonical_exit_code': 0, 'fullscreen_exit_code': 1,
          'runtime_source': 'e749a24e86d45d25d1a06d9fcba223e9adf69fcb',
          'ports_closed_before_archive': True, 'archive': str(archive), 'archive_sha256': digest,
          'archive_bytes': archive.stat().st_size, 'regular_files_verified': len(files),
          'original_disposable_profile_removed': not directory.exists(), 'registry_preserved': registry.exists(),
          'verification': 'single forward stream; all regular-file SHA256 values compared',
          'prior_archive_attempts': 'two incomplete archives removed with hashes/errors retained; first verification interrupted to avoid repeated backward gzip seeks',
          'note': 'Private archive contains disposable credentials; never commit. The failing comparison and its fixture are preserved.'}
(root / 'canonical-profile-archive.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
