"use strict";
// memBrain memory page: the brain view. Draws the memory map (GET /v1/brains/{id}/memory-map) inside a brain
// silhouette: each region of memory is a fixed area of the brain, each memory a neuron, each link a faint axon.
// The placement is illustrative; node size is a layout weight, not a measure of memory strength.

const BRAIN_SVG = "http://www.w3.org/2000/svg";
// Region anchors in a side view of the brain facing left (viewBox 0 0 800 520), with their display order.
const REGIONS = [
  { id: "plans", label: "Plans", x: 205, y: 190 },
  { id: "commitments", label: "Commitments", x: 190, y: 300 },
  { id: "preferences", label: "Preferences", x: 310, y: 120 },
  { id: "constraints", label: "Health and constraints", x: 435, y: 95 },
  { id: "routines", label: "Routines", x: 560, y: 130 },
  { id: "episodes", label: "Recent messages", x: 445, y: 235 },
  { id: "people", label: "People", x: 335, y: 335 },
  { id: "relationship", label: "Relationship", x: 480, y: 330 },
  { id: "milestones", label: "Milestones and dates", x: 650, y: 225 },
  { id: "other", label: "Other notes", x: 610, y: 395 },
];
const BRAIN_OUTLINE = "M150 300 C110 250 115 165 175 120 C225 80 290 62 350 66 C395 40 470 38 520 60 " +
  "C585 62 650 92 690 150 C730 205 728 280 690 320 C668 345 640 352 612 350 C600 375 575 390 545 388 " +
  "C512 405 470 404 440 392 C400 410 350 410 315 392 C270 398 225 380 205 352 C178 345 160 326 150 300 Z";
const CEREBELLUM = "M560 360 C600 352 650 360 672 385 C690 410 668 440 630 446 C590 452 555 438 545 412 " +
  "C538 392 542 368 560 360 Z";
const STEM = "M520 390 C530 420 528 460 515 500 L485 500 C492 465 492 425 482 398 Z";
const FOLDS = [
  "M230 160 C270 150 300 175 340 160", "M200 240 C250 225 280 255 330 240", "M360 110 C400 125 430 105 470 120",
  "M470 165 C510 150 545 175 590 160", "M380 200 C420 185 450 215 500 195", "M560 220 C600 205 630 230 665 215",
  "M250 315 C290 300 320 330 370 315", "M420 300 C460 285 500 310 545 295", "M600 280 C630 270 650 290 680 280",
  "M440 60 C445 110 440 160 450 210",
];

const brainState = { map: null, selected: "", region: "", demo: false };

