import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from membrain import native_bundle

CHECK_VERSIONS = native_bundle._versions


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def archive_bytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as saved:
        for name, content in entries.items():
            row = tarfile.TarInfo(name)
            row.size, row.mode = len(content), 0o644
            saved.addfile(row, io.BytesIO(content))
    return output.getvalue()


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    resources, supplier = tmp_path / "resources", tmp_path / "supplier"
    resources.mkdir()
    supplier.mkdir()
    files = {"bin/postgres": b"reviewed server", "lib/vector": b"reviewed extension",
             "share/fix-CVE-2024-4317.sql": b"reviewed catalog fix"}
    source = archive_bytes({"postgresql-16.15.0-test/bin/postgres": files["bin/postgres"],
                            "postgresql-16.15.0-test/share/fix-CVE-2024-4317.sql": files["share/fix-CVE-2024-4317.sql"]})
    archive = supplier / "postgresql-16.15.0-test.tar.gz"
    archive.write_bytes(source)
    overlay = archive_bytes({"lib/vector": files["lib/vector"]})
    (resources / "overlay.tar.gz").write_bytes(overlay)
    manifest = {"postgres": "16.15", "vector": "0.8.6", "files": [
        {"path": name, "bytes": len(data), "sha256": checksum(data), "mode": 0o644}
        for name, data in files.items()]}
    packed = gzip.compress(json.dumps(manifest).encode())
    (resources / "manifest.json.gz").write_bytes(packed)
    entry = {"manifest": "manifest.json.gz", "manifest_sha256": checksum(packed),
             "overlay": "overlay.tar.gz", "overlay_sha256": checksum(overlay),
             "supplier": {"archive_sha256": checksum(source)}}
    index = {"contract_version": 1, "postgres": "16.15", "vector": "0.8.6",
             "platforms": {"test": entry}}
    (resources / "index.json").write_text(json.dumps(index))
    monkeypatch.setattr(native_bundle, "RESOURCES", resources)
    monkeypatch.setattr(native_bundle, "platform_key", lambda: "test")
    find_spec = native_bundle.importlib.util.find_spec
    monkeypatch.setattr(native_bundle.importlib.util, "find_spec", lambda name: SimpleNamespace(
        submodule_search_locations=[str(supplier)]) if name == "postgresql_binaries" else find_spec(name))
    monkeypatch.setattr(native_bundle, "_cache_directory", lambda: tmp_path / "cache")
    monkeypatch.setattr(native_bundle, "_versions", lambda prefix: None)
    return SimpleNamespace(root=tmp_path, files=files, entry=entry, archive=archive,
                           source=source, resources=resources, manifest=manifest)


def test_availability_is_read_only_and_does_not_import_supplier(candidate):
    (candidate.archive.parent / "__init__.py").write_text("raise AssertionError('must not execute')")
    assert native_bundle.available()
    assert not (candidate.root / "cache").exists()
    assert candidate.archive.read_bytes() == candidate.source


def test_preparation_is_complete_private_and_reuses_verified_files(candidate):
    prefix = native_bundle.prepare()
    for name, content in candidate.files.items():
        assert (prefix / name).read_bytes() == content
    before = {path: (path.stat().st_ino, path.stat().st_mtime_ns) for path in prefix.rglob("*")}
    assert native_bundle.prepare() == prefix
    assert before == {path: (path.stat().st_ino, path.stat().st_mtime_ns) for path in prefix.rglob("*")}
    if os.name != "nt":
        assert (prefix.parent.parent.stat().st_mode & 0o777) == 0o700
        assert (prefix.parent / ".complete").stat().st_mode & 0o777 == 0o600
    assert candidate.archive.read_bytes() == candidate.source
    assert not list(prefix.parent.parent.glob(".staging-*"))


def test_extracted_permissions_are_private_before_native_tools_execute(candidate, monkeypatch):
    private = native_bundle._private
    secured = set()

    def secure(path, *, directory=False):
        private(path, directory=directory)
        secured.add((path, directory))

    def preflight(prefix):
        assert (prefix.parent, True) in secured
        if os.name == "nt":
            assert (prefix, True) in secured
            assert all((path, path.is_dir()) in secured for path in prefix.rglob("*"))

    monkeypatch.setattr(native_bundle, "_private", secure)
    monkeypatch.setattr(native_bundle, "_versions", preflight)
    native_bundle.prepare()


