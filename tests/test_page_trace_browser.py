"""Whatever the memory page shows about the user, the user can see what it rests on and can delete it.

One real local installation, played through the Claude Code plugin's own hooks and MCP tools on the scenario clock
(``resume_correction_world``'s harness, no model call): notes from conversation turns, a correction that replaces a
note and carries an inferred feeling, a feeling the user said, a shared moment, a promise, a boundary, a personality
switch asked for in conversation and a "from now on" change the user agreed to. Then, on day 8, the page as
``membrain plugin ui`` opens it, in a real headless Chromium, for each kind of item the page shows:

- where it came from is shown and opens: a message's notes, a feeling's or a mood trigger's note, a promise's and a
  moment's messages and note, a search result's and a map message's conversation, a version's or an agreement's
  message;
- Delete asks first, and the question names everything else the deletion erases. The list is checked against what
  the erasure removed, read independently from the tombstones of a new export taken before and after;
- afterwards nothing of it remains in any view, in what the host receives at the next session start and prompt, in
  ``memory_recall`` or in a new export.

Each test uses records of its own, so they can run in this order on one installation. All data is fictional.
Skipped without Playwright, Chromium or the embedded database, as the other browser tests are.
"""
from __future__ import annotations

import concurrent.futures
import datetime
import json
import re
from pathlib import Path

import pytest
from resume_correction_world import DAY, _source, call, free_port, harness
from test_memory_page_browser import browser as browser
from test_memory_page_browser import open_every_disclosure, open_view
from test_memory_page_browser import page as page

from membrain import embedded_database, evaluation_clock, host, plugin
from membrain.local_profile import load_profile

try:
    from playwright.sync_api import expect
except ImportError:  # Without Playwright the browser fixture skips (or fails when required) before this is used.
    expect = None

pytestmark = pytest.mark.integration

D1, D3 = DAY[1].date().isoformat(), DAY[3].date().isoformat()

# Day 1, one conversation: (user message, reply, what the host saves for it).
BOOK = "We'll host the book club at my place on Thursdays."
NOTE_BOOK = "Book club meets at the user's place on Thursdays."
MISO = "My cat Miso is allergic to chicken, so no chicken treats."
REPLY_MISO = "Understood, no chicken treats for Miso."
NOTE_MISO = "Miso the cat is allergic to chicken; no chicken treats."
LUMEN = "I got tickets to see the Lumen Quartet in March!"
NOTE_LUMEN = "Has tickets for the Lumen Quartet concert in March."
PUZZLE = "We finally finished the 500-piece lighthouse puzzle together, ha!"
NOTE_PUZZLE = "Finished the 500-piece lighthouse puzzle together."
DENTIST = "Remind me to call the dentist by 2026-11-05."
NOTE_DENTIST = "Remind the user to call the dentist."
FERNWAY = "Please don't bring up my old job at Fernway again."
CABIN = "Our cabin trip is booked for the first weekend of December."
REPLY_CABIN = "Lovely, the cabin trip is noted for early December."
NOTE_CABIN = "Cabin trip booked for the first weekend of December."
RUNNING = "I switched my running days to Tuesday and Saturday."
REPLY_RUNNING = "Got it: running on Tuesdays and Saturdays."
NOTE_RUNNING = "Runs on Tuesdays and Saturdays."
# Day 1, another conversation.
GARDEN = "I'm planting tomatoes and basil on the balcony this spring."
WILTING = "The basil keeps wilting in the afternoon sun."
NOTE_GARDEN = "Growing tomatoes and basil on the balcony this spring."
# Day 3.
BOOK_CHANGE = "Change of plan: book club moves to Wednesdays at the library."
NOTE_BOOK_CHANGE = "Book club meets on Wednesdays at the library."
SWITCH = "Can you switch to a different personality type?"
SHORTER = "From now on, keep your replies short."
YES = "Yes, please do."
LENGTH = "one or two sentences"

FEELINGS = {"relieved": {"label": "relieved", "valence": 1, "intensity": 1, "basis": "inferred", "topic": "book club"},
            "excited": {"label": "excited", "valence": 2, "intensity": 2, "basis": "reported", "topic": "concert"},
            "proud": {"label": "proud", "valence": 1, "intensity": 2, "basis": "reported", "topic": "puzzle"}}


