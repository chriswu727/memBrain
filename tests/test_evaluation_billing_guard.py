import importlib.util
import json
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "evaluation_budget", Path(__file__).resolve().parents[1] / "evaluations/evaluation_budget.py")
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)
ENDPOINT = "https://provider.test/chat/completions"
MODELS = {"host": {"context_tokens": 1000, "max_output_tokens": 100,
                   "input_cny_per_million": "1", "output_cny_per_million": "2"}}


def ledger(tmp_path, limit="0.0024"):
    path = tmp_path / "billing.json"
    budget.create_ledger(path, run_id="practice", limit_cny=limit, endpoint=ENDPOINT, models=MODELS)
    return path


def guarded(path, **options):
    state = json.loads(path.read_text())
    return budget.GuardedTransport(path, run_id="practice", policy_sha256=state["policy_sha256"], **options)


def send(path, handler, **changes):
    body = {"model": "host", "max_tokens": 100, "stream": False,
            "messages": [{"role": "user", "content": "billing-message-fixture-441892"}]}
    body.update(changes)
    with httpx.Client(transport=guarded(path, transport=httpx.MockTransport(handler))) as client:
        return client.post(ENDPOINT, json=body, headers={"Authorization": "Bearer billing-key-fixture-4499209"})


def reply(request=None, **changes):
    data = {"model": "host", "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}
    data.update(changes)
    return httpx.Response(200, json=data)


def test_success_settles_conservatively_and_retains_no_messages_or_keys(tmp_path):
    path = ledger(tmp_path)
    assert send(path, reply).status_code == 200
    state = json.loads(path.read_text())
    entry, = state["requests"].values()
    assert entry["reserved_micros"] == 1200 and entry["actual_micros"] == 30
    assert not state["blocked"]
    assert all(value not in path.read_text() for value in ["billing-message-fixture-441892", "billing-key-fixture-4499209"])
    assert path.stat().st_mode & 0o777 == 0o600


def test_concurrent_arms_cannot_spend_each_others_in_flight_reservations(tmp_path):
    path = ledger(tmp_path)
    inside = threading.Barrier(3)
    release = threading.Event()

    def pending(request):
        inside.wait(timeout=10)
        assert release.wait(10)
        return reply()

    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(send, path, pending) for _ in range(2)]
        try:
            inside.wait(timeout=10)
            with pytest.raises(budget.BudgetStop, match="cap"):
                send(path, lambda request: pytest.fail("unreserved request reached provider"))
            state = json.loads(path.read_text())
            assert sum(row["reserved_micros"] for row in state["requests"].values()) == state["limit_micros"]
        finally:
            release.set()
        assert all(task.result().status_code == 200 for task in tasks)
    state = json.loads(path.read_text())
    assert state["blocked"] and state["stop_reason"] == "reservation_limit"
    assert all("actual_micros" in entry for entry in state["requests"].values())
    with pytest.raises(budget.BudgetStop, match="stopped"):
        send(path, lambda request: pytest.fail("a cap-stopped run resumed after settlement"))


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2},
                                  {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 21},
                                  {"prompt_tokens": 1001, "completion_tokens": 10, "total_tokens": 1011},
                                  {"prompt_tokens": 10, "completion_tokens": 101, "total_tokens": 111}])
def test_uncertain_or_out_of_bound_usage_keeps_its_reservation_and_stops_every_arm(tmp_path, usage):
    path = ledger(tmp_path)
    with pytest.raises(budget.BudgetStop, match="uncertain"):
        send(path, lambda request: reply(usage=usage))
    state = json.loads(path.read_text())
    entry, = state["requests"].values()
    assert state["blocked"] and "actual_micros" not in entry and entry["reserved_micros"] == 1200
    with pytest.raises(budget.BudgetStop, match="stopped"):
        send(path, lambda request: pytest.fail("blocked run reached provider"))


