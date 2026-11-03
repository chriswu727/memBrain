import hashlib
import json
import re
from contextlib import ExitStack, asynccontextmanager
from importlib.resources import files
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .config import Settings, configured_service
from .contracts import CONTRACT_VERSION, schema, validate
from .helpers import DomainError, Principal
from .service import MemoryService, reading

RuntimeIdentifier = Annotated[str, Field(min_length=1, max_length=256)]
RuntimeFingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
RuntimeCounter = Annotated[int, Field(ge=0, le=2**63 - 1)]
RuntimeRevision = Annotated[int, Field(ge=1, le=2**63 - 1)]
RuntimeLeaseSeconds = Annotated[int, Field(ge=1, le=300)]


class RuntimeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NoteSource(RuntimeBody):
    producer_ref: RuntimeIdentifier
    source_event_key: RuntimeIdentifier
    source_revision: RuntimeRevision = 1


class RecallTrace(RuntimeBody):
    event_ids: Annotated[list[RuntimeIdentifier], Field(max_length=50)]


class NoteAffect(RuntimeBody):
    label: Annotated[str, Field(min_length=1, max_length=40)]
    valence: Annotated[int, Field(ge=-2, le=2)]
    intensity: Annotated[int, Field(ge=0, le=3)]
    basis: Literal["reported", "inferred"]
    topic: Annotated[str, Field(max_length=80)] | None = None
    felt_at: Annotated[str, Field(min_length=10, max_length=10)] | None = None


class NoteWrite(RuntimeBody):
    request_id: Annotated[str, Field(min_length=1, max_length=120)]
    text: Annotated[str, Field(min_length=1, max_length=300)]
    replaces: Annotated[list[RuntimeIdentifier], Field(max_length=100)] = []
    source_event_ids: Annotated[list[RuntimeIdentifier], Field(max_length=64)] = []
    source_messages: Annotated[list[NoteSource], Field(max_length=64)] = []
    role: Literal["user", "assistant"] = "assistant"
    producer: Annotated[str, Field(min_length=1, max_length=120)] = "membrain-notes"
    kind: str | None = None
    status: str | None = None
    about: str | None = None
    aliases: Annotated[list[str], Field(max_length=12)] = []
    due: str | None = None
    occurs_at: str | None = None
    pinned: bool = False
    sensitive: bool = False
    shared: bool = False
    affect: NoteAffect | None = None


PersonaAuthor = Literal["host", "user", "feedback"]
PersonaReason = Annotated[str, Field(max_length=200)]


class PersonaWrite(RuntimeBody):
    # The card itself is checked by persona.normalize_card, whose messages name the field at fault.
    card: dict
    made_by: PersonaAuthor
    reason: PersonaReason | None = None
    host_default: bool = False


class PersonaRestore(RuntimeBody):
    version: Annotated[int, Field(ge=1, le=2**31)]
    made_by: PersonaAuthor
    reason: PersonaReason | None = None


class PersonaReset(RuntimeBody):
    made_by: PersonaAuthor
    reason: PersonaReason | None = None


# Relationship (R1). The texts are checked by relationship.py, whose messages say what is wrong.
class SupportStyleWrite(RuntimeBody):
    text: Annotated[str, Field(max_length=2000)]


class BoundaryWrite(RuntimeBody):
    topic: Annotated[str, Field(max_length=2000)]
    aliases: Annotated[list[Annotated[str, Field(max_length=2000)]], Field(max_length=50)] = []


class FamiliarityCap(RuntimeBody):
    level: Literal["new", "getting_to_know", "familiar"] | None


class CommitmentAcknowledgement(RuntimeBody):
    note_ids: Annotated[list[RuntimeIdentifier], Field(max_length=50)]


class MoodPin(RuntimeBody):
    pinned: bool


class RuntimeBegin(RuntimeBody):
    turn_id: RuntimeIdentifier
    conversation_id: RuntimeIdentifier
    branch_id: RuntimeIdentifier
    input_fingerprint: RuntimeFingerprint


class RuntimeScope(RuntimeBody):
    conversation_id: RuntimeIdentifier
    branch_id: RuntimeIdentifier


class RuntimeClaim(RuntimeBody):
    worker_id: RuntimeIdentifier
    lease_seconds: RuntimeLeaseSeconds = 30
    expected_revision: RuntimeRevision | None = None


