import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
_spec = importlib.util.spec_from_file_location("pin_runtime", ROOT / "scripts" / "pin_runtime.py")
pin_runtime = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pin_runtime)
ARCHIVE = re.compile(r'https://github\.com/chriswu727/membrain/archive/([0-9a-f]+)\.zip', re.IGNORECASE)


def pinned_revisions() -> set[str]:
    revisions = set()
    for path in pin_runtime.LAUNCHERS:
        contents = path.read_text()
        assert 'git+https://' not in contents, path
        matches = ARCHIVE.findall(contents)
        assert matches and all(len(revision) == 40 for revision in matches), path
        revisions.update(matches)
    return revisions


def test_every_host_launcher_pins_the_same_immutable_runtime_revision():
    assert len(pinned_revisions()) == 1


def test_the_pinned_runtime_is_the_runtime_in_this_repository():
    """Users install the pinned commit, so it must hold the code that was tested here.

    After changing the runtime, commit, then run scripts/pin_runtime.py with that commit.
    """
    (revision,) = pinned_revisions()
    try:
        present = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", revision + "^{commit}"],
                                 capture_output=True).returncode == 0
    except OSError:
        present = False
    if not present:
        pytest.skip("not a full git checkout")
    changed = subprocess.run(["git", "-C", str(ROOT), "diff", "--name-only", revision, "--", "src/membrain",
                              "pyproject.toml"], capture_output=True, text=True, check=True).stdout.split()
    changed = [name for name in changed if not name.endswith((".pyc",))]
    assert not changed, f"the launchers install {revision[:12]}, which lacks changes to: {', '.join(changed[:10])}"
