"""Evaluation-only billing reservations. Never authorizes a model run."""
import contextlib
import decimal
import fcntl
import hashlib
import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

import httpx

_ERROR_CLASSES = {getattr(httpx, name): name for name in (
    "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout", "TimeoutException",
    "ConnectError", "ReadError", "WriteError", "CloseError", "RemoteProtocolError",
    "LocalProtocolError", "ProxyError", "UnsupportedProtocol", "DecodingError", "HTTPError")}
_ERROR_CLASSES.update({SystemExit: "SystemExit", KeyboardInterrupt: "KeyboardInterrupt"})
# Interruptions (since 2026-11-17): a request that ended in one of these transport failures, with HTTP 429, 500, 502,
# 503 or 504, or with a complete 2xx body that holds no billing JSON (INCOMPLETE_BODIES), is settled at a bound that
# is true for that request (``interruption_bound``) and the ledger stays open, so the caller may send it again. Every
# other failure keeps the whole reservation and blocks the ledger, as before: another HTTP status (501, 505 and the
# other 5xx included), a body whose usage the guard cannot settle, SystemExit, KeyboardInterrupt and any class not
# listed.
INTERRUPTED_CLASSES = frozenset({
    "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout", "TimeoutException",
    "ConnectError", "ReadError", "WriteError", "CloseError", "RemoteProtocolError"})
RETRIED_STATUSES = frozenset({429, 500, 502, 503, 504})
# Why a complete 2xx body holds no billing JSON (``incomplete_body``): only whitespace or empty lines, not parseable
# as JSON, or JSON without a ``usage`` key (an error object, a value that is not an object). Usage that is present but
# malformed or inconsistent, an unapproved response model and completion tokens above max_tokens stay fatal.
INCOMPLETE_BODIES = frozenset({"blank", "not_json", "no_usage"})
# The ``kind`` of an interrupted request's cause: an allowlisted ``error_class``; an ``http_status`` in
# RETRIED_STATUSES; or a 2xx ``http_status`` with a ``body`` in INCOMPLETE_BODIES.
INTERRUPTED_KINDS = frozenset({"provider_transport", "provider_http_status", "provider_incomplete_body"})
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
    """A request interrupted in transport, answered with a status in RETRIED_STATUSES, or answered 2xx with a
    complete body that holds no billing JSON: settled at its bound, the ledger still open. ``failure`` holds the
    content-free cause: ``kind`` and ``error_class``, ``http_status``, or ``http_status`` and ``body``.
    ``request_bytes`` is the size of the body as sent (the ledger entry's), for the caller's record."""

    def __init__(self, failure: dict, request_bytes: int | None = None):
        super().__init__("An interrupted provider request is charged at its bound; the billing run stays open.")
        self.failure = dict(failure)
        self.request_bytes = request_bytes


def retriable_status(status) -> bool:
    """HTTP 429, 500, 502, 503 and 504: answers that a later identical request may not get again. Any other status,
    501 and 505 included, is final."""
    return type(status) is int and status in RETRIED_STATUSES


def incomplete_body(content: bytes) -> str | None:
    """Why a complete 2xx body holds no billing JSON (one of INCOMPLETE_BODIES), or None when it is a JSON object
    with a ``usage`` key: then the usage is checked, and anything wrong with it is fatal."""
    if not content.strip():
        return "blank"
    try:
        data = json.loads(content)
    except (ValueError, RecursionError):
        return "not_json"
    return None if isinstance(data, dict) and "usage" in data else "no_usage"


def interruption_code(failure: dict) -> str:
    """An interruption's cause as one fixed code: the allowlisted class name, ``http_<status>`` or
    ``body_<reason>``; ``other`` for anything else. Never any other text."""
    kind, status = failure.get("kind"), failure.get("http_status")
    if kind == "provider_transport":
        name = failure.get("error_class")
        return name if isinstance(name, str) and name in INTERRUPTED_CLASSES else "other"
    if kind == "provider_http_status" and retriable_status(status):
        return f"http_{status}"
    if kind == "provider_incomplete_body" and failure.get("body") in INCOMPLETE_BODIES:
        return f"body_{failure['body']}"
    return "other"


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


