"""The companion on a coding host: always on, but quiet (owner's decision, 2026-11-19).

A coding host's session (Claude Code, Codex, WorkBuddy) starts with the persona's quiet form, the agreements and the
boundaries; the full card, the mood, familiarity, shared moments, the absence sentence and the first persona's intro
come once, through the prompt hook, when the conversation turns casual or emotional or the host uses a companion tool.
Chat hosts are unchanged. The first tests need no service; the rest play ``companion_world`` through the plugin's own
hooks on a real service."""
import json
from pathlib import Path

import pytest
from companion_world import built_world
from resume_correction_world import CONVERSATIONS, PROMPTS, THIRD, filler_conversations

from membrain import host, persona_presets
from membrain.conversation_tone import companion_cue
from membrain.host_context import COMPANION, companion_update, snapshot
from membrain.persona import render_manner, render_persona, with_agreements
from membrain.relationship import relationship_context

ROOT = Path(__file__).parents[1]
INTRO = "A personality type was picked at random"
FULL = "Companion persona (v"
QUIET = "Your own manner, not a fact about the user"
LEAD = "<membrain-companion>"
FAMILIARITY = "Familiarity:"
MOOD = "<membrain-companion-mood>"
ABSENCE = "The user's last conversation with you was"


# The cue, without a model ------------------------------------------------------------------------------------------

def test_a_whole_coding_world_and_the_real_host_trial_never_cue_the_companion():
    trial = (ROOT / "evaluations/evidence/host-trial-2026-11-18/messages.txt").read_text(encoding="utf-8")
    messages = ([text for _, _, turns in CONVERSATIONS + filler_conversations() for text, _ in turns]
                + [THIRD, *PROMPTS.values()] + [line.split(": ", 1)[1] for line in trial.splitlines() if ": " in line])
    assert len(messages) == 50
    assert [text for text in messages if companion_cue(text)] == []


@pytest.mark.parametrize("text", [
    "hey, the tests are failing on main again", "Morning! Let's pick up where we left off on the parser.",
    "thanks! now add a test for the empty case", "thanks", "perfect, thank you!", "lol that regex is cursed. can you "
    "simplify it?", "ugh, CI is red again", "I'm so tired of this flaky test", "I'm worried this migration will lock "
    "the users table in prod", "nice 🎉 that fixed it", "haha ok", "long day, let's just get the deploy out",
    "hello, can you help me with a Rust lifetime error?", "my boss wants this merged by Friday",
    "I'm happy with this version, commit it", "sorry, I was away for lunch. where were we?",
    "back from lunch, let's continue", "I'm confused, why is the type wrong here?", "sigh. fine, use the old library",
    "I'm going on vacation next week, so let's document the setup", "That was a rough deploy. Let's write a postmortem.",
    "Ugh, the Docker build ate another 20 GB and my laptop is almost full again.",
    "ugh, I'm confused by this error. pandas says KeyError: 'gauge_id' when I merge my flow table with the station "
    "list.", "早上好，继续昨天的重构", "谢谢！", "帮我看看这个报错", "哈哈，这个bug太离谱了"])
def test_work_with_a_greeting_a_laugh_or_a_feeling_about_the_work_stays_quiet(text):
    assert companion_cue(text) is None


@pytest.mark.parametrize(("text", "cue"), [
    ("hi", "casual"), ("Hey there! How's it going?", "casual"), ("你好", "casual"),
    ("Hi! Just got back from a long hike with my sister and I'm so happy.", "casual"),
    ("Today is Wednesday, March 11, 20:00. Hi again! How are you?", "casual"),
    ("ugh, long day. my manager moved the deadline up again.", "feeling"),
    ("Today is Monday, March 16, 20:00. Long day at work.", "feeling"),
    ("I'm really nervous about my first design review on Thursday.", "feeling"),
    ("Honestly I'm exhausted. My kid was up all night.", "feeling"),
    ("I'm stressed, the demo is tomorrow and the build is broken", "feeling"),  # A heavy feeling counts anyway.
    ("My grandmother passed away last night.", "feeling"), ("好累啊，今天先到这吧", "feeling"),
    ("What's your personality like?", "self"), ("You sound a bit different today.", "self"),
    ("Could you switch to a different personality type? Surprise me.", "self"), ("/membrain:persona", "self"),
    ("Thanks for staying with me on Friday night when my flat flooded. That was rough.", "self")])
