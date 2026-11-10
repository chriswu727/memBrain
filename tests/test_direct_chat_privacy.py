"""Local privacy controls for direct chat: device capture, one conversation branch's off-record choice and a
per-turn opt-out, against a real service and PostgreSQL. Generation and delivery are deterministic callbacks."""
import json
import time
from contextlib import contextmanager
from dataclasses import replace
from typing import Annotated

import httpx
import pytest
from pydantic import ConfigDict, Field
from test_ephemeral_chat import durable_rows, pause
from test_ephemeral_chat import system as system

from membrain import agent_session, api, desktop_chat, host, local_recording
from membrain.agent_session import SessionError, open_agent
from membrain.client import MemoryClient
from membrain.helpers import digest
from membrain.local_profile import _save
from membrain.runtime import (
    BrainRuntime,
    DeliveryReceipt,
    RuntimeBlocked,
    RuntimePolicy,
    TemporaryCause,
)

pytestmark = pytest.mark.integration

CONTROL_TABLES = {'memory_runtime_turns', 'memory_runtime_turn_transitions'}
OFF_RECORD = (TemporaryCause('off_record', 'conversation_branch'),)


@contextmanager
def session(system, conversation='chat', branch='main', generate=None, deliver=True, **fields):
    sent = []
    callback = (lambda request: sent.append(request) or DeliveryReceipt('delivered')) if deliver else None
    with open_agent(system.profile.directory, conversation_id=conversation, branch_id=branch,
                    generate=generate or (lambda _: 'synthetic-reply'), generator_fingerprint='fixture',
                    deliver=callback, start_service=False, **fields) as agent:
        agent.sent = sent
        yield agent


def stored(system):
    return json.dumps(durable_rows(system), default=str)


def assert_nothing_captured(system, before, *secrets, changed=()):
    """No memory, learning, working-state or queue row changed; only content-free turn control rows may differ.
    ``changed`` names a table the test itself changed through a server control."""
    after = durable_rows(system)
    for name in before.keys() | after.keys():
        if name not in CONTROL_TABLES and name not in changed:
            assert before.get(name) == after.get(name), name
    sent = b''.join(body for _, _, body in system.requests)
    text = json.dumps(after, default=str)
    for secret in secrets:
        assert secret not in text and secret.encode() not in sent
        assert digest({'message_id': 'one', 'text': secret}) not in text
        for path in system.profile.directory.rglob('*'):
            if path.is_file():
                assert secret.encode() not in path.read_bytes(), path
    assert not list(system.profile.directory.rglob('pending.json'))
    assert not (system.profile.directory / 'plugin' / 'spool.jsonl').exists()


def begin_bodies(system):
    return [json.loads(body) for method, path, body in system.requests
            if method == 'POST' and path.endswith('/runtime/ephemeral-turns')]


def durable_begins(system):
    return [path for method, path, _ in system.requests if method == 'POST' and path.endswith('/runtime/turns')]


# --- BrainRuntime: an explicit per-turn opt-out, with no device-local discovery ------------------------------


def test_record_false_is_temporary_while_server_recording_stays_enabled(system):
    prompts = []
    status = system.memory.recording_status()
    before = durable_rows(system)
    runtime = BrainRuntime(system.memory, lambda r: prompts.append(r) or 'opt-out-answer-sentinel',
                           deliver=lambda _: DeliveryReceipt('delivered'))
    result = runtime.respond('opt-out-input-sentinel', message_id='one', conversation_id='chat', record=False)
    assert result.ephemeral and result.stage == 'completed' and result.text == 'opt-out-answer-sentinel'
    assert result.temporary_causes == (TemporaryCause('caller_opt_out', 'turn'),)
    assert system.memory.recording_status() == status == {'paused': False, 'revision': 0}
    assert begin_bodies(system)[-1]['off_record'] is True and not durable_begins(system)
    assert_nothing_captured(system, before, 'opt-out-input-sentinel', 'opt-out-answer-sentinel')
    row = runtime.journal.get(result.turn_id)
    assert row['ephemeral'] and row['input_fingerprint'] == '0' * 64 and not row['scope_reserved']
    assert row['input_event_refs'] == row['output_event_refs'] == row['context_event_refs'] == []
    assert 'off the record' in json.dumps(prompts[0].messages) and 'Recording is paused' not in json.dumps(prompts[0].messages)

    recorded = runtime.respond('recordable-input', message_id='two', conversation_id='chat')
    assert not recorded.ephemeral and recorded.temporary_causes == ()
    assert 'opt-out-input-sentinel' not in json.dumps(prompts[-1].messages)
    assert 'recordable-input' in stored(system) and 'opt-out-input-sentinel' not in stored(system)
    assert not runtime.temporary.history


def test_record_false_is_never_downgraded_to_a_recorded_turn(system):
    runtime = BrainRuntime(system.memory, lambda _: pytest.fail('No model call is allowed'))
    requests = len(system.requests)
    with pytest.raises(ValueError, match='record=False'):
        runtime.respond('private', message_id='one', conversation_id='chat', record=False, allow_temporary=False)
    for invalid in (None, 0, 'no'):
        with pytest.raises(ValueError, match='boolean'):
            runtime.respond('private', message_id='one', conversation_id='chat', record=invalid)
    assert len(system.requests) == requests and 'private' not in stored(system)


def test_server_pause_and_opt_out_are_both_named_without_an_explicit_reservation(system):
    pause(system)
    runtime = BrainRuntime(system.memory, lambda _: 'reply')
    result = runtime.respond('private', message_id='one', conversation_id='chat', record=False)
    assert result.temporary_causes == (TemporaryCause('server_paused', 'brain'), TemporaryCause('caller_opt_out', 'turn'))
    assert 'off_record' not in begin_bodies(system)[-1]
    legacy = runtime.respond('private', message_id='two', conversation_id='chat')
    assert legacy.temporary_causes == (TemporaryCause('server_paused', 'brain'),)
    replay = runtime.respond('private', message_id='two', conversation_id='chat')
    assert replay.replayed and replay.text is None and replay.temporary_causes == ()


