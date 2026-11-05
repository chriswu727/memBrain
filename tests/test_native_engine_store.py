import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from membrain import embedded_database, native_engine_store


@pytest.fixture
def engine(tmp_path):
    source = tmp_path / "installed/pgserver/pginstall"
    (source / "bin").mkdir(parents=True)
    suffix = ".exe" if os.name == "nt" else ""
    for tool in native_engine_store._TOOLS:
        file = source / "bin" / (tool + suffix)
        file.write_bytes(("original-" + tool).encode())
        file.chmod(0o755)
    (source / "lib").mkdir()
    (source / "lib/vector").write_bytes(b"original vector")
    (source / "share/empty").mkdir(parents=True)
    vendors = source.parent.parent / "pgserver.libs"
    vendors.mkdir()
    (vendors / "dependency").write_bytes(b"relative dependency")
    return SimpleNamespace(source=source, store=tmp_path / "preserved", vendors=vendors)


def test_preservation_survives_source_removal_with_relative_libraries_and_no_hardlinks(engine):
    saved = native_engine_store.preserve(engine.source, engine.store)
    assert saved.prefix == saved.directory / "pgserver/pginstall"
    assert saved.files == 8 and saved.bytes > 0
    assert (saved.directory / "pgserver.libs/dependency").read_bytes() == b"relative dependency"
    assert (saved.prefix / "share/empty").is_dir()
    original = engine.source / "lib/vector"
    copied = saved.prefix / "lib/vector"
    assert copied.stat().st_nlink == 1
    assert (copied.stat().st_dev, copied.stat().st_ino) != (original.stat().st_dev, original.stat().st_ino)
    original.write_bytes(b"new source version")
    original.unlink()
    assert native_engine_store.verify(saved.directory, saved.commitment) == saved
    assert copied.read_bytes() == b"original vector"
    if os.name != "nt":
        assert engine.store.stat().st_mode & 0o777 == 0o700
        assert saved.directory.stat().st_mode & 0o777 == 0o700
        assert (saved.directory / ".complete").stat().st_mode & 0o777 == 0o600


def test_verified_reuse_does_not_rewrite_files_and_updated_source_has_separate_generation(engine):
    first = native_engine_store.preserve(engine.source, engine.store)
    before = {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in first.directory.rglob("*")}
    assert native_engine_store.preserve(engine.source, engine.store) == first
    assert before == {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in first.directory.rglob("*")}
    (engine.source / "lib/vector").write_bytes(b"updated vector")
    second = native_engine_store.preserve(engine.source, engine.store)
    assert first.directory != second.directory and first.commitment != second.commitment
    assert native_engine_store.verify(first.directory, first.commitment) == first
    assert (second.prefix / "lib/vector").read_bytes() == b"updated vector"


@pytest.mark.parametrize("damage", ["bytes", "missing", "extra", "marker", "hardlink"] + (
    ["symlink", "link_directory", "mode"] if os.name != "nt" else []))
def test_damaged_generations_are_preserved_and_repaired_without_moving_live_paths(engine, damage, monkeypatch):
    first = native_engine_store.preserve(engine.source, engine.store)
    vector = first.prefix / "lib/vector"
    if damage == "bytes":
        vector.write_bytes(b"corrupt")
    elif damage == "missing":
        vector.unlink()
    elif damage == "extra":
        (first.directory / "extra").write_bytes(b"unrecorded")
    elif damage == "marker":
        (first.directory / ".complete").write_bytes(b"f" * 64)
    elif damage == "mode":
        vector.chmod(0o666)
    elif damage == "link_directory":
        (first.prefix / "share/empty").rmdir()
        (first.prefix / "share/empty").symlink_to(first.prefix / "bin", target_is_directory=True)
    else:
        vector.unlink()
        if damage == "hardlink":
            os.link(engine.source / "lib/vector", vector)
        else:
            vector.symlink_to(engine.source / "lib/vector")
    with pytest.raises(native_engine_store.NativeEngineStoreError):
        native_engine_store.verify(first.directory, first.commitment)
    replace = native_engine_store.os.replace

    def no_move(source, destination):
        assert Path(source) != first.directory
        return replace(source, destination)

    monkeypatch.setattr(native_engine_store.os, "replace", no_move)
    fixed = native_engine_store.preserve(engine.source, engine.store)
    assert fixed.directory != first.directory and first.directory.is_dir()
    assert fixed.commitment == first.commitment
    assert native_engine_store.preserve(engine.source, engine.store) == fixed


def test_vendor_library_change_affects_identity(engine):
    first = native_engine_store.preserve(engine.source, engine.store)
    (engine.vendors / "dependency").write_bytes(b"new dependency")
    second = native_engine_store.preserve(engine.source, engine.store)
    assert first.commitment != second.commitment
    assert native_engine_store.verify(first.directory, first.commitment) == first