def in_thread(task, *args):
    """MCP calls run asyncio.run, which cannot run inside the loop Playwright's sync API keeps in this thread."""
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        return pool.submit(task, *args).result()


class Trace:
    def __init__(self, memory):
        self.memory, self.ids, self.preset = memory, {}, None

    @property
    def directory(self) -> Path:
        return self.memory.directory

    def day(self, moment) -> None:
        self.memory.clock.advance(self.directory, moment, run=self.directory.name)

    def session(self, session: str, turns) -> None:
        """Turns of one session: (user message, reply, host action or None); an action gets the tool server and the
        turn's source block, as the host model would use them."""
        client, server, _schemas, _instructions = self.memory.tools()
        try:
            plugin.session_start({"session_id": session}, self.directory)
            for index, (text, reply, act) in enumerate(turns):
                context = plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": f"t{index}"},
                                             self.directory)
                if act:
                    act(server, client, *_source(context))
                plugin.stop({"session_id": session, "prompt_id": f"t{index}", "last_assistant_message": reply},
                            self.directory)
        finally:
            client.close()

    def note(self, key, text, **fields):
        def act(server, client, references, capture):
            result = call(server, "memory_note", {"text": text, "source_messages": references,
                                                  "recording_capture": capture, **fields})
            assert result.get("note_id"), result
            self.ids[key] = result["note_id"]
        return act

    def tool(self, name, arguments, key=None):
        def act(server, client, references, capture):
            result = call(server, name, {**arguments(client), "source_messages": references,
                                         "recording_capture": capture} if name == "memory_persona"
                          else arguments(client))
            assert "error" not in result, result
            if key:
                self.ids[key] = result
        return act

    def messages(self) -> dict[str, dict]:
        with self.memory.client() as client:
            items = client.timeline(roles=("user", "assistant"), max_characters=200_000, max_item_characters=20_000,
                                    limit=1000)["items"]
        return {item["text"]: item for item in items if item["conversation_id"] != "membrain-notes"}

    def tombstones(self) -> set[str]:
        """The events erased so far, from a new export: what an erasure removed, read independently of the page."""
        document = host.export_user(self.directory, None)["document"]
        return {entry["object_id"] for entry in document["tombstones"]
                if entry["object_kind"] == "event" and entry["mode"] == "erase_content"}

    def host_view(self, query: str) -> str:
        """What the host receives at the next session start and prompt, what memory_recall returns, and an export."""
        def read():
            session = f"trace-check-{datetime.datetime.now().timestamp()}"
            opening = plugin.session_start({"session_id": session}, self.directory) or ""
            prompt = plugin.user_prompt({"session_id": session, "prompt": "Where were we?", "prompt_id": "t0"},
                                        self.directory) or ""
            client, server, _schemas, _instructions = self.memory.tools()
            try:
                recalled = call(server, "memory_recall", {"query": query}).get("context") or ""
            finally:
                client.close()
            plugin.stop({"session_id": session, "prompt_id": "t0", "last_assistant_message": "Sure."}, self.directory)
            return {"session start": opening, "prompt": prompt, "memory_recall": recalled,
                    "export": json.dumps(host.export_user(self.directory, None), ensure_ascii=False)}
        return in_thread(read)


