"""A bounded view of recorded notes and their sources, without inferred semantic links."""
from __future__ import annotations

from .helpers import DomainError, now
from .notes import NOTES_CONVERSATION, parse_note
from .privacy import neutralize

REGIONS = {
    "person": "people", "constraint": "constraints", "preference": "preferences", "plan": "plans",
    "agent_commitment": "commitments", "routine": "routines", "milestone": "milestones",
    "relationship": "relationship", "other": "other", "message": "episodes",
}
_VISIBLE = ("tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current AND NOT deleted "
            "AND NOT suppressed AND NOT retired AND document IS NOT NULL "
            "AND document->'observed'->>'event_kind'='message'")
_COLUMNS = ("id,sequence,conversation_id,document->'observed'->>'actor_role' AS actor_role,"
            "left(document->'observed'->'content'->>'text',480) AS text,"
            "document->'system_time'->>'recorded_at' AS recorded_at")


def _label(text):
    return neutralize(" ".join(text.split()))[:80]


def memory_map(service, principal, brain_id, *, max_nodes=200, max_edges=400, include_sensitive=False):
    """Return a bounded sample; region counts describe the sample, not the entire brain.

    Weights are layout hints, not inferred activation or recall strength. Recent user messages and note
    sources share the episode budget; assistant replies are excluded. Sensitive flags can mask known note
    sources, but unclassified original messages can still contain personal information. This is an
    authenticated local view, not an anonymized public export.
    """
    for value, minimum, maximum in ((max_nodes, 1, 500), (max_edges, 0, 1000)):
        if type(value) is not int or not minimum <= value <= maximum:
            raise DomainError("validation_failed", "Memory maps allow 1–500 nodes and 0–1000 edges.")
    if type(include_sensitive) is not bool:
        raise DomainError("validation_failed", "include_sensitive must be a boolean.")
    params = service._params(principal, brain_id)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL statement_timeout = '2s'")
        conn.execute("SET LOCAL lock_timeout = '500ms'")
        service._brain(conn, principal, brain_id)
        notes = conn.execute(
            f"SELECT {_COLUMNS} FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
            "AND document->'observed'->>'actor_role' IN ('user','assistant') "
            "ORDER BY sequence DESC LIMIT %s", (*params, NOTES_CONVERSATION, max_nodes + 1),
        ).fetchall()
        recent = conn.execute(
            f"SELECT {_COLUMNS} FROM memory_events WHERE {_VISIBLE} AND conversation_id IS DISTINCT FROM %s "
            "AND document->'observed'->>'actor_role'='user' ORDER BY sequence DESC LIMIT %s",
            (*params, NOTES_CONVERSATION, max_nodes + 1),
        ).fetchall()
        note_budget = max(1, max_nodes * 3 // 4) if recent else max_nodes
        chosen_notes = notes[:note_budget]
        note_ids = [row["id"] for row in chosen_notes]
        links = conn.execute(
            "SELECT d.output_event_id,d.input_event_id,e.sequence FROM memory_event_dependencies d "
            "JOIN memory_events e ON e.tenant_id=d.tenant_id AND e.owner_id=d.owner_id "
            "AND e.brain_id=d.brain_id AND e.id=d.input_event_id "
            "WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s AND d.output_event_id=ANY(%s::text[]) "
            "AND e.is_current AND NOT e.deleted AND NOT e.suppressed AND NOT e.retired "
            "AND e.document IS NOT NULL AND e.conversation_id IS DISTINCT FROM %s "
            "AND e.document->'observed'->>'event_kind'='message' "
            "AND e.document->'observed'->>'actor_role'='user' "
            "ORDER BY e.sequence DESC,d.output_event_id LIMIT %s",
            (*params, note_ids, NOTES_CONVERSATION, max_edges + max_nodes + 1),
        ).fetchall() if note_ids else []
        source_ids = list(dict.fromkeys(row["input_event_id"] for row in links))[:max_nodes]
        sources = conn.execute(
            f"SELECT {_COLUMNS} FROM memory_events WHERE {_VISIBLE} AND id=ANY(%s::text[]) "
            "AND document->'observed'->>'actor_role'='user' ORDER BY sequence DESC",
            (*params, source_ids),
        ).fetchall() if source_ids else []
        message_rows = {row["id"]: row for row in [*recent[:1], *sources, *recent]}
        chosen_messages = list(message_rows.values())[:max_nodes - len(chosen_notes)]
        hidden_sources = set()
        if not include_sensitive and chosen_messages:
            # A masked note's original message must not reveal the same content through another node.
            hidden_sources = {row["input_event_id"] for row in conn.execute(
                "SELECT DISTINCT d.input_event_id FROM memory_event_dependencies d "
                "JOIN memory_events n ON n.tenant_id=d.tenant_id "
                "AND n.owner_id=d.owner_id AND n.brain_id=d.brain_id AND n.id=d.output_event_id "
                "WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s AND d.input_event_id=ANY(%s::text[]) "
                "AND n.is_current AND NOT n.deleted AND NOT n.suppressed "
                "AND NOT n.retired AND n.conversation_id=%s AND n.document IS NOT NULL "
                "AND left(n.document->'observed'->'content'->>'text',1)='[' AND ("
                "split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive' OR "
                "split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive · %%')",
                (*params, [row["id"] for row in chosen_messages], NOTES_CONVERSATION),
            )}
    return _project(brain_id, chosen_notes, chosen_messages, links, hidden_sources,
                    max_nodes=max_nodes, max_edges=max_edges, include_sensitive=include_sensitive,
                    truncated=(len(notes) > len(chosen_notes) or len(recent) > len(chosen_messages)
                               or len(links) >= max_edges + max_nodes + 1))


def _project(brain_id, notes, messages, links, hidden_sources, *, max_nodes, max_edges,
             include_sensitive, truncated):
    nodes, fields_by_id = [], {}
    for row in notes:
        fields, text = parse_note(row["text"] or "")
        sensitive = bool(fields.get("sensitive"))
        masked = sensitive and not include_sensitive
        kind = fields.get("kind", "other")
        fields_by_id[row["id"]] = {} if masked else fields
        nodes.append({"id": "note:" + row["id"], "region": REGIONS.get(kind, "other"), "kind": kind,
                      "label": "Sensitive memory" if masked else _label(text),
                      "status": None if masked else fields.get("status"),
                      "date": None if masked else fields.get("due") or fields.get("occurs_at"),
                      "sensitive": sensitive, "recorded_at": row["recorded_at"],
                      "weight": 1.0 if fields.get("pinned") else 0.5})
    for row in messages:
        masked = row["id"] in hidden_sources
        nodes.append({"id": "msg:" + row["id"], "region": "episodes", "kind": "message",
                      "label": "Sensitive memory" if masked else _label(row["text"] or ""),
                      "status": None, "date": None, "sensitive": masked,
                      "recorded_at": row["recorded_at"], "weight": 0.25})
    available = {node["id"] for node in nodes}
    edges, seen = [], set()

    def edge(source, target, kind, basis):
        key = (source, target, kind)
        if source != target and source in available and target in available and key not in seen:
            seen.add(key)
            edges.append({"source": source, "target": target, "type": kind, "basis": basis})

    for link in links:
        edge("note:" + link["output_event_id"], "msg:" + link["input_event_id"], "derived_from", "source_event_ids")
    people = {}
    for ident, fields in fields_by_id.items():
        if fields.get("kind") == "person" and fields.get("about"):
            people.setdefault(fields["about"], []).append(ident)
    for ident, fields in fields_by_id.items():
        targets = people.get(fields.get("about"), [])
        if len(targets) == 1:
            edge("note:" + ident, "note:" + targets[0], "about_person", "about")
    regions = []
    for region in REGIONS.values():
        items = [node for node in nodes if node["region"] == region]
        regions.append({"id": region, "count": len(items),
                        "last_activity": max((node["recorded_at"] for node in items if node["recorded_at"]), default=None)})
    return {"brain_id": brain_id, "generated_at": now(), "truncated": truncated or len(edges) > max_edges,
            "limits": {"max_nodes": max_nodes, "max_edges": max_edges},
            "regions": regions, "nodes": nodes, "edges": edges[:max_edges]}