@pytest.mark.parametrize("damage", ["content", "missing", "extra", "marker", "dangling_link"])
def test_invalid_cache_is_retained_and_repaired_without_moving_live_binaries(candidate, damage, monkeypatch):
    prefix = native_bundle.prepare()
    replace = native_bundle.os.replace

    def preserve_path(source, target):
        assert Path(source) != prefix.parent
        return replace(source, target)

    monkeypatch.setattr(native_bundle.os, "replace", preserve_path)
    if damage == "content":
        (prefix / "lib/vector").write_bytes(b"unreviewed extension")
    elif damage == "missing":
        (prefix / "bin/postgres").unlink()
    elif damage == "extra":
        (prefix / "unreviewed").write_bytes(b"extra")
    elif damage == "marker":
        (prefix.parent / ".complete").write_bytes(b"\xff" * 64)
    else:
        (prefix / "lib/vector").unlink()
        (prefix / "lib/vector").symlink_to(prefix / "missing")
    repaired = native_bundle.prepare()
    assert repaired != prefix
    assert native_bundle.prepare() == repaired
    assert (repaired / "lib/vector").read_bytes() == candidate.files["lib/vector"]
    assert prefix.parent.is_dir()
    assert not list(prefix.parent.parent.glob(".staging-*"))
    assert candidate.archive.read_bytes() == candidate.source


@pytest.mark.parametrize("part", ["archive", "overlay", "manifest"])
def test_corrupt_inputs_never_publish_a_complete_cache(candidate, part):
    path = candidate.archive if part == "archive" else candidate.resources / (
        "overlay.tar.gz" if part == "overlay" else "manifest.json.gz")
    path.write_bytes(b"corrupt")
    with pytest.raises(native_bundle.NativeBundleError):
        native_bundle.prepare()
    assert not list(candidate.root.rglob(".complete"))
    assert not list((candidate.root / "cache").glob(".staging-*"))


def test_archive_escape_is_rejected_even_when_its_checksum_matches(candidate):
    source = archive_bytes({"postgresql-16.15.0-test/../../outside": b"escape"})
    candidate.archive.write_bytes(source)
    candidate.entry["supplier"]["archive_sha256"] = checksum(source)
    index = json.loads((candidate.resources / "index.json").read_text())
    index["platforms"]["test"] = candidate.entry
    (candidate.resources / "index.json").write_text(json.dumps(index))
    with pytest.raises(native_bundle.NativeBundleError):
        native_bundle.prepare()
    assert not (candidate.root / "outside").exists()
    assert not list(candidate.root.rglob(".complete"))


@pytest.mark.parametrize("name", ["../outside", "/outside", "a/../../outside", "a\\outside", "a:outside", "a/./b", None])
def test_native_manifest_paths_cannot_escape(name):
    with pytest.raises(native_bundle.NativeBundleError):
        native_bundle._path(name)


def test_unavailable_supplier_does_not_select_legacy_pgserver(candidate, monkeypatch):
    monkeypatch.setattr(native_bundle.importlib.util, "find_spec", lambda name: None)
    assert not native_bundle.available()
    assert native_bundle.prepare() is None
    assert not (candidate.root / "cache").exists()


def test_failed_publication_cleans_only_its_own_staging_directory(candidate, monkeypatch):
    old = candidate.root / "unrelated"
    old.mkdir()
    (old / "keep").write_bytes(b"keep")
    original = native_bundle.os.replace

    def interrupted(source, target):
        if Path(source).name.startswith(".staging-"):
            raise OSError("synthetic publication failure")
        return original(source, target)

    monkeypatch.setattr(native_bundle.os, "replace", interrupted)
    with pytest.raises(native_bundle.NativeBundleError):
        native_bundle.prepare()
    assert not list((candidate.root / "cache").glob(".staging-*"))
    assert not list(candidate.root.rglob(".complete"))
    assert (old / "keep").read_bytes() == b"keep"


