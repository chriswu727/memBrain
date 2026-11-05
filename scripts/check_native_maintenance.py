"""Exercise real catalog/vector maintenance, interrupted closed databases and privilege boundaries."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

from membrain import embedded_database, native_bundle, native_maintenance, native_snapshot
from membrain.local_profile import _private, ensure_profile, load_profile

CLOSED = 'closed "quoted'


def closed(port):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(("127.0.0.1", port)) != 0


def choose(cache):
    native_bundle._cache_directory = lambda: cache
    prefix = native_bundle.prepare()
    embedded_database._installation = lambda: prefix
    return prefix


def worker(directory, cache, operation, commitment):
    profile = load_profile(directory / "profile")
    choose(cache)
    layout = embedded_database._layout(profile)
    update = native_maintenance._set_controls

    def crash(connection, row, allowed, limit):
        update(connection, row, allowed, limit)
        if row["name"] == "template0" and allowed:
            os._exit(73)

    native_maintenance._set_controls = crash
    native_maintenance.maintain(profile, layout, directory / "snapshot", commitment, operation)
    raise AssertionError("The intentional process exit was not reached")


def flags(profile):
    with embedded_database._admin_connection(profile, "postgres") as connection:
        return connection.execute("SELECT oid,datname,datallowconn,datconnlimit,datacl::text "
                                  "FROM pg_database ORDER BY oid").fetchall()


def statistics_visible(profile):
    with psycopg.connect(host="127.0.0.1", port=profile.database_port, user="maintenance_probe",
                          password=profile.app_password, dbname="agent_memory", connect_timeout=5) as connection:
        return [connection.execute("SELECT count(*) FROM pg_stats_ext WHERE statistics_name='maintenance_stat'").fetchone()[0],
                connection.execute("SELECT count(*) FROM pg_stats_ext_exprs WHERE statistics_name='maintenance_expr'").fetchone()[0]]


def fingerprint(profile):
    with embedded_database._admin_connection(profile, "agent_memory") as connection:
        connection.execute("SET enable_seqscan=off")
        connection.execute("SET hnsw.ef_search=1000")
        rows = connection.execute("SELECT id,payload::text,embedding::text FROM maintenance_fixture ORDER BY id").fetchall()
        near = connection.execute("SELECT id FROM maintenance_fixture ORDER BY embedding <-> '[9.123,2.456,3.789]'::vector LIMIT 10").fetchall()
        assert not connection.execute("SELECT 1 FROM pg_index WHERE NOT indisvalid OR NOT indisready").fetchall()
    return hashlib.sha256(json.dumps([rows, near]).encode()).hexdigest()


def check(directory, cache, *, legacy, require_root):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    _private(directory, directory=True)
    report = {"completed": False, "model_calls": 0, "target": native_bundle.platform_key(),
              "scope": "resumable SQL maintenance component only; default selector and lifecycle orchestrator unchanged",
              "legacy_upgrade": legacy, "root_service_account": require_root, "phase": "created"}
    profile = None
    original = embedded_database._installation

    def checkpoint(phase):
        report["phase"] = phase
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(phase, flush=True)

    try:
        if require_root:
            assert os.name != "nt" and os.geteuid() == 0
        checkpoint("prepare_cache")
        prefix = choose(cache)
        if legacy:
            spec = importlib.util.find_spec("pgserver")
            first = Path(next(iter(spec.submodule_search_locations))) / "pginstall"
        else:
            first = prefix
        embedded_database._installation = lambda: first
        profile = ensure_profile(directory / "profile", database_engine="embedded")
        assert closed(profile.api_port) and closed(profile.database_port)
        checkpoint("initialize_fixture")
        source = embedded_database._layout(profile)
        embedded_database._start_layout(profile, embedded_database._layout(profile),
                                               initialize=not embedded_database._layout(profile).data.exists())
        with embedded_database._admin_connection(profile, "postgres") as connection:
            connection.execute(sql.SQL("CREATE ROLE maintenance_probe LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(sql.Literal(profile.app_password)))
            connection.execute(sql.SQL("CREATE DATABASE {} WITH CONNECTION LIMIT 3").format(sql.Identifier(CLOSED)))
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            assert connection.execute("SHOW server_version").fetchone()[0] == ("16.2" if legacy else "16.15")
            connection.execute("CREATE EXTENSION vector")
            connection.execute("CREATE TABLE maintenance_fixture(id integer PRIMARY KEY,payload jsonb,embedding vector(3))")
            connection.execute("INSERT INTO maintenance_fixture SELECT n,jsonb_build_object('memory','synthetic-'||n),ARRAY[n::real,(n%19)::real,(n%13)::real]::vector FROM generate_series(1,1000)n")
            connection.execute("CREATE INDEX maintenance_hnsw ON maintenance_fixture USING hnsw(embedding vector_l2_ops)")
            connection.execute("CREATE INDEX maintenance_ivf ON maintenance_fixture USING ivfflat(embedding vector_cosine_ops) WITH(lists=10)")
            connection.execute("CREATE TABLE maintenance_private(a text,b text)")
            connection.execute("INSERT INTO maintenance_private SELECT 'private-synthetic-'||(n%3),'group-'||(n%3) FROM generate_series(1,1000)n")
            connection.execute("CREATE STATISTICS maintenance_stat(mcv) ON a,b FROM maintenance_private")
            connection.execute("CREATE STATISTICS maintenance_expr ON(lower(a)) FROM maintenance_private")
            connection.execute("ALTER STATISTICS maintenance_stat OWNER TO maintenance_probe")
            connection.execute("ALTER STATISTICS maintenance_expr OWNER TO maintenance_probe")
            connection.execute("ANALYZE maintenance_private")
        with embedded_database._admin_connection(profile, CLOSED) as connection:
            connection.execute('CREATE SCHEMA "vector lab"')
            connection.execute('CREATE EXTENSION vector WITH SCHEMA "vector lab"')
        with embedded_database._admin_connection(profile, "postgres") as connection:
            connection.execute(sql.SQL("ALTER DATABASE {} WITH ALLOW_CONNECTIONS false").format(sql.Identifier(CLOSED)))
        report["statistics_visible_before"] = statistics_visible(profile)
        assert report["statistics_visible_before"] == ([0, 1] if legacy else [0, 0])
        original_flags, original_rows = flags(profile), fingerprint(profile)
        embedded_database.stop(profile)
        checkpoint("snapshot_before_catalog_change")
        receipt = native_snapshot.create(source, directory / "snapshot")
        embedded_database._installation = lambda: prefix
        layout = embedded_database._layout(profile)
        assert layout.data == source.data
        embedded_database._start_layout(profile, embedded_database._layout(profile),
                                               initialize=not embedded_database._layout(profile).data.exists())
        operation = str(uuid4())
        checkpoint("interrupt_closed_database_opening")
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--directory", str(directory),
                                 "--cache-directory", str(cache), "--operation", operation,
                                 "--commitment", receipt["receipt_sha256"]], capture_output=True, timeout=90)
        diagnostics = {"returncode": result.returncode, "stdout": result.stdout.decode("utf-8", "replace"),
                       "stderr": result.stderr.decode("utf-8", "replace")}
        for field in ("stdout", "stderr"):
            for secret in (profile.api_key, profile.admin_password, profile.app_password):
                diagnostics[field] = diagnostics[field].replace(secret, "[redacted]")
        (directory / "worker-result.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
        report["worker_returncode"] = result.returncode
        assert result.returncode == 73
        current = next(row for row in flags(profile) if row[1] == "template0")
        assert current[2:4] == (True, 0)
        try:
            with psycopg.connect(host="127.0.0.1", port=profile.database_port, user="maintenance_probe",
                                  password=profile.app_password, dbname="template0", connect_timeout=5):
                raise AssertionError("The interrupted opening must not admit an ordinary role")
        except psycopg.OperationalError as error:
            assert error.sqlstate in (None, "53300")
            assert 'too many connections for database "template0"' in str(error)
            report["ordinary_connection_error_sqlstate"] = error.sqlstate
        checkpoint("restore_flags_before_rejecting_bad_backup")
        try:
            native_maintenance.maintain(profile, layout, directory / "missing-snapshot",
                                         receipt["receipt_sha256"], operation)
            raise AssertionError("A missing backup must block maintenance")
        except native_maintenance.NativeMaintenanceError as error:
            assert error.code == "native_maintenance_backup"
        assert flags(profile) == original_flags
        checkpoint("resume_catalog_and_vector")
        status = native_maintenance.maintain(profile, layout, directory / "snapshot",
                                             receipt["receipt_sha256"], operation)
        assert status["state"] == "complete" and status["database_count"] == len(original_flags)
        assert flags(profile) == original_flags and fingerprint(profile) == original_rows
        assert statistics_visible(profile) == [0, 0]
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            assert connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == "0.8.6"
        journal = json.loads((layout.data.parent / ".native-maintenance/catalog.json").read_text())
        assert journal["state"] == "complete" and all(row["complete"] for row in journal["databases"])
        closed_row = next(row for row in journal["databases"] if row["name"] == CLOSED)
        with embedded_database._admin_connection(profile, "postgres") as connection:
            native_maintenance._set_controls(connection, closed_row, True, 0)
            try:
                with embedded_database._admin_connection(profile, CLOSED) as target:
                    assert target.execute("SELECT e.extversion,n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'").fetchone() == ("0.8.6", "vector lab")
            finally:
                native_maintenance._restore_controls(connection, [closed_row])
        checkpoint("repeat_and_restart")
        native_maintenance.maintain(profile, layout, directory / "snapshot", receipt["receipt_sha256"], operation)
        embedded_database.stop(profile)
        embedded_database._start_layout(profile, embedded_database._layout(profile),
                                               initialize=not embedded_database._layout(profile).data.exists())
        assert flags(profile) == original_flags and fingerprint(profile) == original_rows
        assert statistics_visible(profile) == [0, 0]
        report.update(completed=True, database_count=len(original_flags), snapshot_receipt_sha256=receipt["receipt_sha256"],
                      deliberate_worker_exit=73, interrupted_opening_blocks_ordinary_role=True,
                      flags_restored_before_backup_rejection=True, closed_flags_limits_and_acls_preserved=True,
                      resumed_all_database_catalog_repair=True, public_and_custom_schema_vector_upgraded=True,
                      complete_vector_rows_and_nearest_results_preserved=True,
                      nonowner_statistics_hidden_after_repair=True, repeat_and_restart_verified=True)
    except BaseException as error:
        report.update(error_type=type(error).__name__, error_code=getattr(error, "code", None))
        raise
    finally:
        if profile is not None:
            try:
                embedded_database.stop(profile)
            except Exception as error:
                report.update(completed=False, cleanup_error_type=type(error).__name__)
            report["ports_closed"] = closed(profile.api_port) and closed(profile.database_port)
        else:
            report["ports_closed"] = None
        embedded_database._installation = original
        report["completed"] = report["completed"] and report["ports_closed"] is True
        checkpoint("complete" if report["completed"] else report["phase"])
    assert report["completed"]
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cache-directory", type=Path, required=True)
    parser.add_argument("--legacy-upgrade", action="store_true")
    parser.add_argument("--require-root", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--operation")
    parser.add_argument("--commitment")
    arguments = parser.parse_args()
    if arguments.worker:
        worker(arguments.directory.resolve(), arguments.cache_directory.resolve(), arguments.operation, arguments.commitment)
    else:
        check(arguments.directory.resolve(), arguments.cache_directory.resolve(),
              legacy=arguments.legacy_upgrade, require_root=arguments.require_root)
