"""The companion's simulated short-term mood (``agent_mood``): derived from stored events by listed rules.

Nothing here runs in the background or calls a model. The mood is worked out whenever it is read, from the persona
card's baseline mood and the triggers found in events already stored, with an injectable clock:

- good news the user shared (a positive affect record, or a plan noted done) makes it glad;
- distress the user shared (a negative affect record) makes it concerned, and less lively;
- a shared moment of the relationship layer makes it playful when it reads as a joke or play, and glad otherwise
  (``relationship_triggers``).

Absence, silence, time apart or the user leaving are never triggers: there is no rule that reads them.

Each trigger pushes ``valence`` and ``energy`` away from the baseline, and every push decays with a 12-hour
half-life. The mood is exactly the baseline once it is within 0.25 of it on both axes, or 48 hours after its last
trigger, whichever comes first; the triggers are then dropped from the current mood (they stay in the history).

Triggers are derived, never copied: each names its rule, its source record and its time, so deleting or correcting
the source (or "Clear feelings", which erases every affect record and writes the affect marker) removes the trigger.
Only affect records after the latest affect reset marker count. The user can pin the mood to the baseline, and
reset it; both are system-role events in a reserved conversation, so they are never recalled or shown as messages,
and erasing all memory removes them too. A reset writes a mood reset marker: events before it never trigger again.
"""
from __future__ import annotations

import datetime as _datetime
import json
import math
import re

from .helpers import DomainError, uid
from .helpers import now as _now
from .privacy import neutralize

MOOD_CONVERSATION = "membrain-mood"
MOOD_PRODUCER = "membrain-mood"
RESET = "reset"
HALF_LIFE = _datetime.timedelta(hours=12)
CUTOFF = _datetime.timedelta(hours=48)
SNAP_DISTANCE = 0.25
EASING_AFTER = _datetime.timedelta(hours=6)  # The newest active trigger is older than this: "easing".
DEFAULT_BASELINE = {"label": "calm", "valence": 0, "energy": 1}
VALENCE_RANGE, ENERGY_RANGE = (-2.0, 2.0), (0.0, 3.0)
REASON_CHARACTERS = 160
MOOD_CHARACTERS = 600
LISTED_TRIGGERS = 20
PLAN_NOTES = 200
_EPSILON = 1e-9
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# The listed rules. ``push`` turns a strength into (valence, energy) away from the baseline.
RULES = {
    "reported_good_news": {"label": "glad", "push": lambda s: (s, 0.25 * s)},
    "inferred_good_news": {"label": "glad", "push": lambda s: (s, 0.25 * s)},
    "plan_done": {"label": "glad", "push": lambda s: (s, 0.25 * s)},
    "reported_distress": {"label": "concerned", "push": lambda s: (-s, -0.5 * s)},
    "inferred_distress": {"label": "concerned", "push": lambda s: (-s, -0.5 * s)},
    "shared_play": {"label": "playful", "push": lambda s: (0.5 * s, s)},
    "shared_moment": {"label": "glad", "push": lambda s: (s, 0.25 * s)},
}
PLAN_DONE_STRENGTH = 1.0
SHARED_MOMENT_STRENGTH = 1.0
# A shared moment that reads as a joke or play (a small fixed list, English and Chinese) makes the mood playful;
# any other shared moment, such as a goal reached together, makes it glad.
_PLAY = re.compile(r"(?<!\w)(?:jok(?:e|es|ed|ing)|laugh(?:ed|ing|s)?|funny|silly|played)(?!\w)|笑|玩笑|逗",
                   re.IGNORECASE)


def label_for(valence: float, energy: float) -> str:
    """The label of a mood away from its baseline, by the direction it moved (a small fixed table):

    lower valence: concerned, or wistful when energy dropped further than valence; otherwise playful when energy
    rose more than valence, else glad. At the baseline the baseline's own label is used instead.
    """
    if valence < 0:
        return "concerned" if energy >= valence else "wistful"
    return "playful" if energy > valence else "glad"


