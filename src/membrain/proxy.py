"""OpenAI-compatible memory proxy: give any bot that lets you set a ``base_url`` long-term memory.

Point the bot's ``base_url`` at the proxy instead of the model provider (DeepSeek, OpenAI, a local model...). For each
chat completion the proxy adds the person's memory, fenced as historical data, to the start of their latest message
(not as a system message, so remembered text never gets the authority of the bot's own instructions), forwards
the request upstream (streaming or not), and stores the message and the reply. Everything else is passed through.

People are told apart by the request's ``user`` field or the ``X-Membrain-User`` header (with optional
``X-Membrain-Platform`` and ``X-Membrain-Group``); requests without either share one memory.
``X-Membrain-Roleplay: <character>`` keeps a role-play's memory apart from real life; ``X-Membrain-Share-Real-Life: 1``
also shows that person's non-sensitive real-life notes in it. The memory
block is placed after the stable start of the conversation so providers' prompt caches keep working.

By default the proxy listens on loopback and forwards the client's own API key. To serve other machines, store the
provider key in ``MEMBRAIN_UPSTREAM_KEY`` and set ``MEMBRAIN_PROXY_TOKEN``; clients then use the token as their key.
"""
from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .adapters.chatbot import ChatMemory, Speaker

PRODUCER = "membrain-proxy"
DEFAULT_PORT = 8790
MAX_BODY_BYTES = 32 * 1024 * 1024  # Generous for pasted documents and inline images.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_LOOPBACK_ORIGIN = r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?"
_FORWARDED = ("content-type", "accept", "openai-organization", "openai-project", "anthropic-version")
_logger = logging.getLogger("membrain.proxy")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content
                         if isinstance(part, dict) and part.get("type") in ("text", "input_text"))
    return ""


def _latest_user(messages: list) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], dict) and messages[index].get("role") == "user":
            return index
    return None


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _hostname(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):  # [::1]:8790
        return value[1:].split("]", 1)[0]
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": {"message": message, "type": "invalid_request_error"}}, status)


NAMESPACE = re.compile(r"[A-Za-z0-9_-]{1,40}\Z")


def parse_tokens(value: str | None) -> dict[str, str]:
    """``MEMBRAIN_PROXY_TOKENS``: comma-separated ``token:namespace`` pairs, one per bot or client."""
    tokens = {}
    for entry in (value or "").split(","):
        if not entry.strip():
            continue
        secret, _, namespace = entry.strip().rpartition(":")
        if len(secret) < 16 or not NAMESPACE.match(namespace):
            raise ValueError("MEMBRAIN_PROXY_TOKENS entries are token:namespace, with tokens of at least 16 "
                             "characters and namespaces of letters, digits, '-' or '_'.")
        tokens[secret] = namespace
    return tokens


