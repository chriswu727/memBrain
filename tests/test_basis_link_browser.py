"""From a reply to its basis on the memory page: addresses (#note=, #message=) on a real service with several
accounts, in a real headless Chromium. The scenario's own installation is covered in
``test_resume_correction_page_browser.py``; here, what needs accounts of its own: a source the agent said opens its
conversation, another account's ids show nothing, and the address survives signing in with the key.

All data is fictional. Skipped without Playwright, Chromium or the test database, as ``test_memory_page_browser``
is (a failure under MEMBRAIN_REQUIRE_BROWSER=1)."""
import re
import uuid

import pytest
from test_memory_page_browser import account as account
from test_memory_page_browser import browser as browser
from test_memory_page_browser import page as page
from test_memory_page_browser import server as server

try:
    from playwright.sync_api import expect
except ImportError:  # Without Playwright the browser fixture skips (or fails when required) before this is used.
    expect = None

pytestmark = pytest.mark.integration

GONE = "This item is no longer here."


def said(client, text: str, conversation: str, role: str = "user") -> str:
    return client.observe(text, conversation_id=conversation, branch_id="main", role=role,
                          source_event_key=f"basis-{uuid.uuid4()}",
                          producer_ref="basis-link-test")["result"]["accepted_event_ids"][0]


def sign_in_at(page, server, key: str, fragment: str):
    """Signing in with the key, as the page's own form does, on a page opened at an address."""
    page.goto(f"{server.base_url}/memory#{fragment}")
    page.locator("#signin summary").click()
    page.fill("#key", key)
    page.locator("#key-form button[type=submit]").click()
    expect(page.locator("#tabs")).to_be_visible()


def test_a_source_the_agent_said_opens_its_conversation_at_that_message(server, account, page):
    key, client = account
    said(client, "Can you remind me which bakery we picked for the party?", "basis-chat")
    reply = said(client, "We picked Crumb & Co on Elm Street for the party cake.", "basis-chat", role="assistant")
    said(client, "Great, thanks.", "basis-chat")
    note = client.write_note("Party cake comes from Crumb & Co on Elm Street.", kind="other",
                             source_event_ids=[reply])["note_id"]
    sign_in_at(page, server, key, f"note={note}")
    item = page.locator("#notes article.item.addressed")
    expect(item.locator("details .message .meta")).to_have_text(re.compile(r"^\d{4}-\d{2}-\d{2} · Agent$"))
    link = item.locator("details a.source-conversation")
    expect(link).to_have_attribute("href", f"#message={reply}")
    link.click()
    message = page.locator("#conversations .message.addressed")
    expect(message).to_have_count(1)
    expect(message).to_have_class("message assistant addressed")
    expect(message.locator(":scope > p.user-text")).to_have_text(
        "We picked Crumb & Co on Elm Street for the party cake.")
    expect(page.locator("#conversations > details.item[open] .message")).to_have_count(3)


@pytest.mark.parametrize("kind", ["note", "message"])
def test_another_accounts_ids_show_nothing_of_them(server, page, kind):
    from membrain.client import MemoryClient

    mine, theirs = server.keys.pop(), server.keys.pop()
    with MemoryClient(server.base_url, theirs) as other:
        other.brain_id = other.create_brain("Someone else")["id"]
        message = said(other, "My spare key is under the blue flowerpot.", "their-chat")
        note = other.write_note("Keeps a spare key under the blue flowerpot.", source_event_ids=[message])["note_id"]
    with MemoryClient(server.base_url, mine) as client:
        client.brain_id = client.create_brain("Mine")["id"]
        client.write_note("Prefers window seats on trains.", kind="preference", role="user")
        said(client, "Book the 9:10 train to Leeds.", "my-chat")
    view = "notes" if kind == "note" else "conversations"
    sign_in_at(page, server, mine, f"{kind}={note if kind == 'note' else message}")
    expect(page.locator(f"#view-{view}")).to_be_visible()
    expect(page.locator(f"#{view} > .item-gone")).to_have_text(GONE)
    expect(page.locator(".addressed")).to_have_count(0)
    content = page.content()
    assert "flowerpot" not in content and note not in content and message not in content
    if view == "notes":
        expect(page.locator("#notes article.item .user-text")).to_have_text(["Prefers window seats on trains."])
    else:
        expect(page.locator("#conversations .message .user-text")).to_have_text(["Book the 9:10 train to Leeds."])
