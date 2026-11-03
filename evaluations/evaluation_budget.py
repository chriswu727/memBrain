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


class BudgetStop(RuntimeError):
    pass


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
    def __init__(self, path, *, run_id, policy_sha256, transport=None):
        self.path = Path(path)
        self.run_id, self.policy_sha256 = run_id, policy_sha256
        if not self.path.is_absolute() or not self.path.is_file():
            raise BudgetStop("An approved run needs its pre-created shared billing ledger.")
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
                raise BudgetStop("Billing evidence is uncertain; the run is stopped.")

    def _reserve(self, request):
        try:
            body = json.loads(request.content)
            model, output = body["model"], _integer(body["max_tokens"])
            tools, messages = body.get("tools", []), body.get("messages", [])
            tools = [] if tools is None else tools
            if (not isinstance(body, dict) or not isinstance(tools, list) or not isinstance(messages, list)
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
                raise BudgetStop("Billing evidence is uncertain; the run is stopped.")
            if request.method != "POST" or str(request.url) != state["endpoint"] or body.get("stream", False) is not False:
                raise BudgetStop("The request differs from the frozen billing endpoint or protocol.")
            rate = state["models"].get(model)
            if rate is None or not 0 < output <= rate["max_output_tokens"]:
                raise BudgetStop("The request differs from the frozen model or output limit.")
            reserved = _charge(rate["context_tokens"], rate["input_cny_per_million"]) + _charge(
                rate["max_output_tokens"], rate["output_cny_per_million"])
            used = sum(entry.get("actual_micros", entry["reserved_micros"]) for entry in state["requests"].values())
            if used + reserved > state["limit_micros"]:
                raise BudgetStop("The shared billing cap cannot reserve this request.")
            ident = uuid.uuid4().hex
            state["requests"][ident] = {"model": model, "max_tokens": output, "reserved_micros": reserved}
            _write(self.path, state)
            return ident

    def _settle(self, ident, response):
        with _locked(self.path):
            state = self._state()
            entry = state["requests"][ident]
            rate = state["models"][entry["model"]]
            try:
                if not 200 <= response.status_code < 300:
                    raise BudgetStop("Provider billing is unknown for this HTTP status.")
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
                _write(self.path, state)
                raise BudgetStop("Billing evidence is uncertain; its reservation is retained and the run is stopped.") from None
            entry["actual_micros"] = actual
            entry["prompt_tokens"], entry["completion_tokens"] = prompt, completion
            _write(self.path, state)

    def handle_request(self, request):
        ident = self._reserve(request)
        try:
            response = self.transport.handle_request(request)
            response.read()
        except BaseException:
            with _locked(self.path):
                state = self._state()
                state["blocked"] = True
                _write(self.path, state)
            raise BudgetStop("An interrupted provider request retains its billing reservation; the run is stopped.") from None
        self._settle(ident, response)
        return response

    def close(self):
        self.transport.close()
