import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from membrain import agent_session
from membrain.agent_session import open_agent
from membrain.api import create_app
from membrain.client import MemoryClient
from membrain.config import Settings
from membrain.helpers import Principal, digest, uid
from membrain.local_profile import _save, ensure_profile
from membrain.runtime import BrainRuntime, DeliveryReceipt, RuntimeBlocked, RuntimePolicy
from membrain.service import MemoryService
from membrain.storage import Database

pytestmark = pytest.mark.integration


@pytest.fixture
def system(tmp_path, monkeypatch):
    dsn = os.environ['MEMORY_DATABASE_URL']
    profile = ensure_profile(tmp_path / 'profile')
    principal = Principal(profile.tenant_id, profile.principal_id)
    service = MemoryService(Database(dsn))
    settings = Settings(database_url=dsn, api_keys={
        hashlib.sha256(profile.api_key.encode()).hexdigest(): principal,
        hashlib.sha256(b'outsider-fixture').hexdigest(): Principal(uid(), uid()),
    })
    requests = []
    with TestClient(create_app(settings, service=service)) as server:
        def forward(request):
            requests.append((request.method, request.url.path, request.content))
            response = server.request(request.method, str(request.url), headers=dict(request.headers), content=request.content)
            return httpx.Response(response.status_code, content=response.content, headers=dict(response.headers))

        @contextmanager
        def connect(*args, **kwargs):
            with MemoryClient('http://testserver', profile.api_key, profile.brain_id,
                              transport=httpx.MockTransport(forward)) as memory:
                yield memory

        with connect() as memory:
            profile = replace(profile, brain_id=memory.create_brain('Temporary tests')['id'])
            _save(profile)
        monkeypatch.setattr(agent_session.desktop_connection, 'open_client', connect)
        with connect() as memory:
            yield SimpleNamespace(memory=memory, profile=profile, principal=principal, service=service, requests=requests, transport=forward)


def pause(system, paused=True):
    status = system.memory.recording_status()
    return system.memory.set_recording(paused=paused, expected_revision=status['revision'])


def durable_rows(system):
    result = {}
    with system.service.database.transaction(system.principal) as conn:
        names = conn.execute("SELECT table_name FROM information_schema.columns WHERE table_schema=current_schema() "
                             "AND column_name='tenant_id' AND table_name LIKE 'memory_%'").fetchall()
        for row in names:
            name = row['table_name']
            result[name] = conn.execute(sql.SQL('SELECT to_jsonb(t) AS value FROM {} t WHERE tenant_id=%s')
                                       .format(sql.Identifier(name)), (system.principal.tenant_id,)).fetchall()
    return result


def test_paused_turns_use_ram_context_without_persisting_content_or_input_hash(system):
    prompts, sent = [], []
    pause(system)
    before = durable_rows(system)
    runtime = BrainRuntime(system.memory, lambda r: prompts.append(r) or 'temporary-answer-sentinel',
                           deliver=lambda r: sent.append(r) or DeliveryReceipt('delivered'))
    first = runtime.respond('temporary-input-sentinel', message_id='one', conversation_id='chat')
    second = runtime.respond('follow up', message_id='two', conversation_id='chat')
    assert first.ephemeral and second.ephemeral and first.stage == second.stage == 'completed'
    assert 'temporary-input-sentinel' in json.dumps(prompts[-1].messages)
    assert len(sent) == 2
    after = durable_rows(system)
    for name in before.keys() | after.keys():
        if name not in {'memory_runtime_turns', 'memory_runtime_turn_transitions'}:
            assert before[name] == after[name], name
    stored = json.dumps(after, default=str)
    for value in ['temporary-input-sentinel', 'temporary-answer-sentinel', digest({'message_id': 'one', 'text': 'temporary-input-sentinel'})]:
        assert value not in stored
        assert value.encode() not in b''.join(body for _, _, body in system.requests)
    row = runtime.journal.get(first.turn_id)
    assert not row['lease_active'] and not row['scope_reserved']
    assert row['input_fingerprint'] == '0' * 64 and row['input_event_refs'] == row['output_event_refs'] == []
    assert runtime.journal.sources(first.turn_id) == {'input_events': [], 'output_events': []}


