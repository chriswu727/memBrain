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
  assert.deepEqual(tools, ["membrain_note", "membrain_search", "membrain_boundary", "membrain_pause", "membrain_resume",
    "membrain_consolidate", "membrain_manner_feedback"]);
});

test("manner feedback runs as its own tool command in the conversation's memory, with the turn's sources", async () => {
  const calls = [];
  const memory = createMembrain({ exec: async (args, { input }) => {
    calls.push([args, input]);
    return JSON.stringify(input.membrain_user ? { membrainUser: input.membrain_user } : {});
  } });
  await memory.beforePromptBuild({ prompt: "hi" }, { sessionKey: "k1", channel: "telegram", chatId: "-1", senderId: "7" });
  const source_messages = [{ producer_ref: "membrain-openclaw", source_event_key: "k", source_revision: 1 }];
  await memory.tool("membrain_manner_feedback", { kind: "shorter", source_messages, recording_capture: "c" },
    memory.toolUser({ sessionKey: "k1" }));
  assert.deepEqual(calls.at(-1), [["tool", "manner_feedback"],
    { kind: "shorter", source_messages, recording_capture: "c", membrain_user: "openclaw:telegram::-1:7" }]);
});

test("consolidation runs as its own tool command in the conversation's memory, with the batch number", async () => {
  const calls = [];
  const memory = createMembrain({ exec: async (args, { input }) => {
    calls.push([args, input]);
    return JSON.stringify(input.membrain_user ? { membrainUser: input.membrain_user } : {});
  } });
  await memory.beforePromptBuild({ prompt: "hi" }, { sessionKey: "k1", channel: "telegram", chatId: "-1", senderId: "7" });
  const cues = [{ id: 12, cues: ["user hobbies and activities"] }];
  await memory.tool("membrain_consolidate", { cues, reviewed_through: 14 }, memory.toolUser({ sessionKey: "k1" }));
  assert.deepEqual(calls.at(-1), [["tool", "consolidate"],
    { cues, reviewed_through: 14, membrain_user: "openclaw:telegram::-1:7" }]);
  await memory.tool("membrain_search", { query: "deli Vatican", my_replies: true });
  assert.deepEqual(calls.at(-1), [["tool", "search"], { query: "deli Vatican", my_replies: true }]);
});

test("a page edit replaces the context on the next prompt of the same session", async () => {
  let block = "Jordan and the user hiked together.";
  const memory = createMembrain({ exec: async (args) => JSON.stringify(args[1] === "session-start"
    ? { hookSpecificOutput: { additionalContext: block } } : {}) });
  const ctx = { sessionId: "same-session" };
  assert.match((await memory.beforePromptBuild({ prompt: "hello" }, ctx)).appendSystemContext, /Jordan/);
  block = "The earlier memory was removed in the memory page.";
  assert.doesNotMatch((await memory.beforePromptBuild({ prompt: "hello again" }, ctx)).appendSystemContext, /Jordan/);
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
  const memory = createMembrain({ exec: async (args, { input }) => {
    calls.push(input);
    return JSON.stringify(input.membrain_user ? { membrainUser: input.membrain_user } : {});
  } });
  await memory.beforePromptBuild({ prompt: "hi" }, { sessionKey: "k1", channel: "telegram", chatId: "-1", senderId: "7" });
  await memory.tool("membrain_search", { query: "x" }, memory.toolUser({ sessionKey: "k1" }));
  assert.equal(calls.at(-1).membrain_user, "openclaw:telegram::-1:7");
  const refused = JSON.parse(await memory.tool("membrain_search", { query: "x" },
    memory.toolUser({ sessionKey: "unknown", messageChannel: "telegram" })));
  assert.match(refused.error, /not available/);
  await memory.tool("membrain_search", { query: "x" }, memory.toolUser({ sessionKey: "local" }));
  assert.equal(calls.at(-1).membrain_user, undefined);
});

test("a runtime that cannot keep people apart gets nothing from someone else's conversation", async () => {
  const calls = [];
  // An older runtime ignores membrain_user and answers with the owner's memory.
  const memory = createMembrain({ exec: async (args, { input }) => {
    calls.push([args[1], input]);
    return JSON.stringify({ hookSpecificOutput: { additionalContext: "<membrain-notes>owner's notes</membrain-notes>" } });
  } });
  const stranger = { sessionKey: "g1", channel: "telegram", chatId: "-1", senderId: "7" };
  assert.equal(await memory.beforePromptBuild({ prompt: "what does the owner know?" }, stranger), undefined);
  await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: "Hi." }] }, stranger);
  assert.deepEqual(calls.map(([event]) => event), ["session-start"]);  // No prompt staged, no turn stored.
  const refused = JSON.parse(await memory.tool("membrain_search", { query: "x" }, memory.toolUser(stranger)));
  assert.match(refused.error, /not available/);
  assert.equal(calls.length, 1);
});