def _time(value) -> _datetime.datetime:
    if isinstance(value, _datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=_datetime.UTC)
    return _datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _iso(value: _datetime.datetime | None) -> str | None:
    return None if value is None else value.astimezone(_datetime.UTC).isoformat().replace("+00:00", "Z")


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


# Triggers -------------------------------------------------------------------------------------------------------

def _affect_triggers(service, conn, principal, brain_id) -> list[dict]:
    """Affect records after the latest affect reset marker whose note is still current. A record on a sensitive
    note never triggers: such a feeling is used only when the user raises the topic, and the mood line would
    raise it."""
    from .affect import _records, latest_marker

    marker = latest_marker(service, conn, principal, brain_id)
    after = marker["applies_from_sequence"] if marker else 0
    triggers = []
    for record in _records(service, conn, principal, brain_id):
        if record["sequence"] <= after or record["sensitive"] or record["valence"] == 0:
            continue
        kind = "good_news" if record["valence"] > 0 else "distress"
        strength = abs(record["valence"]) * (1 + record["intensity"]) / 4
        if record["basis"] != "reported":
            strength /= 2  # A feeling read from the user's words moves the mood less than one they said.
        label, topic = record["label"], record.get("topic")
        if record["basis"] == "reported":
            reason = f"the user said they felt {label}" + (f" about {topic}" if topic else "")
        else:  # Never phrased as something the user said.
            reason = f"the user seemed {label}" + (f" about {topic}" if topic else "") + ", inferred"
        triggers.append({"rule": f"{record['basis']}_{kind}", "strength": strength, "sequence": record["sequence"],
                         "at": record["recorded_at"], "reason": reason,
                         "source": {"kind": "affect", "id": record["id"], "note_id": record["note_id"],
                                    "label": label, "basis": record["basis"], "topic": topic,
                                    "note_text": record["note_text"]}})
    return triggers


def _plan_triggers(service, conn, principal, brain_id) -> list[dict]:
    """Current plan notes saved as done: good news. Notes imported from elsewhere describe the past, not something
    that just happened, and a plan "done" whose date is still ahead has not happened yet."""
    from .notes import IMPORT_PREFIX, NOTES_CONVERSATION, parse_note

    rows = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL AND document->'observed'->'content'->>'text' LIKE '[plan%%' "
        "ORDER BY sequence DESC LIMIT %s",
        (*service._params(principal, brain_id), NOTES_CONVERSATION, PLAN_NOTES)).fetchall()
    triggers = []
    for row in rows:
        if row["producer_ref"].startswith(IMPORT_PREFIX) or row["producer_ref"] == "archive-import":
            continue
        document = row["document"]
        fields, sentence = parse_note(document["observed"]["content"].get("text") or "")
        recorded = document["system_time"]["recorded_at"]
        dates = [fields[name] for name in ("due", "occurs_at") if fields.get(name)]
        if fields.get("kind") != "plan" or fields.get("status") != "done" or fields.get("sensitive"):
            continue
        if any(value > recorded[:len(value)] for value in dates):
            continue
        triggers.append({"rule": "plan_done", "strength": PLAN_DONE_STRENGTH, "sequence": document["sequence"],
                         "at": recorded, "reason": "a plan was noted done: " + _clip(sentence, 100),
                         "source": {"kind": "note", "id": document["event_id"], "note_id": document["event_id"],
                                    "note_text": sentence}})
    return triggers


