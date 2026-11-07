import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "membrain" / "web"
REGIONS = ["people", "constraints", "preferences", "plans", "commitments", "routines", "milestones", "relationship",
           "other", "episodes", "emotions", "persona", "mood", "semantic", "episodic", "schemas", "working"]


def test_the_demo_map_served_to_the_page_is_the_fictional_example():
    served = json.loads((WEB / "memory-map-demo.json").read_text(encoding="utf-8"))
    example = json.loads((WEB.parents[2] / "examples" / "memory-map-demo.json").read_text(encoding="utf-8"))
    assert served == example and served["demo"] is True


def test_the_brain_view_draws_every_contract_region_and_is_wired_into_the_page():
    script = (WEB / "brain.js").read_text(encoding="utf-8")
    assert sorted(re.findall(r'\{ id: "(\w+)", label:', script)) == sorted(REGIONS)
    assert "memory-map?max_nodes=200&max_edges=400" in script
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    assert '<script src="/static/brain.js" defer></script>' in page and 'id="view-brain"' in page
    assert 'data-view="brain"' in page
    styles = (WEB / "memory.css").read_text(encoding="utf-8")
    for region in REGIONS:
        assert f".brain-node.region-{region} " in styles and f"--r-{region}:" in styles


def _function_body(script, name):
    start = script.index(f"function {name}(")
    depth, index = 0, script.index("{", start)
    for end in range(index, len(script)):
        depth += {"{": 1, "}": -1}.get(script[end], 0)
        if depth == 0:
            return script[index:end + 1]
    raise AssertionError(f"unbalanced function {name}")


def test_the_showcase_is_a_separate_mode_entered_from_the_brain_tab_or_the_address():
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    assert '<script src="/static/showcase.js" defer></script>' in page
    assert 'id="brain-showcase"' in page and 'id="brain-show"' in page and 'id="show-close"' in page
    assert re.search(r'<section id="brain-show"[^>]* hidden>', page), "the showcase starts closed; the brain view stays"
    memory = (WEB / "memory.js").read_text(encoding="utf-8")
    # Read before the sign-in link's query string is removed, then honoured once the brain map is loaded.
    assert memory.index('get("show") === "1"') < memory.index("history.replaceState")
    assert 'show(SHOWCASE ? "brain" : view)' in memory and "if (SHOWCASE) window.openShowcase();" in memory
    script = (WEB / "showcase.js").read_text(encoding="utf-8")
    assert "if (DEMO && SHOWCASE) openShowcase();" in script
    assert 'event.key === "Escape"' in script and '$("show-close").addEventListener("click", closeShowcase)' in script
    # Only the map brain.js already loaded: no request of its own.
    assert "fetch(" not in script and "api(" not in script and "/v1/" not in script
    assert 'new CustomEvent("brain-map"' in (WEB / "brain.js").read_text(encoding="utf-8")
    for region in REGIONS:
        assert re.search(rf"\b{region}: \[\d+, \d+, \d+\]", script)
        assert re.search(rf'\b{region}: "#[0-9a-f]{{6}}"', script)


def test_showcase_dots_lines_and_pulses_come_only_from_the_memory_map():
    script = (WEB / "showcase.js").read_text(encoding="utf-8")
    render = _function_body(script, "renderShowcase")
    # Lines: one per edge of map.edges whose ends are drawn; the caption counts exactly those.
    assert "const links = map.edges.filter((edge) => positions[edge.source] && positions[edge.target]);" in render
    assert script.count('"show-edge"') == 1 and 'class: "show-edge"' in render[render.index("showState.links = links.map("):]
    # Dots: one per node of map.nodes; the caption counts exactly those.
    assert "const drawn = map.nodes.filter((node) => positions[node.id]);" in render
    assert script.count('"show-node') == 1 and "for (const node of drawn)" in render
    assert "${drawn.length}" in render and "${links.length}" in render
    # Pulses: built from showState.links only, capped, and never started under reduced motion.
    pulses = _function_body(script, "startPulses")
    assert "const order = showState.links.map(" in pulses and "slot.link = order[" in pulses
    assert set(re.findall(r"showState\.(\w+)", pulses)) <= {"open", "links", "slots", "nodes", "frame"}
    assert "map." not in pulses and "SHOW_" not in pulses
    assert "Math.min(MAX_PULSES," in pulses and re.search(r"const MAX_PULSES = (\d+);", script).group(1) == "40"
    assert "reducedMotion.matches" in pulses and '"(prefers-reduced-motion: reduce)"' in script
    assert script.count('"show-pulse"') == 1 and script.count('"show-trail"') == 1
    # Decoration: grooves and outlines only, never a circle or a memory class, and hidden from assistive technology.
    for name in ("decoration", "cortexFolds", "foliaPaths"):
        body = _function_body(script, name)
        assert '"circle"' not in body and "show-node" not in body and "show-edge" not in body
        assert not re.search(r"(?<![.\w])map\b|brainState|showState\.(links|nodes)", body), name
    assert '"show-decoration", "aria-hidden": "true"' in script
    styles = (WEB / "memory.css").read_text(encoding="utf-8")
    assert re.search(r"\.show-groove \{ stroke: #0[0-9a-f]{5};", styles), "folds are dark grooves, not lit lines"


def test_the_map_shows_the_latest_recorded_recall_honestly_and_edits_notes_like_the_notes_tab():
    script = (WEB / "brain.js").read_text(encoding="utf-8")
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    assert "&trace=true" in script and "/static/memory-map-demo.json" in script
    # Named as the latest recorded recall, a miss is shown as a miss, and the page says what is not traced.
    assert "Latest recorded recall" in script and "it found nothing to add." in script
    assert "Notes and history added when a session starts are not traced" in page
    assert "current reply" not in script
    # Edit and delete reuse the Notes tab's editor and erase, never in the fictional demo.
    assert "noteEditor(note, [], () => loadBrain())" in script
    assert 'forget("events", [id], "erase_content", NOTES)' in script
    assert '!brainState.demo) detail.append(noteActions(' in script
