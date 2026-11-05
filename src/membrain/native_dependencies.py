"""Verified additive dependencies for already bound native engine prefixes."""
from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import shutil
import stat
import tarfile

from . import native_bundle
from .local_profile import _directory, profile_lock

XML_LIBRARY = "lib/libxml2.so.2"
XML_ADDITIONS = {XML_LIBRARY, "share/licenses/libxml2/COPYING", "share/licenses/libxml2/Copyright",
                 "share/licenses/libxml2/debian-copyright", "share/licenses/libxml2/source.json"}


def _entry():
    index = json.loads((native_bundle.RESOURCES / "index.json").read_text(encoding="utf-8"))
    if (index["contract_version"], index["postgres"], index["vector"]) != (
            1, native_bundle.POSTGRES, native_bundle.VECTOR):
        raise native_bundle._invalid()
    return index["platforms"][native_bundle.platform_key()]


def _previous(entry, current):
    previous = entry.get("previous")
    if previous is None:
        return None
    if (not (native_bundle.platform_key() or "").startswith("linux-")
            or not isinstance(previous, dict) or set(previous) != {"manifest", "manifest_sha256"}
            or previous["manifest_sha256"] == entry["manifest_sha256"]):
        raise native_bundle._invalid()
    records = native_bundle._manifest(previous)
    if (current.keys() - records.keys() != XML_ADDITIONS
            or any(current.get(name) != row for name, row in records.items())
            or current[XML_LIBRARY]["bytes"] > 16 * 1024**2):
        raise native_bundle._invalid()
    return previous, records


def target_manifest(prefix):
    entry = _entry()
    current = native_bundle._manifest(entry)
    previous = _previous(entry, current)
    if native_bundle._validate_tree(prefix, current):
        return entry["manifest_sha256"]
    if previous is not None and native_bundle._validate_tree(prefix, previous[1]):
        return previous[0]["manifest_sha256"]
    raise native_bundle._invalid()


def _root(shared):
    if shared:
        from .embedded_database import SHARED_ROOT

        if os.geteuid() != 0:
            raise native_bundle._invalid()
        return SHARED_ROOT / "native-dependencies"
    return native_bundle._cache_directory() / "dependencies"


def _matches(directory, row, shared):
    try:
        metadata = directory.lstat()
        mode = 0o755 if shared else 0o700
        if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != mode
                or {path.name for path in directory.iterdir()} != {"libxml2.so.2"}):
            return False
        library = directory / "libxml2.so.2"
        metadata = library.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o644
                or metadata.st_size != row["bytes"]):
            return False
        descriptor = os.open(library, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            return ((opened.st_dev, opened.st_ino) == (metadata.st_dev, metadata.st_ino)
                    and hashlib.file_digest(stream, "sha256").hexdigest() == row["sha256"])
    except OSError:
        return False


def _prepare(entry, row, shared):
    root = _directory(_root(shared))
    root.mkdir(parents=True, mode=0o755 if shared else 0o700, exist_ok=True)
    metadata = root.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != (0o755 if shared else 0o700):
        raise native_bundle._invalid()
    with profile_lock(root / ".lock", timeout=120):
        base = root / ("libxml2-" + row["sha256"])
        for directory in (base, *sorted(root.glob(base.name + "-repair-*"))):
            if _matches(directory, row, shared):
                return directory
        if shutil.disk_usage(root).free < row["bytes"] + 4 * 1024**2:
            raise native_bundle.NativeBundleError("embedded_database_space_low",
                                                 "Not enough free space to prepare the verified database dependency. Existing engines and data were preserved.")
        data = native_bundle._resource(entry["overlay"], entry["overlay_sha256"])
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = [member for member in archive if member.name == XML_LIBRARY]
            if len(members) != 1 or not members[0].isfile() or members[0].size != row["bytes"]:
                raise native_bundle._invalid()
            with archive.extractfile(members[0]) as stream:
                library = stream.read(row["bytes"] + 1)
        if len(library) != row["bytes"] or hashlib.sha256(library).hexdigest() != row["sha256"]:
            raise native_bundle._invalid()
        staging = root / (".dependency-" + secrets.token_hex(12))
        staging.mkdir(mode=0o700)
        try:
            with (staging / "libxml2.so.2").open("xb") as stream:
                stream.write(library)
                stream.flush()
                os.fchmod(stream.fileno(), 0o644)
                os.fsync(stream.fileno())
            staging.chmod(0o755 if shared else 0o700)
            if not _matches(staging, row, shared):
                raise native_bundle._invalid()
            native_bundle._sync_directory(staging)
            target = base if not base.exists() and not base.is_symlink() else root / (
                base.name + "-repair-" + secrets.token_hex(12))
            os.replace(staging, target)
            native_bundle._sync_directory(root)
            return target
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def xml_directory(prefix, *, shared=False):
    if not (native_bundle.platform_key() or "").startswith("linux-"):
        return None
    if (prefix / XML_LIBRARY).exists() or (prefix / XML_LIBRARY).is_symlink():
        return None
    try:
        entry = _entry()
        if entry.get("previous") is None:
            return None
        current = native_bundle._manifest(entry)
        previous = _previous(entry, current)
        if not native_bundle._validate_tree(prefix, previous[1]):
            return None
        return _prepare(entry, current[XML_LIBRARY], shared)
    except native_bundle.NativeBundleError:
        raise
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError):
        raise native_bundle._invalid() from None
