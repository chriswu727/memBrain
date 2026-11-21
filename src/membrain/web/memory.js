// memBrain memory page: notes, conversations, search and privacy for one local installation.
const $ = (id) => document.getElementById(id);
const uid = () => crypto.randomUUID();
const HOST_NAMES = { "claude-code": "Claude Code", codex: "Codex", hermes: "Hermes", openclaw: "OpenClaw", workbuddy: "WorkBuddy" };
const NOTES = "membrain-notes";
const AFFECT = "membrain-affect";
const state = { key: "", brain: "", notes: [], connectionShown: false };
let messageTimer;
// /memory?demo=brain shows fictional data only (brain.js): no sign-in, no saved session read or changed, no API call.
const DEMO = new URLSearchParams(location.search).get("demo") === "brain";
// &show=1 opens the brain in showcase mode (showcase.js). Read now: the sign-in link's query is removed below.
const SHOWCASE = new URLSearchParams(location.search).get("show") === "1";

function notify(text, error = false) {
  clearTimeout(messageTimer);
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
  messageTimer = setTimeout(() => { $("message").textContent = ""; }, 6000);
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, body, method) {
  const response = await fetch(path, {
    method: method || (body === undefined ? "GET" : "POST"),
    headers: { Authorization: `Bearer ${state.key}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || ["rejected", "conflict", "failed"].includes(data.outcome)) {
    throw Object.assign(new Error(data.error?.message || data.detail || `Request failed (${response.status})`),
      { status: response.status });
  }
  return data;
}

function action(name, payload, conversation = "membrain-memory-page") {
  return api("/v1/actions", { message_type: "request", contract_version: "1.0.0-draft", request_id: uid(),
    action: name, target: { brain_ref: state.brain, conversation_ref: conversation, branch_ref: "main" }, payload });
}

function timeline(params) {
  const query = new URLSearchParams({ max_characters: "200000", max_item_characters: "20000", limit: "1000" });
  for (const [key, value] of Object.entries(params)) {
    if (["role", "event_id"].includes(key)) for (const item of [].concat(value)) query.append(key, item);
    else query.set(key, String(value));
  }
  return api(`/v1/brains/${encodeURIComponent(state.brain)}/timeline?${query}`);
}

async function scopeGeneration() {
  const data = await api(`/v1/brains/${encodeURIComponent(state.brain)}/dashboard`);
  return data.brain.scope_generation;
}

async function forget(kind, ids, mode, conversation) {
  return action("forget", { idempotency_key: uid(), selector: { kind, ids }, mode,
    expected_scope_generation: await scopeGeneration() }, conversation);
}

const day = (value) => (value || "").slice(0, 10) || "undated";

function guard(button, task) {
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    button.disabled = true;
    try { await task(); } catch (error) { notify(error.message, true); } finally { button.disabled = false; }
  });
}

function onSubmit(form, task) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const buttons = [...form.querySelectorAll("button")];
    buttons.forEach((button) => { button.disabled = true; });
    try { await task(); } catch (error) { notify(error.message, true); } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  });
}

const KINDS = ["person", "constraint", "preference", "plan", "routine", "milestone", "relationship", "agent_commitment", "other"];
const STATUSES = ["intended", "scheduled", "done", "cancelled", "superseded"];
// The kind of a shared moment, as the agent or the user judged it; the simulated mood reads it (notes.MOMENTS).
const MOMENTS = ["play", "hard", "other"];
const openPlan = (fields) => ["intended", "scheduled"].includes(fields.status || "intended");

function typedNote(text) {
  const match = /^\[([^\[\]]{1,200})\] ([\s\S]+)$/.exec(text || "");
  const tokens = match ? match[1].split(" · ") : [];
  const fields = {};
  if (!match || !KINDS.includes(tokens[0])) return { fields, tags: [], sentence: text };
  fields.kind = tokens[0];
  for (const token of tokens.slice(1)) {
    if (STATUSES.includes(token)) fields.status = token;
    else if (["pinned", "sensitive"].includes(token) || (token === "shared" && fields.kind === "milestone")) fields[token] = true;
    else if (/^(due|on) \d{4}-\d{2}(-\d{2})?$/.test(token)) fields[token.startsWith("due ") ? "due" : "occurs_at"] = token.split(" ")[1];
    else if (token.startsWith("about ")) fields.about = token.slice(6);
    else if (token.startsWith("aka ")) fields.aliases = token.slice(4).split(",").map((value) => value.trim());
    else if (MOMENTS.includes(token.slice(7)) && token.startsWith("moment ") && fields.shared) fields.moment = token.slice(7);
    else return { fields: {}, tags: [], sentence: text };
  }
  return { fields, tags: tokens.map((token) => token.replace("agent_commitment", "agent promise")), sentence: match[2] };
}

// What to say to the agent instead: the page has no form for memory content.
const EMPTY_NOTES = { notes: "No notes yet. Tell your agent what to remember, and it will keep it here.",
  people: "No people yet. When you tell your agent about someone, it keeps a note here.",
  plans: "No plans or dates yet. When you tell your agent about a plan or a date, it keeps a note here." };

async function loadNotes(view = "notes") {
  const response = await timeline({ role: ["assistant", "user"], conversation_id: NOTES });
  state.notes = response.items; state.notesComplete = response.complete;
  const list = $(view);
  list.replaceChildren();
  let items = state.notes;
  if (view === "people") items = items.filter((note) => typedNote(note.text).fields.kind === "person");
  if (view === "plans") items = items.filter((note) => {
    const fields = typedNote(note.text).fields;
    return ["plan", "agent_commitment", "milestone"].includes(fields.kind) && ($("show-completed").checked || openPlan(fields));
  });
  items = [...items].sort((a, b) => Number(Boolean(typedNote(b.text).fields.pinned)) - Number(Boolean(typedNote(a.text).fields.pinned)));
  if (!response.complete) list.append(element("p", "This is a partial list. Some older notes did not fit; use Search to find them.", "hint"));
  if (!items.length) list.append(element("p", EMPTY_NOTES[view], "empty"));
  for (const note of items) list.append(noteItem(note));
}

// The conversation a source message was said in, as the Conversations view names it: its first day, its size and
// how it began. Read when the sources are opened, one request per conversation.
async function conversationLabels(blocks) {
  const wanted = [...new Set(blocks.map(([message]) => message.conversation_id).filter(Boolean))];
  const labels = new Map();
  await Promise.all(wanted.map(async (conversation) => {
    try {
      const { items } = await timeline({ role: ["user", "assistant"], conversation_id: conversation });
      const messages = items.reverse();
      const first = messages.find((message) => message.actor_role === "user") || messages[0];
      if (first) labels.set(conversation, `${day(messages[0].recorded_at)} · ${messages.length} messages · ${first.text.slice(0, 90)}`);
    } catch { /* The message itself is still shown. */ }
  }));
  for (const [message, block] of blocks) {
    const label = labels.get(message.conversation_id);
    if (!label) continue;
    // Opens the Conversations view at this message, through the page's own address (goTo): a link, never an act.
    const link = element("a", `In the conversation: ${label}`, "source-conversation");
    if (message.conversation_id !== NOTES && ["user", "assistant"].includes(message.actor_role)) {
      link.href = `#message=${encodeURIComponent(message.event_id)}`;
    }
    const line = element("p", undefined, "hint");
    line.append(link);
    block.append(line);
  }
}

function sourceBlock(message) {
  const block = element("div", undefined, "message");
  block.append(element("div", `${day(message.recorded_at)} · ${message.actor_role === "user" ? "You" : "Agent"}`, "meta"), element("p", message.text, "user-text"));
  return block;
}

// ``earlier`` are the messages behind the notes this one replaced (read from those notes): the page shows them apart
// from the messages this note was said in, never as support for it.
async function showSources(container, ids, earlier = [], earlierNotes = 0) {
  container.replaceChildren(element("p", "Loading original messages…", "hint"));
  try {
    const wanted = [...new Set([...ids, ...earlier])];
    const { items } = await timeline({ role: ["user", "assistant", "operator", "tool"], event_id: wanted });
    container.replaceChildren();
    if (items.length < wanted.length) container.append(element("p", "Some original messages are no longer available.", "hint"));
    const messages = items.reverse(), blocks = [];
    const own = messages.filter((message) => !earlier.includes(message.event_id));
    const behind = messages.filter((message) => earlier.includes(message.event_id));
    if (earlier.length && own.length) {
      const days = [...new Set(own.map((message) => day(message.recorded_at)))];
      container.append(element("p", days.length === 1 ? `Said on ${days[0]}:` : "Said in these messages:", "hint source-role"));
    }
    for (const message of own) { const block = sourceBlock(message); blocks.push([message, block]); container.append(block); }
    if (behind.length) {
      container.append(element("p", earlierNotes > 1 ? "The earlier notes were based on:" : "The earlier note was based on:", "hint source-role"));
      for (const message of behind) { const block = sourceBlock(message); blocks.push([message, block]); container.append(block); }
    }
    await conversationLabels(blocks);
  } catch (error) { container.replaceChildren(element("p", error.message, "hint")); }
}

// "N original messages", opened on demand: where a note, a feeling or a shared moment came from.
function sourcesDetails(ids, earlier = [], earlierNotes = 0) {
  const count = new Set([...ids, ...earlier]).size;
  const details = element("details");
  details.append(element("summary", `${count} original message${count === 1 ? "" : "s"}`));
  const content = element("div"); details.append(content);
  let loaded = false;
  details.addEventListener("toggle", () => {
    if (details.open && !loaded) { loaded = true; showSources(content, ids, earlier, earlierNotes); }
  });
  return details;
}

// What a note replaced, read each time from the replaced notes themselves (the service returns them with the note,
// newest first): read-only, and erased with this note. An earlier note whose content was erased shows nothing of
// itself, neither sentence nor date; that this note replaced one is this note's own record.
function lineageBlock(note) {
  const earlier = note.replaced || [];
  if (!earlier.length) return null;
  const direct = earlier.filter((entry) => entry.depth === 1).length || 1;
  const block = element("div", undefined, "lineage");
  block.append(element("p", direct === 1 ? `Replaced an earlier note on ${day(note.recorded_at)}.`
    : `Replaced ${direct} earlier notes on ${day(note.recorded_at)}.`, "hint"));
  for (const entry of earlier.filter((value) => !value.erased)) {
    const row = element("p", undefined, "earlier");
    row.dataset.eventId = entry.event_id;
    row.append(element("span", `Earlier (${day(entry.recorded_at)}):`, "hint"), " ",
      element("span", typedNote(entry.text).sentence, "user-text"));
    block.append(row);
  }
  return block;
}

// A message a current note overruled (the service names that note, read from the records each time).
function supersededHint(message) {
  return message.superseded_by
    ? element("p", `Superseded by a note saved on ${day(message.superseded_by.recorded_at)}.`, "hint superseded") : null;
}

// What else a deletion erases, as the service reads it on request from the dependencies the erasure itself follows
// (``erased_with``): one line per record, named as the page shows it, so the question and the erasure cannot disagree.
const clip = (text, size = 100) => (text.length > size ? `${text.slice(0, size - 1)}…` : text);

function erasedLine(entry) {
  const when = day(entry.recorded_at);
  if (entry.kind === "note") return `${translate(`Note (${when}):`)} ${clip(typedNote(entry.text).sentence)}`;
  if (entry.kind === "earlier_note") return `${translate(`Earlier note (${when}):`)} ${clip(typedNote(entry.text).sentence)}`;
  if (entry.kind === "hidden_note") return `${translate(`Hidden note (${when}):`)} ${clip(typedNote(entry.text).sentence)}`;
  if (entry.kind === "feeling") return `${translate("Feeling:")} ${entry.label}${entry.topic ? ` · ${entry.topic}` : ""}`;
  if (entry.kind === "message") {
    return `${translate(entry.actor_role === "assistant" ? `Your agent's reply (${when}):` : `Message (${when}):`)} ${clip(entry.text)}`;
  }
  return translate(entry.kind === "suggestion" ? `Personality suggestion (${when})` : `Other record (${when})`);
}

// The question, then what goes with it. Without a list the question is translated whole, as every confirm is.
function deleteQuestion(question, entries, many = false) {
  if (!entries.length) return question;
  return `${translate(question)}\n\n${translate(many ? "Deleted with them:" : "Deleted with it:")}\n`
    + entries.map((entry) => `• ${erasedLine(entry)}`).join("\n");
}

// A record as it is now, with what deleting it would erase as well; null once it is gone.
async function erasureOf(id) {
  const { items } = await timeline({ role: ["user", "assistant"], event_id: [id], erasure: true });
  return items[0] || null;
}

// The question for deleting a note (a shared moment and a promise are notes too): what it replaced goes with it.
function noteQuestion(entries, question) {
  const earlier = entries.filter((entry) => entry.kind === "earlier_note").length;
  return deleteQuestion(question || (!earlier ? "Delete this note? Its content is erased."
    : earlier === 1 ? "Delete this note and the earlier note it replaced? Their content is erased."
      : "Delete this note and the earlier notes it replaced? Their content is erased."), entries);
}

// Deletes a note after asking, read again first so the question names what deleting it erases now: "deleted", or
// null when the user said no. A note deleted meanwhile is reported ("gone"), not deleted again.
async function deleteNote(id, done, question) {
  const fresh = await erasureOf(id);
  if (!fresh) { notify(GONE, true); return "gone"; }
  if (!confirm(noteQuestion(fresh.erased_with, question))) return null;
  await forget("events", [id], "erase_content", NOTES);
  notify(done);
  return "deleted";
}

// The same for a message of a conversation: the reply that answers it and the notes drawn from it go with it.
// The ids erased, or null when the user said no.
async function deleteMessage(message) {
  const fresh = await erasureOf(message.event_id);
  if (!fresh) { notify(GONE, true); return [message.event_id]; }
  if (!confirm(deleteQuestion("Delete this message? Its content is erased everywhere it was used.", fresh.erased_with))) return null;
  await forget("events", [message.event_id], "erase_content", message.conversation_id);
  notify("Message deleted.");
  return [message.event_id, ...fresh.erased_with.map((entry) => entry.event_id)];
}

// A link to a note by its address (goTo): it only opens the note, with its sources and what it replaced.
function noteLink(id, text, className = "note-link") {
  const link = element("a", text, className);
  link.href = `#note=${encodeURIComponent(id)}`;
  return link;
}

function messageLink(id, text = "Open in its conversation") {
  const link = element("a", text, "source-conversation");
  link.href = `#message=${encodeURIComponent(id)}`;
  return link;
}

// The notes that rest on a message (they are erased with it), each a link to the note.
function restsOn(message) {
  const notes = (message.erased_with || []).filter((entry) => entry.kind === "note");
  if (!notes.length) return null;
  const box = element("div", undefined, "rests-on");
  box.append(element("p", notes.length === 1 ? "A note rests on this message:" : `${notes.length} notes rest on this message:`, "hint"));
  for (const note of notes) {
    const line = element("p", undefined, "hint");
    line.append(noteLink(note.event_id, typedNote(note.text).sentence, "note-link user-text"));
    box.append(line);
  }
  return box;
}

function noteItem(note) {
  const item = element("article", undefined, "item");
  item.dataset.eventId = note.event_id;
  const parsed = typedNote(note.text), fields = parsed.fields;
  const meta = element("div", undefined, "meta");
  meta.append(element("span", day(note.recorded_at)));
  const imported = (note.producer || "").startsWith("membrain-import:") ? note.producer.slice(16) : null;
  meta.append(element("span", note.actor_role === "user" ? "written by you" : imported ? `imported from ${HOST_NAMES[imported] || imported}` : "saved by your agent", "tag"));
  for (const tag of parsed.tags) meta.append(element("span", tag, "tag"));
  const actions = element("span", undefined, "actions");
  const remove = element("button", "Delete", "link danger");
  actions.append(remove); meta.append(actions); item.append(meta, element("p", parsed.sentence, "user-text"));
  const date = fields.due || fields.occurs_at;
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  if (date && openPlan(fields) && date < (date.length === 7 ? today.slice(0, 7) : today)) item.append(element("p", "Date has passed; completion is not confirmed.", "hint"));
  const lineage = lineageBlock(note);
  if (lineage) item.append(lineage);
  // The messages behind the notes this one replaced stay linked to it so that deleting one reaches it, but they are
  // the earlier note's basis, not this one's.
  const earlier = [...new Set((note.replaced || []).flatMap((entry) => entry.source_event_ids || []))];
  const ids = (note.source_event_ids || []).filter((id) => !earlier.includes(id));
  if (note.pending_source_count) item.append(element("p", "Waiting for the source message to finish recording.", "hint"));
  if (ids.length || earlier.length) item.append(sourcesDetails(ids, earlier, (note.replaced || []).length));
  else if (!note.pending_source_count) item.append(element("p", note.actor_role === "user" ? "Standalone note written by you." : "Original message not linked.", "hint"));
  guard(remove, async () => {
    if (await deleteNote(note.event_id, "Note deleted.")) await show(currentView());
  });
  return item;
}

$("show-completed").addEventListener("change", () => loadNotes("plans"));

// Feelings ---------------------------------------------------------------------------------------------------

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const shortDate = (value) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || "");
  return match ? `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1]}` : day(value);
};

