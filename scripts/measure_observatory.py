"""Measure the memory page's 3D observatory in a real browser: first frame, interaction frames, picking, heap, idle.

    python scripts/measure_observatory.py                              # headless Chromium, 200/400 and 500/1000
    python scripts/measure_observatory.py --headed --channel chrome    # the installed Chrome, with the real GPU
    python scripts/measure_observatory.py --sizes 500x1000 --samples 120 --dpr 2 --out result.json

It needs only Playwright with a Chromium (the dev dependency group); no database, service, model or network. A small
local HTTP server on an ephemeral port serves the package's own web assets (src/membrain/web) with the service's
security headers, and answers /static/memory-map-demo.json with a generated fictional map of the requested size, so
the page runs in its demo mode and makes no /v1/ request. Everything is measured inside the page after the map
payload has arrived:

- first frame: from the page's "membrain-map-payload" mark to the observatory's first frame of that map, cold (the
  first load, including fetching and parsing three.js) and warm (the map loaded again into a ready renderer);
- interaction frames: real mouse drags and wheel zooms through Playwright; each frame records its input event's
  timestamp, and in measurement mode it waits for the GPU (a one-pixel readPixels) so the time includes drawing;
- pick to detail: real clicks on projected node positions; from the pointerup to the detail panel being filled, and
  to the next 3D frame that shows the selection;
- JS heap after load (Chromium's JSHeapUsedSize, after a forced garbage collection);
- frames over an idle period and while the page is reported hidden: requestAnimationFrame calls are counted by an
  injected wrapper, and must be 0.

The proposed acceptance targets (architecture/phase-c-design.md, C0 revision) are p95 interaction frame <= 33.3 ms and
p95 pick to detail <= 100 ms on the reference Mac. The script reports the renderer string. A software renderer
(SwiftShader, llvmpipe, Microsoft Basic Render) is labelled as such and its numbers can never pass those gates; they
are indicative only. Run it headed with a GPU-backed browser on the reference Mac for a gate result.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "membrain" / "web"
NOTE_REGIONS = [("plans", "plan"), ("commitments", "agent_commitment"), ("preferences", "preference"),
                ("constraints", "constraint"), ("routines", "routine"), ("people", "person"),
                ("relationship", "milestone"), ("milestones", "milestone"), ("other", "other")]
REGION_ORDER = ["people", "constraints", "preferences", "plans", "commitments", "routines", "milestones",
                "relationship", "other", "episodes", "emotions"]
HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
           "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                                       "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")}
SOFTWARE_GL = ("swiftshader", "llvmpipe", "softpipe", "basic render", "software")
FRAME_GATE_MS, PICK_GATE_MS = 33.3, 100.0
RAF_COUNTER = """(() => {
  const original = window.requestAnimationFrame.bind(window);
  window.__rafCalls = 0;
  window.requestAnimationFrame = (callback) => { window.__rafCalls += 1; return original(callback); };
})();"""


def fixture_map(nodes: int = 200, edges: int = 400, traced: int = 8) -> dict:
    """A fictional map of exactly ``nodes`` nodes and ``edges`` edges, shaped like memory_map.py's payload."""
    affect_count = max(1, nodes // 10)
    message_count = (nodes - affect_count) // 2
    note_count = nodes - affect_count - message_count
    out_nodes, out_edges = [], []
    clock = 0

    def stamp():
        nonlocal clock
        clock += 1
        return f"2026-10-{1 + (clock // 1440) % 28:02d}T{(clock // 60) % 24:02d}:{clock % 60:02d}:00Z"

    notes = []
    for index in range(note_count):
        region, kind = NOTE_REGIONS[index % len(NOTE_REGIONS)]
        node = {"id": f"note:fx-{index:04d}", "region": region, "kind": kind,
                "label": f"Fictional {kind.replace('_', ' ')} note {index}", "status": None, "date": None,
                "sensitive": False, "recorded_at": stamp(), "weight": 1.0 if index % 10 == 0 else 0.5}
        notes.append(node)
    messages = [{"id": f"msg:fx-{index:04d}", "region": "episodes", "kind": "message",
                 "label": f"Fictional message {index}", "status": None, "date": None, "sensitive": False,
                 "recorded_at": stamp(), "weight": 0.25} for index in range(message_count)]
    feelings = [{"id": f"affect:fx-{index:04d}", "region": "emotions", "kind": "affect",
                 "label": f"fictional feeling {index}", "status": None, "date": None, "sensitive": False,
                 "basis": "reported" if index % 2 else "inferred", "recorded_at": stamp(), "weight": 0.25}
                for index in range(affect_count)]
    out_nodes = notes + feelings + messages
    for index, node in enumerate(out_nodes):
        node["traced"] = node["kind"] == "message" and index % max(1, message_count // max(1, traced)) == 0
    seen = set()

    def add(source, target, kind, basis):
        if len(out_edges) < edges and (source, target, kind) not in seen and source != target:
            seen.add((source, target, kind))
            out_edges.append({"source": source, "target": target, "type": kind, "basis": basis})

    people = [node for node in notes if node["kind"] == "person"]
    for index, feeling in enumerate(feelings):
        add(feeling["id"], notes[index % len(notes)]["id"], "feeling_of", "note")
    for index, note in enumerate(notes):
        if people and note["kind"] != "person" and index % 4 == 1:
            add(note["id"], people[index % len(people)]["id"], "about_person", "about")
    step = 0
    while len(out_edges) < edges and message_count:
        note = notes[step % len(notes)]
        message = messages[(step * 7 + step // len(notes)) % message_count]
        add(note["id"], message["id"], "derived_from", "source_event_ids")
        step += 1
        if step > edges * 50:
            break
    regions = []
    for region in REGION_ORDER:
        items = [node for node in out_nodes if node["region"] == region]
        regions.append({"id": region, "count": len(items),
                        "last_activity": max((node["recorded_at"] for node in items), default=None)})
    shown = sum(1 for node in out_nodes if node["traced"])
    return {"brain_id": "fictional-measurement", "generated_at": "2026-11-04T12:00:00Z", "demo": True,
            "truncated": False, "limits": {"max_nodes": nodes, "max_edges": edges}, "regions": regions,
            "nodes": out_nodes, "edges": out_edges, "trace": {"at": "2026-11-04T11:59:00Z", "used": shown, "shown": shown}}


class _Handler(SimpleHTTPRequestHandler):
    map_body = (WEB / "memory-map-demo.json").read_bytes()

    def log_message(self, *args):
        pass

    def end_headers(self):
        for name, value in HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/static/memory-map-demo.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(self.map_body)))
            self.end_headers()
            self.wfile.write(self.map_body)
            return
        if path == "/memory":
            self.path = "/memory.html"
        elif path.startswith("/static/"):
            self.path = path[len("/static"):]
        else:
            self.send_error(404)
            return
        super().do_GET()

    def guess_type(self, path):
        return "text/javascript" if str(path).endswith(".js") else super().guess_type(path)


class StaticServer:
    """The package's web assets on an ephemeral local port; the demo map is whatever ``set_map`` last gave."""

    def __init__(self):
        handler = type("Handler", (_Handler,), {})
        self._handler = handler
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), partial(handler, directory=str(WEB)))
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def set_map(self, payload: dict):
        self._handler.map_body = json.dumps(payload).encode()

    def close(self):
        self._server.shutdown()
        self._server.server_close()