def test_explicit_reservation_keeps_authentication_revision_scope_and_idempotency(system):
    journal = BrainRuntime(system.memory, lambda _: 'unused').journal
    status = system.memory.recording_status()
    fields = {'conversation_id': 'chat', 'branch_id': 'main', 'expected_recording_revision': status['revision']}

    def rejected(call, code, status_code=409):
        with pytest.raises(httpx.HTTPStatusError) as error:
            call()
        assert error.value.response.status_code == status_code
        assert error.value.response.json()['error']['code'] == code

    first = 'turn-' + 'a' * 40
    rejected(lambda: journal.begin_ephemeral(turn_id=first, **fields), 'context_stale')
    rejected(lambda: journal.begin_ephemeral(turn_id=first, off_record=True, **(fields | {
        'expected_recording_revision': status['revision'] + 1})), 'context_stale')
    rejected(lambda: system.memory._request('POST', journal._path().removesuffix('turns') + 'ephemeral-turns', json={
        'turn_id': first, **fields, 'off_record': 'yes'}), 'validation_failed', 422)
    assert journal.list() == []

    row = journal.begin_ephemeral(turn_id=first, off_record=True, **fields)
    assert row['ephemeral'] and row['scope_reserved'] and row['recording_revision'] == status['revision']
    assert journal.begin_ephemeral(turn_id=first, off_record=True, **fields)['revision'] == row['revision']
    rejected(lambda: journal.begin_ephemeral(turn_id='turn-' + 'b' * 40, off_record=True, **fields), 'scope_conflict')
    rejected(lambda: journal.begin(turn_id='turn-' + 'b' * 40, conversation_id='chat', branch_id='main',
                                   input_fingerprint=digest('durable')), 'scope_conflict')
    rejected(lambda: journal.begin(turn_id=first, conversation_id='chat', branch_id='main',
                                   input_fingerprint=digest('durable')), 'stage_conflict')
    other = journal.begin_ephemeral(turn_id='turn-' + 'c' * 40, off_record=True, **(fields | {'branch_id': 'other'}))
    assert other['scope_reserved']
    durable = journal.begin(turn_id='turn-' + 'd' * 40, conversation_id='recorded', branch_id='main',
                            input_fingerprint=digest('durable'))
    rejected(lambda: journal.begin_ephemeral(turn_id=durable['turn_id'], off_record=True, **(
        fields | {'conversation_id': 'recorded'})), 'idempotency_conflict')
    assert not journal.get(durable['turn_id'])['ephemeral']
    with MemoryClient('http://testserver', 'outsider-fixture', system.profile.brain_id,
                      transport=httpx.MockTransport(system.transport)) as outsider:
        with pytest.raises(httpx.HTTPStatusError) as denied:
            BrainRuntime(outsider, lambda _: 'unused').journal.begin_ephemeral(
                turn_id='turn-' + 'e' * 40, off_record=True, **(fields | {'conversation_id': 'outsider'}))
        assert denied.value.response.status_code == 404
    assert system.memory.recording_status() == status


@pytest.mark.parametrize('change', ['pause', 'erase'])
def test_policy_or_deletion_change_still_invalidates_an_explicit_temporary_turn(system, change):
    system.memory.observe('old-source', source_event_key='old', conversation_id='chat', branch_id='main')
    sent = []

    def generate(request):
        assert 'old-source' in request.memory_context
        if change == 'pause':
            pause(system)
        else:
            system.memory.forget([], kind='all_authorized_scope', mode='erase_content', expected_scope_generation=1)
        return 'stale-private-reply'

    runtime = BrainRuntime(system.memory, generate, deliver=lambda r: sent.append(r) or DeliveryReceipt('delivered'))
    with pytest.raises(RuntimeBlocked) as blocked:
        runtime.respond('private-input', message_id='one', conversation_id='chat', record=False)
    assert blocked.value.code in ('context_stale', 'generation_uncertain')
    assert not sent and not runtime.temporary.history
    row = runtime.journal.get(blocked.value.turn_id)
    assert row['stage'] == 'failed' and not row['scope_reserved']
    assert 'stale-private-reply' not in stored(system) and 'private-input' not in stored(system)
    with pytest.raises(RuntimeBlocked, match='temporary_recovery_unavailable'):
        runtime.respond('private-input', message_id='one', conversation_id='chat', record=False)


class LegacyEphemeralBegin(api.RuntimeBody):
    """The request model of a service that predates explicit off-record reservations."""
    turn_id: api.RuntimeIdentifier
    conversation_id: api.RuntimeIdentifier
    branch_id: api.RuntimeIdentifier
    expected_recording_revision: Annotated[int, Field(ge=0, lt=2**63)]
    review_policy: api.RuntimeFingerprint | None = None


class LenientLegacyBegin(LegacyEphemeralBegin):
    model_config = ConfigDict(extra='ignore', strict=True)


