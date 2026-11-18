"""Said last week, corrected midway, continued today: what the host receives on day 8, measured, not fixed.

The scenario (an outside review's, and the next user-facing delivery): on day 1 the user and the agent decide to use
PostgreSQL for the Tidepool project; on day 3, in another conversation, the user corrects it ("only the server uses
PostgreSQL; local stays SQLite"); on day 8 a new session, with nothing in its context, opens with "finish the local
install" (or "set up my dev machine", or the same request in Chinese). The agent should go ahead on SQLite without the
user explaining again, never bring back "PostgreSQL everywhere", and the user should be able to see the basis.

Played on a real local installation through the plugin's hooks and MCP tools, on the scenario clock, with no model
(``resume_correction_world``). The host's part is played twice: a diligent host that saves and replaces notes, indexes
messages when asked and searches; and a lazy host that calls no memBrain tool. A short history (only the scenario's
messages, as in a user's first week) and a busy one (thirty more messages of other project talk on days 4, 6 and 7)
are both measured, the busy one with keyword recall only (a fresh installation before the embedding model arrives)
and with the local embedding model.

Tests pass where today's behaviour is right. Where it is wrong or missing they are strict xfails naming why, so a
change that fixes one turns it into a failure that has to be looked at. Whether a host model then answers correctly
from what it receives is not measured here: that needs a model in the loop.
"""
import re

import pytest
from resume_correction_world import (
    CORRECTION,
    DATE,
    DECISION,
    DISK,
    NOTE_CORRECTED,
    NOTE_DECISION,
    NOTE_INFERRED,
    NOTE_PNPM,
    PNPM,
    PROMPTS,
    QUERIES,
    block,
    built_world,
    history_lines,
    note_lines,
    received,
)

pytestmark = pytest.mark.integration

CLAUDE_CODE_HOOK_LIMIT = 10_000  # Characters of additionalContext Claude Code keeps from one hook.
VARIANTS = list(PROMPTS)


@pytest.fixture(scope="module")
def diligent(tmp_path_factory):
    with built_world(tmp_path_factory, "diligent") as world:
        yield world


@pytest.fixture(scope="module")
def lazy(tmp_path_factory):
    with built_world(tmp_path_factory, "lazy") as world:
        yield world


@pytest.fixture(scope="module")
def lazy_busy_keywords(tmp_path_factory):
    with built_world(tmp_path_factory, "lazy", busy=True) as world:
        yield world


@pytest.fixture(scope="module")
def lazy_busy(tmp_path_factory):
    with built_world(tmp_path_factory, "lazy", busy=True, model=True) as world:
        yield world


@pytest.fixture(scope="module")
def diligent_busy(tmp_path_factory):
    with built_world(tmp_path_factory, "diligent", busy=True, model=True) as world:
        yield world


WORLDS = ["diligent", "lazy", "lazy_busy_keywords", "lazy_busy", "diligent_busy"]


@pytest.fixture
def world(request):
    return request.getfixturevalue(request.param)


def line_with(lines, text):
    found = [line for line in lines if text in line]
    return found[0] if found else None


def memory_lines(text):
    return [line for line in block(text, "membrain-memory").splitlines() if line.startswith("- [")]


def stated(line):
    """A note line without its feeling phrases, which carry their own basis."""
    return re.sub(r" \((the user said they felt|seemed) [^)]*\)", "", line)


# 1. The diligent host: the correction arrives in the notes, unasked ------------------------------------------------

@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("world", ["diligent", "diligent_busy"], indirect=True)
def test_the_corrected_note_reaches_every_new_session_unasked_and_the_replaced_one_does_not(world, variant):
    opening = world.captures["day8"][variant]["session_start"]
    lines = note_lines(opening)
    corrected = line_with(lines, NOTE_CORRECTED)
    assert corrected and corrected.startswith(f"- [{DATE[3]}]")
    assert world.note_ids["corrected"] in corrected  # The note's id, which memory_note's replaces takes.
    assert NOTE_DECISION not in received(world.captures["day8"][variant])
    assert [line for line in lines if "PostgreSQL" in line] == [corrected]


