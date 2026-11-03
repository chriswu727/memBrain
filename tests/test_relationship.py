"""R1 relationship: shared moments, derived familiarity, boundaries in recall, the commitment record, reset."""
import datetime
import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from membrain import desktop, embedded_database, host, notes
from membrain import service as service_module
from membrain.api import create_app
from membrain.config import configured_service
from membrain.helpers import DomainError, Principal, uid
from membrain.host_context import snapshot
from membrain.local_profile import load_profile
from membrain.notes import format_note, parse_note, store_note
from membrain.relationship import (
    RELATIONSHIP_CHARACTERS,
    RELATIONSHIP_CONVERSATION,
    THRESHOLDS,
    acknowledge,
    add_boundary,
    familiarity,
    kept_out,
    relationship,
    relationship_context,
    remove_boundary,
    reset_relationship,
    set_cap,
    set_support_style,
    touches,
)

WEB = Path(__file__).parents[1] / "src" / "membrain" / "web"
TODAY = datetime.date(2027, 3, 30)
EX = {"id": "b1", "topic": "my ex", "aliases": ["前任", "Jordan"]}


# Without a database ---------------------------------------------------------------------------------------------

def test_boundaries_match_whole_words_aliases_and_chinese_and_yield_when_the_user_raises_them():
    assert touches("My ex texted me last night", [EX]) == [EX]
    assert touches("the EX-boyfriend thing again", [EX]) and touches("Coffee with jordan?", [EX])
    assert touches("我前任昨天又联系我了", [EX]) and touches("前任的事", [EX])
    for unrelated in ("The next exam is on Friday", "an expert opinion", "Texas trip", ""):
        assert touches(unrelated, [EX]) == [], unrelated
    assert kept_out("My ex and I used to hike at Mount Tam.", [EX], "Any hiking ideas?")
    assert not kept_out("My ex and I used to hike at Mount Tam.", [EX], "I ran into my ex today")
    assert not kept_out("My ex and I used to hike at Mount Tam.", [EX], "我今天遇到前任了")
    assert not kept_out("Hiking at Mount Tam was lovely.", [EX], "Any hiking ideas?")
    # A message touching two boundaries stays out unless the current message raises both.
    work = {"id": "b2", "topic": "work", "aliases": ["工作"]}
    assert kept_out("My ex visited me at work.", [EX, work], "about my ex")
    assert not kept_out("My ex visited me at work.", [EX, work], "my ex came to work")
    # "my", "the" and "关于" lead the topic without being what it is about.
    assert touches("我的前任", [{"id": "b3", "topic": "关于我的前任", "aliases": []}])


def test_familiarity_is_derived_from_days_and_moments_through_documented_thresholds():
    assert THRESHOLDS == (("getting_to_know", 3, 0), ("familiar", 14, 2), ("close", 45, 6))
    days = [(datetime.date(2027, 3, 2) + datetime.timedelta(days=n)).isoformat() for n in range(60)]
    level = lambda count, moments, cap=None: familiarity(days[:count], moments, cap, TODAY)["level"]  # noqa: E731
    assert [level(0, 0), level(2, 9), level(3, 0), level(13, 9), level(14, 1), level(14, 2), level(44, 9),
            level(45, 5), level(45, 6)] == ["new", "new", "getting_to_know", "getting_to_know", "getting_to_know",
                                            "familiar", "familiar", "familiar", "close"]
    known = familiarity(days[:23], 6, None, TODAY)
    assert known["reason"] == "familiar: 23 days of conversation since 2 Mar, 6 shared moments"
    assert (known["days"], known["since"], known["shared_moments"]) == (23, "2027-03-02", 6)
    assert known["next"] == {"level": "close", "days": 45, "shared_moments": 6}
    assert familiarity([], 0, None, TODAY)["reason"] == "new: no conversation yet, 0 shared moments"
    assert familiarity(days[:1], 1, None, TODAY)["reason"] == "new: 1 day of conversation since 2 Mar, 1 shared moment"
    assert familiarity(days[:1], 0, None, datetime.date(2028, 1, 5))["reason"].endswith("since 2 Mar 2027, 0 shared moments")
    # The user can cap it at a lower level; a cap above the derived level changes nothing.
    capped = familiarity(days[:50], 7, "getting_to_know", TODAY)
    assert (capped["level"], capped["derived_level"], capped["cap"]) == ("getting_to_know", "close", "getting_to_know")
    assert capped["reason"] == ("getting to know: 50 days of conversation since 2 Mar, 7 shared moments "
                                "(capped by you; the rule gives close)")
    assert familiarity(days[:3], 0, "familiar", TODAY)["level"] == "getting_to_know"


def state(**extra):
    base = {"familiarity": familiarity(["2027-03-02"] * 1, 0, None, TODAY), "support_style": None,
            "boundaries": [], "shared_moments": [], "commitments": {"missed": []}, "today": TODAY.isoformat()}
    return {**base, **extra}


def test_the_block_lists_familiarity_style_boundaries_three_recent_moments_and_a_missed_promise_once():
    moments = [{"id": f"m{n}", "text": f"Moment {n}", "occurs_at": f"2027-03-0{n}", "recorded_at": "x"}
               for n in range(1, 6)] + [{"id": "s", "text": "Private moment", "occurs_at": "2027-03-09",
                                         "sensitive": True}]
    missed = {"note_id": "c1", "text": "Send the recipe", "due": "2027-03-10", "acknowledged": False}
    result = state(support_style={"text": "listen first, advice only when asked"}, boundaries=[EX],
                   shared_moments=moments, commitments={"missed": [missed, {**missed, "note_id": "c0",
                                                                             "acknowledged": True}]})
    context = relationship_context(result)
    block = context["block"]
    assert block.startswith("<membrain-relationship>\n") and block.endswith("\n</membrain-relationship>")
    assert "Familiarity: new: 1 day of conversation since 2 Mar, 0 shared moments." in block
    assert "How they like to be supported: listen first, advice only when asked" in block
    assert "Do not raise them, or anything recalled about them, unless the user does: my ex (also: 前任, Jordan)." in block
    assert "Shared moments, oldest first:\n- 3 Mar: Moment 3 (id: m3)\n- 4 Mar: Moment 4 (id: m4)\n- 5 Mar: Moment 5" in block
    assert "Moment 2" not in block and "Private moment" not in block  # Three at most; sensitive ones never.
    assert "Send the recipe (due 2027-03-10, id: c1)" in block and "id: c0" not in block
    assert context["once"] == ["c1"] and len(block) <= RELATIONSHIP_CHARACTERS
    assert "pressure" in block and "not a score of the user" in block
    # What decides a refresh ignores the growing day count and the one-time line, but not a newly missed promise.
    later = relationship_context({**result, "familiarity": familiarity(["2027-03-02", "2027-03-03"], 0, None, TODAY),
                                  "commitments": {"missed": [{**missed, "acknowledged": True}, result["commitments"]["missed"][1]]}})
    assert later["stable"] == context["stable"] and later["block"] != block and later["once"] == []
    assert relationship_context({**result, "commitments": {"missed": []}})["stable"] != context["stable"]
    assert relationship_context(None) == {"block": None, "stable": None, "once": []}


