import assert from "node:assert/strict";
import test from "node:test";

import { MemoryClient } from "./index.ts";
import type { NoteAffect } from "./index.ts";

test("timeline sends roles, budgets and the excluded conversation as query parameters", async () => {
  const requests: { url: URL; init?: RequestInit }[] = [];
  const result = { items: [], complete: true, characters: 0 };
  const client = new MemoryClient({
    baseUrl: "http://memory.test", apiKey: "test-key", brainId: "brain /?#",
    fetch: async (input, init) => {
      requests.push({ url: new URL(String(input)), init });
      return Response.json(result);
    },
  });
  assert.deepEqual(await client.timeline({ roles: ["user", "assistant"], maxCharacters: 900, excludeConversation: "now /?&" }), result);
  assert.equal(requests[0].url.pathname, "/v1/brains/brain%20%2F%3F%23/timeline");
  assert.deepEqual(requests[0].url.searchParams.getAll("role"), ["user", "assistant"]);
  assert.equal(requests[0].url.searchParams.get("max_characters"), "900");
  assert.equal(requests[0].url.searchParams.get("exclude_conversation"), "now /?&");
  assert.equal(requests[0].init?.method, "GET");
  await client.timeline();
  assert.deepEqual(requests[1].url.searchParams.getAll("role"), ["user"]);
  await client.timeline({ eventIds: ["event-1", "event 2"] });
  assert.deepEqual(requests[2].url.searchParams.getAll("event_id"), ["event-1", "event 2"]);
  await client.timeline({ conversationId: "membrain-notes" });
  assert.equal(requests[3].url.searchParams.get("conversation_id"), "membrain-notes");
});

test("ensureBrain creates or reuses a named brain with PUT", async () => {
  const requests: { url: URL; init?: RequestInit }[] = [];
  const client = new MemoryClient({
    baseUrl: "http://memory.test", apiKey: "test-key", brainId: "home",
    fetch: async (input, init) => {
      requests.push({ url: new URL(String(input)), init });
      return Response.json({ id: "user-abc" });
    },
  });
  assert.deepEqual(await client.ensureBrain("user-abc", "user qq:1001"), { id: "user-abc" });
  assert.equal(requests[0].url.pathname, "/v1/brains/user-abc");
  assert.equal(requests[0].init?.method, "PUT");
  assert.deepEqual(JSON.parse(String(requests[0].init?.body)), { name: "user qq:1001" });
});

test("notes preserve shared moments and evidence-backed feelings including neutral values", async () => {
  const bodies: any[] = [];
  const client = new MemoryClient({ baseUrl: "http://memory.test", apiKey: "test-key", brainId: "brain",
    fetch: async (_input, init) => { bodies.push(JSON.parse(String(init?.body))); return Response.json({ note_id: "n" }); } });
  const affect: NoteAffect = { label: "平静", valence: 0, intensity: 0, basis: "reported", felt_at: "2026-11-03" };
  await client.writeNote("We finished a puzzle together.", { kind: "milestone", shared: true, affect,
    sourceEventIds: ["source"] });
  assert.equal(bodies[0].shared, true);
  assert.deepEqual(bodies[0].affect, affect);
  assert.deepEqual(bodies[0].source_event_ids, ["source"]);
  await client.writeNote("A personal milestone.", { kind: "milestone", shared: false });
  assert.equal(bodies[1].shared, false);
  assert.equal("affect" in bodies[1], false);
});

