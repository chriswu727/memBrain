import copy

import pytest
from psycopg.types.json import Jsonb
from test_passage_index import TEXT, PassageProvider
from test_turns import turns as turns
from test_vector_jobs import drain, recall_request

from membrain import host, relationship
from membrain.helpers import DomainError, Principal, uid

pytestmark = pytest.mark.integration


def prepare(turns, text=TEXT):
    turns.service.embedding_provider = PassageProvider()
    event = turns.observe(text)
    drain(turns)
    response = turns.service.handle(turns.principal, recall_request(turns, 'travel document location'))
    assert response['outcome'] == 'completed', response
    item = response['result']['items'][0]
    memory = item['memory']
    request = {'memory_id': memory['memory_id'], 'revision': memory['revision'],
               'span': item['matched_statement_span']}
    return event, request, response


def read(turns, requests, query='travel document location'):
    return turns.service.recall_windows(turns.principal, turns.brain, requests, query,
                                        conversation_id='new', branch_id='main')


class Client:
    def __init__(self, turns):
        self.turns = turns
        self.brain_id = turns.brain
        self.traced = []

    def recall(self, query, **options):
        request = recall_request(self.turns, query)
        request['payload'].update(options)
        return self.turns.service.handle(self.turns.principal, request)

    def recall_windows(self, requests, query):
        return read(self.turns, requests, query)

    def timeline(self, **options):
        return self.turns.service.timeline(self.turns.principal, self.brain_id, **options)

    def following(self, ids):
        return self.turns.service.following(self.turns.principal, self.brain_id, ids)

    def trace_recall(self, ids):
        self.traced = ids


@pytest.mark.parametrize('repeat', [70, 500, 850])
def test_bounded_fresh_windows_deliver_long_tails_without_increasing_host_context_budget(turns, repeat):
    text = 'I reviewed ordinary office receipts and sorted supplies ' * repeat + 'and my passport is in the blue kitchen drawer'
    event, request, response = prepare(turns, text)
    item = response['result']['items'][0]
    assert item['memory']['statement'].endswith(text)
    window = read(turns, [request])['items'][0]
    assert len(window['text']) <= 700
    assert 'passport is in the blue kitchen drawer' in window['text']
    assert window['text'] == text[window['window_span']['start']:window['window_span']['end']]
    client = Client(turns)
    context = host.recall_context(client, 'travel document location', current_conversation='new', boundaries=[])
    assert 'passport is in the blue kitchen drawer' in context
    assert 'excerpt' in context and len(context) <= host.CONTEXT_CHARACTERS
    assert client.traced == [event['event_id']]


def test_source_boundary_outside_the_excerpt_is_checked_on_the_complete_message(turns):
    text = 'ordinary office paperwork ' * 850 + 'my confidential diagnosis ' + 'ordinary paperwork ' * 350
    text += 'and my passport is in the blue kitchen drawer'
    _, request, _ = prepare(turns, text)
    relationship.add_boundary(turns.service, turns.principal, turns.brain, 'diagnosis')
    assert read(turns, [request])['items'] == []
    client = Client(turns)
    assert host.recall_context(client, 'travel document location', boundaries=[]) is None
    assert client.traced == []
    assert read(turns, [request], 'diagnosis and travel document location')['items']


@pytest.mark.parametrize('damage', ['erasure', 'hash', 'revision', 'suppression', 'scope', 'branch'])
def test_window_reads_recheck_current_parent_and_source_authority(turns, damage):
    event, request, _ = prepare(turns)
    if damage == 'erasure':
        turns.action('forget', {'idempotency_key': uid(), 'selector': {'kind': 'events', 'ids': [event['event_id']]},
                                'mode': 'erase_content', 'expected_scope_generation': 1})
    elif damage == 'revision':
        request['revision'] += 1
    else:
        with turns.database.transaction(turns.principal) as conn:
            if damage == 'suppression':
                conn.execute('UPDATE memory_assertions SET suppressed=true WHERE brain_id=%s', (turns.brain,))
            elif damage in ('scope', 'branch'):
                row = conn.execute('SELECT document FROM memory_assertions WHERE brain_id=%s',
                                   (turns.brain,)).fetchone()
                memory = copy.deepcopy(row['document'])
                memory['scope'].update(conversation_id='new', visibility='conversation', branch_id='hidden')
                if damage == 'scope':
                    memory['scope']['conversation_id'] = 'hidden'
                conn.execute('UPDATE memory_assertions SET document=%s WHERE brain_id=%s',
                             (Jsonb(memory), turns.brain))
            else:
                row = conn.execute('SELECT document FROM memory_events WHERE brain_id=%s AND id=%s',
                                   (turns.brain, event['event_id'])).fetchone()
                document = copy.deepcopy(row['document'])
                document['content_sha256'] = '0' * 64
                conn.execute('UPDATE memory_events SET document=%s WHERE brain_id=%s AND id=%s',
                             (Jsonb(document), turns.brain, event['event_id']))
    assert read(turns, [request])['items'] == []