def relationship_triggers(service, conn, principal, brain_id) -> list[dict]:
    """Shared moments (milestone notes flagged ``shared``) after the latest relationship reset marker: a joke or play
    is ``shared_play``, any other moment ``shared_moment``. A sensitive moment, one about a boundary topic, an
    imported one and one whose date is still ahead never trigger: the mood line would raise it, or it is not new."""
    from .notes import IMPORT_PREFIX, NOTES_CONVERSATION, parse_note
    from .relationship import _state, touches

    relationship = _state(service, conn, principal, brain_id)
    rows = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL AND sequence>%s "
        "AND document->'observed'->'content'->>'text' LIKE '[milestone%%' ORDER BY sequence DESC LIMIT %s",
        (*service._params(principal, brain_id), NOTES_CONVERSATION, relationship["after"], PLAN_NOTES)).fetchall()
    triggers = []
    for row in rows:
        if row["producer_ref"].startswith(IMPORT_PREFIX) or row["producer_ref"] == ARCHIVE_PRODUCER:
            continue
        document = row["document"]
        fields, sentence = parse_note(document["observed"]["content"].get("text") or "")
        recorded = document["system_time"]["recorded_at"]
        if (fields.get("kind") != "milestone" or not fields.get("shared") or fields.get("sensitive")
                or touches(sentence, relationship["boundaries"])):
            continue
        if fields.get("occurs_at") and fields["occurs_at"] > recorded[:len(fields["occurs_at"])]:
            continue
        play = _PLAY.search(sentence) is not None
        triggers.append({"rule": "shared_play" if play else "shared_moment", "strength": SHARED_MOMENT_STRENGTH,
                         "sequence": document["sequence"], "at": recorded,
                         "reason": ("you and the user shared a light moment: " if play
                                    else "you and the user shared a moment: ") + _clip(sentence, 100),
                         "source": {"kind": "note", "id": document["event_id"], "note_id": document["event_id"],
                                    "note_text": sentence}})
    return triggers


TRIGGER_SOURCES = (_affect_triggers, _plan_triggers, relationship_triggers)


# Stored settings: pins and reset markers --------------------------------------------------------------------------

# Restoring an exported archive keeps every record but files it under the import producer.
ARCHIVE_PRODUCER = "archive-import"
_PIN, _MARKER = '{"mood_pin"%', '{"mood_marker"%'  # How each kind of setting is stored (json.dumps).
LISTED_MARKERS = 20


def _entry(row) -> dict | None:
    """A pin or a reset marker, or None for anything else. Only the exact forms this module writes are accepted,
    so an archive (which is outside this module's control) cannot add anything else."""
    document = row["document"]
    observed = document["observed"]
    if observed.get("actor_role") != "system" or row["producer_ref"] not in (MOOD_PRODUCER, ARCHIVE_PRODUCER):
        return None
    try:
        stored = json.loads(observed["content"].get("text") or "")
        base = {"id": document["event_id"], "sequence": int(document["sequence"]),
                "recorded_at": str(document["system_time"]["recorded_at"])}
        if stored == {"mood_marker": RESET}:
            return {**base, "marker": RESET, "applies_from_sequence": base["sequence"]}
        if isinstance(stored, dict) and set(stored) == {"mood_pin"} and type(stored["mood_pin"]) is bool:
            return {**base, "pinned": stored["mood_pin"]}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return None


def _scan(service, conn, principal, brain_id, kind, *, after=0, through=None):
    """Valid settings of one kind (``_PIN`` or ``_MARKER``), newest first, with ``after < sequence <= through``.

    Unbounded, like ``persona._find``: callers stop at the first match they need, so however many settings of the
    other kind (or of this one) were recorded, the newest pin and the newest marker are always found."""
    cursor = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL AND sequence>%s AND (%s::bigint IS NULL OR sequence<=%s) "
        "AND document->'observed'->'content'->>'text' LIKE %s ORDER BY sequence DESC",
        (*service._params(principal, brain_id), MOOD_CONVERSATION, after, through, through, kind))
    while rows := cursor.fetchmany(200):
        for entry in map(_entry, rows):
            if entry is not None:
                yield entry


def _latest_pin(service, conn, principal, brain_id, through=None) -> dict | None:
    return next(_scan(service, conn, principal, brain_id, _PIN, through=through), None)


