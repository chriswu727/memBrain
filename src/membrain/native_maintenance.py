"""Resumable pre-readiness PostgreSQL catalog and vector maintenance."""
from __future__ import annotations

import hashlib
import math
import re
import socket
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg import sql

from . import embedded_database, native_bundle, native_snapshot
from .deletion_registry import RegistryError
from .local_profile import LocalProfileBusy, profile_lock
from .recovery_profile import read_document, write_document

CATALOG_SCRIPT_SHA256 = "2a4edf00e85f28ac5cd8867477d572a5e7f609f416da18a00e18442a15baf83d"
TARGET_SERVER = 160015
_LOCK = (0x6D656D62, 0x63617431)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
_MESSAGES = {
    "active": "Stop the local API before native maintenance. Existing service and data were preserved.",
    "busy": "Another native maintenance operation is active. Retry after it finishes; existing data was preserved.",
    "binding": "The native maintenance identity, backup or database inventory does not match. API readiness is blocked; existing data and recovery files were preserved.",
    "journal": "The private native maintenance journal could not be read or persisted. API readiness is blocked; existing data and recovery files were preserved.",
    "backup": "The native maintenance backup failed verification. API readiness is blocked; existing data and recovery files were preserved.",
    "unsupported": "Native maintenance requires the pinned PostgreSQL/vector versions and supported local databases. API readiness is blocked; existing data was preserved.",
    "failed": "Native catalog or vector maintenance did not finish. API readiness is blocked; retry with the same verified engine, journal and backup.",
}


class NativeMaintenanceError(RuntimeError):
    def __init__(self, reason):
        self.code = "native_maintenance_" + reason
        super().__init__(_MESSAGES[reason])


def _session(connection):
    connection.execute("SET search_path=pg_catalog")
    connection.execute("SET default_transaction_read_only=off")
    connection.execute("SET statement_timeout='10min'")
    connection.execute("SET lock_timeout='10s'")


def _identity(connection, profile, layout):
    row = connection.execute(
        "SELECT current_setting('server_version_num')::integer,system_identifier::text,"
        "current_setting('data_directory'),current_setting('is_superuser'),"
        "host(inet_server_addr()),inet_server_port(),pg_is_in_recovery(),current_user "
        "FROM pg_control_system()").fetchone()
    if row is None or row[0] != TARGET_SERVER:
        raise NativeMaintenanceError("unsupported")
    if (not isinstance(row[1], str) or not row[1].isdecimal() or not 0 < int(row[1]) < 2**64
            or Path(row[2]).resolve() != layout.data.resolve() or row[3] != "on"
            or row[4] != "127.0.0.1" or row[5] != profile.database_port or row[6] or row[7] != "postgres"):
        raise NativeMaintenanceError("binding")
    return row[1]


def _inventory(connection):
    rows = connection.execute("SELECT oid,datname,datallowconn,datconnlimit FROM pg_database ORDER BY oid").fetchall()
    return {row[0]: {"oid": row[0], "name": row[1], "allow_connections": row[2],
                     "connection_limit": row[3]} for row in rows}


def _save(path, journal):
    try:
        write_document(path, journal)
    except (OSError, ValueError, RegistryError):
        raise NativeMaintenanceError("journal") from None


def _load(path):
    try:
        return read_document(path)
    except (OSError, ValueError, RegistryError):
        raise NativeMaintenanceError("journal") from None


def _validate(journal, profile, layout, operation_id, commitment, identity):
    fields = {"version", "operation_id", "installation_id", "system_identifier", "data_directory",
              "snapshot_receipt_sha256", "target_server", "target_vector", "state", "databases"}
    if (not isinstance(journal, dict) or set(journal) != fields or type(journal["version"]) is not int
            or journal["version"] != 1 or journal["operation_id"] != operation_id
            or journal["installation_id"] != profile.installation_id
            or journal["system_identifier"] != identity
            or journal["data_directory"] != str(layout.data.resolve())
            or journal["snapshot_receipt_sha256"] != commitment
            or type(journal["target_server"]) is not int or journal["target_server"] != TARGET_SERVER
            or journal["target_vector"] != native_bundle.VECTOR
            or journal["state"] not in ("running", "complete")
            or not isinstance(journal["databases"], list) or not 1 <= len(journal["databases"]) <= 256):
        raise NativeMaintenanceError("binding")
    seen = set()
    for row in journal["databases"]:
        if (not isinstance(row, dict) or set(row) != {"oid", "name", "allow_connections", "connection_limit",
                                                    "inspected", "vector_before", "catalog_hashes", "reindexed", "complete"}
                or type(row["oid"]) is not int or not 0 < row["oid"] < 2**32 or row["oid"] in seen
                or not isinstance(row["name"], str) or not row["name"] or "\0" in row["name"]
                or len(row["name"].encode("utf-8")) > 63
                or type(row["connection_limit"]) is not int or not -1 <= row["connection_limit"] < 2**31
                or any(type(row[field]) is not bool for field in ("allow_connections", "inspected", "reindexed", "complete"))
                or row["vector_before"] is not None and (
                    not isinstance(row["vector_before"], str) or not _VERSION.fullmatch(row["vector_before"]))):
            raise NativeMaintenanceError("journal")
        seen.add(row["oid"])
        hashes = row["catalog_hashes"]
        if hashes is not None and (not isinstance(hashes, dict) or set(hashes) != {"pg_stats_ext", "pg_stats_ext_exprs"}
                                   or any(not isinstance(value, str) or not _SHA.fullmatch(value) for value in hashes.values())):
            raise NativeMaintenanceError("journal")
        if ((not row["inspected"] and (row["vector_before"] is not None or hashes is not None))
                or row["reindexed"] and hashes is None
                or row["complete"] and not row["reindexed"]):
            raise NativeMaintenanceError("journal")
    if journal["state"] == "complete" and not all(row["complete"] for row in journal["databases"]):
        raise NativeMaintenanceError("journal")


