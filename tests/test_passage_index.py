import copy
from dataclasses import replace

import pytest
from test_candidates import SPACE, key, query_vector
from test_candidates import candidates as candidates
from test_turns import turns as turns
from test_vector_jobs import drain, recall_request

from membrain import host, vector_jobs
from membrain.embeddings import EmbeddingPassage, EmbeddingResult, EmbeddingSpace
from membrain.helpers import DomainError, Principal, uid

pytestmark = pytest.mark.integration


class PassageProvider:
    space = EmbeddingSpace('passage-test', 'v1', 3)
    document_index_version = 'test-passages-v1'

    def __init__(self, mutate=None, invalid=False):
        self.mutate = mutate
        self.invalid = invalid

    def __call__(self, request):
        if request.purpose == 'query':
            return EmbeddingResult(self.space, ((1., 0., 0.),), None, 'query', 0)
        if self.mutate:
            self.mutate()
        parts = []
        for text in request.texts:
            windows = []
            for start in range(0, len(text), 300):
                end = min(start + 400, len(text))
                vector = (1., 0., 0.) if 'passport' in text[start:end] else (0., 1., 0.)
                windows.append(EmbeddingPassage(start, end, vector))
                if end == len(text):
                    break
            if self.invalid:
                windows[0] = EmbeddingPassage(1, windows[0].end, windows[0].vector)
            parts.append(tuple(windows))
        return EmbeddingResult(self.space, tuple((0., 1., 0.) for _ in request.texts), None, 'document', 0,
                               tuple(parts), self.document_index_version)


TEXT = 'I reviewed ordinary office receipts and sorted supplies ' * 70 + 'and my passport is in the blue kitchen drawer'


def test_many_passages_cannot_consume_other_parents_candidate_slots(candidates):
    first = candidates.add('I keep routine receipts in the office drawer ' * 100)
    second = candidates.add('My travel documents are in the blue cupboard.')
    candidates.embed(first, [0., 1., 0.])
    candidates.embed(second, [1., .1, 0.])
    with candidates.database.transaction(candidates.principal) as conn:
        conn.execute('INSERT INTO memory_embedding_passages(tenant_id,owner_id,brain_id,memory_id,memory_revision,'
                     'model,model_version,passage_index,start_offset,end_offset,embedding) '
                     'SELECT %s,%s,%s,%s,%s,%s,%s,n,n*30,n*30+400,\'[1,0,0]\'::vector '
                     'FROM generate_series(0,99) n',
                     (*candidates.params, *key(first), SPACE.model, SPACE.model_version))
    _, state = candidates.query('passport location', budget=2048, query_embedding=query_vector())
    roots = state['candidate_versions']
    assert len(roots) == len(set(roots)) == 2
    assert set(roots) == {key(first), key(second)}
    assert all(any(signal['method'] == 'vector' for signal in state['rank_signals'][root]) for root in roots)


def counts(turns):
    with turns.database.transaction(turns.principal) as conn:
        return tuple(conn.execute(f'SELECT count(*) AS n FROM {table} WHERE brain_id=%s',
                                  (turns.brain,)).fetchone()['n']
                     for table in ('memory_embeddings', 'memory_embedding_passages'))


@pytest.mark.parametrize('prefix,qualifier', [('', ''), ('I dreamed that ', 'dream'), ('Suppose that ', 'hypothetical')])
def test_passage_recall_keeps_one_parent_and_delivers_the_matched_tail_to_the_host(turns, prefix, qualifier):
    text = prefix + TEXT
    turns.service.embedding_provider = PassageProvider()
    event = turns.observe(text)
    drain(turns)
    parents, passages = counts(turns)
    assert parents == 1 and passages > 1
    request = recall_request(turns, 'travel document location')
    if qualifier:
        ordinary = turns.service.handle(turns.principal, request)
        assert ordinary['outcome'] == 'completed' and ordinary['result']['items'] == []
        request = recall_request(turns, 'travel document location')
        request['payload']['world_filter'] = [qualifier]
    response = turns.service.handle(turns.principal, request)
    assert response['outcome'] == 'completed', response
    items = response['result']['items']
    assert len(items) == 1 and items[0]['memory']['statement'].endswith(text)
    assert items[0]['matched_statement_span']['start'] > 3000
    assert items[0]['memory']['evidence_refs'][0]['event_id'] == event['event_id']

    class Client:
        brain_id = turns.brain

        def recall(self, query, **options):
            return response

        def timeline(self, **options):
            if not options.get('event_ids'):
                return {'items': []}
            return {'items': [{'event_id': event['event_id'], 'text': text, 'actor_role': 'user',
                               'conversation_id': turns.conversation, 'recorded_at': '2026-11-07'}]}

        def trace_recall(self, event_ids):
            self.traced = event_ids

    client = Client()
    context = host.recall_context(client, 'travel document location', current_conversation='new', boundaries=[])
    assert 'passport is in the blue kitchen drawer' in context
    if qualifier:
        assert f'user said, {qualifier}' in context
    assert client.traced == [event['event_id']] and len(context) <= host.CONTEXT_CHARACTERS
    del response['result']['items'][0]['matched_statement_span']
    assert 'passport' not in host.recall_context(client, 'travel document location', boundaries=[])