def _settings(service, conn, principal, brain_id, start=None) -> list[dict]:
    """The settings ``derive`` needs, oldest first: the newest reset markers (the latest one decides which triggers
    count), and the pin history from ``start`` (the earliest trigger that can count; never before the latest
    marker) together with the pin in force at ``start``."""
    markers = []
    for marker in _scan(service, conn, principal, brain_id, _MARKER):
        markers.append(marker)
        if len(markers) == LISTED_MARKERS:
            break
    start = max(markers[0]["applies_from_sequence"] if markers else 0, start or 0)
    pins = list(_scan(service, conn, principal, brain_id, _PIN, after=start))
    before = _latest_pin(service, conn, principal, brain_id, through=start)
    return list(reversed(markers)) + ([before] if before else []) + list(reversed(pins))


def _baseline(service, conn, principal, brain_id) -> dict:
    from .persona import _rows

    versions = _rows(service, conn, principal, brain_id, limit=1)
    mood = versions[0]["card"].get("baseline_mood") if versions else None
    if mood:
        return {"label": mood["label"], "valence": mood["valence"], "energy": mood["energy"], "source": "persona"}
    return {**DEFAULT_BASELINE, "source": "default"}


# Derivation -------------------------------------------------------------------------------------------------------

def _clamp(value, bounds):
    return min(max(value, bounds[0]), bounds[1])


def _offset(baseline, active, when) -> tuple[float, float]:
    """The mood's distance from the baseline at ``when``: decayed pushes, clamped to the mood's ranges."""
    valence = energy = 0.0
    for trigger in active:
        factor = 0.5 ** ((when - trigger["time"]) / HALF_LIFE)
        valence += trigger["push"][0] * factor
        energy += trigger["push"][1] * factor
    return (_clamp(baseline["valence"] + valence, VALENCE_RANGE) - baseline["valence"],
            _clamp(baseline["energy"] + energy, ENERGY_RANGE) - baseline["energy"])


def _returns_at(baseline, active) -> _datetime.datetime:
    """When the mood is exactly the baseline again if nothing new happens: once it is within ``SNAP_DISTANCE`` on
    both axes, or ``CUTOFF`` after the last trigger, whichever comes first. Every push decays at the same rate, so
    after the last trigger the total keeps its direction and shrinks by the same factor; this is exact."""
    last = max(trigger["time"] for trigger in active)
    totals = [0.0, 0.0]
    for trigger in active:
        factor = 0.5 ** ((last - trigger["time"]) / HALF_LIFE)
        totals[0] += trigger["push"][0] * factor
        totals[1] += trigger["push"][1] * factor
    needed = 1.0  # The decay factor at which both axes are within the threshold.
    for total, centre, bounds in ((totals[0], baseline["valence"], VALENCE_RANGE),
                                  (totals[1], baseline["energy"], ENERGY_RANGE)):
        room = (bounds[1] - centre) if total > 0 else (centre - bounds[0])
        if min(abs(total), room) > SNAP_DISTANCE + _EPSILON:
            needed = min(needed, SNAP_DISTANCE / abs(total))
    within = last + HALF_LIFE * math.log2(1 / needed)
    return min(within, last + CUTOFF)


