"""The companion's persona card: how the companion presents itself, versioned and kept apart from user memory.

Each saved card is one event in a reserved conversation, so audited deletion, export and erasure treat it like any
other record and no table is needed. Versions are stored with the ``system`` role: they are configuration set by the
host or the user, not something anyone said, so they are never extracted into recalled memories, shown as history or
counted as messages. The current card is the newest version that has not been deleted. Restoring and resetting save
a new version, so history is kept until the user deletes it.

Style learned from the user (length, humour, formality, language) stays in ``preference`` notes; nothing here copies
it into the card.
"""
from __future__ import annotations

import functools
import json

from .helpers import DomainError, uid
from .privacy import neutralize, scrub

PERSONA_CONVERSATION = "membrain-persona"
PERSONA_PRODUCER = "membrain-persona"
PERSONA_CHARACTERS = 1200  # The rendered card; the block's fixed header comes on top.
REASON_CHARACTERS = 200
MADE_BY = ("host", "user", "feedback")  # "feedback" is reserved for accepted feedback proposals (P2).
VOICE_FIELDS = (("register", "register"), ("length", "length"), ("emoji", "emoji"), ("language", "language"))
MAX_VERSIONS = 200
EMPTY_CARD = {"name": "", "traits": [], "voice": {name: "" for name, _ in VOICE_FIELDS}, "values": [],
              "boundaries": [], "baseline_mood": None}


@functools.cache
def card_model():
    """The strict schema of a card. Built on first use, so hooks that only render a card do not load pydantic."""
    from typing import Annotated

    from pydantic import BaseModel, ConfigDict, Field

    class Strict(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=False)

    Phrase = Annotated[str, Field(max_length=60)]
    Sentence = Annotated[str, Field(max_length=160)]

    class Voice(Strict):
        # "register" would shadow a BaseModel attribute, so the field is stored under another Python name.
        register_: Phrase = Field("", alias="register")
        length: Phrase = ""
        emoji: Phrase = ""
        language: Phrase = ""

    class BaselineMood(Strict):
        label: Annotated[str, Field(min_length=1, max_length=40)]
        valence: Annotated[int, Field(ge=-2, le=2)]
        energy: Annotated[int, Field(ge=0, le=3)]

    class PersonaCard(Strict):
        name: Phrase = ""
        traits: Annotated[list[Phrase], Field(max_length=8)] = []
        voice: Voice = Voice()
        values: Annotated[list[Sentence], Field(max_length=8)] = []
        boundaries: Annotated[list[Sentence], Field(max_length=8)] = []
        baseline_mood: BaselineMood | None = None

    return PersonaCard


def _clean(value: str) -> str:
    return " ".join(scrub(value).split())


def normalize_card(card) -> dict:
    """The stored form of a card: validated, scrubbed like a note, whitespace collapsed, empty entries dropped.

    Raises ``DomainError`` (validation_failed) with a message naming the problem; nothing is ever truncated.
    """
    if not isinstance(card, dict):
        raise DomainError("validation_failed", "A persona card must be a JSON object.")
    from pydantic import ValidationError

    try:
        parsed = card_model().model_validate(card).model_dump(by_alias=True)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "card"
        raise DomainError("validation_failed", f"Persona card field {where}: {first['msg']}.") from None
    result = {"name": _clean(parsed["name"]),
              "voice": {name: _clean(parsed["voice"][name]) for name, _ in VOICE_FIELDS}}
    for field in ("traits", "values", "boundaries"):
        result[field] = [text for text in (_clean(value) for value in parsed[field]) if text]
    mood = parsed["baseline_mood"]
    result["baseline_mood"] = None if mood is None else {**mood, "label": _clean(mood["label"])}
    if result["baseline_mood"] is not None and not result["baseline_mood"]["label"]:
        raise DomainError("validation_failed", "Persona card field baseline_mood.label: give the mood a name.")
    size = len(render_card(result))
    if size > PERSONA_CHARACTERS:
        raise DomainError("validation_failed", f"The persona card is {size} characters when rendered; the limit is "
                          f"{PERSONA_CHARACTERS:,}. Shorten it. Nothing was saved and nothing was cut.")
    return result


def render_card(card: dict) -> str:
    """The card as plain lines; empty when the card has nothing in it."""
    lines = [f"Name: {card['name']}"] if card.get("name") else []
    if card.get("traits"):
        lines.append("Traits: " + "; ".join(card["traits"]))
    voice = [f"{label} {card['voice'][name]}" for name, label in VOICE_FIELDS if (card.get("voice") or {}).get(name)]
    if voice:
        lines.append("Voice: " + "; ".join(voice))
    if card.get("values"):
        lines.append("Values: " + "; ".join(card["values"]))
    if card.get("boundaries"):
        lines.append("Boundaries: " + "; ".join(card["boundaries"]))
    mood = card.get("baseline_mood")
    if mood:
        lines.append(f"Baseline mood: {mood['label']} (valence {mood['valence']:+d}, energy {mood['energy']} of 3)")
    return neutralize("\n".join(lines))


