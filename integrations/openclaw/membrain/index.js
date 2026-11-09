// memBrain for OpenClaw. The memory work happens in the memBrain runtime (installed with uv); this plugin maps
// OpenClaw's hooks onto `membrain plugin hook ... --host openclaw` and its tools onto `membrain plugin tool ...`.
import { spawn } from "node:child_process";

const PACKAGE = process.env.MEMBRAIN_PACKAGE ||
  "membrain-ai[embedded,semantic] @ https://github.com/chriswu727/membrain/archive/8715fc0c910f4af80d5a2dadc703f3214f4a030a.zip";

function run(command, args, { input, timeoutMs = 12_000, env } = {}) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(command, args, { env: { ...process.env, ...env }, stdio: ["pipe", "pipe", "ignore"] });
    } catch {
      resolve(null);
      return;
    }
    let output = "";
    const timer = setTimeout(() => child.kill(), timeoutMs);
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.on("error", () => { clearTimeout(timer); resolve(null); });
    child.on("close", (code) => { clearTimeout(timer); resolve(code === 0 ? output : null); });
    child.stdin.on("error", () => {});
    child.stdin.end(input === undefined ? "" : JSON.stringify(input));
  });
}

function membrain(args, options) {
  return run("uvx", ["--offline", "--python", "3.12", "--from", "membrain-ai", "membrain", "plugin", ...args], options);
}

function textOf(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.filter((part) => part && part.type === "text" && typeof part.text === "string")
      .map((part) => part.text).join("\n");
  }
  return "";
}

export function lastAssistantText(messages) {
  for (let index = (messages?.length ?? 0) - 1; index >= 0; index--) {
    const message = messages[index];
    if (message && message.role === "assistant") {
      const text = textOf(message.content);
      if (text.trim()) return text;
    }
  }
  return "";
}

const TOOLS = [
  {
    name: "membrain_note",
    description: "Save one short, lasting fact about the user (health, people, dates, places, preferences, decisions, " +
      "constraints, plans and their changes) so it is shown at the start of every later session. One fact per note, " +
      "under 300 characters, with dates when they matter. Set kind when it is clear: person (with about = their name, " +
      "aliases, and the relation in the text), constraint, preference, plan (with status intended until the user " +
      "confirms it is scheduled or done, and due or occurs_at as YYYY-MM-DD), routine, milestone, relationship, or " +
      "agent_commitment for something you promised to do. Status done means everything in the note has happened: a " +
      "purchase paid for but not yet delivered, or a booking still ahead, is scheduled, with its date. " +
      "When a fact changes, save the updated note and pass the " +
      "old note's id in replaces. For every write, copy recording_capture from this turn's membrain-source block; " +
      "never substitute another turn's capture. When the user expresses a feeling about it, add affect: basis reported only if " +
      "they said it, inferred (with the message it was read from as a source) if clearly evident but unsaid; never " +
      "invent one. Do not save routine requests or anything the user asked you not to keep.",
    parameters: { type: "object", properties: {
      text: { type: "string" },
      recording_capture: { type: "string", maxLength: 130,
        description: "Copy recording_capture from this turn's membrain-source block. Never reuse another turn's value." },
      replaces: { type: "array", items: { type: "string" } },
      source_event_ids: { type: "array", items: { type: "string" }, maxItems: 64 },
      source_messages: { type: "array", maxItems: 64, items: { type: "object", properties: {
        producer_ref: { type: "string" }, source_event_key: { type: "string" }, source_revision: { type: "integer", minimum: 1 },
      }, required: ["producer_ref", "source_event_key", "source_revision"] } },
      kind: { type: "string", enum: ["person", "constraint", "preference", "plan", "routine", "milestone",
        "relationship", "agent_commitment", "other"] },
      about: { type: "string" },
      aliases: { type: "array", items: { type: "string" } },
      status: { type: "string", enum: ["intended", "scheduled", "done", "cancelled", "superseded"] },
      due: { type: "string", description: "YYYY-MM-DD" },
      occurs_at: { type: "string", description: "YYYY-MM-DD" },
      pinned: { type: "boolean" },
      sensitive: { type: "boolean" },
      shared: { type: "boolean", description: "With kind milestone: a moment you and the user shared, such as a goal reached together or a shared joke." },
      affect: { type: "object", description: "A feeling the user expressed about this; kept as evidence, never a score.",
        properties: {
          label: { type: "string", maxLength: 40, description: "The user's own word, e.g. nervous." },
          valence: { type: "integer", minimum: -2, maximum: 2 },
          intensity: { type: "integer", minimum: 0, maximum: 3 },
          basis: { type: "string", enum: ["reported", "inferred"] },
          topic: { type: "string", maxLength: 80 },
          felt_at: { type: "string", description: "YYYY-MM-DD" },
        }, required: ["label", "valence", "intensity", "basis"] },
    }, required: ["text"] },
  },
  {
    name: "membrain_search",
    description: "Search the user's earlier conversations and notes by a few concrete keywords (names, places, " +
      "activities, dates) when a request depends on personal context that is not already shown.",
    parameters: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
  },
  {
    name: "membrain_boundary",
    description: "Save a topic the user asked you not to bring up, with other names they use for it. Earlier " +
      "messages about it stay out of recalled memory unless the user raises it. This is not a pause or deletion: " +
      "the conversation is still remembered. The memory page can remove it.",
    parameters: { type: "object", properties: { topic: { type: "string" },
      aliases: { type: "array", items: { type: "string" } } }, required: ["topic"] },
  },
  {
    name: "membrain_pause",
    description: 'Stop recording only when the user asks you not to remember or store something ("off the record", "don\'t remember this"), not when they ask you to keep something private or between you: save that as a sensitive note instead. Without arguments the pause lasts for the rest of this conversation; pass hours when they name a duration, or until_resumed only when they ask you to stop remembering until they say so. The current exchange is not stored either.',
    parameters: { type: "object", properties: { hours: { type: "number" }, until_resumed: { type: "boolean" } } },
  },
  {
    name: "membrain_resume",
    description: "Resume recording after membrain_pause, when the user asks; their current message is then stored.",
    parameters: { type: "object", properties: {} },
  },
];

