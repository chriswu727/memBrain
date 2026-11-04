"use strict";
// memBrain memory page: the 3D observatory. It draws the same memory map brain.js loaded (no request of its own) in
// three dimensions, with three.js vendored under /static/vendor/three/ (loaded only when the 3D view is first shown).
//
// What it shows is exactly the payload: one shape per node, one line per edge of its recorded type, the regions as
// fixed volumes inside an illustrative shell. Positions come from a hash of each node's region and ID, so the same
// map always gives the same layout and adding or removing one record never moves another. There is no force
// simulation, no animation loop and no travelling signal: a frame is drawn only after an interaction, a data change
// or a resize, never while idle, hidden or switched away. Selection goes through brain.js (the same detail panel,
// edit and delete), so the 3D view and the 2D map always agree.

const OBS_THREE = "/static/vendor/three/three.module.js";
// Region volumes: centre (x right, y up, z towards the viewer) and the radii of an ellipsoid, in world units.
// Centres follow the 2D map's anchors; depths spread the areas through the shell. Areas are kinds of record,
// not parts of a real brain.
const OBS_SPACE = {
  plans: { at: [-2.26, 0.58, 0.5], size: [0.42, 0.36, 0.48] },
  commitments: { at: [-2.42, -0.58, -0.5], size: [0.42, 0.36, 0.48] },
  preferences: { at: [-1.16, 1.32, -0.6], size: [0.42, 0.34, 0.48] },
  constraints: { at: [0.16, 1.58, 0.6], size: [0.42, 0.34, 0.48] },
  routines: { at: [1.47, 1.21, -0.5], size: [0.42, 0.34, 0.48] },
  episodes: { at: [0.26, 0.1, 0], size: [0.72, 0.5, 1.0] },
  people: { at: [-0.89, -0.95, 0.7], size: [0.42, 0.34, 0.48] },
  relationship: { at: [0.63, -0.89, -0.7], size: [0.42, 0.34, 0.48] },
  milestones: { at: [2.42, 0.21, 0.5], size: [0.42, 0.36, 0.48] },
  other: { at: [2.0, -1.4, -0.4], size: [0.42, 0.34, 0.48] },
  emotions: { at: [-1.05, 0.1, -0.9], size: [0.36, 0.3, 0.4] },
  persona: { at: [-1.0, 0.8, 0.8], size: [0.48, 0.34, 0.4] },
  mood: { at: [0.2, -0.5, 0.9], size: [0.48, 0.34, 0.4] },
};
// Recorded dependency types from the memory and companion maps; unknown types are drawn plain grey.
const OBS_EDGES = {
  derived_from: { color: "--accent", dash: null, opacity: 0.55 },
  about_person: { color: "--r-people", dash: [0.14, 0.08], opacity: 0.85 },
  feeling_of: { color: "--r-emotions", dash: [0.035, 0.05], opacity: 0.95 },
  based_on_feedback: { color: "--r-persona", dash: null, opacity: 0.7 },
  proposed_from_feedback: { color: "--r-persona", dash: [0.14, 0.08], opacity: 0.7 },
  accepted_proposal: { color: "--r-persona", dash: null, opacity: 0.95 },
  restored_from: { color: "--r-persona", dash: [0.08, 0.04], opacity: 0.7 },
  baseline_from: { color: "--r-mood", dash: [0.14, 0.08], opacity: 0.7 },
  triggered_by: { color: "--r-mood", dash: null, opacity: 0.8 },
  affected_by: { color: "--r-mood", dash: [0.035, 0.05], opacity: 0.95 },
};
const OBS_HOME = { theta: 0.35, phi: 1.32, radius: 7.6, target: [0, 0, 0] };
const OBS_MESSAGES = {
  loading: "Loading the 3D view…",
  unsupported: "The 3D view needs WebGL 2, which this browser does not provide or has turned off. Showing the 2D map and the list instead.",
  failed: "The 3D view could not start. Showing the 2D map and the list instead.",
  lost: "The 3D view lost its graphics context. Showing the 2D map until the browser restores it.",
};

const obs = {
  three: null, renderer: null, scene: null, camera: null, light: null, built: null, map: null,
  mode: "3d", fallback: "", loading: null, pending: 0, dirty: false, generation: 0,
  view: { ...OBS_HOME, target: [...OBS_HOME.target] }, animation: null, drag: null, pointers: new Map(),
  focused: "", hovered: "", lastInput: 0, pendingPick: null, firstFrame: false,
  renders: 0, builds: 0, disposals: 0, measure: false, frameTimes: [], pickTimes: [],
};

