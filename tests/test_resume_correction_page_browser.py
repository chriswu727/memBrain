"""The source one click away: what the memory page shows for "said last week, corrected midway, continued today".

The page of the scenario's own installation (``resume_correction_world``), opened as ``membrain plugin ui`` opens it
(a single-use ``?code=`` link), in a real headless Chromium. The question a user asks is "why does it think local is
SQLite?": which message said it, when, and that it replaced the earlier decision. Measured, not fixed: tests pass on
today's behaviour where it is right and are strict xfails where it is wrong or missing. With ``RESUME_CORRECTION_DUMP``
set, the DOM text each test reads is written there as well, for the report.
"""
import os
import re
from pathlib import Path

import pytest
from resume_correction_world import (
    CORRECTION,
    DATE,
    DAY8_REPLY,
    DECISION,
    NOTE_CORRECTED,
    NOTE_DECISION,
    NOTE_INFERRED,
    NOTE_PNPM,
    NOTE_THIRD,
    THIRD,
    built_world,
)
from test_memory_page_browser import browser as browser
from test_memory_page_browser import open_view
from test_memory_page_browser import page as page

from membrain import host
from membrain.local_profile import load_profile

try:
    from playwright.sync_api import expect
except ImportError:  # Without Playwright the browser fixture skips (or fails when required) before this is used.
    expect = None

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def diligent(tmp_path_factory):
    with built_world(tmp_path_factory, "diligent") as world:
        yield world


@pytest.fixture(scope="module")
def lazy(tmp_path_factory):
    with built_world(tmp_path_factory, "lazy") as world:
        yield world


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    """The diligent world with a second change on day 5: decision, correction, change (A -> B -> C)."""
    with built_world(tmp_path_factory, "diligent", chain=True) as world:
        yield world


@pytest.fixture(scope="module", autouse=True)
def worlds_before_the_browser(diligent, lazy, chain):
    """Every world is played before Chromium starts: the host's MCP calls use asyncio.run, which cannot run inside
    the event loop that Playwright's sync API keeps running in this thread."""
    return diligent, lazy, chain


def dump(name: str, text: str) -> None:
    target = os.environ.get("RESUME_CORRECTION_DUMP")
    if target:
        Path(target).mkdir(parents=True, exist_ok=True)
        (Path(target) / f"page-{name}.txt").write_text(text, encoding="utf-8")


def open_page(page, world):
    """The page as `membrain plugin ui` opens it: the installation's own service, signed in by a one-time code."""
    page.goto(f"{load_profile(world.directory).base_url}/memory?code={host.issue_ui_code(world.directory)}")
    expect(page.locator("#tabs")).to_be_visible()
    expect(page.locator("#view-notes")).to_be_visible()


def corrected_note(page):
    item = page.locator("#notes article.item").filter(has_text=NOTE_CORRECTED)
    expect(item).to_have_count(1)
    return item


def sources_of(item):
    item.locator("details summary").click()
    messages = item.locator("details .message")
    expect(messages.first).to_be_visible()
    return messages


def search(page, query: str):
    open_view(page, "search")
    page.fill("#search-text", query)
    page.locator("#search-form button[type=submit]").click()
    results = page.locator("#results > *")
    expect(results.first).to_be_visible()
    return page.locator("#results")


# Notes ------------------------------------------------------------------------------------------------------------

def test_the_notes_list_shows_the_corrected_note_dated_the_day_of_the_correction(diligent, page):
    open_page(page, diligent)
    item = corrected_note(page)
    dump("notes", page.locator("#notes").inner_text())
    expect(item.locator(".meta")).to_contain_text(DATE[3])
    expect(item.locator(".meta")).to_contain_text("saved by your agent")
    expect(page.locator("#notes article.item")).to_have_count(3)
    # The replaced note is not a note of its own: it is shown only under the note that replaced it.
    expect(page.locator("#notes article.item > p.user-text").filter(has_text=NOTE_DECISION)).to_have_count(0)