async function loadFeelings() {
  const { records, markers, complete } = await api(`/v1/brains/${encodeURIComponent(state.brain)}/affect`);
  const marker = markers[0];
  $("feelings-marker").hidden = !marker;
  $("feelings-marker").textContent = marker ? `Feelings cleared on ${shortDate(marker.recorded_at)}` : "";
  const list = $("feelings");
  list.replaceChildren();
  if (!complete) list.append(element("p", "This is a partial list of the most recent feelings.", "hint"));
  if (!records.length) list.append(element("p", "No feelings recorded. When you tell your agent how you feel about something, it can keep that with the note it belongs to.", "empty"));
  for (const record of records) list.append(feelingItem(record));
}

function feelingItem(record) {
  const item = element("article", undefined, "item feeling");
  const meta = element("div", undefined, "meta");
  meta.append(element("span", shortDate(record.felt_at)),
    element("span", record.basis === "reported" ? "you said" : "inferred", "tag feeling-basis"));
  if (record.sensitive) meta.append(element("span", "sensitive", "tag"));
  const actions = element("span", undefined, "actions");
  const remove = element("button", "Delete", "link danger");
  actions.append(remove); meta.append(actions);
  item.append(meta, element("p", record.label + (record.topic ? ` · ${record.topic}` : ""), "user-text"));
  item.append(element("p", record.basis === "reported" ? "You said you felt this."
    : "Your agent inferred this from what you wrote; you did not say it.", "hint"));
  const note = element("div", undefined, "feeling-note");
  note.append(element("p", "On the note:", "hint"), element("p", record.note_text, "user-text"));
  const open = element("p", undefined, "hint");
  open.append(noteLink(record.note_id, "Show the note"));
  note.append(open);
  item.append(note);
  const ids = record.source_event_ids || [];
  if (ids.length) item.append(sourcesDetails(ids));
  else item.append(element("p", "Original message not linked.", "hint"));
  guard(remove, async () => {
    if (!confirm("Delete this feeling? The note and its messages stay.")) return;
    await forget("events", [record.id], "erase_content", AFFECT); notify("Feeling deleted."); await loadFeelings();
  });
  return item;
}

