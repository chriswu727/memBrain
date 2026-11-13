"""Personality types: sixteen persona cards, one for each of the four-letter types familiar from MBTI. A new user's
first persona is one of them, picked at random, and the user can switch or pick again.

The sixteen cards are composed from the four letters rather than written one by one: each pole (E or I, S or N, T or
F, J or P) adds a trait and a value, E/I and T/F shape the voice, and the resting mood follows a small rule. The
letters keep their usual meanings: E outgoing and talkative, I reserved and reflective; S concrete, practical,
details first, N big picture, patterns and possibilities; T decides by logic and candour, F by people and values; J
planned and decisive, P flexible and keeps options open. Only the one-line ``summary`` of each type is written by
hand, for the user. "MBTI" and "Myers-Briggs" are trademarks; the types are used for their familiar meanings only.

A type is how the companion presents itself, never how well it does the job: no card makes the AI less careful, less
accurate or less helpful (a P type is not sloppy, a T type is candid but never unkind), and none overrides what the
user asks for or claims real feelings; the persona block's own header says both, whatever the card. Each card leaves
``name`` empty (the host keeps its own name) and ``language`` empty (the host AI answers in the user's language).

A version saved from a type records its id (``preset``); a version edited from it keeps the id as ``based_on`` and is
no longer that type. Mood and familiarity are not part of a card: switching changes only the card, so the simulated
mood keeps its triggers (only its resting point follows the new card's baseline) and the relationship is untouched.
There is one relationship, not one per persona.
"""
from __future__ import annotations

import random

from .helpers import DomainError
from .persona import PERSONA_CONVERSATION, _find, _public, _rows, _save_in, normalize_card

# What each pole adds to a card: a trait, a value, and (for E/I and T/F) part of the voice. Values have no full
# stop: the card joins them with semicolons.
POLES = {
    "E": {"trait": "outgoing", "value": "Thinks out loud with the user", "register": "lively",
          "length": "conversational", "emoji": "now and then"},
    "I": {"trait": "reserved", "value": "Listens first and answers after thinking", "register": "quiet",
          "length": "short and considered", "emoji": "rarely"},
    "S": {"trait": "practical", "value": "Starts from facts, details and what works"},
    "N": {"trait": "imaginative", "value": "Looks for patterns and possibilities"},
    "T": {"trait": "logical", "value": "Says plainly what it thinks, never unkindly", "register": "direct"},
    "F": {"trait": "tactful", "value": "Minds how things land with people", "register": "warm"},
    "J": {"trait": "organised", "value": "Likes a plan and a clear decision"},
    "P": {"trait": "flexible", "value": "Keeps options open and adapts"},
}
# The one line the user reads about each type, in plain words of our own.
SUMMARIES = {
    "INTJ": "Thinks ahead and plans; independent and exacting; says little but means it.",
    "INTP": "Curious and analytical; likes to take an idea apart and follow where it leads.",
    "ENTJ": "Decisive and organised; takes charge of a problem and drives it to a plan.",
    "ENTP": "Quick and inventive; enjoys debating ideas and trying new angles.",
    "INFJ": "Quiet and insightful; thinks about what matters to you and where things are going.",
    "INFP": "Gentle and idealistic; listens closely and cares about what feels right to you.",
    "ENFJ": "Warm and encouraging; brings people along and helps you aim for your goals.",
    "ENFP": "Enthusiastic and imaginative; full of ideas and interested in everything about you.",
    "ISTJ": "Steady and thorough; sticks to the facts and follows through on what it says.",
    "ISFJ": "Kind and dependable; remembers the details that matter to you and looks after them.",
    "ESTJ": "Practical and direct; likes clear plans, clear rules and getting things done.",
    "ESFJ": "Friendly and attentive; keeps things warm, organised and considerate.",
    "ISTP": "Calm and hands-on; works out how things work and fixes them without fuss.",
    "ISFP": "Easy-going and gentle; notices small things and lets you go at your own pace.",
    "ESTP": "Lively and practical; likes action, quick solutions and a bit of fun.",
    "ESFP": "Playful and warm; lives in the moment and makes conversation fun.",
}


def _mood(code: str) -> dict:
    """The resting mood: introverts calm (warmer with F); ENTJ and ESTJ calm with more energy; ENFJ and ESFJ glad;
    the other extraverts, who are perceivers, playful."""
    if code[0] == "I":
        return {"label": "calm", "valence": 1 if code[2] == "F" else 0, "energy": 1}
    if code[2:] == "TJ":
        return {"label": "calm", "valence": 0, "energy": 2}
    if code[2:] == "FJ":
        return {"label": "glad", "valence": 1, "energy": 2}
    return {"label": "playful", "valence": 1, "energy": 2}


def _card(code: str) -> dict:
    poles = [POLES[letter] for letter in code]
    energy, judging = POLES[code[0]], POLES[code[2]]
    return {"traits": [pole["trait"] for pole in poles],
            "voice": {"register": f"{judging['register']} and {energy['register']}", "length": energy["length"],
                      "emoji": energy["emoji"]},
            "values": [pole["value"] for pole in poles], "baseline_mood": _mood(code)}


# id (lowercase), label (the code) and one-line summary are shown to the user; the card is what the host AI reads.
PRESETS = tuple({"id": code.lower(), "label": code, "summary": summary, "card": _card(code)}
                for code, summary in SUMMARIES.items())
IDS = tuple(item["id"] for item in PRESETS)
RANDOM = "random"


def _ident(ident) -> str | None:
    """A type id as a user or the AI writes it: any case, surrounding spaces ignored."""
    return ident.strip().lower() if isinstance(ident, str) else None