def test_window_reader_rejects_a_foreign_principal_and_unbounded_requests(turns):
    _, request, _ = prepare(turns)
    with pytest.raises(DomainError):
        turns.service.recall_windows(Principal(uid(), uid()), turns.brain, [request], 'passport')
    for windows in ([], [request] * 13, [request, request],
                    [{**request, 'revision': True}],
                    [{**request, 'span': {'start': 0, 'end': 401, 'unit': 'unicode_code_point'}}]):
        with pytest.raises(DomainError):
            read(turns, windows)


def test_http_windows_require_authentication_and_python_client_preserves_scope(turns):
    import hashlib

    import httpx
    from fastapi.testclient import TestClient

    from membrain.api import create_app
    from membrain.client import MemoryClient
    from membrain.config import Settings

    _, request, _ = prepare(turns)
    settings = Settings(database_url=turns.database.dsn,
                        api_keys={hashlib.sha256(b'window-test').hexdigest(): turns.principal})
    with TestClient(create_app(settings, service=turns.service)) as api:
        url = f'/v1/brains/{turns.brain}/recall-windows'
        assert api.post(url, json={'windows': [request], 'query': 'passport'}).status_code == 401
        headers = {'Authorization': 'Bearer window-test'}
        for body in ({'windows': [], 'query': 'passport'}, {'windows': [request], 'query': 'passport', 'unknown': 1}):
            assert api.post(url, headers=headers, json=body).status_code == 422

        def send(message):
            response = api.request(message.method, message.url.path, headers=dict(message.headers), content=message.content)
            return httpx.Response(response.status_code, json=response.json())

        with MemoryClient('http://testserver', 'window-test', turns.brain, transport=httpx.MockTransport(send)) as client:
            found = client.recall_windows([request], 'passport', conversation_id='new', branch_id='main')
            assert 'blue kitchen drawer' in found['items'][0]['text']


def test_matched_context_projection_is_explicit_bounded_and_keeps_the_original_memory(turns):
    from membrain.context_views import recall_context_view

    _, _, response = prepare(turns, TEXT * 8)
    original = copy.deepcopy(response)
    projected = recall_context_view(response['result'])
    fragment = projected['memories'][0]
    assert fragment['recall_detail'] == 'matched_excerpt_expandable'
    assert fragment['excerpt_use'] == 'partial_original_statement_not_an_independent_fact'
    assert len(fragment['statement']) <= 400
    assert fragment['statement_characters'] > 30000
    assert fragment['use'] == 'historical_report_not_current_rule'
    assert response == original
    request = recall_request(turns, 'passport')
    request['payload']['intent'] = 'exact_quote'
    request['payload']['budget']['max_context_tokens'] = 64000
    full = turns.service.handle(turns.principal, request)
    assert full['outcome'] == 'completed'
    assert all('matched_statement_span' not in item for item in full['result']['items'])


def test_an_inquiry_excerpt_keeps_its_original_act_in_model_and_host_context(turns):
    from membrain.context_views import recall_context_view

    _, _, response = prepare(turns, 'What do you think about ' + TEXT + '?')
    fragment = recall_context_view(response['result'])['memories'][0]
    assert fragment['source_act'] == {'act': 'inquiry', 'rule_version': 'literal-episodes-v3'}
    client = Client(turns)
    context = host.recall_context(client, 'travel document location', boundaries=[])
    assert 'inquiry excerpt' in context and 'passport' in context


@pytest.mark.parametrize('failure', ['exception', 'omitted', 'wrong_reference', 'wrong_span'])
def test_failed_or_mismatched_window_read_does_not_use_the_old_timeline_copy(turns, failure):
    prepare(turns)

    class Broken(Client):
        def recall_windows(self, requests, query):
            if failure == 'exception':
                raise TimeoutError('source read unavailable')
            result = super().recall_windows(requests, query)
            if failure == 'omitted':
                result['items'] = []
            elif failure == 'wrong_reference':
                result['items'][0]['evidence_ref']['source_content_sha256'] = '0' * 64
            else:
                result['items'][0]['window_span']['start'] += 1
            return result

    client = Broken(turns)
    assert host.recall_context(client, 'travel document location', boundaries=[]) is None
    assert client.traced == []
