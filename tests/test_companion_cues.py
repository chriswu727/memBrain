"""Companion cues from the second two-arm attempt (evaluations/maturity-c5-second-attempt-2026-11-17.md) and the
owner's decisions of 2026-11-18: the mood moves on news told without a feeling word and shows in the host's own words
(C); a return after a long absence is acknowledged once (D); a listed shared moment may be used (E); "shorter" states
a limit (F); a moment the user only tells about is not shared (G).

No service and no database except the last test, which uses a real service: memory clients are stand-ins, and every
installation is a temporary directory."""
import datetime
import json
import re
from pathlib import Path

import pytest
from test_host import Client
from test_persona_growth import installation as installation

from membrain import helpers, host, notes, persona_growth, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.helpers import uid
from membrain.mood import MOOD_CHARACTERS, MOOD_GUIDANCE, RULES, render_mood
from membrain.relationship import RELATIONSHIP_CHARACTERS, SHARED_MOMENT_CUE, relationship_context

ROOT = Path(__file__).parents[1]
NOW = datetime.datetime(2026, 9, 12, 15, 0, tzinfo=datetime.UTC)
SKILL = (ROOT / "plugins/membrain/skills/membrain/SKILL.md").read_text(encoding="utf-8")
OPENCLAW = (ROOT / "integrations/openclaw/membrain/index.js").read_text(encoding="utf-8")
ASTRBOT = " ".join((ROOT / "integrations/astrbot/astrbot_plugin_membrain/main.py").read_text(encoding="utf-8").split())


@pytest.fixture(autouse=True)
def scenario_clock(monkeypatch):
    """A fixed clock and zone, as an evaluation's scenario clock gives the host side."""
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: NOW)
    monkeypatch.setattr(helpers, "display_zone", lambda: datetime.UTC)


# C. The mood moves on news and shows without a template ---------------------------------------------------------

def test_news_that_carries_a_feeling_is_saved_with_an_inferred_one_on_every_note_tool():
    sentence = "News that plainly carries a feeling the user does not name (a promotion, a pet that died) is saved "
    assert sentence + "with an inferred one." in notes.NOTE_TOOL_DESCRIPTION
    assert "Never invent a feeling" in notes.NOTE_TOOL_DESCRIPTION  # The rule against inventing one stays.
    assert "news they told plainly carries without naming it (basis inferred)" in notes.NOTE_FIELDS["affect"][
        "description"]
    openclaw = "".join(re.findall(r'"([^"]*)"', OPENCLAW[OPENCLAW.index('name: "membrain_note"'):
                                                         OPENCLAW.index("parameters:")]))
    for text in (openclaw, ASTRBOT):
        assert "as for news that plainly carries a feeling they do not name; never invent one." in text
    assert "is saved with an inferred feeling; without one the simulated mood cannot follow the news" in SKILL


def test_the_mood_shows_once_in_the_hosts_own_words_and_keeps_its_safeguards():
    for phrase in ("Let it show once in this reply, in your own words", "never a set phrase, never wording you used before",
                   "no sentence about your own mood unless the user asks",
                   "Leave it out only when the user's message is serious.",
                   "It is not a fact about the user.", "Never use it to pressure them.",
                   "If the user sincerely asks whether you have feelings, say this is a simulated mood."):
        assert phrase in MOOD_GUIDANCE, phrase
    longest = render_mood({"label": "concerned", "easing": True, "since": "2026-09-12T14:05:00Z",
                           "reason": "x" * 400}, tz=datetime.UTC)
    assert longest.endswith(MOOD_GUIDANCE + "\n</membrain-companion-mood>") and len(longest) <= MOOD_CHARACTERS
    assert "Let it show once in this reply, in your own words: one small touch that belongs to this reply" in SKILL
    assert "colour tone lightly" not in longest  # The guidance a host ignored (first two-arm attempt).


