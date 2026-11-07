import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psycopg
from psycopg.rows import dict_row

from membrain import embedded_database, host
from membrain.client import MemoryClient
from membrain.local_profile import load_profile

root = Path(__file__).parent
repository = Path('/Users/yichen/tmp/membrain-review-20261029')
archive = root / 'canonical-profile-b994ec8.tar.gz'
directory = root / 'perf-b994ec8-installation'
prefix = directory.name + '/'
assert not directory.exists()
assert shutil.disk_usage(root).free > 2_000_000_000
assert hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == '18924505bb3ee0851800646740135430c9667d668ecb382c431495c3347b6ddd'
expected = json.loads((root / 'failing-profile-files.private.json').read_text())
files = {}
with tarfile.open(archive, 'r|gz') as saved:
    for member in saved:
        if not member.name.startswith(prefix):
            continue
        target = root / member.name
        assert target.is_relative_to(directory) and '..' not in Path(member.name).parts
        if member.isdir():
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.chmod(0o700)
        else:
            assert member.isfile(), member.name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with saved.extractfile(member) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o600)
            files[member.name] = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
            assert files[member.name] == expected[member.name]
assert files == {name: value for name, value in expected.items() if name.startswith(prefix)}
for name, value in expected.items():
    if not name.startswith(prefix):
        assert hashlib.file_digest((root / name).open('rb'), 'sha256').hexdigest() == value
profile = load_profile(directory)
settings = profile.settings()
assert settings.cognition_base_url is None and settings.embedding_base_url is None
from membrain.local_embeddings import complete
assert not complete(Path(settings.embedding_local_directory))
for dsn in (profile.database_url, profile.migration_database_url):
    target = urlsplit(dsn)
    assert target.hostname == '127.0.0.1' and target.port == profile.database_port
for port in (profile.database_port, profile.api_port):
    with socket.socket() as connection:
        assert connection.connect_ex(('127.0.0.1', port)) != 0
environment = {key: value for key, value in os.environ.items()
               if not key.startswith(('MEMORY_', 'MEMBRAIN_'))
               and not key.endswith(('_API_KEY', '_API_TOKEN'))}
environment.update(PYTHON_DOTENV_DISABLED='1', MEMBRAIN_SEMANTIC='0')
hashes = {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in (repository / 'src').rglob('*')
          if path.is_file() and '__pycache__' not in path.parts}
import cProfile
import threading
from membrain.client import default_read_fence
from membrain.contracts import CONTRACT_VERSION
from membrain.helpers import Principal, uid
from membrain.recovery_authority import configure_authority
from membrain.service import MemoryService
from membrain.storage import Database
report = {'purpose': 'single-Python-thread core function attribution, not R5 qualification', 'completed': False, 'runs': [], 'model_calls': 0, 'restored_files_verified': len(files)}
started = False
try:
    embedded_database.start(profile)
    started = True
    database = Database(settings.database_url)
    configure_authority(database, settings)
    assert database.recovery_authority is not None
    service = MemoryService(database)
    principal = Principal(profile.tenant_id, profile.principal_id)
    def request():
        return {'message_type':'request','contract_version':CONTRACT_VERSION,'request_id':uid(),'action':'recall',
                'target':{'brain_ref':host.user_brain_id('bench-user-0')},
                'payload':{'query':'What is the appointment for project0000?','intent':'explore','cue_event_ids':[],'additional_cues':[], 'read_fence':default_read_fence(), 'budget':host.recall_budget(embeddings=0),'evidence_cutoff':{'mode':'through_sequence','through_sequence':2**53}}}
    assert service.handle(principal, request())['outcome']=='completed'
    for index in range(2):
        assert threading.active_count()==1, 'requires one Python thread, unlike API cProfile attempts'
        profiler = cProfile.Profile()
        cpu = time.thread_time_ns()
        result = profiler.runcall(service.handle, principal, request())
        cpu = (time.thread_time_ns()-cpu)/1e6
        assert result['outcome']=='completed' and result['result']['items']
        assert threading.active_count()==1
        profiler.create_stats()
        rows = [{'file':key[0],'line':key[1],'name':key[2],'calls':value[1], 'self_ms':value[2]*1000,'cumulative_ms':value[3]*1000} for key,value in profiler.stats.items()]
        report['runs'].append({'index':index,'thread_count':threading.active_count(),'profiled_thread_cpu_ms':cpu,'items':len(result['result']['items']),'by_cumulative':sorted(rows,key=lambda x:x['cumulative_ms'],reverse=True)[:80],'by_self':sorted(rows,key=lambda x:x['self_ms'],reverse=True)[:80]})
    report['completed'] = True
finally:
    if 'database' in locals(): database.close()
    if started: embedded_database.stop(profile)
    report['ports_closed'] = True
    for port in (profile.database_port,profile.api_port):
        with socket.socket() as connection:report['ports_closed'] &= connection.connect_ex(('127.0.0.1',port)) != 0
    report['source_unchanged'] = all(hashlib.sha256((repository/name).read_bytes()).hexdigest()==value for name,value in hashes.items())
    if report['completed'] and report['ports_closed']:
        shutil.rmtree(directory); report['restored_copy_removed'] = True
    (root/'core-single-thread-profile.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items() if key!='runs'}))
assert report['completed'] and report['ports_closed'] and report['source_unchanged']
