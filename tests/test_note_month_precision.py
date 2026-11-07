import datetime

import pytest
from test_mood import write
from test_persona_decisions import brain as brain
from test_persona_growth import _restored
from test_typed_notes import item

from membrain import notes
from membrain.relationship import acknowledge, relationship


@pytest.mark.parametrize('field', ['due', 'occurs_at'])
@pytest.mark.parametrize('day', [1, 15, 31])
def test_current_month_plan_never_invents_a_day_or_claims_the_month_has_passed(field, day):
    text = notes.format_note('Send the itinerary.', kind='plan', **{field: '2027-03'})
    rendered = notes.render_coming_up({'items': [item('plan', text)]}, today=datetime.date(2027, 3, day))
    assert rendered is not None and 'Send the itinerary.' in rendered
    assert '2027-03 (day unspecified)' in rendered
    plan_line = next(line for line in rendered.splitlines() if '(id: plan)' in line)
    assert '2027-03-01' not in plan_line and 'has passed' not in plan_line
    assert '(today)' not in rendered and '(tomorrow)' not in rendered


@pytest.mark.parametrize('today,expected', [('2027-02-26', True), ('2027-02-01', False), ('2027-04-01', True)])
def test_month_plan_uses_its_whole_interval_for_the_coming_up_window(today, expected):
    text = notes.format_note('Send the itinerary.', kind='plan', due='2027-03')
    rendered = notes.render_coming_up({'items': [item('plan', text)]}, today=datetime.date.fromisoformat(today))
    assert bool(rendered) is expected
    if rendered:
        assert '2027-03-01' not in rendered
        assert ('2027-03 has passed' in rendered) is (today == '2027-04-01')


def test_month_cancellation_keeps_priority_until_the_whole_month_has_passed(monkeypatch):
    fields = {'kind': 'plan', 'status': 'cancelled', 'occurs_at': '2028-02'}
    entry = item('cancelled', notes.format_note('Trip cancelled.', **fields))
    monkeypatch.setattr(notes, '_clock_today', lambda: datetime.date(2028, 2, 29))
    assert notes._priority((entry, fields, 'Trip cancelled.')) == 3
    monkeypatch.setattr(notes, '_clock_today', lambda: datetime.date(2028, 3, 1))
    assert notes._priority((entry, fields, 'Trip cancelled.')) == 4


@pytest.mark.integration
@pytest.mark.parametrize('restored', [False, True])
@pytest.mark.parametrize('field', ['due', 'occurs_at'])
def test_month_commitment_cannot_be_missed_or_acknowledged_until_month_end(brain, restored, field):
    saved = write(brain, 'Send the itinerary.', kind='agent_commitment', status='intended', **{field: '2028-02'})
    if restored:
        brain = (*brain[:2], _restored(brain, 'Restored month commitment'))
    for today in (datetime.date(2028, 2, 1), datetime.date(2028, 2, 29)):
        state = relationship(*brain, today=today)
        assert state['commitments']['missed'] == []
        assert [entry['note_id'] for entry in state['commitments']['open']] == [saved['note_id']]
        assert state['once'] == []
        acknowledge(*brain, [saved['note_id']], today=today)
    state = relationship(*brain, today=datetime.date(2028, 3, 1))
    assert state['once'] == [saved['note_id']]
    assert not state['commitments']['missed'][0]['acknowledged']
    assert state['commitments']['missed'][0][field] == '2028-02'
    shown = acknowledge(*brain, state['once'], today=datetime.date(2028, 3, 1))
    assert shown['once'] == [] and shown['commitments']['missed'][0]['acknowledged']