@pytest.mark.parametrize("world", ["diligent", "diligent_busy"], indirect=True)
def test_the_corrected_note_says_it_replaced_the_day1_decision_and_when(world):
    """The day of the note it replaced, read from the replaced record; never the old sentence."""
    corrected = line_with(note_lines(world.captures["day8"]["finish"]["session_start"]), NOTE_CORRECTED)
    assert re.search(r"replac|correct|supersed|instead of", corrected, re.IGNORECASE) and DATE[1] in corrected
    assert corrected == (f"- [{DATE[3]}] {NOTE_CORRECTED} (replaces your note of {DATE[1]}) "
                         f"(id: {world.note_ids['corrected']})")


def test_a_note_is_dated_by_when_it_was_saved_not_by_the_message_it_came_from(diligent):
    """Here the host saved each note in the turn the user said it, so the two dates agree. A note saved later from
    recorded history (source_event_ids) would carry the later date; nothing on the line gives the message's date."""
    lines = note_lines(diligent.captures["day8"]["finish"]["session_start"])
    notes = {item["event_id"]: item for item in diligent.notes()}
    for key, text in (("corrected", NOTE_CORRECTED), ("pnpm", NOTE_PNPM), ("inferred", NOTE_INFERRED)):
        saved = notes[diligent.note_ids[key]]["recorded_at"][:10]
        assert line_with(lines, text).startswith(f"- [{saved}]")


# 2. How much it knows: said once, said three times, inferred ------------------------------------------------------

def test_a_decision_said_once_and_a_preference_said_on_three_days_look_alike_in_the_notes(diligent):
    lines = note_lines(diligent.captures["day8"]["finish"]["session_start"])
    once, repeated = line_with(lines, NOTE_CORRECTED), line_with(lines, NOTE_PNPM)
    shape = re.compile(r"^- \[\d{4}-\d{2}-\d{2}\] .+ \(id: [0-9a-f-]{36}\)$")
    assert shape.match(once) and shape.match(repeated)
    assert repeated.startswith(f"- [{DATE[1]}]")  # The first day only: the repeats on days 3 and 5 left no trace.


@pytest.mark.xfail(strict=True, reason="Notes carry no count of times said and no first or last date: the diligent "
                   "host saw its own pnpm note on days 3 and 5 and, as instructed, saved nothing new, so the notes block "
                   "cannot tell a preference repeated on three days from a decision said once.")
def test_a_preference_said_on_three_days_is_shown_as_repeated(diligent):
    repeated = line_with(note_lines(diligent.captures["day8"]["finish"]["session_start"]), NOTE_PNPM)
    assert re.search(r"3 times|three|repeated", repeated) or (DATE[3] in repeated and DATE[5] in repeated)


def test_only_a_feeling_says_it_was_inferred(diligent):
    line = line_with(note_lines(diligent.captures["day8"]["finish"]["session_start"]), NOTE_INFERRED)
    assert "(seemed frustrated, inferred, 2 Nov)" in line


@pytest.mark.xfail(strict=True, reason="memory_note has no basis field for the fact itself (only affect.basis), so a "
                   "fact the host inferred ('keep local installs light') is shown exactly like one the user stated. "
                   "NOTE_TOOL_DESCRIPTION forbids noting what the user did not state; nothing records it when a host "
                   "does.")
def test_a_note_the_host_inferred_is_marked_as_inferred(diligent):
    line = line_with(note_lines(diligent.captures["day8"]["finish"]["session_start"]), NOTE_INFERRED)
    assert "inferred" in stated(line)


def test_the_short_history_shows_each_time_the_preference_was_said_with_its_date(diligent):
    lines = history_lines(diligent.captures["day8"]["finish"]["session_start"])
    for day in (1, 3, 5):
        assert line_with(lines, PNPM[day]).startswith(f"- [{DATE[day]}]")


# 3. Raw history: both messages, dated, oldest first, and nothing linking them ------------------------------------

@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("world", ["diligent", "lazy"], indirect=True)
def test_a_short_history_is_given_whole_with_both_messages_dated_and_the_correction_last(world, variant):
    capture = world.captures["day8"][variant]
    opening = capture["session_start"]
    assert opening.startswith("memBrain memory is active for this user. Their complete history from earlier sessions "
                              "is below.")
    lines = history_lines(opening)
    decision, correction = line_with(lines, DECISION), line_with(lines, CORRECTION)
    # With a note that replaced the decision's note, the decision says so; a lazy host's history has no notes.
    mark = f" · superseded by your note of {DATE[3]}" if world.host_kind == "diligent" else ""
    assert decision == f"- [{DATE[1]}{mark}] {DECISION}" and correction == f"- [{DATE[3]}] {CORRECTION}"
    assert lines.index(decision) < lines.index(correction)
    # With the whole history in the session, the prompt hook adds no recall: only the note-source block.
    assert block(capture["user_prompt"], "membrain-memory") == ""
    assert re.fullmatch(r"<membrain-source>.*</membrain-source>", capture["user_prompt"], re.DOTALL)


