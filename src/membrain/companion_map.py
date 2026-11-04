"""A read-only graph of companion state and its surviving evidence."""
from __future__ import annotations

from . import affect, mood, persona, persona_growth, relationship
from .helpers import DomainError, now
from .memory_map import REGIONS
from .notes import NOTES_CONVERSATION, parse_note
from .privacy import neutralize


class _Graph:
    def __init__(self, max_nodes, max_edges):
        self.max_nodes, self.max_edges = max_nodes, max_edges
        self.nodes, self.edges, self.seen = {}, [], set()
        self.truncated = False

    def node(self, ident, kind, region, label, recorded_at=None, *, sensitive=False, **details):
        if ident in self.nodes:
            return ident
        if len(self.nodes) >= self.max_nodes:
            self.truncated = True
            return None
        self.nodes[ident] = {
            "id": ident, "kind": kind, "region": region,
            "label": "Sensitive memory" if sensitive else neutralize(" ".join(label.split()))[:80],
            "recorded_at": recorded_at, "sensitive": sensitive,
            "details": {} if sensitive else details,
        }
        return ident

    def edge(self, source, target, kind, basis):
        key = source, target, kind
        if source not in self.nodes or target not in self.nodes or source == target or key in self.seen:
            return
        if len(self.edges) >= self.max_edges:
            self.truncated = True
            return
        self.seen.add(key)
        self.edges.append({"source": source, "target": target, "type": kind, "basis": basis})


def companion_map(service, principal, brain_id, *, max_nodes=200, max_edges=400, include_sensitive=False):
    for value, low, high in ((max_nodes, 1, 500), (max_edges, 0, 1000)):
        if type(value) is not int or not low <= value <= high:
            raise DomainError("validation_failed", "Companion maps allow 1–500 nodes and 0–1000 edges.")
    if type(include_sensitive) is not bool:
        raise DomainError("validation_failed", "include_sensitive must be a boolean.")
    graph = _Graph(max_nodes, max_edges)
    when = mood._clock(None)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL statement_timeout = '2s'")
        conn.execute("SET LOCAL lock_timeout = '500ms'")
        service._brain(conn, principal, brain_id)
        versions, _ = persona._entries(service, conn, principal, brain_id, limit=max_nodes + 1)
        proposals = persona_growth._State(service, conn, principal, brain_id).proposals
        current_mood = mood._read(service, conn, principal, brain_id, when)
        state = relationship._state(service, conn, principal, brain_id)
        moments = relationship._moments(service, conn, principal, brain_id, state["after"])
        _project(service, conn, principal, brain_id, graph, versions, proposals, current_mood, state,
                 moments, include_sensitive)
    nodes = list(graph.nodes.values())
    regions = list(dict.fromkeys(node["region"] for node in nodes))
    return {
        "brain_id": brain_id, "contract_version": "companion-map-v1", "generated_at": now(),
        "limits": {"max_nodes": max_nodes, "max_edges": max_edges},
        "nodes": nodes, "edges": graph.edges, "truncated": graph.truncated,
        "regions": [{"id": region, "count": sum(node["region"] == region for node in nodes)}
                    for region in regions],
        "coverage": {"persona": "bounded_versions", "proposals": "stored_only",
                     "mood": "current_and_bounded_triggers", "relationship": "settings_and_shared_moments",
                     "learned_memory": "not_projected", "recall": "not_observed"},
        "limitations": ["Positions and node size do not measure memory strength.",
                        "Edges show recorded dependencies, not a reasoning or execution timeline.",
                        "This authenticated local view is not an anonymized public export."],
    }


