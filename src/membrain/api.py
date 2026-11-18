import hashlib
import json
import re
import threading
from contextlib import ExitStack, asynccontextmanager
from importlib.resources import files
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .config import Settings, configured_service
from .contracts import CONTRACT_VERSION, schema, validate
from .helpers import DomainError, Principal
from .service import MemoryService, reading

RuntimeIdentifier = Annotated[str, Field(min_length=1, max_length=256)]
RuntimeCounter = Annotated[int, Field(ge=0, le=2**63 - 1)]
RuntimeRevision = Annotated[int, Field(ge=1, le=2**63 - 1)]


class RuntimeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NoteSource(RuntimeBody):
    producer_ref: RuntimeIdentifier
    source_event_key: RuntimeIdentifier
    source_revision: RuntimeRevision = 1


class ErasureReference(RuntimeBody):
    producer_ref: RuntimeIdentifier
    source_event_key: RuntimeIdentifier
    event_id: RuntimeIdentifier | None = None


class ErasureRead(RuntimeBody):
    references: Annotated[list[ErasureReference], Field(max_length=128)]


class SourceMessagesRead(RuntimeBody):
    messages: Annotated[list[NoteSource], Field(min_length=1, max_length=64)]


class MessageCueItem(RuntimeBody):
    event_id: RuntimeIdentifier | None = None
    sequence: RuntimeRevision | None = None
    producer_ref: RuntimeIdentifier | None = None
    source_event_key: RuntimeIdentifier | None = None
    cues: Annotated[list[Annotated[str, Field(min_length=1, max_length=200)]], Field(max_length=6)]


class MessageCuesWrite(RuntimeBody):
    items: Annotated[list[MessageCueItem], Field(max_length=200)]
    model_version: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    reviewed_through_sequence: RuntimeCounter | None = None


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
    context_source_messages: Annotated[list[NoteSource], Field(max_length=64)] = []
    require_current_sources: bool = False
    expected_dependency_generation: RuntimeCounter | None = None
    expected_recording_revision: RuntimeCounter | None = None
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
    moment: str | None = None
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
    preset: Annotated[str, Field(min_length=1, max_length=40)] | None = None  # A personality type, or "random".


# Feedback on the companion's manner that the host AI reports (P2); the kind and sources are checked by
# persona_growth.report_feedback, whose messages say what is wrong.
class MannerFeedback(RuntimeBody):
    kind: Annotated[str, Field(min_length=1, max_length=40)]
    source_event_ids: Annotated[list[RuntimeIdentifier], Field(max_length=10)] = []
    source_messages: Annotated[list[NoteSource], Field(max_length=10)] = []


# Preset personas and changes the host AI proposes; persona_presets and persona_growth check the values.
class PersonaPresetSwitch(RuntimeBody):
    preset: Annotated[str, Field(min_length=1, max_length=40)]
    made_by: Literal["host", "user"] = "user"
    source_event_ids: Annotated[list[RuntimeIdentifier], Field(max_length=1)] = []
    source_messages: Annotated[list[NoteSource], Field(max_length=1)] = []


class PersonaProposal(RuntimeBody):
    changes: dict
    reason: PersonaReason
    source_event_ids: Annotated[list[RuntimeIdentifier], Field(max_length=10)] = []
    source_messages: Annotated[list[NoteSource], Field(max_length=10)] = []


class PersonaConfirmation(RuntimeBody):
    source_event_ids: Annotated[list[RuntimeIdentifier], Field(max_length=1)] = []
    source_messages: Annotated[list[NoteSource], Field(max_length=1)] = []
    conversation_id: RuntimeIdentifier | None = None  # The conversation of a cited message not recorded yet.


# Relationship (R1). The texts are checked by relationship.py, whose messages say what is wrong.
class BoundaryWrite(RuntimeBody):
    topic: Annotated[str, Field(max_length=2000)]
    aliases: Annotated[list[Annotated[str, Field(max_length=2000)]], Field(max_length=50)] = []


