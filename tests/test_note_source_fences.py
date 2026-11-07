import hashlib

import pytest
from psycopg.types.json import Jsonb
from test_note_workflow import brain as brain
from test_note_workflow import write
from test_timeline import Brain

from membrain.helpers import DomainError, Principal, uid
from membrain.note_sources import read_messages
from membrain.notes import store_note

pytestmark = pytest.mark.integration


def source(brain, text="My appointment is on Thursday."):
    key = uid()
    event_id = brain.say(text, source_key=key)
    return event_id, {"producer_ref": "timeline-test", "source_event_key": key, "source_revision": 1}


def read(brain, references):
    return read_messages(brain.service, brain.principal, brain.brain, references)


def test_exact_source_reads_are_scoped_and_do_not_include_notes(brain):
    event_id, ref = source(brain)
    assert read(brain, [ref])["items"] == [{"reference": ref, "event_id": event_id,
                                          "actor_role": "user", "text": "My appointment is on Thursday."}]
    other = Brain(brain.service, brain.principal)
    assert read(other, [ref])["items"] == []
    foreign = Principal(uid(), uid())
    with pytest.raises(DomainError):
        read_messages(brain.service, foreign, brain.brain, [ref])
    note = write(brain, "A note cannot pose as an original message.")
    with brain.service.database.transaction(brain.principal) as conn:
        metadata = brain.service._brain(conn, brain.principal, brain.brain)
        document = brain.service._events(conn, brain.principal, metadata,
                                         event_ids=[note["note_id"]])[0]
    observed = document["observed"]
    note_ref = {name: observed[name] for name in ("producer_ref", "source_event_key", "source_revision")}
    assert read(brain, [note_ref])["items"] == []


@pytest.mark.parametrize("damage", ["deleted", "suppressed", "retired", "superseded", "draft", "cancelled"])
def test_strict_note_sources_are_rechecked_before_any_replacement(brain, damage):
    event_id, ref = source(brain)
    kept = write(brain, "Keep the original note.")["note_id"]
    generation = read(brain, [ref])["dependency_generation"]
    with brain.service.database.transaction(brain.principal) as conn:
        params = (brain.principal.tenant_id, brain.principal.principal_id, brain.brain, event_id)
        if damage in ("draft", "cancelled"):
            conn.execute("UPDATE memory_events SET document=jsonb_set(document,'{observed,delivery_state}',%s) "
                         "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s", (Jsonb(damage), *params))
        else:
            assignment = "is_current=false" if damage == "superseded" else f"{damage}=true"
            conn.execute("UPDATE memory_events SET " + assignment
                         + " WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s", params)
    assert read(brain, [ref])["items"] == []
    with pytest.raises(DomainError) as error:
        write(brain, "Stale replacement.", replaces=[kept], source_messages=[ref],
              require_current_sources=True, expected_dependency_generation=generation)
    assert error.value.code == "source_unavailable"
    assert [item["event_id"] for item in brain.timeline(roles=("assistant",))["items"]] == [kept]


def test_strict_sources_preserve_pending_reference_support_for_ordinary_notes(brain):
    key = uid()
    ref = {"producer_ref": "timeline-test", "source_event_key": key, "source_revision": 1}
    with pytest.raises(DomainError) as error:
        write(brain, "Not yet supported.", source_messages=[ref], require_current_sources=True)
    assert error.value.code == "source_unavailable"
    pending = write(brain, "A host note can precede the current message.", source_messages=[ref])
    assert pending["pending_source_count"] == 1
    event_id = brain.say("The current message arrives.", source_key=key)
    assert brain.timeline(roles=("assistant",))["items"][0]["source_event_ids"] == [event_id]


def test_new_source_guard_defaults_keep_existing_note_idempotency(brain):
    arguments = {"request_id": uid(), "text": "The existing request."}
    initial = store_note(brain.service, brain.principal, brain.brain, arguments)
    replay = store_note(brain.service, brain.principal, brain.brain,
                        {**arguments, "context_source_messages": [], "require_current_sources": False,
                         "expected_dependency_generation": None})
    assert replay == initial


@pytest.mark.parametrize("references", [[], [{}], [{"producer_ref": "p", "source_event_key": "k", "source_revision": True}],
                                      [{"producer_ref": "p", "source_event_key": "k", "source_revision": 1}] * 65])
def test_exact_source_reads_reject_unbounded_or_malformed_references(brain, references):
    with pytest.raises(DomainError) as error:
        read(brain, references)
    assert error.value.code == "validation_failed"


def test_source_http_reads_require_authentication_and_strict_bounded_inputs(brain):
    from fastapi.testclient import TestClient

    from membrain.api import create_app
    from membrain.config import Settings

    event_id, ref = source(brain)
    settings = Settings(database_url=brain.service.database.dsn,
                        api_keys={hashlib.sha256(b"local-test").hexdigest(): brain.principal})
    with TestClient(create_app(settings, service=brain.service)) as client:
        url = f"/v1/brains/{brain.brain}/source-messages"
        headers = {"Authorization": "Bearer local-test"}
        assert client.post(url, json={"messages": [ref]}).status_code == 401
        valid = client.post(url, json={"messages": [ref]}, headers=headers)
        assert valid.status_code == 200
        assert valid.json()["items"][0]["event_id"] == event_id
        for messages in ([], [ref] * 65, [{**ref, "source_revision": True}], [{**ref, "foreign": True}]):
            assert client.post(url, json={"messages": messages}, headers=headers).status_code == 422
        notes_url = f"/v1/brains/{brain.brain}/notes"
        for fields in ({"require_current_sources": "true"}, {"expected_dependency_generation": True},
                       {"expected_dependency_generation": -1}, {"context_source_messages": [ref]}):
            body = {"request_id": uid(), "text": "Invalid guarded write.", **fields}
            assert client.post(notes_url, json=body, headers=headers).status_code == 422
