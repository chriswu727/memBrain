import test from "node:test";
import assert from "node:assert/strict";
import { MemoryClient, MemoryHttpError } from "./index.ts";

test("recording control scopes the brain and retains the caller's revision", async () => {
  const requests: { url: string; method?: string; body?: unknown }[] = [];
  const client = new MemoryClient({
    baseUrl: "http://memory.test", apiKey: "test-key", brainId: "default",
    fetch: async (input, init) => {
      requests.push({ url: String(input), method: init?.method,
        ...(init?.body ? { body: JSON.parse(init.body as string) } : {}) });
      return Response.json({ paused: init?.method === "PUT", revision: 7 });
    },
  });
  assert.deepEqual(await client.recordingStatus("brain /?#"), { paused: false, revision: 7 });
  const options = Object.freeze({ paused: true, expectedRevision: 6, brainId: "brain /?#" });
  assert.deepEqual(await client.setRecording(options), { paused: true, revision: 7 });
  assert.deepEqual(requests, [
    { url: "http://memory.test/v1/brains/brain%20%2F%3F%23/recording", method: "GET" },
    { url: "http://memory.test/v1/brains/brain%20%2F%3F%23/recording", method: "PUT",
      body: { paused: true, expected_revision: 6 } },
  ]);
  assert.equal(client.brainId, "default");
});

test("a stale resume is surfaced without fetching and replacing its revision", async () => {
  let calls = 0;
  const client = new MemoryClient({
    baseUrl: "http://memory.test", apiKey: "test-key", brainId: "brain",
    fetch: async () => {
      calls++;
      return Response.json({ error: { code: "version_conflict" } }, { status: 409 });
    },
  });
  await assert.rejects(client.setRecording({ paused: false, expectedRevision: 0 }),
    error => error instanceof MemoryHttpError && error.status === 409);
  assert.equal(calls, 1);
});