def _project(service, conn, principal, brain_id, graph, versions, proposals, current_mood, state,
             moments, include_sensitive):
    params = service._params(principal, brain_id)
    requested = set()
    for version in versions:
        requested.update((version.get("feedback") or {}).get("source_event_ids", []))
    for proposal in proposals:
        requested.update(source["event_id"] for source in proposal["sources"])
    requested.update(moment["id"] for moment in moments)
    affect_ids = [trigger["source"]["id"] for trigger in current_mood["triggers"]
                  if trigger["source"]["kind"] == "affect"]
    feelings = {record["id"]: record for record in affect._records(
        service, conn, principal, brain_id, ids=affect_ids, limit=graph.max_nodes)} if affect_ids else {}
    for record in feelings.values():
        requested.add(record["note_id"])
        requested.update(record["source_event_ids"])
    for trigger in current_mood["triggers"]:
        requested.add(trigger["source"]["id"])
        if trigger["source"].get("note_id"):
            requested.add(trigger["source"]["note_id"])
    dependencies = conn.execute(
        "SELECT d.output_event_id,d.input_event_id FROM memory_event_dependencies d "
        "JOIN memory_events n ON n.tenant_id=d.tenant_id AND n.owner_id=d.owner_id "
        "AND n.brain_id=d.brain_id AND n.id=d.output_event_id "
        "WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s "
        "AND d.output_event_id=ANY(%s::text[]) AND n.conversation_id=%s "
        "AND n.is_current AND NOT n.deleted AND NOT n.suppressed AND NOT n.retired "
        "AND n.document IS NOT NULL ORDER BY d.output_event_id,d.input_event_id LIMIT %s",
        (*params, sorted(requested), NOTES_CONVERSATION, graph.max_edges + 1),
    ).fetchall() if requested else []
    graph.truncated |= len(dependencies) > graph.max_edges or not current_mood["complete_history"]
    dependencies = dependencies[:graph.max_edges]
    requested.update(row["input_event_id"] for row in dependencies)
    rows = conn.execute(
        "SELECT id,revision,conversation_id,document->'observed'->>'actor_role' AS actor_role,"
        "left(document->'observed'->'content'->>'text',480) AS text,"
        "document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current AND NOT deleted "
        "AND NOT suppressed AND NOT retired AND document IS NOT NULL "
        "AND id=ANY(%s::text[]) AND document->'observed'->>'event_kind'='message' "
        "AND document->'observed'->>'actor_role' IN ('user','assistant') "
        "ORDER BY sequence DESC LIMIT %s", (*params, sorted(requested), graph.max_nodes + 1),
    ).fetchall() if requested else []
    graph.truncated |= len(rows) > graph.max_nodes or len(versions) > graph.max_nodes
    rows = {row["id"]: row for row in rows[:graph.max_nodes]}
    hidden = set()
    if rows and not include_sensitive:
        hidden = {row["input_event_id"] for row in conn.execute(
            "SELECT DISTINCT d.input_event_id FROM memory_event_dependencies d "
            "JOIN memory_events n ON n.tenant_id=d.tenant_id AND n.owner_id=d.owner_id "
            "AND n.brain_id=d.brain_id AND n.id=d.output_event_id "
            "WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s "
            "AND d.input_event_id=ANY(%s::text[]) AND n.is_current AND NOT n.deleted "
            "AND NOT n.suppressed AND NOT n.retired AND n.document IS NOT NULL "
            "AND n.conversation_id=%s AND left(n.document->'observed'->'content'->>'text',1)='[' "
            "AND (split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive' "
            "OR split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive · %%')",
            (*params, list(rows), NOTES_CONVERSATION)).fetchall()}

    def event(ident):
        row = rows.get(ident)
        if row is None:
            return None
        is_note = row["conversation_id"] == NOTES_CONVERSATION
        if not is_note and row["actor_role"] != "user":
            return None
        fields, text = parse_note(row["text"] or "") if is_note else ({}, row["text"] or "")
        masked = not include_sensitive and (ident in hidden or fields.get("sensitive", False))
        return graph.node(("note:" if is_note else "msg:") + ident,
                          fields.get("kind", "other") if is_note else "message",
                          ("relationship" if fields.get("shared") else REGIONS.get(fields.get("kind"), "other"))
                          if is_note else "episodes", text, row["recorded_at"],
                          sensitive=masked, event_id=ident, revision=row["revision"],
                          actor_role=row["actor_role"], status=fields.get("status"))

    mood_id = graph.node("mood:current", "simulated_mood", "mood", "Simulated mood: " + current_mood["label"],
                         simulated=True, at_baseline=current_mood["at_baseline"], pinned=current_mood["pinned"],
                         baseline=current_mood["baseline"], back_at_baseline_at=current_mood["back_at_baseline_at"],
                         evaluated_at=current_mood["now"])
    persona_ids = {}
    for version in versions[:graph.max_nodes]:
        feedback = version.get("feedback") or {}
        masked = not include_sensitive and bool(set(feedback.get("source_event_ids", [])) & hidden)
        ident = graph.node("persona:" + version["event_id"], "persona", "persona",
                           f"Personality v{version['version']}: {version['card'].get('name') or 'Companion'}",
                           version["recorded_at"], sensitive=masked, event_id=version["event_id"],
                           version=version["version"], made_by=version["made_by"], action=version["action"],
                           text=persona.render_card(version["card"]))
        persona_ids[version["version"]] = ident
        for source in feedback.get("source_event_ids", []):
            graph.edge(ident, event(source), "based_on_feedback", "accepted_persona_feedback")
    if versions and current_mood["baseline"]["source"] == "persona":
        graph.edge(mood_id, persona_ids.get(versions[0]["version"]), "baseline_from", "persona_baseline_mood")
    for version in versions[:graph.max_nodes]:
        if type(version.get("restored_from")) is int and 0 < version["restored_from"] < version["version"]:
            graph.edge(persona_ids.get(version["version"]), persona_ids.get(version["restored_from"]),
                       "restored_from", "persona_restore")

    for proposal in sorted(proposals, key=lambda item: -item["sequence"])[:graph.max_nodes]:
        masked = not include_sensitive and any(source["event_id"] in hidden for source in proposal["sources"])
        ident = graph.node("proposal:" + proposal["id"], "persona_proposal", "persona", proposal["label"],
                           proposal["proposed_at"], sensitive=masked, event_id=proposal["id"],
                           status=proposal["status"], version=proposal["version"], decided_at=proposal["decided_at"],
                           withdrawn_because=proposal["withdrawn_because"])
        for source in proposal["sources"]:
            graph.edge(ident, event(source["event_id"]), "proposed_from_feedback", "persona_proposal_sources")
        if proposal["status"] == "accepted":
            version_id = persona_ids.get(proposal["version"])
            matched = next((version for version in versions if version["version"] == proposal["version"]), None)
            if matched and (matched.get("feedback") or {}).get("proposal_id") == proposal["id"]:
                graph.edge(version_id, ident, "accepted_proposal", "persona_feedback_proposal_id")

    for trigger in current_mood["triggers"]:
        source = trigger["source"]
        masked = False
        if source["kind"] == "affect":
            record = feelings.get(source["id"])
            if record is None:
                continue
            masked = not include_sensitive and (record["sensitive"]
                                                 or bool(set(record["source_event_ids"]) & hidden))
            source_id = graph.node("affect:" + record["id"], "affect", "emotions", record["label"],
                                   record["recorded_at"], sensitive=masked, basis=record["basis"],
                                   event_id=record["id"])
            graph.edge(source_id, event(record["note_id"]), "feeling_of", "affect_note_id")
        else:
            source_id = event(source["id"])
            masked = bool(source_id and graph.nodes[source_id]["sensitive"])
        if not source_id:
            continue
        ident = graph.node("trigger:" + trigger["id"], "mood_trigger", "mood", trigger["rule"], trigger["at"],
                           sensitive=masked,
                           rule=trigger["rule"], status=trigger["status"], reason=neutralize(trigger["reason"]),
                           ended_at=trigger["ended_at"])
        graph.edge(ident, source_id, "triggered_by", "mood_rule_source")
        if trigger["status"] == "active":
            graph.edge(mood_id, ident, "affected_by", "active_mood_trigger")

    for boundary in state["boundaries"]:
        graph.node("boundary:" + boundary["id"], "boundary", "relationship", boundary["topic"],
                   boundary["recorded_at"], event_id=boundary["id"], aliases=boundary["aliases"])
    support = state["support_style"]
    if support and support["text"]:
        graph.node("support:" + support["id"], "support_style", "relationship", support["text"],
                   support["recorded_at"], event_id=support["id"], text=neutralize(support["text"]))
    for moment in moments:
        event(moment["id"])
    for dependency in dependencies:
        target = event(dependency["input_event_id"])
        if target and target.startswith("msg:"):
            graph.edge(event(dependency["output_event_id"]), target, "derived_from", "source_event_ids")
