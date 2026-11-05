"""Exercise a private offline snapshot through real native upgrade and staged rollback."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import socket
import sys
import time
import zipfile
from pathlib import Path

from psycopg import sql

from membrain import embedded_database, native_bundle, native_snapshot
from membrain.local_profile import _private, ensure_profile


def closed(port):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(("127.0.0.1", port)) != 0


def legacy_installation():
    spec = importlib.util.find_spec("pgserver")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("The explicit legacy check requires pgserver 0.1.4")
    return Path(next(iter(spec.submodule_search_locations))) / "pginstall"


def stop(layout):
    if not (layout.data / "PG_VERSION").exists():
        return
    if embedded_database._run(layout, "pg_ctl", "status", "-D", str(layout.data), timeout=30).returncode == 0:
        result = embedded_database._run(layout, "pg_ctl", "stop", "-D", str(layout.data),
                                        "-m", "fast", "-w", "-t", "60", timeout=90)
        if result.returncode:
            raise RuntimeError("Owned snapshot fixture did not stop")


def check(directory, cache_directory, *, legacy, require_root, large_file_bytes=0):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    _private(directory, directory=True)
    if require_root:
        assert os.name != "nt" and os.geteuid() == 0
    native_bundle._cache_directory = lambda: cache_directory
    prefix = native_bundle.prepare()
    first = legacy_installation() if legacy else prefix
    suffix = ".exe" if os.name == "nt" else ""
    version = native_bundle.subprocess.check_output(
        [str(first / "bin" / ("postgres" + suffix)), "--version"], env=native_bundle.environment(first))
    assert version.strip().endswith(b" 16.2" if legacy else b" 16.15")
    profile = ensure_profile(directory / "profile", database_engine="embedded")
    assert closed(profile.api_port) and closed(profile.database_port)
    report = {"completed": False, "model_calls": 0, "target": native_bundle.platform_key(),
              "scope": "offline snapshot component only; no automatic upgrader or default selector adoption",
              "legacy_upgrade": legacy, "root_service_account": require_root, "timings_ms": {}, "phase": "created"}
    assert type(large_file_bytes) is int and large_file_bytes >= 0
    report["large_file_bytes"] = large_file_bytes
    original = embedded_database._installation
    layouts = []

    def checkpoint(phase):
        report["phase"] = phase
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(phase, flush=True)

    def fingerprint():
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            rows = connection.execute("SELECT id,payload::text,embedding::text FROM snapshot_fixture ORDER BY id").fetchall()
            vector = connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
            indexes = connection.execute("SELECT c.relname,i.indisvalid,i.indisready FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indrelid='snapshot_fixture'::regclass ORDER BY 1").fetchall()
            result = connection.execute("SELECT id FROM snapshot_fixture ORDER BY embedding <-> '[9.123,2.456,3.789]'::vector LIMIT 10").fetchall()
        with embedded_database._admin_connection(profile, "postgres") as connection:
            roles = connection.execute("SELECT rolname,rolsuper,rolcanlogin,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls,rolpassword FROM pg_authid WHERE rolname='snapshot_owner'").fetchall()
            databases = connection.execute("SELECT datname,datallowconn FROM pg_database ORDER BY 1").fetchall()
        with embedded_database._admin_connection(profile, "snapshot_secondary") as connection:
            secondary = connection.execute("SELECT value FROM other_database").fetchall()
        value = {"rows": rows, "vector": vector, "indexes": indexes, "nearest": result,
                 "roles": roles, "databases": databases, "secondary": secondary}
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    checkpoint("initialize_original")
    try:
        embedded_database._installation = lambda: first
        source = embedded_database._layout(profile)
        layouts.append(source)
        embedded_database.start(profile)
        with embedded_database._admin_connection(profile, "postgres") as connection:
            connection.execute(sql.SQL("CREATE ROLE snapshot_owner LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(sql.Literal(profile.app_password)))
            connection.execute("CREATE DATABASE snapshot_secondary OWNER snapshot_owner")
        with embedded_database._admin_connection(profile, "snapshot_secondary") as connection:
            connection.execute("CREATE TABLE other_database(value text)")
            connection.execute("INSERT INTO other_database VALUES ('preserve a second database')")
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            connection.execute("CREATE EXTENSION vector")
            connection.execute("CREATE TABLE snapshot_fixture(id integer PRIMARY KEY,payload jsonb,embedding vector(3))")
            connection.execute("INSERT INTO snapshot_fixture SELECT n,jsonb_build_object('memory','synthetic-'||n),ARRAY[n::real,(n%19)::real,(n%13)::real]::vector FROM generate_series(1,1000)n")
            connection.execute("CREATE INDEX snapshot_hnsw ON snapshot_fixture USING hnsw(embedding vector_l2_ops)")
            connection.execute("CREATE INDEX snapshot_ivf ON snapshot_fixture USING ivfflat(embedding vector_cosine_ops) WITH(lists=10)")
            assert connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == ("0.6.2" if legacy else "0.8.6")
        before = fingerprint()
        embedded_database.stop(profile)
        configuration = source.data / "postgresql.conf"
        with configuration.open("ab") as stream:
            stream.write(b"\n# custom configuration must survive native rollback\nwork_mem = '8MB'\n")
        if require_root:
            assert source.account is not None
            os.chown(configuration, 0, source.account[1])
            configuration.chmod(0o640)
        if large_file_bytes:
            with (source.data / "membrain-large-snapshot-fixture").open("xb") as stream:
                stream.truncate(large_file_bytes)
            if require_root:
                os.chown(source.data / "membrain-large-snapshot-fixture", 0, source.account[1])
        configuration_bytes = configuration.read_bytes()
        baseline = native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES)
        checkpoint("snapshot_original")
        started = time.perf_counter()
        receipt = native_snapshot.create(source, directory / "snapshot")
        report["timings_ms"]["snapshot_create_verify"] = (time.perf_counter() - started) * 1000
        native_snapshot.verify(directory / "snapshot", receipt["receipt_sha256"])
        if large_file_bytes:
            with zipfile.ZipFile(directory / "snapshot/cluster.zip") as saved:
                member = saved.getinfo("data/membrain-large-snapshot-fixture")
                assert member.file_size == large_file_bytes
                assert large_file_bytes > zipfile.ZIP64_LIMIT and member.extract_version >= 45
                report["zip64_large_member_verified"] = True
        assert native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES) == baseline
        checkpoint("upgrade_and_change_original")
        embedded_database._installation = lambda: prefix
        upgraded = embedded_database._layout(profile)
        layouts.append(upgraded)
        assert upgraded.data == source.data
        embedded_database.start(profile)
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            assert connection.execute("SHOW server_version").fetchone()[0] == "16.15"
            connection.execute("ALTER EXTENSION vector UPDATE TO '0.8.6'")
            connection.execute("UPDATE snapshot_fixture SET payload='\"changed after backup\"' WHERE id=1")
        with embedded_database._admin_connection(profile, "postgres") as connection:
            connection.execute("ALTER ROLE snapshot_owner NOLOGIN")
        with embedded_database._admin_connection(profile, "snapshot_secondary") as connection:
            connection.execute("UPDATE other_database SET value='changed after backup'")
        assert fingerprint() != before
        embedded_database.stop(profile)
        changed = native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES)
        checkpoint("restore_new_staging")
        restored = embedded_database._Layout(source.binaries, source.data.parent / "snapshot-restored",
                                             source.data.parent / "snapshot-restored.log", source.account)
        layouts.append(restored)
        started = time.perf_counter()
        result = native_snapshot.restore(directory / "snapshot", receipt["receipt_sha256"], restored)
        report["timings_ms"]["staged_restore_verify"] = (time.perf_counter() - started) * 1000
        assert result["verified"] and native_snapshot._inventory(restored.data, native_snapshot.DEFAULT_MAX_BYTES) == baseline
        assert native_snapshot._inventory(source.data, native_snapshot.DEFAULT_MAX_BYTES) == changed
        assert (restored.data / "postgresql.conf").read_bytes() == configuration_bytes
        checkpoint("start_restored_original_engine")
        result = embedded_database._run(restored, "pg_ctl", "start", "-D", str(restored.data),
                                        "-l", str(restored.log), "-w", "-t", "90", timeout=120)
        if result.returncode:
            raise RuntimeError("Restored snapshot did not start with its original engine")
        assert fingerprint() == before
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            assert connection.execute("SHOW server_version").fetchone()[0] == ("16.2" if legacy else "16.15")
            assert connection.execute("SHOW work_mem").fetchone()[0] == "8MB"
        if large_file_bytes and sys.platform.startswith("linux"):
            import resource

            report["python_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            assert report["python_peak_rss_mib"] < 512
        report.update(completed=True, snapshot_receipt_sha256=receipt["receipt_sha256"],
                      snapshot_archive_sha256=receipt["archive_sha256"], entries=receipt["entries"],
                      data_bytes=receipt["data_bytes"], original_fingerprint=before,
                      original_unchanged_during_snapshot=True, upgraded_original_preserved_during_restore=True,
                      restored_complete_bytes_modes_owners_timestamps=True,
                      roles_second_database_vector_indexes_and_rows_restored=True,
                      original_engine_and_vector_restored=True, custom_configuration_preserved=True)
    except BaseException as error:
        report.update(error_type=type(error).__name__, error_code=getattr(error, "code", None))
        raise
    finally:
        for layout in reversed(layouts):
            try:
                stop(layout)
            except Exception as error:
                report.update(completed=False, cleanup_error_type=type(error).__name__)
        embedded_database._installation = original
        report["ports_closed"] = closed(profile.api_port) and closed(profile.database_port)
        report["completed"] = report["completed"] and report["ports_closed"]
        checkpoint("complete" if report["completed"] else report["phase"])
    assert report["completed"]
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cache-directory", type=Path, required=True)
    parser.add_argument("--legacy-upgrade", action="store_true")
    parser.add_argument("--require-root", action="store_true")
    parser.add_argument("--large-file-bytes", type=int, default=0)
    arguments = parser.parse_args()
    check(arguments.directory.resolve(), arguments.cache_directory.resolve(),
          legacy=arguments.legacy_upgrade, require_root=arguments.require_root,
          large_file_bytes=arguments.large_file_bytes)