@pytest.mark.parametrize("world", [
    "diligent", "diligent_busy",
    *(pytest.param(world, marks=pytest.mark.xfail(strict=True, reason=(
        "A lazy host saves no notes, so no note replaced the decision: a message is marked only when a current note "
        "overruled it (note_lineage.superseded), never by reading its text. Only the order and a generic header "
        "sentence tell this host the day-1 decision was corrected."))) for world in ("lazy", "lazy_busy_keywords",
                                                                                   "lazy_busy"))], indirect=True)
def test_the_earlier_decision_is_marked_as_superseded_wherever_it_is_shown(world):
    shown = [line for capture in world.captures["day8"].values()
             for line in history_lines(capture["session_start"]) + memory_lines(capture["user_prompt"])
             if DECISION in line]
    shown += [line for context in world.captures["recall"].values() for line in memory_lines(context)
              if DECISION in line]
    assert shown and all(re.search(r"supersed|correct|replac", line, re.IGNORECASE) for line in shown)


@pytest.mark.parametrize("world", ["lazy", "lazy_busy_keywords", "lazy_busy"], indirect=True)
def test_a_lazy_host_gets_no_notes_at_all(world):
    for capture in world.captures["day8"].values():
        assert "<membrain-notes>" not in received(capture)
    assert world.notes() == []


# 4. A busy week: the history block no longer reaches day 1 or day 3 ----------------------------------------------

@pytest.mark.parametrize("world", ["lazy_busy_keywords", "lazy_busy", "diligent_busy"], indirect=True)
def test_after_a_busy_week_the_session_history_holds_neither_message(world):
    for capture in world.captures["day8"].values():
        opening = capture["session_start"]
        assert "most recent messages this user wrote in earlier sessions" in opening
        lines = history_lines(opening)
        assert line_with(lines, DECISION) is None and line_with(lines, CORRECTION) is None


# What the prompt hook recalls for each wording, by world: True where the day-3 correction arrives unasked.
CORRECTION_RECALLED = {
    ("lazy_busy_keywords", "finish"): True, ("lazy_busy_keywords", "dev_machine"): False,
    ("lazy_busy_keywords", "chinese"): False,
    ("lazy_busy", "finish"): True, ("lazy_busy", "dev_machine"): True, ("lazy_busy", "chinese"): True,
    ("diligent_busy", "finish"): True, ("diligent_busy", "dev_machine"): True, ("diligent_busy", "chinese"): True,
}
MISSES = {key for key, value in CORRECTION_RECALLED.items() if not value}


@pytest.mark.parametrize(("world", "variant"), [
    pytest.param(world, variant, marks=pytest.mark.xfail(strict=True, reason=(
        "Keyword recall only (no embedding model yet): the wording shares no word with the correction, and no "
        "note exists for a lazy host, so the correction does not reach this session.")) if (world, variant) in MISSES
        else ()) for world, variant in CORRECTION_RECALLED], indirect=["world"])
def test_after_a_busy_week_the_prompt_hook_recalls_the_correction_with_its_date(world, variant):
    lines = memory_lines(world.captures["day8"][variant]["user_prompt"])
    assert line_with(lines, CORRECTION) == f"- [{DATE[3]} · user said] {CORRECTION}"


@pytest.mark.parametrize("world", ["lazy_busy_keywords", "lazy_busy"], indirect=True)
def test_a_lazy_host_is_asked_on_day8_to_index_what_it_never_indexed(world):
    """The cue phrases that help keyword recall come from the host (memory_consolidate); a host that ignores the
    request leaves every earlier message unindexed."""
    notice = block(world.captures["day8"]["finish"]["session_start"], "notice")
    found = re.search(r"(\d+) earlier messages have not been indexed by memory yet", notice)
    assert found and int(found.group(1)) >= 39


