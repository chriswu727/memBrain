import copy
import hashlib
import importlib.metadata
import json
import math
import statistics
import sys
import time
from functools import partial
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root / 'native'))
sys.path.insert(0, '/Users/yichen/tmp/membrain-review-20261029/tests')

import jsonschema_rs
from test_contract_linking import documents, mutations

from membrain import contracts


def plain(value, depth=0):
    if depth > 64:
        return False
    kind = type(value)
    if kind is str or kind is bool or value is None:
        return True
    if kind is int:
        return abs(value) <= 2**53
    if kind is float:
        return math.isfinite(value) and abs(value) <= 2**53
    if kind is list:
        return all(plain(item, depth + 1) for item in value)
    if kind is dict:
        return all(type(key) is str and plain(item, depth + 1) for key, item in value.items())
    return False


retrieved = []


def retrieve(uri):
    retrieved.append(uri)
    raise ValueError('External references are not permitted')


def native(definition, checker):
    document = contracts.schema()
    formats = {node['format'] for node in contracts._subschemas(document) if 'format' in node}
    return jsonschema_rs.Draft202012Validator(
        {'$schema': document['$schema'], '$defs': document['$defs'], '$ref': '#/$defs/' + definition},
        formats={name: partial(checker.conforms, format=name) for name in formats},
        validate_formats=True, offline=True, retriever=retrieve,
    )


report = {'purpose': 'isolated native validation experiment; no runtime/dependency change or R5 qualification',
          'version': importlib.metadata.version('jsonschema-rs'),
          'schema_sha256': hashlib.sha256(json.dumps(contracts.schema(), sort_keys=True).encode()).hexdigest(),
          'guard': 'exact native JSON types, finite numbers within2**53, maxdepth64; otherwise reference fallback',
          'external_references': retrieved, 'definitions': [], 'timings': [], 'completed': False}
for definition, document in documents().items():
    reference = contracts.validator(definition)
    candidate = native(definition, reference.format_checker)
    tested = positives = 0
    mismatches = []
    for index, value in enumerate([document, *mutations(document, 500, seed='native-' + definition)]):
        expected = reference.is_valid(value)
        accepted = plain(value) and candidate.is_valid(value)
        tested += 1
        positives += accepted
        if accepted and not expected:
            mismatches.append(index)
    report['definitions'].append({'name': definition, 'tested': tested,
                                  'accepted': positives, 'false_acceptances': mismatches})
    (root / 'native-experiment.json').write_text(json.dumps(report, indent=2)+'\n')
    assert not mismatches, (definition, mismatches)

fixture = Path('/Users/yichen/tmp/membrain-release-qualification-20261104/validation-response.private.json')
value = json.loads(fixture.read_text())
assert len(value['result']['items']) == 51
reference = contracts.validator('ActionResponse')
candidate = native('ActionResponse', reference.format_checker)
assert reference.is_valid(value) and plain(value) and candidate.is_valid(value)
report['fixture'] = {'bytes': fixture.stat().st_size, 'items': 51,
                     'sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(), 'private_fixture_excluded': True}
for name, check in [('reference', reference.is_valid), ('native', candidate.is_valid),
                    ('guarded_native', lambda value: plain(value) and candidate.is_valid(value))]:
    samples = []
    for _ in range(40):
        before = time.thread_time_ns()
        assert check(value)
        samples.append((time.thread_time_ns()-before)/1e6)
    report['timings'].append({'name': name, 'median_cpu_ms': statistics.median(samples),
                              'min_cpu_ms': min(samples), 'max_cpu_ms': max(samples), 'samples_cpu_ms': samples})
report['completed'] = True
assert not retrieved
(root / 'native-experiment.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('fixture','schema_sha256')}))