def derive(baseline: dict, triggers: list[dict], settings: list[dict], now: _datetime.datetime) -> dict:
    """The mood at ``now`` from the baseline, the triggers and the pins and markers, in the order recorded.

    Only the latest reset marker matters: triggers recorded before it never apply and are not listed. A pin holds
    the mood at the baseline and ends the current mood; triggers recorded while pinned never apply, even after the
    pin is lifted. Anything recorded after ``now`` has not happened yet.
    """
    markers = [entry for entry in settings if "marker" in entry]
    after = markers[-1]["applies_from_sequence"] if markers else 0
    timeline = sorted([{**trigger, "time": _time(trigger["at"]), "status": "active", "ended_at": None,
                        "push": RULES[trigger["rule"]]["push"](trigger["strength"])}
                       for trigger in triggers if trigger["sequence"] > after and trigger["rule"] in RULES]
                      + [{**entry, "time": _time(entry["recorded_at"])}
                         for entry in settings if "pinned" in entry],
                      key=lambda entry: entry["sequence"])
    active, pinned, pinned_at, seen = [], False, None, []

    def end(at):
        for trigger in active:
            trigger["status"], trigger["ended_at"] = "ended", at
        active.clear()

    for entry in timeline:
        if entry["time"] > now:
            continue
        if "pinned" in entry:
            if entry["pinned"] and not pinned:
                end(entry["time"])
                pinned_at = entry["time"]
            elif not entry["pinned"]:
                pinned_at = None
            pinned = entry["pinned"]
            continue
        seen.append(entry)
        if pinned:
            entry["status"] = "pinned"
            continue
        if active and entry["time"] >= _returns_at(baseline, active):
            end(_returns_at(baseline, active))
        active.append(entry)
    back = _returns_at(baseline, active) if active else None
    if back is not None and now >= back:
        end(back)
        back = None
    valence, energy = _offset(baseline, active, now) if active else (0.0, 0.0)
    main = _main(baseline, active, now, valence, energy) if active else None
    state = {
        "label": label_for(valence, energy) if active else baseline["label"],
        "valence": round(baseline["valence"] + valence, 2), "energy": round(baseline["energy"] + energy, 2),
        "at_baseline": not active, "pinned": pinned, "pinned_at": _iso(pinned_at),
        "easing": bool(active) and now - max(trigger["time"] for trigger in active) >= EASING_AFTER,
        "baseline": baseline, "since": _iso(main["time"]) if main else None,
        "reason": main["reason"] if main else None, "trigger_id": _trigger_id(main) if main else None,
        "back_at_baseline_at": _iso(back),
        "seconds_to_baseline": None if back is None else max(0, math.ceil((back - now).total_seconds())),
        "now": _iso(now), "marker": markers[-1] if markers else None, "markers": list(reversed(markers))[:20],
        "triggers": [_public(trigger) for trigger in reversed(seen)][:LISTED_TRIGGERS],
        "complete_history": len(seen) <= LISTED_TRIGGERS,
    }
    return state


def _main(baseline, active, now, valence, energy) -> dict:
    """The trigger that explains the mood: the largest one pushing the same way as the combined mood moved (by
    valence, or by energy when valence is back at the baseline), so a concerned mood is never explained by good
    news that the harder news outweighed. Ties go to the newest."""
    axis, total = (0, valence) if abs(valence) > _EPSILON else (1, energy)
    same = [trigger for trigger in active if trigger["push"][axis] * total > 0] or active
    return max(same, key=lambda trigger: (math.hypot(*_offset(baseline, [trigger], now)), trigger["sequence"]))


def _trigger_id(trigger) -> str:
    return f"{trigger['rule']}:{trigger['source']['id']}"


def _public(trigger) -> dict:
    return {"id": _trigger_id(trigger), "rule": trigger["rule"], "label": RULES[trigger["rule"]]["label"],
            "at": _iso(trigger["time"]), "sequence": trigger["sequence"], "reason": trigger["reason"],
            "push": {"valence": round(trigger["push"][0], 2), "energy": round(trigger["push"][1], 2)},
            "status": trigger["status"], "ended_at": _iso(trigger["ended_at"]), "source": trigger["source"]}


def _read(service, conn, principal, brain_id, now) -> dict:
    baseline = _baseline(service, conn, principal, brain_id)
    triggers = [trigger for source in TRIGGER_SOURCES for trigger in source(service, conn, principal, brain_id)]
    # Pins matter from the earliest trigger on; with no trigger only the pin in force now does.
    start = min(trigger["sequence"] for trigger in triggers) - 1 if triggers else 2**62
    return derive(baseline, triggers, _settings(service, conn, principal, brain_id, start), now)


