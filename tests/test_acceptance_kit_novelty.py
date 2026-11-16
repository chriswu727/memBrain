"""The kit's novelty check on a synthetic git repository: it reads earlier scenarios from one commit, finds a copied
or recorded hash and a high 8-gram overlap, and prints only numbers and booleans. No model, no network."""
import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOVELTY = ROOT / "evaluations" / "acceptance-kit" / "novelty.py"
PLANT = "zqplanted"
pytestmark = pytest.mark.skipif(shutil.which("git") is None or os.name == "nt", reason="needs git")


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_kit_novelty", NOVELTY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _words(seed: str, count: int) -> str:
    return " ".join(f"{PLANT}{seed}{number}" for number in range(count))


def _repo(tmp_path: Path, recorded_hash: str) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / "evaluations" / "evidence" / "old").mkdir(parents=True)
    (repo / "evaluations" / "v1-old-scenario-a.py").write_text(f'SESSIONS_LONG = [("s", ["{_words("a", 200)}"])]\n')
    (repo / "evaluations" / "not-a-scenario-harness.py").write_text(f'X = "{_words("h", 200)}"\n')
    (repo / "evaluations" / "evidence" / "old" / "scenario_s1.py.gz").write_bytes(
        gzip.compress(f'SESSIONS_LONG = [("s", ["{_words("z", 200)}"])]\n'.encode()))
    (repo / "evaluations" / "record.md").write_text(f"Scenario hash `{recorded_hash}`.\n")
    for command in (["init", "-q"], ["add", "-A"],
                    ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "earlier"]):
        subprocess.run(["git", "-C", str(repo), *command], check=True)
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()
    return repo, base


def _run(*arguments):
    done = subprocess.run([sys.executable, str(NOVELTY), *map(str, arguments)], capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


def test_new_scenario_passes_and_output_holds_no_text(tmp_path):
    secret = b"never printed " + _words("n", 300).encode()
    heldout = tmp_path / "heldout.py"
    heldout.write_bytes(secret)
    repo, base = _repo(tmp_path, "0" * 64)
    code, out, err = _run("--repo", repo, "--base", base, "--threshold-pct", 10, heldout)
    summary = json.loads(out)
    assert code == 0 and summary["ok"] is True
    assert summary["earlier_files"] == 2  # the top-level scenario and the evidence .gz; not the harness file
    assert summary["results"][0]["sha256_new"] is True
    assert summary["results"][0]["max_8gram_overlap_pct"] == 0.0
    assert PLANT not in out + err and "heldout" not in out + err and "scenario" not in out + err


def test_copied_and_overlapping_scenarios_fail(tmp_path):
    copied_text = gzip.decompress(gzip.compress(f'SESSIONS_LONG = [("s", ["{_words("z", 200)}"])]\n'.encode()))
    copied = tmp_path / "copied.py"
    copied.write_bytes(copied_text)
    overlapping = tmp_path / "overlapping.py"
    overlapping.write_text(_words("a", 100) + " " + _words("n", 100))  # half of its tokens from scenario a
    recorded = tmp_path / "recorded.py"
    recorded.write_text(_words("r", 50))
    repo, base = _repo(tmp_path, hashlib.sha256(recorded.read_bytes()).hexdigest())
    code, out, _ = _run("--repo", repo, "--base", base, "--threshold-pct", 10, copied, overlapping, recorded)
    results = json.loads(out)["results"]
    assert code == 1
    assert results[0]["sha256_new"] is False and results[0]["max_8gram_overlap_pct"] == 100.0
    assert results[1]["sha256_new"] is True and 40 < results[1]["max_8gram_overlap_pct"] < 60
    assert results[1]["within_threshold"] is False
    assert results[2]["sha256_new"] is False  # its hash is recorded in an earlier record


def test_chinese_is_compared_by_character():
    module = _load()
    assert len(module.grams("今天是三月三日星期二".encode())) == 3
    assert module.TOKEN.findall("Hello, 世界 42") == ["Hello", "世", "界", "42"]


def test_read_errors_print_only_a_type(tmp_path):
    repo, base = _repo(tmp_path, "0" * 64)
    code, out, _ = _run("--repo", repo, "--base", base, "--threshold-pct", 10, tmp_path / "missing-secret-name.py")
    assert code == 2 and json.loads(out) == {"ok": False, "error": "FileNotFoundError"}