def test_the_corrected_note_shows_what_it_replaced_and_when(diligent, page):
    open_page(page, diligent)
    item = corrected_note(page)
    expect(item).to_contain_text(re.compile(r"replac|correct|earlier", re.IGNORECASE), timeout=2_000)
    expect(item).to_contain_text(DATE[1], timeout=2_000)
    lineage = item.locator(".lineage")
    expect(lineage.locator("p.hint").first).to_have_text(f"Replaced an earlier note on {DATE[3]}.")
    expect(lineage.locator("p.earlier")).to_have_text(f"Earlier ({DATE[1]}): {NOTE_DECISION}")
    dump("note-lineage", item.inner_text())


def test_the_corrected_notes_original_messages_include_the_day3_correction_and_the_day1_decision(diligent, page):
    """store_note keeps a replacement's predecessor's sources as its dependencies, so the corrected note lists both
    messages: first the one it was said in, then, apart, the one the replaced note was based on."""
    open_page(page, diligent)
    item = corrected_note(page)
    expect(item.locator("details summary")).to_have_text("2 original messages")
    messages = sources_of(item)
    expect(messages).to_have_count(2)
    expect(messages.nth(1).locator(".source-conversation")).to_be_visible()
    dump("note-sources", item.inner_text())
    expect(messages.nth(0).locator(".meta")).to_have_text(f"{DATE[3]} · You")
    expect(messages.nth(0).locator(".user-text")).to_have_text(CORRECTION)
    expect(messages.nth(1).locator(".meta")).to_have_text(f"{DATE[1]} · You")
    expect(messages.nth(1).locator(".user-text")).to_have_text(DECISION)


def test_the_original_messages_say_which_one_corrected_the_other(diligent, page):
    """The messages the note was said in and those behind the note it replaced, each under its own heading."""
    open_page(page, diligent)
    item = corrected_note(page)
    sources_of(item)
    roles = item.locator("details .source-role")
    expect(roles).to_have_text([f"Said on {DATE[3]}:", "The earlier note was based on:"])
    content = item.locator("details > div")
    expect(content).to_contain_text(re.compile(
        rf"Said on {DATE[3]}:\s*{DATE[3]} · You\s*{re.escape(CORRECTION)}.*The earlier note was based on:\s*"
        rf"{DATE[1]} · You\s*{re.escape(DECISION)}", re.DOTALL))


def test_each_original_message_names_its_conversation(diligent, page):
    """As the Conversations view names it: the day it began, its size and how it began."""
    open_page(page, diligent)
    messages = sources_of(corrected_note(page))
    expect(messages.nth(0).locator(".source-conversation")).to_have_text(
        f"In the conversation: {DATE[3]} · 6 messages · {CORRECTION}")
    expect(messages.nth(1).locator(".source-conversation")).to_have_text(
        f"In the conversation: {DATE[1]} · 8 messages · {DECISION[:90]}")


@pytest.mark.xfail(strict=True, reason="A source message names its conversation ('In the conversation: …') but "
                   "cannot open it: the Conversations view lists the latest 100 messages with no address or anchor for "
                   "one conversation, so a link would need navigation the page does not have (a follow-up).")
def test_an_original_message_links_to_its_conversation(diligent, page):
    open_page(page, diligent)
    messages = sources_of(corrected_note(page))
    expect(messages.nth(1).locator("a, button")).not_to_have_count(0, timeout=2_000)


def test_a_lazy_hosts_page_has_no_notes_to_explain_anything(lazy, page):
    open_page(page, lazy)
    expect(page.locator("#notes .empty")).to_have_text(
        "No notes yet. Tell your agent what to remember, and it will keep it here.")


# How much it knows ------------------------------------------------------------------------------------------------