guard($("clear-feelings"), async () => {
  if (!confirm("Clear every recorded feeling, said or inferred? Notes and messages stay, and feelings are not recreated from earlier messages.")) return;
  await api(`/v1/brains/${encodeURIComponent(state.brain)}/affect/reset`, {});
  notify("Feelings cleared."); await loadFeelings();
});
const currentView = () => $("tabs").querySelector("button.active")?.dataset.view || "notes";

// Conversations ----------------------------------------------------------------------------------------------

async function loadConversations(reset = true) {
  const response = await timeline({ role: ["user", "assistant"], limit: 100, erasure: true,
    ...(reset || !state.conversationCursor ? {} : { before_sequence: state.conversationCursor }) });
  state.conversations = reset ? response.items : [...state.conversations, ...response.items];
  state.conversationCursor = response.next_before_sequence;
  const items = state.conversations;
  const groups = new Map();
  for (const message of items) {
    if (message.conversation_id === NOTES) continue;
    if (!groups.has(message.conversation_id)) groups.set(message.conversation_id, []);
    groups.get(message.conversation_id).push(message);
  }
  const list = $("conversations");
  list.replaceChildren();
  if (!groups.size) {
    list.append(element("p", "No conversations recorded yet.", "empty"));
    return;
  }
  for (const [conversation, messages] of groups) list.append(conversationItem(conversation, messages.reverse()));
  if (state.conversationCursor) {
    const more = element("button", "Load older messages", "secondary");
    guard(more, () => loadConversations(false)); list.append(more);
  }
}

function conversationItem(conversation, messages) {
  const item = element("details", undefined, "item");
  item.dataset.conversation = conversation;
  const summary = element("summary");
  const first = messages.find((message) => message.actor_role === "user") || messages[0];
  summary.textContent = `${day(messages[0].recorded_at)} · ${messages.length} messages · ${first.text.slice(0, 90)}`;
  item.append(summary);
  for (const message of messages) {
    const block = element("div", undefined, `message ${message.actor_role}`);
    block.dataset.eventId = message.event_id;
    const meta = element("div", undefined, "meta");
    meta.append(element("span", message.actor_role === "user" ? "You" : "Agent"), element("span", day(message.recorded_at)));
    const remove = element("button", "Delete", "link danger");
    const actions = element("span", undefined, "actions");
    actions.append(remove);
    meta.append(actions);
    block.append(meta, element("p", message.text, "user-text"));
    const superseded = supersededHint(message);
    if (superseded) block.append(superseded);
    const notes = restsOn(message);
    if (notes) block.append(notes);
    guard(remove, async () => {
      const erased = await deleteMessage(message);
      // The reply that answered it goes with it, on the page too.
      for (const id of erased || []) itemsOf(item, ".message", id)?.remove();
    });
    item.append(block);
  }
  const removeAll = element("button", "Delete this conversation", "link danger");
  guard(removeAll, async () => {
    // Every message of the conversation, read again, with what rests on each; what lies inside it is not listed.
    const { items, complete } = await timeline({ role: ["user", "assistant"], conversation_id: conversation, erasure: true });
    const inside = new Set(items.map((message) => message.event_id));
    const entries = [...new Map(items.flatMap((message) => message.erased_with)
      .filter((entry) => !inside.has(entry.event_id)).map((entry) => [entry.event_id, entry])).values()];
    let question = deleteQuestion("Delete every message in this conversation?", entries, true);
    if (!complete) question = `${translate(question)}\n\n${translate("The conversation is too long to list everything here; what rests on its older messages is deleted too.")}`;
    if (!confirm(question)) return;
    await forget("conversation", [conversation], "erase_content", conversation);
    notify("Conversation deleted.");
    await loadConversations();
  });
  item.append(removeAll);
  return item;
}

// Search -----------------------------------------------------------------------------------------------------

onSubmit($("search-form"), async () => {
  const query = $("search-text").value.trim();
  const results = $("results");
  results.replaceChildren();
  const budget = { max_context_tokens: 16000, max_model_calls: 0, max_embedding_calls: 1, max_expansion_steps: 2,
    max_wall_time_ms: 5000, max_cost_microunits: 0, currency: "USD", token_counting: "conservative_estimate",
    tokenizer_id: null };
  const payload = { query, intent: "explore", cue_event_ids: [], additional_cues: [],
    read_fence: { minimum_durable_sequence: 0, consistency: "read_your_writes", snapshot_revision: null },
    evidence_cutoff: { mode: "through_sequence", through_sequence: 2 ** 53 } };
  let response;
  try {
    response = await action("recall", { ...payload, budget });
  } catch {
    response = await action("recall", { ...payload, budget: { ...budget, max_embedding_calls: 0 } });
  }
  const sources = [];
  for (const item of response.result.items) {
    for (const ref of item.memory.evidence_refs || []) {
      if (ref.relationship === "supports" && !sources.includes(ref.event_id)) sources.push(ref.event_id);
    }
  }
  if (!sources.length) {
    results.append(element("p", "Nothing found.", "empty"));
    return;
  }
  const { items } = await timeline({ role: ["user", "assistant"], event_id: sources.slice(0, 20), erasure: true });
  const byId = new Map(items.map((message) => [message.event_id, message]));
  for (const id of sources.slice(0, 20)) {
    const message = byId.get(id);
    if (!message) continue;
    const block = element("div", undefined, "item");
    block.dataset.eventId = message.event_id;
    const note = message.conversation_id === NOTES;
    const meta = element("div", undefined, "meta");
    meta.append(element("span", day(message.recorded_at)),
      element("span", note ? "note" : message.actor_role === "user" ? "You" : "Agent", "tag"));
    block.append(meta, element("p", message.text, "user-text"));
    const superseded = supersededHint(message);
    if (superseded) block.append(superseded);
    const notes = restsOn(message);
    if (notes) block.append(notes);
    // Where it was said, and Delete, as in its conversation (a note: as in Notes).
    const row = element("div", undefined, "row result-actions");
    const remove = element("button", "Delete", "link danger");
    row.append(note ? noteLink(message.event_id, "Show the note") : messageLink(message.event_id), remove);
    block.append(row);
    guard(remove, async () => {
      const erased = note ? (await deleteNote(message.event_id, "Note deleted.") ? [message.event_id] : null)
        : await deleteMessage(message);
      for (const gone of erased || []) itemsOf(results, ":scope > .item", gone)?.remove();
    });
    results.append(block);
  }
});

// Relationship -----------------------------------------------------------------------------------------------
// Shared moments (milestone notes flagged shared), derived familiarity with its reason, boundaries and the promise
// record. The service derives everything; the page shows it, with its sources, and deletes.

const relationshipPath = (suffix = "") => `/v1/brains/${encodeURIComponent(state.brain)}/relationship${suffix}`;
const LEVEL_NAMES = { new: "new", getting_to_know: "getting to know", familiar: "familiar", close: "close" };
const PROMISE_TAGS = { kept: "kept", missed: "missed", cancelled: "cancelled", open: "open" };

async function loadRelationship() {
  const data = await api(relationshipPath());
  state.relationship = data;
  const marker = data.markers?.[0];
  $("relationship-marker").hidden = !marker;
  $("relationship-marker").textContent = marker ? `Relationship reset on ${shortDate(marker.recorded_at)}` : "";
  const known = data.familiarity;
  const level = $("relationship-level");
  level.replaceChildren(element("strong", LEVEL_NAMES[known.level] || known.level, "tag"), element("span", known.reason));
  const next = known.next;
  $("relationship-next").textContent = !next ? ""
    : next.shared_moments ? `Next: ${LEVEL_NAMES[next.level]} at ${next.days} days and ${next.shared_moments} shared moment${next.shared_moments === 1 ? "" : "s"}.`
    : `Next: ${LEVEL_NAMES[next.level]} at ${next.days} days of conversation.`;
  const boundaries = $("boundaries");
  boundaries.replaceChildren();
  if (!data.boundaries.length) boundaries.append(element("p", "No boundaries.", "empty"));
  for (const boundary of data.boundaries) boundaries.append(boundaryItem(boundary));
  const moments = $("moments");
  moments.replaceChildren();
  if (!data.shared_moments.length) moments.append(element("p", "No shared moments yet. When you and your companion do something together, your agent can keep it here.", "empty"));
  if (data.shared_moments_truncated) moments.append(element("p", "Only the latest shared moments are listed; familiarity counts all retained moments.", "hint"));
  for (const moment of data.shared_moments) moments.append(momentItem(moment));
  const record = data.commitments;
  $("commitments-summary").textContent = `Kept: ${record.kept.length} · missed: ${record.missed.length} · cancelled: ${record.cancelled.length} · open: ${record.open.length}`;
  const promises = $("commitments");
  promises.replaceChildren();
  const listed = [...record.missed.map((item) => ["missed", item]), ...record.kept.map((item) => ["kept", item]),
    ...record.cancelled.map((item) => ["cancelled", item])];
  if (!listed.length) promises.append(element("p", "No kept or missed promises since the relationship began or was last reset.", "empty"));
  for (const [kind, item] of listed) promises.append(promiseItem(kind, item));
}

