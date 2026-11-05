from test_relationship import brain as brain
from test_relationship import installation as installation
from test_relationship import say

from membrain.helpers import uid
from membrain.relationship import (
    _append,
    add_boundary,
    relationship,
    relationship_boundaries,
    reset_relationship,
    set_cap,
)


def test_relationship_controls_and_reset_survive_more_than_5000_records(brain):
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        stored_brain = service._brain(conn, principal, ident)
        for _ in range(5000):
            _append(service, conn, principal, stored_brain,
                    {"relationship_marker": "reset", "removed": {}}, uid())
    say(brain, "Please keep our earlier conversations private.")
    saved = add_boundary(*brain, "earlier conversations")
    assert [item["topic"] for item in saved["boundaries"]] == ["earlier conversations"]
    assert relationship_boundaries(*brain)["boundaries"] == saved["boundaries"]
    assert set_cap(*brain, "new")["familiarity"]["cap"] == "new"
    result = reset_relationship(*brain)
    assert result["removed"]["boundaries"] == 1
    assert result["removed"]["cap"] == 1
    assert len(result["markers"]) == 5001
    assert result["marker"] == result["markers"][0]
    assert result["familiarity"]["days"] == 0
    assert result["familiarity"]["cap"] is None
    assert relationship_boundaries(*brain)["boundaries"] == []
    say(brain, "We can start again today.")
    assert relationship(*brain)["familiarity"]["days"] == 1
