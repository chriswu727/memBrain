"""Cues attached to a message let recall find it by words it never used; what is recalled is the message."""
import pytest
from test_turns import turns as turns
from test_vector_jobs import drain, recall_request

from membrain import host, message_cues
from membrain.embeddings import EmbeddingResult, EmbeddingSpace
from membrain.helpers import DomainError, Principal, digest, uid

pytestmark = pytest.mark.integration

POTTERY = "I signed up for a pottery class on Thursdays."
OTHER = "The train to the coast leaves at seven."


def _recalled(turns, question, **options):
    response = turns.service.handle(turns.principal, recall_request(turns, question, **options))
    assert response["outcome"] == "completed", response
    return response


def _statements(response):
    return [item["memory"]["statement"] for item in response["result"]["items"]]


def _cue_rows(turns):
    with turns.database.transaction(turns.principal) as conn:
        return conn.execute("SELECT event_id,cue_text,rule_version,model_version,embedding IS NOT NULL AS embedded "
                            "FROM memory_message_cues WHERE brain_id=%s ORDER BY event_id", (turns.brain,)).fetchall()


def _generation(turns):
    return turns.store.status(turns.principal, turns.brain)["scope_generation"]


def _elsewhere(turns):
    """Finish indexing, then ask from another conversation, as a later session does."""
    drain(turns)
    turns.conversation = "later"


def test_a_message_is_recalled_through_its_cues_and_the_cue_is_never_shown(turns):
    pottery = turns.observe(POTTERY, conversation="earlier")
    turns.observe(OTHER, conversation="earlier")
    _elsewhere(turns)
    question = "What are Melanie's hobbies?"
    assert not any("pottery" in statement for statement in _statements(_recalled(turns, question)))

    result = message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": pottery["event_id"], "cues": ["Melanie hobbies and activities"]}], model_version="test-model")
    assert result == {"written": 1, "skipped": 0, "embedded": 0}
    assert _cue_rows(turns) == [{"event_id": pottery["event_id"], "cue_text": "Melanie hobbies and activities",
                                 "rule_version": "message-cue-v1", "model_version": "test-model", "embedded": False}]

    response = _recalled(turns, question)
    items = [item for item in response["result"]["items"] if "pottery" in item["memory"]["statement"]]
    assert len(items) == 1
    assert [signal["method"] for signal in items[0]["rank_signals"]] == ["entity"]
    assert items[0]["rank_signals"][0]["model_or_index_version"] == "message-cue-v1"
    assert "hobbies and activities" not in str(response)  # The cue finds the message and is not part of the answer.
    assert host._sources(response, "later") == [(pottery["event_id"], 0)]  # A host is shown the original message.


def test_a_message_is_named_by_its_source_key_and_new_cues_replace_the_old(turns):
    turns.observe(POTTERY, source_key="turn-7", conversation="earlier")
    _elsewhere(turns)
    item = {"producer_ref": "turn-test", "source_event_key": "turn-7"}
    assert message_cues.write(turns.service, turns.principal, turns.brain,
                              [{**item, "cues": ["Melanie hobbies and activities"]}])["written"] == 1
    assert message_cues.write(turns.service, turns.principal, turns.brain,
                              [{**item, "cues": ["Melanie weekly schedule", "Melanie weekly schedule", "  "]}])["written"] == 1
    assert [row["cue_text"] for row in _cue_rows(turns)] == ["Melanie weekly schedule"]
    assert not any("pottery" in statement for statement in _statements(_recalled(turns, "Any hobbies?")))
    assert any("pottery" in statement for statement in _statements(_recalled(turns, "What is the weekly schedule?")))
    # Cues that come back empty remove the ones the message had.
    assert message_cues.write(turns.service, turns.principal, turns.brain, [{**item, "cues": []}]) == {
        "written": 0, "skipped": 1, "embedded": 0}
    assert _cue_rows(turns) == []


def test_cues_are_bounded_scrubbed_and_only_for_current_messages(turns):
    kept = turns.observe(POTTERY, conversation="earlier")
    gone = turns.observe(OTHER, conversation="earlier")
    turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [gone["event_id"]]},
                            "mode": "erase_content", "expected_scope_generation": _generation(turns)})
    result = message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": kept["event_id"], "cues": ["x" * 300, "password: hunter2hunter2", *["cue %d" % n for n in range(9)]]},
        {"event_id": gone["event_id"], "cues": ["Train times"]},
        {"event_id": "no-such-event", "cues": ["Nothing"]},
        {"producer_ref": "turn-test", "source_event_key": "no-such-key", "cues": ["Nothing"]},
    ])
    assert result == {"written": 1, "skipped": 3, "embedded": 0}
    rows = _cue_rows(turns)
    assert [row["event_id"] for row in rows] == [kept["event_id"]]
    phrases = rows[0]["cue_text"].split("; ")
    assert len(phrases) <= message_cues.MAX_CUES and all(len(phrase) <= message_cues.CUE_CHARACTERS for phrase in phrases)
    assert "hunter2" not in rows[0]["cue_text"]
    for bad in ([], [{"cues": ["no message named"]}], [{"event_id": kept["event_id"], "cues": "not a list"}],
                [{"event_id": kept["event_id"], "cues": [3]}], [{"event_id": kept["event_id"], "cues": ["a"]}] * 201):
        with pytest.raises(DomainError) as raised:
            message_cues.write(turns.service, turns.principal, turns.brain, bad)
        assert raised.value.code == "validation_failed"


