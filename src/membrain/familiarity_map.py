"""Derived familiarity summaries, kept separate from stored graph records."""
from . import relationship
from .notes import NOTES_CONVERSATION


def load_familiarity(service, conn, principal, brain_id, state, today, include_sensitive):
    params = service._params(principal, brain_id)
    rows = conn.execute(
        "SELECT n.id,d.input_event_id FROM memory_events n LEFT JOIN memory_event_dependencies d "
        "ON d.tenant_id=n.tenant_id AND d.owner_id=n.owner_id AND d.brain_id=n.brain_id AND d.output_event_id=n.id "
        "WHERE n.tenant_id=%s AND n.owner_id=%s AND n.brain_id=%s AND n.is_current AND NOT n.deleted "
        "AND NOT n.suppressed AND NOT n.retired AND n.document IS NOT NULL AND n.conversation_id=%s "
        "AND left(n.document->'observed'->'content'->>'text',1)='[' AND ("
        "split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive' OR "
        "split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive · %%')",
        (*params, NOTES_CONVERSATION)).fetchall()
    protected = {ident for row in rows for ident in (row["id"], row["input_event_id"]) if ident}
    moments = relationship._moment_state(service, conn, principal, brain_id, state["after"], protected=protected)
    private_day = bool(protected and conn.execute(
        f"SELECT 1 FROM memory_events WHERE {relationship._VISIBLE} AND sequence>%s "
        "AND id=ANY(%s::text[]) AND document->'observed'->>'event_kind'='message' "
        "AND document->'observed'->>'actor_role'='user' AND conversation_id IS DISTINCT FROM %s "
        "AND producer_ref <> 'membrain-memory-page' LIMIT 1",
        (*params, state["after"], sorted(protected), NOTES_CONVERSATION)).fetchone())
    if (private_day or moments["sensitive"]) and not include_sensitive:
        return moments, {"derived": True, "masked": True}
    days = relationship._days(service, conn, principal, brain_id, state["after"])
    cap = state["cap"]["level"] if state["cap"] else None
    summary = relationship.familiarity(days, moments["total"], cap, today)
    return moments, {**summary, "derived": True, "masked": False, "after_sequence": state["after"],
                     "basis": "distinct_visible_user_conversation_days_and_shared_moments_after_reset"}


def visible_evidence(summary, moments, state, graph):
    if summary["masked"]:
        return summary
    shared = ["note:" + moment["id"] for moment in moments["items"] if "note:" + moment["id"] in graph.nodes]
    cap = "cap:" + state["cap"]["id"] if state["cap"] else None
    reset = "relationship-reset:" + state["marker"]["id"] if state["marker"] else None
    return {**summary, "evidence": {"shared_moment_nodes": shared,
                                   "shared_moments_truncated": len(shared) < moments["total"],
                                   "cap_node": cap if cap in graph.nodes else None,
                                   "reset_node": reset if reset in graph.nodes else None}}
