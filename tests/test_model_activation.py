"""The local model activates inside the running service; finishing its download never interrupts requests (#29)."""
import hashlib
import os
import shutil
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from membrain import desktop, embedded_database, host, local_embeddings
from membrain.embeddings import EmbeddingSpace
from membrain.local_profile import ensure_profile, load_profile
from membrain.notes import NOTES_CONVERSATION
from membrain.service import MemoryService

MODEL = os.environ.get("MEMBRAIN_TEST_EMBEDDING_MODEL")
EARLIER = "We booked flights for my sister's wedding."


def _fake_files(monkeypatch):
    contents = {"onnx/model_quantized.onnx": b"model" * 10, "tokenizer.json": b"{}"}
    monkeypatch.setattr(local_embeddings, "FILES", {
        name: (hashlib.sha256(data).hexdigest(), len(data)) for name, data in contents.items()})
    return contents


def _install(contents, installation):
    for name, data in contents.items():
        target = local_embeddings.model_directory(installation) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def test_a_provider_that_is_not_ready_is_treated_as_absent(tmp_path, monkeypatch):
    contents = _fake_files(monkeypatch)
    provider = local_embeddings.LocalEmbeddingProvider(local_embeddings.model_directory(tmp_path))
    service = MemoryService(SimpleNamespace(), embedding_provider=provider)
    assert not provider.ready and service.embedding_provider is None
    with pytest.raises(local_embeddings.LocalEmbeddingError):
        provider.embed(["not installed yet"])
    _install({name: contents[name] for name in ["tokenizer.json"]}, tmp_path)
    assert service.embedding_provider is None  # A partly installed model is still not ready.
    _install(contents, tmp_path)
    assert provider.ready and service.embedding_provider is provider
    # Readiness only moves forward: a request that saw the provider never meets an absent one later.
    shutil.rmtree(local_embeddings.model_directory(tmp_path))
    assert service.embedding_provider is provider
    always = SimpleNamespace(space=EmbeddingSpace("remote", "1", 3))
    assert MemoryService(SimpleNamespace(), embedding_provider=always).embedding_provider is always


def test_query_embedding_spends_no_budget_before_the_model_is_ready(tmp_path, monkeypatch):
    from membrain.vector_jobs import query_embedding

    _fake_files(monkeypatch)
    provider = local_embeddings.LocalEmbeddingProvider(local_embeddings.model_directory(tmp_path))
    service = MemoryService(SimpleNamespace(), embedding_provider=provider)
    request = {"action": "recall", "payload": {"budget": {"max_embedding_calls": 1}}, "target": {"brain_ref": "b"}}
    # Returns before touching the database (a SimpleNamespace here) or the budget.
    assert query_embedding(service, None, request) == (None, None, 0)


def test_profile_configuration_is_the_same_before_and_after_the_download(tmp_path, monkeypatch):
    contents = _fake_files(monkeypatch)
    monkeypatch.setattr(local_embeddings, "runtime_available", lambda: True)
    profile = ensure_profile(tmp_path / "profile")
    before, fingerprint = profile.settings(), desktop._fingerprint(profile)
    assert before.embedding_local_directory == str(local_embeddings.model_directory(profile.directory))
    _install(contents, profile.directory)
    after = load_profile(profile.directory)
    # An existing profile (made before or after this change) gets the same value an installed model always had.
    assert after.settings().embedding_local_directory == before.embedding_local_directory == str(
        local_embeddings.installed(profile.directory))
    assert desktop._fingerprint(after) == fingerprint
    monkeypatch.setattr(local_embeddings, "runtime_available", lambda: False)
    assert load_profile(profile.directory).settings().embedding_local_directory is None