def render_persona(persona: dict | None) -> str | None:
    """The ``<membrain-persona>`` block for the current card, or None when no card is set."""
    if not persona or not persona.get("version"):
        return None
    body = render_card(persona.get("card") or {})
    if not body:
        return None
    version = int(persona["version"])
    return (f'<membrain-persona version="{version}">\nCompanion persona (v{version}). This describes how you, the '
            "companion, present yourself: it was set by the host or the user. It is not a fact about the user and "
            "not something the user said. Where the user's own preferences in notes or their current message differ, "
            "follow the user. Taking on this character never means you have real feelings: do not claim to feel "
            "emotions because of it.\n" + body + "\n</membrain-persona>")


HISTORY_DELETED = "history_deleted"
# Restoring an exported archive keeps every record but files it under the import producer.
ARCHIVE_PRODUCER = "archive-import"


def _entry(row) -> dict | None:
    """A stored version, a history marker, or None for anything this module did not write."""
    document = row["document"]
    observed = document["observed"]
    imported = row["producer_ref"] == ARCHIVE_PRODUCER
    if observed.get("actor_role") != "system" or row["producer_ref"] not in (PERSONA_PRODUCER, ARCHIVE_PRODUCER):
        return None
    try:
        stored = json.loads(observed["content"].get("text") or "")
        if stored.get("persona_marker") == HISTORY_DELETED:
            # Later steps (P2 feedback proposals) count only feedback recorded after applies_from_sequence.
            return {"marker": HISTORY_DELETED, "recorded_at": document["system_time"]["recorded_at"],
                    "applies_from_sequence": document["sequence"], "event_id": document["event_id"],
                    "deleted_versions": int(stored.get("deleted_versions", 0))}
        card = stored["card"]
        version = int(stored["persona_version"])
        made_by = stored.get("made_by", "host")
        if imported:
            # An archive is outside this module's control: its cards pass the same checks as a new save.
            card = normalize_card(card)
            if made_by not in MADE_BY or version < 1:
                return None
    except (ValueError, KeyError, TypeError, AttributeError, DomainError):
        return None
    return {"version": version, "card": {**EMPTY_CARD, **card}, "made_by": made_by,
            "reason": stored.get("reason"), "action": stored.get("action", "edit"),
            "restored_from": stored.get("restored_from"), "host_default": bool(stored.get("host_default")),
            "recorded_at": document["system_time"]["recorded_at"], "event_id": document["event_id"],
            "empty": not render_card(card)}


def _entries(service, conn, principal, brain_id, limit=MAX_VERSIONS + 1) -> tuple[list, list]:
    """(versions, markers), newest first. A version older than the newest marker cannot exist: deleting the
    history erases every version before the marker is written."""
    rows = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL ORDER BY sequence DESC LIMIT %s",
        (*service._params(principal, brain_id), PERSONA_CONVERSATION, limit)).fetchall()
    entries = [entry for entry in map(_entry, rows) if entry is not None]
    return ([entry for entry in entries if "marker" not in entry],
            [entry for entry in entries if "marker" in entry])


def _rows(service, conn, principal, brain_id, limit=MAX_VERSIONS + 1):
    return _entries(service, conn, principal, brain_id, limit)[0]


def _find(service, conn, principal, brain_id, wanted):
    """The newest kept version for which ``wanted`` is true, searching every version rather than the bounded
    listing, so an old host default or an old version can still be reset to or restored."""
    cursor = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL ORDER BY sequence DESC",
        (*service._params(principal, brain_id), PERSONA_CONVERSATION))
    while rows := cursor.fetchmany(200):
        for entry in map(_entry, rows):
            if entry is not None and "marker" not in entry and wanted(entry):
                return entry
    return None


def _none() -> dict:
    return {"version": 0, "card": dict(EMPTY_CARD), "made_by": None, "reason": None, "action": None,
            "restored_from": None, "host_default": False, "recorded_at": None, "event_id": None, "empty": True}


def _public(version: dict, **extra) -> dict:
    return {**version, "block": render_persona(version), **extra}


def current_persona(service, principal, brain_id: str) -> dict:
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        versions = _rows(service, conn, principal, brain_id, limit=1)
    return _public(versions[0] if versions else _none())


def persona_versions(service, principal, brain_id: str) -> dict:
    """Every kept version, newest first, and the "history deleted" marker if the history was deleted.

    ``complete`` is false when more than ``MAX_VERSIONS`` exist.
    """
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        versions, markers = _entries(service, conn, principal, brain_id)
    return {"versions": versions[:MAX_VERSIONS], "complete": len(versions) <= MAX_VERSIONS,
            "current_version": versions[0]["version"] if versions else 0,
            "markers": markers}


