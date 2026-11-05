import http.server
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache

import jsonschema_rs
import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from jsonschema.validators import extend
from test_cognition import event, request, scope, state
from test_contract_linking import error_details, mutations

from membrain import cognition, contracts, native_contracts
from membrain.helpers import DomainError


def _response(count):
    sources = [event(f"The routine appointment for project{number:04d} is on Friday.", number + 1)
               for number in range(count)]
    memories = [cognition.extract_event(source)[0] for source in sources]
    result = cognition.recall(scope(), request("routine appointment"), memories, sources,
                              state(count, candidate_total=count))
    return {"message_type": "response", "contract_version": contracts.CONTRACT_VERSION,
            "request_id": "r", "action": "recall", "outcome": "completed", "server_scope": scope(), "result": result}


@pytest.fixture
def response():
    value = _response(24)
    assert len(value["result"]["items"]) == 24
    return value


def test_small_recalls_and_other_actions_do_not_pay_for_schema_audits(monkeypatch):
    calls = []

    def audit(current):
        calls.append(current)
        return None

    monkeypatch.setattr(native_contracts, "_snapshot", audit)
    for value in (_response(0), _response(1), _response(15), {
        "message_type": "response", "contract_version": contracts.CONTRACT_VERSION,
        "request_id": "r", "action": "observe", "outcome": "rejected",
        "error": {"code": "validation_failed", "message": "Rejected", "retryable": False},
    }):
        contracts.validate("ActionResponse", value)
    assert not calls


def agrees(value):
    reference = contracts.validator("ActionResponse")
    first = next(reference.iter_errors(value), None)
    if first is None:
        contracts.validate("ActionResponse", value)
    else:
        with pytest.raises(DomainError) as failure:
            contracts.validate("ActionResponse", value)
        assert error_details(failure.value.__cause__) == error_details(first)


def test_native_response_checks_reuse_only_schema_and_recheck_values(response):
    current = contracts.validator("ActionResponse")
    native_contracts._compiled.cache_clear()
    references = sys.getrefcount(response)
    for _ in range(3):
        assert native_contracts.accepts_response(current, response)
        contracts.validate("ActionResponse", response)
    assert sys.getrefcount(response) == references
    assert native_contracts._compiled.cache_info().currsize == 1
    response["result"]["items"][0]["memory"]["scope"]["policy_revision"] = "wrong"
    assert not native_contracts.accepts_response(current, response)
    agrees(response)
    response["result"]["items"][0]["memory"]["scope"]["policy_revision"] = 1
    assert native_contracts.accepts_response(current, response)
    assert native_contracts._compiled.cache_info().currsize == 1


def test_concurrent_first_recalls_compile_the_schema_only_once(response, monkeypatch):
    native_contracts._compiled.cache_clear()
    original = jsonschema_rs.Draft202012Validator
    calls = []

    def compile_schema(*args, **kwargs):
        calls.append(True)
        time.sleep(0.03)
        return original(*args, **kwargs)

    monkeypatch.setattr(jsonschema_rs, "Draft202012Validator", compile_schema)
    barrier = threading.Barrier(8)
    current = contracts.validator("ActionResponse")

    def validate(index):
        barrier.wait(timeout=10)
        return native_contracts.accepts_response(current, response)

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(validate, range(8)))
    assert len(calls) == 1
    assert native_contracts._compiled.cache_info().currsize == 1


def test_concurrent_cold_validators_share_one_prepared_class(monkeypatch):
    original = contracts._prepared_root.__wrapped__
    calls = []

    @lru_cache
    def prepare():
        calls.append(True)
        time.sleep(0.03)
        return original()

    contracts.validator.cache_clear()
    monkeypatch.setattr(contracts, "_prepared_root", prepare)
    barrier = threading.Barrier(8)

    def get_validator(index):
        barrier.wait(timeout=10)
        return contracts.validator("ActionResponse")

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            validators = list(pool.map(get_validator, range(8)))
        assert len(calls) == 1
        assert all(type(current) is type(validators[0]) for current in validators)
    finally:
        contracts.validator.cache_clear()


