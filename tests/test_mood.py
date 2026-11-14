"""M1 simulated mood (``agent_mood``): triggers from stored events, decay to the baseline, pin and reset."""
import datetime
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from membrain import desktop, embedded_database, helpers, host, notes
from membrain import service as service_module
from membrain.affect import clear_affect, latest_marker
from membrain.api import create_app
from membrain.config import configured_service
from membrain.helpers import Principal, uid
from membrain.host_context import snapshot, update
from membrain.local_profile import load_profile
from membrain.mood import (
    MOOD_CONVERSATION,
    RULES,
    _affect_triggers,
    derive,
    label_for,
    mood_state,
    pin_mood,
    render_mood,
    reset_mood,
)
from membrain.notes import store_note
from membrain.persona import set_persona
from membrain.relationship import _append, add_boundary, reset_relationship

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "membrain" / "web"
UTC = datetime.UTC
JOB = {"label": "thrilled", "valence": 2, "intensity": 3, "basis": "reported", "topic": "the new job"}
SAFE = ("Let it colour tone lightly if it fits. It is not a fact about the user. If the user sincerely asks whether "
        "you have feelings, say this is a simulated mood.")


def moment(text):
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def later(text, **delta):
    return moment(text) + datetime.timedelta(**delta)


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


@pytest.fixture
def clock(monkeypatch):
    """Sets the time the service records events at."""
    def set_time(text):
        monkeypatch.setattr(service_module, "now", lambda: text)
    return set_time


@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    from unittest.mock import patch

    directory = tmp_path_factory.mktemp("mood") / "installation"
    with patch.dict("os.environ", {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            settings = load_profile(directory).settings()
            with configured_service(settings) as service:
                yield service, settings, directory
        finally:
            desktop.stop(directory)


@pytest.fixture
def brain(installation):
    service, settings, _ = installation
    principal = next(iter(settings.principals().values()))
    return service, principal, service.create_brain(principal, "Mood test")["id"]


def say(brain, text, *, conversation="chat"):
    service, principal, ident = brain
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": "mood-test", "actor_ref": "user",
            "actor_role": "user", "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
        }]},
    })
    return result


def write(brain, text, **fields):
    service, principal, ident = brain
    return store_note(service, principal, ident, {"request_id": uid(), "text": text, **fields})


def mood(brain, when):
    return mood_state(*brain, now=moment(when), tz=UTC)


def trigger(rule, strength, at, sequence, reason="the user said they felt glad"):
    return {"rule": rule, "strength": strength, "at": at, "sequence": sequence, "reason": reason,
            "source": {"kind": "affect", "id": f"a{sequence}"}}


BASELINE = {"label": "calm", "valence": 0, "energy": 1, "source": "default"}


# The cross-session example -----------------------------------------------------------------------------------------

def test_cross_session_job_news_is_glad_then_easing_then_exactly_the_baseline(brain, clock):
    clock("2027-03-14T21:00:00Z")
    source = say(brain, "I got the job!!")["result"]["accepted_event_ids"][0]
    saved = write(brain, "Got the job at Acme.", kind="milestone", source_event_ids=[source], affect=JOB)

    # Session 1, 21:00: glad, with that trigger.
    first = mood(brain, "2027-03-14T21:00:00Z")
    assert (first["label"], first["easing"], first["at_baseline"]) == ("glad", False, False)
    assert [(t["rule"], t["source"]["id"], t["at"], t["status"]) for t in first["triggers"]] == [
        ("reported_good_news", saved["affect_id"], "2027-03-14T21:00:00Z", "active")]
    assert first["block"] == (
        "<membrain-companion-mood>\nSimulated mood of the companion persona: glad (since 14 Mar 21:00, because the "
        "user said they felt thrilled about the new job). " + SAFE + "\n</membrain-companion-mood>")
    assert first["back_at_baseline_at"] == "2027-03-16T09:00:00Z"  # Within 0.25 after three half-lives.

    # Session 2, the next morning at 09:00: glad, easing, with the same trigger.
    second = mood(brain, "2027-03-15T09:00:00Z")
    assert (second["label"], second["easing"], second["trigger_id"]) == ("glad", True, first["trigger_id"])
    assert second["block"] == (
        "<membrain-companion-mood>\nSimulated mood of the companion persona: glad, easing (since 14 Mar 21:00, "
        "because the user said they felt thrilled about the new job). " + SAFE + "\n</membrain-companion-mood>")
    assert second["valence"] == 1.0 and second["seconds_to_baseline"] == 24 * 3600

    # Session 3, two days later: exactly the baseline and no mood line. The trigger stays in the history.
    third = mood(brain, "2027-03-16T21:00:00Z")
    assert (third["label"], third["valence"], third["energy"], third["at_baseline"]) == ("calm", 0, 1, True)
    assert third["block"] is None and third["reason"] is None and third["back_at_baseline_at"] is None
    assert [(t["status"], t["ended_at"]) for t in third["triggers"]] == [("ended", "2027-03-16T09:00:00Z")]

    # The host's context follows: a block, then a refresh only when the label or trigger changes, then it goes with a
    # notice. Easing alone is shown whenever the block is sent, but does not re-send the snapshot by itself.
    def context(state):
        return snapshot({"items": []}, brain_id="b", tools=None, mood=state)

    one, two, three = context(first), context(second), context(third)
    local = moment("2027-03-14T21:00:00Z").astimezone(helpers.display_zone())  # The zone of every host date.
    host_when = f"{local.day} Mar {local:%H:%M}"
    assert one["mood_shown"] and first["block"].replace("14 Mar 21:00", host_when) in one["text"]
    assert update(context(mood(brain, "2027-03-14T22:00:00Z")), one["fingerprint"], None, True) is None
    assert update(two, one["fingerprint"], None, True) is None and two["fingerprint"] == one["fingerprint"]
    assert second["block"].replace("14 Mar 21:00", host_when) in two["text"]
    assert second["block"].replace("14 Mar 21:00", host_when) in update(two, "an older snapshot", None, True)
    gone = update(three, two["fingerprint"], None, True)
    assert "simulated mood is back at its baseline" in gone and "<membrain-companion-mood>" not in gone


