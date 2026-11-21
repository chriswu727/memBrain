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

# A conversation is named by its first message, shortened to 90 characters between two words (memory.js shorten).
DECISION_SHOWN = "Let's get the Tidepool backend going today. Decision: we'll use PostgreSQL as the…"


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
        f"In the conversation: {DATE[1]} · 8 messages · {DECISION_SHOWN}")


def test_an_original_message_links_to_its_conversation(diligent, page):
    """Each source line under a note opens the Conversations view at that message, in its own conversation."""
    open_page(page, diligent)
    ids = diligent.messages()
    for text, conversation in ((DECISION, "tidepool-day1"), (CORRECTION, "tidepool-day3")):
        open_view(page, "notes")  # Choosing a tab leaves the address the last link set.
        assert "#" not in page.url
        link = sources_of(corrected_note(page)).filter(has_text=text).locator("a.source-conversation")
        expect(link).to_have_attribute("href", f"#message={ids[text]['event_id']}")
        link.click()
        expect(page.locator("#view-conversations")).to_be_visible()
        assert page.url.endswith(f"/memory#message={ids[text]['event_id']}")
        opened = page.locator("#conversations > details.item").first
        expect(opened).to_have_attribute("open", "")
        expect(opened).to_have_attribute("data-conversation", conversation)
        expect(page.locator("#conversations .addressed")).to_have_count(1)
        expect(opened.locator(".message.addressed > p.user-text")).to_have_text(text)
        # The conversation is shown once, whole, not again among the latest messages.
        expect(page.locator(f'#conversations > details.item[data-conversation="{conversation}"]')).to_have_count(1)
    dump("source-to-conversation", page.locator("#conversations > details.item").first.inner_text())


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
    # The corrected note is not a search result: recall is over messages. Since 2026-11-19 each message names the
    # notes that rest on it, as a link to the note: both messages lead to the corrected note.
    expect(results.locator(":scope > .item > p.user-text").filter(has_text=NOTE_CORRECTED)).to_have_count(0)
    for item in (decision, correction):
        expect(item.locator(".rests-on a.note-link")).to_have_text(NOTE_CORRECTED)


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
    # The map's labels are cut at 80 characters between words, with an ellipsis that says so (memory_map.label).
    expect(detail.locator("p.user-text").first).to_have_text(
        "Tidepool database: PostgreSQL on the server only; local development stays on…")
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
                   "recall it was given, so the stored reply leads nowhere (the brain trace covers the last search "
                   "only). The way from a reply to its basis is the host's: it runs `membrain plugin ui --note <id>` "
                   "with the note it used, which opens the page at that note (tests below).")
def test_the_day8_reply_links_to_its_basis(diligent, page):
    open_page(page, diligent)
    open_view(page, "conversations")
    day8 = page.locator("#conversations > details.item").filter(has_text=DATE[8])
    day8.first.locator("summary").click()
    reply = page.locator("#conversations .message.assistant").filter(has_text=DAY8_REPLY)
    expect(reply).to_have_count(1)
    expect(reply).to_contain_text(re.compile(r"based on|basis|source", re.IGNORECASE), timeout=2_000)


# Addresses: from a reply to its basis ------------------------------------------------------------------------------
# The host has the note's id (on its note line); `membrain plugin ui --note <id>` opens /memory?code=…#note=<id>.

GONE = "This item is no longer here."


def open_at(page, world, fragment: str, query: str = ""):
    """The page as `membrain plugin ui --note <id>` opens it: a single-use code and the item in the fragment."""
    page.goto(f"{load_profile(world.directory).base_url}/memory?{query}code={host.issue_ui_code(world.directory)}"
              f"#{fragment}")
    expect(page.locator("#tabs")).to_be_visible()


def link_of(world, note_id: str) -> str:
    """What `membrain plugin ui --no-browser --note <id>` prints, run as the host would run it."""
    import argparse
    import contextlib
    import io

    from membrain import plugin, plugin_cli

    parser = argparse.ArgumentParser()
    plugin_cli.add_commands(parser.add_subparsers(dest="command"))
    output = io.StringIO()
    patch = pytest.MonkeyPatch()
    patch.setattr(plugin, "start", lambda directory: {})  # The world's service is already running.
    try:
        with contextlib.redirect_stdout(output):
            plugin_cli.dispatch(parser.parse_args(["plugin", "ui", "--no-browser", "--note", note_id,
                                                   "--directory", str(world.directory)]))
    finally:
        patch.undo()
    return output.getvalue().strip().splitlines()[-1]


