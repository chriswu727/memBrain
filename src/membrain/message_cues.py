"""Retrieval cues attached to stored messages.

A cue names whom a message is about and what kind of fact it holds ("Melanie hobbies and activities"), in the words
a later question would use. Cues are an index over the original messages: recall may reach a message through its
cues, and what it then returns is the message. A cue is never shown as memory content, is written only for a
message that is current, and is removed when that message is hidden or erased.
"""
import json
import math
import re

from . import cognition
from .embeddings import EmbeddingRequest
from .helpers import DomainError

RULE_VERSION = "message-cue-v1"
MAX_ITEMS = 200
MAX_CUES = 6
CUE_CHARACTERS = 80
EMBEDDING_BATCH = 32
BOUNDARY_MINIMUM = 10  # A batch is cut at a conversation's end only if at least this many messages remain in it.
TERM_ROWS = 1024  # Cue rows read for one query term; a commoner term tells the routes little.
# How much a cue match counts beside the keyword and meaning routes over the messages themselves (``candidates``).
# A cue matched by its words counts like a keyword match of the message, scaled by the square of the share of the
# query it covers; a cue matched by meaning counts half, as a message matched by meaning does. Chosen on the LoCoMo
# development conversations (evaluations/message-cues-2026-11-11.md).
KEYWORD_WEIGHT = 1.0
KEYWORD_POWER = 2
VECTOR_WEIGHT = 0.5
_MARKERS = re.compile(r"\[(?:private|secret removed)\]", re.IGNORECASE)


def cue_text(cues) -> str | None:
    """The stored form of one message's cues: scrubbed phrases joined with ``; ``, or ``None`` when nothing is left."""
    from .privacy import scrub

    if not isinstance(cues, (list, tuple)):
        raise DomainError("validation_failed", "Cues must be a list of short phrases.")
    phrases = []
    for cue in cues[:MAX_CUES]:
        if not isinstance(cue, str):
            raise DomainError("validation_failed", "Cues must be a list of short phrases.")
        phrase = " ".join(_MARKERS.sub(" ", scrub(cue)).split())[:CUE_CHARACTERS].strip(" ;")
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    return "; ".join(phrases) or None


def _vectors(service, texts):
    """Cue vectors from the in-process model, or ``None`` without one."""
    provider = service.embedding_provider
    if provider is None:
        return None
    from .vector_jobs import _validate_result

    unique = list(dict.fromkeys(texts))
    vectors = {}
    try:
        for start in range(0, len(unique), EMBEDDING_BATCH):
            request = EmbeddingRequest(tuple(unique[start:start + EMBEDDING_BATCH]))
            result = provider(request)
            _validate_result(provider, request, result)
            vectors.update(zip(request.texts, result.vectors, strict=True))
    except Exception:
        return None  # The cues are still written, and matched by their words.
    return provider.space, [vectors[text] for text in texts]


