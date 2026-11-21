"""The versions installations get are the ones uv.lock pins and the suite runs: the launchers install memBrain with
the constraints file generated from uv.lock. No service, database or network."""
import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
_spec = importlib.util.spec_from_file_location("write_constraints", ROOT / "scripts" / "write_constraints.py")
write_constraints = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(write_constraints)


def test_the_constraints_files_are_current_with_uv_lock():
    """After changing uv.lock, run python scripts/write_constraints.py."""
    expected = write_constraints.constraints((ROOT / "uv.lock").read_text(encoding="utf-8"))
    for path in write_constraints.TARGETS:
        assert path.read_text(encoding="utf-8") == expected, f"{path.relative_to(ROOT)} differs from uv.lock"


def test_the_constraints_pin_every_package_the_launchers_install_at_its_locked_version():
    locked = {package["name"]: package["version"] for package in
              tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))["package"]}
    lines = [line for line in write_constraints.TARGETS[0].read_text(encoding="utf-8").splitlines()
             if not line.startswith("#")]
    pinned = dict(line.split("==") for line in lines)
    assert all(locked[name] == version for name, version in pinned.items())
    # The runtime, both launcher extras and what they pull in; not the project itself, not development tools.
    assert {"fastapi", "psycopg-binary", "postgresql-binaries", "onnxruntime", "tokenizers", "numpy"} <= set(pinned)
    assert not {"membrain-ai", "pytest", "ruff", "playwright"} & set(pinned)


def test_the_check_mode_agrees():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "write_constraints.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_the_constraints_files_are_in_the_source_archive_and_beside_every_launcher():
    """The plugin hosts install the plugin directory; OpenClaw's instructions take its directory from the source
    archive GitHub builds, which leaves out what .gitattributes marks export-ignore."""
    for path in write_constraints.TARGETS:
        result = subprocess.run(["git", "-C", str(ROOT), "check-attr", "export-ignore", "--",
                                 str(path.relative_to(ROOT))], capture_output=True, text=True, check=True)
        assert result.stdout.strip().endswith("export-ignore: unspecified"), result.stdout
    plugin = ROOT / "plugins" / "membrain"
    assert '${CLAUDE_PLUGIN_ROOT}/constraints.txt' in (plugin / "hooks" / "claude-hooks.json").read_text()
    assert '${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}/constraints.txt' in (plugin / "hooks" / "codex-hooks.json").read_text()
    assert '"${0%/*}/../constraints.txt"' in (plugin / "bin" / "membrain-hook").read_text()
    assert '"%~dp0..\\constraints.txt"' in (plugin / "bin" / "membrain-hook.cmd").read_text()
    assert 'new URL("./constraints.txt", import.meta.url)' in (
        ROOT / "integrations" / "openclaw" / "membrain" / "index.js").read_text()
