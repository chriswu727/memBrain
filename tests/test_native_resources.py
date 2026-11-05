import gzip
import hashlib
import io
import json
import tarfile

from membrain import native_bundle


def test_all_packaged_native_overlays_match_their_reviewed_manifests():
    index = json.loads((native_bundle.RESOURCES / "index.json").read_text())
    assert set(index["platforms"]) == {"macos-arm64", "macos-x86_64", "linux-x86_64", "linux-aarch64", "windows-x86_64"}
    for key, entry in index["platforms"].items():
        records = native_bundle._manifest(entry)
        assert len(records) == entry["native_files"]
        suffix = ".exe" if key.startswith("windows") else ""
        assert all("bin/" + name + suffix in records for name in native_bundle.TOOLS)
        data = native_bundle._resource(entry["overlay"], entry["overlay_sha256"])
        names = set()
        with tarfile.open(fileobj=io.BytesIO(data)) as saved:
            for member in saved:
                assert member.isfile()
                assert native_bundle._path(member.name).as_posix() == member.name
                assert member.name in records
                with saved.extractfile(member) as stream:
                    assert hashlib.file_digest(stream, "sha256").hexdigest() == records[member.name]["sha256"]
                assert member.name not in names
                names.add(member.name)
        assert len(names) == entry["overlay_files"]
        assert "share/extension/vector.control" in names
        assert "share/extension/vector--0.6.2--0.7.0.sql" in names
        assert "share/extension/vector--0.8.6.sql" in names
        assert "share/licenses/pgvector/LICENSE" in names
        assert "share/licenses/postgresql/LICENSE" in names
        assert not any("bin/" + name + suffix in names for name in native_bundle.TOOLS)
        if key.startswith(("macos", "windows")):
            assert "share/licenses/openssl/LICENSE.txt" in names
            assert entry["openssl"].startswith("OpenSSL 3.5.9 ")
        with gzip.open(native_bundle.RESOURCES / entry["manifest"], "rt") as stream:
            assert json.load(stream)["vector"] == "0.8.6"