// Layout -----------------------------------------------------------------------------------------------------------

function obsHash(text) {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function obsRandom(seed) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let value = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

// A point in the node's region volume chosen only by its region and ID: stable across loads and unaffected by others.
function obsPosition(node) {
  const space = OBS_SPACE[node.region] || OBS_SPACE.other;
  const random = obsRandom(obsHash(`${node.region}|${node.id}`));
  let x, y, z;
  do { x = random() * 2 - 1; y = random() * 2 - 1; z = random() * 2 - 1; } while (x * x + y * y + z * z > 1);
  return [space.at[0] + x * space.size[0], space.at[1] + y * space.size[1], space.at[2] + z * space.size[2]];
}

function obsLayout(map) {
  return Object.fromEntries(map.nodes.map((node) => [node.id, obsPosition(node)]));
}

// Size is the payload's layout weight (0 to 1), nothing else.
const obsRadius = (node) => 0.06 + 0.06 * (Number.isFinite(node.weight) ? Math.max(0, Math.min(1, node.weight)) : 0.5);
const obsShape = (node) => (node.kind === "message" ? "message" : node.kind === "affect" ? "affect" : "note");

// Theme ------------------------------------------------------------------------------------------------------------

function obsColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

// Renderer lifecycle -----------------------------------------------------------------------------------------------

async function obsEnsureRenderer() {
  if (obs.renderer) return true;
  if (!obs.three) {
    obs.loading ||= import(OBS_THREE).catch(() => { obs.loading = null; });
    obs.three = (await obs.loading) || null;
    if (!obs.three) { obsFallback("failed"); return false; }
  }
  if (obs.renderer) return true;
  const THREE = obs.three;
  const canvas = $("observatory-canvas");
  // Ask for WebGL 2 ourselves, so a browser without it gets the 2D map and a message rather than a console error.
  const context = canvas.getContext("webgl2", { alpha: true, antialias: true, depth: true, stencil: false,
    premultipliedAlpha: true, preserveDrawingBuffer: false, powerPreference: "low-power" });
  if (!context) {
    obsFallback("unsupported");
    return false;
  }
  try {
    obs.renderer = new THREE.WebGLRenderer({ canvas, context, antialias: true, alpha: true });
  } catch {
    obsFallback("unsupported");
    return false;
  }
  obs.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  obs.renderer.setClearColor(0x000000, 0);
  obs.camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  obs.light = new THREE.DirectionalLight(0xffffff, 1.6);
  obs.camera.add(obs.light);
  obs.light.position.set(0.4, 0.8, 0.2);
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    cancelAnimationFrame(obs.pending);
    obs.pending = 0;
    obsFallback("lost");
  });
  canvas.addEventListener("webglcontextrestored", () => {
    if (obs.fallback !== "lost") return;
    obs.fallback = "";
    obsDispose();  // Buffers from the lost context are gone; build them again from the current map.
    obsSync();
  });
  obsResize();
  new ResizeObserver(() => { if (obsResize()) obsRequestRender(); }).observe(canvas);
  return true;
}

function obsResize() {
  const canvas = $("observatory-canvas");
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!obs.renderer || !width || !height) return false;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  if (obs.renderer.getPixelRatio() !== ratio) obs.renderer.setPixelRatio(ratio);
  obs.renderer.setSize(width, height, false);
  obs.camera.aspect = width / height;
  obs.camera.updateProjectionMatrix();
  return true;
}

function obsFallback(reason) {
  obs.fallback = reason;
  obsDispose();
  obsShowMode();
}

// Free every geometry and material of the current map; the renderer and its context stay for the next build.
function obsDispose() {
  if (!obs.scene) return;
  obs.scene.traverse((object) => {
    if (object.isInstancedMesh) object.dispose();
    object.geometry?.dispose();
    for (const material of [].concat(object.material || [])) material.dispose();
  });
  obs.scene.remove(obs.camera);
  obs.scene = null;
  obs.built = null;
  obs.disposals += 1;
  obs.renderer?.renderLists.dispose();
  $("observatory-labels").replaceChildren();
}

// Building the scene -----------------------------------------------------------------------------------------------

