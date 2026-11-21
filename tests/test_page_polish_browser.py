"""What a recording of the memory page shows on a real, small memory: cut text, the 3D view's labels and tooltip, the
key's rows, the showcase's honesty label and its layout of real data.

The memory is recorded as a user makes it (``page_polish_world``: the Claude Code plugin's hooks and MCP server on a
disposable installation), and its page opened as ``membrain plugin ui`` opens it, in a real headless Chromium with
software WebGL. Assertions are on geometry and text, never on pixels. With ``PAGE_POLISH_SHOTS`` set to a directory,
each test also saves screenshots there at device scale factor 2 (same viewport and data before and after a change).
All data is fictional.
"""
import json
import math
import os
import re
from pathlib import Path

import pytest
from page_polish_world import HANGZHOU, NOTE_TRIP, TRIP, built_world
from test_memory_page_browser import browser as browser
from test_memory_page_browser import open_view

from membrain import host
from membrain.local_profile import load_profile

try:
    from playwright.sync_api import expect
except ImportError:  # Without Playwright the browser fixture skips (or fails when required) before this is used.
    expect = None

pytestmark = pytest.mark.integration

WEB = Path(__file__).resolve().parents[1] / "src" / "membrain" / "web"
DEMO = json.loads((WEB / "memory-map-demo.json").read_text(encoding="utf-8"))
SHOTS = os.environ.get("PAGE_POLISH_SHOTS")
WIDE, NARROW = {"width": 1200, "height": 900}, {"width": 900, "height": 900}
RECORDING = {"width": 1280, "height": 720}


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    with built_world(tmp_path_factory, "small") as world:
        yield world


@pytest.fixture(scope="module")
def large(tmp_path_factory):
    with built_world(tmp_path_factory, "large") as world:
        yield world


@pytest.fixture(scope="module", autouse=True)
def worlds_before_the_browser(small, large):
    """Both worlds are played before Chromium starts: the host's MCP calls use asyncio.run, which cannot run inside
    the event loop that Playwright's sync API keeps running in this thread."""
    return small, large


