"use strict";
// memBrain memory page: showcase mode. A full-screen, dark rendering of the memory map that brain.js already loaded,
// for presenting and screen recording. It makes no request of its own.
// In the SVG fallback every dot is a node of the map, and every line or travelling light is an edge of the map. The
// silhouette, folds, glow and background are decoration in their own layer: drawn as dark grooves, never as dots or
// lit lines, and never counted.

const SHOW_VIEWBOX = "90 18 652 486";
// A side view of the brain facing left (same coordinate space as brain.js): cerebrum with a notch where the lateral
// fissure starts, temporal lobe below it, cerebellum tucked under the occipital lobe, and the brain stem.
const SHOW_CEREBRUM = "M290 312 C262 322 212 324 172 312 C134 300 108 270 106 232 C104 186 122 140 160 106 " +
  "C206 66 276 44 350 38 C424 30 504 36 566 58 C632 82 686 128 708 184 C726 228 726 262 716 282 " +
  "C706 304 684 320 656 326 C628 332 600 330 576 334 C560 360 540 390 504 402 C452 416 372 416 316 404 " +
  "C270 394 238 376 236 352 C234 334 252 322 290 312 Z";
const SHOW_CEREBELLUM = "M580 330 C610 320 664 318 696 334 C718 348 720 376 704 400 C686 424 644 436 608 432 " +
  "C578 428 558 410 554 388 C552 364 560 342 580 330 Z";
const SHOW_STEM = "M520 388 C530 410 532 432 524 452 C518 468 512 484 512 504 L546 504 C546 484 552 468 560 452 " +
  "C570 430 578 408 574 384 Z";
const SHOW_STEM_SIDES = ["M520 388 C530 410 532 432 524 452 C518 468 512 484 512 504",
  "M574 384 C578 408 570 430 560 452 C552 468 546 484 546 504"];
// Spines of the main sulci: lateral fissure, central, precentral, postcentral, superior and inferior frontal,
// superior and inferior temporal, intraparietal, lunate and parieto-occipital.
const SHOW_SULCI = [
  [[290, 312], [330, 300], [390, 288], [450, 278], [505, 268], [540, 248], [552, 228]],
  [[470, 36], [462, 80], [446, 130], [430, 180], [420, 226], [414, 262]],
  [[410, 38], [402, 86], [388, 136], [374, 186], [364, 236], [356, 276]],
  [[530, 48], [516, 100], [500, 150], [488, 200], [480, 250]],
  [[380, 78], [330, 74], [276, 84], [222, 104], [178, 138]],
  [[356, 170], [306, 166], [252, 176], [198, 198], [148, 236]],
  [[300, 350], [360, 334], [430, 322], [500, 310], [556, 290], [610, 262]],
  [[320, 384], [392, 378], [462, 370], [530, 356]],
  [[510, 160], [566, 146], [624, 158], [672, 190]],
  [[700, 226], [682, 262], [664, 300]],
  [[640, 92], [652, 130]],
];
// Region placement for this silhouette (illustrative, like the brain view) and the largest cluster radius there.
const SHOW_ANCHORS = { plans: [222, 150, 55], commitments: [196, 250, 42], preferences: [316, 104, 45],
  constraints: [446, 78, 38], routines: [582, 122, 50], episodes: [440, 205, 72], people: [352, 352, 36],
  relationship: [488, 340, 40], milestones: [652, 222, 48], other: [632, 382, 36], emotions: [316, 250, 38],
  persona: [340, 170, 40], mood: [445, 285, 40], semantic: [370, 210, 45], episodic: [470, 210, 45], schemas: [530, 275, 40],
  working: [245, 245, 40] };
const SHOW_COLOURS = { plans: "#ffa94d", commitments: "#ff8466", preferences: "#b69cff", constraints: "#ff6f9e",
  routines: "#57b8ff", episodes: "#3ee0b0", people: "#ffd54a", relationship: "#e59cf5", milestones: "#7f9bff",
  other: "#b8c2cc", emotions: "#a6e05a", persona: "#b69cff", mood: "#ffb86b",
  semantic: "#6ae4ff", episodic: "#9c9aff", schemas: "#e69cff", working: "#ffcf70" };
