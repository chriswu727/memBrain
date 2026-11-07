"""The 3D observatory on the memory page: vendored three.js, offline loading, packaging and honest semantics.

None of these needs a browser or a database; tests/test_memory_observatory_browser.py checks the behaviour in Chromium.
"""
import hashlib
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from membrain.api import create_app
from membrain.config import Settings

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "membrain" / "web"
VENDOR = WEB / "vendor"
THREE_VERSION = "0.186.1"
# Each vendored file, unmodified from https://registry.npmjs.org/three/-/three-0.186.1.tgz (see vendor/VENDOR.md).
VENDORED = {
    "three/three.module.js": "9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea",
    "three/three.core.js": "9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6",
    "three/LICENSE": "8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc",
}
MEMORY_EDGE_TYPES = {"derived_from", "about_person", "feeling_of"}
EDGE_TYPES = MEMORY_EDGE_TYPES | {"working_member", "working_evidence", "based_on_feedback", "proposed_from_feedback", "accepted_proposal", "restored_from",
                                  "baseline_from", "triggered_by", "affected_by", "memory_evidence", "memory_derivation",
                                  "episode_evidence", "episode_member", "pattern_member", "association", "belief_relation"}
PAGE_SCRIPTS = ["i18n.js", "memory.js", "brain.js", "observatory.js", "hologram.js", "showcase.js"]


def test_vendored_three_js_matches_the_recorded_hashes_version_and_licence():
    present = {str(path.relative_to(VENDOR)) for path in VENDOR.rglob("*") if path.is_file()}
    assert present == {*VENDORED, "VENDOR.md"}, "vendor only the files VENDOR.md lists"
    record = (VENDOR / "VENDOR.md").read_text(encoding="utf-8")
    for name, digest in VENDORED.items():
        assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == digest, name
        assert digest in record and f"`{name}`" in record, name
    assert f"three.js {THREE_VERSION} (MIT)" in record
    assert f"https://registry.npmjs.org/three/-/three-{THREE_VERSION}.tgz" in record
    licence = (VENDOR / "three" / "LICENSE").read_text(encoding="utf-8")
    assert licence.startswith("The MIT License") and "three.js authors" in licence
    assert f"const REVISION = '{THREE_VERSION.split('.')[1]}';" in (VENDOR / "three" / "three.core.js").read_text(encoding="utf-8")


def test_the_page_loads_three_js_from_the_package_only():
    script = (WEB / "observatory.js").read_text(encoding="utf-8")
    assert re.findall(r'import\("([^"]+)"\)|import\((\w+)\)', script) == [("", "OBS_THREE"), ("", "OBS_THREE")]
    assert 'const OBS_THREE = "/static/vendor/three/three.module.js";' in script
    module = (VENDOR / "three" / "three.module.js").read_text(encoding="utf-8")
    assert set(re.findall(r"^(?:import|export) .* from '([^']+)';$", module, re.MULTILINE)) == {"./three.core.js"}
    core = (VENDOR / "three" / "three.core.js").read_text(encoding="utf-8")
    assert not re.search(r"^\s*import\s", core, re.MULTILINE) and "import(" not in core
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    assert '<script src="/static/observatory.js" defer></script>' in page
    # No page asset names another host: every script and stylesheet is local, and no script fetches by URL.
    assert not re.search(r'(src|href)="(https?:)?//', page)
    for name in PAGE_SCRIPTS:
        text = (WEB / name).read_text(encoding="utf-8")
        assert not re.search(r"""(fetch|import)\(\s*["'`](https?:)?//""", text), name
        assert "cdn" not in text.lower(), name
    assert "fetch(" not in script and "api(" not in script and "/v1/" not in script, "the 3D view reuses brain.js's map"


