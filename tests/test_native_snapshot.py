import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from membrain import native_snapshot


@pytest.fixture
def cluster(tmp_path, monkeypatch):
    data = tmp_path / "original"
    data.mkdir(mode=0o700)
    (data / "global").mkdir(mode=0o700)
    (data / "base").mkdir(mode=0o700)
    (data / "base/empty").mkdir(mode=0o700)
    (data / "PG_VERSION").write_bytes(b"16\n")
    (data / "global/pg_control").write_bytes(b"synthetic control\0" * 32)
    (data / "base/memory").write_bytes(b"private synthetic memory\0\xff\n")
    (data / "postgresql.conf").write_bytes(b"# preserve custom bytes\r\nshared_buffers=64MB\r\n")
    for path in data.rglob("*"):
        if path.is_file():
            path.chmod(0o600)
    layout = SimpleNamespace(data=data, binaries=tmp_path / "bin", account=None, log=tmp_path / "log")
    calls = []

    def run(layout, program, *arguments, **options):
        assert program == "pg_controldata" and arguments == ("-D", str(layout.data))
        assert options == {"timeout": 30, "capture": True}
        calls.append(layout.data)
        output = ("pg_control version number: 1300\nCatalog version number: 202307071\n"
                  "Database system identifier: 1234567890123456789\nDatabase cluster state: shut down\n"
                  "Latest checkpoint location: 0/1234ABCD\n")
        return subprocess.CompletedProcess([], 0, stdout=output.encode())

    monkeypatch.setattr(native_snapshot.embedded_database, "_run", run)
    monkeypatch.setattr(native_snapshot.shutil, "disk_usage", lambda path: SimpleNamespace(free=1024**4))
    return SimpleNamespace(root=tmp_path, layout=layout, backup=tmp_path / "backup", calls=calls)


def restored_layout(cluster, name="restored"):
    return SimpleNamespace(**{**vars(cluster.layout), "data": cluster.root / name})


def source_state(cluster):
    return native_snapshot._inventory(cluster.layout.data, native_snapshot.DEFAULT_MAX_BYTES)


def create(cluster):
    return native_snapshot.create(cluster.layout, cluster.backup)


def rewrite(cluster, receipt, transform_manifest=None, transform_members=None):
    archive = cluster.backup / "cluster.zip"
    with zipfile.ZipFile(archive) as saved:
        members = {info.filename: saved.read(info) for info in saved.infolist()}
    if transform_manifest:
        document = json.loads(members["manifest.json"])
        transform_manifest(document)
        members["manifest.json"] = json.dumps(document).encode()
    if transform_members:
        transform_members(members)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as saved:
        for name, data in members.items():
            saved.writestr(name, data)
    metadata = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    metadata.update(archive_bytes=archive.stat().st_size, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    manifest_sha256=hashlib.sha256(members["manifest.json"]).hexdigest())
    (cluster.backup / "receipt.json").write_text(json.dumps(metadata))
    return hashlib.sha256((cluster.backup / "receipt.json").read_bytes()).hexdigest()


def test_complete_private_snapshot_restores_every_byte_mode_owner_and_timestamp(cluster):
    original = source_state(cluster)
    receipt = create(cluster)
    manifest = native_snapshot.verify(cluster.backup, receipt["receipt_sha256"])
    assert manifest["root"] == original[0] and manifest["entries"] == original[1]
    assert len(cluster.calls) == 2
    layout = restored_layout(cluster)
    result = native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], layout)
    assert result == {"verified": True, "receipt_sha256": receipt["receipt_sha256"],
                      "system_identifier": receipt["system_identifier"], "data_bytes": receipt["data_bytes"]}
    assert native_snapshot._inventory(layout.data, 1024**2) == original == source_state(cluster)
    assert (layout.data / "base/empty").is_dir()
    assert {path.name for path in cluster.backup.iterdir()} == {"receipt.json", "cluster.zip"}
    if os.name != "nt":
        assert stat.S_IMODE(cluster.backup.stat().st_mode) == 0o700
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in cluster.backup.iterdir())


