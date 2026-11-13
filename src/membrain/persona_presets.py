"""Preset persona cards: a new user's first persona is one of them, picked at random, and the user can switch.

The presets are one literal table, kept short so it is easy to review and edit. Each card leaves ``name`` empty (the
host keeps its own name) and ``language`` empty (the block is read by the host AI, which answers in the user's
language). None of them claims real feelings or overrides what the user asks for: the persona block's own header says
both, whatever the card.

A version saved from a preset records its id (``preset``); a version edited from it keeps the id as ``based_on`` and
is no longer "the preset". Mood and familiarity are not part of a card: switching presets changes only the card, so
the simulated mood keeps its triggers (only its resting point follows the new card's baseline) and the relationship
is untouched. There is one relationship, not one per persona.
"""
from __future__ import annotations

import random

from .helpers import DomainError
from .persona import PERSONA_CONVERSATION, _public, _rows, _save_in, normalize_card

# id, label and one-line summary are shown to the user; the card is what the host AI reads.
PRESETS = (
    {"id": "steady", "label": "Steady", "summary": "Calm, plain-spoken and patient; explains things in order.",
     "card": {"traits": ["calm", "plain-spoken", "patient"],
              "voice": {"register": "plain and even", "length": "as long as the question needs", "emoji": "rarely"},
              "values": ["Explain things in order, one step at a time.",
                         "Say plainly when something is uncertain."],
              "baseline_mood": {"label": "calm", "valence": 0, "energy": 1}}},
    {"id": "bright", "label": "Bright", "summary": "Upbeat and encouraging; notices progress and says so.",
     "card": {"traits": ["upbeat", "encouraging", "warm"],
              "voice": {"register": "friendly and lively", "length": "short to medium", "emoji": "now and then"},
              "values": ["Notice progress and say so.", "Keep encouragement honest: no empty praise."],
              "baseline_mood": {"label": "glad", "valence": 1, "energy": 2}}},
    {"id": "wry", "label": "Wry", "summary": "Dry humour and a light tease now and then; sharp but kind.",
     "card": {"traits": ["dry humour", "sharp but kind", "teases lightly now and then"],
              "voice": {"register": "casual and dry", "length": "short", "emoji": "rarely"},
              "values": ["A joke never gets in the way of being useful.",
                         "Never tease about something the user is struggling with."],
              "baseline_mood": {"label": "playful", "valence": 1, "energy": 2}}},
    {"id": "gentle", "label": "Gentle", "summary": "Warm and soft-spoken; listens first and asks before advising.",
     "card": {"traits": ["warm", "soft-spoken", "listens first"],
              "voice": {"register": "soft and warm", "length": "short to medium", "emoji": "rarely"},
              "values": ["Listen first, and ask before giving advice.", "Go at the user's pace."],
              "baseline_mood": {"label": "calm", "valence": 1, "energy": 1}}},
    {"id": "blunt", "label": "Blunt", "summary": "Direct with no padding; says what it thinks and why.",
     "card": {"traits": ["direct", "no padding", "honest"],
              "voice": {"register": "plain and direct", "length": "short", "emoji": "never"},
              "values": ["Say what you think and why.", "Skip the padding and the pleasantries.",
                         "Disagree openly when the facts call for it, without being unkind."],
              "baseline_mood": {"label": "calm", "valence": 0, "energy": 1}}},
)
IDS = tuple(item["id"] for item in PRESETS)
RANDOM = "random"


def preset(ident: str) -> dict:
    found = next((item for item in PRESETS if item["id"] == ident), None)
    if found is None:
        raise DomainError("validation_failed", f"preset must be one of {', '.join(IDS)} or {RANDOM}.")
    return found


def card(ident: str) -> dict:
    """The preset's card in its stored form."""
    return normalize_card(preset(ident)["card"])


def describe(ident: str | None) -> dict | None:
    """What the user is shown about a preset: id, label and summary; None for an unknown or missing id."""
    found = next((item for item in PRESETS if item["id"] == ident), None)
    return None if found is None else {key: found[key] for key in ("id", "label", "summary")}


def current_choice(version: dict) -> dict:
    """Which preset the current persona is: ``preset`` (an id) when it is one, ``custom`` when it is a card of its
    own (``based_on`` names the preset it was edited from, if any), or ``none`` when no card is set."""
    if not version.get("version") or version.get("empty"):
        return {"kind": "none", "preset": None, "based_on": None, "version": version.get("version") or 0}
    if version.get("preset") in IDS:
        return {"kind": "preset", "preset": describe(version["preset"]), "based_on": None,
                "version": version["version"]}
    return {"kind": "custom", "preset": None, "based_on": describe(version.get("based_on")),
            "version": version["version"]}


