"""The host-trial tool end to end, with a stub in place of Claude Code on a sandboxed PATH and a real local service.

Each test prepares a real trial from this checkout's HEAD (a frozen runtime copy built from uv's cache, a plugin copy,
a new memory with its own ports and the local embedding model, a synthetic project) and plays a scenario through
``trial.py run``. The stub (evaluations/host-trial/stub/claude) reads the arguments the runner gives the host and
runs the plugin copy's REAL hooks and tool server against the trial's memory; only the choice of tools, their input
and the reply text are scripted. Starts services and a browser: run it under the shared lock, through the focused
runner. No real host or model is started.
"""
import datetime
import getpass
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "evaluations" / "host-trial"
MODEL = os.environ.get("MEMBRAIN_TEST_EMBEDDING_MODEL") or str(Path.home() / ".cache" / "membrain" / "eval-embedding-model")
SESSION_KEYS = {"PATH", "HOME", "USER", "LOGNAME", "LANG", "TERM", "TRIAL_TURN", "MEMBRAIN_DIRECTORY"}


def _load():
    spec = importlib.util.spec_from_file_location("host_trial_tool_e2e", TOOL / "trial.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trial = _load()
HEAD = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


class Host:
    """The stub on a PATH that holds nothing else of the user's: no real `claude` can be found."""

    def __init__(self, root: Path, script: dict):
        self.bin = root / "host-bin"
        self.bin.mkdir()
        shutil.copyfile(TOOL / "stub" / "claude", self.bin / "claude")
        (self.bin / "claude").chmod(0o755)
        (self.bin / "claude-script.json").write_text(json.dumps({"turns": script}))
        self.path = f"{self.bin}:/usr/bin:/bin"

    def invocations(self) -> list[dict]:
        path = self.bin / "state" / "invocations.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run(self, folder: Path, approval: Path, *extra) -> tuple[int, dict]:
        environment = {"PATH": self.path, "HOME": str(Path.home()), "USER": os.environ.get("USER", ""),
                       "LOGNAME": os.environ.get("LOGNAME", ""), "LANG": "C.UTF-8"}
        done = subprocess.run([sys.executable, str(TOOL / "trial.py"), "run", str(folder), "--approval", str(approval),
                               *extra], env=environment, capture_output=True, text=True, timeout=1500)
        assert done.stdout.strip(), done.stderr[-4000:]
        return done.returncode, json.loads(done.stdout)


def approve(root: Path, folder: Path, *, max_turns: int, model: str = "sonnet") -> Path:
    path = root / f"approval-{folder.name}-{len(list(root.glob('approval-*')))}.json"
    path.write_text(json.dumps({"approved_by": "the test", "date": datetime.date.today().isoformat(), "model": model,
                                "max_turns": max_turns,
                                "scenario_sha256": trial.scenarios.sha256(folder / "scenario.json")}))
    return path


def tree(*roots: Path) -> dict:
    out = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def service(folder: Path, action: str) -> dict:
    return trial.memory_ops(folder, action, folder / "brain")


def verdicts(folder: Path) -> dict:
    return {(item["turn"], item["label"]): item for item in json.loads((folder / "results.json").read_text())["checks"]}


SOURCE = {"source_messages": "{source_messages}", "recording_capture": "{capture}"}
SCRIPT_A = {
    "t01-day1-decision": {"cost": 0.12, "actions": [
        {"tool": "ToolSearch", "input": {"query": "select:mcp__plugin_membrain_membrain__memory_note", "max_results": 1}},
        {"tool": "memory_note", "input": {"text": "Tidepool project: decided to use PostgreSQL as the database.",
                                          "kind": "other", **SOURCE}},
        {"tool": "Write", "input": {"file_path": "backend/.env.example", "content":
                                    "DATABASE_URL=postgresql+psycopg://tidepool:tidepool@localhost:5432/tidepool\n"}},
        {"say": "Postgres is wired in, and I saved the decision."}]},
    "t02-day1-pnpm": {"actions": [
        {"tool": "memory_note", "input": {"text": "Prefers pnpm over npm for frontend packages.", "kind": "preference",
                                          **SOURCE}},
        {"say": "pnpm it is."}]},
    "t03-day3-correction": {"cost": 0.03, "actions": [
        {"tool": "memory_note", "input": {"text": "Tidepool: PostgreSQL only on the server; local stays SQLite.",
                                          "kind": "other", "replaces": ["{note_id:PostgreSQL as the database}"],
                                          **SOURCE}},
        {"say": "I updated the earlier note, which said PostgreSQL for the whole project."}]},
    "t04-day3-migration": {"actions": [{"say": "Here is the migration, for PostgreSQL and for SQLite."}]},
    "t05-day8-finish": {"actions": [
        {"tool": "Read", "input": {"file_path": "backend/.env.example"}},
        {"tool": "Write", "input": {"file_path": "backend/.env", "content": "DATABASE_URL=sqlite:///tidepool.db\n"}},
        {"say": "The README still says Postgres, but your decision is that local uses SQLite."}]},
    "t06-day8-why": {"actions": [{"say": "You told me in an earlier session that local stays SQLite."}]},
    "t07-day8-show": {"actions": [
        {"tool": "Bash", "input": {"command": "membrain plugin ui --note {note_id:SQLite}",
                                   "description": "Open the memory page at the note"}},
        {"say": "I opened your memory page at that note."}]},
}
SCRIPT_B = {
    "t01-which-database": {"actions": [{"say": "Local uses SQLite; only the server uses PostgreSQL."}]},
    "t02-show-where": {"actions": [
        {"tool": "Bash", "input": {"command": "membrain plugin ui --note {note_id:SQLite}"}},
        {"say": "I opened your memory page at that note."}]},
    "t03-forget-pnpm": {"actions": [
        {"tool": "memory_recall", "input": {"query": "pnpm", "with_ids": True}, "save_as": "found"},
        {"tool": "memory_forget", "input": {"ids": "{select:found.records|pnpm|event_id}"}},
        {"say": "Done: I erased your message about pnpm."}]},
    "t04-boundary-heroku": {"actions": [
        {"tool": "memory_boundary", "input": {"topic": "the old Heroku setup", "aliases": ["Heroku"]}},
        {"say": "Understood, I won't bring it up."}]},
    "t05-whats-left": {"actions": [{"say": "Next: run the backend against SQLite and start the frontend."}]},
}


def test_both_delivered_scenarios_play_through_the_stub_and_the_earlier_scene_is_never_altered(tmp_path):
    root = tmp_path / "trials"
    host = Host(tmp_path, SCRIPT_A)
    first = trial.prepare(TOOL / "scenarios" / "resume-after-correction.json", commit=HEAD, root=root,
                          model_from=Path(MODEL), offline=True)
    try:
        prepared = json.loads((first / "prepared.json").read_text())
        assert prepared["commit"] == HEAD and prepared["service"]["ready"] is True
        assert (first / "bin" / "membrain").resolve() == (first / "runtime" / ".venv" / "bin" / "membrain").resolve()
        assert "(trial)/runtime/.venv/bin/python" in (first / "plugin-diff.txt").read_text()
        assert sorted(p.name for p in (first / "work").rglob("*") if p.is_file()) == [
            ".env.example", "README.md", "app.py", "package.json", "requirements.txt"]
        code, outcome = host.run(first, approve(tmp_path, first, max_turns=7))
        assert (code, outcome["status"], outcome["failed_checks"], outcome["rehearsal"]) == (0, "completed", 0, True), \
            json.dumps([item for item in json.loads((first / "results.json").read_text())["checks"]
                        if item["verdict"] == "FAIL"], indent=1)[:4000]
        found = verdicts(first)
        for key in (("t01-day1-decision", "the decision is saved as a note"),
                    ("t03-day3-correction", "the correction is a note that replaces the decision"),
                    ("t03-day3-correction", "the service holds the corrected note as replacing the decision"),
                    ("t05-day8-finish", "the new session writes SQLite into the project"),
                    ("t07-day8-show", "the page command is run at the corrected note"),
                    ("final", "the day-1 note stays replaced")):
            assert found[key]["verdict"] == "pass", (key, found[key])
        assert found[("t02-day1-pnpm", "a preference note on pnpm")]["verdict"] == "noted"
        # The host got exactly the hand-made trial's arguments and clean environment, and nothing else ran it.
        calls = host.invocations()
        assert len(calls) == 7
        sessions = json.loads((first / "sessions.json").read_text())
        assert calls[0]["argv"] == ["-p", "Let's get the Tidepool backend going. Decision: we'll use PostgreSQL as the "
                                    "database for the project.", "--model", "sonnet", "--plugin-dir",
                                    str(first / "plugin"), "--output-format", "stream-json", "--verbose",
                                    "--permission-mode", "acceptEdits", "--allowedTools",
                                    "mcp__plugin_membrain_membrain", "Read", "Glob", "Grep", "Edit", "Write",
                                    "Bash(membrain plugin ui:*)", "--session-id", sessions["day1"]]
        assert [call["argv"][-2] for call in calls] == ["--session-id", "--resume"] * 2 + \
            ["--session-id", "--resume", "--resume"]
        for call in calls:
            assert set(call["environment"]) - {"PWD", "SHLVL", "_", "OLDPWD"} == SESSION_KEYS
            assert call["environment"]["PATH"].startswith(f"{first / 'bin'}:{host.bin}:")
            assert call["environment"]["MEMBRAIN_DIRECTORY"] == str(first / "brain")
            assert call["cwd"] == str(first / "work")
        assert "memBrain records this conversation" in (host.bin / "state" / "server-instructions.txt").read_text()
        # Cost is the host's own, per turn; the run stopped the service at the end.
        record = json.loads((first / "run.json").read_text())
        assert record["total_cost_usd"] == pytest.approx(0.12 + 0.03 + 5 * 0.01)
        assert record["service"] == "stopped" and service(first, "status")["ready"] is False
        assert "owner's own" in record["host_login"]
        # The lead's own look at the page, at the corrected note.
        page = json.loads((first / "page-at-note.json").read_text())
        assert page["captured"] is True and "SQLite" in page["text"], page
        assert "Loading original messages" not in page["text"] and "Quick correction on the database" in page["text"], page
        # The memory is read with each record's speaker, so a role filter cannot pass by matching nothing.
        state = json.loads((first / "states" / "final.json").read_text())
        assert {record["role"] for record in state["records"]} == {"user", "assistant"}
        # The report: per-turn summaries, the checks, the memory, a record draft; nothing private in any of it.
        report = first / "report"
        assert len(list((report / "summaries").glob("*.txt"))) == 7
        draft = (report / "record-draft.md").read_text()
        assert draft.startswith("**A stub rehearsal")
        for section in ("## Checks", "## How it was run, and how it differs from an installation", "## Limits",
                        "owner's own login", "## Cost on the host", "0.20 USD"):
            assert section in draft, section
        user = getpass.getuser()
        for path in report.rglob("*"):
            if path.is_file() and path.suffix in (".md", ".txt"):
                text = path.read_text()
                assert str(tmp_path) not in text and str(Path.home()) not in text, path
                assert user.lower() not in text.lower(), path
        # A trial never runs twice.
        code, outcome = host.run(first, approve(tmp_path, first, max_turns=7))
        assert code == 2 and "already run" in outcome["refused"]

        # The second scenario continues that memory in a new trial: a clone, so the first scene stays as it was.
        scene = tree(first / "brain", first / ".agent-memory-recovery", first / "work")
        second = trial.prepare(TOOL / "scenarios" / "show-forget-boundary.json", commit=HEAD, root=root,
                               model_from=Path(MODEL), continue_from=first, offline=True)
        try:
            assert json.loads((second / "prepared.json").read_text())["memory"] == "cloned"
            assert json.loads((second / "brain" / "recovery.json").read_text())["registry_path"].startswith(str(second))
            (tmp_path / "b").mkdir()
            host_b = Host(tmp_path / "b", SCRIPT_B)
            code, outcome = host_b.run(second, approve(tmp_path, second, max_turns=6))
            assert (code, outcome["status"], outcome["failed_checks"]) == (0, "completed", 0), json.dumps(
                [item for item in json.loads((second / "results.json").read_text())["checks"]
                 if item["verdict"] == "FAIL"], indent=1)[:4000]
            found = verdicts(second)
            for key in (("t01-which-database", "the user's day-1 pnpm message is stored before it is forgotten"),
                        ("t02-show-where", "the page command is run at the corrected note"),
                        ("t03-forget-pnpm", "the records it named are gone from the service"),
                        ("t03-forget-pnpm", "the user's day-1 pnpm message is no longer stored"),
                        ("t03-forget-pnpm", "no current note about pnpm"),
                        ("t04-boundary-heroku", "the boundary is in the service"),
                        ("t05-whats-left", "the forgotten message is not handed to the new session"),
                        ("t05-whats-left", "the message about the boundary topic is left out of the history")):
                assert found[key]["verdict"] == "pass", (key, found[key])
            lead = found[("t03-forget-pnpm", "the reply, against what the tools returned")]
            assert lead["verdict"] == "for lead" and [title for title, _ in lead["shown"]] == [
                "reply", "memory_recall input", "memory_recall result", "memory_forget input", "memory_forget result"]
            assert (second / "work" / "backend" / ".env").read_text() == "DATABASE_URL=sqlite:///tidepool.db\n"
            assert tree(first / "brain", first / ".agent-memory-recovery", first / "work") == scene
            ledger = [json.loads(line) for line in (root / trial.LEDGER).read_text().splitlines()]
            assert [(entry["scenario"], entry["status"], entry["rehearsal"]) for entry in ledger] == [
                ("resume-after-correction", "started", True), ("resume-after-correction", "completed", True),
                ("show-forget-boundary", "started", True), ("show-forget-boundary", "completed", True)]
            keep = os.environ.get("HOST_TRIAL_REPORTS")  # The redacted reports, kept as evidence of a rehearsal.
            if keep:
                for folder in (first, second):
                    shutil.copytree(folder / "report", Path(keep) / folder.name.rsplit("-", 2)[0])
        finally:
            if service(second, "status")["ready"]:
                service(second, "stop")
    finally:
        if service(first, "status")["ready"]:
            service(first, "stop")


def small_scenario(tmp_path: Path, name: str, *, stop_on_failure: bool) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({
        "name": name, "description": "A small synthetic scenario for the runner's own tests.",
        "memory": {"new": True}, "project": {"files": {"README.md": "# Kestrel\n"}}, "stop_on_failure": stop_on_failure,
        "sessions": [{"name": "one", "turns": [
            {"name": "first", "message": "I'm moving to Lisbon in March.", "checks": [
                {"type": "tool", "name": "memory_note", "label": "a fact is saved"}]},
            {"name": "second", "message": "What should I pack?"},
            {"name": "third", "message": "Thanks, that helps."}]}]}))
    return path