@pytest.mark.parametrize('legacy', ['rejects_unknown_field', 'ignores_unknown_field', 'route_missing'])
def test_a_service_without_explicit_support_fails_closed_before_any_model_call(system, monkeypatch, legacy):
    if legacy == 'route_missing':
        @contextmanager
        def connect(*args, **kwargs):
            def forward(request):
                if request.url.path.endswith('/runtime/ephemeral-turns'):
                    return httpx.Response(404, json={'detail': 'Not Found'})
                return system.transport(request)

            with MemoryClient('http://testserver', system.profile.api_key, system.profile.brain_id,
                              transport=httpx.MockTransport(forward)) as memory:
                yield memory

        monkeypatch.setattr(agent_session.desktop_connection, 'open_client', connect)
    else:
        monkeypatch.setattr(api, 'EphemeralBegin',
                            LegacyEphemeralBegin if legacy == 'rejects_unknown_field' else LenientLegacyBegin)
    before = durable_rows(system)
    expected = 'context_stale' if legacy == 'ignores_unknown_field' else 'off_record_reservation_rejected'
    with session(system, generate=lambda _: pytest.fail('No model call is allowed')) as agent:
        agent.set_off_record(True)
        with pytest.raises(RuntimeBlocked, match=expected):
            agent.respond('legacy-private-input', message_id='one')
        assert agent.pending is None and not agent.sent
        assert agent.recording_state()['controls']['conversation']['state'] == 'paused'
        with pytest.raises(RuntimeBlocked, match=expected):
            agent._runtime.respond('legacy-private-input', message_id='two', conversation_id='chat', record=False)
    assert durable_rows(system) == before and not durable_begins(system)
    assert_nothing_captured(system, before, 'legacy-private-input')


# --- open_agent: machine-local controls bound at the session boundary ---------------------------------------


def test_device_capture_pause_makes_direct_chat_temporary_without_changing_the_server(system):
    prompts = []
    server = system.memory.recording_status()
    before = durable_rows(system)
    local_recording.change(system.profile.directory, paused=True, hours=1)
    control = (system.profile.directory / 'plugin' / 'paused.json').read_bytes()
    with session(system, generate=lambda r: prompts.append(r) or 'device-answer-sentinel') as agent:
        state = agent.recording_state()
        assert state['recording'] == 'paused'
        assert state['controls']['server'] == {'scope': 'brain', 'state': 'on', 'revision': server['revision']}
        assert state['controls']['device']['state'] == 'paused' and state['controls']['conversation']['state'] == 'on'
        result = agent.respond('device-input-sentinel', message_id='one')
        assert result.ephemeral and result.stage == 'completed' and len(agent.sent) == 1
        (cause,) = result.temporary_causes
        assert (cause.reason, cause.scope) == ('local_pause', 'installation')
        assert time.time() + 3500 < cause.until < time.time() + 3700
        assert agent.pending is None
    with session(system, conversation='another-chat') as other:
        assert other.respond('another-device-sentinel', message_id='one').temporary_causes[0].reason == 'local_pause'
    assert system.memory.recording_status() == server
    assert (system.profile.directory / 'plugin' / 'paused.json').read_bytes() == control
    assert begin_bodies(system)[-1]['off_record'] is True
    assert_nothing_captured(system, before, 'device-input-sentinel', 'device-answer-sentinel', 'another-device-sentinel')

    local_recording.change(system.profile.directory, paused=False)
    with session(system, generate=lambda r: prompts.append(r) or 'recorded-reply') as agent:
        assert agent.recording_state()['recording'] == 'on'
        result = agent.respond('recordable-after-device-resume', message_id='two')
        assert not result.ephemeral and result.temporary_causes == ()
    assert 'device-input-sentinel' not in json.dumps(prompts[-1].messages)
    assert 'recordable-after-device-resume' in stored(system) and 'device-input-sentinel' not in stored(system)


def test_reading_local_controls_creates_no_host_state(system):
    with session(system) as agent:
        assert agent.recording_state()['recording'] == 'on'
        assert not agent.respond('recorded', message_id='one').ephemeral
    assert not (system.profile.directory / 'plugin').exists()
    assert not list(system.profile.directory.rglob('recording.json'))


def test_off_record_choice_is_isolated_by_conversation_and_branch_and_survives_restart(system):
    before = durable_rows(system)
    with session(system, 'chat-a') as a:
        state = a.set_off_record(True)
        assert state['recording'] == 'paused' and state['controls']['conversation'] == {
            'scope': 'conversation_branch', 'state': 'paused'}
        assert state['controls']['server']['state'] == state['controls']['device']['state'] == 'on'
        assert a.respond('a-off-record-sentinel', message_id='one').temporary_causes == OFF_RECORD
    assert_nothing_captured(system, before, 'a-off-record-sentinel')
    (choice,) = system.profile.directory.rglob('recording.json')
    saved = json.loads(choice.read_text())
    assert set(saved) == {'version', 'identity', 'recording'} and saved['recording'] == 'off'
    assert saved['identity'] == {
        'installation_id': system.profile.installation_id, 'brain_id': system.profile.brain_id,
        'tenant_id': system.profile.tenant_id, 'principal_id': system.profile.principal_id,
        'conversation_id': 'chat-a', 'branch_id': 'main'}

    with session(system, 'chat-b') as b:
        assert b.recording_state()['recording'] == 'on'
        assert not b.respond('b-recorded', message_id='one').ephemeral
    with session(system, 'chat-a', branch='alternative') as branch:
        assert branch.recording_state()['recording'] == 'on'
        assert not branch.respond('a-other-branch-recorded', message_id='one').ephemeral
    with session(system, 'chat-a') as restarted:
        assert restarted.recording_state()['controls']['conversation']['state'] == 'paused'
        assert not restarted._runtime.temporary.history
        assert restarted.respond('a-still-off-sentinel', message_id='two').temporary_causes == OFF_RECORD
    text = stored(system)
    assert 'b-recorded' in text and 'a-other-branch-recorded' in text
    assert 'a-off-record-sentinel' not in text and 'a-still-off-sentinel' not in text
    assert system.memory.recording_status() == {'paused': False, 'revision': 0}


@pytest.mark.parametrize('field', ['installation_id', 'brain_id', 'tenant_id', 'principal_id',
                                   'conversation_id', 'branch_id'])