function boundaryItem(boundary) {
  const item = element("article", undefined, "item relationship-boundary");
  const meta = element("div", undefined, "meta");
  meta.append(element("span", day(boundary.recorded_at)));
  const actions = element("span", undefined, "actions");
  const remove = element("button", "Remove", "link danger");
  actions.append(remove); meta.append(actions);
  item.append(meta, element("p", boundary.topic, "user-text"));
  if (boundary.aliases.length) item.append(element("p", `also: ${boundary.aliases.join(", ")}`, "hint"));
  item.append(element("p", "Original message not linked.", "hint"));
  guard(remove, async () => {
    if (!confirm("Remove this boundary? Your companion may bring the topic up again, and earlier messages about it are recalled normally.")) return;
    await api(relationshipPath(`/boundaries/${encodeURIComponent(boundary.id)}`), undefined, "DELETE");
    notify("Boundary removed."); await loadRelationship();
  });
  return item;
}

function momentItem(moment) {
  const item = element("article", undefined, "item relationship-moment");
  const meta = element("div", undefined, "meta");
  meta.append(element("span", shortDate(moment.occurs_at || moment.recorded_at)));
  if (moment.written_by_user) meta.append(element("span", "written by you", "tag"));
  if (moment.sensitive) meta.append(element("span", "sensitive", "tag"));
  if (moment.moment === "hard") meta.append(element("span", moment.mellowed ? "a hard time, mellowed since" : "a hard time", "tag"));
  const actions = element("span", undefined, "actions");
  const remove = element("button", "Delete", "link danger");
  actions.append(remove); meta.append(actions);
  item.append(meta, element("p", moment.text, "user-text"));
  if (moment.source_event_ids?.length) item.append(sourcesDetails(moment.source_event_ids));
  item.append(noteLine(moment.id));
  guard(remove, async () => {
    if (await deleteNote(moment.id, "Shared moment deleted.", "Delete this shared moment? Its note is erased.")) await loadRelationship();
  });
  return item;
}

function noteLine(id) {
  const line = element("p", undefined, "hint");
  line.append(noteLink(id, "Show the note"));
  return line;
}

// A promise is an agent_commitment note: its messages, the note itself (in Notes and in Plans and dates) and Delete.
function promiseItem(kind, promise) {
  const item = element("article", undefined, "item relationship-promise");
  const meta = element("div", undefined, "meta");
  meta.append(element("span", PROMISE_TAGS[kind], kind === "missed" ? "tag relationship-missed" : "tag"));
  if (promise.due) meta.append(element("span", `due ${promise.due}`, "tag"));
  if (kind === "missed") meta.append(element("span", promise.acknowledged ? "shown to your agent" : "not shown yet", "tag"));
  const actions = element("span", undefined, "actions");
  const remove = element("button", "Delete", "link danger");
  actions.append(remove); meta.append(actions);
  item.append(meta, element("p", promise.text, "user-text"));
  const ids = promise.source_event_ids || [];
  item.append(ids.length ? sourcesDetails(ids) : element("p", "Original message not linked.", "hint"), noteLine(promise.note_id));
  guard(remove, async () => {
    if (await deleteNote(promise.note_id, "Promise deleted.", "Delete this promise? Its note is erased.")) await loadRelationship();
  });
  return item;
}

// What the given records' deletion erases as well, read in batches the timeline accepts; the records themselves are
// not listed.
async function erasedWithAll(ids) {
  const found = new Map(), own = new Set(ids);
  for (let start = 0; start < ids.length; start += 100) {
    const { items } = await timeline({ role: ["user", "assistant"], event_id: ids.slice(start, start + 100), erasure: true });
    for (const entry of items.flatMap((item) => item.erased_with)) if (!own.has(entry.event_id)) found.set(entry.event_id, entry);
  }
  return [...found.values()];
}

guard($("relationship-reset"), async () => {
  const data = await api(relationshipPath());
  const entries = await erasedWithAll(data.shared_moments.map((moment) => moment.id));
  if (!confirm(deleteQuestion(entries.length
    ? "Reset the relationship? This deletes every shared moment and the record of promises kept and missed. Familiarity starts again at new and counts only days from now. The boundaries stay in force, so those topics are still kept out; remove a boundary on its own if you want. Conversations, your other notes, the personality and the feelings not listed below stay."
    : "Reset the relationship? This deletes every shared moment and the record of promises kept and missed. Familiarity starts again at new and counts only days from now. The boundaries stay in force, so those topics are still kept out; remove a boundary on its own if you want. Conversations, your other notes, the personality and feelings stay.",
  entries, true))) return;
  await api(relationshipPath("/reset"), {});
  notify("Relationship reset."); await loadRelationship();
});

// Personality ------------------------------------------------------------------------------------------------
// The companion's persona card, versioned by the service. The page has no card editor: the user asks their agent
// for a change. Restoring a version and switching the type save a new version, so nothing is lost until "Delete
// personality history".

const personaPath = (suffix = "") => `/v1/brains/${encodeURIComponent(state.brain)}/persona${suffix}`;
const VOICE = [["register", "register"], ["length", "length"], ["emoji", "emoji"], ["language", "language"]];
const MADE_BY = { user: "set by you", host: "set by the host", feedback: "from accepted feedback" };
// Preset personas: which one is current, and switching to another. The labels and summaries are the service's own.
const PRESET_KIND = { preset: "Personality type:", custom: "Your own card", none: "No personality type" };

function personaRows(card) {
  const rows = [];
  if (card.name) rows.push(["Name", card.name]);
  if (card.traits?.length) rows.push(["Traits", card.traits.join("; ")]);
  const voice = VOICE.filter(([name]) => card.voice?.[name]).map(([name, label]) => [label, card.voice[name]]);
  if (voice.length) rows.push(["Voice", voice]);
  if (card.values?.length) rows.push(["Values", card.values.join("; ")]);
  if (card.boundaries?.length) rows.push(["Boundaries", card.boundaries.join("; ")]);
  const mood = card.baseline_mood;
  if (mood) rows.push(["Baseline mood", { label: mood.label, scale: `(valence ${mood.valence > 0 ? "+" : ""}${mood.valence}, energy ${mood.energy} of 3)` }]);
  return rows;
}

function personaCard(card) {
  const list = element("dl", undefined, "persona-card");
  for (const [label, value] of personaRows(card)) {
    const term = element("dt", label), detail = element("dd");
    if (Array.isArray(value)) {
      for (const [name, text] of value) {
        const part = element("span", undefined, "persona-part");
        part.append(element("span", name, "hint"), element("span", text, "user-text"));
        detail.append(part);
      }
    } else if (typeof value === "object") detail.append(element("span", value.label, "user-text"), element("span", value.scale, "hint"));
    else detail.append(element("span", value, "user-text"));
    list.append(term, detail);
  }
  return list;
}

// What the user agreed with their agent (an accepted suggestion, a change they confirmed) is kept across personality
// types. The service gives each version its agreements and its card without them, so an agreement carried over is
// shown apart from the card and never looks like part of the type.
function personaAgreements(agreements) {
  const box = element("div", undefined, "persona-agreements");
  box.append(element("p", "Kept from what you agreed with your agent, whatever the personality type:", "hint"));
  for (const agreement of agreements) {
    const item = element("div", undefined, "persona-agreement");
    item.append(element("p", agreement.source === "feedback"
      ? `From version ${agreement.version}: a suggestion you accepted`
      : `From version ${agreement.version}: a change your agent suggested and you agreed to`, "hint"),
    personaCard(agreement.changes));
    // The messages it rests on, from those that still exist: the user's yes, or the feedback they accepted.
    if (agreement.said_in?.length) item.append(saidIn(agreement.source === "feedback" ? "What you said:" : "Where you agreed:", agreement.said_in));
    box.append(item);
  }
  return box;
}

// User messages quoted as links to where they were said.
function saidIn(label, messages) {
  const box = element("div", undefined, "persona-said-in");
  box.append(element("p", label, "hint"));
  const list = element("ul", "", "persona-said-quotes");
  for (const message of messages) {
    const row = element("li", "");
    row.append(messageLink(message.event_id, `“${message.text}”`), element("span", ` ${day(message.recorded_at)}`, "hint"));
    row.firstChild.classList.add("user-text");
    list.append(row);
  }
  box.append(list);
  return box;
}

function personaContent(version) {
  const agreements = version.agreements || [];
  const card = agreements.length ? version.base_card : version.card;
  const parts = [personaRows(card).length ? personaCard(card) : element("p", "No card.", "hint")];
  if (agreements.length) parts.push(personaAgreements(agreements));
  return parts;
}

