"""Package reviewed native overlays without copying PostgreSQL server binaries."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def overlay_path(name):
    path = PurePosixPath(name)
    return (name.startswith(("share/extension/vector", "include/server/extension/vector/", "include/openssl/", "lib/ossl-modules/",
                             "share/licenses/openssl/", "share/licenses/libxml2/", "lib/libcrypto", "lib/libssl"))
            or name == "lib/libxml2.so.2"
            or path.name in {"vector.so", "vector.dylib", "vector.dll", "openssl", "openssl.exe",
                             "libcrypto-3-x64.dll", "libssl-3-x64.dll"})


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def package(artifacts, provenance, output):
    records = json.loads(provenance.read_text(encoding="utf-8"))
    if not records["completed"] or len(records["platforms"]) != 5:
        raise ValueError("All five candidate platforms must have completed qualification")
    output.mkdir(parents=True, exist_ok=False)
    index = {"contract_version": 1, "postgres": "16.15", "vector": "0.8.6", "platforms": {}}
    for entry in records["platforms"]:
        target = entry["target"]
        archive = artifacts / f"native-{target}-lts.zip"
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != entry["artifact_sha256"]:
                raise ValueError("Candidate artifact checksum mismatch")
        with zipfile.ZipFile(archive) as saved:
            manifest = json.loads(saved.read("native-artifacts/manifest.json"))
            qualification = json.loads(saved.read("native-artifacts/qualification.json"))
            if not qualification["completed"] or not qualification["port_closed"]:
                raise ValueError("Candidate qualification is incomplete")
            if (manifest["postgres"], manifest["vector"]) != (index["postgres"], index["vector"]):
                raise ValueError("Candidate versions do not match")
            selected = {row["path"]: row for row in manifest["files"] if overlay_path(row["path"])}
            files = {}
            with saved.open("native-artifacts/engine.tar.gz") as stream, tarfile.open(fileobj=stream, mode="r|gz") as source:
                for member in source:
                    name = member.name.removeprefix("pginstall/")
                    if name not in selected:
                        continue
                    if not member.isfile():
                        raise ValueError("Native overlay entries must be regular files")
                    data = source.extractfile(member).read()
                    if checksum(data) != selected[name]["sha256"]:
                        raise ValueError("Candidate native file differs from its manifest")
                    files[name] = (data, selected[name]["mode"])
            if set(files) != set(selected):
                raise ValueError("Candidate overlay entries are missing")
            for name, original in (("share/licenses/pgvector/LICENSE", "PGVECTOR-LICENSE"),
                                   ("share/licenses/postgresql/LICENSE", "POSTGRESQL-COPYRIGHT")):
                files[name] = (saved.read("native-artifacts/" + original), 0o644)
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as packed:
                for name, (data, mode) in sorted(files.items()):
                    member = tarfile.TarInfo(name)
                    member.size, member.mode, member.mtime = len(data), mode & 0o777, 0
                    packed.addfile(member, io.BytesIO(data))
            data = gzip.compress(buffer.getvalue(), mtime=0)
            overlay = target + ".tar.gz"
            (output / overlay).write_bytes(data)
            full = {row["path"]: row for row in manifest["files"]}
            for name, (content, mode) in files.items():
                full[name] = {"path": name, "bytes": len(content), "mode": mode,
                              "sha256": checksum(content)}
            payload = {"postgres": index["postgres"], "vector": index["vector"],
                       "files": [full[name] for name in sorted(full)]}
            data = gzip.compress((json.dumps(payload, sort_keys=True) + "\n").encode(), mtime=0)
            manifest_name = target + ".json.gz"
            (output / manifest_name).write_bytes(data)
            index["platforms"][target] = {
                "overlay": overlay, "overlay_sha256": checksum((output / overlay).read_bytes()),
                "manifest": manifest_name, "manifest_sha256": checksum(data),
                "supplier": manifest["supplier_wheel"], "openssl": manifest["openssl"]["version"].splitlines()[0],
                "candidate_artifact_sha256": entry["artifact_sha256"],
                "candidate_run": entry["workflow_run"], "candidate_job": entry["job"],
                "overlay_files": len(files), "native_files": len(full),
            }
    (output / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-directory", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = package(args.artifacts_directory, args.provenance, args.output_directory)
    print(json.dumps({"platforms": len(result["platforms"]), "published": False,
                      "resource_bytes": sum(path.stat().st_size for path in args.output_directory.iterdir())}))


if __name__ == "__main__":
    main()