def test_a_choice_bound_to_another_identity_is_unknown_never_off_the_record(system, field):
    with session(system) as agent:
        agent.set_off_record(True)
        path = agent._recording_path
    forged = json.loads(path.read_text())
    forged['identity'][field] = 'someone-else'
    path.write_text(json.dumps(forged))
    with session(system) as agent:
        state = agent.recording_state()
        assert state['controls']['conversation'] == {
            'scope': 'conversation_branch', 'state': 'unknown', 'reason': 'local_state_unreadable'}
        assert state['recording'] == 'unknown'
        result = agent.respond('conservative-sentinel', message_id='one')
        assert result.temporary_causes == (TemporaryCause('local_state_unreadable', 'conversation_branch'),)
    assert 'conservative-sentinel' not in stored(system)


def test_another_brain_of_the_same_installation_keeps_its_own_choice(system, monkeypatch):
    with session(system) as agent:
        agent.set_off_record(True)
    original = system.profile
    other = replace(original, brain_id=system.memory.create_brain('Second brain')['id'])

    @contextmanager
    def connect(*args, **kwargs):
        with MemoryClient('http://testserver', original.api_key, other.brain_id,
                          transport=httpx.MockTransport(system.transport)) as memory:
            yield memory

    _save(other)
    with monkeypatch.context() as patch:
        patch.setattr(agent_session.desktop_connection, 'open_client', connect)
        with open_agent(other.directory, conversation_id='chat', generate=lambda _: 'reply',
                        generator_fingerprint='fixture', start_service=False) as agent:
            assert agent.recording_state()['recording'] == 'on'
            assert not agent.respond('second-brain-recorded', message_id='one').ephemeral
    _save(original)
    with session(system) as agent:
        assert agent.respond('first-brain-private', message_id='one').temporary_causes == OFF_RECORD
    assert len(list(system.profile.directory.rglob('recording.json'))) == 1


@pytest.mark.parametrize('opening', [
    'Off the record: opening-sentinel is what I think.',
    "Don't remember this: opening-sentinel is the surprise.",
    'Pause recording. opening-sentinel follows.',
    '请不要记录这一段：opening-sentinel 是我的想法。',
    '别记录这条消息。opening-sentinel',
])
def test_a_direct_opening_control_is_honoured_before_capture_and_never_stored(system, opening):
    before = durable_rows(system)
    with session(system) as agent:
        result = agent.respond(opening, message_id='one')
        assert result.ephemeral and result.temporary_causes == OFF_RECORD and result.text == 'synthetic-reply'
        assert agent.recording_state()['controls']['conversation']['state'] == 'paused'
        follow = agent.respond('follow-up-sentinel without a command', message_id='two')
        assert follow.temporary_causes == OFF_RECORD
    assert_nothing_captured(system, before, 'opening-sentinel', 'follow-up-sentinel', opening)
    assert system.memory.recording_status() == {'paused': False, 'revision': 0}
    with session(system) as agent:
        assert agent.set_off_record(False)['recording'] == 'on'
        assert not agent.respond('recorded again', message_id='three').ephemeral
    assert 'recorded again' in stored(system) and 'opening-sentinel' not in stored(system)


@pytest.mark.parametrize('text', [
    'She told the reporter "off the record" and then kept talking.',
    'The manual says: "Don\'t remember this" is a supported command.',
    'I heard him say off the record that the launch slipped.',
    'What does "pause recording" do in this app?',
    '他说“请不要记录这一段”，然后就离开了。',
    '手册里写着：“不要记录”是一个指令。',
    'Please keep what I told you yesterday off the record in your summary.',
])
def test_quoted_or_reported_privacy_words_do_not_change_recording(system, text):
    with session(system) as agent:
        result = agent.respond(text, message_id='one')
        assert not result.ephemeral and result.temporary_causes == ()
        assert agent.recording_state()['recording'] == 'on'
    assert not list(system.profile.directory.rglob('recording.json'))
    assert text in json.loads(stored(system))['memory_events'][0]['value']['document']['observed']['content']['text']


def test_unreadable_device_control_is_unknown_and_handled_as_temporary(system):
    before = durable_rows(system)
    control = system.profile.directory / 'plugin' / 'paused.json'
    control.parent.mkdir(mode=0o700)
    for index, damaged in enumerate((b'{not json', b'[]', b'{"until": "soon"}', b'{"until": NaN}')):
        control.write_bytes(damaged)
        with session(system, conversation=f'chat-{index}') as agent:
            state = agent.recording_state()
            assert state['recording'] == 'unknown' and state['new_message'] == 'temporary'
            assert state['controls']['device'] == {
                'scope': 'installation', 'state': 'unknown', 'reason': 'local_state_unreadable'}
            report = '\n'.join(desktop_chat._recording_report(state))
            assert 'only after the memory service confirms a temporary reservation' in report
            assert 'whole brain (server): on.' in report and '(installation): unknown' in report
            assert 'No message can be answered' not in report and 'paused' not in report
            result = agent.respond('unknown-device-sentinel', message_id='one')
            assert result.temporary_causes == (TemporaryCause('local_state_unreadable', 'installation'),)
            assert agent.set_off_record(True)['recording'] == 'paused'
        assert control.read_bytes() == damaged
    assert_nothing_captured(system, before, 'unknown-device-sentinel')


def test_an_expired_device_pause_follows_host_expiry_and_a_current_server_read(system):
    control = system.profile.directory / 'plugin' / 'paused.json'
    control.parent.mkdir(mode=0o700)
    expired = json.dumps({'since': time.time() - 7200, 'until': time.time() - 5, 'revision': 'f' * 32}).encode()
    control.write_bytes(expired)
    with session(system) as agent:
        assert agent.recording_state()['controls']['device'] == {'scope': 'installation', 'state': 'on'}
        assert not agent.respond('recorded-after-expiry', message_id='one').ephemeral
        # Direct chat only reads the control; cleanup stays with the host paths that hold the state lock.
        assert control.read_bytes() == expired
        pause(system)
        result = agent.respond('server-paused-after-expiry', message_id='two')
        assert result.temporary_causes == (TemporaryCause('server_paused', 'brain'),)
    assert 'recorded-after-expiry' in stored(system) and 'server-paused-after-expiry' not in stored(system)