function obsBuild(map) {
  obsDispose();
  const THREE = obs.three;
  const scene = new THREE.Scene();
  scene.add(new THREE.AmbientLight(0xffffff, 1.1), obs.camera);
  const positions = obsLayout(map);
  const index = new Map();
  const groups = { note: [], message: [], affect: [] };
  for (const node of map.nodes) groups[obsShape(node)].push(node);
  const geometries = { note: new THREE.IcosahedronGeometry(1, 1), message: new THREE.OctahedronGeometry(1.15, 0),
    affect: new THREE.TetrahedronGeometry(1.3, 0) };
  const matrix = new THREE.Matrix4(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3(),
    point = new THREE.Vector3();
  const meshes = {};
  for (const [shape, nodes] of Object.entries(groups)) {
    if (!nodes.length) { geometries[shape].dispose(); continue; }
    const mesh = new THREE.InstancedMesh(geometries[shape], new THREE.MeshLambertMaterial({ color: 0xffffff }), nodes.length);
    mesh.name = `nodes-${shape}`;
    mesh.userData.ids = nodes.map((node) => node.id);
    nodes.forEach((node, slot) => {
      const radius = obsRadius(node);
      matrix.compose(point.set(...positions[node.id]), quaternion, scale.setScalar(radius));
      mesh.setMatrixAt(slot, matrix);
      index.set(node.id, { node, shape, slot, position: positions[node.id], radius });
    });
    mesh.computeBoundingSphere();
    meshes[shape] = mesh;
    scene.add(mesh);
  }
  // One line object per edge type, only between nodes the map draws.
  const byType = {};
  for (const edge of map.edges) {
    if (index.has(edge.source) && index.has(edge.target)) (byType[edge.type] ||= []).push(edge);
  }
  const lines = {};
  for (const [type, edges] of Object.entries(byType)) {
    const style = OBS_EDGES[type] || { color: "--muted", dash: null, opacity: 0.5 };
    const coordinates = new Float32Array(edges.length * 6);
    edges.forEach((edge, slot) => {
      coordinates.set(index.get(edge.source).position, slot * 6);
      coordinates.set(index.get(edge.target).position, slot * 6 + 3);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(coordinates, 3));
    const color = obsColor(style.color, "#6b7c93");
    const material = style.dash
      ? new THREE.LineDashedMaterial({ color, dashSize: style.dash[0], gapSize: style.dash[1], transparent: true, opacity: style.opacity })
      : new THREE.LineBasicMaterial({ color, transparent: true, opacity: style.opacity });
    const line = new THREE.LineSegments(geometry, material);
    if (style.dash) line.computeLineDistances();
    line.name = `edges-${type}`;
    line.userData.edges = edges.map((edge) => `${edge.type}:${edge.source}>${edge.target}`);
    lines[type] = line;
    scene.add(line);
  }
  // Recalled records: a gold ring around each node the latest recorded recall returned.
  const traced = map.nodes.filter((node) => node.traced && index.has(node.id));
  let halos = null;
  if (traced.length) {
    halos = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1),
      new THREE.MeshBasicMaterial({ color: obsColor("--trace", "#e0a100"), wireframe: true }), traced.length);
    halos.name = "recalled";
    halos.userData.ids = traced.map((node) => node.id);
    traced.forEach((node, slot) => {
      const entry = index.get(node.id);
      matrix.compose(point.set(...entry.position), quaternion, scale.setScalar(entry.radius * 1.9));
      halos.setMatrixAt(slot, matrix);
    });
    halos.computeBoundingSphere();
    scene.add(halos);
  }
  const marker = (color) => {
    const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshBasicMaterial({ color, wireframe: true }));
    mesh.visible = false;
    scene.add(mesh);
    return mesh;
  };
  const selection = marker(obsColor("--ink", "#1d2733"));
  selection.name = "selection";
  const focus = marker(obsColor("--accent", "#2f6fb0"));
  focus.name = "focus";
  scene.add(obsShell(THREE));
  obs.scene = scene;
  obs.built = { map, index, meshes, lines, halos, selection, focus, lit: null, generation: ++obs.generation };
  obs.builds += 1;
  obs.firstFrame = true;
  obsLabels(map);
  obsHighlight();
}

