"""One user, two projects: what a new session in each project, and in a directory never seen before, receives.

The scenario (``two_project_world``): in project Tidepool PostgreSQL is decided on day 1 and corrected on day 3 to
"only the server uses PostgreSQL; local stays SQLite", in a session run from a git worktree of Tidepool; in project
Harbor the user said on day 2 "we use MySQL here, locally too", in Harbor's ``app`` subdirectory; personal facts
(pnpm over npm, a laptop low on disk space, "call me Sam") were said in one project or the other. On day 8 the same
words, "finish the local install", open a new session in Harbor, in Tidepool and in a scratch directory.

Before this change (measured on the start commit, ``evaluations/workspaces-2026-11-19.md``) nothing recorded where
anything was said: a Harbor session was handed Tidepool's "local development stays on SQLite" as an unmarked note,
newer than Harbor's own MySQL note and saying it replaced an earlier one, and a search for "local database" in
Harbor listed Tidepool's note first. Now each message keeps its project's label, a note takes its project from the
messages it was written from, and every block marks a line from another project with that project's name. Nothing
is hidden: every note and message still reaches every session, other projects' only giving way first when a block
is full.

Played through the plugin's hook functions with the payloads Claude Code sends (``cwd`` included) and the plugin's
MCP server started in the session's directory, on a real installation and the scenario clock, with no model.
"""
import json
from pathlib import Path

import pytest
from resume_correction_world import CORRECTION, DECISION, DISK, NOTE_PNPM, PNPM
from two_project_world import (
    CONVERSATIONS,
    CSV,
    DAY8,
    HARBOR_DB,
    NAME,
    NOTES,
    QUERIES,
    built_world,
    filler_conversations,
    line_with,
    lines,
)

from membrain import workspace

pytestmark = pytest.mark.integration

CLAUDE_CODE_HOOK_LIMIT = 10_000
LABELS = {"tidepool": "Tidepool", "tidepool-worktree": "Tidepool", "harbor": "Harbor"}
HERE = {"harbor": "Harbor", "tidepool": "Tidepool", "scratch": "scratch"}


@pytest.fixture(scope="module")
def named(tmp_path_factory):
    with built_world(tmp_path_factory, "diligent", named=True) as world:
        yield world


@pytest.fixture(scope="module")
def unnamed(tmp_path_factory):
    with built_world(tmp_path_factory, "diligent", named=False, busy=True, model=True) as world:
        yield world


@pytest.fixture(scope="module")
def lazy(tmp_path_factory):
    with built_world(tmp_path_factory, "lazy", named=False, busy=True, model=True) as world:
        yield world


WORLDS = ["named", "unnamed", "lazy"]
DILIGENT = ["named", "unnamed"]


def note_text(world, key):
    entry = next(entry for entry in NOTES if entry[0] == key)
    return entry[2] if world.named else entry[3]


def conversations(world):
    return CONVERSATIONS + (filler_conversations() if world.busy else [])


# What is stored ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", WORLDS)
def test_each_message_and_reply_keeps_the_label_of_its_project_even_from_a_worktree_or_subdirectory(request, name):
    world = request.getfixturevalue(name)
    stored = world.messages()
    for place, _session, _day, turns in conversations(world):
        for text, reply in turns:
            assert stored[text].get("workspaces") == [LABELS[place]], text
            assert stored[reply].get("workspaces") == [LABELS[place]], reply


@pytest.mark.parametrize("name", WORLDS)
def test_no_path_of_any_session_is_recorded_anywhere_in_the_installation(request, name):
    """The hooks receive the absolute working directory (the user's account name and their client's project in it);
    neither the path nor its parent folders are written anywhere: not in the database files, the queue, the session
    state or the logs. Only the folder's own name is, as the label."""
    world = request.getfixturevalue(name)
    root = str(Path(world.places["scratch"]).parent).encode()
    found = []
    for path in Path(world.directory).rglob("*"):
        if path.is_file() and "models" not in path.parts:
            if root in path.read_bytes():
                found.append(str(path.relative_to(world.directory)))
    assert found == []


def test_an_export_carries_each_messages_label_and_no_path(lazy):
    with lazy.client() as client:
        archive = client.download_archive(client.export()["result"]["archive_id"])
    events = archive["document"]["events"]
    labels = {event["observed"].get("workspace_ref") for event in events}
    assert {"Tidepool", "Harbor"} <= labels
    assert str(Path(lazy.places["scratch"]).parent) not in json.dumps(archive)


