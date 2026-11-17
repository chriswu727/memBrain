"""Transient provider failures (since 2026-11-17), with fake transports only: no network, no service, no database,
no model. The billing guard settles a request interrupted in transport, or answered with HTTP 429 or a 5xx, at a
bound that is true for that request and leaves the ledger open; the C5 host client sends the same request again after
30 and 120 seconds, three sends at most, and records each interrupted send in provider-interruptions.jsonl; validity
and diagnose report them by position and code only. Every other failure still stops the run as before."""
import importlib.util
import json
import multiprocessing
import random
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SECRET = "zq-interruption-secret-5521"  # Planted in every provider body, exception and session id.


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load("c5_harness_interruptions", ROOT / "evaluations" / "c5-harness.py")
budget = harness.billing_module()
POLICY = json.loads((ROOT / "evaluations" / "maturity-provider-policy-2026-11-14.json").read_text())
RATE = {**POLICY["models"]["deepseek-v4-pro"], "response_models": [harness.MODEL]}
ENDPOINT = harness.BASE_URL + "/chat/completions"
RESERVATION, LIMIT = 20_054_016, 80_000_000  # Micro-CNY: the policy's full reservation and its 80 CNY limit.
MESSAGES = [{"role": "system", "content": "You are a companion. Heute ist Dienstag. 今天是3月3日。"},
            {"role": "user", "content": f"Ich bin müde. 我有点累。 {SECRET}"}]
TOOLS = [{"type": "function", "function": {"name": "memory_recall", "description": "Recall what the user said.",
                                            "parameters": {"type": "object", "properties": {
                                                "query": {"type": "string", "description": "Wörter oder 词语"}}}}}]
AT = {"session": f"{SECRET}-session", "turn": 2, "round": 1, "where": "session 1 of 3, message 3"}


def ledger(tmp_path, limit=None):
    path = tmp_path / "ledger.json"
    budget.create_ledger(path, run_id="interruption-practice", limit_cny=limit or POLICY["proposed_limit_cny"],
                         endpoint=ENDPOINT, models={harness.MODEL: RATE})
    return path


def guard(path, handler):
    state = json.loads(path.read_text())
    return budget.GuardedTransport(path, run_id="interruption-practice", policy_sha256=state["policy_sha256"],
                                   transport=httpx.MockTransport(handler))


def state(path):
    return json.loads(path.read_text())