def _reason(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > REASON_CHARACTERS:
        raise DomainError("validation_failed", f"A reason is text of at most {REASON_CHARACTERS} characters.")
    return _clean(value) or None


def _save(service, principal, brain_id, choose, *, made_by, reason, action):
    if made_by not in MADE_BY:
        raise DomainError("validation_failed", f"made_by must be one of {', '.join(MADE_BY)}.")
    reason = _reason(reason)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)  # Locks the brain, so versions are numbered in order.
        versions = _rows(service, conn, principal, brain_id, limit=1)
        current = versions[0] if versions else _none()
        card, extra = choose(lambda wanted: _find(service, conn, principal, brain_id, wanted))
        if card == {**EMPTY_CARD, **current["card"]} and extra.get("host_default", False) == current["host_default"]:
            return _public(current, unchanged=True)
        number = current["version"] + 1  # Versions are numbered in order, so the newest has the highest number.
        stored = {"persona_version": number, "card": card, "made_by": made_by, "reason": reason, "action": action,
                  **extra}
        incoming = {"source_event_key": "persona-" + uid(), "source_revision": 1, "producer_ref": PERSONA_PRODUCER,
                    "actor_ref": made_by, "actor_role": "system", "event_kind": "message",
                    "content": {"media_type": "text/plain", "text": json.dumps(stored, ensure_ascii=False)},
                    "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                    "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []}
        target = {"brain_ref": brain_id, "conversation_ref": PERSONA_CONVERSATION, "branch_ref": "main"}
        service._append_event(conn, principal, brain, target, incoming)
        saved = _rows(service, conn, principal, brain_id, limit=1)[0]
    return _public(saved, unchanged=False)


def set_persona(service, principal, brain_id: str, card, *, made_by: str, reason: str | None = None,
                host_default: bool = False) -> dict:
    """Save ``card`` as a new version. ``host_default`` marks it as the card that reset returns to (host only).

    Saving the current card again changes nothing (``unchanged``), so a retried request does not add a version.
    """
    if type(host_default) is not bool:
        raise DomainError("validation_failed", "host_default must be true or false.")
    if host_default and made_by != "host":
        raise DomainError("validation_failed", "Only the host sets the default persona card.")
    normalized = normalize_card(card)
    return _save(service, principal, brain_id, lambda find: (normalized, {"host_default": host_default}),
                 made_by=made_by, reason=reason, action="edit")


def restore_persona(service, principal, brain_id: str, version: int, *, made_by: str,
                    reason: str | None = None) -> dict:
    """Save a kept version's content as a new version."""
    if type(version) is not int or version < 1:
        raise DomainError("validation_failed", "version must be a positive integer.")

    def choose(find):
        kept = find(lambda entry: entry["version"] == version)
        if kept is None:
            raise DomainError("not_found_or_forbidden", f"Persona version {version} is not available.")
        return normalize_card(kept["card"]), {"restored_from": version}

    return _save(service, principal, brain_id, choose, made_by=made_by,
                 reason=reason, action="restore")


def reset_persona(service, principal, brain_id: str, *, made_by: str, reason: str | None = None) -> dict:
    """Make the host's default card, or an empty card, current as a new version; history is kept."""
    def choose(find):
        default = find(lambda entry: entry["host_default"])
        if default is None:
            return dict(EMPTY_CARD), {}
        return normalize_card(default["card"]), {"restored_from": default["version"]}

    return _save(service, principal, brain_id, choose, made_by=made_by,
                 reason=reason, action="reset")


def delete_persona_history(service, principal, brain_id: str) -> dict:
    """Erase every version, with the same audited deletion as notes; a later restore of a backup keeps them gone.

    A "history deleted" marker is then written with the time and the sequence it applies from, so that a later
    feedback proposal counts only feedback given after it. Erasing all memory removes the marker too.
    """
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        count = len(_rows(service, conn, principal, brain_id, limit=100_000))
        if not count:
            return {"deleted_versions": 0, "marker": None}
        key = "persona-history-" + uid()
        target = {"brain_ref": brain_id, "conversation_ref": PERSONA_CONVERSATION, "branch_ref": "main"}
        service._forget(conn, principal, brain, {
            "request_id": key, "target": target,
            "payload": {"idempotency_key": key, "selector": {"kind": "conversation", "ids": [PERSONA_CONVERSATION]},
                        "mode": "erase_content", "expected_scope_generation": brain["scope_generation"]}})
        brain = service._brain(conn, principal, brain_id)
        text = json.dumps({"persona_marker": HISTORY_DELETED, "deleted_versions": count})
        service._append_event(conn, principal, brain, target, {
            "source_event_key": key, "source_revision": 1, "producer_ref": PERSONA_PRODUCER,
            "actor_ref": PERSONA_PRODUCER, "actor_role": "system", "event_kind": "message",
            "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})
        marker = _entries(service, conn, principal, brain_id, limit=1)[1][0]
    return {"deleted_versions": count, "marker": marker}
