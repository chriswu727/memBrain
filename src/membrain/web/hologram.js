"use strict";

// Cortical filaments, dendrites and the projector are illustrative geometry. Record cores and signal paths
// alone carry map identities; simulated signals never imply that a recall or biological event occurred.
class MemoryHologram {
  constructor() {
    this.generation = 0;
    this.frames = 0;
    this.turn = -.28;
    this.tilt = .09;
    this.zoom = 1;
    this.paused = false;
    this.motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    document.addEventListener("visibilitychange", () => this.schedule());
    this.motion.addEventListener("change", () => this.schedule());
  }

  async open(map) {
    this.close();
    const generation = this.generation;
    try {
      const T = await import("/static/vendor/three/three.module.js");
      if (generation !== this.generation || !showState.open) return;
      this.T = T;
      const canvas = document.createElement("canvas");
      canvas.className = "hologram-canvas";
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", translate("3D memory hologram. Drag to rotate and scroll to zoom. Signals are simulated."));
      const context = canvas.getContext("webgl2", { alpha: true, antialias: true, powerPreference: "low-power" });
      if (!context) return;
      this.renderer = new T.WebGLRenderer({ canvas, context, alpha: true, antialias: true });
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      this.renderer.setClearColor(0x02050c, 0);
      this.scene = new T.Scene();
      this.camera = new T.PerspectiveCamera(39, 1, .1, 80);
      this.brain = new T.Group();
      this.scene.add(this.brain);
      this.build(map);
      $("show-stage").append(canvas);
      $("brain-show").classList.add("holographic");
      $("show-simulation").hidden = false;
      stopPulses();
      this.bind(canvas);
      this.resize = new ResizeObserver(() => { this.size(); this.schedule(); });
      this.resize.observe($("show-stage"));
      canvas.addEventListener("webglcontextlost", (event) => {
        event.preventDefault();
        if (this.renderer?.domElement !== canvas) return;
        this.close();
        startPulses();
      });
      this.size();
      this.draw(0);
      this.schedule();
    } catch (error) {
      if (generation !== this.generation) return;
      this.close();
      startPulses();
    }
  }

  geometry(positions, colours, sizes) {
    const T = this.T, geometry = new T.BufferGeometry();
    geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
    if (colours) geometry.setAttribute("color", new T.Float32BufferAttribute(colours, 3));
    if (sizes) geometry.setAttribute("size", new T.Float32BufferAttribute(sizes, 1));
    return geometry;
  }

  points(positions, colours, sizes, opacity = 1) {
    const T = this.T;
    const material = new T.ShaderMaterial({
      transparent: true, depthWrite: false, blending: T.AdditiveBlending, vertexColors: true,
      uniforms: { opacity: { value: opacity }, pixelRatio: { value: Math.min(window.devicePixelRatio || 1, 1.5) } },
      vertexShader: `attribute float size; varying vec3 tint; uniform float pixelRatio;
        void main() { tint = color; vec4 p = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = clamp(size * pixelRatio * 7.0 / -p.z, 1.0, 100.0);
          gl_Position = projectionMatrix * p; }`,
      fragmentShader: `varying vec3 tint; uniform float opacity;
        void main() { float r = length(gl_PointCoord - .5) * 2.0;
          float halo = exp(-r * r * 5.5) * .36 + exp(-r * r * 65.0);
          gl_FragColor = vec4(tint, halo * opacity * (1.0 - smoothstep(.65, 1.0, r))); }`,
    });
    return new T.Points(this.geometry(positions, colours, sizes), material);
  }

  lines(positions, color, opacity, parent = this.brain) {
    const T = this.T;
    const line = new T.LineSegments(this.geometry(positions), new T.LineBasicMaterial({
      color, transparent: true, opacity, depthWrite: false, blending: T.AdditiveBlending,
    }));
    parent.add(line);
    return line;
  }

  surface(theta, phi) {
    const fold = .96 + .045 * Math.sin(theta * 23 + Math.sin(phi * 7) * 2) * Math.sin(phi * 19 + theta * 4);
    const s = Math.sin(theta), x = 3.12 * s * Math.cos(phi), z = 1.63 * s * Math.sin(phi);
    const cleft = .40 * Math.exp(-z * z / .055) * Math.max(0, Math.cos(theta));
    return [x * fold, (1.87 * Math.cos(theta) - cleft) * fold + .18, z * fold];
  }

