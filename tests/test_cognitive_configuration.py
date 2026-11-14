import hashlib
import os
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
    service,
    storage,
)
from membrain.config import Settings, configured_service
from membrain.helpers import Principal


@pytest.fixture
def cognitive_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for key in ("BASE_URL", "API_KEY", "MODEL", "MODEL_VERSION", "DIMENSIONS"):
        monkeypatch.delenv("MEMORY_EMBEDDING_" + key, raising=False)
    for name in [name for name in os.environ if name.startswith("MEMORY_COGNITION_")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://unused")
    return monkeypatch


COGNITION = {"MEMORY_COGNITION_BASE_URL": "https://cognition.example/v1",
             "MEMORY_COGNITION_API_KEY": "private-cognition-token", "MEMORY_COGNITION_MODEL": "configured-model",
             "MEMORY_COGNITION_THINKING": "disabled", "MEMORY_COGNITION_REASONING_EFFORT": "private-effort",
             "MEMORY_COGNITION_MAX_WALL_TIME_MS": "not-a-number", "MEMORY_COGNITION_MAX_ENVELOPE_BYTES": "0"}


def test_model_backends_are_disabled_without_explicit_configuration(cognitive_env, caplog):
    with caplog.at_level("WARNING", logger="membrain.config"):
        settings = Settings.from_env()
    assert settings.embedding_local_directory is None
    assert "MEMORY_COGNITION" not in caplog.text


@pytest.mark.parametrize("names", [list(COGNITION), ["MEMORY_COGNITION_MODEL"], ["MEMORY_COGNITION_THINKING"],
                                   ["MEMORY_COGNITION_MAX_WALL_TIME_MS", "MEMORY_COGNITION_MAX_ENVELOPE_BYTES"]])
def test_settings_of_the_removed_cognition_model_are_ignored_with_a_warning(cognitive_env, caplog, names):
    """A deployment that configured a cognition model starts: its settings, complete, partial or malformed, are
    ignored with one warning that names them and never their values, and no setting of the model is kept."""
    for name in names:
        cognitive_env.setenv(name, COGNITION[name])
    with caplog.at_level("WARNING", logger="membrain.config"):
        settings = Settings.from_env()
    assert not any(name.startswith("cognition") or name == "semantic_policy" for name in dir(settings))
    warnings = [record.getMessage() for record in caplog.records if record.name == "membrain.config"]
    assert len(warnings) == 1 and all(name in warnings[0] for name in names)
    assert not any(COGNITION[name] in warnings[0] for name in names)
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


def test_default_factory_constructs_no_external_provider(cognitive_env, monkeypatch):
    monkeypatch.setattr(storage.Database, "check_compatibility", lambda *args, **kwargs: None)
    def forbidden(*args, **kwargs):
        pytest.fail("Unconfigured provider must not be created")

    monkeypatch.setattr(local_embeddings, "LocalEmbeddingProvider", forbidden)
    monkeypatch.setattr(service, "MemoryService", lambda database, **kwargs: SimpleNamespace(**kwargs))
    for name, value in COGNITION.items():
        cognitive_env.setenv(name, value)
    with configured_service(Settings.from_env()) as configured:
        assert vars(configured) == {"embedding_provider": None}


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