def test_a_new_relationship_with_nothing_beyond_the_default_renders_no_block():
    # A first session must not gain a block that only says "new"; an empty memory stays empty.
    empty = relationship_context(state())
    assert (empty["block"], empty["once"]) == (None, [])
    assert snapshot({"items": []}, brain_id="b", tools=None, relationship=state())["text"] == ""
    for extra in ({"familiarity": familiarity(["2027-03-02"], 0, "new", TODAY)},
                  {"familiarity": familiarity([f"2027-03-0{n}" for n in range(1, 4)], 0, None, TODAY)},
                  {"support_style": {"text": "listen first"}}, {"boundaries": [EX]},
                  {"shared_moments": [{"id": "m1", "text": "Our first chat.", "occurs_at": "2027-03-02"}]},
                  {"commitments": {"missed": [{"note_id": "c1", "text": "Send the recipe", "due": "2027-03-10"}]}}):
        assert relationship_context(state(**extra))["block"], extra
    # An acknowledged promise alone is nothing to show.
    assert relationship_context(state(commitments={"missed": [{"note_id": "c1", "text": "x", "due": "2027-03-10",
                                                               "acknowledged": True}]}))["block"] is None


def test_boundaries_keep_shared_moments_and_missed_promises_out_of_the_block():
    moments = [{"id": "m1", "text": "We celebrated getting over Jordan together.", "occurs_at": "2027-03-02"},
               {"id": "m2", "text": "和前任分手后我们一起去看了海。", "occurs_at": "2027-03-03"},
               {"id": "m3", "text": "Our first chat.", "occurs_at": "2027-03-04"}]
    missed = [{"note_id": "c1", "text": "Ask how the talk with Jordan went", "due": "2027-03-10"},
              {"note_id": "c2", "text": "问问前任的事处理得怎样", "due": "2027-03-11"},
              {"note_id": "c3", "text": "Send the recipe", "due": "2027-03-12"}]
    context = relationship_context(state(boundaries=[EX], shared_moments=moments, commitments={"missed": missed}))
    block = context["block"]
    assert "getting over Jordan" not in block and "看了海" not in block
    assert "Our first chat." in block and "Send the recipe" in block
    assert "talk with Jordan" not in block and "处理得怎样" not in block
    assert context["once"] == ["c3"]  # A promise kept out of the block is never acknowledged as shown.


def test_a_sensitive_missed_promise_is_listed_but_never_raised_automatically():
    missed = [{"note_id": "c1", "text": "Check in after the biopsy results", "due": "2027-03-10", "sensitive": True}]
    context = relationship_context(state(commitments={"missed": missed}))
    assert context["block"] is None and context["once"] == []


def test_snapshot_keeps_bounded_notes_and_shared_moments_out_of_the_notes_block():
    saved = {"items": [
        {"event_id": "n1", "text": "Prefers short replies.", "actor_role": "assistant", "recorded_at": "2027-03-01"},
        {"event_id": "n2", "text": format_note("Broke up with Jordan in January.", kind="relationship"),
         "actor_role": "assistant", "recorded_at": "2027-03-01"},
        {"event_id": "n3", "text": format_note("Our first chat.", kind="milestone", shared=True),
         "actor_role": "assistant", "recorded_at": "2027-03-01"}]}
    bond = state(boundaries=[EX], shared_moments=[{"id": "n3", "text": "Our first chat.", "occurs_at": None,
                                                    "recorded_at": "2027-03-01T10:00:00Z"}])
    current = snapshot(saved, brain_id="b", tools=None, relationship=bond)
    text = current["text"]
    assert "Prefers short replies." in text and "Jordan in January" not in text
    assert text.count("Our first chat.") == 1 and "- 1 Mar: Our first chat. (id: n3)" in text
    assert text.index("<membrain-relationship>") < text.index("<membrain-notes>")
    assert current["boundaries"] == [EX] and current["acknowledge"] == []
    # Without the relationship layer (an older service) the shared moment stays an ordinary note.
    assert "Our first chat." in snapshot(saved, brain_id="b", tools=None)["text"]
    more = snapshot(saved, brain_id="b", tools=None, relationship={
        **bond, "familiarity": familiarity(["2027-03-02", "2027-03-03"], 1, None, TODAY)})
    assert more["fingerprint"] == current["fingerprint"]  # A new day of conversation alone does not refresh.


def test_shared_marks_only_a_milestone_and_round_trips():
    stored = format_note("We finished the 10k plan together.", kind="milestone", occurs_at="2027-03-12", shared=True)
    assert stored == "[milestone · on 2027-03-12 · shared] We finished the 10k plan together."
    assert parse_note(stored)[0] == {"kind": "milestone", "occurs_at": "2027-03-12", "shared": True}
    assert parse_note("[plan · shared] Not a moment.") == ({}, "[plan · shared] Not a moment.")
    with pytest.raises(ValueError, match="kind milestone"):
        format_note("A plan.", kind="plan", shared=True)
    assert "shared" in notes.NOTE_FIELDS and "shared true" in notes.NOTE_TOOL_DESCRIPTION


