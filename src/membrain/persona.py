"""The companion's persona card: how the companion presents itself, versioned and kept apart from user memory.

Each saved card is one event in a reserved conversation, so audited deletion, export and erasure treat it like any
other record and no table is needed. Versions are stored with the ``system`` role: they are configuration set by the
host or the user, not something anyone said, so they are never extracted into recalled memories, shown as history or
counted as messages. The current card is the newest version that has not been deleted. Restoring and resetting save
a new version, so history is kept until the user deletes it. What the user agreed with the agent (an accepted
suggestion, a confirmed change) is read from that history and kept across a change of personality type (see
"Agreements" below).

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
# "feedback": saved by accepting a suggestion (persona_growth, P2). A preset (persona_presets) is saved by the host
# when it is the first persona and by the user when they switch; a change the host AI proposed is saved by the user.
MADE_BY = ("host", "user", "feedback")
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


def render_manner(persona: dict | None) -> str | None:
    """The quiet form of the ``<membrain-persona>`` block, for a coding host's work session (``host_context``): the
    voice, and of the traits, values and boundaries only those the user's personality type does not have, which are
    what the user agreed with the agent or wrote themselves. A host was seen to follow the voice (emoji in almost
    every reply after a switch to a type with "emoji now and then": host trial of 2026-11-13); no trial showed it
    using the type's own traits or values, so they wait for a casual exchange, with the baseline mood. A card with no
    type is shown whole but for its mood."""
    if not render_persona(persona):
        return None
    from .persona_presets import PRESETS

    card = {**EMPTY_CARD, **(persona.get("card") or {})}
    origin = persona.get("preset") or persona.get("based_on")
    own = next((item["card"] for item in PRESETS if item["id"] == origin), None)
    quiet = {**card, "baseline_mood": None}
    if own is not None:
        quiet.update({field: [value for value in card[field] if value not in own.get(field, ())]
                      for field in ("traits", "values", "boundaries")})
    body = render_card(quiet)
    if not body:
        return None
    return (f'<membrain-persona version="{int(persona["version"])}">\nYour own manner, not a fact about the user; '
            "where the user's preferences differ, follow the user.\n" + body + "\n</membrain-persona>")


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
        # Checked inside the guard: a malformed record (from an archive) is ignored, never an error for the page.
        feedback = _feedback(stored.get("feedback"))
        if feedback is not None and made_by != "feedback":
            return None
        origin = {name: _preset_id(stored.get(name)) for name in ("preset", "based_on")}
        proposal = _host_proposal(stored.get("host_proposal"))
        source = _source(stored.get("source"))
        agreed = _agreed_changes(stored.get("agreed_changes"))
        if agreed is not None and proposal is None:
            return None
    except (ValueError, KeyError, TypeError, AttributeError, DomainError):
        return None
    return {"version": version, "card": {**EMPTY_CARD, **card}, "made_by": made_by,
            "reason": stored.get("reason"), "action": stored.get("action", "edit"),
            "feedback": feedback, **origin, "host_proposal": proposal, "agreed_changes": agreed, "source": source,
            "language": stored.get("language") if feedback is not None and stored.get("language") in ("en", "zh")
            else None,
            "restored_from": stored.get("restored_from"), "host_default": bool(stored.get("host_default")),
            "recorded_at": document["system_time"]["recorded_at"], "event_id": document["event_id"],
            "empty": not render_card(card)}


def _preset_id(value) -> str | None:
    """A preset id (``persona_presets``): the preset a version was saved from (``preset``) or edited from
    (``based_on``). Any short id is read back, so a preset later removed from the table still reads as custom."""
    if value is None:
        return None
    if not isinstance(value, str) or not 0 < len(value) <= 40 or not value.replace("_", "").isalnum():
        raise ValueError("preset")
    return value


def _host_proposal(value) -> dict | None:
    """The host AI's proposal a version came from: its id, and the user message that confirmed it (None when the
    user accepted it on the memory page)."""
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {"proposal_id", "confirmed_by"}
            or not isinstance(value["proposal_id"], str) or not 0 < len(value["proposal_id"]) <= 200
            or not (value["confirmed_by"] is None or isinstance(value["confirmed_by"], str)
                    and 0 < len(value["confirmed_by"]) <= 200)):
        raise ValueError("host_proposal")
    return dict(value)


def _agreed_changes(value) -> dict | None:
    """What the user agreed to when they confirmed or accepted a host proposal, as the accepted version records it
    (``persona_growth._accept_host``): the voice fields the proposal set, the list entries it added to the card it was
    made on, and a name or baseline mood it gave; empty when it changed nothing. Each part must be one a card can
    hold."""
    if value is None:
        return None
    if not isinstance(value, dict) or not set(value) <= {"name", "voice", "baseline_mood", *AGREEMENT_LISTS}:
        raise ValueError("agreed_changes")
    voice = value.get("voice", {})
    if not isinstance(voice, dict) or not set(voice) <= {name for name, _ in VOICE_FIELDS} or "voice" in value and not voice:
        raise ValueError("agreed_changes")
    if any(field in value and not value[field] for field in AGREEMENT_LISTS):
        raise ValueError("agreed_changes")
    card = {**EMPTY_CARD, **{field: value[field] for field in value if field != "voice"},
            "voice": {**EMPTY_CARD["voice"], **voice}}
    if normalize_card(card) != card:
        raise ValueError("agreed_changes")  # Only the stored form of a card: nothing to clean, nothing dropped.
    return json.loads(json.dumps(value))


def _source(value) -> dict | None:
    """The user message a preset switch was asked for in: a recorded id, or the exact reference of the current
    message (``persona_growth._reference``)."""
    if value is None:
        return None
    if isinstance(value, dict) and set(value) == {"event_id"} and isinstance(value["event_id"], str) and (
            0 < len(value["event_id"]) <= 200):
        return dict(value)
    if isinstance(value, dict) and set(value) == {"message"}:
        from .persona_growth import _reference

        return {"message": _reference(value["message"])}
    raise ValueError("source")


def _origin(entry: dict | None, *, edited: bool) -> dict:
    """What a new version says about the preset it comes from: the same ``preset`` when it keeps a preset's content
    (restore, reset), or ``based_on`` when it is an edit of one."""
    if entry is None:
        return {}
    if not edited and entry.get("preset"):
        return {"preset": entry["preset"]}
    origin = entry.get("preset") or entry.get("based_on")
    return {"based_on": origin} if origin else {}


def _feedback(value) -> dict | None:
    """The accepted suggestion a version came from (P2): its id, feedback kind and source message ids."""
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {"proposal_id", "kind", "source_event_ids"}
            or not all(isinstance(value[key], str) and 0 < len(value[key]) <= 200 for key in ("proposal_id", "kind"))
            or not isinstance(value["source_event_ids"], list) or not 0 < len(value["source_event_ids"]) <= 20
            or not all(isinstance(item, str) and 0 < len(item) <= 200 for item in value["source_event_ids"])):
        raise ValueError("feedback")
    return {"proposal_id": value["proposal_id"], "kind": value["kind"],
            "source_event_ids": list(value["source_event_ids"])}


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


# Agreements ---------------------------------------------------------------------------------------------------------
# What the user agreed with the agent is memory, so it survives a change of personality type (owner, 2026-11-18): a
# manner suggestion the user accepted (a version ``made_by`` "feedback") and a "from now on" change the agent proposed
# and the user confirmed (``action`` "proposal"). The agreements in force are read from the version history.
#
# An agreement is exactly what the user accepted, as recorded when they accepted it, and never a difference against
# another version (outside review, 2026-11-18: with the version before it deleted, such a difference took the
# personality type's own traits, values and mood for agreed). For an accepted manner suggestion it is the change its
# kind states (``persona_growth.KINDS``: one voice field or one trait, with the value the accepted card holds for it);
# for a host proposal, the changes the accepted version records (``agreed_changes``: the voice fields the proposal set,
# the entries it added, a name or mood it gave). A version saved before ``agreed_changes`` existed is read from the
# proposal it names (``_legacy_proposal``): only the voice fields, name and mood it states, never its list additions,
# which only the card it was made on could tell. A version that does not record enough to tell what was accepted is
# not an agreement: nothing of it is carried.
#
# Each later version keeps the agreements in force before it, each with the part of it the new card still has, so an
# agreement can only shrink; restoring a version takes the agreements in force at that version. A switch of type and
# a reset (``persona_presets``) apply the agreements in force on top of the new card, in the order they were made, so
# a switch never ends one. An agreement ends when the card no longer has it through the user's own act: an accepted
# change of the opposite kind or a confirmed change that replaces it, a confirmed or accepted proposal that removes
# it (``changes.remove``) or clears it, a card written through ``PUT .../persona`` without it, restoring a version
# from before it, deleting its version, deleting the personality history (every version goes) or erasing memory.
#
# A removal or a clearing is a change to the current card, never an agreement: it is not recorded in
# ``agreed_changes`` and is not applied to another type's card. A later switch starts from that type's own card plus
# the agreements still in force, so an entry the user removed comes back only when it is the type's own (or by
# restoring a version that had it). An emptied voice field or name, or a null mood, is therefore never part of an
# agreement (``_kept``), also when an earlier runtime recorded one.

AGREEMENT_LISTS = ("traits", "values", "boundaries")
AGREEMENTS_DO_NOT_FIT = ("This card and the changes you agreed with your agent do not fit on one card together. "
                         "Nothing was saved.")


def _agreed(entry: dict) -> str | None:
    """The kind of agreement a version records: "feedback" (an accepted suggestion), "proposal" (a confirmed or
    accepted change the agent proposed), or None for any other version."""
    if entry.get("made_by") == "feedback" and entry.get("feedback"):
        return "feedback"
    if entry.get("action") == "proposal" and entry.get("host_proposal"):
        return "proposal"
    return None


def _kept(changes: dict, card: dict) -> dict:
    """The part of an agreement's changes the card still has. A cleared field (an empty voice field or name, a null
    mood) is a change to one card, never an agreement, so it is never kept."""
    card = {**EMPTY_CARD, **card}
    kept = {}
    voice = {name: value for name, value in (changes.get("voice") or {}).items()
             if value and (card["voice"].get(name) or "") == value}
    if voice:
        kept["voice"] = voice
    for field in AGREEMENT_LISTS:
        values = [value for value in changes.get(field) or () if value in card[field]]
        if values:
            kept[field] = values
    for field in ("name", "baseline_mood"):
        if changes.get(field) and card[field] == changes[field]:
            kept[field] = changes[field]
    return kept


def manner_change(kind: str, card: dict) -> dict:
    """The change an accepted manner suggestion of ``kind`` made, read from the card it was accepted into: the kind's
    voice field or trait, when the card holds one of the kind's values (today's or an earlier runtime's,
    ``persona_growth.EARLIER_VALUES``); empty for an unknown kind or a card without one."""
    from .persona_growth import EARLIER_VALUES, KINDS

    spec = KINDS.get(kind)
    if spec is None:
        return {}
    known = {value.casefold() for value in (*spec["value"].values(), *EARLIER_VALUES.get(kind, ()))}
    card = {**EMPTY_CARD, **card}
    if spec["field"] == "traits":
        trait = next((value for value in card["traits"] if value.casefold() in known), None)
        return {"traits": [trait]} if trait else {}
    name = spec["field"].split(".", 1)[1]
    value = card["voice"].get(name) or ""
    return {"voice": {name: value}} if value.casefold() in known else {}


def proposal_change(changes: dict, base: dict) -> dict:
    """What a host proposal states, as an agreement: the voice fields it sets, the entries it adds to ``base`` (the
    card it is accepted onto, which already has the others), and a name or baseline mood it gives. ``changes`` is the
    proposal's stored form (``persona_growth.propose_change``), whose lists hold the whole merged list: an entry of
    ``base`` missing from it was removed, which is a change to that card and no part of the agreement, as is a field
    the proposal clears (dropped by ``_kept``)."""
    base = {**EMPTY_CARD, **base}
    result = {}
    for field, value in changes.items():
        if field == "voice" and isinstance(value, dict) and value:
            result["voice"] = {name: text for name, text in value.items() if isinstance(text, str)}
        elif field in AGREEMENT_LISTS and isinstance(value, list):
            added = [entry for entry in value if entry not in base[field]]
            if added:
                result[field] = added
        elif field in ("name", "baseline_mood"):
            result[field] = value
    return result


def _legacy_proposal(card: dict, record: dict | None) -> dict:
    """A host proposal accepted before versions recorded ``agreed_changes``: the voice fields, name and baseline mood
    the stored proposal it names states. Its lists were stored merged with the card it was made on, so which entries
    it added cannot be told from the proposal alone, and an agreement is never read from another version: no list
    entry of it is carried. Nothing is carried without the proposal, or when the accepted card is not the one it
    proposed."""
    card = {**EMPTY_CARD, **card}
    if record is None or record.get("proposed_card") != normalize_card(card):
        return {}
    stated = {field: value for field, value in record["changes"].items() if field not in AGREEMENT_LISTS}
    return proposal_change(stated, EMPTY_CARD) if stated else {}


def stated_by(entry: dict, proposals: dict | None = None) -> dict:
    """What the user accepted at version ``entry``, as recorded when they accepted it, limited to what its card holds;
    empty when the version is not an agreement or does not record enough to tell. ``proposals``: host proposal records
    by id (``proposal_records``), for versions saved before ``agreed_changes``. No other version is ever read."""
    source = _agreed(entry)
    card = {**EMPTY_CARD, **entry["card"]}
    if source == "feedback":
        return manner_change(entry["feedback"]["kind"], card)
    if source != "proposal":
        return {}
    if entry.get("agreed_changes") is not None:
        return _kept(entry["agreed_changes"], card)
    return _kept(_legacy_proposal(card, (proposals or {}).get(entry["host_proposal"]["proposal_id"])), card)


def agreements_by_version(versions, proposals: dict | None = None) -> dict[int, list[dict]]:
    """The agreements in force at each version, oldest first within each list; ``versions`` oldest first. Each starts
    as what its version states (``stated_by``) and only loses parts after it, so none is ever more than that."""
    found: dict[int, list[dict]] = {}
    state: list[dict] = []
    for entry in versions:
        card = entry["card"]
        base = found.get(entry.get("restored_from")) if entry.get("action") == "restore" else None
        state = [{**agreement, "changes": kept} for agreement in (state if base is None else base)
                 if (kept := _kept(agreement["changes"], card))]
        source = _agreed(entry)
        stated = stated_by(entry, proposals) if source else {}
        if stated:
            state.append({"version": entry["version"], "made_at": entry["recorded_at"], "source": source,
                          "kind": (entry["feedback"] or {}).get("kind") if source == "feedback" else None,
                          "reason": entry.get("reason"), "changes": stated})
        found[entry["version"]] = state
    return found


def _ascending(service, conn, principal, brain_id) -> list[dict]:
    """Every kept version, oldest first, read in pages."""
    cursor = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL ORDER BY sequence",
        (*service._params(principal, brain_id), PERSONA_CONVERSATION))
    versions = []
    while rows := cursor.fetchmany(200):
        versions += [entry for entry in map(_entry, rows) if entry is not None and "marker" not in entry]
    return versions


def proposal_records(service, conn, principal, brain_id, versions) -> dict:
    """The stored host proposals that kept versions accepted without recording ``agreed_changes``, by id."""
    from .persona_growth import PROPOSALS_CONVERSATION
    from .persona_growth import _entry as proposal_entry

    ids = sorted({entry["host_proposal"]["proposal_id"] for entry in versions
                  if _agreed(entry) == "proposal" and entry.get("agreed_changes") is None})
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND id=ANY(%s::text[]) AND is_current AND NOT deleted AND NOT suppressed "
        "AND NOT retired AND document IS NOT NULL",
        (*service._params(principal, brain_id), PROPOSALS_CONVERSATION, ids)).fetchall()
    records = (proposal_entry(row) for row in rows)
    return {record["id"]: record for record in records
            if record is not None and record.get("type") == "proposal" and record.get("kind") == "host"}


def agreements_in_force(service, conn, principal, brain_id) -> list[dict]:
    """The agreements in force at the current version, in the order they were made."""
    versions = _ascending(service, conn, principal, brain_id)
    if not versions:
        return []
    proposals = proposal_records(service, conn, principal, brain_id, versions)
    return agreements_by_version(versions, proposals).get(versions[-1]["version"], [])


def with_agreements(card: dict, agreements) -> dict:
    """``card`` with each agreement applied on top, in order: voice fields set, list entries added, name and mood
    replaced. Raises ``DomainError`` when the result does not pass ``normalize_card``."""
    merged = json.loads(json.dumps({**EMPTY_CARD, **card}))
    for agreement in agreements:
        for field, value in agreement["changes"].items():
            if field == "voice":
                merged["voice"] = {**merged["voice"], **value}
            elif field in AGREEMENT_LISTS:
                merged[field] = merged[field] + [entry for entry in value if entry not in merged[field]]
            else:
                merged[field] = value
    try:
        return normalize_card(merged)
    except DomainError:
        raise DomainError("validation_failed", AGREEMENTS_DO_NOT_FIT) from None


def base_card(card: dict, agreements) -> dict:
    """``card`` without the parts the agreements in force put there: what the page shows as the card itself."""
    result = json.loads(json.dumps({**EMPTY_CARD, **card}))
    for agreement in agreements:
        changes = agreement["changes"]
        for name in changes.get("voice") or {}:
            result["voice"][name] = ""
        for field in AGREEMENT_LISTS:
            result[field] = [value for value in result[field] if value not in (changes.get(field) or ())]
        if "name" in changes:
            result["name"] = ""
        if "baseline_mood" in changes:
            result["baseline_mood"] = None
    return result


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
            "feedback": None, "preset": None, "based_on": None, "host_proposal": None, "agreed_changes": None,
            "language": None, "source": None,
            "restored_from": None, "host_default": False, "recorded_at": None, "event_id": None, "empty": True}


def _public(version: dict, **extra) -> dict:
    return {**version, "block": render_persona(version), **extra}


def current_persona(service, principal, brain_id: str) -> dict:
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        versions = _rows(service, conn, principal, brain_id, limit=1)
        _quote_feedback(service, conn, principal, brain_id, versions)  # The reason's dates, from messages kept.
    for version in versions:
        version.pop("feedback_messages", None)  # Their words are for the versions listing only.
    return _public(versions[0] if versions else _none())


def persona_versions(service, principal, brain_id: str) -> dict:
    """Every kept version, newest first, and the "history deleted" marker if the history was deleted.

    ``complete`` is false when more than ``MAX_VERSIONS`` exist. Each version carries the agreements in force at it
    (``agreements``, oldest first) and its card without them (``base_card``), so the page can show an agreement
    carried over apart from the personality type.
    """
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        versions, markers = _entries(service, conn, principal, brain_id)
        versions = versions[:MAX_VERSIONS + 1]
        _quote_feedback(service, conn, principal, brain_id, versions[:MAX_VERSIONS])
        every = _ascending(service, conn, principal, brain_id) if versions else []
        _quote_feedback(service, conn, principal, brain_id, every)  # The agreements carry their version's reason.
        _quote_asked(service, conn, principal, brain_id, [*versions[:MAX_VERSIONS], *every])
        agreed = agreements_by_version(every, proposal_records(service, conn, principal, brain_id, every))
    by_number = {entry["version"]: entry for entry in every}
    for version in versions:
        version["agreements"] = agreed.get(version["version"], [])
        version["base_card"] = base_card(version["card"], version["agreements"])
        for agreement in version["agreements"]:
            # Where the user agreed, read from the messages that still exist: the message that said yes to the
            # agent's suggestion, or the messages whose feedback they accepted. None when they accepted it here.
            entry = by_number.get(agreement["version"]) or {}
            asked = entry.get("asked_in") or {}
            agreement["said_in"] = ([asked] if agreement["source"] == "proposal" and asked.get("event_id")
                                    else list(entry.get("feedback_messages") or []) if agreement["source"] == "feedback"
                                    else [])
    return {"versions": versions[:MAX_VERSIONS], "complete": len(versions) <= MAX_VERSIONS,
            "current_version": versions[0]["version"] if versions else 0,
            "agreements": versions[0]["agreements"] if versions else [],
            "markers": markers}


def _quote_feedback(service, conn, principal, brain_id, versions) -> None:
    """Quote current feedback only when that revision preceded the accepted persona version. Edited or erased
    messages must not rewrite an earlier decision's evidence, including after archive restore."""
    pairs = [(version["event_id"], ident) for version in versions
             for ident in (version.get("feedback") or {}).get("source_event_ids", [])]
    rows = conn.execute(
        "SELECT p.id AS persona_id,e.id,left(e.document->'observed'->'content'->>'text',160) AS text,"
        "e.document->'system_time'->>'recorded_at' AS recorded_at "
        "FROM unnest(%s::text[],%s::text[]) AS refs(persona_id,source_id) "
        "JOIN memory_events p ON p.id=refs.persona_id "
        "JOIN memory_events e ON e.id=refs.source_id AND e.tenant_id=p.tenant_id "
        "AND e.owner_id=p.owner_id AND e.brain_id=p.brain_id "
        "WHERE p.tenant_id=%s AND p.owner_id=%s AND p.brain_id=%s "
        "AND p.is_current AND NOT p.deleted AND NOT p.suppressed AND NOT p.retired AND p.document IS NOT NULL "
        "AND e.is_current AND NOT e.deleted AND NOT e.suppressed AND NOT e.retired AND e.document IS NOT NULL "
        "AND e.sequence<p.sequence AND e.document->'observed'->>'actor_role'='user'",
        ([pair[0] for pair in pairs], [pair[1] for pair in pairs],
         *service._params(principal, brain_id))).fetchall() if pairs else []
    found = {(row["persona_id"], row["id"]): row for row in rows}
    for version in versions:
        feedback = version.get("feedback")
        if feedback:
            version["feedback_messages"] = [
                {"event_id": ident, "text": " ".join((row["text"] or "").split()), "recorded_at": row["recorded_at"]}
                for ident in feedback.get("source_event_ids") or []
                if (row := found.get((version["event_id"], ident))) is not None]
            version["reason"] = _feedback_reason(version)