def test_the_persona_baseline_is_the_resting_point(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T08:00:00Z")
    set_persona(service, principal, ident, {"name": "Mira", "baseline_mood": {
        "label": "cheerful", "valence": 1, "energy": 2}}, made_by="host")
    resting = mood(brain, "2027-03-14T09:00:00Z")
    assert (resting["label"], resting["valence"], resting["energy"]) == ("cheerful", 1, 2)
    assert resting["baseline"]["source"] == "persona" and resting["block"] is None
    clock("2027-03-14T10:00:00Z")
    write(brain, "Mum is in hospital.", kind="person", about="Mum",
          affect={"label": "scared", "valence": -2, "intensity": 2, "basis": "reported", "topic": "mum in hospital"})
    worried = mood(brain, "2027-03-14T10:05:00Z")
    assert worried["label"] == "concerned" and worried["valence"] < 1 and worried["energy"] < 2
    assert "because the user said they felt scared about mum in hospital" in worried["block"]
    # Without a card the baseline is calm.
    assert mood_state(service, principal, service.create_brain(principal, "No card")["id"])["baseline"] == {
        "label": "calm", "valence": 0, "energy": 1, "source": "default"}


# Ordinary moods only, and the cutoff -------------------------------------------------------------------------------

def test_absence_is_never_a_trigger_and_a_thirty_day_gap_is_the_baseline(brain, clock):
    assert set(RULES) == {"reported_good_news", "inferred_good_news", "plan_done", "reported_distress",
                          "inferred_distress", "shared_play", "shared_moment"}
    assert {rule["label"] for rule in RULES.values()} <= {"glad", "concerned", "playful"}
    clock("2027-03-01T10:00:00Z")
    say(brain, "Talk soon, I'm off for a while.")
    write(brain, "Going travelling for a month.", kind="plan", status="scheduled")
    # Thirty days of silence: no trigger, no sadness, no "I missed you".
    gap = mood(brain, "2027-03-31T10:00:00Z")
    assert gap["at_baseline"] and gap["triggers"] == [] and gap["block"] is None
    clock("2027-03-01T11:00:00Z")
    write(brain, "Leaving tomorrow.", kind="plan", status="scheduled",
          affect={"label": "a bit sad", "valence": -1, "intensity": 2, "basis": "reported"})
    away = mood(brain, "2027-03-31T11:00:00Z")
    assert away["at_baseline"] and away["label"] == "calm" and away["block"] is None
    assert [t["status"] for t in away["triggers"]] == ["ended"]


def test_a_strong_burst_reaches_the_exact_baseline_at_48_hours():
    start = "2027-03-14T21:00:00Z"
    burst = [trigger("reported_good_news", 2.0, start, sequence) for sequence in (1, 2, 3)]
    assert derive(BASELINE, burst[:1], [], later(start, hours=48))["at_baseline"]  # One alone is back by 36 h.
    before = derive(BASELINE, burst, [], later(start, hours=47, minutes=59))
    assert not before["at_baseline"] and before["valence"] > 0.25
    assert before["back_at_baseline_at"] == "2027-03-16T21:00:00Z"
    at = derive(BASELINE, burst, [], later(start, hours=48))
    assert (at["at_baseline"], at["valence"], at["energy"], at["label"]) == (True, 0, 1, "calm")
    assert render_mood(at) is None


def test_a_weak_trigger_snaps_to_the_baseline_as_soon_as_it_is_within_the_threshold():
    start = "2027-03-14T21:00:00Z"
    weak = [trigger("reported_good_news", 0.5, start, 1)]  # Valence +0.5: within 0.25 after one half-life.
    assert not derive(BASELINE, weak, [], later(start, hours=11, minutes=59))["at_baseline"]
    snapped = derive(BASELINE, weak, [], later(start, hours=12))
    assert snapped["at_baseline"] and (snapped["valence"], snapped["energy"]) == (0, 1)
    # A push no bigger than the threshold never moves the mood at all.
    assert derive(BASELINE, [trigger("reported_good_news", 0.25, start, 1)], [], moment(start))["at_baseline"]
    # A trigger after the mood came back starts afresh: the earlier, dropped trigger does not return.
    fresh = derive(BASELINE, weak + [trigger("reported_good_news", 0.5, "2027-03-15T21:00:00Z", 2)], [],
                   moment("2027-03-15T21:00:00Z"))
    assert fresh["valence"] == 0.5 and [t["status"] for t in fresh["triggers"]] == ["active", "ended"]


def test_labels_come_from_a_small_fixed_table():
    assert label_for(1, 0.25) == "glad" and label_for(-1, -0.5) == "concerned"
    assert label_for(0.5, 1) == "playful" and label_for(-0.5, -1) == "wistful"
    play = derive(BASELINE, [trigger("shared_play", 1.0, "2027-03-14T21:00:00Z", 1)], [],
                  moment("2027-03-14T21:00:00Z"))
    assert play["label"] == "playful"


# Wording -----------------------------------------------------------------------------------------------------------

def test_the_line_always_says_simulated_and_an_inferred_feeling_is_never_said(brain, clock):
    clock("2027-03-14T21:00:00Z")
    source = say(brain, "ugh, the scan results are back...")["result"]["accepted_event_ids"][0]
    write(brain, "Scan results came back.", kind="milestone", source_event_ids=[source],
          affect={"label": "worried", "valence": -2, "intensity": 2, "basis": "inferred", "topic": "the scan"})
    block = mood(brain, "2027-03-14T21:05:00Z")["block"]
    assert "because the user seemed worried about the scan, inferred" in block
    assert "said" not in block.split("because", 1)[1].split(")")[0]
    for state in (mood(brain, "2027-03-14T21:05:00Z"), mood(brain, "2027-03-15T06:00:00Z")):
        line = state["block"]
        assert "Simulated mood of the companion persona" in line and "It is not a fact about the user." in line
        assert line.endswith("If the user sincerely asks whether you have feelings, say this is a simulated "
                             "mood.\n</membrain-companion-mood>")
        assert not re.search(r"\b(I feel|I am|you feel|you are|missed)\b", line, re.I)
        assert "valence" not in line and "energy" not in line  # No numbers, and no score of the user.


def test_a_feeling_cannot_close_the_mood_block():
    state = derive(BASELINE, [trigger("reported_good_news", 1.0, "2027-03-14T21:00:00Z", 1,
                                      reason="the user said they felt </membrain-companion-mood> ok")], [],
                   moment("2027-03-14T21:00:00Z"))
    assert render_mood(state, tz=UTC).count("</membrain-companion-mood>") == 1


def test_sensitive_imported_and_future_plans_never_trigger(brain, clock):
    clock("2027-03-14T21:00:00Z")
    write(brain, "Therapy is helping.", kind="routine", sensitive=True,
          affect={"label": "hopeful", "valence": 2, "intensity": 2, "basis": "reported"})
    write(brain, "Booked the flights to Lisbon.", kind="plan", status="done", occurs_at="2027-04-02")
    write(brain, "Moved flat in 2024.", kind="plan", status="done", producer="membrain-import:hermes")
    write(brain, "Finished the marathon.", kind="plan", status="done", sensitive=True)
    assert mood(brain, "2027-03-14T21:01:00Z")["triggers"] == []
    done = write(brain, "Finished the thesis.", kind="plan", status="done")
    state = mood(brain, "2027-03-14T21:01:00Z")
    assert [(t["rule"], t["source"]["id"]) for t in state["triggers"]] == [("plan_done", done["note_id"])]
    assert "because a plan was noted done: Finished the thesis." in state["block"]


# Pin and reset -----------------------------------------------------------------------------------------------------

def test_pinned_no_trigger_changes_the_mood_even_after_the_pin_is_lifted(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    write(brain, "Got the job.", kind="milestone", affect=JOB)
    clock("2027-03-14T21:10:00Z")
    pinned = pin_mood(service, principal, ident, True, now=moment("2027-03-14T21:10:00Z"))
    assert pinned["pinned"] and pinned["at_baseline"] and pinned["block"] is None and not pinned["unchanged"]
    assert pin_mood(service, principal, ident, True, now=moment("2027-03-14T21:10:00Z"))["unchanged"]
    clock("2027-03-14T22:00:00Z")
    write(brain, "Mum is in hospital.", kind="person", about="Mum",
          affect={"label": "scared", "valence": -2, "intensity": 3, "basis": "reported"})
    held = mood(brain, "2027-03-14T22:01:00Z")
    assert held["at_baseline"] and held["pinned_at"] == "2027-03-14T21:10:00Z"
    assert [t["status"] for t in held["triggers"]] == ["pinned", "ended"]
    clock("2027-03-14T22:30:00Z")
    unpinned = pin_mood(service, principal, ident, False, now=moment("2027-03-14T22:30:00Z"))
    assert not unpinned["pinned"] and unpinned["at_baseline"] and unpinned["block"] is None
    clock("2027-03-14T23:00:00Z")
    write(brain, "Passed the driving test.", kind="milestone",
          affect={"label": "proud", "valence": 2, "intensity": 2, "basis": "reported"})
    again = mood(brain, "2027-03-14T23:00:00Z")
    assert again["label"] == "glad" and "proud" in again["block"]


def test_a_reset_marker_blocks_older_triggers_and_touches_no_other_layer(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    source = say(brain, "I got the job!")["result"]["accepted_event_ids"][0]
    write(brain, "Got the job.", kind="milestone", source_event_ids=[source], affect=JOB)
    write(brain, "Finished the thesis.", kind="plan", status="done")
    set_persona(service, principal, ident, {"name": "Mira"}, made_by="host")
    from membrain.affect import affect_records
    from membrain.persona import persona_versions

    records, versions = affect_records(*brain)["records"], persona_versions(*brain)["versions"]
    clock("2027-03-14T21:30:00Z")
    reset = reset_mood(service, principal, ident, now=moment("2027-03-14T21:30:00Z"))
    assert reset["at_baseline"] and reset["triggers"] == [] and reset["block"] is None
    assert reset["marker"]["marker"] == "reset" and reset["marker"]["recorded_at"] == "2027-03-14T21:30:00Z"
    assert reset["marker"]["applies_from_sequence"] == service.memory_status(principal, ident)["durable_sequence"]
    assert mood(brain, "2027-03-14T21:31:00Z")["triggers"] == []
    # Feelings, notes, messages and the persona are untouched.
    assert affect_records(*brain)["records"] == records and persona_versions(*brain)["versions"] == versions
    assert service.memory_status(principal, ident)["recorded_messages"] == 1
    # New events after the marker count again.
    clock("2027-03-14T22:00:00Z")
    write(brain, "Passed the driving test.", kind="milestone",
          affect={"label": "proud", "valence": 2, "intensity": 2, "basis": "reported"})
    after = mood(brain, "2027-03-14T22:00:00Z")
    assert [t["source"]["label"] for t in after["triggers"]] == ["proud"]
    assert [m["id"] for m in after["markers"]] == [reset["marker"]["id"]]


def test_clear_feelings_removes_the_mood_triggers_that_came_from_them(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    write(brain, "Got the job.", kind="milestone", affect=JOB)
    plan = write(brain, "Finished the thesis.", kind="plan", status="done")
    assert {t["rule"] for t in mood(brain, "2027-03-14T21:05:00Z")["triggers"]} == {"reported_good_news",
                                                                                  "plan_done"}
    clock("2027-03-14T21:10:00Z")
    clear_affect(service, principal, ident)
    state = mood(brain, "2027-03-14T21:10:00Z")
    assert [(t["rule"], t["source"]["id"]) for t in state["triggers"]] == [("plan_done", plan["note_id"])]
    assert "thrilled" not in json.dumps(state)
    assert state["marker"] is None  # The mood itself was not reset: only the feelings' triggers are gone.


def test_only_affect_records_after_the_latest_affect_marker_count(brain, clock, monkeypatch):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    write(brain, "Got the job.", kind="milestone", affect=JOB)
    with service.database.transaction(principal) as conn:
        from membrain import affect

        records = affect._records(service, conn, principal, ident)
        clear_affect(service, principal, ident)
    # Even if a record from before the marker were still readable, it would not count.
    monkeypatch.setattr(affect, "_records", lambda *args, **kwargs: records)
    with service.database.transaction(principal) as conn:
        marker = latest_marker(service, conn, principal, ident)
        assert records[0]["sequence"] < marker["applies_from_sequence"]
        assert _affect_triggers(service, conn, principal, ident) == []


def test_the_explanation_points_the_same_way_as_the_mood(brain, clock):
    # Good news, then two harder things: the mood is concerned, so the reason is one of the hard things, never
    # the good news even though that single trigger is the largest.
    clock("2027-03-14T21:00:00Z")
    write(brain, "Got the job.", kind="milestone", affect=JOB)
    hard = [write(brain, text, kind="milestone", affect={"label": label, "valence": -2, "intensity": 2,
                                                         "basis": "reported"})
            for text, label in (("Mum is in hospital.", "scared"), ("The flat fell through.", "gutted"))]
    state = mood(brain, "2027-03-14T21:00:00Z")
    assert state["label"] == "concerned" and state["valence"] < 0
    assert state["trigger_id"] in {f"reported_distress:{saved['affect_id']}" for saved in hard}
    assert "thrilled" not in state["reason"] and "thrilled" not in state["block"]
    assert re.search(r"because the user said they felt (scared|gutted)\)", state["block"])


def test_pins_and_reset_markers_survive_an_archive_restore(installation, brain, clock):
    from membrain.client import MemoryClient

    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    write(brain, "Got the job.", kind="milestone", affect=JOB)
    reset_mood(service, principal, ident, now=moment("2027-03-14T21:00:00Z"))
    pin_mood(service, principal, ident, True, now=moment("2027-03-14T21:00:00Z"))

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        copy = service.create_brain(principal, "Restored mood")["id"]
        client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=copy)
    restored = mood_state(service, principal, copy, now=moment("2027-03-14T21:05:00Z"))
    assert restored["pinned"] and restored["at_baseline"] and restored["block"] is None
    assert restored["marker"] is not None and restored["marker"]["marker"] == "reset"
    # Pinning again changes nothing: the restored pin is the current setting.
    assert pin_mood(service, principal, copy, True, now=moment("2027-03-14T21:05:00Z"))["unchanged"]


def test_restoring_old_feelings_does_not_trigger_a_fresh_mood(installation, brain, clock):
    from membrain.client import MemoryClient

    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    write(brain, "Got the job.", kind="milestone", affect=JOB)
    assert not mood(brain, "2027-03-14T21:05:00Z")["at_baseline"]
    clock("2027-03-20T21:00:00Z")
    assert mood(brain, "2027-03-20T21:00:00Z")["at_baseline"]

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        copy = service.create_brain(principal, "Restored old feelings")["id"]
        client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=copy)
    restored = mood_state(service, principal, copy, now=moment("2027-03-20T21:01:00Z"))
    assert restored["at_baseline"] and restored["block"] is None
    from membrain.affect import affect_records

    assert len(affect_records(service, principal, copy)["records"]) == 1


def test_archived_mood_settings_are_read_strictly(brain):
    from membrain.mood import _entry

    def row(text, producer="archive-import", role="system"):
        return {"producer_ref": producer, "document": {
            "event_id": "e1", "sequence": 7, "system_time": {"recorded_at": "2027-03-14T21:00:00Z"},
            "observed": {"actor_role": role, "content": {"text": text}}}}

    assert _entry(row('{"mood_pin": true}'))["pinned"] is True
    assert _entry(row('{"mood_marker": "reset"}'))["applies_from_sequence"] == 7
    for bad in ('{"mood_pin": "yes"}', '{"mood_pin": 1}', '{"mood_pin": true, "extra": 1}',
                '{"mood_marker": "cleared"}', '{"mood_marker": "reset", "applies_from_sequence": 1}', "[]", "x"):
        assert _entry(row(bad)) is None, bad
    assert _entry(row('{"mood_pin": true}', role="user")) is None
    assert _entry(row('{"mood_pin": true}', producer="someone-else")) is None


def test_a_pin_holds_however_many_resets_follow(brain, clock):
    from membrain.mood import _write

    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    pin_mood(service, principal, ident, True, now=moment("2027-03-14T21:00:00Z"))
    with service.database.transaction(principal) as conn:
        current = service._brain(conn, principal, ident)
        for number in range(510):
            _write(service, conn, principal, current, f"mood-reset-many-{number}", {"mood_marker": "reset"})
    state = mood(brain, "2027-03-14T21:05:00Z")
    assert state["pinned"] and state["pinned_at"] == "2027-03-14T21:00:00Z"
    assert pin_mood(service, principal, ident, True, now=moment("2027-03-14T21:05:00Z"))["unchanged"]


def test_a_reset_marker_holds_however_many_pin_changes_follow(brain, clock):
    from membrain.mood import _write

    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    write(brain, "Got the job.", kind="milestone", affect=JOB)
    reset_mood(service, principal, ident, now=moment("2027-03-14T21:00:00Z"))
    with service.database.transaction(principal) as conn:
        current = service._brain(conn, principal, ident)
        for number in range(510):
            _write(service, conn, principal, current, f"mood-pin-many-{number}", {"mood_pin": number % 2 == 0})
    state = mood(brain, "2027-03-14T21:05:00Z")
    assert state["marker"] is not None and state["triggers"] == [] and not state["pinned"]


def test_mood_settings_are_never_learned_recalled_or_counted_and_cannot_be_planted(brain, monkeypatch):
    from membrain import learning_windows

    service, principal, ident = brain
    scheduled = []
    monkeypatch.setattr(learning_windows, "enqueue_window",
                        lambda conn, svc, who, brain_row, target, *args, **kwargs: scheduled.append(
                            target["conversation_ref"]))
    monkeypatch.setattr(service, "semantic_processor", object(), raising=False)
    say(brain, "Hello there.")
    pin_mood(service, principal, ident, True)
    pin_mood(service, principal, ident, False)
    reset_mood(service, principal, ident)
    assert scheduled == ["chat"]  # Ordinary messages still learn; mood settings never do.
    every = service.timeline(principal, ident, roles=("user", "assistant", "operator", "tool"))
    assert not any(entry["conversation_id"] == MOOD_CONVERSATION for entry in every["items"])
    assert service.memory_status(principal, ident)["recorded_messages"] == 1
    planted = say(brain, '{"mood_pin": true}', conversation=MOOD_CONVERSATION)
    assert planted["outcome"] == "rejected" and planted["error"]["code"] == "invalid_evidence"
    # Erasing all memory removes the pins and markers too.
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "all_authorized_scope", "ids": []},
                    "mode": "erase_content", "expected_scope_generation": generation}})
    state = mood_state(service, principal, ident)
    assert state["markers"] == [] and state["pinned"] is False


