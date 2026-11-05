"""Durable pre-admission native engine transitions and guarded recovery promotion."""
from __future__ import annotations

import ctypes
import errno
import functools
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import psycopg

from . import (
    embedded_database,
    native_bundle,
    native_engine_store,
    native_maintenance,
    native_snapshot,
)
from .deletion_registry import DeletionRegistry, RegistryError
from .local_profile import LocalProfileBusy, LocalProfileError, _directory, _private, profile_lock
from .recovery_profile import (
    check_start_allowed,
    load_binding,
    read_document,
    sync_directory,
    write_document,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_VERSIONS = (160002, 160015)
_PHASES = {"observed", "backing_up", "backed_up", "maintaining", "restarting", "prepared",
           "bootstrapping", "admitted", "restoring", "parking", "promoting", "promoted", "rolled_back"}
_RECOVERY = {"restoring", "parking", "promoting", "promoted", "rolled_back"}
_MESSAGES = {
    "active": "Stop the local API and worker before upgrading the database. Existing service and data were preserved.",
    "busy": "Another local lifecycle or recovery operation is active. Retry after it finishes; existing data was preserved.",
    "binding": "The native upgrade identity or private journal does not match this installation. Readiness is blocked; existing data and recovery files were preserved.",
    "authority": "The recovery binding or deletion registry changed or could not be verified. Automatic rollback is blocked; existing data and recovery files were preserved.",
    "target": "The pinned target engine failed verification. Existing engines, data and recovery files were preserved.",
    "source": "A new transition requires a verified preserved original engine and its owned running database. Existing data was preserved.",
    "conflict": "A native recovery path or maintenance journal conflicts with this operation. Existing paths were not overwritten.",
    "backup": "The original native snapshot could not be verified. Readiness is blocked; existing data and recovery files were preserved.",
    "admitted": "This transition has admitted application traffic. Automatic rollback is forbidden; continue on the target engine.",
    "rolled_back": "The original engine and snapshot were restored. Start an explicit new transition before admitting application traffic.",
    "application": "Application initialization or recovery reconciliation did not finish. Readiness remains blocked; retry on the target engine.",
    "failed": "The native transition did not finish. Retry to read its durable state; existing engines, data and recovery files were preserved.",
}


class NativeTransitionError(RuntimeError):
    def __init__(self, reason):
        self.code = "native_transition_" + reason
        super().__init__(_MESSAGES[reason])


def _guard(function):
    @functools.wraps(function)
    def wrapped(self, *args, **kwargs):
        if not self.valid:
            raise NativeTransitionError("failed")
        if _open_port(self.profile.api_port):
            raise NativeTransitionError("active")
        try:
            return function(self, *args, **kwargs)
        except NativeTransitionError:
            raise
        except (OSError, ValueError, TypeError, KeyError, RegistryError, LocalProfileError,
                psycopg.Error, subprocess.SubprocessError, native_engine_store.NativeEngineStoreError,
                native_snapshot.NativeSnapshotError, native_maintenance.NativeMaintenanceError):
            raise NativeTransitionError("failed") from None
    return wrapped


def _move_absent(source, destination):
    if os.name == "nt":
        os.rename(source, destination)
    else:
        library = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            move = library.renamex_np
            move.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            arguments = (os.fsencode(source), os.fsencode(destination), 4)
        elif sys.platform.startswith("linux") and hasattr(library, "renameat2"):
            move = library.renameat2
            move.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            arguments = (-100, os.fsencode(source), -100, os.fsencode(destination), 1)
        else:
            raise OSError(errno.ENOTSUP, "Atomic exclusive rename is unavailable")
        move.restype = ctypes.c_int
        if move(*arguments):
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
    sync_directory(destination.parent)


def _open_port(port):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(("127.0.0.1", port)) == 0


def _identity(profile, layout, versions, identifier=None):
    with embedded_database._admin_connection(profile, "postgres") as connection:
        connection.execute("SET search_path=pg_catalog")
        connection.execute("SET statement_timeout='10s'")
        row = connection.execute(
            "SELECT current_setting('server_version_num')::integer,system_identifier::text,"
            "current_setting('data_directory'),current_setting('is_superuser'),"
            "host(inet_server_addr()),inet_server_port(),pg_is_in_recovery(),current_user "
            "FROM pg_control_system()").fetchone()
        if (row is None or row[0] not in versions or not isinstance(row[1], str)
                or not row[1].isdecimal() or not 0 < int(row[1]) < 2**64
                or identifier is not None and row[1] != identifier
                or Path(row[2]).resolve() != layout.data.resolve() or row[3] != "on"
                or row[4] != "127.0.0.1" or row[5] != profile.database_port or row[6] or row[7] != "postgres"):
            raise NativeTransitionError("binding")
        return row[0], row[1]


def _target(layout):
    try:
        index = json.loads((native_bundle.RESOURCES / "index.json").read_text())
        entry = index["platforms"][native_bundle.platform_key()]
        records = native_bundle._manifest(entry)
        if not native_bundle._validate_tree(layout.binaries.parent, records):
            raise NativeTransitionError("target")
        return entry["manifest_sha256"]
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, native_bundle.NativeBundleError):
        raise NativeTransitionError("target") from None