def test_recall_context_leaves_out_bounded_messages_unless_the_current_message_raises_them():
    class Client:
        def __init__(self):
            self.traced = None

        def recall(self, query, **options):
            refs = [{"event_id": event, "relationship": "supports"} for event in ("e1", "e2")]
            return {"result": {"items": [{"memory": {"statement": f"user m1 (statement): {text}",
                                                     "evidence_refs": [ref], "scope": {"conversation_id": "old"}},
                                          "rank_signals": [{"method": "keyword", "score": 1}]}
                                         for ref, text in zip(refs, ("My ex and I hiked Mount Tam every week",
                                                                     "Mount Tam trails are best in spring"))]}}

        def timeline(self, **options):
            texts = {"e1": "My ex and I hiked Mount Tam every week.", "e2": "Mount Tam trails are best in spring."}
            return {"items": [{"event_id": event, "text": texts[event], "actor_role": "user", "conversation_id": "old",
                               "recorded_at": "2027-03-01"} for event in options["event_ids"]]}

        def following(self, ids):
            return {"items": []}

        def trace_recall(self, ids):
            self.traced = ids

        def relationship(self):
            return {"boundaries": [EX]}

    client = Client()
    quiet = host.recall_context(client, "Hiking ideas near Mount Tam?") or ""
    assert "best in spring" in quiet and "My ex" not in quiet and client.traced == ["e2"]
    raised = host.recall_context(client, "I saw my ex at Mount Tam") or ""
    assert "My ex and I hiked" in raised and "best in spring" in raised
    assert "My ex" in (host.recall_context(client, "Hiking ideas near Mount Tam?", boundaries=[]) or "")


# On a real service ----------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("relationship") / "installation"
    with patch.dict(os.environ, {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            settings = load_profile(directory).settings()
            with configured_service(settings) as service:
                yield directory, service, settings
        finally:
            desktop.stop(directory)


@pytest.fixture
def brain(installation):
    _, service, settings = installation
    principal = next(iter(settings.principals().values()))
    return service, principal, service.create_brain(principal, "Relationship test")["id"]


@pytest.fixture
def api(installation, brain):
    service, principal, ident = brain
    settings = replace(installation[2], api_keys={hashlib.sha256(b"relationship-test-key").hexdigest(): principal})
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer relationship-test-key"}) as client:
        yield client, f"/v1/brains/{ident}/relationship"


def say(brain, text, *, conversation="chat", on=None, monkeypatch=None):
    """One user message; ``on`` (with ``monkeypatch``) records it on that day, as the service clock reads it."""
    service, principal, ident = brain
    if on is not None:
        monkeypatch.setattr(service_module, "now", lambda: f"{on}T12:00:00Z")
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": "relationship-test", "actor_ref": "user",
            "actor_role": "user", "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
        }]},
    })
    return result


def note(brain, text, **fields):
    service, principal, ident = brain
    return store_note(service, principal, ident, {"request_id": uid(), "text": text, **fields})


def days_of_conversation(brain, monkeypatch, count, start=datetime.date(2027, 3, 2)):
    for offset in range(count):
        assert say(brain, f"Day {offset} chat.", on=(start + datetime.timedelta(days=offset)).isoformat(),
                   monkeypatch=monkeypatch)["outcome"] == "completed"
    monkeypatch.undo()


def test_cross_session_a_boundary_keeps_the_topic_out_until_it_is_removed(installation):
    directory = installation[0]
    user = "relationship-" + uid()

    def turn(session, text, reply="Okay."):
        context = host.prompt_context(directory, session, text, turn_id=uid(), user_id=user) or ""
        host.finish_turn(directory, session, reply, user_id=user)
        return context

    host.session_context(directory, "s0", user_id=user)
    turn("s0", "My ex Jordan and I used to go hiking at Mount Tam every Sunday.")
    turn("s0", "我前任以前总带我去海边。")
    turn("s0", "I also love hiking near Mount Tam on my own.")
    # Session 1: "please don't bring up my ex again" creates a boundary (the host calls the boundary tool).
    host.session_context(directory, "s1", user_id=user)
    turn("s1", "Please don't bring up my ex again.", "Understood, I won't.")
    with host.ready_client(directory, user) as client:
        saved = client.add_boundary("my ex", ["前任", "Jordan"])
        boundary = saved["boundaries"][0]
        assert (boundary["topic"], boundary["aliases"]) == ("my ex", ["前任", "Jordan"])
    # Session 5: the context lists the boundary, and recall leaves out messages about it unless raised.
    start = host.session_context(directory, "s5", user_id=user)
    assert "<membrain-relationship>" in start and "my ex (also: 前任, Jordan)" in start
    assert "Mount Tam every Sunday" not in start and "海边" not in start
    assert "hiking near Mount Tam on my own" in start  # Everything else is still there.
    quiet = turn("s5", "Any hiking ideas near Mount Tam this weekend?")
    recalled = quiet[quiet.index("<membrain-memory>"):]
    assert "hiking near Mount Tam on my own" in recalled and "Jordan" not in recalled and "Sunday" not in recalled
    raised = turn("s5", "I ran into Jordan at Mount Tam today, it was awkward.")
    assert "Mount Tam every Sunday" in raised
    # After the user removes the boundary on the page, session 6 recalls the topic normally.
    with host.ready_client(directory, user) as client:
        assert client.remove_boundary(boundary["id"])["boundaries"] == []
    later = host.session_context(directory, "s6", user_id=user)
    later += turn("s6", "Any hiking ideas near Mount Tam this weekend?")
    assert "Mount Tam every Sunday" in later and "海边" in later and "Boundaries:" not in later


