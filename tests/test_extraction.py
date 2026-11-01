import json

import httpx
import pytest

from membrain import desktop, embedded_database, host
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.extraction import MAX_NOTES, PRODUCER, Extractor, worth_reading


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def model(notes, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"notes": notes})}}]})
    return Extractor("https://api.example/v1", "cheap-model", "sk-test", transport=httpx.MockTransport(handler))


def test_proposals_are_checked_before_they_become_notes():
    seen = []
    extractor = model([
        {"text": "Mei is the user's younger sister; allergic to sesame.", "kind": "person", "about": "Mei",
         "aliases": ["Meimei"], "status": "done", "replaces": []},
        {"text": "Fly to Lisbon on 2026-12-03 for Tomas's wedding.", "kind": "plan", "status": "intended",
         "due": "2026-12-03", "replaces": ["n1", 7]},
        {"text": "Likes tea.", "kind": "hobby"},
        {"text": "  "},
        *({"text": f"fact {index}"} for index in range(10)),
    ], seen)
    notes = extractor.propose("My sister Mei can't eat sesame, and I fly to Lisbon on 3 December.", "Noted!",
                              "- Earlier note (id: n1)")
    assert len(notes) <= MAX_NOTES
    person, plan, tea = notes[:3]
    assert person == {"text": "Mei is the user's younger sister; allergic to sesame.", "replaces": [], "kind": "person",
                      "about": "Mei", "aliases": ["Meimei"]}  # A status is only for plans and promises.
    assert plan["status"] == "intended" and plan["due"] == "2026-12-03" and plan["replaces"] == ["n1"]
    assert tea == {"text": "Likes tea.", "replaces": []}  # An unknown kind is dropped, the note is kept.
    request = seen[0]
    assert request["model"] == "cheap-model" and request["response_format"] == {"type": "json_object"}
    assert "- Earlier note (id: n1)" in request["messages"][1]["content"]


def test_greetings_are_not_sent_for_extraction():
    assert not worth_reading("hi!") and not worth_reading("你好呀") and not worth_reading("ok thanks")
    assert worth_reading("My sister Mei is allergic to sesame") and worth_reading("我妹妹对芝麻过敏")


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_a_bot_without_tools_gets_notes_from_extraction(tmp_path):
    directory = tmp_path / "brain"
    seen = []
    extractor = model([{"text": "Allergic to sesame; carries an EpiPen.", "kind": "constraint", "sensitive": True}],
                      seen)
    memory = ChatMemory(directory, producer="membrain-proxy", tools=None, extractor=extractor)
    alice, bob = Speaker("api", "alice"), Speaker("api", "bob")
    try:
        host.start(directory)
        memory.context(alice, "I'm allergic to sesame and always carry an EpiPen.", session="a1", turn_id="t1")
        memory.record(alice, "Thanks, I'll keep that in mind.", session="a1", turn_id="t1",
                      prompt="I'm allergic to sesame and always carry an EpiPen.")
        memory.record(bob, "Hi!", session="b1", turn_id="t1", prompt="hi")  # Too short to read.
        memory.pause(bob)
        memory.record(bob, "Sure.", session="b1", turn_id="t2", prompt="Off the record: I am allergic to cats.")
        extractor.wait()
        later = memory.context(alice, "What should I order tonight?", session="a2", turn_id="t1")
        assert "Allergic to sesame; carries an EpiPen." in later and "sensitive" in later
        assert "membrain-source" not in later  # Without a note tool there is nothing to pass a source to.
        with host.ready_client(directory, memory.user_id(bob)) as client:
            from membrain.notes import list_notes

            assert list_notes(client)["items"] == []
        with host.ready_client(directory, memory.user_id(alice)) as client:
            items = list_notes(client)["items"]
            assert {item.get("producer") for item in items} == {PRODUCER}
            # The note is linked to the turn it came from: the person's message and the reply.
            assert len(items[0]["source_event_ids"]) == 2 and items[0]["pending_source_count"] == 0
        assert len(seen) == 1

        # Paused while the reply was being written and resumed before it was recorded: the turn is not
        # recorded, so it is not read either.
        memory.context(alice, "Off the record: my brother Sam owes money to a loan shark.", session="a3",
                       turn_id="t1")
        memory.pause(alice)
        memory.resume(alice)
        memory.record(alice, "I won't keep that.", session="a3", turn_id="t1",
                      prompt="Off the record: my brother Sam owes money to a loan shark.")
        extractor.wait()
        assert len(seen) == 1

        # Forgetting the message the note came from forgets the note.
        with host.ready_client(directory, memory.user_id(alice)) as client:
            generation = client.dashboard()["brain"]["scope_generation"]
            client.forget(items[0]["source_event_ids"], kind="events", mode="erase_content",
                          expected_scope_generation=generation)
            assert list_notes(client)["items"] == []
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
