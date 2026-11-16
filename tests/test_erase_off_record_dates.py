"""Erasing everything also removes the person's off-the-record dates (evaluations/offrecord-dates-and-one-reply-2026-11-16.md).

The memory page's "Erase everything", and the same ``forget`` through the API, reach the installation's own local
service; once the erasure has completed, that service removes the brain's dates file from the installation. The
first tests need no service or database; the last group runs against a real local installation (``host.start``).
"""
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from membrain import api, desktop, host
from membrain.config import Settings
from membrain.desktop_connection import open_client
from membrain.helpers import Principal
from membrain.local_profile import load_profile

OWN = "3f0e1c55-0b6a-4d6c-9f0e-8f5a2b8c1d00"


def _dates(directory, user_id=None, day="2026-09-12"):
    host._write_state(host._off_record_file(directory, user_id), {"dates": [day]})
    return host._off_record_file(directory, user_id, create=False)


def _installation(tmp_path):
    (tmp_path / "profile.json").write_text(json.dumps({"brain_id": OWN}), encoding="utf-8")
    return tmp_path


# The removal itself ------------------------------------------------------------------------------------------------

def test_the_installations_own_brain_removes_its_own_file_only(tmp_path):
    directory = _installation(tmp_path)
    own, alice = _dates(directory), _dates(directory, "alice")
    assert host.erase_off_record_dates(directory, OWN) is True
    assert not own.exists() and alice.exists()


def test_a_users_brain_removes_only_that_users_file(tmp_path):
    directory = _installation(tmp_path)
    own, alice, bob = _dates(directory), _dates(directory, "alice"), _dates(directory, "bob")
    assert alice.name == host.user_brain_id("alice") + ".json"  # The per-user file is named by the brain id.
    assert host.erase_off_record_dates(directory, host.user_brain_id("alice")) is True
    assert not alice.exists() and own.exists() and bob.exists()


@pytest.mark.parametrize("brain", [
    "another-brain", host.user_brain_id(host.roleplay_user("alice", "Captain")),
    host.user_brain_id(host.roleplay_user(None, "Captain")), "../off-record", "user-../../profile", "", None])
def test_any_other_brain_removes_nothing(tmp_path, brain):
    # A role-play's dates are its person's: erasing the role-play's memory leaves them.
    directory = _installation(tmp_path)
    own, alice = _dates(directory), _dates(directory, "alice")
    assert host.erase_off_record_dates(directory, brain) is False
    assert own.exists() and alice.exists() and (directory / "profile.json").exists()


def test_a_missing_file_or_state_folder_is_fine_and_nothing_is_created(tmp_path):
    directory = _installation(tmp_path)
    assert host.erase_off_record_dates(directory, OWN) is False
    assert not (directory / "plugin").exists()
    host.state_directory(directory)
    assert host.erase_off_record_dates(directory, host.user_brain_id("alice")) is False
    assert sorted(path.name for path in (directory / "plugin").iterdir()) == []


def test_an_unreadable_profile_removes_nothing_of_the_owners(tmp_path):
    own = _dates(tmp_path)
    assert host.erase_off_record_dates(tmp_path, OWN) is False  # No profile.json.
    (tmp_path / "profile.json").write_text("not json", encoding="utf-8")
    assert host.erase_off_record_dates(tmp_path, OWN) is False and own.exists()


def test_a_held_lock_never_raises(tmp_path, monkeypatch):
    directory = _installation(tmp_path)
    own = _dates(directory)

    def busy(*args, **kwargs):
        raise TimeoutError("held")

    monkeypatch.setattr(host, "profile_lock", busy)
    assert host.erase_off_record_dates(directory, OWN) is False and own.exists()
    assert "off-record dates not erased: TimeoutError" in (directory / "plugin" / "hooks.log").read_text()


# Which completed actions reach it ----------------------------------------------------------------------------------

def _forget(kind="all_authorized_scope", mode="erase_content", brain=OWN):
    return {"message_type": "request", "contract_version": "1.0.0-draft", "request_id": str(uuid4()),
            "action": "forget", "target": {"brain_ref": brain, "conversation_ref": "membrain-memory-page",
                                           "branch_ref": "main"},
            "payload": {"idempotency_key": str(uuid4()), "selector": {"kind": kind, "ids": []}, "mode": mode,
                        "expected_scope_generation": 0}}


def _supervisor(directory):
    return SimpleNamespace(profile=SimpleNamespace(directory=directory, brain_id=OWN, tenant_id="tenant",
                                                   principal_id="owner"))


PRINCIPAL = Principal("tenant", "owner")