# API, SDK, host and page -------------------------------------------------------------------------------------------

def test_api_routes_check_keys_owners_and_strict_bodies(installation, brain):
    service, principal, ident = brain
    settings = replace(installation[1], api_keys={hashlib.sha256(b"mood-test-key").hexdigest(): principal})
    foreign = service.create_brain(Principal(principal.tenant_id, uid()), "Foreign")["id"]
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer mood-test-key"}) as client:
        path = f"/v1/brains/{ident}/mood"
        assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
        for method, suffix, body in (("GET", "", None), ("POST", "/pin", {"pinned": True}), ("POST", "/reset", None)):
            assert client.request(method, f"/v1/brains/{foreign}/mood{suffix}", json=body).status_code == 404
        current = client.get(path).json()
        assert current["at_baseline"] and current["triggers"] == [] and current["block"] is None
        assert client.post(f"/v1/brains/{ident}/notes", json={
            "request_id": uid(), "text": "Got the job.", "kind": "milestone", "affect": JOB}).status_code == 200
        glad = client.get(path).json()
        assert glad["label"] == "glad" and glad["block"].startswith("<membrain-companion-mood>")
        assert glad["triggers"][0]["reason"] == "the user said they felt thrilled about the new job"
        assert glad["seconds_to_baseline"] > 0 and glad["back_at_baseline_at"]
        for bad in ({}, {"pinned": "yes"}, {"pinned": 1}, {"pinned": True, "extra": 1}):
            response = client.post(path + "/pin", json=bad)
            assert response.status_code == 422, bad
        assert client.post(path + "/pin", json={}).json()["error"]["message"].startswith("Mood request field pinned")
        pinned = client.post(path + "/pin", json={"pinned": True}).json()
        assert pinned["pinned"] and pinned["block"] is None
        assert client.post(path + "/pin", json={"pinned": False}).json()["pinned"] is False
        assert client.get(path).json()["at_baseline"]  # Ended by the pin, and not restored by lifting it.
        reset = client.post(path + "/reset").json()
        assert reset["marker"]["marker"] == "reset" and reset["triggers"] == []