def test_familiarity_crosses_its_thresholds_with_the_numbers_the_page_shows(brain, monkeypatch):
    service, principal, ident = brain
    days_of_conversation(brain, monkeypatch, 13)
    first = note(brain, "Our first conversation.", kind="milestone", shared=True, occurs_at="2027-03-02")
    note(brain, "We laughed about the burnt pancakes.", kind="milestone", shared=True, occurs_at="2027-03-05")
    note(brain, "Graduated in 2019.", kind="milestone")  # Not shared: an ordinary milestone.
    store_note(service, principal, ident, {"request_id": uid(), "text": "A note written by the user.", "role": "user"})
    say(brain, "Messages in a page note do not count.", conversation="membrain-notes")
    known = relationship(service, principal, ident, today=TODAY)["familiarity"]
    assert (known["level"], known["days"], known["shared_moments"]) == ("getting_to_know", 13, 2)
    days_of_conversation(brain, monkeypatch, 2, start=datetime.date(2027, 3, 14))  # The 14th distinct day, and a repeat.
    say(brain, "A second message on the same day.", on="2027-03-15", monkeypatch=monkeypatch)
    monkeypatch.undo()
    result = relationship(service, principal, ident, today=TODAY)
    assert result["familiarity"]["level"] == "familiar"
    assert result["familiarity"]["reason"] == "familiar: 14 days of conversation since 2 Mar, 2 shared moments"
    assert [moment["text"] for moment in result["shared_moments"]] == [
        "Our first conversation.", "We laughed about the burnt pancakes."]
    assert "Familiarity: familiar: 14 days of conversation since 2 Mar" in result["block"]
    # The cap holds it lower and says so; removing the cap restores the derived level.
    capped = set_cap(service, principal, ident, "getting_to_know", today=TODAY)["familiarity"]
    assert capped["level"] == "getting_to_know" and "(capped by you; the rule gives familiar)" in capped["reason"]
    assert set_cap(service, principal, ident, None, today=TODAY)["familiarity"]["level"] == "familiar"
    with pytest.raises(DomainError):
        set_cap(service, principal, ident, "close")
    # Deleting a shared moment lowers the count again: nothing is kept after the user deletes it.
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "membrain-notes", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [first["note_id"]]},
                    "mode": "erase_content", "expected_scope_generation": generation}})
    assert relationship(service, principal, ident, today=TODAY)["familiarity"]["level"] == "getting_to_know"


def test_a_missed_commitment_is_shown_once_and_kept_ones_are_recorded(installation):
    directory = installation[0]
    user = "promise-" + uid()
    host.session_context(directory, "p0", user_id=user)
    host.prompt_context(directory, "p0", "Can you send me the lasagne recipe?", turn_id="1", user_id=user)
    host.finish_turn(directory, "p0", "I'll send it by the 10th.", user_id=user)
    with host.ready_client(directory, user) as client:
        missed = notes.save_note(client, "Send the lasagne recipe.", kind="agent_commitment", status="intended",
                                 due="2020-01-10")["note_id"]
        notes.save_note(client, "Check in after the move.", kind="agent_commitment", status="done", due="2020-01-02")
        notes.save_note(client, "Plan the picnic.", kind="agent_commitment", status="cancelled", due="2020-01-03")
        record = client.relationship()["commitments"]
        assert [item["note_id"] for item in record["missed"]] == [missed] and not record["missed"][0]["acknowledged"]
        assert [item["text"] for item in record["kept"]] == ["Check in after the move."]
        assert [item["text"] for item in record["cancelled"]] == ["Plan the picnic."]  # Cancelled is not missed.
    first = host.session_context(directory, "p1", user_id=user)
    assert "past its date and not done (shown once): Send the lasagne recipe." in first
    # Shown once: the next message does not refresh because of it, and a new session does not repeat it.
    assert "<membrain-updates>" not in (host.prompt_context(directory, "p1", "Hi", turn_id="2", user_id=user) or "")
    second = host.session_context(directory, "p2", user_id=user)
    assert "shown once" not in second  # Nothing else to say yet, so there is no relationship block at all.
    with host.ready_client(directory, user) as client:
        assert client.relationship()["commitments"]["missed"][0]["acknowledged"] is True


def test_sensitive_and_bounded_missed_promises_are_listed_but_not_shown_or_acknowledged(brain):
    service, principal, ident = brain
    add_boundary(service, principal, ident, "my ex", ["前任", "Jordan"])
    private = note(brain, "Check in after the biopsy results.", kind="agent_commitment", status="intended",
                   due="2027-03-10", sensitive=True)["note_id"]
    bounded = note(brain, "问问前任的事处理得怎样", kind="agent_commitment", status="intended", due="2027-03-11")["note_id"]
    plain = note(brain, "Send the recipe.", kind="agent_commitment", status="intended", due="2027-03-12")["note_id"]
    result = relationship(service, principal, ident, today=TODAY)
    missed = {item["note_id"]: item for item in result["commitments"]["missed"]}
    assert set(missed) == {private, bounded, plain}  # The page lists every one.
    assert missed[private]["sensitive"] is True and missed[plain]["sensitive"] is False
    assert result["once"] == [plain] and "biopsy" not in result["block"] and "前任的事" not in result["block"]
    after = acknowledge(service, principal, ident, [private, bounded, plain], today=TODAY)
    assert {item["note_id"]: item["acknowledged"] for item in after["commitments"]["missed"]} == {
        private: False, bounded: False, plain: True}


def test_mcp_recall_honors_boundaries_with_and_without_an_installation(brain, tmp_path):
    import asyncio

    import httpx

    from membrain.client import MemoryClient
    from membrain.mcp_server import create_server

    service, principal, ident = brain
    say(brain, "My ex Jordan and I hiked Mount Tam every Sunday.")
    say(brain, "Mount Tam trails are best in spring.")
    add_boundary(service, principal, ident, "my ex", ["前任", "Jordan"])
    service.work_once(principal, ident)

    def handle(request):
        path, query = request.url.path, request.url.params
        if path == "/v1/actions":
            return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))
        if path.endswith("/relationship"):
            return httpx.Response(200, json=relationship(service, principal, ident))
        if path.endswith("/timeline/following"):
            return httpx.Response(200, json=service.following(principal, ident, query.get_list("event_id")))
        if path.endswith("/timeline"):
            return httpx.Response(200, json=service.timeline(
                principal, ident, roles=query.get_list("role"), event_ids=query.get_list("event_id") or None,
                max_characters=int(query["max_characters"]), max_item_characters=int(query["max_item_characters"]),
                limit=int(query["limit"])))
        return httpx.Response(200, json={"recorded": 0})

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        for directory in (None, tmp_path):  # The standalone server and a local installation's.
            server = create_server(client, directory=directory)
            _, quiet = asyncio.run(server.call_tool("memory_recall", {"query": "Mount Tam"}))
            quiet = json.dumps(quiet, ensure_ascii=False)
            assert "best in spring" in quiet and "every Sunday" not in quiet, directory
            _, raised = asyncio.run(server.call_tool("memory_recall", {"query": "Jordan at Mount Tam"}))
            assert "every Sunday" in json.dumps(raised, ensure_ascii=False), directory