class RuntimeLearningRetry(RuntimeBody):
    request_id: RuntimeIdentifier
    expected_fence: RuntimeCounter


class CognitiveBudgetPolicy(RuntimeBody):
    window_seconds: Annotated[int, Field(ge=1, le=2_592_000)]
    max_model_calls: Annotated[int, Field(ge=0, le=1_000_000)]
    max_input_bytes: Annotated[int, Field(ge=0, le=1_000_000_000_000)]


class RuntimeBudgetChange(RuntimeBody):
    request_id: RuntimeIdentifier
    expected_revision: Annotated[int, Field(ge=0, le=2**63 - 2)]
    policy: CognitiveBudgetPolicy


class RuntimeRenew(RuntimeBody):
    lease_token: RuntimeIdentifier
    lease_seconds: RuntimeLeaseSeconds = 30
    expected_revision: RuntimeRevision | None = None


class RuntimeLeaseMutation(RuntimeBody):
    lease_token: RuntimeIdentifier
    expected_revision: RuntimeRevision


class RuntimeEventRef(RuntimeBody):
    event_id: RuntimeIdentifier
    revision: RuntimeRevision


class RuntimeOutput(RuntimeLeaseMutation):
    text: Annotated[str, Field(max_length=64000)]
    delivery_state: Literal["draft", "delivered", "partially_delivered", "cancelled"]


class RuntimeAdvance(RuntimeLeaseMutation):
    stage: Literal[
        "captured", "prepared", "generating", "generated", "delivering",
        "delivered",
    ]
    input_event_refs: Annotated[list[RuntimeEventRef], Field(max_length=64)] | None = None
    output_event_refs: Annotated[list[RuntimeEventRef], Field(max_length=64)] | None = None
    context_event_refs: Annotated[list[RuntimeEventRef], Field(max_length=64)] | None = None
    context_fingerprint: RuntimeFingerprint | None = None
    context_generation: RuntimeCounter | None = None
    working_revision: RuntimeCounter | None = None
    durable_sequence: RuntimeCounter | None = None
    context_tokens: RuntimeCounter | None = None
    recall_plan: dict | None = None
    response_review_policy: RuntimeFingerprint | None = None
    orientation_route: dict | None = None
    prepared_packet_id: RuntimeIdentifier | None = None
    memory_context_sha256: RuntimeFingerprint | None = None
    selection_omitted_reason: Literal["custom_context"] | None = None


class RuntimeResponseReviewReservation(RuntimeLeaseMutation):
    policy_fingerprint: RuntimeFingerprint
    request_fingerprint: RuntimeFingerprint
    draft_sha256: RuntimeFingerprint


class RuntimeResponseReviewCompletion(RuntimeLeaseMutation):
    request_fingerprint: RuntimeFingerprint
    status: Literal["approved", "rejected", "inconclusive"]
    issue_codes: Annotated[list[Literal[
        "current_input_misread", "unsupported_memory_claim", "applicability_override", "uncertainty_erased",
        "unconfirmed_action", "uncertain_current_input_fidelity", "uncertain_memory_fidelity",
        "uncertain_applicability", "uncertain_uncertainty", "uncertain_action_claims",
        "incomplete_review", "review_unavailable",
    ]], Field(max_length=16)]


class RuntimeRecallReservation(RuntimeLeaseMutation):
    input_bytes: Annotated[int, Field(ge=1, le=262144)]
    max_model_calls: Annotated[int, Field(ge=1, le=8)]
    max_input_bytes: Annotated[int, Field(ge=1, le=262144)]
    context_generation: RuntimeCounter
    source_refs: Annotated[list[RuntimeEventRef], Field(max_length=64)]
    request_fingerprint: RuntimeFingerprint


class RuntimeFail(RuntimeLeaseMutation):
    failure_code: Literal[
        "capture_failed", "prepare_failed", "generation_failed", "generation_uncertain",
        "delivery_failed", "delivery_uncertain", "commit_failed", "source_unavailable",
        "context_stale", "cancelled", "budget_exceeded", "dependency_unavailable", "internal_error",
    ]


