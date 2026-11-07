import pytest
from test_affect import NERVOUS, say, write
from test_affect_provenance import INFERRED, new_reference
from test_persona_decisions import brain as brain

from membrain.affect import MAX_RECORDS, _records, affect_records
from membrain.mood import mood_state

pytestmark = pytest.mark.integration


def test_pending_inferences_do_not_hide_current_supported_feeling(brain):
    source = say(brain, "I am nervous about Friday's interview.")
    saved = write(brain, "Interview on Friday.", source_event_ids=[source], affect=NERVOUS)
    assert [record["id"] for record in affect_records(*brain)["records"]] == [saved["affect_id"]]
    assert not mood_state(*brain)["at_baseline"]

    for index in range(MAX_RECORDS + 1):
        pending = write(brain, f"Pending interview reading {index}.",
                        source_messages=[new_reference()], affect=INFERRED)
        assert pending["affect_id"]

    listed = affect_records(*brain)
    mood = mood_state(*brain)
    actual = {"record_ids": [record["id"] for record in listed["records"]],
              "complete": listed["complete"], "at_baseline": mood["at_baseline"]}
    assert actual == {"record_ids": [saved["affect_id"]], "complete": True, "at_baseline": False}


def test_pending_inference_does_not_mask_supported_feeling_overflow(brain):
    source = say(brain, "I am nervous about Friday's interview.")
    for index in range(MAX_RECORDS + 1):
        write(brain, f"Supported interview reading {index}.", source_event_ids=[source], affect=NERVOUS)
    write(brain, "Pending interview reading.", source_messages=[new_reference()], affect=INFERRED)

    listed = affect_records(*brain)
    assert len(listed["records"]) == MAX_RECORDS
    assert not listed["complete"]


def test_supported_window_lookahead_does_not_query_pending_tail_one_record_at_a_time(brain):
    source = say(brain, "I am nervous about Friday's interview.")
    oldest = write(brain, "First supported interview reading.", source_event_ids=[source], affect=NERVOUS)
    for index in range(256):
        write(brain, f"Pending interview reading {index}.", source_messages=[new_reference()], affect=INFERRED)
    newest = [write(brain, f"Supported interview reading {index}.", source_event_ids=[source], affect=NERVOUS)
              for index in range(MAX_RECORDS)]

    class QueryBudget:
        calls = 0

        def __init__(self, connection):
            self.connection = connection

        def execute(self, *args, **kwargs):
            self.calls += 1
            assert self.calls <= 20, "A small valid lookahead must not turn invalid history into per-record queries"
            return self.connection.execute(*args, **kwargs)

    service, principal, ident = brain
    with service.database.transaction(principal) as connection:
        service._brain(connection, principal, ident)
        records = _records(service, QueryBudget(connection), principal, ident)
    expected = [item["affect_id"] for item in reversed(newest)]
    assert [record["id"] for record in records] == [*expected, oldest["affect_id"]]
    listed = affect_records(*brain)
    assert [record["id"] for record in listed["records"]] == expected
    assert not listed["complete"]
