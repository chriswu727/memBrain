"""Write the versions uv.lock resolved for the runtime into the constraints file the launchers install with.

    python scripts/write_constraints.py           # rewrite plugins/membrain/constraints.txt and OpenClaw's copy
    python scripts/write_constraints.py --check   # exit 1 when either differs from uv.lock

`uv tool install` reads neither the package's uv.lock nor its uv settings, so without this file an installation
resolves the newest versions its requirement ranges allow, which the test suite never ran. The launchers pass it
with `--constraints` and install without it when that fails (an older uv without the option, or a locked version
with no wheel for the platform). tests/test_constraints.py fails while the files differ from uv.lock.
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "plugins" / "membrain" / "constraints.txt",
           ROOT / "integrations" / "openclaw" / "membrain" / "constraints.txt"]
PROJECT = "membrain-ai"
EXTRAS = ("embedded", "semantic")  # The launchers install membrain-ai[embedded,semantic].
HEADER = ("# Generated from uv.lock by scripts/write_constraints.py; do not edit.\n"
          "# The launchers install memBrain with these versions, the ones its tests ran (uv tool install --constraints).\n")


def constraints(lock_text: str) -> str:
    """Every package the runtime with its launcher extras can install, at its locked version, one per line."""
    packages = {package["name"]: package for package in tomllib.loads(lock_text)["package"]}
    project = packages[PROJECT]
    pending = list(project.get("dependencies", []))
    for extra in EXTRAS:
        pending += project["optional-dependencies"][extra]
    seen, names = set(), set()
    while pending:
        dependency = pending.pop()
        name = dependency["name"]
        package = packages[name]
        if name not in names:
            names.add(name)
            pending += package.get("dependencies", [])
        for extra in dependency.get("extra", []):
            if (name, extra) not in seen:
                seen.add((name, extra))
                pending += package.get("optional-dependencies", {}).get(extra, [])
    return HEADER + "".join(f"{name}=={packages[name]['version']}\n" for name in sorted(names))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="Only report whether the files are current")
    args = parser.parse_args()
    expected = constraints((ROOT / "uv.lock").read_text(encoding="utf-8"))
    stale = [path for path in TARGETS if not path.exists() or path.read_text(encoding="utf-8") != expected]
    if args.check:
        for path in stale:
            print(f"{path.relative_to(ROOT)} differs from uv.lock; run python scripts/write_constraints.py",
                  file=sys.stderr)
        return 1 if stale else 0
    for path in stale:
        path.write_text(expected, encoding="utf-8", newline="\n")
        print(f"{path.relative_to(ROOT)}: written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