  build(map) {
    const T = this.T, random = seeded(341), shell = [], colours = [], sizes = [], filaments = [];
    for (let i = 0; i < 18000; i++) {
      const theta = Math.acos(2 * random() - 1), phi = random() * Math.PI * 2;
      shell.push(...this.surface(theta, phi));
      const blue = random();
      colours.push(.08 + blue * .16, .35 + blue * .34, .65 + blue * .3);
      sizes.push(1.1 + random() * 1.8);
    }
    for (let i = 0; i < 1800; i++) {
      const theta = Math.acos(2 * random() - 1), phi = random() * Math.PI * 2;
      shell.push(1.92 + .78 * Math.sin(theta) * Math.cos(phi), -1.28 + .6 * Math.cos(theta), .76 * Math.sin(theta) * Math.sin(phi));
      colours.push(.12, .4, .65);
      sizes.push(1.6);
    }
    this.brain.add(this.points(shell, colours, sizes, .48));
    for (let i = 0; i < 115; i++) {
      const phi = random() * Math.PI * 2, start = random() * 2.5 + .14;
      let previous;
      for (let j = 0; j < 60; j++) {
        const theta = start + j * .006;
        const p = this.surface(theta, phi + .045 * Math.sin(theta * 24 + i) + j * .0007);
        if (previous) filaments.push(...previous, ...p);
        previous = p;
      }
    }
    this.lines(filaments, 0x399cdc, .20);
    const hindbrain = [];
    for (let i = 0; i < 18; i++) {
      const y = -1.82 + i * .064, r = Math.sqrt(Math.max(0, 1 - ((y + 1.28) / .6) ** 2));
      for (let j = 0; j < 80; j++) {
        const a = j * Math.PI / 40, b = (j + 1) * Math.PI / 40;
        hindbrain.push(1.92 + .78 * r * Math.cos(a), y, .76 * r * Math.sin(a),
          1.92 + .78 * r * Math.cos(b), y, .76 * r * Math.sin(b));
      }
    }
    for (let i = 0; i < 18; i++) {
      const a = i * Math.PI / 9;
      hindbrain.push(.9 + .21 * Math.cos(a), -1.42, .21 * Math.sin(a),
        .64 + .13 * Math.cos(a), -2.2, .13 * Math.sin(a));
    }
    this.lines(hindbrain, 0x4e94d0, .15);

    const layout = obsLayout(map), positions = [], nodeColours = [], nodeSizes = [], dendrites = [];
    this.layout = layout;
    this.nodes = map.nodes.map((node) => node.id);
    this.links = map.edges.filter((edge) => layout[edge.source] && layout[edge.target]);
    const recent = recentIds(map);
    for (const node of map.nodes) {
      const p = layout[node.id], color = new T.Color(recent.has(node.id) ? "#fff2bd" : SHOW_COLOURS[node.region] || "#64ddff");
      positions.push(...p);
      nodeColours.push(color.r, color.g, color.b);
      nodeSizes.push(recent.has(node.id) ? 27 : 18);
      const rng = seeded(obsHash(node.id));
      for (let branch = 0; branch < (map.contract_version === "memory-structure-v1" ? 0 : 5); branch++) {
        let a = p;
        const angle = rng() * Math.PI * 2, rise = rng() * 2 - 1;
        for (let j = 1; j <= 4; j++) {
          const r = j * .045;
          const b = [p[0] + Math.cos(angle + j * .23) * r, p[1] + rise * r, p[2] + Math.sin(angle + j * .23) * r];
          dendrites.push(...a, ...b);
          if (j > 2) dendrites.push(...b, b[0] + .04 * Math.sin(angle), b[1] + .035, b[2] + .04 * Math.cos(angle));
          a = b;
        }
      }
    }
    this.brain.add(this.points(positions, nodeColours, nodeSizes));
    this.lines(dendrites, 0x64dfff, .25);
    const wires = [];
    this.paths = this.links.map((edge, index) => {
      const a = new T.Vector3(...layout[edge.source]), b = new T.Vector3(...layout[edge.target]);
      const middle = a.clone().lerp(b, .5);
      middle.y += .16 + (index % 7) * .045;
      middle.z += Math.sin(index * 2.4) * .28;
      const curve = new T.QuadraticBezierCurve3(a, middle, b), points = curve.getPoints(64);
      for (let i = 1; i < points.length; i++) wires.push(...points[i - 1].toArray(), ...points[i].toArray());
      return points;
    });
    this.lines(wires, 0x35afd6, .19);
    const signalPositions = [], signalColours = [], signalSizes = [];
    this.signalCount = Math.min(48, this.paths.length);
    for (let i = 0; i < this.signalCount; i++) {
      for (let tail = 0; tail < 12; tail++) {
        signalPositions.push(0, 0, 0);
        const intensity = (1 - tail / 12) ** 1.7;
        signalColours.push(.52 * intensity, .90 * intensity, intensity);
        signalSizes.push(tail === 0 ? 24 : 13 - tail * .7);
      }
    }
    this.signals = this.points(signalPositions, signalColours, signalSizes);
    this.signals.frustumCulled = false;
    this.brain.add(this.signals);
    this.projector();
    this.map = map;
  }