def test_the_mood_is_computed_as_before():
    # The rules and their pushes are unchanged by the new wording: good news (reported, inferred, a plan done) makes
    # it glad, distress concerned, a shared moment playful or glad.
    assert {name: (rule["label"], rule["push"](2.0)) for name, rule in RULES.items()} == {
        "reported_good_news": ("glad", (2.0, 0.5)), "inferred_good_news": ("glad", (2.0, 0.5)),
        "plan_done": ("glad", (2.0, 0.5)), "reported_distress": ("concerned", (-2.0, -1.0)),
        "inferred_distress": ("concerned", (-2.0, -1.0)), "shared_play": ("playful", (1.0, 2.0)),
        "shared_moment": ("glad", (2.0, 0.5))}


# D. A return after a long absence ---------------------------------------------------------------------------------

def ago(days, hours=0):
    return (NOW - datetime.timedelta(days=days, hours=hours)).isoformat().replace("+00:00", "Z")


@pytest.mark.parametrize("last, expected", [
    (ago(7), "7 days ago (5 September)"), (ago(19), "19 days ago (24 August)"),
    (ago(400), "400 days ago (8 August 2025)"), (ago(6), None),
    (ago(6, 20), None),  # Seven calendar days but not seven whole days.
    (None, None), ("not a time", None), (ago(-1), None)])
def test_the_absence_sentence_counts_whole_days(last, expected):
    text = host.absence_notice(last)
    if expected is None:
        assert text == ""
    else:
        assert text == (f"The user's last conversation with you was {expected}. Open your first reply with a few "
                        "words of your own that welcome them back (no set phrase), then answer; never say you missed "
                        "them or were waiting, never ask why they were away, and do not make them feel they should "
                        "come more often.")
    assert host.ABSENCE_NOTICE_DAYS == 7


def test_the_absence_sentence_uses_the_users_local_dates_and_the_scenario_clock(monkeypatch):
    # 05:00 on 24 Aug UTC is 19:00 on 23 Aug ten hours west of UTC, and 15:00 on 12 Sep UTC is 05:00 that day there.
    monkeypatch.setattr(helpers, "display_zone", lambda: datetime.timezone(datetime.timedelta(hours=-10)))
    assert "20 days ago (23 August)" in host.absence_notice("2026-08-24T05:00:00Z")
    monkeypatch.setattr(helpers, "display_zone", lambda: datetime.UTC)
    assert "19 days ago (24 August)" in host.absence_notice("2026-08-24T05:00:00Z")
    # The scenario clock moves, and the sentence with it.
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: NOW + datetime.timedelta(days=11))
    assert "30 days ago (24 August)" in host.absence_notice("2026-08-24T05:00:00Z")


class Timeline(Client):
    """A stand-in memory whose earlier conversations are ``messages`` (newest first)."""

    def __init__(self, messages=(), brain_id="brain"):
        super().__init__()
        self.messages, self.brain_id, self.asked = list(messages), brain_id, []

    def timeline(self, **options):
        self.asked.append(options)
        if options.get("conversation_id"):
            return {"complete": True, "items": []}
        excluded = options.get("exclude_conversation")
        return {"complete": True, "items": [
            {"event_id": f"e{number}", "text": "Hello.", "conversation_id": conversation, "producer": producer,
             "recorded_at": at, "sequence": 100 - number}
            for number, (conversation, producer, at) in enumerate(self.messages) if conversation != excluded]}


SENTENCE = "The user's last conversation with you was"
# A chat host's hooks (OpenClaw's), which put the sentence in the session notice; a coding host holds it for the
# first message when that message is casual (test_quiet_companion.py).
CHAT_HOST = plugin.PRODUCERS["openclaw"]


def test_the_session_notice_says_it_once_and_leaves_out_what_is_not_a_conversation(tmp_path, monkeypatch):
    client = Timeline([("membrain-notes", "membrain-notes", ago(1)), ("chat-2", "membrain-memory-page", ago(2)),
                       ("imported", "membrain-import:hermes", ago(3)), ("c1", "membrain-claude-code", ago(19))])
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    opening = plugin.session_start({"session_id": "c2"}, tmp_path, CHAT_HOST)
    assert opening.count(SENTENCE + " 19 days ago (24 August).") == 1
    assert client.asked[0]["exclude_conversation"] == "c2" and client.asked[0]["roles"] == ("user",)
    # A context rebuilt before the first prompt (a resumed session) still has it; nothing after the first prompt does.
    assert SENTENCE in plugin.session_start({"session_id": "c2"}, tmp_path, CHAT_HOST)
    plugin.user_prompt({"session_id": "c2", "prompt": "Hi again!", "prompt_id": "t1"}, tmp_path, CHAT_HOST)
    assert SENTENCE not in plugin.session_start({"session_id": "c2"}, tmp_path, CHAT_HOST)