// The shell: a lobed ellipsoid of faint lines. Illustration only; it holds no data and is never picked.
function obsShell(THREE) {
  const coordinates = [];
  const surface = (u, v) => {
    const lobes = 1 + 0.05 * Math.sin(5 * u) * Math.sin(3 * v) - 0.08 * Math.exp(-((v - Math.PI / 2) ** 2) * 6) * Math.cos(u) ** 8;
    return [3.45 * Math.sin(v) * Math.cos(u) * lobes + 0.1, 2.35 * Math.cos(v) * lobes - 0.05, 2.05 * Math.sin(v) * Math.sin(u) * lobes];
  };
  const push = (a, b) => coordinates.push(...a, ...b);
  for (let ring = 1; ring < 10; ring += 1) {
    const v = (ring / 10) * Math.PI;
    for (let step = 0; step < 72; step += 1) push(surface((step / 72) * 2 * Math.PI, v), surface(((step + 1) / 72) * 2 * Math.PI, v));
  }
  for (let meridian = 0; meridian < 14; meridian += 1) {
    const u = (meridian / 14) * 2 * Math.PI;
    for (let step = 0; step < 36; step += 1) push(surface(u, (step / 36) * Math.PI), surface(u, ((step + 1) / 36) * Math.PI));
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(coordinates, 3));
  const shell = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: obsColor("--muted", "#8b9a94"), transparent: true, opacity: 0.16, depthWrite: false }));
  shell.name = "shell";
  return shell;
}

function obsLabels(map) {
  const layer = $("observatory-labels");
  const counts = Object.fromEntries((map.regions || []).map((region) => [region.id, region.count]));
  layer.replaceChildren(...REGIONS.filter((region) => counts[region.id]).map((region) => {
    const label = element("span", region.label, "observatory-label");
    label.dataset.region = region.id;
    return label;
  }));
}

// Selection, focus and region highlight, all from brain.js's state -------------------------------------------------

function obsHighlight() {
  const selected = brainState.selected, region = brainState.region;
  for (const button of $("observatory-list").querySelectorAll("button")) {
    if (button.dataset.id === selected) button.setAttribute("aria-current", "true"); else button.removeAttribute("aria-current");
  }
  const built = obs.built;
  if (!built) return;
  const THREE = obs.three;
  const linked = neighbours(selected);
  const focused = Boolean(selected || region);
  const color = new THREE.Color(), dim = new THREE.Color(obsColor("--card", "#ffffff"));
  const sensitive = new THREE.Color("#9aa29f");
  for (const mesh of Object.values(built.meshes)) {
    mesh.userData.ids.forEach((id, slot) => {
      const node = built.index.get(id).node;
      if (node.sensitive) color.copy(sensitive); else color.set(obsColor(`--r-${node.region}`, "#8b9a94"));
      if (focused && !linked.has(id) && !(region && node.region === region)) color.lerp(dim, 0.72);
      mesh.setColorAt(slot, color);
    });
    mesh.instanceColor.needsUpdate = true;
  }
  if (built.lit) {
    built.lit.geometry.dispose();
    built.lit.material.dispose();
    obs.scene.remove(built.lit);
    built.lit = null;
  }
  const edges = selected ? built.map.edges.filter((edge) => (edge.source === selected || edge.target === selected)
    && built.index.has(edge.source) && built.index.has(edge.target)) : [];
  if (edges.length) {
    const coordinates = new Float32Array(edges.length * 6);
    edges.forEach((edge, slot) => {
      coordinates.set(built.index.get(edge.source).position, slot * 6);
      coordinates.set(built.index.get(edge.target).position, slot * 6 + 3);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(coordinates, 3));
    built.lit = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: obsColor("--ink", "#1d2733") }));
    built.lit.name = "selected-edges";
    obs.scene.add(built.lit);
  }
  obsMark(built.selection, selected);
  obsMark(built.focus, obs.focused !== selected ? obs.focused : "");
  obsRequestRender();
}

function obsMark(mesh, id) {
  const entry = id && obs.built.index.get(id);
  mesh.visible = Boolean(entry);
  if (!entry) return;
  mesh.position.set(...entry.position);
  mesh.scale.setScalar(entry.radius * 2.1);
}

// Camera -----------------------------------------------------------------------------------------------------------

function obsApplyCamera() {
  const { theta, phi, radius, target } = obs.view;
  obs.camera.position.set(target[0] + radius * Math.sin(phi) * Math.sin(theta), target[1] + radius * Math.cos(phi),
    target[2] + radius * Math.sin(phi) * Math.cos(theta));
  obs.camera.lookAt(...target);
  obs.camera.updateMatrixWorld();
}

const obsReducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// Moves the camera to a new view: a short glide, or at once when the person prefers reduced motion.
function obsMoveCamera(view) {
  const goal = { ...obs.view, ...view };
  if (obsReducedMotion()) {
    obs.animation = null;
    obs.view = goal;
  } else {
    obs.animation = { from: { ...obs.view, target: [...obs.view.target] }, to: goal, start: performance.now(), duration: 450 };
  }
  obsRequestRender();
}