_HOLDING = threading.local()  # .depth: how many _locked blocks this thread is inside (lock_held).


@contextlib.contextmanager
def _locked(path):
    # The depth is raised before the lock is asked for and lowered only after the lock file is closed (which releases
    # the lock), so lock_held() is true whenever this thread may hold the lock.
    _HOLDING.depth = getattr(_HOLDING, "depth", 0) + 1
    try:
        with path.with_suffix(path.suffix + ".lock").open("a") as file:
            os.chmod(file.name, 0o600)
            fcntl.flock(file, fcntl.LOCK_EX)
            yield
    finally:
        _HOLDING.depth -= 1


def lock_held() -> bool:
    """True while the calling thread is inside a guarded section, waiting for the ledger lock or holding it. A
    signal handler (it runs in the main thread, between two steps of whatever that thread was doing) must not take
    the lock then: flock on a second descriptor of the same file would wait for this process itself, for ever."""
    return getattr(_HOLDING, "depth", 0) > 0


def _now() -> float:
    return round(time.time(), 3)


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
            # Sizes only (never content), for the bound of an interruption. ``seq`` numbers the reservations in the
            # order they were made, across every process sharing this ledger (it is taken under the lock); an entry
            # of an older ledger without one still counts, so a number is never given twice.
            requests = state["requests"]
            seq = 1 + max([len(requests)] + [entry["seq"] for entry in requests.values()
                                             if type(entry.get("seq")) is int])
            requests[ident] = {"seq": seq, "reserved_at": _now(), "model": model, "max_tokens": output,
                               "reserved_micros": reserved, "request_bytes": len(request.content),
                               "tools_bytes": tools_bytes(tools)}
            _write(self.path, state)
            return ident

    def _settle(self, ident, response) -> str | None:
        """Settle a response from its usage. When a complete 2xx body holds no billing JSON, settle nothing and
        return its INCOMPLETE_BODIES reason: the caller settles it as an interruption."""
        with _locked(self.path):
            state = self._state()
            entry = state["requests"][ident]
            rate = state["models"][entry["model"]]
            failure = {"kind": "provider_http_status", "http_status": response.status_code}
            try:
                if not 200 <= response.status_code < 300:
                    raise BudgetStop("Provider billing is unknown for this HTTP status.")
                failure = {"kind": "response_billing"}
                reason = incomplete_body(response.content)
                if reason is not None:
                    return reason
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
                entry["failure"], entry["settled_at"] = failure, _now()
                _write(self.path, state)
                raise BudgetStop("Billing evidence is uncertain; its reservation is retained and the run is stopped.") from None
            entry["actual_micros"], entry["settled_at"] = actual, _now()
            entry["prompt_tokens"], entry["completion_tokens"] = prompt, completion
            _write(self.path, state)
            return None

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
            state["requests"][ident]["settled_at"] = _now()
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
                entry["actual_micros"], entry["settled_at"] = bound, _now()
                entry["interrupted"] = {**failure, "prompt_tokens_bound": prompt,
                                        "completion_tokens_bound": completion}
                _write(self.path, state)
                sent = entry["request_bytes"]
        if bound is None:
            self._retain(ident, failure)
            raise BudgetStop("An interrupted provider request retains its billing reservation; the run is stopped.")
        raise ProviderInterrupted(failure, sent)

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
        reason = self._settle(ident, response)
        if reason is not None:  # A complete 2xx body without billing JSON: no more than this request can be billed.
            self._interrupted(ident, {"kind": "provider_incomplete_body", "http_status": response.status_code,
                                      "body": reason})
        return response

    def close(self):
        self.transport.close()
