"""The memory page shows an agent's proposal that removes or replaces an entry of the card plainly, in English and
Chinese, and Accept applies it (owner's line, 2026-11-18: the page has no card editor; the user asks the agent)."""
import pytest
from test_memory_page_browser import (
    CARD,
    answer_next_dialog,
    open_view,
    sign_in,
    switch_language,
    untranslated,
)
from test_memory_page_browser import account as account
from test_memory_page_browser import browser as browser
from test_memory_page_browser import page as page
from test_memory_page_browser import server as server

try:
    from playwright.sync_api import expect
except ImportError:  # Without Playwright the browser fixture skips (or fails when required) before this is used.
    expect = None

pytestmark = pytest.mark.integration

NOTE = ("This changes the current card only. Switching type later starts from that type's own card plus what you "
        "agreed with your agent.")
NOTE_ZH = "这只修改当前的设定。之后切换类型时，会从那个类型自己的设定开始，再加上你和 agent 约定好的内容。"


def test_a_proposed_replacement_says_what_it_removes_and_adds_in_both_languages_and_accept_applies_it(
        server, page, account):
    key, client = account
    client.set_persona(CARD, made_by="host")  # Traits "warm" and "curious".
    client.propose_persona_change({"traits": ["gentle"], "remove": {"traits": ["WARM"]}},
                                  reason="The user asked to be gentle instead of warm.")
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    item = page.locator("#persona-proposals .persona-proposal.proposal-open")
    expect(item).to_have_count(1)
    expect(item.locator(".proposal-removes")).to_have_text("Removes: warm")
    expect(item.locator(".proposal-adds")).to_have_text("Adds: gentle")
    expect(item.locator(".proposal-removal-note")).to_have_text(NOTE)
    expect(page.locator("#view-persona .heading .muted").first).to_contain_text(
        "To change it, ask your agent to add, remove or replace something")

    switch_language(page, "zh")
    item = page.locator("#persona-proposals .persona-proposal.proposal-open")
    expect(item.locator(".proposal-removes")).to_have_text("将删除： warm")
    expect(item.locator(".proposal-adds")).to_have_text("将添加： gentle")
    expect(item.locator(".proposal-removal-note")).to_have_text(NOTE_ZH)
    expect(page.locator("#view-persona .heading .muted").first).to_contain_text("要添加、删除或替换什么")
    assert untranslated(page, "#persona-proposals") == []

    seen = answer_next_dialog(page, accept=True)  # The page's Accept, answered for real.
    item.get_by_role("button", name="接受", exact=True).click()
    expect(page.locator("#persona-version")).to_have_text("版本 2")
    assert seen and seen[0][0] == "confirm"
    saved = client.persona()
    assert saved["card"]["traits"] == ["curious", "gentle"] and saved["host_proposal"]["confirmed_by"] is None
    assert saved["agreed_changes"] == {"traits": ["gentle"]}
    expect(page.locator("#persona-view")).not_to_contain_text("warm")


def test_a_proposal_that_only_adds_or_replaces_a_value_shows_no_removal_note(server, page, account):
    key, client = account
    client.set_persona(CARD, made_by="host")
    client.propose_persona_change({"traits": ["patient"], "voice": {"length": "one sentence"}},
                                  reason="The user asked for patience and one-sentence replies.")
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    item = page.locator("#persona-proposals .persona-proposal.proposal-open")
    expect(item.locator(".proposal-adds")).to_have_text(["Adds: patient", "Adds: one sentence"])
    expect(item.locator(".proposal-removes")).to_have_text(["Removes: two or three sentences"])
    expect(item.locator(".proposal-removal-note")).to_have_count(0)
