import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from test_turns import turns as turns
from test_vector_jobs import drain, recall_request

from membrain.client import integration_capabilities
from membrain.embeddings import EmbeddingResult, EmbeddingSpace
from membrain.helpers import uid
from membrain.vector_jobs import query_embedding

pytestmark = pytest.mark.integration


class Local:
    metered = False
    space = EmbeddingSpace('local-query-test', 'v1', 3)

    def __init__(self, callback=None):
        self.calls = 0
        self.callback = callback

    def __call__(self, request):
        self.calls += 1
        if self.callback:
            self.callback()
        return EmbeddingResult(self.space, ((1.0, 0.0, 0.0),), None, 'local', 0)


def test_local_query_can_finish_while_an_unrelated_reader_holds_the_brain(turns):
    turns.service.embedding_provider = Local()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with turns.database.transaction(turns.principal) as conn:
            conn.execute('SELECT id FROM memory_brains WHERE id=%s FOR SHARE', (turns.brain,))
            result = pool.submit(query_embedding, turns.service, turns.principal, recall_request(turns))
            vector, snapshot, calls = result.result(timeout=2)
            assert vector.vectors == ((1.0, 0.0, 0.0),) and calls == 1
            assert snapshot['scope']['brain_id'] == turns.brain


def test_local_query_replay_is_idempotent_without_accumulating_background_jobs(turns):
    turns.observe('My favorite tree is a willow.')
    drain(turns)
    provider = turns.service.embedding_provider = Local()
    request = recall_request(turns, 'willow')
    first = turns.service.handle(turns.principal, request)
    assert first['outcome'] == 'completed', first
    assert turns.service.handle(turns.principal, request) == first
    changed = copy.deepcopy(request)
    changed['payload']['query'] = 'another question'
    assert turns.service.handle(turns.principal, changed)['error']['code'] == 'idempotency_conflict'
    assert provider.calls == 1
    with turns.database.transaction(turns.principal) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_jobs WHERE brain_id=%s AND kind='query_embedding'",
                            (turns.brain,)).fetchone()['n'] == 0
        conn.execute('DELETE FROM memory_read_cache WHERE brain_id=%s', (turns.brain,))
    assert turns.service.handle(turns.principal, request)['error']['code'] == 'version_conflict'
    assert provider.calls == 1


def test_erasure_during_local_query_prevents_stale_recall(turns):
    ref = turns.observe('Private appointment details at the willow cafe.')
    drain(turns)

    def erase():
        turns.action('forget', {'idempotency_key': uid(), 'selector': {'kind': 'events', 'ids': [ref['event_id']]},
                                'mode': 'erase_content', 'expected_scope_generation': 1})

    turns.service.embedding_provider = Local(erase)
    result = turns.service.handle(turns.principal, recall_request(turns, 'willow cafe'))
    assert result['outcome'] != 'completed'
    assert result['error']['code'] == 'context_stale'
    assert 'Private appointment' not in str(result)


def test_local_inference_holds_no_database_brain_lock(turns):
    def check():
        with turns.database.transaction(turns.principal) as conn:
            conn.execute("SET LOCAL lock_timeout='200ms'")
            conn.execute('SELECT id FROM memory_brains WHERE id=%s FOR UPDATE', (turns.brain,))

    turns.service.embedding_provider = Local(check)
    result = turns.service.handle(turns.principal, recall_request(turns))
    assert result['outcome'] == 'completed', result


@pytest.mark.parametrize('different_query', [False, True])
def test_concurrent_local_queries_keep_the_same_request_binding(turns, different_query):
    barrier = Barrier(2, timeout=2)
    turns.service.embedding_provider = Local(barrier.wait)
    request = recall_request(turns)
    other = copy.deepcopy(request)
    if different_query:
        other['payload']['query'] = 'another question'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(turns.service.handle, turns.principal, item) for item in (request, other)]
        results = [future.result(timeout=5) for future in futures]
    if different_query:
        assert sorted(item['outcome'] for item in results) == ['completed', 'conflict']
        assert next(item for item in results if item['outcome'] == 'conflict')['error']['code'] == 'idempotency_conflict'
    else:
        assert results[0]['outcome'] == 'completed'
        assert results[0] == results[1]


@pytest.mark.parametrize('revise', [False, True])
def test_local_prepare_keeps_the_exact_input_revision(turns, revise):
    ref = turns.observe('Meet me at the willow cafe.', source_key='meeting')
    turns.begin()
    turns.claim()
    turns.advance('captured', input_event_refs=[ref])

    def change():
        if revise:
            turns.observe('Meet me at the oak cafe instead.', source_key='meeting', revision=2)

    turns.service.embedding_provider = Local(change)
    request = recall_request(turns)
    request['action'] = 'prepare'
    request['payload'] = {'turn_id': turns.turn_id, 'latest_input_event_ids': [ref['event_id']],
                          'read_fence': request['payload']['read_fence'], 'budget': request['payload']['budget'],
                          'capabilities': integration_capabilities()}
    result = turns.service.handle(turns.principal, request)
    if revise:
        assert result['outcome'] != 'completed'
        assert result['error']['code'] in {'source_unavailable', 'context_stale'}
    else:
        assert result['outcome'] == 'completed', result
        assert result['result']['usage']['embedding_calls'] == 1