@pytest.mark.parametrize("target", ["backup", "source", "source_child"])
def test_snapshot_never_overwrites_or_recurses_into_existing_data(cluster, target):
    original = source_state(cluster)
    destination = {"backup": cluster.backup, "source": cluster.layout.data,
                   "source_child": cluster.layout.data / "backup"}[target]
    if target == "backup":
        destination.mkdir()
        (destination / "keep").write_bytes(b"keep")
    with pytest.raises(native_snapshot.NativeSnapshotError) as error:
        native_snapshot.create(cluster.layout, destination)
    assert error.value.code == "native_snapshot_conflict"
    assert source_state(cluster) == original
    if target == "backup":
        assert (destination / "keep").read_bytes() == b"keep"


def test_restore_refuses_existing_source_or_destination_without_touching_it(cluster):
    receipt = create(cluster)
    original = source_state(cluster)
    with pytest.raises(native_snapshot.NativeSnapshotError, match="already exists"):
        native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], cluster.layout)
    assert source_state(cluster) == original
    layout = restored_layout(cluster)
    layout.data.mkdir()
    (layout.data / "keep").write_bytes(b"keep")
    with pytest.raises(native_snapshot.NativeSnapshotError, match="already exists"):
        native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], layout)
    assert (layout.data / "keep").read_bytes() == b"keep"


def test_restore_cannot_nest_a_cluster_inside_the_original_cluster(cluster):
    receipt = create(cluster)
    original = source_state(cluster)
    nested = SimpleNamespace(**{**vars(cluster.layout), "data": cluster.layout.data / "base/nested"})
    with pytest.raises(native_snapshot.NativeSnapshotError, match="already exists"):
        native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], nested)
    assert source_state(cluster) == original
    assert not (cluster.layout.data / "base/.native-maintenance").exists()


def test_snapshot_budget_is_checked_before_reading_an_oversized_file(cluster):
    original = source_state(cluster)
    with pytest.raises(native_snapshot.NativeSnapshotError) as error:
        native_snapshot.create(cluster.layout, cluster.backup, max_bytes=1)
    assert error.value.code == "native_snapshot_limit_exceeded"
    assert source_state(cluster) == original and not cluster.backup.exists()


@pytest.mark.parametrize("kind", ["pid", "dirty", "major", "control_warning", "failed_tool"])
def test_running_unclean_newer_or_damaged_clusters_are_not_snapshotted(cluster, monkeypatch, kind):
    if kind == "pid":
        (cluster.layout.data / "postmaster.pid").write_text("12345")
    elif kind == "major":
        (cluster.layout.data / "PG_VERSION").write_text("17\n")
    else:
        run = native_snapshot.embedded_database._run

        def changed(*args, **kwargs):
            result = run(*args, **kwargs)
            if kind == "dirty":
                result.stdout = result.stdout.replace(b"shut down", b"in production")
            elif kind == "control_warning":
                result.stdout += b"pg_controldata: warning: Calculated CRC checksum does not match\n"
            else:
                result.returncode = 1
            return result

        monkeypatch.setattr(native_snapshot.embedded_database, "_run", changed)
    original = source_state(cluster)
    with pytest.raises(native_snapshot.NativeSnapshotError):
        create(cluster)
    assert not cluster.backup.exists() and source_state(cluster) == original


def test_windows_version_file_newline_is_accepted_without_relaxing_the_major(cluster):
    (cluster.layout.data / "PG_VERSION").write_bytes(b"16\r\n")
    assert create(cluster)["system_identifier"] == "1234567890123456789"