const MAX_PULSES = 40;
const showState = { open: false, frame: 0, slots: [], links: [], nodes: {}, opener: null, rendered: null, folds: null };
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Deterministic pseudo-random numbers, so the folds and the signal rhythm look the same each time.
function seeded(seed) {
  let value = seed >>> 0;
  return () => { value = (value * 1664525 + 1013904223) >>> 0; return value / 4294967296; };
}

function fixed(value) { return value.toFixed(1); }

// A smooth path through points (Catmull-Rom as cubic Béziers).
function smoothPath(p) {
  let d = `M${fixed(p[0][0])} ${fixed(p[0][1])}`;
  for (let i = 0; i < p.length - 1; i++) {
    const a = p[i - 1] || p[i], b = p[i], c = p[i + 1], e = p[i + 2] || c;
    d += ` C${fixed(b[0] + (c[0] - a[0]) / 6)} ${fixed(b[1] + (c[1] - a[1]) / 6)} ` +
      `${fixed(c[0] - (e[0] - b[0]) / 6)} ${fixed(c[1] - (e[1] - b[1]) / 6)} ${fixed(c[0])} ${fixed(c[1])}`;
  }
  return d;
}

// Points every `step` units along a polyline.
function densify(spine, step) {
  const points = [spine[0]];
  for (let i = 0; i < spine.length - 1; i++) {
    const [ax, ay] = spine[i], [bx, by] = spine[i + 1];
    const parts = Math.max(1, Math.round(Math.hypot(bx - ax, by - ay) / step));
    for (let k = 1; k <= parts; k++) points.push([ax + (bx - ax) * k / parts, ay + (by - ay) * k / parts]);
  }
  return points;
}

// Direction of the folds at a point: along the temporal lobe below the fissure, round the frontal pole in front,
// parallel to the central sulcus in the middle, and round the occipital pole behind.
function foldAngle(x, y) {
  const fissure = SHOW_SULCI[0];
  const below = x > 250 && x < 590 && y > fissure.reduce((best, [fx, fy]) => (Math.abs(fx - x) < Math.abs(best[0] - x) ? [fx, fy] : best))[1] + 8;
  if (below) return 0.05;
  if (x < 350) return Math.atan2(y - 225, x - 400) + Math.PI / 2;
  if (x < 560) return 1.81;
  return Math.atan2(y - 215, x - 560) + Math.PI / 2;
}

// The folds of the cortex: the main sulci with short side branches, then meandering folds that wander between
// them until they come close to another fold, which fills the surface like the gyri of a real brain.
function cortexFolds() {
  if (showState.folds) return showState.folds;
  const random = seeded(7);
  const deep = [], major = [], minor = [];
  const cell = 4, taken = new Set();
  const key = (x, y) => `${Math.floor(x / cell)},${Math.floor(y / cell)}`;
  const mark = (points) => {
    for (let i = 0; i < points.length - 1; i++) {
      const [ax, ay] = points[i], [bx, by] = points[i + 1], steps = Math.ceil(Math.hypot(bx - ax, by - ay) / 2);
      for (let k = 0; k <= steps; k++) taken.add(key(ax + (bx - ax) * k / steps, ay + (by - ay) * k / steps));
    }
  };
  const crowded = (x, y, gap) => {
    for (let dx = -gap; dx <= gap; dx += cell) for (let dy = -gap; dy <= gap; dy += cell) {
      if (dx * dx + dy * dy <= gap * gap && taken.has(key(x + dx, y + dy))) return true;
    }
    return false;
  };
  SHOW_SULCI.forEach((spine, index) => {
    const wave = index === 0 ? 1.2 : index === 1 ? 2.2 : 3.4;
    const points = densify(spine, 15).map(([x, y], i, all) => {
      if (i === 0 || i === all.length - 1) return [x, y];
      const [ax, ay] = all[i - 1], [bx, by] = all[i + 1], length = Math.hypot(bx - ax, by - ay) || 1;
      const offset = (i % 2 ? 1 : -1) * wave * (0.6 + random() * 0.8);
      return [x - offset * (by - ay) / length, y + offset * (bx - ax) / length];
    });
    (index < 2 ? deep : major).push(smoothPath(points));
    mark(points);
    for (let i = 2; i < points.length - 1; i += 2) {
      const [ax, ay] = points[i - 1], [bx, by] = points[i + 1], length = Math.hypot(bx - ax, by - ay) || 1;
      const side = (i / 2) % 2 ? 1 : -1;
      const along = [(bx - ax) / length, (by - ay) / length], across = [-along[1] * side, along[0] * side];
      const reach = 12 + random() * 12, lean = (random() - 0.3) * 0.8;
      const [x, y] = points[i];
      const tip = [x + (across[0] + along[0] * lean) * reach, y + (across[1] + along[1] * lean) * reach];
      const bend = [x + across[0] * reach * 0.55 + along[0] * 4, y + across[1] * reach * 0.55 + along[1] * 4];
      minor.push(`M${fixed(x)} ${fixed(y)} Q${fixed(bend[0])} ${fixed(bend[1])} ${fixed(tip[0])} ${fixed(tip[1])}`);
      mark([[x, y], bend, tip]);
    }
  });
  const seeds = [];
  for (let y = 36; y < 418; y += 14) for (let x = 100; x < 730; x += 14) seeds.push([x + random() * 10, y + random() * 10, random()]);
  seeds.sort((a, b) => a[2] - b[2]);
  for (const [sx, sy] of seeds) {
    if (crowded(sx, sy, 10)) continue;
    let angle = foldAngle(sx, sy) + (random() - 0.5) * 0.8 + (random() < 0.5 ? Math.PI : 0);
    let turn = (random() - 0.5) * 0.6, turned = 0;
    const points = [[sx, sy]];
    for (let step = 0; step < 9; step++) {
      turn = Math.max(-0.55, Math.min(0.55, turn + (random() - 0.5) * 0.5));
      // Never curl round into a ring, which could be mistaken for a memory.
      if (Math.abs(turned + turn) > 1.7) turn = -turn;
      turned += turn;
      angle += turn;
      const [px, py] = points[points.length - 1];
      const next = [px + Math.cos(angle) * 8, py + Math.sin(angle) * 8];
      if (next[0] < 96 || next[0] > 734 || next[1] < 26 || next[1] > 420 || crowded(next[0], next[1], 8)) break;
      points.push(next);
    }
    if (points.length < 3) continue;
    minor.push(smoothPath(points));
    mark(points);
  }
  showState.folds = { deep, major, minor };
  return showState.folds;
}