function personaHistory(version) {
  if (version.action === "preset") return version.made_by === "host" ? "first type, picked at random" : "switched type";
  if (version.action === "proposal") {
    return version.host_proposal?.confirmed_by ? "your agent's suggestion, confirmed in conversation" : "your agent's suggestion, accepted here";
  }
  if (version.action === "restore" && version.restored_from) return `restored from version ${version.restored_from}`;
  if (version.action === "reset") return version.empty ? "reset to no card" : "reset to the host's default";
  if (version.action === "feedback") return "accepted suggestion"; // P2: the reason quotes the feedback.
  return version.host_default ? "host default" : "edited";
}

function personaPresets(listing) {
  const current = listing.current, line = $("persona-preset");
  line.replaceChildren(element("span", PRESET_KIND[current.kind], "hint"));
  // The label is the four-letter code, the same in every language; the summary is translated.
  if (current.kind === "preset") line.append(" ", element("strong", current.preset.label), " ", element("span", current.preset.summary, "hint"));
  if (current.kind === "custom" && current.based_on) line.append(" ", element("span", "based on", "hint"), " ", element("strong", current.based_on.label));
  const choice = $("persona-preset-choice");
  choice.replaceChildren(...listing.presets.map((item) => {
    const option = element("option", item.label);
    option.title = item.summary;
    option.value = item.id;
    return option;
  }));
  if (current.kind === "preset") choice.value = current.preset.id;
}

async function loadPersona() {
  const [current, history, presets] = await Promise.all([api(personaPath()), api(personaPath("/versions")),
    api(personaPath("/presets"))]);
  state.persona = current;
  personaPresets(presets);
  $("persona-version").textContent = current.version ? `Version ${current.version}` : "No versions yet";
  const view = $("persona-view");
  const listed = history.versions.find((version) => version.version === current.version);
  view.replaceChildren(...(current.empty
    ? [element("p", "No personality card is set. Your agent keeps its usual manner.", "empty")]
    : listed ? personaContent(listed) : [personaCard(current.card)]));
  const list = $("persona-versions");
  list.replaceChildren();
  if (!history.versions.length) list.append(element("p", "No versions yet. Switch to a personality type, or ask your agent for a change, to save the first one.", "empty"));
  if (!history.complete) list.append(element("p", "Only the most recent versions are listed.", "hint"));
  for (const version of history.versions) list.append(personaVersion(version, version.version === history.current_version));
  // Every version older than a "history deleted" marker was erased, so the marker always comes last.
  for (const marker of history.markers || []) {
    const item = element("article", undefined, "item persona-marker");
    item.append(element("p", `History deleted on ${day(marker.recorded_at)}`, "hint"));
    list.append(item);
  }
  // The baseline mood comes from the card, and a suggestion (P2) is withdrawn once the card already has it.
  await Promise.all([loadMood(), loadProposals()]);
}

function personaVersion(version, current) {
  const item = element("article", undefined, "item persona-version");
  const meta = element("div", undefined, "meta");
  meta.append(element("strong", `Version ${version.version}`), element("span", day(version.recorded_at)),
    element("span", MADE_BY[version.made_by] || version.made_by, "tag"), element("span", personaHistory(version), "tag"));
  if (current) meta.append(element("span", "current", "tag persona-current-tag"));
  const actions = element("span", undefined, "actions");
  if (!current) {
    const restore = element("button", "Restore", "link");
    guard(restore, async () => {
      if (!confirm(`Restore version ${version.version}? Its content becomes a new version.`)) return;
      const saved = await api(personaPath("/restore"), { version: version.version, made_by: "user" });
      notify(saved.unchanged ? "No change: that is already the current card." : `Saved as version ${saved.version}.`);
      await loadPersona();
    });
    actions.append(restore);
  }
  meta.append(actions);
  item.append(meta);
  if (version.reason) item.append(element("p", version.reason, version.feedback ? "hint" : "user-text"));
  // The user's message this version was made in (a "yes" to the agent's suggestion, or a switch asked for in
  // conversation), from the message as it is now; a deleted one is never shown.
  if (version.asked_in?.event_id) {
    item.append(saidIn(version.action === "proposal" ? "Where you agreed:" : "Where you asked for it:", [version.asked_in]));
  } else if (version.asked_in?.deleted) item.append(element("p", "The message behind this change is no longer in memory.", "hint"));
  if (version.feedback) {
    // P2: the feedback is quoted from the messages that still exist; a deleted message is never shown.
    const quotes = element("ul", "", "persona-feedback-quotes");
    for (const message of version.feedback_messages || []) {
      const row = element("li", "");
      row.append(messageLink(message.event_id, `“${message.text}”`), element("span", ` ${String(message.recorded_at).slice(0, 10)}`, "hint"));
      row.firstChild.classList.add("user-text");
      quotes.append(row);
    }
    if (!(version.feedback_messages || []).length) quotes.append(element("li", "The messages behind this change were deleted.", "hint"));
    item.append(quotes);
  }
  item.append(...(version.empty ? [element("p", "No card.", "hint")] : personaContent(version)));
  return item;
}

async function switchType(preset) {
  const saved = await api(personaPath("/preset"), { preset, made_by: "user" });
  notify(saved.unchanged ? "No change: that is already the current card." : `Saved as version ${saved.version}.`);
  await loadPersona();
}
guard($("persona-preset-switch"), async () => {
  if (!confirm("Switch to this personality type? It is saved as a new version, and earlier versions can be restored. The mood, familiarity and what you agreed with your agent carry over.")) return;
  await switchType($("persona-preset-choice").value);
});
// Picking again: a different type at random (the owner's meaning of resetting the personality).
guard($("persona-random"), async () => {
  if (!confirm("Pick another personality type at random? It is saved as a new version, and earlier versions can be restored. The mood, familiarity and what you agreed with your agent carry over.")) return;
  await switchType("random");
});
// An agreement in one line, for a question: each part of the card it changed.
function agreementText(agreement) {
  return personaRows(agreement.changes).map(([label, value]) => `${translate(label)}: ${Array.isArray(value)
    ? value.map(([name, text]) => `${translate(name)} ${text}`).join("; ") : typeof value === "object" ? value.label : value}`).join("; ");
}

guard($("persona-delete-history"), async () => {
  // What goes with the versions, read again: the agreements in force (they are kept in the versions) and every
  // suggestion, decided or waiting.
  const [history, listing] = await Promise.all([api(personaPath("/versions")), api(personaPath("/proposals"))]);
  const lines = (history.agreements || []).map((agreement) => `• ${translate(`Agreed with your agent in version ${agreement.version}:`)} ${clip(agreementText(agreement), 160)}`);
  const count = listing.proposals.length;
  if (count) lines.push(`• ${translate(count === 1 ? "1 suggestion" : `${count} suggestions`)}`);
  const question = "Delete every personality version, including the current card? This cannot be undone.";
  if (!confirm(lines.length ? `${translate(question)}\n\n${translate("Deleted with them:")}\n${lines.join("\n")}` : question)) return;
  await api(personaPath("/versions"), undefined, "DELETE");
  notify("Personality history deleted.");
  await loadPersona();
});

// Persona suggestions from feedback (P2) -------------------------------------------------------------------------
// The service makes a suggestion when the user gives the same kind of feedback three times. The page lists it with
// the quoted messages and the change to the card; only Accept changes the card, as a new version.
const PROPOSAL_KINDS = { less_formal: "More casual", more_formal: "More formal", more_playful: "More playful",
  shorter: "Shorter replies", longer: "Longer, more detailed replies", less_emoji: "Fewer emoji", more_emoji: "More emoji",
  host: "Suggested by your agent" };
const PROPOSAL_FIELDS = { traits: "Traits", "voice.register": "Register", "voice.length": "Typical length",
  "voice.emoji": "Emoji use", "voice.language": "Language", name: "Name", values: "Values", boundaries: "Boundaries",
  baseline_mood: "Baseline mood" };
const PROPOSAL_STATUS = { open: "waiting for you", accepted: "accepted", rejected: "rejected", withdrawn: "withdrawn" };
const PROPOSAL_WITHDRAWN = { source_unavailable: "Withdrawn: a cited message was changed or removed. Ask your agent for a fresh suggestion.",
  sources_removed: "Withdrawn: fewer than three of its messages are still in memory.",
  already_in_card: "Withdrawn: the card already has this.", does_not_fit: "Withdrawn: the card has no room for it.",
  feedback_used: "Withdrawn: you already decided on this feedback. A new suggestion needs new feedback.",
  contradicted: "Withdrawn: you later asked for the opposite.",
  replaced: "Withdrawn: your agent made a newer suggestion.", persona_changed: "Withdrawn: the card changed after it was suggested." };
// A baseline mood is shown as one value, as the card shows it.
const proposalText = (value) => (value && typeof value === "object" && !Array.isArray(value)
  ? `${value.label} (${value.valence > 0 ? "+" : ""}${value.valence}, ${value.energy})` : value);

function proposalValue(values, other, mark) {
  // One side of the change: list entries the other side lacks are marked; an empty value reads "(empty)".
  const box = element("span", undefined, "proposal-side");
  const items = Array.isArray(values) ? values : [values].filter(Boolean);
  if (!items.length) box.append(element("span", "(empty)", "hint"));
  items.forEach((text, index) => {
    if (index) box.append(element("span", "; ", "hint"));
    const changed = !Array.isArray(values) || !other.includes(text);
    box.append(changed ? element(mark, text, "user-text") : element("span", text, "user-text"));
  });
  return box;
}