def test_a_casual_or_emotional_message_or_one_about_the_agent_cues_it(text, cue):
    assert companion_cue(text) == cue


# The quiet form ------------------------------------------------------------------------------------------------------

def test_the_quiet_persona_is_the_voice_and_what_the_user_added_in_about_a_third_of_the_card():
    for preset in persona_presets.PRESETS:
        persona = {"version": 1, "card": persona_presets.card(preset["id"]), "preset": preset["id"]}
        quiet, full = render_manner(persona), render_persona(persona)
        assert quiet.startswith('<membrain-persona version="1">\n' + QUIET + "; where the user's preferences differ, "
                                "follow the user.\nVoice: register ")
        assert all(word not in quiet for word in ("Traits:", "Values:", "Baseline mood"))
        assert len(quiet) <= 230 and len(quiet) / len(full) < 0.34, (preset["id"], len(quiet), len(full))
    # What the user agreed to stays: a voice change and an added value, kept on a type's card by a switch.
    card = with_agreements(persona_presets.card("intj"), [
        {"changes": {"voice": {"length": "one to three sentences unless the user asks for detail"},
                     "values": ["Walks the user through database migrations step by step"]}}])
    quiet = render_manner({"version": 4, "card": card, "preset": "intj"})
    assert "length one to three sentences unless the user asks for detail" in quiet
    assert "\nValues: Walks the user through database migrations step by step\n" in quiet
    assert "Listens first" not in quiet  # The type's own value waits for a casual exchange.
    # A card edited from a type is compared with that type; a card of no type is shown whole but for its mood.
    edited = {**card, "traits": [*card["traits"], "patient"]}
    assert "\nTraits: patient\n" in render_manner({"version": 5, "card": edited, "based_on": "intj"})
    own = render_manner({"version": 2, "card": {**card, "baseline_mood": {"label": "calm", "valence": 0,
                                                                         "energy": 1}}})
    assert "Traits: reserved; imaginative; logical; organised" in own and "Baseline mood" not in own
    assert render_manner(None) is None and render_manner({"version": 0, "card": card}) is None


def bond(**extra):
    return {"familiarity": {"level": "familiar", "reason": "familiar: 20 days of conversation since 1 Mar, 2 shared "
                                                           "moments"},
            "boundaries": [], "shared_moments": [{"id": "m1", "text": "Laughed at a pun.", "recorded_at":
                                                  "2026-09-01T10:00:00Z"}],
            "commitments": {"missed": []}, "today": "2026-09-12", **extra}


def test_the_quiet_relationship_keeps_only_the_boundaries_and_missed_promises():
    assert relationship_context(bond(), quiet=True)["block"] is None  # Familiarity and moments wait.
    boundary = {"id": "b1", "topic": "my ex", "aliases": []}
    missed = {"note_id": "n1", "text": "I'll check the migration on Friday.", "due": "2026-09-11"}
    quiet = relationship_context(bond(boundaries=[boundary], commitments={"missed": [missed]}), quiet=True)
    assert quiet["block"] == (
        "<membrain-relationship>\nBoundaries: topics the user asked you not to bring up. Do not raise them, or "
        "anything recalled about them, unless the user does: my ex.\nA promise you made is past its date and not "
        "done (shown once): I'll check the migration on Friday. (due 2026-09-11, id: n1). Acknowledge it briefly if "
        "it fits, and update its note when it is done or dropped.\n</membrain-relationship>")
    assert quiet["once"] == ["n1"]
    full = relationship_context(bond(boundaries=[boundary]))["block"]
    assert FAMILIARITY in full and "Laughed at a pun." in full  # A chat host's block is as before.


