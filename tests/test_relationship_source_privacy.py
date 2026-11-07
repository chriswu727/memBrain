import datetime

import pytest
from test_affect import forget, say, write
from test_persona_decisions import brain as brain
from test_persona_growth import _restored

from membrain import relationship as module
from membrain.host_context import snapshot
from membrain.relationship import acknowledge, relationship

pytestmark = pytest.mark.integration
TODAY = datetime.date(2027, 3, 30)


@pytest.mark.parametrize("kind", ["shared", "commitment"])
@pytest.mark.parametrize("restored", [False, True])
@pytest.mark.parametrize("mark_after", [False, True])
def test_source_privacy_keeps_records_but_not_automatic_context(brain, kind, restored, mark_after):
    source = say(brain, "The STARLIGHT visit is private.")

    def mark():
        return write(brain, "STARLIGHT is private.", sensitive=True, source_event_ids=[source])

    private = None if mark_after else mark()
    fields = {"kind": "milestone", "shared": True} if kind == "shared" else {
        "kind": "agent_commitment", "status": "intended", "due": "2027-03-29"}
    saved = write(brain, "Our STARLIGHT visit.", source_event_ids=[source], **fields)
    if mark_after:
        assert "STARLIGHT" in relationship(*brain, today=TODAY)["block"]
        private = mark()
    if restored:
        brain = (*brain[:2], _restored(brain, "Restored relationship privacy"))
    state = relationship(*brain, today=TODAY)
    items = state["shared_moments"] if kind == "shared" else state["commitments"]["missed"]
    assert len(items) == 1 and "STARLIGHT" in items[0]["text"]
    assert items[0]["sensitive"]
    assert state["shared_moments_total"] == (1 if kind == "shared" else 0)
    context = snapshot({"items": []}, brain_id=brain[2], tools=None, relationship=state)
    assert "STARLIGHT" not in context["text"] and context["acknowledge"] == []
    if kind == "commitment":
        ignored = acknowledge(*brain, [saved["note_id"]], today=TODAY)
        assert not ignored["commitments"]["missed"][0]["acknowledged"]
    forget(brain, [private["note_id"]], conversation="membrain-notes")
    visible = relationship(*brain, today=TODAY)
    assert visible["familiarity"] == state["familiarity"]
    assert visible["shared_moments_total"] == state["shared_moments_total"]
    assert "STARLIGHT" in visible["block"]
    if kind == "commitment":
        assert visible["once"] == [saved["note_id"]]
        acknowledged = acknowledge(*brain, visible["once"], today=TODAY)
        assert acknowledged["once"] == []


def test_explicit_graph_protection_marks_the_individual_shared_moment(brain):
    source = say(brain, "Our STARLIGHT visit.")
    saved = write(brain, "Our STARLIGHT visit.", kind="milestone", shared=True, source_event_ids=[source])
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        state = module._moment_state(service, conn, principal, ident, 0, protected={source})
    assert state["total"] == 1 and state["sensitive"]
    assert state["items"][0]["id"] == saved["note_id"] and state["items"][0]["sensitive"]


def test_source_checks_are_batched_and_include_moments_beyond_the_visible_sample(brain, monkeypatch):
    source = say(brain, "Our STARLIGHT visit.")
    write(brain, "STARLIGHT is private.", sensitive=True, source_event_ids=[source])
    for index in range(260):
        write(brain, f"Shared visit {index}.", kind="milestone", shared=True,
              **({"source_event_ids": [source]} if index == 0 else {}))
    monkeypatch.setattr(module, "MAX_MOMENTS", 2)
    from membrain import memory_map

    checked = []
    original = memory_map.sensitive_note_ids

    def tracked(conn, params, ids):
        checked.append(len(ids))
        return original(conn, params, ids)

    monkeypatch.setattr(memory_map, "sensitive_note_ids", tracked)
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        state = module._moment_state(service, conn, principal, ident, 0)
    assert state["total"] == 260 and len(state["items"]) == 2 and state["truncated"]
    assert state["sensitive"] and all(not item["sensitive"] for item in state["items"])
    assert checked == [256, 4]