@pytest.mark.parametrize("name", DILIGENT)
def test_a_note_takes_its_project_from_the_messages_it_was_written_from(request, name):
    world = request.getfixturevalue(name)
    places = {item["event_id"]: item.get("workspaces") for item in world.notes()}
    expected = {"corrected": ["Tidepool"], "harbor_db": ["Harbor"], "pnpm": ["Tidepool"], "inferred": ["Harbor"],
                "name": ["Harbor"]}
    assert {key: places[world.note_ids[key]] for key in expected} == expected


# The day-8 sessions: notes --------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", DILIGENT)
@pytest.mark.parametrize("place", DAY8)
def test_every_current_note_reaches_every_session_whatever_project_it_came_from(request, name, place):
    world = request.getfixturevalue(name)
    opening = world.captures["day8"][place]["session_start"]
    for key in ("corrected", "harbor_db", "pnpm", "inferred", "name"):
        assert line_with(opening, "membrain-notes", note_text(world, key)), (place, key)


@pytest.mark.parametrize("name", DILIGENT)
def test_in_harbor_tidepools_database_note_is_marked_as_tidepools_and_harbors_own_is_not(request, name):
    world = request.getfixturevalue(name)
    opening = world.captures["day8"]["harbor"]["session_start"]
    tidepool = line_with(opening, "membrain-notes", note_text(world, "corrected"))
    harbor = line_with(opening, "membrain-notes", note_text(world, "harbor_db"))
    assert tidepool.startswith("- [2026-11-04 · in Tidepool] ")
    assert harbor.startswith("- [2026-11-03] ")
    assert workspace.notice("Harbor") in opening


@pytest.mark.parametrize("name", DILIGENT)
def test_in_tidepool_harbors_database_note_is_marked_and_its_own_correction_is_not(request, name):
    world = request.getfixturevalue(name)
    opening = world.captures["day8"]["tidepool"]["session_start"]
    assert line_with(opening, "membrain-notes", note_text(world, "corrected")).startswith("- [2026-11-04] ")
    assert line_with(opening, "membrain-notes", note_text(world, "harbor_db")).startswith("- [2026-11-03 · in Harbor] ")


@pytest.mark.parametrize("name", DILIGENT)
def test_personal_notes_carry_where_they_were_said_and_the_header_says_they_hold_everywhere(request, name):
    """pnpm was noted in Tidepool, the name and the disk in Harbor. Each is marked in the other project (the truth
    about where it was said) and the sentence the header adds says that what a line says about the user holds
    everywhere. The mark does not decide anything: it is the host's to read."""
    world = request.getfixturevalue(name)
    harbor = world.captures["day8"]["harbor"]["session_start"]
    tidepool = world.captures["day8"]["tidepool"]["session_start"]
    assert "· in Tidepool] " in line_with(harbor, "membrain-notes", NOTE_PNPM)
    assert "· in" not in line_with(harbor, "membrain-notes", "Wants to be called Sam.")
    assert "· in Harbor] " in line_with(tidepool, "membrain-notes", "Wants to be called Sam.")
    assert "· in Harbor] " in line_with(tidepool, "membrain-notes", "Laptop is low on disk space")
    assert "what it says about the user holds everywhere" in tidepool


@pytest.mark.parametrize("name", DILIGENT)
def test_in_a_directory_never_seen_before_every_note_names_its_project(request, name):
    world = request.getfixturevalue(name)
    opening = world.captures["day8"]["scratch"]["session_start"]
    for key, label in (("corrected", "Tidepool"), ("harbor_db", "Harbor"), ("pnpm", "Tidepool"), ("name", "Harbor")):
        assert f"· in {label}] " in line_with(opening, "membrain-notes", note_text(world, key)), key
    assert workspace.notice("scratch") in opening


# The day-8 sessions: history, prompt recall, search -------------------------------------------------------------

def test_with_a_short_history_every_message_is_shown_and_those_of_the_other_project_are_marked(named):
    harbor = named.captures["day8"]["harbor"]["session_start"]
    tidepool = named.captures["day8"]["tidepool"]["session_start"]
    scratch = named.captures["day8"]["scratch"]["session_start"]
    for text in (DECISION, CORRECTION, PNPM[1]):
        assert "· in Tidepool" in line_with(harbor, "membrain-history", text), text
        assert "· in" not in line_with(tidepool, "membrain-history", text), text  # The correction: from a worktree.
        assert "· in Tidepool" in line_with(scratch, "membrain-history", text), text
    for text in (HARBOR_DB, NAME, DISK, CSV):
        assert "· in" not in line_with(harbor, "membrain-history", text), text
        assert "· in Harbor" in line_with(tidepool, "membrain-history", text), text
    assert "Everything this user wrote in earlier sessions" in harbor


