import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash')
pytestmark = pytest.mark.skipif(BASH is None or os.name == 'nt', reason='The C5 runner needs a POSIX shell')


@pytest.fixture
def runner(tmp_path):
    binary = tmp_path / 'bin'
    binary.mkdir()
    probe = binary / 'python3'
    probe.write_text('#!/bin/sh\nif [ "$1" = "-" ]; then exit 0; fi\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    probe.chmod(0o755)
    sleep = binary / 'sleep'
    sleep.write_text('#!/bin/sh\n/bin/sleep 0.001\n')
    sleep.chmod(0o755)
    python = tmp_path / 'fake-python'
    python.write_text('''#!/usr/bin/env python3
import os,signal,sys,time
from pathlib import Path
if sys.argv[-1] in ('--preflight','--stop'):
    Path(os.environ['CONTROL_LOG']+sys.argv[-1]).touch()
    raise SystemExit(0)
arm=sys.argv[-3];out=Path(sys.argv[-1])
def interrupted(signum,frame):
    (out/'terminated').touch()
    raise SystemExit(128+signum)
signal.signal(signal.SIGTERM,interrupted)
(out/'started').touch()
if arm==os.environ.get('FAIL_ARM'):
    (out/'failed').touch()
    raise SystemExit(7)
time.sleep(10 if os.environ.get('LONG_RUN') else 0.01)
(out/'finished').touch()
''')
    python.chmod(0o755)
    environment = {**os.environ, 'C5_STUB': '1', 'C5_PYTHON': str(python),
                   'MEMBRAIN_MODEL_CACHE': str(tmp_path), 'CONTROL_LOG': str(tmp_path / 'control'),
                   'PATH': str(binary) + os.pathsep + os.environ['PATH']}
    for name in ['MEMBRAIN_SRC', 'MEMBRAIN_EVALUATION_CLOCK']:
        environment.pop(name, None)
    out = tmp_path / 'out'
    command = [BASH, str(ROOT / 'evaluations/c5-run-scenario.sh'), 'public-practice.py', str(out), 'practice']
    return command, environment, out


@pytest.mark.parametrize('failed', ['E', 'F'])
def test_a_later_arm_failure_stops_its_siblings_during_startup(runner, failed):
    command, environment, out = runner
    result = subprocess.run(command, env={**environment, 'FAIL_ARM': failed, 'LONG_RUN': '1'},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1, result.stderr
    assert f'arm {failed} failed with exit 7' in result.stderr
    assert (out / f'practice-{failed}/failed').is_file()
    assert (out / 'practice-P/terminated').is_file()
    assert not list(out.glob('*/finished'))
    if failed == 'E':
        assert not (out / 'practice-F/started').exists()


def test_successful_arms_all_finish_and_return_success(runner):
    command, environment, out = runner
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert all((out / f'practice-{arm}/finished').is_file() for arm in 'PEF')
    assert not list(out.glob('*/terminated'))


def test_a_failed_live_arm_stops_the_shared_attempt_before_terminating_siblings(runner):
    command, environment, out = runner
    environment.update(C5_STUB='0', DEEPSEEK_API_KEY='fake-no-network', C5_BILLING_LEDGER='fake-no-network',
                       C5_ATTEMPT_ID='fake', C5_BILLING_POLICY_SHA256='fake', FAIL_ARM='E', LONG_RUN='1')
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1, result.stderr
    stopped = Path(environment['CONTROL_LOG'] + '--stop')
    terminated = out / 'practice-P/terminated'
    assert Path(environment['CONTROL_LOG'] + '--preflight').is_file()
    assert stopped.is_file() and terminated.is_file()
    assert stopped.stat().st_mtime_ns <= terminated.stat().st_mtime_ns
    assert not list(out.glob('*/finished'))


def test_terminating_the_runner_stops_the_started_arm(runner):
    command, environment, out = runner
    process = subprocess.Popen(command, env={**environment, 'LONG_RUN': '1'},
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while not (out / 'practice-P/started').is_file():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        process.send_signal(signal.SIGTERM)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 143, stderr
        assert (out / 'practice-P/terminated').is_file()
        assert not list(out.glob('*/finished'))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