def test_existing_history_is_read_with_exact_branch_isolation(system):
    for branch, text in [('main', 'visible-old-source'), ('other', 'hidden-other-branch')]:
        system.memory.observe(text, source_event_key=branch, conversation_id='chat', branch_id=branch)
    pause(system)
    prompts = []
    runtime = BrainRuntime(system.memory, lambda r: prompts.append(r) or 'ok')
    assert runtime.respond('new', message_id='one', conversation_id='chat').ephemeral
    assert 'visible-old-source' in prompts[0].memory_context
    assert 'hidden-other-branch' not in json.dumps(prompts[0].messages)


def test_replay_restart_and_resume_never_backfill_or_regenerate(system):
    pause(system)
    calls = []
    runtime = BrainRuntime(system.memory, lambda r: calls.append(r) or 'secret-reply', deliver=lambda _: DeliveryReceipt('delivered'))
    first = runtime.respond('secret-pause-text', message_id='one', conversation_id='chat')
    restarted = BrainRuntime(system.memory, lambda _: pytest.fail('A temporary reply cannot be regenerated'))
    replay = restarted.respond('secret-pause-text', message_id='one', conversation_id='chat')
    assert replay.replayed and replay.text is None and len(calls) == 1
    with pytest.raises(RuntimeBlocked, match='temporary_recovery_unavailable'):
        restarted.resume(first.turn_id)
    pause(system, False)
    with pytest.raises(httpx.HTTPStatusError):
        runtime.respond('secret-pause-text', message_id='one', conversation_id='chat')
    current = runtime.respond('new-recordable-text', message_id='two', conversation_id='chat')
    assert not current.ephemeral
    assert 'secret-pause-text' not in json.dumps(calls[-1].messages)
    assert 'secret-pause-text' not in json.dumps(durable_rows(system), default=str)


def test_policy_change_during_generation_withholds_result_and_discards_temporary_history(system):
    pause(system)
    delivered = []

    def generate(request):
        pause(system, False)
        return 'stale-private-output'

    runtime = BrainRuntime(system.memory, generate, deliver=lambda r: delivered.append(r) or DeliveryReceipt('delivered'))
    with pytest.raises(RuntimeBlocked, match='context_stale'):
        runtime.respond('paused-input', message_id='one', conversation_id='chat')
    assert not delivered and not runtime.temporary.history
    assert 'stale-private-output' not in json.dumps(durable_rows(system), default=str)


@pytest.mark.parametrize('delivery', [False, True])
def test_uncertain_callbacks_are_not_retried_and_do_not_leave_a_content_queue(system, delivery):
    pause(system)
    calls = []

    def fail(request):
        calls.append(request)
        raise OSError('synthetic interruption')

    runtime = BrainRuntime(system.memory, (lambda _: 'reply') if delivery else fail,
                           deliver=fail if delivery else None)
    with pytest.raises(OSError):
        runtime.respond('private-input', message_id='one', conversation_id='chat')
    with pytest.raises(RuntimeBlocked, match='temporary_recovery_unavailable'):
        runtime.respond('private-input', message_id='one', conversation_id='chat')
    assert len(calls) == 1 and not runtime.temporary.history
    row = runtime.journal.list()[0]
    assert row['stage'] == 'failed' and row['failure_code'] == ('delivery_uncertain' if delivery else 'generation_uncertain')
    assert 'private-input' not in json.dumps(durable_rows(system), default=str)


def test_session_never_writes_pending_fingerprint_and_close_drops_history(system):
    pause(system)
    with open_agent(system.profile.directory, conversation_id='chat', generate=lambda _: 'ephemeral-reply',
                    generator_fingerprint='fixture', start_service=False) as agent:
        result = agent.respond('ephemeral-private-input', message_id='one')
        assert result.ephemeral and agent.pending is None
        assert agent._runtime.temporary.history
        assert not list(system.profile.directory.rglob('pending.json'))
    assert not agent._runtime.temporary.history
    for path in system.profile.directory.rglob('*'):
        if path.is_file():
            assert b'ephemeral-private-input' not in path.read_bytes()


def test_pause_between_session_preflight_and_durable_begin_drops_pending_without_capture(system, monkeypatch):
    with open_agent(system.profile.directory, conversation_id='chat', generate=lambda _: 'temporary-reply',
                    generator_fingerprint='fixture', start_service=False) as agent:
        original = agent._runtime.journal.begin

        def begin(**fields):
            pause(system)
            return original(**fields)

        monkeypatch.setattr(agent._runtime.journal, 'begin', begin)
        with pytest.raises(RuntimeBlocked, match='recording_paused'):
            agent.respond('racing-private-input', message_id='race')
        assert agent.pending is None and not list(system.profile.directory.rglob('pending.json'))
        assert agent.respond('fresh-temporary-input', message_id='fresh').ephemeral
        stored = json.dumps(durable_rows(system), default=str)
        assert 'racing-private-input' not in stored and 'fresh-temporary-input' not in stored


