"""Where something was said: the project a coding host's session ran in, as a short label.

A coding host (Claude Code, Codex, WorkBuddy) gives each hook the session's working directory. One person's memory
spans all their projects, so a decision made in one ("local development stays on SQLite") would otherwise reach a
session in another project as if it held there. Each recorded message therefore carries its project's label
(``workspace_ref``, stored in the message's own record and erased with it); a note's places are read each time from
the messages it was written from (the timeline's ``workspaces``). Nothing is hidden because of where it was said: a
line from another project is marked with that project's name and gives way first when a block is full.

The label is the name of the project folder: for a git repository the folder of its main working tree, so every
worktree of a repository has the repository's label; otherwise the session's own folder. Never the path: a path
names the user's account and the layout of their disk. The home directory names the user, so it is no project.
"""
from __future__ import annotations

import os
from pathlib import Path

from .privacy import scrub

LABEL_CHARACTERS = 64
_DROPPED = str.maketrans({character: " " for character in '[]·<>"`'})
# Notes of these kinds are about the user, wherever they were said (``notes.NOTE_TOOL_DESCRIPTION``): another
# project's do not give way before this project's. Other kinds (decisions saved as "other", plans, commitments, untyped
# notes) are what a project's sessions mostly save about the project.
PERSONAL_KINDS = frozenset({"person", "constraint", "preference", "routine", "relationship", "milestone"})


def label(cwd) -> str | None:
    """The project label of a session run in ``cwd`` (as a hook payload gives it); None when there is no usable one."""
    if not isinstance(cwd, str) or not cwd.strip() or len(cwd) > 4096 or "\0" in cwd:
        return None
    try:
        path = Path(os.path.abspath(os.path.expanduser(cwd)))
        home = Path(os.path.abspath(Path.home()))
    except (OSError, RuntimeError, ValueError):
        return None
    folder = _repository(path, home) or path
    if folder == home or folder == Path(folder.anchor) or not folder.name:
        return None
    return _clean(folder.name)


def _repository(path: Path, home: Path) -> Path | None:
    """The folder that names the git repository ``path`` is in, or None outside one. A repository in the home
    directory itself (dotfiles) is not a project: its folder would be the user's name."""
    for folder in (path, *path.parents):
        if folder == home:
            return None
        marker = folder / ".git"
        try:
            if marker.is_dir():
                return folder
            if marker.is_file():
                return _main_tree(folder, marker)
        except OSError:
            return None
    return None


def _main_tree(folder: Path, marker: Path) -> Path:
    """For a linked worktree (``.git`` is a file naming ``.git/worktrees/<name>``), the main repository's folder, read
    from its ``commondir``; for anything else with a ``.git`` file (a submodule), the folder itself."""
    try:
        text = marker.read_text(encoding="utf-8", errors="replace")[:4096].strip()
        if not text.startswith("gitdir:"):
            return folder
        gitdir = Path(text[len("gitdir:"):].strip())
        gitdir = gitdir if gitdir.is_absolute() else folder / gitdir
        common = gitdir / "commondir"
        if not common.is_file():
            return folder
        shared = Path(os.path.abspath(gitdir / common.read_text(encoding="utf-8", errors="replace").strip()))
    except (OSError, ValueError):
        return folder
    return shared.parent if shared.name == ".git" else shared  # A bare repository: its own folder (Tidepool.git).


def _clean(name: str) -> str | None:
    name = " ".join(name.translate(_DROPPED).split())
    if name.endswith(".git") and len(name) > 4:
        name = name[:-4].strip()
    name = name[:LABEL_CHARACTERS].strip()
    # A folder named like a credential or an identity number is not written down at all.
    return name if name and scrub(name) == name else None


def places(item: dict) -> tuple[str, ...]:
    """The projects a timeline item was said in: a message's own, a note's messages' (``workspaces``)."""
    values = item.get("workspaces") if isinstance(item, dict) else None
    if not isinstance(values, list):
        return ()
    return tuple(sorted({value for value in values if isinstance(value, str) and value.strip()}))


def elsewhere(item: dict, current: str | None) -> tuple[str, ...]:
    """The places of an item said only in projects other than ``current``; empty for one said in the current project
    (or in it too) or with no recorded place. With no current project, every recorded place is elsewhere."""
    found = places(item)
    return () if current in found else found


def mark(item: dict, current: str | None) -> str:
    """The qualifier " · in Tidepool" of an item from another project; nothing otherwise."""
    found = elsewhere(item, current)
    return f" · in {' and '.join(found)}" if found else ""


def notice(current: str | None) -> str:
    """The sentence a block adds when one of its lines carries ``mark``."""
    where = "another project" if current else "the project <name>"
    return (f'A line marked "in <name>" comes from work in {where}: what it says about that project holds only '
            "there; what it says about the user holds everywhere.")


def gives_way(item: dict, fields: dict, current: str | None) -> bool:
    """Whether a note gives way before others when the notes block is full: one said in one other project, of a kind
    that is mostly about a project, neither pinned nor written by the user."""
    return (len(elsewhere(item, current)) == 1 and fields.get("kind") not in PERSONAL_KINDS
            and not fields.get("pinned") and item.get("actor_role") != "user")


def first_here(items: list, current: str | None) -> list:
    """``items`` (in their order) with those from another project after the rest, which keep their order too."""
    return [item for item in items if not elsewhere(item, current)] + [item for item in items
                                                                       if elsewhere(item, current)]
