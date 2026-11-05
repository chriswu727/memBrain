"""Build an unpublished, checksummed PostgreSQL 16.15 / pgvector 0.8.6 candidate."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

POSTGRES = "16.15"
SUPPLIER_VERSION = "16.15.0"
VECTOR = "0.8.6"
VECTOR_URL = f"https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v{VECTOR}"
VECTOR_SHA256 = "10bf9938906e5d643bbc4a7eea104b6f57ba4898e5b76b20e60484ea1d5a7f8f"
OPENSSL = "3.5.9"
OPENSSL_URL = f"https://github.com/openssl/openssl/releases/download/openssl-{OPENSSL}/openssl-{OPENSSL}.tar.gz"
OPENSSL_SHA256 = "603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a"
XML_VERSION = "2.9.13+dfsg-1ubuntu0.14"
XML_SOURCE_URL = "https://archive.ubuntu.com/ubuntu/pool/main/libx/libxml2/"
XML_SOURCES = {
    "libxml2_2.9.13+dfsg.orig.tar.xz": "13cf2e55e603c34143486f4082cbf202859ac1eec5130b8d8e5e3c06a9902d8a",
    f"libxml2_{XML_VERSION}.debian.tar.xz": "25ff38d4356a491aa49c415cff6460453793694a72e4c9a894b94128e65b8040",
    f"libxml2_{XML_VERSION}.dsc": "0c43450d95fb5a935610d86e06aa52d56a58d3a7e6348fd4d993b7054e71cf53",
}
WHEELS = {
    ("Darwin", "arm64"): ("macosx_11_0_arm64", "c73c7eacd71da727085aa3a4ebfa60b862ce8eacb72102df691b620d7a66460b"),
    ("Darwin", "x86_64"): ("macosx_10_9_x86_64", "4a1ec8dc225f404c677a43e84472b84e83482c6e7e34c183c44529477dcc6d74"),
    ("Linux", "x86_64"): ("manylinux_2_17_x86_64", "93bad86ed48ba850a587ed9e3f066a271e7c7ffdaba524f9eeda4cac20efc951"),
    ("Linux", "aarch64"): ("manylinux_2_17_aarch64", "11d0ddeb1fdf9c5c8b059d658a3da0fd6fc0f420bff450d9204f3a4f3983007f"),
    ("Windows", "AMD64"): ("win_amd64", "5b4bc720edb424c132840849684cdc864bd828dff96097ee667337eb351623b0"),
}
TOOLS = ("postgres", "pg_ctl", "initdb", "pg_dump", "pg_restore", "psql", "pg_config")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, expected, path):
    with urllib.request.urlopen(url, timeout=60) as response, path.open("xb") as stream:
        shutil.copyfileobj(response, stream)
    if digest(path) != expected:
        raise ValueError(f"Checksum mismatch: {path.name}")


def run(command, *, cwd=None, capture=False, environment=None):
    cleaned = {key: value for key, value in os.environ.items()
               if not key.startswith(("PG", "MEMORY_", "MEMBRAIN_", "LD_", "DYLD_"))
               and key not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "PYTHONPATH", "PYTHONHOME"}}
    cleaned.update(environment or {})
    return subprocess.run(list(map(str, command)), cwd=cwd, env=cleaned, check=True,
                          text=True, stdout=subprocess.PIPE if capture else None,
                          timeout=1200).stdout


def extract_wheel(wheel, work):
    with zipfile.ZipFile(wheel) as archive:
        members = [name for name in archive.namelist()
                   if name.startswith("postgresql_binaries/postgresql-") and name.endswith(".tar.gz")]
        if len(members) != 1:
            raise ValueError("Expected exactly one PostgreSQL archive")
        data = archive.read(members[0])
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        roots = {Path(member.name).parts[0] for member in archive}
        if len(roots) != 1 or not next(iter(roots)).startswith(f"postgresql-{SUPPLIER_VERSION}-"):
            raise ValueError("Unexpected PostgreSQL archive layout")
        archive.extractall(work, filter="data")
    return work / next(iter(roots)), hashlib.sha256(data).hexdigest()


def tool(prefix, name):
    return prefix / "bin" / (name + (".exe" if os.name == "nt" else ""))


def contained_path(prefix, value):
    path = Path(value.strip()).resolve(strict=True)
    if not path.is_relative_to(prefix.resolve()):
        raise ValueError("PostgreSQL directory escapes its extracted prefix")
    return path


def compile_vector(source, prefix):
    if os.name == "nt":
        run(["nmake", "/NOLOGO", "/F", "Makefile.win", f"PGROOT={prefix}", "OPTFLAGS="], cwd=source)
        run(["nmake", "/NOLOGO", "/F", "Makefile.win", f"PGROOT={prefix}", "OPTFLAGS=", "install"], cwd=source)
        return "Windows x64 baseline (no /arch override)"
    options = [f"PG_CONFIG={tool(prefix, 'pg_config')}", "OPTFLAGS=", "with_llvm=no"]
    environment = {}
    if platform.system() == "Darwin":
        sdk = run(["xcrun", "--show-sdk-path"], capture=True).strip()
        minimum = "11.0" if platform.machine() == "arm64" else "10.13"
        options += [f"PG_SYSROOT={sdk}", f"CPPFLAGS=-isysroot {sdk}",
                    f"LDFLAGS=-isysroot {sdk}", f"MACOSX_DEPLOYMENT_TARGET={minimum}"]
        environment["MACOSX_DEPLOYMENT_TARGET"] = minimum
    run(["make", "-j2", *options], cwd=source, environment=environment)
    run(["make", "install", *options], cwd=source, environment=environment)
    return "portable OPTFLAGS=; host compiler and libc baseline recorded separately"


def vector_library(prefix):
    directory = contained_path(prefix, run([tool(prefix, "pg_config"), "--pkglibdir"], capture=True))
    suffix = {"Darwin": "dylib", "Linux": "so", "Windows": "dll"}[platform.system()]
    return directory / f"vector.{suffix}"


def update_openssl(prefix, work):
    system, machine = platform.system(), platform.machine()
    if system == "Linux":
        return {"source": "operating system", "version": run(["openssl", "version", "-a"], capture=True),
                "server_dependencies": run(["ldd", tool(prefix, "postgres")], capture=True),
                "client_dependencies": run(["ldd", tool(prefix, "psql")], capture=True),
                "scope": "tested host libraries only; distribution compatibility remains a separate gate"}
    archive = work / "openssl.tar.gz"
    download(OPENSSL_URL, OPENSSL_SHA256, archive)
    with tarfile.open(archive) as saved:
        saved.extractall(work, filter="data")
    source, installed = work / f"openssl-{OPENSSL}", work / "openssl-installed"
    target = {("Darwin", "arm64"): "darwin64-arm64-cc", ("Darwin", "x86_64"): "darwin64-x86_64-cc",
              ("Windows", "AMD64"): "VC-WIN64A"}[(system, machine)]
    environment = {}
    if system == "Darwin":
        environment["MACOSX_DEPLOYMENT_TARGET"] = "11.0" if machine == "arm64" else "10.13"
    run(["perl", "Configure", target, "shared", "no-tests", f"--prefix={installed}",
         f"--openssldir={installed / 'ssl'}", "--libdir=lib"], cwd=source, environment=environment)
    make = ["nmake", "/NOLOGO"] if system == "Windows" else ["make", "-j2"]
    run([*make, "build_sw"], cwd=source, environment=environment)
    run([*make, "install_sw"], cwd=source, environment=environment)
    if system == "Windows":
        for name in ("libcrypto-3-x64.dll", "libssl-3-x64.dll", "openssl.exe"):
            shutil.copyfile(installed / "bin" / name, prefix / "bin" / name)
        for name in ("libcrypto.lib", "libssl.lib"):
            shutil.copyfile(installed / "lib" / name, prefix / "lib" / name)
    else:
        for name in ("libcrypto.3.dylib", "libssl.3.dylib"):
            shutil.copyfile(installed / "lib" / name, prefix / "lib" / name)
        shutil.copy2(installed / "bin" / "openssl", prefix / "bin" / "openssl")
    shutil.copytree(installed / "lib" / "ossl-modules", prefix / "lib" / "ossl-modules")
    shutil.copytree(installed / "include" / "openssl", prefix / "include" / "openssl", dirs_exist_ok=True)
    licenses = prefix / "share" / "licenses" / "openssl"
    licenses.mkdir(parents=True)
    for name in ("LICENSE.txt", "AUTHORS.md"):
        shutil.copyfile(source / name, licenses / name)
    if system == "Darwin":
        changed = [prefix / "bin" / "openssl", prefix / "lib" / "libcrypto.3.dylib",
                   prefix / "lib" / "libssl.3.dylib", *sorted((prefix / "lib" / "ossl-modules").glob("*.dylib"))]
        for path in changed:
            if run(["otool", "-D", path], capture=True).splitlines()[1:]:
                run(["install_name_tool", "-id", "@rpath/" + path.name, path])
            for line in run(["otool", "-L", path], capture=True).splitlines()[1:]:
                dependency = line.rsplit(" (compatibility version", 1)[0].strip()
                if dependency.startswith(str(installed) + "/"):
                    destination = prefix / Path(dependency).relative_to(installed)
                    relative = os.path.relpath(destination, path.parent)
                    run(["install_name_tool", "-change", dependency, "@loader_path/" + relative, path])
                elif not dependency.startswith(("@", "/usr/lib/", "/System/Library/")):
                    raise ValueError("OpenSSL has an unbundled native dependency")
            run(["codesign", "--force", "--sign", "-", path])
            run(["codesign", "--verify", path])
    version = run([tool(prefix, "openssl"), "version", "-a"], capture=True)
    if not version.startswith("OpenSSL " + OPENSSL + " "):
        raise ValueError("Unexpected replacement OpenSSL version")
    return {"source": OPENSSL_URL, "sha256": OPENSSL_SHA256, "version": version,
            "target": target, "reason": "replace the supplier's unsupported OpenSSL 3.6.3"}


def inspect_xml_library(path):
    dynamic = run(["readelf", "-d", path], capture=True)
    needed = set(re.findall(r"\(NEEDED\).*\[(.*?)\]", dynamic))
    allowed = {"libc.so.6", "libm.so.6", "libz.so.1", "liblzma.so.5", "libpthread.so.0", "libdl.so.2"}
    if (re.findall(r"\(SONAME\).*\[(.*?)\]", dynamic) != ["libxml2.so.2"]
            or not needed or needed - allowed or re.search(r"\((?:RPATH|RUNPATH)\)", dynamic)):
        raise ValueError("XML compatibility library has an unexpected ABI or dependency")
    return {"dynamic": dynamic, "needed": sorted(needed),
            "symbol_versions": run(["readelf", "--version-info", path], capture=True)}


def update_xml(prefix, work):
    if platform.system() != "Linux":
        return None
    for name, expected in XML_SOURCES.items():
        download(XML_SOURCE_URL + name.replace("+", "%2B"), expected, work / name)
    source, installed = work / "libxml-source", work / "libxml-installed"
    # Inputs are pinned against the previously verified signed Ubuntu source descriptor.
    run(["dpkg-source", "--no-check", "-x", work / f"libxml2_{XML_VERSION}.dsc", source])
    options = ["--enable-shared", "--disable-static", "--without-python", "--without-icu",
               "--with-iconv", "--with-zlib", "--with-lzma", f"--prefix={installed}", "--libdir=" + str(installed / "lib")]
    environment = {"CFLAGS": "-O2 -fPIC", "CPPFLAGS": "", "LDFLAGS": ""}
    run(["autoreconf", "-fi"], cwd=source, environment=environment)
    run([source / "configure", *options], cwd=source, environment=environment)
    run(["make", "-j2"], cwd=source, environment=environment)
    run(["make", "check"], cwd=source, environment=environment)
    run(["make", "install"], cwd=source, environment=environment)
    encodings = {"GB18030": "记忆", "SHIFT_JIS": "記憶", "ISO-8859-1": "mémoire"}
    for encoding, content in encodings.items():
        document = work / f"xml-{encoding}.xml"
        document.write_bytes(f'<?xml version="1.0" encoding="{encoding}"?><memory>{content}</memory>'.encode(encoding))
        converted = run([installed / "bin" / "xmllint", "--encode", "UTF-8", document], capture=True)
        if f"<memory>{content}</memory>" not in converted:
            raise ValueError("XML encoding conversion changed the input")
    library = installed / "lib" / "libxml2.so.2"
    if not library.resolve(strict=True).is_relative_to(installed):
        raise ValueError("XML compatibility library escapes its build prefix")
    inspection = inspect_xml_library(library)
    destination = prefix / "lib" / library.name
    shutil.copyfile(library, destination)
    destination.chmod(0o755)
    licenses = prefix / "share" / "licenses" / "libxml2"
    licenses.mkdir(parents=True)
    for name, original in (("COPYING", source / "COPYING"), ("Copyright", source / "Copyright"),
                           ("debian-copyright", source / "debian" / "copyright")):
        shutil.copyfile(original, licenses / name)
    metadata = {"version": XML_VERSION, "source_url": XML_SOURCE_URL, "sources": XML_SOURCES,
                "options": [option for option in options if not option.startswith(("--prefix=", "--libdir="))],
                "upstream_checks_passed": True, "encoding_roundtrips": sorted(encodings),
                "library_sha256": digest(destination), **inspection}
    (licenses / "source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def inspect_library(path):
    system = platform.system()
    if system == "Darwin":
        architecture = run(["lipo", "-archs", path], capture=True).strip()
        if architecture != platform.machine():
            raise ValueError("Unexpected vector architecture")
        dependencies = run(["otool", "-L", path], capture=True)
        for line in dependencies.splitlines()[1:]:
            dependency = line.rsplit(" (compatibility version", 1)[0].strip()
            if not dependency.startswith(("/usr/lib/", "/System/Library/")):
                raise ValueError(f"Unbundled vector dependency: {dependency}")
        commands = run(["otool", "-l", path], capture=True)
        minimum = "11.0" if platform.machine() == "arm64" else "10.13"
        minimum_versions = re.findall(r"minos (\d+\.\d+(?:\.\d+)?)", commands)
        if not minimum_versions:
            match = re.search(r"cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version (\d+\.\d+(?:\.\d+)?)", commands)
            minimum_versions = [match[1]] if match else []
        if not minimum_versions or any(tuple(map(int, value.split(".")[:2])) > tuple(map(int, minimum.split("."))) for value in minimum_versions):
            raise ValueError("Vector deployment target exceeds its declared minimum")
        run(["codesign", "--force", "--sign", "-", path])
        run(["codesign", "--verify", path])
        return {"architecture": architecture, "dependencies": dependencies, "load_commands": commands,
                "minimum_macos": minimum_versions, "declared_minimum_macos": minimum}
    if system == "Windows":
        return {"headers": run(["dumpbin", "/HEADERS", path], capture=True),
                "dependencies": run(["dumpbin", "/DEPENDENTS", path], capture=True)}
    return {"header": run(["readelf", "-h", path], capture=True),
            "dynamic": run(["readelf", "-d", path], capture=True),
            "symbol_versions": run(["readelf", "--version-info", path], capture=True),
            "dependencies": run(["ldd", path], capture=True)}


def inventory(prefix):
    records = []
    for path in sorted(prefix.rglob("*")):
        if not path.resolve(strict=True).is_relative_to(prefix):
            raise ValueError("Bundle contains a link outside its prefix")
        if path.is_file():
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError("Bundle contains a non-regular file")
            records.append({"path": path.relative_to(prefix).as_posix(), "sha256": digest(path),
                            "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode)})
    return records


def write_bundle(prefix, source, output, metadata):
    files = inventory(prefix)
    metadata["files"] = files
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    postgres_license = prefix / "COPYRIGHT"
    if not postgres_license.is_file():
        postgres_license = prefix / "server_license.txt"
    for name, path in (("PGVECTOR-LICENSE", source / "LICENSE"),
                       ("POSTGRESQL-COPYRIGHT", postgres_license)):
        if not path.is_file():
            raise ValueError(f"Missing license: {name}")
        shutil.copyfile(path, output / name)
    with zipfile.ZipFile(output / "vector-resources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in files:
            name = row["path"]
            if name.startswith("share/extension/vector") or Path(name).name in {"vector.so", "vector.dll", "vector.dylib"}:
                archive.write(prefix / name, name)
        archive.write(source / "LICENSE", "PGVECTOR-LICENSE")
    with tarfile.open(output / "engine.tar.gz", "x:gz") as archive:
        archive.add(prefix, arcname="pginstall")
    artifacts = {path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
                 for path in sorted(output.iterdir()) if path.is_file()}
    (output / "artifacts.json").write_text(json.dumps(artifacts, indent=2) + "\n", encoding="utf-8")


def build(work, output):
    key = (platform.system(), platform.machine())
    if key not in WHEELS:
        raise ValueError(f"Unsupported platform: {key}")
    if any(character.isspace() for character in str(work)):
        raise ValueError("The native build directory must not contain whitespace")
    if output.exists():
        raise ValueError("The output directory must be new")
    work.mkdir(parents=True, exist_ok=False)
    tag, expected = WHEELS[key]
    filename = f"postgresql_binaries-{SUPPLIER_VERSION}-py3-none-{tag}.whl"
    with urllib.request.urlopen(f"https://pypi.org/pypi/postgresql-binaries/{SUPPLIER_VERSION}/json", timeout=60) as response:
        entries = json.load(response)["urls"]
    entry = next(row for row in entries if row["filename"] == filename)
    if entry["digests"]["sha256"] != expected:
        raise ValueError("Supplier metadata differs from the pinned wheel checksum")
    wheel = work / filename
    download(entry["url"], expected, wheel)
    prefix, inner_hash = extract_wheel(wheel, work)
    archive = work / "pgvector.tar.gz"
    download(VECTOR_URL, VECTOR_SHA256, archive)
    with tarfile.open(archive) as saved:
        saved.extractall(work, filter="data")
    source = work / f"pgvector-{VECTOR}"
    xml = update_xml(prefix, work)
    openssl = update_openssl(prefix, work)
    versions = {name: run([tool(prefix, name), "--version"], capture=True).strip() for name in TOOLS}
    if not all(value.endswith(" " + POSTGRES) for value in versions.values()):
        raise ValueError("Unexpected PostgreSQL tool version")
    options = compile_vector(source, prefix)
    metadata = {"postgres": POSTGRES, "vector": VECTOR, "platform": list(key), "qualification_only": True,
                "runtime_dependency_changed": False, "supplier_python_executed": False,
                "supplier_wheel": {"filename": filename, "sha256": expected, "archive_sha256": inner_hash},
                "vector_source": {"url": VECTOR_URL, "sha256": VECTOR_SHA256},
                "openssl": openssl, "libxml2": xml,
                "build_options": options, "host": platform.platform(), "tools": versions,
                "library": inspect_library(vector_library(prefix)),
                "compiler": run(["cl" if os.name == "nt" else "cc", "--version"], capture=True).strip()
                if os.name != "nt" else os.environ.get("VCToolsVersion", "unknown")}
    write_bundle(prefix, source, output, metadata)
    return prefix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    prefix = build(args.work_directory.resolve(), args.output_directory.resolve())
    print(json.dumps({"prefix": str(prefix), "published": False}))


if __name__ == "__main__":
    main()
