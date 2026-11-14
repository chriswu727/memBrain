from datetime import datetime, timedelta, timezone

from . import cognition
from .contracts import validate
from .helpers import DomainError, _hash, _identifier, _integer, _refs, digest, now
from .snapshots import check_snapshot_sources, check_uncorrected_sources

ORIENTATION_ROUTE_VERSION = "orientation-route-v1"


def assess_orientation(turn, working, state, *, planned=False, embedded=False, historical=False):
    reasons = []
    memories = state["belief_memories"]
    relations = state["belief_relations"]
    if turn["orientation_job_id"]:
        reasons.append("existing_orientation")
    if planned:
        reasons.append("recall_plan")
    if embedded:
        reasons.append("embedding_recall")
    if not historical:
        reasons.append("historical_boundary_required")
    if any(memory.get("conditions", {"op": "always"}) != {"op": "always"}
           or memory.get("procedure") is not None for memory in memories):
        reasons.append("conditional_memory")
    if any(relation.get("conditions") != {"op": "always"} for relation in relations):
        reasons.append("conditional_relation")
    if working["items"] or working["open_loops"] or state["context_observations"]:
        reasons.append("working_state")
    if (state["source_truncated"] or state["rebuilding"]
            or state["belief_incomplete_versions"] or not state["context_observations_complete"]):
        reasons.append("incomplete_dependencies")
    return {
        "version": ORIENTATION_ROUTE_VERSION,
        "decision": "orient" if reasons else "skip",
        "reasons": reasons or ["no_contextual_dependencies"],
        "input_fingerprint": digest([
            turn["turn_id"], turn["conversation_id"], turn["branch_id"], turn["input_event_refs"],
        ]),
        "snapshot": {**{key: state[key] for key in (
            "scope_generation", "dependency_generation", "durable_sequence", "indexed_sequence",
        )}, "working_revision": working["revision"]},
        "dependency_fingerprint": digest({
            "memories": sorted((memory["memory_id"], memory["revision"], digest(memory)) for memory in memories),
            "relations": sorted((relation["relation_id"], relation["revision"], digest(relation))
                                for relation in relations),
            "sources": sorted((event["event_id"], event["revision"], event["content_sha256"])
                              for event in state["working_event_metadata"].values()),
            "working": {key: value for key, value in working.items() if key != "updated_at"},
        }),
    }


def orientation_route(policy, decision, reasons, assessment=None):
    return {"version": ORIENTATION_ROUTE_VERSION, "policy": policy,
            "decision": decision, "reasons": reasons, "assessment": assessment}


# Orientation results that older runtimes stored.
#
# Orientation asked the removed cognition model for the current situation of a runtime turn and stored the answer in
# a completed ``orient`` job. No new one is written. A turn captured before the upgrade, and the working state such
# a turn saved, can still point at one; it is used only while every source, memory, episode and belief relation it
# was built from is still current, as before. The checks of the model's own output format (proposal mode, input
# contract, frozen policy, and the re-check of current-request situation updates against their proposal) went with
# the model: the stored result passed them when it was published, and its sources are re-checked here.


def _current_input_authorization(result):
    binding = result.get("current_input_binding")
    try:
        refs = _refs(result.get("current_input_refs", []))
        if refs or binding is not None:
            if not isinstance(binding, dict) or set(binding) != {"turn_id", "job_id"} or not refs:
                raise DomainError("validation_failed", "Missing current input binding.")
            for value in binding.values():
                _identifier(value)
            scope = result.get("scope")
            validate("BoundScope", scope)
            for key in ("conversation_id", "branch_id"):
                _identifier(scope[key])
    except DomainError as error:
        raise DomainError("context_stale", "Current input authorization is malformed.") from error
    return refs, binding


def _validate_current_input_binding(conn, service, principal, brain, result, events):
    refs, binding = _current_input_authorization(result)
    if not refs and binding is None:
        return
    turn = conn.execute(
        "SELECT t.input_event_refs,t.conversation_id,t.branch_id FROM memory_runtime_turns t "
        "JOIN memory_jobs j ON j.tenant_id=t.tenant_id AND j.owner_id=t.owner_id AND j.brain_id=t.brain_id "
        "AND j.id=t.orientation_job_id WHERE t.tenant_id=%s AND t.owner_id=%s AND t.brain_id=%s "
        "AND t.turn_id=%s AND j.id=%s AND j.kind='orient' AND j.payload->>'turn_id'=t.turn_id "
        "AND j.state NOT IN ('cancelled','superseded')",
        (*service._params(principal, brain["id"]), binding["turn_id"], binding["job_id"]),
    ).fetchone()
    scope = result.get("scope", {})
    if (not turn or turn["input_event_refs"] != refs
            or (turn["conversation_id"], turn["branch_id"]) != (scope.get("conversation_id"), scope.get("branch_id"))
            or any((ref["event_id"], ref["revision"]) not in events for ref in refs)):
        raise DomainError("context_stale", "Current input authorization changed.")