@pytest.mark.parametrize("failure", ["timeout", "http", "malformed", "other_model"])
def test_provider_failures_never_release_money_for_an_automatic_retry(tmp_path, failure):
    path = ledger(tmp_path)

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("unknown whether billed", request=request)
        if failure == "http":
            return httpx.Response(503)
        if failure == "malformed":
            return httpx.Response(200, content=b"not json")
        return reply(model="unapproved-model")

    with pytest.raises(budget.BudgetStop):
        send(path, handler)
    assert json.loads(path.read_text())["blocked"]
    with pytest.raises(budget.BudgetStop):
        send(path, lambda request: pytest.fail("failed run retried externally"))


@pytest.mark.parametrize("failure,expected", [
    ("timeout", {"kind": "provider_transport", "error_class": "ReadTimeout"}),
    ("body_timeout", {"kind": "provider_transport", "error_class": "ReadTimeout"}),
    ("interrupt", {"kind": "provider_transport", "error_class": "SystemExit"}),
    ("unknown_class", {"kind": "provider_transport", "error_class": "other"}),
    ("http", {"kind": "provider_http_status", "http_status": 503}),
    ("malformed", {"kind": "response_billing"}),
    ("other_model", {"kind": "response_billing"}),
])
def test_provider_stop_records_safe_cause_without_releasing_reservation(tmp_path, failure, expected):
    path = ledger(tmp_path)
    original_policy = json.loads(path.read_text())["policy_sha256"]
    secret = "PRIVATE-PROVIDER-BODY-AND-EXCEPTION"

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(secret, request=request)
        if failure == "body_timeout":
            class InterruptedBody(httpx.SyncByteStream):
                def __iter__(self):
                    yield secret.encode()
                    raise httpx.ReadTimeout(secret, request=request)
            return httpx.Response(200, stream=InterruptedBody())
        if failure == "interrupt":
            raise SystemExit(secret)
        if failure == "unknown_class":
            raise type(secret, (RuntimeError,), {})(secret)
        if failure == "http":
            return httpx.Response(503, content=secret, headers={"x-private": secret})
        if failure == "malformed":
            return httpx.Response(200, content=secret)
        return reply(model=secret)

    with pytest.raises(budget.BudgetStop) as error:
        send(path, handler)
    stopped = guarded(path, allow_stopped=True, transport=httpx.MockTransport(
        lambda request: pytest.fail("stopped guard sent another request")))
    stopped.stop("arm_failed")
    state = json.loads(path.read_text())
    entry, = state["requests"].values()
    assert entry["failure"] == expected
    assert state["stop_reason"] == expected["kind"]
    assert state["blocked"] and "actual_micros" not in entry and entry["reserved_micros"] == 1200
    assert budget.policy_hash(state) == original_policy
    assert secret not in path.read_text() + str(error.value)
    assert "billing-message-fixture-441892" not in path.read_text()
    assert "billing-key-fixture-4499209" not in path.read_text()
    with pytest.raises(budget.BudgetStop, match="stopped"):
        stopped.check()


def test_concurrent_shutdown_keeps_the_first_provider_failure_and_both_reservations(tmp_path):
    path = ledger(tmp_path)
    arrived = threading.Barrier(2)
    first_failed = threading.Event()

    def first(request):
        arrived.wait(timeout=10)
        return httpx.Response(503)

    def second(request):
        arrived.wait(timeout=10)
        assert first_failed.wait(10)
        raise SystemExit("private interrupted request")

    def run_first():
        try:
            with pytest.raises(budget.BudgetStop):
                send(path, first)
        finally:
            first_failed.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(run_first)
        two = pool.submit(send, path, second)
        one.result()
        with pytest.raises(budget.BudgetStop):
            two.result()
    state = json.loads(path.read_text())
    assert state["blocked"] and state["stop_reason"] == "provider_http_status"
    assert {entry["failure"]["kind"] for entry in state["requests"].values()} == {
        "provider_http_status", "provider_transport"}
    assert all("actual_micros" not in entry for entry in state["requests"].values())
    assert sum(entry["reserved_micros"] for entry in state["requests"].values()) == 2400


@pytest.mark.parametrize("changes", [{"model": "other"}, {"max_tokens": 101}, {"max_tokens": True},
                                    {"max_tokens": 0}, {"stream": True}, {"enable_search": True},
                                    {"tools": [{"type": "web_search"}]},
                                    {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]}])