@pytest.fixture
def context(browser):
    """New pages at device scale factor 2; any uncaught page error fails the test."""
    opened, errors = [], []

    def new(viewport=WIDE, locale="en-US"):
        context = browser.new_context(viewport=viewport, locale=locale, device_scale_factor=2)
        page = context.new_page()
        page.set_default_timeout(20_000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        opened.append(context)
        return page

    yield new
    for item in opened:
        item.close()
    assert errors == [], "uncaught errors on the page"


def shot(page, name: str, locator=None) -> None:
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    (locator or page).screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def open_page(page, world):
    """The page as `membrain plugin ui` opens it: the installation's own service, signed in by a one-time code."""
    page.goto(f"{load_profile(world.directory).base_url}/memory?code={host.issue_ui_code(world.directory)}")
    expect(page.locator("#tabs")).to_be_visible()
    expect(page.locator("#view-notes")).to_be_visible()


# Defect 1: text cut on the page ------------------------------------------------------------------------------------

WORD = re.compile(r"\w")


def assert_cut_at_a_word(shown: str, full: str) -> None:
    """``shown`` is ``full`` shortened: a prefix of it, then "…", ending between two words of the source."""
    assert shown.endswith("…") and len(shown) < len(full), (shown, full)
    kept = shown[:-1].rstrip()
    assert full.startswith(kept), (shown, full)
    after = full[len(kept):len(kept) + 1]
    assert not (WORD.match(kept[-1]) and WORD.match(after)), f"cut inside a word: {shown!r}"


def test_source_links_and_conversation_summaries_end_with_an_ellipsis_at_a_word(small, context):
    page = context()
    open_page(page, small)
    item = page.locator("#notes article.item").filter(has_text=NOTE_TRIP)
    item.locator("details summary").click()
    link = item.locator(".source-conversation")
    expect(link).to_have_count(1)
    shot(page, "1-note-source-link", item)
    text = link.inner_text()
    prefix = re.match(r"In the conversation: \S+ · \d+ messages · ", text).group(0)
    assert_cut_at_a_word(text[len(prefix):], TRIP)

    open_view(page, "conversations")
    summaries = page.locator("#conversations details.item > summary")
    expect(summaries.first).to_be_visible()
    trip = summaries.filter(has_text="My sister Mira")
    shot(page, "1-conversation-summaries", page.locator("#conversations"))
    text = trip.inner_text()
    assert_cut_at_a_word(text[re.match(r"\S+ · \d+ messages · ", text).end():], TRIP)

    # Chinese has no spaces: the cut falls between two words as the browser's own word segmenter divides them.
    chinese = summaries.filter(has_text="下个月我们要去杭州")
    text = chinese.inner_text()
    shown = text[re.match(r"\S+ · \d+ messages · ", text).end():]
    assert shown.endswith("…") and HANGZHOU.startswith(shown[:-1]), shown
    boundaries = page.evaluate("""(text) => [...new Intl.Segmenter("zh", { granularity: "word" }).segment(text)]
        .map((part) => part.index)""", HANGZHOU)
    assert len(shown) - 1 in boundaries, f"cut inside a word: {shown!r}"


def test_one_function_cuts_every_shortened_text_on_the_page(small, context):
    """The same cut for summaries, source links and the lines of a delete question: never inside a surrogate pair,
    a combining sequence or an emoji sequence; at a word boundary when there is one; always with "…"."""
    page = context()
    open_page(page, small)
    results = page.evaluate("""() => {
        const lone = /[\\uD800-\\uDBFF](?![\\uDC00-\\uDFFF])|(?<![\\uD800-\\uDBFF])[\\uDC00-\\uDFFF]/;
        const graphemes = (text) => [...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)]
            .map((part) => part.segment);
        const cases = {
            emoji: "🙂".repeat(80),
            combining: "e\\u0301".repeat(80),
            family: "👨‍👩‍👧".repeat(40),
            english: "We will hike the Alta Via 1 in the Dolomites with Mira from hut to hut over nine days next July",
            unbroken: "x".repeat(200),
            short: "Short text.",
        };
        const out = {};
        for (const [name, text] of Object.entries(cases)) {
            const cut = shorten(text, 40);
            const kept = cut.endsWith("…") ? cut.slice(0, -1) : cut;
            out[name] = { cut, lone: lone.test(cut), whole: graphemes(text).join("").startsWith(kept)
                && graphemes(kept).every((part, index) => part === graphemes(text)[index]), length: cut.length };
        }
        out.erased = erasedLine({ kind: "message", actor_role: "user", recorded_at: "2026-11-02T10:00:00Z",
            text: "We will hike the Alta Via 1 in the Dolomites with Mira from hut to hut over nine days next July, "
                + "then take the train back to Venice." });
        return out;
    }""")
    for name in ("emoji", "combining", "family", "english", "unbroken"):
        case = results[name]
        assert case["cut"].endswith("…") and case["length"] <= 40 and not case["lone"] and case["whole"], (name, case)
    assert results["short"]["cut"] == "Short text."
    assert_cut_at_a_word(results["english"]["cut"],
                         "We will hike the Alta Via 1 in the Dolomites with Mira from hut to hut over nine days next July")
    line = results["erased"]
    assert line.startswith("Message (2026-11-02): ") and line.endswith("…"), line
    assert_cut_at_a_word(line[len("Message (2026-11-02): "):], "We will hike the Alta Via 1 in the Dolomites with Mira "
                         "from hut to hut over nine days next July, then take the train back to Venice.")


# Defect 3: the 3D view's area names and tooltip ---------------------------------------------------------------------

def open_3d(page, world=None, demo=False):
    if demo:
        page.goto(f"{load_profile(world.directory).base_url}/memory?demo=brain")
    else:
        open_page(page, world)
        open_view(page, "brain")
    page.wait_for_function("""() => { const s = window.observatory && window.observatory.snapshot();
        return s && s.active && s.renders > 0 && !s.pending && !s.animating && s.nodes.length > 0; }""")
    return page.evaluate("() => window.observatory.snapshot()")


def next_frame(page, renders: int) -> dict:
    page.wait_for_function(f"""() => {{ const s = window.observatory.snapshot();
        return s.renders > {renders} && !s.pending && !s.animating; }}""")
    return page.evaluate("() => window.observatory.snapshot()")


def label_overlaps(page) -> list:
    return page.evaluate("""() => {
        const boxes = [...document.querySelectorAll("#observatory-labels .observatory-label")]
            .filter((label) => !label.hidden && getComputedStyle(label).opacity !== "0")
            .map((label) => ({ text: label.textContent, box: label.getBoundingClientRect() }));
        const out = [];
        for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
            const a = boxes[i].box, b = boxes[j].box;
            if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5)
                out.push([boxes[i].text, boxes[j].text]);
        }
        return out;
    }""")


def visible_labels(page) -> int:
    return page.locator("#observatory-labels .observatory-label:not([hidden])").count()


@pytest.mark.parametrize("which", ["small", "large", "demo", "small-zh-narrow"])
def test_area_names_never_overlap_at_rest_or_while_rotating(small, large, context, which):
    world = large if which == "large" else small
    page = context(NARROW if "narrow" in which else WIDE, "zh-CN" if "zh" in which else "en-US")
    state = open_3d(page, world, demo=which == "demo")
    shot(page, f"3-labels-{which}-rest", page.locator("#observatory"))
    assert label_overlaps(page) == [], "at the default rotation"
    assert visible_labels(page) > 0
    page.locator("#observatory-canvas").focus()
    # A full turn round the vertical axis, a frame per key press, then tilted up and down.
    for step, key in enumerate(["ArrowRight"] * 52 + ["ArrowUp"] * 8 + ["ArrowLeft"] * 13 + ["ArrowDown"] * 16):
        page.keyboard.press(key)
        state = next_frame(page, state["renders"])
        assert label_overlaps(page) == [], f"after {step + 1} key presses ({key})"
        if step in (13, 26, 39):
            shot(page, f"3-labels-{which}-turn-{step}", page.locator("#observatory"))


@pytest.mark.parametrize("which", ["small", "large-narrow"])
def test_the_tooltip_stays_inside_the_3d_view_at_every_edge(small, large, context, which):
    world = large if "large" in which else small
    page = context(NARROW if "narrow" in which else WIDE)
    state = open_3d(page, world)
    canvas = page.locator("#observatory-canvas")
    canvas.focus()
    for _ in range(9):  # Closer, so the records spread to every edge of the view.
        page.keyboard.press("+")
        state = next_frame(page, state["renders"])
    box = canvas.bounding_box()
    projected = page.evaluate("""(ids) => ids.map((id) => ({ id, ...window.observatory.project(id) }))
        .filter((point) => point.inside)""", state["nodes"])
    margin = 4
    inside = [point for point in projected if box["x"] + margin < point["x"] < box["x"] + box["width"] - margin
              and box["y"] + margin < point["y"] < box["y"] + box["height"] - margin]
    edges = {"left": min(inside, key=lambda point: point["x"]), "right": max(inside, key=lambda point: point["x"]),
             "top": min(inside, key=lambda point: point["y"]), "bottom": max(inside, key=lambda point: point["y"])}
    for edge, point in edges.items():
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.move(point["x"], point["y"])
        tip = page.locator("#observatory-tip")
        expect(tip).to_be_visible()
        page.wait_for_timeout(50)
        rect = tip.bounding_box()
        shot(page, f"3-tooltip-{which}-{edge}", page.locator("#observatory"))
        assert rect["x"] >= box["x"] - 0.5 and rect["y"] >= box["y"] - 0.5, (edge, rect, box)
        assert rect["x"] + rect["width"] <= box["x"] + box["width"] + 0.5, (edge, rect, box)
        assert rect["y"] + rect["height"] <= box["y"] + box["height"] + 0.5, (edge, rect, box)


# Defect 4: the key's rows ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("viewport,locale", [(WIDE, "en-US"), (NARROW, "en-US"), (NARROW, "zh-CN")],
                         ids=["1200-en", "900-en", "900-zh"])
