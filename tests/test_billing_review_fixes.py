"""The billing review of 2026-11-17 (findings F1, F3, F4, F6 and F7), with fake transports only: no network, no
service, no database, no model. A complete 2xx body without billing JSON is an interruption (F1); only 429, 500, 502,
503 and 504 are retried (F3); ledger entries carry a sequence number and times, interruption lines the request's
size, and the ledger check compares the two (F4); validity reports the delay interruptions added per session (F6);
the harness's SIGTERM handler never waits for a ledger lock its own process holds (F7)."""
import importlib.util
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SECRET = "zq-billing-review-secret-7731"  # Planted in every provider body, exception and session id.


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load("c5_harness_billing_review", ROOT / "evaluations" / "c5-harness.py")
budget = harness.billing_module()
review = _load("acceptance_review_billing_review", ROOT / "evaluations" / "acceptance_review.py")
POLICY = json.loads((ROOT / "evaluations" / "maturity-provider-policy-2026-11-14.json").read_text())
RATE = {**POLICY["models"]["deepseek-v4-pro"], "response_models": [harness.MODEL]}
ENDPOINT = harness.BASE_URL + "/chat/completions"
RESERVATION = 20_054_016
MESSAGES = [{"role": "system", "content": "You are a companion. 今天是3月3日。"},
            {"role": "user", "content": f"Ich bin müde. {SECRET}"}]
BODY = {"model": harness.MODEL, "max_tokens": 16384, "stream": False, "messages": MESSAGES}


def ledger(tmp_path, name="ledger.json"):
    path = tmp_path / name
    budget.create_ledger(path, run_id="review-practice", limit_cny=POLICY["proposed_limit_cny"], endpoint=ENDPOINT,
                         models={harness.MODEL: RATE})
    return path


def guard(path, handler, **options):
    return budget.GuardedTransport(path, run_id="review-practice", policy_sha256=state(path)["policy_sha256"],
                                   transport=httpx.MockTransport(handler), **options)


def state(path):
    return json.loads(path.read_text())


def bound(body: bytes) -> int:
    return min(1_048_576, 2 * len(body) + 16_384) * 9 + 16_384 * 27