@pytest.mark.parametrize("name", ["unnamed", "lazy"])
def test_after_a_busy_week_harbors_history_keeps_harbors_messages_before_tidepools_newer_ones(request, name):
    """A busy week does not fit the history block. Before, it held the most recent messages whatever their project
    (Tidepool's day-7 talk), and none of Harbor's database message; now Harbor's come first and Tidepool's fill the
    rest, marked."""
    world = request.getfixturevalue(name)
    opening = world.captures["day8"]["harbor"]["session_start"]
    harbor = [text for place, _s, _d, turns in conversations(world) if place == "harbor" for text, _r in turns]
    shown = lines(opening, "membrain-history")
    assert all(line_with(opening, "membrain-history", text) for text in harbor)
    assert len(shown) > len(harbor)  # Tidepool's messages too, as room allows.
    assert all("· in Tidepool" in line for line in shown if not any(text in line for text in harbor))
    assert "the most recent of this project, then of other projects as room allowed" in opening


@pytest.mark.parametrize("name", ["unnamed", "lazy"])
def test_the_prompt_hook_marks_what_it_recalls_from_the_other_project(request, name):
    world = request.getfixturevalue(name)
    prompt = world.captures["day8"]["harbor"]["user_prompt"]
    assert "· in Tidepool" in line_with(prompt, "membrain-memory", CORRECTION)
    assert "· in" not in line_with(prompt, "membrain-memory", HARBOR_DB)
    assert workspace.notice("Harbor") in prompt
    tidepool = world.captures["day8"]["tidepool"]["user_prompt"]
    assert "· in" not in line_with(tidepool, "membrain-memory", CORRECTION)


@pytest.mark.parametrize("name", WORLDS)
@pytest.mark.parametrize("query", QUERIES)
def test_a_search_reaches_both_projects_and_marks_the_other_one(request, name, query):
    world = request.getfixturevalue(name)
    harbor = world.captures["day8"]["harbor"]["recall"][query]
    tidepool = world.captures["day8"]["tidepool"]["recall"][query]
    assert "· in Tidepool" in line_with(harbor, "membrain-memory", CORRECTION)
    assert "· in" not in line_with(harbor, "membrain-memory", HARBOR_DB)
    assert "· in" not in line_with(tidepool, "membrain-memory", CORRECTION)
    assert "· in Harbor" in line_with(tidepool, "membrain-memory", HARBOR_DB)
    if world.host_kind == "diligent":
        assert line_with(harbor, "membrain-memory", note_text(world, "corrected")).startswith(
            "- [2026-11-04 · in Tidepool · note] ")
        assert line_with(harbor, "membrain-memory", note_text(world, "harbor_db")).startswith("- [2026-11-03 · note] ")
        # Both match the search's words alike: the session's own project's note comes first.
        for text, own, other in ((harbor, "harbor_db", "corrected"), (tidepool, "corrected", "harbor_db")):
            found = lines(text, "membrain-memory")
            assert found.index(line_with(text, "membrain-memory", note_text(world, own))) < found.index(
                line_with(text, "membrain-memory", note_text(world, other)))


@pytest.mark.parametrize("name", WORLDS)
def test_every_hook_stays_within_claude_codes_limit(request, name):
    world = request.getfixturevalue(name)
    for place in DAY8:
        for part in ("session_start", "user_prompt"):
            assert len(world.captures["day8"][place][part] or "") <= CLAUDE_CODE_HOOK_LIMIT, (place, part)


def test_erasing_a_message_takes_its_label_with_it(lazy):
    """Last in this module: it changes the lazy world. The label is part of the message's record, so erasing the
    message leaves nothing of it; an export holds no event for it, only its tombstone."""
    event_id = lazy.messages()[HARBOR_DB]["event_id"]
    with lazy.client() as client:
        generation = client.dashboard()["brain"]["scope_generation"]
        client.forget([event_id], kind="events", mode="erase_content", expected_scope_generation=generation,
                      conversation_id="harbor-day2", branch_id="main")
        archive = client.download_archive(client.export()["result"]["archive_id"])
    document = archive["document"]
    assert event_id not in {event["event_id"] for event in document["events"]}
    assert event_id in {stone["object_id"] for stone in document["tombstones"]}
    assert HARBOR_DB not in lazy.messages()
