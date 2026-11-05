"""Inspect the checksummed Linux supplier when ordinary native startup cannot load tools."""
import hashlib
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from membrain import native_bundle


def main():
    source = native_bundle._source()
    assert source is not None
    key, entry, archive = source
    assert key.startswith("linux-")
    with archive.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == entry["supplier"]["archive_sha256"]
    with tempfile.TemporaryDirectory(prefix="membrain-native-loader-") as directory:
        with tarfile.open(archive) as saved:
            saved.extractall(directory, filter="data")
        prefix, = Path(directory).iterdir()
        environment = native_bundle.environment(prefix)
        for name in native_bundle.TOOLS:
            tool = prefix / "bin" / name
            result = subprocess.run([str(tool), "--version"], env=environment, capture_output=True, text=True,
                                    timeout=15, check=False)
            print(name, "exit", result.returncode, (result.stdout + result.stderr).strip(), flush=True)
            if shutil.which("ldd"):
                linked = subprocess.run(["ldd", str(tool)], env=environment, capture_output=True, text=True,
                                        timeout=15, check=False)
                print(linked.stdout + linked.stderr, flush=True)


if __name__ == "__main__":
    main()