@pytest.mark.parametrize("mode", ["erase_content", "suppress_recall"])
def test_hiding_or_erasing_a_message_removes_its_cues(turns, mode):
    pottery = turns.observe(POTTERY, conversation="earlier")
    other = turns.observe(OTHER, conversation="earlier")
    _elsewhere(turns)
    message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": pottery["event_id"], "cues": ["Melanie hobbies and activities"]},
        {"event_id": other["event_id"], "cues": ["Melanie travel plans"]}])
    turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [pottery["event_id"]]},
                            "mode": mode, "expected_scope_generation": _generation(turns)})
    assert [row["event_id"] for row in _cue_rows(turns)] == [other["event_id"]]
    assert not any("pottery" in statement for statement in _statements(_recalled(turns, "What are Melanie's hobbies?")))


def test_a_corrected_message_is_not_reached_through_the_cues_of_its_earlier_revision(turns):
    first = turns.observe("I play the cello in a quartet.", source_key="turn-3", conversation="earlier")
    _elsewhere(turns)
    message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": first["event_id"], "cues": ["Melanie hobbies and activities"]}])
    turns.conversation = "earlier"
    turns.observe("The dentist moved my appointment to Friday.", source_key="turn-3", revision=2)
    _elsewhere(turns)
    assert _cue_rows(turns) == []  # The cues described what the message said before.
    assert _statements(_recalled(turns, "What are Melanie's hobbies?")) == []


def test_cues_cannot_be_written_while_recording_is_paused_or_into_another_owner_s_brain(turns):
    from membrain.recording_control import recording_status, set_recording

    pottery = turns.observe(POTTERY, conversation="earlier")
    items = [{"event_id": pottery["event_id"], "cues": ["Melanie hobbies and activities"]}]
    with pytest.raises(DomainError):
        message_cues.write(turns.service, Principal(turns.principal.tenant_id, uid()), turns.brain, items)
    revision = recording_status(turns.service, turns.principal, turns.brain)["revision"]
    set_recording(turns.service, turns.principal, turns.brain, paused=True, expected_revision=revision)
    with pytest.raises(DomainError) as raised:
        message_cues.write(turns.service, turns.principal, turns.brain, items)
    assert raised.value.code == "recording_paused" and _cue_rows(turns) == []


class Meaning:
    """An in-process model: texts about hobbies or pastimes point one way, everything else another."""

    space = EmbeddingSpace("cue-test", "v1", 3)
    document_index_version = "single-vector-v1"

    def __call__(self, request):
        vectors = tuple((1.0, 0.0, 0.0) if any(word in text.lower() for word in ("hobbies", "pastime"))
                        else (0.0, 1.0, 0.0) for text in request.texts)
        return EmbeddingResult(self.space, vectors, {}, digest(request.texts),
                               sum(len(text.encode()) for text in request.texts), None, "single-vector-v1")


def test_cues_are_embedded_by_a_local_model_and_matched_by_meaning(turns):
    turns.service.embedding_provider = Meaning()
    pottery = turns.observe(POTTERY, conversation="earlier")
    turns.observe(OTHER, conversation="earlier")
    drain(turns)
    _elsewhere(turns)
    result = message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": pottery["event_id"], "cues": ["Melanie hobbies and activities"]}])
    assert result == {"written": 1, "skipped": 0, "embedded": 1} and _cue_rows(turns)[0]["embedded"]
    response = _recalled(turns, "Which pastime did she pick up?")  # No word in common with the message or the cue.
    items = [item for item in response["result"]["items"] if "pottery" in item["memory"]["statement"]]
    assert items and "entity" in [signal["method"] for signal in items[0]["rank_signals"]]


def test_the_cue_table_is_isolated_by_owner(turns):
    with turns.database.transaction(turns.principal) as conn:
        row = conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                           "WHERE oid='memory_message_cues'::regclass").fetchone()
    assert row == {"relrowsecurity": True, "relforcerowsecurity": True}
    pottery = turns.observe(POTTERY, conversation="earlier")
    message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": pottery["event_id"], "cues": ["Melanie hobbies and activities"]}])
    with turns.database.transaction(Principal(turns.principal.tenant_id, uid())) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_message_cues").fetchone()["n"] == 0


def _pending(turns, **options):
    return message_cues.pending(turns.service, turns.principal, turns.brain, **options)


