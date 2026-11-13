"""The recall block uses its budget and every current note is a candidate."""

import httpx
import pytest
from test_plugin import _ReadyClient, _response, _source

from membrain import host, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.notes import NOTE_PAGES, format_note, list_notes, render_notes


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def _recalled(count, text="Short fact number {index} about the trip."):
    messages = {f"m{index}": {"event_id": f"m{index}", "conversation_id": f"c{index}", "actor_role": "user",
                              "recorded_at": f"2026-03-{index % 28 + 1:02d}T00:00:00Z",
                              "text": text.format(index=index)} for index in range(count)}
    response = _response(*(_source(f"user user (direct_statement): {message['text']}", key, score=1 - index * .01)
                           for index, (key, message) in enumerate(messages.items())))

    class Client:
        brain_id = "brain"

        def recall(self, query, **options):
            return response

        def timeline(self, **options):
            return {"items": [messages[key] for key in options["event_ids"] if key in messages]}

        def following(self, event_ids):
            return {"items": []}

    return Client(), messages


def test_short_recalled_messages_fill_the_block_instead_of_stopping_at_twelve():
    client, messages = _recalled(60)
    context = plugin.recall_context(client, "what about the trip?", current_conversation="current")
    lines = [line for line in context.splitlines() if line.startswith("- [")]
    assert len(lines) == host.MAX_MESSAGES == 40 and len(context) <= host.CONTEXT_CHARACTERS
    shown = {line.split("] ", 1)[1] for line in lines}
    assert shown == {messages[f"m{index}"]["text"] for index in range(40)}  # The best ranked, in full.


def test_long_recalled_messages_still_stop_at_the_character_budget():
    client, _ = _recalled(60, text="Fact {index}: " + "a long account of the day. " * 30)
    context = plugin.recall_context(client, "what about the trip?", current_conversation="current")
    lines = [line for line in context.splitlines() if line.startswith("- [")]
    assert 1 < len(lines) < 20 and len(context) <= host.CONTEXT_CHARACTERS


def test_a_host_that_starts_every_message_with_session_context_keeps_the_previous_prompt_as_a_cue(tmp_path, monkeypatch):
    cues = []

    class Client(_ReadyClient):
        def recall(self, query, **options):
            cues.append(options.get("additional_cues"))
            return {"result": {"items": []}}

        def timeline(self, **options):
            if options.get("conversation_id") == "membrain-notes":
                return self.notes
            return {"complete": False, "items": []}

    client = Client({"complete": False, "items": []})
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    memory, mei = ChatMemory(tmp_path, tools=None), Speaker("discord", "mei")
    session = memory.session(mei)
    memory.context(mei, "Mom fell and we're going to urgent care.", session=session, turn_id="1")
    memory.record(mei, "I'm sorry. What do you need?", session=session, turn_id="1")
    memory.context(mei, "What do I tell the front desk?", session=session, turn_id="2")
    assert cues == [[], ["Mom fell and we're going to urgent care."]]


def test_a_pause_still_clears_the_cue_for_such_a_host(tmp_path, monkeypatch):
    cues = []

    class Client(_ReadyClient):
        def recall(self, query, **options):
            cues.append(options.get("additional_cues"))
            return {"result": {"items": []}}

        def timeline(self, **options):
            return self.notes if options.get("conversation_id") == "membrain-notes" else {"complete": False, "items": []}

    client = Client({"complete": False, "items": []})
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    monkeypatch.setattr(host, "use_brain", lambda *args: None)
    memory, mei = ChatMemory(tmp_path, tools=None), Speaker("discord", "mei")
    session = memory.session(mei)
    memory.context(mei, "My salary is a private matter.", session=session, turn_id="1")
    memory.record(mei, "Understood.", session=session, turn_id="1")
    host.pause(tmp_path, user_id=memory.user_id(mei))
    host.resume(tmp_path, user_id=memory.user_id(mei))
    memory.context(mei, "What should I cook tonight?", session=session, turn_id="2")
    assert cues[-1] == []


class _Notes:
    """A service double whose timeline pages notes newest first, 200 at a time, like the real one."""

    def __init__(self, texts, fail_after=None):
        self.items = [{"event_id": f"n{index}", "sequence": index + 1, "text": text, "actor_role": "assistant",
                       "producer": "membrain-notes", "recorded_at": "2026-04-01T00:00:00Z"}
                      for index, text in enumerate(texts)]
        self.calls, self.fail_after = 0, fail_after

    def timeline(self, **options):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise httpx.ReadTimeout("slow")
        before = options.get("before_sequence")
        newest_first = [item for item in reversed(self.items) if before is None or item["sequence"] < before]
        page = newest_first[:options["limit"]]
        complete = len(newest_first) <= options["limit"]
        return {"items": page, "complete": complete, "characters": sum(len(item["text"]) for item in page),
                "next_before_sequence": None if complete else page[-1]["sequence"]}


def test_a_pinned_note_older_than_two_hundred_newer_notes_is_still_shown():
    texts = [format_note("Severe peanut allergy: never suggest peanuts.", kind="constraint", pinned=True)] + [
        f"Ordinary fact number {index} about the garden." for index in range(450)]
    client = _Notes(texts)
    listed = list_notes(client)
    assert len(listed["items"]) == 451 and listed["complete"] and client.calls == 3
    assert "Severe peanut allergy" in render_notes(listed)


def test_note_listing_is_bounded_and_says_when_it_stopped_early():
    client = _Notes([f"Fact {index}." for index in range(200 * NOTE_PAGES + 50)])
    listed = list_notes(client)
    assert len(listed["items"]) == 200 * NOTE_PAGES and not listed["complete"] and client.calls == NOTE_PAGES
    failing = _Notes([f"Fact {index}." for index in range(450)], fail_after=1)
    listed = list_notes(failing)
    assert len(listed["items"]) == 200 and not listed["complete"]  # The newest notes still show.
    assert "did not fit" in render_notes(listed)
