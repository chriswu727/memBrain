import hashlib
import json
import posixpath
import tarfile
import zipfile
from pathlib import Path

root = Path(__file__).parent
entries = [
    ('macos-arm64', 'ddd1718406bd4bd7a9ead19afc01a63fa29687264df81be6db90eb7ab89f558c', 41966197762, 127043649433),
    ('macos-x86_64', '453823a922af3ec789d6a78588d5d421468b0647247cf732453e280f8e1655f5', 41966197762, 127043649507),
    ('linux-x86_64', '9f46784b2f286de80acc76efa721b4edff63c7ec7d5c5063994924e90c8df380', 41966197762, 127043649408),
    ('linux-aarch64', 'b3f86336176adfddcd7bb00144f9ac4a839a76102bf04fa3f93a93fdc5377991', 41966197762, 127043649409),
    ('windows-x86_64', '251fdc3e51fb0bf039d45f0c6c0f43415f0767efd6d4c7b4c0918365ba040d73', 41969028210, 127052671478),
]
results = []
for target, expected, run, job in entries:
    path = root / f'native-{target}-lts.zip'
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected
    with zipfile.ZipFile(path) as saved:
        prefix = 'native-artifacts/'
        manifest = json.loads(saved.read(prefix + 'manifest.json'))
        hashes = json.loads(saved.read(prefix + 'artifacts.json'))
        qualification = json.loads(saved.read(prefix + 'qualification.json'))
        assert qualification['completed'] and qualification['port_closed']
        assert qualification['encrypted_connection']['ssl']
        assert manifest['postgres'] == '16.15' and manifest['vector'] == '0.8.6'
        assert all(value.endswith(' 16.15') for value in qualification['tools'].values())
        assert qualification['legacy_upgrade'] == (target != 'linux-aarch64')
        for name, record in hashes.items():
            assert Path(name).name == name
            with saved.open(prefix + name) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == record['sha256']
        if target.startswith(('macos', 'windows')):
            assert manifest['openssl']['version'].startswith('OpenSSL 3.5.9 ')
        expected_files = {row['path']: row['sha256'] for row in manifest['files']}
        verified, links = {}, {}
        with saved.open(prefix + 'engine.tar.gz') as stream, tarfile.open(fileobj=stream, mode='r|gz') as archive:
            for member in archive:
                assert member.name == 'pginstall' or member.name.startswith('pginstall/')
                name = member.name.removeprefix('pginstall/')
                if member.isfile():
                    with archive.extractfile(member) as contents:
                        verified[name] = hashlib.file_digest(contents, 'sha256').hexdigest()
                    assert verified[name] == expected_files[name]
                elif member.issym() or member.islnk():
                    destination = (posixpath.join(posixpath.dirname(member.name), member.linkname)
                                   if member.issym() else member.linkname)
                    destination = posixpath.normpath(destination)
                    assert destination.startswith('pginstall/')
                    links[name] = destination.removeprefix('pginstall/')
                else:
                    assert member.isdir()
        for name, destination in links.items():
            seen = {name}
            while destination in links:
                assert destination not in seen
                seen.add(destination)
                destination = links[destination]
            verified[name] = verified[destination]
            assert verified[name] == expected_files[name]
        assert verified == expected_files
        metadata = root / 'platform-evidence' / target
        metadata.mkdir(parents=True)
        for name in ('manifest.json', 'artifacts.json', 'qualification.json', 'PGVECTOR-LICENSE', 'POSTGRESQL-COPYRIGHT'):
            (metadata / name).write_bytes(saved.read(prefix + name))
        results.append({'target': target, 'workflow_run': run, 'job': job,
                        'artifact_sha256': expected, 'artifact_bytes': path.stat().st_size,
                        'files_verified': len(verified), 'legacy_upgrade': qualification['legacy_upgrade'],
                        'fixture_rows': qualification['stages'][0]['rows'],
                        'ports_closed': True, 'encrypted_connection': qualification['encrypted_connection'],
                        'openssl_source': manifest['openssl']['source'],
                        'openssl_version': manifest['openssl']['version'].splitlines()[0]})
report = {'completed': True, 'scope': 'five per-platform candidate results from two runs, not one all-green matrix or default-runtime acceptance',
          'platforms': results, 'default_runtime_changed': False,
          'note': 'Windows reuses the engine built in run41966608340; only qualification/profile ACL source changed afterward.'}
(root / 'candidate-platforms.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
