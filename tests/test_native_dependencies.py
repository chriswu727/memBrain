import gzip
import hashlib
import io
import json
import os
import stat
import tarfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from membrain import native_bundle, native_dependencies

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Linux dependency cache uses POSIX ownership and loader rules")


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    resources, prefix = tmp_path / "resources", tmp_path / "old"
    resources.mkdir()
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin/postgres").write_bytes(b"old engine")
    (prefix / "bin/postgres").chmod(0o644)
    files = {"bin/postgres": b"old engine"}
    additions = {name: b"reviewed XML" if name == native_dependencies.XML_LIBRARY else b"license"
                 for name in native_dependencies.XML_ADDITIONS}

    def manifest(name, values):
        rows = [{"path": key, "sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value), "mode": 0o644}
                for key, value in values.items()]
        data = gzip.compress(json.dumps({"postgres": "16.15", "vector": "0.8.6", "files": rows}).encode())
        (resources / name).write_bytes(data)
        return {"manifest": name, "manifest_sha256": hashlib.sha256(data).hexdigest()}

    old = manifest("old.json.gz", files)
    entry = manifest("new.json.gz", files | additions)
    overlay = io.BytesIO()
    with tarfile.open(fileobj=overlay, mode="w:gz") as archive:
        for name, content in additions.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    (resources / "overlay.tar.gz").write_bytes(overlay.getvalue())
    entry.update(previous=old, overlay="overlay.tar.gz", overlay_sha256=hashlib.sha256(overlay.getvalue()).hexdigest())

    def save():
        (resources / "index.json").write_text(json.dumps({"contract_version": 1, "postgres": "16.15", "vector": "0.8.6",
                                                         "platforms": {"linux-x86_64": entry}}))

    save()
    monkeypatch.setattr(native_bundle, "RESOURCES", resources)
    monkeypatch.setattr(native_bundle, "platform_key", lambda: "linux-x86_64")
    monkeypatch.setattr(native_bundle, "_cache_directory", lambda: tmp_path / "cache")
    return SimpleNamespace(prefix=prefix, resources=resources, old=old, entry=entry, files=files,
                           additions=additions, manifest=manifest, save=save, root=tmp_path)


def test_old_binding_uses_only_verified_dependency_without_supplier_or_engine_changes(candidate, monkeypatch):
    monkeypatch.setattr(native_bundle, "prepare", lambda: pytest.fail("No supplier selection"))
    monkeypatch.setenv("LD_LIBRARY_PATH", "/untrusted")
    monkeypatch.setenv("LD_PRELOAD", "/untrusted/code")
    before = {p: (p.read_bytes(), p.stat().st_ino) for p in candidate.prefix.rglob("*") if p.is_file()}
    assert native_dependencies.target_manifest(candidate.prefix) == candidate.old["manifest_sha256"]
    directory = native_dependencies.xml_directory(candidate.prefix)
    assert (directory / "libxml2.so.2").read_bytes() == b"reviewed XML"
    assert list(directory.iterdir()) == [directory / "libxml2.so.2"]
    env = native_bundle.environment(candidate.prefix)
    assert env["LD_LIBRARY_PATH"] == str(directory) and "LD_PRELOAD" not in env
    assert native_dependencies.xml_directory(candidate.prefix) == directory
    assert before == {p: (p.read_bytes(), p.stat().st_ino) for p in candidate.prefix.rglob("*") if p.is_file()}


@pytest.mark.parametrize("change", ["changed", "removed", "extra", "not_linux"])
def test_predecessor_acceptance_requires_exact_reviewed_addition(candidate, monkeypatch, change):
    files = candidate.files | candidate.additions
    if change == "changed":
        files["bin/postgres"] = b"changed"
    elif change == "removed":
        del files["bin/postgres"]
    elif change == "extra":
        files["lib/arbitrary.so"] = b"unreviewed"
    else:
        monkeypatch.setattr(native_bundle, "platform_key", lambda: "macos-arm64")
        with pytest.raises(native_bundle.NativeBundleError):
            native_dependencies._previous(candidate.entry, native_bundle._manifest(candidate.entry))
        return
    candidate.entry.update(candidate.manifest("new.json.gz", files))
    candidate.save()
    with pytest.raises(native_bundle.NativeBundleError):
        native_dependencies.target_manifest(candidate.prefix)
    assert not (candidate.root / "cache").exists()


def test_unknown_or_modified_engine_never_receives_loader_override(candidate):
    (candidate.prefix / "bin/postgres").write_bytes(b"tampered")
    assert native_dependencies.xml_directory(candidate.prefix) is None
    assert "LD_LIBRARY_PATH" not in native_bundle.environment(candidate.prefix)
    with pytest.raises(native_bundle.NativeBundleError):
        native_dependencies.target_manifest(candidate.prefix)


@pytest.mark.parametrize("damage", ["content", "extra", "link", "mode"])
def test_dependency_corruption_is_preserved_and_repaired(candidate, damage):
    original = native_dependencies.xml_directory(candidate.prefix)
    library = original / "libxml2.so.2"
    if damage == "content":
        library.write_bytes(b"tampered")
    elif damage == "extra":
        (original / "libssl.so.3").write_bytes(b"unexpected override")
    elif damage == "link":
        os.link(library, original.parent / "linked-library")
    else:
        library.chmod(0o666)
    repaired = native_dependencies.xml_directory(candidate.prefix)
    assert original.exists() and repaired != original
    assert (repaired / "libxml2.so.2").read_bytes() == b"reviewed XML"
    assert stat.S_IMODE((repaired / "libxml2.so.2").stat().st_mode) == 0o644


def test_dependency_creation_serializes_concurrent_startup(candidate):
    with ThreadPoolExecutor(max_workers=4) as workers:
        paths = list(workers.map(lambda _: native_dependencies.xml_directory(candidate.prefix), range(8)))
    assert len(set(paths)) == 1
    assert not list(paths[0].parent.glob(".dependency-*"))


def test_shared_dependency_is_public_read_only_and_separate_from_private_cache(candidate, monkeypatch):
    private = native_dependencies.xml_directory(candidate.prefix)
    monkeypatch.setattr(native_dependencies, "_root", lambda shared: candidate.root / "shared")
    shared = native_dependencies.xml_directory(candidate.prefix, shared=True)
    assert shared != private
    assert stat.S_IMODE(shared.stat().st_mode) == 0o755
    assert stat.S_IMODE((shared / "libxml2.so.2").stat().st_mode) == 0o644


def test_low_space_never_publishes_dependency(candidate, monkeypatch):
    monkeypatch.setattr(native_dependencies.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    with pytest.raises(native_bundle.NativeBundleError) as failure:
        native_dependencies.xml_directory(candidate.prefix)
    assert failure.value.code == "embedded_database_space_low"
    assert not list((candidate.root / "cache").rglob("libxml2.so.2"))


def test_corrupt_overlay_rejects_before_dependency_publication(candidate):
    (candidate.resources / "overlay.tar.gz").write_bytes(b"corrupt")
    with pytest.raises(native_bundle.NativeBundleError):
        native_dependencies.xml_directory(candidate.prefix)
    assert not list((candidate.root / "cache").rglob("libxml2.so.2"))


def test_interrupted_publication_retries_without_modifying_bound_engine(candidate, monkeypatch):
    original = native_dependencies.os.replace

    def fail(*args):
        raise OSError("interrupted before promotion")

    monkeypatch.setattr(native_dependencies.os, "replace", fail)
    with pytest.raises(native_bundle.NativeBundleError):
        native_dependencies.xml_directory(candidate.prefix)
    assert (candidate.prefix / "bin/postgres").read_bytes() == b"old engine"
    assert not list((candidate.root / "cache").rglob("libxml2.so.2"))
    monkeypatch.setattr(native_dependencies.os, "replace", original)
    assert native_dependencies.xml_directory(candidate.prefix).is_dir()


def test_predecessor_checksum_tampering_is_rejected(candidate):
    (candidate.resources / candidate.old["manifest"]).write_bytes(b"tampered")
    with pytest.raises(native_bundle.NativeBundleError):
        native_dependencies.target_manifest(candidate.prefix)
    with pytest.raises(native_bundle.NativeBundleError):
        native_dependencies.xml_directory(candidate.prefix)