// What a change takes off the card and what it puts on, read from its before and after: list entries one by one, a
// single value (a voice field, the name, the mood) as a whole. A replacement is one change with both.
function proposalParts(change) {
  const before = Array.isArray(change.before) ? change.before : [proposalText(change.before)].filter(Boolean);
  const after = Array.isArray(change.after) ? change.after : [proposalText(change.after)].filter(Boolean);
  return { removed: before.filter((text) => !after.includes(text)), added: after.filter((text) => !before.includes(text)) };
}

function proposalPlain(label, items, kind) {
  const line = element("p", undefined, `proposal-plain proposal-${kind}`);
  line.append(element("span", label, "hint"), " ");
  items.forEach((text, index) => {
    if (index) line.append(element("span", "; ", "hint"));
    line.append(element("span", text, "user-text"));
  });
  return line;
}

function proposalChange(change) {
  const parts = proposalParts(change);
  change = { ...change, before: proposalText(change.before), after: proposalText(change.after) };
  const list = element("dl", undefined, "persona-card proposal-diff");
  const detail = element("dd");
  const before = Array.isArray(change.before) ? change.before : [change.before].filter(Boolean);
  const after = Array.isArray(change.after) ? change.after : [change.after].filter(Boolean);
  detail.append(proposalValue(change.before, after, "del"), element("span", "→", "proposal-arrow"),
    proposalValue(change.after, before, "ins"));
  // Said plainly as well: what goes and what comes.
  if (parts.removed.length) detail.append(proposalPlain("Removes:", parts.removed, "removes"));
  if (parts.added.length) detail.append(proposalPlain("Adds:", parts.added, "adds"));
  list.append(element("dt", PROPOSAL_FIELDS[change.field] || change.field), detail);
  return list;
}

// Whether accepting takes something off the card: a list entry removed, or a value cleared. A replaced value is not
// a removal: the new one is what the user agrees to.
const proposalRemoves = (changes) => changes.some((change) => {
  const parts = proposalParts(change);
  return parts.removed.length && (Array.isArray(change.after) || !parts.added.length);
});

function proposalSources(proposal) {
  const box = element("div", undefined, "proposal-sources");
  box.append(element("p", "What you said:", "hint"));
  const list = element("ul");
  for (const source of proposal.sources) {
    const line = element("li");
    const quote = element("q", source.text, "user-text");
    const link = messageLink(source.event_id, "");
    link.append(quote);
    line.append(link, element("span", shortDate(source.recorded_at), "hint"));
    list.append(line);
  }
  box.append(list);
  return box;
}

function proposalItem(proposal) {
  const item = element("article", undefined, `item persona-proposal proposal-${proposal.status}`);
  const meta = element("div", undefined, "meta");
  const host = proposal.kind === "host";  // Proposed by the host AI; the user may also confirm it in conversation.
  meta.append(element("strong", host ? PROPOSAL_KINDS.host : `${PROPOSAL_KINDS[proposal.kind] || proposal.kind}: from ${proposal.source_count} messages`),
    element("span", shortDate(proposal.proposed_at)), element("span", PROPOSAL_STATUS[proposal.status] || proposal.status, "tag"));
  item.append(meta);
  if (host && proposal.reason) item.append(element("p", "Why, in your agent's words:", "hint"), element("p", proposal.reason, "user-text"));
  if (proposal.status === "open" && proposal.change) {
    item.append(element("p", "Change to the card (everything else stays):", "hint"), proposalChange(proposal.change));
  }
  if (proposal.status === "open" && proposal.changes?.length) {
    item.append(element("p", "Change to the card (everything else stays):", "hint"), ...proposal.changes.map(proposalChange));
    // A removal changes this card only; it is not carried to another personality type as an agreement is.
    if (proposalRemoves(proposal.changes)) {
      item.append(element("p", "This changes the current card only. Switching type later starts from that type's own card plus what you agreed with your agent.", "hint proposal-removal-note"));
    }
  }
  if (proposal.status === "accepted") item.append(element("p", `Accepted on ${shortDate(proposal.decided_at)} as version ${proposal.version}.`, "hint"));
  if (proposal.status === "rejected") {
    item.append(element("p", proposal.paused_until ? `Rejected on ${shortDate(proposal.decided_at)}. None of this kind until ${shortDate(proposal.paused_until)}.`
      : `Rejected on ${shortDate(proposal.decided_at)}.`, "hint"));
  }
  if (proposal.status === "withdrawn") item.append(element("p", PROPOSAL_WITHDRAWN[proposal.withdrawn_because] || "Withdrawn.", "hint"));
  if (host && proposal.evidence?.status === "pending") item.append(element("p", "Waiting for the source message to finish recording.", "hint"));
  if (host && proposal.evidence?.status === "not_cited") item.append(element("p", "Your agent cited no source messages for this suggestion.", "hint"));
  if (host && proposal.evidence?.status === "unavailable" && proposal.status !== "withdrawn") item.append(element("p", "Some original evidence is no longer available. Your earlier decision is unchanged.", "hint"));
  if (proposal.sources.length) item.append(proposalSources(proposal));
  if (proposal.status === "open") {
    const actions = element("div", undefined, "row persona-actions");
    const accept = element("button", "Accept"), reject = element("button", "Reject", "secondary");
    guard(accept, async () => {
      if (!confirm("Accept this suggestion? The card is saved as a new version; you can restore the earlier one at any time.")) return;
      const result = await api(personaPath(`/proposals/${encodeURIComponent(proposal.id)}/accept`), {});
      notify(`Saved as version ${result.persona.version}.`);
      await loadPersona();
    });
    guard(reject, async () => {
      if (!confirm(host ? "Reject this suggestion?" : "Reject this suggestion? None of the same kind is offered again for 30 days.")) return;
      await api(personaPath(`/proposals/${encodeURIComponent(proposal.id)}/reject`), {});
      notify(host ? "Suggestion rejected." : "Suggestion rejected. None of this kind for 30 days.");
      await loadProposals();
    });
    if (host && proposal.evidence?.status === "pending") accept.disabled = true;
    actions.append(accept, reject);
    item.append(actions);
  }
  return item;
}

async function loadProposals() {
  const listing = await api(personaPath("/proposals"));
  const open = listing.proposals.filter((proposal) => proposal.status === "open");
  const earlier = listing.proposals.filter((proposal) => proposal.status !== "open");
  $("persona-proposals-open").hidden = !open.length;
  $("persona-proposals-open").textContent = open.length ? `${open.length} waiting` : "";
  const list = $("persona-proposals");
  list.replaceChildren();
  if (!open.length) list.append(element("p", "No suggestions waiting.", "empty"));
  for (const proposal of open) list.append(proposalItem(proposal));
  for (const pause of listing.pauses) {
    list.append(element("p", `${PROPOSAL_KINDS[pause.kind] || pause.kind}: paused until ${shortDate(pause.until)} after you rejected it.`, "hint"));
  }
  $("persona-proposals-earlier").hidden = !earlier.length;
  $("persona-proposals-history").replaceChildren(...earlier.map(proposalItem));
}
// End of persona suggestions

// Companion mood (M1) ----------------------------------------------------------------------------------------
// A simulated short-term mood the service derives from stored events; the page reads it, pins it or resets it.
const moodPath = (suffix = "") => `/v1/brains/${encodeURIComponent(state.brain)}/mood${suffix}`;
const MOOD_LABELS = { glad: "Glad", concerned: "Concerned", playful: "Playful", calm: "Calm", wistful: "Wistful" };
const MOOD_RULES = { reported_good_news: "Good news you shared", inferred_good_news: "Good news, inferred",
  plan_done: "A plan noted done", reported_distress: "Something hard you shared",
  inferred_distress: "Something hard, inferred", shared_play: "A shared joke",
  shared_moment: "A moment you shared" };
const MOOD_STATUS = { active: "active", ended: "back at baseline", pinned: "ignored while pinned",
  superseded: "replaced by a later feeling about the same thing" };
const two = (value) => String(value).padStart(2, "0");
function moodTime(value) {
  const moment = new Date(value);
  return `${moment.getDate()} ${MONTHS[moment.getMonth()]} ${two(moment.getHours())}:${two(moment.getMinutes())}`;
}

function moodLabel(mood) {
  // A baseline named on the personality card is the user's or host's own word; the table's labels are translated.
  if (mood.at_baseline && mood.baseline.source === "persona") return element("span", mood.label, "tag user-text");
  return element("span", MOOD_LABELS[mood.label] || mood.label, "tag");
}

function moodSource(trigger) {
  const source = trigger.source || {};
  const box = element("div", undefined, "feeling-note");
  if (source.kind === "affect") {
    box.append(element("p", source.basis === "reported" ? "You said you felt" : "Your agent inferred you seemed", "hint"),
      element("p", source.label + (source.topic ? ` · ${source.topic}` : ""), "user-text"));
    if (source.basis !== "reported") box.append(element("p", "You did not say it.", "hint"));
  }
  if (source.note_text) box.append(element("p", "On the note:", "hint"), element("p", source.note_text, "user-text"));
  if (source.source_event_ids?.length) box.append(sourcesDetails(source.source_event_ids));
  if (source.note_id) box.append(noteLine(source.note_id));
  return box;
}

