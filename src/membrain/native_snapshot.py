"""Private offline cluster snapshots for the pre-readiness native upgrade transition."""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import zipfile
import zlib
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import embedded_database, native_bundle
from .local_profile import _directory, _open_private, _pairs, _private, profile_lock
from .recovery_profile import sync_directory, write_document

DEFAULT_MAX_BYTES = 64 * 1024**3
MAX_MANIFEST_BYTES = 64 * 1024**2
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MESSAGES = {
    "invalid": "The native database snapshot failed integrity checks. Existing database data was preserved.",
    "unsupported": "Native snapshots require PostgreSQL 16, ordinary local files and the original platform. External tablespace or WAL links are unsupported. Existing data was preserved.",
    "not_stopped": "The database must be cleanly stopped before native upgrade or recovery. Existing data was preserved.",
    "space_low": "Not enough free space for a verified native snapshot and staged recovery. Existing data was preserved.",
    "limit_exceeded": "The native snapshot exceeds its configured size limit. Increase the snapshot budget before retrying. Existing data was preserved.",
    "conflict": "The native snapshot or recovery destination already exists and was preserved.",
    "changed": "The database changed during its offline snapshot. The snapshot was not completed and existing data was preserved.",
    "io_failed": "The native snapshot could not be prepared. Check file access and available space. Existing data and partial recovery files were preserved.",
}


class NativeSnapshotError(RuntimeError):
    def __init__(self, reason):
        self.code = "native_snapshot_" + reason
        super().__init__(_MESSAGES[reason])


def _guard(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NativeSnapshotError:
            raise
        except (ValueError, KeyError, TypeError, OverflowError, RecursionError, zipfile.BadZipFile, zlib.error):
            raise NativeSnapshotError("invalid") from None
        except (OSError, subprocess.SubprocessError):
            raise NativeSnapshotError("io_failed") from None
    return wrapped


def _name(value):
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise NativeSnapshotError("invalid")
    path = PurePosixPath(value)
    if (path.is_absolute() or path.as_posix() != value or value == "." or ".." in path.parts
            or "\\" in value or ":" in value
            or any(part.endswith((" ", ".")) or PureWindowsPath(part).is_reserved() for part in path.parts)):
        raise NativeSnapshotError("invalid")
    return path


def _metadata(path):
    value = path.lstat()
    if (value.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)
            or getattr(value, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            or not (stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode))
            or stat.S_ISREG(value.st_mode) and value.st_nlink != 1):
        raise NativeSnapshotError("unsupported")
    return {"mode": stat.S_IMODE(value.st_mode), "uid": value.st_uid, "gid": value.st_gid,
            "mtime_ns": value.st_mtime_ns}


def _data_file(path):
    before = path.lstat()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        current = os.fstat(descriptor)
        if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)):
            raise NativeSnapshotError("unsupported")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _digest(stream, *, max_bytes=None):
    hashed, size = hashlib.sha256(), 0
    while chunk := stream.read(65536):
        hashed.update(chunk)
        size += len(chunk)
        if max_bytes is not None and size > max_bytes:
            raise NativeSnapshotError("invalid")
    return {"bytes": size, "sha256": hashed.hexdigest()}


def _private_digest(path):
    with os.fdopen(_open_private(path, os.O_RDONLY), "rb") as stream:
        return _digest(stream)


def _copy_member(source, target, row):
    hashed, remaining = hashlib.sha256(), row["bytes"]
    while chunk := source.read(min(65536, remaining + 1)):
        if len(chunk) > remaining:
            raise NativeSnapshotError("changed")
        target.write(chunk)
        hashed.update(chunk)
        remaining -= len(chunk)
    if remaining or hashed.hexdigest() != row["sha256"]:
        raise NativeSnapshotError("changed")


def _budget(max_bytes):
    if type(max_bytes) is not int or max_bytes <= 0:
        raise NativeSnapshotError("invalid")


def _inventory(data, max_bytes):
    root = _metadata(data)
    if not data.is_dir() or root["mode"] not in (0o700, 0o750) and os.name != "nt":
        raise NativeSnapshotError("unsupported")
    rows, total = [], 0
    for path in sorted(data.rglob("*")):
        metadata = _metadata(path)
        name = _name(path.relative_to(data).as_posix()).as_posix()
        row = {"path": name, "kind": "directory" if path.is_dir() else "file", **metadata}
        if row["kind"] == "file":
            if path.stat().st_size > max_bytes - total:
                raise NativeSnapshotError("limit_exceeded")
            with _data_file(path) as stream:
                row.update(_digest(stream, max_bytes=max_bytes - total))
            total += row["bytes"]
            if total > max_bytes:
                raise NativeSnapshotError("limit_exceeded")
        rows.append(row)
    return root, rows