// Cerebellum folia: arcs fanning out from where the cerebellum meets the stem.
function foliaPaths() {
  const paths = [];
  for (let r = 18; r < 140; r += 11) {
    const [cx, cy, a0, a1] = [578, 334, -0.25, 2.1];
    paths.push(`M${fixed(cx + r * Math.cos(a0))} ${fixed(cy + r * Math.sin(a0))} ` +
      `A${r} ${r} 0 0 1 ${fixed(cx + r * Math.cos(a1))} ${fixed(cy + r * Math.sin(a1))}`);
  }
  return paths;
}

function decoration() {
  const defs = svg("defs");
  defs.innerHTML = `
    <radialGradient id="show-fill" cx="42%" cy="36%" r="72%">
      <stop offset="0" stop-color="#2d3769"/><stop offset=".6" stop-color="#1c2349"/><stop offset="1" stop-color="#131834"/>
    </radialGradient>
    <radialGradient id="show-fill-small" cx="30%" cy="20%" r="90%">
      <stop offset="0" stop-color="#262e5a"/><stop offset="1" stop-color="#121730"/>
    </radialGradient>
    <linearGradient id="show-stem-fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#1a2144"/><stop offset=".7" stop-color="#151b38"/><stop offset="1" stop-color="#151b38" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="show-stem-line" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#b3c0ff" stop-opacity=".6"/><stop offset=".75" stop-color="#b3c0ff" stop-opacity=".35"/>
      <stop offset="1" stop-color="#b3c0ff" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="show-clip-cerebrum"><path d="${SHOW_CEREBRUM}"/></clipPath>
    <clipPath id="show-clip-cerebellum"><path d="${SHOW_CEREBELLUM}"/></clipPath>
    <filter id="show-rim" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="6"/></filter>
    <filter id="show-glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="2.6" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>`;
  // Decoration only: aria-hidden, no pointer events, never part of the counts.
  const art = svg("g", { class: "show-decoration", "aria-hidden": "true" });
  const rim = svg("g", { class: "show-rim", filter: "url(#show-rim)" });
  rim.append(svg("path", { d: SHOW_CEREBRUM }), svg("path", { d: SHOW_CEREBELLUM }));
  art.append(rim, svg("path", { d: SHOW_STEM, class: "show-stem", fill: "url(#show-stem-fill)" }));
  for (const d of SHOW_STEM_SIDES) art.append(svg("path", { d, class: "show-stem-side", stroke: "url(#show-stem-line)" }));
  art.append(svg("path", { d: SHOW_CEREBELLUM, class: "show-lobe", fill: "url(#show-fill-small)" }));
  const folia = svg("g", { "clip-path": "url(#show-clip-cerebellum)", class: "show-folds" });
  for (const d of foliaPaths()) folia.append(svg("path", { d, class: "show-groove folium" }), svg("path", { d, class: "show-ridge minor" }));
  art.append(folia, svg("path", { d: SHOW_CEREBRUM, class: "show-lobe", fill: "url(#show-fill)" }));
  const folds = svg("g", { "clip-path": "url(#show-clip-cerebrum)", class: "show-folds" });
  const { deep, major, minor } = cortexFolds();
  for (const [list, kind] of [[minor, "minor"], [major, "major"], [deep, "deep"]]) {
    for (const d of list) folds.append(svg("path", { d, class: `show-groove ${kind}` }), svg("path", { d, class: `show-ridge ${kind}` }));
  }
  art.append(folds);
  return [defs, art];
}