def test_a_host_conversation_pause_does_not_cover_an_unrelated_direct_conversation(system, monkeypatch):
    """A pause a host conversation asked for lists the host conversations active when it was set. A direct
    conversation is not in the list: the pause does not apply to it, and it neither inherits nor ends that pause."""
    directory = system.profile.directory
    monkeypatch.setattr(host, 'start_in_background', lambda *args: None)
    monkeypatch.setattr(host, 'ready_client', lambda directory, user_id=None: host.use_brain(MemoryClient(
        'http://testserver', system.profile.api_key, system.profile.brain_id,
        transport=httpx.MockTransport(system.transport)), user_id))

    def host_turn(turn, prompt):
        receipt = {}
        host.prompt_context(directory, 'a-host-session', prompt, turn_id=turn)
        records = host.finish_turn(directory, 'a-host-session', 'host-reply-sentinel-' + turn, turn_id=turn, receipt=receipt)
        return records, [(item['state'], item['scope']) for item in receipt['messages']]

    assert host_turn('t1', 'Off the record: host-private-sentinel') == ([], [('excluded', 'conversation')] * 2)
    control = host._pause_file(directory).read_bytes()
    assert json.loads(control)['conversations'] == [host._session_marker(directory, 'a-host-session').stem]
    device = local_recording.local_status(directory)
    assert device['paused'] and device['scope'] == 'conversations'

    with session(system, 'unrelated-direct') as agent:
        state = agent.recording_state()
        assert state['recording'] == 'on' and state['new_message'] == 'record'
        assert state['controls']['device'] == {'scope': 'installation', 'state': 'on', 'host_conversations': 'paused'}
        report = '\n'.join(desktop_chat._recording_report(state))
        assert 'Recording is on for new messages' in report
        assert 'does not apply to this direct conversation' in report and 'captured' not in report
        assert 'pausing the server switch also stops recorded turns in progress' in report
        result = agent.respond('direct-recorded-sentinel', message_id='one')
        assert not result.ephemeral and result.temporary_causes == ()
        # The direct conversation's own choice still works beside the host's pause, and only for itself.
        agent.set_off_record(True)
        assert agent.respond('direct-private-sentinel', message_id='two').temporary_causes == OFF_RECORD
    assert host._pause_file(directory).read_bytes() == control

    assert host_turn('t2', 'host-follow-up-sentinel') == ([], [('excluded', 'conversation')] * 2)
    assert host._pause_file(directory).read_bytes() == control
    text = stored(system)
    assert 'direct-recorded-sentinel' in text
    for excluded in ('host-private-sentinel', 'host-follow-up-sentinel', 'host-reply-sentinel', 'direct-private-sentinel'):
        assert excluded not in text
    assert system.memory.recording_status() == {'paused': False, 'revision': 0}


def test_a_host_conversation_pause_beside_a_server_pause_never_reads_as_direct_chat_being_recorded(system):
    host.pause(system.profile.directory, conversation=True, session='a-host-session')
    control = host._pause_file(system.profile.directory).read_bytes()
    server = pause(system)
    with session(system, 'unrelated-direct') as agent:
        state = agent.recording_state()
        assert state['recording'] == 'paused' and state['new_message'] == 'temporary'
        assert state['controls']['server'] == {'scope': 'brain', 'state': 'paused', 'revision': server['revision']}
        assert state['controls']['device'] == {'scope': 'installation', 'state': 'on', 'host_conversations': 'paused'}
        lines = desktop_chat._recording_report(state)
        assert 'are handled as temporary' in lines[0] and 'whole brain (server): paused.' in lines[1]
        assert '(installation): on; a separate local pause covers the host conversations that were active' in lines[2]
        assert 'does not apply to this direct conversation' in lines[2]
        report = '\n'.join(lines)
        assert 'captured' not in report and 'Recording is on' not in report and 'recorded.' not in report
        result = agent.respond('direct-while-both-paused', message_id='one')
        assert result.temporary_causes == (TemporaryCause('server_paused', 'brain'),)
    assert system.memory.recording_status() == server
    assert host._pause_file(system.profile.directory).read_bytes() == control
    assert 'direct-while-both-paused' not in stored(system)


@pytest.mark.parametrize('hours', [1, None])
def test_an_installation_pause_set_by_a_host_still_covers_every_direct_conversation(system, hours):
    host.pause(system.profile.directory, hours)
    for conversation in ('first-direct', 'second-direct'):
        with session(system, conversation) as agent:
            device = agent.recording_state()['controls']['device']
            assert device['state'] == 'paused' and 'host_conversations' not in device
            assert (device['until'] is None) is (hours is None) and len(device['revision']) == 64
            (cause,) = agent.respond('installation-paused-sentinel', message_id='one').temporary_causes
            assert (cause.reason, cause.scope) == ('local_pause', 'installation')
    assert local_recording.local_status(system.profile.directory)['scope'] == 'installation'
    assert 'installation-paused-sentinel' not in stored(system)


@contextmanager
def interruptible(system, monkeypatch):
    """A connection whose service can be made silent, to tell an unreachable service from a policy change."""
    offline = []

    @contextmanager
    def connect(*args, **kwargs):
        def forward(request):
            if offline:
                raise httpx.ConnectError('synthetic outage', request=request)
            return system.transport(request)

        with MemoryClient('http://testserver', system.profile.api_key, system.profile.brain_id,
                          transport=httpx.MockTransport(forward)) as memory:
            yield memory

    with monkeypatch.context() as patch:
        patch.setattr(agent_session.desktop_connection, 'open_client', connect)
        yield offline


