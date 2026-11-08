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


def test_greetings_are_not_sent_for_extraction_but_short_updates_are():
    for text in ("hi!", "你好呀", "ok thanks", "Thanks so much!!", "谢谢！", "哈哈哈", "😂😂", "good night", "  "):
        assert not worth_reading(text), text
    for text in ("My sister Mei is allergic to sesame", "我妹妹对芝麻过敏", "我不吃花生", "已取消", "改到周五",
                 "I am vegan", "cancelled it", "moved to Friday", "she said no", "好的", "ok"):
        assert worth_reading(text), text


def test_a_short_reply_is_read_with_the_exchange_it_answers():
    seen = []
    model([], seen).propose("已取消", "好的，周四的牙医预约取消了。", "(none)",
                            previous=("周四下午三点的牙医还去吗？", "要我提醒你周四下午三点去看牙医吗？"))
    content = seen[0]["messages"][1]["content"]
    assert "Previous exchange" in content and "周四下午三点的牙医还去吗？" in content
    assert content.index("Previous exchange") < content.index("Latest exchange:\nPerson: 已取消")


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

        # An externally erased exchange must not be sent to the provider again.
        memory.context(alice, "actually it's peanuts, not sesame", session="a1", turn_id="t2")
        memory.record(alice, "Got it, peanuts.", session="a1", turn_id="t2", prompt="actually it's peanuts, not sesame")
        extractor.wait()
        assert len(seen) == 2
        content = seen[1]["messages"][1]["content"]
        assert "Previous exchange" not in content
        assert "always carry an EpiPen" not in content
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_failed_and_skipped_turns_show_as_degraded_until_extraction_works_again(tmp_path):
    from membrain import diagnostics
    from membrain.extraction import extraction_status, record_outcome

    assert extraction_status(tmp_path) is None
    record_outcome(tmp_path, saved=2)
    assert extraction_status(tmp_path)["state"] == "ok"
    unavailable = httpx.HTTPStatusError("busy", request=httpx.Request("POST", "https://api.example/v1"),
                                        response=httpx.Response(503))
    record_outcome(tmp_path, error=unavailable)
    record_outcome(tmp_path, skipped=True)
    status = extraction_status(tmp_path)
    assert status["state"] == "degraded" and status["failed_since_success"] == 2
    assert status["last_error"] == "queue full" and status["turns_failed"] == 1 and status["turns_skipped"] == 1
    check = next(item for item in diagnostics.diagnose(tmp_path)["checks"] if item["name"] == "note_extraction")
    assert check["state"] == "warning" and "still recorded and recalled" in check["detail"]
    record_outcome(tmp_path, saved=0)
    status = extraction_status(tmp_path)
    assert status["state"] == "ok" and status["turns_read"] == 2 and status["notes_saved"] == 2


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_a_provider_that_fails_for_now_is_retried_and_one_that_refuses_is_reported(tmp_path):
    from membrain.extraction import extraction_status

    calls = []

    def flaky(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) <= 2:
            raise httpx.ConnectError("connection reset", request=request)
        if len(calls) == 3:
            note = {"text": "Moved to Wellington in May.", "kind": "milestone"}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"notes": [note]})}}]})
        return httpx.Response(401, json={"error": "invalid key"})

    extractor = Extractor("https://api.example/v1", "cheap-model", "sk-test", transport=httpx.MockTransport(flaky))
    extractor.retry_delays = (0, 0)
    directory = tmp_path / "brain"
    memory = ChatMemory(directory, producer="membrain-proxy", tools=None, extractor=extractor)
    person = Speaker("api", "rua")
    try:
        host.start(directory)
        memory.context(person, "I moved to Wellington in May.", session="w1", turn_id="t1")
        memory.record(person, "Welcome to Wellington!", session="w1", turn_id="t1", prompt="I moved to Wellington in May.")
        extractor.wait()
        assert len(calls) == 3 and extraction_status(directory)["state"] == "ok"
        assert "Moved to Wellington in May." in memory.context(person, "Where do I live now, remind me?", session="w2", turn_id="t1")
        memory.record(person, "In Wellington.", session="w2", turn_id="t1", prompt="Where do I live now, remind me?")
        extractor.wait()
        status = host.installation_status(directory)["note_extraction"]
        assert len(calls) == 4  # Refused for good: not retried.
        assert status["state"] == "degraded" and status["last_error"] == "HTTP 401"
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_extraction_saves_only_what_the_person_said():
    from membrain.extraction import INSTRUCTIONS

    assert "Save only what the person said" in INSTRUCTIONS and "is not a fact" in INSTRUCTIONS
    assert "language the person wrote the latest exchange in" in INSTRUCTIONS


def test_extraction_sees_the_weekday_and_the_coming_weeks():
    import datetime

    seen = []
    model([], seen).propose("我妈想11号到13号来，帮我回她让她16号周六再来。", "好的。", "(none)",
                            today=datetime.date(2027, 10, 7))
    content = seen[0]["messages"][1]["content"]
    assert "Today is 2027-10-07 (Thursday)." in content
    assert "2027-10-16 Sat" in content and "2027-11-11" in content  # Five weeks ahead.
    assert "next such day from today" in seen[0]["messages"][0]["content"]
