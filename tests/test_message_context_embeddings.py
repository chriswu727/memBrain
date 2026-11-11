"""A statement captured from a message is embedded as that message, and the meaning route lists a message once."""
import pytest
from test_turns import turns as turns
from test_vector_jobs import drain

from membrain import vector_jobs
from membrain.candidates import _one_per_message
from membrain.embeddings import EmbeddingPassage, EmbeddingResult, EmbeddingSpace
from membrain.helpers import digest

MESSAGE = "We moved the reunion to Lisbon. Tomas will bring the photo albums. It starts on the ninth."


class Local:
    """An unmetered provider that records its inputs; ``split`` names inputs it reports as several passages."""

    metered = False
    space = EmbeddingSpace("context-test", "v1", 3)
    document_index_version = "local-test-passages-v1"

    def __init__(self, split=()):
        self.calls, self.split = [], tuple(split)

    def __call__(self, request):
        self.calls.append(request.texts)
        passages = None
        if request.purpose != "query":
            passages = tuple(
                (EmbeddingPassage(0, len(text) // 2, (0.0, 1.0, 0.0)),
                 EmbeddingPassage(len(text) // 2, len(text), (0.0, 0.0, 1.0))) if text in self.split else ()
                for text in request.texts)
        return EmbeddingResult(self.space, tuple((1.0, float(len(text) % 7), 0.0) for text in request.texts), {},
                               digest(request.texts), sum(len(text.encode()) for text in request.texts), passages,
                               self.document_index_version if request.purpose != "query" else "single-vector-v1")


def _stored(turns):
    with turns.database.transaction(turns.principal) as conn:
        return conn.execute(
            "SELECT a.document->>'statement' AS statement,v.embedding::text AS vector,v.document_index_version,"
            "(SELECT count(*) FROM memory_embedding_passages p WHERE p.brain_id=v.brain_id AND p.memory_id=v.memory_id) "
            "AS passages FROM memory_embeddings v JOIN memory_assertions a ON a.tenant_id=v.tenant_id "
            "AND a.brain_id=v.brain_id AND a.id=v.memory_id AND a.revision=v.memory_revision "
            "WHERE v.brain_id=%s ORDER BY a.document->>'statement'", (turns.brain,)).fetchall()


@pytest.mark.integration
def test_the_statements_of_one_message_are_embedded_once_as_that_message(turns):
    vectors = Local()
    turns.service.embedding_provider = vectors
    turns.observe(MESSAGE)
    drain(turns)
    rows = _stored(turns)
    assert len(rows) == 3 and len({row["vector"] for row in rows}) == 1  # Three sentences, one vector.
    inputs = [text for call in vectors.calls for text in call]
    assert inputs == [MESSAGE]  # Sent once, as the whole message, without the statement's role prefix.
    assert {row["document_index_version"] for row in rows} == {"local-test-passages-v1+message-context-v1"}
    assert all(row["passages"] == 0 for row in rows)


@pytest.mark.integration
def test_a_long_message_keeps_statement_vectors(turns):
    vectors = Local()
    turns.service.embedding_provider = vectors
    long_message = MESSAGE + " " + "The garden path floods every spring and needs gravel again. " * 30
    assert len(long_message) > vector_jobs.MESSAGE_CONTEXT_CHARACTERS
    turns.observe(long_message)
    drain(turns)
    inputs = {text for call in vectors.calls for text in call}
    assert long_message not in inputs and all("(direct_statement): " in text for text in inputs)


@pytest.mark.integration
def test_a_message_the_model_must_split_falls_back_to_the_statement(turns):
    vectors = Local(split=[MESSAGE])
    turns.service.embedding_provider = vectors
    turns.observe(MESSAGE)
    drain(turns)
    rows = _stored(turns)
    inputs = [text for call in vectors.calls for text in call]
    assert inputs[0] == MESSAGE and len(inputs) == 4  # The message once, then each statement as itself.
    assert all("(direct_statement): " in text for text in inputs[1:])
    assert len(rows) == 3 and all(row["passages"] == 0 for row in rows)


@pytest.mark.integration
def test_vectors_from_the_earlier_rule_are_queued_again(turns):
    vectors = Local()
    turns.service.embedding_provider = vectors
    turns.observe(MESSAGE)
    drain(turns)
    with turns.database.transaction(turns.principal) as conn:
        conn.execute("UPDATE memory_embeddings SET document_index_version='local-test-passages-v1' WHERE brain_id=%s",
                     (turns.brain,))
        conn.execute("DELETE FROM memory_jobs WHERE brain_id=%s AND kind='embed'", (turns.brain,))
    queued, _ = vector_jobs.queue_missing_embeddings(turns.service, turns.principal, turns.brain)
    assert queued == 3
    drain(turns)
    assert {row["document_index_version"] for row in _stored(turns)} == {"local-test-passages-v1+message-context-v1"}


def _row(memory_id, event, distance, *, method="direct_capture", start=None, extra=()):
    refs = [{"relationship": "supports", "event_id": event, "event_revision": 1}, *extra]
    return {"document": {"memory_id": memory_id, "revision": 1, "evidence_refs": refs,
                         "derivation": {"method": method}}, "distance": distance, "start_offset": start}


def test_the_meaning_route_lists_a_message_once_and_prefers_the_keyword_match():
    rows = [_row("a1", "A", 0.2), _row("a2", "A", 0.2), _row("a3", "A", 0.2), _row("b1", "B", 0.3),
            _row("a-old", "A", 0.25),  # A vector from the earlier rule: another distance, so another candidate.
            _row("b-passage", "B", 0.3, start=0),  # A passage match keeps its own place.
            _row("derived", "B", 0.3, method="consolidation"),
            _row("two-sources", "B", 0.3, extra=[{"relationship": "supports", "event_id": "C", "event_revision": 1}])]
    kept = [row["document"]["memory_id"] for row in _one_per_message(rows, {("a2", 1): 0.6, ("a3", 1): 0.1})]
    assert kept == ["a2", "b1", "a-old", "b-passage", "derived", "two-sources"]
    assert [row["document"]["memory_id"] for row in _one_per_message(rows[:4], {})] == ["a1", "b1"]
