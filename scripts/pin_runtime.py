"""Point every host launcher at one memBrain runtime, so what users install is what the repository tested.

    python scripts/pin_runtime.py <commit>        # a 40-character commit that is on GitHub
    python scripts/pin_runtime.py --pypi 0.1.0    # after that version is published on PyPI

A commit pin cannot name the commit that adds it, so change the runtime first, commit, then pin to that commit in a
second commit. tests/test_installation_pin.py fails while the pinned commit's runtime differs from the source.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "plugins" / "membrain"
LAUNCHERS = [PACKAGE / name for name in (
    ".claude-mcp.json", ".codex-mcp.json", ".codebuddy-mcp.json", "hooks/claude-hooks.json",
    "hooks/codex-hooks.json", "bin/membrain-hook", "bin/membrain-hook.cmd")] + [
    ROOT / "integrations" / "openclaw" / "membrain" / "index.js",
    ROOT / "integrations" / "astrbot" / "astrbot_plugin_membrain" / "requirements.txt"]
REQUIREMENT = "membrain-ai[embedded,semantic]"
PINNED = re.compile(re.escape(REQUIREMENT) + r"(?: @ https://github\.com/chriswu727/membrain/archive/[^\s\"'}]+\.zip"
                    r"|==[0-9][0-9A-Za-z.+-]*)", re.IGNORECASE)


def requirement(commit: str | None, version: str | None) -> str:
    if version:
        return f"{REQUIREMENT}=={version}"
    return f"{REQUIREMENT} @ https://github.com/chriswu727/membrain/archive/{commit}.zip"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("commit", nargs="?")
    parser.add_argument("--pypi", metavar="VERSION")
    args = parser.parse_args()
    if bool(args.commit) == bool(args.pypi):
        parser.error("give a commit or --pypi VERSION")
    if args.commit:
        if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
            parser.error("give the full 40-character commit")
        subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", args.commit + "^{commit}"],
                       check=True, stdout=subprocess.DEVNULL)
    target = requirement(args.commit, args.pypi)
    for path in LAUNCHERS:
        with path.open(encoding="utf-8", newline="") as stream:  # Keep each file's line endings.
            text = stream.read()
        updated, count = PINNED.subn(target, text)
        if not count:
            print(f"{path.relative_to(ROOT)}: no runtime requirement found", file=sys.stderr)
            return 1
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(updated)
        print(f"{path.relative_to(ROOT)}: {count} pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