def test_reset_starts_familiarity_again_and_nothing_from_before_the_marker_returns(brain, monkeypatch):
    from membrain.affect import affect_records
    from membrain.persona import current_persona, set_persona

    service, principal, ident = brain
    days_of_conversation(brain, monkeypatch, 14)
    source = say(brain, "Remember when we named the cat Biscuit together?")["result"]["accepted_event_ids"][0]
    note(brain, "Named the cat Biscuit together.", kind="milestone", shared=True, source_event_ids=[source])
    note(brain, "Our first conversation.", kind="milestone", shared=True)
    add_boundary(service, principal, ident, "my ex", ["前任"])
    set_support_style(service, principal, ident, "listen first, advice only when asked")
    set_cap(service, principal, ident, "familiar")
    promise = note(brain, "Send the recipe.", kind="agent_commitment", status="intended", due="2027-03-10")["note_id"]
    note(brain, "Called back as promised.", kind="agent_commitment", status="done")
    acknowledge(service, principal, ident, [promise], today=TODAY)
    kept = note(brain, "Allergic to peanuts.", kind="constraint",
                affect={"label": "worried", "valence": -1, "intensity": 1, "basis": "reported"})
    set_persona(service, principal, ident, {"name": "Mira"}, made_by="host")
    before = relationship(service, principal, ident, today=TODAY)
    assert before["familiarity"]["level"] == "familiar" and before["commitments"]["missed"][0]["acknowledged"]
    messages = service.timeline(principal, ident, roles=("user",), limit=1000)["items"]

    reset = reset_relationship(service, principal, ident, today=TODAY)
    assert reset["removed"] == {"shared_moments": 2, "boundaries": 1, "support_style": 1, "cap": 1,
                                "acknowledgements": 1}
    marker = reset["marker"]
    assert marker["marker"] == "reset" and marker["recorded_at"] and marker["applies_from_sequence"]
    # One more session, on a new day.
    say(brain, "Good morning!", on="2027-03-31", monkeypatch=monkeypatch)
    monkeypatch.undo()
    after = relationship(service, principal, ident, today=datetime.date(2027, 3, 31))
    assert after["familiarity"]["level"] == "new"
    assert after["familiarity"]["reason"] == "new: 1 day of conversation since 31 Mar, 0 shared moments"
    assert (after["shared_moments"], after["boundaries"], after["support_style"]) == ([], [], None)
    assert after["familiarity"]["cap"] is None
    assert after["commitments"] == {"kept": [], "missed": [], "cancelled": [], "open": []}
    assert after["markers"] == [marker] and after["block"] is None
    # A moment read from a message before the marker is never recreated; a new one is kept.
    again = note(brain, "Named the cat Biscuit together.", kind="milestone", shared=True, source_event_ids=[source])
    assert "never recreated" in again["shared_refused"]
    fresh = note(brain, "Our first chat since the reset.", kind="milestone", shared=True)
    assert "shared_refused" not in fresh
    assert [moment["text"] for moment in relationship(service, principal, ident)["shared_moments"]] == [
        "Our first chat since the reset."]
    # Conversations, other notes, the persona and feelings stay.
    assert service.timeline(principal, ident, roles=("user",), limit=1000)["items"][1:] == messages
    current_notes = {row["text"] for row in service.timeline(principal, ident, roles=("assistant", "user"),
                                                           conversation_id="membrain-notes", limit=1000)["items"]}
    assert format_note("Allergic to peanuts.", kind="constraint") in current_notes
    assert format_note("Send the recipe.", kind="agent_commitment", status="intended", due="2027-03-10") in current_notes
    assert not any("Biscuit" in text and "shared" in text for text in current_notes)
    assert [entry["note_id"] for entry in affect_records(service, principal, ident)["records"]] == [kept["note_id"]]
    assert current_persona(service, principal, ident)["card"]["name"] == "Mira"
    with service.database.transaction(principal) as conn:
        tombstones = conn.execute(
            "SELECT count(*) AS value FROM memory_tombstones t JOIN memory_events e ON e.tenant_id=t.tenant_id "
            "AND e.owner_id=t.owner_id AND e.brain_id=t.brain_id AND e.id=t.object_id WHERE t.brain_id=%s "
            "AND e.conversation_id=ANY(%s) AND t.mode='erase_content'",
            (ident, [RELATIONSHIP_CONVERSATION, "membrain-notes"])).fetchone()
    assert tombstones["value"] >= 6  # Audited deletion, so it holds if a backup is restored.
    # Erasing all memory removes the marker too.
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident}, "payload": {
            "idempotency_key": uid(), "selector": {"kind": "all_authorized_scope", "ids": []},
            "mode": "erase_content", "expected_scope_generation": generation}})
    assert relationship(service, principal, ident)["markers"] == []


