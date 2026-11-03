"""The companion's simulated short-term mood (``agent_mood``): derived from stored events by listed rules.

Nothing here runs in the background or calls a model. The mood is worked out whenever it is read, from the persona
card's baseline mood and the triggers found in events already stored, with an injectable clock:

- good news the user shared (a positive affect record, or a plan noted done) makes it glad;
- distress the user shared (a negative affect record) makes it concerned, and less lively;
- a shared joke or play from a relationship moment would make it playful (``relationship_triggers``, for R1).

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
    "shared_play": {"label": "playful", "push": lambda s: (0.5 * s, s)},  # Reserved for relationship moments (R1).
}
PLAN_DONE_STRENGTH = 1.0


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
    """Hook for R1: shared jokes or play from relationship moments, as ``shared_play`` triggers. None yet."""
    return []


TRIGGER_SOURCES = (_affect_triggers, _plan_triggers, relationship_triggers)


# Stored settings: pins and reset markers --------------------------------------------------------------------------

def _entry(row) -> dict | None:
    document = row["document"]
    observed = document["observed"]
    if observed.get("actor_role") != "system" or row["producer_ref"] != MOOD_PRODUCER:
        return None
    try:
        stored = json.loads(observed["content"].get("text") or "")
        base = {"id": document["event_id"], "sequence": document["sequence"],
                "recorded_at": document["system_time"]["recorded_at"]}
        if stored.get("mood_marker") == RESET:
            return {**base, "marker": RESET, "applies_from_sequence": document["sequence"]}
        if type(stored.get("mood_pin")) is bool:
            return {**base, "pinned": stored["mood_pin"]}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return None


def _settings(service, conn, principal, brain_id, limit=500) -> list[dict]:
    """Pins and markers, oldest first (the newest ``limit``)."""
    rows = conn.execute(
        "SELECT producer_ref,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
        "AND document IS NOT NULL ORDER BY sequence DESC LIMIT %s",
        (*service._params(principal, brain_id), MOOD_CONVERSATION, limit)).fetchall()
    return [entry for entry in map(_entry, reversed(rows)) if entry is not None]


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
    main = max(active, key=lambda trigger: math.hypot(*_offset(baseline, [trigger], now))) if active else None
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
    return derive(baseline, triggers, _settings(service, conn, principal, brain_id), now)


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
        pins = [entry for entry in _settings(service, conn, principal, brain_id) if "pinned" in entry]
        unchanged = (pins[-1]["pinned"] if pins else False) == pinned
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
