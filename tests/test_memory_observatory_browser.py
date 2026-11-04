"""The memory page's 3D observatory in a real headless Chromium (software WebGL here, SwiftShader in CI), against a
real service and database on an ephemeral port: pixels, rotation, zoom, picking, the shared detail panel with edit and
delete through the native confirm dialog, recalled records, the keyboard list, reduced motion, WebGL loss and absence,
frames only on demand, disposal when switching away, deletions, resets and restores reflected in the scene, network
isolation, English and Chinese, and no sideways scroll.

All data is fictional. Without Playwright, Chromium or the test database the module is skipped, unless
MEMBRAIN_REQUIRE_BROWSER=1, which turns every such skip into a failure. Rendering measurements are not asserted here;
scripts/measure_observatory.py reports them.
"""
import hashlib
import importlib.util
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import uuid
import zlib
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

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "membrain" / "web"
REQUIRED = os.environ.get("MEMBRAIN_REQUIRE_BROWSER") == "1"
DESKTOP, PHONE = {"width": 1280, "height": 900}, {"width": 390, "height": 844}
DEMO = json.loads((WEB / "memory-map-demo.json").read_text(encoding="utf-8"))
DELETE_NOTE = "Delete this note? Its content is erased."
LOST = "The 3D view lost its graphics context. Showing the 2D map until the browser restores it."
UNSUPPORTED = ("The 3D view needs WebGL 2, which this browser does not provide or has turned off. Showing the 2D map "
               "and the list instead.")
ENGLISH_KEPT = {"memBrain", "agent", "WebGL", "Home", "Enter", "about", "3D", "2D"}
RAF_COUNTER = """(() => {
  const original = window.requestAnimationFrame.bind(window);
  window.__rafCalls = 0;
  window.requestAnimationFrame = (callback) => { window.__rafCalls += 1; return original(callback); };
})();"""
NO_WEBGL = """(() => {
  const original = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
    return /webgl/i.test(type) ? null : original.call(this, type, ...rest);
  };
})();"""