def _snapshot_documents(conn, service, principal, brain, refs, table, identifier, eligibility):
    try:
        if not isinstance(refs, (list, tuple)):
            raise DomainError("validation_failed", "Invalid snapshot references.")
        versions = set()
        for ref in refs:
            if not isinstance(ref, dict):
                raise DomainError("validation_failed", "Invalid snapshot reference.")
            versions.add((_identifier(ref[identifier]), _integer(ref["revision"], 1)))
            _hash(ref["content_sha256"])
    except (DomainError, KeyError) as error:
        raise DomainError("context_stale", "Cognitive document snapshot is malformed.") from error
    if not versions:
        return {}
    versions = sorted(versions)
    rows = conn.execute(
        "SELECT id,revision,document FROM " + table + " WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND (id,revision) IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) AND " + eligibility,
        (*service._params(principal, brain["id"]), [key[0] for key in versions], [key[1] for key in versions]),
    ).fetchall()
    return {(row["id"], row["revision"]): row["document"] for row in rows}


def validate_orientation_snapshot(conn, service, principal, brain, result):
    """Check that a stored orientation result was built only from what is still current; return its events."""
    scope = result.get("scope", {})
    events, lookup = check_snapshot_sources(conn, service, principal, brain, result)
    _validate_current_input_binding(conn, service, principal, brain, result, lookup)
    check_uncorrected_sources(conn, service, principal, brain, result, lookup)
    for field, table, identifier, eligibility, failure in (
            ("memory_snapshot", "memory_assertions", "memory_id",
             "NOT invalidated AND NOT deleted AND NOT suppressed", ("source_unavailable", "Cognitive parent changed.")),
            ("episode_snapshot", "memory_episodes", "episode_id",
             "is_current AND NOT invalidated AND NOT deleted AND document IS NOT NULL",
             ("context_stale", "Cognitive episode changed.")),
            ("belief_relation_snapshot", "memory_belief_relations", "relation_id",
             "NOT invalidated AND NOT deleted AND document IS NOT NULL",
             ("context_stale", "Cognitive belief relationship changed."))):
        references = result.get(field, [])
        documents = _snapshot_documents(conn, service, principal, brain, references, table, identifier, eligibility)
        for ref in references:
            document = documents.get((ref[identifier], ref["revision"]))
            if document is None or field == "memory_snapshot" and document["lifecycle"] == "retracted":
                raise DomainError(*failure)
            if field == "belief_relation_snapshot":
                document = service._rebind(document, principal, brain)
                if digest(document) != ref["content_sha256"] or not cognition._scope_allows(document["scope"], scope):
                    raise DomainError(*failure)
            elif (digest(document) != ref["content_sha256"]
                  or not cognition._scope_allows(service._rebind(document, principal, brain)["scope"], scope)):
                raise DomainError(*failure)
    return events


def orientation_result(conn, service, principal, brain, row):
    """The completed orientation an older runtime stored for this turn, or ``None``."""
    if not row.get("orientation_job_id"):
        return None
    job = conn.execute(
        "SELECT kind,payload,state,result FROM memory_jobs WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s",
        (*service._params(principal, brain["id"]), row["orientation_job_id"]),
    ).fetchone()
    if not job or job["state"] in ("cancelled", "superseded"):
        raise DomainError("context_stale", "Orientation was invalidated.")
    if job["kind"] != "orient" or job["payload"].get("turn_id") != row["turn_id"]:
        raise DomainError("invalid_evidence", "Orientation belongs to another turn.")
    if job["state"] != "completed" or not job["result"]:
        return None
    result = job["result"]
    _current_input_authorization(result)
    scope = result.get("scope", {})
    if not isinstance(scope, dict):
        raise DomainError("context_stale", "Cognitive scope binding is malformed.")
    if (scope.get("conversation_id"), scope.get("branch_id")) != (row["conversation_id"], row["branch_id"]):
        raise DomainError("invalid_evidence", "Orientation belongs to another context.")
    validate_orientation_snapshot(conn, service, principal, brain, result)
    if result.get("current_input_refs", []) and result.get("current_input_binding") != {
        "turn_id": row["turn_id"], "job_id": row["orientation_job_id"],
    }:
        raise DomainError("context_stale", "Orientation current input binding changed.")
    return result


def orientation_updates(conn, service, principal, brain, row):
    result = orientation_result(conn, service, principal, brain, row)
    if not result:
        return []
    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    return [{"key": "situation:" + item["key"],
             "value": {"orientation_job_id": row["orientation_job_id"],
                       **{key: item[key] for key in ("kind", "value", "state", "world", "conditions", "verification",
                                                    "observation", "evidence_use", "request_verification")
                          if key in item}},
             "knowledge_state": "inferred", "evidence_refs": item["evidence_refs"], "expires_at": expires,
             "updated_at": now()}
            for item in result.get("situation_updates", [])]