function anchorOf(region) {
  const id = regionOf(region).id;
  const [x, y, reach] = SHOW_ANCHORS[id];
  return { id, x, y, reach };
}

function spacingFor(anchor, count) { return Math.max(4.5, Math.min(13, anchor.reach / Math.sqrt(count))); }

// Placement: a sunflower spiral per region, oldest at the centre, tightening in crowded regions so clusters stay inside.
function showLayout(map) {
  if (map.contract_version === "memory-structure-v1") return Object.fromEntries(Object.entries(obsLayout(map))
    .map(([id, point]) => [id, { x: 400 + point[0] * 85, y: 250 - point[1] * 85,
      scale: .8, region: map.nodes.find((node) => node.id === id).region }]));
  const positions = {};
  const groups = {};
  for (const node of map.nodes) (groups[anchorOf(node.region).id] ||= []).push(node);
  for (const [region, nodes] of Object.entries(groups)) {
    const anchor = anchorOf(region), spacing = spacingFor(anchor, nodes.length);
    nodes.sort((a, b) => String(a.recorded_at).localeCompare(String(b.recorded_at)) || a.id.localeCompare(b.id));
    nodes.forEach((node, index) => {
      const distance = spacing * Math.sqrt(index + 0.5), angle = index * 2.39996;
      positions[node.id] = { x: anchor.x + distance * Math.cos(angle), y: anchor.y + distance * Math.sin(angle) * 0.8,
        scale: spacing / 13, region };
    });
  }
  return positions;
}