def test_requests_outside_the_frozen_limits_are_refused_before_network(tmp_path, changes):
    path = ledger(tmp_path)
    with pytest.raises(budget.BudgetStop):
        send(path, lambda request: pytest.fail("invalid request reached provider"), **changes)
    state = json.loads(path.read_text())
    assert not state["requests"] and state["blocked"]
    with pytest.raises(budget.BudgetStop, match="stopped"):
        send(path, lambda request: pytest.fail("a refused request did not stop other arms"))


def test_an_unknown_request_after_a_crash_still_consumes_its_full_reservation(tmp_path):
    path = ledger(tmp_path, "0.0012")
    guard = guarded(path, transport=httpx.MockTransport(reply))
    guard._reserve(httpx.Request("POST", ENDPOINT, json={"model": "host", "max_tokens": 100, "stream": False}))
    with pytest.raises(budget.BudgetStop, match="cap"):
        send(path, lambda request: pytest.fail("crashed reservation was reclaimed"))
    with pytest.raises(budget.BudgetStop, match="never reused"):
        budget.create_ledger(path, run_id="new-run", limit_cny="1", endpoint=ENDPOINT, models=MODELS)


def test_cache_hits_never_lower_the_frozen_maximum_rate(tmp_path):
    path = ledger(tmp_path)
    usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110, "prompt_cache_hit_tokens": 100}
    send(path, lambda request: reply(usage=usage))
    entry, = json.loads(path.read_text())["requests"].values()
    assert entry["actual_micros"] == 120


def test_separate_arm_processes_share_one_cap(tmp_path):
    path = ledger(tmp_path)
    context = multiprocessing.get_context("fork")
    inside, release = context.Barrier(3), context.Event()

    def arm():
        def pending(request):
            inside.wait(timeout=10)
            assert release.wait(10)
            return reply()
        send(path, pending)

    arms = [context.Process(target=arm) for _ in range(2)]
    for process in arms:
        process.start()
    try:
        inside.wait(timeout=10)
        with pytest.raises(budget.BudgetStop, match="cap"):
            send(path, lambda request: pytest.fail("another process bypassed in-flight reservations"))
    finally:
        release.set()
        for process in arms:
            process.join(10)
            if process.is_alive():
                process.kill()
    assert [process.exitcode for process in arms] == [0, 0]


@pytest.mark.parametrize("url", ["https://other.test/chat/completions", ENDPOINT + "/other"])
def test_the_extractor_can_omit_stream_but_another_endpoint_is_refused(tmp_path, url):
    path = ledger(tmp_path)
    guard = guarded(path, transport=httpx.MockTransport(reply))
    with httpx.Client(transport=guard) as client:
        assert client.post(ENDPOINT, json={"model": "host", "max_tokens": 100}).status_code == 200
        with pytest.raises(budget.BudgetStop, match="endpoint"):
            client.post(url, json={"model": "host", "max_tokens": 100})
        with pytest.raises(budget.BudgetStop, match="stopped"):
            client.post(ENDPOINT, json={"model": "host", "max_tokens": 100})


def test_the_provider_version_must_be_explicitly_frozen(tmp_path):
    path = tmp_path / "billing.json"
    models = {"host": {**MODELS["host"], "response_models": ["host-version-reviewed"]}}
    budget.create_ledger(path, run_id="practice", limit_cny="1", endpoint=ENDPOINT, models=models)
    assert send(path, lambda request: reply(model="host-version-reviewed")).status_code == 200


def test_the_real_extractor_request_uses_the_same_transport_and_settlement(tmp_path):
    from membrain.extraction import Extractor

    path = tmp_path / "billing.json"
    models = {"host": {**MODELS["host"], "max_output_tokens": 1200}}
    budget.create_ledger(path, run_id="practice", limit_cny="1", endpoint=ENDPOINT, models=models)

    def extraction(request):
        return reply(choices=[{"message": {"content": '{"notes": []}'}}])

    extractor = Extractor("https://provider.test", "host", "fake-key", transport=guarded(
        path, transport=httpx.MockTransport(extraction)))
    try:
        assert extractor.propose("I prefer tea", "Okay", "") == []
    finally:
        extractor._http.close()
    entry, = json.loads(path.read_text())["requests"].values()
    assert entry["max_tokens"] == 1200 and entry["actual_micros"] == 30