function obsStepAnimation(now) {
  const { from, to, start, duration } = obs.animation;
  const t = Math.min(1, (now - start) / duration);
  const ease = t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2;
  const mix = (a, b) => a + (b - a) * ease;
  obs.view = { theta: mix(from.theta, to.theta), phi: mix(from.phi, to.phi), radius: mix(from.radius, to.radius),
    target: from.target.map((value, axis) => mix(value, to.target[axis])) };
  if (t >= 1) obs.animation = null;
  return t < 1;
}

function obsRotate(dTheta, dPhi) {
  obs.animation = null;
  obs.view.theta += dTheta;
  obs.view.phi = Math.max(0.12, Math.min(Math.PI - 0.12, obs.view.phi + dPhi));
  obsRequestRender();
}

function obsZoom(factor) {
  obs.animation = null;
  obs.view.radius = Math.max(3.2, Math.min(22, obs.view.radius * factor));
  obsRequestRender();
}

// Drawing on demand ------------------------------------------------------------------------------------------------

const obsActive = () => Boolean(obs.scene) && !obs.fallback && obs.mode === "3d" && !$("view-brain").hidden;

function obsRequestRender() {
  if (!obsActive()) return;
  if (document.visibilityState === "hidden") { obs.dirty = true; return; }
  if (!obs.pending) obs.pending = requestAnimationFrame(obsFrame);
}

function obsFrame(now) {
  obs.pending = 0;
  if (!obsActive()) return;
  if (document.visibilityState === "hidden") { obs.dirty = true; return; }
  obs.dirty = false;
  const start = performance.now();
  const moving = obs.animation ? obsStepAnimation(now) : false;
  obsApplyCamera();
  obs.renderer.render(obs.scene, obs.camera);
  if (obs.measure) {  // Measurement only: wait for the GPU so the frame time includes the drawing itself.
    const gl = obs.renderer.getContext();
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
  }
  obsPlaceLabels();
  obs.renders += 1;
  const end = performance.now();
  if (obs.frameTimes.length >= 2000) obs.frameTimes.shift();
  obs.frameTimes.push({ input: obs.lastInput, start, end });
  obs.lastInput = 0;
  if (obs.pendingPick) { obs.pendingPick.frame = end; obs.pickTimes.push(obs.pendingPick); obs.pendingPick = null; }
  if (obs.firstFrame) {
    obs.firstFrame = false;
    performance.mark("membrain-observatory-frame", { detail: { generation: obs.built.generation } });
  }
  if (moving) obsRequestRender();
}

// Area names follow their volumes; a name that would cover a nearer one moves down a line, so none overlap.
function obsPlaceLabels() {
  const canvas = $("observatory-canvas");
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const point = new obs.three.Vector3();
  const placed = [];
  const labels = [...$("observatory-labels").children].map((label) => {
    const space = OBS_SPACE[label.dataset.region];
    point.set(space.at[0], space.at[1] + space.size[1] + 0.12, space.at[2]).project(obs.camera);
    label.size ||= [label.offsetWidth, label.offsetHeight];
    return { label, x: ((point.x + 1) / 2) * width, y: ((1 - point.y) / 2) * height, depth: point.z,
      visible: point.z > -1 && point.z < 1 && Math.abs(point.x) < 0.92 && Math.abs(point.y) < 0.95 };
  }).sort((a, b) => a.depth - b.depth);
  for (const item of labels) {
    item.label.hidden = !item.visible;
    if (!item.visible) continue;
    const [w, h] = item.label.size;
    let top = item.y - h;
    for (let tries = 0; tries < 4; tries += 1) {
      const clash = placed.find((box) => Math.abs(box.x - item.x) * 2 < box.w + w && top < box.top + box.h && top + h > box.top);
      if (!clash) break;
      top = clash.top + clash.h + 1;
    }
    placed.push({ x: item.x, top, w, h });
    item.label.style.transform = `translate(${item.x - w / 2}px, ${top}px)`;
  }
}

// Picking: project every node and take the nearest one under the pointer. Exact, and cheap at 500 nodes.

function obsScreen(position, rect = $("observatory-canvas").getBoundingClientRect()) {
  const point = new obs.three.Vector3(...position).project(obs.camera);
  return { x: rect.left + ((point.x + 1) / 2) * rect.width, y: rect.top + ((1 - point.y) / 2) * rect.height,
    depth: point.z, inside: point.z > -1 && point.z < 1 && Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1 };
}