def _set_controls(connection, row, allowed, limit):
    connection.execute(sql.SQL("ALTER DATABASE {} WITH ALLOW_CONNECTIONS {} CONNECTION LIMIT {}").format(
        sql.Identifier(row["name"]), sql.Literal(allowed), sql.Literal(limit)))


def _restore_controls(connection, rows):
    current = _inventory(connection)
    failed = False
    for row in rows:
        value = current.get(row["oid"])
        if value is None or value["name"] != row["name"]:
            failed = True
            continue
        original = (row["allow_connections"], row["connection_limit"])
        observed = (value["allow_connections"], value["connection_limit"])
        if observed == original:
            continue
        if row["allow_connections"] or observed != (True, 0):
            failed = True
            continue
        try:
            _set_controls(connection, row, *original)
        except psycopg.Error:
            failed = True
    if failed:
        raise NativeMaintenanceError("binding")


def _same_inventory(connection, rows):
    current = _inventory(connection)
    expected = {row["oid"]: {field: row[field] for field in (
        "oid", "name", "allow_connections", "connection_limit")} for row in rows}
    if current != expected:
        raise NativeMaintenanceError("binding")


def _catalog_hashes(connection):
    rows = connection.execute(
        "SELECT c.relname,pg_get_viewdef(c.oid),c.reloptions,c.relowner=r.oid "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_roles r ON r.rolname=current_user WHERE n.nspname='pg_catalog' "
        "AND c.relname IN ('pg_stats_ext','pg_stats_ext_exprs') ORDER BY c.relname").fetchall()
    if len(rows) != 2 or any(not row[3] or "security_barrier=true" not in (row[2] or [])
                             or "pg_has_role(c.relowner, 'USAGE'::text)" not in row[1]
                             or "row_security_active(c.oid)" not in row[1] for row in rows):
        raise NativeMaintenanceError("failed")
    return {row[0]: hashlib.sha256(row[1].encode()).hexdigest() for row in rows}


def _vector(connection):
    row = connection.execute("SELECT e.extversion,n.nspname FROM pg_extension e "
                             "JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'").fetchone()
    if row is not None and (not _VERSION.fullmatch(row[0]) or tuple(map(int, row[0].split(".")))
                            > tuple(map(int, native_bundle.VECTOR.split(".")))):
        raise NativeMaintenanceError("unsupported")
    return row


def _verify_database(connection, row):
    if _catalog_hashes(connection) != row["catalog_hashes"]:
        raise NativeMaintenanceError("failed")
    vector = _vector(connection)
    if row["vector_before"] is not None and vector is None:
        raise NativeMaintenanceError("binding")
    if vector is not None:
        if vector[0] != native_bundle.VECTOR:
            raise NativeMaintenanceError("failed")
        schema = sql.Identifier(vector[1])
        distance = connection.execute(sql.SQL(
            "SELECT '[1,2,3]'::{}.vector OPERATOR({}.<->) '[4,5,6]'::{}.vector"
        ).format(schema, schema, schema)).fetchone()[0]
        if not math.isclose(distance, math.sqrt(27), rel_tol=1e-6):
            raise NativeMaintenanceError("failed")
    if connection.execute("SELECT 1 FROM pg_index WHERE NOT indisvalid OR NOT indisready LIMIT 1").fetchone():
        raise NativeMaintenanceError("failed")


