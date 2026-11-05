import hashlib
import json
import statistics
import time
from pathlib import Path

from membrain import contracts, native_contracts

root = Path(__file__).parent
fixture = Path('/Users/yichen/tmp/membrain-release-qualification-20261104/validation-response.private.json')
value = json.loads(fixture.read_text())
current = contracts.validator('ActionResponse')
assert len(value['result']['items']) == 51
current.validate(value)
assert native_contracts.accepts_response(current, value)
contracts.validate('ActionResponse', value)
report = {'purpose': 'fixed reference/native/native/reference CPU microbenchmark; not R5 qualification',
          'private_fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(), 'fixture_items': 51,
          'iterations_per_arm': 100, 'completed': False, 'arms': []}
for label in ('reference', 'native', 'native', 'reference'):
    samples = []
    for _ in range(100):
        began = time.thread_time_ns()
        if label == 'reference':
            current.validate(value)
        else:
            contracts.validate('ActionResponse', value)
        samples.append((time.thread_time_ns()-began)/1e6)
    report['arms'].append({'mode': label, 'median_cpu_ms': statistics.median(samples),
                           'min_cpu_ms': min(samples), 'max_cpu_ms': max(samples), 'raw_cpu_ms': samples})
report['completed'] = True
(root / 'final-microbenchmark.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps([{k:v for k,v in arm.items() if k!='raw_cpu_ms'} for arm in report['arms']]))
