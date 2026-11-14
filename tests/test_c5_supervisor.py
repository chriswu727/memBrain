"""The run script's supervisor with a fake harness: arms P then F, one after the other, each cleaned up after it."""
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
control = os.environ['CONTROL_LOG']
def event(name):
    with open(control + '.events', 'a') as stream:
        stream.write(f'{time.time():.6f} {name}\\n')
if sys.argv[-1] in ('--preflight','--stop'):
    Path(control+sys.argv[-1]).touch()
    event(sys.argv[-1])
    raise SystemExit(0)
if '--cleanup' in sys.argv:
    name = Path(sys.argv[-1]).name
    event('cleanup ' + name)
    print('{"ok": %s, "profiles": 1}' % ('false' if name.endswith(os.environ.get('FAIL_CLEANUP', '#')) else 'true'))
    raise SystemExit(1 if name.endswith(os.environ.get('FAIL_CLEANUP', '#')) else 0)
arm=sys.argv[-3];out=Path(sys.argv[-1])
def interrupted(signum,frame):
    (out/'terminated').touch()
    event('terminated ' + arm)
    raise SystemExit(128+signum)
signal.signal(signal.SIGTERM,interrupted)
(out/'started').touch()
event('started ' + arm)
if arm==os.environ.get('FAIL_ARM'):
    (out/'failed').touch()
    event('failed ' + arm)
    raise SystemExit(7)
time.sleep(10 if os.environ.get('LONG_RUN') else 0.05)
(out/'finished').touch()
event('finished ' + arm)
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


def events(environment):
    path = Path(environment['CONTROL_LOG'] + '.events')
    return [line.split(' ', 1)[1] for line in path.read_text().splitlines()] if path.exists() else []


def stamps(directory):
    return {name: float(value) for name, value in
            (line.split(' ') for line in (directory / 'supervisor.log').read_text().splitlines())}


def test_successful_arms_run_one_after_the_other_each_cleaned_up_before_the_next(runner):
    command, environment, out = runner
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert events(environment) == ['started P', 'finished P', 'cleanup practice-P',
                                   'started F', 'finished F', 'cleanup practice-F']
    assert all((out / f'practice-{arm}/finished').is_file() for arm in 'PF')
    assert not (out / 'practice-E').exists() and not list(out.glob('*/terminated'))
    p, f = stamps(out / 'practice-P'), stamps(out / 'practice-F')
    # The arms never overlap: F starts only after P finished and was cleaned up.
    assert p['started'] <= p['finished'] <= p['cleaned'] <= f['started'] <= f['finished'] <= f['cleaned']


def test_a_failed_first_arm_never_starts_the_second_and_is_still_cleaned_up(runner):
    command, environment, out = runner
    result = subprocess.run(command, env={**environment, 'FAIL_ARM': 'P'}, capture_output=True, text=True,
                            timeout=20)
    assert result.returncode == 1, result.stderr
    assert 'arm P failed with exit 7' in result.stderr
    assert events(environment) == ['started P', 'failed P', 'cleanup practice-P']
    assert not (out / 'practice-F').exists()


def test_a_failed_second_arm_fails_the_scenario_after_the_first_finished(runner):
    command, environment, out = runner
    result = subprocess.run(command, env={**environment, 'FAIL_ARM': 'F'}, capture_output=True, text=True,
                            timeout=20)
    assert result.returncode == 1, result.stderr
    assert 'arm F failed with exit 7' in result.stderr
    assert events(environment) == ['started P', 'finished P', 'cleanup practice-P', 'started F', 'failed F',
                                   'cleanup practice-F']


def test_a_failed_cleanup_stops_before_the_next_arm(runner):
    command, environment, out = runner
    result = subprocess.run(command, env={**environment, 'FAIL_CLEANUP': '-P'}, capture_output=True, text=True,
                            timeout=20)
    assert result.returncode == 1, result.stderr
    assert 'cleanup of practice-P failed' in result.stderr
    assert events(environment) == ['started P', 'finished P', 'cleanup practice-P']
    assert not (out / 'practice-F').exists()
    assert 'cleaned' not in stamps(out / 'practice-P')


def test_a_failed_live_arm_stops_the_shared_attempt_and_never_starts_the_next(runner):
    command, environment, out = runner
    environment.update(C5_STUB='0', DEEPSEEK_API_KEY='fake-no-network', C5_BILLING_LEDGER='fake-no-network',
                       C5_ATTEMPT_ID='fake', C5_BILLING_POLICY_SHA256='fake', FAIL_ARM='P')
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 1, result.stderr
    assert Path(environment['CONTROL_LOG'] + '--preflight').is_file()
    assert events(environment) == ['--preflight', 'started P', 'failed P', '--stop', 'cleanup practice-P']
    assert not (out / 'practice-F').exists()


def test_terminating_a_live_runner_blocks_the_ledger_before_stopping_the_running_arm(runner):
    command, environment, out = runner
    environment.update(C5_STUB='0', DEEPSEEK_API_KEY='fake-no-network', C5_BILLING_LEDGER='fake-no-network',
                       C5_ATTEMPT_ID='fake', C5_BILLING_POLICY_SHA256='fake', LONG_RUN='1')
    process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while not (out / 'practice-P/started').is_file():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        process.send_signal(signal.SIGTERM)
        _, stderr = process.communicate(timeout=20)
        assert process.returncode == 143, stderr
        assert events(environment)[:4] == ['--preflight', 'started P', '--stop', 'terminated P']
        assert events(environment)[-1] == 'cleanup practice-P'
        assert not (out / 'practice-F').exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


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
        _, stderr = process.communicate(timeout=20)
        assert process.returncode == 143, stderr
        assert (out / 'practice-P/terminated').is_file()
        assert not list(out.glob('*/finished'))
        assert not (out / 'practice-F').exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
