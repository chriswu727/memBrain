"""Gap 21 of the maturity test matrix: the memory page (/memory) in a real headless Chromium, against a real service and
database. The showcase makes no API request; persona suggestions are accepted, rejected and dismissed through the
page's own native confirm() dialogs; a note edited or deleted on the brain map redraws the map; every companion section
renders in English and Chinese, and the language switch keeps the current view; the page never scrolls sideways.

All data is fictional. The service listens on an ephemeral port picked here, never the default one. Without Playwright,
Chromium or the test database the module is skipped, unless MEMBRAIN_REQUIRE_BROWSER=1 (set in Verify), which turns
every such skip into a failure."""
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest

from membrain.client import MemoryClient

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # Playwright is a dev dependency; without it the module is skipped (or fails when required).
    sync_playwright = None

pytestmark = pytest.mark.integration

WEB = Path(__file__).resolve().parents[1] / "src" / "membrain" / "web"
REQUIRED = os.environ.get("MEMBRAIN_REQUIRE_BROWSER") == "1"
DESKTOP, PHONE = {"width": 1280, "height": 900}, {"width": 390, "height": 844}
CARD = {"name": "Wren", "traits": ["warm", "curious"],
        "voice": {"register": "formal", "length": "two or three sentences", "emoji": "", "language": ""},
        "values": ["honesty over flattery"], "boundaries": ["no medical advice"], "baseline_mood": None}
ACCEPT = ("Accept this suggestion? The card is saved as a new version; you can restore the earlier one at any "
          "time.")
REJECT = "Reject this suggestion? None of the same kind is offered again for 30 days."
RESET = ("Reset the personality to the host's default, or to no card? Earlier versions are kept and can be "
         "restored. Notes and messages are not touched.")
DELETE_NOTE = "Delete this note? Its content is erased."
# English words that may stay in the Chinese page: product names, and "agent", which the Chinese text keeps.
ENGLISH_KEPT = {"memBrain", "agent", "Claude", "Code", "Codex", "hook"}
VIEWS = ["notes", "brain", "persona", "plans", "people", "feelings", "conversations", "search", "privacy"]


def unavailable(reason: str):
    if REQUIRED:
        pytest.fail(f"MEMBRAIN_REQUIRE_BROWSER=1, but {reason}", pytrace=False)
    pytest.skip(reason)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


# Fixtures ---------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def browser():
    if sync_playwright is None:
        unavailable("Playwright is not installed (it is in the dev dependency group)")
    playwright = sync_playwright().start()
    try:
        try:
            chromium = playwright.chromium.launch()
        except PlaywrightError as error:
            unavailable(f"Chromium cannot be launched: {str(error).splitlines()[0]}")
        yield chromium
        chromium.close()
    finally:
        playwright.stop()