def test_the_companion_update_sends_the_companion_blocks_without_the_notes():
    persona = {"version": 3, "card": persona_presets.card("enfp"), "preset": "enfp"}
    notes = {"items": [{"event_id": "n1", "text": "[preference] Prefers pnpm over npm.", "recorded_at":
                        "2026-09-01T10:00:00Z", "sequence": 1}]}
    current = snapshot(notes, brain_id="b", tools=None, persona=persona, relationship=bond())
    quiet = snapshot(notes, brain_id="b", tools=None, persona=persona, relationship=bond(), quiet=True)
    assert quiet["fingerprint"] != current["fingerprint"] and "Prefers pnpm" in quiet["text"]
    assert "Laughed at a pun." not in quiet["text"] and FAMILIARITY not in quiet["text"]
    update = companion_update(current, ("The user's last conversation with you was 9 days ago (3 September).",))
    assert update.startswith(LEAD + "\n" + COMPANION + " The user's last conversation")
    assert render_persona(persona) in update and FAMILIARITY in update and "Prefers pnpm" not in update


def test_a_companion_tool_marks_only_a_session_it_names(tmp_path):
    host.companion_tool_used(tmp_path, "not a capture")
    host.companion_tool_used(tmp_path, "a" * 32 + "." + "b" * 64 + "." + "c" * 32)  # No such session: nothing.
    assert not (host.state_directory(tmp_path) / "sessions" / ("a" * 32 + ".json")).exists()


# Through the plugin's hooks, on a real service ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def worlds(tmp_path_factory):
    opened = {}
    with (built_world(tmp_path_factory, "first_coding") as opened["first_coding"],
          built_world(tmp_path_factory, "first_casual") as opened["first_casual"],
          built_world(tmp_path_factory, "returning") as opened["returning"],
          built_world(tmp_path_factory, "tool_mark") as opened["tool_mark"],
          built_world(tmp_path_factory, "agreements") as opened["agreements"]):
        yield opened


def prompts(world, session):
    return [entry["user_prompt"] or "" for entry in world.captures["sessions"][session]["prompts"]]


def start(world, session):
    return world.captures["sessions"][session]["session_start"] or ""


def persona_block(text):
    begin = text.index("<membrain-persona ")
    return text[begin:text.index("</membrain-persona>", begin) + len("</membrain-persona>")]


def test_a_new_users_first_coding_session_has_no_introduction_and_only_the_quiet_form(worlds):
    world = worlds["first_coding"]
    opening = start(world, "coding-day1")
    assert INTRO not in opening and QUIET in opening and FULL not in opening
    assert all(word not in opening for word in ("Traits:", "Baseline mood", "<membrain-relationship>", MOOD))
    assert len(persona_block(opening)) <= 230
    for context in prompts(world, "coding-day1"):
        assert all(word not in context for word in (LEAD, INTRO, FULL, FAMILIARITY)), context
    assert QUIET in prompts(world, "coding-day1")[1]  # The refresh after the first note keeps the quiet form.
    with world.client() as client:
        persona = client.persona()  # The type was still picked and saved: only the introduction is not handed.
    assert persona["version"] == 1 and persona["preset"] in persona_presets.IDS


def test_a_casual_opener_brings_the_whole_companion_and_the_introduction_once(worlds):
    world = worlds["first_casual"]
    assert QUIET in start(world, "casual-day1") and INTRO not in start(world, "casual-day1")
    first, second = prompts(world, "casual-day1")
    assert first.count(LEAD) == 1 and FULL in first and first.count(INTRO) == 1
    assert "In your reply, mention it once" in first and "/membrain:persona" in first
    assert all(word not in second for word in (LEAD, INTRO, "<membrain-updates>"))


