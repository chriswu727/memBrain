import json
import math
import time

from psycopg.types.json import Jsonb

from .embeddings import EmbeddingPassage, EmbeddingRequest, EmbeddingResult, EmbeddingSpace
from .helpers import DomainError, digest, uid
from .jobs import JobStore

# A statement captured from a message is embedded as that whole message, not as the single sentence: on its own a
# sentence has lost the speaker, the date and what the neighbouring sentences were about, and ranked the evidence
# far lower (evaluations/recall-fusion-2026-11-10.md). The stored index version carries this rule, so vectors made
# under the earlier one are replaced by the backfill.
MESSAGE_CONTEXT_VERSION = "message-context-v1"
MESSAGE_CONTEXT_CHARACTERS = 1500  # A longer message keeps the statement's own vector and passages.


def provider_index_version(provider):
    return getattr(provider, "document_index_version", "single-vector-v1")


def document_index_version(provider):
    """The index version stored with a vector: the provider's own document index and how its input was chosen."""
    return provider_index_version(provider) + "+" + MESSAGE_CONTEXT_VERSION


def _message_contexts(conn, service, principal, brain_id, documents):
    """The whole source message of each directly captured statement, by ``(memory_id, revision)``.

    Only a statement that cites one current message as its support gets one; anything derived from several sources,
    or whose message is long, unavailable or empty, is embedded as its statement, as before."""
    wanted = {}
    for document in documents:
        refs = [ref for ref in document.get("evidence_refs") or [] if ref.get("relationship") == "supports"]
        if (document.get("derivation") or {}).get("method") == "direct_capture" and len(refs) == 1:
            wanted[(document["memory_id"], document["revision"])] = (refs[0]["event_id"], refs[0]["event_revision"])
    if not wanted:
        return {}
    rows = conn.execute(
        "SELECT id,revision,document #>> '{observed,content,text}' AS text FROM memory_events "
        "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=ANY(%s::text[]) "
        "AND NOT deleted AND NOT suppressed AND NOT retired AND document IS NOT NULL",
        (*service._params(principal, brain_id), sorted({event for event, _ in wanted.values()}))).fetchall()
    texts = {(row["id"], row["revision"]): row["text"] for row in rows}
    contexts = {}
    for key, source in wanted.items():
        text = texts.get(source)
        if isinstance(text, str) and text.strip() and len(text) <= MESSAGE_CONTEXT_CHARACTERS:
            contexts[key] = text
    return contexts


def _embed_documents(service, principal, brain_id, job, statements, contexts):
    """Vectors and passages for ``statements``, each embedded as its message context when it has one.

    Identical inputs are sent once. A context that the provider had to split into passages does not describe the
    statement's own text, so that statement is embedded again as itself; only an unmetered provider is asked twice.
    """
    provider = service.embedding_provider
    if getattr(provider, "metered", True) and provider_index_version(provider) != "single-vector-v1":
        contexts = [None] * len(statements)  # A paid provider that splits its input is asked once, as before.
    inputs = [contexts[index] if contexts[index] is not None else statement
              for index, statement in enumerate(statements)]
    unique = list(dict.fromkeys(inputs))
    result = _call(service, principal, brain_id, job, EmbeddingRequest(tuple(unique)))
    position = {text: index for index, text in enumerate(unique)}
    vectors = [result.vectors[position[text]] for text in inputs]
    passages = [(result.passages[position[text]] if result.passages is not None else ()) for text in inputs]
    split = [index for index, parts in enumerate(passages) if parts and contexts[index] is not None]
    if split:
        again = list(dict.fromkeys(statements[index] for index in split))
        own = _call(service, principal, brain_id, job, EmbeddingRequest(tuple(again)))
        place = {text: index for index, text in enumerate(again)}
        for index in split:
            vectors[index] = own.vectors[place[statements[index]]]
            passages[index] = own.passages[place[statements[index]]] if own.passages is not None else ()
    return result, vectors, passages


def embedding_job_id(memory_id, revision, provider):
    identity = [memory_id, revision, provider.space.descriptor()]
    version = document_index_version(provider)
    if version != "single-vector-v1":
        identity.append(version)
    return "embed:" + digest(identity)


