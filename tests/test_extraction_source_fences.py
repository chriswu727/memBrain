import json
from types import SimpleNamespace

import httpx
import pytest

from membrain import desktop, host
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.extraction import Extractor, extraction_status
from membrain.notes import list_notes


@pytest.fixture
def chat(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    directory = tmp_path / "brain"
    state = SimpleNamespace(seen=[], pending=[], response=lambda body: [])

    def handle(request):
        body = json.loads(request.content)
        state.seen.append(body)
        notes = state.response(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"notes": notes})}}]})

    extractor = Extractor("https://model.example/v1", "local-test", transport=httpx.MockTransport(handle))
    extractor.retry_delays = (0,)
    monkeypatch.setattr(extractor, "submit", lambda task: state.pending.append(task) or True)
    memory = ChatMemory(directory, producer="membrain-proxy", tools=None, extractor=extractor)
    person = Speaker("api", "test-person")
    host.start(directory)
    client = host.ready_client(directory, memory.user_id(person))
    state.directory, state.memory, state.person, state.client = directory, memory, person, client

    def record(text, turn):
        memory.record(person, "Noted.", session="conversation", turn_id=turn, prompt=text)
        return [item["event_id"] for item in client.timeline(roles=("user", "assistant"),
                                                           conversation_id="conversation")["items"][:2]]

    def erase(ids):
        client.forget(ids, kind="events", mode="erase_content",
                      expected_scope_generation=client.dashboard()["brain"]["scope_generation"])

    state.record, state.erase = record, erase
    state.run = lambda: state.pending.pop(0)()
    state.notes = lambda: list_notes(client)["items"]
    try:
        yield state
    finally:
        client.close()
        extractor._http.close()
        desktop.stop(directory)


def content(body):
    return body["messages"][1]["content"]


def test_previous_context_is_live_and_its_deletion_removes_derived_notes(chat):
    previous = chat.record("My visit to the planetarium is on Thursday.", "first")
    chat.run()
    current = chat.record("Move it to Friday.", "second")
    chat.response = lambda body: [{"text": "The planetarium visit moved to Friday.", "kind": "plan"}]
    chat.run()
    assert "My visit to the planetarium is on Thursday." in content(chat.seen[-1])
    assert set(chat.notes()[0]["source_event_ids"]) == set(previous + current)
    assert "planetarium" not in repr(chat.memory._previous)
    chat.erase(previous[:1])
    assert chat.notes() == []


def test_erased_queued_turn_never_reaches_the_provider(chat):
    sources = chat.record("private-queued-source-471 is my allergy.", "first")
    chat.erase(sources)
    chat.run()
    assert chat.seen == [] and chat.notes() == []
    assert "private-queued-source-471" not in repr(chat.memory._previous)
    assert extraction_status(chat.directory)["last_error"] == "source_unavailable"


def test_recording_pause_during_provider_call_prevents_note_save(chat):
    chat.record("Please remember my Thursday appointment.", "first")

    def respond(body):
        host.pause(chat.directory, user_id=chat.memory.user_id(chat.person))
        return [{"text": "Thursday appointment."}]

    chat.response = respond
    chat.run()
    assert chat.notes() == []
    assert extraction_status(chat.directory)["last_error"] == "recording_paused"


@pytest.mark.parametrize("erase_current", [True, False])
def test_retry_rereads_message_and_note_context_after_erasure(chat, erase_current):
    previous = chat.record("private-previous-source-472 is my allergy.", "first")
    chat.run()
    current = chat.record("Please remember the updated plan.", "second")
    doomed = current if erase_current else previous
    chat.client.write_note("private-note-context-473", source_event_ids=doomed)
    chat.seen.clear()

    def respond(body):
        if len(chat.seen) == 1:
            assert "private-note-context-473" in content(body)
            chat.erase(doomed)
            raise httpx.ConnectError("retry the synthetic provider")
        return []

    chat.response = respond
    chat.run()
    assert len(chat.seen) == (1 if erase_current else 2)
    if not erase_current:
        assert "Previous exchange" not in content(chat.seen[-1])
        assert "private-previous-source-472" not in content(chat.seen[-1])
        assert "private-note-context-473" not in content(chat.seen[-1])
    assert chat.notes() == []


@pytest.mark.parametrize("change", ["erase_current", "erase_previous", "correct_current", "erase_other_note"])
def test_provider_time_changes_cannot_write_or_replace_notes(chat, change):
    previous = chat.record("The earlier appointment is Thursday.", "first")
    chat.run()
    current = chat.record("The current appointment is Friday.", "second")
    kept = chat.client.write_note("Keep this existing note.")["note_id"]
    other = chat.client.write_note("Another existing context note.")["note_id"]

    def respond(body):
        if change == "correct_current":
            chat.client.observe("The corrected appointment is Saturday.", conversation_id="conversation",
                                branch_id="main", source_event_key="conversation:second:user", source_revision=2,
                                producer_ref="membrain-proxy")
        else:
            chat.erase({"erase_current": current, "erase_previous": previous, "erase_other_note": [other]}[change])
        return [{"text": "Stale proposed replacement.", "replaces": [kept]}]

    chat.response = respond
    chat.run()
    assert kept in {note["event_id"] for note in chat.notes()}
    assert "Stale proposed replacement" not in json.dumps(chat.notes())
    assert extraction_status(chat.directory)["last_error"] == "source_context_changed"


def test_one_extraction_can_replace_multiple_notes_without_invalidating_its_own_fence(chat):
    first = chat.client.write_note("First old note.")["note_id"]
    second = chat.client.write_note("Second old note.")["note_id"]
    chat.record("Update both appointment notes.", "first")
    chat.response = lambda body: [
        {"text": "First updated note.", "replaces": [first]},
        {"text": "Second updated note.", "replaces": [second]},
    ]
    chat.run()
    notes = chat.notes()
    assert len(notes) == 2
    assert {first, second}.isdisjoint(note["event_id"] for note in notes)
    assert extraction_status(chat.directory)["state"] == "ok"


def test_previous_context_does_not_make_a_new_feeling_precede_the_clear_marker(chat):
    chat.record("The interview is on Friday.", "first")
    chat.run()
    chat.client.clear_affect()
    current = chat.record("I am nervous about the interview.", "second")
    chat.response = lambda body: [{"text": "The interview is on Friday.", "kind": "plan",
                                  "affect": {"label": "nervous", "valence": -1, "intensity": 2,
                                             "basis": "reported"}}]
    chat.run()
    readings = chat.client.affect_records()["records"]
    assert len(readings) == 1 and readings[0]["label"] == "nervous"
    assert set(readings[0]["source_event_ids"]) == set(current)