class Requests:
    """Runs rounds of reads, writes and session starts back to back in another thread, recording every failure.

    ``checkpoint`` returns only after a whole round that began after the call has finished, so each activation step
    wrapped with it is guaranteed to overlap real requests, whatever the machine's timing.
    """

    def __init__(self, directory, note):
        self.directory, self.note = directory, note
        self.failures, self.rounds = [], 0
        self.begun = self.finished = 0
        self.condition = threading.Condition()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def step(self, name, action, check=lambda value: True):
        try:
            value = action()
        except Exception as error:  # noqa: BLE001 - every failure is the finding
            self.failures.append((self.begun, name, f"{type(error).__name__}: {error}"[:300]))
            return
        if not check(value):
            self.failures.append((self.begun, name, "unexpected result: " + repr(value)[:300]))

    def run(self):
        client = host.ready_client(self.directory)
        try:
            while not self.stopped.is_set():
                with self.condition:
                    self.begun += 1
                    number = self.begun
                self.step("notes", lambda: client.timeline(roles=("assistant", "user"),
                                                           conversation_id=NOTES_CONVERSATION),
                          lambda value: any(self.note in item["text"] for item in value["items"]))
                self.step("timeline", lambda: client.timeline(), lambda value: value["items"])
                self.step("recall", lambda: host.recall(client, "sister wedding"),
                          lambda value: value["result"]["items"])
                self.step("mcp memory_recall", lambda: host.recall_context(client, "sister wedding"),
                          lambda value: value and "wedding" in value)
                self.step("message write", lambda: client.observe(**host.message_record(
                    "rounds", "user", f"Round {number} checked the memory service.", turn_id=str(number))))
                self.step("session start", lambda: host.session_context(self.directory, f"session-{number}"),
                          lambda value: self.note in value)
                with self.condition:
                    self.finished = number
                    self.condition.notify_all()
        finally:
            client.close()

    def checkpoint(self, timeout=120):
        with self.condition:
            mark = self.begun
            assert self.condition.wait_for(lambda: self.finished > mark, timeout), "request round did not finish"


@pytest.mark.skipif(not MODEL or not local_embeddings.runtime_available(),
                    reason="set MEMBRAIN_TEST_EMBEDDING_MODEL to an installation directory containing the model")
def test_model_activation_never_interrupts_requests_in_flight(tmp_path, monkeypatch):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    source = local_embeddings.installed(Path(MODEL))
    assert source is not None
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    directory = tmp_path / "installation"
    note = "My sister's wedding is in Lisbon in December."
    requests, stop = None, desktop.stop
    try:
        host.start(directory)
        assert host.semantic_state(directory) == "not_downloaded"
        instance = desktop.status(directory)["instance_id"]
        client = host.ready_client(directory)
        client.write_note(note)
        for number, text in enumerate([EARLIER,
                                       "Mi hermana se casa en diciembre."]):
            host.deliver(directory, client, host.message_record("before", "user", text, turn_id=str(number)))
        assert not _vector_ranked(client)  # Keyword recall only while the model is missing.

        # A session start with the service unavailable would launch a background start; count it as a failure.
        monkeypatch.setattr(host, "start_in_background", lambda directory: requests.failures.append(
            (requests.begun, "session start", "service unavailable")))
        requests = Requests(directory, note)
        requests.thread.start()
        requests.checkpoint()

        def install(installation):
            # The real download, minus the network: verified files appear one by one while requests run.
            target = local_embeddings.model_directory(installation)
            for name in local_embeddings.FILES:
                requests.checkpoint()
                (target / name).parent.mkdir(parents=True, exist_ok=True)
                partial = (target / name).with_name(Path(name).name + ".partial")
                shutil.copyfile(source / name, partial)
                os.replace(partial, target / name)
            requests.checkpoint()
            return target

        def overlapping(step):
            def run(*args, **kwargs):
                result = step(*args, **kwargs)
                requests.checkpoint()  # Every lifecycle step the activation takes is overlapped by requests.
                return result
            return run

        monkeypatch.setattr(local_embeddings, "download", install)
        for name in ("stop", "start", "restart"):
            monkeypatch.setattr(desktop, name, overlapping(getattr(desktop, name)))
        result = host.fetch_model(directory)
        requests.checkpoint()
        requests.checkpoint()
        requests.stopped.set()
        requests.thread.join(120)
        assert requests.failures == []
        assert result == {"semantic_recall": "ready", "service_restarted": False, "activated": True}
        status = desktop.status(directory)
        assert status["instance_id"] == instance and status["state"] == "ready"
        assert client._request("GET", "v1/local/memory-status")["semantic_recall"] == "ready"
        # Messages stored before activation are embedded in the background and found by meaning.
        deadline = time.monotonic() + 180
        while not any(EARLIER in statement for statement in _vector_ranked(client)):
            assert time.monotonic() < deadline, client.memory_status()
            threading.Event().wait(0.5)
        assert desktop.status(directory)["instance_id"] == instance
        client.close()
    finally:
        if requests is not None:
            requests.stopped.set()
        try:
            stop(directory)
        except desktop.DesktopError:
            pass


def _vector_ranked(client) -> set[str]:
    """Statements recalled through the embedding index for a query that shares no keyword with them."""
    response = client.recall("¿Cuándo es la boda?", budget=host.recall_budget())
    return {item["memory"]["statement"] for item in response["result"]["items"]
            if any(signal["method"] == "vector" for signal in item.get("rank_signals", ()))}
