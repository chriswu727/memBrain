import hashlib
import json
import os
import subprocess
import tarfile
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
report = {'purpose': 'isolated native PostgreSQL 16.15 compatibility prototype; not a distributed wheel or release pass', 'completed': False, 'sources': [], 'commands': []}
prefix = root / 'pginstall'

def download(url, name):
    dest = root / name
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    dest.write_bytes(data)
    return dest, hashlib.sha256(data).hexdigest()

def run(args, cwd):
    result = subprocess.run(args, cwd=cwd, env={key: value for key, value in os.environ.items() if not key.startswith(('PG', 'MEMORY_'))}, check=False)
    report['commands'].append({'argv': list(map(str, args)), 'cwd': str(cwd), 'returncode': result.returncode})
    if result.returncode:
        raise RuntimeError(f'build command failed with {result.returncode}')

try:
    pg, digest = download('https://ftp.postgresql.org/pub/source/v16.15/postgresql-16.15.tar.bz2', 'postgresql-16.15.tar.bz2')
    with urllib.request.urlopen('https://ftp.postgresql.org/pub/source/v16.15/postgresql-16.15.tar.bz2.sha256', timeout=60) as response:
        upstream = response.read().decode().split()[0]
    assert digest == upstream
    report['sources'].append({'url': 'https://ftp.postgresql.org/pub/source/v16.15/postgresql-16.15.tar.bz2', 'sha256': digest, 'upstream_checksum_matches': True})
    with tarfile.open(pg) as archive:
        archive.extractall(root, filter='data')
    source = root / 'postgresql-16.15'
    run([str(source / 'configure'), f'--prefix={prefix}', '--without-readline', '--without-icu'], source)
    run(['make', '-j4'], source)
    run(['make', 'install'], source)
    vector, digest = download('https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.6.2', 'pgvector-0.6.2.tar.gz')
    report['sources'].append({'url': 'https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.6.2', 'sha256': digest, 'version_preserved_from_current_wheel': True, 'separate_upstream_checksum_available': False})
    with tarfile.open(vector) as archive:
        archive.extractall(root, filter='data')
    run(['make', '-j4', f'PG_CONFIG={prefix / "bin/pg_config"}'], root / 'pgvector-0.6.2')
    run(['make', 'install', f'PG_CONFIG={prefix / "bin/pg_config"}'], root / 'pgvector-0.6.2')
    report['version'] = subprocess.check_output([prefix / 'bin/postgres', '--version'], text=True).strip()
    report['completed'] = True
finally:
    (root / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n')