def expected_bound(body: bytes, tools) -> int:
    """The stated formula, computed here independently of the guard."""
    schema = len(json.dumps(tools, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) if tools else 0
    prompt = min(1_048_576, 2 * len(body) + 4 * schema + 16_384)
    return prompt * 9 + 16_384 * 27  # 9 and 27 CNY per million tokens: 9 and 27 micro-CNY per token.


class Provider:
    """A fake provider: the given failures on the first sends, then a billed reply."""

    def __init__(self, *failures):
        self.failures, self.bodies = list(failures), []

    def __call__(self, request):
        self.bodies.append(request.content)
        failure = self.failures.pop(0) if self.failures else None
        if isinstance(failure, int):
            return httpx.Response(failure, content=SECRET.encode(), headers={"x-private": SECRET})
        if isinstance(failure, tuple):  # (status, exception class): the body is cut short after the status.
            status, error = failure

            class CutBody(httpx.SyncByteStream):
                def __iter__(self):
                    yield SECRET.encode()
                    raise error(SECRET, request=request)
            return httpx.Response(status, stream=CutBody())
        if failure == "malformed":
            return httpx.Response(200, content=SECRET.encode())
        if failure == "other_model":
            return reply(model=SECRET)
        if failure == "system_exit":
            raise SystemExit(SECRET)
        if failure == "keyboard":
            raise KeyboardInterrupt(SECRET)
        if failure == "unknown":
            raise type(SECRET.replace("-", "_"), (RuntimeError,), {})(SECRET)
        if failure is not None:
            raise failure(SECRET, request=request)
        return reply()


def reply(model=None):
    return httpx.Response(200, json={
        "model": model or harness.MODEL, "choices": [{"message": {"role": "assistant", "content": "Fake reply."}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})


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


def interruptions(out):
    path = out / harness.INTERRUPTIONS
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# The host client retries an interrupted send ----------------------------------------------------------------------

def test_a_timeout_then_success_is_charged_at_its_bound_and_the_reply_is_used(tmp_path, live, capsys):
    path = ledger(tmp_path)
    provider = Provider(httpx.ReadTimeout)
    host = host_for(path, provider, tmp_path)
    message, usage = host.call(MESSAGES, TOOLS, at=AT)
    assert message["content"] == "Fake reply." and usage["total_tokens"] == 150
    assert host.calls == 2 and live == [30] and provider.bodies[0] == provider.bodies[1]  # The same request again.
    ledger_state = state(path)
    assert ledger_state["blocked"] is False and "stop_reason" not in ledger_state
    interrupted, settled = sorted(ledger_state["requests"].values(), key=lambda entry: "interrupted" not in entry)
    bound = expected_bound(provider.bodies[0], TOOLS)
    assert interrupted["interrupted"] == {"kind": "provider_transport", "error_class": "ReadTimeout",
                                          "prompt_tokens_bound": 2 * len(provider.bodies[0]) + 4 * budget.tools_bytes(
                                              TOOLS) + 16_384, "completion_tokens_bound": 16_384}
    assert interrupted["actual_micros"] == bound < 1_000_000 and interrupted["reserved_micros"] == RESERVATION
    assert "failure" not in interrupted and settled["actual_micros"] == 100 * 9 + 50 * 27
    assert SECRET not in path.read_text()
    (line,) = interruptions(tmp_path)
    assert set(line) == {"format", "time", "session", "turn", "round", "kind", "error_class", "send", "retried"}
    assert {key: line[key] for key in ("format", "turn", "round", "kind", "error_class", "send", "retried")} == {
        "format": 1, "turn": 2, "round": 1, "kind": "provider_transport", "error_class": "ReadTimeout", "send": 1,
        "retried": True}
    assert not (tmp_path / "harness-events.jsonl").exists()  # A retried interruption is not a harness event.
    out = capsys.readouterr().out
    assert "provider interrupted ReadTimeout at session 1 of 3, message 3, round 2: send 1 of 3, retry in 30 s" in out
    assert SECRET not in out and "api.deepseek.com" not in out


@pytest.mark.parametrize("first,second", [(httpx.ReadTimeout, 503), (429, httpx.ConnectError), (502, 500)])
def test_two_interruptions_then_success_wait_30_then_120_seconds(tmp_path, live, first, second):
    path = ledger(tmp_path)
    provider = Provider(first, second)
    host = host_for(path, provider, tmp_path)
    message, _ = host.call(MESSAGES, TOOLS, at=AT)
    assert message["content"] == "Fake reply." and host.calls == 3 and live == [30, 120]
    assert len(set(provider.bodies)) == 1
    ledger_state = state(path)
    assert ledger_state["blocked"] is False and len(ledger_state["requests"]) == 3
    bounds = [entry["actual_micros"] for entry in ledger_state["requests"].values() if "interrupted" in entry]
    assert bounds == [expected_bound(provider.bodies[0], TOOLS)] * 2
    assert [(line["send"], line["retried"]) for line in interruptions(tmp_path)] == [(1, True), (2, True)]


@pytest.mark.parametrize("failure,reason", [(httpx.ReadTimeout, "provider_transport"),
                                            (503, "provider_http_status"), (429, "provider_http_status")])
def test_three_interruptions_block_the_ledger_and_stop_the_arm_as_before(tmp_path, live, capsys, failure, reason):
    path = ledger(tmp_path)
    provider = Provider(failure, failure, failure, None)
    host = host_for(path, provider, tmp_path)
    with pytest.raises(budget.BudgetStop, match="every send") as stopped:
        host.call(MESSAGES, TOOLS, at=AT)
    assert not isinstance(stopped.value, budget.ProviderInterrupted) and stopped.value.__suppress_context__
    assert len(provider.bodies) == 3 and host.calls == 3 and live == [30, 120]
    ledger_state = state(path)
    assert ledger_state["blocked"] is True and ledger_state["stop_reason"] == reason
    assert all(entry["actual_micros"] == expected_bound(provider.bodies[0], TOOLS)
               for entry in ledger_state["requests"].values())
    assert [(line["send"], line["retried"]) for line in interruptions(tmp_path)] == [(1, True), (2, True), (3, False)]
    with pytest.raises(budget.BudgetStop, match="stopped"):
        guard(path, provider).check()
    with pytest.raises(budget.BudgetStop, match="stopped"):
        host.call(MESSAGES, TOOLS, at=AT)  # No fourth send reaches the provider.
    assert len(provider.bodies) == 3
    assert "no retry left: the ledger is blocked and the arm stops" in capsys.readouterr().out


def test_the_call_cap_counts_every_retry(tmp_path, live):
    path = ledger(tmp_path)
    provider = Provider(httpx.ReadTimeout, httpx.ReadTimeout)
    host = host_for(path, provider, tmp_path, cap=2)
    with pytest.raises(RuntimeError, match="host call cap reached"):
        host.call(MESSAGES, TOOLS, at=AT)
    assert len(provider.bodies) == 2 and host.calls == 2 and live == [30]
    assert state(path)["blocked"] is True and state(path)["stop_reason"] == "provider_transport"
    assert [(line["send"], line["retried"]) for line in interruptions(tmp_path)] == [(1, True), (2, False)]
    # A retried send is counted like any call: two calls used, so the next host call is refused before sending.
    other = Provider(httpx.ReadTimeout)
    (tmp_path / "second").mkdir()
    second = host_for(ledger(tmp_path / "second"), other, tmp_path / "second", cap=3)
    second.call(MESSAGES, None, at=AT)
    assert second.calls == 2
    second.call(MESSAGES, None, at=AT)
    with pytest.raises(RuntimeError, match="host call cap reached"):
        second.call(MESSAGES, None, at=AT)
    assert len(other.bodies) == 3


def test_interruption_retries_are_separate_from_the_empty_reply_retries(tmp_path, live):
    path = ledger(tmp_path)
    calls = []

    def provider(request):
        calls.append(request.content)
        if len(calls) == 1:
            raise httpx.ReadTimeout(SECRET, request=request)
        if len(calls) <= 4:  # Three empty replies, then a reply.
            return httpx.Response(200, json={"model": harness.MODEL, "choices": [{"message": {"content": " "}}],
                                             "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        return reply()

    host = host_for(path, provider, tmp_path)
    message, _ = host.call(MESSAGES, None, at=AT)
    assert message["content"] == "Fake reply." and host.calls == 5 and live == [30, 10, 20, 30]
    assert state(path)["blocked"] is False


# What stays fatal ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("failure,cause", [
    (400, {"kind": "provider_http_status", "http_status": 400}),
    (401, {"kind": "provider_http_status", "http_status": 401}),
    (403, {"kind": "provider_http_status", "http_status": 403}),
    (422, {"kind": "provider_http_status", "http_status": 422}),
    ((400, httpx.ReadTimeout), {"kind": "provider_transport", "error_class": "ReadTimeout"}),
    (httpx.DecodingError, {"kind": "provider_transport", "error_class": "DecodingError"}),
    (httpx.LocalProtocolError, {"kind": "provider_transport", "error_class": "LocalProtocolError"}),
    (httpx.ProxyError, {"kind": "provider_transport", "error_class": "ProxyError"}),
    (httpx.UnsupportedProtocol, {"kind": "provider_transport", "error_class": "UnsupportedProtocol"}),
    ("system_exit", {"kind": "provider_transport", "error_class": "SystemExit"}),
    ("keyboard", {"kind": "provider_transport", "error_class": "KeyboardInterrupt"}),
    ("unknown", {"kind": "provider_transport", "error_class": "other"}),
    ("malformed", {"kind": "response_billing"}),
    ("other_model", {"kind": "response_billing"}),
])
def test_other_failures_keep_the_reservation_block_the_ledger_and_are_never_retried(tmp_path, live, failure, cause):
    path = ledger(tmp_path)
    provider = Provider(failure)
    host = host_for(path, provider, tmp_path)
    with pytest.raises(budget.BudgetStop) as stopped:
        host.call(MESSAGES, TOOLS, at=AT)
    assert not isinstance(stopped.value, budget.ProviderInterrupted)
    assert len(provider.bodies) == 1 and live == [] and not interruptions(tmp_path)
    ledger_state = state(path)
    (entry,) = ledger_state["requests"].values()
    assert ledger_state["blocked"] is True and ledger_state["stop_reason"] == cause["kind"]
    assert entry["failure"] == cause and "actual_micros" not in entry and "interrupted" not in entry
    assert entry["reserved_micros"] == RESERVATION and SECRET not in path.read_text() + str(stopped.value)


def test_a_guard_refusal_for_headroom_is_fatal_and_never_retried(tmp_path, live):
    path = ledger(tmp_path, limit="20")  # Below one full reservation: the first request is refused before HTTP.
    provider = Provider()
    host = host_for(path, provider, tmp_path)
    with pytest.raises(budget.BudgetStop, match="cap"):
        host.call(MESSAGES, TOOLS, at=AT)
    assert provider.bodies == [] and live == [] and state(path)["stop_reason"] == "reservation_limit"


def test_a_request_without_max_tokens_never_reaches_the_provider(tmp_path):
    path = ledger(tmp_path)
    transport = guard(path, Provider(httpx.ReadTimeout))
    with httpx.Client(transport=transport) as client, pytest.raises(budget.BudgetStop):
        client.post(ENDPOINT, json={"model": harness.MODEL, "stream": False, "messages": MESSAGES})
    assert state(path)["blocked"] and state(path)["stop_reason"] == "request_refused" and not state(path)["requests"]


@pytest.mark.parametrize("max_tokens", [None, 0, True, "16384", 393_217])
def test_no_bound_without_a_usable_max_tokens(max_tokens):
    with pytest.raises(budget.BudgetStop):
        budget.interruption_bound(1000, 0, max_tokens, RATE)


def test_an_interruption_without_a_computable_bound_keeps_the_old_stop(tmp_path, live, monkeypatch):
    def unknown(*args):
        raise budget.BudgetStop("no bound")

    monkeypatch.setattr(budget, "interruption_bound", unknown)
    path = ledger(tmp_path)
    provider = Provider(httpx.ReadTimeout)
    host = host_for(path, provider, tmp_path)
    with pytest.raises(budget.BudgetStop, match="retains its billing reservation"):
        host.call(MESSAGES, TOOLS, at=AT)
    (entry,) = state(path)["requests"].values()
    assert state(path)["blocked"] and state(path)["stop_reason"] == "provider_transport"
    assert entry["failure"] == {"kind": "provider_transport", "error_class": "ReadTimeout"}
    assert "actual_micros" not in entry and len(provider.bodies) == 1 and live == []


def test_an_old_reservation_without_sizes_keeps_the_old_stop(tmp_path):
    path = ledger(tmp_path)
    transport = guard(path, Provider())
    ident = transport._reserve(httpx.Request("POST", ENDPOINT, json={"model": harness.MODEL, "max_tokens": 16384}))
    ledger_state = state(path)
    del ledger_state["requests"][ident]["tools_bytes"]
    path.write_text(json.dumps(ledger_state))
    failure = {"kind": "provider_transport", "error_class": "ReadTimeout"}
    with pytest.raises(budget.BudgetStop, match="retains"):
        transport._interrupted(ident, failure)
    assert state(path)["blocked"] and state(path)["requests"][ident]["failure"] == failure


# The guard alone ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("failure,cause", [
    *[(status, {"kind": "provider_http_status", "http_status": status}) for status in (429, 500, 502, 503, 504, 599)],
    *[(error, {"kind": "provider_transport", "error_class": error.__name__}) for error in (
        httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout, httpx.PoolTimeout, httpx.ConnectError,
        httpx.ReadError, httpx.WriteError, httpx.CloseError, httpx.RemoteProtocolError)],
    ((200, httpx.ReadTimeout), {"kind": "provider_transport", "error_class": "ReadTimeout"}),
    ((503, httpx.RemoteProtocolError), {"kind": "provider_transport", "error_class": "RemoteProtocolError"}),
])
def test_the_guard_settles_each_interruption_at_its_bound_and_leaves_the_ledger_open(tmp_path, failure, cause):
    path = ledger(tmp_path)
    provider = Provider(failure)
    with httpx.Client(transport=guard(path, provider)) as client:
        with pytest.raises(budget.ProviderInterrupted) as interrupted:
            client.post(ENDPOINT, json={"model": harness.MODEL, "max_tokens": 16384, "stream": False,
                                        "messages": MESSAGES, "tools": TOOLS})
        assert interrupted.value.failure == cause and interrupted.value.__context__ is None
        assert SECRET not in str(interrupted.value)
        (entry,) = state(path)["requests"].values()
        assert entry["actual_micros"] == expected_bound(provider.bodies[0], TOOLS)
        assert {key: entry["interrupted"][key] for key in cause} == cause and "failure" not in entry
        assert state(path)["blocked"] is False and SECRET not in path.read_text()
        assert client.post(ENDPOINT, json={"model": harness.MODEL, "max_tokens": 16384,
                                           "messages": MESSAGES}).status_code == 200


# The bound never undercounts ----------------------------------------------------------------------------------------

ENGLISH = "I moved to Lisbon for a design job and my sister visits on the fourteenth. "
GERMAN = "Heute ist Dienstag, der 3. März; ich bin müde, aber glücklich. Grüße! "
CHINESE = "今天是三月三日，我搬到了里斯本，妹妹十四号来看我。"
OTHER = "😀🎉 ẞ ﬁ ​ ‍ <membrain-persona> & \"quotes\" \\ \n\t"


def _text(generator, size):
    pieces = [ENGLISH, GERMAN, CHINESE, OTHER]
    weights = generator.choice([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1), (3, 2, 2, 1)])
    text = ""
    while len(text) < size:
        piece = generator.choices(pieces, weights)[0]
        text += piece[generator.randrange(len(piece)):] if generator.random() < 0.3 else piece
    return text[:size]