class Server:
    def __init__(self, base_url: str, keys: list[str]):
        self.base_url, self.keys = base_url, keys


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    dsn = os.environ.get("MEMORY_DATABASE_URL")
    if not dsn:
        unavailable("MEMORY_DATABASE_URL must point to the dedicated test database")
    try:
        import psycopg

        psycopg.connect(dsn, connect_timeout=3).close()
    except Exception as error:  # noqa: BLE001 - any connection failure means there is no database to test against.
        unavailable(f"the test database is unreachable: {str(error).splitlines()[0]}")
    # One fictional principal per test, so each signs in to an account with exactly one brain.
    keys = [f"gap21-{uuid.uuid4()}" for _ in range(12)]
    key_file = tmp_path_factory.mktemp("gap21") / "keys.json"
    key_file.write_text(json.dumps({hashlib.sha256(key.encode()).hexdigest(): {
        "tenant_id": str(uuid.uuid4()), "principal_id": str(uuid.uuid4())} for key in keys}))
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = {**os.environ, "MEMORY_DATABASE_URL": dsn, "MEMORY_API_KEYS_FILE": str(key_file),
                   "MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "membrain.api:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
        env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        with httpx.Client(timeout=0.5, trust_env=False) as health:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(f"the memory service exited: {process.stderr.read()}")
                try:
                    if health.get(base_url + "/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail("the memory service did not become ready")
        yield Server(base_url, keys)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture
def account(server):
    """A fresh principal with one brain: (access key, an SDK client bound to that brain)."""
    key = server.keys.pop()
    with MemoryClient(server.base_url, key) as client:
        client.brain_id = client.create_brain("Gap 21 browser test")["id"]
        yield key, client


@pytest.fixture
def page(browser):
    """A desktop-sized English page; any uncaught page error fails the test."""
    context = browser.new_context(viewport=DESKTOP, locale="en-US")
    tab = context.new_page()
    tab.set_default_timeout(15_000)
    errors = []
    tab.on("pageerror", lambda error: errors.append(str(error)))
    yield tab
    context.close()
    assert errors == [], "uncaught errors on the page"


# Helpers ----------------------------------------------------------------------------------------------------------

def sign_in(page, base_url: str, key: str):
    page.goto(f"{base_url}/memory")
    page.locator("#signin summary").click()
    page.fill("#key", key)
    page.locator("#key-form button[type=submit]").click()
    expect(page.locator("#tabs")).to_be_visible()
    expect(page.locator("#view-notes")).to_be_visible()
    page.evaluate("() => { window.gap21SamePage = true; }")  # Gone if the page reloads.


def same_page(page) -> bool:
    return page.evaluate("() => window.gap21SamePage === true")


def open_view(page, view: str):
    page.locator(f'#tabs button[data-view="{view}"]').click()
    expect(page.locator(f"#view-{view}")).to_be_visible()
    expect(page.locator(f'#tabs button[data-view="{view}"]')).to_have_class(re.compile(r"\bactive\b"))


def answer_next_dialog(page, accept: bool) -> list:
    """Answer the page's next native dialog for real (no stub of window.confirm) and record what it asked."""
    seen = []

    def handle(dialog):
        seen.append((dialog.type, dialog.message))
        if accept:
            dialog.accept()
        else:
            dialog.dismiss()

    page.once("dialog", handle)
    return seen


def switch_language(page, to: str):
    page.locator("#language").click()  # The page's own control; it reloads the page in the other language.
    expect(page.locator("html")).to_have_attribute("lang", "zh-CN" if to == "zh" else "en")
    expect(page.locator("#tabs")).to_be_visible()


def assert_no_horizontal_scroll(page, where: str):
    widths = page.evaluate("""() => ({ page: document.documentElement.scrollWidth,
        body: document.body.scrollWidth, viewport: document.documentElement.clientWidth })""")
    assert max(widths["page"], widths["body"]) <= widths["viewport"], (where, widths)


def untranslated(page, selector: str) -> list[str]:
    """Interface text in the section that still has English words; text people wrote (.user-text) is exempt."""
    texts = page.locator(selector).evaluate("""(root) => {
        const out = [];
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (node.parentElement.closest(".user-text, pre, code, script, style")) continue;
            const text = node.nodeValue.replace(/\\s+/g, " ").trim();
            if (text) out.push(text);
        }
        for (const element of root.querySelectorAll("[placeholder], [aria-label], [title]")) {
            if (element.closest(".user-text")) continue;
            for (const name of ["placeholder", "aria-label", "title"]) {
                const value = element.getAttribute(name);
                if (value) out.push(value);
            }
        }
        return out;
    }""")
    return [text for text in texts if set(re.findall(r"[A-Za-z]{2,}", text)) - ENGLISH_KEPT]


def seed_feedback(client: MemoryClient, text: str):
    """The user gives the same feedback in three conversations, through the real observe route."""
    for index in (1, 2, 3):
        result = client.observe(text, conversation_id=f"gap21-chat-{index}", branch_id="main",
                                source_event_key=f"gap21-{uuid.uuid4()}", producer_ref="gap21-browser-test")
        assert result["outcome"] == "completed", result
    listing = client.persona_proposals()
    assert listing["open"] == 1 and len(listing["proposals"]) == 1, listing
    return listing["proposals"][0]


def map_labels(client: MemoryClient) -> dict[str, str]:
    return {node["id"]: node.get("label") or "" for node in client.memory_map()["nodes"]}


# 1. Showcase ------------------------------------------------------------------------------------------------------

def test_showcase_shows_fictional_data_and_makes_no_api_request(server, page):
    requests, console_errors = [], []
    page.on("request", lambda request: requests.append(request.url))
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(f"{server.base_url}/memory?demo=brain&show=1")
    expect(page.locator("#brain-show")).to_be_visible()
    expect(page.locator("#show-demo")).to_be_visible()
    expect(page.locator("#show-demo")).to_have_text("Fictional demo data")
    demo = json.loads((WEB / "memory-map-demo.json").read_text(encoding="utf-8"))
    assert demo["demo"] is True
    expect(page.locator("#show-stage .show-node").first).to_be_attached()
    drawn = page.locator("#show-stage .show-node").count()
    assert 0 < drawn <= len(demo["nodes"])
    expect(page.locator("#show-counts")).to_contain_text(f"{drawn} memories")
    for size in (DESKTOP, PHONE):
        page.set_viewport_size(size)
        assert_no_horizontal_scroll(page, f"showcase at {size['width']} px")
    page.set_viewport_size(DESKTOP)

    # Closing the showcase leaves the fictional brain view, which offers no edit or delete.
    page.keyboard.press("Escape")
    expect(page.locator("#brain-show")).to_be_hidden()
    expect(page.locator("#view-brain")).to_be_visible()
    expect(page.locator("#brain-demo")).to_be_visible()
    expect(page.locator("#signin")).to_be_hidden()
    first_note = page.locator('#brain-canvas circle.brain-node[data-id^="note:"]').first
    first_note.click()
    expect(page.locator("#brain-detail")).to_be_visible()
    expect(page.locator("#brain-detail .brain-note-actions")).to_have_count(0)
    page.wait_for_load_state("networkidle")

    paths = [urlsplit(url).path for url in requests if not url.startswith("data:")]
    assert [path for path in paths if path.startswith("/v1/")] == [], "the showcase must not call the API"
    assert {urlsplit(url).netloc for url in requests if not url.startswith("data:")} == {
        urlsplit(server.base_url).netloc}, "the showcase loads nothing from another host"
    assert "/static/memory-map-demo.json" in paths
    assert page.evaluate("() => sessionStorage.getItem('membrain-page')") is None, "no saved session is written"
    assert console_errors == []


# 2. Persona suggestions through the real confirm() dialogs ---------------------------------------------------------

def test_accepting_a_suggestion_in_the_confirm_dialog_saves_a_new_version_and_redraws_without_reload(
        server, account, page):
    key, client = account
    assert client.set_persona(CARD, made_by="host", reason="Initial character")["version"] == 1
    proposal = seed_feedback(client, "You're too formal.")
    assert (proposal["kind"], proposal["change"]["after"]) == ("less_formal", "casual")
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    expect(page.locator("#persona-version")).to_have_text("Version 1")
    card = page.locator("#persona-proposals .persona-proposal")
    expect(card).to_have_count(1)
    expect(card.locator(".meta strong")).to_have_text("More casual: from 3 messages")
    expect(card.locator(".proposal-sources q")).to_have_text(["You're too formal."] * 3)
    expect(card.locator(".proposal-diff del")).to_have_text("formal")
    expect(card.locator(".proposal-diff ins")).to_have_text("casual")
    expect(page.locator("#persona-proposals-open")).to_have_text("1 waiting")
    accept = card.get_by_role("button", name="Accept", exact=True)

    # Dismissing the dialog changes nothing, on the page or in the service.
    seen = answer_next_dialog(page, accept=False)
    accept.click()
    expect(accept).to_be_enabled()
    assert seen == [("confirm", ACCEPT)]
    expect(card).to_have_count(1)
    expect(page.locator("#persona-version")).to_have_text("Version 1")
    assert client.persona_proposals()["open"] == 1
    assert [version["version"] for version in client.persona_versions()["versions"]] == [1]

    # Accepting saves version 2 from the feedback, and the page shows it without a reload.
    seen = answer_next_dialog(page, accept=True)
    accept.click()
    expect(page.locator("#persona-version")).to_have_text("Version 2")
    assert seen == [("confirm", ACCEPT)]
    expect(page.locator("#persona-view .persona-part").filter(has_text="register")).to_contain_text("casual")
    expect(page.locator("#persona-proposals")).to_have_text("No suggestions waiting.")
    expect(page.locator("#persona-proposals-open")).to_be_hidden()
    expect(page.locator("#persona-proposals-earlier")).to_be_visible()
    earlier = page.locator("#persona-proposals-history .persona-proposal")
    expect(earlier).to_have_count(1)
    expect(earlier).to_contain_text("accepted")
    expect(earlier).to_contain_text(re.compile(r"Accepted on .+ as version 2\."))
    newest = page.locator("#persona-versions .persona-version").first
    expect(newest).to_contain_text("Version 2")
    expect(newest).to_contain_text("from accepted feedback")
    expect(newest).to_contain_text("accepted suggestion")
    expect(newest.locator(".persona-feedback-quotes .user-text")).to_have_text(["“You're too formal.”"] * 3)
    expect(page.locator("#persona-versions .persona-version")).to_have_count(2)
    assert same_page(page), "accepting must not reload the page"

    persona = client.persona()
    assert (persona["version"], persona["card"]["voice"]["register"]) == (2, "casual")
    versions = client.persona_versions()["versions"]
    assert (versions[0]["made_by"], versions[0]["feedback"]["proposal_id"]) == ("feedback", proposal["id"])
    decided = client.persona_proposals()
    assert decided["open"] == 0
    assert [(item["id"], item["status"], item["version"]) for item in decided["proposals"]] == [
        (proposal["id"], "accepted", 2)]


def test_rejecting_a_suggestion_in_the_confirm_dialog_shows_the_pause_and_dismissing_keeps_it_open(
        server, account, page):
    key, client = account
    assert client.set_persona(CARD, made_by="host", reason="Initial character")["version"] == 1
    proposal = seed_feedback(client, "Your replies are too long.")
    assert proposal["kind"] == "shorter"
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    card = page.locator("#persona-proposals .persona-proposal")
    expect(card.locator(".meta strong")).to_have_text("Shorter replies: from 3 messages")
    reject = card.get_by_role("button", name="Reject", exact=True)

    seen = answer_next_dialog(page, accept=False)
    reject.click()
    expect(reject).to_be_enabled()
    assert seen == [("confirm", REJECT)]
    expect(card).to_have_count(1)
    expect(page.locator("#persona-proposals")).not_to_contain_text("paused until")
    assert client.persona_proposals()["open"] == 1 and client.persona_proposals()["pauses"] == []

    seen = answer_next_dialog(page, accept=True)
    reject.click()
    pause = page.locator("#persona-proposals > p.hint")
    expect(pause).to_have_text(re.compile(r"^Shorter replies: paused until \d{1,2} \w{3} \d{4} after you rejected it\.$"))
    assert seen == [("confirm", REJECT)]
    expect(page.locator("#persona-proposals .persona-proposal")).to_have_count(0)
    expect(page.locator("#persona-proposals .empty")).to_have_text("No suggestions waiting.")
    earlier = page.locator("#persona-proposals-history .persona-proposal")
    expect(earlier).to_have_count(1)
    expect(earlier).to_contain_text("rejected")
    expect(earlier).to_contain_text(re.compile(r"Rejected on .+\. None of this kind until .+\."))
    expect(page.locator("#persona-version")).to_have_text("Version 1")
    assert same_page(page), "rejecting must not reload the page"

    listing = client.persona_proposals()
    assert listing["open"] == 0
    assert [(item["id"], item["status"]) for item in listing["proposals"]] == [(proposal["id"], "rejected")]
    assert [pause["kind"] for pause in listing["pauses"]] == ["shorter"]
    assert client.persona()["version"] == 1, "rejecting never changes the card"


def test_the_personality_card_is_edited_restored_and_reset_on_the_page_without_reload(server, account, page):
    key, client = account
    assert client.set_persona(CARD, made_by="host", reason="Initial character", host_default=True)["version"] == 1
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    expect(page.locator("#persona-version")).to_have_text("Version 1")
    expect(page.locator("#persona-view")).to_contain_text("Wren")

    # Edit: the form saves version 2 as the user.
    page.locator("#persona-edit").click()
    form = page.locator("#persona-form")
    expect(form).to_be_visible()
    form.locator('input[name="name"]').fill("Wren the Gardener")
    form.locator('input[name="register"]').fill("casual")
    form.locator('input[name="reason"]').fill("Warmer for daily chats")
    form.get_by_role("button", name="Save as a new version").click()
    expect(page.locator("#persona-version")).to_have_text("Version 2")
    expect(form).to_be_hidden()
    expect(page.locator("#persona-view")).to_contain_text("Wren the Gardener")
    newest = page.locator("#persona-versions .persona-version").first
    expect(newest).to_contain_text("set by you")
    expect(newest).to_contain_text("Warmer for daily chats")

    # Reset: dismissing the confirm changes nothing; accepting returns to the host default as version 3.
    seen = answer_next_dialog(page, accept=False)
    page.locator("#persona-reset").click()
    expect(page.locator("#persona-reset")).to_be_enabled()
    assert len(seen) == 1 and seen[0] == ("confirm", RESET)
    expect(page.locator("#persona-version")).to_have_text("Version 2")
    seen = answer_next_dialog(page, accept=True)
    page.locator("#persona-reset").click()
    expect(page.locator("#persona-version")).to_have_text("Version 3")
    assert seen == [("confirm", RESET)]
    expect(page.locator("#persona-view .user-text").first).to_have_text("Wren")
    expect(page.locator("#persona-versions .persona-version").first).to_contain_text("reset to the host's default")

    # Restore version 2 through the real confirm: its content becomes version 4.
    seen = answer_next_dialog(page, accept=True)
    page.locator("#persona-versions .persona-version", has_text="Version 2").get_by_role(
        "button", name="Restore").click()
    expect(page.locator("#persona-version")).to_have_text("Version 4")
    assert seen == [("confirm", "Restore version 2? Its content becomes a new version.")]
    expect(page.locator("#persona-versions .persona-version").first).to_contain_text("restored from version 2")
    expect(page.locator("#persona-view .user-text").first).to_have_text("Wren the Gardener")
    expect(page.locator("#persona-versions .persona-version")).to_have_count(4)
    assert same_page(page), "editing, restoring and resetting must not reload the page"
    versions = client.persona_versions()["versions"]
    assert [(item["version"], item["action"]) for item in versions][:2] == [(4, "restore"), (3, "reset")]
    assert client.persona()["card"]["name"] == "Wren the Gardener"


# 3. The brain map redraws after an edit or a delete ---------------------------------------------------------------

def test_editing_and_deleting_a_note_on_the_brain_map_redraws_the_map_without_reload(server, account, page):
    key, client = account
    tea = client.write_note("Prefers green tea in the morning.", kind="preference", role="user")
    walk = client.write_note("Walks the dog Biscuit before work.", kind="routine", role="user")
    tea_id, walk_id = f"note:{tea['note_id']}", f"note:{walk['note_id']}"
    labels = map_labels(client)
    assert {tea_id, walk_id} <= set(labels), labels
    sign_in(page, server.base_url, key)
    open_view(page, "brain")
    nodes = page.locator("#brain-canvas circle.brain-node")
    expect(nodes).to_have_count(len(labels))
    expect(page.locator("#brain-summary")).to_contain_text(f"{len(labels)} memories")

    # Edit: the same editor as the Notes tab, opened from the map.
    page.locator(f'#brain-canvas circle.brain-node[data-id="{tea_id}"]').click()
    detail = page.locator("#brain-detail")
    expect(detail).to_contain_text("Prefers green tea in the morning.")
    detail.locator(".brain-note-actions").get_by_role("button", name="Edit", exact=True).click()
    detail.locator("textarea").fill("Prefers jasmine tea in the morning.")
    detail.get_by_role("button", name="Save correction").click()
    expect(page.locator(f'#brain-canvas circle.brain-node[data-id="{tea_id}"]')).to_have_count(0)
    edited = page.locator("#brain-canvas circle.brain-node").filter(
        has=page.locator("title", has_text="Prefers jasmine tea in the morning."))
    expect(edited).to_have_count(1)
    expect(page.locator("#brain-canvas title", has_text="green tea")).to_have_count(0)
    after_edit = map_labels(client)
    assert tea_id not in after_edit and "Prefers jasmine tea in the morning." in after_edit.values()
    expect(nodes).to_have_count(len(after_edit))
    assert same_page(page), "editing on the map must not reload the page"

    # Delete, through the real confirm dialog.
    page.locator(f'#brain-canvas circle.brain-node[data-id="{walk_id}"]').click()
    expect(detail).to_contain_text("Walks the dog Biscuit before work.")
    seen = answer_next_dialog(page, accept=True)
    detail.locator(".brain-note-actions").get_by_role("button", name="Delete", exact=True).click()
    expect(page.locator(f'#brain-canvas circle.brain-node[data-id="{walk_id}"]')).to_have_count(0)
    assert seen == [("confirm", DELETE_NOTE)]
    expect(page.locator("#brain-canvas title", has_text="Biscuit")).to_have_count(0)
    after_delete = map_labels(client)
    assert walk_id not in after_delete and not any("Biscuit" in label for label in after_delete.values())
    expect(nodes).to_have_count(len(after_delete))
    expect(page.locator("#brain-summary")).to_contain_text(f"{len(after_delete)} memories")
    expect(detail).to_be_hidden()
    assert same_page(page), "deleting on the map must not reload the page"


# 4. Every companion section in English and Chinese -----------------------------------------------------------------

SECTIONS = {  # selector: (English, Chinese) strings that must render.
    ".persona-current": [("Current card", "当前设定"), ("Edit personality", "编辑个性"), ("Version 1", "版本 1")],
    "#persona-proposals-card": [("Suggestions from your feedback", "根据你的反馈提出的建议"),
                                ("More casual: from 3 messages", "更随意：来自 3 条消息"),
                                ("waiting for you", "等你决定"), ("What you said:", "你说过的话："),
                                ("Accept", "接受"), ("Reject", "拒绝")],
    "#mood": [("Simulated mood", "模拟心情"), ("Triggers", "触发记录"), ("Reset mood", "重置心情")],
    "#relationship": [("Familiarity", "熟悉程度"), ("How you like to be supported", "你希望被怎样支持"),
                      ("Boundaries", "边界"), ("Shared moments", "共同时刻"),
                      ("Promises kept and missed", "做到和错过的承诺")],
}
FEELINGS = [("Feelings", "感受"), ("you said", "你说的"), ("You said you felt this.", "这是你说过的感受。"),
            ("Clear feelings", "清除感受")]


def companion_brain(client: MemoryClient):
    assert client.set_persona(CARD, made_by="host", reason="Initial character")["version"] == 1
    seed_feedback(client, "You're too formal.")
    client.write_note("Job interview at the bakery on Friday.", kind="plan", role="user",
                      affect={"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported",
                              "topic": "the interview"})
    client.set_support_style("Listen first; advice only when asked.")
    client.add_boundary("the old flat", ["旧公寓"])
    assert client.affect_records()["records"], "the fictional feeling is stored"


def assert_language(page, language: str):
    index = 0 if language == "en" else 1
    for selector, pairs in SECTIONS.items():
        section = page.locator(selector)
        for pair in pairs:
            expect(section).to_contain_text(pair[index])
        if language == "zh":
            assert untranslated(page, selector) == [], selector
    expect(page.locator("#view-persona h1").first).to_have_text("Personality" if language == "en" else "个性")
    expect(page.locator("#relationship h1")).to_have_text("Relationship" if language == "en" else "关系")


def test_every_companion_section_renders_in_english_and_chinese_and_the_switch_keeps_the_view(
        server, account, page):
    key, client = account
    companion_brain(client)
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    expect(page.locator("#persona-proposals .persona-proposal")).to_have_count(1)
    assert_language(page, "en")
    expect(page.locator("#language")).to_have_text("中文")

    # The page's own language control reloads in Chinese and stays on the Companion tab.
    switch_language(page, "zh")
    expect(page.locator("#view-persona")).to_be_visible()
    expect(page.locator('#tabs button[data-view="persona"]')).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator("#view-notes")).to_be_hidden()
    expect(page.locator('#tabs button[data-view="persona"]')).to_have_text("伙伴")
    expect(page.locator("#persona-proposals .persona-proposal")).to_have_count(1)
    assert_language(page, "zh")
    # The native dialog asks in Chinese too; dismissing it changes nothing.
    seen = answer_next_dialog(page, accept=False)
    page.locator("#persona-proposals .persona-proposal button").first.click()
    expect(page.locator("#persona-proposals .persona-proposal")).to_have_count(1)
    assert len(seen) == 1 and seen[0][0] == "confirm" and re.search(r"[一-鿿]", seen[0][1]), seen
    assert client.persona_proposals()["open"] == 1

    open_view(page, "feelings")
    feelings = page.locator("#view-feelings")
    expect(feelings.locator(".feeling")).to_have_count(1)
    for _, chinese in FEELINGS:
        expect(feelings).to_contain_text(chinese)
    assert untranslated(page, "#view-feelings") == []

    # Back to English, still on the Feelings tab.
    switch_language(page, "en")
    expect(page.locator("#view-feelings")).to_be_visible()
    expect(page.locator('#tabs button[data-view="feelings"]')).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator("#language")).to_have_text("中文")
    for english, _ in FEELINGS:
        expect(feelings).to_contain_text(english)
    open_view(page, "persona")
    assert_language(page, "en")


# 5. Layout --------------------------------------------------------------------------------------------------------

def test_no_view_scrolls_sideways_at_desktop_or_phone_width_in_either_language(server, account, page):
    key, client = account
    companion_brain(client)
    client.write_note("Walks the dog Biscuit before work.", kind="routine", role="user")
    sign_in(page, server.base_url, key)
    for language in ("en", "zh"):
        if language == "zh":
            switch_language(page, "zh")
        for size in (DESKTOP, PHONE):
            page.set_viewport_size(size)
            for view in VIEWS:
                open_view(page, view)
                page.wait_for_load_state("networkidle")
                assert_no_horizontal_scroll(page, f"{view} in {language} at {size['width']} px")
