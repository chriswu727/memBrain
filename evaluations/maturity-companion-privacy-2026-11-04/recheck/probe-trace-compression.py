import json
import socket
import time
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from membrain import embedded_database
from membrain.local_profile import load_profile

root = Path(__file__).parent
profile = load_profile(root / "perf-privacy-installation")
assert json.loads((root / "failed-profile-archive.json").read_text())["regular_files_verified"]
report = {"purpose": "lossless trace row compression space/CPU probe on session-local temporary tables; not R5 or production write timing", "model_calls": 0, "completed": False, "arms": [], "limitations": "Temporary tables omit WAL and production indexes; sample/cache/order effects remain. No production table/configuration or retention setting is changed."}
started = False
try:
    embedded_database.start(profile)
    started = True
    with psycopg.connect(profile.migration_database_url, row_factory=dict_row) as conn:
        conn.execute("SET LOCAL statement_timeout='30s'")
        conn.execute("SET LOCAL lock_timeout='500ms'")
        before = conn.execute("SELECT count(*) AS n FROM memory_traces").fetchone()["n"]
        conn.execute("CREATE TEMP TABLE membrain_trace_sample AS SELECT * FROM memory_traces ORDER BY id LIMIT 5000")
        sample = conn.execute("SELECT count(*) AS n FROM pg_temp.membrain_trace_sample").fetchone()["n"]
        assert sample == 5000
        for index, target in enumerate((2040, 1024, 1024, 2040)):
            name = f"membrain_trace_probe_{index}"
            conn.execute(f"CREATE TEMP TABLE {name} (LIKE memory_traces INCLUDING DEFAULTS INCLUDING STORAGE)")
            conn.execute(f"ALTER TABLE pg_temp.{name} SET (toast_tuple_target={target})")
            began = time.perf_counter_ns()
            conn.execute(f"INSERT INTO pg_temp.{name} SELECT * FROM pg_temp.membrain_trace_sample")
            elapsed = (time.perf_counter_ns()-began)/1e6
            different = conn.execute(f"SELECT count(*) AS n FROM ((SELECT * FROM pg_temp.{name} EXCEPT ALL SELECT * FROM pg_temp.membrain_trace_sample) UNION ALL (SELECT * FROM pg_temp.membrain_trace_sample EXCEPT ALL SELECT * FROM pg_temp.{name})) differences").fetchone()["n"]
            assert different == 0
            sizes = conn.execute(f"SELECT count(*) AS n,avg(pg_column_size(document)) AS average_document_bytes,sum(pg_column_size(document)) AS document_bytes FROM pg_temp.{name}").fetchone()
            relation = conn.execute("SELECT pg_total_relation_size(%s) AS bytes", ("pg_temp."+name,)).fetchone()["bytes"]
            methods = conn.execute(f"SELECT pg_column_compression(document) AS method,count(*) AS n FROM pg_temp.{name} GROUP BY 1").fetchall()
            report["arms"].append({"index": index, "toast_tuple_target": target, "insert_wall_ms": elapsed, "all_columns_identical": True, "differences": different, "relation_bytes": relation, "sizes": sizes, "compression_methods": methods})
        assert conn.execute("SELECT count(*) AS n FROM memory_traces").fetchone()["n"] == before
        report.update(completed=True, sample_rows=sample, base_rows_before=before, base_rows_after=before, base_configuration_unchanged=True)
        conn.rollback()
finally:
    if started:
        embedded_database.stop(profile)
    closed = []
    for port in (profile.api_port,profile.database_port):
        with socket.socket() as connection:
            connection.settimeout(.2)
            closed.append(connection.connect_ex(("127.0.0.1",port)) != 0)
    report["ports_closed"] = all(closed)
    (root / "trace-compression-probe.json").write_text(json.dumps(report,default=str,indent=2)+"\n")
assert report["completed"] and report["ports_closed"]
print(json.dumps(report,default=str))
