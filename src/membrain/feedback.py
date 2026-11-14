"""Feedback on a delivered answer: the ``recall_feedback`` of the public ``commit`` action.

Confirmation or correction is credited to a memory only when the answer it refers to was delivered by a runtime
turn that had selected that memory (``memory_runtime_turns``). The bundled runtime mode that created such turns was
removed; brains from older runtimes still hold them, so the proof below still reads them, and a ``commit`` that
names one can still credit its memory. Without such a turn, feedback is kept as a trace and credits nothing, as
before. The checks of a turn's delivery receipt and prepared memory selection that the proof needs are those of
the runtime mode's ``delivery_receipts`` and ``prepared_selection`` modules, moved here unchanged.
"""
import copy
import hashlib
import json
from datetime import datetime

from psycopg.types.json import Jsonb

from . import cognition
from .contracts import validate
from .helpers import DomainError, _hash, _identifier, _integer, _refs, digest
from .legacy_erasure import recompute_access
from .retrieval import resolve_dependency_closure

ATTRIBUTION_VERSION = "sole-exact-statement-v1"

RECEIPT_VERSION = "runtime-delivery-receipt-v1"
RECEIPT_STATES = frozenset({"delivered", "partially_delivered", "cancelled"})
RECEIPT_REASONS = frozenset({
    "source_unavailable", "context_generation_changed", "working_revision_changed", "orientation_changed",
    "recording_changed",
})
RECEIPT_FAILURES = frozenset({"source_unavailable", "context_stale", "commit_failed", "cancelled"})
SELECTION_MAX_BYTES = 131072


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _receipt_failure(reasons, state):
    if "source_unavailable" in reasons:
        return "source_unavailable"
    if "working_revision_changed" in reasons:
        return "commit_failed"
    if reasons:
        return "context_stale"
    return "cancelled" if state == "cancelled" else None


def _sanitize_delivery_receipt(value):
    if not isinstance(value, dict):
        return None
    try:
        state, disposition, failure = (value[key] for key in ("state", "disposition", "failure_code"))
        if (value["version"] != RECEIPT_VERSION or not isinstance(state, str) or state not in RECEIPT_STATES
                or disposition not in ("content_recorded", "content_withheld")
                or failure is not None and (not isinstance(failure, str) or failure not in RECEIPT_FAILURES)):
            return None
        content_hash = _hash(value["content_sha256"])
        size = _integer(value["content_bytes"], 0 if state == "cancelled" else 1, 64000)
        if state == "cancelled" and (size or content_hash != hashlib.sha256(b"").hexdigest()):
            return None
        reasons = value["stale_reasons"]
        if (not isinstance(reasons, list) or len(reasons) > len(RECEIPT_REASONS)
                or any(not isinstance(reason, str) or reason not in RECEIPT_REASONS for reason in reasons)
                or len(set(reasons)) != len(reasons)):
            return None
        if ((disposition == "content_withheld" and not {"source_unavailable", "recording_changed"}.intersection(reasons))
                or failure != _receipt_failure(reasons, state)):
            return None
        binding = value["authorization"]
        reference = binding["draft_event_ref"]
        authorized = {
            "draft_event_ref": {"event_id": _identifier(reference["event_id"]),
                                "revision": _integer(reference["revision"], 1)},
            "context_fingerprint": _hash(binding["context_fingerprint"]),
            "context_generation": _integer(binding["context_generation"]),
            "working_revision": _integer(binding["working_revision"]),
            "turn_fence": _integer(binding["turn_fence"], 1),
            "turn_revision": _integer(binding["turn_revision"], 1),
        }
        return {"version": RECEIPT_VERSION, "state": state, "content_sha256": content_hash, "content_bytes": size,
                "authorization": authorized, "disposition": disposition,
                "stale_reasons": sorted(reasons), "failure_code": failure}
    except (DomainError, KeyError, TypeError):
        return None