def _inode(path):
    path = _directory(path)
    metadata = path.stat()
    if not path.is_dir():
        raise NativeTransitionError("conflict")
    return [metadata.st_dev, metadata.st_ino]


def _profile_identity(profile):
    return {"directory": str(profile.directory), "tenant_id": profile.tenant_id,
            "principal_id": profile.principal_id, "api_port": profile.api_port,
            "database_port": profile.database_port}


def _uuid(value):
    return isinstance(value, str) and str(UUID(value)) == value


def _sha(value):
    return isinstance(value, str) and _SHA.fullmatch(value)


class Transition:
    def __init__(self, profile, layout, path, stack):
        self.profile, self.layout, self.path, self.stack = profile, layout, path, stack
        self.maintenance = layout.data.parent / ".native-maintenance"
        self.journal, self.registry_locks, self.valid = None, set(), True

    def _authority(self):
        binding = load_binding(self.profile)
        if binding is None:
            default = self.profile.directory.parent / ".agent-memory-recovery" / self.profile.installation_id
            if default.exists() or default.is_symlink():
                raise NativeTransitionError("authority")
            head = None
        else:
            path = Path(binding["registry_path"])
            if path not in self.registry_locks and path.exists():
                self.stack.enter_context(profile_lock(path, timeout=120))
                self.registry_locks.add(path)
            registry = DeletionRegistry(path, binding["registry_id"])
            if not registry.path.exists() and binding["state"] == "initializing":
                head = None
            else:
                head = registry.verify()
                if head["installation_id"] != self.profile.installation_id:
                    raise NativeTransitionError("authority")
        return hashlib.sha256(json.dumps({"binding": binding, "head": head}, sort_keys=True).encode()).hexdigest()

    def _same_authority(self):
        if _open_port(self.profile.api_port):
            raise NativeTransitionError("active")
        if self._authority() != self.journal["authority"]:
            raise NativeTransitionError("authority")

    def _save(self, **changes):
        document = {**self.journal, **changes}
        self.valid = False
        write_document(self.path, document)
        self.journal, self.valid = document, True

    def _old(self):
        value = self.journal["original"]
        engine = native_engine_store.verify(Path(value["directory"]), value["commitment"])
        return replace(self.layout, binaries=engine.prefix / "bin")

    def _validate(self, document):
        fields = {"version", "operation_id", "installation_id", "profile", "data", "log", "account", "target",
                  "original", "system_identifier", "authority", "phase", "snapshot", "restore", "admitted_authority"}
        if (not isinstance(document, dict) or set(document) != fields
                or type(document["version"]) is not int or document["version"] != 1
                or not _uuid(document["operation_id"])
                or document["installation_id"] != self.profile.installation_id
                or document["profile"] != _profile_identity(self.profile)
                or document["data"] != str(self.layout.data) or document["log"] != str(self.layout.log)
                or document["account"] != (list(self.layout.account) if self.layout.account else None)
                or document["target"] != {"prefix": str(self.layout.binaries.parent), "manifest": _target(self.layout)}
                or document["phase"] not in _PHASES or not _sha(document["authority"])
                or not isinstance(document["system_identifier"], str)
                or not document["system_identifier"].isdecimal()
                or not 0 < int(document["system_identifier"]) < 2**64):
            raise NativeTransitionError("binding")
        original = document["original"]
        if (not isinstance(original, dict) or set(original) != {"directory", "commitment", "version"}
                or not _sha(original["commitment"]) or type(original["version"]) is not int
                or original["version"] not in _SOURCE_VERSIONS
                or not isinstance(original["directory"], str)
                or str(_directory(Path(original["directory"]))) != original["directory"]):
            raise NativeTransitionError("binding")
        admitted = document["admitted_authority"]
        if (document["phase"] == "admitted" and not _sha(admitted)
                or document["phase"] != "admitted" and admitted is not None):
            raise NativeTransitionError("binding")
        snapshot = document["snapshot"]
        if snapshot is not None:
            if (not isinstance(snapshot, dict) or set(snapshot) != {"directory", "commitment"}
                    or not isinstance(snapshot["directory"], str)
                    or Path(snapshot["directory"]).parent != self._work(document)
                    or not Path(snapshot["directory"]).name.startswith("snapshot-")
                    or not _uuid(Path(snapshot["directory"]).name.removeprefix("snapshot-"))
                    or snapshot["commitment"] is not None and not _sha(snapshot["commitment"])):
                raise NativeTransitionError("binding")
        if document["phase"] not in ("observed", "backing_up") and (
                snapshot is None or not _sha(snapshot["commitment"])):
            raise NativeTransitionError("binding")
        recovery = document["restore"]
        if recovery is not None:
            if (not isinstance(recovery, dict) or set(recovery) != {"stage", "failed", "stage_inode", "failed_inode"}
                    or recovery["failed"] != str(self.layout.data.parent / (".native-failed-" + document["operation_id"]))):
                raise NativeTransitionError("binding")
            if recovery["stage"] is not None and (not isinstance(recovery["stage"], str)
                    or Path(recovery["stage"]).parent != self.layout.data.parent
                    or not Path(recovery["stage"]).name.startswith(".native-restore-" + document["operation_id"] + "-")
                    or Path(recovery["stage"]).name != ".native-restore-" + document["operation_id"] + "-" + Path(recovery["stage"]).name[-36:]
                    or not _uuid(Path(recovery["stage"]).name[-36:])):
                raise NativeTransitionError("binding")
            for field in ("stage_inode", "failed_inode"):
                value = recovery[field]
                if value is not None and (not isinstance(value, list) or len(value) != 2
                        or any(type(item) is not int or item < 0 for item in value)):
                    raise NativeTransitionError("binding")
        if (document["phase"] in _RECOVERY and recovery is None
                or document["phase"] not in _RECOVERY and recovery is not None
                or document["phase"] in {"parking", "promoting", "promoted", "rolled_back"}
                and (recovery["stage_inode"] is None or recovery["failed_inode"] is None)):
            raise NativeTransitionError("binding")

    def _work(self, document=None):
        return self.path.parent / ("transition-" + (document or self.journal)["operation_id"])

    def _create(self, original):
        if original is None or not _open_port(self.profile.database_port):
            raise NativeTransitionError("source")
        engine = native_engine_store.verify(original.directory, original.commitment)
        if self.layout.account is not None and not embedded_database._traversable(engine.prefix):
            engine = native_engine_store.preserve(engine.prefix, embedded_database.SHARED_ROOT / "upgrade-engines", shared=True)
        old = replace(self.layout, binaries=engine.prefix / "bin")
        version, identifier = _identity(self.profile, old, _SOURCE_VERSIONS)
        with embedded_database._admin_connection(self.profile, "postgres") as connection:
            if connection.execute("SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() "
                                  "AND backend_type='client backend'").fetchone()[0]:
                raise NativeTransitionError("busy")
        tool = embedded_database._run(old, "postgres", "--version", capture=True)
        expected = f" {version // 10000}.{version % 10000}"
        if tool.returncode or not tool.stdout.decode().strip().endswith(expected):
            raise NativeTransitionError("source")
        if (self.maintenance / "catalog.json").exists():
            raise NativeTransitionError("conflict")
        return {"version": 1, "operation_id": str(uuid4()), "installation_id": self.profile.installation_id,
                "profile": _profile_identity(self.profile), "data": str(self.layout.data), "log": str(self.layout.log),
                "account": list(self.layout.account) if self.layout.account else None,
                "target": {"prefix": str(self.layout.binaries.parent), "manifest": _target(self.layout)},
                "original": {"directory": str(engine.directory), "commitment": engine.commitment, "version": version},
                "system_identifier": identifier, "authority": self._authority(), "phase": "observed",
                "snapshot": None, "restore": None, "admitted_authority": None}

    def _stop(self, versions):
        if _open_port(self.profile.database_port):
            _identity(self.profile, self.layout, versions, self.journal["system_identifier"])
            result = embedded_database._run(self.layout, "pg_ctl", "stop", "-D", str(self.layout.data),
                                            "-m", "fast", "-w", "-t", "60", timeout=90)
            if result.returncode or _open_port(self.profile.database_port):
                raise NativeTransitionError("failed")
        elif embedded_database._run(self.layout, "pg_ctl", "status", "-D", str(self.layout.data), timeout=30).returncode == 0:
            raise NativeTransitionError("active")

    def _cold(self, layout, *, clean=True):
        value = native_snapshot._control(layout, clean=clean)
        if value["system_identifier"] != self.journal["system_identifier"]:
            raise NativeTransitionError("binding")
        return value

    def _start(self, layout, version):
        if not (layout.data / "PG_VERSION").is_file():
            raise NativeTransitionError("binding")
        if not _open_port(self.profile.database_port):
            self._cold(layout, clean=False)
            result = embedded_database._run(layout, "pg_ctl", "start", "-D", str(layout.data),
                                            "-l", str(layout.log), "-w", "-t", "90", timeout=120)
            if result.returncode:
                raise NativeTransitionError("failed")
        _identity(self.profile, layout, (version,), self.journal["system_identifier"])

    def _backup(self):
        value = self.journal["snapshot"]
        try:
            manifest = native_snapshot.verify(Path(value["directory"]), value["commitment"])
        except native_snapshot.NativeSnapshotError:
            raise NativeTransitionError("backup") from None
        if manifest["control"]["system_identifier"] != self.journal["system_identifier"]:
            raise NativeTransitionError("binding")
        return manifest

    def _matches(self, layout, manifest):
        return (native_snapshot._inventory(layout.data, native_snapshot.DEFAULT_MAX_BYTES)
                == (manifest["root"], manifest["entries"]) and self._cold(layout) == manifest["control"])

    def _snapshot(self):
        self._same_authority()
        self._stop((self.journal["original"]["version"],))
        old = self._old()
        self._cold(old)
        value = self.journal["snapshot"]
        if value is not None and (Path(value["directory"]) / "receipt.json").is_file():
            receipt = native_snapshot._private_digest(Path(value["directory"]) / "receipt.json")["sha256"]
            manifest = native_snapshot.verify(Path(value["directory"]), receipt)
            if not self._matches(old, manifest):
                raise NativeTransitionError("binding")
        else:
            work = self._work()
            work.mkdir(mode=0o700, exist_ok=True)
            _private(work, directory=True)
            value = {"directory": str(work / ("snapshot-" + str(uuid4()))), "commitment": None}
            self._save(phase="backing_up", snapshot=value)
            receipt = native_snapshot.create(old, Path(value["directory"]))["receipt_sha256"]
        self._same_authority()
        self._save(phase="backed_up", snapshot={**value, "commitment": receipt})

    def _maintain(self):
        snapshot = self.journal["snapshot"]
        native_maintenance.maintain(self.profile, self.layout, Path(snapshot["directory"]),
                                     snapshot["commitment"], self.journal["operation_id"])

    @_guard
    def prepare(self):
        phase = self.journal["phase"]
        if phase in _RECOVERY:
            raise NativeTransitionError("rolled_back" if phase == "rolled_back" else "conflict")
        if phase == "admitted":
            self._start(self.layout, native_maintenance.TARGET_SERVER)
            self._ready()
            return {"state": "admitted", "operation_id": self.journal["operation_id"]}
        if phase not in {"bootstrapping"}:
            self._same_authority()
        if phase in {"observed", "backing_up"}:
            self._snapshot()
        if self.journal["phase"] == "backed_up":
            self._backup()
            self._save(phase="maintaining")
        if self.journal["phase"] == "maintaining":
            if _open_port(self.profile.database_port):
                version, _ = _identity(self.profile, self.layout, _SOURCE_VERSIONS, self.journal["system_identifier"])
                if version != native_maintenance.TARGET_SERVER:
                    self._stop((self.journal["original"]["version"],))
            self._start(self.layout, native_maintenance.TARGET_SERVER)
            self._maintain()
            self._save(phase="restarting")
        if self.journal["phase"] == "restarting":
            self._stop((native_maintenance.TARGET_SERVER,))
            self._start(self.layout, native_maintenance.TARGET_SERVER)
            self._maintain()
            self._save(phase="prepared")
        else:
            self._start(self.layout, native_maintenance.TARGET_SERVER)
            self._maintain()
        return {"state": self.journal["phase"], "operation_id": self.journal["operation_id"]}

    def _ready(self):
        journal = native_maintenance._load(self.maintenance / "catalog.json")
        if journal is None or journal["state"] != "complete":
            raise NativeTransitionError("binding")
        native_maintenance._validate(journal, self.profile, self.layout, self.journal["operation_id"],
                                     self.journal["snapshot"]["commitment"], self.journal["system_identifier"])
        rows = {row["name"]: row for row in journal["databases"]}
        for database in ("postgres", "agent_memory"):
            if database not in rows:
                raise NativeTransitionError("binding")
            with embedded_database._admin_connection(self.profile, database) as connection:
                native_maintenance._session(connection)
                _identity(self.profile, self.layout, (native_maintenance.TARGET_SERVER,), self.journal["system_identifier"])
                row = {**rows[database]}
                if database == "agent_memory":
                    row["vector_before"] = native_bundle.VECTOR
                native_maintenance._verify_database(connection, row)
                if database == "postgres":
                    role = connection.execute("SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication,rolcanlogin "
                                              "FROM pg_roles WHERE rolname='memory_app'").fetchone()
                    if role != (False, False, False, False, False, True):
                        raise NativeTransitionError("application")

    def _application(self):
        from .helpers import Principal
        from .recovery_profile import authority_for
        from .storage import Database

        self._ready()
        database = Database(self.profile.database_url, self.profile.migration_database_url)
        database.check_compatibility(require_current=True)
        binding = load_binding(self.profile)
        if binding is None or binding["state"] != "active":
            raise NativeTransitionError("application")
        self._authority()
        with database.transaction(Principal(self.profile.tenant_id, self.profile.principal_id)) as connection:
            authority_for(self.profile).assert_reconciled(connection, Principal(self.profile.tenant_id, self.profile.principal_id))

    @_guard
    def admit(self, bootstrap):
        self.prepare()
        admitted = self.journal["phase"] == "admitted"
        if not admitted:
            self._save(phase="bootstrapping")
        try:
            bootstrap()
            self._application()
        except Exception:
            raise NativeTransitionError("application") from None
        if not admitted:
            self._save(phase="admitted", admitted_authority=self._authority())
        return {"state": "admitted", "operation_id": self.journal["operation_id"]}

    def _archive_catalog(self):
        path = self.maintenance / "catalog.json"
        archived = self.maintenance / ("catalog-" + self.journal["operation_id"] + ".failed.json")
        selected = path if path.exists() else archived
        if not selected.exists():
            return
        document = native_maintenance._load(selected)
        native_maintenance._validate(document, self.profile, self.layout, self.journal["operation_id"],
                                     self.journal["snapshot"]["commitment"], self.journal["system_identifier"])
        if path.exists():
            _move_absent(path, archived)

    def _restore_stage(self, manifest):
        recovery = self.journal["restore"]
        stage = Path(recovery["stage"]) if recovery["stage"] else None
        valid = False
        if stage is not None and stage.exists():
            try:
                valid = self._matches(replace(self.layout, data=stage), manifest)
            except (OSError, native_snapshot.NativeSnapshotError):
                pass
        if not valid:
            stage = self.layout.data.parent / (".native-restore-" + self.journal["operation_id"] + "-" + str(uuid4()))
            recovery = {**recovery, "stage": str(stage), "stage_inode": None}
            self._save(restore=recovery)
            snapshot = self.journal["snapshot"]
            native_snapshot.restore(Path(snapshot["directory"]), snapshot["commitment"], replace(self.layout, data=stage))
        self._cold(self.layout, clean=False)
        self._save(phase="parking", restore={**recovery, "stage_inode": _inode(stage), "failed_inode": _inode(self.layout.data)})

    def _promote(self, manifest):
        recovery = self.journal["restore"]
        data, stage, failed = self.layout.data, Path(recovery["stage"]), Path(recovery["failed"])
        if self.journal["phase"] == "parking":
            if data.exists() and not failed.exists():
                self._cold(self.layout, clean=False)
                if _inode(data) != recovery["failed_inode"]:
                    raise NativeTransitionError("conflict")
                _move_absent(data, failed)
            elif data.exists() or not failed.exists() or _inode(failed) != recovery["failed_inode"]:
                raise NativeTransitionError("conflict")
            self._save(phase="promoting")
        if self.journal["phase"] == "promoting":
            if not failed.exists() or _inode(failed) != recovery["failed_inode"]:
                raise NativeTransitionError("conflict")
            self._cold(replace(self.layout, data=failed), clean=False)
            if not data.exists() and stage.exists():
                if _inode(stage) != recovery["stage_inode"] or not self._matches(replace(self.layout, data=stage), manifest):
                    raise NativeTransitionError("conflict")
                _move_absent(stage, data)
            elif (stage.exists() or not data.exists() or _inode(data) != recovery["stage_inode"]
                  or not self._matches(self.layout, manifest)):
                raise NativeTransitionError("conflict")
            self._save(phase="promoted")

    @_guard
    def rollback(self):
        phase = self.journal["phase"]
        if phase == "admitted":
            raise NativeTransitionError("admitted")
        self._same_authority()
        if phase == "rolled_back":
            self._start(self._old(), self.journal["original"]["version"])
            return {"state": "rolled_back", "operation_id": self.journal["operation_id"]}
        if phase in {"observed", "backing_up"}:
            raise NativeTransitionError("backup")
        manifest = self._backup()
        if phase not in _RECOVERY:
            self._stop((self.journal["original"]["version"], native_maintenance.TARGET_SERVER))
            recovery = {"stage": None, "stage_inode": None, "failed_inode": None,
                        "failed": str(self.layout.data.parent / (".native-failed-" + self.journal["operation_id"]))}
            self._save(phase="restoring", restore=recovery)
        if self.journal["phase"] == "restoring":
            self._stop((self.journal["original"]["version"], native_maintenance.TARGET_SERVER))
            self._restore_stage(manifest)
        self._same_authority()
        if self.journal["phase"] in {"parking", "promoting"}:
            if _open_port(self.profile.database_port):
                raise NativeTransitionError("active")
            self._promote(manifest)
        if self.journal["phase"] == "promoted":
            self._archive_catalog()
            self._save(phase="rolled_back")
        self._start(self._old(), self.journal["original"]["version"])
        return {"state": "rolled_back", "operation_id": self.journal["operation_id"]}