function renderShowcase(map) {
  stopPulses();
  const attributes = { viewBox: SHOW_VIEWBOX, preserveAspectRatio: "xMidYMid meet" };
  const still = svg("svg", { ...attributes, class: "show-still", role: "img", "aria-labelledby": "show-title",
    "aria-describedby": "show-counts" });
  still.append(...decoration());

  const positions = showLayout(map);
  // Every line and every travelling light comes from map.edges; edges whose ends are not drawn are left out and
  // not counted.
  const links = map.edges.filter((edge) => positions[edge.source] && positions[edge.target]);
  const edgeLayer = svg("g", { class: "show-edges", "aria-hidden": "true" });
  showState.links = links.map((edge) => {
    const from = positions[edge.source], to = positions[edge.target];
    const middle = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 - 24 };
    const d = `M${fixed(from.x)} ${fixed(from.y)} Q${fixed(middle.x)} ${fixed(middle.y)} ${fixed(to.x)} ${fixed(to.y)}`;
    edgeLayer.append(svg("path", { d, class: "show-edge" }));
    const length = Math.hypot(middle.x - from.x, middle.y - from.y) + Math.hypot(to.x - middle.x, to.y - middle.y);
    return { edge, from, to, middle, d, length };
  });
  still.append(edgeLayer);

  const recent = recentIds(map);
  const nodeLayer = svg("g", { class: "show-nodes", filter: "url(#show-glow)", "aria-hidden": "true" });
  showState.nodes = {};
  const drawn = map.nodes.filter((node) => positions[node.id]);
  for (const node of drawn) {
    const at = positions[node.id];
    const radius = (4.6 + 3.6 * Math.max(0, Math.min(1, Number(node.weight) || 0))) * Math.max(0.55, at.scale);
    showState.nodes[node.id] = { x: at.x, y: at.y, r: radius };
    nodeLayer.append(svg("circle", { cx: fixed(at.x), cy: fixed(at.y), r: fixed(radius), fill: SHOW_COLOURS[at.region],
      class: `show-node${recent.has(node.id) ? " recent" : ""}${node.sensitive ? " sensitive" : ""}` }));
  }
  still.append(nodeLayer);

  const perRegion = {};
  for (const node of drawn) perRegion[positions[node.id].region] = (perRegion[positions[node.id].region] || 0) + 1;
  const labels = svg("g", { class: "show-labels", "aria-hidden": "true" });
  for (const region of REGIONS) {
    if (!perRegion[region.id]) continue;
    const anchor = anchorOf(region.id);
    const extent = spacingFor(anchor, perRegion[region.id]) * Math.sqrt(perRegion[region.id]) * 0.8;
    const label = svg("text", { x: anchor.x, y: fixed(anchor.y - extent - 13), class: "show-label" });
    label.textContent = region.label;
    labels.append(label);
  }
  still.append(labels);
  // Moving parts live in their own layer so the still picture (with its filters) is painted once.
  const motion = svg("svg", { ...attributes, class: "show-motion", "aria-hidden": "true" });
  motion.innerHTML = `<defs><radialGradient id="show-pulse-halo"><stop offset="0" stop-color="#effeff" stop-opacity=".95"/>
    <stop offset=".3" stop-color="#9af2ff" stop-opacity=".5"/><stop offset="1" stop-color="#9af2ff" stop-opacity="0"/></radialGradient></defs>`;
  $("show-stage").replaceChildren(still, motion);

  const legend = $("show-legend");
  legend.replaceChildren();
  for (const region of REGIONS) {
    if (!perRegion[region.id]) continue;
    const item = element("span", "", "show-legend-item");
    const dot = element("span", "", "show-legend-dot");
    dot.style.background = SHOW_COLOURS[region.id];
    item.append(dot, element("span", region.label), element("span", String(perRegion[region.id]), "show-legend-count"));
    legend.append(item);
  }
  $("show-counts").textContent = drawn.length
    ? `${drawn.length} ${drawn.length === 1 ? "memory" : "memories"} · ${links.length} ${links.length === 1 ? "link" : "links"}`
    : "No memories yet. Talk with your agent, then come back.";
  $("show-demo").hidden = !(map.demo || brainState.demo);
  $("show-more").hidden = !map.truncated;
  showState.rendered = map;
  startPulses();
  $("show-fictional").hidden = !(map.demo || brainState.demo);
  hologram.open(map);
}

// Signals: at most MAX_PULSES lights at once. Each light travels along one link from showState.links (built from
// map.edges above), the link brightens while it does, and the node it reaches flashes; then it takes another link.
function startPulses() {
  stopPulses();
  const layer = $("show-stage").querySelector(".show-motion");
  if (!showState.open || document.hidden || hologram.renderer || hologram.paused || reducedMotion.matches || !layer || !showState.links.length) return;
  const random = seeded(11);
  const order = showState.links.map((link) => [random(), link]).sort((a, b) => a[0] - b[0]).map(([, link]) => link);
  const count = Math.min(MAX_PULSES, Math.ceil(order.length / 2));
  let next = 0;
  const now = performance.now();
  showState.slots = Array.from({ length: count }, (unused, index) => {
    const trail = svg("path", { class: "show-trail" });
    const ring = svg("circle", { class: "show-flash", r: "0" });
    const light = svg("g", { class: "show-pulse" });
    light.append(svg("circle", { r: "8", fill: "url(#show-pulse-halo)" }), svg("circle", { r: "2.1", class: "show-pulse-core" }));
    for (const part of [trail, ring, light]) { part.style.opacity = "0"; layer.append(part); }
    return { trail, ring, light, link: null, start: now + index * (3000 / count) + random() * 500, duration: 0, flash: null };
  });
  const step = (time) => {
    for (const slot of showState.slots) {
      if (slot.flash) {
        const f = (time - slot.flash.start) / 600;
        if (f >= 1) { slot.ring.style.opacity = "0"; slot.flash = null; }
        else { slot.ring.setAttribute("r", fixed(slot.flash.r + 1 + f * 7)); slot.ring.style.opacity = String(0.9 * (1 - f)); }
      }
      if (!slot.link) {
        if (time < slot.start) continue;
        slot.link = order[next++ % order.length];
        slot.start = time;
        slot.duration = 1000 + slot.link.length * 7;
        slot.trail.setAttribute("d", slot.link.d);
      }
      const t = (time - slot.start) / slot.duration;
      if (t >= 1) {
        const target = showState.nodes[slot.link.edge.target];
        slot.flash = { start: time, r: target.r };
        slot.ring.setAttribute("cx", fixed(target.x));
        slot.ring.setAttribute("cy", fixed(target.y));
        slot.light.style.opacity = slot.trail.style.opacity = "0";
        slot.link = null;
        slot.start = time + 400 + random() * 1800;
        continue;
      }
      const { from, middle, to } = slot.link, u = 1 - t, fade = Math.min(1, t * 6, (1 - t) * 6);
      const x = u * u * from.x + 2 * u * t * middle.x + t * t * to.x, y = u * u * from.y + 2 * u * t * middle.y + t * t * to.y;
      slot.light.setAttribute("transform", `translate(${fixed(x)} ${fixed(y)})`);
      slot.light.style.opacity = String(fade);
      slot.trail.style.opacity = String(0.55 * fade);
    }
    showState.frame = requestAnimationFrame(step);
  };
  showState.frame = requestAnimationFrame(step);
}