def _control(layout, *, clean=True):
    if clean and (layout.data / "postmaster.pid").exists():
        raise NativeSnapshotError("not_stopped")
    if not clean and embedded_database._run(
            layout, "pg_ctl", "status", "-D", str(layout.data), timeout=30).returncode == 0:
        raise NativeSnapshotError("not_stopped")
    _metadata(layout.data / "PG_VERSION")
    with _data_file(layout.data / "PG_VERSION") as stream:
        if stream.read(32) not in (b"16\n", b"16\r\n"):
            raise NativeSnapshotError("unsupported")
    result = embedded_database._run(layout, "pg_controldata", "-D", str(layout.data),
                                    timeout=30, capture=True)
    text = result.stdout.decode("utf-8", "strict")
    if result.returncode or "pg_controldata:" in text:
        raise NativeSnapshotError("invalid")
    fields = dict(line.split(":", 1) for line in text.splitlines() if ":" in line)
    fields = {key: value.strip() for key, value in fields.items()}
    identifier = fields.get("Database system identifier", "")
    checkpoint = fields.get("Latest checkpoint location", "")
    if (fields.get("pg_control version number") != "1300"
            or fields.get("Catalog version number") != "202307071"
            or not identifier.isdecimal() or not 0 < int(identifier) < 2**64
            or re.fullmatch(r"[0-9A-F]{1,8}/[0-9A-F]{1,8}", checkpoint) is None):
        raise NativeSnapshotError("unsupported")
    if fields.get("Database cluster state") not in (
            {"shut down"} if clean else {"shut down", "in production", "in crash recovery", "starting up", "shutting down"}):
        raise NativeSnapshotError("not_stopped")
    return {"system_identifier": identifier, "checkpoint": checkpoint}


def _space(destination_parent, data_parent, data_bytes, entries):
    recovery = data_bytes + 4096 * entries + 32 * 1024**2
    backup = recovery + data_bytes // 100 + MAX_MANIFEST_BYTES
    if destination_parent.stat().st_dev == data_parent.stat().st_dev:
        if shutil.disk_usage(destination_parent).free < recovery + backup:
            raise NativeSnapshotError("space_low")
    elif (shutil.disk_usage(destination_parent).free < backup
          or shutil.disk_usage(data_parent).free < recovery):
        raise NativeSnapshotError("space_low")


def _manifest(raw, max_bytes):
    if len(raw) > MAX_MANIFEST_BYTES:
        raise NativeSnapshotError("invalid")
    value = json.loads(raw, object_pairs_hook=_pairs)
    if (not isinstance(value, dict) or set(value) != {"version", "platform", "root", "control", "entries"}
            or type(value["version"]) is not int or value["version"] != 1
            or value["platform"] != native_bundle.platform_key() or value["platform"] is None
            or not isinstance(value["entries"], list)):
        raise NativeSnapshotError("unsupported")
    root = value["root"]
    rows, total = {}, 0
    for row in [root, *value["entries"]]:
        if not isinstance(row, dict):
            raise NativeSnapshotError("invalid")
        for field in ("mode", "uid", "gid", "mtime_ns"):
            if type(row.get(field)) is not int or row[field] < 0:
                raise NativeSnapshotError("invalid")
        if row["mode"] & ~0o777 or max(row["uid"], row["gid"]) >= 2**32:
            raise NativeSnapshotError("invalid")
    if set(root) != {"mode", "uid", "gid", "mtime_ns"}:
        raise NativeSnapshotError("invalid")
    if os.name != "nt" and root["mode"] not in (0o700, 0o750):
        raise NativeSnapshotError("invalid")
    for row in value["entries"]:
        name = _name(row["path"]).as_posix()
        fields = {"path", "kind", "mode", "uid", "gid", "mtime_ns"}
        if row["kind"] == "file":
            fields |= {"bytes", "sha256"}
            if (type(row["bytes"]) is not int or row["bytes"] < 0
                    or not isinstance(row["sha256"], str) or not _SHA.fullmatch(row["sha256"])):
                raise NativeSnapshotError("invalid")
            total += row["bytes"]
        elif row["kind"] != "directory":
            raise NativeSnapshotError("invalid")
        if total > max_bytes:
            raise NativeSnapshotError("limit_exceeded")
        if set(row) != fields or name in rows or name == "postmaster.pid":
            raise NativeSnapshotError("invalid")
        rows[name] = row
    for name in rows:
        parent = PurePosixPath(name).parent.as_posix()
        if parent != "." and rows.get(parent, {}).get("kind") != "directory":
            raise NativeSnapshotError("invalid")
    if (rows.get("PG_VERSION", {}).get("kind") != "file"
            or rows.get("global/pg_control", {}).get("kind") != "file"
            or not isinstance(value["control"], dict)
            or set(value["control"]) != {"system_identifier", "checkpoint"}
            or not isinstance(value["control"]["system_identifier"], str)
            or not re.fullmatch(r"[0-9]{1,20}", value["control"]["system_identifier"])
            or not 0 < int(value["control"]["system_identifier"]) < 2**64
            or not isinstance(value["control"]["checkpoint"], str)
            or not re.fullmatch(r"[0-9A-F]{1,8}/[0-9A-F]{1,8}", value["control"]["checkpoint"])):
        raise NativeSnapshotError("invalid")
    return value, rows, total


