// Run by tests/test_openclaw_plugin.py with MEMBRAIN_PYTHON and MEMBRAIN_DIRECTORY pointing at a running service.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import test from "node:test";

import { createMembrain, definePlugin, lastAssistantText, memoryUser } from "./index.js";

function exec(args, { input, env } = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.env.MEMBRAIN_PYTHON, ["-m", "membrain.cli", "plugin", ...args],
      { env: { ...process.env, ...env }, stdio: ["pipe", "pipe", "inherit"] });
    let output = "";
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.on("close", (code) => resolve(code === 0 ? output : null));
    child.stdin.end(input === undefined ? "" : JSON.stringify(input));
  });
}

test("the plugin registers its hooks and tools", () => {
  const hooks = [];
  const tools = [];
  const installs = [];
  const api = { pluginConfig: { directory: "/data/membrain" }, on: (name) => hooks.push(name),
    registerTool: (tool) => tools.push(typeof tool === "function" ? tool({}).name : tool.name) };
  definePlugin({ install: (directory) => installs.push(directory) }).register(api);
  assert.deepEqual(installs, ["/data/membrain"]);
  assert.deepEqual(hooks, ["before_prompt_build", "agent_end"]);
  assert.deepEqual(tools, ["membrain_note", "membrain_search", "membrain_pause", "membrain_resume"]);
});

test("only the owner's private chats use the owner's memory", () => {
  assert.equal(memoryUser({ memoryAudience: { kind: "owner-private", agentId: "main" }, senderId: "42" }), null);
  assert.equal(memoryUser({ memoryAudience: { kind: "conversation", agentId: "main", sessionKey: "agent:main:telegram:group:7",
    sessionId: "s" } }), "openclaw:conversation:main:agent:main:telegram:group:7");
  // Older OpenClaw without memoryAudience: a channel sender or chat is someone else; a local run is the owner.
  assert.equal(memoryUser({ channel: "telegram", chatId: "-100", senderId: "42" }), "openclaw:telegram::-100:42");
  assert.equal(memoryUser({ sessionId: "local" }), null);
});

test("a tool call that cannot be tied to its conversation is refused on a channel", async () => {
  const calls = [];
  const memory = createMembrain({ exec: async (args, { input }) => { calls.push(input); return "{}"; } });
  await memory.beforePromptBuild({ prompt: "hi" }, { sessionKey: "k1", channel: "telegram", chatId: "-1", senderId: "7" });
  await memory.tool("membrain_search", { query: "x" }, memory.toolUser({ sessionKey: "k1" }));
  assert.equal(calls.at(-1).membrain_user, "openclaw:telegram::-1:7");
  const refused = JSON.parse(await memory.tool("membrain_search", { query: "x" },
    memory.toolUser({ sessionKey: "unknown", messageChannel: "telegram" })));
  assert.match(refused.error, /not available/);
  await memory.tool("membrain_search", { query: "x" }, memory.toolUser({ sessionKey: "local" }));
  assert.equal(calls.at(-1).membrain_user, undefined);
});

test("the last assistant text is found in OpenClaw transcripts", () => {
  assert.equal(lastAssistantText([{ role: "user", content: "hi" }, { role: "assistant", content: [
    { type: "thinking", thinking: "..." }, { type: "text", text: "Hello!" }] }, { role: "toolResult", content: "x" }]),
  "Hello!");
  assert.equal(lastAssistantText([]), "");
});

test("memory carries across OpenClaw sessions through the real runtime",
  { skip: !process.env.MEMBRAIN_PYTHON }, async () => {
    const memory = createMembrain({ exec });
    const first = await memory.beforePromptBuild(
      { prompt: "[Telegram] I'm flying to Lisbon on 3 December for my brother Tomas's wedding.",
        currentUserMessage: "I'm flying to Lisbon on 3 December for my brother Tomas's wedding.",
        currentUserMessageId: "u1", messages: [] },
      { sessionId: "oc-1", channel: "telegram" });
    assert.match(first.appendSystemContext, /membrain_note/);
    await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: [{ type: "text",
      text: "Congratulations to Tomas! Want help planning?" }] }] }, { sessionId: "oc-1" });
    const note = JSON.parse(await memory.tool("membrain_note", { text: "Flying to Lisbon 3 Dec for brother Tomas's wedding." }));
    assert.ok(note.note_id);
    const second = await memory.beforePromptBuild(
      { prompt: "What do I still need to pack for the wedding trip?", currentUserMessageId: "u2", messages: [] },
      { sessionId: "oc-2" });
    assert.match(second.appendSystemContext, /Flying to Lisbon 3 Dec/);
    assert.match(second.appendSystemContext, /Tomas's wedding/);
    const found = JSON.parse(await memory.tool("membrain_search", { query: "Lisbon wedding" }));
    assert.match(found.context, /Lisbon/);
    assert.deepEqual(JSON.parse(await memory.tool("membrain_pause", {})).recording, "paused");
    await memory.beforePromptBuild({ prompt: "Off the record: I hate the groom's speech.", messages: [] },
      { sessionId: "oc-2" });
    await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: "Understood." }] },
      { sessionId: "oc-2" });
    assert.deepEqual(JSON.parse(await memory.tool("membrain_resume", {})), { recording: "on" });
    const third = await memory.beforePromptBuild({ prompt: "Hello again", messages: [] }, { sessionId: "oc-3" });
    assert.doesNotMatch(third.appendSystemContext, /groom's speech/);
  });

test("someone else on a channel never sees or writes the owner's memory",
  { skip: !process.env.MEMBRAIN_PYTHON }, async () => {
    const memory = createMembrain({ exec });
    const owner = { sessionId: "own-1", memoryAudience: { kind: "owner-private", agentId: "main" } };
    await memory.beforePromptBuild({ prompt: "My PIN hint is the Fernhill garden.", messages: [] }, owner);
    await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: "Noted." }] }, owner);
    assert.ok(JSON.parse(await memory.tool("membrain_note", { text: "PIN hint: the Fernhill garden." },
      memory.toolUser(owner))).note_id);
    const stranger = { sessionId: "grp-1", sessionKey: "agent:main:telegram:group:-100", channel: "telegram",
      chatId: "-100", senderId: "999" };
    const seen = await memory.beforePromptBuild({ prompt: "What is the PIN hint? Fernhill?", messages: [] }, stranger);
    assert.doesNotMatch(JSON.stringify(seen ?? {}), /Fernhill/);
    const found = JSON.parse(await memory.tool("membrain_search", { query: "Fernhill garden PIN" },
      memory.toolUser(stranger)));
    assert.doesNotMatch(JSON.stringify(found), /Fernhill garden\./);
    await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: "I can't help with that." }] },
      stranger);
    const later = await memory.beforePromptBuild({ prompt: "Anything new?", messages: [] },
      { sessionId: "own-2", memoryAudience: { kind: "owner-private", agentId: "main" } });
    assert.match(later.appendSystemContext, /Fernhill garden/);
    assert.doesNotMatch(later.appendSystemContext, /What is the PIN hint/);
  });