@pytest.mark.parametrize("library", [".dylibs", ".libs"])
def test_hidden_package_libraries_survive_nested_engine_preservation(engine, library):
    directory = engine.source.parent / library
    directory.mkdir()
    (directory / "libpq").write_bytes(b"out-of-prefix native dependency")
    saved = native_engine_store.preserve(engine.source, engine.store)
    repeated = native_engine_store.preserve(saved.prefix, engine.store.parent / "second-store")
    assert saved.commitment == repeated.commitment
    assert (repeated.directory / "pgserver" / library / "libpq").read_bytes() == b"out-of-prefix native dependency"
    with pytest.raises(native_engine_store.NativeEngineStoreError) as error:
        native_engine_store.preserve(engine.source, directory / "nested-store")
    assert error.value.code == "embedded_database_engine_invalid"
    assert not (directory / "nested-store").exists()


def test_source_changes_during_copy_never_publish_and_partial_evidence_remains(engine, monkeypatch):
    copy = native_engine_store._copy_file

    def changed(source, target, row):
        copy(source, target, row)
        if source.name == "vector":
            source.write_bytes(b"changed after copy")

    monkeypatch.setattr(native_engine_store, "_copy_file", changed)
    with pytest.raises(native_engine_store.NativeEngineStoreError) as error:
        native_engine_store.preserve(engine.source, engine.store)
    assert error.value.code == "embedded_database_engine_changed"
    assert not list(engine.store.glob("postgres-*"))
    assert list(engine.store.glob(".engine-staging-*"))


@pytest.mark.parametrize("point", ["space", "publish"])
def test_failed_copy_preserves_existing_generation_and_source(engine, monkeypatch, point):
    first = native_engine_store.preserve(engine.source, engine.store)
    (engine.source / "lib/vector").write_bytes(b"new version")
    if point == "space":
        monkeypatch.setattr(native_engine_store.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
    else:
        monkeypatch.setattr(native_engine_store.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("private path")))
    with pytest.raises(native_engine_store.NativeEngineStoreError) as error:
        native_engine_store.preserve(engine.source, engine.store)
    assert error.value.code == "embedded_database_engine_" + ("space_low" if point == "space" else "failed")
    assert "private path" not in str(error.value)
    assert native_engine_store.verify(first.directory, first.commitment) == first
    assert (engine.source / "lib/vector").read_bytes() == b"new version"


def test_threads_share_one_complete_generation(engine):
    with ThreadPoolExecutor(max_workers=4) as pool:
        saved = list(pool.map(lambda _: native_engine_store.preserve(engine.source, engine.store), range(4)))
    assert len({result.directory for result in saved}) == 1
    assert len(list(engine.store.glob("postgres-*"))) == 1


def test_processes_share_one_complete_generation(engine):
    script = ("import sys;from pathlib import Path;from membrain.native_engine_store import preserve;"
              "print(preserve(Path(sys.argv[1]),Path(sys.argv[2])).commitment)")
    children = [subprocess.Popen([sys.executable, "-c", script, str(engine.source), str(engine.store)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
    results = [child.communicate(timeout=30) for child in children]
    assert all(child.returncode == 0 for child in children), results
    assert len({out.strip() for out, _ in results}) == 1
    assert len(list(engine.store.glob("postgres-*"))) == 1


@pytest.mark.parametrize("destination", ["source", "vendor", "ancestor"])
def test_store_cannot_mutate_installed_engine_trees(engine, destination):
    store = {"source": engine.source / "store", "vendor": engine.vendors / "store",
             "ancestor": engine.source.parent}[destination]
    with pytest.raises(native_engine_store.NativeEngineStoreError) as error:
        native_engine_store.preserve(engine.source, store)
    assert error.value.code == "embedded_database_engine_invalid"
    if destination != "ancestor":
        assert not store.exists()


if os.name != "nt":
    def test_internal_file_links_are_relocatable_but_external_or_directory_links_fail(engine):
        (engine.source / "lib/vector-alias").symlink_to("vector")
        saved = native_engine_store.preserve(engine.source, engine.store)
        assert (saved.prefix / "lib/vector-alias").readlink() == Path("vector")
        assert native_engine_store.verify(saved.directory, saved.commitment) == saved
        (engine.source / "lib/outside").symlink_to(engine.vendors / "dependency")
        with pytest.raises(native_engine_store.NativeEngineStoreError):
            native_engine_store.preserve(engine.source, engine.store)

    def test_named_pipe_is_rejected_without_waiting(engine):
        os.mkfifo(engine.source / "lib/pipe")
        with pytest.raises(native_engine_store.NativeEngineStoreError):
            native_engine_store.preserve(engine.source, engine.store)

    def test_shared_engine_is_readable_to_service_account_and_rechecked_on_reuse(engine):
        path = embedded_database._shared_binaries(engine.source, engine.store)
        assert engine.store.stat().st_mode & 0o777 == 0o755
        assert path.stat().st_mode & 0o777 == 0o755
        (path / "pgserver/pginstall/lib/vector").write_bytes(b"damaged")
        repaired = embedded_database._shared_binaries(engine.source, engine.store)
        assert repaired != path and path.exists()
        assert (repaired / "pgserver/pginstall/lib/vector").read_bytes() == b"original vector"

    def test_unsafe_shared_store_is_not_reused(engine):
        engine.store.mkdir(mode=0o777)
        engine.store.chmod(0o777)
        with pytest.raises(embedded_database.EmbeddedDatabaseError) as error:
            embedded_database._shared_binaries(engine.source, engine.store)
        assert error.value.code == "embedded_database_engine_invalid"
