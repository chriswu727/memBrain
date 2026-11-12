"""The companion switch: whether the persona, simulated-mood and familiarity blocks reach the host AI.

The companion layer is on by default. Turning it off stops the ``<membrain-persona>`` and
``<membrain-companion-mood>`` blocks and the familiarity part of ``<membrain-relationship>`` at session start and at
prompt time, for every host that uses this installation (Claude Code, Codex, WorkBuddy, CodeBuddy, OpenClaw, Hermes,
chat bots and the proxy all render context through ``membrain.host``). It deletes nothing: the persona versions,
mood settings and relationship records stay in memory, and turning it on again shows them as before. Boundaries and
their recall filter, feelings on note lines, commitments, notes, history, recall and consolidation do not depend on
it.

The setting lives next to the local pause files, in the installation's ``plugin`` directory: ``companion.json`` for
the installation's owner, ``companion-users/<brain>.json`` for one person of a multi-user host. A role-play follows
the setting of the person behind it, as a pause does. A file exists only while the layer is off; one that cannot be
read counts as off, because nothing else writes it. Reading it needs no service, so hooks skip the persona and mood
reads altogether while it is off.
"""
from __future__ import annotations

import time
from pathlib import Path

TOOL_DESCRIPTION = (
    "Turn memBrain's companion layer (the persona card, the simulated mood and the familiarity of the relationship) "
    "off or on, only when the user asks for that: enabled=false turns it off, enabled=true turns it on, no argument "
    "reports whether it is on. It changes what later context shows, for every host on this computer, and deletes "
    "nothing: turning it on again brings back the same persona, mood and relationship. Boundaries, feelings on "
    "notes, commitments and recall keep working either way. Tell the user the returned state in a few words.")


def _path(directory: Path, user_id: str | None, *, create: bool = True) -> Path:
    from . import host

    root = host.state_directory(directory) if create else Path(directory) / "plugin"
    person = host.real_life_user(user_id)
    if person is None:
        return root / "companion.json"
    folder = root / "companion-users"
    if create:
        folder.mkdir(mode=0o700, exist_ok=True)
    return folder / (host.user_brain_id(person) + ".json")


def enabled(directory: Path, user_id: str | None = None) -> bool:
    """Whether the companion layer is on for this person (``None`` is the installation's owner)."""
    import json

    try:
        state = json.loads(_path(directory, user_id, create=False).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    return isinstance(state, dict) and state.get("enabled") is True


def status(directory: Path, user_id: str | None = None) -> dict:
    from . import host

    on = enabled(directory, user_id)
    return {"companion": "on" if on else "off", "enabled": on,
            "applies_to": "the installation's owner" if host.real_life_user(user_id) is None else "this user",
            "note": ("The persona, simulated mood and familiarity are shown to the agent." if on else
                     "The persona, simulated mood and familiarity are not shown to the agent; nothing was deleted. "
                     "Boundaries, feelings on notes, commitments and recall still work.")}


def set_enabled(directory: Path, value: bool, user_id: str | None = None) -> dict:
    """Turn the companion layer on or off for this person; returns the new state. Nothing in memory changes."""
    from . import host
    from .local_profile import profile_lock

    if type(value) is not bool:
        raise ValueError("The companion switch takes true (on) or false (off).")
    path = _path(directory, user_id)
    with profile_lock(host.state_directory(directory) / "session-state-lock", timeout=5):
        if value:
            path.unlink(missing_ok=True)
        else:
            host._write_state(path, {"enabled": False, "since": time.time()})
    host.log(directory, f"companion layer turned {'on' if value else 'off'}")
    return status(directory, user_id)


def forget(directory: Path, user_id: str | None) -> None:
    """Drop the person's setting when everything memBrain holds for them is erased."""
    _path(directory, user_id, create=False).unlink(missing_ok=True)