def _completed(brain=OWN, outcome="completed"):
    return {"outcome": outcome, "server_scope": {"brain_id": brain}}


@pytest.mark.parametrize("request_, response", [
    (_forget(kind="events"), _completed()),
    (_forget(kind="conversation"), _completed()),
    (_forget(mode="suppress_recall"), _completed()),
    ({**_forget(), "action": "observe"}, _completed()),
    (_forget(), _completed(outcome="conflict")),
    (_forget(), _completed(outcome="rejected")),
    (_forget(), _completed(outcome="failed")),
    (_forget(), {"outcome": "completed"}),
])
def test_only_a_completed_erasure_of_everything_removes_the_dates(tmp_path, request_, response):
    directory = _installation(tmp_path)
    own = _dates(directory)
    desktop.LocalSupervisor.after_action(_supervisor(directory), PRINCIPAL, request_, response)
    assert own.exists()
    desktop.LocalSupervisor.after_action(_supervisor(directory), PRINCIPAL, _forget(), _completed())
    assert not own.exists()


def test_another_principal_of_the_service_removes_nothing(tmp_path):
    directory = _installation(tmp_path)
    own = _dates(directory)
    desktop.LocalSupervisor.after_action(_supervisor(directory), Principal("tenant", "someone-else"),
                                         _forget(), _completed())
    assert own.exists()


class _Service:
    def __init__(self, outcome):
        self.outcome = outcome

    def handle(self, principal, request):
        return {"message_type": "response", "request_id": request["request_id"], "action": request["action"],
                "outcome": self.outcome}


@pytest.fixture
def without_schema(monkeypatch):
    monkeypatch.setattr(api, "validate", lambda *args: None)


def _app(service, after_action):
    settings = Settings(database_url="unused", api_keys={
        hashlib.sha256(b"test-only-key").hexdigest(): PRINCIPAL})
    return TestClient(api.create_app(settings, service, after_action=after_action))


def test_the_action_route_calls_the_hook_only_for_a_completed_action(without_schema):
    calls = []
    for outcome in ("conflict", "rejected", "failed", "completed"):
        with _app(_Service(outcome), lambda *arguments: calls.append(arguments)) as client:
            response = client.post("/v1/actions", headers={"Authorization": "Bearer test-only-key"}, json=_forget())
            assert response.json()["outcome"] == outcome
    assert [(principal, request["action"], response["outcome"]) for principal, request, response in calls] == [
        (PRINCIPAL, "forget", "completed")]


def test_a_failing_hook_never_changes_the_completed_response(without_schema):
    def broken(*arguments):
        raise RuntimeError("bookkeeping failed")

    with _app(_Service("completed"), broken) as client:
        response = client.post("/v1/actions", headers={"Authorization": "Bearer test-only-key"}, json=_forget())
    assert response.status_code == 200 and response.json()["outcome"] == "completed"


def test_a_service_without_an_installation_has_no_hook(without_schema):
    # A deployment that is not an installation's own (create_app without after_action) does nothing extra.
    with _app(_Service("completed"), None) as client:
        response = client.post("/v1/actions", headers={"Authorization": "Bearer test-only-key"}, json=_forget())
    assert response.json()["outcome"] == "completed"


# Through the real local app ---------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    import os

    directory = tmp_path_factory.mktemp("erase-off-record")
    previous = os.environ.get("MEMBRAIN_SEMANTIC")
    os.environ["MEMBRAIN_SEMANTIC"] = "0"
    try:
        host.start(directory)
        yield load_profile(directory)
    finally:
        desktop.stop(directory)
        if previous is None:
            os.environ.pop("MEMBRAIN_SEMANTIC", None)
        else:
            os.environ["MEMBRAIN_SEMANTIC"] = previous


@pytest.fixture
def connected(installation):
    host.resume(installation.directory)
    with open_client(installation.directory, start_service=False) as client:
        yield client


def _generation(client, brain):
    return client.dashboard(brain)["brain"]["scope_generation"]


def _page_forget(client, brain, kind="all_authorized_scope", ids=(), mode="erase_content", generation=None):
    """The request the memory page sends (memory.js: ``action`` and ``forget``)."""
    body = {"message_type": "request", "contract_version": "1.0.0-draft", "request_id": str(uuid4()),
            "action": "forget", "target": {"brain_ref": brain, "conversation_ref": "membrain-memory-page",
                                           "branch_ref": "main"},
            "payload": {"idempotency_key": str(uuid4()), "selector": {"kind": kind, "ids": list(ids)},
                        "mode": mode, "expected_scope_generation": (
                            _generation(client, brain) if generation is None else generation)}}
    return client._http.post("/v1/actions", json=body).raise_for_status().json()