def _quote_asked(service, conn, principal, brain_id, versions) -> None:
    """The user's message a version was made in, from the message as it is now: the one that confirmed the agent's
    suggestion (``host_proposal.confirmed_by``) or asked for a type switch (``source``). ``version["asked_in"]`` is
    the message (``event_id``, ``text``, ``recorded_at``) while it is a current user message of a conversation,
    ``{"deleted": true}`` once it was deleted or hidden, and absent when the version names no message or none can be
    found by its reference (not recorded yet, or erased with a key that named its content). Nothing of a deleted
    message is read."""
    wanted = {}
    for version in versions:
        proposal, source = version.get("host_proposal") or {}, version.get("source") or {}
        if proposal.get("confirmed_by"):
            wanted[version["event_id"]] = ("id", proposal["confirmed_by"])
        elif source.get("event_id"):
            wanted[version["event_id"]] = ("id", source["event_id"])
        elif source.get("message"):
            wanted[version["event_id"]] = ("message", source["message"])
    if not wanted:
        return
    from .persona_growth import _reserved

    ids = sorted({value for kind, value in wanted.values() if kind == "id"})
    references = [value for kind, value in wanted.values() if kind == "message"]
    rows = conn.execute(
        "SELECT id,producer_ref,source_key,source_revision,"
        "(is_current AND NOT deleted AND NOT suppressed AND NOT retired AND document IS NOT NULL "
        "AND document->'observed'->>'actor_role'='user' AND NOT (conversation_id=ANY(%s::text[]))) AS shown,"
        "CASE WHEN NOT deleted THEN left(document->'observed'->'content'->>'text',160) END AS text,"
        "document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND (id=ANY(%s::text[]) OR (producer_ref,source_key,"
        "source_revision) IN (SELECT * FROM unnest(%s::text[],%s::text[],%s::bigint[])))",
        (_reserved(), *service._params(principal, brain_id), ids,
         [ref["producer_ref"] for ref in references], [ref["source_event_key"] for ref in references],
         [ref["source_revision"] for ref in references])).fetchall()
    by_id = {row["id"]: row for row in rows}
    by_key = {(row["producer_ref"], row["source_key"], row["source_revision"]): row for row in rows}
    for version in versions:
        kind, value = wanted.get(version["event_id"], (None, None))
        row = by_id.get(value) if kind == "id" else by_key.get(
            (value["producer_ref"], value["source_event_key"], value["source_revision"])) if kind else None
        if row is None:
            continue
        version["asked_in"] = ({"event_id": row["id"], "text": " ".join((row["text"] or "").split()),
                                "recorded_at": row["recorded_at"]} if row["shown"] and row["text"]
                               else {"deleted": True})