def test_metadata_setup_failure_preserves_reference_validation(response, monkeypatch):
    def unavailable(values):
        raise RuntimeError("Accelerator metadata unavailable")

    contracts.validator.cache_clear()
    contracts._prepared_root.cache_clear()
    monkeypatch.setattr(native_contracts, "_capture_containers", unavailable)
    try:
        current = contracts.validator("ActionResponse")
        assert not native_contracts.accepts_response(current, response)
        agrees(response)
        response["result"]["items"] = "wrong"
        agrees(response)
    finally:
        contracts.validator.cache_clear()
        contracts._prepared_root.cache_clear()


def test_native_and_reference_response_validation_agree_on_deterministic_mutations(response):
    agrees(response)
    for broken in mutations(response, 1000, seed="native-response-errors"):
        agrees(broken)


@pytest.mark.parametrize("value", [2**54, 1e100, float("nan"), float("inf"), -float("inf"),
                                  Decimal("1"), Fraction(1, 2), (), {1: "value"}])
def test_noncanonical_values_keep_reference_validation(response, value):
    response["result"]["usage"]["context_tokens"] = value
    assert not native_contracts.accepts_response(contracts.validator("ActionResponse"), response)
    agrees(response)


def test_native_rejects_subclasses_and_deep_or_cyclic_values():
    class Record(dict):
        pass

    class Text(str):
        pass

    assert not native_contracts._plain(Record())
    assert not native_contracts._plain(Text("text"))
    deep = []
    for _ in range(66):
        deep = [deep]
    assert not native_contracts._plain(deep)
    cycle = {}
    cycle["self"] = cycle
    assert not native_contracts._plain(cycle)


def test_live_schema_edits_disable_native_even_when_prepared_keywords_hold_old_values(response, monkeypatch):
    current = contracts.validator("ActionResponse")
    assert native_contracts.accepts_response(current, response)
    monkeypatch.setitem(current.schema["properties"], "request_id", {"const": "another request"})
    assert not native_contracts.accepts_response(current, response)
    agrees(response)


def test_relaxing_schema_metadata_cannot_bypass_prepared_constraints(response, monkeypatch):
    current = contracts.validator("ActionResponse")
    monkeypatch.setitem(current.schema, "allOf", [])
    response["result"]["items"] = "wrong"
    assert not native_contracts.accepts_response(current, response)
    assert not current.is_valid(response)
    agrees(response)


def test_changed_prepared_root_validation_is_not_bypassed(response, monkeypatch):
    current = contracts.validator("ActionResponse")

    def reject(*args):
        yield ValidationError("Modified response validation")

    monkeypatch.setattr(current, "_validators", [*current._validators, (reject, "custom", True)])
    assert not native_contracts.accepts_response(current, response)
    with pytest.raises(DomainError) as failure:
        contracts.validate("ActionResponse", response)
    assert failure.value.__cause__.message == "Modified response validation"


def test_changed_prepared_child_validation_is_not_bypassed(response, monkeypatch):
    current = contracts.validator("ActionResponse")
    memory = contracts._linked_definitions()["MemoryAssertion"]
    child = next(child for child, _, _ in type(current)._membrain_nodes if child.schema is memory)

    def reject(*args):
        yield ValidationError("Modified memory validation")

    monkeypatch.setattr(child, "_validators", [*child._validators, (reject, "custom", True)])
    assert not native_contracts.accepts_response(current, response)
    with pytest.raises(DomainError) as failure:
        contracts.validate("ActionResponse", response)
    assert failure.value.__cause__.message == "Modified memory validation"


def test_in_place_prepared_child_rule_edits_are_not_bypassed(response):
    current = contracts.validator("ActionResponse")
    condition = current.schema["allOf"][0]
    child = next(child for child, schema, _ in type(current)._membrain_nodes if schema is condition)

    def reject(*args):
        yield ValidationError("Additional child validation")

    previous = child._validators[0]
    child._validators[0] = reject, "custom", True
    try:
        assert not native_contracts.accepts_response(current, response)
        with pytest.raises(DomainError) as failure:
            contracts.validate("ActionResponse", response)
        assert failure.value.__cause__.message == "Additional child validation"
    finally:
        child._validators[0] = previous