def _recorded(profile, document):
    if document is None:
        return None
    account = document["account"]
    if account is not None and (not isinstance(account, list) or len(account) != 2
            or any(type(value) is not int or value < 0 for value in account)):
        raise NativeTransitionError("binding")
    layout = embedded_database._Layout(_directory(Path(document["target"]["prefix"]) / "bin"),
                                       _directory(Path(document["data"])), _directory(Path(document["log"])),
                                       tuple(account) if account else None)
    Transition(profile, layout, profile.directory / "native-transition.json", None)._validate(document)
    return layout


def recorded_layout(profile):
    try:
        return _recorded(profile, read_document(profile.directory / "native-transition.json"))
    except NativeTransitionError:
        raise
    except (OSError, ValueError, TypeError, KeyError, RegistryError, LocalProfileError):
        raise NativeTransitionError("binding") from None


@contextmanager
def session(profile, target_layout=None, *, original=None, retry_rolled_back=False):
    """Exit after admit, then launch the API while retaining the caller's lifecycle lock."""
    try:
        if profile.database_engine != "embedded":
            raise NativeTransitionError("binding")
        with ExitStack() as stack:
            stack.enter_context(profile_lock(profile.directory / "lifecycle", timeout=360))
            stack.enter_context(profile_lock(profile.directory, timeout=120))
            path = profile.directory / "native-transition.json"
            document = read_document(path)
            if target_layout is None:
                layout = _recorded(profile, document)
                if layout is None:
                    raise NativeTransitionError("source")
            else:
                layout = replace(target_layout, data=_directory(target_layout.data), log=_directory(target_layout.log),
                                 binaries=_directory(target_layout.binaries))
            handle = Transition(profile, layout, path, stack)
            if document is not None:
                handle._validate(document)
            stack.enter_context(profile_lock(layout.data.parent / ".native-maintenance", timeout=120))
            stack.enter_context(profile_lock(profile.directory / "supervisor", timeout=0))
            if _open_port(profile.api_port):
                raise NativeTransitionError("active")
            check_start_allowed(profile, allow_initializing=True, allow_native_upgrade=True)
            _target(layout)
            if document is not None:
                handle.journal = document
                if retry_rolled_back:
                    if document["phase"] != "rolled_back":
                        raise NativeTransitionError("conflict")
                    engine = native_engine_store.verify(Path(document["original"]["directory"]), document["original"]["commitment"])
                    history = profile.directory / ("transition-" + document["operation_id"] + ".json")
                    previous = read_document(history)
                    if previous is not None and previous != document:
                        raise NativeTransitionError("conflict")
                    if previous is None:
                        write_document(history, document)
                    document = handle._create(engine)
                    write_document(handle.path, document)
                    handle.journal = document
            else:
                document = handle._create(original)
                write_document(handle.path, document)
                handle.journal = document
            handle._authority()
            try:
                yield handle
            finally:
                handle.valid = False
    except NativeTransitionError:
        raise
    except LocalProfileBusy:
        raise NativeTransitionError("busy") from None
    except (OSError, ValueError, TypeError, KeyError, RegistryError, LocalProfileError,
            psycopg.Error, subprocess.SubprocessError, native_engine_store.NativeEngineStoreError):
        raise NativeTransitionError("failed") from None