def _validate_result(provider, request, result):
    if (not isinstance(result, EmbeddingResult) or result.space != provider.space
            or not isinstance(result.vectors, (tuple, list)) or len(result.vectors) != len(request.texts)):
        raise DomainError("invalid_evidence", "Embedding response does not match its request.")
    for vector in result.vectors:
        if (not isinstance(vector, (tuple, list)) or len(vector) != result.space.dimensions or not any(vector)
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector)):
            raise DomainError("invalid_evidence", "Embedding response must contain finite nonzero vectors.")
    if request.purpose == 'query':
        if result.passages is not None:
            raise DomainError("invalid_evidence", "Query embedding cannot publish document passages.")
        return
    if result.document_index_version != provider_index_version(provider):
        raise DomainError("invalid_evidence", "Embedding document index version does not match its provider.")
    if result.passages is None:
        if result.document_index_version != 'single-vector-v1':
            raise DomainError("invalid_evidence", "A passage index must declare document coverage.")
    elif (not isinstance(result.passages, (tuple, list)) or len(result.passages) != len(request.texts)
          or any(not isinstance(parts, (tuple, list)) or len(parts) > 1024 for parts in result.passages)):
        raise DomainError("invalid_evidence", "Passage coverage must align with every requested document.")


def _call(service, principal, brain_id, job, request):
    jobs = JobStore(service.database)
    provider = service.embedding_provider
    if not getattr(provider, "metered", True):
        # An in-process model has no cost or external call to account for; it must not consume the brain's
        # background budget, which limits paid provider calls.
        try:
            result = provider(request)
        except Exception:
            raise DomainError("dependency_unavailable", "Embedding model is unavailable.", True) from None
        _validate_result(provider, request, result)
        return result
    lease = {"lease_token": job["lease_token"], "fence": job["fence"]}
    try:
        metadata = provider.request_metadata(request)
    except ValueError:
        raise DomainError("budget_exceeded", "Embedding input exceeds the provider request limits.") from None
    operation_id = f"embedding:{job['fence']}"
    reserved = jobs.reserve_operation(
        principal, brain_id, job["id"], **lease, operation_id=operation_id,
        **metadata, max_model_calls=1, max_input_bytes=262144,
    )
    if not reserved["newly_reserved"]:
        raise DomainError("budget_exceeded", "Embedding was already reserved.")
    try:
        result = provider(request)
        _validate_result(provider, request, result)
        if result.request_fingerprint != metadata["request_fingerprint"]:
            raise DomainError("invalid_evidence", "Embedding response does not match its request.")
    except Exception:
        jobs.settle_operation(principal, brain_id, job["id"], **lease, operation_id=operation_id, outcome="uncertain")
        raise DomainError("dependency_unavailable", "Embedding provider is unavailable.", True) from None
    jobs.settle_operation(principal, brain_id, job["id"], **lease, operation_id=operation_id,
                          outcome="completed", usage=result.usage, response_fingerprint=digest(result.vectors))
    return result


def embed_memory(service, principal, brain_id, job):
    params = service._params(principal, brain_id)
    version = job["payload"]
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        row = conn.execute(
            "SELECT document FROM memory_assertions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND id=%s AND revision=%s AND is_current AND NOT invalidated AND NOT suppressed AND NOT deleted",
            (*params, version["memory_id"], version["revision"]),
        ).fetchone()
        if row is None or row["document"] is None:
            raise DomainError("source_unavailable", "Embedding source is unavailable.")
        statement = row["document"]["statement"]
        context = _message_contexts(conn, service, principal, brain_id, [row["document"]]).get(
            (version["memory_id"], version["revision"]))
    result, vectors, passages = _embed_documents(service, principal, brain_id, job, [statement], [context])

    _publish_embedding(service, principal, brain_id, job, statement, result, vectors[0], passages=passages[0])