def reply(**changes):
    data = {"model": harness.MODEL, "choices": [{"message": {"role": "assistant", "content": "Fake reply."}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
    data.update(changes)
    return httpx.Response(200, json=data)


BODIES = {  # Complete 2xx bodies without billing JSON, and the reason the guard records.
    "blank": (lambda: httpx.Response(200, content=b"\n\n   \n\r\n\t\n"), "blank"),
    "empty": (lambda: httpx.Response(200, content=b""), "blank"),
    "truncated": (lambda: httpx.Response(200, content=b'{"model": "deepseek-v4-pro", "choices": [{"mess'), "not_json"),
    "text": (lambda: httpx.Response(200, content=SECRET.encode()), "not_json"),
    "error_object": (lambda: httpx.Response(200, json={"error": {"message": SECRET, "code": "overloaded"}}),
                     "no_usage"),
    "list": (lambda: httpx.Response(200, json=[SECRET]), "no_usage"),
}


class Provider:
    """A fake provider: the given failures on the first sends (a status, an exception class or a name in BODIES),
    then a billed reply."""

    def __init__(self, *failures, delay=0.0):
        self.failures, self.bodies, self.delay = list(failures), [], delay

    def __call__(self, request):
        self.bodies.append(request.content)
        failure = self.failures.pop(0) if self.failures else None
        if failure is not None and self.delay:  # A busy wait: time.sleep is replaced by the live fixture.
            until = time.monotonic() + self.delay
            while time.monotonic() < until:
                pass
        if isinstance(failure, int):
            return httpx.Response(failure, content=SECRET.encode())
        if isinstance(failure, str):
            return BODIES[failure][0]()
        if failure is not None:
            raise failure(SECRET, request=request)
        return reply()


@pytest.fixture
def live(monkeypatch):
    """A live host client against fakes: the waits are recorded, never slept."""
    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", f"fake-key-{SECRET}")
    slept = []
    monkeypatch.setattr(harness.time, "sleep", slept.append)
    return slept


def host_for(path, provider, out, cap=15):
    transport = guard(path, provider)
    return harness.Host(cap=cap, transport=transport, guard=transport, out=out)


def at(session="s-a", turn=0, round_=0):
    return {"session": session, "turn": turn, "round": round_, "where": "session 1 of 2, message 1"}


def interruptions(out):
    path = out / harness.INTERRUPTIONS
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# F1: a complete 2xx body without billing JSON is an interruption ---------------------------------------------------

@pytest.mark.parametrize("name", sorted(BODIES))
def test_a_2xx_body_without_billing_json_is_settled_at_its_bound_and_sent_again(tmp_path, live, capsys, name):
    path = ledger(tmp_path)
    provider = Provider(name)
    host = host_for(path, provider, tmp_path)
    message, usage = host.call(MESSAGES, None, at=at())
    assert message["content"] == "Fake reply." and usage["total_tokens"] == 150
    assert host.calls == 2 and live == [30] and provider.bodies[0] == provider.bodies[1]
    ledger_state = state(path)
    assert ledger_state["blocked"] is False and "stop_reason" not in ledger_state
    interrupted, settled = sorted(ledger_state["requests"].values(), key=lambda entry: entry["seq"])
    reason = BODIES[name][1]
    assert interrupted["interrupted"] == {"kind": "provider_incomplete_body", "http_status": 200, "body": reason,
                                          "prompt_tokens_bound": 2 * len(provider.bodies[0]) + 16_384,
                                          "completion_tokens_bound": 16_384}
    assert interrupted["actual_micros"] == bound(provider.bodies[0]) and "failure" not in interrupted
    assert settled["actual_micros"] == 100 * 9 + 50 * 27
    (line,) = interruptions(tmp_path)
    assert {key: line[key] for key in ("format", "kind", "http_status", "body", "request_bytes", "send", "retried",
                                       "wait_seconds")} == {
        "format": 2, "kind": "provider_incomplete_body", "http_status": 200, "body": reason,
        "request_bytes": len(provider.bodies[0]), "send": 1, "retried": True, "wait_seconds": 30}
    assert "error_class" not in line and not (tmp_path / "harness-events.jsonl").exists()
    out = capsys.readouterr().out
    assert f"provider interrupted body_{reason} at session 1 of 2, message 1, round 1: send 1 of 3, retry in 30 s" in out
    assert SECRET not in out + path.read_text()


def test_three_bodies_without_billing_json_block_the_ledger_with_their_kind(tmp_path, live):
    path = ledger(tmp_path)
    provider = Provider("blank", "truncated", "error_object", None)
    host = host_for(path, provider, tmp_path)
    with pytest.raises(budget.BudgetStop, match="every send"):
        host.call(MESSAGES, None, at=at())
    assert len(provider.bodies) == 3 and live == [30, 120]
    ledger_state = state(path)
    assert ledger_state["blocked"] is True and ledger_state["stop_reason"] == "provider_incomplete_body"
    assert [entry["interrupted"]["body"] for entry in sorted(ledger_state["requests"].values(),
                                                             key=lambda entry: entry["seq"])] == [
        "blank", "not_json", "no_usage"]
    assert [(line["body"], line["retried"]) for line in interruptions(tmp_path)] == [
        ("blank", True), ("not_json", True), ("no_usage", False)]


@pytest.mark.parametrize("usage,changes", [
    (None, {}),  # Present but null.
    ({}, {}),
    ({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 151}, {}),  # Inconsistent.
    ({"prompt_tokens": SECRET, "completion_tokens": 50, "total_tokens": 150}, {}),  # Malformed.
    ({"prompt_tokens": 100, "completion_tokens": 16_385, "total_tokens": 16_485}, {}),  # Above max_tokens.
    ({"prompt_tokens": 1_048_577, "completion_tokens": 1, "total_tokens": 1_048_578}, {}),  # Above the context.
    ({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, {"model": SECRET}),  # Unexpected model.
    ({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, {"model": None}),
])
def test_usage_that_is_present_but_wrong_stays_fatal(tmp_path, live, usage, changes):
    path = ledger(tmp_path)

    def provider(request):
        return reply(usage=usage, **changes)

    host = host_for(path, provider, tmp_path)
    with pytest.raises(budget.BudgetStop, match="uncertain") as stopped:
        host.call(MESSAGES, None, at=at())
    assert not isinstance(stopped.value, budget.ProviderInterrupted) and live == [] and not interruptions(tmp_path)
    ledger_state = state(path)
    (entry,) = ledger_state["requests"].values()
    assert ledger_state["blocked"] is True and ledger_state["stop_reason"] == "response_billing"
    assert entry["failure"] == {"kind": "response_billing"} and "actual_micros" not in entry
    assert entry["reserved_micros"] == RESERVATION and type(entry["settled_at"]) is float
    assert SECRET not in path.read_text() + str(stopped.value)


def test_the_incomplete_body_reasons():
    assert budget.incomplete_body(b"") == budget.incomplete_body(b" \n\n\r\n") == "blank"
    assert budget.incomplete_body(b'{"usage": ') == budget.incomplete_body(b"\xff\xfe\x00") == "not_json"
    assert budget.incomplete_body(b"[" * 100_000 + b"]" * 100_000) == "not_json"  # Too deep to parse.
    assert budget.incomplete_body(b'{"error": {}}') == budget.incomplete_body(b'"text"') == "no_usage"
    assert budget.incomplete_body(b'{"usage": null}') is None  # Present: its checks decide, and fail.


# F3: only 429, 500, 502, 503 and 504 are retried -----------------------------------------------------------------

def test_a_502_is_retried_and_a_501_is_fatal(tmp_path, live):
    path = ledger(tmp_path)
    host = host_for(path, Provider(502), tmp_path)
    assert host.call(MESSAGES, None, at=at())[0]["content"] == "Fake reply." and live == [30]
    assert [line["http_status"] for line in interruptions(tmp_path)] == [502] and not state(path)["blocked"]

    other = tmp_path / "other"
    other.mkdir()
    path = ledger(other)
    provider = Provider(501)
    host = host_for(path, provider, other)
    with pytest.raises(budget.BudgetStop) as stopped:
        host.call(MESSAGES, None, at=at())
    assert not isinstance(stopped.value, budget.ProviderInterrupted) and len(provider.bodies) == 1
    (entry,) = state(path)["requests"].values()
    assert state(path)["blocked"] and entry["failure"] == {"kind": "provider_http_status", "http_status": 501}
    assert "actual_micros" not in entry and live == [30] and not interruptions(other)


def test_the_retried_statuses():
    assert [status for status in range(100, 600) if budget.retriable_status(status)] == [429, 500, 502, 503, 504]
    assert not budget.retriable_status(True) and not budget.retriable_status("503")


# F4: sequence numbers and times on the ledger, sizes on the interruption lines ---------------------------------------

def test_two_processes_sharing_a_ledger_number_their_reservations_in_order(tmp_path):
    path = ledger(tmp_path)
    context = multiprocessing.get_context("fork")
    inside, release = context.Barrier(3), context.Event()

    def arm():
        sends = []

        def provider(request):
            sends.append(1)
            if len(sends) == 1:
                inside.wait(timeout=10)  # Both processes' first requests are in flight at once.
                assert release.wait(10)
            return reply()

        with httpx.Client(transport=guard(path, provider)) as client:
            for _ in range(4):
                assert client.post(ENDPOINT, json=BODY).status_code == 200

    arms = [context.Process(target=arm) for _ in range(2)]
    for process in arms:
        process.start()
    try:
        inside.wait(timeout=10)
        in_flight = state(path)["requests"]
        assert sorted(entry["seq"] for entry in in_flight.values()) == [1, 2]
        assert all("settled_at" not in entry for entry in in_flight.values())
    finally:
        release.set()
        for process in arms:
            process.join(20)
            if process.is_alive():
                process.kill()
    assert [process.exitcode for process in arms] == [0, 0]
    entries = sorted(state(path)["requests"].values(), key=lambda entry: entry["seq"])
    assert [entry["seq"] for entry in entries] == list(range(1, 9))
    times = [entry["reserved_at"] for entry in entries]
    assert times == sorted(times) and all(type(value) is float for value in times)
    assert all(entry["settled_at"] >= entry["reserved_at"] for entry in entries)


def test_an_older_ledger_without_sequence_numbers_still_numbers_new_reservations_after_its_entries(tmp_path):
    path = ledger(tmp_path)
    old = state(path)
    old["requests"] = {"a" * 32: {"model": harness.MODEL, "max_tokens": 16384, "reserved_micros": RESERVATION,
                                  "actual_micros": 2000},
                       "b" * 32: {"model": harness.MODEL, "max_tokens": 16384, "reserved_micros": RESERVATION,
                                  "actual_micros": 3000}}
    path.write_text(json.dumps(old))
    with httpx.Client(transport=guard(path, lambda request: reply())) as client:
        assert client.post(ENDPOINT, json=BODY).status_code == 200
    (new,) = [entry for entry in state(path)["requests"].values() if "seq" in entry]
    assert new["seq"] == 3 and budget.policy_hash(state(path)) == state(path)["policy_sha256"]
    # The ledger check cannot place the older entries in a scenario, so it refuses such a ledger.
    checked = review.ledger_check(path, [], 0)
    assert not checked["valid"] and any("no sequence number" in problem for problem in checked["problems"])


def scenario_runs(tmp_path, path, name, failures_p, failures_f, live):
    """Two run directories of one scenario whose host sends were interrupted as given, then succeeded."""
    runs = []
    for arm, failures in (("P", failures_p), ("F", failures_f)):
        run = tmp_path / f"{name}-{arm}"
        run.mkdir()
        host = host_for(path, Provider(*failures), run)
        for turn in range(2):
            host.call(MESSAGES + [{"role": "user", "content": "x" * (turn + 1) * 50}], None, at=at(turn=turn))
        runs.append(run)
    return runs


def test_the_ledger_check_pairs_every_interrupted_entry_with_its_line(tmp_path, live, capsys):
    path = ledger(tmp_path)
    runs = scenario_runs(tmp_path, path, "one", [httpx.ReadTimeout], [503, "blank"], live)
    checked = review.ledger_check(path, runs, 0)
    assert checked["valid"], checked["problems"]
    assert checked["ledger_interrupted"] == checked["interruption_lines"] == {
        "ReadTimeout": 1, "body_blank": 1, "http_503": 1}
    assert checked["only_in_ledger"] == checked["only_in_lines"] == [] and checked["ledger_highest_seq"] == 7

    # The command: content-free JSON, exit 0.
    command = [sys.executable, str(ROOT / "evaluations" / "acceptance_review.py"), "ledger-check", "--ledger",
               str(path), "--after-seq", "0", *map(str, runs)]
    done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["valid"] is True and SECRET not in done.stdout + done.stderr


@pytest.mark.parametrize("damage", ["line_missing", "size_changed", "line_added", "code_changed"])
def test_the_ledger_check_reports_a_difference_as_a_harness_defect(tmp_path, live, damage):
    path = ledger(tmp_path)
    runs = scenario_runs(tmp_path, path, "one", [httpx.ReadTimeout], [503, "blank"], live)
    file = runs[1] / harness.INTERRUPTIONS
    lines = [json.loads(line) for line in file.read_text().splitlines()]
    if damage == "line_missing":
        lines = lines[:1]
    elif damage == "size_changed":
        lines[0]["request_bytes"] += 1
    elif damage == "line_added":
        lines.append({**lines[0], "turn": 1})
    else:
        lines[0]["http_status"] = 502
    file.write_text("".join(json.dumps(line) + "\n" for line in lines))
    checked = review.ledger_check(path, runs, 0)
    assert not checked["valid"] and any("harness defect" in problem for problem in checked["problems"])
    assert checked["only_in_ledger"] or checked["only_in_lines"]
    command = [sys.executable, str(ROOT / "evaluations" / "acceptance_review.py"), "ledger-check", "--ledger",
               str(path), "--after-seq", "0", *map(str, runs)]
    assert subprocess.run(command, capture_output=True, text=True, timeout=60).returncode == 1


def test_the_ledger_check_counts_only_the_scenarios_own_reservations(tmp_path, live):
    path = ledger(tmp_path)
    scenario_runs(tmp_path, path, "one", [httpx.ReadTimeout], [], live)
    before = max(entry["seq"] for entry in state(path)["requests"].values())
    second = scenario_runs(tmp_path, path, "two", [], [429], live)
    assert review.ledger_check(path, second, before)["valid"]
    whole = review.ledger_check(path, second, 0)  # The first scenario's interruption has no line in these runs.
    assert not whole["valid"] and whole["only_in_ledger"] and whole["only_in_ledger"][0]["code"] == "ReadTimeout"


def test_the_ledger_check_refuses_unusable_input(tmp_path):
    assert not review.ledger_check(tmp_path / "missing.json", [], 0)["valid"]
    (tmp_path / "bad.json").write_text("{" + SECRET)
    checked = review.ledger_check(tmp_path / "bad.json", [], 0)
    assert not checked["valid"] and SECRET not in json.dumps(checked)
    usage = subprocess.run([sys.executable, str(ROOT / "evaluations" / "acceptance_review.py"), "ledger-check",
                            "--ledger", str(tmp_path / "bad.json")], capture_output=True, text=True, timeout=60)
    assert usage.returncode != 0 and "usage" in usage.stderr


# F6: the delay interruptions added, per session ----------------------------------------------------------------------

SESSIONS = [("s-a", ["Today is Monday, March 2, 20:00. one", "two"]),
            ("s-b", ["Today is Tuesday, March 3, 23:00. three", "four"])]


def test_validity_and_diagnose_report_the_delay_per_session(tmp_path, live, capsys):
    path = ledger(tmp_path)
    scenario = tmp_path / "zq_delay.py"
    scenario.write_text(f"SESSIONS_LONG = {SESSIONS!r}\n")
    runs = []
    for number, arm in enumerate("PF"):
        run = tmp_path / f"k-{arm}"
        run.mkdir()
        rows = [{"arm": arm, "scenario": scenario.stem, "session": session, "turn": index, "reply": "Hello",
                 "usage": {"prompt_tokens": 1}} for session, turns in SESSIONS for index in range(len(turns))]
        (run / f"results_{scenario.stem}_{arm}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (run / "run.log").write_text(f"12:00:01 {arm} {scenario.stem} finished\n")
        (run / "persona.json").write_text(json.dumps({"arm": arm, "source": "seeded", "seed": "x", "preset": "enfp",
                                                      "card_sha256": "enfp", "version": 1}))
        start = 10 + 20 * number
        (run / "supervisor.log").write_text(f"started {start}\nfinished {start + 5}\ncleaned {start + 6}\n")
        runs.append(run)
    host = host_for(path, Provider(httpx.ReadTimeout, delay=0.05), runs[0])
    host.call(MESSAGES, None, at=at("s-a", 1, 0))
    host = host_for(path, Provider(503, httpx.ConnectError, delay=0.05), runs[0])
    host.call(MESSAGES, None, at=at("s-b", 0, 2))
    lines = interruptions(runs[0])
    assert [line["wait_seconds"] for line in lines] == [30, 30, 120]
    assert all(line["send_seconds"] >= 0.05 for line in lines)
    expected = {1: lines[0]["send_seconds"] + 30, 2: lines[1]["send_seconds"] + 30 + lines[2]["send_seconds"] + 120}

    result = review.validity(runs, scenario, persona_preset="enfp")
    assert result["valid"], result["problems"]
    report = result["provider_interruptions"]["k-P (P)"]
    assert [item["session"] for item in report["delay_by_session"]] == [1, 2]
    for item in report["delay_by_session"]:
        assert abs(item["seconds"] - expected[item["session"]]) <= 0.2
    assert abs(report["delay_seconds"] - sum(expected.values())) <= 0.2
    assert result["provider_interruptions"]["k-F (F)"]["delay_by_session"] == []
    assert review.ledger_check(path, runs, 0)["valid"]
    capsys.readouterr()
    review.diagnose(runs, scenario)
    out = capsys.readouterr().out
    assert "interruption delay (failed sends plus waits; in P on the scenario clock): " in out
    assert "session 1 of 2: 30." in out and "session 2 of 2: 150." in out


# F7: the SIGTERM handler never waits for its own process's lock -------------------------------------------------------

CHILD = r'''
import fcntl, importlib.util, json, os, signal, sys, time
from pathlib import Path
import httpx
spec = importlib.util.spec_from_file_location("c5_harness_signal_child", sys.argv[1])
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
budget = harness.billing_module()
path, mode = Path(sys.argv[2]), sys.argv[3]
policy = json.loads(path.read_text())["policy_sha256"]
harness.BILLING = budget.GuardedTransport(path, run_id="review-practice", policy_sha256=policy,
                                          transport=httpx.MockTransport(lambda request: httpx.Response(200)))
signal.signal(signal.SIGTERM, harness.interrupted)
body = {"model": harness.MODEL, "max_tokens": 16384, "stream": False, "messages": []}
if mode in ("inside", "unsafe"):
    original = budget._write

    def write(target, state):  # SIGTERM arrives while _reserve holds the ledger lock.
        if mode == "unsafe":  # What the handler did before the review: stop() under the process's own lock.
            harness.BILLING.stop("arm_interrupted")
        os.kill(os.getpid(), signal.SIGTERM)
        original(target, state)

    budget._write = write
    with httpx.Client(transport=harness.BILLING) as client:
        client.post(harness.BASE_URL + "/chat/completions", json=body)
elif mode == "waiting":  # SIGTERM arrives while this process waits for a lock another process holds.
    print("ready", flush=True)
    sys.stdin.readline()  # The test takes the lock, then lets this process ask for it.
    harness.BILLING.check()
else:  # Outside any guarded section.
    os.kill(os.getpid(), signal.SIGTERM)
    time.sleep(10)
sys.exit(5)
'''


def _child(tmp_path, path, mode, timeout=30, **options):
    script = tmp_path / "signal_child.py"
    script.write_text(CHILD)
    command = [sys.executable, str(script), str(ROOT / "evaluations" / "c5-harness.py"), str(path), mode]
    env = {key: value for key, value in os.environ.items() if not key.startswith("C5_")}
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env, **options)


def test_a_sigterm_inside_a_guarded_section_exits_at_once_and_leaves_the_block_to_the_run_script(tmp_path):
    path = ledger(tmp_path)
    started = time.monotonic()
    done = _child(tmp_path, path, "inside")
    assert done.returncode == 128 + signal.SIGTERM, done.stderr
    assert time.monotonic() - started < 25
    # The handler did not touch the ledger; the request never got its entry; nothing holds the lock now.
    assert state(path)["blocked"] is False and state(path)["requests"] == {}
    guard(path, lambda request: pytest.fail("no request"), allow_stopped=True).stop("arm_failed")  # The --stop.
    assert state(path)["blocked"] is True and state(path)["stop_reason"] == "arm_failed"


def test_without_the_lock_check_the_same_signal_would_hang(tmp_path):
    """The control: stop() under the process's own lock waits for that process for ever (killed at the timeout)."""
    path = ledger(tmp_path)
    with pytest.raises(subprocess.TimeoutExpired):
        _child(tmp_path, path, "unsafe", timeout=3)


def test_a_sigterm_while_waiting_for_another_processs_lock_exits_without_waiting(tmp_path):
    import fcntl

    path = ledger(tmp_path)
    script = tmp_path / "signal_child.py"
    script.write_text(CHILD)
    child = subprocess.Popen([sys.executable, str(script), str(ROOT / "evaluations" / "c5-harness.py"), str(path),
                              "waiting"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env={key: value for key, value in os.environ.items()
                                             if not key.startswith("C5_")})
    try:
        assert child.stdout.readline().strip() == "ready"
        with (path.parent / (path.name + ".lock")).open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)  # Another process (this test) holds the ledger lock.
            child.stdin.write("go\n")
            child.stdin.flush()
            time.sleep(0.5)  # The child is now waiting in flock.
            child.send_signal(signal.SIGTERM)
            assert child.wait(timeout=20) == 128 + signal.SIGTERM  # While the lock is still held elsewhere.
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)
    assert state(path)["blocked"] is False


def test_a_sigterm_outside_a_guarded_section_still_blocks_the_ledger(tmp_path):
    path = ledger(tmp_path)
    done = _child(tmp_path, path, "outside")
    assert done.returncode == 128 + signal.SIGTERM, done.stderr
    assert state(path)["blocked"] is True and state(path)["stop_reason"] == "arm_interrupted"


def test_lock_held_follows_the_guarded_sections_of_the_calling_thread(tmp_path):
    path = ledger(tmp_path)
    assert not budget.lock_held()
    with budget._locked(path):
        assert budget.lock_held()
        with budget._locked(tmp_path / "other.json"):
            assert budget.lock_held()
        assert budget.lock_held()
    assert not budget.lock_held()
    with pytest.raises(RuntimeError), budget._locked(path):
        raise RuntimeError
    assert not budget.lock_held()
