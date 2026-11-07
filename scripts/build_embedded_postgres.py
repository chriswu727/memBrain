"""Build a host macOS engine wheel for qualification, without publishing it."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

POSTGRES = "16.15"
PGVECTOR = "0.6.2"
SOURCES = (
    (f"https://ftp.postgresql.org/pub/source/v{POSTGRES}/postgresql-{POSTGRES}.tar.bz2",
     "c1575341fa7bd40f5274ea465b34390f4dc64cdd0770af327005caaeb9f6b7ed"),
    (f"https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v{PGVECTOR}",
     "a11cc249a9f3f3d7b13069a1696f2915ac28991a72d7ba4e2bcfdceddbaeae49"),
)
MACHO = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
         b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def target_version():
    major, minor = map(int, platform.mac_ver()[0].split(".")[:2])
    return major, 0 if major >= 11 else minor


def run(command, *, cwd=None, capture=False):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PG", "MEMORY_", "MEMBRAIN_"))
                   and key not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL"}}
    environment["MACOSX_DEPLOYMENT_TARGET"] = ".".join(map(str, target_version()))
    return subprocess.run(list(map(str, command)), cwd=cwd, env=environment, check=True,
                          text=True, stdout=subprocess.PIPE if capture else None,
                          timeout=1800).stdout


def extract(url, expected, archive, directory):
    with urllib.request.urlopen(url, timeout=60) as response, archive.open("xb") as stream:
        shutil.copyfileobj(response, stream)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"Source checksum mismatch: {archive.name}")
    with tarfile.open(archive) as source:
        source.extractall(directory, filter="data")


def relocate(prefix):
    for path in sorted(prefix.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in MACHO:
                continue
        if run(["lipo", "-archs", path], capture=True).strip() != platform.machine():
            raise ValueError(f"Unexpected architecture in {path.name}")
        load_commands = run(["otool", "-l", path], capture=True).splitlines()
        minimum = [line.split()[1] for line in load_commands if line.strip().startswith("minos ")]
        if not minimum or any(tuple(map(int, version.split(".")[:2])) > target_version()
                              for version in minimum):
            raise ValueError(f"Deployment target exceeds the wheel tag in {path.name}")
        identities = run(["otool", "-D", path], capture=True).splitlines()[1:]
        if identities:
            run(["install_name_tool", "-id", "@rpath/" + path.name, path])
        for line in run(["otool", "-L", path], capture=True).splitlines()[1:]:
            dependency = line.rsplit(" (compatibility version", 1)[0].strip()
            if dependency.startswith(str(prefix) + "/"):
                relative = os.path.relpath(dependency, path.parent)
                run(["install_name_tool", "-change", dependency, "@loader_path/" + relative, path])
            elif not dependency.startswith(("@", "/usr/lib/", "/System/Library/")):
                raise ValueError(f"Unbundled native dependency in {path.name}: {dependency}")
        # install_name_tool invalidates the compiler's ad-hoc signature on Apple Silicon.
        run(["codesign", "--force", "--sign", "-", path])
        run(["codesign", "--verify", path])


def write_wheel(prefix, output, source, vector):
    major, minor = target_version()
    machine = platform.machine()
    if machine not in {"arm64", "x86_64"}:
        raise ValueError("Unsupported macOS build architecture")
    tag = f"py3-none-macosx_{major}_{minor}_{machine}"
    version = POSTGRES + ".0"
    info = f"membrain_postgres-{version}.dist-info"
    files = {"membrain_postgres/__init__.py": (f'__version__ = "{version}"\n'.encode(), 0o644)}
    manifest = {"postgres": POSTGRES, "pgvector": PGVECTOR, "wheel_tag": tag,
                "scope": "host macOS qualification artifact; no other platform is verified",
                "sources": [{"url": url, "sha256": digest} for url, digest in SOURCES], "files": []}
    for path in sorted(prefix.rglob("*")):
        if path.is_file():
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(prefix):
                raise ValueError("Bundle contains a link outside its prefix")
            name = path.relative_to(prefix).as_posix()
            data, mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
            files["membrain_postgres/pginstall/" + name] = (data, mode)
            manifest["files"].append({"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                                      "bytes": len(data), "mode": mode})
    files["membrain_postgres/manifest.json"] = ((json.dumps(manifest, indent=2) + "\n").encode(), 0o644)
    for name, path in (("POSTGRESQL", source / "COPYRIGHT"), ("PGVECTOR", vector / "LICENSE")):
        files[f"{info}/licenses/{name}"] = (path.read_bytes(), 0o644)
    metadata = (f"Metadata-Version: 2.4\nName: membrain-postgres\nVersion: {version}\n"
                "Summary: Native PostgreSQL and pgvector binaries for memBrain\n"
                "Requires-Python: >=3.12\nLicense-Expression: PostgreSQL\n"
                "License-File: licenses/POSTGRESQL\nLicense-File: licenses/PGVECTOR\n")
    files[f"{info}/METADATA"] = (metadata.encode(), 0o644)
    files[f"{info}/WHEEL"] = (("Wheel-Version: 1.0\nGenerator: membrain-engine-builder\n"
                               f"Root-Is-Purelib: false\nTag: {tag}\n").encode(), 0o644)
    rows = io.StringIO(newline="")
    writer = csv.writer(rows, lineterminator="\n")
    for name, (data, _) in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, len(data)))
    writer.writerow((f"{info}/RECORD", "", ""))
    files[f"{info}/RECORD"] = (rows.getvalue().encode(), 0o644)
    output.mkdir(parents=True, exist_ok=True)
    wheel = output / f"membrain_postgres-{version}-{tag}.whl"
    with zipfile.ZipFile(wheel, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (data, mode) in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | mode) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    return wheel


def build(work, output, jobs):
    if platform.system() != "Darwin":
        raise ValueError("This qualification builder currently supports macOS only")
    if not 1 <= jobs <= 8:
        raise ValueError("Build jobs must be between 1 and 8")
    if any(character.isspace() for character in str(work)):
        raise ValueError("The PostgreSQL build directory must not contain whitespace")
    work.mkdir(parents=True, exist_ok=False)
    prefix = work / "pginstall"
    extract(*SOURCES[0], work / "postgres.tar.bz2", work)
    extract(*SOURCES[1], work / "vector.tar.gz", work)
    source, vector = work / f"postgresql-{POSTGRES}", work / f"pgvector-{PGVECTOR}"
    run([source / "configure", f"--prefix={prefix}", "--without-readline", "--without-icu"], cwd=source)
    run(["make", f"-j{jobs}"], cwd=source)
    run(["make", "install"], cwd=source)
    run(["make", f"-j{jobs}", f"PG_CONFIG={prefix / 'bin/pg_config'}"], cwd=vector)
    run(["make", "install", f"PG_CONFIG={prefix / 'bin/pg_config'}"], cwd=vector)
    relocate(prefix)
    return write_wheel(prefix, output, source, vector)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-directory", type=Path, required=True, help="New private build directory")
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    wheel = build(args.work_directory.resolve(), args.output_directory.resolve(), args.jobs)
    with wheel.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    print(json.dumps({"wheel": str(wheel), "sha256": digest, "bytes": wheel.stat().st_size,
                      "published": False, "installed_runtime_changed": False}))


if __name__ == "__main__":
    main()
