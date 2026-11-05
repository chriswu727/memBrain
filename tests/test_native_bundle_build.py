import hashlib
import importlib.util
import io
import os
import tarfile
import zipfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "native_bundle_build", Path(__file__).parents[1] / "scripts" / "build_native_bundle.py")
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


def wheel_with_member(tmp_path, member, content=b"payload"):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        entry = tarfile.TarInfo(member)
        entry.size = len(content)
        archive.addfile(entry, io.BytesIO(content))
    wheel = tmp_path / "supplier.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("postgresql_binaries/postgresql-16.15.0-test.tar.gz", data.getvalue())
        archive.writestr("postgresql_binaries/__init__.py", "raise AssertionError('must not execute')")
    return wheel


def test_supplier_extraction_does_not_execute_package_code(tmp_path):
    wheel = wheel_with_member(tmp_path, "postgresql-16.15.0-test/bin/postgres")
    prefix, checksum = builder.extract_wheel(wheel, tmp_path / "extracted")
    assert (prefix / "bin/postgres").read_bytes() == b"payload"
    assert len(checksum) == 64


@pytest.mark.parametrize("member", ["../../outside", "/outside", "postgresql-16.15.0-test/../../outside"])
def test_supplier_extraction_rejects_traversal(tmp_path, member):
    wheel = wheel_with_member(tmp_path, member)
    with pytest.raises((ValueError, tarfile.FilterError)):
        builder.extract_wheel(wheel, tmp_path / "extracted")
    assert not (tmp_path / "outside").exists()


def test_download_rejects_content_that_differs_from_pin(tmp_path, monkeypatch):
    monkeypatch.setattr(builder.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"different"))
    with pytest.raises(ValueError, match="Checksum mismatch"):
        builder.download("https://example.test/archive", hashlib.sha256(b"expected").hexdigest(),
                         tmp_path / "archive")


def test_bundle_inventory_rejects_external_links(tmp_path):
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    external = tmp_path / "external"
    external.write_bytes(b"private")
    (prefix / "link").symlink_to(external)
    with pytest.raises(ValueError, match="outside"):
        builder.inventory(prefix)


@pytest.mark.parametrize("license_name", ["COPYRIGHT", "server_license.txt"])
def test_bundle_includes_licenses_and_exact_file_hashes(tmp_path, license_name):
    prefix, source, output = tmp_path / "prefix", tmp_path / "source", tmp_path / "output"
    (prefix / "lib").mkdir(parents=True)
    (prefix / "share/extension").mkdir(parents=True)
    source.mkdir()
    (source / "LICENSE").write_text("vector license")
    (prefix / license_name).write_text("postgres license")
    (prefix / "lib/vector.so").write_bytes(b"compiled vector")
    (prefix / "share/extension/vector.control").write_text("control")
    metadata = {}
    builder.write_bundle(prefix, source, output, metadata)
    import json
    manifest = json.loads((output / "manifest.json").read_text())
    for row in manifest["files"]:
        assert row["sha256"] == builder.digest(prefix / row["path"])
    artifacts = json.loads((output / "artifacts.json").read_text())
    assert all(row["sha256"] == builder.digest(output / name) for name, row in artifacts.items())
    with zipfile.ZipFile(output / "vector-resources.zip") as archive:
        assert set(archive.namelist()) == {
            "lib/vector.so", "share/extension/vector.control", "PGVECTOR-LICENSE"}
    assert (output / "POSTGRESQL-COPYRIGHT").read_text() == "postgres license"


def test_portable_compile_overrides_host_native_flags(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(builder.platform, "system", lambda: "Linux")
    monkeypatch.setattr(builder, "run", lambda command, **kw: calls.append((command, kw)))
    builder.compile_vector(tmp_path / "source", tmp_path / "prefix")
    assert len(calls) == 2
    assert all("OPTFLAGS=" in command for command, _ in calls)
    if os.name != "nt":
        assert all("with_llvm=no" in command for command, _ in calls)


def test_builder_rejects_unknown_platform_before_creating_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(builder.platform, "system", lambda: "Unsupported")
    with pytest.raises(ValueError, match="Unsupported platform"):
        builder.build(tmp_path / "work", tmp_path / "output")
    assert not list(tmp_path.iterdir())
