"""Exercise an unpublished native bundle, including an optional PostgreSQL 16.2 upgrade."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import tarfile
from pathlib import Path

import psycopg
from build_native_bundle import POSTGRES, TOOLS, VECTOR, digest, tool
from psycopg import sql

from membrain.local_profile import _private
from membrain.native_bundle import environment as native_environment


def free_port():
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return stream.getsockname()[1]


def is_closed(port):
    with socket.socket() as stream:
        stream.settimeout(0.2)
        return stream.connect_ex(("127.0.0.1", port)) != 0


def old_installation():
    spec = importlib.util.find_spec("pgserver")
    if spec is None or not spec.submodule_search_locations:
        raise ValueError("The explicit legacy upgrade check requires pgserver 0.1.4")
    return Path(next(iter(spec.submodule_search_locations))) / "pginstall"


def check(artifacts, work, *, legacy):
    checksums = json.loads((artifacts / "artifacts.json").read_text(encoding="utf-8"))
    for name, row in checksums.items():
        if Path(name).name != name or digest(artifacts / name) != row["sha256"]:
            raise ValueError("Artifact checksum mismatch")
    manifest = json.loads((artifacts / "manifest.json").read_text(encoding="utf-8"))
    if manifest["postgres"] != POSTGRES or manifest["vector"] != VECTOR:
        raise ValueError("Unexpected engine or extension manifest version")
    work.mkdir(mode=0o700, parents=True, exist_ok=False)
    _private(work, directory=True)
    with tarfile.open(artifacts / "engine.tar.gz") as archive:
        archive.extractall(work, filter="data")
    prefix = work / "pginstall"
    for row in manifest["files"]:
        path = prefix / row["path"]
        if not path.resolve(strict=True).is_relative_to(prefix) or digest(path) != row["sha256"]:
            raise ValueError("Relocated engine differs from its manifest")
    versions = {name: subprocess.check_output([tool(prefix, name), "--version"], text=True,
                                              env=native_environment(prefix)).strip()
                for name in TOOLS}
    if not all(value.endswith(" " + POSTGRES) for value in versions.values()):
        raise ValueError("Relocated tools do not match the pinned version")
    first = old_installation() if legacy else prefix
    if legacy and "16.2" != subprocess.check_output([tool(first, "postgres"), "--version"], text=True).strip().split()[-1]:
        raise ValueError("The legacy baseline must be PostgreSQL 16.2")
    data, log, password_file = work / "data", work / "postgres.log", work / ".password"
    port, password = free_port(), secrets.token_urlsafe(24)
    descriptor = os.open(password_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(password + "\n")
    _private(password_file)
    environment = native_environment(prefix)
    environment.update(PGPASSWORD=password, PGCONNECT_TIMEOUT="5", LC_ALL="C")
    report = {"completed": False, "model_calls": 0, "legacy_upgrade": legacy,
              "tools": versions, "manifest_sha256": digest(artifacts / "manifest.json"), "stages": [],
              "host": platform.platform(),
              "os_release": platform.freedesktop_os_release() if platform.system() == "Linux" else None}
    if platform.system() == "Linux" and manifest.get("libxml2"):
        dependencies = subprocess.check_output(["ldd", str(tool(prefix, "postgres"))],
                                               text=True, env=environment)
        resolved_xml = re.search(r"libxml2\.so\.2 => (.+?) \(", dependencies)
        if (not resolved_xml or Path(resolved_xml[1]).resolve() != (prefix / "lib/libxml2.so.2").resolve()
                or "not found" in dependencies):
            raise ValueError("Relocated PostgreSQL did not resolve the bundled XML library")
        report["server_dependencies"] = dependencies
    current = first

    def command(root, program, *arguments, capture=False):
        capture = capture or program == "initdb"
        result = subprocess.run([str(tool(root, program)), *map(str, arguments)], env=environment,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                              stderr=subprocess.STDOUT if capture else subprocess.DEVNULL,
                              text=True, check=False, timeout=180)
        if result.returncode:
            raise RuntimeError(f"{program} failed with exit code {result.returncode}: {result.stdout or ''}")
        return result

    def connection(database="postgres", *, sslmode="prefer"):
        return psycopg.connect(host="127.0.0.1", port=port, user="postgres", password=password,
                               dbname=database, connect_timeout=5, autocommit=True, sslmode=sslmode)

    def start(root):
        nonlocal current
        current = root
        command(root, "pg_ctl", "start", "-D", data, "-l", log, "-w", "-t", "90")

    def stop():
        command(current, "pg_ctl", "stop", "-D", data, "-m", "fast", "-w", "-t", "60")

    def fixture_fingerprint():
        with connection("agent_memory") as conn:
            rows = conn.execute("SELECT id, payload::text, embedding::text FROM fixture ORDER BY id").fetchall()
            return {"rows": len(rows), "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest()}

    try:
        command(first, "initdb", "-D", data, "-U", "postgres", "-A", "scram-sha-256",
                "--pwfile", password_file, "-E", "UTF8", "--locale=C", "--no-instructions")
        password_file.unlink()
        with (data / "postgresql.conf").open("a", encoding="utf-8") as stream:
            stream.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\nunix_socket_directories=''\nshared_buffers=32MB\n")
        start(first)
        with connection() as conn:
            conn.execute("CREATE DATABASE agent_memory")
        with connection("agent_memory") as conn:
            conn.execute("CREATE EXTENSION vector")
            conn.execute("CREATE TABLE fixture (id integer PRIMARY KEY, payload jsonb NOT NULL, embedding vector(3))")
            conn.execute("INSERT INTO fixture SELECT n, jsonb_build_object('text', 'synthetic-' || n, 'duplicate', n % 7), ARRAY[n::real, (n % 19)::real, (n % 13)::real]::vector FROM generate_series(1,1000) n")
            conn.execute("CREATE INDEX fixture_hnsw ON fixture USING hnsw (embedding vector_l2_ops)")
            conn.execute("CREATE INDEX fixture_ivfflat ON fixture USING ivfflat (embedding vector_cosine_ops) WITH (lists=10)")
            before_version = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
            if before_version != ("0.6.2" if legacy else VECTOR):
                raise ValueError("Unexpected initial vector extension version")
        before = fixture_fingerprint()
        report["stages"].append({"name": "original_fixture", "extension": before_version, **before})
        stop()
        start(prefix)
        with connection("agent_memory") as conn:
            conn.execute("ALTER EXTENSION vector UPDATE TO '0.8.6'")
            assert conn.execute("SHOW server_version").fetchone()[0] == POSTGRES
            assert conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == VECTOR
            assert conn.execute("SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector").fetchone()[0] == 27 ** 0.5
            document = '<memory xmlns="urn:membrain"><entry id="7">记忆 &amp; mémoire</entry></memory>'
            assert conn.execute("SELECT xpath('/m:memory/m:entry/text()', %s::xml, ARRAY[ARRAY['m','urn:membrain']])::text[]",
                                (document,)).fetchone()[0] == ["记忆 &amp; mémoire"]
            assert conn.execute("SELECT id, content FROM XMLTABLE(XMLNAMESPACES('urn:membrain' AS m), '/m:memory/m:entry' PASSING (%s::xml) COLUMNS id integer PATH '@id', content text PATH '.')",
                                (document,)).fetchall() == [(7, "记忆 & mémoire")]
            try:
                conn.execute("SELECT XMLPARSE(DOCUMENT '<memory>')")
            except psycopg.errors.InvalidXmlDocument:
                pass
            else:
                raise ValueError("Malformed XML was accepted")
            report["xml_queries"] = {"unicode": True, "namespaces": True, "xmltable": True,
                                     "malformed_rejected": True}
            plans = {}
            report["vector_query_plans"] = plans
            for operator in ("<->", "<#>", "<=>"):
                query = sql.SQL("SELECT id FROM fixture ORDER BY embedding {} '[9.123,2.456,3.789]'::vector LIMIT 10").format(sql.SQL(operator))
                conn.execute("SET enable_indexscan=off")
                exact = conn.execute(query).fetchall()
                conn.execute("SET enable_indexscan=on")
                conn.execute("SET enable_seqscan=off")
                conn.execute("SET hnsw.ef_search=1000")
                conn.execute("SET ivfflat.probes=10")
                assert conn.execute(query).fetchall() == exact
                plan = conn.execute(sql.SQL("EXPLAIN (FORMAT JSON) ") + query).fetchone()[0]
                plans[operator] = plan
                expected_index = {"<->": "fixture_hnsw", "<=>": "fixture_ivfflat"}.get(operator)
                if expected_index:
                    assert expected_index in json.dumps(plan)
                conn.execute("RESET enable_seqscan")
            conn.execute("INSERT INTO fixture VALUES (1001, '{\"new\":true}', '[9,2,3]')")
            conn.execute("DELETE FROM fixture WHERE id=1001")
            conn.execute("VACUUM (ANALYZE) fixture")
            conn.execute("REINDEX TABLE fixture")
            assert not conn.execute("SELECT indexrelid FROM pg_index WHERE NOT indisvalid OR NOT indisready").fetchall()
        assert fixture_fingerprint() == before
        report["stages"].append({"name": "engine_and_vector_upgraded", "extension": VECTOR, **before})
        script = (prefix / "share/fix-CVE-2024-4317.sql").read_text(encoding="utf-8")
        repaired = []
        with connection() as control:
            databases = control.execute("SELECT datname, datallowconn FROM pg_database ORDER BY 1").fetchall()
            for database, allowed in databases:
                if not allowed:
                    control.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(sql.Identifier(database)))
                try:
                    with connection(database) as target:
                        target.execute(script, prepare=False)
                        target.execute(script, prepare=False)
                        views = target.execute("SELECT pg_get_viewdef(c.oid) LIKE '%%pg_has_role(c.relowner, ''USAGE''%%' FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='pg_catalog' AND c.relname IN ('pg_stats_ext','pg_stats_ext_exprs')").fetchall()
                        assert len(views) == 2 and all(row[0] for row in views)
                    repaired.append(database)
                finally:
                    if not allowed:
                        control.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(sql.Identifier(database)))
            assert databases == control.execute("SELECT datname, datallowconn FROM pg_database ORDER BY 1").fetchall()
        report["catalog_repair_databases"] = repaired
        report["catalog_script_sha256"] = hashlib.sha256(script.encode()).hexdigest()
        dump = work / "fixture.dump"
        command(prefix, "pg_dump", "--host=127.0.0.1", f"--port={port}", "--username=postgres",
                "--format=custom", "--file", dump, "agent_memory")
        with connection() as conn:
            conn.execute("CREATE DATABASE restored")
        command(prefix, "pg_restore", "--host=127.0.0.1", f"--port={port}", "--username=postgres",
                "--dbname=restored", "--exit-on-error", dump)
        with connection("restored") as conn:
            rows = conn.execute("SELECT id, payload::text, embedding::text FROM fixture ORDER BY id").fetchall()
            assert hashlib.sha256(json.dumps(rows).encode()).hexdigest() == before["sha256"]
            assert conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0] == VECTOR
        stop()
        openssl = tool(prefix, "openssl")
        if not openssl.is_file():
            openssl = shutil.which("openssl")
        if not openssl:
            raise ValueError("OpenSSL is required for the encrypted connection check")
        request_config = work / "certificate.cnf"
        request_config.write_text("[req]\ndistinguished_name=dn\n[dn]\n", encoding="utf-8")
        subprocess.run([str(openssl), "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-keyout", str(data / "server.key"), "-out", str(data / "server.crt"),
                        "-subj", "/CN=localhost", "-config", str(request_config)], env=environment,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True, timeout=90)
        (data / "server.key").chmod(0o600)
        with (data / "postgresql.conf").open("a", encoding="utf-8") as stream:
            stream.write("\nssl=on\nssl_cert_file='server.crt'\nssl_key_file='server.key'\n")
        start(prefix)
        with connection("agent_memory", sslmode="require") as conn:
            encrypted = conn.execute("SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone()
            assert encrypted and encrypted[0]
            report["encrypted_connection"] = {"ssl": encrypted[0], "version": encrypted[1], "cipher": encrypted[2]}
        assert fixture_fingerprint() == before
        report.update(completed=True, restart_preserves_rows=True, backup_restore_preserves_rows=True,
                      runtime_dependency_changed=False, qualifications_are_not_release_acceptance=True)
    finally:
        password_file.unlink(missing_ok=True)
        status = subprocess.run([str(tool(current, "pg_ctl")), "status", "-D", str(data)], env=environment,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if status.returncode == 0:
            stop()
        report["port_closed"] = is_closed(port)
        (work / "qualification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        shutil.copyfile(work / "qualification.json", artifacts / "qualification.json")
    assert report["completed"] and report["port_closed"]
    print(json.dumps({"completed": True, "legacy_upgrade": legacy, "fixture_rows": before["rows"],
                      "port_closed": True, "catalog_repair_databases": repaired}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--work-directory", type=Path, required=True)
    parser.add_argument("--legacy-upgrade", action="store_true")
    args = parser.parse_args()
    check(args.artifacts.resolve(), args.work_directory.resolve(), legacy=args.legacy_upgrade)


if __name__ == "__main__":
    main()