@pytest.mark.parametrize('hours', [1, None])
def test_a_device_pause_lifted_and_set_again_starts_an_empty_temporary_context(system, hours):
    """Reviewer's reproduction: no message is sent while capture is on, so only the pause's identity shows it."""
    prompts = []
    before = durable_rows(system)
    directory = system.profile.directory
    with session(system, generate=lambda r: prompts.append(json.dumps(r.messages)) or 'synthetic-reply') as agent:
        host.pause(directory, hours)
        assert agent.respond('private-before-device-policy-cycle', message_id='before-cycle').ephemeral
        assert agent.respond('same-pause-follow-up', message_id='same-pause').ephemeral
        assert 'private-before-device-policy-cycle' in prompts[-1]
        server = system.memory.recording_status()
        first = agent.recording_state()['controls']['device']['revision']
        host.resume(directory)
        host.pause(directory, hours)
        second = agent.respond('fresh-temporary-segment', message_id='after-cycle')
        assert [cause.reason for cause in second.temporary_causes] == ['local_pause']
        assert agent.recording_state()['controls']['device']['revision'] != first
        assert system.memory.recording_status() == server == {'paused': False, 'revision': 0}
        assert 'private-before-device-policy-cycle' not in prompts[-1] and 'same-pause-follow-up' not in prompts[-1]
        assert agent.respond('second-segment-follow-up', message_id='after-cycle-2').ephemeral
        assert 'fresh-temporary-segment' in prompts[-1] and 'private-before-device-policy-cycle' not in prompts[-1]
    assert_nothing_captured(system, before, 'private-before-device-policy-cycle', 'same-pause-follow-up',
                            'fresh-temporary-segment', 'second-segment-follow-up')


def test_an_expired_local_timer_ends_temporary_context_but_a_silent_service_does_not(system, monkeypatch):
    prompts = []
    control = system.profile.directory / 'plugin' / 'paused.json'
    with interruptible(system, monkeypatch) as offline, session(
            system, generate=lambda r: prompts.append(json.dumps(r.messages)) or 'synthetic-reply') as agent:
        agent.set_off_record(True)
        host.pause(system.profile.directory, 1)

        def reasons(text, message_id):
            return [cause.reason for cause in agent.respond(text, message_id=message_id).temporary_causes]

        assert reasons('secret-before-outage', 'one') == ['local_pause', 'off_record']
        # A silent service confirms nothing about any policy: the turn stops and the context is left alone.
        offline.append(True)
        with pytest.raises(httpx.ConnectError):
            agent.respond('never-answered', message_id='two')
        offline.clear()
        assert reasons('after-outage', 'three') == ['local_pause', 'off_record']
        assert 'secret-before-outage' in prompts[-1] and 'never-answered' not in prompts[-1]
        # The local timer runs out on this machine's own clock: an authoritative change of local policy.
        pause = json.loads(control.read_text())
        control.write_text(json.dumps(pause | {'until': time.time() - 1}))
        assert reasons('after-expiry', 'four') == ['off_record']
        assert 'secret-before-outage' not in prompts[-1] and 'after-outage' not in prompts[-1]
        assert json.loads(control.read_text())['revision'] == pause['revision']
    assert system.memory.recording_status() == {'paused': False, 'revision': 0}
    for secret in ('secret-before-outage', 'never-answered', 'after-outage', 'after-expiry'):
        assert secret not in stored(system)


def test_a_device_pause_during_a_running_recorded_turn_applies_from_the_next_message(system):
    """Local controls decide how a new message is captured. They are not a fence around a recorded turn whose
    model call is already running: only the server switch stops that."""
    def generate(request):
        local_recording.change(system.profile.directory, paused=True)
        return 'reply-generated-during-device-pause'

    with session(system, generate=generate) as agent:
        result = agent.respond('recorded-in-flight-input', message_id='one')
        assert result.stage == 'completed' and not result.ephemeral and result.temporary_causes == ()
        assert [request.text for request in agent.sent] == ['reply-generated-during-device-pause']
        agent._runtime.generate = lambda _: 'temporary-reply'
        (cause,) = agent.respond('private-next-message', message_id='two').temporary_causes
        assert (cause.reason, cause.scope) == ('local_pause', 'installation')
    text = stored(system)
    assert 'recorded-in-flight-input' in text and 'reply-generated-during-device-pause' in text
    assert 'private-next-message' not in text
    assert system.memory.recording_status() == {'paused': False, 'revision': 0}


def test_an_unreachable_service_stops_before_generation_and_is_reported_unknown(system, monkeypatch):
    before = durable_rows(system)
    with interruptible(system, monkeypatch) as offline, session(
            system, generate=lambda _: pytest.fail('No model call is allowed')) as agent:
        offline.append(True)
        state = agent.recording_state()
        assert state['controls']['server'] == {'scope': 'brain', 'state': 'unknown', 'revision': None}
        assert state['recording'] == 'unknown' and state['new_message'] == 'unavailable'
        assert [state['controls'][name]['state'] for name in ('device', 'conversation')] == ['on', 'on']
        report = '\n'.join(desktop_chat._recording_report(state))
        assert 'No message can be answered until it responds' in report
        assert 'Local controls are on. Whether a new message would be recorded is unconfirmed' in report
        assert 'whole brain (server): unknown' in report and '(installation): on.' in report
        assert 'handled as temporary' not in report and 'Recording is on' not in report and 'paused' not in report
        with pytest.raises(httpx.ConnectError):
            agent.respond('offline-sentinel', message_id='one')

        state = agent.set_off_record(True)
        assert state['recording'] == 'paused' and state['new_message'] == 'unavailable'
        assert state['controls']['server']['state'] == 'unknown' and state['controls']['conversation']['state'] == 'paused'
        report = '\n'.join(desktop_chat._recording_report(state))
        assert 'No message can be answered until it responds' in report
        assert "Temporary handling still needs the service's reservation, which is unconfirmed" in report
        assert 'This conversation branch: off the record.' in report and 'whole brain (server): unknown' in report
        assert 'are handled as temporary' not in report
        with pytest.raises(httpx.ConnectError):
            agent.respond('offline-sentinel', message_id='two')
        assert agent.pending is None and not agent.sent
        offline.clear()
        state = agent.recording_state()
        assert state['new_message'] == 'temporary' and state['controls']['server']['state'] == 'on'
        assert 'are handled as temporary' in desktop_chat._recording_report(state)[0]
        agent._runtime.generate = lambda _: 'back online'
        assert agent.respond('offline-sentinel', message_id='three').temporary_causes == OFF_RECORD
    assert_nothing_captured(system, before, 'offline-sentinel')


