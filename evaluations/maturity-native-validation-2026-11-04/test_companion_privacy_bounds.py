import pytest
from test_companion_map import WHEN, brain, installation, note, say
from membrain.companion_map import companion_map
from membrain.persona import set_persona
from membrain.persona_growth import accept_proposal, persona_proposals

@pytest.mark.parametrize("bound", [2, 3, 4])
def test_hidden_feedback_outside_source_sample_stays_private(brain, bound):
    set_persona(*brain, {"name": "Aster", "voice": {"register": "formal"}}, made_by="host")
    first = say(brain, "You're too formal. Please be more casual. My private code is STARLIGHT.")
    for _ in range(2):
        say(brain, "You're too formal. Please be more casual.")
    note(brain, "STARLIGHT is private.", kind="constraint", sensitive=True, source_event_ids=[first])
    proposal = persona_proposals(*brain, now=WHEN)["proposals"][0]
    accept_proposal(*brain, proposal["id"], now=WHEN)
    full = companion_map(*brain)
    protected_ids = {node["id"] for node in full["nodes"] if node["kind"] in {"persona", "persona_proposal"} and node["sensitive"]}
    assert len(protected_ids) == 2
    small = companion_map(*brain, max_nodes=bound)
    derived = [node for node in small["nodes"] if node["id"] in protected_ids]
    assert derived
    assert all(node["sensitive"] and node["masked"] and node["details"] == {} and node["recorded_at"] is None for node in derived), derived