function obsPick(clientX, clientY) {
  if (!obs.built) return "";
  obsApplyCamera();
  const rect = $("observatory-canvas").getBoundingClientRect();
  const focal = rect.height / 2 / Math.tan((obs.camera.fov * Math.PI) / 360);
  let best = null, near = null;
  for (const [id, entry] of obs.built.index) {
    const screen = obsScreen(entry.position, rect);
    if (!screen.inside) continue;
    const distance = Math.hypot(screen.x - clientX, screen.y - clientY);
    const size = (entry.radius * focal) / obs.camera.position.distanceTo(obs.tmpVector(entry.position));
    if (distance <= size && (!best || screen.depth < best.depth)) best = { id, depth: screen.depth };
    else if (distance <= Math.max(size, 7) && (!near || distance < near.distance)) near = { id, distance };
  }
  return best?.id || near?.id || "";
}
obs.tmpVector = (position) => (obs.vector ||= new obs.three.Vector3()).set(...position);

// Input ------------------------------------------------------------------------------------------------------------

function obsBindInput() {
  const canvas = $("observatory-canvas");
  const tip = $("observatory-tip");
  canvas.addEventListener("pointerdown", (event) => {
    if (!obs.built) return;
    canvas.setPointerCapture(event.pointerId);
    obs.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    obs.drag = { x: event.clientX, y: event.clientY, moved: 0, pinch: obs.pointers.size === 2 ? obsPinch() : 0 };
    tip.hidden = true;
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!obs.built) return;
    if (obs.drag && obs.pointers.has(event.pointerId)) {
      obs.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      obs.lastInput ||= event.timeStamp;
      if (obs.pointers.size === 2) {
        const distance = obsPinch();
        if (obs.drag.pinch && distance) obsZoom(obs.drag.pinch / distance);
        obs.drag.pinch = distance;
        obs.drag.moved += 10;
        return;
      }
      const dx = event.clientX - obs.drag.x, dy = event.clientY - obs.drag.y;
      obs.drag.x = event.clientX; obs.drag.y = event.clientY;
      obs.drag.moved += Math.abs(dx) + Math.abs(dy);
      obsRotate(-dx * 0.008, -dy * 0.008);
      return;
    }
    if (event.pointerType !== "mouse") return;
    const id = obsPick(event.clientX, event.clientY);
    canvas.classList.toggle("over-node", Boolean(id));
    if (id !== obs.hovered) {
      obs.hovered = id;
      const node = id && obs.built.index.get(id).node;
      tip.hidden = !node;
      if (node) tip.textContent = `${regionOf(node.region).label}: ${nodeText(node)}`;
    }
    if (obs.hovered) {
      const rect = canvas.getBoundingClientRect();
      tip.style.transform = `translate(${event.clientX - rect.left + 12}px, ${event.clientY - rect.top + 12}px)`;
    }
  });
  const release = (event) => {
    if (!obs.pointers.delete(event.pointerId)) return;
    const drag = obs.drag;
    if (obs.pointers.size === 0) obs.drag = null;
    if (event.type === "pointerup" && drag && drag.moved < 6 && obs.pointers.size === 0) {
      const id = obsPick(event.clientX, event.clientY);
      if (id) {
        const input = event.timeStamp;
        selectNode(id);
        obs.pendingPick = { id, input, detail: performance.now(), frame: 0 };
      }
    }
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("pointerleave", () => { $("observatory-tip").hidden = true; obs.hovered = ""; });
  canvas.addEventListener("wheel", (event) => {
    if (!obs.built) return;
    event.preventDefault();
    obs.lastInput ||= event.timeStamp;
    obsZoom(Math.exp(Math.max(-1, Math.min(1, event.deltaY * 0.0015))));
  }, { passive: false });
  canvas.addEventListener("keydown", (event) => {
    if (!obs.built) return;
    const keys = { ArrowLeft: () => obsRotate(-0.12, 0), ArrowRight: () => obsRotate(0.12, 0),
      ArrowUp: () => obsRotate(0, -0.1), ArrowDown: () => obsRotate(0, 0.1), "+": () => obsZoom(0.88),
      "=": () => obsZoom(0.88), "-": () => obsZoom(1 / 0.88), Home: () => obsMoveCamera({ ...OBS_HOME, target: [...OBS_HOME.target] }) };
    if (!keys[event.key]) return;
    event.preventDefault();
    obs.lastInput ||= event.timeStamp;
    keys[event.key]();
  });
}

