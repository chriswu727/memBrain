"""Compare isolated initdb environments and password-file permissions after a qualification failure."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

from membrain import native_bundle
from membrain.local_profile import _private


def check(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    _private(directory, directory=True)
    native_bundle._cache_directory = lambda: directory / "cache"
    prefix = native_bundle.prepare()
    suffix = ".exe" if os.name == "nt" else ""
    report = {"scope": "diagnosis only; these attempts do not replace a failed acceptance",
              "model_calls": 0, "target": native_bundle.platform_key(), "attempts": []}
    for controlled_environment in (False, True):
        for private_password in (False, True):
            name = f"environment-{int(controlled_environment)}-private-{int(private_password)}"
            work = directory / name
            work.mkdir(mode=0o700)
            _private(work, directory=True)
            password = work / ".password"
            descriptor = os.open(password, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(secrets.token_hex(24) + "\n")
            if private_password:
                _private(password)
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith(("PG", "MEMORY_"))
                           and key not in {"PYTHONPATH", "PYTHONHOME"}}
            environment["LC_ALL"] = "C"
            if controlled_environment:
                environment = native_bundle.environment(prefix)
            try:
                result = subprocess.run(
                    [str(prefix / "bin" / ("initdb" + suffix)), "--debug", "-D", str(work / "data"),
                     "-U", "postgres", "-A", "scram-sha-256", "--pwfile", str(password), "-E", "UTF8",
                     "--locale=C", "--no-instructions"],
                    env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=120, check=False)
                row = {"controlled_environment": controlled_environment, "private_password": private_password,
                       "returncode": result.returncode, "output_bytes": len(result.stdout),
                       "output": result.stdout.decode("utf-8", "replace"),
                       "version_file_created": (work / "data/PG_VERSION").is_file()}
                report["attempts"].append(row)
                print(json.dumps({key: value for key, value in row.items() if key != "output"}), flush=True)
            finally:
                password.unlink(missing_ok=True)
                (directory / "diagnosis.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert not list(directory.rglob("postmaster.pid"))
    print(json.dumps({"attempts": len(report["attempts"]), "no_servers_started": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    check(parser.parse_args().directory.resolve())
