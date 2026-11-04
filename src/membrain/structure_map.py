"""A bounded projection of stored memory versions and their explicit structural relationships."""
from __future__ import annotations

from .archive_views import memory_parents, memory_sources
from .companion_map import _Graph
from .helpers import DomainError, now
from .memory_map import _COLUMNS, _VISIBLE, memory_map
from .notes import NOTES_CONVERSATION


def memory_key(identifier, revision):
    return f"memory:{identifier}@{revision}"


def episode_key(identifier, revision):
    return f"episode:{identifier}@{revision}"


def _protected_sources(conn, params, ids):
    if not ids:
        return set()
    return {row["input_event_id"] for row in conn.execute(
        "SELECT DISTINCT d.input_event_id FROM memory_event_dependencies d JOIN memory_events n "
        "ON n.tenant_id=d.tenant_id AND n.owner_id=d.owner_id AND n.brain_id=d.brain_id AND n.id=d.output_event_id "
        "WHERE d.tenant_id=%s AND d.owner_id=%s AND d.brain_id=%s AND d.input_event_id=ANY(%s::text[]) "
        "AND n.is_current AND NOT n.deleted AND NOT n.suppressed AND NOT n.retired AND n.document IS NOT NULL "
        "AND n.conversation_id=%s AND ("
        "split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive' OR "
        "split_part(n.document->'observed'->'content'->>'text','] ',1) LIKE '%% · sensitive · %%')",
        (*params, sorted(ids), NOTES_CONVERSATION),
    ).fetchall()}