def _schemas(generator):
    tools = []
    for number in range(generator.randrange(0, 15)):
        properties = {f"field_{index}": {"type": generator.choice(["string", "integer", "array"]),
                                         "description": _text(generator, generator.randrange(1, 300))}
                      for index in range(generator.randrange(0, 6))}
        tools.append({"type": "function", "function": {
            "name": f"memory_tool_{number}", "description": _text(generator, generator.randrange(1, 1200)),
            "parameters": {"type": "object", "properties": properties, "required": sorted(properties)[:1]}}})
    return tools


def _worst_prompt_tokens(body: dict) -> int:
    """The most tokens a provider could count for this request, on a tokenizer with no merges (one token per UTF-8
    byte, the worst case of byte-level BPE): every string of the messages rendered as sent with sixteen marker tokens
    per message, the tool schemas re-serialized in the most expansive common forms (ASCII-only escapes, indentation,
    HTML-safe escaping of < > & '), and a 4,096-token template preamble."""
    tokens = 4096
    for message in body["messages"]:
        tokens += 16 + sum(len(str(value).encode()) for key, value in message.items() if key != "tool_calls")
        for call in message.get("tool_calls") or ():
            tokens += 16 + len(json.dumps(call, ensure_ascii=False).encode())
    if body.get("tools"):
        rendered = json.dumps(body["tools"], ensure_ascii=True, indent=2)
        escaped = json.dumps(body["tools"], ensure_ascii=True)
        for char, code in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("'", "\\u0027")):
            escaped = escaped.replace(char, code)
        tokens += max(len(rendered.encode()), len(escaped.encode()))
    return tokens