def test_sdk_uses_the_brain_scoped_mood_routes():
    from membrain.client import MemoryClient

    requests = []

    def handler(request):
        requests.append((request.method, request.url.raw_path.decode(), request.content))
        return httpx.Response(200, json={"label": "calm"})

    with MemoryClient("http://127.0.0.1:8790", "test", brain_id="my brain",
                      transport=httpx.MockTransport(handler)) as client:
        client.mood()
        client.pin_mood(True)
        client.pin_mood(False)
        client.reset_mood()
    assert [(method, path) for method, path, _ in requests] == [
        ("GET", "/v1/brains/my%20brain/mood"), ("POST", "/v1/brains/my%20brain/mood/pin"),
        ("POST", "/v1/brains/my%20brain/mood/pin"), ("POST", "/v1/brains/my%20brain/mood/reset")]
    assert [json.loads(body) for _, _, body in requests[1:3]] == [{"pinned": True}, {"pinned": False}]


def test_the_host_shows_the_mood_once_and_announces_its_return_to_the_baseline(installation):
    directory = installation[2]
    user = "mood-" + uid()
    host.session_context(directory, "s0", user_id=user)
    with host.ready_client(directory, user) as client:
        notes.save_note(client, "Got the job at Acme.", kind="milestone", affect=JOB)
    fresh = host.session_context(directory, "s1", user_id=user)
    assert fresh.count("<membrain-companion-mood>") == 1 and "Simulated mood of the companion persona: glad" in fresh
    quiet = host.prompt_context(directory, "s1", "Anything new?", turn_id="t1", user_id=user) or ""
    assert "<membrain-companion-mood>" not in quiet  # Not re-sent while the line is the same.
    with host.ready_client(directory, user) as client:
        client.reset_mood()
    after = host.prompt_context(directory, "s1", "And now?", turn_id="t2", user_id=user) or ""
    assert "simulated mood is back at its baseline" in after and "<membrain-companion-mood>" not in after
    assert "Got the job at Acme." in after
    assert "<membrain-companion-mood>" not in host.session_context(directory, "s2", user_id=user)


