"""A deleted message's date never comes back (outside review of 2026-11-18).

The "return after an absence" notice rests only on a user message that still exists as a current, readable record:
when the last one is deleted it falls back to the one before it, and to nothing when none is left. The session keeps
only that the question was asked, never the sentence, so a deletion between the session's first context and its first
prompt is seen too. The other dates derived from messages (the history block, the familiarity line, an accepted
suggestion's reason) are checked after a deletion too.

Every test drives the normal plugin hooks (session start, prompt, stop) or records on the service's own clock, and
deletes through the same action the memory page sends, on a real service. The host's clock is moved forward as an
evaluation's scenario clock does."""
import copy
import datetime
import json
import re

import pytest
from test_persona_growth import brain as brain
from test_persona_growth import forget
from test_persona_growth import installation as installation

from membrain import helpers, host, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.client import default_budget
from membrain.helpers import digest, uid
from membrain.persona import PERSONA_CONVERSATION, _save, current_persona, persona_versions
from membrain.persona_growth import KINDS, accept_proposal, persona_proposals
from membrain.persona_presets import switch_preset

SENTENCE = "The user's last conversation with you was"


@pytest.fixture
def clock(monkeypatch):
    """The host side's clock (``helpers.now``), moved forward by ``clock(days)``; the service records real times."""
    start = datetime.datetime.now(datetime.UTC)
    monkeypatch.setattr(helpers, "display_zone", lambda: datetime.UTC)

    def move(days):
        monkeypatch.setattr(helpers, "_scenario_clock", lambda: start + datetime.timedelta(days=days))

    return move


def talk(directory, user, session, text, turn):
    """One exchange through the hooks Claude Code calls."""
    plugin.session_start({"session_id": session, "membrain_user": user}, directory)
    plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": turn, "membrain_user": user}, directory)
    plugin.stop({"session_id": session, "last_assistant_message": "Glad you told me.", "prompt_id": turn,
                 "membrain_user": user}, directory)


def message(directory, user, text):
    with host.ready_client(directory, user) as client:
        items = client.timeline(roles=("user",), limit=1000)["items"]
    return next(item for item in items if item["text"] == text)


def delete(directory, user, kind, ids, conversation):
    """What the memory page sends for "Delete" on a message or "Delete this conversation"."""
    with host.ready_client(directory, user) as client:
        generation = client.dashboard()["brain"]["scope_generation"]
        result = client.forget(ids, kind=kind, mode="erase_content", expected_scope_generation=generation,
                               conversation_id=conversation)
    assert result.get("outcome") == "completed", result


# The session start of a chat host with several people (OpenClaw), which shows the absence sentence and the
# familiarity line at once; a coding host holds both for a casual message (test_quiet_companion.py).
CHAT_HOST = plugin.PRODUCERS["openclaw"]


def opening(directory, user, session):
    return plugin.session_start({"session_id": session, "membrain_user": user}, directory, CHAT_HOST) or ""


def test_a_deleted_last_message_gives_no_date_and_the_one_before_it_is_used(installation, clock):
    directory, _, _ = installation
    user = "absence-deleted-" + uid()
    clock(0)
    talk(directory, user, "old-" + user, "We planted tomatoes in the old garden.", "t1")
    talk(directory, user, "last-" + user, "I finally fixed the bike.", "t1")
    clock(10)
    # The control: both messages exist, so the notice names the last one.
    assert opening(directory, user, "control-" + user).count(SENTENCE + " 10 days ago") == 1
    last = message(directory, user, "I finally fixed the bike.")
    delete(directory, user, "events", [last["event_id"]], last["conversation_id"])
    clock(10)
    # The earlier conversation is still a current record: its date is the one told (the same day here, so the same
    # count); the deleted message is never what the sentence rests on.
    assert opening(directory, user, "after-one-" + user).count(SENTENCE + " 10 days ago") == 1
    earlier = message(directory, user, "We planted tomatoes in the old garden.")
    delete(directory, user, "conversation", [earlier["conversation_id"]], earlier["conversation_id"])
    assert SENTENCE not in opening(directory, user, "after-all-" + user)