@pytest.fixture(scope="module")
def trace(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    patch = pytest.MonkeyPatch()
    patch.setenv("MEMBRAIN_SEMANTIC", "0")
    patch.setenv("PYTHON_DOTENV_DISABLED", "1")
    patch.setenv(evaluation_clock.ENV, "")
    patch.setattr(harness, "STUB", True)
    directory = tmp_path_factory.mktemp("page-trace") / "brain"
    try:
        world = Trace(harness.Memory(directory, None, (free_port(), free_port()), DAY[1]))
        world.session("trace-day1", [
            (BOOK, "Book club at yours on Thursdays, noted.", world.note("book", NOTE_BOOK, kind="plan")),
            (MISO, REPLY_MISO, world.note("miso", NOTE_MISO, kind="constraint")),
            (LUMEN, "That sounds wonderful!", world.note("lumen", NOTE_LUMEN, kind="plan", affect=FEELINGS["excited"])),
            (PUZZLE, "That was fun, we did it!", world.note("puzzle", NOTE_PUZZLE, kind="milestone", shared=True,
                                                            moment="play", affect=FEELINGS["proud"])),
            (DENTIST, "I'll remind you about the dentist.", world.note("dentist", NOTE_DENTIST, kind="agent_commitment",
                                                                      due="2026-11-05")),
            (FERNWAY, "Understood, I won't bring it up.", world.tool(
                "memory_boundary", lambda client: {"topic": "my old job at Fernway", "aliases": ["Fernway"]})),
            (CABIN, REPLY_CABIN, world.note("cabin", NOTE_CABIN, kind="plan")),
            (RUNNING, REPLY_RUNNING, world.note("running", NOTE_RUNNING, kind="routine")),
        ])
        world.session("trace-garden", [
            (GARDEN, "Tomatoes and basil, lovely.", world.note("garden", NOTE_GARDEN, kind="other")),
            (WILTING, "Try moving it out of the afternoon sun.", None),
        ])
        world.day(DAY[3])

        def switch(client):
            current = client.persona_presets()["current"]
            world.preset = next(item["id"] for item in client.persona_presets()["presets"]
                                if current.get("preset", {}).get("id") != item["id"])
            return {"action": "switch", "preset": world.preset}

        world.session("trace-day3", [
            (BOOK_CHANGE, "Wednesdays at the library, got it.", world.note(
                "book_change", NOTE_BOOK_CHANGE, kind="plan", replaces=[world.ids["book"]],
                affect=FEELINGS["relieved"])),
            (SWITCH, "Done, I switched.", world.tool("memory_persona", switch)),
            (SHORTER, "Shall I keep my replies brief from now on?", world.tool("memory_persona", lambda client: {
                "action": "propose", "changes": {"voice": {"length": LENGTH}},
                "reason": "The user asked for short replies from now on."}, key="proposal")),
            (YES, "Done.", world.tool("memory_persona", lambda client: {
                "action": "confirm", "proposal_id": world.ids["proposal"]["proposal_id"]})),
        ])
        world.day(DAY[8])
        messages = world.messages()
        world.ids.update({text: messages[text]["event_id"] for text in (
            BOOK, MISO, REPLY_MISO, LUMEN, PUZZLE, DENTIST, CABIN, REPLY_CABIN, RUNNING, REPLY_RUNNING, GARDEN,
            WILTING, BOOK_CHANGE, SWITCH, YES)})
        yield world
    finally:
        from membrain import desktop

        try:
            if directory in harness.STARTED:
                harness.STARTED.remove(directory)
                desktop.stop(directory)
        finally:
            evaluation_clock.disable()
            patch.undo()


@pytest.fixture(scope="module", autouse=True)
def world_before_the_browser(trace):
    """The world is played before Chromium starts (see ``in_thread``)."""
    return trace


def open_page(page, world, query: str = ""):
    page.goto(f"{load_profile(world.directory).base_url}/memory?{query}code={host.issue_ui_code(world.directory)}")
    expect(page.locator("#tabs")).to_be_visible()
    expect(page.locator("#view-notes")).to_be_visible()


def delete(page, world, button, *, accept: bool = True):
    """Click a Delete: the question the page asked, the ``erased_with`` it was written from (the request the page
    made), and the events the erasure removed (tombstones of an export before and after), without the clicked one."""
    before = world.tombstones() if accept else set()
    asked = []
    page.once("dialog", lambda dialog: (asked.append(dialog.message), dialog.accept() if accept else dialog.dismiss()))
    with page.expect_response(lambda response: "erasure=true" in response.url) as response:
        if accept:  # The erasure itself: the page's forget request.
            with page.expect_response(lambda reply: reply.url.endswith("/v1/actions")
                                      and reply.request.method == "POST") as erased:
                button.click()
            assert erased.value.json()["outcome"] == "completed"
        else:
            button.click()
    items = response.value.json()["items"]
    removed = (world.tombstones() - before) if accept else set()
    assert len(asked) == 1, asked
    return asked[0], items, removed


def listed(question: str) -> list[str]:
    return [line[2:] for line in question.split("\n") if line.startswith("• ")]


LISTS = {"notes": ["notes"], "people": ["people"], "plans": ["plans"], "feelings": ["feelings"],
         "conversations": ["conversations"], "persona": ["persona-versions", "moments", "mood-triggers"],
         "brain": ["brain-legend"]}


def show(page, view: str) -> None:
    """Open a view and wait until its lists are drawn from this load: each list's stand-in child is replaced."""
    page.evaluate("""(ids) => ids.forEach((id) => {
        const mark = document.createElement("i"); mark.className = "trace-stale"; document.getElementById(id).append(mark);
    })""", LISTS[view])
    open_view(page, view)
    for ident in LISTS[view]:
        expect(page.locator(f"#{ident} > i.trace-stale")).to_have_count(0)
    page.wait_for_load_state("networkidle")


def page_text(page) -> str:
    """Every view the page has for memory, with every disclosure open."""
    texts = []
    for view in ("notes", "people", "plans", "feelings", "conversations", "persona"):
        show(page, view)
        open_every_disclosure(page)
        texts.append(page.locator(f"#view-{view}").inner_text())
    return "\n".join(texts)


def gone_everywhere(page, world, texts, query: str) -> None:
    shown = page_text(page)
    received = world.host_view(query)
    for text in texts:
        assert text not in shown, text
        for reader, content in received.items():
            assert text not in content, (text, reader)


# Where it came from ----------------------------------------------------------------------------------------------

def test_a_message_says_which_notes_rest_on_it_and_each_opens_its_note(trace, page):
    open_page(page, trace)
    show(page, "conversations")
    open_every_disclosure(page)
    message = page.locator("#conversations .message.user").filter(has_text=MISO)
    expect(message.locator(".rests-on p.hint").first).to_have_text("A note rests on this message:")
    link = message.locator(".rests-on a.note-link")
    expect(link).to_have_text(NOTE_MISO)
    expect(link).to_have_attribute("href", f"#note={trace.ids['miso']}")
    # A corrected fact rests on both of its messages: the correction and, through the note it replaced, the first.
    first = page.locator("#conversations .message.user").filter(has_text=BOOK)
    expect(first.locator(".rests-on a.note-link")).to_have_text(NOTE_BOOK_CHANGE)
    expect(page.locator("#conversations .message.user").filter(has_text=WILTING).locator(".rests-on")).to_have_count(0)
    link.click()
    expect(page.locator("#notes article.item.addressed > p.user-text")).to_have_text(NOTE_MISO)


def test_a_feeling_and_a_mood_trigger_lead_to_their_note_and_messages(trace, page):
    open_page(page, trace)
    show(page, "feelings")
    feeling = page.locator("#feelings article.feeling").filter(has_text="excited")
    expect(feeling.locator("a.note-link")).to_have_text("Show the note")
    expect(feeling.locator("a.note-link")).to_have_attribute("href", f"#note={trace.ids['lumen']}")
    feeling.locator("details summary").click()
    expect(feeling.locator("details a.source-conversation")).to_have_attribute("href", f"#message={trace.ids[LUMEN]}")
    show(page, "persona")
    page.evaluate("() => { document.getElementById('mood-triggers').closest('details').open = true; }")
    triggers = page.locator("#mood-triggers .mood-trigger")
    expect(triggers.first).to_be_visible()
    proud = triggers.filter(has_text="proud")
    expect(proud.locator("a.note-link")).to_have_attribute("href", f"#note={trace.ids['puzzle']}")
    proud.locator("details summary").click()
    expect(proud.locator("details a.source-conversation")).to_have_attribute("href", f"#message={trace.ids[PUZZLE]}")
    proud.locator("a.note-link").click()
    expect(page.locator("#notes article.item.addressed > p.user-text")).to_have_text(NOTE_PUZZLE)


def test_a_version_and_an_agreement_lead_to_the_message_the_user_said_it_in(trace, page):
    open_page(page, trace)
    show(page, "persona")
    versions = page.locator("#persona-versions .persona-version")
    agreed = versions.filter(has_text="your agent's suggestion, confirmed in conversation")
    expect(agreed.locator(".persona-said-in > p.hint").first).to_have_text("Where you agreed:")
    expect(agreed.locator(".persona-said-in a.source-conversation").first).to_have_text(f"“{YES}”")
    expect(agreed.locator(".persona-said-in a.source-conversation").first).to_have_attribute(
        "href", f"#message={trace.ids[YES]}")
    switched = versions.filter(has_text="switched type")
    expect(switched.locator(".persona-said-in > p.hint")).to_have_text("Where you asked for it:")
    expect(switched.locator(".persona-said-in a.source-conversation")).to_have_attribute(
        "href", f"#message={trace.ids[SWITCH]}")
    # The agreement kept across types, under the current card.
    agreement = page.locator("#persona-view .persona-agreement")
    expect(agreement.locator("a.source-conversation")).to_have_attribute("href", f"#message={trace.ids[YES]}")
    agreement.locator("a.source-conversation").click()
    expect(page.locator("#conversations .message.addressed > p.user-text")).to_have_text(YES)


def test_a_boundary_says_no_message_is_recorded_for_it(trace, page):
    open_page(page, trace)
    show(page, "persona")
    boundary = page.locator("#boundaries .relationship-boundary")
    expect(boundary.locator("p.user-text")).to_have_text("my old job at Fernway")
    expect(boundary.locator("p.hint").last).to_have_text("Original message not linked.")


def test_the_new_texts_in_chinese(trace, page):
    open_page(page, trace, query="lang=zh&")
    show(page, "conversations")
    open_every_disclosure(page)
    message = page.locator("#conversations .message.user").filter(has_text=MISO)
    expect(message.locator(".rests-on p.hint").first).to_have_text("有一条笔记依据这条消息：")
    question, _items, _removed = delete(page, trace, message.get_by_role("button", name="删除"), accept=False)
    assert question.startswith("删除这条消息？它在所有用到的地方都会被清除。\n\n会一并删除：\n"), question
    # As the lineage lines are, a label and then what the user or the agent wrote, after a space.
    assert f"• 笔记（{D1}）： {NOTE_MISO}" in question and f"• agent 的回复（{D1}）： {REPLY_MISO}" in question
    show(page, "feelings")
    expect(page.locator("#feelings a.note-link").first).to_have_text("查看这条笔记")
    show(page, "persona")
    expect(page.locator("#persona-versions .persona-said-in > p.hint").first).to_have_text(
        re.compile("^(你同意时说的话：|你提出时说的话：)$"))
    page.goto(f"{load_profile(trace.directory).base_url}/memory?lang=en&code={host.issue_ui_code(trace.directory)}")
    expect(page.locator("#tabs")).to_be_visible()


# Deleting each kind: the question names what goes, and nothing of it remains -------------------------------------

def test_deleting_a_message_names_its_reply_and_its_note_and_erases_exactly_those(trace, page):
    open_page(page, trace)
    show(page, "conversations")
    open_every_disclosure(page)
    message = page.locator("#conversations .message.user").filter(has_text=MISO)
    question, items, removed = delete(page, trace, message.get_by_role("button", name="Delete"))
    assert question.startswith("Delete this message? Its content is erased everywhere it was used.\n\nDeleted with it:\n")
    assert sorted(listed(question)) == sorted([f"Note ({D1}): {NOTE_MISO}", f"Your agent's reply ({D1}): {REPLY_MISO}"])
    assert {entry["event_id"] for entry in items[0]["erased_with"]} == removed - {trace.ids[MISO]}
    assert removed == {trace.ids[MISO], trace.ids[REPLY_MISO], trace.ids["miso"]}
    # The reply goes from the open conversation at once.
    expect(page.locator("#conversations .message").filter(has_text=REPLY_MISO)).to_have_count(0)
    gone_everywhere(page, trace, [MISO, REPLY_MISO, NOTE_MISO], "Miso chicken treats")


def test_deleting_a_conversation_names_the_notes_that_rest_on_it(trace, page):
    open_page(page, trace)
    show(page, "conversations")
    conversation = page.locator("#conversations > details.item").filter(has_text=GARDEN[:40])
    conversation.locator("summary").click()
    question, items, removed = delete(page, trace, conversation.locator(":scope > button"))
    assert question == f"Delete every message in this conversation?\n\nDeleted with them:\n• Note ({D1}): {NOTE_GARDEN}"
    inside = {item["event_id"] for item in items}
    assert {GARDEN, WILTING} <= {item["text"] for item in items}
    assert removed - inside == {trace.ids["garden"]}
    gone_everywhere(page, trace, [GARDEN, WILTING, NOTE_GARDEN], "basil balcony tomatoes")


def test_deleting_a_corrected_note_names_the_note_it_replaced_and_its_feeling(trace, page):
    open_page(page, trace)
    note = page.locator("#notes article.item").filter(has_text=NOTE_BOOK_CHANGE)
    question, items, removed = delete(page, trace, note.get_by_role("button", name="Delete"))
    assert question == ("Delete this note and the earlier note it replaced? Their content is erased.\n\n"
                        f"Deleted with it:\n• Earlier note ({D1}): {NOTE_BOOK}\n• Feeling: relieved · book club")
    assert {entry["event_id"] for entry in items[0]["erased_with"]} == removed - {trace.ids["book_change"]}
    assert trace.ids["book"] in removed and len(removed) == 3
    # The messages stay: deleting a note never deletes what was said.
    assert BOOK in trace.messages() and BOOK_CHANGE in trace.messages()
    gone_everywhere(page, trace, [NOTE_BOOK, NOTE_BOOK_CHANGE, "relieved"], "book club library")


def test_deleting_a_feeling_erases_only_the_feeling(trace, page):
    open_page(page, trace)
    show(page, "feelings")
    feeling = page.locator("#feelings article.feeling").filter(has_text="excited")
    before = trace.tombstones()
    asked = []
    page.once("dialog", lambda dialog: (asked.append(dialog.message), dialog.accept()))
    feeling.get_by_role("button", name="Delete").click()
    expect(page.locator("#feelings article.feeling").filter(has_text="excited")).to_have_count(0)
    removed = trace.tombstones() - before
    # Nothing depends on a feeling, so the fixed question is exact: the note and its messages stay.
    assert asked == ["Delete this feeling? The note and its messages stay."] and len(removed) == 1
    with trace.memory.client() as client:
        notes = client.timeline(roles=("assistant",), conversation_id="membrain-notes", limit=1000)["items"]
    assert NOTE_LUMEN in {item["text"].split("] ", 1)[-1] for item in notes} and LUMEN in trace.messages()
    gone_everywhere(page, trace, ["excited"], "Lumen Quartet")


def test_deleting_a_shared_moment_names_its_feeling(trace, page):
    open_page(page, trace)
    show(page, "persona")
    moment = page.locator("#moments .relationship-moment").filter(has_text=NOTE_PUZZLE)
    moment.locator("details summary").click()
    expect(moment.locator("details a.source-conversation")).to_have_attribute("href", f"#message={trace.ids[PUZZLE]}")
    expect(moment.locator("a.note-link")).to_have_attribute("href", f"#note={trace.ids['puzzle']}")
    question, items, removed = delete(page, trace, moment.get_by_role("button", name="Delete"))
    assert question == ("Delete this shared moment? Its note is erased.\n\nDeleted with it:\n"
                        "• Feeling: proud · puzzle")
    assert {entry["event_id"] for entry in items[0]["erased_with"]} == removed - {trace.ids["puzzle"]}
    gone_everywhere(page, trace, [NOTE_PUZZLE, "proud"], "lighthouse puzzle")


def test_a_promise_shows_its_message_and_its_note_and_can_be_deleted(trace, page):
    open_page(page, trace)
    show(page, "persona")
    promise = page.locator("#commitments .relationship-promise").filter(has_text=NOTE_DENTIST)
    expect(promise.locator(".meta .actions button")).to_have_text(["Delete"])
    expect(promise.locator("details summary")).to_have_text("1 original message")
    promise.locator("details summary").click()
    expect(promise.locator("details a.source-conversation")).to_have_attribute("href", f"#message={trace.ids[DENTIST]}")
    expect(promise.locator("a.note-link")).to_have_attribute("href", f"#note={trace.ids['dentist']}")
    question, items, removed = delete(page, trace, promise.get_by_role("button", name="Delete"))
    assert question == "Delete this promise? Its note is erased." and items[0]["erased_with"] == []
    assert removed == {trace.ids["dentist"]}
    expect(page.locator("#commitments")).not_to_contain_text(NOTE_DENTIST)
    gone_everywhere(page, trace, [NOTE_DENTIST], "dentist")


def test_a_search_result_opens_its_conversation_names_its_note_and_can_be_deleted(trace, page):
    open_page(page, trace)
    open_view(page, "search")
    page.fill("#search-text", "cabin trip December")
    page.locator("#search-form button[type=submit]").click()
    result = page.locator("#results > .item").filter(has_text=CABIN)
    expect(result.locator(".result-actions a.source-conversation")).to_have_attribute(
        "href", f"#message={trace.ids[CABIN]}")
    expect(result.locator(".rests-on a.note-link")).to_have_text(NOTE_CABIN)
    question, items, removed = delete(page, trace, result.get_by_role("button", name="Delete"))
    assert sorted(listed(question)) == sorted([f"Note ({D1}): {NOTE_CABIN}", f"Your agent's reply ({D1}): {REPLY_CABIN}"])
    assert {entry["event_id"] for entry in items[0]["erased_with"]} == removed - {trace.ids[CABIN]}
    expect(page.locator("#results")).not_to_contain_text(CABIN)
    gone_everywhere(page, trace, [CABIN, REPLY_CABIN, NOTE_CABIN], "cabin trip December")


def test_a_message_on_the_map_opens_its_conversation_and_can_be_deleted(trace, page):
    open_page(page, trace)
    show(page, "brain")
    page.locator("#mode-2d").click()
    node = page.locator(f'#brain-canvas circle.brain-node[data-id="msg:{trace.ids[RUNNING]}"]')
    node.click()
    actions = page.locator("#brain-detail .brain-note-actions")
    expect(actions.locator("a.source-conversation")).to_have_attribute("href", f"#message={trace.ids[RUNNING]}")
    question, items, removed = delete(page, trace, actions.get_by_role("button", name="Delete"))
    assert sorted(listed(question)) == sorted([f"Note ({D1}): {NOTE_RUNNING}",
                                               f"Your agent's reply ({D1}): {REPLY_RUNNING}"])
    assert {entry["event_id"] for entry in items[0]["erased_with"]} == removed - {trace.ids[RUNNING]}
    expect(page.locator(f'#brain-canvas circle.brain-node[data-id="msg:{trace.ids[RUNNING]}"]')).to_have_count(0)
    gone_everywhere(page, trace, [RUNNING, REPLY_RUNNING, NOTE_RUNNING], "running days")


def test_removing_a_boundary_erases_only_the_boundary(trace, page):
    open_page(page, trace)
    show(page, "persona")
    before = trace.tombstones()
    asked = []
    page.once("dialog", lambda dialog: (asked.append(dialog.message), dialog.accept()))
    page.locator("#boundaries .relationship-boundary").get_by_role("button", name="Remove").click()
    expect(page.locator("#boundaries .relationship-boundary")).to_have_count(0)
    assert asked[0].startswith("Remove this boundary?") and len(trace.tombstones() - before) == 1
    # The user's message that asked for it stays: removing a boundary deletes no message.
    assert FERNWAY in trace.messages()
    gone_everywhere(page, trace, ["also: Fernway"], "Fernway")


def test_deleting_the_personality_history_names_the_agreement_that_goes_with_it(trace, page):
    open_page(page, trace)
    show(page, "persona")
    page.locator("#companion-more summary").click()
    asked = []
    page.once("dialog", lambda dialog: (asked.append(dialog.message), dialog.accept()))
    page.locator("#persona-delete-history").click()
    expect(page.locator("#persona-versions .persona-version")).to_have_count(0)
    version = re.search(r"in version (\d+):", asked[0])
    assert asked == ["Delete every personality version, including the current card? This cannot be undone.\n\n"
                     f"Deleted with them:\n• Agreed with your agent in version {version.group(1)}: Voice: length {LENGTH}"
                     "\n• 1 suggestion"], asked
    received = trace.host_view("short replies")
    for reader, content in received.items():
        assert LENGTH not in content and "<membrain-persona" not in content, reader
    assert LENGTH not in page_text(page)
