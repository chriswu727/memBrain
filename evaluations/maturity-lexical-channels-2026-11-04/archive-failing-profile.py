import hashlib
import json
import os
import shutil
import socket
import tarfile
from pathlib import Path

from membrain.local_profile import load_profile

root = Path(__file__).parent
directory = root / 'perf-merged-installation'
canonical = json.loads((root / 'canonical-command.json').read_text())
visual = json.loads((root / 'visual-command.json').read_text())
assert canonical['exit_code'] == 0 and visual['exit_code'] == 1
assert visual['source_unchanged'] and visual['all_ports_closed']
profile = load_profile(directory)
assert not (directory / 'postgres/postmaster.pid').exists()
for port in (profile.api_port, profile.database_port):
    with socket.socket() as connection:
        connection.settimeout(.2)
        assert connection.connect_ex(('127.0.0.1', port)) != 0
registry = Path(profile.settings().recovery_registry_path)
assert registry.is_relative_to(root) and registry != root and registry != directory
roots = [directory, registry]
files = {}
for folder in roots:
    for path in folder.rglob('*'):
        assert not path.is_symlink()
        assert path.is_dir() or path.is_file()
        if path.is_file():
            with path.open('rb') as stream:
                files[str(path.relative_to(root))] = hashlib.file_digest(stream, 'sha256').hexdigest()
archive = root / 'canonical-profile-merged.tar.gz'
descriptor = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'wb') as output, tarfile.open(fileobj=output, mode='w:gz', compresslevel=6) as saved:
    for folder in roots:
        saved.add(folder, arcname=str(folder.relative_to(root)))
verified = {}
with tarfile.open(archive, 'r|gz') as saved:
    for member in saved:
        if member.isfile():
            with saved.extractfile(member) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        elif member.islnk():
            actual = verified[member.linkname]
        else:
            assert member.isdir()
            continue
        assert member.name not in verified
        assert actual == files[member.name]
        verified[member.name] = actual
assert verified == files
with archive.open('rb') as stream:
    archive_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
(root / 'failing-profile-files.private.json').write_text(json.dumps(files, indent=2) + '\n')
(root / 'failing-profile-files.private.json').chmod(0o600)
shutil.rmtree(directory)
report = {'source': canonical['source_commit'], 'runtime_pin': canonical['runtime_pin'],
          'reason': 'retain the stopped failing fixture and its raw data for controlled CPU/SQL attribution',
          'archive': str(archive), 'archive_sha256': archive_hash, 'archive_bytes': archive.stat().st_size,
          'regular_files_verified': len(files), 'ports_closed_before_archive': True,
          'original_owned_profile_removed': not directory.exists(), 'registry_preserved': registry.exists(),
          'never_commit_archive_or_profiles': True}
(root / 'failing-profile-archive.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