def test_records_are_never_recalled_counted_or_scheduled_for_learning(brain, monkeypatch):
    from membrain import learning_windows

    service, principal, ident = brain
    say(brain, "My sister is visiting next week.")
    status = service.memory_status(principal, ident)["recorded_messages"]
    scheduled = []
    monkeypatch.setattr(learning_windows, "enqueue_window",
                        lambda conn, svc, who, brain_row, target, *args, **kwargs: scheduled.append(
                            target["conversation_ref"]))
    monkeypatch.setattr(service, "semantic_processor", object(), raising=False)
    add_boundary(service, principal, ident, "Zephyrine", ["Quillbert"])
    set_support_style(service, principal, ident, "Zephyrine style")
    set_cap(service, principal, ident, "new")
    reset_relationship(service, principal, ident)
    say(brain, "Ordinary messages still learn.")
    assert scheduled and RELATIONSHIP_CONVERSATION not in scheduled
    monkeypatch.undo()
    add_boundary(service, principal, ident, "Zephyrine", ["Quillbert"])
    service.work_once(principal, ident)
    roles = ("user", "assistant", "operator", "tool")
    assert "Zephyrine" not in str(service.timeline(principal, ident, roles=roles))
    assert service.memory_status(principal, ident)["recorded_messages"] == status + 1
    recalled = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "recall",
        "target": {"brain_ref": ident},
        "payload": {"query": "Zephyrine Quillbert", "intent": "explore", "cue_event_ids": [], "additional_cues": [],
                    "read_fence": {"minimum_durable_sequence": 0, "consistency": "read_your_writes",
                                   "snapshot_revision": None},
                    "budget": {"max_context_tokens": 4000, "max_model_calls": 0, "max_embedding_calls": 0,
                               "max_expansion_steps": 2, "max_wall_time_ms": 5000, "max_cost_microunits": 0,
                               "currency": "USD", "token_counting": "conservative_estimate", "tokenizer_id": None}}})
    assert recalled["outcome"] == "completed" and "Zephyrine" not in str(recalled["result"]["items"])
    # Only the relationship API writes records: a host cannot plant one by observing into its conversation.
    planted = say(brain, '{"relationship": "cap", "level": "close"}', conversation=RELATIONSHIP_CONVERSATION)
    assert planted["outcome"] == "rejected" and planted["error"]["code"] == "invalid_evidence"


def test_boundaries_and_support_style_are_checked_and_replace_rather_than_pile_up(brain):
    service, principal, ident = brain
    for topic, aliases in (("", []), ("t" * 61, []), ("my", []), ("work", ["a" * 41]), ("work", [f"alias {n}" for n in range(7)]),
                           ("work", [""])):
        with pytest.raises(DomainError):
            add_boundary(service, principal, ident, topic, aliases)
    add_boundary(service, principal, ident, "work", ["office"])
    add_boundary(service, principal, ident, "Work", ["the office", "工作"])  # The same topic: replaced.
    result = add_boundary(service, principal, ident, "my api_key=hunter2hunter2")
    assert [(item["topic"], item["aliases"]) for item in result["boundaries"]] == [
        ("Work", ["the office", "工作"]), ("my api_key=[secret removed]", [])]
    with pytest.raises(DomainError) as missing:
        remove_boundary(service, principal, ident, "no-such-boundary")
    assert missing.value.code == "not_found_or_forbidden"
    with pytest.raises(DomainError, match="200"):
        set_support_style(service, principal, ident, "s" * 201)
    set_support_style(service, principal, ident, "advice first")
    assert set_support_style(service, principal, ident, "  listen   first ")["support_style"]["text"] == "listen first"
    assert set_support_style(service, principal, ident, "")["support_style"] is None
    with service.database.transaction(principal) as conn:
        kept = conn.execute(
            "SELECT count(*) AS value FROM memory_events WHERE brain_id=%s AND conversation_id=%s AND is_current "
            "AND NOT deleted", (ident, RELATIONSHIP_CONVERSATION)).fetchone()["value"]
    assert kept == 2  # Two boundaries; replaced boundaries and earlier support styles were erased.


def test_api_and_sdk_routes_check_keys_owners_and_bodies(installation, brain, api):
    service, principal, ident = brain
    client, path = api
    foreign = service.create_brain(Principal(principal.tenant_id, uid()), "Foreign")["id"]
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    empty = client.get(path).json()
    assert empty["familiarity"]["level"] == "new" and empty["boundaries"] == [] and empty["block"] is None
    for method, suffix, body in (("GET", "", None), ("PUT", "/support-style", {"text": "x"}),
                                 ("POST", "/boundaries", {"topic": "x"}), ("DELETE", "/boundaries/x", None),
                                 ("POST", "/cap", {"level": None}), ("POST", "/acknowledge", {"note_ids": []}),
                                 ("POST", "/reset", None)):
        denied = client.request(method, f"/v1/brains/{foreign}/relationship{suffix}", json=body)
        assert denied.status_code == 404, (method, suffix)
        assert client.request(method, f"{path}{suffix}", json=body,
                              headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.put(path + "/support-style", json={"text": "listen first"}).json()["support_style"]["text"] == "listen first"
    added = client.post(path + "/boundaries", json={"topic": "my ex", "aliases": ["前任"]}).json()["boundaries"]
    assert added[0]["topic"] == "my ex"
    bad = client.post(path + "/boundaries", json={"topic": "x", "extra": 1})
    assert bad.status_code == 422 and bad.json()["error"]["message"].startswith("Relationship request field extra")
    assert client.post(path + "/boundaries", json={"topic": ""}).status_code == 422
    assert client.post(path + "/cap", json={"level": "close"}).status_code == 422
    assert client.post(path + "/cap", json={"level": "new"}).json()["familiarity"]["cap"] == "new"
    assert client.post(path + "/acknowledge", json={"note_ids": ["unknown"]}).status_code == 200
    assert client.delete(path + "/boundaries/" + added[0]["id"]).json()["boundaries"] == []
    assert client.delete(path + "/boundaries/" + added[0]["id"]).status_code == 404
    reset = client.post(path + "/reset").json()
    assert reset["marker"]["marker"] == "reset" and reset["support_style"] is None and reset["familiarity"]["cap"] is None
    shared = client.post(f"/v1/brains/{ident}/notes", json={"request_id": uid(), "text": "First chat.",
                                                           "kind": "milestone", "shared": True}).json()
    assert client.get(path).json()["shared_moments"][0]["id"] == shared["note_id"]


def test_sdk_uses_the_brain_scoped_relationship_routes():
    import httpx

    from membrain.client import MemoryClient

    requests = []

    def handler(request):
        requests.append((request.method, request.url.raw_path.decode(), request.content))
        return httpx.Response(200, json={"boundaries": []})

    with MemoryClient("http://127.0.0.1:8790", "test", brain_id="my brain",
                      transport=httpx.MockTransport(handler)) as client:
        client.relationship()
        client.set_support_style("listen first")
        client.add_boundary("my ex", ["前任"])
        client.remove_boundary("b 1")
        client.cap_familiarity("familiar")
        client.acknowledge_commitments(["n1"])
        client.reset_relationship()
    base = "/v1/brains/my%20brain/relationship"
    assert [(method, path) for method, path, _ in requests] == [
        ("GET", base), ("PUT", base + "/support-style"), ("POST", base + "/boundaries"),
        ("DELETE", base + "/boundaries/b%201"), ("POST", base + "/cap"), ("POST", base + "/acknowledge"),
        ("POST", base + "/reset")]
    assert json.loads(requests[2][2]) == {"topic": "my ex", "aliases": ["前任"]}
    assert json.loads(requests[4][2]) == {"level": "familiar"}


def test_restored_archives_keep_the_relationship_records(installation, brain):
    import httpx

    from membrain.client import MemoryClient

    service, principal, ident = brain
    note(brain, "Our first conversation.", kind="milestone", shared=True)
    add_boundary(service, principal, ident, "my ex", ["前任"])
    set_support_style(service, principal, ident, "listen first")
    set_cap(service, principal, ident, "getting_to_know")

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        copy = service.create_brain(principal, "Restored relationship")["id"]
        client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=copy)
    restored = relationship(service, principal, copy)
    assert [(item["topic"], item["aliases"]) for item in restored["boundaries"]] == [("my ex", ["前任"])]
    assert restored["support_style"]["text"] == "listen first"
    assert restored["familiarity"]["cap"] == "getting_to_know"
    assert [moment["text"] for moment in restored["shared_moments"]] == ["Our first conversation."]
    # The restored records can still be changed, and the boundary removed.
    assert remove_boundary(service, principal, copy, restored["boundaries"][0]["id"])["boundaries"] == []


