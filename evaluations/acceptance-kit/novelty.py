#!/usr/bin/env python3
"""Check that held-out scenarios are new, printing only numbers and booleans.

  novelty.py --repo REPO --base COMMIT --threshold-pct T HELDOUT.py [HELDOUT.py ...]

The earlier scenarios are the public ones in REPO at COMMIT: every top-level `evaluations/*.py` whose name contains
"scenario" and that assigns `SESSIONS_LONG` at the start of a line, and every `evaluations/evidence/**/scenario_*.py.gz`.
They are read from git (`git show COMMIT:PATH`), so nothing outside that commit counts as earlier. For each held-out
file, in the order given:

- `sha256_new`: its sha256 differs from every earlier file's (the .gz files decompressed) and from every 64-hex string
  recorded anywhere under `evaluations/` at COMMIT (earlier attempts' bindings record the hashes of scenarios that
  were never published);
- `max_8gram_overlap_pct`: the largest share, over the earlier files, of the held-out file's distinct 8-grams of
  tokens that also occur in that one earlier file (tokens: lowercased runs of letters or digits, and each CJK
  character alone, so Chinese text is compared character by character);
- `union_8gram_overlap_pct`: the same share against all earlier files together.

`ok` is true when every held-out file is `sha256_new` and its largest overlap is at most T. It prints one JSON line
and never a token, an n-gram, a file name or any text of either side; held-out files are given by the operator and
identified in the output only by their position. Exit 0 when ok, 1 when not, 2 on a usage or read error.
Standard library only.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

N = 8
TOKEN = re.compile(r"[㐀-䶿一-鿿豈-﫿]|[^\W㐀-䶿一-鿿豈-﫿_]+")
ASSIGNS_SESSIONS = re.compile(rb"^SESSIONS_LONG\s*=", re.MULTILINE)
HEX64 = re.compile(rb"\b[0-9a-f]{64}\b")


def grams(data: bytes) -> set[tuple[str, ...]]:
    tokens = TOKEN.findall(data.decode("utf-8", errors="replace").lower())
    return {tuple(tokens[index:index + N]) for index in range(len(tokens) - N + 1)}


def _git(repo: Path, *arguments: str) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True)
    if done.returncode != 0:
        raise OSError("git failed")
    return done.stdout


def earlier(repo: Path, base: str) -> tuple[list[bytes], set[str]]:
    """The earlier scenarios' bytes and every 64-hex string recorded under evaluations/ at BASE."""
    files, recorded = [], set()
    for path in _git(repo, "ls-tree", "-r", "-z", "--name-only", base, "--", "evaluations").split(b"\0"):
        if not path:
            continue
        name = PurePosixPath(path.decode())
        top = len(name.parts) == 2
        if top and name.suffix == ".py" and "scenario" in name.name:
            data = _git(repo, "show", f"{base}:{name}")
            if ASSIGNS_SESSIONS.search(data):
                files.append(data)
        elif name.parts[:2] == ("evaluations", "evidence") and name.name.startswith("scenario_") \
                and name.name.endswith(".py.gz"):
            files.append(gzip.decompress(_git(repo, "show", f"{base}:{name}")))
    for line in _git(repo, "grep", "-I", "-h", "-o", "-E", "[0-9a-f]{64}", base, "--", "evaluations").splitlines():
        recorded.update(match.decode() for match in HEX64.findall(line))
    return files, recorded


def check(heldout: list[bytes], earlier_files: list[bytes], recorded: set[str], threshold: float) -> dict:
    earlier_grams = [grams(data) for data in earlier_files]
    union = set().union(*earlier_grams) if earlier_grams else set()
    earlier_hashes = {hashlib.sha256(data).hexdigest() for data in earlier_files} | recorded
    results = []
    for index, data in enumerate(heldout, 1):
        own = grams(data)
        share = (lambda other: round(100 * len(own & other) / len(own), 2) if own else 0.0)
        largest = max((share(other) for other in earlier_grams), default=0.0)
        results.append({"position": index, "grams": len(own),
                        "sha256_new": hashlib.sha256(data).hexdigest() not in earlier_hashes,
                        "max_8gram_overlap_pct": largest, "union_8gram_overlap_pct": share(union),
                        "within_threshold": largest <= threshold})
    return {"earlier_files": len(earlier_files), "recorded_hashes": len(recorded), "n": N, "threshold_pct": threshold,
            "results": results,
            "ok": bool(results) and all(item["sha256_new"] and item["within_threshold"] for item in results)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", required=True, help="the commit whose public scenarios count as earlier")
    parser.add_argument("--threshold-pct", required=True, type=float)
    parser.add_argument("heldout", nargs="+")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        print(json.dumps({"ok": False, "error": "usage"}))
        return 2
    try:
        files, recorded = earlier(Path(args.repo), args.base)
        heldout = [Path(path).read_bytes() for path in args.heldout]
        summary = check(heldout, files, recorded, args.threshold_pct)
    except Exception as error:  # noqa: BLE001 - reported by type only: a message could quote a file.
        print(json.dumps({"ok": False, "error": type(error).__name__}))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
