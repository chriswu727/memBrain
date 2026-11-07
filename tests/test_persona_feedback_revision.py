import pytest
from test_persona_decisions import brain as brain
from test_persona_decisions import revise
from test_persona_growth import CARD, _restored, listing, said

from membrain.companion_map import companion_map
from membrain.persona import persona_versions, set_persona
from membrain.persona_growth import accept_proposal, reject_proposal

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('restored', [False, True])
@pytest.mark.parametrize('replacement', ['Your replies are too formal now, with entirely different wording.',
                                        'Your replies are too long; this is a new complaint.'])
def test_accepted_personality_does_not_claim_later_message_revisions_as_its_evidence(brain, restored, replacement):
    set_persona(*brain, CARD, made_by='user')
    sources = [said(brain, text) for text in (
        "you're too formal", 'be more casual please', 'Can you be more casual?')]
    proposal = listing(brain)['proposals'][0]
    accepted = accept_proposal(*brain, proposal['id'])['persona']
    before = companion_map(*brain)
    assert {edge['target'] for edge in before['edges'] if edge['type'] == 'based_on_feedback'} == {
        'msg:' + source for source in sources}
    revise(brain, sources[0], replacement)
    if restored:
        brain = (*brain[:2], _restored(brain, 'Restored revised feedback'))

    history = persona_versions(*brain)['versions']
    version = next(item for item in history if item['version'] == accepted['version'])
    assert version['card']['voice']['register'] == 'casual'
    assert {item['event_id'] for item in version['feedback_messages']} == set(sources[1:])
    closed = next(item for item in listing(brain)['proposals'] if item['id'] == proposal['id'])
    assert closed['status'] == 'accepted'
    assert {item['event_id'] for item in closed['sources']} == set(sources[1:])
    graph = companion_map(*brain)
    assert {edge['target'] for edge in graph['edges'] if edge['type'] == 'based_on_feedback'} == {
        'msg:' + source for source in sources[1:]}
    assert not any(edge['type'] == 'proposed_from_feedback' and edge['target'] == 'msg:' + sources[0]
                   for edge in graph['edges'])


@pytest.mark.parametrize('decision', ['accepted', 'rejected'])
@pytest.mark.parametrize('restored', [False, True])
def test_decided_proposal_graph_excludes_revised_feedback(brain, decision, restored):
    set_persona(*brain, CARD, made_by='user')
    sources = [said(brain, text) for text in (
        "you're too formal", 'be more casual please', 'Can you be more casual?')]
    proposal = listing(brain)['proposals'][0]
    (accept_proposal if decision == 'accepted' else reject_proposal)(*brain, proposal['id'])
    revise(brain, sources[0], 'Be more casual with the new topic we discussed today.')
    if restored:
        brain = (*brain[:2], _restored(brain, 'Restored decided feedback'))
    graph = companion_map(*brain)
    targets = {edge['target'] for edge in graph['edges']
               if edge['source'] == 'proposal:' + proposal['id'] and edge['type'] == 'proposed_from_feedback'}
    assert targets == {'msg:' + source for source in sources[1:]}
    closed = next(item for item in listing(brain)['proposals'] if item['id'] == proposal['id'])
    assert closed['status'] == decision
    assert {item['event_id'] for item in closed['sources']} == set(sources[1:])


def test_feedback_revised_before_acceptance_remains_valid_evidence(brain):
    set_persona(*brain, CARD, made_by='user')
    sources = [said(brain, text) for text in (
        "you're too formal", 'be more casual please', 'Can you be more casual?')]
    proposal = listing(brain)['proposals'][0]
    changed = 'Your replies are too formal for our daily conversation.'
    revise(brain, sources[0], changed)
    accept_proposal(*brain, proposal['id'])
    brain = (*brain[:2], _restored(brain, 'Restored accepted revision'))
    version = persona_versions(*brain)['versions'][0]
    quoted = {item['event_id']: item['text'] for item in version['feedback_messages']}
    assert set(quoted) == set(sources) and quoted[sources[0]] == changed
    graph = companion_map(*brain)
    assert {edge['target'] for edge in graph['edges'] if edge['type'] == 'based_on_feedback'} == {
        'msg:' + source for source in sources}