def test_the_bound_is_never_below_what_the_provider_could_charge_and_never_above_the_reservation():
    generator = random.Random(20261117)
    for _ in range(400):
        messages = [{"role": "system", "content": _text(generator, generator.randrange(1, 20_000))}]
        for _ in range(generator.randrange(0, 12)):
            messages.append({"role": "user", "content": _text(generator, generator.randrange(1, 4000))})
            message = {"role": "assistant", "content": _text(generator, generator.randrange(0, 4000))}
            if generator.random() < 0.3:
                message["reasoning_content"] = _text(generator, generator.randrange(0, 4000))
                message["tool_calls"] = [{"id": "call-1", "type": "function", "function": {
                    "name": "memory_note", "arguments": json.dumps({"text": _text(generator, 200)})}}]
                messages.append(message)
                message = {"role": "tool", "tool_call_id": "call-1", "content": _text(generator, 2000)}
            messages.append(message)
        body = {"model": harness.MODEL, "messages": messages, "max_tokens": 16384, "stream": False,
                "thinking": {"type": "enabled"}}
        tools = _schemas(generator)
        if tools:
            body["tools"] = tools
        sent = httpx.Request("POST", ENDPOINT, json=body).content  # The bytes the host client sends.
        prompt, completion, charge = budget.interruption_bound(len(sent), budget.tools_bytes(tools), 16384, RATE)
        worst = _worst_prompt_tokens(body)
        assert prompt >= min(worst, RATE["context_tokens"]), (len(sent), worst, prompt)
        assert charge >= min(worst, RATE["context_tokens"]) * 9 + 16384 * 27
        assert completion == 16384 and charge <= RESERVATION