def write(service, principal, brain_id, items, *, model_version=None, reviewed_through_sequence=None) -> dict:
    """Attach cues to current messages, replacing any cues a message already has.

    ``items`` name a message by ``event_id``, by its ``sequence`` as ``pending`` gave it, or by ``producer_ref`` and
    ``source_event_key`` as a host knows it. A
    message that is unknown, superseded, hidden or erased is skipped and counted, not an error: the caller indexed
    what it had been shown. ``reviewed_through_sequence`` records how far the caller read the messages ``pending``
    offered, whether or not they got cues, so they are not offered again; with it ``items`` may be empty.
    """
    from .recording_control import require_recording
    from .service import _writable

    _writable()
    reviewed = reviewed_through_sequence
    if reviewed is not None and (type(reviewed) is not int or not 0 <= reviewed < 2**63):
        raise DomainError("validation_failed", "The reviewed sequence must be a non-negative integer.")
    if not isinstance(items, list) or not (0 if reviewed is not None else 1) <= len(items) <= MAX_ITEMS:
        raise DomainError("validation_failed", f"Send 1 to {MAX_ITEMS} messages with cues.")
    if model_version is not None and (not isinstance(model_version, str) or not 1 <= len(model_version) <= 200):
        raise DomainError("validation_failed", "A model version must contain 1 to 200 characters.")
    by_event, by_source, by_sequence = {}, {}, {}
    for item in items:
        if not isinstance(item, dict):
            raise DomainError("validation_failed", "Each item names one message and its cues.")
        text = cue_text(item.get("cues"))
        event_id, producer, key = item.get("event_id"), item.get("producer_ref"), item.get("source_event_key")
        if isinstance(event_id, str) and event_id:
            by_event[event_id] = text
        elif type(item.get("sequence")) is int and 0 < item["sequence"] < 2**63:
            by_sequence[item["sequence"]] = text
        elif isinstance(producer, str) and producer and isinstance(key, str) and key:
            by_source[(producer, key)] = text
        else:
            raise DomainError("validation_failed",
                              "Name a message by event_id, by sequence, or by producer_ref and source_event_key.")
    params = service._params(principal, brain_id)
    current = ("AND is_current AND NOT deleted AND NOT suppressed AND NOT retired AND document IS NOT NULL "
               "AND document->'observed'->>'event_kind'='message' ")
    with service.database.transaction(principal) as conn:
        require_recording(service._brain(conn, principal, brain_id))
        found = {}
        if by_event:
            for row in conn.execute(
                    "SELECT id,revision FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                    "AND id=ANY(%s::text[]) " + current, (*params, sorted(by_event))):
                found[row["id"]] = (row["revision"], by_event[row["id"]])
        if by_sequence:
            for row in conn.execute(
                    "SELECT id,revision,sequence FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                    "AND sequence=ANY(%s::bigint[]) " + current, (*params, sorted(by_sequence))):
                found[row["id"]] = (row["revision"], by_sequence[row["sequence"]])
        if by_source:
            for row in conn.execute(
                    "SELECT id,revision,producer_ref,source_key FROM memory_events WHERE tenant_id=%s AND owner_id=%s "
                    "AND brain_id=%s AND (producer_ref,source_key) IN (SELECT * FROM unnest(%s::text[],%s::text[])) "
                    + current, (*params, [producer for producer, _ in by_source], [key for _, key in by_source])):
                found[row["id"]] = (row["revision"], by_source[(row["producer_ref"], row["source_key"])])
    keep = {event: value for event, value in found.items() if value[1] is not None}
    embedded = _vectors(service, [text for _, text in keep.values()]) if keep else None
    written = 0
    with service.database.transaction(principal) as conn:
        brain = service._brain(conn, principal, brain_id)
        require_recording(brain)
        if reviewed is not None:
            if reviewed > brain["durable_sequence"]:
                raise DomainError("validation_failed", "The reviewed sequence is beyond the recorded messages.")
            conn.execute(
                "INSERT INTO memory_cue_progress(tenant_id,owner_id,brain_id,reviewed_through_sequence) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT (tenant_id,brain_id) DO UPDATE SET reviewed_through_sequence="
                "GREATEST(memory_cue_progress.reviewed_through_sequence,EXCLUDED.reviewed_through_sequence),"
                "updated_at=clock_timestamp()", (*params, reviewed))
        if found:  # A message whose cues came back empty loses the ones it had.
            conn.execute("DELETE FROM memory_message_cues WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                         "AND event_id=ANY(%s::text[])", (*params, [event for event in found if event not in keep]))
        for index, (event, (revision, text)) in enumerate(keep.items()):
            space, vector = (embedded[0], embedded[1][index]) if embedded else (None, None)
            written += conn.execute(
                "INSERT INTO memory_message_cues(tenant_id,owner_id,brain_id,event_id,event_revision,cue_text,"
                "rule_version,model_version,embedding,embedding_model,embedding_model_version) "
                "SELECT %s,%s,%s,e.id,e.revision,%s,%s,%s,%s::vector,%s,%s FROM memory_events e "
                "WHERE e.tenant_id=%s AND e.owner_id=%s AND e.brain_id=%s AND e.id=%s AND e.revision=%s "
                "AND e.is_current AND NOT e.deleted AND NOT e.suppressed AND NOT e.retired AND e.document IS NOT NULL "
                "ON CONFLICT (tenant_id,brain_id,event_id) DO UPDATE SET event_revision=EXCLUDED.event_revision,"
                "cue_text=EXCLUDED.cue_text,rule_version=EXCLUDED.rule_version,model_version=EXCLUDED.model_version,"
                "embedding=EXCLUDED.embedding,embedding_model=EXCLUDED.embedding_model,"
                "embedding_model_version=EXCLUDED.embedding_model_version,created_at=clock_timestamp()",
                (*params, text, RULE_VERSION, model_version,
                 json.dumps(vector) if vector is not None else None,
                 space.model if space else None, space.model_version if space else None,
                 *params, event, revision),
            ).rowcount
    return {"written": written, "skipped": len(by_event) + len(by_source) + len(by_sequence) - written,
            "embedded": written if embedded else 0, **({} if reviewed is None else {"reviewed_through_sequence": reviewed})}


_UNREVIEWED = (
    "FROM memory_events e WHERE e.tenant_id=%s AND e.owner_id=%s AND e.brain_id=%s AND e.is_current AND NOT e.deleted "
    "AND NOT e.suppressed AND NOT e.retired AND e.document IS NOT NULL "
    "AND e.document->'observed'->>'event_kind'='message' AND e.document->'observed'->>'actor_role'='user' "
    "AND e.sequence>COALESCE((SELECT p.reviewed_through_sequence FROM memory_cue_progress p "
    "WHERE p.tenant_id=e.tenant_id AND p.brain_id=e.brain_id),0) "
    "AND NOT EXISTS (SELECT 1 FROM memory_message_cues c WHERE c.tenant_id=e.tenant_id AND c.brain_id=e.brain_id "
    "AND c.event_id=e.id) ")


def pending(service, principal, brain_id, *, limit=20, max_characters=6000, item_characters=600,
            whole_conversations=False) -> dict:
    """The user's messages not yet reviewed for cues, oldest first, for whoever writes cues to read.

    ``through_sequence`` is what to pass back to ``write`` as ``reviewed_through_sequence`` once these have been
    read. ``remaining`` counts every unreviewed message, the returned ones included. While recording is paused
    nothing is offered, because cues could not be saved.

    With ``whole_conversations`` the batch ends where a conversation ends, when that leaves it at least
    ``BOUNDARY_MINIMUM`` messages: a reader names what a message is about better with the rest of its
    conversation in front of it than with a conversation cut in two.
    """
    from .service import reading

    for value, low, high in ((limit, 1, 100), (max_characters, 200, 50_000), (item_characters, 50, 5_000)):
        if type(value) is not int or not low <= value <= high:
            raise DomainError("validation_failed", "Pending-cue limits are outside the supported range.")
    params = service._params(principal, brain_id)
    with reading(), service.database.transaction(principal) as conn:
        brain = service._brain(conn, principal, brain_id)
        if brain["recording_paused"]:
            return {"items": [], "through_sequence": None, "remaining": 0, "recording_paused": True}
        remaining = conn.execute("SELECT count(*) AS n " + _UNREVIEWED, params).fetchone()["n"]
        rows = conn.execute(
            "SELECT e.id,e.sequence,e.conversation_id,e.document #>> '{observed,content,text}' AS text,"
            "e.document #>> '{system_time,recorded_at}' AS recorded_at " + _UNREVIEWED + "ORDER BY e.sequence LIMIT %s",
            (*params, limit)).fetchall()
    items, used = [], 0
    for row in rows:
        text = " ".join((row["text"] or "").split())
        if len(text) > item_characters:
            text = text[:item_characters - 1] + "…"
        if items and used + len(text) > max_characters:
            break
        used += len(text)
        items.append({"event_id": row["id"], "sequence": row["sequence"], "conversation_id": row["conversation_id"],
                      "recorded_at": row["recorded_at"], "text": text})
    if whole_conversations and items and (len(items) < len(rows) or remaining > len(items)):
        # More follows this batch: end it at the last change of conversation, if enough is left before it.
        ends = [index for index in range(1, len(items))
                if items[index]["conversation_id"] != items[index - 1]["conversation_id"]]
        if ends and ends[-1] >= BOUNDARY_MINIMUM:
            items = items[:ends[-1]]
    return {"items": items, "through_sequence": items[-1]["sequence"] if items else None, "remaining": remaining,
            "recording_paused": False}


def ranked_events(conn, params, text, query_embedding, *, limit) -> list[tuple[str, int, float]]:
    """Messages whose cues match the query, best first, as ``(event_id, event_revision, score)``.

    The score adds two reciprocal ranks. One is by the query's words found in the cues, each word weighted by how
    rare it is among the brain's cues, and counted in proportion to the share of the query the cue covers: a cue
    that shares only a person's name with the question is found, and counts for little. The other, when the query
    was embedded in the cues' space, is by distance. It is a ranking score and not a probability.
    """
    words = sorted(cognition._terms(text)[0])
    terms = [word for word in words if len(word) <= 256][:128]
    score = {}
    if terms and limit > 0 and KEYWORD_WEIGHT > 0:
        from .lexical_candidates import _prefixes

        rows = conn.execute(
            "WITH queries AS (SELECT term_id,to_tsquery('simple',query) AS query "
            "FROM unnest(%s::text[]) WITH ORDINALITY term(query,term_id)) "
            "SELECT q.term_id,m.event_id,m.event_revision,count(*) OVER (PARTITION BY q.term_id) AS frequency,"
            "(SELECT count(*) FROM memory_message_cues WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s) AS total "
            "FROM queries q CROSS JOIN LATERAL (SELECT c.event_id,c.event_revision FROM memory_message_cues c "
            "WHERE c.tenant_id=%s AND c.owner_id=%s AND c.brain_id=%s AND c.cue_lexemes @@ q.query "
            "ORDER BY c.event_id LIMIT %s) m",
            ([" | ".join(_prefixes([term])) for term in terms], *params, *params, TERM_ROWS),
        ).fetchall()
        if rows:
            total = max(rows[0]["total"], 1)
            frequency = {row["term_id"]: row["frequency"] for row in rows}

            def rarity(count):
                return math.log(1 + (max(total, count) - count + 0.5) / (count + 0.5))

            whole = sum(rarity(frequency.get(index + 1, 0)) for index in range(len(terms)))
            matched = {}
            for row in rows:
                key = (row["event_id"], row["event_revision"])
                matched[key] = matched.get(key, 0.0) + rarity(row["frequency"])
            order = sorted(matched, key=lambda key: (-matched[key], key))[:limit]
            for rank, key in enumerate(order):
                covered = matched[key] / whole
                score[key] = KEYWORD_WEIGHT * covered ** KEYWORD_POWER / (61 + rank)
    if query_embedding is not None and limit > 0 and VECTOR_WEIGHT > 0:
        space = query_embedding.space
        vector = "[" + ",".join(str(value) for value in query_embedding.vectors[0]) + "]"
        rows = conn.execute(
            "SELECT event_id,event_revision FROM memory_message_cues WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND embedding_model=%s AND embedding_model_version=%s AND vector_dims(embedding)=%s "
            "ORDER BY embedding <=> %s::vector,event_id LIMIT %s",
            (*params, space.model, space.model_version, space.dimensions, vector, limit),
        ).fetchall()
        for rank, row in enumerate(rows):
            key = (row["event_id"], row["event_revision"])
            score[key] = score.get(key, 0.0) + VECTOR_WEIGHT / (61 + rank)
    return [(*key, score[key]) for key in sorted(score, key=lambda key: (-score[key], key))[:limit]]


def erase(conn, params, event_ids) -> None:
    """Remove the cues of messages that are being hidden or erased."""
    conn.execute("DELETE FROM memory_message_cues WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                 "AND event_id=ANY(%s::text[])", (*params, sorted(event_ids)))


__all__ = ["RULE_VERSION", "cue_text", "erase", "pending", "ranked_events", "write"]