def test_a_preference_said_on_three_days_shows_one_original_message_like_a_decision_said_once(diligent, page):
    open_page(page, diligent)
    repeated = page.locator("#notes article.item").filter(has_text=NOTE_PNPM)
    expect(repeated.locator(".meta")).to_have_text(re.compile(rf"^{DATE[1]}saved by your agentpreferenceDelete$"))
    expect(repeated.locator("details summary")).to_have_text("1 original message")


@pytest.mark.xfail(strict=True, reason="A note links the messages the host named when saving it; the repeats on days "
                   "3 and 5 were never linked (the host had nothing new to save), so the page cannot show that the "
                   "preference was said three times.")
def test_a_preference_said_on_three_days_shows_all_three_messages(diligent, page):
    open_page(page, diligent)
    repeated = page.locator("#notes article.item").filter(has_text=NOTE_PNPM)
    expect(repeated.locator("details summary")).to_have_text("3 original messages", timeout=2_000)


def test_the_feeling_on_the_inferred_note_is_marked_inferred_in_feelings(diligent, page):
    open_page(page, diligent)
    open_view(page, "feelings")
    feeling = page.locator("#feelings article.feeling")
    expect(feeling).to_have_count(1)
    dump("feelings", feeling.inner_text())
    expect(feeling.locator(".feeling-basis")).to_have_text("inferred")
    expect(feeling).to_contain_text("Your agent inferred this from what you wrote; you did not say it.")
    expect(feeling).to_contain_text(NOTE_INFERRED)


@pytest.mark.xfail(strict=True, reason="The Notes view tags a note with who saved it and its kind (memory.js "
                   "noteItem); the inferred fact reads 'saved by your agent · constraint', exactly like stated facts, "
                   "and its inferred feeling is shown only under Feelings.")
def test_the_inferred_note_is_marked_inferred_in_notes(diligent, page):
    open_page(page, diligent)
    inferred = page.locator("#notes article.item").filter(has_text=NOTE_INFERRED)
    expect(inferred.locator(".meta")).to_contain_text("inferred", timeout=2_000)


# Search -----------------------------------------------------------------------------------------------------------

def test_search_finds_both_messages_dated_and_does_not_list_the_note(diligent, page):
    open_page(page, diligent)
    results = search(page, "PostgreSQL")
    dump("search-postgresql", results.inner_text())
    decision = results.locator(".item").filter(has_text=DECISION)
    correction = results.locator(".item").filter(has_text=CORRECTION)
    expect(decision.locator(".meta")).to_have_text(f"{DATE[1]}You")
    expect(correction.locator(".meta")).to_have_text(f"{DATE[3]}You")
    # The corrected note is not a search result: recall is over messages, and the note's sentence is not shown.
    expect(results).not_to_contain_text(NOTE_CORRECTED)


def test_search_marks_the_day1_decision_as_replaced_by_the_day3_correction(diligent, page):
    open_page(page, diligent)
    results = search(page, "PostgreSQL")
    expect(results.locator(".item").filter(has_text=DECISION)).to_contain_text(
        re.compile(r"replac|correct|supersed", re.IGNORECASE), timeout=2_000)
    expect(results.locator(".item").filter(has_text=DECISION).locator(".superseded")).to_have_text(
        f"Superseded by a note saved on {DATE[3]}.")
    expect(results.locator(".item").filter(has_text=CORRECTION).locator(".superseded")).to_have_count(0)


def test_on_a_lazy_hosts_page_search_is_the_only_way_to_the_correction(lazy, page):
    open_page(page, lazy)
    results = search(page, "local SQLite")
    dump("search-lazy-local-sqlite", results.inner_text())
    expect(results.locator(".item").filter(has_text=CORRECTION).locator(".meta")).to_have_text(f"{DATE[3]}You")


# Brain map --------------------------------------------------------------------------------------------------------