@pytest.mark.parametrize("messages", [[], [("c1", "membrain-claude-code", ago(6))],
                                      [("membrain-notes", "membrain-notes", ago(30))]])
def test_no_sentence_for_a_first_conversation_or_a_short_gap(tmp_path, monkeypatch, messages):
    client = Timeline(messages)
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    assert SENTENCE not in plugin.session_start({"session_id": "c2"}, tmp_path, CHAT_HOST)


def test_each_person_on_a_multi_user_host_gets_their_own_and_a_chat_bot_says_it_with_the_first_message(
        tmp_path, monkeypatch):
    memory = ChatMemory(tmp_path)
    ada, bo, cy = (Speaker(platform="test", user=name) for name in ("ada", "bo", "cy"))
    clients = {memory.user_id(ada): Timeline([("old", "membrain-chatbot", ago(19))], "brain-ada"),
               memory.user_id(bo): Timeline([("old", "membrain-chatbot", ago(2))], "brain-bo"),
               memory.user_id(cy): Timeline([], "brain-cy")}
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: clients[user_id])
    sessions = {speaker.user: memory.session(speaker, "room", today=NOW.date()) for speaker in (ada, bo, cy)}
    first = memory.context(ada, "Hi, I'm back!", session=sessions["ada"], turn_id="t1") or ""
    assert first.count(SENTENCE + " 19 days ago (24 August).") == 1
    assert SENTENCE not in (memory.context(bo, "Hi!", session=sessions["bo"], turn_id="t1") or "")
    assert SENTENCE not in (memory.context(cy, "Hi!", session=sessions["cy"], turn_id="t1") or "")
    memory.record(ada, "Welcome back!", session=sessions["ada"], turn_id="t1")
    # The chat bot asks for the session context before every message: only the first one carries the sentence.
    assert SENTENCE not in (memory.context(ada, "How are you?", session=sessions["ada"], turn_id="t2") or "")


def test_a_role_play_or_a_service_that_is_starting_gives_no_sentence(tmp_path, monkeypatch):
    client = Timeline([("old", "membrain-claude-code", ago(19))])
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    assert SENTENCE not in host.session_context(tmp_path, "rp1", roleplay="Ada the pirate")
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: None)
    monkeypatch.setattr(host, "start_in_background", lambda directory: None)
    assert SENTENCE not in host.session_context(tmp_path, "s9")


# E. A listed shared moment can be used ----------------------------------------------------------------------------

def bond(moments, boundaries=()):
    return {"familiarity": {"level": "familiar", "reason": "familiar: 20 days of conversation since 1 Mar, 2 shared "
                                                           "moments"},
            "boundaries": list(boundaries), "shared_moments": moments,
            "commitments": {"missed": []}, "today": "2026-09-12"}


def test_the_relationship_block_says_once_how_a_shared_moment_may_be_used_and_stays_within_its_budget():
    assert SHARED_MOMENT_CUE == ("You may refer to one of these when what the user says makes it relevant, in your own "
                                 "words: lightly for a hard time that has mellowed, gently for a recent one. Never "
                                 "recite the list.")
    hard = {"id": "m1", "text": "Got through the night her flat flooded.", "occurs_at": "2026-08-01",
            "moment": "hard", "mellowed": True}
    play = {"id": "m2", "text": "A silly pun contest.", "occurs_at": "2026-09-01", "moment": "play"}
    block = relationship_context(bond([hard, play]))["block"]
    assert block.count(SHARED_MOMENT_CUE) == 1 and block.index(SHARED_MOMENT_CUE) < block.index("pun contest")
    assert "Shared moments, oldest first. " + SHARED_MOMENT_CUE + "\n- 1 Aug: Got through" in block
    assert SHARED_MOMENT_CUE not in (relationship_context(bond([]))["block"] or "")
    # Long moments and twelve boundaries: the moments that do not fit are left out, never the budget.
    boundaries = [{"id": f"b{n}", "topic": f"topic number {n} " + "y" * 40, "aliases": []} for n in range(12)]
    long = [{"id": f"m{n}", "text": "z" * 290, "occurs_at": "2026-09-0" + str(n + 1), "moment": "other"}
            for n in range(3)]
    crowded = relationship_context(bond(long, boundaries))["block"]
    assert len(crowded) <= RELATIONSHIP_CHARACTERS
    assert "Relationship" not in SHARED_MOMENT_CUE and "You may refer to a listed shared moment" in SKILL


