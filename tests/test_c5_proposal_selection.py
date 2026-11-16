"""A page decision on a persona suggestion takes the open suggestion by its origin and its place in the page's own
order (open first, newest first), never by any text: not its label, not its quoted feedback, not the card it
proposes. Two open suggestions are never ambiguous; a missing one is not applicable (the host did not do its part),
never a failure that stops the run."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_c5_harness import harness

CARD = {"name": "Casual companion", "voice": {"register": "casual"}}


def proposal(ident, kind, label, status="open"):
    return {'id': ident, 'kind': kind, 'label': label, 'status': status, 'proposed_card': deepcopy(CARD),
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


def act(client, decision, **selector):
    return harness.apply_page_action(SimpleNamespace(client=lambda: client),
                                     {'do': decision + '_proposal', **selector}, {})


@pytest.mark.parametrize('decision', ['accept', 'reject'])
def test_the_selector_reads_no_text_of_the_suggestion(decision):
    misleading = proposal('p-new', 'more_playful', 'more casual')
    misleading['sources'] = [{'text': 'Discuss less_formal and p-target.'}]
    client = Proposals([misleading, proposal('p-target', 'less_formal', 'more playful')])
    result = act(client, decision, origin='feedback', position=2)
    assert result.get('proposal') == 'p-target' and client.decisions == [(decision, 'p-target')]
    assert 'match' not in harness.ACTION_ARGUMENTS[decision + '_proposal'][1]


@pytest.mark.parametrize('decision', ['accept', 'reject'])
def test_two_open_suggestions_are_not_ambiguous_the_page_order_decides(decision):
    client = Proposals([proposal('p1', 'more_playful', 'more playful'), proposal('p2', 'less_formal', 'more casual')])
    result = act(client, decision)
    assert 'failed' not in result and result['proposal'] == 'p1' and client.decisions == [(decision, 'p1')]


@pytest.mark.parametrize('decision', ['accept', 'reject'])
def test_a_suggestion_that_is_not_open_is_never_decided(decision):
    client = Proposals([proposal('p1', 'less_formal', 'more casual', status='rejected'),
                        proposal('p2', 'host', 'suggested by the agent', status='withdrawn')])
    result = act(client, decision)
    assert result == {'not_applicable': 'no_open_proposal', 'open': 0} and client.decisions == []
    assert harness.page_status(result) == ('not_applicable', 'no_open_proposal')


def test_the_host_and_feedback_origins_are_kept_apart():
    entries = [proposal('p-host', 'host', 'suggested by the agent'), proposal('p-feedback', 'less_formal', 'casual')]
    client = Proposals(entries)
    assert act(client, 'accept', origin='host')['proposal'] == 'p-host'
    client = Proposals(entries)
    assert act(client, 'accept', origin='feedback')['proposal'] == 'p-feedback'
    client = Proposals(entries[:1])
    assert act(client, 'accept', origin='feedback')['not_applicable'] == 'no_open_proposal'
    assert client.decisions == []