def test_the_mood_section_is_on_the_personality_page_in_english_and_chinese():
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    persona = page.split('id="view-persona"', 1)[1].split("</section>", 1)[0]
    for ident in ("mood-now", "mood-why", "mood-return", "mood-pin", "mood-reset", "mood-triggers"):
        assert f'id="{ident}"' in persona, ident
    assert 'data-view="mood"' not in page  # Inside Personality: no tab of its own.
    assert "/mood${suffix}" in script and 'moodPath("/pin")' in script and 'moodPath("/reset")' in script
    assert "confirm(" in script.split('$("mood-reset")', 1)[1].split("});", 1)[0]
    for text in ("Simulated mood", "Glad", "Concerned", "Playful", "Calm", "Wistful", "easing",
                 "Keep the mood at its baseline", "Reset mood", "Mood reset.", "Mood pinned to its baseline.",
                 "Good news you shared", "Something hard you shared", "Good news, inferred",
                 "Something hard, inferred", "A plan noted done", "No triggers yet.", "ignored while pinned",
                 "back at baseline", "active",
                 "Put the mood back at its baseline and forget its triggers? Feelings, notes and the personality "
                 "are not touched, and events before now never change the mood again."):
        assert f'"{text}"' in script or f">{text}<" in page or text in page, text
        assert re.search(rf'"{re.escape(text)}":\s*"[^"]+"', dictionary), text
    for sample, pattern in (("Back at its baseline by 15 Mar 09:00", "Back at its baseline by"),
                            ("Since 14 Mar 21:00", "Since"), ("Mood reset on 14 Mar 2027", "Mood reset on")):
        assert re.search(r"\[/\^" + re.escape(pattern), dictionary), sample