def test_each_key_row_keeps_its_sample_count_and_description_on_one_line_box(small, context, viewport, locale):
    page = context(viewport, locale)
    open_3d(page, small)
    rows = page.locator("#observatory-edges li:not([hidden])")
    expect(rows.first).to_be_visible()
    shot(page, f"4-key-{viewport['width']}-{locale}", page.locator(".observatory-key"))
    measured = page.evaluate("""() => [...document.querySelectorAll("#observatory-edges li:not([hidden])")].map((row) => {
        const swatch = row.querySelector(".edge-swatch").getBoundingClientRect();
        const count = row.querySelector(".edge-count").getBoundingClientRect();
        const name = row.querySelector("strong");
        const description = [...row.children].find((child) => child.tagName === "SPAN"
            && !child.classList.contains("edge-swatch") && !child.classList.contains("edge-count"));
        const first = (node) => { const range = document.createRange(); range.selectNodeContents(node);
            const rect = range.getClientRects()[0]; return { top: rect.top, bottom: rect.bottom }; };
        return { edge: row.dataset.edge, swatch: { top: swatch.top - 4, bottom: swatch.bottom + 4 },
            count: { top: count.top, bottom: count.bottom }, name: first(name),
            description: description ? first(description) : null };
    })""")
    assert {row["edge"] for row in measured} >= {"derived_from", "replaced_source", "about_person", "feeling_of"}
    for row in measured:
        parts = [row["swatch"], row["count"], row["name"]] + ([row["description"]] if row["description"] else [])
        assert max(part["top"] for part in parts) < min(part["bottom"] for part in parts), row