def test_pause_during_durable_generation_never_saves_or_automatically_replays_reply(system):
    sent = []

    def generate(request):
        pause(system)
        return 'private-after-pause-reply'

    with open_agent(system.profile.directory, conversation_id='chat', generate=generate,
                    deliver=lambda r: sent.append(r) or DeliveryReceipt('delivered'),
                    generator_fingerprint='fixture', start_service=False) as agent:
        with pytest.raises(RuntimeBlocked):
            agent.respond('captured-before-pause', message_id='one')
        assert not sent
        assert agent.pending is not None
        agent.cancel(turn_id=agent.pending['turn_id'], acknowledge_uncertain=True)
        agent._runtime.generate = lambda _: 'temporary fresh reply'
        assert agent.respond('fresh-temporary-input', message_id='fresh').ephemeral
    stored = json.dumps(durable_rows(system), default=str)
    assert 'captured-before-pause' in stored
    assert 'private-after-pause-reply' not in stored and 'fresh-temporary-input' not in stored


def test_bounds_and_same_scope_exclusion_remain_enforced(system):
    pause(system)
    prompts = []
    runtime = BrainRuntime(system.memory, lambda r: prompts.append(r) or 'reply',
                           policy=RuntimePolicy(memory_context_tokens=40, recent_context_events=2))
    for i in range(4):
        runtime.respond('message-' + str(i), message_id=str(i), conversation_id='chat')
    history = runtime.temporary.history[('chat', 'main')][1]
    assert len(history) <= 2 and sum(len(x['content'].encode()) for x in history) <= 40
    other = BrainRuntime(system.memory, lambda _: 'unused')
    runtime.generate = lambda _: other.respond('overlap', message_id='second', conversation_id='chat')
    with pytest.raises(RuntimeBlocked, match='scope_conflict'):
        runtime.respond('first', message_id='first', conversation_id='chat')


def test_erasure_during_temporary_generation_blocks_stale_output(system):
    system.memory.observe('old-source', source_event_key='old', conversation_id='chat', branch_id='main')
    pause(system)
    sent = []

    def generate(request):
        assert 'old-source' in request.memory_context
        system.memory.forget([], kind='all_authorized_scope', mode='erase_content', expected_scope_generation=1)
        return 'stale-reply'

    runtime = BrainRuntime(system.memory, generate, deliver=lambda r: sent.append(r) or DeliveryReceipt('delivered'))
    with pytest.raises(RuntimeBlocked, match='context_stale'):
        runtime.respond('temporary', message_id='one', conversation_id='chat')
    assert not sent and not runtime.temporary.history


@pytest.mark.parametrize('change', ['resume', 'pause_cycle', 'erase'])
def test_inflight_temporary_delivery_preserves_fact_but_withholds_stale_content(system, change):
    pause(system)
    sent = []

    def deliver(request):
        sent.append(request)
        if change == 'erase':
            system.memory.forget([], kind='all_authorized_scope', mode='erase_content', expected_scope_generation=1)
        else:
            pause(system, False)
            if change == 'pause_cycle':
                pause(system)
        return DeliveryReceipt('delivered')

    runtime = BrainRuntime(system.memory, lambda _: 'sent-private-reply', deliver=deliver)
    with pytest.raises(RuntimeBlocked, match='context_stale'):
        runtime.respond('private-input', message_id='one', conversation_id='chat')
    row = runtime.journal.list()[0]
    assert row['ephemeral_delivery_state'] == 'delivered'
    assert row['stage'] == 'failed' and not row['scope_reserved'] and not row['lease_active']
    assert len(sent) == 1 and not runtime.temporary.history
    assert 'sent-private-reply' not in json.dumps(durable_rows(system), default=str)