def _user_brain(client, user_id):
    brain = host.user_brain_id(user_id)
    client.ensure_brain(brain, "user " + user_id)
    return brain


def _observe(client, brain, text="A public fixture message."):
    home = client.brain_id
    client.brain_id = brain
    try:
        return client.observe(text, conversation_id="fixture-" + uuid4().hex, branch_id="main",
                              source_event_key=str(uuid4()))["result"]["accepted_event_ids"]
    finally:
        client.brain_id = home


def test_a_users_erase_everything_removes_only_that_users_dates(connected, installation):
    directory = installation.directory
    alice, bob = "alice-" + uuid4().hex, "bob-" + uuid4().hex
    brain = _user_brain(connected, alice)
    _user_brain(connected, bob)
    _observe(connected, brain)
    alice_file, bob_file, own = _dates(directory, alice), _dates(directory, bob), _dates(directory)
    assert alice_file.name == brain + ".json"
    response = _page_forget(connected, brain)
    assert response["outcome"] == "completed" and response["server_scope"]["brain_id"] == brain
    assert not alice_file.exists() and bob_file.exists() and own.exists()
    own.unlink()
    bob_file.unlink()


def test_a_users_dates_are_found_by_the_users_brain_id(connected, installation):
    directory = installation.directory
    person = "carol-" + uuid4().hex
    brain = _user_brain(connected, person)
    path = _dates(directory, person)
    assert host.off_record_dates(directory, person) == ["2026-09-12"]
    assert _page_forget(connected, brain)["outcome"] == "completed"
    assert not path.exists() and host.off_record_dates(directory, person) == []


def test_other_forgets_leave_the_dates(connected, installation):
    directory = installation.directory
    person = "dana-" + uuid4().hex
    brain = _user_brain(connected, person)
    path = _dates(directory, person)
    first, second = _observe(connected, brain, "One public message."), _observe(connected, brain, "Another.")
    assert _page_forget(connected, brain, "events", first)["outcome"] == "completed"
    assert _page_forget(connected, brain, "events", second, mode="suppress_recall")["outcome"] == "completed"
    assert _page_forget(connected, brain, mode="suppress_recall")["outcome"] == "completed"
    assert path.exists() and host.off_record_dates(directory, person) == ["2026-09-12"]
    path.unlink()


def test_a_failed_erasure_leaves_the_dates(connected, installation):
    directory = installation.directory
    person = "erin-" + uuid4().hex
    brain = _user_brain(connected, person)
    first, _ = _observe(connected, brain, "One public message."), _observe(connected, brain, "Another.")
    path = _dates(directory, person)
    stale = _generation(connected, brain)  # The page read it, then another erasure moved it on.
    assert _page_forget(connected, brain, "events", first)["outcome"] == "completed"
    response = _page_forget(connected, brain, generation=stale)
    assert response["outcome"] == "conflict" and response["error"]["code"] == "version_conflict"
    assert path.exists()
    path.unlink()


def test_an_erasure_with_no_dates_is_fine_and_creates_none(connected, installation):
    directory = installation.directory
    person = "frank-" + uuid4().hex
    brain = _user_brain(connected, person)
    _observe(connected, brain)
    assert _page_forget(connected, brain)["outcome"] == "completed"
    assert not (directory / "plugin" / "off-record-users" / (brain + ".json")).exists()


def test_a_date_recorded_after_the_erasure_is_kept(connected, installation):
    directory = installation.directory
    person = "gina-" + uuid4().hex
    brain = _user_brain(connected, person)
    path = _dates(directory, person, day="2026-09-01")
    assert _page_forget(connected, brain)["outcome"] == "completed" and not path.exists()
    host._note_off_record(directory, person)  # A later off-the-record turn.
    later = host.off_record_dates(directory, person)
    assert len(later) == 1 and path.exists()
    event = _observe(connected, brain)
    assert _page_forget(connected, brain, "events", event)["outcome"] == "completed"
    assert host.off_record_dates(directory, person) == later
    path.unlink()


def test_the_pages_erase_everything_removes_the_owners_dates(connected, installation):
    # Last in this module: it erases the installation's own memory.
    directory = installation.directory
    own = _dates(directory)
    other = _dates(directory, "harry-" + uuid4().hex)
    assert host.off_record_dates(directory) == ["2026-09-12"]
    response = _page_forget(connected, installation.brain_id)
    assert response["outcome"] == "completed" and response["server_scope"]["brain_id"] == installation.brain_id
    assert not own.exists() and other.exists() and host.off_record_dates(directory) == []
    assert "off the record" not in host.session_context(directory, "after-erase").lower()
    other.unlink()
