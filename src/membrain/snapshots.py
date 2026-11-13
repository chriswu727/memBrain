"""Checks that the sources a stored snapshot was built from are still the current, visible, uncorrected ones.

A snapshot binds a scope and exact source event versions (``source_snapshot``). Query embeddings use these checks on
their own; background learning adds its own checks of memories, episodes and belief relations around them.
"""
from . import cognition
from .contracts import validate
from .helpers import DomainError


def check_snapshot_sources(conn, service, principal, brain, snapshot):
    """Check the scope binding, generations and source versions; return the events and their version lookup."""
    scope = snapshot.get("scope", {})
    try:
        validate("BoundScope", scope)
    except DomainError as error:
        raise DomainError("context_stale", "Cognitive scope binding is malformed.") from error
    if scope.get("scope_generation") != brain["scope_generation"]:
        raise DomainError("context_stale", "Cognitive scope changed.")
    if "dependency_generation" in snapshot and snapshot["dependency_generation"] != brain["dependency_generation"]:
        raise DomainError("context_stale", "Cognitive dependency generation changed.")
    refs = snapshot.get("source_snapshot", [])
    events = service._events(conn, principal, brain, event_ids=[r["event_id"] for r in refs], limit=128)
    lookup = {(e["event_id"], e["revision"]): e for e in events}
    for ref in refs:
        event = lookup.get((ref["event_id"], ref["revision"]))
        if (event is None or event["content_sha256"] != ref["content_sha256"]
                or not cognition._scope_allows(event["scope"], scope)):
            raise DomainError("source_unavailable", "Cognitive source changed.")
    return events, lookup


def check_uncorrected_sources(conn, service, principal, brain, snapshot, lookup):
    """Reject a snapshot whose exact source version has since been corrected."""
    refs = snapshot.get("source_snapshot", [])
    superseded = service._superseded_evidence(conn, principal, brain, [r["event_id"] for r in refs])
    if any((ref["event_id"], ref["event_revision"]) in lookup
           and lookup[(ref["event_id"], ref["event_revision"])]["content_sha256"] == ref["source_content_sha256"]
           for ref in superseded):
        raise DomainError("context_stale", "Cognitive source was corrected.")


def validate_source_snapshot(conn, service, principal, brain, snapshot):
    """Validate a snapshot that binds only a scope and source events, as a query embedding's does; return the events."""
    events, lookup = check_snapshot_sources(conn, service, principal, brain, snapshot)
    check_uncorrected_sources(conn, service, principal, brain, snapshot, lookup)
    return events
