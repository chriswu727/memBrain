import hashlib
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright
from membrain import embedded_database, host
from membrain.client import MemoryClient
from membrain.local_profile import load_profile

ROOT = Path('/Users/yichen/tmp/membrain-release-qualification-20261104')
INSTALLATION = Path('/Users/yichen/tmp/membrain-release-qualification-20261104/perf-b994ec8-installation')
PROFILE = load_profile(INSTALLATION)
QUERIES = [f'What is the appointment for project{i % 50:04d}?' for i in range(20)]
BOOT = '''
import sys
from pathlib import Path
import uvicorn
from membrain.api import create_app
from membrain.local_profile import load_profile
profile=load_profile(Path(sys.argv[1]))
uvicorn.run(create_app(profile.settings()),host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
'''
ENV = {key: value for key, value in os.environ.items()
       if not key.startswith(('MEMORY_', 'MEMBRAIN_')) and not key.endswith(('_API_KEY', '_API_TOKEN'))}
ENV.update(MEMBRAIN_SEMANTIC='0', PYTHON_DOTENV_DISABLED='1')
os.environ['DEBUG'] = 'pw:browser'
REPORT = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'runtime_pin': 'b994ec8080d46ee861f6ed8738a1617929f50d2a', 'model_calls': 0,
          'protocol': 'Same settled 1k corpus; closed/open/open/closed, fresh API per phase, browser kept open on blank in closed phases. Real 200-node-limit memory page and fullscreen hologram in open phases, normal page polling retained. Three cycles per phase; each cycle uses the unchanged three recall workloads and 21 canonical queries per worker, discarding each first. Browser events are pumped while recall workers run. Browser process stderr and explicit page crash/close/disconnect events are captured; this adds observability after an unexplained TargetClosed failure, without changing renderer, workloads or bars. Normal 30-second polling remains active; no timing samples discarded beyond the declared warmups. Animation is paused only after measurement for screenshots; capture errors remain failures while subsequent workload phases continue.',
          'completed': False, 'passed': False, 'phases': [], 'browser_events': []}
BROWSER_STATE = {'closing': False, 'phase_index': None}


def save():
    (ROOT / 'visual-permissions-abba.json').write_text(json.dumps(REPORT, indent=2) + '\n')


def stats(parts):
    values = sorted(elapsed for raw in parts for elapsed in raw)
    return {'n': len(values), 'nonempty': len(values), 'median_ms': round(statistics.median(values), 2),
            'p95_ms': round(values[int(.95 * (len(values) - 1))], 2), 'max_ms': round(max(values), 2),
            'raw_ms': [[round(value, 2) for value in raw] for raw in parts]}