class CommitmentAcknowledgement(RuntimeBody):
    note_ids: Annotated[list[RuntimeIdentifier], Field(max_length=50)]


class MoodPin(RuntimeBody):
    pinned: bool


class RecordingControl(RuntimeBody):
    paused: bool
    expected_revision: Annotated[int, Field(ge=0, lt=2**63 - 1)]


def capabilities(*, embedding_enabled=False) -> dict:
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
            "memBrain runs no model of its own; notes, cues and other interpretations come from the host's AI.",
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
    return (isinstance(service, MemoryService) and getattr(kind, "handle", None) is MemoryService.handle
            and getattr(kind, "respond", None) is MemoryService.respond
            and getattr(kind, "_respond", None) is MemoryService._respond
            and not {"handle", "respond", "_respond"}.intersection(own))


def create_app(settings: Settings | None = None, service=None, jobs=None, *, after_action=None) -> FastAPI:
    """The memory service's HTTP application.

    ``after_action(principal, request, response)``, when given, runs after an action posted to ``/v1/actions`` has
    completed (its response is final, valid and has outcome ``completed``), before the response is sent. It is for
    the host-side bookkeeping of a local installation; a failure in it is ignored and never changes the response."""
    settings = settings or Settings.from_env()
    resources = ExitStack()
    recall_runner = None
    if service is None:
        service = resources.enter_context(configured_service(settings))
        if settings.recall_processes:
            from .recall_service_executor import RecallServiceExecutor

            recall_runner = service.recall_runner = RecallServiceExecutor(settings.recall_processes, settings)
            service.request_runner = recall_runner.respond
            resources.callback(recall_runner.close)

    @asynccontextmanager
    async def lifespan(app):
        try:
            if recall_runner is not None:
                await run_in_threadpool(recall_runner.start)
            warm_up = getattr(getattr(service, "_embedding_provider", None), "warm_up", None)
            if warm_up is not None:
                # Not awaited: the service answers while the local model loads, and a recall that arrives first
                # loads it itself.
                threading.Thread(target=warm_up, name="embedding-warm-up", daemon=True).start()
            yield
        finally:
            resources.close()

    app = FastAPI(title="memBrain", version=__version__, lifespan=lifespan)
    app.state.service = service
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

    def job_store():
        if app.state.jobs is None:
            from .jobs import JobStore
            from .storage import Database

            database = getattr(service, "database", None) or Database(settings.database_url, settings.migration_database_url)
            app.state.jobs = JobStore(database)
        return app.state.jobs

    def job_metadata(record):
        from .jobs import FAILURE_CODES, PUBLIC_FIELDS

        result = {key: value for key, value in record.items() if key in {*PUBLIC_FIELDS, "lease_active"}}
        if result.get("last_error") is not None and result["last_error"] not in FAILURE_CODES:
            result["last_error"] = "internal_error"
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
            "lease_conflict": 409, "provider_uncertain": 409,
            "recovery_acknowledgement_required": 409, "deletion_in_progress": 409,
            "source_unavailable": 409, "context_stale": 409, "recording_paused": 409, "recording_stale": 409,
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
        return capabilities(embedding_enabled=getattr(service, "embedding_provider", None) is not None)

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

    @app.post("/v1/brains/{brain_id}/recall-windows")
    async def recall_windows(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        body = await read_document(request)
        if set(body) - {'windows', 'query', 'conversation_id', 'branch_id'}:
            raise DomainError('validation_failed', 'Unknown recall window fields.')
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(service.recall_windows, principal, brain_id, body.get('windows'),
                                      body.get('query'), conversation_id=body.get('conversation_id'),
                                      branch_id=body.get('branch_id'))

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
                   trace: bool = False, structure: bool = False, principal: Principal = Depends(authenticate)):
        from .memory_map import memory_map as read_memory_map
        from .structure_map import structure_map

        try:
            with reading():
                return (structure_map if structure else read_memory_map)(service, principal, brain_id, max_nodes=max_nodes, max_edges=max_edges,
                                       include_sensitive=include_sensitive,
                                       trace=(traces.last(principal, brain_id) or {}) if trace else None)
        except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled):
            raise DomainError("dependency_unavailable", "Memory is busy updating. Retry the map shortly.",
                              retryable=True) from None

    @app.get("/v1/brains/{brain_id}/companion-map")
    def companion_map(brain_id: str, max_nodes: int = Query(default=200, ge=1, le=500),
                      max_edges: int = Query(default=400, ge=0, le=1000), include_sensitive: bool = False,
                      principal: Principal = Depends(authenticate)):
        from .companion_map import companion_map as read_companion_map

        try:
            with reading():
                return read_companion_map(service, principal, brain_id, max_nodes=max_nodes,
                                          max_edges=max_edges, include_sensitive=include_sensitive)
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

    @app.post("/v1/brains/{brain_id}/source-messages")
    def source_messages(brain_id: str, body: SourceMessagesRead, principal: Principal = Depends(authenticate)):
        return service.source_messages(principal, brain_id, [ref.model_dump() for ref in body.messages])

    @app.post("/v1/brains/{brain_id}/message-cues")
    async def write_message_cues(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from . import message_cues

        body = await runtime_body(request, MessageCuesWrite)
        return await run_in_threadpool(message_cues.write, service, principal, brain_id, body["items"],
                                       model_version=body.get("model_version"),
                                       reviewed_through_sequence=body.get("reviewed_through_sequence"))

    @app.get("/v1/brains/{brain_id}/message-cues/pending")
    def pending_message_cues(brain_id: str, limit: int = Query(20, ge=1, le=100),
                             max_characters: int = Query(6000, ge=200, le=50_000),
                             whole_conversations: bool = False,
                             principal: Principal = Depends(authenticate)):
        from . import message_cues

        return message_cues.pending(service, principal, brain_id, limit=limit, max_characters=max_characters,
                                    whole_conversations=whole_conversations)

    @app.get("/v1/brains/{brain_id}/recording")
    def get_recording(brain_id: str, principal: Principal = Depends(authenticate)):
        from .recording_control import recording_status

        return recording_status(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/recording/erasures")
    def read_recording_erasures(brain_id: str, body: ErasureRead, principal: Principal = Depends(authenticate)):
        from .recording_control import erased_sources

        return erased_sources(service, principal, brain_id, [ref.model_dump() for ref in body.references])

    @app.put("/v1/brains/{brain_id}/recording")
    async def change_recording(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from .recording_control import set_recording

        body = await runtime_body(request, RecordingControl)
        return await run_in_threadpool(set_recording, service, principal, brain_id, **body)

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

    # Persona suggestions from the user's feedback (P2). Listing stores any suggestion that has become due; the card
    # changes only when the user accepts one.
    @app.get("/v1/brains/{brain_id}/persona/proposals")
    def get_persona_proposals(brain_id: str, principal: Principal = Depends(authenticate)):
        from .persona_growth import persona_proposals

        return persona_proposals(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/persona/proposals/{proposal_id}/accept")
    def accept_persona_proposal(brain_id: str, proposal_id: str, principal: Principal = Depends(authenticate)):
        from .persona_growth import accept_proposal

        return accept_proposal(service, principal, brain_id, proposal_id)

    @app.post("/v1/brains/{brain_id}/persona/proposals/{proposal_id}/reject")
    def reject_persona_proposal(brain_id: str, proposal_id: str, principal: Principal = Depends(authenticate)):
        from .persona_growth import reject_proposal

        return reject_proposal(service, principal, brain_id, proposal_id)

    @app.get("/v1/brains/{brain_id}/persona/presets")
    def get_persona_presets(brain_id: str, principal: Principal = Depends(authenticate)):
        from .persona_presets import listing

        with reading():
            return listing(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/persona/first")
    def post_first_persona(brain_id: str, principal: Principal = Depends(authenticate)):
        # A preset picked at random, only for a brain with no persona record of any kind (persona_presets).
        from .persona_presets import assign_first_persona, has_any_record

        with reading():  # Every session start asks; only a brain without any persona record takes the lock.
            if has_any_record(service, principal, brain_id):
                return {"assigned": False, "preset": None}
        return assign_first_persona(service, principal, brain_id)

    @app.post("/v1/brains/{brain_id}/persona/preset")
    async def post_persona_preset(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from .persona_presets import switch_preset

        body = await persona_body(request, PersonaPresetSwitch)
        return await run_in_threadpool(switch_preset, service, principal, brain_id, body.pop("preset"), **body)

    @app.post("/v1/brains/{brain_id}/persona/proposals")
    async def post_persona_proposal(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from .persona_growth import propose_change

        body = await persona_body(request, PersonaProposal)
        return await run_in_threadpool(propose_change, service, principal, brain_id, body.pop("changes"), **body)

    @app.post("/v1/brains/{brain_id}/persona/proposals/{proposal_id}/confirm")
    async def confirm_persona_proposal(brain_id: str, proposal_id: str, request: Request,
                                       principal: Principal = Depends(authenticate)):
        from .persona_growth import confirm_change

        body = await persona_body(request, PersonaConfirmation)
        return await run_in_threadpool(confirm_change, service, principal, brain_id, proposal_id, **body)

    @app.post("/v1/brains/{brain_id}/persona/proposals/{proposal_id}/decline")
    def decline_persona_proposal(brain_id: str, proposal_id: str, principal: Principal = Depends(authenticate)):
        from .persona_growth import decline_change

        return decline_change(service, principal, brain_id, proposal_id)

    @app.post("/v1/brains/{brain_id}/persona/feedback")
    async def post_manner_feedback(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        from .persona_growth import report_feedback

        body = await persona_body(request, MannerFeedback)
        return await run_in_threadpool(report_feedback, service, principal, brain_id, body.pop("kind"), **body)

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

    @app.get("/v1/brains/{brain_id}/relationship/boundaries")
    def get_relationship_boundaries(brain_id: str, principal: Principal = Depends(authenticate)):
        from .relationship import relationship_boundaries

        with reading():
            return relationship_boundaries(service, principal, brain_id)

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

    @app.post("/v1/brains/{brain_id}/relationship/acknowledge")
    async def post_acknowledge(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        # The host reports missed commitments it has shown once, so later context does not repeat them.
        from starlette.concurrency import run_in_threadpool

        from .relationship import acknowledge

        body = await relationship_body(request, CommitmentAcknowledgement)
        return await run_in_threadpool(acknowledge, service, principal, brain_id, body["note_ids"])

    @app.post("/v1/brains/{brain_id}/relationship/reset")
    def post_relationship_reset(brain_id: str, principal: Principal = Depends(authenticate)):
        # Audited erasure of shared moments and acknowledgements (the boundaries stay), then a reset marker.
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
        if after_action is not None and result.get("outcome") == "completed":
            try:
                await run_in_threadpool(after_action, principal, body, result)
            except Exception:
                pass  # Bookkeeping beside a completed action never turns it into a failure.
        try:
            # The bytes the default encoding produces for plain JSON data, without first rebuilding every value
            # of the response with jsonable_encoder. Anything json cannot encode takes the default path.
            return JSONResponse(result)
        except (TypeError, ValueError):
            return result

    @app.get("/v1/brains/{brain_id}/runtime/jobs")
    def list_jobs(brain_id: str, request: Request, principal: Principal = Depends(authenticate)):
        return {"jobs": [job_metadata(record) for record in job_store().list(
            principal, brain_id, limit=runtime_limit(request),
        )]}

    @app.get("/v1/brains/{brain_id}/runtime/jobs/{job_id}")
    def get_job(brain_id: str, job_id: str, principal: Principal = Depends(authenticate)):
        return job_metadata(job_store().get(principal, brain_id, job_id))

    # The turn lifecycle API (runtime/status, runtime/scope, runtime/turns, runtime/ephemeral-turns and the
    # operations on a turn) was removed with runtime mode; its paths answer 404 like any unknown path.

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
