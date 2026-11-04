import assert from "node:assert/strict";
import test from "node:test";

import { MemoryClient, MemoryHttpError } from "./index.ts";
import type { PersonaCard } from "./index.ts";

function recorded() {
  const requests: { url: URL; init: RequestInit }[] = [];
  const payload = { version: 7, details: { retained: true }, optional: null };
  const epoch = "11111111-1111-4111-8111-111111111111";
  const client = new MemoryClient({ baseUrl: "https://memory.test/prefix", apiKey: "test-key",
    brainId: "owner", recoveryEpoch: epoch, fetch: async (url, init) => {
      requests.push({ url: new URL(String(url)), init: init! });
      return Response.json(payload);
    } });
  return { client, requests, payload, epoch };
}

test("every companion operation retains explicit brain scope, authentication and recovery acknowledgement", async () => {
  const { client, requests, payload, epoch } = recorded();
  const brain = "person /?#", id = "record /?#";
  const options = { brainId: brain };
  const record = encodeURIComponent(id);
  const operations: [string, string, () => Promise<unknown>][] = [
    ["GET", "persona", () => client.persona(brain)],
    ["PUT", "persona", () => client.setPersona({ name: "Aster" }, options)],
    ["GET", "persona/versions", () => client.personaVersions(brain)],
    ["POST", "persona/restore", () => client.restorePersona(1, options)],
    ["POST", "persona/reset", () => client.resetPersona(options)],
    ["DELETE", "persona/versions", () => client.deletePersonaHistory(brain)],
    ["GET", "persona/proposals", () => client.personaProposals(brain)],
    ["POST", `persona/proposals/${record}/accept`, () => client.acceptPersonaProposal(id, brain)],
    ["POST", `persona/proposals/${record}/reject`, () => client.rejectPersonaProposal(id, brain)],
    ["GET", "affect", () => client.affectRecords(brain)],
    ["POST", "affect/reset", () => client.clearAffect(brain)],
    ["GET", "mood", () => client.mood(brain)],
    ["POST", "mood/pin", () => client.pinMood(true, brain)],
    ["POST", "mood/reset", () => client.resetMood(brain)],
    ["GET", "relationship", () => client.relationship(brain)],
    ["PUT", "relationship/support-style", () => client.setSupportStyle("Listen first.", brain)],
    ["POST", "relationship/boundaries", () => client.addBoundary("work", [], brain)],
    ["DELETE", `relationship/boundaries/${record}`, () => client.removeBoundary(id, brain)],
    ["POST", "relationship/cap", () => client.capFamiliarity("new", brain)],
    ["POST", "relationship/acknowledge", () => client.acknowledgeCommitments([id], brain)],
    ["POST", "relationship/reset", () => client.resetRelationship(brain)],
    ["GET", "memory-map", () => client.memoryMap(options)],
    ["GET", "companion-map", () => client.companionMap(options)],
  ];
  for (const [method, path, run] of operations) {
    assert.deepEqual(await run(), payload);
    const request = requests.at(-1)!;
    assert.equal(request.init.method, method);
    assert.equal(request.url.pathname, `/prefix/v1/brains/${encodeURIComponent(brain)}/${path}`);
    const headers = new Headers(request.init.headers);
    assert.equal(headers.get("authorization"), "Bearer test-key");
    assert.equal(headers.get("x-memory-recovery-epoch"), epoch);
    assert.equal(request.init.redirect, "error");
    assert.ok(request.init.signal instanceof AbortSignal);
  }
  assert.equal(requests.length, operations.length);
});

test("persona mutations preserve immutable cards, explicit user decisions and host defaults", async () => {
  const { client, requests } = recorded();
  const card: PersonaCard = Object.freeze({ name: "星 🧠", traits: Object.freeze(["patient"]),
    voice: Object.freeze({ register: "casual" }), baseline_mood: null });
  await client.setPersona(card, { madeBy: "user", reason: "", hostDefault: false });
  await client.setPersona(card, { hostDefault: true });
  await client.restorePersona(1, { madeBy: "user", reason: "Roll back." });
  await client.resetPersona();
  assert.deepEqual(requests.map(r => JSON.parse(String(r.init.body))), [
    { card, made_by: "user", reason: "", host_default: false },
    { card, made_by: "host", host_default: true },
    { version: 1, made_by: "user", reason: "Roll back." },
    { made_by: "host" },
  ]);
  assert.equal(card.name, "星 🧠");
  assert.deepEqual(card.traits, ["patient"]);
});

test("relationship and mood controls preserve removal, false and bounded acknowledgements", async () => {
  const { client, requests } = recorded();
  const aliases = Object.freeze(["Jordan", "前任"]);
  const notes = Object.freeze(Array.from({ length: 60 }, (_, i) => `note-${i}`));
  await client.setSupportStyle("");
  await client.addBoundary("old relationship", aliases);
  await client.capFamiliarity(null);
  await client.pinMood(false);
  await client.acknowledgeCommitments(notes);
  assert.deepEqual(requests.map(r => JSON.parse(String(r.init.body))), [
    { text: "" }, { topic: "old relationship", aliases }, { level: null }, { pinned: false },
    { note_ids: notes.slice(0, 50) },
  ]);
  assert.equal(notes.length, 60);
  assert.deepEqual(aliases, ["Jordan", "前任"]);
});

test("map windows keep zero edges and require explicit sensitive-content opt-in", async () => {
  const { client, requests } = recorded();
  await client.memoryMap({ maxNodes: 1, maxEdges: 0, trace: true, structure: true });
  await client.companionMap();
  await client.companionMap({ maxNodes: 500, maxEdges: 1000, includeSensitive: true });
  assert.deepEqual(Object.fromEntries(requests[0].url.searchParams), {
    max_nodes: "1", max_edges: "0", include_sensitive: "false", trace: "true", structure: "true",
  });
  assert.deepEqual(Object.fromEntries(requests[1].url.searchParams), {
    max_nodes: "200", max_edges: "400", include_sensitive: "false",
  });
  assert.equal(requests[2].url.searchParams.get("include_sensitive"), "true");
});

test("unscoped companion requests fail before contacting a service", () => {
  let calls = 0;
  const client = new MemoryClient({ baseUrl: "https://memory.test", apiKey: "test-key",
    fetch: async () => { calls++; return Response.json({}); } });
  for (const run of [() => client.persona(), () => client.setPersona({}), () => client.resetRelationship(),
    () => client.affectRecords(), () => client.mood(), () => client.companionMap()]) {
    assert.throws(run, /brainId is required/);
  }
  assert.equal(calls, 0);
});

test("a denied companion request never falls back to the owner's brain or retries", async () => {
  const requests: string[] = [];
  const client = new MemoryClient({ baseUrl: "https://memory.test", apiKey: "test-key", brainId: "owner",
    fetch: async url => { requests.push(String(url)); return Response.json({ error: "forbidden" }, { status: 403 }); } });
  await assert.rejects(client.addBoundary("private topic", [], "someone-else"),
    error => error instanceof MemoryHttpError && error.status === 403);
  assert.deepEqual(requests, ["https://memory.test/v1/brains/someone-else/relationship/boundaries"]);
});