def _feedback_reason(version: dict) -> str | None:
    """An accepted suggestion's reason as it is shown: the kind, and the dates of the messages it came from that
    still exist (``persona_growth.reason_for``; ``version["feedback_messages"]`` from ``_quote_feedback``). A version
    accepted since 2026-11-18 stores the kind only and its language; one accepted before stored the dates of every
    message, so its language is read from the start of that reason and its dates are never shown as stored."""
    from .persona_growth import KINDS, reason_for

    reason, kind = version.get("reason"), version["feedback"]["kind"]
    if not isinstance(reason, str) or kind not in KINDS:
        return reason
    language = version.get("language") or _stored_language(reason)
    if language is None:
        return reason
    return reason_for({"language": language, "kind": kind, "sources": version.get("feedback_messages") or []})


def _stored_language(reason: str) -> str | None:
    """The language of a feedback reason stored before versions kept it: its fixed opening says it."""
    return "zh" if reason.startswith("接受的建议") else "en" if reason.startswith("Accepted suggestion:") else None


def archived_event(event: dict) -> dict:
    """A persona version as an archive holds it (export, and archives sanitized after an erasure): an accepted
    suggestion's reason with no dates, as versions accepted since 2026-11-18 store it, so an earlier version's stored
    dates of messages since deleted do not leave in a copy. Its content hash is updated to match; every other event is
    returned unchanged. A restored version gets its dates back on read from the messages restored with it."""
    observed = event.get("observed") or {}
    if observed.get("actor_role") != "system" or (event.get("scope") or {}).get("conversation_id") != PERSONA_CONVERSATION:
        return event
    from .helpers import digest
    from .persona_growth import KINDS, reason_for

    try:
        stored = json.loads((observed.get("content") or {}).get("text") or "")
        reason, kind = stored.get("reason"), (stored.get("feedback") or {}).get("kind")
    except (ValueError, AttributeError, TypeError):
        return event
    if stored.get("made_by") != "feedback" or kind not in KINDS or not isinstance(reason, str):
        return event
    language = stored.get("language") if stored.get("language") in ("en", "zh") else _stored_language(reason)
    clean = reason_for({"language": language, "kind": kind, "sources": []}) if language else None
    if clean is None or clean == reason:
        return event
    content = {**observed["content"], "text": json.dumps({**stored, "reason": clean}, ensure_ascii=False)}
    return {**event, "observed": {**observed, "content": content}, "content_sha256": digest(content)}