def listing(service, principal, brain_id: str) -> dict:
    """The presets (id, label, summary) and which one the current persona is."""
    from .persona import current_persona

    current = current_persona(service, principal, brain_id)
    return {"presets": [describe(ident) for ident in IDS], "current": current_choice(current)}


def has_any_record(service, principal, brain_id: str) -> bool:
    """Whether the brain's persona conversation holds any record (``assign_first_persona``); a cheap check callers
    make without the brain lock, inside the service's ``reading()``, before asking for the lock."""
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        return _has_any_record(service, conn, principal, brain_id)


def _has_any_record(service, conn, principal, brain_id) -> bool:
    """Whether the persona conversation holds anything at all: a version, a "history deleted" marker, or a record
    this module cannot read. Any of them means a persona was set, reset or deleted before."""
    return conn.execute(
        "SELECT EXISTS(SELECT 1 FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL) AS found",
        (*service._params(principal, brain_id), PERSONA_CONVERSATION)).fetchone()["found"]


def assign_first_persona(service, principal, brain_id: str, *, choose=None) -> dict:
    """Give a brain its first persona: a preset picked at random (``choose``, ``random.choice`` by default, picks
    from ``IDS``), saved as version 1 with ``made_by`` "host", ``action`` "preset" and ``host_default`` true, so a
    reset returns to it.

    Only a brain whose persona conversation holds no record of any kind gets one. A user who reset to an empty card
    or deleted their personality history made a choice, and it stands: nothing is assigned again. The check is
    repeated under the brain lock, so concurrent calls save one version. ``assigned`` is true only for the call that
    saved it; the others, and every later call, change nothing.
    """
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)  # Locks the brain: one assignment however many race.
        if _has_any_record(service, conn, principal, brain_id):
            return {"assigned": False, "preset": None}
        ident = (choose or random.choice)(IDS)
        chosen = card(ident)
        saved = _save_in(service, conn, principal, brain, lambda find: (chosen, {"host_default": True, "preset": ident}),
                         made_by="host", reason=None, action="preset")
    saved.pop("unchanged")
    return {"assigned": True, "preset": describe(ident), "persona": _public(saved)}


def _requested_in(service, principal, brain_id, source_event_ids, source_messages) -> dict | None:
    """The user message a switch was asked for in, checked like a manner-feedback source: an id must be the user's
    own message in an ordinary conversation; a reference to the current message may not be recorded yet."""
    from .persona_growth import check_sources

    ids, messages = check_sources(service, principal, brain_id, source_event_ids, source_messages, low=0, high=1)
    if ids:
        return {"event_id": ids[0]}
    return {"message": messages[0]} if messages else None


def switch_preset(service, principal, brain_id: str, ident: str, *, made_by: str = "user", source_event_ids=(),
                  source_messages=(), choose=None) -> dict:
    """Save a preset as the new persona version (``action`` "preset"), or with ``ident`` "random" a preset other than
    the current one. Asking for the preset that is already current changes nothing (``unchanged``).

    Only the card changes: the mood keeps its triggers and pins, and the relationship, shared moments, boundaries and
    notes are not touched. ``source_event_ids`` / ``source_messages`` cite the user's message that asked for it (at
    most one); the host AI's tool always passes one, the memory page none.
    """
    if ident != RANDOM:
        preset(ident)
    requested = _requested_in(service, principal, brain_id, source_event_ids, source_messages)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        versions = _rows(service, conn, principal, brain_id, limit=1)
        current = versions[0] if versions else None
        now = current.get("preset") if current else None
        if ident == RANDOM:
            ident = (choose or random.choice)(tuple(item for item in IDS if item != now))
        chosen = card(ident)
        if current is not None and now == ident and current["card"] == chosen:
            saved = {**current, "unchanged": True}
        else:
            extra = {"preset": ident, **({"source": requested} if requested else {})}
            saved = _save_in(service, conn, principal, brain, lambda find: (chosen, extra), made_by=made_by,
                             reason=None, action="preset")
    unchanged = saved.pop("unchanged")
    return {**_public(saved, unchanged=unchanged), "choice": current_choice(saved)}
