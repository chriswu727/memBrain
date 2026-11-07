import json

from psycopg.types.json import Jsonb

from .helpers import digest

MAX_RESPONSES = 128
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_AGE_SECONDS = 24 * 60 * 60
MAINTENANCE_BATCH = 256


def _lock(conn, params, *, wait):
    function = "pg_advisory_xact_lock" if wait else "pg_try_advisory_xact_lock"
    return conn.execute(f"SELECT {function}(hashtextextended(%s,0)) AS acquired",
                        (digest(["read-response-cache", *params]),)).fetchone()["acquired"]


def load(conn, params, action, key):
    row = conn.execute(
        "SELECT response FROM memory_read_cache WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND action=%s AND key=%s AND created_at>clock_timestamp()-(%s * interval '1 second')",
        (*params, action, key, MAX_AGE_SECONDS),
    ).fetchone()
    return row["response"] if row else None


def _prune(conn, params):
    rows = conn.execute(
        "SELECT action,key,response_bytes,created_at<=clock_timestamp()-(%s * interval '1 second') AS expired "
        "FROM memory_read_cache WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "ORDER BY created_at DESC,action,key", (MAX_AGE_SECONDS, *params),
    ).fetchall()
    count, size, removed = 0, 0, []
    for row in rows:
        if row["expired"] or count >= MAX_RESPONSES or size + row["response_bytes"] > MAX_RESPONSE_BYTES:
            removed.append((row["action"], row["key"]))
        else:
            count += 1
            size += row["response_bytes"]
    if removed:
        conn.execute(
            "DELETE FROM memory_read_cache WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND (action,key) IN (SELECT * FROM unnest(%s::text[],%s::text[]))",
            (*params, [action for action, _ in removed], [key for _, key in removed]),
        )
    return len(removed)


def store(conn, params, action, key, response):
    _lock(conn, params, wait=True)
    encoded = json.dumps(response)
    size = len(encoded.encode("utf-8"))
    if size <= MAX_RESPONSE_BYTES:
        conn.execute(
            "INSERT INTO memory_read_cache(tenant_id,owner_id,brain_id,action,key,response,response_bytes) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (*params, action, key, Jsonb(response), size),
        )
    _prune(conn, params)


def maintain(conn, params):
    if not _lock(conn, params, wait=False):
        return
    _prune(conn, params)
    state = conn.execute(
        "SELECT * FROM memory_cache_maintenance WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s", params,
    ).fetchone()
    if state is None:
        state = conn.execute(
            "INSERT INTO memory_cache_maintenance(tenant_id,owner_id,brain_id) VALUES(%s,%s,%s) RETURNING *",
            params,
        ).fetchone()
    if state["requests_complete"] and state["traces_complete"]:
        return
    if not state["requests_complete"]:
        rows = conn.execute(
            "SELECT action,key FROM memory_requests WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND action IN ('recall','inspect') AND (action,key)>(%s,%s) ORDER BY action,key LIMIT %s",
            (*params, state["request_action"], state["request_key"], MAINTENANCE_BATCH),
        ).fetchall()
        if rows:
            conn.execute(
                "UPDATE memory_requests SET response=NULL WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                "AND response IS NOT NULL AND (action,key) IN (SELECT * FROM unnest(%s::text[],%s::text[]))",
                (*params, [row["action"] for row in rows], [row["key"] for row in rows]),
            )
            state.update(request_action=rows[-1]["action"], request_key=rows[-1]["key"])
        state["requests_complete"] = len(rows) < MAINTENANCE_BATCH
    if not state["traces_complete"]:
        rows = conn.execute(
            "SELECT id,document->>'kind' AS kind FROM memory_traces "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id>%s ORDER BY id LIMIT %s",
            (*params, state["trace_id"], MAINTENANCE_BATCH),
        ).fetchall()
        if rows:
            conn.execute(
                "DELETE FROM memory_traces WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                "AND id=ANY(%s::text[]) AND document->>'kind'='candidate_hit'",
                (*params, [row["id"] for row in rows if row["kind"] == "candidate_hit"]),
            )
            state["trace_id"] = rows[-1]["id"]
        state["traces_complete"] = len(rows) < MAINTENANCE_BATCH
    conn.execute(
        "UPDATE memory_cache_maintenance SET request_action=%s,request_key=%s,trace_id=%s,"
        "requests_complete=%s,traces_complete=%s WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s",
        (state["request_action"], state["request_key"], state["trace_id"],
         state["requests_complete"], state["traces_complete"], *params),
    )