def _reason(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > REASON_CHARACTERS:
        raise DomainError("validation_failed", f"A reason is text of at most {REASON_CHARACTERS} characters.")
    return _clean(value) or None


def _save_in(service, conn, principal, brain, choose, *, made_by, reason, action) -> dict:
    """Save a new version inside the caller's transaction, which holds the brain lock. Returns the saved version
    with ``unchanged`` false, or the current one with ``unchanged`` true when nothing would change."""
    if made_by not in MADE_BY:
        raise DomainError("validation_failed", f"made_by must be one of {', '.join(MADE_BY)}.")
    reason = _reason(reason)
    brain_id = brain["id"]
    versions = _rows(service, conn, principal, brain_id, limit=1)
    current = versions[0] if versions else _none()
    card, extra = choose(lambda wanted: _find(service, conn, principal, brain_id, wanted))
    if card == {**EMPTY_CARD, **current["card"]} and extra.get("host_default", False) == current["host_default"]:
        return {**current, "unchanged": True}
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
    return {**_rows(service, conn, principal, brain_id, limit=1)[0], "unchanged": False}


def _save(service, principal, brain_id, choose, *, made_by, reason, action):
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)  # Locks the brain, so versions are numbered in order.
        saved = _save_in(service, conn, principal, brain, choose, made_by=made_by, reason=reason, action=action)
    unchanged = saved.pop("unchanged")
    return _public(saved, unchanged=unchanged)


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

    def choose(find):
        # An edit of a preset is no longer that preset, but says which one it started from. A card the host sets
        # is its own.
        origin = {} if made_by == "host" else _origin(find(lambda entry: True), edited=True)
        return normalized, {"host_default": host_default, **origin}

    return _save(service, principal, brain_id, choose, made_by=made_by, reason=reason, action="edit")


