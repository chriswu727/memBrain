import hashlib
import json
import os
import shutil

from .local_profile import profile_lock

COMPACT_BYTES = 1024 * 1024
BATCH_BYTES = 256 * 1024
MAX_LINE_BYTES = 64 * 1024 * 1024 + 1


def sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _write(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def cursor_path(path):
    return path.with_suffix(".cursor.json")


def reset(path):
    cursor_path(path).unlink(missing_ok=True)
    sync_directory(path.parent)


def _resume(path, stream):
    position, checksum = 0, hashlib.sha256()
    try:
        with cursor_path(path).open("rb") as saved:
            cursor = json.loads(saved.read(4096))
        offset = cursor["offset"]
        if type(offset) is int and 0 < offset <= min(os.fstat(stream.fileno()).st_size, MAX_LINE_BYTES):
            remaining = offset
            while remaining:
                chunk = stream.read(min(remaining, 65536))
                if not chunk:
                    break
                checksum.update(chunk)
                remaining -= len(chunk)
            if not remaining and checksum.hexdigest() == cursor["sha256"]:
                position = offset
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if not position:
        checksum = hashlib.sha256()
        stream.seek(0)
    return position, checksum


def batch(path, limit):
    with path.open("rb") as stream:
        position, checksum = _resume(path, stream)
        lines, size = [], 0
        for _ in range(limit):
            line = stream.readline(MAX_LINE_BYTES)
            if not line:
                break
            lines.append(line)
            size += len(line)
            if size >= BATCH_BYTES:
                break
    return position, checksum, lines


def pending(path):
    if not path.exists():
        return 0
    try:
        with profile_lock(path.parent / "spool-write-lock", timeout=5), path.open("rb") as stream:
            _resume(path, stream)
            return sum(bool(line.strip()) for line in stream)
    except FileNotFoundError:
        return 0


def acknowledge(path, offset, checksum):
    _write(cursor_path(path), json.dumps({"offset": offset, "sha256": checksum.hexdigest()}).encode())


def unacknowledged(path):
    with path.open("rb") as stream:
        _resume(path, stream)
        yield from stream


def replace_queue(path, payload):
    reset(path)
    _write(path, payload)


def compact(path, offset, *, force=False):
    size = path.stat().st_size
    if not offset or not force and offset < COMPACT_BYTES and offset * 2 < size:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with path.open("rb") as stream, os.fdopen(descriptor, "wb") as target:
        stream.seek(offset)
        shutil.copyfileobj(stream, target, length=65536)
        target.flush()
        os.fsync(target.fileno())
    # Clearing the cursor first makes either side of an interrupted replacement safe to replay.
    reset(path)
    os.replace(temporary, path)
    sync_directory(path.parent)
