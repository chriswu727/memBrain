"""Evaluation-only billing reservations. Never authorizes a model run."""
import contextlib
import decimal
import fcntl
import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

import httpx

_ERROR_CLASSES = {getattr(httpx, name): name for name in (
    "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout", "TimeoutException",
    "ConnectError", "ReadError", "WriteError", "CloseError", "RemoteProtocolError",
    "LocalProtocolError", "ProxyError", "UnsupportedProtocol", "DecodingError", "HTTPError")}
_ERROR_CLASSES.update({SystemExit: "SystemExit", KeyboardInterrupt: "KeyboardInterrupt"})
# Interruptions (since 2026-11-17): a request that ended in one of these transport failures, or with HTTP 429 or a
# 5xx, is settled at a bound that is true for that request (``interruption_bound``) and the ledger stays open, so the
# caller may send it again. Every other failure keeps the whole reservation and blocks the ledger, as before:
# another HTTP status, a response the guard cannot settle, SystemExit, KeyboardInterrupt and any class not listed.
INTERRUPTED_CLASSES = frozenset({
    "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout", "TimeoutException",
    "ConnectError", "ReadError", "WriteError", "CloseError", "RemoteProtocolError"})
# The prompt bound of an interrupted request, in tokens (``interruption_bound``): twice the bytes of the request body
# as sent, plus four times the bytes of its tool schemas in their shortest JSON form, plus a fixed allowance for the
# text the provider adds (chat template, role markers, tool preamble), never above the context bound. Every token of
# a byte-level tokenizer stands for at least one UTF-8 byte of the text it encodes, in any language, so a prompt has
# no more tokens than bytes. Message text is rendered as sent, and the body holds every byte of it; a tool schema may
# be re-serialized, and JSON escaping writes at most six bytes for each byte of the shortest form (2 + 4 = 6 times
# for the schemas). The reasoning is in evaluation-billing.md.
PROMPT_TOKENS_PER_BYTE = 2
PROMPT_TOKENS_PER_TOOL_BYTE = 4
PROMPT_TOKENS_ALLOWANCE = 16_384


class BudgetStop(RuntimeError):
    pass


class ProviderInterrupted(BudgetStop):
    """A request interrupted in transport or answered with HTTP 429 or a 5xx: settled at its bound, the ledger still
    open. ``failure`` holds the content-free cause: ``kind`` and ``error_class`` or ``http_status``."""

    def __init__(self, failure: dict):
        super().__init__("An interrupted provider request is charged at its bound; the billing run stays open.")
        self.failure = dict(failure)


def retriable_status(status) -> bool:
    """HTTP 429 and every 5xx: an answer that a later identical request may not get again."""
    return type(status) is int and (status == 429 or 500 <= status <= 599)


def tools_bytes(tools) -> int:
    """The UTF-8 bytes of a request's tool schemas in their shortest JSON form (0 without tools)."""
    return len(json.dumps(tools, ensure_ascii=False, separators=(",", ":")).encode()) if tools else 0


def interruption_bound(request_bytes, schema_bytes, max_tokens, rate) -> tuple[int, int, int]:
    """(prompt token bound, completion token bound, charge in micro-CNY) of an interrupted request whose body was
    ``request_bytes`` bytes with ``schema_bytes`` of tool schemas (``tools_bytes``), at the request's own
    ``max_tokens``, at the policy's maximum rates:

        prompt = min(context_tokens, 2 * request_bytes + 4 * schema_bytes + 16,384)
        charge = ceil(prompt * input rate) + ceil(max_tokens * output rate)

    Raises BudgetStop when it cannot be computed; the caller then keeps the whole reservation."""
    request_bytes, schema_bytes, max_tokens = _integer(request_bytes), _integer(schema_bytes), _integer(max_tokens)
    context, output = _integer(rate["context_tokens"]), _integer(rate["max_output_tokens"])
    if not request_bytes or schema_bytes > request_bytes or not 0 < max_tokens <= output:
        raise BudgetStop("No bound for this interrupted request.")
    prompt = min(context, PROMPT_TOKENS_PER_BYTE * request_bytes + PROMPT_TOKENS_PER_TOOL_BYTE * schema_bytes
                 + PROMPT_TOKENS_ALLOWANCE)
    return prompt, max_tokens, _charge(prompt, rate["input_cny_per_million"]) + _charge(
        max_tokens, rate["output_cny_per_million"])


def _integer(value):
    if type(value) is not int or value < 0:
        raise BudgetStop("Invalid billing count.")
    return value


def _charge(tokens, rate):
    try:
        value = decimal.Decimal(rate)
    except (decimal.InvalidOperation, TypeError, ValueError):
        raise BudgetStop("Invalid frozen billing rate.") from None
    if not value.is_finite() or value < 0:
        raise BudgetStop("Invalid frozen billing rate.")
    return int((tokens * value).to_integral_value(rounding=decimal.ROUND_CEILING))