def test_the_hosts_link_opens_the_page_at_the_note_with_its_lineage_and_both_source_lists(diligent, page):
    note = diligent.note_ids["corrected"]
    link = link_of(diligent, note)
    assert re.fullmatch(rf"{re.escape(load_profile(diligent.directory).base_url)}/memory\?code=[\w-]+#note={note}",
                        link)
    page.goto(link)
    expect(page.locator("#view-notes")).to_be_visible()
    # The code is exchanged and dropped; the address stays.
    expect(page).to_have_url(re.compile(rf"/memory#note={note}$"))
    item = page.locator("#notes article.item.addressed")
    expect(item).to_have_count(1)
    expect(item.locator(":scope > p.user-text")).to_have_text(NOTE_CORRECTED)
    expect(item.locator(".lineage p.hint").first).to_have_text(f"Replaced an earlier note on {DATE[3]}.")
    expect(item.locator(".lineage p.earlier")).to_have_text(f"Earlier ({DATE[1]}): {NOTE_DECISION}")
    expect(item.locator(":scope > details")).to_have_attribute("open", "")
    expect(item.locator("details .source-role")).to_have_text([f"Said on {DATE[3]}:", "The earlier note was based on:"])
    expect(item.locator("details .message .user-text")).to_have_text([CORRECTION, DECISION])
    expect(item.locator("details .message .meta")).to_have_text([f"{DATE[3]} · You", f"{DATE[1]} · You"])
    expect(item.locator("details a.source-conversation")).to_have_count(2)
    expect(page.locator("#notes article.item")).to_have_count(3)  # The normal view, at that note.
    expect(page.locator(".item-gone")).to_have_count(0)
    dump("address-note", item.inner_text())
    # A reload keeps the address (the page's own session), and choosing a tab leaves it.
    page.reload()
    expect(page.locator("#notes article.item.addressed > p.user-text")).to_have_text(NOTE_CORRECTED)
    expect(page.locator("#notes article.item.addressed > details")).to_have_attribute("open", "")
    open_view(page, "conversations")
    expect(page).to_have_url(re.compile(r"/memory$"))
    page.reload()
    expect(page.locator("#view-conversations")).to_be_visible()
    expect(page.locator(".addressed")).to_have_count(0)


def test_the_page_opens_at_a_message_in_its_conversation(diligent, page):
    decision = diligent.messages()[DECISION]["event_id"]
    open_at(page, diligent, f"message={decision}")
    expect(page.locator("#view-conversations")).to_be_visible()
    expect(page).to_have_url(re.compile(rf"/memory#message={decision}$"))
    opened = page.locator("#conversations > details.item").first
    expect(opened).to_have_attribute("open", "")
    expect(opened.locator("summary")).to_have_text(f"{DATE[1]} · 8 messages · {DECISION_SHOWN}")
    message = page.locator("#conversations .message.addressed")
    expect(message).to_have_count(1)
    expect(message.locator(":scope > p.user-text")).to_have_text(DECISION)
    expect(message.locator(".meta")).to_contain_text(f"You{DATE[1]}")
    expect(message.locator(".superseded")).to_have_text(f"Superseded by a note saved on {DATE[3]}.")
    expect(opened.locator(".message")).to_have_count(8)
    dump("address-message", opened.inner_text())


def test_the_address_of_a_replaced_note_opens_the_note_that_replaced_it_at_that_line(diligent, page):
    open_at(page, diligent, f"note={diligent.note_ids['decision']}")
    item = page.locator("#notes article.item.addressed")
    expect(item.locator(":scope > p.user-text")).to_have_text(NOTE_CORRECTED)
    expect(item.locator(".lineage p.earlier.addressed")).to_have_text(f"Earlier ({DATE[1]}): {NOTE_DECISION}")
    expect(page.locator(".item-gone")).to_have_count(0)


@pytest.mark.parametrize("fragment", ["note=not-a-note", "message=not-a-message", "note=", "note=" + "x" * 300])
def test_an_unknown_address_shows_one_plain_line_and_the_normal_view(diligent, page, fragment):
    open_at(page, diligent, fragment)
    view = "notes" if fragment.startswith("note") else "conversations"
    expect(page.locator(f"#view-{view}")).to_be_visible()
    expect(page.locator(f"#{view} > .item-gone")).to_have_text(GONE)
    expect(page.locator(".item-gone")).to_have_count(1)
    expect(page.locator(".addressed")).to_have_count(0)
    if view == "notes":
        expect(page.locator("#notes article.item")).to_have_count(3)
    else:
        expect(page.locator("#conversations > details.item").first).to_be_visible()
    expect(page.locator("#message")).to_have_text("")  # No error.