def test_parallel_preparation_publishes_one_complete_prefix(candidate):
    barrier = threading.Barrier(4)

    def prepare():
        barrier.wait(timeout=5)
        return native_bundle.prepare()

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: prepare(), range(4)))
    assert len(set(results)) == 1
    assert len(list((candidate.root / "cache").glob("*/.complete"))) == 1
    assert not list((candidate.root / "cache").glob(".staging-*"))


def test_low_space_preserves_supplier_and_existing_cache(candidate, monkeypatch):
    monkeypatch.setattr(native_bundle.shutil, "disk_usage", lambda root: SimpleNamespace(free=0))
    with pytest.raises(native_bundle.NativeBundleError) as error:
        native_bundle.prepare()
    assert error.value.code == "embedded_database_space_low"
    assert candidate.archive.read_bytes() == candidate.source
    assert not list((candidate.root / "cache").glob(".staging-*"))
    assert not list(candidate.root.rglob(".complete"))


def test_process_death_before_publication_leaves_no_usable_partial_cache(candidate):
    script = """
import json,os,sys
from pathlib import Path
from membrain import native_bundle
root=Path(sys.argv[1])
entry=json.loads((root/'resources/index.json').read_text())['platforms']['test']
native_bundle.RESOURCES=root/'resources'
native_bundle._source=lambda:('test',entry,root/'supplier/postgresql-16.15.0-test.tar.gz')
native_bundle._cache_directory=lambda:root/'cache'
native_bundle._versions=lambda prefix:os._exit(73)
native_bundle.prepare()
"""
    process = subprocess.run([sys.executable, "-c", script, str(candidate.root)],
                             capture_output=True, timeout=30)
    assert process.returncode == 73
    assert not list(candidate.root.rglob(".complete"))
    abandoned = list((candidate.root / "cache").glob(".staging-*"))
    assert len(abandoned) == 1
    retained = {path.relative_to(abandoned[0]): path.read_bytes()
                for path in abandoned[0].rglob("*") if path.is_file()}
    prefix = native_bundle.prepare()
    assert prefix.is_dir()
    assert (prefix.parent / ".complete").is_file()
    assert {path.relative_to(abandoned[0]): path.read_bytes()
            for path in abandoned[0].rglob("*") if path.is_file()} == retained
    assert candidate.archive.read_bytes() == candidate.source


def test_tool_preflight_rejects_old_server_and_redacts_its_output(candidate, monkeypatch):
    monkeypatch.setattr(native_bundle.subprocess, "run", lambda *args, **kw:
                        subprocess.CompletedProcess([], 0, stdout=b"postgres (PostgreSQL) 16.2 private-path"))
    with pytest.raises(native_bundle.NativeBundleError) as error:
        CHECK_VERSIONS(candidate.root)
    assert error.value.code == "embedded_database_dependencies_missing"
    assert "private-path" not in str(error.value)


def test_parallel_processes_share_one_complete_cache(candidate):
    script = """
import json,sys
from pathlib import Path
from membrain import native_bundle
root=Path(sys.argv[1])
entry=json.loads((root/'resources/index.json').read_text())['platforms']['test']
native_bundle.RESOURCES=root/'resources'
native_bundle._source=lambda:('test',entry,root/'supplier/postgresql-16.15.0-test.tar.gz')
native_bundle._cache_directory=lambda:root/'cache'
native_bundle._versions=lambda prefix:None
print('ready',flush=True)
sys.stdin.readline()
print(native_bundle.prepare(),flush=True)
"""
    processes = [subprocess.Popen([sys.executable, "-c", script, str(candidate.root)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True) for _ in range(4)]
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda process: process.communicate("go\n", timeout=30), processes))
        assert all(process.returncode == 0 for process in processes), results
        assert len({stdout.strip() for stdout, _ in results}) == 1
        assert all(stdout.startswith("ready\n") for stdout, _ in results)
        assert len(list((candidate.root / "cache").glob("*/.complete"))) == 1
        assert not list((candidate.root / "cache").glob(".staging-*"))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
