"""Qualify native transition recovery, independent authorities and durable admission."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
from dataclasses import replace
from pathlib import Path

from psycopg import sql

from membrain import embedded_database, native_bundle, native_engine_store, native_transition
from membrain.cli import bootstrap
from membrain.helpers import Principal
from membrain.local_profile import _private, ensure_profile, load_profile
from membrain.recovery_profile import ensure_authority, read_document
from membrain.service import MemoryService
from membrain.storage import Database


def closed(port):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(("127.0.0.1", port)) != 0


def application(profile):
    with contextlib.redirect_stdout(io.StringIO()):
        bootstrap(profile.settings(), app_password=profile.app_password)
    MemoryService(Database(profile.database_url)).ensure_brain(
        Principal(profile.tenant_id, profile.principal_id), profile.brain_id, profile.name)
    ensure_authority(profile)


def fingerprint(profile):
    with embedded_database._admin_connection(profile, "agent_memory") as connection:
        connection.execute("SET enable_seqscan=off")
        connection.execute("SET hnsw.ef_search=1000")
        rows = connection.execute("SELECT id,payload::text,embedding::text FROM transition_fixture ORDER BY id").fetchall()
        near = connection.execute("SELECT id FROM transition_fixture ORDER BY embedding <-> '[9.123,2.456,3.789]'::vector LIMIT 10").fetchall()
        indexes = connection.execute("SELECT c.relname,i.indisvalid,i.indisready FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indrelid='transition_fixture'::regclass ORDER BY 1").fetchall()
        vector = connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
    with embedded_database._admin_connection(profile, "postgres") as connection:
        roles = connection.execute("SELECT rolname,rolsuper,rolcanlogin,rolcreaterole,rolcreatedb,rolpassword FROM pg_authid WHERE rolname='transition_owner'").fetchall()
    return hashlib.sha256(json.dumps([rows, near, indexes, vector, roles]).encode()).hexdigest()


def start_old(profile, layout):
    result = embedded_database._run(layout, "pg_ctl", "start", "-D", str(layout.data), "-l", str(layout.log), "-w", "-t", "90")
    assert result.returncode == 0


def stop(layout):
    if layout.data.exists() and embedded_database._run(layout, "pg_ctl", "status", "-D", str(layout.data)).returncode == 0:
        result = embedded_database._run(layout, "pg_ctl", "stop", "-D", str(layout.data), "-m", "fast", "-w", "-t", "60")
        assert result.returncode == 0


def worker(directory, mode, fault):
    config = json.loads((directory / "fixture.json").read_text())
    profile = load_profile(Path(config["profile"]))
    if mode == "rollback":
        move = native_transition._move_absent
        count = 0

        def crash(source, destination):
            nonlocal count
            move(source, destination)
            count += 1
            if count == fault:
                os._exit(83)

        native_transition._move_absent = crash
        with native_transition.session(profile) as handle:
            handle.rollback()
    else:
        write = native_transition.write_document

        def crash(path, document):
            write(path, document)
            if document.get("phase") == "admitted":
                os._exit(85)

        native_transition.write_document = crash
        with native_transition.session(profile) as handle:
            handle.admit(lambda: application(profile))
    raise AssertionError("The deliberate process exit was not reached")


def child(directory, profile, mode, fault):
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--directory", str(directory),
                             "--worker", mode, "--rollback-fault", str(fault)], capture_output=True, timeout=300)
    diagnostics = {"returncode": result.returncode,
                   "stdout": result.stdout.decode("utf-8", "replace"), "stderr": result.stderr.decode("utf-8", "replace")}
    for field in ("stdout", "stderr"):
        for secret in (profile.api_key, profile.admin_password, profile.app_password):
            diagnostics[field] = diagnostics[field].replace(secret, "[redacted]")
    (directory / (mode + "-worker-result.json")).write_text(json.dumps(diagnostics, indent=2) + "\n")
    assert result.returncode == (83 if mode == "rollback" else 85)


def archive_failed_fixture(directory, profile, layout, failed):
    assert os.name != "nt" and os.geteuid() != 0
    stop(layout)
    assert closed(profile.api_port) and closed(profile.database_port) and not (failed / "postmaster.pid").exists()
    records, directories = {}, set()
    for path in (failed, *failed.rglob("*")):
        assert not path.is_symlink() and path.stat().st_uid == os.getuid()
        name = path.relative_to(failed.parent).as_posix()
        if path.is_file():
            assert path.stat().st_nlink == 1
            with path.open("rb") as stream:
                records[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        else:
            assert path.is_dir()
            directories.add(name)
    archive = directory / "completed-failed-fixture.tar.gz"
    descriptor = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        with tarfile.open(fileobj=stream, mode="w:gz") as saved:
            saved.add(failed, arcname=failed.name)
        stream.flush()
        os.fsync(stream.fileno())
    verified, saved_dirs = {}, set()
    with tarfile.open(archive, "r|gz") as saved:
        for member in saved:
            if member.isfile():
                with saved.extractfile(member) as stream:
                    verified[member.name] = hashlib.file_digest(stream, "sha256").hexdigest()
            else:
                assert member.isdir()
                saved_dirs.add(member.name)
    assert records == verified and directories == saved_dirs and closed(profile.database_port)
    for path in failed.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest() == records[path.relative_to(failed.parent).as_posix()]
    shutil.rmtree(failed)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (directory / "fixture-archive-summary.json").write_text(json.dumps({
        "owned_terminal_synthetic_pgdata_only": True, "ports_closed_before_removal": True,
        "files_verified": len(records), "directories_verified": len(directories),
        "archive_bytes": archive.stat().st_size, "archive_sha256": digest, "archive_mode": "0600",
        "profiles_journals_snapshots_engines_logs_preserved": True}, indent=2) + "\n")
    start_old(profile, layout)


def check(directory, cache, *, legacy, require_root, legacy_location, fault, reuse_source, archive_fixture):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    _private(directory, directory=True)
    report = {"completed": False, "model_calls": 0, "target": native_bundle.platform_key(), "phase": "created",
              "scope": "durable transition internal controller; default selection and installer handoff not adopted",
              "legacy_upgrade": legacy, "root_service_account": require_root, "legacy_location": legacy_location,
              "rollback_move_fault": fault, "reused_owned_fixture": reuse_source is not None}
    profile = source = target = None
    original_installation = embedded_database._installation

    def checkpoint(phase):
        report["phase"] = phase
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(phase, flush=True)

    try:
        if require_root:
            assert os.name != "nt" and os.geteuid() == 0
        assert not legacy_location or require_root
        native_bundle._cache_directory = lambda: cache
        prefix = native_bundle.prepare()
        if reuse_source:
            assert legacy and not require_root
            metadata = read_document(reuse_source)
            assert metadata["owned_synthetic_fixture"] is True
            profile = load_profile(Path(metadata["profile"]))
            assert profile.installation_id == metadata["installation_id"]
            engine = native_engine_store.verify(Path(metadata["engine_directory"]), metadata["engine_commitment"])
            source = embedded_database._Layout(engine.prefix / "bin", Path(metadata["data"]),
                                               profile.directory / "transition-fixture.log", None)
            assert closed(profile.api_port) and closed(profile.database_port)
            start_old(profile, source)
        else:
            spec = importlib.util.find_spec("pgserver") if legacy else None
            first = Path(next(iter(spec.submodule_search_locations))) / "pginstall" if legacy else prefix
            engine = native_engine_store.preserve(first, directory / "original-engine")
            profile = ensure_profile(directory / "profile", database_engine="embedded")
            assert closed(profile.api_port) and closed(profile.database_port)
            embedded_database._installation = lambda: engine.prefix
            if legacy_location:
                account = embedded_database._service_account(embedded_database.LEGACY_SERVICE_ACCOUNT)
                parent = embedded_database.LEGACY_SHARED_ROOT / "clusters" / profile.installation_id
                parent.mkdir(mode=0o700, parents=True, exist_ok=False)
                os.chown(parent, *account)
                binaries = embedded_database._shared_binaries(engine.prefix, embedded_database.LEGACY_SHARED_ROOT)
                initial = embedded_database._Layout(binaries / "pgserver/pginstall/bin", parent / "data", parent / "postgres.log", account)
                source = initial
                embedded_database._initialize(profile, initial)
            else:
                source = embedded_database._layout(profile)
            embedded_database.start(profile)
            source = embedded_database._layout(profile)
        checkpoint("initialize_original_fixture")
        with embedded_database._admin_connection(profile, "postgres") as connection:
            connection.execute(sql.SQL("CREATE ROLE transition_owner LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Literal(profile.app_password)))
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            assert connection.execute("SHOW server_version").fetchone()[0] == ("16.2" if legacy else "16.15")
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.execute("CREATE TABLE transition_fixture(id integer PRIMARY KEY,payload jsonb,embedding vector(3))")
            connection.execute("INSERT INTO transition_fixture SELECT n,jsonb_build_object('memory','synthetic-'||n),ARRAY[n::real,(n%19)::real,(n%13)::real]::vector FROM generate_series(1,1000)n")
            connection.execute("CREATE INDEX transition_hnsw ON transition_fixture USING hnsw(embedding vector_l2_ops)")
            connection.execute("CREATE INDEX transition_ivf ON transition_fixture USING ivfflat(embedding vector_cosine_ops) WITH(lists=10)")
        before = fingerprint(profile)
        embedded_database._installation = lambda: prefix
        target = replace(source, binaries=prefix / "bin") if reuse_source else embedded_database._layout(profile)
        assert target.data == source.data and target.account == source.account
        (directory / "fixture.json").write_text(json.dumps({"profile": str(profile.directory)}) + "\n")
        checkpoint("prepare_target")
        with native_transition.session(profile, target, original=engine) as handle:
            handle.prepare()
            first_operation = handle.journal["operation_id"]
            first_backup = handle.journal["snapshot"].copy()
        checkpoint("hard_exit_during_recovery")
        child(directory, profile, "rollback", fault)
        assert closed(profile.api_port) and closed(profile.database_port)
        checkpoint("resume_from_profile_journal_without_path_discovery")
        with native_transition.session(profile) as handle:
            handle.rollback()
            assert handle.layout.data == source.data and handle.layout.account == source.account
            assert handle.journal["snapshot"] == first_backup and fingerprint(profile) == before
            failed = Path(handle.journal["restore"]["failed"])
            old_layout = handle._old()
            assert failed.exists()
            assert (handle.maintenance / ("catalog-" + first_operation + ".failed.json")).exists()
        if archive_fixture:
            assert reuse_source is not None
            archive_failed_fixture(directory, profile, old_layout, failed)
        checkpoint("explicit_new_operation_and_interrupted_application_setup")
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            connection.execute("UPDATE transition_fixture SET payload='\"between operations\"' WHERE id=1")

        def partial_application():
            application(profile)
            raise RuntimeError("Deliberate interruption after independent authority creation")

        with native_transition.session(profile, retry_rolled_back=True) as handle:
            assert handle.journal["operation_id"] != first_operation
            handle.prepare()
            try:
                handle.admit(partial_application)
                raise AssertionError("Partial application initialization must fail")
            except native_transition.NativeTransitionError as error:
                assert error.code == "native_transition_application"
            try:
                handle.rollback()
                raise AssertionError("A newly created independent authority must block rollback")
            except native_transition.NativeTransitionError as error:
                assert error.code == "native_transition_authority"
        checkpoint("hard_exit_after_durable_admission")
        child(directory, profile, "admission", fault)
        checkpoint("verify_admission_blocks_old_snapshot_after_new_write")
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            connection.execute("UPDATE transition_fixture SET payload='\"write after admission\"' WHERE id=2")
        after = fingerprint(profile)
        with native_transition.session(profile) as handle:
            assert handle.prepare()["state"] == "admitted"
            try:
                handle.rollback()
                raise AssertionError("Admission must permanently block automatic rollback")
            except native_transition.NativeTransitionError as error:
                assert error.code == "native_transition_admitted"
            assert fingerprint(profile) == after
        report.update(completed=True, worker_exit_during_recovery=83, worker_exit_after_admission=85,
                      original_rows_roles_vector_indexes_and_nearest_restored=True,
                      original_backup_immutable_during_resume=True, failed_target_preserved_or_privately_archived=True,
                      target_sql_journal_archived=True, original_data_location_and_account_retained=True,
                      new_operation_uses_fresh_snapshot=True, independent_authority_blocks_rollback=True,
                      application_schema_and_authority_reconciled=True, admission_durable_before_api_launch=True,
                      post_admission_write_preserved=True)
    except BaseException as error:
        report.update(error_type=type(error).__name__, error_code=getattr(error, "code", None))
        raise
    finally:
        if target is not None or source is not None:
            try:
                stop(target or source)
            except Exception as error:
                report.update(completed=False, cleanup_error_type=type(error).__name__)
        if profile is not None:
            report["ports_closed"] = closed(profile.api_port) and closed(profile.database_port)
        embedded_database._installation = original_installation
        report["completed"] = report["completed"] and report.get("ports_closed") is True
        checkpoint("complete" if report["completed"] else report["phase"])
    assert report["completed"]
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cache-directory", type=Path)
    parser.add_argument("--legacy-upgrade", action="store_true")
    parser.add_argument("--require-root", action="store_true")
    parser.add_argument("--legacy-location", action="store_true")
    parser.add_argument("--rollback-fault", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--worker", choices=("rollback", "admission"))
    parser.add_argument("--reuse-source", type=Path)
    parser.add_argument("--archive-completed-failed-fixture", action="store_true")
    args = parser.parse_args()
    if args.worker:
        worker(args.directory.resolve(), args.worker, args.rollback_fault)
    else:
        if args.cache_directory is None:
            parser.error("--cache-directory is required for qualification")
        check(args.directory.resolve(), args.cache_directory.resolve(), legacy=args.legacy_upgrade,
              require_root=args.require_root, legacy_location=args.legacy_location, fault=args.rollback_fault,
              reuse_source=args.reuse_source, archive_fixture=args.archive_completed_failed_fixture)
