"""Durable, verified engine copies independent of replaceable Python environments."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from .local_profile import (
    LocalProfileBusy,
    LocalProfileError,
    _directory,
    _open_private,
    _private,
    profile_lock,
)
from .native_bundle import _secure_windows_tree, _sync_directory

_MAX_BYTES = 1024**3
_MAX_FILES = 20000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TOOLS = ("postgres", "pg_ctl", "pg_controldata", "initdb", "pg_dump", "pg_restore")
_MESSAGES = {
    "invalid": "The preserved database engine failed integrity checks. Existing engines and database data were preserved.",
    "changed": "The database engine changed while being preserved. Retry after the package update finishes; existing engines and data were preserved.",
    "busy": "Another process is preserving the database engine. Retry after it finishes; existing data was preserved.",
    "space_low": "Not enough free space to preserve the database engine. Existing engines and database data were preserved.",
    "failed": "The database engine could not be preserved. Check file access and free space; existing engines, data and partial copies were preserved.",
}


class NativeEngineStoreError(RuntimeError):
    def __init__(self, reason):
        self.code = "embedded_database_engine_" + reason
        super().__init__(_MESSAGES[reason])


@dataclass(frozen=True)
class PreservedEngine:
    directory: Path
    commitment: str
    files: int
    bytes: int

    @property
    def prefix(self):
        return self.directory / "pgserver/pginstall"


def _file(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        before, opened = path.lstat(), os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(opened.st_mode)
                or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                or opened.st_size > _MAX_BYTES):
            raise NativeEngineStoreError("invalid")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _hash(path):
    digest, size = hashlib.sha256(), 0
    with _file(path) as stream:
        before = os.fstat(stream.fileno())
        while chunk := stream.read(65536):
            size += len(chunk)
            if size > _MAX_BYTES:
                raise NativeEngineStoreError("invalid")
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    if (size != before.st_size or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
        raise NativeEngineStoreError("changed")
    return size, digest.hexdigest()


def _tree(root, prefix="", *, copied=False):
    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise NativeEngineStoreError("invalid")
    rows, total = [], 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if copied and relative == ".complete":
            continue
        metadata = path.lstat()
        name = prefix + relative
        if (len(name.encode()) > 4096 or any(ord(char) < 32 for char in name)
                or len(rows) >= _MAX_FILES
                or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                and not stat.S_ISLNK(metadata.st_mode)):
            raise NativeEngineStoreError("invalid")
        if copied and os.name != "nt" and metadata.st_uid != os.getuid():
            raise NativeEngineStoreError("invalid")
        row = {"path": name}
        if stat.S_ISLNK(metadata.st_mode):
            link = path.readlink()
            if link.is_absolute() or not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
                raise NativeEngineStoreError("invalid")
            row.update(kind="link", target=link.as_posix())
        elif stat.S_ISDIR(metadata.st_mode):
            if copied and os.name != "nt" and stat.S_IMODE(metadata.st_mode) != 0o755:
                raise NativeEngineStoreError("invalid")
            row.update(kind="directory")
        elif stat.S_ISREG(metadata.st_mode):
            mode = 0o755 if metadata.st_mode & 0o111 else 0o644
            if copied and (metadata.st_nlink != 1 or os.name != "nt" and stat.S_IMODE(metadata.st_mode) != mode):
                raise NativeEngineStoreError("invalid")
            size, digest = _hash(path)
            total += size
            if total > _MAX_BYTES:
                raise NativeEngineStoreError("invalid")
            row.update(kind="file", bytes=size, sha256=digest, mode=mode if os.name != "nt" else 0)
        else:
            raise NativeEngineStoreError("invalid")
        rows.append(row)
    return sorted(rows, key=lambda row: row["path"])


def _roots(source):
    roots = {"pgserver/pginstall": source}
    for name, path in (("pgserver.libs", source.parent.parent / "pgserver.libs"),
                       ("pgserver/.dylibs", source.parent / ".dylibs"),
                       ("pgserver/.libs", source.parent / ".libs")):
        if path.exists() or path.is_symlink():
            roots[name] = path
    return roots


def _source(source):
    source = _directory(source)
    rows = [{"path": "pgserver", "kind": "directory"}]
    for name, root in _roots(source).items():
        rows.append({"path": name, "kind": "directory"})
        rows.extend(_tree(root, name + "/"))
    suffix = ".exe" if os.name == "nt" else ""
    names = {row["path"] for row in rows if row["kind"] == "file"}
    if not all("pgserver/pginstall/bin/" + tool + suffix in names for tool in _TOOLS):
        raise NativeEngineStoreError("invalid")
    if len(rows) > _MAX_FILES or sum(row.get("bytes", 0) for row in rows) > _MAX_BYTES:
        raise NativeEngineStoreError("invalid")
    return source, sorted(rows, key=lambda row: row["path"])


def _commitment(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _verified(directory, commitment):
    directory = _directory(directory)
    if not isinstance(commitment, str) or not _SHA.fullmatch(commitment) or not directory.is_dir():
        raise NativeEngineStoreError("invalid")
    metadata = directory.stat()
    if os.name != "nt" and (metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) not in (0o700, 0o755)):
        raise NativeEngineStoreError("invalid")
    with os.fdopen(_open_private(directory / ".complete", os.O_RDONLY), "rb") as stream:
        if stream.read(65) != commitment.encode():
            raise NativeEngineStoreError("invalid")
    rows = _tree(directory, copied=True)
    if _commitment(rows) != commitment:
        raise NativeEngineStoreError("invalid")
    return PreservedEngine(directory, commitment, sum(row["kind"] == "file" for row in rows),
                           sum(row.get("bytes", 0) for row in rows))


def verify(directory: Path, commitment: str):
    try:
        return _verified(directory, commitment)
    except NativeEngineStoreError:
        raise
    except (OSError, ValueError, LocalProfileError):
        raise NativeEngineStoreError("invalid") from None


def _copy_file(source, destination, row):
    digest, size = hashlib.sha256(), 0
    with _file(source) as incoming, destination.open("xb") as outgoing:
        while chunk := incoming.read(65536):
            size += len(chunk)
            if size > row["bytes"]:
                raise NativeEngineStoreError("changed")
            digest.update(chunk)
            outgoing.write(chunk)
        if os.name != "nt":
            os.fchmod(outgoing.fileno(), row["mode"])
        outgoing.flush()
        os.fsync(outgoing.fileno())
    if size != row["bytes"] or digest.hexdigest() != row["sha256"]:
        raise NativeEngineStoreError("changed")


def _preserve(source, store, shared, timeout):
    source, rows = _source(source)
    identity = _commitment(rows)
    store = _directory(store)
    sources = _roots(source)
    if any(store.is_relative_to(path) or path.is_relative_to(store) for path in sources.values()):
        raise NativeEngineStoreError("invalid")
    store.mkdir(mode=0o755 if shared else 0o700, parents=True, exist_ok=True)
    if shared:
        metadata = store.stat()
        if os.name == "nt" or metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
            raise NativeEngineStoreError("invalid")
    else:
        _private(store, directory=True)
    with profile_lock(store / ".engine-copy", timeout=timeout):
        base = store / ("postgres-" + identity[:24])
        for candidate in [base, *sorted(store.glob(base.name + "-repair-*"))]:
            try:
                return _verified(candidate, identity)
            except (NativeEngineStoreError, OSError, ValueError, LocalProfileError):
                pass
        if shutil.disk_usage(store).free < sum(row.get("bytes", 0) for row in rows) + 32 * 1024**2:
            raise NativeEngineStoreError("space_low")
        staging = store / (".engine-staging-" + secrets.token_hex(12))
        staging.mkdir(mode=0o700)
        _private(staging, directory=True)
        for row in rows:
            target = staging / row["path"]
            if row["kind"] == "directory":
                target.mkdir(mode=0o755)
                target.chmod(0o755)
                continue
            origin = next(name for name in sources if row["path"].startswith(name + "/"))
            original = sources[origin] / row["path"][len(origin) + 1:]
            if row["kind"] == "link":
                target.symlink_to(row["target"])
            else:
                _copy_file(original, target, row)
        if _source(source)[1] != rows or _tree(staging, copied=True) != rows:
            raise NativeEngineStoreError("changed")
        if os.name == "nt":
            _secure_windows_tree(staging)
        descriptor = _open_private(staging / ".complete", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(identity.encode())
            stream.flush()
            os.fsync(stream.fileno())
        for path in sorted((p for p in staging.rglob("*") if p.is_dir()), reverse=True):
            _sync_directory(path)
        if shared:
            staging.chmod(0o755)
        _sync_directory(staging)
        target = base if not base.exists() and not base.is_symlink() else store / (
            base.name + "-repair-" + secrets.token_hex(12))
        os.replace(staging, target)
        _sync_directory(store)
        return _verified(target, identity)


def preserve(source: Path, store: Path, *, shared: bool = False, timeout: float = 120):
    """Copy already trusted native inputs; this does not establish supplier provenance."""
    try:
        return _preserve(source, store, shared, timeout)
    except NativeEngineStoreError:
        raise
    except LocalProfileBusy:
        raise NativeEngineStoreError("busy") from None
    except (OSError, ValueError, LocalProfileError):
        raise NativeEngineStoreError("failed") from None
