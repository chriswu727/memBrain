import copy
import random

import pytest

from membrain.mood import _successors


def record(sequence, *, note="first", topic=None, basis="reported"):
    return {"sequence": sequence, "note_id": note, "topic": topic, "basis": basis}


def test_nearest_inference_cannot_hide_later_reported_correction():
    records = [record(1), record(2, basis="inferred"), record(3)]
    assert _successors(records) == [records[2], records[2], None]


def test_first_correction_across_note_and_topic_wins_without_transitive_merging():
    records = [record(1, topic=" Interview "), record(2, note="second", topic="interview"),
               record(3, note="second", topic="new job"), record(4, note="fourth", topic="new job")]
    assert _successors(records) == [records[1], records[2], records[3], None]
    assert _successors([records[0], records[2], records[3]]) == [None, records[3], None]


@pytest.mark.parametrize("seed", range(16))
def test_indexed_successions_match_ordered_pair_rule(seed):
    rng = random.Random(seed)
    topics = [None, "", "  ", "Interview", " INTERVIEW ", "new job", "new  job", "First", "first", "面试"]
    records = [record(sequence, note=str(rng.randrange(25)), topic=rng.choice(topics),
                      basis=rng.choice(("reported", "inferred"))) for sequence in range(1, 151)]
    original = copy.deepcopy(records)
    expected = []
    for index, earlier in enumerate(records):
        topic = " ".join((earlier["topic"] or "").split()).casefold()
        expected.append(next((later for later in records[index + 1:]
                              if (earlier["basis"] != "reported" or later["basis"] == "reported")
                              and (later["note_id"] == earlier["note_id"]
                                   or topic and " ".join((later["topic"] or "").split()).casefold() == topic)), None))
    assert _successors(records) == expected
    assert records == original
