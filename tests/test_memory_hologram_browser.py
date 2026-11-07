"""Exercise the immersive renderer against the same local CSP and fictional payload as the 3D measurement page."""
import hashlib
import importlib.util
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from test_memory_observatory_browser import NO_WEBGL, _tab
from test_memory_observatory_browser import browser as _shared_browser

browser = _shared_browser

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def preview():
    spec = importlib.util.spec_from_file_location("hologram_preview", ROOT / "scripts" / "measure_observatory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.StaticServer()
    server.set_map(module.fixture_map(200, 400))
    try:
        yield server
    finally:
        server.close()


def state(page):
    return page.evaluate("window.memoryHologram.snapshot()")


def ready(page):
    page.wait_for_function("() => window.memoryHologram?.snapshot().ready")


@pytest.mark.parametrize("language", ["en", "zh"])
def test_fullscreen_pixels_interaction_and_resource_lifecycle(browser, preview, language):
    context, tab = _tab(browser)
    page = tab.page
    try:
        page.goto(f"{preview.base_url}/memory?demo=brain&show=1&lang={language}")
        ready(page)
        assert page.locator("#show-foot").count() == 0
        assert not page.locator(".show-foot").is_visible()
        assert page.locator("#show-simulation").is_visible()
        assert page.locator("#show-fictional").is_visible()
        original = state(page)
        assert len(original["nodeIds"]) == 200 and len(original["edges"]) == 400
        assert original["signalCount"] == 48 and original["active"]
        canvas = page.locator(".hologram-canvas")
        box = canvas.bounding_box()
        assert box == {"x": 0, "y": 0, "width": 1280, "height": 900}
        page.wait_for_function("() => window.memoryHologram.snapshot().frames > 8")
        page.locator("#show-pause").click()
        frozen = state(page)
        assert not frozen["active"]
        page.wait_for_timeout(200)
        assert state(page)["frames"] == frozen["frames"]
        before = hashlib.sha256(canvas.screenshot()).hexdigest()
        page.mouse.move(610, 380)
        page.mouse.down()
        page.mouse.move(830, 450, steps=8)
        page.mouse.up()
        assert state(page)["turn"] > original["turn"] + .5
        assert hashlib.sha256(canvas.screenshot()).hexdigest() != before
        page.mouse.wheel(0, 200)
        page.wait_for_function(f"() => window.memoryHologram.snapshot().zoom > {original['zoom']}")
        for width, height in [(390, 844), (1280, 900)]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_function(f"() => document.querySelector('.hologram-canvas').clientWidth === {width}")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#show-close").focus()
        page.keyboard.press("Tab")
        assert page.locator("#show-pause").evaluate("e => e === document.activeElement")
        page.keyboard.press("Shift+Tab")
        assert page.locator("#show-close").evaluate("e => e === document.activeElement")
        page.keyboard.press("Escape")
        assert not state(page)["ready"] and not state(page)["active"]
        assert state(page)["nodeIds"] == [] and canvas.count() == 0
        assert not page.evaluate("document.querySelector('main').inert")
        for _ in range(3):
            page.locator("#brain-showcase").click()
            ready(page)
            page.locator("#show-close").click()
        page.locator("#brain-showcase").click()
        ready(page)
        page.locator("#show-pause").click()
        page.wait_for_function("() => window.memoryHologram.snapshot().frames > 20")
        output = os.environ.get("MEMBRAIN_EVIDENCE_DIRECTORY")
        if output:
            page.screenshot(path=str(Path(output) / f"hologram-{language}.png"))
        page.wait_for_load_state("networkidle")
        assert all(urlsplit(url).netloc == urlsplit(preview.base_url).netloc for url in tab.requests)
        assert not any("/v1/" in url for url in tab.requests)
        assert tab.errors == []
    finally:
        context.close()


def test_reduced_motion_hidden_pause_and_map_replacement(browser, preview):
    context, tab = _tab(browser, reduced_motion="reduce")
    page = tab.page
    try:
        page.goto(f"{preview.base_url}/memory?demo=brain&show=1")
        ready(page)
        frozen = state(page)
        page.wait_for_timeout(200)
        assert state(page)["frames"] == frozen["frames"] and not frozen["active"]
        page.emulate_media(reduced_motion="no-preference")
        page.wait_for_function("() => window.memoryHologram.snapshot().active")
        page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange'))")
        hidden = state(page)
        page.wait_for_timeout(200)
        assert state(page)["frames"] == hidden["frames"] and not hidden["active"]
        page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: false}); document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_function("() => window.memoryHologram.snapshot().active")
        replacement = {"demo": False, "nodes": [{"id": "note:one", "region": "persona", "kind": "note"},
                                               {"id": "note:two", "region": "mood", "kind": "note"}],
                       "edges": [{"source": "note:one", "target": "note:two", "type": "baseline_from"},
                                 {"source": "note:missing", "target": "note:two", "type": "baseline_from"}]}
        page.evaluate("map => document.dispatchEvent(new CustomEvent('brain-map', {detail: map}))", replacement)
        page.wait_for_function("() => window.memoryHologram.snapshot().nodeIds.length === 2")
        assert state(page)["edges"] == replacement["edges"][:1]
        assert state(page)["signalCount"] == 1
        page.evaluate("document.dispatchEvent(new CustomEvent('brain-map', {detail: {nodes: [], edges: []}}))")
        page.wait_for_function("() => window.memoryHologram.snapshot().ready && window.memoryHologram.snapshot().nodeIds.length === 0")
        assert state(page)["signalCount"] == 0
        page.evaluate("document.dispatchEvent(new Event('brain-clear'))")
        assert not state(page)["ready"] and not state(page)["active"]
        assert tab.errors == []
    finally:
        context.close()


@pytest.mark.parametrize("loss", [False, True])
def test_graphics_fallback_retains_honest_map_and_close(browser, preview, loss):
    context, tab = _tab(browser)
    page = tab.page
    try:
        if not loss:
            page.add_init_script(NO_WEBGL)
        page.goto(f"{preview.base_url}/memory?demo=brain&show=1")
        if loss:
            ready(page)
            page.evaluate("document.querySelector('.hologram-canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext()")
            page.wait_for_function("() => !window.memoryHologram.snapshot().ready")
        page.locator(".show-still").wait_for(state="visible")
        assert page.locator("#show-demo").is_visible()
        assert page.locator(".show-node").count() == 200
        assert page.locator(".show-edge").count() == 400
        page.locator("#show-close").click()
        assert not page.locator("#brain-show").is_visible()
        assert not state(page)["ready"]
        assert tab.errors == []
    finally:
        context.close()