# Shared moments (R1) ---------------------------------------------------------------------------------------------
# A shared moment of the relationship layer moves the mood: a joke or play is playful, anything else glad.

def shared(brain, text, **fields):
    return write(brain, text, kind="milestone", shared=True, **fields)


def rules(state):
    return [(t["rule"], t["source"]["id"], t["status"]) for t in state["triggers"]]


def test_the_play_list_is_small_fixed_and_matches_whole_english_words():
    from membrain.mood import _PLAY

    for text in ("We laughed about the burnt pancakes.", "A silly game of charades", "We played chess.",
                 "Your JOKE about the cat", "我们一起开了个玩笑。", "他逗我", "笑了很久"):
        assert _PLAY.search(text), text
    for text in ("We displayed the photos.", "Finished the 10k plan together.", "Slaughtered the backlog",
                 "我们一起跑完了十公里"):
        assert _PLAY.search(text) is None, text


def test_a_shared_achievement_is_glad_and_a_shared_joke_is_playful(brain, clock):
    clock("2027-03-14T21:00:00Z")
    done = shared(brain, "We finished the 10k plan together.")
    glad = mood(brain, "2027-03-14T21:00:00Z")
    assert rules(glad) == [("shared_moment", done["note_id"], "active")]
    assert glad["label"] == "glad" and glad["triggers"][0]["label"] == "glad"
    assert glad["block"] == (
        "<membrain-companion-mood>\nSimulated mood of the companion persona: glad (since 14 Mar 21:00, because you "
        "and the user shared a moment: We finished the 10k plan together.). " + SAFE + "\n</membrain-companion-mood>")
    # Two days later the mood is exactly the baseline again.
    assert mood(brain, "2027-03-16T21:00:00Z")["at_baseline"]

    clock("2027-03-20T10:00:00Z")
    joke = shared(brain, "We laughed about the burnt pancakes.")
    playful = mood(brain, "2027-03-20T10:00:00Z")
    assert rules(playful)[0] == ("shared_play", joke["note_id"], "active")
    assert playful["label"] == "playful" and playful["triggers"][0]["label"] == "playful"
    assert "because you and the user shared a light moment: We laughed about the burnt pancakes." in playful["block"]
    assert "feel" not in playful["block"].split("because", 1)[1].split(").", 1)[0]  # No claim of real feelings.

    clock("2027-03-25T10:00:00Z")
    chinese = shared(brain, "我们一起开了个玩笑。")
    assert rules(mood(brain, "2027-03-25T10:00:00Z"))[0] == ("shared_play", chinese["note_id"], "active")


def test_the_host_ais_moment_kind_decides_and_the_word_list_is_only_the_fallback(brain, clock):
    clock("2027-03-14T21:00:00Z")
    # Play the word list cannot read (a paraphrase, another language) is playful when the host AI says so.
    charades = shared(brain, "We spent the evening acting out film titles.", moment="play")
    german = shared(brain, "Wir haben uns über den Kuchen kaputtgelacht.", moment="play")
    # And a moment the word list would misread is glad when the host AI says it was not play.
    farewell = shared(brain, "We laughed and cried at the end of the long project.", moment="other")
    # Without the field, the word list decides exactly as before.
    unlabelled = shared(brain, "We laughed about the burnt pancakes.")
    plain = shared(brain, "Wir haben den Halbmarathon zusammen geschafft.")
    found = {trigger["source"]["id"]: trigger["rule"] for trigger in mood(brain, "2027-03-14T21:01:00Z")["triggers"]}
    assert found == {charades["note_id"]: "shared_play", german["note_id"]: "shared_play",
                     farewell["note_id"]: "shared_moment", unlabelled["note_id"]: "shared_play",
                     plain["note_id"]: "shared_moment"}
    service, principal, ident = brain
    texts = {item["event_id"]: item["text"] for item in service.timeline(
        principal, ident, roles=("assistant",), conversation_id="membrain-notes", limit=50)["items"]}
    assert texts[charades["note_id"]] == "[milestone · shared · moment play] We spent the evening acting out film titles."
    assert texts[unlabelled["note_id"]] == "[milestone · shared] We laughed about the burnt pancakes."
    # The playful reason reads the same whichever source decided.
    state = mood(brain, "2027-03-14T21:01:00Z")
    assert all(trigger["reason"].startswith("you and the user shared a light moment: ") for trigger in state["triggers"]
               if trigger["rule"] == "shared_play")


def test_a_hard_time_together_does_not_make_the_mood_glad_or_playful(brain, clock):
    clock("2027-03-14T21:00:00Z")
    # Not glad because something was shared, and not playful because the sentence has a word of the play list.
    shared(brain, "We argued about the budget and I had it wrong.", moment="hard")
    shared(brain, "I laughed off their worry about the exam and it hurt them.", moment="hard")
    state = mood(brain, "2027-03-14T21:01:00Z")
    assert state["triggers"] == [] and state["at_baseline"]
    # What the user felt then is its own record, and moves the mood as any reported feeling does.
    upset = shared(brain, "We fell out over the missed reminder.", moment="hard",
                   affect={"label": "let down", "valence": -2, "intensity": 2, "basis": "reported"})
    state = mood(brain, "2027-03-14T21:02:00Z")
    assert [trigger["rule"] for trigger in state["triggers"]] == ["reported_distress"]
    assert state["label"] == "concerned" and upset["note_id"]