def recorded_delivery_receipt(row):
    """Whether a runtime turn row carries a delivery receipt that matches the turn it is stored on."""
    if (not isinstance(row, dict) or not isinstance(row.get("stage"), str)
            or row["stage"] not in {"delivered", "completed", "failed"}):
        return False
    receipt = _sanitize_delivery_receipt(row.get("delivery_receipt"))
    if receipt is None or row.get("failure_code") != receipt["failure_code"]:
        return False
    terminal = row["stage"] != "delivered"
    if row.get("scope_reserved") is not (not terminal):
        return False
    if (row["stage"] == "failed") != (receipt["failure_code"] is not None):
        return False
    binding = receipt["authorization"]
    try:
        if (_hash(row["context_fingerprint"]) != binding["context_fingerprint"]
                or _integer(row["context_generation"]) != binding["context_generation"]
                or _integer(row["working_revision"]) != binding["working_revision"] + int(row["stage"] == "completed")
                or _integer(row["fence"], 1) < binding["turn_fence"]
                or _integer(row["revision"], 1) <= binding["turn_revision"]):
            return False
        reference = binding["draft_event_ref"]
        expected = {"event_id": reference["event_id"], "revision": reference["revision"] + int(
            receipt["disposition"] == "content_recorded")}
        return _refs(row["output_event_refs"]) == [expected]
    except (DomainError, KeyError, TypeError):
        return False


def _sanitize_prepared_selection(value):
    if value is None:
        return None
    try:
        validate("PreparedMemorySelection", value)
        if len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()) > SELECTION_MAX_BYTES:
            return None
        if value["state"] == "unavailable" and value["unavailable_reason"] == "custom_context":
            return copy.deepcopy(value)
        references = value["input_event_refs"] + value["source_event_refs"]
        if (not value["input_event_refs"] or any(type(ref["revision"]) is not int for ref in references)
                or any(type(value[key]) is not int for key in ("context_generation", "working_revision"))
                or any(len({ref["event_id"] for ref in value[key]}) != len(value[key])
                       for key in ("input_event_refs", "source_event_refs"))
                or len({item["memory_id"] for item in value["memories"]}) != len(value["memories"])):
            return None
        sources = {(ref["event_id"], ref["revision"], ref["content_sha256"]) for ref in value["source_event_refs"]}
        for memory in value["memories"]:
            if (type(memory["memory_revision"]) is not int or not memory["evidence_refs"]
                    or any(type(ref["event_revision"]) is not int
                           or (ref["event_id"], ref["event_revision"], ref["source_content_sha256"]) not in sources
                           for ref in memory["evidence_refs"])):
                return None
    except (DomainError, TypeError, ValueError, UnicodeError):
        return None
    return copy.deepcopy(value)


def selection_for_turn(row):
    """The complete memory selection a runtime turn stored for the context it prepared, or ``None``."""
    selection = _sanitize_prepared_selection(row.get("prepared_memory_selection"))
    if (selection is None or selection["state"] != "complete"
            or selection["turn_id"] != row["turn_id"]
            or selection["context_fingerprint"] != row["context_fingerprint"]
            or selection["context_generation"] != row["context_generation"]
            or any(selection[key] != row[key] for key in ("brain_id", "conversation_id", "branch_id"))
            or selection["input_event_refs"] != row["input_event_refs"]
            or any({"event_id": ref["event_id"], "revision": ref["revision"]} not in row["context_event_refs"]
                   for ref in selection["source_event_refs"])):
        return None
    return selection


def _source_proof(conn, service, principal, brain, target, memory):
    params = service._params(principal, brain["id"])

    def fetch(versions):
        rows = conn.execute(
            "SELECT document,is_current FROM memory_assertions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND (id,revision) IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) "
            "AND NOT invalidated AND NOT deleted AND NOT suppressed AND document IS NOT NULL",
            (*params, [key[0] for key in versions], [key[1] for key in versions]),
        ).fetchall()
        result = []
        for row in rows:
            value = service._rebind(row["document"], principal, brain)
            if not row["is_current"]:
                value["lifecycle"] = "superseded"
            result.append(value)
        return result

    closure = resolve_dependency_closure([memory], fetch, max_nodes=256, max_depth=8)
    if closure.truncated or closure.missing_versions or closure.cycle_versions:
        return None
    memories = {(item["memory_id"], item["revision"]): item for item in closure.memories}
    event_ids = {ref["event_id"] for item in closure.memories
                 for ref in item["evidence_refs"] + item.get("counterexamples", [])}
    event_ids.update(identifier for item in closure.memories for identifier in item.get("root_event_ids", []))
    if len(event_ids) > 1024:
        return None
    events = {item["event_id"]: item for item in service._events(
        conn, principal, brain, event_ids=sorted(event_ids), limit=1024,
    )}
    if set(events) != event_ids:
        return None
    if not cognition._evidence_valid(
        memory, memories, events, service._scope(principal, brain, target), brain["dependency_generation"],
        None, set(), False, "exact_quote", valid_dependency_versions=frozenset(memories),
        superseded_evidence_refs=tuple(service._superseded_evidence(conn, principal, brain, sorted(event_ids))),
    ):
        return None
    return {"events": list(events.values()), "memories": sorted({key[0] for key in memories})}


