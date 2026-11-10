"""Task-owned full-suite run for the 2026-11-10 status audit; never uses an existing profile.

Usage, from the repository root: ``uv run python <this file> <new empty run directory>``.
"""
import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
SOURCE = Path.cwd()


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    import psycopg
    import pytest

    from membrain import desktop, embedded_database
    from membrain.local_profile import ensure_profile

    if ROOT is None:
        raise SystemExit('Pass a new run directory outside the repository.')
    ROOT.mkdir(parents=True, exist_ok=False)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', MEMBRAIN_SEMANTIC='0', MEMBRAIN_REQUIRE_BROWSER='1')
    paths = sorted((SOURCE / 'src').rglob('*.py')) + sorted((SOURCE / 'migrations').glob('*.sql'))
    hashes = {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    profile = ensure_profile(
        ROOT / 'database', database_engine='embedded', api_port=free_port(), database_port=free_port()
    )
    result = {'scope': 'local WSL2 full source suite for a status audit; not platform qualification'}
    started = time.time()
    try:
        desktop._prepare_database(profile)
        os.environ.update(
            MEMORY_DATABASE_URL=profile.database_url,
            MEMORY_MIGRATION_DATABASE_URL=profile.migration_database_url,
        )
        with psycopg.connect(profile.database_url) as conn:
            result['database'] = conn.execute(
                "select version(), extversion from pg_extension where extname='vector'"
            ).fetchone()
        print('Database:', result['database'], flush=True)
        result['pytest_exit'] = int(pytest.main([
            'tests', '-q', '-rs', '--durations=20',
            '--basetemp', str(ROOT / 'pytest'),
            '-o', 'tmp_path_retention_policy=failed', '-p', 'no:cacheprovider',
            f'--junitxml={ROOT / "junit.xml"}',
        ]))
    finally:
        embedded_database.stop(profile)
        result['database_stopped'] = not embedded_database.running(profile)
        result['seconds'] = round(time.time() - started)
        result['source_unchanged'] = all(
            hashlib.sha256((SOURCE / p).read_bytes()).hexdigest() == h for p, h in hashes.items()
        )
        (ROOT / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2), flush=True)
    return result.get('pytest_exit', 1)


if __name__ == '__main__':
    sys.exit(main())