def _database(profile, layout, control, journal, row, path, script):
    try:
        if not row["allow_connections"]:
            # The superuser can connect at limit zero, while an interrupted opening stays closed to ordinary roles.
            _set_controls(control, row, True, 0)
        with embedded_database._admin_connection(profile, row["name"]) as connection:
            _session(connection)
            if (_identity(connection, profile, layout) != journal["system_identifier"]
                    or connection.execute("SELECT oid FROM pg_database WHERE datname=current_database()").fetchone()[0] != row["oid"]):
                raise NativeMaintenanceError("binding")
            vector = _vector(connection)
            if (row["inspected"] and row["vector_before"] is None and vector is not None
                    and journal["state"] != "complete"):
                raise NativeMaintenanceError("binding")
            if not row["inspected"]:
                row.update(inspected=True, vector_before=vector[0] if vector else None)
                _save(path, journal)
            if (row["vector_before"] is not None and (vector is None or vector[0] not in (
                    row["vector_before"], native_bundle.VECTOR))):
                raise NativeMaintenanceError("binding")
            if row["catalog_hashes"] is None:
                with connection.transaction():
                    connection.execute(script, prepare=False)
                    hashes = _catalog_hashes(connection)
                    if vector is not None and vector[0] != native_bundle.VECTOR:
                        connection.execute(sql.SQL("ALTER EXTENSION vector UPDATE TO {}").format(
                            sql.Literal(native_bundle.VECTOR)))
                row["catalog_hashes"] = hashes
                _save(path, journal)
            if not row["reindexed"]:
                connection.execute(sql.SQL("REINDEX DATABASE {}").format(sql.Identifier(row["name"])))
                row["reindexed"] = True
                _save(path, journal)
            _verify_database(connection, row)
            row["complete"] = True
            _save(path, journal)
    finally:
        _restore_controls(control, [row])


def _run(profile, layout, snapshot_directory, commitment, operation_id):
    if (not isinstance(operation_id, str) or str(UUID(operation_id)) != operation_id
            or not isinstance(commitment, str) or not _SHA.fullmatch(commitment)):
        raise NativeMaintenanceError("binding")
    script_bytes = (layout.binaries.parent / "share/fix-CVE-2024-4317.sql").read_bytes()
    if hashlib.sha256(script_bytes).hexdigest() != CATALOG_SCRIPT_SHA256:
        raise NativeMaintenanceError("unsupported")
    script = script_bytes.decode("utf-8")
    with profile_lock(layout.data.parent / ".native-maintenance", timeout=120) as directory:
        with socket.socket() as stream:
            stream.settimeout(.2)
            if stream.connect_ex(("127.0.0.1", profile.api_port)) == 0:
                raise NativeMaintenanceError("active")
        path = directory / "catalog.json"
        with embedded_database._admin_connection(profile, "postgres") as control:
            _session(control)
            if not control.execute("SELECT pg_try_advisory_lock(%s,%s)", _LOCK).fetchone()[0]:
                raise NativeMaintenanceError("busy")
            identity = _identity(control, profile, layout)
            journal = _load(path)
            if journal is not None:
                _validate(journal, profile, layout, operation_id, commitment, identity)
                _restore_controls(control, journal["databases"])
                _same_inventory(control, journal["databases"])
            try:
                snapshot = native_snapshot.verify(snapshot_directory, commitment)
            except native_snapshot.NativeSnapshotError:
                raise NativeMaintenanceError("backup") from None
            if snapshot["control"]["system_identifier"] != identity:
                raise NativeMaintenanceError("binding")
            if journal is None:
                inventory = _inventory(control)
                if not 1 <= len(inventory) <= 256 or any(row["connection_limit"] < -1 for row in inventory.values()):
                    raise NativeMaintenanceError("unsupported")
                rows = [{**row, "inspected": False, "vector_before": None, "catalog_hashes": None,
                         "reindexed": False, "complete": False} for row in inventory.values()]
                journal = {"version": 1, "operation_id": operation_id, "installation_id": profile.installation_id,
                           "system_identifier": identity, "data_directory": str(layout.data.resolve()),
                           "snapshot_receipt_sha256": commitment, "target_server": TARGET_SERVER,
                           "target_vector": native_bundle.VECTOR, "state": "running", "databases": rows}
                _validate(journal, profile, layout, operation_id, commitment, identity)
                _save(path, journal)
            for row in journal["databases"]:
                _database(profile, layout, control, journal, row, path, script)
            _same_inventory(control, journal["databases"])
            journal["state"] = "complete"
            _save(path, journal)
            return {"state": "complete", "database_count": len(journal["databases"]),
                    "system_identifier": identity, "snapshot_receipt_sha256": commitment}


def maintain(profile, layout, snapshot_directory: Path, commitment: str, operation_id: str):
    try:
        return _run(profile, layout, snapshot_directory, commitment, operation_id)
    except NativeMaintenanceError:
        raise
    except LocalProfileBusy:
        raise NativeMaintenanceError("busy") from None
    except (RegistryError, ValueError, TypeError, KeyError, OSError, psycopg.Error):
        raise NativeMaintenanceError("failed") from None