@pytest.mark.parametrize('state', ['cancelled', 'unknown', 'partially_delivered'])
def test_temporary_delivery_states_do_not_claim_a_full_send(system, state):
    pause(system)
    runtime = BrainRuntime(system.memory, lambda _: 'full draft',
                           deliver=lambda _: DeliveryReceipt(state, 'actual fragment' if state == 'partially_delivered' else None))
    if state == 'partially_delivered':
        result = runtime.respond('input', message_id='one', conversation_id='chat')
        assert result.text == 'actual fragment'
    else:
        with pytest.raises(RuntimeBlocked, match='cancelled' if state == 'cancelled' else 'delivery_uncertain'):
            runtime.respond('input', message_id='one', conversation_id='chat')
    row = runtime.journal.list()[0]
    assert row['ephemeral_delivery_state'] == state
    assert not row['lease_active'] and not row['scope_reserved']
    assert 'actual fragment' not in json.dumps(durable_rows(system), default=str)


def test_lost_temporary_settlement_response_never_repeats_delivery(system, monkeypatch):
    pause(system)
    sent = []
    runtime = BrainRuntime(system.memory, lambda _: 'private-reply',
                           deliver=lambda r: sent.append(r) or DeliveryReceipt('delivered'))
    original = runtime.journal.advance_ephemeral

    def lose_response(*args, **fields):
        result = original(*args, **fields)
        if fields['stage'] == 'completed':
            raise httpx.ReadError('Synthetic lost settlement response')
        return result

    monkeypatch.setattr(runtime.journal, 'advance_ephemeral', lose_response)
    with pytest.raises(httpx.ReadError):
        runtime.respond('input', message_id='one', conversation_id='chat')
    replay = runtime.respond('input', message_id='one', conversation_id='chat')
    assert replay.replayed and replay.text is None and len(sent) == 1
    assert runtime.journal.get(replay.turn_id)['ephemeral_delivery_state'] == 'delivered'
    assert not runtime.temporary.history


@pytest.mark.parametrize('verdict', ['approved', 'rejected', 'invalid'])
def test_temporary_answer_review_runs_once_without_persisting_draft_or_review(system, verdict):
    from test_answer_review import assessment

    from membrain.answer_review import AnswerReviewer

    pause(system)
    calls, sent = [], []
    response = assessment()
    if verdict == 'rejected':
        response = assessment(applicability='violation')
        response['findings'] = [{'code': 'applicability_override', 'quote': 'private-draft'}]

    def review(request):
        calls.append(request)
        row = runtime.journal.get(request.turn_id)
        assert row['response_review_calls'] == 1 and row['response_review'] is None
        return 'invalid json' if verdict == 'invalid' else json.dumps(response)

    runtime = BrainRuntime(system.memory, lambda _: 'private-draft',
                           answer_reviewer=AnswerReviewer(review, reviewer_id='synthetic-review'),
                           deliver=lambda r: sent.append(r) or DeliveryReceipt('delivered'))
    if verdict == 'approved':
        assert runtime.respond('private-review-input', message_id='one', conversation_id='chat').ephemeral
        assert len(sent) == 1
    else:
        with pytest.raises(RuntimeBlocked):
            runtime.respond('private-review-input', message_id='one', conversation_id='chat')
        assert not sent
    assert len(calls) == 1
    stored = json.dumps(durable_rows(system), default=str)
    assert 'private-review-input' not in stored and 'private-draft' not in stored and calls[0].draft_sha256 not in stored


def test_mutating_prompt_during_generation_cannot_reach_delivery(system):
    pause(system)
    sent = []

    def generate(request):
        request.messages[-1]['content'] = 'substituted input'
        return 'reply'

    runtime = BrainRuntime(system.memory, generate, deliver=lambda r: sent.append(r) or DeliveryReceipt('delivered'))
    with pytest.raises(RuntimeBlocked, match='context_stale'):
        runtime.respond('original input', message_id='one', conversation_id='chat')
    assert not sent


