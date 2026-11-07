from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_c5_harness import harness, practice


def proposal(ident, kind, label):
    return {'id': ident, 'kind': kind, 'label': label, 'status': 'open',
            'proposed_card': {**deepcopy(practice.ACCEPTED_CARD), 'name': 'Casual companion'},
            'sources': [{'text': 'Please keep our casual conversations playful.'}]}


class Proposals:
    def __init__(self, entries):
        self.entries = entries
        self.decisions = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def persona_proposals(self):
        return {'proposals': self.entries}

    def accept_persona_proposal(self, ident):
        self.decisions.append(('accept', ident))
        return {'persona': {'version': 2}}

    def reject_persona_proposal(self, ident):
        self.decisions.append(('reject', ident))
        return {'version': None}

    def persona(self):
        return {'version': 2, 'card': practice.ACCEPTED_CARD}


def act(client, decision, match):
    action = {'do': decision + '_persona_proposal', 'match': match, 'card': practice.ACCEPTED_CARD}
    return harness.apply_page_action(SimpleNamespace(client=lambda: client), action, {})


@pytest.mark.parametrize('decision', ['accept', 'reject'])
def test_selector_does_not_match_inherited_card_or_feedback(decision):
    client = Proposals([proposal('p-new', 'more_playful', 'more playful'),
                        proposal('p-target', 'less_formal', 'more casual')])
    result = act(client, decision, 'casual')
    assert result.get('proposal') == 'p-target'
    assert client.decisions == [(decision, 'p-target')]


@pytest.mark.parametrize('decision', ['accept', 'reject'])
def test_ambiguous_proposal_selection_does_not_mutate_persona(decision):
    client = Proposals([proposal('p1', 'more_playful', 'more playful'),
                        proposal('p2', 'less_formal', 'more casual')])
    result = act(client, decision, 'more')
    assert result.get('failed') and result.get('ambiguous') is True
    assert harness.failure_code(result) == 'ambiguous_proposal'
    assert client.decisions == []


@pytest.mark.parametrize('decision', ['accept', 'reject'])
@pytest.mark.parametrize('match', ['less_formal', 'p-target'])
def test_exact_proposal_identity_takes_precedence_over_text(decision, match):
    misleading = proposal('p-new', 'more_playful', 'more playful')
    misleading['sources'] = [{'text': 'Discuss less_formal and p-target.'}]
    client = Proposals([misleading, proposal('p-target', 'less_formal', 'more casual')])
    result = act(client, decision, match)
    assert result.get('proposal') == 'p-target'
    assert client.decisions == [(decision, 'p-target')]


def test_nonidentifying_text_does_not_select_a_proposal():
    client = Proposals([proposal('p1', 'more_playful', 'more playful')])
    result = act(client, 'reject', 'conversations')
    assert result.get('failed')
    assert client.decisions == []


def test_nonopen_proposal_is_never_selected_by_exact_identity():
    item = proposal('p1', 'less_formal', 'more casual')
    item['status'] = 'rejected'
    client = Proposals([item])
    result = act(client, 'accept', 'p1')
    assert result.get('failed') and client.decisions == []


def test_blank_selector_does_not_select_a_proposal():
    client = Proposals([proposal('p1', 'less_formal', 'more casual')])
    result = act(client, 'accept', '  ')
    assert result.get('failed') and client.decisions == []