function moodTrigger(trigger) {
  const item = element("article", undefined, "item mood-trigger");
  const meta = element("div", undefined, "meta");
  meta.append(element("span", moodTime(trigger.at)), element("span", MOOD_RULES[trigger.rule] || trigger.rule, "tag"),
    element("span", MOOD_STATUS[trigger.status] || trigger.status, `tag mood-${trigger.status}`));
  item.append(meta, moodSource(trigger));
  return item;
}

async function loadMood() {
  const mood = await api(moodPath());
  state.mood = mood;
  const now = $("mood-now");
  now.replaceChildren(moodLabel(mood));
  if (mood.easing) now.append(element("span", "easing", "hint"));
  const why = $("mood-why");
  why.replaceChildren();
  if (mood.pinned) why.append(element("p", "Pinned to its baseline: no trigger changes it until you lift the pin.", "hint"));
  else if (mood.at_baseline) why.append(element("p", "At its baseline. Nothing has moved it since it last came back.", "hint"));
  else {
    const main = mood.triggers.find((trigger) => trigger.id === mood.trigger_id);
    why.append(element("p", `Since ${moodTime(mood.since)}`, "hint"));
    if (main) why.append(element("p", MOOD_RULES[main.rule] || main.rule, "mood-rule"), moodSource(main));
  }
  $("mood-return").hidden = !mood.back_at_baseline_at;
  $("mood-return").textContent = mood.back_at_baseline_at ? `Back at its baseline by ${moodTime(mood.back_at_baseline_at)}` : "";
  $("mood-marker").hidden = !mood.marker;
  $("mood-marker").textContent = mood.marker ? `Mood reset on ${shortDate(mood.marker.recorded_at)}` : "";
  $("mood-pin").checked = mood.pinned;
  const list = $("mood-triggers");
  list.replaceChildren();
  if (!mood.triggers.length) list.append(element("p", "No triggers yet.", "empty"));
  if (!mood.complete_history) list.append(element("p", "Only the most recent triggers are listed.", "hint"));
  for (const trigger of mood.triggers) list.append(moodTrigger(trigger));
}

$("mood-pin").addEventListener("change", async () => {
  const pin = $("mood-pin");
  pin.disabled = true;
  try {
    await api(moodPath("/pin"), { pinned: pin.checked });
    notify(pin.checked ? "Mood pinned to its baseline." : "Mood pin lifted.");
    await loadMood();
  } catch (error) { notify(error.message, true); pin.checked = !pin.checked; } finally { pin.disabled = false; }
});
guard($("mood-reset"), async () => {
  if (!confirm("Put the mood back at its baseline and forget its triggers? Feelings, notes and the personality are not touched, and events before now never change the mood again.")) return;
  await api(moodPath("/reset"), {});
  notify("Mood reset."); await loadMood();
});
// End of companion mood

// Privacy ----------------------------------------------------------------------------------------------------

let recordingState = null;
let recordingRead = 0;

async function loadRecording() {
  const request = ++recordingRead;
  const brain = state.brain;
  try {
    let result;
    try {
      result = await api(`/v1/local/recording?brain_id=${encodeURIComponent(brain)}`);
    } catch (error) {
      if (error.status !== 404) throw error;
      result = { server: await api(`/v1/brains/${encodeURIComponent(brain)}/recording`), local: null };
    }
    if (request !== recordingRead || brain !== state.brain) return;
    recordingState = { ...result, brain };
    const serverPaused = result.server.paused;
    const localPaused = result.local?.paused;
    // A pause a host conversation asked for lists the host conversations active when it was set; it is not a
    // pause of the device.
    const hostConversation = localPaused && result.local.scope === "conversations";
    $("recording").hidden = false;
    $("recording").textContent = serverPaused ? "Recording paused" : hostConversation ? "Host conversation paused"
      : localPaused ? "Device capture paused" : "Recording on";
    $("recording").classList.toggle("paused", serverPaused || localPaused);
    $("recording-text").textContent = serverPaused
      ? "New messages and notes are paused for this memory. Earlier memory stays available."
      : hostConversation ? "Memory accepts writes. A local pause covers existing host conversations on this device; it is not a pause of device capture."
      : localPaused ? "Memory accepts writes, but chat capture is paused on this device."
        : "Memory accepts new messages and notes. Conversation-specific pauses still apply.";
    $("recording-actions").hidden = false;
    $("pause").hidden = serverPaused;
    $("resume").hidden = !serverPaused;
    $("local-recording").hidden = !result.local;
    $("local-recording-text").textContent = hostConversation
      ? "A host conversation asked not to be recorded. This pause covers the host conversations that were active when it was set."
      : localPaused ? "Chat capture is paused on this device." : "Chat capture is enabled on this device.";
    $("pause-local").hidden = localPaused;
    $("pause-hours").hidden = localPaused;
    $("resume-local").hidden = !localPaused;
  } catch {
    if (request !== recordingRead || brain !== state.brain) return;
    recordingState = null;
    $("recording").hidden = false;
    $("recording").textContent = "Recording status unavailable";
    $("recording").classList.add("paused");
    $("recording-text").textContent = "Recording status could not be checked. Refresh before changing it.";
    $("recording-actions").hidden = true;
    $("local-recording").hidden = true;
  }
}

async function changeRecording(paused, local = false) {
  const current = recordingState;
  if (!current || current.brain !== state.brain || (local && !current.local)) {
    throw new Error("Recording status could not be checked. Refresh before changing it.");
  }
  try {
    if (local) {
      const hours = $("pause-hours").value;
      await api("/v1/local/recording", { paused, expected_revision: current.local.revision,
        ...(paused && hours ? { hours: Number(hours) } : {}) });
    } else {
      await api(`/v1/brains/${encodeURIComponent(current.brain)}/recording`,
        { paused, expected_revision: current.server.revision }, "PUT");
    }
  } finally {
    await loadRecording();
  }
}
guard($("pause"), () => changeRecording(true));
guard($("resume"), () => changeRecording(false));
guard($("pause-local"), () => changeRecording(true, true));
guard($("resume-local"), () => changeRecording(false, true));
guard($("refresh-recording"), loadRecording);
guard($("export"), async () => {
  const { result } = await action("export", { include_events: true, include_working_states: true,
    include_assertions: true, include_provenance: true, include_tombstones: true, budget: {
      max_context_tokens: 16000, max_model_calls: 0, max_embedding_calls: 0, max_expansion_steps: 2,
      max_wall_time_ms: 30000, max_cost_microunits: 0, currency: "USD", token_counting: "conservative_estimate",
      tokenizer_id: null } });
  const archive = result.archive || result;
  const document_ = await api(`/v1/archives/${encodeURIComponent(archive.archive_id)}`);
  const url = URL.createObjectURL(new Blob([JSON.stringify(document_, null, 2)], { type: "application/json" }));
  const link = element("a");
  link.href = url;
  link.download = "membrain-export.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  notify("Exported. The file contains your original messages; store it securely.");
});
guard($("erase"), async () => {
  if ($("erase-confirm").value.trim() !== "ERASE") {
    notify("Type ERASE to confirm.", true);
    return;
  }
  await forget("all_authorized_scope", [], "erase_content");
  $("erase-confirm").value = "";
  notify("Everything was erased.");
});

const INSTALL_COMMANDS = {
  "claude-code": "claude plugin install membrain --marketplace chriswu727/membrain",
  codex: "codex plugin marketplace add chriswu727/memBrain\ncodex plugin add membrain@membrain",
};
function setupCommand() { $("setup-command").textContent = INSTALL_COMMANDS[$("setup-host").value]; }
$("setup-host").addEventListener("change", setupCommand);
setupCommand();
guard($("copy-setup"), async () => {
  try { await navigator.clipboard.writeText($("setup-command").textContent); notify("Install command copied."); }
  catch { notify("Select and copy the install command above."); }
});
guard($("prepare-model"), async () => {
  await api("/v1/local/semantic-model", {});
  notify("Preparing recall by meaning. Keyword search keeps working; this page will update automatically.");
  await loadServiceStatus();
});

function showConnection(brain, local) {
  if (!local) { $("first-use").hidden = true; return; }
  $("first-use").hidden = false;
  const received = brain.recorded_messages > 0;
  $("connection-summary").textContent = received ? "Messages are arriving" : "Waiting for your first message";
  if (!state.connectionShown) {
    // Someone on this page has usually come through the plugin already: the install command stays folded away.
    $("first-use").open = !received;
    if (brain.last_message_producer === "membrain-codex") $("setup-host").value = "codex";
    setupCommand(); state.connectionShown = true;
  }
  $("setup-service").textContent = local.ready ? "Running on this computer." : "Needs attention. Run membrain doctor for a diagnosis.";
  const producer = { "membrain-plugin": "Claude Code", "membrain-codex": "Codex", "membrain-hermes": "Hermes",
    "membrain-openclaw": "OpenClaw", "membrain-workbuddy": "WorkBuddy" }[brain.last_message_producer];
  $("setup-recording").textContent = received
    ? `${brain.recorded_messages} message(s) recorded${producer ? `; latest from ${producer}` : ""}${brain.last_message_at ? ` on ${day(brain.last_message_at)}` : ""}.`
    : "No messages yet. Say something to your agent; after it replies, refresh: the message appears under Conversations, and anything it saves for later under Notes.";
  const semantic = local.semantic_recall;
  $("setup-semantic").textContent = semantic === "ready"
    ? `Enabled. ${brain.embedding_pending ? `${brain.embedding_pending} memory item(s) still preparing.` : "Finds related wording across languages."}`
    : semantic === "downloading" ? "Downloading the local model (about 135 MB). Keyword search already works."
    : semantic === "download_failed" ? "The download failed. Check your connection and retry below; keyword search still works."
    : semantic === "activating" ? "The model is downloaded and is being enabled. Keyword search already works."
    : semantic === "unavailable" ? "Local model support is missing. Reinstall using the documented semantic extra."
    : "Optional local model; no API key or usage charge. Keyword search already works.";
  for (const [id, ready] of [["setup-service", local.ready], ["setup-recording", received], ["setup-semantic", semantic === "ready"]]) {
    $(id).parentElement.dataset.ready = String(Boolean(ready));
  }
  $("prepare-model").hidden = ["ready", "activating", "downloading", "unavailable"].includes(semantic);
  $("prepare-model").textContent = semantic === "download_failed" ? "Retry model download" : "Enable recall by meaning";
}