# Defect 5: the showcase's honesty label ------------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [RECORDING, NARROW], ids=["1280x720", "900"])
def test_the_demo_label_is_the_largest_text_of_the_showcase(small, context, viewport):
    page = context(viewport)
    page.goto(f"{load_profile(small.directory).base_url}/memory?demo=brain&show=1")
    page.wait_for_function("() => window.memoryHologram.snapshot().ready")
    label = page.locator("#show-simulation")
    expect(label).to_be_visible()
    expect(page.locator("#show-fictional")).to_be_visible()
    shot(page, f"5-showcase-demo-{viewport['width']}")
    sizes = page.evaluate("""() => {
        const label = document.getElementById("show-simulation");
        const own = parseFloat(getComputedStyle(label).fontSize);
        const others = [];
        for (const element of document.querySelectorAll("#brain-show *")) {
            if (label.contains(element) || !element.getClientRects().length) continue;
            const text = [...element.childNodes].filter((node) => node.nodeType === 3).map((node) => node.nodeValue)
                .join("").trim();
            if (text) others.push([text, parseFloat(getComputedStyle(element).fontSize)]);
        }
        return { own, others, inside: label.getBoundingClientRect().right <= innerWidth };
    }""")
    # Legible when a recording is shown at half size: at least 12 px there, and nothing else in the showcase larger.
    assert sizes["own"] / 2 >= 12, sizes
    assert all(size <= sizes["own"] for _, size in sizes["others"]), sizes
    assert sizes["inside"], sizes