def restore_persona(service, principal, brain_id: str, version: int, *, made_by: str,
                    reason: str | None = None) -> dict:
    """Save a kept version's content as a new version."""
    if type(version) is not int or version < 1:
        raise DomainError("validation_failed", "version must be a positive integer.")

    def choose(find):
        kept = find(lambda entry: entry["version"] == version)
        if kept is None:
            raise DomainError("not_found_or_forbidden", f"Persona version {version} is not available.")
        return normalize_card(kept["card"]), {"restored_from": version, **_origin(kept, edited=False)}

    return _save(service, principal, brain_id, choose, made_by=made_by,
                 reason=reason, action="restore")


def reset_persona(service, principal, brain_id: str, *, made_by: str, reason: str | None = None,
                  preset: str | None = None, choose=None) -> dict:
    """Pick the persona again, as a new version; history is kept (``persona_presets.pick_again``).

    With ``preset``, that personality type (or "random"). Otherwise the card the host itself saved as its default
    (``host_default``), for a host that set one; otherwise a type picked at random other than the current one.
    Before personality types, a reset without a host default emptied the card; it no longer does.
    """
    from .persona_presets import pick_again

    if made_by not in MADE_BY:
        raise DomainError("validation_failed", f"made_by must be one of {', '.join(MADE_BY)}.")
    return pick_again(service, principal, brain_id, made_by=made_by, reason=_reason(reason), ident=preset,
                      choose=choose)