def test_temporary_api_rejects_content_and_durable_output_even_after_resume(system):
    status = pause(system)
    runtime = BrainRuntime(system.memory, lambda _: 'unused')
    identifier = 'turn-' + 'a' * 40
    row = runtime.journal.begin_ephemeral(turn_id=identifier, conversation_id='chat', branch_id='main',
                                          expected_recording_revision=status['revision'])
    claim = runtime.journal.claim(identifier, worker_id='test')
    with pytest.raises(httpx.HTTPStatusError):
        system.memory._request('POST', runtime.journal._path(identifier, 'ephemeral-advance'), json={
            'lease_token': claim['lease_token'], 'expected_revision': claim['revision'],
            'stage': 'generating', 'text': 'must-not-be-accepted',
        })
    pause(system, False)
    with pytest.raises(httpx.HTTPStatusError):
        runtime.journal.record_output(identifier, lease_token=claim['lease_token'],
                                      expected_revision=claim['revision'], text='forbidden-durable-output', delivery_state='draft')
    assert row['ephemeral'] and 'forbidden-durable-output' not in json.dumps(durable_rows(system), default=str)
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation), system.service.database.transaction(system.principal) as conn:
        conn.execute("UPDATE memory_runtime_turns SET input_fingerprint=%s WHERE brain_id=%s AND turn_id=%s",
                     (digest('forbidden hash'), system.profile.brain_id, identifier))


def test_process_death_does_not_recover_private_input_and_explicit_cancel_releases_scope(system, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    from examples.evaluation_host import loopback_server

    pause(system)
    key = system.profile.api_key
    settings = Settings(database_url=os.environ['MEMORY_DATABASE_URL'], api_keys={hashlib.sha256(key.encode()).hexdigest(): system.principal})
    program = '''
import os,sys
from membrain.client import MemoryClient
from membrain.runtime import BrainRuntime,RuntimeBlocked
with MemoryClient(sys.argv[1],sys.argv[2],sys.argv[3],trust_env=False) as memory:
    def generate(request):
        os._exit(37)
    runtime=BrainRuntime(memory,generate)
    try:
        runtime.respond('process-private-input',message_id='crash',conversation_id='chat')
    except RuntimeBlocked as error:
        print(error.code)
'''
    with loopback_server(create_app(settings, service=system.service)) as url:
        args = [sys.executable, '-c', program, url, key, system.profile.brain_id]
        crashed = subprocess.run(args, capture_output=True, text=True, timeout=30)
        assert crashed.returncode == 37
        restarted = subprocess.run(args, capture_output=True, text=True, timeout=30)
        assert restarted.returncode == 0 and restarted.stdout.strip() == 'temporary_recovery_unavailable'
    identifier = 'turn-' + digest([system.profile.brain_id, 'chat', 'main', 'crash'])[:40]
    assert 'process-private-input' not in json.dumps(durable_rows(system), default=str)
    with system.service.database.transaction(system.principal) as conn:
        conn.execute("UPDATE memory_runtime_turns SET lease_expires_at=clock_timestamp()-interval '1 second' "
                     "WHERE brain_id=%s AND turn_id=%s", (system.profile.brain_id, identifier))
    with open_agent(system.profile.directory, conversation_id='chat', generate=lambda _: 'new reply',
                    generator_fingerprint='fixture', start_service=False) as agent:
        assert agent.pending is None
        from membrain.agent_session import SessionError

        with pytest.raises(SessionError, match='acknowledgement_required'):
            agent.cancel(turn_id=identifier)
        assert agent.cancel(turn_id=identifier, acknowledge_uncertain=True)['failure_code'] == 'generation_uncertain'
        assert agent.respond('new independent input', message_id='fresh').ephemeral


def test_temporary_control_and_context_preserve_owner_isolation(system):
    status = pause(system)
    runtime = BrainRuntime(system.memory, lambda _: 'unused')
    identifier = 'turn-' + 'b' * 40
    runtime.journal.begin_ephemeral(turn_id=identifier, conversation_id='chat', branch_id='main',
                                   expected_recording_revision=status['revision'])
    claimed = runtime.journal.claim(identifier, worker_id='owner')
    with MemoryClient('http://testserver', 'outsider-fixture', system.profile.brain_id,
                      transport=httpx.MockTransport(system.transport)) as outsider:
        other = BrainRuntime(outsider, lambda _: pytest.fail('Unauthorized generation'))
        calls = [
            lambda: other.journal.begin_ephemeral(turn_id='turn-' + 'c' * 40, conversation_id='chat', branch_id='main',
                                                  expected_recording_revision=status['revision']),
            lambda: other.journal.ephemeral_context(identifier, lease_token=claimed['lease_token'], limit=6, max_bytes=4000),
            lambda: other.journal.advance_ephemeral(identifier, lease_token=claimed['lease_token'],
                                                    expected_revision=claimed['revision'], stage='generating'),
        ]
        for call in calls:
            with pytest.raises(httpx.HTTPStatusError) as denied:
                call()
            assert denied.value.response.status_code == 404