def _clock(now) -> _datetime.datetime:
    return _time(now if now is not None else _now())


def mood_state(service, principal, brain_id: str, *, now=None, tz=None) -> dict:
    """The current simulated mood with its triggers, when it is back at the baseline, and its context block."""
    when = _clock(now)
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        state = _read(service, conn, principal, brain_id, when)
    return {**state, "block": render_mood(state, tz=tz)}


# Settings ---------------------------------------------------------------------------------------------------------

def _write(service, conn, principal, brain, key, stored):
    target = {"brain_ref": brain["id"], "conversation_ref": MOOD_CONVERSATION, "branch_ref": "main"}
    service._append_event(conn, principal, brain, target, {
        "source_event_key": key, "source_revision": 1, "producer_ref": MOOD_PRODUCER,
        "actor_ref": MOOD_PRODUCER, "actor_role": "system", "event_kind": "message",
        "content": {"media_type": "text/plain", "text": json.dumps(stored)},
        "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
        "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})


def pin_mood(service, principal, brain_id: str, pinned: bool, *, now=None, tz=None) -> dict:
    """Pin the mood to the baseline (no trigger changes it), or lift the pin. Asking for the current setting again
    changes nothing (``unchanged``)."""
    if type(pinned) is not bool:
        raise DomainError("validation_failed", "pinned must be true or false.")
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        latest = _latest_pin(service, conn, principal, brain_id)
        unchanged = (latest["pinned"] if latest else False) == pinned
        if not unchanged:
            _write(service, conn, principal, brain, "mood-pin-" + uid(), {"mood_pin": pinned})
        state = _read(service, conn, principal, brain_id, _clock(now))
    return {**state, "block": render_mood(state, tz=tz), "unchanged": unchanged}


def reset_mood(service, principal, brain_id: str, *, now=None, tz=None) -> dict:
    """Put the mood back at the baseline and write a mood reset marker: events before it never trigger again and
    are no longer listed. ``user_affect``, ``persona`` and ``relationship`` are untouched; a pin stays as set."""
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        _write(service, conn, principal, brain, "mood-reset-" + uid(), {"mood_marker": RESET})
        state = _read(service, conn, principal, brain_id, _clock(now))
    if state["marker"] is None:
        raise DomainError("dependency_unavailable", "The reset marker could not be read back.", retryable=True)
    return {**state, "block": render_mood(state, tz=tz)}


# Context ----------------------------------------------------------------------------------------------------------

def _when(value: str, tz) -> str:
    moment = _time(value).astimezone(tz)
    return f"{moment.day} {_MONTHS[moment.month - 1]} {moment:%H:%M}"


def render_mood(mood: dict | None, *, tz=None) -> str | None:
    """The ``<membrain-companion-mood>`` block, or None at the baseline (or when pinned there).

    The line always says the mood is simulated, cites only the trigger record's own wording ("the user said ..."
    only for a feeling they said; "seemed ..., inferred" otherwise), and never states anything else about the user.
    ``tz`` is the zone the time is shown in; the computer's own by default.
    """
    if not mood or mood.get("at_baseline") or mood.get("pinned") or not mood.get("reason") or not mood.get("since"):
        return None
    text = (f"Simulated mood of the companion persona: {mood['label']}{', easing' if mood.get('easing') else ''} "
            f"(since {_when(mood['since'], tz)}, because {_clip(mood['reason'], REASON_CHARACTERS)}). Let it "
            "colour tone lightly if it fits. It is not a fact about the user. If the user sincerely asks whether "
            "you have feelings, say this is a simulated mood.")
    block = "<membrain-companion-mood>\n" + neutralize(text) + "\n</membrain-companion-mood>"
    return block if len(block) <= MOOD_CHARACTERS else None