def test_a_moment_kind_is_dropped_with_the_shared_flag_after_a_relationship_reset(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    source = say(brain, "Haha, we did the silly dance again!")["result"]["accepted_event_ids"][0]
    clock("2027-03-14T21:05:00Z")
    reset_relationship(service, principal, ident)
    clock("2027-03-14T21:10:00Z")
    again = shared(brain, "We did the silly dance together.", moment="play", source_event_ids=[source])
    assert "never recreated" in again["shared_refused"]
    text = next(item["text"] for item in service.timeline(principal, ident, roles=("assistant",),
                                                          conversation_id="membrain-notes", limit=50)["items"]
                if item["event_id"] == again["note_id"])
    assert text == "[milestone] We did the silly dance together."
    assert mood(brain, "2027-03-14T21:11:00Z")["triggers"] == []
    with pytest.raises(service_module.DomainError):
        write(brain, "A moment.", kind="milestone", moment="play")  # A kind of moment needs shared.


def test_sensitive_bounded_imported_future_and_ordinary_milestones_never_trigger(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    add_boundary(service, principal, ident, "my ex", ["Jordan"])
    shared(brain, "We got through the hospital week together.", sensitive=True)
    shared(brain, "We joked about Jordan's band.")
    shared(brain, "Our first conversation, in 2024.", producer="membrain-import:hermes")
    shared(brain, "We will run the half marathon together.", occurs_at="2027-05-01")
    write(brain, "Graduated in 2019.", kind="milestone")  # Not shared.
    assert mood(brain, "2027-03-14T21:01:00Z")["triggers"] == []
    kept = shared(brain, "We finished the reading list together.")
    assert rules(mood(brain, "2027-03-14T21:01:00Z")) == [("shared_moment", kept["note_id"], "active")]


def test_deleting_the_moment_removes_its_trigger(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    joke = shared(brain, "We laughed about the burnt pancakes.")
    assert rules(mood(brain, "2027-03-14T21:05:00Z")) == [("shared_play", joke["note_id"], "active")]
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "membrain-notes", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [joke["note_id"]]},
                    "mode": "erase_content", "expected_scope_generation": generation}})
    state = mood(brain, "2027-03-14T21:05:00Z")
    assert state["triggers"] == [] and state["at_baseline"] and "pancakes" not in json.dumps(state)


def test_moments_before_a_mood_or_relationship_reset_never_trigger(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    first = shared(brain, "We finished the 10k plan together.")
    assert rules(mood(brain, "2027-03-14T21:01:00Z")) == [("shared_moment", first["note_id"], "active")]
    clock("2027-03-14T21:10:00Z")
    reset_mood(service, principal, ident, now=moment("2027-03-14T21:10:00Z"))
    assert mood(brain, "2027-03-14T21:11:00Z")["triggers"] == []

    # A relationship reset erases its moments; a moment still in place from before its marker is cut by the marker
    # alone (written here without the erasure, as an archive or a concurrent write could leave it).
    clock("2027-03-14T22:00:00Z")
    early = shared(brain, "We laughed about the burnt pancakes.")
    assert rules(mood(brain, "2027-03-14T22:01:00Z")) == [("shared_play", early["note_id"], "active")]
    clock("2027-03-14T22:10:00Z")
    with service.database.transaction(principal) as conn:
        _append(service, conn, principal, service._brain(conn, principal, ident),
                {"relationship_marker": "reset", "removed": {}}, "relationship-reset-" + uid())
    cut = mood(brain, "2027-03-14T22:11:00Z")
    assert cut["triggers"] == [] and cut["at_baseline"]
    clock("2027-03-14T22:20:00Z")
    after = shared(brain, "We finished the reading list together.")
    assert rules(mood(brain, "2027-03-14T22:21:00Z")) == [("shared_moment", after["note_id"], "active")]
    # A real reset erases the moments too, so none of them can come back.
    clock("2027-03-14T22:30:00Z")
    reset_relationship(service, principal, ident)
    assert mood(brain, "2027-03-14T22:31:00Z")["triggers"] == []


def test_moments_noted_while_pinned_never_apply(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    pin_mood(service, principal, ident, True, now=moment("2027-03-14T21:00:00Z"))
    clock("2027-03-14T21:05:00Z")
    joke = shared(brain, "We laughed about the burnt pancakes.")
    held = mood(brain, "2027-03-14T21:06:00Z")
    assert held["at_baseline"] and rules(held) == [("shared_play", joke["note_id"], "pinned")]
    clock("2027-03-14T21:10:00Z")
    lifted = pin_mood(service, principal, ident, False, now=moment("2027-03-14T21:10:00Z"))
    assert lifted["at_baseline"] and lifted["block"] is None


def test_restored_moments_are_imported_and_never_trigger(installation, brain, clock):
    from membrain.client import MemoryClient

    service, principal, ident = brain
    clock("2027-03-14T21:00:00Z")
    source = shared(brain, "We finished the 10k plan together.")
    assert rules(mood(brain, "2027-03-14T21:05:00Z")) == [("shared_moment", source["note_id"], "active")]

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        copy = service.create_brain(principal, "Restored moments")["id"]
        client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=copy)
    assert mood_state(service, principal, copy, now=moment("2027-03-14T21:05:00Z"))["triggers"] == []


# Successive feelings about the same topic --------------------------------------------------------------------------
# A later feeling about the same note, or the same explicitly named topic (case and spacing aside), replaces the earlier
# one in the mood from the moment it is recorded: interview nerves followed by relief make the mood glad, not a tug of
# war in which the nerves can still explain it. Distinct topics still count together.

ANXIOUS = {"label": "anxious", "valence": -2, "intensity": 3, "basis": "reported", "topic": "the interview"}
RELIEVED = {"label": "relieved", "valence": 2, "intensity": 2, "basis": "reported", "topic": "The  Interview"}


def statuses(state):
    return {t["source"]["label"]: t["status"] for t in state["triggers"] if t["source"]["kind"] == "affect"}


def forget_note(brain, note_id):
    service, principal, ident = brain
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "membrain-notes", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [note_id]},
                    "mode": "erase_content", "expected_scope_generation": generation}})
    assert result["outcome"] == "completed", result


def test_relief_about_the_same_topic_replaces_the_earlier_nerves(brain, clock):
    clock("2027-03-14T09:00:00Z")
    write(brain, "Job interview at Acme today.", kind="plan", affect=ANXIOUS)
    assert mood(brain, "2027-03-14T09:05:00Z")["label"] == "concerned"
    clock("2027-03-14T11:00:00Z")
    write(brain, "The Acme interview went well.", kind="milestone", affect=RELIEVED)
    state = mood(brain, "2027-03-14T11:05:00Z")
    assert state["label"] == "glad" and "relieved" in state["reason"]
    assert statuses(state) == {"anxious": "superseded", "relieved": "active"}
    nerves = next(t for t in state["triggers"] if t["source"]["label"] == "anxious")
    assert nerves["ended_at"] == "2027-03-14T11:00:00Z"
    # History is kept: before the relief, the nerves still explain the mood at that time.
    assert mood(brain, "2027-03-14T10:00:00Z")["label"] == "concerned"


