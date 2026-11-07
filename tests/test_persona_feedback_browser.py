import pytest
from test_memory_page_browser import CARD, open_view, sign_in
from test_memory_page_browser import account as account
from test_memory_page_browser import browser as browser
from test_memory_page_browser import page as page
from test_memory_page_browser import server as server

pytestmark = pytest.mark.integration


def edges(graph):
    return {(edge['source'], edge['target'], edge['type']) for edge in graph['edges']}


def test_fullscreen_persona_graph_drops_evidence_revised_after_acceptance(server, page, account):
    key, client = account
    client.set_persona(CARD, made_by='user')
    sources = []
    for index, text in enumerate(("You're too formal.", 'Be more casual please.', 'Can you be more casual?')):
        result = client.observe(text, conversation_id='revision-chat', branch_id='main',
                                source_event_key=f'feedback-{index}', producer_ref='revision-browser')
        assert result['outcome'] == 'completed'
        sources.extend(result['result']['accepted_event_ids'])
    proposal = client.persona_proposals()['proposals'][0]
    client.accept_persona_proposal(proposal['id'])
    sign_in(page, server.base_url, key)
    open_view(page, 'brain')
    page.select_option('#brain-layer', 'companion')
    page.wait_for_function("() => document.querySelectorAll('#brain-canvas .edge-based_on_feedback').length === 3")
    page.locator('#brain-showcase').click()
    page.wait_for_function('() => window.memoryHologram?.snapshot().ready')
    before = page.evaluate('window.memoryHologram.snapshot()')
    expected = client.companion_map()
    assert set(before['nodeIds']) == {node['id'] for node in expected['nodes']}
    assert edges(before) == edges(expected)

    revised = client.observe('Your replies are too formal for the new topic today.', conversation_id='revision-chat',
                             branch_id='main', source_event_key='feedback-0', source_revision=2,
                             producer_ref='revision-browser')
    assert revised['result']['accepted_event_ids'] == sources[:1]
    page.evaluate('async () => { await window.loadBrain(); }')
    assert not page.evaluate('window.memoryHologram.snapshot().ready')
    page.wait_for_function("() => document.querySelectorAll('#brain-canvas .edge-based_on_feedback').length === 2")
    page.locator('#brain-showcase').click()
    page.wait_for_function("() => window.memoryHologram.snapshot().ready && "
                           "window.memoryHologram.snapshot().edges.filter(e => e.type === 'based_on_feedback').length === 2")
    after = page.evaluate('window.memoryHologram.snapshot()')
    expected = client.companion_map()
    assert set(after['nodeIds']) == {node['id'] for node in expected['nodes']}
    assert edges(after) == edges(expected)
    assert not any(edge['target'] == 'msg:' + sources[0] for edge in after['edges']
                   if edge['type'] in {'based_on_feedback', 'proposed_from_feedback'})
    assert client.persona()['card']['voice']['register'] == 'casual'
    page.locator('#show-close').click()