def _percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    return round(ordered[min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))], 2)


def _summary(values):
    return {"samples": len(values), "median_ms": round(statistics.median(values), 2) if values else None,
            "p95_ms": _percentile(values, 0.95), "max_ms": round(max(values), 2) if values else None}


def _wait_renders(page, before, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = page.evaluate("() => window.observatory.snapshot()")
        if state["renders"] > before and not state["pending"] and not state["animating"]:
            return state
        page.wait_for_timeout(5)
    raise TimeoutError("the observatory did not draw a frame")


def _wait_ready(page):
    page.wait_for_function("() => window.observatory && window.observatory.snapshot().renders > 0"
                           " && window.observatory.snapshot().generation > 0", timeout=60_000)


def _first_frame(page):
    return page.evaluate("""() => {
        const payload = performance.getEntriesByName("membrain-map-payload").at(-1);
        const frame = performance.getEntriesByName("membrain-observatory-frame").at(-1);
        return payload && frame ? frame.startTime - payload.startTime : null;
    }""")


def _machine():
    cpu = platform.processor() or ""
    try:
        if platform.system() == "Darwin":
            cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        elif Path("/proc/cpuinfo").is_file():
            cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                        if line.startswith("model name")), cpu)
    except OSError:
        pass
    return {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "cpu": cpu,
            "logical_cpus": os.cpu_count()}