test("note writes preserve explicit sources and retry identity while timeline cursors stay encoded", async () => {
  const requests: { url: URL; init?: RequestInit }[] = [];
  const client = new MemoryClient({ baseUrl: "http://memory.test", apiKey: "test-key", brainId: "brain /?#",
    fetch: async (input, init) => { requests.push({ url: new URL(String(input)), init }); return Response.json({ note_id: "n1" }); } });
  const options = { requestId: "stable-note", sourceEventIds: ["event one"], sourceMessages: [
    { producer_ref: "host", source_event_key: "current:one:user", source_revision: 1 }], kind: "plan", status: "scheduled", occursAt: "2026-11-04" };
  await client.writeNote("Appointment.", options);
  await client.writeNote("Appointment.", options);
  assert.equal(requests[0].url.pathname, "/v1/brains/brain%20%2F%3F%23/notes");
  assert.deepEqual(requests[0].init?.body, requests[1].init?.body);
  const body = JSON.parse(String(requests[0].init?.body));
  assert.equal(body.request_id, "stable-note");
  assert.equal(body.occurs_at, "2026-11-04");
  assert.deepEqual(body.source_event_ids, ["event one"]);
  assert.deepEqual(body.source_messages, options.sourceMessages);
  await client.timeline({ beforeSequence: 123 });
  assert.equal(requests[2].url.searchParams.get("before_sequence"), "123");
  await client.following(["event one"]);
  assert.deepEqual(requests[3].url.searchParams.getAll("event_id"), ["event one"]);
});

test("exact source reads and guarded writes preserve the dependency generation including zero", async () => {
  const requests: { url: URL; init?: RequestInit }[] = [];
  const client = new MemoryClient({ baseUrl: "http://memory.test", apiKey: "test-key", brainId: "home",
    fetch: async (input, init) => { requests.push({ url: new URL(String(input)), init }); return Response.json({}); } });
  const sources = Object.freeze([{ producer_ref: "host", source_event_key: "turn:user", source_revision: 2 }]);
  await client.sourceMessages(sources, "brain /?#");
  assert.equal(requests[0].url.pathname, "/v1/brains/brain%20%2F%3F%23/source-messages");
  assert.deepEqual(JSON.parse(String(requests[0].init?.body)), { messages: sources });
  await client.writeNote("The plan changed.", { sourceMessages: sources, contextSourceMessages: sources,
    requireCurrentSources: true, expectedDependencyGeneration: 0, expectedRecordingRevision: 0 });
  const body = JSON.parse(String(requests[1].init?.body));
  assert.deepEqual(body.source_messages, sources);
  assert.deepEqual(body.context_source_messages, sources);
  assert.equal(body.require_current_sources, true);
  assert.equal(body.expected_dependency_generation, 0);
  assert.equal(body.expected_recording_revision, 0);
});

test("message cues are sent with the message they belong to", async () => {
  const requests: { url: URL; init?: RequestInit }[] = [];
  const client = new MemoryClient({ baseUrl: "http://memory.test", apiKey: "test-key", brainId: "home",
    fetch: async (input, init) => { requests.push({ url: new URL(String(input)), init }); return Response.json({}); } });
  const items = [{ event_id: "event one", cues: ["Melanie hobbies and activities"] },
    { producer_ref: "host", source_event_key: "turn:user", cues: ["Caroline country of origin"] }];
  await client.writeMessageCues(items, { brainId: "brain /?#" });
  await client.writeMessageCues(items, { modelVersion: "cue-model-1" });
  assert.equal(requests[0].url.pathname, "/v1/brains/brain%20%2F%3F%23/message-cues");
  assert.deepEqual(JSON.parse(String(requests[0].init?.body)), { items });
  assert.deepEqual(JSON.parse(String(requests[1].init?.body)), { items, model_version: "cue-model-1" });
  await client.pendingMessageCues({ limit: 5 });
  assert.equal(requests[2].url.pathname, "/v1/brains/home/message-cues/pending");
  assert.equal(requests[2].url.searchParams.get("limit"), "5");
  assert.equal(requests[2].url.searchParams.get("max_characters"), "6000");
  assert.equal(requests[2].url.searchParams.get("whole_conversations"), "false");
  await client.writeMessageCues([{ sequence: 7, cues: ["Sam hobbies and activities"] }], { reviewedThroughSequence: 9 });
  assert.deepEqual(JSON.parse(String(requests[3].init?.body)),
    { items: [{ sequence: 7, cues: ["Sam hobbies and activities"] }], reviewed_through_sequence: 9 });
});