@pytest.mark.parametrize("override", [{"input_cny_per_million": "0"}, {"output_cny_per_million": "NaN"},
                                     {"response_models": "host"}, {"context_tokens": True}])
def test_incomplete_or_ambiguous_frozen_policies_are_refused(tmp_path, override):
    with pytest.raises(budget.BudgetStop):
        budget.create_ledger(tmp_path / "billing.json", run_id="practice", limit_cny="1", endpoint=ENDPOINT,
                             models={"host": {**MODELS["host"], **override}})


def test_a_new_scenario_cannot_switch_ledger_path_attempt_or_rates(tmp_path):
    path = ledger(tmp_path)
    state = json.loads(path.read_text())
    with pytest.raises(budget.BudgetStop, match="frozen attempt"):
        budget.GuardedTransport(path, run_id="another-attempt", policy_sha256=state["policy_sha256"])
    another = tmp_path / "new-ledger.json"
    other = budget.create_ledger(another, run_id="practice", limit_cny="1", endpoint=ENDPOINT, models=MODELS)
    assert other["policy_sha256"] != state["policy_sha256"]
    with pytest.raises(budget.BudgetStop, match="frozen attempt"):
        budget.GuardedTransport(another, run_id="practice", policy_sha256=state["policy_sha256"])
    state["limit_micros"] *= 10
    path.write_text(json.dumps(state))
    with pytest.raises(budget.BudgetStop, match="frozen attempt"):
        budget.GuardedTransport(path, run_id="practice", policy_sha256=state["policy_sha256"])


def test_all_published_output_is_reserved_even_when_the_request_limit_is_smaller(tmp_path):
    path = ledger(tmp_path)
    with pytest.raises(budget.BudgetStop, match="uncertain"):
        send(path, lambda request: reply(), max_tokens=1)
    state = json.loads(path.read_text())
    entry, = state["requests"].values()
    assert entry["reserved_micros"] == 1200 and "actual_micros" not in entry
    assert state["blocked"]


@pytest.mark.parametrize("changes", [{"tools": [None]}, {"messages": {}}, {"messages": "text"},
                                    {"messages": ["text"]}, {"model": []}, {"model": {}},
                                    {"model": None}, {"model": 1}, {"model": True}, {"model": ""}])
def test_malformed_request_shapes_are_structured_stops_before_network(tmp_path, changes):
    path = ledger(tmp_path)
    with pytest.raises(budget.BudgetStop):
        send(path, lambda request: pytest.fail("malformed request reached provider"), **changes)
    state = json.loads(path.read_text())
    assert state["blocked"] and not state["requests"]
    with pytest.raises(budget.BudgetStop, match="stopped"):
        send(path, lambda request: pytest.fail("another arm continued after a malformed request"))


def test_an_idempotent_stop_handle_cannot_send_a_request_or_clear_the_original_reason(tmp_path):
    path = ledger(tmp_path)
    guard = guarded(path, transport=httpx.MockTransport(lambda request: pytest.fail("stopped run reached provider")))
    guard.stop("arm_failed")
    guard.stop("arm_interrupted")
    with pytest.raises(budget.BudgetStop, match="stopped"):
        guard.check()
    stopped = guarded(path, allow_stopped=True, transport=httpx.MockTransport(
        lambda request: pytest.fail("stop-only handle reached provider")))
    stopped.stop("arm_failed")
    with httpx.Client(transport=stopped) as client, pytest.raises(budget.BudgetStop, match="stopped"):
        client.post(ENDPOINT, json={"model": "host", "max_tokens": 100})
    state = json.loads(path.read_text())
    assert state["blocked"] and state["stop_reason"] == "arm_failed" and not state["requests"]