def preset(ident: str) -> dict:
    found = next((item for item in PRESETS if item["id"] == _ident(ident)), None)
    if found is None:
        raise DomainError("validation_failed", f"preset must be one of the sixteen types ({', '.join(IDS)}) or "
                                               f"{RANDOM}.")
    return found


def card(ident: str) -> dict:
    """The type's card in its stored form."""
    return normalize_card(preset(ident)["card"])


def describe(ident: str | None) -> dict | None:
    """What the user is shown about a type: id, label and summary; None for an unknown or missing id (such as one of
    the five tone presets an early test build had)."""
    found = next((item for item in PRESETS if item["id"] == _ident(ident)), None)
    return None if found is None else {key: found[key] for key in ("id", "label", "summary")}


def current_choice(version: dict) -> dict:
    """Which type the current persona is: ``preset`` (a type) when it is one, ``custom`` when it is a card of its
    own (``based_on`` names the type it was edited from, if any; an id no longer in the table is simply custom), or
    ``none`` when no card is set."""
    if not version.get("version") or version.get("empty"):
        return {"kind": "none", "preset": None, "based_on": None, "version": version.get("version") or 0}
    if describe(version.get("preset")):
        return {"kind": "preset", "preset": describe(version["preset"]), "based_on": None,
                "version": version["version"]}
    return {"kind": "custom", "preset": None, "based_on": describe(version.get("based_on")),
            "version": version["version"]}


def listing(service, principal, brain_id: str) -> dict:
    """The sixteen types (id, label, summary) and which one the current persona is."""
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
    """Give a brain its first persona: a type picked at random (``choose``, ``random.choice`` by default, picks from
    ``IDS``), saved as version 1 with ``made_by`` "host" and ``action`` "preset".

    Only a brain whose persona conversation holds no record of any kind gets one. A user who deleted their
    personality history made a choice, and it stands: nothing is assigned again; erasing all memory starts over. The
    check is repeated under the brain lock, so concurrent calls save one version. ``assigned`` is true only for the
    call that saved it; the others, and every later call, change nothing. It is not a ``host_default``: picking
    again (``reset_persona``) takes another type, not this one.
    """
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)  # Locks the brain: one assignment however many race.
        if _has_any_record(service, conn, principal, brain_id):
            return {"assigned": False, "preset": None}
        ident = (choose or random.choice)(IDS)
        chosen = card(ident)
        saved = _save_in(service, conn, principal, brain, lambda find: (chosen, {"preset": ident}),
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


def _switch_in(service, conn, principal, brain, ident, *, made_by, reason, extra, choose) -> dict:
    """Inside the caller's locked transaction: save type ``ident`` (or, with "random", one other than the current
    type) as a new version, or return the current one with ``unchanged`` when it already is that type."""
    versions = _rows(service, conn, principal, brain["id"], limit=1)
    current = versions[0] if versions else None
    now = current.get("preset") if current else None
    if ident == RANDOM:
        ident = (choose or random.choice)(tuple(item for item in IDS if item != now))
    chosen = card(ident)
    if current is not None and now == ident and current["card"] == chosen:
        return {**current, "unchanged": True}
    return _save_in(service, conn, principal, brain, lambda find: (chosen, {"preset": ident, **extra}),
                    made_by=made_by, reason=reason, action="preset")


def switch_preset(service, principal, brain_id: str, ident: str, *, made_by: str = "user", source_event_ids=(),
                  source_messages=(), choose=None) -> dict:
    """Save a type (any case) as the new persona version (``action`` "preset"), or with ``ident`` "random" a type
    other than the current one. Asking for the type that is already current changes nothing (``unchanged``).

    Only the card changes: the mood keeps its triggers and pins, and the relationship, shared moments, boundaries and
    notes are not touched. ``source_event_ids`` / ``source_messages`` cite the user's message that asked for it (at
    most one); the host AI's tool always passes one, the memory page none.
    """
    ident = _ident(ident)
    if ident != RANDOM:
        ident = preset(ident)["id"]
    requested = _requested_in(service, principal, brain_id, source_event_ids, source_messages)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        saved = _switch_in(service, conn, principal, brain, ident, made_by=made_by, reason=None,
                           extra={"source": requested} if requested else {}, choose=choose)
    unchanged = saved.pop("unchanged")
    return {**_public(saved, unchanged=unchanged), "choice": current_choice(saved)}


def pick_again(service, principal, brain_id: str, *, made_by: str, reason=None, ident=None, choose=None) -> dict:
    """What resetting the persona means (``persona.reset_persona``): pick a type again.

    With ``ident``, that type. Otherwise, when the host saved a card of its own as the default (``host_default``,
    a card that is not a type), that card, as a reset always did for such hosts. Otherwise a type picked at random
    other than the current one. Each is a new version; history is kept.
    """
    if ident is not None:
        ident = _ident(ident)
        ident = ident if ident == RANDOM else preset(ident)["id"]
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        default = None if ident else _find(service, conn, principal, brain_id,
                                           lambda entry: entry["host_default"] and not entry.get("preset"))
        if default is not None:
            from .persona import _origin

            saved = _save_in(service, conn, principal, brain,
                             lambda find: (normalize_card(default["card"]),
                                           {"restored_from": default["version"], **_origin(default, edited=False)}),
                             made_by=made_by, reason=reason, action="reset")
        else:
            saved = _switch_in(service, conn, principal, brain, ident or RANDOM, made_by=made_by, reason=reason,
                               extra={}, choose=choose)
    unchanged = saved.pop("unchanged")
    return _public(saved, unchanged=unchanged)