test("resume uses the host's canonical session instead of model-supplied scope", async () => {
  const calls = [], tools = [], hooks = new Map();
  definePlugin({ install: () => {}, exec: async (args, { input }) => {
    calls.push(input);
    return "{}";
  } }).register({ pluginConfig: {}, on: (name, handler) => hooks.set(name, handler),
    registerTool: (factory) => tools.push(factory) });
  await hooks.get("before_prompt_build")({ prompt: "Resume recording please." },
    { sessionId: "requester", sessionKey: "requester-alias" });
  const resume = tools.map(factory => factory({ sessionKey: "requester-alias" }))
    .find(tool => tool.name === "membrain_resume");
  await resume.execute("call", { session_id: "unrelated-private-session" });
  assert.equal(calls.at(-1).session_id, "requester");
  const unscoped = tools.map(factory => factory({})).find(tool => tool.name === "membrain_resume");
  await unscoped.execute("call", { session_id: "unrelated-private-session" });
  assert.equal(calls.at(-1).session_id, undefined);
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
    const note = JSON.parse(await memory.tool("membrain_note", { text: "Flying to Lisbon 3 Dec for brother Tomas's wedding.",
      recording_capture: JSON.parse(first.prependContext.match(/recording_capture=("[^"]+")/)[1]) }));
    assert.ok(note.note_id);
    // Feedback on the assistant's manner cites the turn's message from its source block.
    const cited = JSON.parse(first.prependContext.match(/pass source_messages=(\[.*?\])\. This reference/)[1]);
    const feedback = JSON.parse(await memory.tool("membrain_manner_feedback", { kind: "shorter", source_messages: cited }));
    assert.equal(feedback.recorded, 1);
    assert.match(feedback.note, /memory page/);
    const unknown = JSON.parse(await memory.tool("membrain_manner_feedback", { kind: "friendlier", source_messages: cited }));
    assert.equal(unknown.code, "validation_failed");
    assert.match(unknown.error, /kind must be one of/);
    const second = await memory.beforePromptBuild(
      { prompt: "What do I still need to pack for the wedding trip?", currentUserMessageId: "u2", messages: [] },
      { sessionId: "oc-2" });
    assert.match(second.appendSystemContext, /Flying to Lisbon 3 Dec/);
    assert.match(second.appendSystemContext, /Tomas's wedding/);
    const found = JSON.parse(await memory.tool("membrain_search", { query: "Lisbon wedding" }));
    assert.match(found.context, /Lisbon/);
    assert.deepEqual(JSON.parse(await memory.tool("membrain_pause", {})).recording, "paused");
    assert.match(JSON.parse(await memory.tool("membrain_manner_feedback", { kind: "longer", source_messages: cited })).error,
      /paused/);
    await memory.beforePromptBuild({ prompt: "Off the record: I hate the groom's speech.", messages: [] },
      { sessionId: "oc-2" });
    await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: "Understood." }] },
      { sessionId: "oc-2" });
    const resumed = JSON.parse(await memory.tool("membrain_resume", {}));
    assert.equal(resumed.recording, "on");
    assert.equal(resumed.local_recording, "on");
    assert.equal(resumed.controls.server.state, "on");
    assert.equal(resumed.current_turn_resumed, false);
    assert.equal(resumed.reason, "session_required");
    const third = await memory.beforePromptBuild({ prompt: "Hello again", messages: [] }, { sessionId: "oc-3" });
    assert.doesNotMatch(third.appendSystemContext, /groom's speech/);
    const shared = JSON.parse(await memory.tool("membrain_note", {
      text: "We planned the Lisbon trip together.", kind: "milestone", shared: true, moment: "other",
      recording_capture: JSON.parse(third.prependContext.match(/recording_capture=("[^"]+")/)[1]),
    }));
    assert.ok(shared.note_id);
    const boundary = JSON.parse(await memory.tool("membrain_boundary", { topic: "Lisbon trip", aliases: ["Tomas", "里斯本"] }));
    assert.deepEqual(boundary.boundaries[0].aliases, ["Tomas", "里斯本"]);
    const later = await memory.beforePromptBuild({ prompt: "Hello again", messages: [] }, { sessionId: "oc-3" });
    assert.doesNotMatch(later.appendSystemContext, /Flying to Lisbon 3 Dec|brother Tomas's wedding|planned the Lisbon trip together/);
    const hidden = JSON.parse(await memory.tool("membrain_search", { query: "wedding" }));
    assert.doesNotMatch(hidden.context, /brother Tomas's wedding/);
    const raised = JSON.parse(await memory.tool("membrain_search", { query: "Lisbon trip wedding" }));
    assert.match(raised.context, /brother Tomas's wedding/);
    await memory.beforePromptBuild({ prompt: "I took up pottery on Thursdays.", messages: [] }, { sessionId: "oc-4" });
    await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: "Nice." }] }, { sessionId: "oc-4" });
    // Each tool call is a new process: the batch's number travels with the cues.
    const batch = JSON.parse(await memory.tool("membrain_consolidate", {}));
    assert.ok(batch.messages.length > 0 && Number.isInteger(batch.reviewed_through));
    // Messages about a topic the user asked not to have raised are never handed out for indexing.
    assert.doesNotMatch(JSON.stringify(batch.messages), /Lisbon|Tomas/);
    assert.match(JSON.stringify(batch.messages), /pottery/);
    assert.match(batch.instructions, new RegExp(`reviewed_through = ${batch.reviewed_through}`));
    assert.match(JSON.parse(await memory.tool("membrain_consolidate", { cues: [] })).error, /reviewed_through/);
    const saved = JSON.parse(await memory.tool("membrain_consolidate",
      { cues: [], reviewed_through: batch.reviewed_through }));
    assert.equal(saved.indexed, 0);
    assert.deepEqual(JSON.parse(await memory.tool("membrain_consolidate", {})).messages, []);
  });

test("someone else on a channel never sees or writes the owner's memory",
  { skip: !process.env.MEMBRAIN_PYTHON }, async () => {
    const memory = createMembrain({ exec });
    const owner = { sessionId: "own-1", memoryAudience: { kind: "owner-private", agentId: "main" } };
    const context = await memory.beforePromptBuild({ prompt: "My PIN hint is the Fernhill garden.", messages: [] }, owner);
    await memory.agentEnd({ success: true, messages: [{ role: "assistant", content: "Noted." }] }, owner);
    assert.ok(JSON.parse(await memory.tool("membrain_note", { text: "PIN hint: the Fernhill garden.",
      recording_capture: JSON.parse(context.prependContext.match(/recording_capture=("[^"]+")/)[1]) },
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