def policy_hash(state):
    policy = {key: state[key] for key in ("version", "run_id", "ledger_path", "limit_micros", "endpoint", "models")}
    return hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _write(path, state):
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as file:
            json.dump(state, file, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextlib.contextmanager
def _locked(path):
    with path.with_suffix(path.suffix + ".lock").open("a") as file:
        os.chmod(file.name, 0o600)
        fcntl.flock(file, fcntl.LOCK_EX)
        yield


def create_ledger(path, *, run_id, limit_cny, endpoint, models):
    path = Path(path)
    if not path.is_absolute():
        raise BudgetStop("The shared billing ledger needs an absolute path.")
    limit = _charge(1_000_000, limit_cny)
    if not run_id or not limit or not models or not endpoint.startswith("https://"):
        raise BudgetStop("A run, positive limit, HTTPS endpoint and frozen models are required.")
    for model, rate in models.items():
        if not model or not _integer(rate["context_tokens"]) or not _integer(rate["max_output_tokens"]):
            raise BudgetStop("Invalid frozen model limits.")
        for key in ("input_cny_per_million", "output_cny_per_million"):
            if not _charge(1, rate[key]):
                raise BudgetStop("Frozen billing rates must be positive.")
        versions = rate.get("response_models", [model])
        if not isinstance(versions, list) or not versions or any(not isinstance(value, str) or not value for value in versions):
            raise BudgetStop("Frozen response models must be explicit identifiers.")
    with _locked(path):
        if path.exists():
            raise BudgetStop("A billing ledger is never reused or replaced.")
        state = {"version": 1, "run_id": run_id, "ledger_path": str(path), "limit_micros": limit,
                 "endpoint": endpoint, "models": models, "blocked": False, "requests": {}}
        state["policy_sha256"] = policy_hash(state)
        _write(path, state)
        return {"ledger_path": str(path), "run_id": run_id, "policy_sha256": state["policy_sha256"],
                "initial_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class GuardedTransport(httpx.BaseTransport):
    def __init__(self, path, *, run_id, policy_sha256, transport=None, allow_stopped=False):
        self.path = Path(path)
        self.run_id, self.policy_sha256 = run_id, policy_sha256
        if not self.path.is_absolute() or not self.path.is_file():
            raise BudgetStop("An approved run needs its pre-created shared billing ledger.")
        if allow_stopped:
            with _locked(self.path):
                self._state()
        else:
            self.check()
        self.transport = transport if transport is not None else httpx.HTTPTransport(retries=0)

    def _state(self):
        state = json.loads(self.path.read_text())
        if (state["version"] != 1 or state["run_id"] != self.run_id or state["ledger_path"] != str(self.path)
                or policy_hash(state) != self.policy_sha256):
            raise BudgetStop("The billing ledger differs from the frozen attempt.")
        return state

    def check(self):
        with _locked(self.path):
            state = self._state()
            if state["blocked"]:
                raise BudgetStop("The shared billing run is stopped.")

    def _reserve(self, request):
        try:
            body = json.loads(request.content)
            model, output = body["model"], _integer(body["max_tokens"])
            tools, messages = body.get("tools", []), body.get("messages", [])
            tools = [] if tools is None else tools
            if (not isinstance(body, dict) or not isinstance(model, str) or not model
                    or not isinstance(tools, list) or not isinstance(messages, list)
                    or any(not isinstance(tool, dict) for tool in tools)
                    or any(not isinstance(message, dict) for message in messages)):
                raise BudgetStop("Invalid text completion shape.")
        except (ValueError, KeyError, TypeError):
            raise BudgetStop("A bounded, non-streaming chat request is required.") from None
        allowed = {"model", "messages", "max_tokens", "stream", "thinking", "temperature", "response_format",
                   "tools", "tool_choice"}
        if (set(body) - allowed
                or any(tool.get("type") != "function" for tool in tools)
                or any(not isinstance(message.get("content"), (str, type(None))) for message in messages)):
            raise BudgetStop("Only the frozen text and client-function protocol is billable by this guard.")
        with _locked(self.path):
            state = self._state()
            if state["version"] != 1 or state["blocked"]:
                raise BudgetStop("The shared billing run is stopped.")
            if request.method != "POST" or str(request.url) != state["endpoint"] or body.get("stream", False) is not False:
                raise BudgetStop("The request differs from the frozen billing endpoint or protocol.")
            rate = state["models"].get(model)
            if rate is None or not 0 < output <= rate["max_output_tokens"]:
                raise BudgetStop("The request differs from the frozen model or output limit.")
            reserved = _charge(rate["context_tokens"], rate["input_cny_per_million"]) + _charge(
                rate["max_output_tokens"], rate["output_cny_per_million"])
            used = sum(entry.get("actual_micros", entry["reserved_micros"]) for entry in state["requests"].values())
            if used + reserved > state["limit_micros"]:
                state["blocked"] = True
                state["stop_reason"] = "reservation_limit"
                _write(self.path, state)
                raise BudgetStop("The shared billing cap cannot reserve this request.")
            ident = uuid.uuid4().hex
            # Sizes only (never content), for the bound of an interruption.
            state["requests"][ident] = {"model": model, "max_tokens": output, "reserved_micros": reserved,
                                        "request_bytes": len(request.content), "tools_bytes": tools_bytes(tools)}
            _write(self.path, state)
            return ident

    def _settle(self, ident, response):
        with _locked(self.path):
            state = self._state()
            entry = state["requests"][ident]
            rate = state["models"][entry["model"]]
            failure = {"kind": "provider_http_status", "http_status": response.status_code}
            try:
                if not 200 <= response.status_code < 300:
                    raise BudgetStop("Provider billing is unknown for this HTTP status.")
                failure = {"kind": "response_billing"}
                data = response.json()
                usage = data["usage"]
                prompt = _integer(usage["prompt_tokens"])
                completion = _integer(usage["completion_tokens"])
                total = _integer(usage["total_tokens"])
                if (data["model"] not in rate.get("response_models", [entry["model"]]) or total != prompt + completion
                        or prompt > rate["context_tokens"] or completion > entry["max_tokens"]):
                    raise BudgetStop("Response billing differs from the frozen bounds.")
                actual = _charge(prompt, rate["input_cny_per_million"]) + _charge(
                    completion, rate["output_cny_per_million"])
                if actual > entry["reserved_micros"]:
                    raise BudgetStop("Response charge exceeds its reservation.")
            except (httpx.HTTPError, ValueError, KeyError, TypeError, BudgetStop):
                state["blocked"] = True
                state.setdefault("stop_reason", failure["kind"])
                entry["failure"] = failure
                _write(self.path, state)
                raise BudgetStop("Billing evidence is uncertain; its reservation is retained and the run is stopped.") from None
            entry["actual_micros"] = actual
            entry["prompt_tokens"], entry["completion_tokens"] = prompt, completion
            _write(self.path, state)

    def stop(self, reason):
        with _locked(self.path):
            state = self._state()
            state["blocked"] = True
            state.setdefault("stop_reason", reason)
            _write(self.path, state)

    def _retain(self, ident, failure):
        """The failure's charge is unknown: the request keeps its whole reservation and the ledger is blocked."""
        with _locked(self.path):
            state = self._state()
            state["blocked"] = True
            state.setdefault("stop_reason", failure["kind"])
            state["requests"][ident]["failure"] = failure
            _write(self.path, state)

    def _interrupted(self, ident, failure):
        """Settle an interrupted request at its bound and raise ProviderInterrupted with the ledger left open. When
        the bound cannot be computed, keep the whole reservation and block the ledger instead (BudgetStop)."""
        with _locked(self.path):
            state = self._state()
            entry = state["requests"][ident]
            try:
                prompt, completion, bound = interruption_bound(
                    entry["request_bytes"], entry["tools_bytes"], entry["max_tokens"], state["models"][entry["model"]])
                if bound > entry["reserved_micros"]:
                    raise BudgetStop("The bound exceeds the reservation.")
            except (KeyError, TypeError, ValueError, BudgetStop):
                bound = None
            if bound is not None:
                entry["actual_micros"] = bound
                entry["interrupted"] = {**failure, "prompt_tokens_bound": prompt,
                                        "completion_tokens_bound": completion}
                _write(self.path, state)
        if bound is None:
            self._retain(ident, failure)
            raise BudgetStop("An interrupted provider request retains its billing reservation; the run is stopped.")
        raise ProviderInterrupted(failure)

    def handle_request(self, request):
        try:
            ident = self._reserve(request)
        except BudgetStop:
            self.stop("request_refused")
            raise
        status = failure = None
        try:
            response = self.transport.handle_request(request)
            status = response.status_code
            response.read()
        except BaseException as error:
            failure = {"kind": "provider_transport", "error_class": _ERROR_CLASSES.get(type(error), "other")}
        if failure is not None:  # Handled outside the except block, so no provider exception text is chained.
            # A body cut short after a status that is final by itself (a 4xx other than 429) is not an interruption.
            if failure["error_class"] in INTERRUPTED_CLASSES and (
                    status is None or 200 <= status < 300 or retriable_status(status)):
                self._interrupted(ident, failure)
            self._retain(ident, failure)
            raise BudgetStop("An interrupted provider request retains its billing reservation; the run is stopped.")
        if retriable_status(response.status_code):
            self._interrupted(ident, {"kind": "provider_http_status", "http_status": response.status_code})
        self._settle(ident, response)
        return response

    def close(self):
        self.transport.close()
