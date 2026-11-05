import hashlib
import json
import socket
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from membrain import embedded_database
from membrain.local_profile import load_profile

root = Path(__file__).parent
profile = load_profile(root / "perf-privacy-installation")
archive = json.loads((root / "failed-profile-archive.json").read_text())
assert archive["regular_files_verified"] and not archive["original_owned_database_removed"]
report = {"purpose": "read-only PostgreSQL statistics after completed failed R5; no performance acceptance", "model_calls": 0}
started = False
try:
    embedded_database.start(profile)
    started = True
    with psycopg.connect(profile.migration_database_url, autocommit=True, row_factory=dict_row) as conn:
        conn.execute("SET default_transaction_read_only=on")
        report["server"] = conn.execute("SELECT version(),clock_timestamp(),pg_postmaster_start_time(),pg_database_size(current_database()) AS database_bytes").fetchone()
        report["tables"] = conn.execute("SELECT relname,n_live_tup,n_dead_tup,n_tup_ins,n_tup_upd,n_tup_del,last_autovacuum,autovacuum_count,last_autoanalyze,autoanalyze_count FROM pg_stat_user_tables ORDER BY relname").fetchall()
        report["bgwriter"] = conn.execute("SELECT * FROM pg_stat_bgwriter").fetchall()
        report["wal"] = conn.execute("SELECT * FROM pg_stat_wal").fetchall()
        report["settings"] = conn.execute("SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','min_wal_size','max_wal_size','checkpoint_timeout','autovacuum_naptime','autovacuum_vacuum_threshold','autovacuum_vacuum_scale_factor','autovacuum_analyze_threshold','autovacuum_analyze_scale_factor','track_io_timing') ORDER BY name").fetchall()
        report["completed"] = True
finally:
    if started:
        embedded_database.stop(profile)
    closed = []
    for port in (profile.api_port,profile.database_port):
        with socket.socket() as connection:
            connection.settimeout(.2)
            closed.append(connection.connect_ex(("127.0.0.1",port)) != 0)
    report["ports_closed"] = all(closed)
    (root / "failed-pg-statistics.json").write_text(json.dumps(report,default=str,indent=2)+"\n")
assert report.get("completed") and report["ports_closed"]
print(json.dumps({"completed":True,"ports_closed":True,"tables":len(report["tables"])}))
