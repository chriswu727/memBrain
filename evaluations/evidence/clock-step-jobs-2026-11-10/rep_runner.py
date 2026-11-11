"""python rep_runner.py RUN_DIR REPS MODE tests...  MODE: none | monotonic | skew
Creates one fresh embedded database, runs pytest REPS times on it, stops the database."""
import json
import os
import socket
import sys
from pathlib import Path

def _trigger(name, body, events='INSERT'):
    return (f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {body} RETURN NEW; END $$;"
            f"DROP TRIGGER IF EXISTS {name} ON memory_jobs;"
            f"CREATE TRIGGER {name} BEFORE {events} ON memory_jobs FOR EACH ROW EXECUTE FUNCTION {name}();")

# Triggers fire alphabetically: a_* (fault) before b_* (fix emulation).
TRIGGERS = {
    # Fault injection: a backward wall-clock step of 2 s right after ~3% of job inserts makes that job look
    # 2 s newer (created_at) and not yet due (available_at) to everything that follows.
    'skew': _trigger('a_flaky_skew', "IF random() < 0.03 THEN NEW.created_at := NEW.created_at + interval '2 seconds';"
                     " NEW.available_at := NEW.available_at + interval '2 seconds'; END IF;"),
    'skew_created': _trigger('a_flaky_skew', "IF random() < 0.03 THEN NEW.created_at := NEW.created_at + interval '2 seconds'; END IF;"),
    'skew_available': _trigger('a_flaky_skew', "IF random() < 0.03 THEN NEW.available_at := NEW.available_at + interval '2 seconds'; END IF;"),
    # Fix emulation: per-brain creation order never goes backwards (as an identity column would give), and a job
    # inserted as due immediately (available_at <= created_at) stays claimable whatever the clock does later.
    'fixed': _trigger('b_flaky_fix', "NEW.created_at := greatest(NEW.created_at, coalesce((SELECT max(created_at) FROM memory_jobs"
                      " WHERE tenant_id=NEW.tenant_id AND brain_id=NEW.brain_id), '-infinity'::timestamptz) + interval '1 microsecond');"
                      " IF NEW.available_at <= NEW.created_at THEN NEW.available_at := NEW.available_at - interval '1 hour'; END IF;"),
}


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    import psycopg
    import pytest

    from membrain import desktop, embedded_database
    from membrain.local_profile import ensure_profile

    root = Path(sys.argv[1]).resolve()
    reps, mode, paths = int(sys.argv[2]), sys.argv[3], sys.argv[4:]
    root.mkdir(parents=True, exist_ok=False)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', MEMBRAIN_SEMANTIC='0',
                      MEMBRAIN_TEST_EMBEDDING_MODEL=os.environ.get('MEMBRAIN_TEST_EMBEDDING_MODEL', ''),
                      TIMEPLUG_LOG=str(root / 'timeplug.jsonl'))
    profile = ensure_profile(root / 'database', database_engine='embedded', api_port=free_port(), database_port=free_port())
    codes = []
    try:
        desktop._prepare_database(profile)
        os.environ.update(MEMORY_DATABASE_URL=profile.database_url,
                          MEMORY_MIGRATION_DATABASE_URL=profile.migration_database_url)
        if mode != 'none':
            with psycopg.connect(profile.migration_database_url, autocommit=True) as conn:
                for part in mode.split('+'):
                    conn.execute(TRIGGERS[part])
        for rep in range(reps):
            with open(root / 'timeplug.jsonl', 'a') as f:
                f.write(json.dumps({'ev': 'rep', 'rep': rep, 'mode': mode}) + '\n')
            code = int(pytest.main([*paths, '-q', '-p', 'timeplug', '--basetemp', str(root / f'pytest/{rep}'),
                                    '-o', 'tmp_path_retention_policy=failed', '-p', 'no:cacheprovider',
                                    '--junitxml', str(root / f'junit-{rep}.xml')]))
            codes.append(code)
            print(json.dumps({'rep': rep, 'code': code}), flush=True)
    finally:
        embedded_database.stop(profile)
        print(json.dumps({'codes': codes, 'database_stopped': not embedded_database.running(profile)}), flush=True)
    return max(codes) if codes else 1


if __name__ == '__main__':
    sys.exit(main())