// Whose memory a turn uses. The owner's own private chats share the owner's memory (the one Claude Code and
// Codex use); anyone else OpenClaw talks to on a channel gets their own memory, so a stranger in a group never
// sees the owner's notes and never writes into them. OpenClaw resolves this itself as `memoryAudience`; older
// versions without it are treated as someone else whenever the turn came from a channel sender or chat.
export function memoryUser(ctx) {
  const audience = ctx?.memoryAudience;
  if (audience?.kind === "owner-private") return null;
  if (audience?.kind === "conversation") {
    return `openclaw:conversation:${audience.agentId || ""}:${audience.sessionKey || ctx?.sessionKey || ""}`;
  }
  const sender = ctx?.senderId || ctx?.senderExternalId;
  const chat = ctx?.chatId || ctx?.channelId;
  if (!sender && !chat) return null;
  const channel = ctx?.channel || ctx?.messageProvider || "channel";
  return `openclaw:${channel}:${ctx?.accountId || ""}:${chat || ""}:${sender || ""}`;
}

const OWNER = Symbol("owner");
const DENIED = Symbol("denied");

export function createMembrain({ exec = membrain, directory } = {}) {
  const env = directory ? { MEMBRAIN_DIRECTORY: directory } : undefined;
  const prompts = new Map();  // session -> the current turn's prompt, dropped when the turn ends
  const users = new Map();  // Session aliases -> memory owner and canonical session, learned from the turn's hooks.
  const remember = (ctx) => {
    const user = memoryUser(ctx);
    for (const key of [ctx?.sessionKey, ctx?.sessionId]) {
      if (key) users.set(key, { user: user ?? OWNER, session: ctx?.sessionId || ctx?.sessionKey });
    }
    return user;
  };
  const confirmed = new Set();  // Memory users the installed runtime has confirmed it keeps apart.
  const hook = async (event, payload, user) => {
    const input = user ? { ...payload, membrain_user: user } : payload;
    const output = await exec(["hook", event, "--host", "openclaw"], { input, env });
    let parsed = {};
    try {
      parsed = output ? JSON.parse(output) : {};
    } catch {
      parsed = {};
    }
    // A runtime older than per-person memory ignores membrain_user and would use the owner's memory instead.
    if (user && parsed.membrainUser === user) confirmed.add(user);
    if (user && !confirmed.has(user)) return null;
    return parsed.hookSpecificOutput?.additionalContext || null;
  };
  return {
    async beforePromptBuild(event, ctx) {
      const session = ctx?.sessionId || ctx?.sessionKey;
      if (!session) return undefined;
      const user = remember(ctx);
      const block = await hook("session-start", { session_id: session }, user);
      if (user && !confirmed.has(user)) return undefined;  // Never record someone else into the owner's memory.
      const prompt = event?.currentUserMessage ?? event?.prompt ?? "";
      prompts.set(session, prompt);  // Kept in memory for this turn only, for a turn the agent resumes recording in.
      const recalled = prompt.trim()
        ? await hook("user-prompt", { session_id: session, prompt_id: event?.currentUserMessageId, prompt }, user)
        : null;
      const result = {};
      if (block) result.appendSystemContext = block;
      if (recalled) result.prependContext = recalled;
      return Object.keys(result).length ? result : undefined;
    },
    async agentEnd(event, ctx) {
      const session = ctx?.sessionId || ctx?.sessionKey;
      const reply = lastAssistantText(event?.messages);
      const prompt = session ? prompts.get(session) : undefined;
      if (session) prompts.delete(session);
      if (!session || !event?.success || !reply.trim()) return;
      const user = remember(ctx);
      if (user && !confirmed.has(user)) return;
      await hook("stop", { session_id: session, last_assistant_message: reply, prompt }, user);
    },
    // The memory a tool call in this conversation may use: DENIED when it cannot be told safely.
    toolUser(ctx) {
      for (const key of [ctx?.sessionKey, ctx?.sessionId]) {
        if (key && users.has(key)) return users.get(key).user;
      }
      return ctx?.messageChannel ? DENIED : OWNER;  // A local run with no channel is the owner.
    },
    toolSession(ctx) {
      for (const key of [ctx?.sessionKey, ctx?.sessionId]) {
        if (key && users.has(key)) return users.get(key).session;
      }
      return ctx?.sessionId || ctx?.sessionKey;
    },
    async tool(name, params, user = OWNER, session) {
      if (user === DENIED || (user !== OWNER && !confirmed.has(user))) {
        return JSON.stringify({ error: "memBrain tools are not available in this conversation." });
      }
      const input = user === OWNER ? (params ?? {}) : { ...(params ?? {}), membrain_user: user };
      const scoped = { ...input };
      if (name === "membrain_resume") {
        delete scoped.session_id;
        if (session) scoped.session_id = session;
      }
      const output = await exec(["tool", name.replace("membrain_", "")], { input: scoped, env,
        timeoutMs: 20_000 });
      return output || JSON.stringify({ error: "memBrain is not available yet; it may still be installing." });
    },
  };
}

