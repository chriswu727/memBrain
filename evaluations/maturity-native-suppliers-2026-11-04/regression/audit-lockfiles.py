import datetime
import hashlib
import json
import tomllib
import urllib.request
from pathlib import Path

root = Path(__file__).parent
repo = Path('/Users/yichen/tmp/membrain-review-20261029')
queries = []
for entry in tomllib.loads((repo / 'uv.lock').read_text())['package']:
    if entry.get('source', {}).get('registry') == 'https://pypi.org/simple':
        queries.append({'package': {'name': entry['name'], 'ecosystem': 'PyPI'}, 'version': entry['version']})
for name, entry in json.loads((repo / 'sdk/typescript/package-lock.json').read_text())['packages'].items():
    if name and entry.get('resolved', '').startswith('https://registry.npmjs.org/'):
        queries.append({'package': {'name': name.rsplit('node_modules/', 1)[-1], 'ecosystem': 'npm'}, 'version': entry['version']})
unique = {json.dumps(query, sort_keys=True): query for query in queries}
queries = list(unique.values())
report = {'completed': False, 'endpoint': 'https://api.osv.dev/v1/querybatch',
          'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'public locked package versions including development and optional dependencies; does not cover vendored native libraries or prove absence of unknown vulnerabilities',
          'lockfiles': {name: hashlib.sha256((repo / name).read_bytes()).hexdigest()
                        for name in ('uv.lock', 'sdk/typescript/package-lock.json')},
          'queries': queries, 'results': [], 'pages': []}
(root / 'lockfile-audit.json').write_text(json.dumps(report, indent=2) + '\n')
pending = list(enumerate(queries))
all_results = [{} for _ in queries]
while pending:
    payload = json.dumps({'queries': [query for _, query in pending]}).encode()
    request = urllib.request.Request(report['endpoint'], data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        page = json.load(response)
    assert len(page['results']) == len(pending)
    report['pages'].append(page)
    following = []
    for (index, query), result in zip(pending, page['results']):
        all_results[index].setdefault('vulns', []).extend(result.get('vulns', []))
        if result.get('next_page_token'):
            following.append((index, {**queries[index], 'page_token': result['next_page_token']}))
    pending = following
    (root / 'lockfile-audit.json').write_text(json.dumps(report, indent=2) + '\n')
report.update(completed=True, results=all_results, packages_checked=len(queries),
              packages_with_advisories=sum(bool(row.get('vulns')) for row in all_results))
(root / 'lockfile-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ('completed', 'packages_checked', 'packages_with_advisories')}))
for query, result in zip(queries, all_results):
    if result.get('vulns'):
        print(json.dumps({'query': query, 'advisories': result['vulns']}))
