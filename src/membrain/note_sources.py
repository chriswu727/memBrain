"""Resolve explicit note references when either side of a host turn is recorded."""
from psycopg.types.json import Jsonb

from .notes import NOTES_CONVERSATION


def resolve(service, conn, principal, brain, references, *, reject_unavailable=False):
    """Read exact eligible messages; a note may wait only for an identity not recorded yet."""
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
    # Look through tombstones and old revisions as well: a missing eligible row does not mean the
    # source has yet to arrive. Once a key is known, only its current exact revision can support a note.
    identities = list(dict.fromkeys(key[:2] for key in keys))
    rows = conn.execute(
        "SELECT latest.* FROM unnest(%s::text[],%s::text[]) AS refs(producer_ref,source_key) "
        "CROSS JOIN LATERAL (SELECT source.producer_ref,source.source_key,source.source_revision,"
        "source.conversation_id,source.is_current,source.deleted,source.suppressed,source.retired,source.document "
        "FROM memory_events source WHERE source.tenant_id=%s AND source.owner_id=%s AND source.brain_id=%s "
        "AND source.producer_ref=refs.producer_ref AND source.source_key=refs.source_key "
        "ORDER BY source.source_revision DESC LIMIT 1) latest",
        ([key[0] for key in identities], [key[1] for key in identities], *service._params(principal, brain["id"])),
    ).fetchall()
    known = {(row["producer_ref"], row["source_key"]): row for row in rows}
    documents = []
    for key in dict.fromkeys(keys):
        row = known.get(key[:2])
        if row is None:
            continue
        document = row["document"]
        observed = (document or {}).get("observed", {})
        if (row["source_revision"] == key[2] and row["is_current"]
                and not any(row[name] for name in ("deleted", "suppressed", "retired"))
                and row["conversation_id"] not in (NOTES_CONVERSATION, AFFECT_CONVERSATION)
                and observed.get("event_kind") == "message"
                and observed.get("delivery_state") not in ("draft", "cancelled")):
            documents.append(document)
        elif reject_unavailable:
            raise DomainError("source_unavailable", "An exact note source is no longer available.")
    return documents


def reference(observed):
    return {name: observed[name] for name in ("producer_ref", "source_event_key", "source_revision")}


def link(service, conn, principal, brain, document):
    from .affect import AFFECT_CONVERSATION

    params = service._params(principal, brain["id"])
    observed = document["observed"]
    edges, unavailable = [], set()
    sourced_conversations = [NOTES_CONVERSATION, AFFECT_CONVERSATION]
    if document["scope"]["conversation_id"] in sourced_conversations:
        references = observed.get("source_references", [])
        if references:
            sources = resolve(service, conn, principal, brain, references, reject_unavailable=True)
            edges.extend((source["event_id"], document["event_id"]) for source in sources)
    # Find references to the identity, not just this revision. A different revision or an
    # unspoken message cannot leave an earlier interpretation labelled "waiting" indefinitely.
    identity = {name: observed[name] for name in ("producer_ref", "source_event_key")}
    rows = conn.execute(
        "SELECT id,is_current,suppressed,retired,document->'observed'->'source_references' AS refs FROM memory_events "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND conversation_id=ANY(%s::text[]) AND NOT deleted "
        "AND document->'observed'->'source_references' IS NOT NULL "
        "AND document->'observed'->'source_references' @> %s",
        (*params, sourced_conversations, Jsonb([identity]))).fetchall()
    eligible = (document["scope"]["conversation_id"] not in sourced_conversations
                and observed["event_kind"] == "message" and observed["delivery_state"] not in ("draft", "cancelled"))
    for row in rows:
        # Hidden or superseded interpretations still retain bodies that an erasure must reach.
        edges.append((document["event_id"], row["id"]))
        active = row["is_current"] and not row["suppressed"] and not row["retired"]
        if active and (not eligible or any(
                ref["source_revision"] != observed["source_revision"] for ref in row["refs"]
                if all(ref[name] == value for name, value in identity.items()))):
            unavailable.add(row["id"])
    for source, note in edges:
        conn.execute(
            "INSERT INTO memory_event_dependencies(tenant_id,owner_id,brain_id,input_event_id,output_event_id) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (*params, source, note))
    if unavailable:
        # Keep the edges even for unavailable interpretations. A later content erasure must still
        # reach their retired bodies and any dependent affect records or archived copies.
        affected = service._dependent_events(conn, principal, brain, unavailable)
        conn.execute(
            "UPDATE memory_events SET retired=true WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND id=ANY(%s::text[])", (*params, sorted(affected)))
        service._invalidate(conn, principal, brain, event_ids=sorted(affected))
        service._advance(conn, principal, brain)