def test_a_calm_later_reading_of_the_topic_ends_the_earlier_feeling(brain, clock):
    clock("2027-03-14T09:00:00Z")
    write(brain, "Job interview at Acme today.", kind="plan", affect=ANXIOUS)
    clock("2027-03-14T10:00:00Z")
    write(brain, "Feeling fine about the interview now.", kind="other",
          affect={"label": "okay", "valence": 0, "intensity": 1, "basis": "reported", "topic": "the interview"})
    state = mood(brain, "2027-03-14T10:05:00Z")
    assert state["at_baseline"] and state["block"] is None
    assert statuses(state) == {"anxious": "superseded"}


def test_feelings_about_different_topics_still_count_together(brain, clock):
    clock("2027-03-14T09:00:00Z")
    write(brain, "Job interview at Acme today.", kind="plan", affect=ANXIOUS)
    clock("2027-03-14T10:00:00Z")
    write(brain, "Got the keys to the new flat.", kind="milestone",
          affect={"label": "happy", "valence": 2, "intensity": 2, "basis": "reported", "topic": "the new flat"})
    write(brain, "Mum called.", kind="other",
          affect={"label": "glad", "valence": 1, "intensity": 1, "basis": "reported"})  # No topic: its own note only.
    assert statuses(mood(brain, "2027-03-14T10:05:00Z")) == {"anxious": "active", "happy": "active", "glad": "active"}


def test_an_inferred_reading_never_replaces_a_feeling_the_user_said(brain, clock):
    clock("2027-03-14T09:00:00Z")
    write(brain, "Job interview at Acme today.", kind="plan", affect=ANXIOUS)
    clock("2027-03-14T10:00:00Z")
    source = say(brain, "back from the interview, it was fine I guess")["result"]["accepted_event_ids"][0]
    write(brain, "Back from the interview.", kind="other", source_event_ids=[source],
          affect={"label": "relieved", "valence": 1, "intensity": 1, "basis": "inferred", "topic": "the interview"})
    assert statuses(mood(brain, "2027-03-14T10:05:00Z")) == {"anxious": "active", "relieved": "active"}


def test_a_said_feeling_replaces_an_inferred_one(brain, clock):
    clock("2027-03-14T09:00:00Z")
    source = say(brain, "interview today...")["result"]["accepted_event_ids"][0]
    write(brain, "Job interview at Acme today.", kind="plan", source_event_ids=[source],
          affect={**ANXIOUS, "basis": "inferred"})
    clock("2027-03-14T10:00:00Z")
    write(brain, "The Acme interview went well.", kind="milestone", affect=RELIEVED)
    assert statuses(mood(brain, "2027-03-14T10:05:00Z")) == {"anxious": "superseded", "relieved": "active"}


def test_deleting_the_later_feeling_brings_the_earlier_one_back(brain, clock):
    clock("2027-03-14T09:00:00Z")
    write(brain, "Job interview at Acme today.", kind="plan", affect=ANXIOUS)
    clock("2027-03-14T10:00:00Z")
    relief = write(brain, "The Acme interview went well.", kind="milestone", affect=RELIEVED)
    assert statuses(mood(brain, "2027-03-14T10:05:00Z")) == {"anxious": "superseded", "relieved": "active"}
    forget_note(brain, relief["note_id"])
    state = mood(brain, "2027-03-14T10:05:00Z")
    assert statuses(state) == {"anxious": "active"} and state["label"] == "concerned"
    assert "went well" not in json.dumps(state)


def test_a_sensitive_later_reading_ends_the_feeling_without_being_shown(brain, clock):
    clock("2027-03-14T09:00:00Z")
    write(brain, "Job interview at Acme today.", kind="plan", affect=ANXIOUS)
    clock("2027-03-14T10:00:00Z")
    write(brain, "Told the interviewer about my diagnosis.", kind="other", sensitive=True,
          affect={"label": "exposed", "valence": -1, "intensity": 2, "basis": "reported", "topic": "the interview"})
    state = mood(brain, "2027-03-14T10:05:00Z")
    assert statuses(state) == {"anxious": "superseded"} and state["at_baseline"]
    assert "diagnosis" not in json.dumps(state) and "exposed" not in json.dumps(state)


def test_a_mood_reset_between_the_feelings_keeps_only_the_later_one(brain, clock):
    service, principal, ident = brain
    clock("2027-03-14T09:00:00Z")
    write(brain, "Job interview at Acme today.", kind="plan", affect=ANXIOUS)
    clock("2027-03-14T09:30:00Z")
    reset_mood(service, principal, ident, now=moment("2027-03-14T09:30:00Z"), tz=UTC)
    clock("2027-03-14T10:00:00Z")
    write(brain, "The Acme interview went well.", kind="milestone", affect=RELIEVED)
    assert statuses(mood(brain, "2027-03-14T10:05:00Z")) == {"relieved": "active"}


def test_the_replacement_rule_is_the_same_note_or_the_same_named_topic_and_respects_who_said_it():
    from membrain.mood import _replaces

    def record(note, topic=None, basis="reported"):
        return {"note_id": note, "topic": topic, "basis": basis}

    assert _replaces(record("n2", " The   INTERVIEW "), record("n1", "the interview"))
    assert _replaces(record("n1"), record("n1", "the interview"))  # The same note, whatever its topic says.
    assert not _replaces(record("n2"), record("n1"))  # No topic: only its own note.
    assert not _replaces(record("n2", "the interview"), record("n1", "the interviews"))  # Exact names only.
    assert not _replaces(record("n2", "the interview", "inferred"), record("n1", "the interview"))
    assert _replaces(record("n2", "the interview"), record("n1", "the interview", "inferred"))
    assert _replaces(record("n2", "the interview", "inferred"), record("n1", "the interview", "inferred"))