def structure_map(service, principal, brain_id, *, max_nodes=200, max_edges=400, include_sensitive=False, trace=None):
    for value, low, high in ((max_nodes, 1, 500), (max_edges, 0, 1000)):
        if type(value) is not int or not low <= value <= high:
            raise DomainError("validation_failed", "Memory structures allow 1–500 nodes and 0–1000 edges.")
    if type(include_sensitive) is not bool:
        raise DomainError("validation_failed", "include_sensitive must be a boolean.")
    graph = _Graph(max_nodes, max_edges)
    params = service._params(principal, brain_id)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL statement_timeout = '2s'")
        conn.execute("SET LOCAL lock_timeout = '500ms'")
        brain = service._brain(conn, principal, brain_id)
        assertions = conn.execute(
            "SELECT id,revision,document,event_ids,is_current FROM memory_assertions "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current "
            "AND NOT invalidated AND NOT deleted AND NOT suppressed AND document IS NOT NULL "
            "AND document->>'lifecycle' IN ('active','dormant') ORDER BY created_at DESC,id LIMIT %s",
            (*params, max_nodes // 3 + 1),
        ).fetchall()
        episodes = conn.execute(
            "SELECT id,revision,document,event_ids FROM memory_episodes "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current "
            "AND NOT invalidated AND NOT deleted AND document IS NOT NULL "
            "ORDER BY created_at DESC,id LIMIT %s", (*params, max_nodes // 8 + 1),
        ).fetchall()
        patterns = conn.execute(
            "SELECT id,document,event_ids FROM memory_pattern_views "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND NOT invalidated AND NOT deleted "
            "AND document IS NOT NULL ORDER BY created_at DESC,id LIMIT %s", (*params, max_nodes // 8 + 1),
        ).fetchall()
        base = memory_map(service, principal, brain_id, max_nodes=max(1, max_nodes // 2) if assertions or episodes or patterns else max_nodes,
                          max_edges=max_edges, include_sensitive=include_sensitive, trace=trace, _connection=conn)
        graph.nodes.update((node["id"], node) for node in base["nodes"])
        graph.truncated = base["truncated"]
        cap = max(1, max_nodes // 3)
        graph.truncated |= len(assertions) > cap or len(episodes) > max_nodes // 8 or len(patterns) > max_nodes // 8
        assertions, episodes, patterns = assertions[:cap], episodes[:max_nodes // 8], patterns[:max_nodes // 8]
        requested = {key for row in assertions for key in memory_parents(row["document"])}
        requested.update((ref["memory_id"], ref["revision"]) for row in patterns
                         for ref in row["document"].get("source_memory_versions", []))
        members = conn.execute(
            "SELECT episode_id,episode_revision,memory_id,memory_revision,role FROM memory_episode_members "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND (episode_id,episode_revision) IN "
            "(SELECT * FROM unnest(%s::text[],%s::bigint[])) ORDER BY episode_id,position LIMIT %s",
            (*params, [row["id"] for row in episodes], [row["revision"] for row in episodes], max_edges + 1),
        ).fetchall() if episodes else []
        graph.truncated |= len(members) > max_edges
        members = members[:max_edges]
        requested.update((row["memory_id"], row["memory_revision"]) for row in members)
        known = {(row["id"], row["revision"]): row for row in assertions}
        missing = sorted(requested - known.keys())[:max_nodes]
        if missing:
            parents = conn.execute(
                "SELECT id,revision,document,event_ids,is_current FROM memory_assertions "
                "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND NOT invalidated AND NOT deleted "
                "AND NOT suppressed AND document IS NOT NULL AND (id,revision) IN "
                "(SELECT * FROM unnest(%s::text[],%s::bigint[])) ORDER BY id,revision",
                (*params, [key[0] for key in missing], [key[1] for key in missing]),
            ).fetchall()
            known.update(((row["id"], row["revision"]), row) for row in parents)
        source_ids = {identifier for row in known.values() for identifier in memory_sources(row["document"])}
        source_ids.update(identifier for row in [*episodes, *patterns] for identifier in row["event_ids"])
        # Root lists can be much larger than the visible sample. Resolve privacy before bounding source nodes.
        protected = _protected_sources(conn, params, source_ids)
        for row in known.values():
            doc = row["document"]
            representation = doc.get("representation", "semantic_anchor")
            region = "schemas" if representation in {"schema", "procedure"} else "semantic"
            graph.node(memory_key(row["id"], row["revision"]), "assertion", region, doc["statement"],
                       doc["system_time"]["recorded_at"], sensitive=bool(memory_sources(doc) & protected),
                       masked=bool(memory_sources(doc) & protected) and not include_sensitive,
                       statement=doc["statement"][:2048],
                       revision=row["revision"], representation=representation, lifecycle=doc["lifecycle"],
                       epistemic_status=doc["epistemic_status"], current=row["is_current"],
                       activation=doc["dynamics"]["activation"], retention_priority=doc["dynamics"]["retention_priority"])
        for row in episodes:
            doc = row["document"]
            sensitive = bool(set(row["event_ids"]) & protected)
            graph.node(episode_key(row["id"], row["revision"]), "episode", "episodic",
                       doc.get("organization_statement") or "Consolidated episode", sensitive=sensitive,
                       masked=sensitive and not include_sensitive, revision=row["revision"], state=doc["state"])
        for row in patterns:
            doc = row["document"]
            sensitive = bool(set(row["event_ids"]) & protected)
            graph.node("pattern:" + row["id"], "pattern", "schemas", doc.get("summary") or "Cross-episode pattern",
                       sensitive=sensitive, masked=sensitive and not include_sensitive)
        sources = conn.execute(
            f"SELECT {_COLUMNS},revision FROM memory_events WHERE {_VISIBLE} AND id=ANY(%s::text[]) "
            "AND conversation_id IS DISTINCT FROM %s AND document->'observed'->>'actor_role' IN ('user','assistant') "
            "ORDER BY sequence DESC LIMIT %s", (*params, sorted(source_ids), NOTES_CONVERSATION, max_nodes + 1),
        ).fetchall() if source_ids else []
        graph.truncated |= len(sources) > max_nodes
        source_versions = {}
        for row in sources[:max_nodes]:
            ident = "msg:" + row["id"]
            source_versions[(row["id"], row["revision"])] = ident
            if ident in graph.nodes:
                continue
            sensitive = row["id"] in protected
            graph.node(ident, "message", "episodes", row["text"] or "", row["recorded_at"],
                       sensitive=sensitive, masked=sensitive and not include_sensitive, actor_role=row["actor_role"])
        for edge in base["edges"]:
            graph.edge(edge["source"], edge["target"], edge["type"], edge["basis"])
        for row in known.values():
            doc, ident = row["document"], memory_key(row["id"], row["revision"])
            for ref in doc["evidence_refs"]:
                target = source_versions.get((ref["event_id"], ref["event_revision"]))
                if target:
                    graph.edge(ident, target, "memory_evidence", ref["relationship"])
            for parent in memory_parents(doc):
                graph.edge(ident, memory_key(*parent), "memory_derivation", "source_memory_versions")
        for row in episodes:
            for ref in row["document"]["member_refs"]:
                target = source_versions.get((ref["event_id"], ref["revision"]))
                if target:
                    graph.edge(episode_key(row["id"], row["revision"]), target, "episode_evidence", "member_refs")
        for row in members:
            graph.edge(episode_key(row["episode_id"], row["episode_revision"]),
                       memory_key(row["memory_id"], row["memory_revision"]), "episode_member", row["role"])
        for row in patterns:
            for ref in row["document"].get("source_memory_versions", []):
                graph.edge("pattern:" + row["id"], memory_key(ref["memory_id"], ref["revision"]),
                           "pattern_member", "source_memory_versions")
        _relations(conn, params, graph, known, max_edges)
    graph.finish()
    nodes = list(graph.nodes.values())
    trace_result = {**base["trace"], "shown": sum(bool(node.get("traced")) for node in nodes)} if base.get("trace") else None
    return {"brain_id": brain_id, "contract_version": "memory-structure-v1", "generated_at": now(),
            "limits": {"max_nodes": max_nodes, "max_edges": max_edges}, "nodes": nodes, "edges": graph.edges,
            "truncated": graph.truncated, "trace": trace_result,
            "generations": {key: brain[key] for key in ("dependency_generation", "scope_generation", "durable_sequence")},
            "regions": [{"id": region, "count": sum(node["region"] == region for node in nodes)}
                        for region in dict.fromkeys(node["region"] for node in nodes)],
            "coverage": {"records": "bounded_current_and_referenced_versions", "relationships": "stored_only",
                         "companion": "separate_graph", "working_state": "not_projected"},
            "limitations": ["A bounded sample, not the entire database.",
                            "Positions are a visualization of recorded topology, not biological anatomy.",
                            "Travelling signals are simulated, not a live execution trace."]}


def _relations(conn, params, graph, known, max_edges):
    if not known or not max_edges:
        return
    ids = sorted({key[0] for key in known})
    rows = conn.execute(
        "SELECT id,source_id,source_revision,target_id,target_revision,relation FROM memory_associations "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND NOT invalidated "
        "AND source_id=ANY(%s::text[]) AND target_id=ANY(%s::text[]) ORDER BY id LIMIT %s",
        (*params, ids, ids, max_edges + 1),
    ).fetchall()
    graph.truncated |= len(rows) > max_edges
    for row in rows[:max_edges]:
        graph.edge(memory_key(row["source_id"], row["source_revision"]), memory_key(row["target_id"], row["target_revision"]),
                   "association", row["relation"])
    rows = conn.execute(
        "SELECT id,document FROM memory_belief_relations WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND NOT invalidated AND NOT deleted AND document IS NOT NULL AND memory_ids && %s::text[] "
        "ORDER BY id LIMIT %s", (*params, ids, max_edges + 1),
    ).fetchall()
    graph.truncated |= len(rows) > max_edges
    for row in rows[:max_edges]:
        doc = row["document"]
        source = doc["source_memory_version"]
        for target in doc["target_memory_versions"]:
            graph.edge(memory_key(source["memory_id"], source["revision"]), memory_key(target["memory_id"], target["revision"]),
                       "belief_relation", doc["kind"])
