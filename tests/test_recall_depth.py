"""Old memories are not forgotten: automatic recall puts recent ones first, a search made on purpose reaches any.

The owner's rule (2026-11-12): an old memory sinks to a deeper layer that takes more effort to reach, so that recent
and important ones come first, but the AI never really forgets anything. Automatic recall keeps the age weight; a
search the host AI makes through a tool asks the service to rank by relevance alone.
"""
import asyncio
import io
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_turns import turns as turns
from test_vector_jobs import drain, recall_request

from membrain import helpers, host, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.client import default_budget, default_read_fence
from membrain.contracts import validate
from membrain.helpers import DomainError, uid
from membrain.mcp_server import create_server
from membrain.notes import store_note


class Recording:
    brain_id = "brain"

    def __init__(self):
        self.calls = []

    def recall(self, query, **options):
        self.calls.append(options)
        return {"outcome": "completed", "result": {"items": []}}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_a_search_made_on_purpose_asks_for_relevance_alone_and_automatic_recall_does_not():
    client = Recording()
    host.recall(client, "quartz keynote")
    host.recall(client, "quartz keynote", deliberate=True)
    host.recall(client, "quartz keynote", replies=True, deliberate=True)
    automatic, search, search_replies = client.calls
    assert "ranking" not in automatic and "intent" not in automatic
    # Only the ranking changes: the request is not made as a check of earlier records, which would leave out the
    # user's own questions and requests.
    assert search["ranking"] == "relevance" and "intent" not in search
    assert search_replies["ranking"] == "relevance" and search_replies["intent"] == "episode"


def test_the_request_accepts_the_two_rankings_and_refuses_others():
    base = {"query": "quartz", "intent": "explore", "cue_event_ids": [], "additional_cues": [],
            "read_fence": default_read_fence(), "budget": default_budget(1000)}
    for ranking in ("recency", "relevance"):
        validate("RecallPayload", {**base, "ranking": ranking})
    with pytest.raises(DomainError):
        validate("RecallPayload", {**base, "ranking": "newest"})


def test_every_host_s_search_tool_is_a_search_made_on_purpose(tmp_path, monkeypatch, capsys):
    seen = []

    def recall_context(client, query, **options):
        seen.append(options)
        return None

    monkeypatch.setattr(host, "recall_context", recall_context)
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: Recording())
    server = create_server(Recording(), directory=tmp_path)
    asyncio.run(server.call_tool("memory_recall", {"query": "quartz"}))
    assert plugin.run_tool("search", tmp_path, stream=io.BytesIO(json.dumps({"query": "quartz"}).encode())) == 0
    capsys.readouterr()
    ChatMemory(tmp_path).search(Speaker("telegram", "42", None), "quartz")
    assert len(seen) == 3 and all(options.get("deliberate") is True for options in seen)
    # The records listed for forgetting are searched for on purpose as well.
    client = Recording()
    asyncio.run(create_server(client, directory=tmp_path).call_tool("memory_recall", {"query": "quartz", "with_ids": True}))
    assert client.calls[0]["ranking"] == "relevance"


@pytest.mark.integration
def test_a_message_a_note_was_written_from_does_not_sink_and_never_rises_above_a_newer_one(turns, monkeypatch):
    """Recent and important first: the message a note cites ranks as if it were as recent as the newest one."""
    moment = {"value": datetime(2026, 1, 1, tzinfo=UTC)}
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: moment["value"])
    text = "The quartz keynote is in Lisbon."
    noted, plain = (turns.observe(text, conversation="spring")["event_id"] for _ in range(2))
    moment["value"] += timedelta(days=200)
    newest = turns.observe(text, conversation="autumn")["event_id"]
    note = store_note(turns.service, turns.principal, turns.brain,
                      {"request_id": uid(), "text": "Worth keeping.", "source_event_ids": [noted]})
    assert note["source_event_ids"] == [noted]
    drain(turns)
    moment["value"] += timedelta(days=1)
    turns.conversation = "later"

    def scores(**payload):
        request = recall_request(turns, "quartz keynote")
        request["payload"].update(payload)
        response = turns.service.handle(turns.principal, request)
        assert response["outcome"] == "completed", response
        found = {}
        for item in response["result"]["items"]:
            event = item["memory"]["evidence_refs"][0]["event_id"]
            found[event] = max(found.get(event, 0.0), sum(signal["score"] for signal in item["rank_signals"]))
        return found

    # Equally relevant messages are scored by their fused rank, so the age weight is the score over the score a
    # search by relevance alone gives the same message.
    automatic, relevance = scores(), scores(ranking="relevance")
    weight = {event: automatic[event] / relevance[event] for event in (noted, plain, newest)}
    assert weight[noted] == pytest.approx(weight[newest]) and weight[plain] < weight[newest]