function svg(tag, attributes = {}) {
  const node = document.createElementNS(BRAIN_SVG, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
}

function regionOf(id) { return REGIONS.find((region) => region.id === id) || REGIONS[REGIONS.length - 1]; }

// Deterministic placement: a sunflower spiral around the region's anchor, oldest at the centre.
function layout(map) {
  const positions = {};
  const groups = {};
  for (const node of map.nodes) (groups[node.region] ||= []).push(node);
  for (const [region, nodes] of Object.entries(groups)) {
    const anchor = regionOf(region);
    nodes.sort((a, b) => String(a.recorded_at).localeCompare(String(b.recorded_at)) || a.id.localeCompare(b.id));
    nodes.forEach((node, index) => {
      const distance = 11 * Math.sqrt(index + 0.5);
      const angle = index * 2.39996;
      positions[node.id] = { x: anchor.x + distance * Math.cos(angle), y: anchor.y + distance * Math.sin(angle) * 0.8 };
    });
  }
  return positions;
}

function recentIds(map, count = 5) {
  return new Set([...map.nodes].sort((a, b) => String(b.recorded_at).localeCompare(String(a.recorded_at)))
    .slice(0, count).map((node) => node.id));
}

function nodeText(node) {
  return node.sensitive && !node.label ? "Sensitive note (hidden)" : (node.label || "(no text)");
}

function renderBrain(map) {
  brainState.map = map;
  const canvas = $("brain-canvas");
  canvas.replaceChildren();
  const root = svg("svg", { viewBox: "0 0 800 520", role: "img", "aria-labelledby": "brain-title" });
  const title = svg("title", { id: "brain-title" });
  title.textContent = "Your memory as a brain: each dot is one memory, grouped by kind";
  root.append(title);
  const shape = svg("g", { class: "brain-shape" });
  shape.append(svg("path", { d: BRAIN_OUTLINE, class: "brain-outline" }), svg("path", { d: CEREBELLUM, class: "brain-outline" }),
    svg("path", { d: STEM, class: "brain-outline brain-stem" }));
  for (const fold of FOLDS) shape.append(svg("path", { d: fold, class: "brain-fold" }));
  root.append(shape);

  const positions = layout(map);
  const edgeLayer = svg("g", { class: "brain-edges" });
  for (const edge of map.edges) {
    const from = positions[edge.source], to = positions[edge.target];
    if (!from || !to) continue;
    const middle = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 - 24 };
    const path = svg("path", { d: `M${from.x} ${from.y} Q${middle.x} ${middle.y} ${to.x} ${to.y}`,
      class: `brain-edge edge-${edge.type}`, "data-source": edge.source, "data-target": edge.target });
    const tip = svg("title");
    tip.textContent = `${edge.type.replaceAll("_", " ")} (${edge.basis.replaceAll("_", " ")})`;
    path.append(tip);
    edgeLayer.append(path);
  }
  root.append(edgeLayer);

  const recent = recentIds(map);
  const nodeLayer = svg("g", { class: "brain-nodes" });
  for (const node of map.nodes) {
    const at = positions[node.id];
    const radius = 5 + 4 * Math.max(0, Math.min(1, Number(node.weight) || 0));
    const dot = svg("circle", { cx: at.x, cy: at.y, r: radius, tabindex: "0", role: "button",
      class: `brain-node region-${node.region}${recent.has(node.id) ? " recent" : ""}${node.sensitive ? " sensitive" : ""}${node.traced ? " traced" : ""}`,
      "data-id": node.id, "aria-label": `${regionOf(node.region).label}: ${nodeText(node)}` });
    const tip = svg("title");
    tip.textContent = nodeText(node);
    dot.append(tip);
    dot.addEventListener("click", () => selectNode(node.id));
    dot.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectNode(node.id); } });
    dot.addEventListener("mouseenter", () => highlight(node.id));
    dot.addEventListener("mouseleave", () => highlight(brainState.selected));
    dot.addEventListener("focus", () => highlight(node.id));
    nodeLayer.append(dot);
  }
  root.append(nodeLayer);

  const labelLayer = svg("g", { class: "brain-labels", "aria-hidden": "true" });
  const counts = Object.fromEntries((map.regions || []).map((region) => [region.id, region.count]));
  for (const region of REGIONS) {
    if (!counts[region.id]) continue;
    const label = svg("text", { x: region.x, y: region.y - 22 - 2.2 * Math.sqrt(counts[region.id]), class: "brain-label" });
    label.textContent = region.label;
    labelLayer.append(label);
  }
  root.append(labelLayer);
  canvas.append(root);
  renderLegend(map);
  $("brain-summary").textContent = map.nodes.length
    ? `${map.nodes.length} memories and ${map.edges.length} links${map.truncated ? " (the most recent; more exist)" : ""}.`
    : "No memories yet. Talk with your agent, then come back.";
  $("brain-demo").hidden = !(map.demo || brainState.demo);
  renderTrace(map.trace);
  selectNode(brainState.selected && map.nodes.some((node) => node.id === brainState.selected) ? brainState.selected : "");
  document.dispatchEvent(new CustomEvent("brain-map", { detail: map }));
}

// The trace is the latest message recall the service recorded, not everything a reply used: notes and history added
// at the start of a session are not traced, and the page says so.
function renderTrace(trace) {
  const line = $("brain-trace");
  $("brain-trace-box").hidden = !trace;
  if (!trace) return;
  const at = trace.at ? new Date(trace.at) : null;
  const when = at ? `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, "0")}-${String(at.getDate()).padStart(2, "0")} `
    + `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}` : "";
  line.textContent = !at ? "No recall recorded since memory last started."
    : trace.used ? `Latest recorded recall (${when}): ${trace.shown} of ${trace.used} records it used are lit.`
      : `Latest recorded recall (${when}): it found nothing to add.`;
}

function renderLegend(map) {
  const legend = $("brain-legend");
  legend.replaceChildren();
  const counts = Object.fromEntries((map.regions || []).map((region) => [region.id, region.count]));
  for (const region of REGIONS) {
    const button = element("button", "", `legend-item region-${region.id}`);
    button.type = "button";
    button.setAttribute("aria-pressed", String(brainState.region === region.id));
    button.append(element("span", "", "legend-dot"), element("span", region.label), element("span", String(counts[region.id] || 0), "hint"));
    button.disabled = !counts[region.id];
    button.addEventListener("click", () => {
      brainState.region = brainState.region === region.id ? "" : region.id;
      renderLegend(map);
      highlight(brainState.selected);
    });
    legend.append(button);
  }
}