def test_the_only_message_deleted_on_the_page_gives_no_notice_in_a_new_session(installation, clock):
    directory, _, _ = installation
    user = "absence-only-" + uid()
    clock(0)
    talk(directory, user, "earlier-" + user, "My sister visits next week.", "t1")
    only = message(directory, user, "My sister visits next week.")
    delete(directory, user, "events", [only["event_id"]], only["conversation_id"])
    clock(9)
    assert SENTENCE not in opening(directory, user, "later-" + user)


def test_a_deletion_after_the_first_context_and_before_it_is_shown_again_is_seen(installation, clock):
    """A context rebuilt before the session's first prompt (a resumed or compacted session) shows the notice again;
    a message deleted in between must not be named by it."""
    directory, _, _ = installation
    user = "absence-cached-" + uid()
    clock(0)
    talk(directory, user, "earlier-" + user, "The interview is on Friday.", "t1")
    clock(12)
    session = "back-" + user
    assert opening(directory, user, session).count(SENTENCE + " 12 days ago") == 1
    only = message(directory, user, "The interview is on Friday.")
    delete(directory, user, "events", [only["event_id"]], only["conversation_id"])
    rebuilt = opening(directory, user, session)
    assert SENTENCE not in rebuilt
    # Nothing in the session's state holds the sentence or the deleted message's date.
    state = host.session_state(directory, session)
    assert SENTENCE not in str(state) and "12 days ago" not in str(state)
    # The first prompt still ends the notice for this session.
    plugin.user_prompt({"session_id": session, "prompt": "Hello.", "prompt_id": "t1", "membrain_user": user},
                       directory, CHAT_HOST)
    assert SENTENCE not in opening(directory, user, session)


def test_a_chat_bot_that_asks_before_every_message_sees_the_deletion_too(installation, clock):
    directory, _, _ = installation
    memory = ChatMemory(directory)
    speaker = Speaker(platform="test", user="absence-bot-" + uid())
    clock(0)
    old = memory.session(speaker, "room", today=datetime.date(2000, 1, 1))
    memory.context(speaker, "I moved to a new flat.", session=old, turn_id="t1")
    memory.record(speaker, "Congratulations!", session=old, turn_id="t1")
    user = memory.user_id(speaker)
    only = message(directory, user, "I moved to a new flat.")
    delete(directory, user, "events", [only["event_id"]], only["conversation_id"])
    clock(15)
    new = memory.session(speaker, "room", today=datetime.date(2000, 2, 1))
    assert SENTENCE not in (memory.context(speaker, "Hi, I'm back!", session=new, turn_id="t1") or "")


# The other dates a host or the page derives from messages ---------------------------------------------------------

NOW = datetime.datetime(2026, 9, 12, 15, 0, tzinfo=datetime.UTC)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
LONG_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")


def forms(day):
    """Every way a host block or the page writes a day."""
    return {day.isoformat(), f"{day.day} {MONTHS[day.month - 1]}", f"{day.day} {LONG_MONTHS[day.month - 1]}",
            f"{day.month}月{day.day}日"}


def record(service, principal, brain_id, monkeypatch, text, days_ago, conversation, producer="membrain-claude-code"):
    """A user message recorded by the service itself on the scenario clock, ``days_ago`` before ``NOW``."""
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: NOW - datetime.timedelta(days=days_ago))
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": brain_id, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": producer, "actor_ref": "user",
            "actor_role": "user", "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []}]}})
    assert result["outcome"] == "completed", result
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: NOW)
    return result["result"]["accepted_event_ids"][0]