def test_a_mixed_session_gets_the_companion_once_at_the_long_day_and_not_before(worlds):
    world = worlds["returning"]
    opening = start(world, "mixed-day3")
    # The moment's note waits (the user's own day-1 message about the pun is history, and stays).
    moment = "Laughed together at a pun about tide pools."
    assert QUIET in opening and all(word not in opening for word in (FAMILIARITY, moment, MOOD, FULL))
    work, long_day, back = prompts(world, "mixed-day3")
    assert LEAD not in work and FULL not in work
    assert long_day.count(LEAD) == 1 and FULL in long_day and FAMILIARITY in long_day
    assert moment in long_day
    assert "<membrain-notes>" not in long_day and "<membrain-updates>" not in long_day  # The notes are not resent.
    assert all(word not in back for word in (LEAD, "<membrain-updates>", FULL))
    # A bare "thanks" in a work session stays quiet.
    assert all(LEAD not in context and FULL not in context for context in prompts(world, "work-day4"))


def test_a_return_after_a_week_is_welcomed_with_the_first_casual_message_only(worlds):
    world = worlds["returning"]
    assert ABSENCE not in start(world, "return-day12")
    greeting, work = prompts(world, "return-day12")
    assert greeting.count(LEAD) == 1 and greeting.count(ABSENCE + " 8 days ago (5 November).") == 1
    assert ABSENCE not in work and LEAD not in work


def test_the_first_casual_message_of_the_first_session_brings_the_introduction(worlds):
    world = worlds["returning"]
    hike, pun, decision = prompts(world, "chat-day1")
    assert hike.count(LEAD) == 1 and hike.count(INTRO) == 1 and FULL in hike
    assert INTRO not in pun + decision and QUIET not in pun + decision  # The session keeps the whole companion.


def test_everything_is_still_computed_and_recorded_as_before(worlds):
    with worlds["returning"].client() as client:
        relationship = client.relationship()
        versions = client.persona_versions()["versions"]
    assert relationship["familiarity"]["level"] == "getting_to_know" and len(relationship["shared_moments"]) == 1
    assert [version["action"] for version in versions] == ["preset"]


def test_a_companion_tool_used_by_the_host_brings_the_companion_with_the_next_message(worlds):
    world = worlds["tool_mark"]
    save, index, migration = prompts(world, "moment-day1")
    assert LEAD not in save and FULL not in save
    assert index.count(LEAD) == 1 or "<membrain-updates>" in index  # A new moment changes the notes too.
    assert FULL in index and "pun about tide pools" in index and INTRO not in index
    assert all(word not in migration for word in (LEAD, "<membrain-updates>"))
    assert host.session_state(world.directory, "moment-day1")["companion"]["cue"] == "tool"


def test_agreements_and_boundaries_made_in_a_work_session_are_in_the_quiet_form(worlds):
    world = worlds["agreements"]
    proposal, confirmation, boundary = world.tool_calls
    assert proposal["result"]["proposal_id"] and confirmation["result"]["status"] == "waiting_for_message"
    assert boundary["result"]["boundaries"][0]["topic"] == "my ex"
    opening = start(world, "work-day3")
    block = persona_block(opening)
    assert QUIET in block and "Values: Walks the user through database migrations step by step" in block
    assert "Boundaries: topics the user asked you not to bring up" in opening and "my ex" in opening
    assert FULL not in opening and FAMILIARITY not in opening
    assert LEAD not in prompts(world, "work-day3")[0]


# Chat hosts and role-play are unchanged ----------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["returning_openclaw", "returning_chat_bot", "returning_roleplay"])
def test_chat_hosts_and_role_play_get_the_companion_as_before(tmp_path_factory, name):
    with built_world(tmp_path_factory, name) as world:
        everything = json.dumps(world.captures, ensure_ascii=False)
        assert LEAD not in everything and QUIET not in everything
        if name == "returning_roleplay":  # The character is the persona: no card, no introduction, no absence.
            assert "<membrain-persona" not in everything and INTRO not in everything and ABSENCE not in everything
            return
        first = start(world, "chat-day1") or prompts(world, "chat-day1")[0]
        assert FULL in first and first.count(INTRO) == 1
        mixed = start(world, "mixed-day3") or prompts(world, "mixed-day3")[0]
        assert FAMILIARITY in mixed and "pun about tide pools" in mixed
        back = start(world, "return-day12") or prompts(world, "return-day12")[0]
        assert ABSENCE + " 8 days ago (5 November)." in back