def runtime_metadata(record: dict, *, include_lease: bool = False) -> dict:
    from .delivery_receipts import sanitize_delivery_receipt
    from .prepared_selection import sanitize_prepared_selection
    from .turns import PUBLIC_FIELDS

    allowed = {*PUBLIC_FIELDS, "lease_active", "unavailable_event_refs", "sources_available"}
    if include_lease:
        allowed.add("lease_token")
    result = {key: value for key, value in record.items() if key in allowed}
    if "delivery_receipt" in result:
        result["delivery_receipt"] = sanitize_delivery_receipt(result["delivery_receipt"])
    if "prepared_memory_selection" in result:
        result["prepared_memory_selection"] = sanitize_prepared_selection(result["prepared_memory_selection"])
    if result.get("recall_plan") is not None:
        validate("RecallPlan", result["recall_plan"])
    if result.get("response_review") is not None:
        validate("ResponseReview", result["response_review"])
    if result.get("orientation_route") is not None:
        validate("OrientationRoute", result["orientation_route"])
    for field in ("input_event_refs", "output_event_refs", "context_event_refs", "unavailable_event_refs"):
        if field in result:
            result[field] = [
                {key: value for key, value in ref.items() if key in {"event_id", "revision"}}
                for ref in result[field]
            ]
    return result


def capabilities(*, semantic_enabled=False, embedding_enabled=False) -> dict:
    result = {
        "adapter_id": "agent-memory-rest",
        "adapter_version": __version__,
        "protocol_version": CONTRACT_VERSION,
        "transport": "rest",
        "supported_actions": schema()["x-fixed-actions"],
        "capture": {key: False for key in (
            "user_messages", "delivered_assistant_messages", "tool_results", "message_edits",
            "message_deletions", "stable_source_ids", "branch_identity",
        )},
        "hooks": {key: False for key in (
            "before_turn", "after_delivery", "before_compaction", "on_resume",
        )},
        "context_control": "tool_output_only",
        "active_recall": True,
        "automatic_capture": False,
        "automatic_recall": False,
        "guarantee_level": "tools_only",
        "verification_state": "declared",
        "verified_at": None,
        "limitations": [
            "Host integration must explicitly observe messages and prepare each turn.",
            ("Semantic embedding recall is configured; index coverage may be partial."
             if embedding_enabled else "Semantic embeddings are not configured; recall uses lexical and structural cues."),
            ("Bounded semantic proposals and verification are configured; long-term memory quality is not validated."
             if semantic_enabled else "Model-driven semantic processing is not configured."),
            "Typed conditions use a fixed versioned registry; unresolved or expired context does not activate a rule.",
            "Provider billing is unknown; call and input-byte limits are enforced, monetary ceilings are not certified.",
        ],
    }
    validate("IntegrationCapabilities", result)
    return result


def _unmodified_service(service) -> bool:
    """Whether ``service.handle`` is MemoryService's own, so ``respond`` does exactly what it would. Any override,
    in a subclass or on the instance, is what the route must call, and its response is validated here."""
    kind, own = type(service), getattr(service, "__dict__", {})
    return (isinstance(service, MemoryService) and kind.handle is MemoryService.handle
            and kind.respond is MemoryService.respond and "handle" not in own and "respond" not in own)