def test_unreviewed_user_messages_are_offered_oldest_first_until_reviewed(turns):
    first = turns.observe(POTTERY, conversation="earlier")
    turns.observe("Sounds lovely, enjoy the class.", role="assistant", delivery="delivered", conversation="earlier")
    second = turns.observe("Thanks!", conversation="earlier")
    third = turns.observe(OTHER, conversation="earlier")
    offered = _pending(turns)
    assert [item["event_id"] for item in offered["items"]] == [first["event_id"], second["event_id"], third["event_id"]]
    assert offered["items"][0]["text"] == POTTERY and offered["remaining"] == 3 and not offered["recording_paused"]
    assert offered["through_sequence"] == offered["items"][-1]["sequence"]
    part = _pending(turns, limit=2)
    assert [item["event_id"] for item in part["items"]] == [first["event_id"], second["event_id"]]
    assert part["remaining"] == 3

    # The first two are read: one gets cues, the greeting gets none, and neither is offered again.
    result = message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": first["event_id"], "cues": ["Melanie hobbies and activities"]}],
        reviewed_through_sequence=part["through_sequence"])
    assert result["written"] == 1 and result["reviewed_through_sequence"] == part["through_sequence"]
    left = _pending(turns)
    assert [item["event_id"] for item in left["items"]] == [third["event_id"]] and left["remaining"] == 1

    # A batch in which nothing deserved a cue still moves on; progress never moves back.
    message_cues.write(turns.service, turns.principal, turns.brain, [], reviewed_through_sequence=left["through_sequence"])
    message_cues.write(turns.service, turns.principal, turns.brain, [], reviewed_through_sequence=1)
    assert _pending(turns) == {"items": [], "through_sequence": None, "remaining": 0, "recording_paused": False}
    later = turns.observe("My sister Ana moved to Porto.", conversation="later")
    assert [item["event_id"] for item in _pending(turns)["items"]] == [later["event_id"]]


def test_pending_messages_are_bounded_and_leave_out_what_cannot_be_cued(turns):
    from membrain.recording_control import recording_status, set_recording

    kept = turns.observe("A long story. " + "It went on and on. " * 80, conversation="earlier")
    gone = turns.observe(OTHER, conversation="earlier")
    cued = turns.observe(POTTERY, conversation="earlier")
    turns.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [gone["event_id"]]},
                            "mode": "erase_content", "expected_scope_generation": _generation(turns)})
    message_cues.write(turns.service, turns.principal, turns.brain, [
        {"event_id": cued["event_id"], "cues": ["Melanie hobbies and activities"]}])
    offered = _pending(turns, item_characters=100)
    assert [item["event_id"] for item in offered["items"]] == [kept["event_id"]]
    assert len(offered["items"][0]["text"]) == 100 and offered["items"][0]["text"].endswith("…")
    for bad in ({"limit": 0}, {"limit": 101}, {"max_characters": 10}, {"item_characters": 10}):
        with pytest.raises(DomainError):
            _pending(turns, **bad)
    with pytest.raises(DomainError):  # Beyond anything recorded.
        message_cues.write(turns.service, turns.principal, turns.brain, [], reviewed_through_sequence=10_000)
    with pytest.raises(DomainError):
        message_cues.write(turns.service, turns.principal, turns.brain, [])
    revision = recording_status(turns.service, turns.principal, turns.brain)["revision"]
    set_recording(turns.service, turns.principal, turns.brain, paused=True, expected_revision=revision)
    assert _pending(turns) == {"items": [], "through_sequence": None, "remaining": 0, "recording_paused": True}


def test_review_progress_is_isolated_by_owner(turns):
    with turns.database.transaction(turns.principal) as conn:
        row = conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                           "WHERE oid='memory_cue_progress'::regclass").fetchone()
    assert row == {"relrowsecurity": True, "relforcerowsecurity": True}
    turns.observe(POTTERY, conversation="earlier")
    message_cues.write(turns.service, turns.principal, turns.brain, [], reviewed_through_sequence=1)
    with turns.database.transaction(Principal(turns.principal.tenant_id, uid())) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_cue_progress").fetchone()["n"] == 0


def test_a_batch_ends_where_a_conversation_ends_when_enough_remains(turns):
    for number in range(12):
        turns.observe(f"First talk, message {number}.", conversation="first")
    for number in range(5):
        turns.observe(f"Second talk, message {number}.", conversation="second")
    plain = _pending(turns, limit=15)
    assert len(plain["items"]) == 15  # Without the option a batch is simply the oldest messages.
    whole = _pending(turns, limit=15, whole_conversations=True)
    assert len(whole["items"]) == 12 and {item["conversation_id"] for item in whole["items"]} == {"first"}
    assert whole["through_sequence"] == whole["items"][-1]["sequence"] and whole["remaining"] == 17
    # Too little before the boundary: the batch is not cut down to a few messages.
    assert len(_pending(turns, limit=15, whole_conversations=True)["items"]) == 12
    message_cues.write(turns.service, turns.principal, turns.brain, [],
                       reviewed_through_sequence=whole["items"][5]["sequence"])
    short = _pending(turns, limit=8, whole_conversations=True)
    assert len(short["items"]) == 8  # Six of the first talk are left: fewer than the minimum, so no cut.
    # Everything that is left fits: nothing follows, so nothing is cut.
    assert len(_pending(turns, limit=40, whole_conversations=True)["items"]) == 11