def test_passages_are_private_and_erasing_the_source_cascades_to_every_index_row(turns):
    turns.service.embedding_provider = PassageProvider()
    event = turns.observe(TEXT)
    drain(turns)
    with turns.database.transaction(Principal(uid(), uid())) as conn:
        assert not conn.execute('SELECT 1 FROM memory_embedding_passages WHERE brain_id=%s',
                                (turns.brain,)).fetchone()
    turns.action('forget', {'idempotency_key': uid(), 'selector': {'kind': 'events', 'ids': [event['event_id']]},
                            'mode': 'erase_content', 'expected_scope_generation': 1})
    assert counts(turns) == (0, 0)


def test_erasure_during_passage_encoding_cannot_publish_parent_or_fragments(turns):
    event = turns.observe(TEXT)
    turns.service.embedding_provider = PassageProvider()
    assert turns.service.work_once(turns.principal, turns.brain) == 1

    def erase():
        turns.action('forget', {'idempotency_key': uid(), 'selector': {'kind': 'events', 'ids': [event['event_id']]},
                                'mode': 'erase_content', 'expected_scope_generation': 1})

    turns.service.embedding_provider = PassageProvider(mutate=erase)
    with pytest.raises(DomainError):
        turns.service.work_once(turns.principal, turns.brain)
    assert counts(turns) == (0, 0)


def test_incomplete_passage_coverage_is_never_marked_as_an_indexed_document(turns):
    turns.service.embedding_provider = PassageProvider(invalid=True)
    turns.observe(TEXT)
    assert turns.service.work_once(turns.principal, turns.brain) == 1
    with pytest.raises(DomainError, match='cover the unchanged source'):
        turns.service.work_once(turns.principal, turns.brain)
    assert counts(turns) == (0, 0)


@pytest.mark.parametrize('damage', ['count', 'absent', 'zero', 'nonfinite', 'dimension'])
def test_invalid_batch_shapes_do_not_publish_a_partial_index(turns, damage):
    class Broken(PassageProvider):
        def __call__(self, request):
            result = super().__call__(request)
            if damage == 'count':
                return replace(result, passages=result.passages[:-1])
            if damage == 'absent':
                return replace(result, passages=None)
            vector = {'zero': (0., 0., 0.), 'nonfinite': (float('nan'), 0., 0.), 'dimension': (1., 0.)}[damage]
            return replace(result, vectors=(vector, *result.vectors[1:]))

    turns.service.embedding_provider = Broken()
    turns.observe(TEXT)
    assert turns.service.work_once(turns.principal, turns.brain) == 1
    with pytest.raises(DomainError):
        turns.service.work_once(turns.principal, turns.brain)
    assert counts(turns) == (0, 0)


def test_existing_single_vector_documents_are_backfilled_once_for_the_new_index_version(turns):
    class Legacy(PassageProvider):
        document_index_version = 'single-vector-v1'

        def __call__(self, request):
            return EmbeddingResult(self.space, tuple((0., 1., 0.) for _ in request.texts), None, 'legacy', 0)

    turns.service.embedding_provider = Legacy()
    turns.observe(TEXT)
    drain(turns)
    assert counts(turns) == (1, 0)
    turns.service.embedding_provider = PassageProvider()
    assert vector_jobs.queue_missing_embeddings(turns.service, turns.principal, turns.brain)[0] == 1
    drain(turns)
    parents, passages = counts(turns)
    assert parents == 1 and passages > 1
    assert vector_jobs.queue_missing_embeddings(turns.service, turns.principal, turns.brain)[0] == 0


@pytest.mark.parametrize('damage', ['scope', 'hash', 'suppressed', 'deleted'])
def test_passage_hits_cannot_bypass_the_parent_memory_guards(turns, damage):
    from psycopg.types.json import Jsonb

    turns.service.embedding_provider = PassageProvider()
    turns.observe(TEXT)
    drain(turns)
    with turns.database.transaction(turns.principal) as conn:
        if damage == 'scope':
            row = conn.execute('SELECT id,document FROM memory_assertions WHERE brain_id=%s',
                               (turns.brain,)).fetchone()
            memory = copy.deepcopy(row['document'])
            memory['scope'].update(visibility='conversation', conversation_id='hidden')
            conn.execute('UPDATE memory_assertions SET document=%s WHERE brain_id=%s AND id=%s',
                         (Jsonb(memory), turns.brain, row['id']))
        elif damage == 'hash':
            conn.execute("UPDATE memory_embeddings SET content_hash=%s WHERE brain_id=%s", ('0' * 64, turns.brain))
        else:
            conn.execute(f'UPDATE memory_assertions SET {damage}=true WHERE brain_id=%s', (turns.brain,))
    response = turns.service.handle(turns.principal, recall_request(turns, 'travel document location'))
    assert response['outcome'] == 'completed', response
    assert not any(item.get('matched_statement_span') for item in response['result']['items'])