def test_the_vendored_files_are_served_and_shipped_in_the_wheel(monkeypatch):
    # No database is reached: the static routes need none, and the service is a stand-in.
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://unused@127.0.0.1:1/unused")
    with TestClient(create_app(Settings.from_env(), service=object()), base_url="http://127.0.0.1") as client:
        for name in ("three/three.module.js", "three/three.core.js"):
            response = client.get(f"/static/vendor/{name}")
            assert response.status_code == 200 and response.content == (VENDOR / name).read_bytes()
            # Module scripts are refused unless served as JavaScript (the service sends nosniff).
            assert response.headers["content-type"].split(";")[0] in {"text/javascript", "application/javascript"}
        assert "observatory.js" in client.get("/memory").text
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = project["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert "src/membrain" in wheel["packages"] and "exclude" not in wheel
    try:
        ignored = subprocess.run(["git", "check-ignore", *[str(VENDOR / name) for name in VENDORED],
                                  str(WEB / "observatory.js")], cwd=ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        pytest.skip("git is not installed")
    assert ignored.returncode == 1 and ignored.stdout == "", "the wheel build skips git-ignored files"


def test_the_3d_view_draws_exactly_the_edge_types_the_map_records():
    source = (ROOT / "src" / "membrain" / "memory_map.py").read_text(encoding="utf-8")
    recorded = set(re.findall(r'^\s+edge\(.*, "(\w+)", "\w+"\)$', source, re.MULTILINE))
    assert recorded == MEMORY_EDGE_TYPES, "the map's edge types changed; update the 3D view's legend and styles"
    script = (WEB / "observatory.js").read_text(encoding="utf-8")
    styles = re.search(r"const OBS_EDGES = \{(.*?)\n\};", script, re.DOTALL).group(1)
    assert set(re.findall(r"^\s+(\w+): \{", styles, re.MULTILINE)) == EDGE_TYPES
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    assert set(re.findall(r'data-edge="(\w+)"', page)) == EDGE_TYPES
    assert '"source"' not in styles and 'data-edge="source"' not in page
    for name in EDGE_TYPES:
        assert f".edge-swatch.edge-{name}" in (WEB / "memory.css").read_text(encoding="utf-8") or name == "derived_from"


def test_frames_are_drawn_on_demand_with_no_loop_or_simulation():
    script = (WEB / "observatory.js").read_text(encoding="utf-8")
    assert script.count("requestAnimationFrame(") == 1
    assert "if (!obs.pending) obs.pending = requestAnimationFrame(obsFrame);" in script
    assert "setInterval" not in script and "setAnimationLoop" not in script
    assert not re.search(r"force|simulation|tick\(", script.split("\n", 12)[-1], re.IGNORECASE)
    # The only repeat inside a frame is an unfinished camera move, which reduced motion never starts.
    frame = script[script.index("function obsFrame("):script.index("function obsPlaceLabels(")]
    assert frame.count("obsRequestRender()") == 1 and "if (moving) obsRequestRender();" in frame
    assert 'document.visibilityState === "hidden"' in frame
    move = script[script.index("function obsMoveCamera("):script.index("function obsStepAnimation(")]
    assert "obsReducedMotion()" in move and "obs.animation = null;" in move
    # Positions come from the node's region and ID alone.
    assert "obsRandom(obsHash(`${node.region}|${node.id}`))" in script
    assert "Math.random" not in script and "Date.now" not in script
    # Switching away frees every geometry and material.
    dispose = script[script.index("function obsDispose("):script.index("function obsBuild(")]
    assert "geometry?.dispose()" in dispose and "material.dispose()" in dispose and "renderLists.dispose()" in dispose


def test_the_view_says_what_its_marks_mean_and_which_layers_are_missing():
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    text = " ".join(page.split())
    assert "The brain-shaped shell is an illustrative container, not neuroscience." in text
    assert "Size is the map's layout weight" in text and "It is not memory strength, confidence or importance." in text
    assert "returned by the latest recorded recall" in text and "is not everything a reply used." in text
    assert "Being close together in space means nothing." in text
    script = (WEB / "observatory.js").read_text(encoding="utf-8")
    for wording in ("current reply", "playback", "signal travels", "activation"):
        assert wording not in text.lower() and wording not in script.lower(), wording
    layers = re.findall(r'<li data-layer="(\w+)"><strong>[^<]+</strong> <span>', page)
    assert set(layers) == {"assertions", "episodes", "persona", "mood", "relationship"}
    for layer in ("assertions", "episodes"):
        assert re.search(rf'data-layer="{layer}">.*?Available in Memories', page, re.DOTALL)
    for layer in ("persona", "mood"):
        assert re.search(rf'data-layer="{layer}">.*?Available in', page, re.DOTALL)
    assert "Companion development includes a derived familiarity summary" in text
    assert "the summary is not an extra neuron." in text


def test_every_string_the_3d_view_writes_has_chinese():
    script = (WEB / "observatory.js").read_text(encoding="utf-8")
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    messages = re.search(r"const OBS_MESSAGES = \{(.*?)\n\};", script, re.DOTALL).group(1)
    texts = re.findall(r':\s*"([^"]+)"', messages) + ["Latest recorded recall", "derived from", "about person",
                                                         "feeling of"]
    assert len(texts) == 8
    zh = dictionary[:dictionary.index("const ZH_PATTERNS")]
    for text in texts:
        assert re.search(rf'"{re.escape(text)}":\s*"[^"]*[一-鿿]', zh), text
