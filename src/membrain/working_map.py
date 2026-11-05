"""Stored working-state versions and their currently available evidence."""
from __future__ import annotations

import json
from datetime import datetime

from .helpers import DomainError, digest, now
from .memory_map import REGIONS, sensitive_note_ids
from .notes import NOTES_CONVERSATION, parse_note


def load_working(conn, params, graph):
    limit = max(1, graph.max_nodes // 8)
    rows = conn.execute(
        "SELECT conversation_id,branch_id,revision,CASE WHEN octet_length(document::text)<=65536 "
        "THEN document END AS document FROM memory_working_states "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "ORDER BY (document->>'updated_at')::timestamptz DESC,conversation_id,branch_id LIMIT %s", (*params, limit + 1),
    ).fetchall()
    graph.truncated |= len(rows) > limit or any(row["document"] is None for row in rows)
    return [row for row in rows[:limit] if row["document"] is not None]


def working_sources(rows):
    return {ref["event_id"] for row in rows for field in ("items", "open_loops")
            for item in row["document"][field] for ref in item["evidence_refs"]}


def project_working(service, conn, principal, brain, graph, rows, protected, include_sensitive):
    requested = working_sources(rows)
    cap = max(64, min(1024, graph.max_nodes * 4))
    graph.truncated |= len(requested) > cap
    events = service._events(conn, principal, brain, event_ids=sorted(requested)[:cap], limit=cap) if requested else []
    lookup = {event["event_id"]: event for event in events}
    notes = {event["event_id"]: parse_note(event["observed"]["content"].get("text", "")) for event in events
             if event["scope"]["conversation_id"] == NOTES_CONVERSATION}
    private = protected | sensitive_note_ids(conn, service._params(principal, brain["id"]), requested)
    private |= {ident for ident, (fields, _) in notes.items() if fields.get("sensitive")}
    if requested:
        private.update(row["id"] for row in conn.execute(
            "SELECT id FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND id=ANY(%s::text[]) AND conversation_id=%s AND is_current AND NOT deleted "
            "AND NOT suppressed AND NOT retired AND document IS NOT NULL AND ("
            "split_part(document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive' OR "
            "split_part(document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive · %%')",
            (*service._params(principal, brain["id"]), sorted(requested), NOTES_CONVERSATION),
        ).fetchall())
    moment = datetime.fromisoformat(now().replace("Z", "+00:00"))
    for row in rows:
        doc = row["document"]
        ident = "working:" + digest([*service._params(principal, brain["id"]), row["conversation_id"],
                                     row["branch_id"], row["revision"]])
        refs = {ref["event_id"] for field in ("items", "open_loops") for item in doc[field] for ref in item["evidence_refs"]}
        sensitive = bool(refs & private)
        graph.node(ident, "working_state", "working", "Stored working state", doc["updated_at"] if refs <= lookup.keys() else None,
                   sensitive=sensitive, masked=sensitive and not include_sensitive, revision=row["revision"],
                   conversation=row["conversation_id"], branch=row["branch_id"])
        for field in ("items", "open_loops"):
            for item in doc[field]:
                try:
                    candidates = [lookup[key] for key in {ref["event_id"] for ref in item["evidence_refs"]} if key in lookup]
                    sources = service._evidence(item["evidence_refs"], candidates)
                except DomainError:
                    continue
                sensitive = any(source["event_id"] in private for source in sources)
                if field == "items":
                    key, label = item["key"], item["key"]
                    value = item["value"]
                    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
                    expires = item["expires_at"]
                    details = {"knowledge_state": item["knowledge_state"], "text": text[:2048],
                               "text_truncated": len(text) > 2048, "expires_at": expires,
                               "expired": bool(expires and datetime.fromisoformat(expires.replace("Z", "+00:00")) <= moment)}
                    kind, recorded = "working_item", item["updated_at"]
                else:
                    key, label = item["loop_id"], item["description"]
                    details = {"status": item["state"], "text": label[:2048], "text_truncated": len(label) > 2048,
                               "due_time": item["due_time"]}
                    kind, recorded = "open_loop", item["last_updated_at"]
                child = ident + ":" + kind + ":" + digest(key)
                graph.node(child, kind, "working", label, recorded, sensitive=sensitive,
                           masked=sensitive and not include_sensitive, revision=row["revision"], **details)
                graph.edge(ident, child, "working_member", field)
                for source, ref in zip(sources, item["evidence_refs"], strict=True):
                    event_id = source["event_id"]
                    is_note = event_id in notes
                    fields, sentence = notes.get(event_id, ({}, source["observed"]["content"].get("text", "Recorded event")))
                    target = ("note:" if is_note else "msg:") + event_id
                    sensitive = event_id in private
                    event_kind = source["observed"]["event_kind"]
                    kind = fields.get("kind", "other") if is_note else "message" if event_kind == "message" else "source_event"
                    graph.node(target, kind,
                               REGIONS.get(fields.get("kind"), "other") if is_note else "episodes", sentence,
                               source["system_time"]["recorded_at"], sensitive=sensitive,
                               masked=sensitive and not include_sensitive, revision=source["revision"], event_kind=event_kind)
                    graph.edge(child, target, "working_evidence", ref["relationship"])