def _measurement():
    spec = importlib.util.spec_from_file_location("measure_observatory", ROOT / "scripts" / "measure_observatory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    keys = [f"observatory-{uuid.uuid4()}" for _ in range(6)]
    key_file = tmp_path_factory.mktemp("observatory") / "keys.json"
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
    key = server.keys.pop()
    with MemoryClient(server.base_url, key) as client:
        client.brain_id = client.create_brain("Observatory browser test")["id"]
        yield key, client


class Tab:
    """A page plus everything it requested and every uncaught error, for the test's assertions."""

    def __init__(self, page):
        self.page, self.requests, self.errors = page, [], []


def _tab(browser, **options):
    context = browser.new_context(**{"viewport": DESKTOP, "locale": "en-US", **options})
    context.add_init_script(RAF_COUNTER)
    page = context.new_page()
    page.set_default_timeout(20_000)
    tab = Tab(page)
    page.on("request", lambda request: tab.requests.append(request.url))
    page.on("pageerror", lambda error: tab.errors.append(str(error)))
    page.on("console", lambda message: tab.errors.append(message.text) if message.type == "error" else None)
    return context, tab


@pytest.fixture
def tab(browser):
    context, opened = _tab(browser)
    yield opened
    context.close()
    assert opened.errors == [], "uncaught errors on the page"


# Helpers ----------------------------------------------------------------------------------------------------------

def snapshot(page) -> dict:
    return page.evaluate("() => window.observatory.snapshot()")


def settled(page, generation: int = 1):
    """Wait until the 3D view has drawn the map (at least this generation) and nothing is queued or moving."""
    page.wait_for_function(f"""() => {{ const s = window.observatory && window.observatory.snapshot();
        return s && s.active && s.generation >= {generation} && s.renders > 0 && !s.pending && !s.animating; }}""")
    return snapshot(page)


def wait_for_frame(page, before: int):
    page.wait_for_function(f"""() => {{ const s = window.observatory.snapshot();
        return s.renders > {before} && !s.pending && !s.animating; }}""")
    return snapshot(page)


def open_demo(page, base_url, query=""):
    page.goto(f"{base_url}/memory?demo=brain{query}")
    expect(page.locator("#view-brain")).to_be_visible()
    return settled(page)


def sign_in(page, base_url: str, key: str):
    page.goto(f"{base_url}/memory")
    page.locator("#signin summary").click()
    page.fill("#key", key)
    page.locator("#key-form button[type=submit]").click()
    expect(page.locator("#tabs")).to_be_visible()
    page.evaluate("() => { window.observatorySamePage = true; }")


def open_brain(page):
    page.locator('#tabs button[data-view="brain"]').click()
    expect(page.locator("#view-brain")).to_be_visible()


def answer_next_dialog(page, accept: bool) -> list:
    seen = []

    def handle(dialog):
        seen.append((dialog.type, dialog.message))
        dialog.accept() if accept else dialog.dismiss()

    page.once("dialog", handle)
    return seen


def pickable(page, ids=None) -> dict:
    """A node, its projected centre computed in the page, for which a pick at that point resolves to the node."""
    found = page.evaluate("""(ids) => {
        for (const id of ids || window.observatory.snapshot().nodes) {
            const at = window.observatory.project(id);
            if (at && at.inside && window.observatory.pickAt(at.x, at.y) === id) return { id, x: at.x, y: at.y };
        }
        return null;
    }""", ids)
    assert found, "no node can be picked at its projected centre"
    return found


def click_node(page, node_id: str):
    target = pickable(page, [node_id])
    page.mouse.move(target["x"], target["y"])
    page.mouse.down()
    page.mouse.up()
    expect(page.locator("#brain-detail")).to_be_visible()
    assert snapshot(page)["selected"] == node_id


def _png_pixels(data: bytes):
    """Decode an 8-bit RGB or RGBA PNG (what Chromium screenshots are) into rows of RGB tuples."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    position, chunks, header = 8, [], None
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            chunks.append(body)
        position += length + 12
    width, height, depth, colour, _, _, interlace = header
    assert depth == 8 and colour in (2, 6) and interlace == 0, header
    channels = 3 if colour == 2 else 4
    raw, stride, rows, previous = zlib.decompress(b"".join(chunks)), width * channels, [], bytearray(width * channels)
    for row in range(height):
        start = row * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for index in range(stride):
            left = line[index - channels] if index >= channels else 0
            up, corner = previous[index], previous[index - channels] if index >= channels else 0
            if kind == 1:
                line[index] = (line[index] + left) & 255
            elif kind == 2:
                line[index] = (line[index] + up) & 255
            elif kind == 3:
                line[index] = (line[index] + (left + up) // 2) & 255
            elif kind == 4:
                guess = left + up - corner
                pa, pb, pc = abs(guess - left), abs(guess - up), abs(guess - corner)
                line[index] = (line[index] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
        rows.append([tuple(line[i:i + 3]) for i in range(0, stride, channels)])
        previous = line
    return rows


def canvas_pixels(page) -> dict:
    rows = _png_pixels(page.locator("#observatory-canvas").screenshot())
    pixels = [pixel for row in rows for pixel in row]
    background = max(set(pixels[::97]), key=pixels[::97].count)
    differing = sum(1 for pixel in pixels if sum(abs(a - b) for a, b in zip(pixel, background)) > 40)
    saturated = {pixel for pixel in pixels if max(pixel) - min(pixel) > 60}
    return {"total": len(pixels), "differing": differing, "colours": len(set(pixels)), "saturated": len(saturated)}


def edge_keys(payload) -> set:
    return {f"{edge['type']}:{edge['source']}>{edge['target']}" for edge in payload["edges"]}


def assert_no_horizontal_scroll(page, where: str):
    widths = page.evaluate("""() => ({ page: document.documentElement.scrollWidth,
        body: document.body.scrollWidth, viewport: document.documentElement.clientWidth })""")
    assert max(widths["page"], widths["body"]) <= widths["viewport"], (where, widths)


def untranslated(page, selector: str) -> list[str]:
    texts = page.locator(selector).evaluate("""(root) => {
        const out = [];
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (node.parentElement.closest(".user-text, pre, code, script, style, [hidden]")) continue;
            const text = node.nodeValue.replace(/\\s+/g, " ").trim();
            if (text) out.push(text);
        }
        for (const element of root.querySelectorAll("[aria-label], [title]")) {
            for (const name of ["aria-label", "title"]) if (element.getAttribute(name)) out.push(element.getAttribute(name));
        }
        return out;
    }""")
    return [text for text in texts if set(re.findall(r"[A-Za-z]{2,}", text)) - ENGLISH_KEPT]


def seeded_brain(client: MemoryClient) -> dict:
    """Fictional notes with a source message, a person link, a feeling, a shared moment and a recorded recall."""
    client.observe("I like jasmine tea after dinner.", conversation_id="observatory-chat", branch_id="main",
                   source_event_key=f"observatory-{uuid.uuid4()}", producer_ref="observatory-browser-test")
    message = next(node["id"] for node in client.memory_map()["nodes"] if node["kind"] == "message")
    ids = {"message": message}
    ids["tea"] = "note:" + client.write_note("Likes jasmine tea after dinner.", kind="preference", role="user",
                                            source_event_ids=[message.split(":", 1)[1]])["note_id"]
    ids["sam"] = "note:" + client.write_note("Sam is my running partner.", kind="person", about="Sam",
                                            role="user")["note_id"]
    ids["race"] = "note:" + client.write_note("Training for a 10k with Sam.", kind="plan", about="Sam",
                                             role="user")["note_id"]
    saved = client.write_note("Job interview at the bakery on Friday.", kind="plan", role="user",
                              affect={"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported",
                                      "topic": "the interview"})
    ids["interview"], ids["feeling"] = "note:" + saved["note_id"], "affect:" + saved["affect_id"]
    ids["moment"] = "note:" + client.write_note("We finished a puzzle together.", kind="milestone", shared=True,
                                               role="user")["note_id"]
    ids["walk"] = "note:" + client.write_note("Walks the dog Biscuit before work.", kind="routine",
                                             role="user")["note_id"]
    client.trace_recall([message.split(":", 1)[1]])
    payload = client.memory_map(trace=True)
    kinds = {edge["type"] for edge in payload["edges"]}
    assert kinds == {"derived_from", "about_person", "feeling_of"}, payload["edges"]
    assert {ids[name] for name in ("tea", "sam", "race", "interview", "feeling", "moment", "walk")} <= {
        node["id"] for node in payload["nodes"]}
    return ids


# 1. Demo: pixels, rotation, zoom, picking, no API request ----------------------------------------------------------

def test_demo_renders_rotates_zooms_and_picks_the_right_node_without_any_api_request(server, tab):
    page = tab.page
    state = open_demo(page, server.base_url)
    assert state["mode"] == "3d" and state["fallback"] == "" and state["contextLost"] is False
    expect(page.locator("#observatory")).to_be_visible()
    expect(page.locator("#brain-canvas")).to_be_hidden()
    expect(page.locator("#brain-demo")).to_be_visible()
    # The scene holds exactly the payload: every node once, every edge with its recorded type, nothing else.
    assert sorted(state["nodes"]) == sorted(node["id"] for node in DEMO["nodes"])
    assert set(state["edges"]) == edge_keys(DEMO) and len(state["edges"]) == len(DEMO["edges"])
    assert state["recalled"] == [] and "trace" not in DEMO
    assert 0 < state["pixelRatio"] <= 2
    pixels = canvas_pixels(page)
    assert pixels["differing"] > pixels["total"] * 0.01 and pixels["saturated"] > 20, pixels
    for kind, count in (("derived_from", 18), ("about_person", 4), ("feeling_of", 2)):
        expect(page.locator(f'#observatory-edges [data-edge="{kind}"] .edge-count')).to_have_text(str(count))

    # Rotate: a real drag turns the camera and moves every projected node.
    target = pickable(page)
    box = page.locator("#observatory-canvas").bounding_box()
    before, shot = snapshot(page), page.locator("#observatory-canvas").screenshot()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    for step in range(1, 6):
        page.mouse.move(box["x"] + box["width"] / 2 + step * 24, box["y"] + box["height"] / 2 + step * 6)
    page.mouse.up()
    rotated = wait_for_frame(page, before["renders"])
    assert rotated["view"]["theta"] != before["view"]["theta"] and rotated["view"]["phi"] != before["view"]["phi"]
    moved = page.evaluate("(id) => window.observatory.project(id)", target["id"])
    assert abs(moved["x"] - target["x"]) + abs(moved["y"] - target["y"]) > 5
    assert page.locator("#observatory-canvas").screenshot() != shot
    assert rotated["selected"] == "", "a drag is not a click"

    # Zoom: the wheel brings the camera closer and spreads the projection.
    ids = rotated["nodes"][:2]
    spread = lambda: page.evaluate("""(ids) => { const [a, b] = ids.map((id) => window.observatory.project(id));
        return Math.hypot(a.x - b.x, a.y - b.y); }""", ids)  # noqa: E731
    far = spread()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -400)
    zoomed = wait_for_frame(page, rotated["renders"])
    assert zoomed["view"]["radius"] < rotated["view"]["radius"] and spread() > far

    # Pick: a click at a node's projected centre selects exactly that node and opens the shared detail panel.
    target = pickable(page, [node["id"] for node in DEMO["nodes"] if node["id"].startswith("note:")])
    node = next(item for item in DEMO["nodes"] if item["id"] == target["id"])
    page.mouse.click(target["x"], target["y"])
    expect(page.locator("#brain-detail")).to_be_visible()
    expect(page.locator("#brain-detail")).to_contain_text(node["label"])
    expect(page.locator("#brain-detail .brain-note-actions")).to_have_count(0)  # The fictional demo edits nothing.
    picked = settled(page)
    assert picked["selected"] == target["id"]
    expect(page.locator(f'#observatory-list button[data-id="{target["id"]}"]')).to_have_attribute("aria-current", "true")
    # The 2D map shares the selection, and stays one click away.
    page.locator("#mode-2d").click()
    expect(page.locator("#brain-canvas")).to_be_visible()
    expect(page.locator("#observatory")).to_be_hidden()
    expect(page.locator(f'#brain-canvas circle.brain-node[data-id="{target["id"]}"]')).to_have_class(re.compile(r"\blit\b"))
    page.locator("#mode-3d").click()
    settled(page)

    page.wait_for_load_state("networkidle")
    paths = [urlsplit(url).path for url in tab.requests if not url.startswith("data:")]
    assert [path for path in paths if path.startswith("/v1/")] == [], "the demo must not call the API"
    assert {urlsplit(url).netloc for url in tab.requests if not url.startswith("data:")} == {
        urlsplit(server.base_url).netloc}, "nothing is loaded from another host"
    assert {"/static/vendor/three/three.module.js", "/static/vendor/three/three.core.js",
            "/static/memory-map-demo.json"} <= set(paths)


def test_the_layout_is_stable_for_the_same_map_and_unmoved_by_other_records(server, tab):
    page = tab.page
    open_demo(page, server.base_url)
    first, again = (page.evaluate("(map) => window.observatory.layout(map)", DEMO) for _ in range(2))
    assert first == again and set(first) == {node["id"] for node in DEMO["nodes"]}
    changed = json.loads(json.dumps(DEMO))
    removed = changed["nodes"].pop(3)
    changed["nodes"].append({**changed["nodes"][0], "id": "note:fictional-extra", "label": "An added note"})
    changed["nodes"].reverse()
    other = page.evaluate("(map) => window.observatory.layout(map)", changed)
    assert all(other[ident] == first[ident] for ident in other if ident != "note:fictional-extra")
    assert removed["id"] not in other
    # Every node lies inside its region's volume; a region is a place, not a guess about the record.
    regions = {node["id"]: node["region"] for node in DEMO["nodes"]}
    centres = {}
    for ident, position in first.items():
        centres.setdefault(regions[ident], []).append(position)
    assert len({tuple(round(sum(axis) / len(axis), 1) for axis in zip(*items)) for items in centres.values()}) == len(centres)
    # A fresh page draws the same map the same way.
    page.reload()
    settled(page)
    assert page.evaluate("(map) => window.observatory.layout(map)", DEMO) == first


# 2. Keyboard, reduced motion -----------------------------------------------------------------------------------------

def test_the_keyboard_list_moves_focus_and_selection_and_the_3d_view_follows(server, tab):
    page = tab.page
    state = open_demo(page, server.base_url)
    buttons = page.locator("#observatory-list button")
    expect(buttons).to_have_count(len(DEMO["nodes"]))
    assert page.locator('#observatory-list button[tabindex="0"]').count() == 1
    page.locator('#observatory-list button[tabindex="0"]').focus()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    focused = page.evaluate("() => document.activeElement.dataset.id")
    assert focused == buttons.nth(2).get_attribute("data-id")
    focus_state = wait_for_frame(page, state["renders"])
    assert focus_state["focused"] == focused and focus_state["selected"] == ""
    page.keyboard.press("End")
    last = buttons.nth(len(DEMO["nodes"]) - 1)
    expect(last).to_be_focused()
    page.keyboard.press("Home")
    expect(buttons.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    chosen = page.evaluate("() => document.activeElement.dataset.id")
    page.keyboard.press("Enter")
    expect(page.locator("#brain-detail")).to_be_visible()
    label = next(node["label"] for node in DEMO["nodes"] if node["id"] == chosen)
    expect(page.locator("#brain-detail")).to_contain_text(label)
    expect(buttons.nth(1)).to_have_attribute("aria-current", "true")
    moved = settled(page)
    assert moved["selected"] == chosen
    position = page.evaluate("(map) => window.observatory.layout(map)", DEMO)[chosen]
    assert all(abs(a - b) < 1e-6 for a, b in zip(moved["view"]["target"], position)), "the camera turns to the choice"

    # The canvas itself: arrows rotate, minus zooms out, Home resets.
    page.locator("#observatory-canvas").focus()
    page.keyboard.press("ArrowLeft")
    turned = wait_for_frame(page, moved["renders"])
    assert turned["view"]["theta"] < moved["view"]["theta"]
    page.keyboard.press("-")
    out = wait_for_frame(page, turned["renders"])
    assert out["view"]["radius"] > turned["view"]["radius"]
    page.keyboard.press("Home")
    home = settled(page)
    assert home["view"]["target"] == [0, 0, 0] and home["view"]["radius"] == state["view"]["radius"]


@pytest.mark.parametrize("motion", ["reduce", "no-preference"])
def test_reduced_motion_moves_the_camera_at_once_in_a_single_frame(server, browser, motion):
    context, tab = _tab(browser, reduced_motion=motion)
    page = tab.page
    try:
        state = open_demo(page, server.base_url)
        page.locator("#observatory-canvas").focus()
        for _ in range(4):
            page.keyboard.press("ArrowRight")
        page.keyboard.press("-")
        away = settled(page)
        assert away["view"] != state["view"]
        frames = page.evaluate("""() => new Promise((resolve) => {
            const start = window.observatory.snapshot().renders;
            document.getElementById("observatory-reset").click();
            const right_after = window.observatory.snapshot();
            setTimeout(() => resolve({ right_after, frames: window.observatory.snapshot().renders - start }), 900);
        })""")
        home = snapshot(page)
        assert home["view"]["radius"] == pytest.approx(state["view"]["radius"])
        assert home["view"]["theta"] == pytest.approx(state["view"]["theta"])
        if motion == "reduce":
            assert frames["right_after"]["animating"] is False
            assert frames["right_after"]["view"]["theta"] == pytest.approx(state["view"]["theta"])
            assert frames["frames"] == 1, "reduced motion: one frame, no glide"
        else:
            assert frames["right_after"]["animating"] is True and frames["frames"] > 1
        assert tab.errors == []
    finally:
        context.close()


# 3. WebGL loss and absence ------------------------------------------------------------------------------------------

def test_a_lost_webgl_context_falls_back_to_the_2d_map_and_the_3d_view_recovers(server, tab):
    page = tab.page
    state = open_demo(page, server.base_url)
    page.evaluate("""() => { window.__lose = document.getElementById("observatory-canvas").getContext("webgl2")
        .getExtension("WEBGL_lose_context"); window.__lose.loseContext(); }""")
    expect(page.locator("#observatory-status")).to_have_text(LOST)
    expect(page.locator("#observatory")).to_be_hidden()
    expect(page.locator("#brain-canvas")).to_be_visible()
    expect(page.locator("#brain-canvas circle.brain-node")).to_have_count(len(DEMO["nodes"]))
    lost = snapshot(page)
    assert lost["fallback"] == "lost" and lost["active"] is False and lost["nodes"] == []
    # While lost, input and data changes draw nothing.
    calls = page.evaluate("() => window.__rafCalls")
    page.evaluate("() => window.loadBrain()")
    page.wait_for_timeout(500)
    assert page.evaluate("() => window.__rafCalls") == calls
    page.evaluate("() => window.__lose.restoreContext()")
    expect(page.locator("#observatory-status")).to_be_hidden()
    expect(page.locator("#observatory")).to_be_visible()
    restored = settled(page, state["generation"] + 1)
    assert restored["fallback"] == "" and restored["contextLost"] is False
    assert sorted(restored["nodes"]) == sorted(node["id"] for node in DEMO["nodes"])
    assert set(restored["edges"]) == edge_keys(DEMO)
    pixels = canvas_pixels(page)
    assert pixels["differing"] > pixels["total"] * 0.01 and pixels["saturated"] > 20, pixels
    click_node(page, pickable(page)["id"])


def test_without_webgl_the_page_shows_the_2d_map_and_the_list_with_a_message(server, browser):
    context, tab = _tab(browser)
    tab.page.add_init_script(NO_WEBGL)
    page = tab.page
    try:
        page.goto(f"{server.base_url}/memory?demo=brain")
        expect(page.locator("#observatory-status")).to_have_text(UNSUPPORTED)
        expect(page.locator("#mode-3d")).to_be_disabled()
        expect(page.locator("#observatory")).to_be_hidden()
        expect(page.locator("#brain-canvas circle.brain-node")).to_have_count(len(DEMO["nodes"]))
        expect(page.locator("#observatory-list button")).to_have_count(len(DEMO["nodes"]))
        page.locator('#observatory-list button[tabindex="0"]').press("Enter")
        expect(page.locator("#brain-detail")).to_be_visible()
        assert snapshot(page)["fallback"] == "unsupported"
        assert tab.errors == []
    finally:
        context.close()


# 4. Frames only on demand --------------------------------------------------------------------------------------------

def test_no_frames_while_idle_hidden_or_switched_to_2d_and_switching_away_frees_the_gpu(server, tab):
    page = tab.page
    open_demo(page, server.base_url)
    page.wait_for_timeout(1500)  # Settle.
    idle = page.evaluate("() => [window.__rafCalls, window.observatory.snapshot().renders]")
    page.wait_for_timeout(3000)
    assert page.evaluate("() => [window.__rafCalls, window.observatory.snapshot().renders]") == idle, "idle frames"

    # Hidden: input and a resize queue nothing; becoming visible draws one frame.
    hidden = page.evaluate("""async () => {
        Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
        document.dispatchEvent(new Event("visibilitychange"));
        const before = [window.__rafCalls, window.observatory.snapshot().renders];
        const canvas = document.getElementById("observatory-canvas");
        for (let i = 0; i < 10; i += 1) canvas.dispatchEvent(new WheelEvent("wheel", { deltaY: 50, cancelable: true }));
        canvas.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
        await new Promise((resolve) => setTimeout(resolve, 800));
        const after = [window.__rafCalls, window.observatory.snapshot().renders];
        delete document.visibilityState;
        document.dispatchEvent(new Event("visibilitychange"));
        await new Promise((resolve) => setTimeout(resolve, 500));
        return { hidden: [after[0] - before[0], after[1] - before[1]],
                 visible: window.observatory.snapshot().renders - after[1] };
    }""")
    assert hidden == {"hidden": [0, 0], "visible": 1}, hidden

    # Switching to 2D frees every geometry and material, and nothing draws afterwards.
    built = snapshot(page)
    assert built["gpu"]["geometries"] > 0
    page.locator("#mode-2d").click()
    expect(page.locator("#brain-canvas")).to_be_visible()
    away = snapshot(page)
    assert away["active"] is False and away["gpu"]["geometries"] == 0 and away["disposals"] > built["disposals"]
    calls = page.evaluate("() => window.__rafCalls")
    page.set_viewport_size({"width": 1100, "height": 800})
    page.locator("#observatory-canvas").dispatch_event("wheel", {"deltaY": 50})
    page.wait_for_timeout(800)
    assert page.evaluate("() => window.__rafCalls") == calls
    assert page.evaluate("() => localStorage.getItem('membrain-brain-mode')") == "2d"
    # The choice is remembered, and 3D comes back with the same scene.
    page.reload()
    expect(page.locator("#brain-canvas circle.brain-node")).to_have_count(len(DEMO["nodes"]))
    expect(page.locator("#observatory")).to_be_hidden()
    page.locator("#mode-3d").click()
    again = settled(page)
    assert set(again["edges"]) == edge_keys(DEMO) and again["gpu"]["geometries"] == built["gpu"]["geometries"]
    # Repeated switching does not accumulate GPU resources.
    for _ in range(3):
        page.locator("#mode-2d").click()
        page.locator("#mode-3d").click()
        assert settled(page)["gpu"]["geometries"] == built["gpu"]["geometries"]


def test_the_largest_map_the_service_allows_is_drawn_and_picked(server, tab):
    payload = _measurement().fixture_map(500, 1000)
    page = tab.page
    page.route("**/static/memory-map-demo.json", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(payload)))
    state = open_demo(page, server.base_url)
    assert len(state["nodes"]) == 500 and len(state["edges"]) == 1000 and set(state["edges"]) == edge_keys(payload)
    assert sorted(state["recalled"]) == sorted(node["id"] for node in payload["nodes"] if node["traced"])
    target = pickable(page)
    page.mouse.click(target["x"], target["y"])
    expect(page.locator("#brain-detail")).to_be_visible()
    assert settled(page)["selected"] == target["id"]
    page.wait_for_timeout(1000)
    calls = page.evaluate("() => window.__rafCalls")
    page.wait_for_timeout(2000)
    assert page.evaluate("() => window.__rafCalls") == calls


# 5. Real memory: edit, delete, recall highlight, reset, restore -------------------------------------------------------

def test_editing_and_deleting_a_note_in_3d_redraws_the_scene_without_stale_records(server, account, tab):
    key, client = account
    ids = seeded_brain(client)
    page = tab.page
    sign_in(page, server.base_url, key)
    open_brain(page)
    state = settled(page)
    payload = client.memory_map(trace=True)
    assert sorted(state["nodes"]) == sorted(node["id"] for node in payload["nodes"])
    assert set(state["edges"]) == edge_keys(payload)

    # Recalled records: exactly the latest recorded recall, ringed, counted and labelled with that wording.
    assert state["recalled"] == [ids["message"]]
    expect(page.locator("#observatory-recalled-count")).to_have_text("1")
    expect(page.locator(f'#observatory-list button[data-id="{ids["message"]}"] .observatory-recalled')).to_have_text(
        "Latest recorded recall")
    expect(page.locator("#brain-trace")).to_contain_text("Latest recorded recall")

    # Edit through the shared detail panel; the corrected note replaces the old one in the scene.
    click_node(page, ids["tea"])
    expect(page.locator("#brain-detail")).to_contain_text("Likes jasmine tea after dinner.")
    page.locator("#brain-detail .brain-note-actions").get_by_role("button", name="Edit", exact=True).click()
    page.locator("#brain-detail textarea").fill("Likes chamomile tea after dinner.")
    page.locator("#brain-detail").get_by_role("button", name="Save correction").click()
    page.wait_for_function(f"() => !window.observatory.snapshot().nodes.includes({json.dumps(ids['tea'])})")
    edited = settled(page, state["generation"] + 1)
    after_edit = client.memory_map(trace=True)
    assert sorted(edited["nodes"]) == sorted(node["id"] for node in after_edit["nodes"])
    assert set(edited["edges"]) == edge_keys(after_edit)
    assert not any(ids["tea"] in edge for edge in edited["edges"])
    assert edited["gpu"]["geometries"] == state["gpu"]["geometries"], "the old map's buffers were freed"
    expect(page.locator("#observatory-list")).not_to_contain_text("jasmine tea after dinner.")
    assert page.evaluate("() => window.observatorySamePage") is True

    # Delete through the real confirm dialog: the node and every edge touching it leave the scene and the list.
    assert any(ids["race"] in edge for edge in edited["edges"])
    click_node(page, ids["race"])
    seen = answer_next_dialog(page, accept=True)
    page.locator("#brain-detail .brain-note-actions").get_by_role("button", name="Delete", exact=True).click()
    page.wait_for_function(f"() => !window.observatory.snapshot().nodes.includes({json.dumps(ids['race'])})")
    assert seen == [("confirm", DELETE_NOTE)]
    deleted = settled(page, edited["generation"] + 1)
    assert not any(ids["race"] in edge for edge in deleted["edges"])
    assert set(deleted["edges"]) == edge_keys(client.memory_map(trace=True))
    assert deleted["selected"] == "" and deleted["gpu"]["geometries"] == state["gpu"]["geometries"]
    expect(page.locator("#brain-detail")).to_be_hidden()
    expect(page.locator(f'#observatory-list button[data-id="{ids["race"]}"]')).to_have_count(0)
    expect(page.locator("#observatory-labels")).not_to_contain_text("Training for a 10k")
    # Dismissing the dialog deletes nothing.
    click_node(page, ids["walk"])
    seen = answer_next_dialog(page, accept=False)
    page.locator("#brain-detail .brain-note-actions").get_by_role("button", name="Delete", exact=True).click()
    page.wait_for_timeout(500)
    assert seen == [("confirm", DELETE_NOTE)] and ids["walk"] in snapshot(page)["nodes"]
    assert page.evaluate("() => window.observatorySamePage") is True


def test_switching_tabs_frees_the_scene_and_resets_and_restores_show_the_current_state(server, account, tab):
    key, client = account
    ids = seeded_brain(client)
    archive = client.export()["result"]
    page = tab.page
    sign_in(page, server.base_url, key)
    open_brain(page)
    state = settled(page)
    assert {ids["moment"], ids["walk"]} <= set(state["nodes"])

    # Another tab: the 3D view stops and frees its GPU resources.
    page.locator('#tabs button[data-view="notes"]').click()
    expect(page.locator("#view-notes")).to_be_visible()
    away = snapshot(page)
    assert away["active"] is False and away["nodes"] == [] and away["gpu"]["geometries"] == 0
    calls = page.evaluate("() => window.__rafCalls")
    page.set_viewport_size({"width": 1000, "height": 800})
    page.wait_for_timeout(600)
    assert page.evaluate("() => window.__rafCalls") == calls
    page.set_viewport_size(DESKTOP)

    # A relationship reset deletes the shared moment; the scene no longer has it.
    client.reset_relationship()
    open_brain(page)
    reset = settled(page, state["generation"] + 1)
    assert ids["moment"] not in reset["nodes"] and ids["walk"] in reset["nodes"]
    assert sorted(reset["nodes"]) == sorted(node["id"] for node in client.memory_map()["nodes"])

    # Delete a note on the map, then restore the older archive: the deletion holds and the scene agrees.
    click_node(page, ids["walk"])
    answer_next_dialog(page, accept=True)
    page.locator("#brain-detail .brain-note-actions").get_by_role("button", name="Delete", exact=True).click()
    page.wait_for_function(f"() => !window.observatory.snapshot().nodes.includes({json.dumps(ids['walk'])})")
    generation = client.dashboard()["brain"]["scope_generation"]
    restored = client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                              expected_scope_generation=generation)
    assert restored["outcome"] == "completed", restored
    page.locator('#tabs button[data-view="notes"]').click()
    open_brain(page)
    after = settled(page, reset["generation"] + 2)
    current = client.memory_map()
    assert sorted(after["nodes"]) == sorted(node["id"] for node in current["nodes"])
    assert set(after["edges"]) == edge_keys(current)
    assert ids["walk"] not in after["nodes"] and ids["moment"] not in after["nodes"], "restore revived a deletion"
    expect(page.locator("#observatory-list")).not_to_contain_text("Biscuit")


# 6. Languages and layout ----------------------------------------------------------------------------------------------

def test_the_3d_view_reads_in_english_and_chinese_without_sideways_scroll(server, tab):
    page = tab.page
    english = {"#mode-3d": "3D observatory", "#mode-2d": "2D map",
               ".observatory-key h2": "How to read the 3D view", "#observatory-layers summary":
               "Layers this map does not include yet", "#observatory-list-title": "Memories in this map"}
    chinese = {"#mode-3d": "3D 观测台", "#mode-2d": "2D 图", ".observatory-key h2": "怎样看 3D 视图",
               "#observatory-layers summary": "记忆图还没有包含的层", "#observatory-list-title": "记忆图里的记忆"}
    for language, expected in (("en", english), ("zh", chinese)):
        open_demo(page, server.base_url, f"&lang={language}")
        expect(page.locator("html")).to_have_attribute("lang", "zh-CN" if language == "zh" else "en")
        for selector, text in expected.items():
            expect(page.locator(selector)).to_have_text(text)
        key = page.locator(".observatory-key")
        if language == "en":
            expect(key).to_contain_text("The brain-shaped shell is an illustrative container, not neuroscience.")
            expect(key).to_contain_text("It is not memory strength, confidence or importance.")
            expect(page.locator("#observatory-layers")).to_contain_text("Not available yet")
        else:
            expect(key).to_contain_text("不是神经科学")
            expect(key).to_contain_text("布局权重")
            expect(page.locator("#observatory-layers")).to_contain_text("暂不可用")
            page.locator("#observatory-layers summary").click()
            for selector in (".brain-modes", ".observatory-key", "#observatory-layers", ".observatory-list-box",
                             "#observatory-labels"):
                assert untranslated(page, selector) == [], selector
        for size in (DESKTOP, PHONE):
            page.set_viewport_size(size)
            settled(page)
            assert_no_horizontal_scroll(page, f"3D brain view in {language} at {size['width']} px")
            box = page.locator("#observatory-canvas").bounding_box()
            assert box["width"] <= size["width"] and box["height"] >= 200
        page.set_viewport_size(DESKTOP)
    page.goto(f"{server.base_url}/memory?demo=brain&lang=en")