def restore_copy(service, principal, source, name):
    import httpx

    from membrain.client import MemoryClient

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", source, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        copy = service.create_brain(principal, name)["id"]
        client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=copy)
    return copy


def test_a_restored_brain_keeps_days_its_messages_carry_and_adds_nothing_to_the_archive(installation, brain,
                                                                                          monkeypatch):
    service, principal, ident = brain

    def said(text, occurred):
        return service.handle(principal, {
            "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
            "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
            "payload": {"idempotency_key": uid(), "events": [{
                "source_event_key": uid(), "source_revision": 1, "producer_ref": "relationship-test",
                "actor_ref": "user", "actor_role": "user", "event_kind": "message",
                "content": {"media_type": "text/plain", "text": text},
                "occurred_time": {"start": occurred, "end": None, "precision": "exact", "basis": "source_explicit"},
                "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
            }]}})["outcome"]

    monkeypatch.setattr(service_module, "now", lambda: "2027-03-22T12:00:00Z")
    for day in range(2, 22):
        assert said(f"Day {day}.", f"2027-03-{day:02d}T09:00:00Z") == "completed"
    monkeypatch.undo()
    note(brain, "Our first conversation.", kind="milestone", shared=True)
    note(brain, "We finished the 10k plan together.", kind="milestone", shared=True)
    before = relationship(service, principal, ident, today=TODAY)["familiarity"]
    assert (before["level"], before["days"], before["since"]) == ("familiar", 20, "2027-03-02")
    monkeypatch.setattr(service_module, "now", lambda: "2027-04-20T08:00:00Z")
    copy = restore_copy(service, principal, ident, "Restored days")
    monkeypatch.undo()
    after = relationship(service, principal, copy, today=TODAY)["familiarity"]
    assert (after["level"], after["days"], after["since"]) == (before["level"], before["days"], before["since"])
    # A restored brain must stay identical to its archive: the restore wrote nothing beyond the imported events.
    with service.database.transaction(principal) as conn:
        extra = conn.execute(
            "SELECT count(*) AS n FROM memory_events WHERE brain_id=%s AND producer_ref <> 'archive-import'",
            (copy,)).fetchone()["n"]
    assert extra == 0


def test_restored_messages_without_a_reported_time_keep_their_days_across_repeated_restores(installation, brain,
                                                                                             monkeypatch):
    service, principal, ident = brain

    def said(text):
        return service.handle(principal, {
            "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
            "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
            "payload": {"idempotency_key": uid(), "events": [{
                "source_event_key": uid(), "source_revision": 1, "producer_ref": "relationship-test",
                "actor_ref": "user", "actor_role": "user", "event_kind": "message",
                "content": {"media_type": "text/plain", "text": text},
                "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
            }]}})["outcome"]

    for when in ("2027-03-02T09:00:00Z", "2027-03-05T09:00:00Z", "2027-03-09T09:00:00Z"):
        monkeypatch.setattr(service_module, "now", lambda when=when: when)
        assert said(f"Chat recorded at {when}.") == "completed"
    # A clock that ran ahead recorded this one in the future; a restore never counts a day still to come.
    monkeypatch.setattr(service_module, "now", lambda: "2027-05-01T09:00:00Z")
    assert said("Recorded by a clock that ran ahead.") == "completed"
    monkeypatch.setattr(service_module, "now", lambda: "2027-04-20T08:00:00Z")
    first = restore_copy(service, principal, ident, "First restore")
    monkeypatch.setattr(service_module, "now", lambda: "2027-04-25T08:00:00Z")
    second = restore_copy(service, principal, first, "Restore of the restore")
    monkeypatch.undo()
    for copy in (first, second):
        known = relationship(service, principal, copy, today=TODAY)["familiarity"]
        assert (known["days"], known["since"]) == (4, "2027-03-02")
    with service.database.transaction(principal) as conn:
        rows = conn.execute(
            "SELECT document FROM memory_events WHERE brain_id=%s AND is_current ORDER BY sequence", (second,)).fetchall()
        extra = conn.execute(
            "SELECT count(*) AS n FROM memory_events WHERE brain_id IN (%s,%s) AND producer_ref <> 'archive-import'",
            (first, second)).fetchone()["n"]
    assert extra == 0  # Nothing beyond the imported events: the restored brains still equal their archives.
    times = [row["document"]["system_time"] for row in rows]
    # recorded_at stays this copy's ingestion; the original recording time is the earliest one, never a future one.
    assert {time["recorded_at"] for time in times} == {"2027-04-25T08:00:00Z"}
    assert [time["restored_from_recorded_at"] for time in times] == [
        "2027-03-02T09:00:00Z", "2027-03-05T09:00:00Z", "2027-03-09T09:00:00Z", "2027-04-20T08:00:00Z"]
    assert all(row["document"]["observed"]["occurred_time"]["start"] is None for row in rows)  # Never invented.