function stopPulses() {
  cancelAnimationFrame(showState.frame);
  for (const slot of showState.slots) { slot.trail.remove(); slot.ring.remove(); slot.light.remove(); }
  showState.slots = [];
}

function openShowcase() {
  const panel = $("brain-show");
  if (!showState.open) showState.opener = document.activeElement;
  showState.open = true;
  panel.hidden = false;
  document.body.classList.add("showing");
  for (const id of ["header", "main"]) document.querySelector(id).inert = true;
  panel.focus({ preventScroll: true });
  if (brainState.map && showState.rendered !== brainState.map) renderShowcase(brainState.map);
  else if (brainState.map) { startPulses(); hologram.open(brainState.map); }
}
window.openShowcase = openShowcase;

function closeShowcase() {
  if (!showState.open) return;
  showState.open = false;
  stopPulses();
  hologram.close();
  if (document.fullscreenElement === $("brain-show")) document.exitFullscreen().catch(() => {});
  $("brain-show").hidden = true;
  document.body.classList.remove("showing");
  for (const id of ["header", "main"]) document.querySelector(id).inert = false;
  showState.opener?.focus?.({ preventScroll: true });
}

document.addEventListener("brain-map", (event) => { if (showState.open) renderShowcase(event.detail); });
document.addEventListener("brain-clear", () => { closeShowcase(); showState.rendered = null; });
document.addEventListener("keydown", (event) => {
  if (!showState.open) return;
  if (event.key === "Escape") closeShowcase();
  if (event.key === "Tab") {
    const buttons = [...$("brain-show").querySelectorAll("button")].filter((button) => button.getClientRects().length);
    const index = buttons.indexOf(document.activeElement);
    if (event.shiftKey && index <= 0) { event.preventDefault(); buttons.at(-1)?.focus(); }
    else if (!event.shiftKey && (index === buttons.length - 1 || index < 0)) { event.preventDefault(); buttons[0]?.focus(); }
  }
});
document.addEventListener("visibilitychange", () => document.hidden ? stopPulses() : startPulses());
reducedMotion.addEventListener?.("change", () => (reducedMotion.matches ? stopPulses() : startPulses()));
document.addEventListener("DOMContentLoaded", () => {
  $("show-close").addEventListener("click", closeShowcase);
  $("brain-showcase").addEventListener("click", openShowcase);
  $("show-pause").addEventListener("click", () => {
    hologram.paused = !hologram.paused;
    $("show-pause").setAttribute("aria-pressed", String(hologram.paused));
    hologram.schedule();
    if (hologram.paused) stopPulses(); else startPulses();
  });
  $("show-fullscreen").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await $("brain-show").requestFullscreen();
    } catch { /* The viewport mode also works in browsers without the Fullscreen API. */ }
  });
  // /memory?demo=brain&show=1 opens straight into the showcase; signed-in pages do so from memory.js.
  if (DEMO && SHOWCASE) openShowcase();
});