def test_the_bound_of_chinese_german_and_english_text_covers_one_token_per_byte():
    for text in (ENGLISH * 200, GERMAN * 200, CHINESE * 200, OTHER * 200):
        body = {"model": harness.MODEL, "max_tokens": 16384, "messages": [{"role": "user", "content": text}]}
        sent = httpx.Request("POST", ENDPOINT, json=body).content
        prompt, _, _ = budget.interruption_bound(len(sent), 0, 16384, RATE)
        assert prompt >= 2 * len(text.encode("utf-8")) + 16_384  # At least two tokens per byte of the text.


def test_the_bound_is_capped_at_the_context_and_the_charge_at_the_reservation():
    prompt, completion, charge = budget.interruption_bound(10_000_000, 0, 393_216, RATE)
    assert (prompt, completion, charge) == (1_048_576, 393_216, RESERVATION)


# The refusal point with interrupted settlements ---------------------------------------------------------------------

BODY = {"model": harness.MODEL, "max_tokens": 16384, "stream": False, "messages": MESSAGES}


def _send(path, handler):
    with httpx.Client(transport=guard(path, handler)) as client:
        return client.post(ENDPOINT, json=BODY)


def _billed(prompt):
    def handler(request):
        return httpx.Response(200, json={"model": harness.MODEL, "usage": {
            "prompt_tokens": prompt, "completion_tokens": 0, "total_tokens": prompt}})
    return handler


