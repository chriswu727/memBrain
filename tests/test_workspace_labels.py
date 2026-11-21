"""The project label of a session and how blocks mark what was said in another project (``membrain.workspace``).

No service: labels from real directory layouts (``git init``, ``git worktree add``), and the blocks rendered from
timeline items as the service returns them. The behaviour on a real installation, through the plugin's hooks, is
in ``test_two_project_world.py``.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from membrain import host, notes, workspace

HARBOR, TIDEPOOL = "Harbor", "Tidepool"


def git(*arguments, cwd):
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c",
                    "init.defaultBranch=main", *arguments], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home" / "sam"
    folder.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


def test_a_repository_is_labelled_by_its_folder_from_any_subdirectory_and_any_worktree(home):
    assert shutil.which("git"), "git is needed to build the layouts this test reads"
    repository = home / "code" / TIDEPOOL
    (repository / "server" / "db").mkdir(parents=True)
    git("init", cwd=repository)
    git("commit", "--allow-empty", "-m", "start", cwd=repository)
    git("worktree", "add", str(home / "elsewhere" / "fix-db"), cwd=repository)
    assert workspace.label(str(repository)) == TIDEPOOL
    assert workspace.label(str(repository / "server" / "db")) == TIDEPOOL
    # A worktree is the same project, wherever it lives and whatever its folder is called.
    assert workspace.label(str(home / "elsewhere" / "fix-db")) == TIDEPOOL


def test_without_a_repository_the_session_folder_is_the_label_and_the_home_folder_is_none(home, tmp_path):
    (home / "notes" / "scratch").mkdir(parents=True)
    assert workspace.label(str(home / "notes" / "scratch")) == "scratch"
    assert workspace.label(str(home)) is None  # The home folder's name is the user's.
    assert workspace.label(str(Path(home.anchor))) is None
    assert workspace.label("") is None and workspace.label(None) is None and workspace.label(42) is None


def test_a_repository_in_the_home_folder_itself_does_not_name_the_user(home):
    (home / ".git").mkdir()  # Dotfiles kept in git.
    (home / "Documents" / "taxes").mkdir(parents=True)
    assert workspace.label(str(home / "Documents" / "taxes")) == "taxes"


def test_a_submodule_and_a_bare_repository_keep_their_own_names(home):
    module = home / "code" / "Harbor" / "vendor" / "charts"
    module.mkdir(parents=True)
    (home / "code" / "Harbor" / ".git" / "modules" / "charts").mkdir(parents=True)
    (module / ".git").write_text("gitdir: ../../.git/modules/charts\n")
    assert workspace.label(str(module)) == "charts"
    bare = home / "srv" / "Tidepool.git"
    linked = bare / "worktrees" / "main"
    linked.mkdir(parents=True)
    (linked / "commondir").write_text("../..\n")
    (home / "srv" / "checkout").mkdir()
    (home / "srv" / "checkout" / ".git").write_text(f"gitdir: {linked}\n")
    assert workspace.label(str(home / "srv" / "checkout")) == TIDEPOOL


def test_a_label_is_short_plain_text_and_never_something_that_looks_private(home):
    for name, expected in [("my [client] · app", "my client app"), ("x" * 80, "x" * 64),
                           ("tok sk-abcdefghijklmnopqrstuvwxyz0123456789", None)]:
        (home / "code" / name).mkdir(parents=True)
        assert workspace.label(str(home / "code" / name)) == expected


# Blocks ---------------------------------------------------------------------------------------------------------

def note(event_id, text, day, places=(), role="assistant"):
    item = {"event_id": event_id, "text": text, "recorded_at": f"2026-11-0{day}T10:00:00Z", "actor_role": role}
    return {**item, "workspaces": list(places)} if places else item


SAVED = {"items": [  # Newest first, as the timeline gives them.
    note("sam", "[preference] Wants to be called Sam.", 3, [HARBOR]),
    note("tide", "[other] Database: PostgreSQL on the server only; local development stays on SQLite.", 4, [TIDEPOOL]),
    note("harb", "[other] Database: MySQL everywhere, local development included.", 3, [HARBOR]),
    note("pnpm", "[preference] Prefers pnpm over npm for frontend packages.", 2, [TIDEPOOL]),
    note("old", "Has a cat called Miso.", 1),
], "complete": True}


def lines(block):
    return {line.split("(id: ")[1].rstrip(")"): line for line in block.splitlines() if line.startswith("- [")}


def test_notes_from_another_project_are_marked_with_it_and_the_header_says_what_that_means():
    block = notes.render_notes(SAVED, workspace=HARBOR)
    found = lines(block)
    assert found["tide"].startswith("- [2026-11-04 · in Tidepool] Database: PostgreSQL")
    assert found["pnpm"].startswith("- [2026-11-02 · in Tidepool] Prefers pnpm")
    assert found["harb"].startswith("- [2026-11-03] ") and found["sam"].startswith("- [2026-11-03] ")
    assert found["old"].startswith("- [2026-11-01] ")  # No recorded project: shown as before.
    assert workspace.notice(HARBOR) in block and block.count("in <name>") == 1
    assert "holds everywhere" in workspace.notice(HARBOR)


def test_without_any_mark_the_notes_block_is_what_it_was():
    unlabelled = {**SAVED, "items": [{key: value for key, value in item.items() if key != "workspaces"}
                                     for item in SAVED["items"]]}
    assert notes.render_notes(unlabelled, workspace=HARBOR) == notes.render_notes(unlabelled)
    assert "in <name>" not in notes.render_notes(unlabelled, workspace=HARBOR)
    only_here = {**SAVED, "items": [item for item in SAVED["items"] if item.get("workspaces") != [TIDEPOOL]]}
    assert "in <name>" not in notes.render_notes(only_here, workspace=HARBOR)


def test_with_no_current_project_every_recorded_place_is_named():
    block = notes.render_notes(SAVED)  # A chat host, or a session in the home folder.
    assert workspace.notice(None) in block and "comes from work in the project <name>" in block
    found = lines(block)
    assert " · in Harbor] " in found["harb"] and " · in Tidepool] " in found["tide"] and "· in" not in found["old"]


def test_another_projects_project_note_gives_way_first_but_its_personal_notes_do_not():
    parsed = notes._parsed(SAVED)
    ranks = {entry[0]["event_id"]: notes._priority(entry, HARBOR) for entry in parsed}
    assert ranks == {"old": 4, "pnpm": 4, "harb": 4, "tide": 9, "sam": 4}
    # Pinned, written by the user, or said in two projects (one of them this one, or not): never demoted.
    for item in (note("p", "[other · pinned] Pinned.", 1, [TIDEPOOL]), note("u", "Typed.", 1, [TIDEPOOL], role="user"),
                 note("two", "[other] Both.", 1, [TIDEPOOL, "Kelp"])):
        assert notes._priority(notes._parsed({"items": [item]})[0], HARBOR) < 5
    # In a budget for all but one, Tidepool's database note is the one left out: nothing else is.
    sizes = {entry[0]["event_id"]: len(notes._line(*entry, place=workspace.mark(entry[0], HARBOR))) + 35
             for entry in parsed}
    chosen, omitted = notes.select_notes(parsed, sum(sizes.values()) - 1, HARBOR)
    assert omitted == 1 and {entry[0]["event_id"] for entry in chosen} == {"old", "pnpm", "harb", "sam"}
    # In Tidepool the same budget leaves out one of Harbor's notes instead, never its own.
    chosen, _ = notes.select_notes(parsed, sum(sizes.values()) - 1, TIDEPOOL)
    assert "tide" in {entry[0]["event_id"] for entry in chosen}


def test_a_plan_from_another_project_says_so_in_the_coming_up_block():
    plan = {"items": [note("plan", "[plan · intended] Migrate the users table.", 1, [TIDEPOOL])]}
    assert "Migrate the users table. (in Tidepool) (id: plan)" in notes.render_coming_up(plan, workspace=HARBOR)
    assert "Migrate the users table. (id: plan)" in notes.render_coming_up(plan, workspace=TIDEPOOL)


def message(event_id, text, sequence, places=()):
    item = {"event_id": event_id, "text": text, "sequence": sequence, "actor_role": "user",
            "recorded_at": f"2026-11-0{min(sequence, 9)}T10:00:00Z"}
    return {**item, "workspaces": list(places)} if places else item


class Timeline:
    def __init__(self, items):
        self.items = items

    def timeline(self, **options):
        return {"items": sorted(self.items, key=lambda item: -item["sequence"]), "complete": True}


def history_lines(block):
    return [line for line in block.splitlines() if line.startswith("- [")]


def test_the_history_keeps_this_projects_messages_before_newer_ones_from_another_project():
    items = [message("h1", "Harbor uses MySQL locally too.", 1, [HARBOR]),
             message("t1", "Tidepool: only the server uses PostgreSQL; local stays SQLite.", 2, [TIDEPOOL]),
             message("t2", "Tidepool talk about the landing page.", 3, [TIDEPOOL]),
             message("h2", "Harbor CSV export please.", 4, [HARBOR])]
    # Room for both of Harbor's messages and Tidepool's newest, marked.
    budget = sum(len(items[index]["text"]) + host.HISTORY_LINE_OVERHEAD for index in (0, 2, 3)) + len(" · in Tidepool")
    block, complete = host._history(Timeline(items), "now", budget, workspace=HARBOR)
    assert not complete
    assert history_lines(block) == [
        "- [2026-11-01] Harbor uses MySQL locally too.",
        "- [2026-11-03 · in Tidepool] Tidepool talk about the landing page.",
        "- [2026-11-04] Harbor CSV export please."]
    assert "3 messages this user wrote in earlier sessions: the most recent of this project, then of other " \
           "projects as room allowed, oldest first." in block
    assert workspace.notice(HARBOR) in block
    # By recency alone (no recorded project) the newest messages are kept, as before.
    plain = [{key: value for key, value in item.items() if key != "workspaces"} for item in items]
    block, _ = host._history(Timeline(plain), "now", budget, workspace=HARBOR)
    assert "The 2 most recent messages" in block and "in <name>" not in block
    assert history_lines(block) == ["- [2026-11-03] Tidepool talk about the landing page.",
                                    "- [2026-11-04] Harbor CSV export please."]