def delete_persona_history(service, principal, brain_id: str) -> dict:
    """Erase every version, with the same audited deletion as notes; a later restore of a backup keeps them gone.

    A "history deleted" marker is then written with the time and the sequence it applies from, so that a later
    feedback suggestion counts only feedback given after it. The suggestions and the decisions on them (P2) are
    erased too: they are part of the personality's history. Erasing all memory removes the marker too.
    """
    from .persona_growth import PROPOSALS_CONVERSATION

    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        count = len(_rows(service, conn, principal, brain_id, limit=100_000))
        suggestions = conn.execute(
            "SELECT count(*) AS value FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND conversation_id=%s AND is_current AND NOT deleted",
            (*service._params(principal, brain_id), PROPOSALS_CONVERSATION)).fetchone()["value"]
        key = "persona-history-" + uid()
        target = {"brain_ref": brain_id, "conversation_ref": PERSONA_CONVERSATION, "branch_ref": "main"}
        if count or suggestions:
            service._forget(conn, principal, brain, {
                "request_id": key, "target": target,
                "payload": {"idempotency_key": key,
                            "selector": {"kind": "conversation", "ids": [PERSONA_CONVERSATION, PROPOSALS_CONVERSATION]},
                            "mode": "erase_content", "expected_scope_generation": brain["scope_generation"]}})
            brain = service._brain(conn, principal, brain_id)
        # The marker is written even when there was nothing to erase: it is the cut-off feedback counts from, so
        # feedback given before the user asked to delete the history never comes back into a suggestion.
        text = json.dumps({"persona_marker": HISTORY_DELETED, "deleted_versions": count})
        service._append_event(conn, principal, brain, target, {
            "source_event_key": key, "source_revision": 1, "producer_ref": PERSONA_PRODUCER,
            "actor_ref": PERSONA_PRODUCER, "actor_role": "system", "event_kind": "message",
            "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})
        marker = _entries(service, conn, principal, brain_id, limit=1)[1][0]
    return {"deleted_versions": count, "marker": marker}
