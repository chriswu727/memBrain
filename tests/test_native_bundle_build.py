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


@pytest.mark.parametrize("dynamic", [
    "(SONAME) Library soname: [libxml2.so.16]\n(NEEDED) Shared library: [libc.so.6]",
    "(SONAME) Library soname: [libxml2.so.2]\n(NEEDED) Shared library: [libicuuc.so.70]",
    "(SONAME) Library soname: [libxml2.so.2]\n(NEEDED) Shared library: [libc.so.6]\n(RUNPATH) [/build/private]",
    "(SONAME) Library soname: [libxml2.so.2]",
])
def test_xml_library_rejects_wrong_abi_or_unbundled_dependencies(tmp_path, monkeypatch, dynamic):
    monkeypatch.setattr(builder, "run", lambda *a, **kw: dynamic)
    with pytest.raises(ValueError, match="unexpected ABI or dependency"):
        builder.inspect_xml_library(tmp_path / "libxml2.so.2")


def test_xml_library_accepts_old_soname_without_icu(tmp_path, monkeypatch):
    dynamic = "(SONAME) Library soname: [libxml2.so.2]\n(NEEDED) Shared library: [libc.so.6]\n(NEEDED) Shared library: [libz.so.1]"
    monkeypatch.setattr(builder, "run", lambda *a, **kw: dynamic)
    assert builder.inspect_xml_library(tmp_path / "libxml2.so.2")["needed"] == ["libc.so.6", "libz.so.1"]


@pytest.mark.parametrize("machine", ["x86_64", "aarch64"])
def test_xml_arm_dynamic_loader_is_allowed_only_on_arm(tmp_path, monkeypatch, machine):
    dynamic = "(SONAME) Library soname: [libxml2.so.2]\n(NEEDED) Shared library: [libc.so.6]\n(NEEDED) Shared library: [ld-linux-aarch64.so.1]"
    monkeypatch.setattr(builder.platform, "machine", lambda: machine)
    monkeypatch.setattr(builder, "run", lambda *a, **kw: dynamic)
    if machine == "aarch64":
        assert builder.inspect_xml_library(tmp_path / "libxml2.so.2")["needed"] == ["ld-linux-aarch64.so.1", "libc.so.6"]
    else:
        with pytest.raises(ValueError, match="unexpected ABI or dependency"):
            builder.inspect_xml_library(tmp_path / "libxml2.so.2")


def test_build_commands_do_not_inherit_loader_overrides(monkeypatch):
    monkeypatch.setenv("LD_PRELOAD", "/untrusted/lib.so")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/untrusted")
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/untrusted")
    calls = []

    def execute(command, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="done")

    import subprocess
    monkeypatch.setattr(builder.subprocess, "run", execute)
    assert builder.run(["test-tool"], capture=True) == "done"
    assert not any(key.startswith(("LD_", "DYLD_")) for key in calls[0]["env"])


def test_xml_overlay_keeps_library_and_license_but_not_build_tools():
    spec = importlib.util.spec_from_file_location(
        "package_native_resources", Path(__file__).parents[1] / "scripts/package_native_resources.py")
    packager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packager)
    assert packager.overlay_path("lib/libxml2.so.2")
    assert packager.overlay_path("share/licenses/libxml2/Copyright")
    assert packager.overlay_path("share/licenses/libxml2/source.json")
    assert not packager.overlay_path("lib/libxml2.so.16")
    assert not packager.overlay_path("bin/xmllint")


def test_xml_test_corpus_restores_only_data_and_materializes_internal_links(tmp_path):
    archive, source = tmp_path / "upstream.tar", tmp_path / "source"
    with tarfile.open(archive, "w") as saved:
        for name in ("test/fixture", "result/fixture", "parser.c"):
            member = tarfile.TarInfo("libxml2-2.9.13/" + name)
            member.size = 7
            saved.addfile(member, io.BytesIO(b"fixture"))
        link = tarfile.TarInfo("libxml2-2.9.13/test/linked")
        link.type, link.linkname = tarfile.LNKTYPE, "libxml2-2.9.13/test/fixture"
        saved.addfile(link)
    builder.restore_xml_tests(archive, source)
    assert (source / "test/linked").read_bytes() == b"fixture"
    assert (source / "test/linked").stat().st_nlink == 1
    assert (source / "result/fixture").read_bytes() == b"fixture"
    assert not (source / "parser.c").exists()


@pytest.mark.parametrize("name,kind,target", [
    ("test/../../escape", tarfile.REGTYPE, ""),
    ("test/linked", tarfile.SYMTYPE, "/outside"),
    ("test/linked", tarfile.LNKTYPE, "libxml2-2.9.13/parser.c"),
])
def test_xml_test_corpus_rejects_traversal_and_external_links(tmp_path, name, kind, target):
    archive = tmp_path / "upstream.tar"
    with tarfile.open(archive, "w") as saved:
        member = tarfile.TarInfo("libxml2-2.9.13/" + name)
        member.type, member.linkname = kind, target
        saved.addfile(member)
    with pytest.raises(ValueError, match="Unexpected upstream XML test"):
        builder.restore_xml_tests(archive, tmp_path / "source")
