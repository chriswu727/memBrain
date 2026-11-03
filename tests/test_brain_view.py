import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "membrain" / "web"
REGIONS = ["people", "constraints", "preferences", "plans", "commitments", "routines", "milestones", "relationship",
           "other", "episodes"]


def test_the_demo_map_served_to_the_page_is_the_fictional_example():
    served = json.loads((WEB / "memory-map-demo.json").read_text(encoding="utf-8"))
    example = json.loads((WEB.parents[2] / "examples" / "memory-map-demo.json").read_text(encoding="utf-8"))
    assert served == example and served["demo"] is True


def test_the_brain_view_draws_every_contract_region_and_is_wired_into_the_page():
    script = (WEB / "brain.js").read_text(encoding="utf-8")
    assert sorted(re.findall(r'\{ id: "(\w+)", label:', script)) == sorted(REGIONS)
    assert "/memory-map?max_nodes=200&max_edges=400" in script
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    assert '<script src="/static/brain.js" defer></script>' in page and 'id="view-brain"' in page
    assert 'data-view="brain"' in page
    styles = (WEB / "memory.css").read_text(encoding="utf-8")
    for region in REGIONS:
        assert f".brain-node.region-{region} " in styles and f"--r-{region}:" in styles
