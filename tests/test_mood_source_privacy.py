import pytest
from test_affect import say, write
from test_persona_decisions import brain as brain

from membrain.host_context import snapshot
from membrain.mood import mood_state

pytestmark = pytest.mark.integration
FEELING = {"label": "thrilled", "basis": "reported", "valence": 2, "intensity": 3, "topic": "planetarium"}


def reading(brain, source, kind):
    fields = {"source_event_ids": [source]}
    if kind == "affect":
        fields["affect"] = FEELING
    elif kind == "plan":
        fields.update(kind="plan", status="done")
    else:
        fields.update(kind="milestone", shared=True)
    return write(brain, "Completed our planetarium visit.", **fields)


@pytest.mark.parametrize("kind", ["affect", "plan", "shared"])
@pytest.mark.parametrize("mark_after", [False, True])
def test_shared_sensitive_sources_cannot_drive_mood_or_its_automatic_context(brain, kind, mark_after):
    source = say(brain, "I am thrilled about our private planetarium visit.")
    if mark_after:
        reading(brain, source, kind)
        assert not mood_state(*brain)["at_baseline"]
    write(brain, "The planetarium visit is private.", kind="constraint", sensitive=True, source_event_ids=[source])
    if not mark_after:
        reading(brain, source, kind)
    state = mood_state(*brain)
    context = snapshot({"items": []}, brain_id=brain[2], tools=None, mood=state)
    assert state["at_baseline"] and state["triggers"] == []
    assert state["block"] is None
    assert not context["mood_shown"] and "planetarium" not in context["text"]


def test_private_successor_still_ends_a_public_feeling_without_exposing_the_new_trigger(brain):
    old = say(brain, "I'm excited about the interview.")
    write(brain, "Interview next week.", source_event_ids=[old],
          affect={**FEELING, "topic": "interview"})
    assert not mood_state(*brain)["at_baseline"]
    source = say(brain, "The private STARLIGHT result has changed how I feel about the interview.")
    write(brain, "STARLIGHT is private.", sensitive=True, source_event_ids=[source])
    newer = write(brain, "Interview result.", source_event_ids=[source],
                  affect={**FEELING, "topic": "interview", "label": "STARLIGHT worried", "valence": -2})
    state = mood_state(*brain)
    assert state["at_baseline"] and state["block"] is None
    assert len(state["triggers"]) == 1
    ended = state["triggers"][0]
    assert ended["status"] == "superseded" and ended["superseded_by"] is None
    assert ended["source"]["id"] != newer["affect_id"]
