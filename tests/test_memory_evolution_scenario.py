"""One fixed-clock experience crossing notes, cue indexes, affect, relationship and persona decisions.

Scripted host choices test state and provenance, not a model's interpretation or human-like behaviour.
"""
import datetime

from test_affect import write
from test_persona_confirmation import confirm, propose, turn, version
from test_persona_decisions import revise
from test_persona_growth import CARD, _restored, forget, listing
from test_persona_growth import brain as brain
from test_persona_growth import installation as installation

from membrain import helpers, message_cues
from membrain.affect import affect_records
from membrain.companion_map import companion_map
from membrain.mood import mood_state
from membrain.persona import restore_persona, set_persona
from membrain.relationship import relationship, reset_relationship


def test_an_experience_changes_with_evidence_without_recall_promoting_or_preserving_it(brain, monkeypatch):
    clock = [datetime.datetime(2026, 1, 5, 10, tzinfo=datetime.UTC)]
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: clock[0])
    set_persona(*brain, CARD, made_by="user")
    source = turn(brain, "Our practice interview at Cedar Studio was a fun shared game. My hands were shaking.")
    moment = write(brain, "Our first practice interview at Cedar Studio.", kind="milestone", shared=True,
                   moment="play", source_event_ids=[source], affect={"label": "nervous", "valence": -1,
                   "intensity": 2, "basis": "inferred", "topic": "practice interview", "felt_at": "2026-01-05"})
    message_cues.write(*brain, [{"event_id": source, "cues": ["user interview preparation shared activity"]}])
    proposal = propose(brain, source_event_ids=[source])
    first = mood_state(*brain)
    assert {item["rule"] for item in first["triggers"]} >= {"inferred_distress", "shared_play"}
    assert relationship(*brain)["familiarity"]["shared_moments"] == 1
    assert affect_records(*brain)["records"][0]["basis"] == "inferred"
    assert version(brain)["version"] == 1  # A host suggestion alone cannot change the character.

    service, principal, ident = brain
    def counts():
        with service.database.transaction(principal) as conn:
            return conn.execute("SELECT count(*) AS events FROM memory_events WHERE brain_id=%s", (ident,)).fetchone()

    before = counts()
    for _ in range(3):
        mood_state(*brain)
        relationship(*brain)
        companion_map(*brain)
        listing(brain)
    assert counts() == before
    assert affect_records(*brain)["records"][0]["basis"] == "inferred"

    # An edited original cannot keep its old interpretation alive, including an unaccepted personality change.
    clock[0] += datetime.timedelta(hours=1)
    revise(brain, source, "Correction: Cedar Studio was a serious solo interview, not our shared game. I felt calm.")
    assert affect_records(*brain)["records"] == []
    assert relationship(*brain)["familiarity"]["shared_moments"] == 0
    assert mood_state(*brain)["at_baseline"]
    assert next(item for item in listing(brain)["proposals"] if item["id"] == proposal["id"])["status"] == "withdrawn"
    with service.database.transaction(principal) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_message_cues WHERE brain_id=%s", (ident,)).fetchone()["n"] == 0

    # The next interpretation is explicitly reported. A new suggestion still needs the user's later answer.
    updated = write(brain, "Cedar Studio interview was a solo appointment.", kind="milestone",
                    source_event_ids=[source], affect={"label": "calm", "valence": 1, "intensity": 1,
                    "basis": "reported", "topic": "practice interview", "felt_at": "2026-01-05"})
    fresh = propose(brain, source_event_ids=[source])
    turn(brain, "Can we adjust how you help me?", "Shall I add patient to my persona?")
    yes = turn(brain, "Yes, please do.")
    confirm(brain, fresh["id"], yes)
    assert version(brain)["version"] == 2
    assert affect_records(*brain)["records"][0]["basis"] == "reported"
    assert {item["rule"] for item in mood_state(*brain)["triggers"]} == {"reported_good_news"}
    graph = companion_map(*brain)
    assert any(edge["target"] == "proposal:" + fresh["id"] and edge["type"] == "accepted_proposal"
               for edge in graph["edges"])
    assert not any(node["id"] == "note:" + moment["note_id"] for node in graph["nodes"])

    # Time apart returns the simulated mood to baseline; it cannot make the companion resentful.
    clock[0] += datetime.timedelta(days=3)
    assert mood_state(*brain)["at_baseline"]
    assert version(brain)["version"] == 2
    forget(brain, [source])
    assert affect_records(*brain)["records"] == []
    assert not any(node["id"] == "note:" + updated["note_id"] for node in companion_map(*brain)["nodes"])
    decided = next(item for item in listing(brain)["proposals"] if item["id"] == fresh["id"])
    assert decided["status"] == "accepted" and decided["sources"] == []
    assert version(brain)["version"] == 2  # Erasing evidence does not undo the user's accepted choice.
    brain = (*brain[:2], _restored(brain, "Restored evolution scenario"))
    assert affect_records(*brain)["records"] == []
    assert relationship(*brain)["familiarity"]["shared_moments"] == 0
    assert next(item for item in listing(brain)["proposals"] if item["id"] == fresh["id"])["sources"] == []
    restore_persona(*brain, 1, made_by="user")
    assert version(brain)["card"] == CARD
    reset_relationship(*brain)
    assert relationship(*brain)["familiarity"]["days"] == 0