embedded_database.start(PROFILE)
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        browser.on('disconnected', lambda: REPORT['browser_events'].append(
            {'event': 'browser_disconnected', **BROWSER_STATE, 'at': time.monotonic()}))
        REPORT['browser'] = browser.version
        for phase_index, mode in enumerate(('closed', 'open', 'open', 'closed')):
            BROWSER_STATE['phase_index'] = phase_index
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            base = f'http://127.0.0.1:{port}'
            log = (ROOT / f'visual-permissions-{phase_index}-{mode}.log').open('w')
            process = subprocess.Popen([sys.executable, '-c', BOOT, str(INSTALLATION), str(port)],
                                       env=ENV, stdout=log, stderr=subprocess.STDOUT)
            context = browser.new_context(viewport={'width': 1280, 'height': 900}, device_scale_factor=1,
                                          reduced_motion='no-preference')
            clients = []
            errors, outside, requests = [], [], []
            phase = {'mode': mode, 'closing': False, 'api_port': port}
            REPORT['phases'].append(phase)
            save()
            try:
                with httpx.Client(timeout=.5, trust_env=False) as health:
                    deadline = time.monotonic() + 30
                    while True:
                        assert process.poll() is None, 'API exited before health became ready'
                        try:
                            if health.get(base + '/health').status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        if time.monotonic() > deadline:
                            raise RuntimeError('API readiness timed out')
                        time.sleep(.1)
                page = context.new_page()
                page.on('crash', lambda _page, i=phase_index: REPORT['browser_events'].append(
                    {'event': 'page_crash', 'phase_index': i, 'at': time.monotonic()}))
                page.on('close', lambda _page, p=phase, i=phase_index: REPORT['browser_events'].append(
                    {'event': 'page_close', 'phase_index': i, 'expected': p['closing'], 'at': time.monotonic()}))
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda request: requests.append(request.url))
                page.on('request', lambda request: outside.append(request.url)
                        if request.url.startswith('http') and not request.url.startswith(base + '/') else None)
                brain0 = host.user_brain_id('bench-user-0')
                clients = [MemoryClient(base, PROFILE.api_key, brain_id=host.user_brain_id(f'bench-user-{i}'))
                           for i in range(8)]
                same = [clients[0], *[MemoryClient(base, PROFILE.api_key, brain_id=brain0) for _ in range(7)]]
                clients += same[1:]
                if mode == 'open':
                    saved = json.dumps({'key': PROFILE.api_key, 'brain': brain0, 'view': 'brain'})
                    page.add_init_script('sessionStorage.setItem("membrain-page", ' + json.dumps(saved) + ');')
                    page.goto(base + '/memory')
                    page.wait_for_function('() => window.observatory?.snapshot().nodes.length > 0')
                    with MemoryClient(base, PROFILE.api_key, brain_id=brain0) as c:
                        graph = c.memory_map(max_nodes=200, max_edges=400, trace=True, structure=True)
                    scene = page.evaluate('() => window.observatory.snapshot()')
                    assert set(scene['nodes']) == {node['id'] for node in graph['nodes']}
                    renderer = page.evaluate('() => window.observatory.renderer()')
                    assert not any(token in renderer['renderer'].lower() for token in ('swiftshader', 'llvmpipe', 'software'))
                    phase.update(renderer=renderer, nodes=len(graph['nodes']), edges=len(graph['edges']))
                    page.locator('#brain-showcase').click()
                    page.wait_for_function('() => window.memoryHologram.snapshot().ready')
                    page.bring_to_front()
                    before = page.evaluate('() => window.memoryHologram.snapshot()')
                    assert before['edges'] == graph['edges']
                    assert set(before['nodeIds']) == {node['id'] for node in graph['nodes']}
                    assert page.evaluate('() => !document.hidden')
                    phase['payload_digest'] = hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()
                else:
                    page.goto('about:blank')
                    before = None
                begin = time.perf_counter()
                request_begin = len(requests)

                def worker(client):
                    raw = []
                    for index in range(21):
                        start = time.perf_counter()
                        found = host.recall_context(client, QUERIES[index % 20], current_conversation='benchmark')
                        raw.append((time.perf_counter() - start) * 1000)
                        assert found, 'An empty recall cannot count as a successful latency sample'
                    return raw[1:]

                phase['cycles'] = []
                combined = {name: [] for name in ('serial', 'one_brain_8_concurrent', 'eight_brains_8_concurrent')}
                def measure(name, assignments, cycle):
                    with ThreadPoolExecutor(max_workers=len(assignments)) as pool:
                        pending = [pool.submit(worker, client) for client in assignments]
                        while not all(task.done() for task in pending):
                            page.wait_for_timeout(50)
                        parts = [task.result() for task in pending]
                    cycle[name] = stats(parts)
                    combined[name].extend(parts)
                    save()

                for cycle_index in range(3):
                    cycle = {'index': cycle_index}
                    phase['cycles'].append(cycle)
                    measure('serial', [clients[0]], cycle)
                    measure('one_brain_8_concurrent', same, cycle)
                    measure('eight_brains_8_concurrent', clients[:8], cycle)
                for name, parts in combined.items():
                    phase[name] = stats(parts)
                phase['seconds'] = round(time.perf_counter() - begin, 3)
                page.wait_for_timeout(50)
                phase['browser_requests_during_measurement'] = requests[request_begin:]
                if mode == 'open':
                    after = page.evaluate('() => window.memoryHologram.snapshot()')
                    phase['hologram_frames'] = after['frames'] - before['frames']
                    assert after['edges'] == graph['edges'] and set(after['nodeIds']) == {node['id'] for node in graph['nodes']}
                    phase['document_visible'] = page.evaluate('() => !document.hidden')
                    assert any(url.endswith('/status') for url in phase['browser_requests_during_measurement']), 'No normal status poll observed'
                    assert phase['hologram_frames'] > 0 and phase['document_visible']
                    page.locator('#show-pause').click()
                    assert page.locator('#show-pause').get_attribute('aria-pressed') == 'true'
                    phase['paused_for_capture_after_measurement'] = True
                    try:
                        page.screenshot(path=str(ROOT / f'visual-permissions-{phase_index}-open.png'), timeout=10000)
                    except Exception as error:
                        phase['artifact_error'] = {'type': type(error).__name__, 'message': str(error)[:500]}
                        save()
                    page.locator('#show-close').click()
                    assert not page.evaluate('() => window.memoryHologram.snapshot().ready')
                phase['aggregate_passes_recall_bars'] = phase['serial']['p95_ms'] < 500 and phase['one_brain_8_concurrent']['p95_ms'] <= 1000 and phase['eight_brains_8_concurrent']['p95_ms'] <= 600
                phase['failed_windows'] = [cycle['index'] for cycle in phase['cycles'] if not (cycle['serial']['p95_ms'] < 500 and cycle['one_brain_8_concurrent']['p95_ms'] <= 1000 and cycle['eight_brains_8_concurrent']['p95_ms'] <= 600)]
                phase['passes_recall_bars'] = phase['aggregate_passes_recall_bars'] and not phase['failed_windows']
                phase.update(page_errors=errors, external_requests=outside)
                assert not errors and not outside, (errors, outside)
                save()
                print(json.dumps({'mode': mode, **{name: {k: v for k, v in phase[name].items() if k != 'raw_ms'}
                                                   for name in ('serial', 'one_brain_8_concurrent', 'eight_brains_8_concurrent')},
                                  'frames': phase.get('hologram_frames')}), flush=True)
            finally:
                for client in clients:
                    client.close()
                phase['closing'] = True
                try:
                    context.close()
                finally:
                    process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                log.close()
        BROWSER_STATE['closing'] = True
        browser.close()
    REPORT['completed'] = True
    REPORT['passed'] = all(phase['passes_recall_bars'] and not phase.get('artifact_error') for phase in REPORT['phases'])
except Exception as error:
    REPORT['execution_error'] = {'type': type(error).__name__, 'message': str(error)[:1000]}
    traceback.print_exc()
finally:
    embedded_database.stop(PROFILE)
    save()
assert REPORT['completed']
raise SystemExit(0 if REPORT['passed'] else 1)
