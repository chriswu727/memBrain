import itertools
import math

import pytest
from playwright.sync_api import expect
from test_memory_hologram_browser import preview as _preview
from test_memory_observatory_browser import _tab
from test_memory_observatory_browser import browser as _browser

browser, preview = _browser, _preview


def payload(count=2):
    ids = ['note:3fe787cc-7424-4b2c-9057-ae226f80f423', 'note:c33c2301-e48c-42bd-9270-327a3f86317c']
    ids.extend(f'note:dense-{index}' for index in range(2, count))
    nodes = [{'id': ident, 'region': 'plans', 'kind': 'plan', 'weight': 1,
              'label': 'Bring the blue folder.' if index == 0 else f'Plan {index}',
              'recorded_at': '2026-11-05T12:00:00Z'} for index, ident in enumerate(ids)]
    nodes[1].update(label='', sensitive=True, masked=True, recorded_at=None)
    return {'contract_version': 'memory-structure-v1', 'demo': True, 'nodes': nodes,
            'edges': [{'source': ids[0], 'target': ids[1], 'type': 'association', 'basis': 'explicit'}],
            'regions': [{'id': 'plans', 'count': count}], 'truncated': False}


@pytest.mark.parametrize('count', [2, 500])
def test_projected_nodes_are_separate_clickable_and_keep_the_same_graph(browser, preview, count):
    data = payload(count)
    preview.set_map(data)
    context, tab = _tab(browser, reduced_motion='reduce')
    page = tab.page
    try:
        page.goto(f'{preview.base_url}/memory?demo=brain')
        page.wait_for_function('() => window.observatory.snapshot().nodes.length > 0')
        spatial = page.evaluate('map => window.observatory.layout(map)', data)
        page.locator('#mode-2d').click()
        circles = page.locator('#brain-canvas circle.brain-node')
        expect(circles).to_have_count(count)
        positions = circles.evaluate_all('nodes => nodes.map(n => ({id:n.dataset.id, '
                                         'x:+n.getAttribute("cx"), y:+n.getAttribute("cy"), '
                                         'r:+n.getAttribute("r")}))')
        for left, right in itertools.combinations(positions, 2):
            assert math.hypot(left['x'] - right['x'], left['y'] - right['y']) >= left['r'] + right['r'] + 2
        assert all(12 <= p['x'] <= 788 and 12 <= p['y'] <= 508 for p in positions)
        for index in (1, 0):
            page.locator(f'#brain-canvas [data-id="{data["nodes"][index]["id"]}"]').click()
            detail = page.locator('#brain-detail')
            if index == 1:
                expect(detail).to_contain_text('Sensitive memory')
                expect(detail).not_to_contain_text('Saved:')
            else:
                expect(detail).to_contain_text('Bring the blue folder.')
                expect(detail).to_contain_text('Saved:')
        expected_edges = [(e['source'], e['target']) for e in data['edges']]
        assert page.locator('.brain-edge').evaluate_all(
            'edges => edges.map(e => [e.dataset.source, e.dataset.target])') == [list(e) for e in expected_edges]
        shuffled = {**data, 'nodes': list(reversed(data['nodes']))}
        assert page.evaluate('map => layout(map)', shuffled) == page.evaluate('map => layout(map)', data)
        assert page.evaluate('map => window.observatory.layout(map)', data) == spatial
        assert tab.errors == []
    finally:
        context.close()
