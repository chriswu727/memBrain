"""Resolve explicit note references when either side of a host turn is recorded."""
from psycopg.types.json import Jsonb

from .notes import NOTES_CONVERSATION


def resolve(service, conn, principal, brain, references):
    from .affect import AFFECT_CONVERSATION
    from .helpers import DomainError

    if not isinstance(references, (list, tuple)) or not 1 <= len(references) <= 64:
        raise DomainError("validation_failed", "Choose 1 to 64 source messages.")
    keys = []
    for ref in references:
        if (not isinstance(ref, dict)
                or set(ref) != {"producer_ref", "source_event_key", "source_revision"}
                or any(not isinstance(ref[name], str) or not 1 <= len(ref[name]) <= 256
                       for name in ("producer_ref", "source_event_key"))
                or type(ref["source_revision"]) is not int or not 1 <= ref["source_revision"] <= 2**63 - 1):
            raise DomainError("validation_failed", "Source messages require exact producer, key and revision.")
        keys.append((ref["producer_ref"], ref["source_event_key"], ref["source_revision"]))
    rows = conn.execute(
        "SELECT document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND (producer_ref,source_key,source_revision) IN "
        "(SELECT * FROM unnest(%s::text[],%s::text[],%s::bigint[])) "
        "AND is_current AND NOT deleted AND NOT suppressed AND NOT retired AND document IS NOT NULL "
        "AND (conversation_id IS NULL OR NOT (conversation_id=ANY(%s::text[]))) "
        "AND document->'observed'->>'event_kind'='message' "
        "AND document->'observed'->>'delivery_state' NOT IN ('draft','cancelled')",
        (*service._params(principal, brain["id"]), [key[0] for key in keys], [key[1] for key in keys],
         [key[2] for key in keys], [NOTES_CONVERSATION, AFFECT_CONVERSATION]),
    ).fetchall()
    documents = {(item["observed"]["producer_ref"], item["observed"]["source_event_key"],
                  item["observed"]["source_revision"]): item for row in rows for item in [row["document"]]}
    return [documents[key] for key in dict.fromkeys(keys) if key in documents]


def read_messages(service, principal, brain_id, references):
    from .service import reading

    with reading(), service.database.transaction(principal) as conn:
        brain = service._brain(conn, principal, brain_id)
        documents = resolve(service, conn, principal, brain, references)
        return {"dependency_generation": brain["dependency_generation"], "items": [
            {"reference": reference(item["observed"]), "event_id": item["event_id"],
             "actor_role": item["observed"]["actor_role"], "text": item["observed"]["content"].get("text") or ""}
            for item in documents]}


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