function neighbours(id) {
  const linked = new Set(id ? [id] : []);
  for (const edge of brainState.map?.edges || []) {
    if (edge.source === id) linked.add(edge.target);
    if (edge.target === id) linked.add(edge.source);
  }
  return linked;
}

function highlight(id) {
  const root = $("brain-canvas");
  const linked = neighbours(id);
  const region = brainState.region;
  root.classList.toggle("focused", Boolean(id || region));
  for (const dot of root.querySelectorAll(".brain-node")) {
    const node = brainState.map.nodes.find((item) => item.id === dot.dataset.id);
    dot.classList.toggle("lit", linked.has(dot.dataset.id) || (Boolean(region) && node?.region === region));
  }
  for (const path of root.querySelectorAll(".brain-edge")) {
    path.classList.toggle("lit", Boolean(id) && (path.dataset.source === id || path.dataset.target === id));
  }
}

function selectNode(id) {
  brainState.selected = id;
  highlight(id);
  const detail = $("brain-detail");
  const node = brainState.map?.nodes.find((item) => item.id === id);
  detail.hidden = !node;
  if (!node) return;
  detail.replaceChildren();
  detail.append(element("h2", regionOf(node.region).label));
  const text = element("p", nodeText(node), node.sensitive ? "muted" : "user-text");
  detail.append(text);
  const facts = [];
  if (node.status) facts.push(`Status: ${node.status}`);
  if (node.date) facts.push(`Date: ${node.date}`);
  if (node.recorded_at) facts.push(`Saved: ${String(node.recorded_at).slice(0, 10)}`);
  if (facts.length) detail.append(element("p", facts.join(" · "), "hint"));
  if (node.traced) detail.append(element("p", "Used by the latest recorded recall", "hint"));
  if (node.id.startsWith("note:") && !brainState.demo) detail.append(noteActions(node, detail));
  const links = (brainState.map.edges || []).filter((edge) => edge.source === id || edge.target === id);
  if (links.length) {
    const list = element("ul", "", "brain-links");
    for (const edge of links) {
      const other = brainState.map.nodes.find((item) => item.id === (edge.source === id ? edge.target : edge.source));
      const row = element("li", "");
      const open = element("button", other ? nodeText(other) : "(not shown)", "link");
      open.type = "button";
      if (other) open.addEventListener("click", () => selectNode(other.id)); else open.disabled = true;
      row.append(element("span", `${edge.type.replaceAll("_", " ")}: `, "hint"), open);
      list.append(row);
    }
    detail.append(list);
  }
}

// The same edit and delete as the Notes tab; the map redraws afterwards.
function noteActions(node, detail) {
  const id = node.id.slice(5);
  const row = element("div", undefined, "row brain-note-actions");
  const edit = element("button", "Edit", "link"), remove = element("button", "Delete", "link danger");
  edit.type = "button"; remove.type = "button";
  row.append(edit, remove);
  guard(edit, async () => {
    const { items } = await timeline({ role: ["assistant", "user"], conversation_id: NOTES, event_id: [id] });
    const note = items.find((item) => item.event_id === id);
    if (!note) throw new Error("This note is no longer available.");
    detail.replaceChildren(noteEditor(note, [], () => loadBrain()));
    detail.querySelector("textarea").focus();
  });
  guard(remove, async () => {
    if (!confirm("Delete this note? Its content is erased.")) return;
    await forget("events", [id], "erase_content", NOTES);
    notify("Note deleted.");
    brainState.selected = "";
    await loadBrain();
  });
  return row;
}

async function loadBrain() {
  const map = brainState.demo
    ? await (await fetch("/static/memory-map-demo.json")).json()
    : await api(`/v1/brains/${encodeURIComponent(state.brain)}/memory-map?max_nodes=200&max_edges=400&trace=true`);
  renderBrain(map);
}
window.loadBrain = loadBrain;

// /memory?demo=brain shows the fictional demo map without signing in.
document.addEventListener("DOMContentLoaded", () => {
  if (new URLSearchParams(location.search).get("demo") !== "brain") return;
  brainState.demo = true;
  $("signin").hidden = true;
  $("view-brain").hidden = false;
  loadBrain().catch((error) => notify(error.message, true));
});