function obsPinch() {
  const [a, b] = [...obs.pointers.values()];
  return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0;
}

// The keyboard list of every memory in the map ---------------------------------------------------------------------

function obsRenderList(map) {
  const list = $("observatory-list");
  const order = Object.fromEntries(REGIONS.map((region, position) => [region.id, position]));
  const nodes = [...map.nodes].sort((a, b) => (order[a.region] ?? 99) - (order[b.region] ?? 99));
  const keep = list.contains(document.activeElement) ? document.activeElement.dataset.id : "";
  list.replaceChildren(...nodes.map((node) => {
    const item = element("li");
    const button = element("button", undefined, `observatory-item region-${node.region}${node.traced ? " traced" : ""}`);
    button.type = "button";
    button.dataset.id = node.id;
    button.tabIndex = -1;
    button.append(element("span", "", "legend-dot"), element("span", regionOf(node.region).label, "observatory-item-region"),
      element("span", nodeText(node), node.sensitive ? "muted" : "user-text"));
    if (node.traced) button.append(element("span", "Latest recorded recall", "observatory-recalled"));
    item.append(button);
    return item;
  }));
  const buttons = [...list.querySelectorAll("button")];
  const current = buttons.find((button) => button.dataset.id === (keep || brainState.selected)) || buttons[0];
  if (current) current.tabIndex = 0;
  if (keep && current?.dataset.id === keep) current.focus();
  if (!buttons.some((button) => button.dataset.id === obs.focused)) obs.focused = "";
  $("observatory-list-empty").hidden = buttons.length > 0;
}

function obsBindList() {
  const list = $("observatory-list");
  list.addEventListener("keydown", (event) => {
    const buttons = [...list.querySelectorAll("button")];
    const at = buttons.indexOf(document.activeElement);
    if (at < 0) return;
    const next = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: buttons.length - 1, PageDown: at + 10, PageUp: at - 10 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const target = buttons[Math.max(0, Math.min(buttons.length - 1, next))];
    buttons[at].tabIndex = -1;
    target.tabIndex = 0;
    target.focus();
  });
  list.addEventListener("focusin", (event) => {
    const id = event.target.closest("button")?.dataset.id;
    if (!id) return;
    obs.focused = id;
    if (obs.built) { obsMark(obs.built.focus, id !== brainState.selected ? id : ""); obsRequestRender(); }
  });
  list.addEventListener("focusout", () => {
    if (list.contains(document.activeElement)) return;
    obs.focused = "";
    if (obs.built) { obsMark(obs.built.focus, ""); obsRequestRender(); }
  });
  list.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    for (const other of list.querySelectorAll("button")) other.tabIndex = other === button ? 0 : -1;
    selectNode(button.dataset.id);
    const entry = obs.built?.index.get(button.dataset.id);
    if (entry && obsActive()) obsMoveCamera({ target: [...entry.position] });
  });
}

// Modes and wiring -------------------------------------------------------------------------------------------------

function obsShowMode() {
  const three = obs.mode === "3d" && !obs.fallback;
  $("observatory").hidden = !three;
  $("brain-canvas").hidden = three;
  $("observatory-reset").hidden = !three;
  $("mode-3d").setAttribute("aria-pressed", String(obs.mode === "3d"));
  $("mode-2d").setAttribute("aria-pressed", String(obs.mode !== "3d"));
  $("mode-3d").disabled = obs.fallback === "unsupported" || obs.fallback === "failed";
  const status = $("observatory-status");
  const message = obs.fallback ? OBS_MESSAGES[obs.fallback] : three && !obs.scene && obs.map ? OBS_MESSAGES.loading : "";
  status.hidden = !message;
  if (status.textContent !== message) status.textContent = message;
}

async function obsSync() {
  const shown = obs.mode === "3d" && !obs.fallback && !$("view-brain").hidden;
  const wanted = shown && Boolean(obs.map);
  // Start fetching three.js as soon as the 3D view is shown, while the map itself is still loading.
  if (shown && !obs.three && !obs.loading) obs.loading = import(OBS_THREE).catch(() => { obs.loading = null; });
  obsShowMode();
  if (!wanted) { cancelAnimationFrame(obs.pending); obs.pending = 0; obsDispose(); return; }
  if (!(await obsEnsureRenderer())) return;
  if (obs.mode !== "3d" || obs.fallback || !obs.map || $("view-brain").hidden) return obsSync();
  if (obs.built?.map !== obs.map) obsBuild(obs.map);
  obsShowMode();
  obsResize();
  obsRequestRender();
}