def test_no_block_of_a_new_session_names_the_day_of_a_deleted_message(installation, monkeypatch):
    directory, service, settings = installation
    principal = next(iter(settings.principals().values()))
    monkeypatch.setattr(helpers, "display_zone", lambda: datetime.UTC)
    user = "dates-deleted-" + uid()
    with host.ready_client(directory, user) as client:
        brain_id = client.brain_id
    gone = record(service, principal, brain_id, monkeypatch, "The day we talked about the lake house.", 41, "c-old")
    record(service, principal, brain_id, monkeypatch, "Back from the trip.", 12, "c-new")
    deleted_day = (NOW - datetime.timedelta(days=41)).date()
    def names(text):
        return [form for form in forms(deleted_day) if re.search(r"(?<![\d-])" + re.escape(form) + r"(?!\d)", text)]

    def familiarity():  # The familiarity line, as the page and the relationship block give it.
        with host.ready_client(directory, user) as client:
            return client.relationship()["familiarity"]["reason"]

    before = opening(directory, user, "control-" + user)
    assert names(before)  # The control: the day is shown while the message exists.
    assert "2 days of conversation since 2 Aug" in familiarity()
    delete(directory, user, "events", [gone], "c-old")
    after = opening(directory, user, "after-" + user)
    assert SENTENCE + " 12 days ago" in after, after
    assert names(after) == []
    assert "1 day of conversation since 31 Aug" in familiarity() and not names(familiarity())


def test_an_accepted_suggestion_does_not_keep_the_dates_of_deleted_feedback(installation, monkeypatch):
    directory, service, settings = installation
    principal = next(iter(settings.principals().values()))
    user = "dates-feedback-" + uid()
    with host.ready_client(directory, user) as client:
        client.switch_persona_preset("intj")
        brain_id = client.brain_id
    comments = ("Your replies are too long.", "You're too wordy.", "Please be more concise.")
    ids = [record(service, principal, brain_id, monkeypatch, text, days, f"c{days}")
           for text, days in zip(comments, (30, 20, 10), strict=True)]
    with host.ready_client(directory, user) as client:
        proposal = next(item for item in client.persona_proposals()["proposals"] if item["kind"] == "shorter")
        client.accept_persona_proposal(proposal["id"])
        assert "(13 Aug; 23 Aug; 2 Sep)" in client.persona()["reason"]
    delete(directory, user, "events", [ids[0]], "c30")
    with host.ready_client(directory, user) as client:
        listed = client.persona_versions()
        accepted = listed["versions"][0]
        assert accepted["reason"] == "Accepted suggestion: shorter replies, from 2 messages (23 Aug; 2 Sep)"
        assert listed["agreements"][0]["reason"] == accepted["reason"]
        assert client.persona()["reason"] == accepted["reason"]
        assert "feedback_messages" not in client.persona()
    delete(directory, user, "conversation", ["c20", "c10"], "c20")
    with host.ready_client(directory, user) as client:
        assert client.persona()["reason"] == "Accepted suggestion: shorter replies"
        assert client.persona()["card"]["voice"]["length"] == KINDS["shorter"]["value"]["en"]  # The change stays.


def stored_versions(service, principal, brain_id):
    """Each persona version's stored record, as the database holds it (newest first)."""
    with service.database.transaction(principal) as conn:
        rows = conn.execute(
            "SELECT document->'observed'->'content'->>'text' AS text FROM memory_events WHERE tenant_id=%s "
            "AND owner_id=%s AND brain_id=%s AND conversation_id=%s AND is_current AND document IS NOT NULL "
            "ORDER BY sequence DESC", (*service._params(principal, brain_id), PERSONA_CONVERSATION)).fetchall()
    return [json.loads(row["text"]) for row in rows]


def act(service, principal, brain_id, action, payload):
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": action,
        "target": {"brain_ref": brain_id, "conversation_ref": "chat", "branch_ref": "main"}, "payload": payload})
    assert result["outcome"] == "completed", result
    return result["result"]