function installRuntime(directory) {
  // Install or update the runtime and start the local service in the background, like the Claude Code plugin.
  run("uv", ["tool", "install", "--quiet", "--python", "3.12", PACKAGE], { timeoutMs: 15 * 60 * 1000 })
    .then(() => membrain(["start"], { timeoutMs: 10 * 60 * 1000,
      env: directory ? { MEMBRAIN_DIRECTORY: directory } : undefined }));
}

export function definePlugin({ install = installRuntime, exec } = {}) {
  return {
    id: "membrain",
    name: "memBrain",
    description: "Local long-term memory with notes, recall and recording.",
    register(api) {
      const directory = api.pluginConfig?.directory || undefined;
      const memory = createMembrain({ directory, ...(exec ? { exec } : {}) });
      install(directory);
      api.on("before_prompt_build", (event, ctx) => memory.beforePromptBuild(event, ctx));
      api.on("agent_end", (event, ctx) => memory.agentEnd(event, ctx));
      for (const spec of TOOLS) {
        // A factory, so each tool call is bound to the conversation (and so the memory) it came from.
        api.registerTool((ctx) => ({
          ...spec,
          label: spec.name,
          async execute(_id, params) {
            return { content: [{ type: "text", text: await memory.tool(spec.name, params, memory.toolUser(ctx),
              memory.toolSession(ctx)) }] };
          },
        }));
      }
    },
  };
}

export default definePlugin();