def measure(page, server, nodes, edges, samples, cdp):
    server.set_map(fixture_map(nodes, edges))
    page.goto(f"{server.base_url}/memory?demo=brain")
    _wait_ready(page)
    cold = _first_frame(page)
    page.wait_for_timeout(300)
    # Warm first frame: the same payload loaded again into the renderer that is already running.
    warm = []
    for _ in range(5):
        generation = page.evaluate("() => window.observatory.snapshot().generation")
        page.evaluate("() => window.loadBrain()")
        page.wait_for_function(f"() => window.observatory.snapshot().generation > {generation}"
                               " && !window.observatory.snapshot().pending")
        page.wait_for_timeout(50)
        warm.append(_first_frame(page))
    snapshot = page.evaluate("() => window.observatory.snapshot()")
    assert len(snapshot["nodes"]) == nodes and len(snapshot["edges"]) == edges, (len(snapshot["nodes"]), len(snapshot["edges"]))
    cdp.send("HeapProfiler.collectGarbage")
    metrics = {item["name"]: item["value"] for item in cdp.send("Performance.getMetrics")["metrics"]}

    box = page.locator("#observatory-canvas").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.evaluate("() => { window.observatory.measure(true); window.observatory.clearTimings(); }")
    # Drags: one small mouse move per frame, waiting for that frame before the next move.
    page.mouse.move(cx, cy)
    page.mouse.down()
    for step in range(samples):
        before = page.evaluate("() => window.observatory.snapshot().renders")
        page.mouse.move(cx + ((step % 20) - 10) * 4, cy + ((step % 7) - 3) * 3)
        _wait_renders(page, before)
    page.mouse.up()
    for step in range(max(10, samples // 3)):
        before = page.evaluate("() => window.observatory.snapshot().renders")
        page.mouse.wheel(0, 120 if step % 2 else -120)
        _wait_renders(page, before)
    frames = [frame for frame in page.evaluate("() => window.observatory.timings().frames") if frame["input"]]
    render_ms = [frame["end"] - frame["start"] for frame in frames]
    input_ms = [frame["end"] - frame["input"] for frame in frames]

    # Picks: click the projected centre of nodes that the pick at that point resolves to.
    page.evaluate("() => window.observatory.clearTimings()")
    targets = page.evaluate("""(count) => {
        const out = [];
        for (const id of window.observatory.snapshot().nodes) {
            const at = window.observatory.project(id);
            if (at && at.inside && window.observatory.pickAt(at.x, at.y) === id) out.push({ id, x: at.x, y: at.y });
            if (out.length >= count) break;
        }
        return out;
    }""", max(10, samples // 2))
    for target in targets:
        before = page.evaluate("() => window.observatory.snapshot().renders")
        page.mouse.click(target["x"], target["y"])
        _wait_renders(page, before)
        assert page.evaluate("() => window.observatory.snapshot().selected") == target["id"]
    picks = page.evaluate("() => window.observatory.timings().picks")
    detail_ms = [pick["detail"] - pick["input"] for pick in picks]
    pick_frame_ms = [pick["frame"] - pick["input"] for pick in picks if pick["frame"]]
    page.evaluate("() => window.observatory.measure(false)")

    # Idle and hidden: no requestAnimationFrame at all.
    page.mouse.move(box["x"] + box["width"] + 40, cy)
    page.wait_for_timeout(1000)
    idle_before = page.evaluate("() => [window.__rafCalls, window.observatory.snapshot().renders]")
    page.wait_for_timeout(10_000)
    idle_after = page.evaluate("() => [window.__rafCalls, window.observatory.snapshot().renders]")
    hidden = page.evaluate("""async () => {
        Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
        document.dispatchEvent(new Event("visibilitychange"));
        const before = [window.__rafCalls, window.observatory.snapshot().renders];
        const canvas = document.getElementById("observatory-canvas");
        for (let i = 0; i < 20; i += 1) canvas.dispatchEvent(new WheelEvent("wheel", { deltaY: 60, bubbles: true, cancelable: true }));
        window.dispatchEvent(new Event("resize"));
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const after = [window.__rafCalls, window.observatory.snapshot().renders];
        delete document.visibilityState;
        document.dispatchEvent(new Event("visibilitychange"));
        return { raf: after[0] - before[0], renders: after[1] - before[1] };
    }""")
    return {
        "nodes": nodes, "edges": edges,
        "first_frame_after_payload_ms": {"cold_including_three_js_load": round(cold, 2) if cold is not None else None,
                                         "warm": _summary([value for value in warm if value is not None])},
        "interaction_frame_render_ms": _summary(render_ms),
        "interaction_input_to_frame_ms": _summary(input_ms),
        "pick_to_detail_ms": _summary(detail_ms),
        "pick_to_frame_ms": _summary(pick_frame_ms),
        "js_heap_used_mb_after_load": round(metrics.get("JSHeapUsedSize", 0) / 1e6, 2),
        "js_heap_total_mb_after_load": round(metrics.get("JSHeapTotalSize", 0) / 1e6, 2),
        "idle_10s": {"raf_calls": idle_after[0] - idle_before[0], "frames": idle_after[1] - idle_before[1]},
        "hidden_2s_with_input": hidden,
        "gpu_memory": snapshot["gpu"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sizes", default="200x400,500x1000", help="nodes x edges, comma separated")
    parser.add_argument("--samples", type=int, default=60, help="drag frames per size (zoom and picks scale with it)")
    parser.add_argument("--dpr", type=float, default=1.0, help="device pixel ratio to emulate (the page caps it at 2)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--headed", action="store_true", help="run a visible browser (uses the real GPU)")
    parser.add_argument("--channel", help="a Playwright browser channel such as chrome")
    parser.add_argument("--out", help="write the JSON result here as well as to stdout")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    server = StaticServer()
    result = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "machine": _machine(),
              "viewport": {"width": args.width, "height": args.height, "device_scale_factor": args.dpr},
              "samples": args.samples, "warm_up": "one cold load, then five warm reloads of the same map", "runs": []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed, channel=args.channel)
            result["browser"] = {"name": "chromium", "version": browser.version, "headless": not args.headed,
                                 "channel": args.channel}
            for size in args.sizes.split(","):
                nodes, edges = (int(part) for part in size.lower().split("x"))
                context = browser.new_context(viewport={"width": args.width, "height": args.height},
                                              device_scale_factor=args.dpr, locale="en-US")
                context.add_init_script(RAF_COUNTER)
                page = context.new_page()
                requests = []
                page.on("request", lambda request: requests.append(request.url))
                cdp = context.new_cdp_session(page)
                cdp.send("Performance.enable")
                run = measure(page, server, nodes, edges, args.samples, cdp)
                run["renderer"] = page.evaluate("() => window.observatory.renderer()")
                run["page_pixel_ratio"] = page.evaluate("() => window.observatory.snapshot().pixelRatio")
                run["api_requests"] = sum(1 for url in requests if "/v1/" in url)
                run["other_hosts"] = sorted({url.split("/")[2] for url in requests if url.startswith("http")
                                             and not url.startswith(server.base_url)})
                result["runs"].append(run)
                context.close()
            browser.close()
    finally:
        server.close()
    software = any(word in json.dumps([run["renderer"] for run in result["runs"]]).lower() for word in SOFTWARE_GL)
    result["software_gl"] = software
    result["gates"] = {
        "proposed": {"interaction_frame_p95_ms": FRAME_GATE_MS, "pick_to_detail_p95_ms": PICK_GATE_MS},
        "status": ("not applicable: a software renderer cannot pass or fail the reference-Mac gates; indicative only"
                   if software else "evaluated below; valid as a gate result only on the reference Mac"),
        "runs": [{"nodes": run["nodes"], "edges": run["edges"],
                  "interaction_frame_p95_ok": None if software else (run["interaction_input_to_frame_ms"]["p95_ms"] or 1e9) <= FRAME_GATE_MS,
                  "pick_to_detail_p95_ok": None if software else (run["pick_to_detail_ms"]["p95_ms"] or 1e9) <= PICK_GATE_MS,
                  "idle_and_hidden_zero_frames": run["idle_10s"]["raf_calls"] == 0 and run["hidden_2s_with_input"]["raf"] == 0}
                 for run in result["runs"]],
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