@pytest.mark.parametrize("kind", ["file_link", "directory_link", "hardlink"] + (["fifo"] if hasattr(os, "mkfifo") else []))
def test_external_links_and_special_files_are_refused_without_reading_or_modifying_them(cluster, kind):
    outside = cluster.root / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"outside private data")
    path = cluster.layout.data / "external"
    if kind == "file_link":
        path.symlink_to(outside / "keep")
    elif kind == "directory_link":
        path.symlink_to(outside, target_is_directory=True)
    elif kind == "hardlink":
        os.link(outside / "keep", path)
    else:
        os.mkfifo(path)
    with pytest.raises(native_snapshot.NativeSnapshotError) as error:
        create(cluster)
    assert error.value.code == "native_snapshot_unsupported"
    assert not cluster.backup.exists() and (outside / "keep").read_bytes() == b"outside private data"


@pytest.mark.parametrize("phase", ["create", "restore"])
def test_low_space_keeps_original_and_does_not_create_a_partial_destination(cluster, monkeypatch, phase):
    receipt = create(cluster) if phase == "restore" else None
    monkeypatch.setattr(native_snapshot.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    original = source_state(cluster)
    with pytest.raises(native_snapshot.NativeSnapshotError) as error:
        if phase == "create":
            create(cluster)
        else:
            native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], restored_layout(cluster))
    assert error.value.code == "native_snapshot_space_low"
    assert source_state(cluster) == original
    assert not (cluster.root / ("backup" if phase == "create" else "restored")).exists()


@pytest.mark.parametrize("part", ["commitment", "receipt", "archive"])
def test_tampering_never_creates_a_restore_directory(cluster, part):
    receipt = create(cluster)
    commitment = receipt["receipt_sha256"]
    if part == "commitment":
        commitment = "0" * 64
    else:
        path = cluster.backup / ("receipt.json" if part == "receipt" else "cluster.zip")
        with path.open("ab") as stream:
            stream.write(b"changed")
    with pytest.raises(native_snapshot.NativeSnapshotError):
        native_snapshot.restore(cluster.backup, commitment, restored_layout(cluster))
    assert not (cluster.root / "restored").exists()


@pytest.mark.parametrize("path", ["../outside", "/outside", "global/../../outside", "a\\outside", "C:outside",
                                 "global/./file", "global//file", ".", "CON", "NUL.txt", "global/a.", "global/a "])
def test_authenticated_but_unsafe_manifest_paths_fail_before_extraction(cluster, path):
    receipt = create(cluster)
    commitment = rewrite(cluster, receipt, lambda doc: doc["entries"][-1].update(path=path))
    with pytest.raises(native_snapshot.NativeSnapshotError):
        native_snapshot.restore(cluster.backup, commitment, restored_layout(cluster))
    assert not (cluster.root / "restored").exists() and not (cluster.root / "outside").exists()


@pytest.mark.parametrize("damage", ["payload", "extra", "missing", "parent", "metadata", "budget", "platform"])
def test_valid_outer_checksums_do_not_replace_payload_manifest_and_platform_validation(cluster, damage):
    receipt = create(cluster)

    def document(value):
        if damage == "parent":
            next(row for row in value["entries"] if row["path"] == "global")["path"] = "different"
        elif damage == "metadata":
            value["entries"][0]["mode"] = 0o4755
        elif damage == "platform":
            value["platform"] = "different-platform"

    def members(value):
        if damage == "payload":
            value["data/base/memory"] = b"tampered memory"
        elif damage == "extra":
            value["data/extra"] = b"extra"
        elif damage == "missing":
            del value["data/base/memory"]

    commitment = rewrite(cluster, receipt, document, members)
    with pytest.raises(native_snapshot.NativeSnapshotError):
        native_snapshot.restore(cluster.backup, commitment, restored_layout(cluster),
                                max_bytes=1 if damage == "budget" else native_snapshot.DEFAULT_MAX_BYTES)
    assert not (cluster.root / "restored").exists()