@pytest.mark.parametrize("world", ["lazy_busy_keywords", "lazy_busy", "diligent_busy"], indirect=True)
def test_when_both_messages_are_recalled_the_correction_comes_after_the_decision(world):
    for capture in world.captures["day8"].values():
        lines = memory_lines(capture["user_prompt"])
        decision, correction = line_with(lines, DECISION), line_with(lines, CORRECTION)
        if decision and correction:
            assert re.match(rf"- \[{DATE[1]} · user said( · superseded by your note of {DATE[3]})?\] ", decision)
            assert lines.index(decision) < lines.index(correction)


def test_a_diligent_host_after_a_busy_week_is_shown_the_stale_decision_beside_the_corrected_note(diligent_busy):
    """The notes block holds the corrected note; the prompt's recall, below it, holds the day-1 message as well."""
    capture = diligent_busy.captures["day8"]["finish"]
    assert line_with(note_lines(capture["session_start"]), NOTE_CORRECTED)
    assert line_with(memory_lines(capture["user_prompt"]), DECISION)


# 5. memory_recall, as a diligent host would search ------------------------------------------------------------------

@pytest.mark.parametrize("query", QUERIES)
@pytest.mark.parametrize("world", WORLDS, indirect=True)
def test_a_search_finds_the_correction_with_its_date(world, query):
    assert line_with(memory_lines(world.captures["recall"][query]), CORRECTION) == (
        f"- [{DATE[3]} · user said] {CORRECTION}")


@pytest.mark.parametrize("world", WORLDS, indirect=True)
def test_a_search_for_the_database_also_returns_the_stale_decision_first(world):
    lines = memory_lines(world.captures["recall"]["which database"])
    decision, correction = line_with(lines, DECISION), line_with(lines, CORRECTION)
    assert decision and lines.index(decision) < lines.index(correction)


@pytest.mark.parametrize("world", ["diligent", "diligent_busy"], indirect=True)
def test_a_search_for_the_database_returns_the_current_note(world):
    """It comes first, marked as a note with its date and id; the messages follow, the stale one marked."""
    context = world.captures["recall"]["which database"]
    assert NOTE_CORRECTED in context
    lines = memory_lines(context)
    assert lines[0] == (f"- [{DATE[3]} · note] {NOTE_CORRECTED} (replaces your note of {DATE[1]}) "
                        f"(id: {world.note_ids['corrected']})")
    assert NOTE_DECISION not in context
    assert line_with(lines, DECISION).startswith(f"- [{DATE[1]} · user said · superseded by your note of {DATE[3]}] ")


@pytest.mark.parametrize("world", ["lazy", "lazy_busy_keywords", "lazy_busy"], indirect=True)
def test_a_lazy_hosts_search_has_no_note_and_marks_nothing(world):
    for context in world.captures["recall"].values():
        assert " · note] " not in context and "superseded" not in context


def test_search_results_with_ids_name_the_message_and_its_date(diligent):
    records = diligent.captures["recall_records"]["which database"]
    by_text = {record["text"]: record for record in records}
    messages = diligent.messages()
    assert by_text[CORRECTION]["event_id"] == messages[CORRECTION]["event_id"]
    assert (by_text[CORRECTION]["recorded_at"], by_text[DECISION]["recorded_at"]) == (DATE[3], DATE[1])
    assert by_text[CORRECTION]["conversation_id"] == "tidepool-day3"


# 6. What the host could cite: ids and dates, no link ---------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Nothing the host receives links to the memory page: notes carry a note id and "
                   "a date, recall lines a date, and the page has no address for one note or message (memory.js reads "
                   "only ?code, ?demo, ?show and ?lang), so a reply cannot point the user to its basis.")
@pytest.mark.parametrize("world", ["diligent", "lazy"], indirect=True)
def test_the_host_receives_a_link_to_the_basis_it_can_give_the_user(world):
    everything = received(world.captures["day8"]["finish"]) + "".join(world.captures["recall"].values())
    assert re.search(r"https?://|/memory", everything)


# 7. Cost ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("world", WORLDS, indirect=True)
def test_every_hook_stays_within_claude_codes_limit(world):
    for capture in world.captures["day8"].values():
        assert len(capture["session_start"]) <= 9_500
        assert len(capture["user_prompt"] or "") <= CLAUDE_CODE_HOOK_LIMIT


def test_the_notes_block_costs_under_two_thousand_characters_for_three_notes(diligent):
    notes = block(diligent.captures["day8"]["finish"]["session_start"], "membrain-notes")
    assert 1_000 < len(notes) < 2_000
    assert DISK not in notes  # The notes hold the host's summaries, never the user's words.
