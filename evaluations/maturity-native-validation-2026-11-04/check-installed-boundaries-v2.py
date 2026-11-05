import hashlib
import json
import os
import subprocess
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from membrain.local_profile import load_profile

base = Path('/Users/yichen/tmp/membrain-native-validation-20261104')
repository = Path('/Users/yichen/tmp/membrain-review-20261029')
python = base / 'install-final/uv-tools/membrain-ai/bin/python'
directory = base / 'installed-followup-smoke-v2'
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_')) and not key.endswith(('_API_KEY', '_API_TOKEN'))}
environment.pop('PYTHONPATH', None)
environment.update(MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
probe = '''
import importlib.metadata
import json
import sys
import time
from pathlib import Path
import membrain
from membrain import host
from membrain.build_identity import BUILD_ID
from membrain.client import MemoryClient
from membrain.local_profile import load_profile
directory = Path(sys.argv[1])
host.start(directory)
profile = load_profile(directory)
with MemoryClient(profile.base_url, profile.api_key, profile.brain_id) as client:
    client.set_persona({'name': 'Aster', 'voice': {'register': 'formal'}})
    for index in range(3):
        client.observe("You're too formal. Please be more casual.", conversation_id='feedback', branch_id='main',
                       source_event_key=f'feedback-{index}')
    proposal = client.persona_proposals()['proposals'][0]
    client.accept_persona_proposal(proposal['id'])
    client.add_boundary('old workplace')
    deadline = time.monotonic() + 60
    while True:
        status = client.dashboard()['status']
        if not status.get('pending_jobs') and not status.get('index_lag'):
            break
        if time.monotonic() > deadline:
            raise RuntimeError('installed keyword index did not settle')
        time.sleep(.1)
    source = client.observe('A private planetarium appointment.', conversation_id='privacy-source', branch_id='main', source_event_key='private-time-source')['result']['accepted_event_ids'][0]
    private_note = client.write_note('A private planetarium appointment.', kind='milestone', shared=True, sensitive=True, source_event_ids=[source], affect={'label': 'private excitement', 'basis': 'reported', 'valence': 1, 'intensity': 1, 'felt_at': '2026-11-04'})
    new_write_status = client.dashboard()['status']
    deadline = time.monotonic() + 60
    while True:
        settled_status = client.dashboard()['status']
        if not settled_status.get('pending_jobs') and not settled_status.get('index_lag'):
            break
        if time.monotonic() > deadline:
            raise RuntimeError('privacy fixture index did not settle')
        time.sleep(.1)
    for options in ({}, {'structure': True}, {'companion': True}):
        companion = options.get('companion', False)
        hidden = client.companion_map() if companion else client.memory_map(**options)
        masked = [node for node in hidden['nodes'] if node['label'] == 'Sensitive memory']
        assert masked and all(node['recorded_at'] is None for node in masked)
        visible = client.companion_map(include_sensitive=True) if companion else client.memory_map(include_sensitive=True, **options)
        shown = {node['id']: node for node in visible['nodes']}
        assert shown['note:' + private_note['note_id']]['recorded_at'] is not None
        assert shown['msg:' + source]['recorded_at'] is not None
    graph = client.companion_map()
    memory = client.memory_map(structure=True)
from membrain.adapters.chatbot import ChatMemory, Speaker
bot_memory = ChatMemory(directory)
speaker = Speaker('installed-audit', 'synthetic-person')
protected = 'Jordan and the user used to hike Mount Tam together.'
bot_memory.note(speaker, protected)
first_context = bot_memory.context(speaker, 'Any trail ideas?', session='installed-cache-check')
assert protected in first_context
with host.ready_client(directory, bot_memory.user_id(speaker)) as scoped:
    scoped.add_boundary('old relationship', aliases=['Jordan'])
second_context = bot_memory.context(speaker, 'Any trail ideas?', session='installed-cache-check')
assert protected not in second_context
assert 'old relationship (also: Jordan)' in second_context
Path(sys.argv[2]).write_text(json.dumps({'package_root': str(Path(membrain.__file__).parent),
    'build_id': BUILD_ID, 'cache_replay_prevented': True, 'masked_recording_times_verified': True, 'graph_index_status': {'after_new_writes': new_write_status, 'before_snapshot': settled_status}, 'graph': graph, 'memory': memory,
    'versions': {name: importlib.metadata.version(name) for name in
                 ('membrain-ai','jsonschema','jsonschema-rs','referencing','fastapi','psycopg')}}))
'''
report = {'source_commit': subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip(),
          'runtime_pin': '1ca3cb23381650e245c8320906b9c467a9e3ecd7', 'completed': False}
result_path = base / 'installed-followup-smoke-v2.json'
probe_path = base / 'installed-followup-smoke-v2-probe.json'
try:
    subprocess.run([str(python), '-c', probe, str(directory), str(probe_path)],
                   env=environment, cwd=base, check=True)
    installed = json.loads(probe_path.read_text())
    package = Path(installed['package_root'])
    assert 'install-final/uv-tools/' in str(package), package
    expected = {}
    for name in ('membrain', 'agent_memory'):
        for path in (repository / 'src' / name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                expected[name + '/' + str(path.relative_to(repository / 'src' / name))] = path.read_bytes()
    expected['membrain/resources/memory-contract.schema.json'] = (repository / 'architecture/memory-contract.schema.json').read_bytes()
    expected.update({'membrain/resources/migrations/' + path.name: path.read_bytes()
                     for path in (repository / 'migrations').glob('*.sql')})
    actual = {str(path.relative_to(package.parent)): path.read_bytes() for name in ('membrain', 'agent_memory')
              for path in (package.parent / name).rglob('*') if path.is_file() and '__pycache__' not in path.parts}
    mismatches = [name for name, data in expected.items() if actual.get(name) != data]
    unexpected = sorted(set(actual) - set(expected))
    assert not mismatches and not unexpected, (mismatches, unexpected)
    profile = load_profile(directory)
    graph = installed.pop('graph')
    memory = installed.pop('memory')
    errors, outside = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='en-US')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: outside.append(request.url)
                if request.url.startswith('http') and not request.url.startswith(profile.base_url + '/') else None)
        page.goto(profile.base_url + '/memory')
        page.locator('#signin summary').click()
        page.fill('#key', profile.api_key)
        page.locator('#key-form button[type=submit]').click()
        expect(page.locator('#tabs')).to_be_visible()
        page.locator('#tabs button[data-view="brain"]').click()
        page.wait_for_function('() => window.observatory?.snapshot().nodes.length > 0')
        first = page.evaluate('() => window.observatory.snapshot()')
        assert set(first['nodes']) == {node['id'] for node in memory['nodes']}, {'extra': sorted(set(first['nodes']) - {node['id'] for node in memory['nodes']}), 'missing': sorted({node['id'] for node in memory['nodes']} - set(first['nodes']))}
        page.locator('#brain-showcase').click()
        page.wait_for_function('() => window.memoryHologram.snapshot().ready')
        immersive = page.evaluate('() => window.memoryHologram.snapshot()')
        assert set(immersive['nodeIds']) == {node['id'] for node in memory['nodes']}
        assert immersive['edges'] == memory['edges']
        page.locator('#show-pause').click()
        expect(page.locator('#show-pause')).to_have_attribute('aria-pressed', 'true')
        page.screenshot(path=str(base / 'installed-followup-hologram-v2.png'))
        page.locator('#show-close').click()
        page.select_option('#brain-layer', 'companion')
        page.wait_for_function('(generation) => window.observatory.snapshot().generation > generation', arg=first['generation'])
        scene = page.evaluate('() => window.observatory.snapshot()')
        assert set(scene['nodes']) == {node['id'] for node in graph['nodes']}
        assert set(scene['edges']) == {edge['type'] + ':' + edge['source'] + '>' + edge['target'] for edge in graph['edges']}
        persona = next(node for node in graph['nodes'] if node['kind'] == 'persona' and node['details']['version'] == 2)
        page.locator(f'#observatory-list button[data-id="{persona["id"]}"]').click()
        expect(page.locator('#brain-detail')).to_contain_text('based on feedback:')
        page.locator('#mode-2d').click()
        expect(page.locator('#brain-canvas svg')).to_be_visible()
        assert page.locator('#brain-canvas .brain-node').count() == len(graph['nodes'])
        assert not errors and not outside, (errors, outside)
        report.update(installed, checked_files=len(expected), mismatches=mismatches,
                      unexpected_package_files=unexpected,
                      expected_sha256={name: hashlib.sha256(data).hexdigest() for name, data in expected.items()},
                      browser=browser.version, scene_nodes=len(scene['nodes']), scene_edges=len(scene['edges']),
                      page_errors=errors, external_requests=outside, both_layers=True, fallback_2d=True, completed=True)
        browser.close()
finally:
    stopped = subprocess.run([str(python), '-m', 'membrain.cli', 'desktop', 'stop', '--directory', str(directory)],
                             env=environment, cwd=base, capture_output=True, text=True)
    report['stop_returncode'] = stopped.returncode
    result_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'expected_sha256'}, indent=2))
assert report['completed'] and report['stop_returncode'] == 0