def test_source_changes_before_publication_leave_original_and_unpublished_partial(cluster, monkeypatch):
    archive = native_snapshot._archive

    def change_source(*args, **kwargs):
        result = archive(*args, **kwargs)
        (cluster.layout.data / "base/memory").write_bytes(b"newer data must survive")
        return result

    monkeypatch.setattr(native_snapshot, "_archive", change_source)
    with pytest.raises(native_snapshot.NativeSnapshotError) as error:
        create(cluster)
    assert error.value.code == "native_snapshot_changed"
    assert (cluster.layout.data / "base/memory").read_bytes() == b"newer data must survive"
    assert (cluster.backup / ".cluster.partial.zip").is_file()
    assert not (cluster.backup / "receipt.json").exists()


def test_publication_failure_never_creates_a_valid_receipt_or_removes_original(cluster, monkeypatch):
    original = source_state(cluster)

    def fail(*args, **kwargs):
        raise OSError("synthetic interrupted publication")

    monkeypatch.setattr(native_snapshot.os, "replace", fail)
    with pytest.raises(native_snapshot.NativeSnapshotError):
        create(cluster)
    assert source_state(cluster) == original
    assert not (cluster.backup / "receipt.json").exists()
    assert (cluster.backup / ".cluster.partial.zip").is_file()


def test_interrupted_restore_preserves_partial_backup_and_original_then_allows_fresh_staging(cluster, monkeypatch):
    receipt = create(cluster)
    original = source_state(cluster)
    layout = restored_layout(cluster)
    open_private = native_snapshot._open_private

    def fail(path, flags):
        if path == layout.data / "base/memory":
            raise OSError("synthetic interrupted extraction")
        return open_private(path, flags)

    with monkeypatch.context() as patch:
        patch.setattr(native_snapshot, "_open_private", fail)
        with pytest.raises(native_snapshot.NativeSnapshotError):
            native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], layout)
    assert (layout.data / "PG_VERSION").read_bytes() == b"16\n"
    assert not (layout.data / "base/memory").exists()
    assert source_state(cluster) == original
    native_snapshot.verify(cluster.backup, receipt["receipt_sha256"])
    with pytest.raises(native_snapshot.NativeSnapshotError, match="already exists"):
        native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], layout)
    fresh = restored_layout(cluster, "fresh-staging")
    assert native_snapshot.restore(cluster.backup, receipt["receipt_sha256"], fresh)["verified"]
    assert native_snapshot._inventory(fresh.data, 1024**2) == original


def test_parallel_creators_publish_once_and_preserve_the_same_original(cluster):
    original = source_state(cluster)

    def attempt(_):
        try:
            return create(cluster)
        except native_snapshot.NativeSnapshotError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(attempt, range(4)))
    receipts = [value for value in results if isinstance(value, dict)]
    assert len(receipts) == 1 and results.count("native_snapshot_conflict") == 3
    assert source_state(cluster) == original
    native_snapshot.verify(cluster.backup, receipts[0]["receipt_sha256"])


def test_process_death_leaves_no_usable_snapshot_and_retry_preserves_partial(cluster):
    script = """
import os,sys
from pathlib import Path
from types import SimpleNamespace
from membrain import native_snapshot
root=Path(sys.argv[1])
native_snapshot._control=lambda layout:{'system_identifier':'1234567890123456789','checkpoint':'0/1234ABCD'}
native_snapshot._archive=lambda *args,**kwargs:os._exit(73)
native_snapshot.create(SimpleNamespace(data=root/'original'),root/'abandoned')
"""
    result = subprocess.run([sys.executable, "-c", script, str(cluster.root)], capture_output=True, timeout=30)
    assert result.returncode == 73, result.stderr
    abandoned = cluster.root / "abandoned"
    partial = (abandoned / ".cluster.partial.zip").read_bytes()
    assert not (abandoned / "receipt.json").exists()
    with pytest.raises(native_snapshot.NativeSnapshotError):
        native_snapshot.verify(abandoned, "0" * 64)
    with pytest.raises(native_snapshot.NativeSnapshotError, match="already exists"):
        native_snapshot.create(cluster.layout, abandoned)
    create(cluster)
    assert (abandoned / ".cluster.partial.zip").read_bytes() == partial
