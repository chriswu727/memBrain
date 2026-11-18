"""Gap 21 of the maturity test matrix: the memory page (/memory) in a real headless Chromium, against a real service and
database. The showcase makes no API request; persona suggestions are accepted, rejected and dismissed through the
page's own native confirm() dialogs; a note corrected by the agent or deleted on the brain map redraws the map; every
companion section renders in English and Chinese, and the language switch keeps the current view; the page never
scrolls sideways. Since 2026-11-18 the page is for looking, checking sources and deleting: it offers no text entry
for memory content in any view, every item it lists can still be deleted there, and the rarely used whole-memory
controls sit in a collapsed "More" at the end of their view.

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
RESET = ("Pick another personality type at random? It is saved as a new version, and earlier versions can be "
         "restored. The mood, familiarity and what you agreed with your agent carry over.")
DELETE_NOTE = "Delete this note? Its content is erased."
# English words that may stay in the Chinese page: product names, and "agent", which the Chinese text keeps.
# The four-letter personality type codes (and the name of the scheme they come from) read the same in Chinese.
TYPE_CODES = {"INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP",
              "ISFP", "ESTP", "ESFP", "MBTI"}
ENGLISH_KEPT = {"memBrain", "agent", "Claude", "Code", "Codex", "hook", *TYPE_CODES}
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
    keys = [f"gap21-{uuid.uuid4()}" for _ in range(16)]
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

@pytest.mark.parametrize("saved_session", [
    pytest.param(None, id="no-saved-session"),
    pytest.param({"key": "fictional-saved-key", "brain": "fictional-saved-brain", "view": "persona"},
                 id="saved-real-session"),
])
def test_showcase_shows_fictional_data_and_makes_no_api_request(server, page, saved_session):
    requests, console_errors = [], []
    if saved_session is not None:
        page.add_init_script("sessionStorage.setItem('membrain-page', JSON.stringify(" + json.dumps(saved_session) + "));")
    page.on("request", lambda request: requests.append(request.url))
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(f"{server.base_url}/memory?demo=brain&show=1")
    expect(page.locator("#brain-show")).to_be_visible()
    page.wait_for_function("() => window.memoryHologram.snapshot().ready")
    expect(page.locator("#show-simulation")).to_be_visible()
    expect(page.locator("#show-fictional")).to_be_visible()
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
    page.locator("#mode-2d").click()  # The 2D map; the 3D view has its own tests (test_memory_observatory_browser.py).
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
    saved = page.evaluate("() => sessionStorage.getItem('membrain-page')")
    assert (json.loads(saved) if saved else None) == saved_session, "demo mode leaves saved real sessions unchanged"
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


def test_the_personality_card_is_switched_and_restored_on_the_page_without_reload(server, account, page):
    key, client = account
    assert client.set_persona(CARD, made_by="host", reason="Initial character", host_default=True)["version"] == 1
    # Version 2 as an earlier runtime's page editor saved it (made by the user); the page has no editor any more.
    assert client.set_persona({**CARD, "name": "Wren the Gardener", "voice": {**CARD["voice"], "register": "casual"}},
                              made_by="user", reason="Warmer for daily chats")["version"] == 2
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    expect(page.locator("#persona-version")).to_have_text("Version 2")
    expect(page.locator("#persona-view")).to_contain_text("Wren the Gardener")
    newest = page.locator("#persona-versions .persona-version").first
    expect(newest).to_contain_text("set by you")
    expect(newest).to_contain_text("Warmer for daily chats")
    expect(page.locator("#persona-form, #persona-edit")).to_have_count(0)
    expect(page.locator("#view-persona").get_by_role("button", name="Edit personality")).to_have_count(0)

    # Pick another at random: dismissing the confirm changes nothing; accepting saves a personality type as version 3.
    seen = answer_next_dialog(page, accept=False)
    page.locator("#persona-random").click()
    expect(page.locator("#persona-random")).to_be_enabled()
    assert len(seen) == 1 and seen[0] == ("confirm", RESET)
    expect(page.locator("#persona-version")).to_have_text("Version 2")
    seen = answer_next_dialog(page, accept=True)
    page.locator("#persona-random").click()
    expect(page.locator("#persona-version")).to_have_text("Version 3")
    assert seen == [("confirm", RESET)]
    expect(page.locator("#persona-preset")).to_contain_text("Personality type:")
    expect(page.locator("#persona-versions .persona-version").first).to_contain_text("switched type")

    # Restore version 2 through the real confirm: its content becomes version 4.
    seen = answer_next_dialog(page, accept=True)
    page.locator("#persona-versions .persona-version", has_text="Version 2").get_by_role(
        "button", name="Restore").click()
    expect(page.locator("#persona-version")).to_have_text("Version 4")
    assert seen == [("confirm", "Restore version 2? Its content becomes a new version.")]
    expect(page.locator("#persona-versions .persona-version").first).to_contain_text("restored from version 2")
    expect(page.locator("#persona-view .user-text").first).to_have_text("Wren the Gardener")
    expect(page.locator("#persona-versions .persona-version")).to_have_count(4)
    assert same_page(page), "switching and restoring must not reload the page"
    versions = client.persona_versions()["versions"]
    assert [(item["version"], item["action"]) for item in versions][:2] == [(4, "restore"), (3, "preset")]
    assert client.persona()["card"]["name"] == "Wren the Gardener"



def test_the_rarely_used_relationship_reset_is_tucked_away_and_still_confirms(server, account, page):
    # Owner, 2026-11-18: most people rarely reset the relationship, so it is in the collapsed "More" at the end of the
    # Companion view, a text-style button, still behind its confirmation; it keeps the boundaries.
    key, client = account
    client.add_boundary("old workplace")
    client.write_note("We finished a puzzle together.", kind="milestone", shared=True)
    sign_in(page, server.base_url, key)
    open_view(page, "persona")
    more = page.locator("#companion-more")
    expect(more).to_have_js_property("open", False)
    expect(page.locator("#relationship-reset")).to_be_hidden()
    assert page.locator("#view-persona .card.danger").count() == 0
    assert "danger" in page.locator("#relationship-reset").get_attribute("class") and "link" in page.locator(
        "#relationship-reset").get_attribute("class")
    more.locator("summary").focus()
    page.keyboard.press("Enter")  # Reachable by keyboard.
    expect(page.locator("#relationship-reset")).to_be_visible()
    seen = answer_next_dialog(page, accept=False)
    page.locator("#relationship-reset").click()
    expect(page.locator("#relationship-reset")).to_be_enabled()
    assert len(seen) == 1 and seen[0][0] == "confirm" and seen[0][1].startswith("Reset the relationship?")
    assert len(client.relationship()["shared_moments"]) == 1  # Dismissed: nothing changed.
    seen = answer_next_dialog(page, accept=True)
    page.locator("#relationship-reset").click()
    expect(page.locator("#relationship-marker")).to_be_visible()
    assert client.relationship()["shared_moments"] == []
    assert [item["topic"] for item in client.relationship()["boundaries"]] == ["old workplace"]
    expect(page.locator("#boundaries")).to_contain_text("old workplace")
    expect(page.locator("#moments")).not_to_contain_text("puzzle")
    assert same_page(page)
    switch_language(page, "zh")
    open_view(page, "persona")
    expect(page.locator("#companion-more summary")).to_have_text("更多")

# 3. The brain map redraws after a correction or a delete ----------------------------------------------------------

def test_a_note_corrected_by_the_agent_or_deleted_on_the_brain_map_redraws_the_map_without_reload(
        server, account, page):
    key, client = account
    tea = client.write_note("Prefers green tea in the morning.", kind="preference", role="user")
    walk = client.write_note("Walks the dog Biscuit before work.", kind="routine", role="user")
    tea_id, walk_id = f"note:{tea['note_id']}", f"note:{walk['note_id']}"
    labels = map_labels(client)
    assert {tea_id, walk_id} <= set(labels), labels
    sign_in(page, server.base_url, key)
    open_view(page, "brain")
    page.locator("#mode-2d").click()  # The 2D map; the 3D view has its own tests (test_memory_observatory_browser.py).
    nodes = page.locator("#brain-canvas circle.brain-node")
    expect(nodes).to_have_count(len(labels))
    expect(page.locator("#brain-summary")).to_contain_text(f"{len(labels)} memories")

    # The map offers no editor (2026-11-18): the user tells the agent, which saves the corrected note in the old
    # one's place, as memory_note with replaces does. Opening the map again shows it without reloading the page.
    page.locator(f'#brain-canvas circle.brain-node[data-id="{tea_id}"]').click()
    detail = page.locator("#brain-detail")
    expect(detail).to_contain_text("Prefers green tea in the morning.")
    expect(detail.locator(".brain-note-actions button")).to_have_text(["Delete"])
    expect(detail.locator("textarea, input")).to_have_count(0)
    client.write_note("Prefers jasmine tea in the morning.", kind="preference", replaces=[tea["note_id"]])
    open_view(page, "notes")
    open_view(page, "brain")
    expect(page.locator(f'#brain-canvas circle.brain-node[data-id="{tea_id}"]')).to_have_count(0)
    edited = page.locator("#brain-canvas circle.brain-node").filter(
        has=page.locator("title", has_text="Prefers jasmine tea in the morning."))
    expect(edited).to_have_count(1)
    expect(page.locator("#brain-canvas title", has_text="green tea")).to_have_count(0)
    after_edit = map_labels(client)
    assert tea_id not in after_edit and "Prefers jasmine tea in the morning." in after_edit.values()
    expect(nodes).to_have_count(len(after_edit))
    assert same_page(page), "a redrawn map must not reload the page"

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


@pytest.mark.parametrize("mode", ["2d", "3d"])
def test_masked_map_details_hide_recording_time_and_preserve_public_dates(server, account, page, mode):
    key, client = account
    private = client.write_note("A private planetarium appointment.", kind="plan", sensitive=True,
                                due="2026-11-08")
    public = client.write_note("Bring the blue folder.", kind="plan")
    sign_in(page, server.base_url, key)
    open_view(page, "brain")
    if mode == "2d":
        page.locator("#mode-2d").click()
        selector = '#brain-canvas circle.brain-node'
    else:
        selector = '#observatory-list button'
    page.locator(f'{selector}[data-id="note:{private["note_id"]}"]').click()
    detail = page.locator("#brain-detail")
    expect(detail).to_be_visible()
    expect(detail).to_contain_text("Sensitive memory")
    expect(detail).not_to_contain_text("planetarium")
    expect(detail).not_to_contain_text("2026-11-08")
    expect(detail).not_to_contain_text("Saved:")
    page.locator(f'{selector}[data-id="note:{public["note_id"]}"]').click()
    expect(detail).to_contain_text("Bring the blue folder.")
    expect(detail).to_contain_text("Saved:")


# 4. Every companion section in English and Chinese -----------------------------------------------------------------

SECTIONS = {  # selector: (English, Chinese) strings that must render.
    ".persona-current": [("Current card", "当前设定"), ("Pick another at random", "随机换一个"), ("Version 1", "版本 1")],
    "#persona-proposals-card": [("Suggestions from your feedback", "根据你的反馈提出的建议"),
                                ("More casual: from 3 messages", "更随意：来自 3 条消息"),
                                ("waiting for you", "等你决定"), ("What you said:", "你说过的话："),
                                ("Accept", "接受"), ("Reject", "拒绝")],
    "#mood": [("Simulated mood", "模拟心情"), ("Triggers", "触发记录")],
    "#relationship": [("Familiarity", "熟悉程度"), ("Boundaries", "边界"), ("Shared moments", "共同时刻"),
                      ("Promises kept and missed", "做到和错过的承诺")],
    # Collapsed, but its text is translated all the same.
    "#companion-more": [("More", "更多"), ("Keep the mood at its baseline", "让心情保持在基础心情"),
                        ("Reset mood", "重置心情"), ("Reset relationship", "重置关系"),
                        ("Delete personality history", "删除人格历史")],
}
FEELINGS = [("Feelings", "感受"), ("you said", "你说的"), ("You said you felt this.", "这是你说过的感受。"),
            ("Clear feelings", "清除感受")]


def companion_brain(client: MemoryClient):
    assert client.set_persona(CARD, made_by="host", reason="Initial character")["version"] == 1
    seed_feedback(client, "You're too formal.")
    client.write_note("Job interview at the bakery on Friday.", kind="plan", role="user",
                      affect={"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported",
                              "topic": "the interview"})
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
    expect(page.locator("#view-persona h1").first).to_have_text("Personality" if language == "en" else "人格")
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


# 5. Look, check the source, delete (owner, 2026-11-18) -------------------------------------------------------------
# Users do not type memory content on the page: the agent writes it when they say so. The page shows what is kept and
# where it came from, deletes it, and holds a few whole-memory controls.

# Every control on the page that takes typed text or a value, and why it is not a memory edit.
ALLOWED_INPUTS = {
    "key": "the access key (signing in)",
    "search-text": "search: a lookup, nothing is saved",
    "erase-confirm": "the typed guard of Erase everything",
    "setup-host": "select: which install command to show",
    "brain-layer": "select: which graph to draw",
    "persona-preset-choice": "select: the personality type that the one-click Switch takes",
    "pause-hours": "select: how long Pause device capture lasts",
    "show-completed": "checkbox: a filter of the Plans view",
    "mood-pin": "checkbox: the mood pin, a whole-memory switch under More",
}
FORMS = {"key-form", "search-form"}
# The note editor's seven entry points, the persona card editor, the support style, cap and boundary forms.
GONE_IDS = ("add-note", "note-form-host", "first-preference", "persona-form", "persona-edit", "persona-cancel",
            "support-form", "support-text", "relationship-cap", "relationship-cap-save", "boundary-form",
            "boundary-topic", "boundary-aliases", "moment-add", "moment-form-host", "relationship-more")
GONE_BUTTONS = ("Edit", "Add a note", "Add note", "Save correction", "Merge duplicate", "Save as note",
                "Add a preference here", "Edit personality", "Save as a new version", "Save support style",
                "Save limit", "Add boundary", "Add a shared moment")
GONE_FUNCTIONS = ("noteEditor", "resetNoteForm", "field", "duplicatePairs", "personaForm", "personaControl",
                  "observe")


def rich_brain(client: MemoryClient) -> dict:
    """Something in every view: notes of each kind (one pair a likely duplicate, which used to offer "Merge
    duplicate"), conversations, a feeling, a boundary, a shared moment with its source message, a promise, the
    persona with a suggestion."""
    companion_brain(client)
    source = client.observe("We finally finished the 1000-piece puzzle together!", conversation_id="gap21-chat-4",
                            branch_id="main", source_event_key=f"gap21-{uuid.uuid4()}",
                            producer_ref="gap21-browser-test")["result"]["accepted_event_ids"][0]
    moment = client.write_note("We finished the 1000-piece puzzle together.", kind="milestone", shared=True,
                               moment="play", source_event_ids=[source])
    client.observe("The weather is lovely today.", conversation_id="gap21-chat-5", branch_id="main",
                   source_event_key=f"gap21-{uuid.uuid4()}", producer_ref="gap21-browser-test")
    sam = client.write_note("Sam is my running partner.", kind="person", about="Sam")
    client.write_note("Training for a 10k with Sam.", kind="plan", about="Sam", due="2026-12-01")
    client.write_note("Prefers green tea in the morning.", kind="preference")
    client.write_note("Prefers green tea in the mornings.", kind="preference")
    client.write_note("Send Sam the training plan.", kind="agent_commitment", status="intended", due="2026-12-01")
    return {"moment": moment["note_id"], "source": source, "sam": sam["note_id"],
            "feeling": client.affect_records()["records"][0]["id"]}


def open_every_disclosure(page):
    """Open every <details>, so what a click would reveal (sources, earlier suggestions, More) is on the page too."""
    page.evaluate("() => document.querySelectorAll('details').forEach((item) => { item.open = true; })")
    page.wait_for_load_state("networkidle")


def text_entry(page) -> dict:
    return page.evaluate("""(gone) => ({
        controls: [...document.querySelectorAll('input, textarea, select')].map((item) => ({
            id: item.id, tag: item.tagName.toLowerCase(), type: item.type || ''})),
        editable: [...document.querySelectorAll('*')].filter((item) => item.isContentEditable).length,
        forms: [...document.querySelectorAll('form')].map((form) => form.id),
        ids: gone.ids.filter((id) => document.getElementById(id)),
        buttons: [...document.querySelectorAll('button')].map((button) => button.textContent.trim())
            .filter((text) => gone.buttons.includes(text)),
        functions: gone.functions.filter((name) => typeof window[name] === 'function'),
    })""", {"ids": list(GONE_IDS), "buttons": list(GONE_BUTTONS), "functions": list(GONE_FUNCTIONS)})


def assert_no_text_entry(page, where: str):
    found = text_entry(page)
    assert [item for item in found["controls"] if item["id"] not in ALLOWED_INPUTS] == [], where
    assert not any(item["tag"] == "textarea" for item in found["controls"]), where
    assert found["editable"] == 0 and set(found["forms"]) <= FORMS, (where, found)
    assert (found["ids"], found["buttons"], found["functions"]) == ([], [], []), (where, found)


def test_the_page_offers_no_text_entry_for_memory_content_in_any_view(server, account, page):
    key, client = account
    ids = rich_brain(client)
    sign_in(page, server.base_url, key)
    assert_no_text_entry(page, "after signing in")
    for view in VIEWS:
        open_view(page, view)
        page.wait_for_load_state("networkidle")
        open_every_disclosure(page)
        assert_no_text_entry(page, view)
    # Where a form used to be, the page says what to tell the agent instead.
    open_view(page, "persona")
    expect(page.locator("#relationship")).to_contain_text("To add one, tell your agent")
    expect(page.locator("#view-persona .heading .muted").first).to_contain_text("To change it, ask your agent")
    open_view(page, "notes")
    expect(page.locator("#view-notes .heading")).to_contain_text("tell your agent and it saves the corrected note")
    expect(page.locator("#view-notes")).not_to_contain_text("take precedence")
    expect(page.locator("#notes")).not_to_contain_text("Edit to attach its source")
    # A detail opened on the brain map offers Delete, never an editor, for a note and for a feeling.
    open_view(page, "brain")
    page.locator("#mode-2d").click()
    detail = page.locator("#brain-detail")
    for node, delete in ((f"note:{ids['sam']}", "Delete"), (f"affect:{ids['feeling']}", "Delete this feeling")):
        page.locator(f'#brain-canvas circle.brain-node[data-id="{node}"]').click()
        expect(detail).to_be_visible()
        expect(detail.locator(".brain-note-actions button")).to_have_text([delete])
        assert_no_text_entry(page, f"brain detail of {node}")
    # The first-use panel's example sentence stays; its "Add a preference here" button is gone.
    expect(page.locator("#first-use")).to_contain_text("Tell your agent a real preference")
    assert same_page(page)


def test_every_item_the_page_lists_can_still_be_deleted_where_it_could_before(server, account, page):
    key, client = account
    ids = rich_brain(client)
    sign_in(page, server.base_url, key)
    # Notes, People and Plans: one Delete per note, and nothing else to click on it.
    for view in ("notes", "people", "plans"):
        open_view(page, view)
        items = page.locator(f"#{view} article.item")
        expect(items.first).to_be_visible()
        expect(items.locator(".meta .actions button")).to_have_text(["Delete"] * items.count())
    open_view(page, "people")
    seen = answer_next_dialog(page, accept=True)
    page.locator("#people article.item", has_text="Sam is my running partner.").get_by_role(
        "button", name="Delete").click()
    expect(page.locator("#people")).not_to_contain_text("Sam is my running partner.")
    assert seen == [("confirm", DELETE_NOTE)]
    assert ids["sam"] not in {item["event_id"] for item in client.timeline(
        roles=("assistant", "user"), conversation_id="membrain-notes")["items"]}

    # Conversations: Delete on every message, and Delete this conversation.
    open_view(page, "conversations")
    conversations = page.locator("#conversations > details.item")
    expect(conversations.first).to_be_visible()
    expect(conversations.locator(":scope > button")).to_have_text(
        ["Delete this conversation"] * conversations.count())
    open_every_disclosure(page)
    messages = page.locator("#conversations .message")
    expect(messages.locator(".actions button")).to_have_text(["Delete"] * messages.count())
    weather = page.locator("#conversations .message", has_text="The weather is lovely today.")
    seen = answer_next_dialog(page, accept=True)
    weather.get_by_role("button", name="Delete").click()
    expect(page.locator("#conversations .message", has_text="The weather is lovely today.")).to_have_count(0)
    assert seen[0][1].startswith("Delete this message?")

    # The brain map: Delete on a note's detail and on a feeling's.
    open_view(page, "brain")
    page.locator("#mode-2d").click()
    page.locator(f'#brain-canvas circle.brain-node[data-id="affect:{ids["feeling"]}"]').click()
    expect(page.locator("#brain-detail .brain-note-actions button")).to_have_text(["Delete this feeling"])

    # Feelings: Delete on each.
    open_view(page, "feelings")
    feelings = page.locator("#feelings .feeling")
    expect(feelings).to_have_count(1)
    seen = answer_next_dialog(page, accept=True)
    feelings.get_by_role("button", name="Delete").click()
    expect(feelings).to_have_count(0)
    assert client.affect_records()["records"] == [] and seen[0][1].startswith("Delete this feeling?")

    # Companion: Remove on each boundary, Delete on each shared moment (with its original message), Restore on each
    # earlier personality version, Accept and Reject on a suggestion.
    open_view(page, "persona")
    boundary = page.locator("#boundaries .relationship-boundary")
    expect(boundary.locator(".actions button")).to_have_text(["Remove"])
    moment = page.locator("#moments .relationship-moment")
    expect(moment.locator(".actions button")).to_have_text(["Delete"])
    expect(moment.locator("details summary")).to_have_text("1 original message")
    moment.locator("details summary").click()
    expect(moment.locator("details")).to_contain_text("We finally finished the 1000-piece puzzle together!")
    expect(page.locator("#persona-proposals .persona-proposal button")).to_have_text(["Accept", "Reject"])
    seen = answer_next_dialog(page, accept=True)
    boundary.get_by_role("button", name="Remove").click()
    expect(page.locator("#boundaries .relationship-boundary")).to_have_count(0)
    assert client.relationship()["boundaries"] == [] and seen[0][1].startswith("Remove this boundary?")
    seen = answer_next_dialog(page, accept=True)
    moment.get_by_role("button", name="Delete").click()
    expect(page.locator("#moments .relationship-moment")).to_have_count(0)
    assert client.relationship()["shared_moments"] == [] and seen[0][1].startswith("Delete this shared moment?")
    assert same_page(page), "deleting must not reload the page"


def test_the_more_sections_hold_the_rarely_used_controls_collapsed_by_default(server, account, page):
    key, client = account
    companion_brain(client)
    versions = len(client.persona_versions()["versions"])
    sign_in(page, server.base_url, key)

    # Companion: one "More" at the end of the view, closed, holding exactly these four controls.
    open_view(page, "persona")
    more = page.locator("#companion-more")
    expect(more).to_have_js_property("open", False)
    assert page.evaluate("() => document.getElementById('view-persona').lastElementChild.id") == "companion-more"
    controls = more.evaluate("(root) => [...root.querySelectorAll('button, input, select, textarea')].map((e) => e.id)")
    assert controls == ["mood-pin", "mood-reset", "relationship-reset", "persona-delete-history"]
    for ident in controls:
        expect(page.locator(f"#{ident}")).to_be_hidden()
    expect(page.locator("#mood button, #mood input")).to_have_count(0)  # Nothing of them is left on the cards.
    more.locator("summary").click()
    # The mood pin is the only way to turn the simulated mood off: still here, and it still works.
    page.locator("#mood-pin").check()
    expect(page.locator("#mood-why")).to_contain_text("Pinned to its baseline")
    assert client.mood()["pinned"] is True
    page.locator("#mood-pin").uncheck()
    expect(page.locator("#mood-why")).not_to_contain_text("Pinned to its baseline")
    assert client.mood()["pinned"] is False
    # Reset mood and Delete personality history still ask first; dismissing changes nothing.
    for ident, question in (("mood-reset", "Put the mood back at its baseline"),
                            ("persona-delete-history", "Delete every personality version")):
        seen = answer_next_dialog(page, accept=False)
        page.locator(f"#{ident}").click()
        expect(page.locator(f"#{ident}")).to_be_enabled()
        assert len(seen) == 1 and seen[0][1].startswith(question), seen
    assert len(client.persona_versions()["versions"]) == versions and client.mood()["marker"] is None

    # Feelings: its own "More" at the end, closed, with Clear feelings only.
    open_view(page, "feelings")
    feelings_more = page.locator("#feelings-more")
    expect(feelings_more).to_have_js_property("open", False)
    assert page.evaluate("() => document.getElementById('view-feelings').lastElementChild.id") == "feelings-more"
    assert feelings_more.evaluate("(root) => [...root.querySelectorAll('button, input')].map((e) => e.id)") == [
        "clear-feelings"]
    expect(page.locator("#clear-feelings")).to_be_hidden()
    feelings_more.locator("summary").click()
    seen = answer_next_dialog(page, accept=False)
    page.locator("#clear-feelings").click()
    expect(page.locator("#clear-feelings")).to_be_enabled()
    assert len(seen) == 1 and seen[0][1].startswith("Clear every recorded feeling")
    assert len(client.affect_records()["records"]) == 1

    # Privacy: Erase everything stays where it was, visible, with its typed guard.
    open_view(page, "privacy")
    expect(page.locator("#erase")).to_be_visible()
    expect(page.locator("#erase-confirm")).to_be_visible()
    assert page.evaluate("() => document.getElementById('erase').closest('details') === null")
    assert same_page(page)


# 6. Layout --------------------------------------------------------------------------------------------------------

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