def _publish_embedding(service, principal, brain_id, job, statement, result, vector, *, passages=()):
    if result.document_index_version != provider_index_version(service.embedding_provider):
        raise DomainError("invalid_evidence", "Embedding document index version does not match its provider.")
    previous_end = 0
    for index, passage in enumerate(passages):
        if (not isinstance(passage, EmbeddingPassage) or type(passage.start) is not int
                or type(passage.end) is not int or not 0 <= passage.start < passage.end <= len(statement)
                or (index == 0 and passage.start != 0) or passage.start > previous_end
                or passage.end <= previous_end or len(passage.vector) != result.space.dimensions
                or not any(passage.vector)
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in passage.vector)):
            raise DomainError("invalid_evidence", "Embedding passages must cover the unchanged source with finite vectors.")
        previous_end = passage.end
    if passages and (previous_end != len(statement) or len(passages) > 1024):
        raise DomainError("invalid_evidence", "Embedding passages do not cover the complete source within bounds.")
    params, version = service._params(principal, brain_id), job["payload"]
    def publish(conn, _):
        row = conn.execute(
            "SELECT document FROM memory_assertions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND id=%s AND revision=%s AND is_current AND NOT invalidated AND NOT suppressed AND NOT deleted",
            (*params, version["memory_id"], version["revision"]),
        ).fetchone()
        if not row or not row["document"] or row["document"]["statement"] != statement:
            raise DomainError("source_unavailable", "Embedding source changed.")
        conn.execute(
            "INSERT INTO memory_embeddings(tenant_id,owner_id,brain_id,memory_id,memory_revision,model,model_version,"
            "dimensions,content_hash,embedding,document_index_version) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s) "
            "ON CONFLICT (tenant_id,brain_id,memory_id,memory_revision,model,model_version) DO UPDATE SET "
            "content_hash=EXCLUDED.content_hash,embedding=EXCLUDED.embedding,dimensions=EXCLUDED.dimensions,"
            "document_index_version=EXCLUDED.document_index_version",
            (*params, version["memory_id"], version["revision"], result.space.model, result.space.model_version,
             result.space.dimensions, digest(statement), json.dumps(vector),
             document_index_version(service.embedding_provider)),
        )
        identity = (*params, version["memory_id"], version["revision"], result.space.model, result.space.model_version)
        conn.execute("DELETE FROM memory_embedding_passages WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                     "AND memory_id=%s AND memory_revision=%s AND model=%s AND model_version=%s", identity)
        if passages:
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO memory_embedding_passages(tenant_id,owner_id,brain_id,memory_id,memory_revision,"
                    "model,model_version,passage_index,start_offset,end_offset,embedding) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)",
                    [(*identity, index, passage.start, passage.end, json.dumps(passage.vector))
                     for index, passage in enumerate(passages)])

    JobStore(service.database).complete(principal, brain_id, job["id"], lease_token=job["lease_token"],
                                       fence=job["fence"], publish=publish)


def _query_source(conn, service, principal, request):
    payload = request["payload"]
    brain_id = request["target"]["brain_ref"]
    brain = service._brain(conn, principal, brain_id)
    cached = conn.execute(
        "SELECT request_hash FROM memory_requests WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND action=%s AND key=%s",
        (*service._params(principal, brain_id), request["action"], payload.get("idempotency_key", request["request_id"])),
    ).fetchone()
    if cached:
        return None
    events = []
    if request["action"] == "prepare":
        events = service._events(conn, principal, brain, event_ids=payload["latest_input_event_ids"], limit=128)
        lookup = {e["event_id"]: e for e in events}
        if any(key not in lookup for key in payload["latest_input_event_ids"]):
            raise DomainError("source_unavailable", "Query input is unavailable.")
        text = "\n".join(lookup[key]["observed"]["content"].get("text", "") for key in payload["latest_input_event_ids"])
    else:
        text = " ".join([payload["query"], *payload["additional_cues"]])
    if not text.strip():
        return None
    snapshot = {"scope": service._scope(principal, brain, request["target"]), "source_snapshot": [
        {"event_id": e["event_id"], "revision": e["revision"], "content_sha256": e["content_sha256"]} for e in events]}
    return brain, text, snapshot


def _local_query_embedding(service, principal, request):
    from .service import reading

    with service.database.transaction(principal) as conn, reading():
        source = _query_source(conn, service, principal, request)
    if source is None:
        return None, None, 0
    _, text, snapshot = source
    timeout = min(10, request["payload"]["budget"]["max_wall_time_ms"] / 1000)
    result = _call(service, principal, request["target"]["brain_ref"], None,
                   EmbeddingRequest((text,), timeout_seconds=timeout, purpose="query"))
    # The enclosing action validates this snapshot under its brain lock before using the vector or storing a reply.
    return result, snapshot, 1


def query_embedding(service, principal, request):
    from .learning import validate_snapshot

    payload = request["payload"]
    if (service.embedding_provider is None or request["action"] not in {"prepare", "recall"}
            or not payload.get("budget", {}).get("max_embedding_calls", 0)):
        return None, None, 0
    if not getattr(service.embedding_provider, "metered", True):
        return _local_query_embedding(service, principal, request)
    brain_id = request["target"]["brain_ref"]
    params = service._params(principal, brain_id)
    fingerprint = digest({"action": request["action"], "target": request["target"], "payload": payload})
    job_id = "query:" + digest([payload.get("idempotency_key", request["request_id"]), request["action"]])
    with service.database.transaction(principal) as conn:
        source = _query_source(conn, service, principal, request)
        if source is None:
            return None, None, 0
        brain, text, snapshot = source
        conn.execute(
            "INSERT INTO memory_jobs(tenant_id,owner_id,brain_id,id,kind,payload,state,source_event_ids) "
            "VALUES(%s,%s,%s,%s,'query_embedding',%s,'queued',%s) ON CONFLICT DO NOTHING",
            (*params, job_id, Jsonb({"request_hash": fingerprint}), [e["event_id"] for e in snapshot["source_snapshot"]]),
        )
        existing = conn.execute("SELECT * FROM memory_jobs WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s",
                                (*params, job_id)).fetchone()
        if existing["payload"].get("request_hash") != fingerprint:
            raise DomainError("idempotency_conflict", "Query job already binds another request.")
        if existing["state"] == "completed" and existing["result"]:
            data = existing["result"]
            validate_snapshot(conn, service, principal, brain, data["snapshot"])
            return EmbeddingResult(EmbeddingSpace(**data["space"]), (tuple(data["vector"]),), data["usage"],
                                   data["fingerprint"], data["input_bytes"]), data["snapshot"], 1
    jobs = JobStore(service.database)
    job = jobs.claim(principal, brain_id, worker_id=uid(), job_id=job_id, kinds=["query_embedding"], lease_seconds=30)
    if job is None:
        raise DomainError("dependency_unavailable", "Query embedding is unavailable or already running.", True)
    try:
        timeout = min(10, payload["budget"]["max_wall_time_ms"] / 1000)
        result = _call(service, principal, brain_id, job, EmbeddingRequest((text,), timeout_seconds=timeout, purpose="query"))

        def publish(conn, _):
            brain = service._brain(conn, principal, brain_id)
            validate_snapshot(conn, service, principal, brain, snapshot)
            data = {"snapshot": snapshot, "space": result.space.descriptor(), "vector": result.vectors[0],
                    "usage": result.usage, "fingerprint": result.request_fingerprint, "input_bytes": result.input_bytes}
            conn.execute("UPDATE memory_jobs SET result=%s WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s",
                         (Jsonb(data), *params, job_id))

        jobs.complete(principal, brain_id, job_id, lease_token=job["lease_token"], fence=job["fence"], publish=publish)
        return result, snapshot, 1
    except Exception:
        try:
            jobs.fail(principal, brain_id, job_id, lease_token=job["lease_token"], fence=job["fence"],
                      failure_code="provider_uncertain", retry=False)
        except DomainError:
            pass
        raise


BACKFILL_RESCAN_SECONDS = 600


def queue_missing_embeddings(service, principal, brain_id, *, after=("", 0), limit=64):
    """Queue embedding jobs for current memories without a vector in the configured space.

    Memories written before a provider was configured (for example while a local model was still downloading)
    are otherwise never embedded. Returns the number of jobs queued and the last key scanned, or ``None`` when
    the scan reached the end.
    """
    space = service.embedding_provider.space
    params = service._params(principal, brain_id)
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        rows = conn.execute(
            "SELECT a.id,a.revision,a.event_ids FROM memory_assertions a WHERE a.tenant_id=%s AND a.owner_id=%s "
            "AND a.brain_id=%s AND a.is_current AND NOT a.invalidated AND NOT a.suppressed AND NOT a.deleted "
            "AND a.document IS NOT NULL AND (a.id,a.revision) > (%s,%s) AND NOT EXISTS (SELECT 1 FROM memory_embeddings v "
            "WHERE v.tenant_id=a.tenant_id AND v.owner_id=a.owner_id AND v.brain_id=a.brain_id AND v.memory_id=a.id "
            "AND v.memory_revision=a.revision AND v.model=%s AND v.model_version=%s "
            "AND v.document_index_version=%s) ORDER BY a.id,a.revision LIMIT %s",
            (*params, after[0], after[1], space.model, space.model_version,
             document_index_version(service.embedding_provider), limit),
        ).fetchall()
        queued = 0
        for row in rows:
            job_id = embedding_job_id(row["id"], row["revision"], service.embedding_provider)
            queued += conn.execute(
                "INSERT INTO memory_jobs(tenant_id,owner_id,brain_id,id,kind,payload,state,source_event_ids,source_memory_ids) "
                "VALUES(%s,%s,%s,%s,'embed',%s,'queued',%s,%s) ON CONFLICT DO NOTHING",
                (*params, job_id, Jsonb({"memory_id": row["id"], "revision": row["revision"]}),
                 list(row["event_ids"] or []), [row["id"]]),
            ).rowcount
    return queued, ((rows[-1]["id"], rows[-1]["revision"]) if len(rows) == limit else None)


def backfill_embeddings(service, principal, brain_id, *, clock=time.monotonic):
    """Advance a per-brain backfill scan; rescans from the start at most every ten minutes."""
    states = service.__dict__.setdefault("_embedding_backfill", {})
    key = (principal.tenant_id, principal.principal_id, brain_id)
    state = states.get(key, {"after": ("", 0), "resume_at": 0.0})
    if clock() < state["resume_at"]:
        return 0
    queued, last = queue_missing_embeddings(service, principal, brain_id, after=state["after"])
    states[key] = ({"after": last, "resume_at": 0.0} if last is not None
                   else {"after": ("", 0), "resume_at": clock() + BACKFILL_RESCAN_SECONDS})
    return queued


def embed_local_batch(service, principal, brain_id, first, *, limit=32):
    """Batch local inference while each job retains its own lease and publication checks."""
    jobs = JobStore(service.database)
    claimed = [first]
    for _ in range(limit - 1):
        job = jobs.claim(principal, brain_id, worker_id=uid(), kinds=["embed"], lease_seconds=120)
        if job is None:
            break
        claimed.append(job)
    params = service._params(principal, brain_id)
    completed = set()
    try:
        with service.database.transaction(principal) as conn:
            service._brain(conn, principal, brain_id)
            rows = conn.execute(
                "SELECT id,revision,document FROM memory_assertions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                "AND id=ANY(%s::text[]) AND is_current AND NOT invalidated AND NOT suppressed AND NOT deleted "
                "AND document IS NOT NULL", (*params, [job["payload"]["memory_id"] for job in claimed])).fetchall()
            lookup = {(row["id"], row["revision"]): row["document"]["statement"] for row in rows}
            contexts = _message_contexts(conn, service, principal, brain_id, [row["document"] for row in rows])
        valid = [job for job in claimed if (job["payload"]["memory_id"], job["payload"]["revision"]) in lookup]
        if not valid:
            raise DomainError("source_unavailable", "Embedding sources are unavailable.")
        keys = [(job["payload"]["memory_id"], job["payload"]["revision"]) for job in valid]
        texts = tuple(lookup[key] for key in keys)
        result, vectors, passages = _embed_documents(service, principal, brain_id, valid[0], texts,
                                                     [contexts.get(key) for key in keys])
        failure = None
        for index, (job, statement, vector) in enumerate(zip(valid, texts, vectors, strict=True)):
            try:
                _publish_embedding(service, principal, brain_id, job, statement, result, vector,
                                   passages=passages[index])
            except DomainError as error:
                failure = error
                try:
                    jobs.fail(principal, brain_id, job["id"], lease_token=job["lease_token"], fence=job["fence"],
                              failure_code="source_unavailable", retry=False)
                except DomainError:
                    pass
            completed.add(job["id"])
        for job in claimed:
            if job["id"] not in completed:
                jobs.fail(principal, brain_id, job["id"], lease_token=job["lease_token"], fence=job["fence"],
                          failure_code="source_unavailable", retry=False)
        if failure is not None:
            raise failure
        return len(claimed)
    except Exception as error:
        for job in claimed:
            if job["id"] in completed:
                continue
            try:
                jobs.fail(principal, brain_id, job["id"], lease_token=job["lease_token"], fence=job["fence"],
                          failure_code=error.code if isinstance(error, DomainError) and error.code in {
                              "source_unavailable", "context_stale", "budget_exceeded", "provider_uncertain"} else "internal_error",
                          retry=error.retryable if isinstance(error, DomainError) else True)
            except DomainError:
                pass
        raise
