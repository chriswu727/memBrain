"""Verify packaged native resources against the installed supplier and a real database."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from membrain import embedded_database, native_bundle
from membrain.local_profile import ensure_profile


def closed(port):
    with socket.socket() as connection:
        connection.settimeout(.2)
        return connection.connect_ex(("127.0.0.1", port)) != 0


def check(directory, cache_directory=None):
    directory.mkdir(parents=True, exist_ok=False)
    cache_directory = cache_directory or directory / "cache"
    native_bundle._cache_directory = lambda: cache_directory
    report = {"completed": False, "model_calls": 0, "phase": "created",
              "scope": "candidate cache integration only; default embedded selector is not overridden in the product",
              "cache_preexisting": cache_directory.exists(),
              "timings_ms": {}}

    def checkpoint(phase):
        report["phase"] = phase
        with (directory / "result.json").open("w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(phase, flush=True)

    profile = None
    original = embedded_database._installation
    checkpoint("supplier")
    try:
        assert native_bundle.available()
        assert "postgresql_binaries" not in sys.modules
        key, entry, archive = native_bundle._source()
        report["target"] = key
        before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in archive.parent.iterdir() if path.is_file()}
        checkpoint("cache_first_prepare")
        started = time.perf_counter()
        prefix = native_bundle.prepare()
        report["timings_ms"]["first_prepare"] = (time.perf_counter() - started) * 1000
        checkpoint("cache_warm_prepare")
        started = time.perf_counter()
        assert native_bundle.prepare() == prefix
        report["timings_ms"]["warm_prepare"] = (time.perf_counter() - started) * 1000
        assert native_bundle._validate_tree(prefix, native_bundle._manifest(entry))
        checkpoint("profile")
        profile = ensure_profile(directory / "profile", database_engine="embedded")
        assert closed(profile.api_port) and closed(profile.database_port)
        embedded_database._installation = lambda: prefix
        checkpoint("database_start")
        embedded_database.start(profile)
        checkpoint("database_write")
        with embedded_database._admin_connection(profile, "agent_memory") as conn:
            assert conn.execute("SHOW server_version").fetchone()[0] == "16.15"
            assert conn.execute("SHOW shared_buffers").fetchone()[0] == "128MB"
            conn.execute("CREATE EXTENSION vector")
            assert conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == "0.8.6"
            conn.execute("CREATE TABLE cached_fixture (id integer PRIMARY KEY, embedding vector(3))")
            conn.execute("INSERT INTO cached_fixture VALUES (1, '[1,2,3]')")
        checkpoint("client_dump")
        command, environment = embedded_database.client_command(
            profile, "pg_dump", "--username=postgres", "--dbname=agent_memory",
            "--table=cached_fixture", "--data-only", "--inserts")
        assert Path(command[0]).is_relative_to(prefix)
        result = subprocess.run(command, env=environment, capture_output=True, check=True, timeout=10)
        assert b"INSERT INTO public.cached_fixture VALUES (1, '[1,2,3]');" in result.stdout
        checkpoint("database_restart")
        embedded_database.stop(profile)
        embedded_database.start(profile)
        with embedded_database._admin_connection(profile, "agent_memory") as conn:
            assert conn.execute("SELECT id,embedding::text FROM cached_fixture").fetchall() == [(1, "[1,2,3]")]
        report.update(verified_files=entry["native_files"], restart_preserves_rows=True,
                      cached_client_dump_preserves_row=True,
                      supplier_unchanged=before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                                   for path in archive.parent.iterdir() if path.is_file()},
                      supplier_python_executed="postgresql_binaries" in sys.modules,
                      cache_prefix=str(prefix))
        assert report["supplier_unchanged"] and not report["supplier_python_executed"]
        report["completed"] = True
    except BaseException as error:
        report.update(error_type=type(error).__name__, error_code=getattr(error, "code", None))
        raise
    finally:
        try:
            if profile is not None and embedded_database._installation is not original:
                embedded_database.stop(profile)
        except Exception as error:
            report.update(completed=False, cleanup_error_type=type(error).__name__,
                          cleanup_error_code=getattr(error, "code", None))
        finally:
            embedded_database._installation = original
            report["ports_closed"] = (closed(profile.api_port) and closed(profile.database_port)
                                      if profile is not None else None)
            report["completed"] = report["completed"] and report["ports_closed"] is True
            checkpoint("complete" if report["completed"] else report["phase"])
    assert report["completed"] and report["ports_closed"] and report["supplier_unchanged"]
    assert not report["supplier_python_executed"]
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cache-directory", type=Path)
    arguments = parser.parse_args()
    check(arguments.directory.resolve(), arguments.cache_directory.resolve() if arguments.cache_directory else None)