def test_replacing_a_prepared_child_schema_is_not_bypassed(response, monkeypatch):
    current = contracts.validator("ActionResponse")
    condition = current.schema["allOf"][0]
    assert "if" in condition
    child = next(child for child, schema, _ in type(current)._membrain_nodes if schema is condition)
    monkeypatch.setattr(child, "schema", {"then": False, "else": False})
    assert not native_contracts.accepts_response(current, response)
    assert not current.is_valid(response)
    agrees(response)


def test_custom_format_checker_and_validator_methods_are_preserved(response, monkeypatch):
    current = contracts.validator("ActionResponse")
    checker = FormatChecker()
    checker.checks("date-time")(lambda value: False)
    custom = current.evolve(format_checker=checker)
    assert not native_contracts.accepts_response(custom, response)
    monkeypatch.setattr(contracts, "validator", lambda definition: custom)
    agrees(response)

    def reject(self, value):
        raise ValidationError("Modified validator method")

    monkeypatch.setattr(contracts, "validator", lambda definition: current)
    monkeypatch.setattr(type(custom), "validate", reject)
    assert not native_contracts.accepts_response(current, response)
    with pytest.raises(DomainError) as failure:
        contracts.validate("ActionResponse", response)
    assert failure.value.__cause__.message == "Modified validator method"


def test_custom_type_checker_is_preserved(response, monkeypatch):
    current = contracts.validator("ActionResponse")
    checker = Draft202012Validator.TYPE_CHECKER.redefine("integer", lambda checker, value: False)
    custom = extend(type(current), type_checker=checker)(current.schema, format_checker=current.format_checker)
    assert not native_contracts.accepts_response(custom, response)
    monkeypatch.setattr(contracts, "validator", lambda definition: custom)
    agrees(response)


def test_overridden_keywords_are_preserved(response, monkeypatch):
    current = contracts.validator("ActionResponse")

    def reject_strings(validator, declared, value, node):
        if isinstance(value, str):
            yield ValidationError("Custom string validation")
        else:
            yield from Draft202012Validator.VALIDATORS["type"](validator, declared, value, node)

    custom = extend(type(current), {"type": reject_strings})(current.schema, format_checker=current.format_checker)
    assert not native_contracts.accepts_response(custom, response)
    monkeypatch.setattr(contracts, "validator", lambda definition: custom)
    agrees(response)


@pytest.mark.parametrize("stamp", ["2026-11-04T10:00:00Z", "2026-11-04t10:00:00z",
                                   "2026-11-04T10:00:00.123456789+14:00", "2026-02-30T10:00:00Z",
                                   "2016-12-31T23:59:60Z", "2026-11-04T24:00:00Z", "2026-11-04T10:00:00+25:00"])
def test_native_uses_the_same_date_time_rules(response, stamp):
    response["result"]["items"][0]["memory"]["system_time"]["recorded_at"] = stamp
    current = contracts.validator("ActionResponse")
    assert native_contracts.accepts_response(current, response) == current.is_valid(response)
    agrees(response)


@pytest.mark.parametrize("failure", [None, RuntimeError("Native compilation unavailable")])
def test_accelerator_failure_preserves_reference_errors(response, monkeypatch, failure):
    def unavailable(snapshot):
        if failure is not None:
            raise failure
        return None

    monkeypatch.setattr(native_contracts, "_compiled", unavailable)
    agrees(response)
    response["result"]["items"] = "wrong"
    agrees(response)


def test_validator_lookup_errors_still_use_the_contract_error(monkeypatch):
    def unavailable(definition):
        raise ValidationError("Lookup failed")

    monkeypatch.setattr(contracts, "validator", unavailable)
    with pytest.raises(DomainError, match="Invalid ActionResponse at") as failure:
        contracts.validate("ActionResponse", {})
    assert failure.value.__cause__.message == "Lookup failed"


def test_native_compilation_cannot_fetch_external_references():
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        snapshot = json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema",
                               "$ref": f"http://127.0.0.1:{server.server_port}/schema"})
        assert native_contracts._compiled(snapshot) is None
        assert not requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
