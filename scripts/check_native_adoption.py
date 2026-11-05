"""Exercise ordinary native startup, interrupted adoption and HTTP memory persistence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from membrain import desktop, embedded_database, native_bundle
from membrain.desktop_backup import backup
from membrain.desktop_connection import open_client
from membrain.desktop_restore import activate, restore
from membrain.local_profile import _private, ensure_profile, load_profile
from membrain.recovery_profile import authority_for, check_start_allowed, read_document


def worker(directory, cache):
    native_bundle._cache_directory = lambda: cache
    embedded_database._start_layout = lambda *args, **kwargs: os._exit(87)
    desktop.start(directory / "profile")
    raise AssertionError("The intended interrupted source start was not reached")


def fingerprint(profile):
    with embedded_database._admin_connection(profile, "agent_memory") as connection:
        rows = connection.execute("SELECT id,payload,embedding::text FROM adoption_fixture ORDER BY id").fetchall()
        connection.execute("SET enable_seqscan=off")
        nearest = connection.execute("SELECT id FROM adoption_fixture ORDER BY embedding <-> '[9.1,2.4,3.7]'::vector LIMIT 10").fetchall()
    return hashlib.sha256(json.dumps([rows, nearest]).encode()).hexdigest()


def check(directory, cache, *, legacy=False, restore_backup=False, require_root=False):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    _private(directory, directory=True)
    os.environ["MEMBRAIN_SEMANTIC"] = "0"
    native_bundle._cache_directory = lambda: cache
    report = {"completed": False, "model_calls": 0, "legacy_upgrade": legacy,
              "restore_requested": restore_backup, "root": require_root, "phase": "created"}
    profile = None
    restored = None

    def checkpoint(phase):
        report["phase"] = phase
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(phase, flush=True)

    try:
        if require_root:
            assert os.name != "nt" and os.geteuid() == 0
        assert embedded_database.default_engine() == "embedded"
        profile = ensure_profile(directory / "profile", database_engine=embedded_database.default_engine())
        before = profile
        original_identity = None
        if legacy:
            checkpoint("initialize_owned_legacy_fixture")
            prefix = embedded_database._legacy_installation()
            assert prefix is not None
            if require_root:
                account = embedded_database._service_account(embedded_database.LEGACY_SERVICE_ACCOUNT)
                parent = embedded_database.LEGACY_SHARED_ROOT / "clusters" / profile.installation_id
                parent.mkdir(mode=0o700, parents=True, exist_ok=False)
                os.chown(parent, *account)
                binaries = embedded_database._shared_binaries(prefix, embedded_database.LEGACY_SHARED_ROOT)
                layout = embedded_database._Layout(binaries / "pgserver/pginstall/bin", parent / "data",
                                                   parent / "postgres.log", account)
            else:
                layout = embedded_database._layout_from_source(profile, prefix)
            embedded_database._start_layout(profile, layout, initialize=True)
            desktop._bootstrap_application(profile)
            with embedded_database._admin_connection(profile, "postgres") as connection:
                original_identity = connection.execute("SELECT system_identifier::text FROM pg_control_system()").fetchone()[0]
            with embedded_database._admin_connection(profile, "agent_memory") as connection:
                assert connection.execute("SHOW server_version").fetchone()[0] == "16.2"
                connection.execute("CREATE TABLE adoption_fixture(id integer PRIMARY KEY,payload text,embedding vector(3))")
                connection.execute("INSERT INTO adoption_fixture SELECT n,'synthetic-'||n,ARRAY[n::real,(n%19)::real,(n%13)::real]::vector FROM generate_series(1,1000)n")
                connection.execute("CREATE INDEX adoption_hnsw ON adoption_fixture USING hnsw(embedding vector_l2_ops)")
                connection.execute("CREATE INDEX adoption_ivf ON adoption_fixture USING ivfflat(embedding vector_cosine_ops) WITH(lists=10)")
            original_rows = fingerprint(profile)
            result = embedded_database._run(layout, "pg_ctl", "stop", "-D", str(layout.data), "-m", "fast", "-w", "-t", "60")
            assert result.returncode == 0
        checkpoint("interrupt_after_durable_handoff_and_fuse")
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--directory", str(directory),
                                 "--cache-directory", str(cache)], timeout=360, check=False)
        assert result.returncode == 87
        profile = load_profile(profile.directory)
        assert profile.native_engine == "16.15"
        assert read_document(profile.directory / "native-source.json") is not None
        try:
            check_start_allowed(profile)
        except embedded_database.EmbeddedDatabaseError:
            pass
        else:
            raise AssertionError("Pending adoption admitted a direct client")
        checkpoint("ordinary_start_resumes_and_admits")
        assert desktop.start(profile.directory)["ready"]
        profile = load_profile(profile.directory)
        assert all(getattr(profile, name) == getattr(before, name) for name in (
            "installation_id", "brain_id", "tenant_id", "principal_id", "api_key", "admin_password", "app_password"))
        journal = read_document(profile.directory / "native-transition.json")
        assert journal["phase"] == "admitted"
        if original_identity is not None:
            assert journal["system_identifier"] == original_identity and fingerprint(profile) == original_rows
        with embedded_database._admin_connection(profile, "agent_memory") as connection:
            assert connection.execute("SHOW server_version").fetchone()[0] == "16.15"
            assert connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == "0.8.6"
        checkpoint("real_http_memory_and_cold_restart")
        with open_client(profile.directory, start_service=False) as client:
            assert client.observe("My cat is called Biscuit and she hates thunder.", conversation_id="adoption",
                                  branch_id="main", source_event_key="biscuit")["outcome"] == "completed"
        assert desktop.stop(profile.directory)["state"] == "stopped"
        assert desktop.start(profile.directory)["ready"]
        with open_client(profile.directory, start_service=False) as client:
            recalled = client.recall("what is my cat called")
            assert "Biscuit" in json.dumps(recalled)
        report.update(default_native_selector=True, handoff_interruption_exit=87, credentials_preserved=True,
                      original_cluster_preserved=True, admission_before_api=True, http_memory_after_cold_restart=True,
                      legacy_vector_rows_preserved=legacy)
        if restore_backup:
            checkpoint("private_backup_and_quarantined_restore")
            completed = backup(profile.directory, output=directory / "backup", request_id="adoption-backup")
            authority = authority_for(profile)
            result = restore(backup_path=directory / "backup", directory=directory / "restored",
                             registry_path=authority.registry.directory, request_id="adoption-restore")
            restored = load_profile(directory / "restored")
            assert result["state"] == "quarantined"
            try:
                desktop.start(restored.directory)
            except Exception:
                assert not desktop._port_open(restored.api_port)
            else:
                raise AssertionError("Quarantined restore started the API")
            head = authority.registry.head()
            activated = activate(restored.directory, recovery_epoch=result["recovery_epoch"],
                                 backup_id=completed["backup_id"], checkpoint_at=result["checkpoint"]["checkpoint_at"],
                                 retire_installation_id=profile.installation_id, expected_sequence=head["sequence"],
                                 expected_head_hash=head["head_hash"], acknowledge_host_reconciliation=True)
            assert activated["state"] == "active"
            checkpoint("activated_restore_admits_native_engine")
            assert desktop.start(restored.directory)["ready"]
            with open_client(restored.directory, start_service=False) as client:
                assert "Biscuit" in json.dumps(client.recall("what is my cat called"))
            if legacy:
                assert fingerprint(restored) == original_rows
            report.update(private_backup_restore=True, quarantine_blocks_api=True, restored_memory_recalled=True,
                          restored_credentials_rotated=restored.api_key != profile.api_key and restored.app_password != profile.app_password)
        report["completed"] = True
        checkpoint("completed")
    finally:
        for owned in (restored, profile):
            if owned is not None:
                if desktop._port_open(owned.api_port) or desktop._port_open(owned.database_port):
                    desktop.stop(owned.directory)
                assert not desktop._port_open(owned.api_port) and not desktop._port_open(owned.database_port)
        report["owned_ports_closed"] = True
        checkpoint(report["phase"])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cache-directory", type=Path, required=True)
    parser.add_argument("--legacy-upgrade", action="store_true")
    parser.add_argument("--restore-backup", action="store_true")
    parser.add_argument("--require-root", action="store_true")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.worker:
        worker(args.directory, args.cache_directory)
    else:
        check(args.directory, args.cache_directory, legacy=args.legacy_upgrade,
              restore_backup=args.restore_backup, require_root=args.require_root)