def _sole_statement(text, statement):
    if not isinstance(text, str) or not isinstance(statement, str) or not statement:
        return False
    choices = {statement}
    choices.update(start + statement + end for start, end in (
        ('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"),
    ))
    return text.strip() in choices


def _selected_statements(conn, service, principal, brain, selected):
    versions = {(item["document"]["memory_id"], item["document"]["memory_revision"]) for item in selected}
    rows = conn.execute(
        "SELECT id,revision,document FROM memory_assertions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND (id,revision) IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) "
        "AND is_current AND NOT invalidated AND NOT deleted AND NOT suppressed AND document IS NOT NULL",
        (*service._params(principal, brain["id"]), [key[0] for key in versions], [key[1] for key in versions]),
    ).fetchall()
    statements = {(row["id"], row["revision"]): row["document"]["statement"] for row in rows}
    missing = versions - statements.keys()
    if missing:
        event_ids = {ref["event_id"] for item in selected
                     if (item["document"]["memory_id"], item["document"]["memory_revision"]) in missing
                     for ref in item["document"]["evidence_refs"]}
        if len(event_ids) > 1024:
            return None
        for event in service._events(conn, principal, brain, event_ids=sorted(event_ids), limit=1024):
            for memory in cognition.extract_event(event):
                key = memory["memory_id"], memory["revision"]
                if key in missing:
                    statements[key] = memory["statement"]
    return statements if set(statements) == versions else None


def _single_prepared_selection(conn, params, turn, selected, delivered_at):
    groups = conn.execute(
        "SELECT DISTINCT document->>'recall_id' AS recall_id FROM memory_traces "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND document->>'turn_id'=%s "
        "AND document->>'kind' IN ('context_selected','quoted') "
        "AND (document->>'recorded_at')::timestamptz<%s LIMIT 2",
        (*params, turn["turn_id"], delivered_at),
    ).fetchall()
    if len(groups) != 1 or groups[0]["recall_id"] != selected[0]["document"]["recall_id"]:
        return False
    packets = conn.execute(
        "SELECT response #> '{result,recall_traces}' AS traces FROM memory_requests "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND action='prepare' "
        "AND response #>> '{result,turn_id}'=%s "
        "AND response #>> '{result,scope,conversation_id}'=%s AND response #>> '{result,scope,branch_id}'=%s "
        "AND (response #>> '{result,created_at}')::timestamptz<%s LIMIT 2",
        (*params, turn["turn_id"], turn["conversation_id"], turn["branch_id"], delivered_at),
    ).fetchall()
    return len(packets) == 1 and {trace["trace_id"] for trace in packets[0]["traces"]} == {
        item["id"] for item in selected}


def _latest_delivery(conn, params, target, event):
    output = conn.execute(
        "SELECT id,revision,sequence,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND branch_id=%s AND sequence<%s AND is_current AND NOT retired AND NOT suppressed "
        "AND NOT deleted AND document #>> '{observed,actor_role}'='assistant' "
        "AND document #>> '{observed,delivery_state}' IN ('delivered','partially_delivered') "
        "ORDER BY sequence DESC LIMIT 1",
        (*params, target.get("conversation_ref"), target.get("branch_ref"), event["sequence"]),
    ).fetchone()
    if output is None:
        return None
    turns = conn.execute(
        "SELECT * FROM memory_runtime_turns WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND branch_id=%s AND output_event_refs=%s LIMIT 2",
        (*params, target.get("conversation_ref"), target.get("branch_ref"),
         Jsonb([{"event_id": output["id"], "revision": output["revision"]}])),
    ).fetchall()
    if len(turns) != 1:
        return None
    turn = turns[0]
    if turn["stage"] not in {"delivered", "committed", "completed"} and not recorded_delivery_receipt(turn):
        return None
    return turn, output


def _statement_hashes(text):
    if not isinstance(text, str):
        return set()
    text = text.strip()
    candidates = {text}
    for start, end in (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』")):
        if len(text) > 2 and text.startswith(start) and text.endswith(end):
            candidates.add(text[1:-1])
    return {text_hash(value) for value in candidates}


def _bound_delivered_use(conn, service, principal, brain, target, memory, proposal, event, turn, preceding):
    selection = selection_for_turn(turn)
    if selection is None:
        return None
    output = preceding["document"]
    matches = [item for item in selection["memories"]
               if item["statement_sha256"] in _statement_hashes(output["observed"]["content"].get("text"))]
    if (len(matches) != 1 or matches[0]["memory_id"] != memory["memory_id"]
            or matches[0]["memory_revision"] != memory["revision"]
            or matches[0]["statement_sha256"] != text_hash(memory["statement"])
            or matches[0]["recall_id"] != proposal["recall_id"]
            or output["origin"] != "assistant_output" or output["origin_verification"] == "unverified_import"
            or output["content_sha256"] != digest(output["observed"]["content"])
            or not _sole_statement(output["observed"]["content"].get("text"), memory["statement"])):
        return None
    params = service._params(principal, brain["id"])
    if conn.execute(
        "SELECT 1 FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND branch_id=%s AND sequence>%s AND sequence<%s AND is_current "
        "AND NOT retired AND NOT deleted AND NOT suppressed AND document #>> '{observed,delivery_state}'='received' "
        "AND document #>> '{observed,actor_role}' IN ('user','external','operator') LIMIT 1",
        (*params, target.get("conversation_ref"), target.get("branch_ref"), preceding["sequence"], event["sequence"]),
    ).fetchone():
        return None
    bound_events = {item["event_id"]: item for item in service._events(
        conn, principal, brain, event_ids=[ref["event_id"] for ref in selection["source_event_refs"]], limit=64,
    )}
    for reference in selection["source_event_refs"]:
        source = bound_events.get(reference["event_id"])
        if (source is None or source["revision"] != reference["revision"]
                or source["content_sha256"] != reference["content_sha256"]
                or not cognition._scope_allows(source["scope"], service._scope(principal, brain, target))):
            return None
    sources = _source_proof(conn, service, principal, brain, target, memory)
    if sources is None:
        return None
    sources["events"].extend(bound_events.values())
    chosen = matches[0]
    return {"selection": {"id": chosen["trace_id"], "document": {"turn_id": turn["turn_id"]}},
            "output": output, **sources}


def _delivered_use(conn, service, principal, brain, target, memory, proposal, event):
    params = service._params(principal, brain["id"])
    latest = _latest_delivery(conn, params, target, event)
    if latest is not None and latest[0].get("prepared_memory_selection") is not None:
        return _bound_delivered_use(conn, service, principal, brain, target, memory, proposal, event, *latest)
    selected = conn.execute(
        "SELECT id,document FROM memory_traces WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND document->>'recall_id'=%s AND document->>'kind' IN ('context_selected','quoted') "
        "AND document #>> '{scope,conversation_id}'=%s AND document #>> '{scope,branch_id}'=%s "
        "ORDER BY id LIMIT 65",
        (*params, proposal["recall_id"], target.get("conversation_ref"), target.get("branch_ref")),
    ).fetchall()
    if not selected or len(selected) == 65:
        return None
    if any(type(item["document"].get("memory_revision")) is not int for item in selected):
        return None
    matching = [item for item in selected if (item["document"]["memory_id"], item["document"]["memory_revision"])
                == (memory["memory_id"], memory["revision"])]
    if not matching:
        return None
    turn_ids = {item["document"].get("turn_id") for item in selected}
    if len(turn_ids) != 1 or None in turn_ids:
        return None
    used = matching[0]
    if any(cognition._stamp(event["system_time"]["recorded_at"]) <= cognition._stamp(
            item["document"]["recorded_at"]) for item in selected):
        return None
    turn = conn.execute(
        "SELECT * FROM memory_runtime_turns WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND turn_id=%s AND conversation_id=%s AND branch_id=%s",
        (*params, used["document"]["turn_id"], target.get("conversation_ref"), target.get("branch_ref")),
    ).fetchone()
    if not turn or (turn["stage"] not in {"delivered", "committed", "completed"}
                    and not recorded_delivery_receipt(turn)):
        return None
    preceding = conn.execute(
        "SELECT id,revision,sequence,document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND branch_id=%s AND sequence<%s AND is_current AND NOT retired AND NOT suppressed "
        "AND NOT deleted AND document #>> '{observed,actor_role}'='assistant' "
        "AND document #>> '{observed,delivery_state}' IN ('delivered','partially_delivered') "
        "ORDER BY sequence DESC LIMIT 1",
        (*params, target.get("conversation_ref"), target.get("branch_ref"), event["sequence"]),
    ).fetchone()
    if not preceding or turn["output_event_refs"] != [{"event_id": preceding["id"], "revision": preceding["revision"]}]:
        return None
    output = preceding["document"]
    delivered_at = cognition._stamp(output["system_time"]["recorded_at"])
    if any(cognition._stamp(item["document"]["recorded_at"]) >= delivered_at for item in selected):
        return None
    if not _single_prepared_selection(conn, params, turn, selected, delivered_at):
        return None
    if any({"event_id": ref["event_id"], "revision": ref["event_revision"]} not in turn["context_event_refs"]
           for item in matching for ref in item["document"]["evidence_refs"]):
        return None
    if (output["origin"] != "assistant_output" or output["origin_verification"] == "unverified_import"
            or output["content_sha256"] != digest(output["observed"]["content"])
            or not _sole_statement(output["observed"]["content"].get("text"), memory["statement"])):
        return None
    statements = _selected_statements(conn, service, principal, brain, selected)
    if statements is None or {key for key, statement in statements.items()
                              if _sole_statement(output["observed"]["content"].get("text"), statement)} != {
                                  (memory["memory_id"], memory["revision"])}:
        return None
    intervening = conn.execute(
        "SELECT 1 FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=%s AND branch_id=%s AND sequence>%s AND sequence<%s AND is_current "
        "AND NOT retired AND NOT deleted AND NOT suppressed AND document #>> '{observed,delivery_state}'='received' "
        "AND document #>> '{observed,actor_role}' IN ('user','external','operator') LIMIT 1",
        (*params, target.get("conversation_ref"), target.get("branch_ref"), preceding["sequence"], event["sequence"]),
    ).fetchone()
    if intervening:
        return None
    sources = _source_proof(conn, service, principal, brain, target, memory)
    return {"selection": used, "output": output, **sources} if sources else None


def record_feedback(conn, service, principal, brain, target, memory, proposal, event):
    proof = _delivered_use(conn, service, principal, brain, target, memory, proposal, event)
    if proof is None:
        return False
    params = service._params(principal, brain["id"])
    source_events = {item["event_id"]: item for item in [*proof["events"], proof["output"], event]}
    refs = [{"event_id": item["event_id"], "revision": item["revision"], "content_sha256": item["content_sha256"]}
            for item in sorted(source_events.values(), key=lambda item: item["event_id"])]
    result = conn.execute(
        "INSERT INTO memory_feedback_contributions(tenant_id,owner_id,brain_id,memory_id,memory_revision,"
        "feedback_event_id,feedback_event_revision,feedback_content_hash,delivery_event_id,delivery_event_revision,"
        "delivery_content_hash,selection_trace_id,recall_id,turn_id,conversation_id,branch_id,kind,attribution_version,"
        "source_event_refs,source_event_ids,source_memory_ids,observed_at) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (*params, memory["memory_id"], memory["revision"], event["event_id"], event["revision"], event["content_sha256"],
         proof["output"]["event_id"], proof["output"]["revision"], proof["output"]["content_sha256"],
         proof["selection"]["id"], proposal["recall_id"], proof["selection"]["document"]["turn_id"],
         target["conversation_ref"], target["branch_ref"], proposal["kind"], ATTRIBUTION_VERSION,
         Jsonb(refs), sorted(source_events), proof["memories"], datetime.fromisoformat(event["system_time"]["recorded_at"])),
    )
    if result.rowcount:
        recompute_access(conn, params, [(memory["memory_id"], memory["revision"])])
    return bool(result.rowcount)