# F. "Shorter" has a limit a reader can check -------------------------------------------------------------------

def test_a_card_accepted_with_the_old_short_is_kept_and_a_new_suggestion_can_give_the_limit():
    old = {**persona_growth.EMPTY_CARD, "voice": {"register": "", "length": "short", "emoji": "", "language": ""}}
    proposed, why_not = persona_growth._apply("shorter", old, "en")
    assert why_not is None and proposed["voice"]["length"] == persona_growth.KINDS["shorter"]["value"]["en"]
    assert persona_growth._apply("shorter", proposed, "en") == (None, "already_in_card")
    assert persona_growth._apply("longer", proposed, "zh")[0]["voice"]["length"] == "至少四句话，除非用户要求简短"


# G. Shared moments are saved less eagerly -------------------------------------------------------------------------

def test_a_moment_the_user_only_tells_about_is_not_a_shared_moment_on_every_note_tool():
    rule = ("Not something the user only tells you about (a quarrel with someone else, a success at work): shared "
            "means the two of you did it or went through it together in conversation.")
    assert rule in notes.NOTE_FIELDS["shared"]["description"]
    assert ("not something the user only tells you about, such as a quarrel with someone else or a success at work: "
            "shared means the two of you did it or went through it together in conversation") in (
        notes.NOTE_TOOL_DESCRIPTION)
    assert "a first conversation, a goal reached together, a shared joke" in notes.NOTE_TOOL_DESCRIPTION
    assert "moment hard for a difficult time the two of you went through" in notes.NOTE_TOOL_DESCRIPTION
    openclaw = OPENCLAW[OPENCLAW.index('name: "membrain_note"'):]
    assert rule in openclaw and "not something they only tell you about such as a quarrel" in "".join(
        re.findall(r'"([^"]*)"', openclaw[:openclaw.index("parameters:")]))
    assert rule in ASTRBOT
    assert "Something the user only tells you about (a quarrel with someone else, a success at work) is not a shared " \
           "moment" in SKILL and "Your first conversation is one." in SKILL
    assert len(host.server_instructions(plugin.HOST_TOOLS["openclaw"])) <= 1400  # The standing budget is unchanged.
    assert json.dumps(notes.NOTE_FIELDS)  # Still a valid schema.


# D on a real service ----------------------------------------------------------------------------------------------

def test_a_return_is_told_from_the_services_own_record_of_the_last_message(installation, monkeypatch):
    directory, service, settings = installation
    principal = next(iter(settings.principals().values()))
    user = "absence-" + uid()
    with host.ready_client(directory, user) as client:
        brain_id = client.brain_id
    assert SENTENCE not in host.session_context(directory, "first-" + user, user_id=user)  # A first conversation.

    def say(text, conversation, producer="membrain-claude-code"):  # In process, on the same database.
        result = service.handle(principal, {
            "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
            "target": {"brain_ref": brain_id, "conversation_ref": conversation, "branch_ref": "main"},
            "payload": {"idempotency_key": uid(), "events": [{
                "source_event_key": uid(), "source_revision": 1, "producer_ref": producer, "actor_ref": "user",
                "actor_role": "user", "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
                "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []}]}})
        assert result["outcome"] == "completed", result

    # The service records the message on the scenario clock, 19 days before the new conversation starts.
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: NOW - datetime.timedelta(days=19))
    say("We talked about the garden.", "earlier-" + user)
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: NOW)
    opening = host.session_context(directory, "back-" + user, user_id=user)
    assert opening.count(SENTENCE + " 19 days ago (24 August).") == 1
    other = "absence-other-" + uid()
    assert SENTENCE not in host.session_context(directory, "first-" + other, user_id=other)  # Another person's.
