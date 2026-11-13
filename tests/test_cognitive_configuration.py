import hashlib
import traceback
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from membrain import (
    api,
    cli,
    config,
    local_embeddings,
    recall_service_executor,
    semantic_provider,
    service,
    storage,
)
from membrain.config import Settings, configured_service
from membrain.helpers import Principal


@pytest.fixture
def cognitive_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for prefix in ("MEMORY_COGNITION", "MEMORY_EMBEDDING"):
        for key in ("BASE_URL", "API_KEY", "MODEL", "MODEL_VERSION", "DIMENSIONS", "THINKING",
                    "REASONING_EFFORT", "MAX_ENVELOPE_BYTES"):
            monkeypatch.delenv(prefix + "_" + key, raising=False)
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://unused")
    return monkeypatch


def test_model_backends_are_disabled_without_explicit_configuration(cognitive_env):
    settings = Settings.from_env()
    assert settings.cognition_base_url is None
    assert settings.cognition_thinking is None
    assert settings.embedding_local_directory is None


def test_complete_environment_preserves_model_identity_and_hides_keys(cognitive_env):
    for key, value in {
        "MEMORY_COGNITION_BASE_URL": "https://cognition.example/v1",
        "MEMORY_COGNITION_API_KEY": "private-cognition-token",
        "MEMORY_COGNITION_MODEL": "configured-model",
        "MEMORY_COGNITION_THINKING": "disabled",
    }.items():
        cognitive_env.setenv(key, value)
    settings = Settings.from_env()
    assert settings.cognition_model == "configured-model"
    assert settings.cognition_thinking == "disabled"
    assert "private-cognition-token" not in repr(settings)


@pytest.mark.parametrize("local", [False, True])
def test_settings_of_the_removed_remote_embedding_provider_are_ignored_with_a_warning(cognitive_env, caplog, local):
    """A deployment configured for the metered remote embedding provider starts: its settings, complete, partial or
    malformed, are ignored with a warning that names them and never their values; the local model is used when set."""
    removed = {"MEMORY_EMBEDDING_BASE_URL": "https://embedding.example/v1",
               "MEMORY_EMBEDDING_API_KEY": "private-embedding-token", "MEMORY_EMBEDDING_MODEL": "configured-embedding",
               "MEMORY_EMBEDDING_MODEL_VERSION": "release-7", "MEMORY_EMBEDDING_DIMENSIONS": "not-a-number"}
    for key, value in removed.items():
        cognitive_env.setenv(key, value)
    if local:
        cognitive_env.setenv("MEMORY_EMBEDDING_LOCAL_DIRECTORY", "/models/local-embedding")
    else:
        cognitive_env.delenv("MEMORY_EMBEDDING_LOCAL_DIRECTORY", raising=False)
    with caplog.at_level("WARNING", logger="membrain.config"):
        settings = Settings.from_env()
    assert settings.embedding_local_directory == ("/models/local-embedding" if local else None)
    assert not any(hasattr(settings, name) for name in ("embedding_base_url", "embedding_api_key", "embedding_model",
                                                         "embedding_model_version", "embedding_dimensions"))
    warning = caplog.text
    assert all(key in warning for key in removed) and "MEMORY_EMBEDDING_LOCAL_DIRECTORY" in warning
    assert not any(value in warning for value in removed.values())
    assert "private-embedding-token" not in repr(settings)


def test_the_factory_builds_only_the_local_embedding_model(cognitive_env, monkeypatch):
    opened = []
    monkeypatch.setattr(storage.Database, "check_compatibility", lambda *args, **kwargs: None)

    class Local:
        def __init__(self, directory):
            opened.append(directory)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(local_embeddings, "LocalEmbeddingProvider", Local)
    monkeypatch.setattr(service, "MemoryService", lambda database, **kwargs: SimpleNamespace(**kwargs))
    cognitive_env.setenv("MEMORY_EMBEDDING_BASE_URL", "https://embedding.example/v1")
    cognitive_env.setenv("MEMORY_EMBEDDING_LOCAL_DIRECTORY", "/models/local-embedding")
    with configured_service(Settings.from_env()) as configured:
        assert isinstance(configured.embedding_provider, Local)
    assert [str(directory) for directory in opened] == ["/models/local-embedding"]


@pytest.mark.parametrize("key,value", [
    ("MEMORY_COGNITION_MODEL", "configured-model"),
    ("MEMORY_COGNITION_THINKING", "enabled"),
    ("MEMORY_COGNITION_THINKING", "disabled"),
])
def test_partial_or_malformed_configuration_does_not_silently_activate_defaults(cognitive_env, key, value):
    cognitive_env.setenv(key, value)
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize("thinking", ["enabled", "disabled"])
def test_thinking_environment_is_preserved_with_complete_provider(cognitive_env, thinking):
    for key, value in {
        "BASE_URL": "https://cognition.example/v1", "API_KEY": "private-token",
        "MODEL": "configured-model", "THINKING": thinking,
    }.items():
        cognitive_env.setenv("MEMORY_COGNITION_" + key, value)
    assert Settings.from_env().cognition_thinking == thinking