def create_app(settings: Settings | None = None, service=None, turns=None, jobs=None) -> FastAPI:
    settings = settings or Settings.from_env()
    resources = ExitStack()
    if service is None:
        service = resources.enter_context(configured_service(settings))

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            resources.close()

    app = FastAPI(title="memBrain", version=__version__, lifespan=lifespan)
    app.state.service = service
    app.state.turns = turns
    app.state.jobs = jobs
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    bearer = HTTPBearer(auto_error=False)

    def authenticate_identity(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise DomainError("unauthorized", "A valid API key is required")
        key_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        principal = settings.principals().get(key_hash)
        if principal is None:
            raise DomainError("unauthorized", "A valid API key is required")
        return principal

    def authenticate(request: Request, principal: Principal = Depends(authenticate_identity)) -> Principal:
        database = getattr(service, "database", None)
        if database is not None and getattr(database, "recovery_authority", None) is not None:
            from .recovery import metadata

            current = metadata(database, principal)
            if current["recovery_epoch"] is not None and request.headers.get("X-Memory-Recovery-Epoch") != current["recovery_epoch"]:
                raise DomainError("recovery_acknowledgement_required", "Reconcile the host with the recovery checkpoint before continuing.")
        return principal

    async def read_document(request: Request, max_bytes: int | None = None) -> dict:
        limit = settings.max_request_bytes if max_bytes is None else max_bytes
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > limit:
                raise DomainError("budget_exceeded", "Request exceeds the configured size limit")
        try:
            def invalid_constant(value):
                raise ValueError(value)
            document = json.loads(chunks, parse_constant=invalid_constant)
            if not isinstance(document, dict):
                raise ValueError("Object required")
            return document
        except (ValueError, UnicodeDecodeError) as error:
            raise DomainError("validation_failed", "A valid JSON object is required") from error

    def turn_store():
        if app.state.turns is None:
            from .storage import Database
            from .turns import TurnStore

            database = getattr(service, "database", None) or Database(
                settings.database_url, settings.migration_database_url,
            )
            app.state.turns = TurnStore(database, service=service)
        return app.state.turns

    def job_store():
        if app.state.jobs is None:
            from .jobs import JobStore
            from .storage import Database

            database = getattr(service, "database", None) or Database(settings.database_url, settings.migration_database_url)
            app.state.jobs = JobStore(database)
        return app.state.jobs

    def job_metadata(record):
        from .jobs import FAILURE_CODES, PUBLIC_FIELDS, sanitize_learning_summary

        result = {key: value for key, value in record.items() if key in {*PUBLIC_FIELDS, "lease_active"}}
        if result.get("last_error") is not None and result["last_error"] not in FAILURE_CODES:
            result["last_error"] = "internal_error"
        if result.get("kind") in {"orient", "consolidate"}:
            summary = sanitize_learning_summary(record.get("learning_summary"))
            if summary is not None:
                result["learning_summary"] = summary
        return result

    async def runtime_body(request: Request, model: type[RuntimeBody]) -> dict:
        document = await read_document(request)
        try:
            return model.model_validate(document).model_dump(exclude_none=True)
        except ValidationError as error:
            raise DomainError("validation_failed", "Runtime request fields are invalid.") from error

    async def persona_body(request: Request, model: type[RuntimeBody]) -> dict:
        document = await read_document(request)
        try:
            return model.model_validate(document).model_dump(exclude_none=True)
        except ValidationError as error:
            first = error.errors()[0]
            where = ".".join(str(part) for part in first["loc"]) or "body"
            raise DomainError("validation_failed", f"Persona request field {where}: {first['msg']}.") from error

    def runtime_limit(request: Request) -> int:
        if set(request.query_params) - {"limit"} or len(request.query_params.getlist("limit")) > 1:
            raise DomainError("validation_failed", "Only one limit parameter is supported.")
        value = request.query_params.get("limit", "100")
        if len(value) > 3 or not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 200:
            raise DomainError("validation_failed", "Limit must be an integer from 1 to 200.")
        return int(value)

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        status = {
            "unauthorized": 401, "not_found_or_forbidden": 404,
            "version_conflict": 409, "idempotency_conflict": 409,
            "lease_conflict": 409, "stage_conflict": 409, "turn_terminal": 409,
            "scope_conflict": 409, "provider_uncertain": 409,
            "recovery_acknowledgement_required": 409, "deletion_in_progress": 409,
            "source_unavailable": 409, "context_stale": 409,
            "response_review_required": 409, "response_review_uncertain": 409, "response_review_blocked": 409,
            "dependency_unavailable": 503, "budget_exceeded": 413,
        }.get(error.code, 422)
        return JSONResponse({"error": error.as_dict()}, status_code=status)

    @app.exception_handler(psycopg.OperationalError)
    async def database_error(request, error):
        return JSONResponse({"error": {
            "code": "dependency_unavailable", "message": "Database unavailable", "retryable": True,
        }}, status_code=503)

    @app.get("/health")
    def health():
        return {"status": "alive", "version": __version__}

    @app.get("/v1/recovery")
    def recovery_metadata(principal: Principal = Depends(authenticate_identity)):
        from .recovery import metadata

        return metadata(getattr(service, "database", None), principal)

    @app.get("/v1/capabilities")
    def get_capabilities(principal: Principal = Depends(authenticate)):
        return capabilities(semantic_enabled=getattr(service, "semantic_processor", None) is not None,
                            embedding_enabled=getattr(service, "embedding_provider", None) is not None)

    @app.get("/v1/schema")
    def get_schema(principal: Principal = Depends(authenticate)):
        return schema()

    @app.get("/v1/brains")
    def list_brains(principal: Principal = Depends(authenticate)):
        return {"brains": service.list_brains(principal)}

    @app.post("/v1/brains", status_code=201)
    async def create_brain(request: Request, principal: Principal = Depends(authenticate)):
        body = await read_document(request)
        name = body.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise DomainError("validation_failed", "Name must contain 1 to 120 characters")
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(service.create_brain, principal, name.strip())

    @app.put("/v1/brains/{brain_id}")
    async def ensure_brain(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        """Create a brain with a caller-chosen stable ID if it does not exist; idempotent."""
        body = await read_document(request)
        name = body.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise DomainError("validation_failed", "Name must contain 1 to 120 characters")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", brain_id):
            raise DomainError("validation_failed", "Brain IDs use letters, digits, '.', '_', ':' or '-'")
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(service.ensure_brain, principal, brain_id, name.strip())

    @app.get("/v1/brains/{brain_id}/dashboard")
    def dashboard(brain_id: str, principal: Principal = Depends(authenticate)):
        return service.dashboard(principal, brain_id)

    @app.get("/v1/brains/{brain_id}/timeline")
    def timeline(brain_id: str, role: list[str] = Query(default=["user"]), max_characters: int = 8000,
                 max_item_characters: int = 1500, limit: int = 200, exclude_conversation: str | None = None,
                 event_id: list[str] = Query(default=[]), conversation_id: str | None = None,
                 before_sequence: int | None = None, principal: Principal = Depends(authenticate)):
        return service.timeline(principal, brain_id, roles=role, max_characters=max_characters,
                                max_item_characters=max_item_characters, limit=limit,
                                exclude_conversation=exclude_conversation, event_ids=event_id or None,
                                conversation_id=conversation_id, before_sequence=before_sequence)

    from .memory_map import RecallTraces

    traces = RecallTraces()

    @app.post("/v1/brains/{brain_id}/recall-trace")
    def recall_trace(brain_id: str, body: RecallTrace, principal: Principal = Depends(authenticate)):
        # Held in this process only and never stored; the map shows only records the caller may read.
        return {"recorded": traces.add(principal, brain_id, body.event_ids)}

    @app.get("/v1/brains/{brain_id}/memory-map")
    def memory_map(brain_id: str, max_nodes: int = Query(default=200, ge=1, le=500),
                   max_edges: int = Query(default=400, ge=0, le=1000), include_sensitive: bool = False,
                   trace: bool = False, principal: Principal = Depends(authenticate)):
        from .memory_map import memory_map as read_memory_map

        try:
            with reading():
                return read_memory_map(service, principal, brain_id, max_nodes=max_nodes, max_edges=max_edges,
                                       include_sensitive=include_sensitive,
                                       trace=(traces.last(principal, brain_id) or {}) if trace else None)
        except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled):
            raise DomainError("dependency_unavailable", "Memory is busy updating. Retry the map shortly.",
                              retryable=True) from None

    @app.get("/v1/brains/{brain_id}/status")
    def memory_status(brain_id: str, principal: Principal = Depends(authenticate)):
        return service.memory_status(principal, brain_id)

    @app.get("/v1/brains/{brain_id}/timeline/following")
    def following(brain_id: str, event_id: list[str] = Query(default=[]),
                  principal: Principal = Depends(authenticate)):
        return service.following(principal, brain_id, event_id)

    @app.post("/v1/brains/{brain_id}/notes")
    async def write_note(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .notes import store_note

        body = await runtime_body(request, NoteWrite)
        return await run_in_threadpool(store_note, service, principal, brain_id, body)

    @app.get("/v1/brains/{brain_id}/affect")
    def list_affect(brain_id: str, principal: Principal = Depends(authenticate)):
        from .affect import affect_records

        with reading():
            return affect_records(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/affect/reset")
    def reset_affect(brain_id: str, principal: Principal = Depends(authenticate)):
        # "Clear feelings": audited erasure of every affect record, then a reset marker. Notes are untouched.
        from .affect import clear_affect

        return clear_affect(service, principal, brain_id)

    @app.get("/v1/brains/{brain_id}/persona")
    def get_persona(brain_id: str, principal: Principal = Depends(authenticate)):
        from .persona import current_persona

        with reading():
            return current_persona(service, principal, brain_id)

    @app.put("/v1/brains/{brain_id}/persona")
    async def put_persona(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .persona import set_persona

        body = await persona_body(request, PersonaWrite)
        return await run_in_threadpool(set_persona, service, principal, brain_id, body.pop("card"), **body)

    @app.get("/v1/brains/{brain_id}/persona/versions")
    def get_persona_versions(brain_id: str, principal: Principal = Depends(authenticate)):
        from .persona import persona_versions

        with reading():
            return persona_versions(service, principal, brain_id)

    @app.delete("/v1/brains/{brain_id}/persona/versions")
    def delete_persona_versions(brain_id: str, principal: Principal = Depends(authenticate)):
        from .persona import delete_persona_history

        return delete_persona_history(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/persona/restore")
    async def restore_persona_version(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .persona import restore_persona

        body = await persona_body(request, PersonaRestore)
        return await run_in_threadpool(restore_persona, service, principal, brain_id, body.pop("version"), **body)

    @app.post("/v1/brains/{brain_id}/persona/reset")
    async def reset_persona_card(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .persona import reset_persona

        body = await persona_body(request, PersonaReset)
        return await run_in_threadpool(reset_persona, service, principal, brain_id, **body)

    async def relationship_body(request: Request, model: type[RuntimeBody]) -> dict:
        document = await read_document(request)
        try:
            return model.model_validate(document).model_dump()
        except ValidationError as error:
            first = error.errors()[0]
            where = ".".join(str(part) for part in first["loc"]) or "body"
            raise DomainError("validation_failed", f"Relationship request field {where}: {first['msg']}.") from error

    @app.get("/v1/brains/{brain_id}/relationship")
    def get_relationship(brain_id: str, principal: Principal = Depends(authenticate)):
        from .relationship import relationship

        with reading():
            return relationship(service, principal, brain_id)

    @app.put("/v1/brains/{brain_id}/relationship/support-style")
    async def put_support_style(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .relationship import set_support_style

        body = await relationship_body(request, SupportStyleWrite)
        return await run_in_threadpool(set_support_style, service, principal, brain_id, body["text"])

    @app.post("/v1/brains/{brain_id}/relationship/boundaries")
    async def post_boundary(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .relationship import add_boundary

        body = await relationship_body(request, BoundaryWrite)
        return await run_in_threadpool(add_boundary, service, principal, brain_id, body["topic"], body["aliases"])

    @app.delete("/v1/brains/{brain_id}/relationship/boundaries/{boundary_id}")
    def delete_boundary(brain_id: str, boundary_id: str, principal: Principal = Depends(authenticate)):
        from .relationship import remove_boundary

        return remove_boundary(service, principal, brain_id, boundary_id)

    @app.post("/v1/brains/{brain_id}/relationship/cap")
    async def post_cap(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .relationship import set_cap

        body = await relationship_body(request, FamiliarityCap)
        return await run_in_threadpool(set_cap, service, principal, brain_id, body["level"])

    @app.post("/v1/brains/{brain_id}/relationship/acknowledge")
    async def post_acknowledge(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        # The host reports missed commitments it has shown once, so later context does not repeat them.
        from starlette.concurrency import run_in_threadpool

        from .relationship import acknowledge

        body = await relationship_body(request, CommitmentAcknowledgement)
        return await run_in_threadpool(acknowledge, service, principal, brain_id, body["note_ids"])

    @app.post("/v1/brains/{brain_id}/relationship/reset")
    def post_relationship_reset(brain_id: str, principal: Principal = Depends(authenticate)):
        # Audited erasure of moments, support style, boundaries, cap and acknowledgements, then a reset marker.
        from .relationship import reset_relationship

        return reset_relationship(service, principal, brain_id)

    # The companion's simulated mood (agent_mood): derived from stored events at read time, never stored as a score.
    @app.get("/v1/brains/{brain_id}/mood")
    def get_mood(brain_id: str, principal: Principal = Depends(authenticate)):
        from .mood import mood_state

        with reading():
            return mood_state(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/mood/pin")
    async def pin_companion_mood(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from starlette.concurrency import run_in_threadpool

        from .mood import pin_mood

        document = await read_document(request)
        try:
            body = MoodPin.model_validate(document)
        except ValidationError as error:
            first = error.errors()[0]
            where = ".".join(str(part) for part in first["loc"]) or "body"
            raise DomainError("validation_failed", f"Mood request field {where}: {first['msg']}.") from error
        return await run_in_threadpool(pin_mood, service, principal, brain_id, body.pinned)

    @app.post("/v1/brains/{brain_id}/mood/reset")
    def reset_companion_mood(brain_id: str, principal: Principal = Depends(authenticate)):
        from .mood import reset_mood

        return reset_mood(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/work")
    def work(brain_id: str, principal: Principal = Depends(authenticate)):
        return {"processed": service.work_once(principal, brain_id)}

    @app.post("/v1/actions")
    async def action(request: Request, principal: Principal = Depends(authenticate)):
        body = await read_document(request)
        validate("ActionRequest", body)
        from starlette.concurrency import run_in_threadpool
        if _unmodified_service(service):
            result, validated = await run_in_threadpool(service.respond, principal, body)
        else:
            result, validated = await run_in_threadpool(service.handle, principal, body), False
        if not validated:  # A completed response was already validated, as this same unchanged object.
            validate("ActionResponse", result)
        try:
            # The bytes the default encoding produces for plain JSON data, without first rebuilding every value
            # of the response with jsonable_encoder. Anything json cannot encode takes the default path.
            return JSONResponse(result)
        except (TypeError, ValueError):
            return result

    @app.get("/v1/brains/{brain_id}/runtime/status")
    def runtime_status(brain_id: str, principal: Principal = Depends(authenticate)):
        from .learning_progress import sanitize_learning_progress

        result = turn_store().status(principal, brain_id)
        fields = {
            "brain_id", "durable_sequence", "indexed_sequence", "dependency_generation",
            "scope_generation", "turn_count", "active_lease_count", "reserved_scope_count", "stage_counts", "pending_job_count",
            "response_review_counts", "response_review_calls",
        }
        public = {key: value for key, value in result.items() if key in fields}
        if "learning_progress" in result:
            public["learning_progress"] = sanitize_learning_progress(result["learning_progress"])
        return public

    @app.get("/v1/brains/{brain_id}/runtime/cognitive-usage")
    def cognitive_usage(brain_id: str, principal: Principal = Depends(authenticate)):
        return job_store().cognitive_usage(principal, brain_id)

    @app.get("/v1/brains/{brain_id}/runtime/cognitive-budget")
    def cognitive_budget(brain_id: str, principal: Principal = Depends(authenticate)):
        return job_store().cognitive_budget(principal, brain_id)

    @app.put("/v1/brains/{brain_id}/runtime/cognitive-budget")
    async def configure_cognitive_budget(
        brain_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        from starlette.concurrency import run_in_threadpool

        body = await runtime_body(request, RuntimeBudgetChange)
        return await run_in_threadpool(job_store().configure_cognitive_budget, principal, brain_id, **body)

    @app.get("/v1/brains/{brain_id}/runtime/learning-progress")
    def learning_progress(brain_id: str, principal: Principal = Depends(authenticate)):
        from .learning_progress import sanitize_learning_progress

        return sanitize_learning_progress(job_store().learning_progress(
            principal, brain_id, configured=getattr(service, "semantic_processor", None) is not None,
        ))

    @app.get("/v1/brains/{brain_id}/runtime/scope")
    def active_scope(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        if any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
            raise DomainError("validation_failed", "Scope parameters must not be repeated.")
        try:
            body = RuntimeScope.model_validate(dict(request.query_params)).model_dump()
        except ValidationError as error:
            raise DomainError("validation_failed", "A conversation ID and branch ID are required.") from error
        row = turn_store().active_scope(principal, brain_id, **body)
        return {"turn": runtime_metadata(row) if row is not None else None}

    @app.get("/v1/brains/{brain_id}/runtime/jobs")
    def list_jobs(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        return {"jobs": [job_metadata(record) for record in job_store().list(
            principal, brain_id, limit=runtime_limit(request),
        )]}

    @app.get("/v1/brains/{brain_id}/runtime/jobs/{job_id}")
    def get_job(brain_id: str, job_id: str, principal: Principal = Depends(authenticate)):
        return job_metadata(job_store().get(principal, brain_id, job_id))

    @app.post("/v1/brains/{brain_id}/runtime/jobs/{job_id}/retry-learning")
    async def retry_learning(
        brain_id: str, job_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeLearningRetry)
        from starlette.concurrency import run_in_threadpool

        if getattr(service, "semantic_processor", None) is None:
            await run_in_threadpool(job_store().get, principal, brain_id, job_id)
            raise DomainError("dependency_unavailable", "Model-driven learning is not configured.")
        result = await run_in_threadpool(job_store().retry_learning, principal, brain_id, job_id, **body)
        return job_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns", status_code=201)
    async def begin_turn(
        brain_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeBegin)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().begin, principal, brain_id, **body)
        return runtime_metadata(result)

    @app.get("/v1/brains/{brain_id}/runtime/turns")
    def list_turns(
        brain_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        return {"turns": [runtime_metadata(record) for record in turn_store().list(
            principal, brain_id, limit=runtime_limit(request),
        )]}

    @app.get("/v1/brains/{brain_id}/runtime/turns/{turn_id}")
    def get_turn(brain_id: str, turn_id: str, principal: Principal = Depends(authenticate)):
        return runtime_metadata(turn_store().get(principal, brain_id, turn_id))

    @app.get("/v1/brains/{brain_id}/runtime/turns/{turn_id}/sources")
    def turn_sources(brain_id: str, turn_id: str, principal: Principal = Depends(authenticate)):
        return turn_store().sources(principal, brain_id, turn_id)

    @app.get("/v1/brains/{brain_id}/runtime/turns/{turn_id}/history")
    def turn_history(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        fields = {"revision", "stage", "operation", "fence", "failure_code", "occurred_at"}
        return {"history": [
            {key: value for key, value in record.items() if key in fields}
            for record in turn_store().history(
                principal, brain_id, turn_id, limit=runtime_limit(request),
            )
        ]}

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/claim")
    async def claim_turn(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeClaim)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().claim, principal, brain_id, turn_id, **body)
        return runtime_metadata(result, include_lease=True)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/renew")
    async def renew_turn(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeRenew)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().renew, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/advance")
    async def advance_turn(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeAdvance)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().advance, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/recall-reservations")
    async def reserve_turn_recall(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeRecallReservation)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().reserve_recall, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/response-review/reserve")
    async def reserve_turn_response_review(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeResponseReviewReservation)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().reserve_response_review, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/response-review/complete")
    async def complete_turn_response_review(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeResponseReviewCompletion)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().complete_response_review, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/output")
    async def record_turn_output(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeOutput)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().record_output, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/orient")
    async def orient_turn(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeLeaseMutation)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(service.orient_turn, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/release")
    async def release_turn(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeLeaseMutation)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().release, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/fail")
    async def fail_turn(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeFail)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().fail, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.post("/v1/brains/{brain_id}/runtime/turns/{turn_id}/finish")
    async def finish_turn(
        brain_id: str, turn_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        body = await runtime_body(request, RuntimeLeaseMutation)
        from starlette.concurrency import run_in_threadpool

        result = await run_in_threadpool(turn_store().finish, principal, brain_id, turn_id, **body)
        return runtime_metadata(result)

    @app.get("/v1/archives/{archive_id}")
    def download_archive(archive_id: str, principal: Principal = Depends(authenticate)):
        return service.download_archive(principal, archive_id)

    @app.post("/v1/brains/{brain_id}/archives", status_code=201)
    async def upload_archive(
        brain_id: str, request: Request, principal: Principal = Depends(authenticate),
    ):
        document = await read_document(request, max_bytes=16_000_000)
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(service.upload_archive, principal, brain_id, document)

    static = files("membrain").joinpath("web")
    app.mount("/static", StaticFiles(directory=str(static)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def console():
        return static.joinpath("index.html").read_text(encoding="utf-8")

    @app.get("/memory", response_class=HTMLResponse)
    def memory_page():
        return static.joinpath("memory.html").read_text(encoding="utf-8")

    return app