async function loadServiceStatus() {
  $("service-status").hidden = false;
  try {
    const [brain, local] = await Promise.all([
      api(`/v1/brains/${encodeURIComponent(state.brain)}/status`), api("/v1/local/memory-status").catch(() => null),
    ]);
    const lag = brain.index_lag;
    const semantic = local?.semantic_recall;
    $("service-heading").textContent = (local && !local.ready) || brain.failed_jobs ? "Memory service needs attention"
      : local?.pending_records ? "Messages waiting for delivery" : lag ? "Indexing your messages"
      : semantic === "ready" ? "Memory is ready" : "Keyword memory is ready";
    const recall = semantic === "ready" ? "Keyword and semantic recall enabled"
      : semantic === "downloading" ? "Keyword recall ready; semantic model downloading"
      : semantic === "download_failed" ? "Keyword recall ready; model download needs a retry"
      : semantic === "activating" ? "Keyword recall ready; semantic model activating"
      : local ? "Keyword recall ready; semantic model not enabled" : "Keyword recall available; local model status unknown";
    $("service-detail").textContent = `${recall}. ${lag ? `${lag} message(s) waiting for indexing.` : "Message index is up to date."} ${local?.pending_records ? `${local.pending_records} queued record(s).` : ""} ${brain.failed_jobs ? `${brain.failed_jobs} background job(s) need attention. Run membrain doctor.` : ""}`;
    showConnection(brain, local);
  } catch (error) {
    $("service-heading").textContent = "Unable to check memory";
    $("service-detail").textContent = `${error.message} Run membrain doctor for help.`;
  }
}
guard($("refresh-status"), loadServiceStatus);

// The Companion tab holds the personality and the relationship.
const loadCompanion = () => Promise.all([loadPersona(), loadRelationship()]);
const loaders = { notes: () => loadNotes(), brain: () => window.loadBrain(), persona: loadCompanion, people: () => loadNotes("people"),
  plans: () => loadNotes("plans"), feelings: loadFeelings,
  conversations: loadConversations, search: async () => {}, privacy: loadRecording };

async function show(view) {
  if (typeof view !== "string" || !Object.hasOwn(loaders, view)) view = "notes";
  for (const button of $("tabs").querySelectorAll("button")) {
    button.classList.toggle("active", button.dataset.view === view);
    button.setAttribute("aria-pressed", String(button.dataset.view === view));
  }
  for (const name of Object.keys(loaders)) $(`view-${name}`).hidden = name !== view;
  if (!DEMO && state.key) {
    try { sessionStorage.setItem("membrain-page", JSON.stringify({ key: state.key, brain: state.brain, view })); } catch { /* private window */ }
  }
  try { await loaders[view](); } catch (error) { notify(error.message, true); }
}
for (const button of $("tabs").querySelectorAll("button")) {
  button.addEventListener("click", () => { leaveAddress(); show(button.dataset.view); });
}

// Addresses ------------------------------------------------------------------------------------------------------
// /memory#note=<id> opens the Notes view at that note, with its sources and what it replaced shown; /memory#message=<id>
// opens the Conversations view at that message, in its conversation. The fragment holds an id only and is never sent
// to the server; the single-use ?code stays the only credential. An address only reads, navigates and expands: it
// never deletes, accepts or changes anything, and any other key in it is ignored. An id that is not here (never was,
// deleted, hidden, another person's) shows one plain line and the normal view, and nothing about the id.
const GONE = "This item is no longer here.";

function address() {
  const fragment = new URLSearchParams(location.hash.slice(1));
  for (const kind of ["note", "message"]) {
    const id = fragment.get(kind);
    if (id !== null) return { kind, id: id.length <= 256 && !/[\u0000-\u001f]/.test(id) ? id : "" };
  }
  return null;
}

// Choosing a tab leaves the address, so a reload opens the view chosen rather than the item.
function leaveAddress() {
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
}

const itemsOf = (root, selector, id) => [...root.querySelectorAll(selector)].find((node) => node.dataset.eventId === id);

function gone(list) {
  list.querySelector(":scope > .empty")?.remove();
  list.prepend(element("p", GONE, "hint item-gone"));
}

function arrive(node) {
  node.classList.add("addressed");
  node.scrollIntoView({ block: "center" });
}

async function goToNote(id) {
  await show("notes");
  const list = $("notes");
  let item = id ? itemsOf(list, ":scope > article.item", id) : null, earlier = null;
  // A note that a current note replaced is shown under it: open the current note, at that earlier line.
  const current = id && !item && state.notes.find((note) => (note.replaced || []).some((entry) => entry.event_id === id && !entry.erased));
  if (current) {
    item = itemsOf(list, ":scope > article.item", current.event_id);
    earlier = item && itemsOf(item, ".lineage .earlier", id);
  }
  // Only a list too long to read whole can leave a current note out; only then is the note asked for by its id.
  if (id && !item && !state.notesComplete) {
    const { items } = await timeline({ role: ["assistant", "user"], conversation_id: NOTES, event_id: [id] });
    if (items[0]) { item = noteItem(items[0]); list.querySelector(":scope > .empty")?.remove(); list.prepend(item); }
  }
  if (!item) return gone(list);
  const sources = item.querySelector(":scope > details");
  if (sources) sources.open = true;
  arrive(item);
  if (earlier) earlier.classList.add("addressed");
}

async function goToMessage(id) {
  await show("conversations");
  const list = $("conversations"), roles = ["user", "assistant"];
  const found = id ? (await timeline({ role: roles, event_id: [id] })).items[0] : null;
  if (!found || found.conversation_id === NOTES) return gone(list);
  const conversation = found.conversation_id;
  let { items } = await timeline({ role: roles, conversation_id: conversation, erasure: true });
  // A conversation too long for one read is shown up to this message.
  if (!items.some((message) => message.event_id === id)) {
    ({ items } = await timeline({ role: roles, conversation_id: conversation, before_sequence: found.sequence + 1,
      erasure: true }));
  }
  // The latest messages may hold part of this conversation: it is shown whole, first, and open.
  for (const node of list.querySelectorAll(":scope > details.item")) if (node.dataset.conversation === conversation) node.remove();
  list.querySelector(":scope > .empty")?.remove();
  const item = conversationItem(conversation, items.reverse());
  list.prepend(item);
  item.open = true;
  const block = itemsOf(item, ".message", id);
  if (block) arrive(block);
}

async function goTo(target) {
  try { await (target.kind === "note" ? goToNote(target.id) : goToMessage(target.id)); } catch (error) { notify(error.message, true); }
}

window.addEventListener("hashchange", () => {
  const target = address();
  if (target && !DEMO && state.key && !$("tabs").hidden) goTo(target);
});

async function open(key, brain, view = "notes") {
  state.key = key; state.brain = brain;
  if (!state.brain) state.brain = (await api("/v1/brains")).brains?.[0]?.id || "";
  if (!state.brain) throw new Error("No memory installation found. Run membrain plugin start first.");
  await api(`/v1/brains/${encodeURIComponent(state.brain)}/status`);
  $("signin").hidden = true; $("tabs").hidden = false;
  const target = SHOWCASE ? null : address();
  await Promise.all([loadRecording(), loadServiceStatus(), target ? goTo(target) : show(SHOWCASE ? "brain" : view)]);
  if (SHOWCASE) window.openShowcase();
}
onSubmit($("key-form"), () => open($("key").value.trim(), ""));
setInterval(() => { if (!DEMO && state.key && !$("tabs").hidden) { loadServiceStatus(); loadRecording(); } }, 30000);

(async () => {
  if (DEMO) return;
  const code = new URLSearchParams(location.search).get("code");
  if (code) {
    history.replaceState(null, "", `/memory${location.hash}`);  // The code goes; an address stays.
    try {
      const session = await fetch("/v1/local/ui-session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
      const data = await session.json();
      if (!session.ok) throw new Error(data.detail || "This link has expired.");
      return await open(data.api_key, data.brain_id);
    } catch (error) { notify(error.message, true); }
  }
  try {
    const saved = JSON.parse(sessionStorage.getItem("membrain-page") || "null");
    if (saved?.key) return await open(saved.key, saved.brain, saved.view);
  } catch { try { sessionStorage.removeItem("membrain-page"); } catch { /* private window */ } }
  $("signin").hidden = false;
})();