def _archive(path, receipt, max_bytes, *, destination=None):
    with os.fdopen(_open_private(path, os.O_RDONLY), "rb") as stream:
        if (os.fstat(stream.fileno()).st_size != receipt["archive_bytes"]
                or _digest(stream, max_bytes=receipt["archive_bytes"]) != {
                    "bytes": receipt["archive_bytes"], "sha256": receipt["archive_sha256"]}):
            raise NativeSnapshotError("invalid")
        stream.seek(0)
        with zipfile.ZipFile(stream) as saved:
            infos = saved.infolist()
            if (not infos or len({info.filename for info in infos}) != len(infos)
                    or any(info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                           or stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR)
                           for info in infos)):
                raise NativeSnapshotError("invalid")
            info = saved.getinfo("manifest.json")
            if info.file_size > MAX_MANIFEST_BYTES:
                raise NativeSnapshotError("invalid")
            raw = saved.read(info)
            if hashlib.sha256(raw).hexdigest() != receipt["manifest_sha256"]:
                raise NativeSnapshotError("invalid")
            manifest, rows, total = _manifest(raw, max_bytes)
            if (total != receipt["data_bytes"] or len(rows) != receipt["entries"]
                    or manifest["control"]["system_identifier"] != receipt["system_identifier"]):
                raise NativeSnapshotError("invalid")
            expected = {"data/" + name + ("/" if row["kind"] == "directory" else ""): row
                        for name, row in rows.items()}
            if {info.filename for info in infos} != {"manifest.json", *expected}:
                raise NativeSnapshotError("invalid")
            for name, row in sorted(expected.items()):
                info = saved.getinfo(name)
                path = destination / row["path"] if destination else None
                if info.is_dir() != (row["kind"] == "directory") or info.file_size != row.get("bytes", 0):
                    raise NativeSnapshotError("invalid")
                if row["kind"] == "directory":
                    if path:
                        path.mkdir(mode=0o700)
                        _private(path, directory=True)
                    continue
                with saved.open(info) as member:
                    if path is None:
                        actual = _digest(member)
                    else:
                        hashed, size = hashlib.sha256(), 0
                        with os.fdopen(_open_private(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as output:
                            while chunk := member.read(65536):
                                output.write(chunk)
                                hashed.update(chunk)
                                size += len(chunk)
                            output.flush()
                            os.fsync(output.fileno())
                        actual = {"bytes": size, "sha256": hashed.hexdigest()}
                if actual != {"bytes": row["bytes"], "sha256": row["sha256"]}:
                    raise NativeSnapshotError("invalid")
    return manifest


def _receipt(directory, commitment):
    if not isinstance(commitment, str) or not _SHA.fullmatch(commitment):
        raise NativeSnapshotError("invalid")
    if {path.name for path in directory.iterdir()} != {"cluster.zip", "receipt.json"}:
        raise NativeSnapshotError("invalid")
    with os.fdopen(_open_private(directory / "receipt.json", os.O_RDONLY), "rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != commitment:
        raise NativeSnapshotError("invalid")
    value = json.loads(raw, object_pairs_hook=_pairs)
    if (not isinstance(value, dict) or set(value) != {"version", "archive_bytes", "archive_sha256",
                                                    "manifest_sha256", "data_bytes", "entries", "system_identifier"}
            or type(value["version"]) is not int or value["version"] != 1
            or any(type(value[field]) is not int or value[field] <= 0
                   for field in ("archive_bytes", "data_bytes", "entries"))
            or any(not isinstance(value[field], str) or not _SHA.fullmatch(value[field])
                   for field in ("archive_sha256", "manifest_sha256"))):
        raise NativeSnapshotError("invalid")
    return value


def _new_destination(directory):
    if directory.exists() or any((parent / "PG_VERSION").exists() for parent in directory.parents):
        raise NativeSnapshotError("conflict")


@_guard
def create(layout, directory: Path, *, max_bytes=DEFAULT_MAX_BYTES):
    _budget(max_bytes)
    data, directory = _directory(layout.data), _directory(directory)
    if directory.is_relative_to(data) or data.is_relative_to(directory):
        raise NativeSnapshotError("conflict")
    _new_destination(directory)
    with profile_lock(data.parent / ".native-maintenance", timeout=120):
        _new_destination(directory)
        control = _control(layout)
        root, entries = _inventory(data, max_bytes)
        document = {"version": 1, "platform": native_bundle.platform_key(),
                    "root": root, "control": control, "entries": entries}
        raw = (json.dumps(document, sort_keys=True, allow_nan=False) + "\n").encode()
        _manifest(raw, max_bytes)
        total = sum(row.get("bytes", 0) for row in entries)
        _space(directory.parent, data.parent, total, len(entries))
        directory.mkdir(mode=0o700)
        _private(directory, directory=True)
        partial = directory / ".cluster.partial.zip"
        with os.fdopen(_open_private(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as output:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as saved:
                saved.writestr("manifest.json", raw)
                for row in entries:
                    name = "data/" + row["path"]
                    if row["kind"] == "directory":
                        saved.writestr(name + "/", b"")
                    else:
                        with _data_file(data / row["path"]) as source, saved.open(name, "w", force_zip64=True) as target:
                            _copy_member(source, target, row)
            output.flush()
            os.fsync(output.fileno())
        digest = _private_digest(partial)
        receipt = {"version": 1, "archive_bytes": digest["bytes"], "archive_sha256": digest["sha256"],
                   "manifest_sha256": hashlib.sha256(raw).hexdigest(), "data_bytes": total,
                   "entries": len(entries), "system_identifier": control["system_identifier"]}
        _archive(partial, receipt, max_bytes)
        if _control(layout) != control or _inventory(data, max_bytes) != (root, entries):
            raise NativeSnapshotError("changed")
        os.replace(partial, directory / "cluster.zip")
        sync_directory(directory)
        write_document(directory / "receipt.json", receipt)
        sync_directory(directory.parent)
        return {**receipt, "receipt_sha256": _private_digest(directory / "receipt.json")["sha256"]}


@_guard
def verify(directory: Path, commitment: str, *, max_bytes=DEFAULT_MAX_BYTES):
    _budget(max_bytes)
    directory = _directory(directory)
    _private(directory, directory=True)
    return _archive(directory / "cluster.zip", _receipt(directory, commitment), max_bytes)


def _restore_metadata(path, row):
    if os.name != "nt":
        current = path.stat()
        if (current.st_uid, current.st_gid) != (row["uid"], row["gid"]):
            os.chown(path, row["uid"], row["gid"])
    path.chmod(row["mode"])
    os.utime(path, ns=(row["mtime_ns"], row["mtime_ns"]))
    if os.name != "nt" and row.get("kind") == "file":
        with _data_file(path) as stream:
            os.fsync(stream.fileno())


@_guard
def restore(directory: Path, commitment: str, layout, *, max_bytes=DEFAULT_MAX_BYTES):
    _budget(max_bytes)
    directory, destination = _directory(directory), _directory(layout.data)
    if destination.is_relative_to(directory) or directory.is_relative_to(destination):
        raise NativeSnapshotError("conflict")
    _new_destination(destination)
    with profile_lock(destination.parent / ".native-maintenance", timeout=120):
        _new_destination(destination)
        manifest = verify(directory, commitment, max_bytes=max_bytes)
        receipt = _receipt(directory, commitment)
        if shutil.disk_usage(destination.parent).free < receipt["data_bytes"] + 32 * 1024**2:
            raise NativeSnapshotError("space_low")
        destination.mkdir(mode=0o700)
        _private(destination, directory=True)
        _archive(directory / "cluster.zip", receipt, max_bytes, destination=destination)
        for row in sorted(manifest["entries"], key=lambda row: len(PurePosixPath(row["path"]).parts), reverse=True):
            _restore_metadata(destination / row["path"], row)
            if row["kind"] == "directory":
                sync_directory(destination / row["path"])
        _restore_metadata(destination, manifest["root"])
        sync_directory(destination)
        sync_directory(destination.parent)
        root, entries = _inventory(destination, max_bytes)
        if (root, entries) != (manifest["root"], manifest["entries"]) or _control(layout) != manifest["control"]:
            raise NativeSnapshotError("invalid")
        return {"verified": True, "receipt_sha256": commitment,
                "system_identifier": receipt["system_identifier"], "data_bytes": receipt["data_bytes"]}
