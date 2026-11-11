import ipaddress
import os
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from .build_identity import MIGRATIONS, SCHEMA_ID

SCRAM_ONLY = "scram-sha-256"
_REQUIRE_AUTH_LIBPQ = 160000


class DatabaseClientError(RuntimeError):
    code = "database_client_unsupported"

    def __init__(self):
        version = psycopg.pq.version()
        super().__init__(
            f"The PostgreSQL client library in use (libpq {version // 10000}.{version % 10000}) cannot require "
            "SCRAM-SHA-256 authentication, so no connection was attempted and no password was sent. "
            "Install psycopg[binary] 3.2 or later, or use libpq 16 or later.")


def _loopback(value: str) -> bool:
    for host in value.split(","):
        host = host.strip()
        if host.lower() == "localhost":
            return True
        try:
            if ipaddress.ip_address(host).is_loopback:
                return True
        except ValueError:
            continue
    return False


def connection_info(conninfo: str = "", **params) -> str:
    """Return libpq connection parameters with the authentication rule this product applies.

    Every psycopg connection the product opens goes through here. A connection to a loopback TCP address must
    authenticate with SCRAM-SHA-256 (``require_auth``), so a process holding the port cannot request the
    password in cleartext or as an MD5 digest; SCRAM proves knowledge of the password to both sides.
    The product's own profiles set ``require_auth`` explicitly. A ``require_auth`` already present in a
    configured URL is left unchanged, and other hosts and Unix sockets are not altered. libpq older than 16
    does not know the parameter; such clients fail before connecting instead of dropping the requirement.
    The embedded cluster's pg_dump and pg_restore get the same requirement via PGREQUIREAUTH.
    """
    supported = psycopg.pq.version() >= _REQUIRE_AUTH_LIBPQ
    try:
        values = conninfo_to_dict(conninfo, **params)
    except psycopg.ProgrammingError:
        if not supported and ("require_auth" in conninfo or "require_auth" in params):
            raise DatabaseClientError() from None
        raise
    if "require_auth" not in values:
        target = values.get("hostaddr") or values.get("host") or os.environ.get("PGHOSTADDR") \
            or os.environ.get("PGHOST") or ("localhost" if os.name == "nt" else "")
        if _loopback(target):
            values["require_auth"] = SCRAM_ONLY
    if "require_auth" in values and not supported:
        raise DatabaseClientError()
    return make_conninfo("", **values)


def connect(conninfo: str = "", *, row_factory=None, autocommit: bool = False, **params):
    options = {"autocommit": autocommit} | ({"row_factory": row_factory} if row_factory is not None else {})
    return psycopg.connect(connection_info(conninfo, **params), **options)


_CONNECTION_OPTIONS = frozenset({"autocommit", "prepare_threshold", "context", "row_factory", "cursor_factory"})


class _PoolConnection(psycopg.Connection):
    """Pooled connections apply ``connection_info`` when each one is opened."""

    @classmethod
    def connect(cls, conninfo: str = "", **kwargs):
        params = {name: kwargs.pop(name) for name in list(kwargs) if name not in _CONNECTION_OPTIONS}
        return super().connect(connection_info(conninfo, **params), **kwargs)


class SchemaCompatibilityError(RuntimeError):
    code = "database_schema_incompatible"

    def __init__(self):
        super().__init__("The database schema is not supported by this installation; use a compatible release.")


def schema_status(conn, *, require_current: bool = False) -> dict:
    names = tuple(name for name, _ in MIGRATIONS)
    exists = conn.execute("SELECT to_regclass('memory_migrations') AS name").fetchone()["name"]
    if exists:
        applied = tuple(row["name"] for row in conn.execute("SELECT name FROM memory_migrations ORDER BY name"))
        if applied != names[:len(applied)]:
            raise SchemaCompatibilityError()
    else:
        existing_tables = conn.execute(
            "SELECT 1 FROM pg_class WHERE relnamespace=current_schema()::regnamespace "
            "AND relname LIKE 'memory\\_%' ESCAPE '\\' AND relkind IN ('r','p') LIMIT 1"
        ).fetchone()
        if existing_tables:
            raise SchemaCompatibilityError()
        applied = ()
    pending = len(names) - len(applied)
    if require_current and pending:
        raise SchemaCompatibilityError()
    return {"state": "current" if not pending else "migration_required" if exists else "uninitialized",
            "schema_id": SCHEMA_ID, "applied_count": len(applied), "pending_count": pending}


class Database:
    def __init__(self, dsn: str, migration_dsn: str | None = None, *, pool: bool = False):
        self.dsn = dsn
        self.migration_dsn = migration_dsn or dsn
        self.pool = None
        if pool:
            from psycopg_pool import ConnectionPool

            self.pool = ConnectionPool(dsn, connection_class=_PoolConnection, min_size=0, max_size=8, timeout=5,
                                       max_waiting=32,
                                       kwargs={"row_factory": dict_row, "connect_timeout": 5}, open=True)

    def close(self):
        if self.pool is not None:
            self.pool.close()


    def check_compatibility(self, *, require_current: bool = False) -> dict:
        with connect(self.migration_dsn, row_factory=dict_row, connect_timeout=5) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '5000'")
            return schema_status(conn, require_current=require_current)

    def migrate(self):
        with connect(self.migration_dsn, row_factory=dict_row) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(770419510)")
            schema_status(conn)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory_migrations "
                "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            existing = {r["name"] for r in conn.execute("SELECT name FROM memory_migrations")}
            for name, content in MIGRATIONS:
                if name not in existing:
                    conn.execute(content.decode("utf-8"), prepare=False)
                    conn.execute("INSERT INTO memory_migrations (name) VALUES (%s)", (name,))

    @contextmanager
    def transaction(self, principal):
        connection = self.pool.connection() if self.pool is not None else connect(
            self.dsn, row_factory=dict_row, connect_timeout=5)
        with connection as conn:
            conn.execute("SELECT set_config('app.tenant_id', %s, true), set_config('app.principal_id', %s, true)",
                         (principal.tenant_id, principal.principal_id))
            yield conn