def test_the_refusal_point_counts_an_interruption_at_its_bound_not_its_reservation(tmp_path):
    path = ledger(tmp_path)
    bound = expected_bound(httpx.Request("POST", ENDPOINT, json=BODY).content, None)
    target = LIMIT - RESERVATION - bound  # Settled so far, so that the interruption brings it to the refusal point.
    settled = 0
    while target - settled >= 9:
        tokens = min(888_888, (target - settled) // 9)
        assert _send(path, _billed(tokens)).status_code == 200
        settled += tokens * 9
    assert target - 9 < settled <= target
    with pytest.raises(budget.ProviderInterrupted):
        _send(path, Provider(httpx.ReadTimeout))
    used = sum(entry["actual_micros"] for entry in state(path)["requests"].values())
    assert used == settled + bound and LIMIT - RESERVATION - 9 < used <= LIMIT - RESERVATION
    # Had the interruption kept its reservation, this request would already be refused.
    assert settled + RESERVATION + RESERVATION > LIMIT
    assert _send(path, _billed(10)).status_code == 200  # Within the limit with its full reservation.
    with pytest.raises(budget.BudgetStop, match="cap"):
        _send(path, lambda request: pytest.fail("a request past the refusal point reached the provider"))
    assert state(path)["blocked"] and state(path)["stop_reason"] == "reservation_limit"


def test_an_interrupted_reservation_in_flight_still_counts_in_full(tmp_path):
    """Until it settles, an interrupted request holds its whole reservation, like any request in flight."""
    path = ledger(tmp_path, limit="20.054016")  # Room for exactly one full reservation.
    seen = []

    def interrupted(request):
        seen.append(state(path)["requests"])
        with pytest.raises(budget.BudgetStop, match="cap"):
            _send(path, Provider())  # Refused: the interrupted request still holds its whole reservation.
        raise httpx.ReadTimeout(SECRET, request=request)

    with pytest.raises(budget.ProviderInterrupted):
        _send(path, interrupted)
    assert len(seen[0]) == 1 and state(path)["stop_reason"] == "reservation_limit"
    (entry,) = state(path)["requests"].values()  # Settled at its bound once it ended; the refusal's stop stands.
    assert entry["actual_micros"] < RESERVATION and state(path)["blocked"]


# Two arm processes on one ledger, one interrupted --------------------------------------------------------------------

def test_two_arm_processes_share_one_ledger_through_an_interruption(tmp_path, live):
    path = ledger(tmp_path)
    context = multiprocessing.get_context("fork")
    inside, release = context.Barrier(3), context.Event()

    def arm(name, failures):
        out = tmp_path / name
        out.mkdir()
        sends = []

        def provider(request):
            sends.append(1)
            if len(sends) == 1:
                inside.wait(timeout=10)  # Both arms' first sends in flight at once.
                assert release.wait(10)
            if failures:
                raise failures.pop(0)(SECRET, request=request)
            return reply()

        host = host_for(path, provider, out)
        for _ in range(2):
            assert host.call(MESSAGES, TOOLS, at=AT)[0]["content"] == "Fake reply."

    arms = [context.Process(target=arm, args=("a", [httpx.ReadTimeout])), context.Process(target=arm, args=("b", []))]
    for process in arms:
        process.start()
    try:
        inside.wait(timeout=10)
        in_flight = state(path)["requests"]
        assert len(in_flight) == 2 and all("actual_micros" not in entry for entry in in_flight.values())
    finally:
        release.set()
        for process in arms:
            process.join(20)
            if process.is_alive():
                process.kill()
    assert [process.exitcode for process in arms] == [0, 0]
    ledger_state = state(path)
    assert ledger_state["blocked"] is False and len(ledger_state["requests"]) == 5
    interrupted = [entry for entry in ledger_state["requests"].values() if "interrupted" in entry]
    assert len(interrupted) == 1 and all("actual_micros" in entry for entry in ledger_state["requests"].values())
    assert [line["send"] for line in interruptions(tmp_path / "a")] == [1] and not interruptions(tmp_path / "b")
    used = sum(entry["actual_micros"] for entry in ledger_state["requests"].values())
    assert used == interrupted[0]["actual_micros"] + 4 * (100 * 9 + 50 * 27)


# Validity and diagnose ------------------------------------------------------------------------------------------------

review = _load("acceptance_review_interruptions", ROOT / "evaluations" / "acceptance_review.py")
SESSIONS = [(f"{SECRET}-a", [f"Today is Monday, March 2, 20:00. {SECRET} one", f"{SECRET} two"]),
            (f"{SECRET}-b", [f"Today is Tuesday, March 3, 23:00. {SECRET} three", f"{SECRET} four"])]


def world(tmp_path, lines=None):
    """A complete two-arm R4-shaped run with provider-interruptions.jsonl in P, as the harness writes it."""
    scenario = tmp_path / "zq_interruptions.py"
    scenario.write_text(f"SESSIONS_LONG = {SESSIONS!r}\n")
    runs = []
    for number, arm in enumerate("PF"):
        run = tmp_path / f"k-{arm}"
        run.mkdir()
        rows = [{"arm": arm, "scenario": scenario.stem, "session": session, "turn": index, "reply": "Hello",
                 "usage": {"prompt_tokens": 1}} for session, turns in SESSIONS for index in range(len(turns))]
        (run / f"results_{scenario.stem}_{arm}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (run / "run.log").write_text(
            f"12:00:00 provider interrupted ReadTimeout at session 2 of 2, message 1, round 1: send 1 of 3, retry in "
            f"30 s\n12:00:01 {arm} {scenario.stem} finished\n")
        (run / "persona.json").write_text(json.dumps({"arm": arm, "source": "seeded", "seed": "x", "preset": "enfp",
                                                      "card_sha256": "enfp", "version": 1}))
        start = 10 + 20 * number
        (run / "supervisor.log").write_text(f"started {start}\nfinished {start + 5}\ncleaned {start + 6}\n")
        if arm == "P" and lines is not None:
            (run / harness.INTERRUPTIONS).write_text("".join(
                (line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines))
        runs.append(run)
    return scenario, runs


def line(session, turn, round_, send, retried, **cause):
    cause = cause or {"error_class": "ReadTimeout"}
    kind = "provider_http_status" if "http_status" in cause else "provider_transport"
    return {"format": 1, "time": 1.5, "session": session, "turn": turn, "round": round_, "kind": kind, **cause,
            "send": send, "retried": retried}


RETRIED = [line(f"{SECRET}-b", 0, 0, 1, True), line(f"{SECRET}-b", 0, 0, 2, True, http_status=503),
           line(f"{SECRET}-a", 1, 2, 1, True, http_status=429)]


def test_validity_reports_retried_interruptions_by_position_and_stays_valid(tmp_path, capsys):
    scenario, runs = world(tmp_path, RETRIED)
    result = review.validity(runs, scenario, persona_preset="enfp")
    assert result["valid"], result["problems"]
    assert result["provider_interruptions"] == {
        "k-P (P)": {"interrupted_sends": 3, "retried_host_calls": 2, "not_retried": 0, "at": [
            {"session": 2, "message": 1, "round": 1, "send": 1, "code": "ReadTimeout", "retried": True},
            {"session": 2, "message": 1, "round": 1, "send": 2, "code": "http_503", "retried": True},
            {"session": 1, "message": 2, "round": 3, "send": 1, "code": "http_429", "retried": True}]},
        "k-F (F)": {"interrupted_sends": 0, "retried_host_calls": 0, "not_retried": 0, "at": []}}
    assert SECRET not in capsys.readouterr().out


@pytest.mark.parametrize("bad", [
    "{broken " + SECRET,
    line(f"{SECRET}-a", 0, 0, 1, True, error_class=SECRET),
    line(f"{SECRET}-a", 0, 0, 1, True, http_status=400),
    line(f"{SECRET}-a", 0, 0, 3, True),
    line(f"{SECRET}-a", 0, 4, 1, True),
    line(f"{SECRET}-c", 0, 0, 1, True),
    {**line(f"{SECRET}-a", 0, 0, 1, True), "message": SECRET},
    {**line(f"{SECRET}-a", 0, 0, 1, True), "format": 2},
    RETRIED[0],  # A repeated send of the same host call.
])
def test_validity_refuses_malformed_interruption_evidence(tmp_path, capsys, bad):
    scenario, runs = world(tmp_path, [RETRIED[0], bad])
    result = review.validity(runs, scenario, persona_preset="enfp")
    assert not result["valid"] and any("provider-interruptions.jsonl is malformed at line 2" in problem
                                       for problem in result["problems"])
    assert SECRET not in capsys.readouterr().out


def test_validity_refuses_an_interruption_that_was_not_retried(tmp_path, capsys):
    scenario, runs = world(tmp_path, [line(f"{SECRET}-b", 1, 0, 3, False)])
    result = review.validity(runs, scenario, persona_preset="enfp")
    assert not result["valid"] and any("not retried at session 2, message 2, round 1" in problem
                                       for problem in result["problems"])
    assert SECRET not in capsys.readouterr().out


def test_diagnose_prints_interruptions_as_counts_positions_and_codes_only(tmp_path, capsys):
    scenario, runs = world(tmp_path, [*RETRIED, "{broken " + SECRET])
    with (runs[0] / "run.log").open("a") as stream:
        stream.write(f"12:00:02 provider interrupted {SECRET}Error at {SECRET}\n")
    review.diagnose(runs, scenario)
    out = capsys.readouterr().out
    assert SECRET.casefold() not in out.casefold(), out
    assert ("provider interruptions (settled at their bound; a retried one leaves the run valid): 3 sends, 2 host "
            "calls sent again, 0 not retried at session 2 of 2, message 1, round 1, send 1 ReadTimeout retried; "
            "session 2 of 2, message 1, round 1, send 2 http_503 retried; session 1 of 2, message 2, round 3, send 1 "
            "http_429 retried") in out
    assert "malformed provider-interruption lines: 1" in out
    assert "log: provider interrupted ReadTimeout: 1" in out and "log: provider interrupted other: 1" in out


def test_the_review_and_the_guard_agree_on_the_interruption_classes():
    assert review.INTERRUPTED_CLASSES == budget.INTERRUPTED_CLASSES
    assert review.INTERRUPTION_SENDS == len(harness.INTERRUPTION_WAITS) + 1
    assert review.INTERRUPTIONS == harness.INTERRUPTIONS and harness.INTERRUPTION_WAITS == (30, 120)