def test_another_users_note_and_message_are_not_here_on_this_installations_page(diligent, page):
    """A multi-user installation keeps each person of a bot in a brain of their own; the page is the
    installation's, and an address naming another person's note or message shows nothing of it."""
    secret = "Mira's locker code is the year her brother was born."
    with host.ready_client(diligent.directory, "telegram:basis-link-other") as client:
        said = client.observe(secret, conversation_id="other-person-chat", branch_id="main",
                              source_event_key="basis-link-other-1",
                              producer_ref="basis-link-test")["result"]["accepted_event_ids"][0]
        note = client.write_note("Mira keeps a locker code tied to a family date.", role="user",
                                 source_event_ids=[said])["note_id"]
    for fragment, view in ((f"note={note}", "notes"), (f"message={said}", "conversations")):
        open_at(page, diligent, fragment)
        expect(page.locator(f"#{view} > .item-gone")).to_have_text(GONE)
        content = page.content()
        assert "Mira" not in content and "locker" not in content and note not in content and said not in content


@pytest.mark.parametrize("fragment", [
    "note={corrected}&delete=1&action=forget&mode=erase_content",
    "message={decision}&erase=ERASE&view=privacy&confirm=1",
    "view=privacy&erase=ERASE&accept=1",
    "note=%3Cimg%20src%3Dx%20onerror%3D%22window.basisPwned%3D1%22%3E",
])
def test_a_crafted_address_only_navigates_and_never_acts(diligent, page, fragment):
    fragment = fragment.format(corrected=diligent.note_ids["corrected"],
                               decision=diligent.messages()[DECISION]["event_id"])
    before = (len(diligent.notes()), len(diligent.messages()))
    requests, dialogs = [], []
    page.on("request", lambda request: requests.append((request.method, request.url)))
    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    open_at(page, diligent, fragment)
    page.wait_for_load_state("networkidle")
    assert [(method, url.split("?")[0].split("/", 3)[3]) for method, url in requests if method != "GET"] == [
        ("POST", "v1/local/ui-session")]
    assert dialogs == []
    assert page.evaluate("() => window.basisPwned") is None
    expect(page.locator("#notes img, #conversations img")).to_have_count(0)
    expect(page.locator("#view-privacy")).to_be_hidden()
    assert (len(diligent.notes()), len(diligent.messages())) == before


def test_the_address_and_the_gone_line_in_chinese(diligent, page):
    base = load_profile(diligent.directory).base_url
    open_at(page, diligent, "note=not-a-note", query="lang=zh&")
    expect(page.locator("#notes > .item-gone")).to_have_text("这一项已经不在这里了。")
    open_at(page, diligent, f"note={diligent.note_ids['corrected']}", query="lang=zh&")
    item = page.locator("#notes article.item.addressed")
    expect(item.locator(".lineage p.hint").first).to_have_text(f"{DATE[3]} 取代了一条较早的笔记。")
    link = item.locator("details .message").filter(has_text=DECISION).locator("a.source-conversation")
    expect(link).to_have_text(f"所在对话：{DATE[1]} · 8 条消息 · {DECISION_SHOWN}")
    link.click()
    expect(page.locator("#conversations .message.addressed > p.user-text")).to_have_text(DECISION)
    expect(page.locator("#conversations .message.addressed .superseded")).to_have_text(re.compile(DATE[3]))
    page.goto(f"{base}/memory?lang=en&code={host.issue_ui_code(diligent.directory)}")  # Leave the page in English.
    expect(page.locator("#tabs")).to_be_visible()


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
    # The question names each earlier note that goes with it (read from the dependencies the erasure follows).
    assert questions == ["Delete this note and the earlier notes it replaced? Their content is erased.\n\n"
                         f"Deleted with it:\n• Earlier note ({DATE[1]}): {NOTE_DECISION}\n"
                         f"• Earlier note ({DATE[3]}): {NOTE_CORRECTED}"]
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


def test_a_deleted_notes_address_shows_one_plain_line_and_nothing_of_the_note(chain, page):
    """After the deletion above: the host may still hold the note's id from a session that began before it. The
    address shows one plain line and the normal view, and the page asks for nothing the normal view does not."""
    made = []
    # The service's own routes; static files may come from the browser's cache on the second load.
    page.on("request", lambda request: made.append((request.method, request.url)) if "/v1/" in request.url else None)

    def requests_of(fragment: str) -> set:
        made.clear()
        page.goto(f"{load_profile(chain.directory).base_url}/memory?code={host.issue_ui_code(chain.directory)}"
                  + fragment)
        expect(page.locator("#view-notes")).to_be_visible()
        expect(page.locator("#notes article.item").first).to_be_visible()
        page.wait_for_load_state("networkidle")
        return set(made)

    normal = requests_of("")
    for key in ("third", "corrected", "decision"):
        note = chain.note_ids[key]
        addressed = requests_of(f"#note={note}")
        expect(page.locator("#notes > .item-gone")).to_have_text(GONE)
        expect(page.locator("#notes article.item")).to_have_count(2)  # The two notes the deletion left.
        content = page.content()
        assert note not in content and "Tidepool database" not in content and "DuckDB" not in content
        assert addressed == normal, (key, addressed ^ normal)
        assert not [url for _, url in addressed if note in url]