function obsSetMode(mode) {
  obs.mode = mode === "2d" ? "2d" : "3d";
  try { localStorage.setItem("membrain-brain-mode", obs.mode); } catch { /* storage may be unavailable */ }
  obsSync();
}

function obsEdgeCounts(map) {
  const counts = {};
  for (const edge of map.edges) counts[edge.type] = (counts[edge.type] || 0) + 1;
  for (const row of $("observatory-edges").querySelectorAll("[data-edge]")) {
    row.querySelector(".edge-count").textContent = String(counts[row.dataset.edge] || 0);
    row.hidden = !counts[row.dataset.edge];
  }
  const traced = map.nodes.filter((node) => node.traced).length;
  $("observatory-recalled-count").textContent = String(traced);
}

document.addEventListener("DOMContentLoaded", () => {
  try { obs.mode = localStorage.getItem("membrain-brain-mode") === "2d" ? "2d" : "3d"; } catch { /* default */ }
  obsBindInput();
  obsBindList();
  $("mode-3d").addEventListener("click", () => obsSetMode("3d"));
  $("mode-2d").addEventListener("click", () => obsSetMode("2d"));
  $("observatory-reset").addEventListener("click", () => obsMoveCamera({ ...OBS_HOME, target: [...OBS_HOME.target] }));
  document.addEventListener("brain-map", (event) => {
    obs.map = event.detail;
    obsRenderList(obs.map);
    obsEdgeCounts(obs.map);
    obsSync();
  });
  document.addEventListener("brain-highlight", () => obsHighlight());
  document.addEventListener("brain-clear", () => {
    obs.map = null;
    obsRenderList({ nodes: [] });
    obsEdgeCounts({ nodes: [], edges: [] });
    obsSync();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") { cancelAnimationFrame(obs.pending); obs.pending = 0; obs.dirty = true; }
    else if (obs.dirty) obsRequestRender();
  });
  new MutationObserver(() => obsSync()).observe($("view-brain"), { attributes: true, attributeFilter: ["hidden"] });
  obsShowMode();
});

// Read-only inspection for tests and the measurement harness (scripts/measure_observatory.py). It never changes memory.
window.observatory = {
  snapshot() {
    const nodes = [], edges = [], recalled = [];
    obs.scene?.traverse((object) => {
      if (object.name.startsWith("nodes-")) nodes.push(...object.userData.ids);
      if (object.name.startsWith("edges-")) {
        edges.push(...object.userData.edges);
        if (object.geometry.attributes.position.count !== object.userData.edges.length * 2) edges.push("mismatch");
      }
      if (object.name === "recalled") recalled.push(...object.userData.ids);
    });
    const memory = obs.renderer ? { ...obs.renderer.info.memory } : null;
    return { mode: obs.mode, fallback: obs.fallback, active: obsActive(), generation: obs.built?.generation || 0,
      nodes, edges, recalled, selected: brainState.selected, focused: obs.focused, gpu: memory,
      renders: obs.renders, builds: obs.builds, disposals: obs.disposals, pending: Boolean(obs.pending),
      animating: Boolean(obs.animation), view: { ...obs.view, target: [...obs.view.target] },
      pixelRatio: obs.renderer?.getPixelRatio() || 0, contextLost: obs.renderer?.getContext().isContextLost() ?? null };
  },
  project(id) {
    const entry = obs.built?.index.get(id);
    if (!entry) return null;
    obsApplyCamera();
    return obsScreen(entry.position);
  },
  pickAt: (x, y) => obsPick(x, y),
  layout: (map) => obsLayout(map),
  renderer() {
    if (!obs.renderer) return null;
    const gl = obs.renderer.getContext();
    const debug = gl.getExtension("WEBGL_debug_renderer_info");
    return { renderer: gl.getParameter(debug ? debug.UNMASKED_RENDERER_WEBGL : gl.RENDERER),
      vendor: gl.getParameter(debug ? debug.UNMASKED_VENDOR_WEBGL : gl.VENDOR), version: gl.getParameter(gl.VERSION) };
  },
  measure(on) { obs.measure = Boolean(on); },
  timings: () => ({ frames: obs.frameTimes.map((frame) => ({ ...frame })), picks: obs.pickTimes.map((pick) => ({ ...pick })) }),
  clearTimings() { obs.frameTimes = []; obs.pickTimes = []; },
};
