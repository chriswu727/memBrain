"""Verified, per-user PostgreSQL installations assembled outside site-packages."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

from .local_profile import _open_private, _private, profile_lock

RESOURCES = Path(__file__).parent / "resources" / "native"
POSTGRES = "16.15"
VECTOR = "0.8.6"
TOOLS = ("postgres", "pg_ctl", "initdb", "pg_dump", "pg_restore", "psql", "pg_config")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class NativeBundleError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _invalid():
    return NativeBundleError(
        "embedded_database_bundle_invalid",
        "The embedded database failed its integrity checks. Reinstall memBrain and its embedded extra; existing database data was preserved.",
    )


def platform_key():
    return {("Darwin", "arm64"): "macos-arm64", ("Darwin", "x86_64"): "macos-x86_64",
            ("Linux", "x86_64"): "linux-x86_64", ("Linux", "aarch64"): "linux-aarch64",
            ("Windows", "AMD64"): "windows-x86_64"}.get((platform.system(), platform.machine()))


def _path(name):
    if not isinstance(name, str):
        raise _invalid()
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts
            or "\\" in name or ":" in name or path.as_posix() != name):
        raise _invalid()
    return path


def _resource(name, digest):
    if _path(name).name != name or not _DIGEST.fullmatch(digest):
        raise _invalid()
    path = RESOURCES / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise _invalid()
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise _invalid()
    return data


def _source():
    key = platform_key()
    if key is None:
        return None
    try:
        spec = importlib.util.find_spec("postgresql_binaries")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    try:
        index = json.loads((RESOURCES / "index.json").read_text(encoding="utf-8"))
        if (index["contract_version"], index["postgres"], index["vector"]) != (1, POSTGRES, VECTOR):
            raise _invalid()
        entry = index["platforms"][key]
        directory = Path(next(iter(spec.submodule_search_locations)))
        archives = list(directory.glob("postgresql-*.tar.gz"))
        if len(archives) != 1 or not archives[0].is_file() or archives[0].is_symlink():
            raise _invalid()
        return key, entry, archives[0]
    except (OSError, ValueError, KeyError, TypeError):
        raise _invalid() from None


def available():
    return _source() is not None


def _cache_directory():
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Caches" / "memBrain" / "native"
    if os.name == "nt":
        value = os.environ.get("LOCALAPPDATA", "")
        root = Path(value) if value and Path(value).is_absolute() else Path.home() / "AppData" / "Local"
        return root / "memBrain" / "Cache" / "native"
    value = os.environ.get("XDG_CACHE_HOME", "")
    root = Path(value) if value and Path(value).is_absolute() else Path.home() / ".cache"
    return root / "membrain" / "native"


def environment(prefix):
    result = {key: value for key, value in os.environ.items()
              if not key.startswith(("PG", "MEMORY_", "MEMBRAIN_", "DYLD_", "LD_"))
              and key not in {"PYTHONPATH", "PYTHONHOME", "OPENSSL_CONF", "OPENSSL_MODULES"}}
    result["LC_ALL"] = "C"
    if (prefix / "lib" / "ossl-modules").is_dir():
        result.update(OPENSSL_CONF=os.devnull, OPENSSL_MODULES=str(prefix / "lib" / "ossl-modules"))
    return result


def _manifest(entry):
    raw = _resource(entry["manifest"], entry["manifest_sha256"])
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        data = stream.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise _invalid()
    document = json.loads(data)
    if (document["postgres"], document["vector"]) != (POSTGRES, VECTOR):
        raise _invalid()
    records = {}
    for row in document["files"]:
        name = _path(row["path"]).as_posix()
        if (name in records or not _DIGEST.fullmatch(row["sha256"])
                or type(row["bytes"]) is not int or not 0 <= row["bytes"] <= 512 * 1024 * 1024
                or type(row["mode"]) is not int or row["mode"] & ~0o777):
            raise _invalid()
        records[name] = row
    if not 1 <= len(records) <= 10000 or sum(row["bytes"] for row in records.values()) > 1024**3:
        raise _invalid()
    return records


def _validate_tree(prefix, records):
    try:
        return _tree_matches(prefix, records)
    except (OSError, ValueError):
        return False


def _tree_matches(prefix, records):
    if prefix.is_symlink() or not prefix.is_dir():
        return False
    actual = set()
    for path in prefix.rglob("*"):
        if not path.resolve(strict=True).is_relative_to(prefix):
            return False
        if path.is_dir() and not path.is_symlink():
            continue
        name = path.relative_to(prefix).as_posix()
        if name not in records or not path.is_file():
            return False
        metadata = path.stat()
        record = records[name]
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != record["bytes"]:
            return False
        if os.name != "nt" and stat.S_IMODE(metadata.st_mode) != record["mode"]:
            return False
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != record["sha256"]:
                return False
        actual.add(name)
    return actual == records.keys()


def _versions(prefix):
    suffix = ".exe" if os.name == "nt" else ""
    env = environment(prefix)
    for name in TOOLS:
        result = subprocess.run([str(prefix / "bin" / (name + suffix)), "--version"],
                                env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        if result.returncode or not result.stdout.decode("utf-8", "replace").strip().endswith(" " + POSTGRES):
            raise NativeBundleError(
                "embedded_database_dependencies_missing",
                "The embedded database tools could not load. Linux requires compatible OpenSSL 3, libxml2, Kerberos, zlib, LZ4 and Zstandard system libraries. Install the host dependencies or select the Docker engine. Existing data was preserved.",
            )
    crypto = prefix / "bin" / ("openssl" + suffix)
    if crypto.is_file():
        result = subprocess.run([str(crypto), "version"], env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=10)
        if result.returncode or not result.stdout.startswith(b"OpenSSL 3.5.9 "):
            raise _invalid()


def _sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _open_archive(archive):
    if archive.is_symlink() or not archive.is_file() or not 0 < archive.stat().st_size <= 128 * 1024 * 1024:
        raise _invalid()
    return archive.open("rb")


def _secure_windows_tree(prefix):
    # mkdir(0700), including tarfile's directories, can bind Owner Rights to Administrators rather than TokenUser.
    _private(prefix, directory=True)
    for path in prefix.rglob("*"):
        _private(path, directory=path.is_dir())


def _completed(target, identity, records):
    if target.is_symlink():
        raise _invalid()
    marker = target / ".complete"
    try:
        if (not marker.is_file() or marker.is_symlink() or marker.stat().st_size != len(identity)
                or marker.read_bytes() != identity.encode()):
            return False
        if _validate_tree(target / "pginstall", records):
            return True
        os.replace(marker, target / ".invalid")
    except OSError:
        pass
    return False


def prepare():
    source = _source()
    if source is None:
        return None
    key, entry, archive = source
    staging = None
    try:
        records = _manifest(entry)
        identity = entry["manifest_sha256"]
        root = _cache_directory()
        with profile_lock(root, timeout=120):
            base = root / ("v1-" + POSTGRES + "-" + key + "-" + identity[:24])
            for target in (base, *sorted(root.glob(base.name + "-repair-*"))):
                if _completed(target, identity, records):
                    _versions(target / "pginstall")
                    return target / "pginstall"
            overlay = _resource(entry["overlay"], entry["overlay_sha256"])
            if shutil.disk_usage(root).free < sum(row["bytes"] for row in records.values()) + 16 * 1024 * 1024:
                raise NativeBundleError("embedded_database_space_low",
                                        "Not enough free space to prepare the embedded database. Existing data and engine versions were preserved.")
            staging = root / (".staging-" + secrets.token_hex(12))
            staging.mkdir(mode=0o700)
            _private(staging, directory=True)
            with _open_archive(archive) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != entry["supplier"]["archive_sha256"]:
                    raise _invalid()
                stream.seek(0)
                with tarfile.open(fileobj=stream, mode="r:gz") as saved:
                    roots = {PurePosixPath(member.name).parts[0] for member in saved}
                    if len(roots) != 1 or not next(iter(roots)).startswith("postgresql-16.15.0-"):
                        raise _invalid()
                    saved.extractall(staging, filter="data")
            prefix = staging / next(iter(roots))
            os.replace(prefix, staging / "pginstall")
            prefix = staging / "pginstall"
            with tarfile.open(fileobj=io.BytesIO(overlay), mode="r:gz") as saved:
                for member in saved:
                    name = _path(member.name).as_posix()
                    if name not in records or not member.isfile():
                        raise _invalid()
                saved.extractall(prefix, filter="data")
            if os.name == "nt":
                _secure_windows_tree(prefix)
            else:
                for name, row in records.items():
                    path = prefix / name
                    if not path.is_symlink():
                        path.chmod(row["mode"])
            if not _validate_tree(prefix, records):
                raise _invalid()
            _versions(prefix)
            descriptor = _open_private(staging / ".complete", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(identity)
                stream.flush()
                os.fsync(stream.fileno())
            _sync_directory(staging)
            # Windows can keep a running server's directory locked; repair must leave its executable path intact.
            target = base if not base.exists() else root / (base.name + "-repair-" + secrets.token_hex(12))
            os.replace(staging, target)
            staging = None
            _sync_directory(root)
            return target / "pginstall"
    except NativeBundleError:
        raise
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError):
        raise NativeBundleError(
            "embedded_database_cache_failed",
            "The embedded database cache could not be prepared. Check file access, free space and required host libraries, then retry. Existing database data was preserved.",
        ) from None
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
