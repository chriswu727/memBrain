"""The local embedding model is loaded when the service starts, not by the first recall."""
import os
from pathlib import Path

import pytest

from membrain.local_embeddings import LocalEmbeddingProvider, installed


def test_warming_up_a_model_that_is_not_installed_does_nothing(tmp_path):
    provider = LocalEmbeddingProvider(tmp_path / "no-model")
    assert provider.warm_up() is False and provider._session is None


def test_warming_up_loads_the_installed_model():
    cache = os.environ.get("MEMBRAIN_TEST_EMBEDDING_MODEL")
    if not cache or not installed(Path(cache)):
        pytest.skip("Set MEMBRAIN_TEST_EMBEDDING_MODEL to a directory holding the pinned embedding model")
    provider = LocalEmbeddingProvider(installed(Path(cache)), threads=1)
    assert provider._session is None
    assert provider.warm_up() is True and provider._session is not None


def test_the_service_starts_warming_up_without_waiting_for_it():
    import threading

    from fastapi.testclient import TestClient

    from membrain.api import create_app
    from membrain.config import Settings

    started, release = threading.Event(), threading.Event()

    class Provider:
        def warm_up(self):
            started.set()
            release.wait(5)

    class Service:
        _embedding_provider = Provider()

    with TestClient(create_app(Settings(database_url="postgresql://unused"), service=Service())):
        assert started.wait(5)  # Running, and the app came up while it was still blocked.
    release.set()
