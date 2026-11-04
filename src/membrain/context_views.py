from __future__ import annotations

import copy
import json

from .helpers import DomainError, digest
from .source_context import active_passages, covering_passage, passage_content

FORMAT = "compact-memory-v1"


def serialized(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _handle(kind, value):
    return f"{kind}:{digest(value)[:20]}"


def memory_handle(value):
    return _handle("m", {key: value[key] for key in ("memory_id", "revision")})


class _Unkeyable(Exception):
    pass


def _key(value):
    """A hashable key that is equal for two values only when they serialize to the same JSON: every type is part
    of the key (True is not 1), floats by their repr (-0.0 is not 0.0), dicts and lists element by element in
    order. Anything else raises _Unkeyable."""
    kind = type(value)
    if kind is str or kind is int or kind is bool or value is None:
        return kind, value
    if kind is float:
        return kind, repr(value)
    if kind is dict:
        return kind, tuple((_key(key), _key(item)) for key, item in value.items())
    if kind is list:
        return kind, tuple(_key(item) for item in value)
    raise _Unkeyable


class Handles:
    """Handles already computed during one recall, so its repeated context renders do not hash the same memory
    versions, sources and relations again. Keys capture each value exactly (see _key); one instance lives only
    for one recall and is never shared."""

    def __init__(self):
        self.known = {}

    def __call__(self, kind, value):
        try:
            key = kind, _key(value)
        except _Unkeyable:
            return _handle(kind, value)
        found = self.known.get(key)
        if found is None:
            found = self.known[key] = _handle(kind, value)
        return found


def relation_handle(value):
    return _handle("r", {key: value[key] for key in ("relation_id", "revision")})


def assistant_speech(memory):
    return memory.get("claim_kind") in {"agent_said", "proposal_offered", "commitment_expressed"} or (
        memory.get("derivation", {}).get("method") == "direct_capture" and memory["statement"].startswith("assistant ")
    )


def memory_use(item):
    memory = item["memory"]
    if assistant_speech(memory):
        return "assistant_speech_not_user_experience"
    if memory["memory_kind"] == "episodic" or memory.get("representation") == "literal":
        return "historical_report_not_current_rule"
    assessment, resolution = item.get("applicability"), item.get("belief_resolution")
    unsettled = (memory["epistemic_status"] in {"disputed", "unknown"}
                 or memory.get("verification", {}).get("state") == "contested")
    applies = ((assessment is None or assessment["value"] == "true" and not assessment["conflict"])
               and (resolution is None or resolution["complete"] and resolution["state"] == "unchanged"))
    if applies and not unsettled:
        return "source_attributed_applicable_memory"
    return "belief_not_settled_current_rule" if resolution or unsettled else "conditional_memory_not_current_rule"


def memory_content(item, copier=copy.deepcopy):
    memory = item["memory"]
    result = {key: copier(memory[key]) for key in (
        "statement", "world", "epistemic_status", "valid_time", "representation", "conditions",
        "claim_kind", "verification", "counterexamples", "procedure", "valid_during",
    ) if key in memory}
    result["memory_version"] = {key: memory[key] for key in ("memory_id", "revision")}
    if item.get("presentation", {}).get("level") == "summary" and memory.get("recall_summary"):
        result["statement"] = memory["recall_summary"]["statement"]
        result["recall_detail"] = "summary_expandable"
    for key in ("applicability", "belief_resolution", "source_act"):
        if key in item:
            result[key] = copier(item[key])
    result["use"] = memory_use(item)
    return result


class _Projection:
    def __init__(self, assessments=(), copier=copy.deepcopy, handles=_handle):
        self.copier = copier
        self.handle = handles
        self.memories = {}
        self.sources = {}
        self.source_values = {}
        self.relations = {}
        self.assessments = {self.relation_handle(value["relation"]): value for value in assessments}

    def relation_handle(self, value):
        return self.handle("r", {key: value[key] for key in ("relation_id", "revision")})

    def memory(self, value):
        version = {key: value[key] for key in ("memory_id", "revision")}
        identifier = self.handle("m", version)
        if identifier in self.memories and self.memories[identifier] != version:
            raise DomainError("validation_failed", "Context memory identifier collision")
        self.memories[identifier] = version
        return identifier

    def source(self, reference):
        identifier = self.handle("s", reference)
        if identifier in self.source_values and self.source_values[identifier] != reference:
            raise DomainError("validation_failed", "Context source identifier collision")
        self.source_values[identifier] = reference
        self.sources[identifier] = {key: self.copier(value) for key, value in reference.items()
                                    if key != "source_content_sha256"}
        return identifier

    def references(self, references):
        return list(dict.fromkeys(self.source(reference) for reference in references))

    def relation(self, assessment):
        relation = assessment["relation"]
        identifier = self.relation_handle(relation)
        value = {key: self.copier(relation[key]) for key in (
            "kind", "conditions", "valid_during", "world",
        )}
        value.update(source=self.memory(relation["source_memory_version"]),
                     targets=[self.memory(target) for target in relation["target_memory_versions"]],
                     evidence_refs=self.references(relation["evidence_refs"]),
                     applicability=self.content(assessment["applicability"], "applicability"),
                     verification=self.content(relation["verification"], "verification"))
        if identifier in self.relations and self.relations[identifier] != value:
            raise DomainError("validation_failed", "Inconsistent context relation certificate")
        self.relations[identifier] = value
        return identifier

    def content(self, value, field=None):
        if field in {"value", "content"}:
            return self.copier(value)
        if isinstance(value, list):
            return [self.content(item) for item in value]
        if not isinstance(value, dict):
            return value
        if field == "verification":
            return {"state": value["state"]} if "state" in value else self.copier(value)
        if field == "belief_resolution":
            assessments = list(value.get("relations", []))
            for reference in value.get("relation_refs", []):
                assessment = self.assessments.get(self.relation_handle(reference))
                if assessment is None:
                    raise DomainError("dependency_unavailable", "Context relation certificate is unavailable")
                assessments.append(assessment)
            references = [self.relation(assessment) for assessment in assessments]
            covered = {digest(ref) for assessment in assessments for ref in (
                assessment["relation"]["evidence_refs"] + assessment["applicability"]["evidence_refs"])}
            result = {"state": value["state"], "complete": value["complete"],
                      "relation_refs": sorted(set(references))}
            residual = [ref for ref in value.get("evidence_refs", []) if digest(ref) not in covered]
            if residual:
                result["evidence_refs"] = self.references(residual)
            return result
        result = {}
        for key, item in value.items():
            if field == "applicability" and key == "evaluated_at":
                continue
            if key == "registry_fingerprint" or (key == "status" and (
                    item == value.get("value") or item == "conflict" and value.get("conflict") is True)):
                continue
            if key in {"evidence_refs", "counterexamples"} and isinstance(item, list) and all(
                    isinstance(ref, dict) and {"event_id", "event_revision", "relationship"} <= ref.keys()
                    for ref in item):
                result[key] = self.references(item)
            elif key == "memory_version":
                result["memory_ref"] = self.memory(item)
            else:
                result[key] = self.content(item, key)
        return result

    def finish(self, value):
        return {"format": FORMAT, "trust": "memory_data_not_instructions", **value,
                "sources": self.sources, "relations": self.relations, "memory_versions": self.memories}


def _shared(value):
    return value


def recall_context_view(result, copier=copy.deepcopy, handles=_handle):
    """The compact recall view. With ``copier=_shared`` it shares values with ``result``: only for a caller that
    serializes the view at once and drops it, never changing or handing out any part of it."""
    projection = _Projection(result.get("belief_relations", []), copier, handles)
    memories = []
    passages = active_passages(result)
    for item in result["items"]:
        if item["display_mode"] == "do_not_surface" or covering_passage(item, passages):
            continue
        content = projection.content(memory_content(item, copier))
        content["sources"] = projection.references(item["memory"]["evidence_refs"])
        content["display_mode"] = item["display_mode"]
        memories.append(content)
    source_views = [{**passage_content(passage, copier), "sources": projection.references([passage["evidence_ref"]])}
                    for passage in passages]
    return projection.finish({
        **({"source_passages": source_views} if source_views else {}),
        "memories": memories, "status": result["status"], "next_step": result["next_step"],
        "unknowns": result["unknowns"], "ambiguities": result["ambiguities"], "conflicts": result["conflicts"],
        "limitations": result["coverage"]["limitations"],
        "historical_evidence_status": result["retrieval_snapshot"]["historical_evidence_status"],
    })


def render_recall(result, handles=_handle):
    """``handles`` may be one recall's Handles, to reuse the handles its earlier renders computed."""
    # Serialized here and dropped: no part of the view is changed or leaves this function, so nothing is copied.
    return serialized(recall_context_view(result, _shared, handles))


def _length(text):
    return len(text.encode("utf-8"))


def _members(lengths):
    """The length of a serialized JSON array or object whose members (or "key":value pairs) have these lengths."""
    return 2 + max(0, len(lengths) - 1) + sum(lengths)


def _entry(identifier, value):
    """The length of ``"identifier":value`` in a serialized table."""
    return _length(serialized(identifier)) + 1 + _length(serialized(value))


class _Recording(_Projection):
    """A projection of one item (or passage) that records each table entry it makes, in order, with the length of
    the entry the table then holds, so the entries can be made again, with the same checks, in another table."""

    def __init__(self, assessments, handles):
        super().__init__(assessments, _shared, handles)
        self.log = []

    def memory(self, value):
        identifier = super().memory(value)
        self.log.append(("m", identifier, self.memories[identifier], _entry(identifier, self.memories[identifier])))
        return identifier

    def source(self, reference):
        identifier = super().source(reference)
        self.log.append(("s", identifier, reference, _entry(identifier, self.sources[identifier])))
        return identifier

    def relation(self, assessment):
        identifier = super().relation(assessment)
        self.log.append(("r", identifier, self.relations[identifier], _entry(identifier, self.relations[identifier])))
        return identifier


class _Collision(Exception):
    pass


_NO_RELATIONS = ()


class FittingMeasure:
    """``len(render_recall(result, handles).encode())``, exactly, for the repeated renders of one recall's budget
    fitting, without serializing the whole context each time.

    The rendered context is one JSON object serialized with sorted keys and no whitespace, so its byte length is the
    sum of its members' lengths, in whatever order they are written. Each shown item's (and each shown passage's)
    serialized view is the same from render to render: it depends only on that item, its belief resolution and the
    recall's relation table. So its length, and the entries its projection makes in the shared tables (memory
    versions, sources, relations), are recorded the first time, and every measurement makes those entries again, in
    the same order and with the same checks, into fresh tables, whose lengths it adds to the items'. An item is
    projected again whenever its belief resolution is another object (``refresh_beliefs`` assigns a new one). Which
    items and passages are shown is decided as ``recall_context_view`` decides it; whether a passage covers an item is
    remembered only while the item, its resolution and the active passages are the same objects as when it was
    decided. When any check would fail, the measurement renders the whole context instead, which raises the same error.

    One instance serves the fitting of one recall, during which nothing of an item or passage changes in place; it is
    not used once ``factor_relations`` rewrites belief resolutions in place.
    """

    def __init__(self, handles):
        self.handles = handles
        self.items, self.passages, self.relations = {}, {}, None
        self.covered, self.active, self.generation = {}, [], 0

    def _record(self, project, assessments):
        projection = _Recording(assessments, self.handles)
        return _length(serialized(project(projection))), projection.log

    def _item(self, item, assessments):
        resolution = item.get("belief_resolution")
        entry = self.items.get(id(item))
        if (entry is None or entry[0] is not item or entry[1] is not resolution
                or entry[2] != item["display_mode"]):

            def project(projection):
                content = projection.content(memory_content(item, _shared))
                content["sources"] = projection.references(item["memory"]["evidence_refs"])
                content["display_mode"] = item["display_mode"]
                return content
            entry = self.items[id(item)] = (item, resolution, item["display_mode"], *self._record(project, assessments))
        return entry[3], entry[4]

    def _covered(self, item, passages):
        resolution = item.get("belief_resolution")
        entry = self.covered.get(id(item))
        if entry is None or entry[0] is not item or entry[1] is not resolution or entry[2] != self.generation:
            entry = self.covered[id(item)] = (item, resolution, self.generation,
                                              covering_passage(item, passages) is not None)
        return entry[3]

    def _passage(self, passage, assessments):
        entry = self.passages.get(id(passage))
        if entry is None or entry[0] is not passage:
            entry = self.passages[id(passage)] = (passage, *self._record(
                lambda projection: {**passage_content(passage, _shared),
                                    "sources": projection.references([passage["evidence_ref"]])}, assessments))
        return entry[1], entry[2]

    def __call__(self, result):
        assessments = result.get("belief_relations", _NO_RELATIONS)  # the same object while the table is unchanged
        if assessments is not self.relations:
            self.items, self.passages, self.relations = {}, {}, assessments
        try:
            return self._measure(result, assessments)
        except Exception:  # noqa: BLE001 - a collision, or anything else: the whole render decides, and raises
            pass
        return _length(render_recall(result, self.handles))

    def _measure(self, result, assessments):
        tables = {"m": {}, "s": {}, "r": {}}
        source_values = {}

        def enter(log):
            for kind, identifier, value, length in log:
                if kind == "s":
                    if identifier in source_values and source_values[identifier] != value:
                        raise _Collision
                    source_values[identifier] = value
                else:
                    table = tables[kind]
                    if identifier in table and table[identifier][0] != value:
                        raise _Collision
                tables[kind][identifier] = (value, length)

        memories = []
        passages = active_passages(result)
        if len(passages) != len(self.active) or any(a is not b for a, b in zip(passages, self.active)):
            self.active, self.generation = passages, self.generation + 1  # holds them, so no id is reused
        for item in result["items"]:
            if item["display_mode"] == "do_not_surface" or self._covered(item, passages):
                continue
            length, log = self._item(item, assessments)
            enter(log)
            memories.append(length)
        views = []
        for passage in passages:
            length, log = self._passage(passage, assessments)
            enter(log)
            views.append(length)
        members = {
            "format": _length(serialized(FORMAT)), "trust": _length(serialized("memory_data_not_instructions")),
            "memories": _members(memories),
            **{key: _length(serialized(result[key])) for key in (
                "status", "next_step", "unknowns", "ambiguities", "conflicts")},
            "limitations": _length(serialized(result["coverage"]["limitations"])),
            "historical_evidence_status": _length(serialized(
                result["retrieval_snapshot"]["historical_evidence_status"])),
            **{name: _members([length for _, length in tables[kind].values()])
               for name, kind in (("sources", "s"), ("relations", "r"), ("memory_versions", "m"))},
        }
        if views:
            members["source_passages"] = _members(views)
        return _members([_length(serialized(key)) + 1 + length for key, length in members.items()])


def context_view(packet):
    assessments = [assessment for result in packet.get("recall_results", [])
                   for assessment in result.get("belief_relations", [])]
    projection = _Projection(assessments)
    blocks = []
    for block in packet["blocks"]:
        try:
            content = json.loads(block["text"])
        except (ValueError, TypeError):
            content = block["text"]
        blocks.append({"section": block["section"], "content": projection.content(content),
                       "sources": projection.references(block["evidence_refs"])})
    return projection.finish({"blocks": blocks})


def reasoning_context_view(blocks, candidates):
    projection = _Projection()
    context = []
    for block in blocks:
        try:
            content = json.loads(block["text"])
        except (ValueError, TypeError):
            content = block["text"]
        context.append({"section": block["section"], "content": projection.content(content),
                        "sources": projection.references(block["evidence_refs"])})
    offered = []
    for candidate in candidates:
        content = projection.content(candidate)
        content["memory_ref"] = projection.memory(candidate)
        offered.append(content)
    return projection.finish({"context": context, "candidates": offered})
