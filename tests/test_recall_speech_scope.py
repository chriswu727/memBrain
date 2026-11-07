import pytest
from test_cognition import event, request, scope, state
from test_plugin import _response, _source

from membrain import cognition, host


@pytest.mark.parametrize("cue", ["Which kettle did you recommend?", "你上次推荐的水壶是哪款？"])
@pytest.mark.parametrize("intent", ["explore", "current_fact"])
def test_retrieval_cues_do_not_authorize_assistant_speech(cue, intent):
    sources = [event("I own a blue kettle."), event("Consider a red kettle instead.", 2, "assistant")]
    memories = [memory for source in sources for memory in cognition.extract_event(source)]
    result = cognition.recall(scope(), request("kettle", intent=intent, additional_cues=[cue]),
                              memories, sources, state(2))
    statements = [item["memory"]["statement"] for item in result["items"]]
    assert any("blue kettle" in text for text in statements)
    assert not any("red kettle" in text for text in statements)


@pytest.mark.parametrize("query,intent", [("Which kettle did you recommend?", "explore"),
                                         ("kettle", "exact_quote"), ("kettle", "episode")])
def test_explicit_speech_requests_still_recall_assistant_sources(query, intent):
    source = event("Consider a red kettle instead.", role="assistant")
    result = cognition.recall(scope(), request(query, intent=intent),
                              cognition.extract_event(source), [source], state())
    assert any("red kettle" in item["memory"]["statement"] for item in result["items"])


@pytest.mark.parametrize("timeline_available", [True, False])
@pytest.mark.parametrize("explicit", [True, False])
def test_host_filters_direct_assistant_hits_as_well_as_following_replies(timeline_available, explicit):
    asked = {"event_id": "user", "conversation_id": "old", "actor_role": "user",
             "recorded_at": "2026-01-01T00:00:00Z", "text": "I own a blue kettle."}
    suggested = {"event_id": "assistant", "conversation_id": "old", "actor_role": "assistant",
                 "recorded_at": "2026-01-01T00:00:01Z", "text": "Consider a red kettle instead."}
    response = _response(_source("user user (direct_statement): I own a blue kettle.", "user"),
                         _source("assistant assistant (direct_statement): Consider a red kettle instead.",
                                 "assistant"))
    response["result"]["items"][1]["memory"]["claim_kind"] = "proposal_offered"

    class Client:
        def recall(self, query, **options):
            return response

        def timeline(self, **options):
            if not timeline_available:
                raise RuntimeError("unavailable")
            return {"items": [item for item in (asked, suggested) if item["event_id"] in options["event_ids"]]}

        def following(self, wanted):
            return {"items": [{"source_event_id": "user", **suggested}]}

        def trace_recall(self, event_ids):
            self.traced = event_ids

    client = Client()
    query = "Which kettle did you recommend?" if explicit else "What kettle do I own?"
    context = host.recall_context(client, query, cues=("Which kettle did you recommend?",))
    assert "blue kettle" in context
    assert ("red kettle" in context) is explicit
    assert ("assistant" in client.traced) is (explicit and timeline_available)