@pytest.mark.parametrize('control', ['off_record', 'device', 'opening'])
def test_a_pending_recorded_turn_is_neither_converted_nor_replayed_after_a_local_pause(system, control):
    calls = []
    with session(system, generate=lambda r: calls.append(r) or 'pending-draft', deliver=False) as agent:
        first = agent.respond('recorded-before-local-pause', message_id='one')
        assert first.stage == 'generated' and not first.ephemeral
        pending = agent.pending
        text = 'recorded-before-local-pause'
        if control == 'off_record':
            agent.set_off_record(True)
        elif control == 'device':
            local_recording.change(system.profile.directory, paused=True)
        for operation in (lambda: agent.respond(text, message_id='one'), agent.resume):
            if control == 'opening':
                break
            with pytest.raises(SessionError) as error:
                operation()
            assert error.value.code == 'pending_turn_recording_excluded' and error.value.turn_id == first.turn_id
        with pytest.raises(SessionError) as error:
            agent.respond('Off the record: a different private message', message_id='two')
        assert error.value.code == 'pending_turn'
        if control == 'opening':
            # The rejected message changed nothing: its request is honoured only when it can be processed.
            assert agent.recording_state()['recording'] == 'on'
            agent.set_off_record(True)
        row = agent._runtime.journal.get(first.turn_id)
        assert row['stage'] == 'generated' and not row['ephemeral'] and agent.pending == pending and len(calls) == 1
        assert agent.cancel(turn_id=first.turn_id) == {'turn_id': first.turn_id, 'stage': 'failed',
                                                       'failure_code': 'cancelled'}
        assert agent.pending is None
        agent._runtime.generate = lambda _: 'temporary-reply'
        assert agent.respond('private-after-cancel', message_id='three').ephemeral
    text = stored(system)
    assert 'recorded-before-local-pause' in text and 'private-after-cancel' not in text
    assert 'a different private message' not in text


def test_retrying_a_pending_recorded_message_that_opens_with_a_control_is_not_continued(system, monkeypatch):
    """A recorded pending turn with such an opening can only predate this control; its retry must not record more."""
    calls = []
    with session(system, generate=lambda r: calls.append(r) or 'pending-draft', deliver=False) as agent:
        with monkeypatch.context() as patch:
            patch.setattr(agent_session, 'requests_pause', lambda _: False)
            first = agent.respond('Off the record: recorded before the upgrade', message_id='one')
        assert first.stage == 'generated' and not first.ephemeral
        with pytest.raises(SessionError) as error:
            agent.respond('Off the record: recorded before the upgrade', message_id='one')
        assert error.value.code == 'pending_turn_recording_excluded' and error.value.turn_id == first.turn_id
        assert agent.recording_state()['controls']['conversation']['state'] == 'paused' and len(calls) == 1
        assert agent._runtime.journal.get(first.turn_id)['stage'] == 'generated'


def test_lifting_the_local_control_allows_explicit_recovery_of_the_pending_recorded_turn(system):
    calls = []
    with session(system, generate=lambda r: calls.append(r) or 'pending-draft', deliver=False) as agent:
        first = agent.respond('recorded-input', message_id='one')
        agent.set_off_record(True)
        with pytest.raises(SessionError, match='pending_turn_recording_excluded'):
            agent.resume()
        agent.set_off_record(False)
    with session(system, generate=lambda _: pytest.fail('The draft is not regenerated')) as agent:
        result = agent.resume()
        assert result.stage == 'completed' and not result.ephemeral and result.turn_id == first.turn_id
        assert [request.text for request in agent.sent] == ['pending-draft'] and len(calls) == 1


def test_bookkeeping_for_an_already_delivered_reply_may_finish_during_a_local_pause(system, monkeypatch):
    calls = []
    with session(system, generate=lambda r: calls.append(r) or 'delivered-reply') as agent:
        original = agent._runtime.journal.finish
        monkeypatch.setattr(agent._runtime.journal, 'finish', lambda *a, **k: (_ for _ in ()).throw(
            httpx.ConnectError('synthetic lost finish')))
        with pytest.raises(httpx.ConnectError):
            agent.respond('delivered-input', message_id='one')
        monkeypatch.setattr(agent._runtime.journal, 'finish', original)
        assert agent._runtime.journal.get(agent.pending['turn_id'])['stage'] == 'delivered'
        local_recording.change(system.profile.directory, paused=True)
        agent.set_off_record(True)
        result = agent.resume()
        assert result.stage == 'completed' and not result.ephemeral and agent.pending is None
        assert len(calls) == 1 and len(agent.sent) == 1