def test_the_brain_map_links_the_corrected_note_to_both_messages_and_has_no_replaced_note(diligent, page):
    open_page(page, diligent)
    open_view(page, "brain")
    page.locator("#mode-2d").click()
    note = page.locator(f'#brain-canvas circle.brain-node[data-id="note:{diligent.note_ids["corrected"]}"]')
    note.click()
    detail = page.locator("#brain-detail")
    # The map's labels are cut at 80 characters, with an ellipsis that says so (memory_map._label).
    expect(detail.locator("p.user-text").first).to_have_text(NOTE_CORRECTED[:79] + "…")
    dump("brain-detail", detail.inner_text())
    expect(detail).to_contain_text(f"Saved: {DATE[3]}")
    links = detail.locator(".brain-links li")
    expect(links).to_have_count(2)
    # The day-1 message is the basis of the note it replaced, not of this one.
    expect(links.filter(has_text=DECISION[:40])).to_contain_text("earlier note based on:")
    expect(links.filter(has_text=CORRECTION[:40])).to_contain_text("derived from:")
    expect(page.locator(f'#brain-canvas circle.brain-node[data-id="note:{diligent.note_ids["decision"]}"]')
           ).to_have_count(0)


def test_the_brain_map_shows_the_corrected_note_replacing_the_decision(diligent, page):
    """As a line of the note's detail, read from the replaced note: it is not current, so it has no dot."""
    open_page(page, diligent)
    open_view(page, "brain")
    page.locator("#mode-2d").click()
    page.locator(f'#brain-canvas circle.brain-node[data-id="note:{diligent.note_ids["corrected"]}"]').click()
    expect(page.locator("#brain-detail")).to_contain_text(re.compile(r"replac", re.IGNORECASE), timeout=2_000)
    expect(page.locator("#brain-detail .brain-replaces")).to_have_text(f"replaces: {NOTE_DECISION} Saved: {DATE[1]}")


def test_the_brain_map_lights_only_the_last_search(diligent, page):
    """The trace is the latest message recall the service recorded, here the diligent host's last memory_recall
    ("which database"); the notes and history a session starts with are never traced."""
    open_page(page, diligent)
    open_view(page, "brain")
    trace = page.locator("#brain-trace")
    expect(trace).to_have_text(re.compile(r"^Latest recorded recall \(.+\): \d+ of \d+ records it used are lit\.$"))
    dump("brain-trace", trace.inner_text())


# Conversations ----------------------------------------------------------------------------------------------------

def test_conversations_show_the_decision_and_the_correction_in_their_own_days(diligent, page):
    open_page(page, diligent)
    open_view(page, "conversations")
    conversations = page.locator("#conversations > details.item")
    expect(conversations.first).to_be_visible()
    day1 = conversations.filter(has_text=f"{DATE[1]} · ")
    day3 = conversations.filter(has_text=f"{DATE[3]} · ")  # The summary: a mark names a later day too
    expect(day1).to_have_count(1)
    expect(day3).to_have_count(1)
    for item in (day1, day3):
        item.locator("summary").click()
    dump("conversations", page.locator("#conversations").inner_text())
    expect(day1.locator(".message.user").filter(has_text=DECISION)).to_have_count(1)
    expect(day3.locator(".message.user").filter(has_text=CORRECTION)).to_have_count(1)


def test_conversations_mark_the_decision_as_corrected_later(diligent, page):
    open_page(page, diligent)
    open_view(page, "conversations")
    day1 = page.locator("#conversations > details.item").filter(has_text=DATE[1])
    day1.locator("summary").click()
    expect(day1.locator(".message.user").filter(has_text=DECISION)).to_contain_text(
        re.compile(r"replac|correct|supersed", re.IGNORECASE), timeout=2_000)


@pytest.mark.xfail(strict=True, reason="The day-8 reply is stored as text only: no record of the notes, history or "
                   "recall it was given, so the page cannot go from a reply to its basis (the brain trace covers the "
                   "last search only, not the reply).")