def create_proxy_app(memory: ChatMemory, upstream: str, *, upstream_key: str | None = None,
                     token: str | None = None, transport: httpx.AsyncBaseTransport | None = None,
                     allowed_origins: frozenset[str] = frozenset(), tokens: dict[str, str] | None = None) -> FastAPI:
    """The proxy app. With ``token`` clients must present it and ``upstream_key`` is sent upstream instead.

    ``tokens`` gives each bot its own token and namespace: people it names are kept inside that namespace, so
    one bot's token cannot read another bot's people, and every request must name its person.

    Without a token the proxy only answers requests addressed to this computer by name (a web page that
    rebinds its own domain to 127.0.0.1 is refused) and refuses requests that browsers send on behalf of
    other sites, unless their origin is in ``allowed_origins``.
    """
    keys: dict[str, str | None] = {**({token: None} if token else {}), **(tokens or {})}
    if bool(keys) != bool(upstream_key):
        raise ValueError("Set both the upstream key and the proxy token, or neither.")
    origins = frozenset(origin.rstrip("/").lower() for origin in allowed_origins)
    upstream = upstream.rstrip("/")
    client = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=15), transport=transport)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.aclose()

    app = FastAPI(title="memBrain memory proxy", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    # Browser front ends that call the proxy directly need CORS answers; the guard below runs first and refuses
    # every origin that is neither this computer nor listed.
    app.add_middleware(CORSMiddleware, allow_origins=sorted(origins), allow_origin_regex=_LOOPBACK_ORIGIN,
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"], max_age=600)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if not keys and _hostname(request.headers.get("host", "")) not in LOOPBACK_HOSTS:
            return _error(403, "This proxy only answers requests addressed to localhost or 127.0.0.1.")
        origin = request.headers.get("origin", "").rstrip("/").lower()
        if origin and origin not in origins and _hostname(origin.split("://", 1)[-1]) not in LOOPBACK_HOSTS:
            # Bots call the proxy from a server; a browser page from another site must be allowed explicitly.
            return _error(403, "Requests from web pages need their origin in MEMBRAIN_PROXY_ORIGINS.")
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = 0
        if size > MAX_BODY_BYTES:
            return _error(413, "The request is too large.")
        return await call_next(request)

    def authorize(request: Request) -> tuple[dict, str | None] | None:
        """Forwarded headers and the client's namespace, or ``None`` when a token is required and wrong."""
        forwarded = {name: request.headers[name] for name in _FORWARDED if name in request.headers}
        supplied = request.headers.get("authorization", "")
        if not keys:
            if supplied:
                forwarded["authorization"] = supplied
            return forwarded, None
        presented = supplied.removeprefix("Bearer ").strip().encode()
        matched = [namespace for secret, namespace in keys.items() if hmac.compare_digest(presented, secret.encode())]
        if not matched:
            return None
        forwarded["authorization"] = f"Bearer {upstream_key}"
        return forwarded, matched[0]

    def target(path: str) -> str:
        path = path.lstrip("/")
        return f"{upstream}/{path.removeprefix('v1/') if path.startswith('v1/') else path}"

    def speaker(request: Request, body: dict, namespace: str | None) -> Speaker | None:
        user = request.headers.get("x-membrain-user") or body.get("user")
        platform = request.headers.get("x-membrain-platform") or "api"
        group = request.headers.get("x-membrain-group") or None
        if namespace:
            if not user:
                return None  # A namespaced bot must say whose memory to use; never fall back to a shared one.
            platform = f"{namespace}/{platform}"
        return Speaker(platform, str(user) if user else "default", group)

    async def chat(request: Request, path: str) -> Response:
        auth = authorize(request)
        if auth is None:
            return _error(401, "Invalid proxy token.")
        forwarded, namespace = auth
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            # A form or text/plain post is what a cross-site page can send without asking first.
            return _error(415, "Chat completions must be sent as application/json.")
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return _error(413, "The request is too large.")
        try:
            body = json.loads(raw)
            messages = body["messages"]
            assert isinstance(messages, list)
        except (ValueError, KeyError, AssertionError, TypeError):
            return await passthrough(request, path, raw, forwarded)
        person, index = speaker(request, body, namespace), _latest_user(messages)
        if person is None:
            return _error(400, "Name the person with the request's user field or the X-Membrain-User header.")
        # A role-play character (SillyTavern and similar) gets its own memory, apart from the person's real life.
        roleplay = " ".join(request.headers.get("x-membrain-roleplay", "").split())[:80] or None
        share = request.headers.get("x-membrain-share-real-life", "").lower() in ("1", "true", "yes")
        session = request.headers.get("x-membrain-session")
        session = (f"{namespace}:{session}" if namespace and session else session) or memory.session(
            person, f"roleplay:{roleplay}" if roleplay else None)
        turn, prompt = uuid.uuid4().hex[:20], _text(messages[index]["content"]) if index is not None else ""
        if prompt.strip():
            try:
                block = await asyncio.to_thread(memory.context, person, prompt, session=session, turn_id=turn,
                                                roleplay=roleplay, share_real_life=share)
            except Exception as error:  # Memory must never stop the bot from answering.
                _logger.warning("memory failed: %s", type(error).__name__)
                block = None
            if block:
                latest = dict(messages[index])
                content = latest.get("content")
                latest["content"] = ([{"type": "text", "text": block}, *content] if isinstance(content, list)
                                     else f"{block}\n\n{content if isinstance(content, str) else ''}")
                body["messages"] = [*messages[:index], latest, *messages[index + 1:]]

        async def store(reply: str) -> None:
            if prompt.strip() and reply.strip():
                try:
                    await asyncio.to_thread(memory.record, person, reply, session=session, turn_id=turn,
                                            prompt=prompt, roleplay=roleplay)
                except Exception as error:
                    _logger.warning("recording failed: %s", type(error).__name__)

        outgoing = client.build_request("POST", target(path), headers=forwarded, json=body)
        if not body.get("stream"):
            response = await client.send(outgoing)
            if response.status_code == 200:
                try:
                    await store(_text(response.json()["choices"][0]["message"].get("content")))
                except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                    pass
            return Response(response.content, response.status_code,
                            media_type=response.headers.get("content-type"))
        response = await client.send(outgoing, stream=True)

        async def relay():
            parts = []
            try:
                async for line in response.aiter_lines():
                    yield line + "\n"
                    if line.startswith("data:") and response.status_code == 200:
                        try:
                            delta = json.loads(line[5:])["choices"][0]["delta"].get("content")
                        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                            continue
                        if isinstance(delta, str):
                            parts.append(delta)
            finally:
                await response.aclose()
            await store("".join(parts))

        return StreamingResponse(relay(), response.status_code,
                                 media_type=response.headers.get("content-type", "text/event-stream"))

    async def passthrough(request: Request, path: str, raw: bytes | None = None, forwarded: dict | None = None):
        if forwarded is None:
            auth = authorize(request)
            if auth is None:
                return _error(401, "Invalid proxy token.")
            forwarded = auth[0]
        response = await client.request(request.method, target(path), headers=forwarded,
                                        params=request.query_params,
                                        content=raw if raw is not None else await request.body())
        return Response(response.content, response.status_code, media_type=response.headers.get("content-type"))

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def route(path: str, request: Request):
        if request.method == "POST" and path.strip("/").removeprefix("v1/") == "chat/completions":
            return await chat(request, path)
        return await passthrough(request, path)

    return app


def serve(upstream: str, *, host: str = "127.0.0.1", port: int = DEFAULT_PORT, directory: Path | None = None,
          group_memory: str = "separate", upstream_key: str | None = None, token: str | None = None,
          tokens: dict[str, str] | None = None) -> None:
    import uvicorn

    from . import host as host_module

    if not is_loopback(host) and not (token or tokens):
        raise SystemExit("Listening beyond this computer needs MEMBRAIN_PROXY_TOKENS (or MEMBRAIN_PROXY_TOKEN) and "
                         "MEMBRAIN_UPSTREAM_KEY, so only your bots can use the proxy and read memory.")
    directory = host_module.profile_directory(directory)
    host_module.ensure_installation(directory)
    from .extraction import Extractor

    extractor = Extractor.from_environment(base_url=upstream, api_key=upstream_key)
    if extractor is not None and not extractor.api_key:
        raise SystemExit("Note extraction needs MEMBRAIN_EXTRACT_KEY (or MEMBRAIN_UPSTREAM_KEY) for its model.")
    memory = ChatMemory(directory, group_memory=group_memory, producer=PRODUCER, tools=None, extractor=extractor)
    memory.start()
    print(f"memBrain proxy: set your bot's base_url to http://{host}:{port}/v1 (forwarding to {upstream})",
          flush=True)
    import os

    allowed = frozenset(origin.strip() for origin in os.environ.get("MEMBRAIN_PROXY_ORIGINS", "").split(",")
                        if origin.strip())
    uvicorn.run(create_proxy_app(memory, upstream, upstream_key=upstream_key, token=token, tokens=tokens,
                                 allowed_origins=allowed), host=host, port=port, log_level="warning")