def test_the_first_failed_check_stops_the_trial_and_leaves_the_scene_as_it_is(tmp_path):
    host = Host(tmp_path, {"t01-first": {"actions": [{"say": "Lisbon in March sounds lovely."}]}})
    folder = trial.prepare(small_scenario(tmp_path, "stop-check", stop_on_failure=True), commit=HEAD,
                           root=tmp_path / "trials", model_from=Path(MODEL), offline=True)
    try:
        code, outcome = host.run(folder, approve(tmp_path, folder, max_turns=3))
        assert (code, outcome["status"], outcome["turns_used"], outcome["service"]) == (1, "stopped", 1, "left running")
        assert "a check failed in t01-first" in outcome["reason"]
        assert len(host.invocations()) == 1
        assert sorted(path.name for path in (folder / "logs").glob("*.jsonl")) == ["t01-first.jsonl"]
        assert verdicts(folder)[("t01-first", "a fact is saved")]["verdict"] == "FAIL"
        assert service(folder, "status")["ready"] is True  # Left as it was, for the lead to look at.
        assert "the trial stopped" in (folder / "report" / "record-draft.md").read_text()
        code, outcome = host.run(folder, approve(tmp_path, folder, max_turns=3))
        assert code == 2 and "already run" in outcome["refused"] and len(host.invocations()) == 1
    finally:
        if service(folder, "status")["ready"]:
            service(folder, "stop")


