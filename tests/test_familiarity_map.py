import json

import pytest
from test_companion_map import brain as brain
from test_companion_map import erase, note, say
from test_companion_map import installation as installation

from membrain import service as service_module
from membrain.companion_map import companion_map
from membrain.relationship import relationship, reset_relationship, set_cap


def test_familiarity_summary_uses_actual_counts_without_inventing_a_neuron(brain, monkeypatch):
    for day in (1, 2, 3):
        monkeypatch.setattr(service_module, "now", lambda day=day: f"2026-11-{day:02d}T12:00:00Z")
        say(brain, f"We talked on day {day}.")
    saved = note(brain, "Our first puzzle.", kind="milestone", shared=True)
    set_cap(*brain, "new")
    graph = companion_map(*brain)
    summary = graph["familiarity"]
    assert (summary["level"], summary["derived_level"], summary["days"], summary["shared_moments"]) == (
        "new", "getting_to_know", 3, 1)
    assert summary["derived"] and not summary["masked"]
    assert summary["evidence"]["shared_moment_nodes"] == ["note:" + saved["note_id"]]
    assert summary["evidence"]["cap_node"] in {node["id"] for node in graph["nodes"]}
    assert not any(node["kind"] == "familiarity" for node in graph["nodes"])
    assert relationship(*brain)["familiarity"]["shared_moments"] == summary["shared_moments"]


@pytest.mark.parametrize("max_nodes", [1, 2, 200])
@pytest.mark.parametrize("private", ["shared", "day", "shared_source"])
def test_sensitive_familiarity_is_hidden_before_graph_sampling(brain, max_nodes, private):
    source = say(brain, "The secret planetarium meeting.")
    if private == "shared":
        note(brain, "Our secret meeting.", kind="milestone", shared=True, sensitive=True)
    else:
        note(brain, "The meeting is private.", kind="constraint", sensitive=True, source_event_ids=[source])
        if private == "shared_source":
            note(brain, "We made a memory.", kind="milestone", shared=True, source_event_ids=[source])
    result = companion_map(*brain, max_nodes=max_nodes)
    assert result["familiarity"] == {"derived": True, "masked": True}
    assert "planetarium" not in json.dumps(result)
    revealed = companion_map(*brain, max_nodes=max_nodes, include_sensitive=True)["familiarity"]
    assert not revealed["masked"] and revealed["days"] == 1
    reset_relationship(*brain)
    after = companion_map(*brain)["familiarity"]
    assert not after["masked"] and after["days"] == 0 and after["shared_moments"] == 0


def test_familiarity_summary_changes_with_erasure_and_keeps_real_reset_marker(brain):
    source = say(brain, "Our first shared puzzle.")
    note(brain, "We solved the puzzle.", kind="milestone", shared=True, source_event_ids=[source])
    before = companion_map(*brain)["familiarity"]
    assert (before["days"], before["shared_moments"]) == (1, 1)
    erase(brain, source)
    after = companion_map(*brain)["familiarity"]
    assert (after["days"], after["shared_moments"]) == (0, 0)
    reset_relationship(*brain)
    graph = companion_map(*brain)
    reset_id = graph["familiarity"]["evidence"]["reset_node"]
    node = next(node for node in graph["nodes"] if node["id"] == reset_id)
    assert node["kind"] == "relationship_reset" and node["details"]["event_id"]
    assert node["details"]["after_sequence"] == graph["familiarity"]["after_sequence"]


def test_graph_sampling_never_changes_familiarity_counts_or_references_absent_nodes(brain):
    say(brain, "Our conversation.")
    for i in range(4):
        note(brain, f"A shared puzzle {i}.", kind="milestone", shared=True)
    result = companion_map(*brain, max_nodes=1, max_edges=0)
    assert result["familiarity"]["shared_moments"] == 4
    assert result["familiarity"]["evidence"]["shared_moments_truncated"]
    assert set(result["familiarity"]["evidence"]["shared_moment_nodes"]) <= {n["id"] for n in result["nodes"]}