@pytest.mark.parametrize("thinking", ["", "ENABLED", " disabled", "none", "private-invalid-value"])
def test_invalid_thinking_environment_is_rejected_without_echoing_configuration(cognitive_env, thinking):
    for key, value in {
        "BASE_URL": "https://cognition.example/v1", "API_KEY": "private-token",
        "MODEL": "configured-model", "THINKING": thinking,
    }.items():
        cognitive_env.setenv("MEMORY_COGNITION_" + key, value)
    with pytest.raises(ValueError, match="MEMORY_COGNITION_THINKING") as error:
        Settings.from_env()
    rendered = "".join(traceback.format_exception(error.value))
    assert "private-token" not in rendered
    assert "private-invalid-value" not in rendered


@pytest.mark.parametrize("thinking", [True, 1, [], {}])
def test_direct_settings_reject_nonstring_thinking(thinking):
    with pytest.raises(ValueError, match="MEMORY_COGNITION_THINKING"):
        Settings(database_url="unused", cognition_base_url="https://cognition.example/v1",
                 cognition_api_key="token", cognition_model="model", cognition_thinking=thinking)


@pytest.mark.parametrize("missing", ["cognition_base_url", "cognition_api_key", "cognition_model"])
@pytest.mark.parametrize("empty", [None, "", "   "])
def test_thinking_cannot_enable_an_incomplete_provider(missing, empty):
    values = {
        "cognition_base_url": "https://cognition.example/v1",
        "cognition_api_key": "private-token", "cognition_model": "configured-model",
        "cognition_thinking": "disabled",
    }
    values[missing] = empty
    with pytest.raises(ValueError, match="MEMORY_COGNITION requires all of"):
        Settings(database_url="unused", **values)


@pytest.mark.parametrize("thinking", [None, "enabled", "disabled"])
def test_factory_uses_one_explicit_provider_for_proposal_and_verification_and_closes_it(monkeypatch, thinking):
    opened, closed = [], []
    monkeypatch.setattr(storage.Database, "check_compatibility", lambda *args, **kwargs: None)

    class Provider:
        def __init__(self, *args, **kwargs):
            opened.append((args, kwargs, self))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(self)

        def __call__(self, request):
            pytest.fail("Configuration must not make a model request")

    monkeypatch.setattr(semantic_provider, "ChatCompletionsSemanticProvider", Provider)
    monkeypatch.setattr(service, "MemoryService", lambda database, **kwargs: SimpleNamespace(database=database, **kwargs))
    settings = Settings(
        database_url="unused", cognition_base_url="https://cognition.example/v1",
        cognition_api_key="cognition-token", cognition_model="cognition-model",
        cognition_thinking=thinking,
    )
    with configured_service(settings) as configured:
        assert configured.semantic_processor.propose is configured.semantic_processor.verify is opened[0][2]
        assert configured.embedding_provider is None and len(opened) == 1
        assert opened[0][0] == (settings.cognition_base_url, "cognition-token", "cognition-model")
        assert opened[0][1] == {"thinking": thinking, "reasoning_effort": None, "max_response_bytes": 65536}
        assert closed == []
    assert closed == [opened[0][2]]


def test_default_factory_constructs_no_external_provider(monkeypatch):
    monkeypatch.setattr(storage.Database, "check_compatibility", lambda *args, **kwargs: None)
    def forbidden(*args, **kwargs):
        pytest.fail("Unconfigured provider must not be created")

    monkeypatch.setattr(semantic_provider, "ChatCompletionsSemanticProvider", forbidden)
    monkeypatch.setattr(local_embeddings, "LocalEmbeddingProvider", forbidden)
    monkeypatch.setattr(service, "MemoryService", lambda database, **kwargs: SimpleNamespace(**kwargs))
    with configured_service(Settings(database_url="unused")) as configured:
        assert configured.semantic_processor is None
        assert configured.embedding_provider is None


def test_api_and_worker_share_factory_lifetime(monkeypatch):
    lifetimes = []

    class Runner:
        def __init__(self, workers, configuration):
            assert workers == settings.recall_processes and configuration is settings

        def start(self):
            lifetimes.append("runner started")

        def close(self):
            lifetimes.append("runner closed")

        def respond(self, *args, **kwargs):
            pytest.fail("Health checks must not dispatch a recall transaction")

    @contextmanager
    def factory(settings):
        lifetimes.append("opened")
        try:
            yield SimpleNamespace(list_brains=lambda principal: [])
        finally:
            lifetimes.append("closed")

    monkeypatch.setattr(api, "configured_service", factory)
    monkeypatch.setattr(cli, "configured_service", factory)
    monkeypatch.setattr(cli.signal, "signal", lambda *args: None)
    monkeypatch.setattr(recall_service_executor, "RecallServiceExecutor", Runner)
    settings = Settings(database_url="unused", api_keys={
        hashlib.sha256(b"key").hexdigest(): Principal("tenant", "owner"),
    })
    with TestClient(api.create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert lifetimes == ["opened", "runner started"]
    cli.run_worker(settings, once=True)
    assert lifetimes == ["opened", "runner started", "runner closed", "closed", "opened", "closed"]