def test_without_webgl_the_demo_caption_is_the_largest_text_of_the_showcase(small, context):
    """The 2D showcase (no WebGL) says "Fictional demo data" in its caption: as legible as the 3D one's label."""
    page = context(RECORDING)
    page.add_init_script("""(() => { const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
            return /webgl/i.test(type) ? null : original.call(this, type, ...rest); }; })();""")
    page.goto(f"{load_profile(small.directory).base_url}/memory?demo=brain&show=1")
    label = page.locator("#show-demo")
    expect(label).to_have_text("Fictional demo data")
    expect(page.locator("#show-simulation")).to_be_hidden()
    shot(page, "5-showcase-demo-2d")
    sizes = page.evaluate("""() => {
        const label = document.getElementById("show-demo");
        const others = [];
        for (const element of document.querySelectorAll("#brain-show *")) {
            if (element === label || element.closest("svg") || !element.getClientRects().length) continue;
            const text = [...element.childNodes].filter((node) => node.nodeType === 3).map((node) => node.nodeValue)
                .join("").trim();
            if (text) others.push([text, parseFloat(getComputedStyle(element).fontSize)]);
        }
        return { own: parseFloat(getComputedStyle(label).fontSize), others };
    }""")
    assert sizes["own"] / 2 >= 12 and all(size <= sizes["own"] for _, size in sizes["others"]), sizes


# Defect 2: the showcase on real data ------------------------------------------------------------------------------

def spread(positions: dict) -> dict:
    """How far apart the drawn records are, in the 3D layout's units: the median distance from each record to its
    nearest neighbour, and the share of records within 0.6 of their common centre."""
    points = list(positions.values())
    centre = [sum(axis) / len(points) for axis in zip(*points)]
    nearest = sorted(min(math.dist(a, b) for b in points if b is not a) for a in points)
    return {"nearest": nearest[len(nearest) // 2],
            "central": sum(math.dist(point, centre) < 0.6 for point in points) / len(points)}


@pytest.mark.parametrize("which", ["small", "large"])
def test_the_showcase_spreads_a_real_memory_and_draws_every_recorded_link(small, large, context, which):
    """A real memory is mostly original messages and the learned assertions resting on them: the layout keeps them
    apart instead of piling them in the middle of the shell, and every recorded link between drawn records is a
    line. Nothing is added: a dot is a record, a line a recorded link."""
    world = small if which == "small" else large
    with world.client() as client:
        mapped = client.memory_map(max_nodes=200, max_edges=400, structure=True, trace=True)
    page = context(RECORDING)
    open_page(page, world)
    open_view(page, "brain")
    page.locator("#brain-showcase").click()
    page.wait_for_function("() => window.memoryHologram.snapshot().ready")
    page.wait_for_timeout(500)
    shot(page, f"2-showcase-real-{which}")
    drawn = page.evaluate("() => window.memoryHologram.snapshot()")
    assert sorted(drawn["nodeIds"]) == sorted(node["id"] for node in mapped["nodes"])
    key = lambda edge: (edge["source"], edge["target"], edge["type"])  # noqa: E731
    assert sorted(map(key, drawn["edges"])) == sorted(map(key, mapped["edges"]))
    measured = spread(drawn["positions"])
    if SHOTS:
        (Path(SHOTS) / f"2-spread-{which}.json").write_text(json.dumps(measured), encoding="utf-8")
    # Before 2026-11-21: median gaps of 0.13 (small) and 0.11 (large), and 69% of the records within 0.6 of the
    # centre; the built-in demo, 39 records: 0.31 and 23%.
    assert measured["nearest"] >= 0.18 and measured["central"] <= 0.3, measured


def test_the_demo_showcase_is_labelled_as_a_demo(small, context):
    page = context(RECORDING)
    page.goto(f"{load_profile(small.directory).base_url}/memory?demo=brain&show=1")
    page.wait_for_function("() => window.memoryHologram.snapshot().ready")
    page.wait_for_timeout(500)
    shot(page, "2-showcase-demo")
    expect(page.locator("#show-simulation")).to_have_text("Demo · Simulated signals")