def test_each_control_resumes_independently_of_the_others(system):
    before = durable_rows(system)
    local_recording.change(system.profile.directory, paused=True, hours=2)
    paused = pause(system)
    with session(system) as agent:
        agent.set_off_record(True)

        def reasons(message_id):
            return [cause.reason for cause in agent.respond('independent-sentinel', message_id=message_id).temporary_causes]

        assert reasons('one') == ['server_paused', 'local_pause', 'off_record']
        assert 'off_record' not in begin_bodies(system)[-1]
        resumed = pause(system, False)
        assert resumed == {'paused': False, 'revision': paused['revision'] + 1}
        state = agent.recording_state()
        assert [state['controls'][name]['state'] for name in ('server', 'device', 'conversation')] == [
            'on', 'paused', 'paused']
        assert reasons('two') == ['local_pause', 'off_record']
        assert begin_bodies(system)[-1]['off_record'] is True

        device = (system.profile.directory / 'plugin' / 'paused.json').read_bytes()
        assert agent.set_off_record(False)['recording'] == 'paused'
        assert (system.profile.directory / 'plugin' / 'paused.json').read_bytes() == device
        assert reasons('three') == ['local_pause']
        agent.set_off_record(True)
        local_recording.change(system.profile.directory, paused=False)
        assert agent.recording_state()['controls']['conversation']['state'] == 'paused'
        assert reasons('four') == ['off_record']
        assert system.memory.recording_status() == resumed
    # Inspect every file and table only after the session has closed: while it is open it holds its lock file
    # exclusively, which Windows does not let another handle read.
    assert_nothing_captured(system, before, 'independent-sentinel', changed={'memory_brains'})

    with session(system) as agent:
        assert agent.recording_state()['controls']['conversation']['state'] == 'paused'
        assert agent.set_off_record(False)['recording'] == 'on'
        assert not agent.respond('recorded-at-last', message_id='five').ephemeral
        pause(system)
        assert reasons('six') == ['server_paused']
    assert system.memory.recording_status()['revision'] == resumed['revision'] + 1
    assert 'recorded-at-last' in stored(system) and 'independent-sentinel' not in stored(system)


def test_temporary_history_stays_bounded_isolated_and_is_never_backfilled(system):
    system.memory.observe('earlier-recorded-source', source_event_key='old', conversation_id='chat', branch_id='main')
    prompts = []

    def generate(request):
        prompts.append(json.dumps(request.messages, ensure_ascii=False))
        return 'reply-' + str(len(prompts))

    policy = RuntimePolicy(recent_context_events=2, memory_context_tokens=4000)
    with session(system, generate=generate, policy=policy) as agent:
        agent.set_off_record(True)
        for index in range(4):
            agent.respond(f'temporary-turn-{index}', message_id=f't{index}')
        assert 'earlier-recorded-source' in prompts[0]
        assert 'temporary-turn-2' in prompts[3] and 'temporary-turn-0' not in prompts[3]
        (history,) = [items for _, items in agent._runtime.temporary.history.values()]
        assert len(history) == 2

        with session(system, 'other-chat', generate=generate) as other:
            other.respond('other conversation', message_id='o1')
        assert 'temporary-turn' not in prompts[-1]

        agent.set_off_record(False)
        assert not agent._runtime.temporary.history
        agent.respond('recorded-turn', message_id='r1')
        assert 'temporary-turn' not in prompts[-1]

        agent.set_off_record(True)
        agent.respond('second-temporary-segment', message_id='t9')
        assert 'temporary-turn' not in prompts[-1] and 'recorded-turn' in prompts[-1]
    with session(system, generate=generate, policy=policy) as restarted:
        restarted.respond('after-restart', message_id='t10')
        assert 'second-temporary-segment' not in prompts[-1] and 'temporary-turn' not in prompts[-1]
    text = stored(system)
    assert 'recorded-turn' in text and 'temporary-turn' not in text and 'second-temporary-segment' not in text


def test_off_record_turns_deduplicate_without_regeneration_and_do_not_recover_after_failure(system):
    calls = []
    with session(system, generate=lambda r: calls.append(r) or 'private-reply') as agent:
        agent.set_off_record(True)
        first = agent.respond('dedup-private-input', message_id='one')
        replay = agent.respond('dedup-private-input', message_id='one')
        assert replay.replayed and replay.text is None and replay.ephemeral and replay.temporary_causes == ()
        assert len(calls) == 1 and len(agent.sent) == 1

        def interrupted(request):
            raise OSError('synthetic interruption')

        agent._runtime.generate = interrupted
        with pytest.raises(OSError):
            agent.respond('interrupted-private-input', message_id='two')
        with pytest.raises(RuntimeBlocked, match='temporary_recovery_unavailable'):
            agent.respond('interrupted-private-input', message_id='two')
        with pytest.raises(SessionError, match='no_pending_turn'):
            agent.resume()
        failed = agent._runtime.journal.get('turn-' + digest([system.profile.brain_id, 'chat', 'main', 'two'])[:40])
        assert failed['stage'] == 'failed' and failed['failure_code'] == 'generation_uncertain'
    with session(system, generate=lambda _: pytest.fail('A temporary reply is never regenerated')) as restarted:
        replay = restarted.respond('dedup-private-input', message_id='one')
        assert replay.replayed and replay.text is None
        restarted.set_off_record(False)
        with pytest.raises(SessionError) as conflict:
            restarted.respond('dedup-private-input', message_id='one')
        assert conflict.value.code == 'message_identity_conflict' and conflict.value.turn_id == first.turn_id
        assert restarted.pending is None
    text = stored(system)
    assert 'dedup-private-input' not in text and 'interrupted-private-input' not in text and 'private-reply' not in text


def test_deleting_memory_during_off_record_generation_withholds_the_reply(system):
    system.memory.observe('old-source', source_event_key='old', conversation_id='chat', branch_id='main')

    def generate(request):
        system.memory.forget([], kind='all_authorized_scope', mode='erase_content', expected_scope_generation=1)
        return 'stale-private-reply'

    with session(system, generate=generate) as agent:
        agent.set_off_record(True)
        with pytest.raises(RuntimeBlocked, match='context_stale'):
            agent.respond('private-during-erasure', message_id='one')
        assert not agent.sent and not agent._runtime.temporary.history and agent.pending is None
        assert agent.recording_state()['controls']['conversation']['state'] == 'paused'
    assert 'stale-private-reply' not in stored(system) and 'private-during-erasure' not in stored(system)