  projector() {
    const rings = [], beams = [];
    for (const radius of [2.8, 3.02, 3.8, 4.2]) {
      for (let i = 0; i < 240; i++) {
        if (radius === 3.8 && i % 8 < 3) continue;
        const a = i * Math.PI / 120, b = (i + 1) * Math.PI / 120;
        rings.push(Math.cos(a) * radius, -2.65, Math.sin(a) * radius,
          Math.cos(b) * radius, -2.65, Math.sin(b) * radius);
      }
    }
    for (let i = 0; i < 80; i++) {
      const angle = i * Math.PI / 40;
      rings.push(Math.cos(angle) * 4.12, -2.65, Math.sin(angle) * 4.12,
        Math.cos(angle) * (i % 5 ? 4.18 : 4.29), -2.65, Math.sin(angle) * (i % 5 ? 4.18 : 4.29));
      if (i % 5 === 0) beams.push(Math.cos(angle) * 2.8, -2.65, Math.sin(angle) * 2.8,
        Math.cos(angle) * 2.1, 1.25, Math.sin(angle) * 1.3);
    }
    this.lines(rings, 0x21c9ef, .22, this.scene);
    this.lines(beams, 0x2683b8, .035, this.scene);
    const dust = [], color = [], size = [], random = seeded(98);
    for (let i = 0; i < 600; i++) {
      dust.push((random() - .5) * 22, (random() - .5) * 13, (random() - .5) * 16 - 2);
      color.push(.12, .35, .5);
      size.push(random() * 2 + 1);
    }
    this.scene.add(this.points(dust, color, size, .36));
  }

  bind(canvas) {
    canvas.addEventListener("pointerdown", (event) => {
      if (!event.isPrimary) return;
      this.drag = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!this.drag || !event.isPrimary) return;
      this.turn += (event.clientX - this.drag.x) * .005;
      this.tilt = Math.max(-.8, Math.min(.8, this.tilt + (event.clientY - this.drag.y) * .004));
      this.drag = { x: event.clientX, y: event.clientY };
      this.draw(this.time || 0);
    });
    for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) canvas.addEventListener(name, () => { this.drag = null; });
    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      this.zoom = Math.max(.65, Math.min(1.6, this.zoom * Math.exp(event.deltaY * .0007)));
      this.size(); this.draw(this.time || 0);
    }, { passive: false });
  }

  size() {
    if (!this.renderer) return;
    const { width, height } = $("show-stage").getBoundingClientRect();
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / Math.max(height, 1);
    this.camera.position.set(0, 1.1, Math.max(10.2, 7.8 / this.camera.aspect) * this.zoom);
    this.camera.lookAt(0, -.35, 0);
    this.camera.updateProjectionMatrix();
  }

  draw(time) {
    if (!this.renderer) return;
    this.time = time;
    const motion = !this.motion.matches && !this.paused;
    this.brain.rotation.set(this.tilt, this.turn + (motion ? Math.sin(time * .000065) * .3 : 0), -.04);
    this.brain.position.y = motion ? Math.sin(time * .0007) * .055 : 0;
    const buffer = this.signals.geometry.attributes.position;
    for (let i = 0; i < this.signalCount; i++) {
      const progress = (time * .00024 + i * .618034) % 1;
      const path = this.paths[(i * 7 + Math.floor(time * .00024 + i * .618034) * 13) % this.paths.length];
      for (let tail = 0; tail < 12; tail++) {
        const p = path[Math.max(0, Math.min(64, Math.round((progress - tail * .009) * 64)))];
        buffer.setXYZ(i * 12 + tail, p.x, p.y, p.z);
      }
    }
    buffer.needsUpdate = true;
    this.renderer.render(this.scene, this.camera);
    this.frames++;
  }

  schedule() {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    if (!this.renderer || document.hidden) return;
    if (this.motion.matches || this.paused) { this.draw(this.time || 0); return; }
    const tick = (time) => {
      if (!this.renderer || document.hidden) { this.frame = 0; return; }
      if (time - (this.lastFrame || 0) >= 32) { this.draw(time); this.lastFrame = time; }
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  close() {
    this.generation++;
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.resize?.disconnect();
    if (this.scene) this.scene.traverse((object) => { object.geometry?.dispose(); object.material?.dispose(); });
    if (this.renderer) {
      this.renderer.domElement.remove();
      this.renderer.dispose();
      this.renderer.forceContextLoss();
    }
    this.renderer = this.scene = this.camera = this.brain = this.drag = null;
    this.paths = this.nodes = this.links = this.signals = null;
    this.layout = null;
    this.map = null;
    $("brain-show").classList.remove("holographic");
    $("show-simulation").hidden = true;
  }
}

const hologram = new MemoryHologram();
window.memoryHologram = Object.freeze({ snapshot: () => ({
  ready: Boolean(hologram.renderer), frames: hologram.frames, active: Boolean(hologram.frame),
  nodeIds: hologram.map ? [...hologram.nodes] : [],
  edges: hologram.map ? hologram.links.map((edge) => ({ ...edge })) : [],
  turn: hologram.turn, tilt: hologram.tilt, zoom: hologram.zoom,
  signalCount: hologram.map ? hologram.signalCount : 0,
  positions: hologram.map ? structuredClone(hologram.layout) : {},
}) });