def test_a_failed_host_turn_is_never_retried(tmp_path):
    host = Host(tmp_path, {"t01-first": {"exit": 1, "no_result": True, "actions": []}})
    folder = trial.prepare(small_scenario(tmp_path, "host-failure", stop_on_failure=False), commit=HEAD,
                           root=tmp_path / "trials", model_from=Path(MODEL), offline=True)
    try:
        code, outcome = host.run(folder, approve(tmp_path, folder, max_turns=3))
        assert (code, outcome["status"], outcome["turns_used"]) == (1, "stopped", 1)
        assert "failed (exit 1); it is not retried" in outcome["reason"]
        assert len(host.invocations()) == 1 and not (folder / "logs" / "t02-second.jsonl").exists()
    finally:
        if service(folder, "status")["ready"]:
            service(folder, "stop")


def test_a_wrong_model_or_too_many_turns_is_refused_before_the_host_or_the_memory_is_touched(tmp_path):
    host = Host(tmp_path, {})
    folder = trial.prepare(small_scenario(tmp_path, "refusals", stop_on_failure=False), commit=HEAD,
                           root=tmp_path / "trials", model_from=Path(MODEL), offline=True)
    try:
        for approval, expected in ((approve(tmp_path, folder, max_turns=3, model="opus"), "only sonnet or haiku"),
                                   (approve(tmp_path, folder, max_turns=2), "over the approved limit")):
            code, outcome = host.run(folder, approval)
            assert code == 2 and expected in outcome["refused"]
        assert host.invocations() == [] and not (folder / "run.json").exists() and not (folder / "logs").exists()
    finally:
        if service(folder, "status")["ready"]:
            service(folder, "stop")