def test_the_day8_reply_links_to_its_basis(diligent, page):
    open_page(page, diligent)
    open_view(page, "conversations")
    day8 = page.locator("#conversations > details.item").filter(has_text=DATE[8])
    day8.first.locator("summary").click()
    reply = page.locator("#conversations .message.assistant").filter(has_text=DAY8_REPLY)
    expect(reply).to_have_count(1)
    expect(reply).to_contain_text(re.compile(r"based on|basis|source", re.IGNORECASE), timeout=2_000)


# A chain: decision, correction, a second change (A -> B -> C) ------------------------------------------------------

def test_a_chain_shows_every_earlier_note_newest_first_under_the_current_one(chain, page):
    open_page(page, chain)
    expect(page.locator("#notes article.item")).to_have_count(3)
    item = page.locator("#notes article.item").filter(has_text=NOTE_THIRD)
    expect(item).to_have_count(1)
    expect(item.locator(".lineage p.earlier")).to_have_text([f"Earlier ({DATE[3]}): {NOTE_CORRECTED}",
                                                             f"Earlier ({DATE[1]}): {NOTE_DECISION}"])
    sources_of(item)
    expect(item.locator("details .source-role")).to_have_text([f"Said on {DATE[5]}:",
                                                               "The earlier notes were based on:"])
    expect(item.locator("details .message .user-text")).to_have_text([THIRD, DECISION, CORRECTION])
    dump("chain-note", item.inner_text())
    # Both earlier messages are marked as superseded by the current note.
    open_view(page, "conversations")
    for day, text in ((DATE[1], DECISION), (DATE[3], CORRECTION)):
        conversation = page.locator("#conversations > details.item").filter(has_text=f"{day} · ").filter(
            has_text=text[:30])
        conversation.first.locator("summary").click()
        expect(conversation.first.locator(".message.user").filter(has_text=text).locator(".superseded")).to_have_text(
            f"Superseded by a note saved on {DATE[5]}.")


def test_the_lineage_is_in_chinese_too(diligent, page):
    base = load_profile(diligent.directory).base_url
    page.goto(f"{base}/memory?lang=zh&code={host.issue_ui_code(diligent.directory)}")
    item = page.locator("#notes article.item").filter(has_text=NOTE_CORRECTED)
    expect(item.locator(".lineage p.hint").first).to_have_text(f"{DATE[3]} 取代了一条较早的笔记。")
    expect(item.locator(".lineage p.earlier")).to_have_text(f"较早（{DATE[1]}）： {NOTE_DECISION}")
    sources_of(item)
    expect(item.locator("details .source-role")).to_have_text([f"出自 {DATE[3]} 的消息：", "被取代的笔记依据的消息："])
    page.goto(f"{base}/memory?lang=en&code={host.issue_ui_code(diligent.directory)}")  # Leave the page in English.
    expect(page.locator("#tabs")).to_be_visible()


def test_deleting_the_current_note_on_the_page_deletes_what_it_replaced_and_every_mark(chain, page):
    """Last in this module: it changes the chain world. The page asks before deleting both."""
    open_page(page, chain)
    item = page.locator("#notes article.item").filter(has_text=NOTE_THIRD)
    questions = []
    page.once("dialog", lambda dialog: (questions.append(dialog.message), dialog.accept()))
    item.locator("button", has_text="Delete").click()
    expect(page.locator("#notes article.item").filter(has_text="Tidepool database")).to_have_count(0)
    assert questions == ["Delete this note and the earlier notes it replaced? Their content is erased."]
    expect(page.locator("#notes")).not_to_contain_text("PostgreSQL")
    open_view(page, "conversations")
    expect(page.locator("#conversations > details.item").first).to_be_visible()
    expect(page.locator("#conversations .superseded")).to_have_count(0)
    with chain.client() as client:
        notes = client.timeline(roles=("user", "assistant"), conversation_id="membrain-notes", limit=1000)["items"]
        export = client.download_archive(client.export()["result"]["archive_id"])
    assert not [note for note in notes if "Tidepool database" in note["text"]]
    text = str(export)
    assert NOTE_DECISION not in text and NOTE_CORRECTED not in text and NOTE_THIRD not in text