def test_no_stored_or_exported_reason_keeps_the_dates_of_deleted_feedback(brain, monkeypatch):
    """An accepted suggestion stores its reason without dates (the kind and the language only); a version an earlier
    runtime stored with dates is read with the dates of messages that still exist, and leaves in an export, a
    downloaded archive or an archive cleaned after an erasure without them."""
    service, principal, ident = brain
    switch_preset(service, principal, ident, "intj")
    ids = [record(service, principal, ident, monkeypatch, text, days, "chat")
           for text, days in zip(("Your replies are too long.", "You're too wordy.", "Please be more concise."),
                                 (30, 20, 10), strict=True)]
    proposal = next(item for item in persona_proposals(service, principal, ident)["proposals"]
                    if item["kind"] == "shorter")
    accepted = accept_proposal(service, principal, ident, proposal["id"])["persona"]
    assert accepted["reason"] == "Accepted suggestion: shorter replies, from 3 messages (13 Aug; 23 Aug; 2 Sep)"
    stored = stored_versions(service, principal, ident)[0]
    assert (stored["reason"], stored["language"]) == ("Accepted suggestion: shorter replies", "en")
    # A version as an earlier runtime stored it: the dates of every message in its reason, no language beside it.
    card = persona_versions(service, principal, ident)["versions"][0]["card"]
    _save(service, principal, ident, lambda find: ({**card, "voice": {**card["voice"], "emoji": "never"}}, {
        "feedback": {"proposal_id": "earlier", "kind": "less_emoji", "source_event_ids": ids}}),
        made_by="feedback", reason="Accepted suggestion: fewer emoji, from 3 messages (13 Aug; 23 Aug; 2 Sep)",
        action="feedback")
    exported = act(service, principal, ident, "export", {
        "include_events": True, "include_working_states": True, "include_assertions": True,
        "include_provenance": True, "include_tombstones": True, "budget": default_budget(64000)})
    offline = copy.deepcopy(service.download_archive(principal, exported["archive_id"])["document"])
    forget(brain, [ids[0]])  # The first message, of 13 Aug, is deleted after the copy was taken.
    listed = persona_versions(service, principal, ident)["versions"]
    assert [item["reason"] for item in listed[:2]] == [
        "Accepted suggestion: fewer emoji, from 2 messages (23 Aug; 2 Sep)",
        "Accepted suggestion: shorter replies, from 2 messages (23 Aug; 2 Sep)"]
    assert current_persona(service, principal, ident)["reason"] == listed[0]["reason"]

    def reasons(document):
        events = [event for event in document["events"] if event["scope"]["conversation_id"] == PERSONA_CONVERSATION]
        for event in events:
            assert digest(event["observed"]["content"]) == event["content_sha256"]
        return [json.loads(event["observed"]["content"]["text"]).get("reason") for event in events]

    # The export, the archive stored then (cleaned when the message was erased), and a copy taken before.
    for document in (offline, service.download_archive(principal, exported["archive_id"])["document"]):
        assert "Aug" not in json.dumps(reasons(document)), reasons(document)
        assert "Accepted suggestion: fewer emoji" in reasons(document)
    again = act(service, principal, ident, "export", {
        "include_events": True, "include_working_states": True, "include_assertions": True,
        "include_provenance": True, "include_tombstones": True, "budget": default_budget(64000)})
    assert "Aug" not in json.dumps(reasons(service.download_archive(principal, again["archive_id"])["document"]))
    # Restored into a new brain, the reasons read again with the dates of the messages restored with them.
    copy_brain = service.create_brain(principal, "Restored")["id"]
    uploaded = service.upload_archive(principal, copy_brain, offline)
    act(service, principal, copy_brain, "restore", {
        "uploaded_archive_ref": uploaded["archive_id"], "expected_manifest_sha256": uploaded["manifest_sha256"],
        "mode": "new_brain", "apply_current_tombstones": True,
        "expected_scope_generation": service.dashboard(principal, copy_brain)["brain"]["scope_generation"],
        "budget": default_budget(64000)})
    restored = persona_versions(service, principal, copy_brain)["versions"]
    assert restored[0]["reason"].startswith("Accepted suggestion: fewer emoji, from 2 messages (")