@pytest.mark.parametrize("field", ["recorded_at", "restored_from_recorded_at"])
@pytest.mark.parametrize("extreme", ["0001-01-01T00:00:00+23:59", "9999-12-31T23:59:59-23:59"])
def test_an_archive_time_with_no_utc_form_is_an_invalid_archive_and_the_restore_writes_nothing(installation, brain,
                                                                                              field, extreme):
    import httpx

    from membrain.client import MemoryActionError, MemoryClient
    from membrain.helpers import digest

    service, principal, ident = brain
    note(brain, "Our first conversation.", kind="milestone", shared=True)

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        archive_id = client.export()["result"]["archive_id"]
        document = service.download_archive(principal, archive_id)["document"]
        document["events"][0]["system_time"][field] = extreme  # Valid as a date-time, but outside UTC's range.
        with pytest.raises(DomainError) as refused:
            service.upload_archive(principal, ident, document)
        assert refused.value.code == "invalid_archive"
        # An archive stored before this check is refused at restore, and the restore's transaction writes nothing.
        with service.database.transaction(principal) as conn:
            conn.execute("UPDATE memory_archives SET document=%s, manifest_hash=%s WHERE id=%s",
                         (Jsonb(document), digest(document), archive_id))
        copy = service.create_brain(principal, "Never restored")["id"]
        with pytest.raises(MemoryActionError) as rejected:
            client.restore(archive_id, expected_manifest_sha256=digest(document), expected_scope_generation=1,
                           mode="new_brain", brain_id=copy)
    response = rejected.value.response
    assert response["outcome"] == "rejected" and response["error"]["code"] == "invalid_archive", response
    with service.database.transaction(principal) as conn:
        written = conn.execute("SELECT count(*) AS n FROM memory_events WHERE brain_id=%s", (copy,)).fetchone()["n"]
    assert written == 0


def test_days_follow_when_a_message_occurred_but_never_a_time_still_to_come(brain, monkeypatch):
    service, principal, ident = brain

    def said(text, occurred):
        return service.handle(principal, {
            "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
            "target": {"brain_ref": ident, "conversation_ref": "imported-chat", "branch_ref": "main"},
            "payload": {"idempotency_key": uid(), "events": [{
                "source_event_key": uid(), "source_revision": 1, "producer_ref": "relationship-test",
                "actor_ref": "user", "actor_role": "user", "event_kind": "message",
                "content": {"media_type": "text/plain", "text": text},
                "occurred_time": {"start": occurred, "end": None, "precision": "exact", "basis": "source_explicit"},
                "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
            }]}})["outcome"]

    monkeypatch.setattr(service_module, "now", lambda: "2027-03-20T12:00:00Z")
    for day in range(2, 16):  # Fourteen days of history, all recorded on 20 Mar.
        assert said(f"Chat on day {day}.", f"2027-03-{day:02d}T09:00:00Z") == "completed"
    assert said("Late evening in New York.", "2027-03-15T22:30:00-05:00") == "completed"  # 16 Mar in UTC.
    assert said("Earlier today.", "2027-03-20T08:00:00Z") == "completed"
    assert said("A time still to come.", "2027-06-01T09:00:00Z") == "completed"  # Counted on 20 Mar instead.
    monkeypatch.undo()
    known = relationship(service, principal, ident, today=TODAY)["familiarity"]
    assert (known["days"], known["since"]) == (16, "2027-03-02")


def test_the_map_puts_shared_moments_in_the_relationship_region(brain):
    from membrain.memory_map import memory_map

    moment = note(brain, "Our first conversation.", kind="milestone", shared=True)
    plain = note(brain, "Graduated in 2019.", kind="milestone")
    regions = {node["id"]: node["region"] for node in memory_map(*brain)["nodes"]}
    assert regions["note:" + moment["note_id"]] == "relationship"
    assert regions["note:" + plain["note_id"]] == "milestones"


# The page --------------------------------------------------------------------------------------------------------

def test_every_relationship_string_on_the_page_has_chinese():
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    section = script[script.index("// Relationship ---"):script.index("// Personality ---")]
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    literals = set(re.findall(r'(?:element\("\w+", |notify\(|confirm\(|: )"([^"]*[A-Za-z]{2}[^"]*)"', section))
    ignored = {"user-text", "hint", "empty", "tag", "link", "link danger", "meta", "actions", "item", "secondary",
               "danger", "item relationship-moment", "relationship-level", "row", "field", "PUT", "DELETE",
               "relationship-marker", "tag relationship-missed", "check", "item relationship-boundary"}
    missing = sorted(text for text in literals - ignored if f'"{text}"' not in dictionary)
    assert missing == []
    for pattern in ("^Relationship reset on (.+)$", "^(new|getting to know|familiar|close): (\\d+) days?",
                    "^Next: (.+) at (\\d+) days and (\\d+) shared moments?\\.$", "^also: (.+)$",
                    "^Kept: (\\d+) · missed: (\\d+) · cancelled: (\\d+) · open: (\\d+)$", "^due (.+)$"):
        assert pattern in dictionary, pattern
    for message in ("Keep the support style under 200 characters.", "That boundary is not available.",
                    "A boundary topic is 1 to 60 characters."):
        assert f'"{message}"' in dictionary, message
    html = (WEB / "memory.html").read_text(encoding="utf-8")
    assert '<button data-view="persona">Companion</button>' in html and 'id="relationship"' in html
    assert "loadRelationship()" in script and '"shared"' in script
