"""Resolve explicit note references when either side of a host turn is recorded."""
from psycopg.types.json import Jsonb

from .notes import NOTES_CONVERSATION


def reference(observed):
    return {name: observed[name] for name in ("producer_ref", "source_event_key", "source_revision")}


def link(service, conn, principal, brain, document):
    from .affect import AFFECT_CONVERSATION

    params = service._params(principal, brain["id"])
    observed = document["observed"]
    edges = []
    sourced_conversations = [NOTES_CONVERSATION, AFFECT_CONVERSATION]
    if document["scope"]["conversation_id"] in sourced_conversations:
        for ref in observed.get("source_references", []):
            row = conn.execute(
                "SELECT id FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                "AND producer_ref=%s AND source_key=%s AND source_revision=%s "
                "AND (conversation_id IS NULL OR NOT (conversation_id=ANY(%s::text[]))) AND is_current AND NOT deleted AND NOT suppressed "
                "AND NOT retired AND document IS NOT NULL "
                "AND document->'observed'->>'delivery_state' NOT IN ('draft','cancelled')",
                (*params, ref["producer_ref"], ref["source_event_key"], ref["source_revision"], sourced_conversations)).fetchone()
            if row:
                edges.append((row["id"], document["event_id"]))
    elif observed["event_kind"] == "message" and observed["delivery_state"] not in ("draft", "cancelled"):
        rows = conn.execute(
            "SELECT id FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND conversation_id=ANY(%s::text[]) AND is_current AND NOT deleted AND NOT suppressed AND NOT retired "
            "AND document->'observed'->'source_references' IS NOT NULL "
            "AND document->'observed'->'source_references' @> %s",
            (*params, sourced_conversations, Jsonb([reference(observed)]))).fetchall()
        edges.extend((document["event_id"], row["id"]) for row in rows)
    for source, note in edges:
        conn.execute(
            "INSERT INTO memory_event_dependencies(tenant_id,owner_id,brain_id,input_event_id,output_event_id) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (*params, source, note))
