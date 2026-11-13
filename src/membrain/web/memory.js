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

function observe(text, conversation, role, producer) {
  return action("observe", { idempotency_key: uid(), events: [{
    source_event_key: `${producer}:${uid()}`, source_revision: 1, producer_ref: producer, actor_ref: role,
    actor_role: role, event_kind: "message", content: { media_type: "text/plain", text },
    occurred_time: { start: null, end: null, precision: "unknown", basis: "unknown" },
    interpretation_hint: "unknown", delivery_state: "received", parent_source_event_keys: [],
  }] }, conversation);
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
const LABELS = { person: "Person", constraint: "Health or constraint", preference: "Preference", plan: "Plan", routine: "Routine",
  milestone: "Milestone", relationship: "Relationship", agent_commitment: "Agent promise", other: "Other" };
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

function words(text) {
  return new Set((text.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || []).filter((word) => word.length > 2));
}

function duplicatePairs(items) {
  const parsed = items.filter((note) => note.actor_role !== "user").map((note) => ({ note, ...typedNote(note.text), words: words(typedNote(note.text).sentence) }));
  const pairs = new Map();
  parsed.forEach((first, index) => {
    for (const second of parsed.slice(index + 1)) {
      if (first.fields.kind !== second.fields.kind || first.fields.about !== second.fields.about || pairs.has(first.note.event_id)) continue;
      const union = new Set([...first.words, ...second.words]);
      const shared = [...first.words].filter((word) => second.words.has(word)).length;
      if (union.size && shared / union.size >= 0.75) pairs.set(first.note.event_id, second.note);
    }
  });
  return pairs;
}

async function loadNotes(view = "notes") {
  const response = await timeline({ role: ["assistant", "user"], conversation_id: NOTES });
  state.notes = response.items;
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
  if (!items.length) list.append(element("p", view === "notes" ? "No notes yet. Add a lasting fact above, or ask your connected agent to remember one." : "Nothing here yet. Add a note with the matching kind.", "empty"));
  const pairs = duplicatePairs(items);
  for (const note of items) list.append(noteItem(note, pairs.get(note.event_id)));
}

function field(form, controls, name, label, type = "text", options) {
  const wrapper = element("label", undefined, "field");
  wrapper.append(element("span", label));
  const control = element(type === "textarea" ? "textarea" : options ? "select" : "input");
  if (type !== "textarea" && !options) control.type = type;
  if (options) for (const [value, title] of options) {
    const option = element("option", title); option.value = value; control.append(option);
  }
  control.name = name;
  wrapper.append(control); form.append(wrapper); controls[name] = control;
  return control;
}

function noteEditor(note, merged = [], after = () => loadNotes(), initialSources = []) {
  const form = element("form", undefined, "note-editor");
  const controls = {};
  const parsed = typedNote(note?.text || "");
  const fields = parsed.fields;
  const text = field(form, controls, "text", "Note text", "textarea");
  text.value = parsed.sentence || ""; text.maxLength = 300; text.required = true; text.rows = 3;
  field(form, controls, "kind", "Kind", "text", KINDS.map((kind) => [kind, LABELS[kind]])).value = fields.kind || "other";
  field(form, controls, "status", "Plan status", "text", STATUSES.map((value) => [value, value])).value = fields.status || "intended";
  field(form, controls, "about", "Person or topic").value = fields.about || "";
  field(form, controls, "aliases", "Other names, separated by commas").value = (fields.aliases || []).join(", ");
  for (const [name, title] of [["due", "Due date"], ["occurs_at", "Event date"]]) {
    const value = fields[name] || "";
    field(form, controls, name, title, value.length === 7 ? "month" : "date").value = value;
  }
  for (const [name, title] of [["pinned", "Pin this note"], ["sensitive", "Sensitive: mention only when I bring it up"],
    ["shared", "Shared moment: something we did or reached together"]]) {
    const input = field(form, controls, name, title, "checkbox"); input.checked = Boolean(fields[name]); input.parentElement.classList.add("check");
  }
  field(form, controls, "moment", "Kind of moment", "text", [["", "Not set"], ["play", "Play or a joke together"],
    ["hard", "A hard time we went through"], ["other", "Another kind of moment"]]).value = fields.moment || "";
  const sources = new Set([...(note?.source_event_ids || []), ...initialSources]);
  const sourceDetails = element("details", undefined, "source-picker");
  sourceDetails.append(element("summary", "Link original messages"), element("p", "Choose messages this note is based on. Unlinked notes stay clearly labelled.", "hint"));
  const select = element("select"); select.multiple = true; select.size = 5; select.setAttribute("aria-label", "Original messages");
  sourceDetails.append(select); form.append(sourceDetails);
  let loaded = false;
  for (const id of sources) { const option = element("option", `Linked message ${id}`); option.value = id; option.selected = true; select.append(option); }
  sourceDetails.addEventListener("toggle", async () => {
    if (!sourceDetails.open || loaded) return;
    try {
      const { items } = await timeline({ role: ["user", "assistant"] });
      const candidates = items.filter((item) => item.conversation_id !== NOTES);
      for (const message of candidates) {
        let option = [...select.options].find((value) => value.value === message.event_id);
        if (!option) { option = element("option"); option.value = message.event_id; select.append(option); }
        option.textContent = `${day(message.recorded_at)} · ${message.actor_role === "user" ? "You" : "Agent"}: ${message.text.slice(0, 130)}`;
        option.selected = sources.has(message.event_id);
      }
      loaded = true;
    } catch (error) { notify(error.message, true); }
  });
  if (note?.event_id) form.append(element("p", "Saving a correction also deletes any feeling recorded with this note.", "hint"));
  const actions = element("div", undefined, "row editor-actions");
  const save = element("button", note?.event_id ? "Save correction" : "Add note");
  const cancel = element("button", "Cancel", "secondary"); cancel.type = "button";
  actions.append(save, cancel); form.append(actions);
  cancel.addEventListener("click", after);
  const updateStatus = () => {
    controls.status.parentElement.hidden = !["plan", "agent_commitment"].includes(controls.kind.value);
    controls.shared.parentElement.hidden = controls.kind.value !== "milestone";
    controls.moment.parentElement.hidden = controls.kind.value !== "milestone" || !controls.shared.checked;
  };
  controls.kind.addEventListener("change", updateStatus); controls.shared.addEventListener("change", updateStatus);
  updateStatus();
  let requestId = uid(), previousBody = "";
  onSubmit(form, async () => {
    const body = { text: controls.text.value.trim(), kind: controls.kind.value, role: "user", producer: "membrain-memory-page",
      replaces: note?.event_id ? [note.event_id, ...merged.map((item) => item.event_id)] : [],
      source_event_ids: [...select.selectedOptions].map((option) => option.value) };
    for (const name of ["about", "due", "occurs_at"]) if (controls[name].value.trim()) body[name] = controls[name].value.trim();
    if (!controls.status.parentElement.hidden) body.status = controls.status.value;
    if (controls.aliases.value.trim()) body.aliases = controls.aliases.value.split(",").map((value) => value.trim()).filter(Boolean);
    body.pinned = controls.pinned.checked; body.sensitive = controls.sensitive.checked;
    body.shared = controls.kind.value === "milestone" && controls.shared.checked;
    if (body.shared && controls.moment.value) body.moment = controls.moment.value;
    const serialized = JSON.stringify(body);
    if (serialized !== previousBody) { requestId = uid(); previousBody = serialized; }
    await api(`/v1/brains/${encodeURIComponent(state.brain)}/notes`, { request_id: requestId, ...body });
    notify(note?.event_id ? "Note corrected. Your version takes precedence." : "Note added.");
    await after(); await loadServiceStatus();
  });
  return form;
}

function resetNoteForm() {
  $("note-form-host").replaceChildren(noteEditor(null, [], async () => {
    resetNoteForm(); $("add-note").open = false; await loadNotes();
  }));
}

async function showSources(container, ids) {
  container.replaceChildren(element("p", "Loading original messages…", "hint"));
  try {
    const { items } = await timeline({ role: ["user", "assistant", "operator", "tool"], event_id: ids });
    container.replaceChildren();
    if (items.length < ids.length) container.append(element("p", "Some original messages are no longer available.", "hint"));
    for (const message of items.reverse()) {
      const block = element("div", undefined, "message");
      block.append(element("div", `${day(message.recorded_at)} · ${message.actor_role === "user" ? "You" : "Agent"}`, "meta"), element("p", message.text, "user-text"));
      container.append(block);
    }
  } catch (error) { container.replaceChildren(element("p", error.message, "hint")); }
}

function noteItem(note, duplicate) {
  const item = element("article", undefined, "item");
  const parsed = typedNote(note.text), fields = parsed.fields;
  const meta = element("div", undefined, "meta");
  meta.append(element("span", day(note.recorded_at)));
  const imported = (note.producer || "").startsWith("membrain-import:") ? note.producer.slice(16) : null;
  meta.append(element("span", note.actor_role === "user" ? "written by you" : imported ? `imported from ${HOST_NAMES[imported] || imported}` : "saved by your agent", "tag"));
  for (const tag of parsed.tags) meta.append(element("span", tag, "tag"));
  const actions = element("span", undefined, "actions");
  const edit = element("button", "Edit", "link"), remove = element("button", "Delete", "link danger");
  actions.append(edit, remove); meta.append(actions); item.append(meta, element("p", parsed.sentence, "user-text"));
  const date = fields.due || fields.occurs_at;
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  if (date && openPlan(fields) && date < (date.length === 7 ? today.slice(0, 7) : today)) item.append(element("p", "Date has passed; completion is not confirmed.", "hint"));
  const ids = note.source_event_ids || [];
  if (note.pending_source_count) item.append(element("p", "Waiting for the source message to finish recording.", "hint"));
  if (ids.length) {
    const details = element("details"); details.append(element("summary", `${ids.length} original message${ids.length === 1 ? "" : "s"}`));
    const content = element("div"); details.append(content); item.append(details);
    let loaded = false;
    details.addEventListener("toggle", () => { if (details.open && !loaded) { loaded = true; showSources(content, ids); } });
  } else if (!note.pending_source_count) item.append(element("p", note.actor_role === "user" ? "Standalone note written by you." : "Original message not linked. Edit to attach its source.", "hint"));
  edit.addEventListener("click", () => { item.replaceChildren(noteEditor(note, [], () => show(currentView()))); item.querySelector("textarea").focus(); });
  if (duplicate) {
    const merge = element("button", "Merge duplicate", "link");
    merge.addEventListener("click", () => item.replaceChildren(noteEditor(note, [duplicate], () => show(currentView())))); actions.prepend(merge);
  }
  guard(remove, async () => {
    if (!confirm("Delete this note? Its content is erased.")) return;
    await forget("events", [note.event_id], "erase_content", NOTES); notify("Note deleted."); await show(currentView());
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
  item.append(note);
  const ids = record.source_event_ids || [];
  if (ids.length) {
    const details = element("details"); details.append(element("summary", `${ids.length} original message${ids.length === 1 ? "" : "s"}`));
    const content = element("div"); details.append(content); item.append(details);
    let loaded = false;
    details.addEventListener("toggle", () => { if (details.open && !loaded) { loaded = true; showSources(content, ids); } });
  } else item.append(element("p", "Original message not linked.", "hint"));
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
  const response = await timeline({ role: ["user", "assistant"], limit: 100,
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
  const summary = element("summary");
  const first = messages.find((message) => message.actor_role === "user") || messages[0];
  summary.textContent = `${day(messages[0].recorded_at)} · ${messages.length} messages · ${first.text.slice(0, 90)}`;
  item.append(summary);
  for (const message of messages) {
    const block = element("div", undefined, `message ${message.actor_role}`);
    const meta = element("div", undefined, "meta");
    meta.append(element("span", message.actor_role === "user" ? "You" : "Agent"), element("span", day(message.recorded_at)));
    const remove = element("button", "Delete", "link danger");
    const actions = element("span", undefined, "actions");
    actions.append(remove);
    const saveNote = element("button", "Save as note", "link");
    actions.prepend(saveNote);
    saveNote.addEventListener("click", () => {
      const editor = noteEditor({ text: message.text.slice(0, 300), source_event_ids: [message.event_id] }, [], loadConversations);
      block.replaceChildren(editor); editor.querySelector("textarea").focus();
    });
    meta.append(actions);
    block.append(meta, element("p", message.text, "user-text"));
    guard(remove, async () => {
      if (!confirm("Delete this message? Its content is erased everywhere it was used.")) return;
      await forget("events", [message.event_id], "erase_content", conversation);
      block.remove();
      notify("Message deleted.");
    });
    item.append(block);
  }
  const removeAll = element("button", "Delete this conversation", "link danger");
  guard(removeAll, async () => {
    if (!confirm("Delete every message in this conversation?")) return;
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
  const { items } = await timeline({ role: ["user", "assistant"], event_id: sources.slice(0, 20) });
  const byId = new Map(items.map((message) => [message.event_id, message]));
  for (const id of sources.slice(0, 20)) {
    const message = byId.get(id);
    if (!message) continue;
    const block = element("div", undefined, "item");
    const meta = element("div", undefined, "meta");
    meta.append(element("span", day(message.recorded_at)),
      element("span", message.conversation_id === NOTES ? "note" : message.actor_role === "user" ? "You" : "Agent", "tag"));
    block.append(meta, element("p", message.text, "user-text"));
    results.append(block);
  }
});

// Relationship -----------------------------------------------------------------------------------------------
// Shared moments (milestone notes flagged shared), derived familiarity with its reason and an optional limit, the
// support style, boundaries and the promise record. The service derives everything; the page only shows and edits.

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
  $("relationship-cap").value = known.cap || "";
  $("support-text").value = data.support_style?.text || "";
  const boundaries = $("boundaries");
  boundaries.replaceChildren();
  if (!data.boundaries.length) boundaries.append(element("p", "No boundaries. Add a topic you don't want your companion to bring up.", "empty"));
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
  const edit = element("button", "Edit", "link"), remove = element("button", "Delete", "link danger");
  actions.append(edit, remove); meta.append(actions);
  item.append(meta, element("p", moment.text, "user-text"));
  edit.addEventListener("click", () => {
    const note = { event_id: moment.id, text: moment.note_text, source_event_ids: moment.source_event_ids };
    item.replaceChildren(noteEditor(note, [], loadRelationship)); item.querySelector("textarea").focus();
  });
  guard(remove, async () => {
    if (!confirm("Delete this shared moment? Its note is erased.")) return;
    await forget("events", [moment.id], "erase_content", NOTES); notify("Shared moment deleted."); await loadRelationship();
  });
  return item;
}

function promiseItem(kind, promise) {
  const item = element("article", undefined, "item");
  const meta = element("div", undefined, "meta");
  meta.append(element("span", PROMISE_TAGS[kind], kind === "missed" ? "tag relationship-missed" : "tag"));
  if (promise.due) meta.append(element("span", `due ${promise.due}`, "tag"));
  if (kind === "missed") meta.append(element("span", promise.acknowledged ? "shown to your agent" : "not shown yet", "tag"));
  item.append(meta, element("p", promise.text, "user-text"));
  return item;
}

guard($("relationship-cap-save"), async () => {
  const level = $("relationship-cap").value || null;
  await api(relationshipPath("/cap"), { level });
  notify(level ? "Familiarity limit saved." : "Familiarity limit removed."); await loadRelationship();
});
onSubmit($("support-form"), async () => {
  const saved = await api(relationshipPath("/support-style"), { text: $("support-text").value }, "PUT");
  notify(saved.support_style ? "Support style saved." : "Support style removed."); await loadRelationship();
});
onSubmit($("boundary-form"), async () => {
  const aliases = $("boundary-aliases").value.split(/[,，、]/).map((value) => value.trim()).filter(Boolean);
  await api(relationshipPath("/boundaries"), { topic: $("boundary-topic").value.trim(), aliases });
  $("boundary-topic").value = ""; $("boundary-aliases").value = "";
  notify("Boundary added."); await loadRelationship();
});
guard($("moment-add"), async () => {
  const form = noteEditor(null, [], async () => { $("moment-form-host").replaceChildren(); await loadRelationship(); });
  $("moment-form-host").replaceChildren(form);
  form.elements.kind.value = "milestone"; form.elements.kind.dispatchEvent(new Event("change"));
  form.elements.shared.checked = true; form.elements.shared.dispatchEvent(new Event("change")); form.elements.text.focus();
});
guard($("relationship-reset"), async () => {
  if (!confirm("Reset the relationship? This deletes every shared moment, the support style, every boundary (so those topics are no longer kept out), the familiarity limit and the record of promises kept and missed. Familiarity starts again at new and counts only days from now. Conversations, your other notes, the personality and feelings stay.")) return;
  await api(relationshipPath("/reset"), {});
  notify("Relationship reset."); await loadRelationship();
});

// Personality ------------------------------------------------------------------------------------------------
// The companion's persona card, versioned by the service. The page writes as the user; restore and reset save a
// new version, so nothing is lost until "Delete personality history".

const personaPath = (suffix = "") => `/v1/brains/${encodeURIComponent(state.brain)}/persona${suffix}`;
const VOICE = [["register", "register"], ["length", "length"], ["emoji", "emoji"], ["language", "language"]];
const MADE_BY = { user: "set by you", host: "set by the host", feedback: "from accepted feedback" };
// Preset personas: which one is current, and switching to another. The labels and summaries are the service's own.
const PRESET_KIND = { preset: "Personality type:", custom: "Your own card", none: "No personality type" };
const lines = (text) => text.split("\n").map((value) => value.trim()).filter(Boolean);
// By name, not as properties: a control named "length" would otherwise read as the collection's length.
const personaControl = (name) => $("persona-form").elements.namedItem(name);

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

function personaForm(card) {
  personaControl("name").value = card.name || "";
  personaControl("traits").value = (card.traits || []).join("\n");
  for (const [name] of VOICE) personaControl(name).value = card.voice?.[name] || "";
  personaControl("values").value = (card.values || []).join("\n");
  personaControl("boundaries").value = (card.boundaries || []).join("\n");
  personaControl("mood_label").value = card.baseline_mood?.label || "";
  personaControl("mood_valence").value = String(card.baseline_mood?.valence ?? 0);
  personaControl("mood_energy").value = String(card.baseline_mood?.energy ?? 1);
  personaControl("reason").value = "";
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
  view.replaceChildren(current.empty
    ? element("p", "No personality card is set. Your agent keeps its usual manner.", "empty")
    : personaCard(current.card));
  $("persona-form").hidden = true;
  const list = $("persona-versions");
  list.replaceChildren();
  if (!history.versions.length) list.append(element("p", "No versions yet. Edit the personality to save the first one.", "empty"));
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
  if (version.feedback) {
    // P2: the feedback is quoted from the messages that still exist; a deleted message is never shown.
    const quotes = element("ul", "", "persona-feedback-quotes");
    for (const message of version.feedback_messages || []) {
      const row = element("li", "");
      row.append(element("span", `“${message.text}”`, "user-text"), element("span", ` ${String(message.recorded_at).slice(0, 10)}`, "hint"));
      quotes.append(row);
    }
    if (!(version.feedback_messages || []).length) quotes.append(element("li", "The messages behind this change were deleted.", "hint"));
    item.append(quotes);
  }
  item.append(version.empty ? element("p", "No card.", "hint") : personaCard(version.card));
  return item;
}

guard($("persona-edit"), async () => {
  personaForm(state.persona?.card || {});
  $("persona-form").hidden = false;
  personaControl("name").focus();
});
$("persona-cancel").addEventListener("click", () => { $("persona-form").hidden = true; });
onSubmit($("persona-form"), async () => {
  const value = (name) => personaControl(name).value.trim();
  const card = { name: value("name"), traits: lines(value("traits")), voice: {}, values: lines(value("values")),
    boundaries: lines(value("boundaries")), baseline_mood: null };
  for (const [name] of VOICE) card.voice[name] = value(name);
  if (value("mood_label")) {
    card.baseline_mood = { label: value("mood_label"), valence: Number(value("mood_valence")), energy: Number(value("mood_energy")) };
  }
  const body = { card, made_by: "user" };
  if (value("reason")) body.reason = value("reason");
  const saved = await api(personaPath(), body, "PUT");
  notify(saved.unchanged ? "No change: that is already the current card." : `Saved as version ${saved.version}.`);
  await loadPersona();
});
async function switchType(preset) {
  const saved = await api(personaPath("/preset"), { preset, made_by: "user" });
  notify(saved.unchanged ? "No change: that is already the current card." : `Saved as version ${saved.version}.`);
  await loadPersona();
}
guard($("persona-preset-switch"), async () => {
  if (!confirm("Switch to this personality type? It is saved as a new version, and earlier versions can be restored. The mood and familiarity carry over.")) return;
  await switchType($("persona-preset-choice").value);
});
// Picking again: a different type at random (the owner's meaning of resetting the personality).
guard($("persona-random"), async () => {
  if (!confirm("Pick another personality type at random? It is saved as a new version, and earlier versions can be restored. The mood and familiarity carry over.")) return;
  await switchType("random");
});
guard($("persona-delete-history"), async () => {
  if (!confirm("Delete every personality version, including the current card? This cannot be undone.")) return;
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
const PROPOSAL_WITHDRAWN = { sources_removed: "Withdrawn: fewer than three of its messages are still in memory.",
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

function proposalChange(change) {
  change = { ...change, before: proposalText(change.before), after: proposalText(change.after) };
  const list = element("dl", undefined, "persona-card proposal-diff");
  const detail = element("dd");
  const before = Array.isArray(change.before) ? change.before : [change.before].filter(Boolean);
  const after = Array.isArray(change.after) ? change.after : [change.after].filter(Boolean);
  detail.append(proposalValue(change.before, after, "del"), element("span", "→", "proposal-arrow"),
    proposalValue(change.after, before, "ins"));
  list.append(element("dt", PROPOSAL_FIELDS[change.field] || change.field), detail);
  return list;
}

function proposalSources(proposal) {
  const box = element("div", undefined, "proposal-sources");
  box.append(element("p", "What you said:", "hint"));
  const list = element("ul");
  for (const source of proposal.sources) {
    const line = element("li");
    line.append(element("q", source.text, "user-text"), element("span", shortDate(source.recorded_at), "hint"));
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
  }
  if (proposal.status === "accepted") item.append(element("p", `Accepted on ${shortDate(proposal.decided_at)} as version ${proposal.version}.`, "hint"));
  if (proposal.status === "rejected") {
    item.append(element("p", proposal.paused_until ? `Rejected on ${shortDate(proposal.decided_at)}. None of this kind until ${shortDate(proposal.paused_until)}.`
      : `Rejected on ${shortDate(proposal.decided_at)}.`, "hint"));
  }
  if (proposal.status === "withdrawn") item.append(element("p", PROPOSAL_WITHDRAWN[proposal.withdrawn_because] || "Withdrawn.", "hint"));
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
    // pause of the device and says nothing about whether a direct chat is recorded.
    const hostConversation = localPaused && result.local.scope === "conversations";
    $("recording").hidden = false;
    $("recording").textContent = serverPaused ? "Recording paused" : hostConversation ? "Host conversation paused"
      : localPaused ? "Device capture paused" : "Recording on";
    $("recording").classList.toggle("paused", serverPaused || localPaused);
    $("recording-text").textContent = serverPaused
      ? "New messages, notes and background learning are paused for this memory. Earlier memory stays available."
      : hostConversation ? "Memory accepts writes. A local pause covers existing host conversations on this device; it is not a pause of device capture."
      : localPaused ? "Memory accepts writes, but chat capture is paused on this device."
        : "Memory accepts new messages and notes. Conversation-specific pauses still apply.";
    $("recording-actions").hidden = false;
    $("pause").hidden = serverPaused;
    $("resume").hidden = !serverPaused;
    $("local-recording").hidden = !result.local;
    $("local-recording-text").textContent = hostConversation
      ? "A host conversation asked not to be recorded. This pause covers the host conversations that were active when it was set. It does not apply to direct chat; direct chat still follows its server, device and conversation controls."
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
guard($("first-preference"), async () => {
  await show("notes"); $("add-note").open = true;
  const form = $("note-form-host").querySelector("form");
  form.elements.kind.value = "preference"; form.elements.kind.dispatchEvent(new Event("change"));
  form.elements.text.focus();
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
  $("connection-summary").textContent = received ? "Messages are arriving" : "Finish connecting your agent";
  if (!state.connectionShown) {
    $("first-use").open = !received; $("connect-agent").open = !received;
    if (brain.last_message_producer === "membrain-codex") $("setup-host").value = "codex";
    setupCommand(); state.connectionShown = true;
  }
  $("setup-service").textContent = local.ready ? "Running on this computer." : "Needs attention. Run membrain doctor for a diagnosis.";
  const producer = { "membrain-plugin": "Claude Code", "membrain-codex": "Codex", "membrain-hermes": "Hermes",
    "membrain-openclaw": "OpenClaw", "membrain-workbuddy": "WorkBuddy" }[brain.last_message_producer];
  $("setup-recording").textContent = received
    ? `${brain.recorded_messages} message(s) recorded${producer ? `; latest from ${producer}` : ""}${brain.last_message_at ? ` on ${day(brain.last_message_at)}` : ""}.`
    : "No agent messages received yet. Connect below, send a message and wait for its reply, then refresh.";
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
    const extraction = local?.note_extraction;
    const extractionFailing = extraction?.state === "degraded";
    $("service-heading").textContent = (local && !local.ready) || brain.failed_jobs ? "Memory service needs attention"
      : local?.pending_records ? "Messages waiting for delivery" : lag ? "Indexing your messages"
      : extractionFailing ? "Note extraction needs attention"
      : semantic === "ready" ? "Memory is ready" : "Keyword memory is ready";
    const recall = semantic === "ready" ? "Keyword and semantic recall enabled"
      : semantic === "downloading" ? "Keyword recall ready; semantic model downloading"
      : semantic === "download_failed" ? "Keyword recall ready; model download needs a retry"
      : semantic === "activating" ? "Keyword recall ready; semantic model activating"
      : local ? "Keyword recall ready; semantic model not enabled" : "Keyword recall available; local model status unknown";
    $("service-detail").textContent = `${recall}. ${lag ? `${lag} message(s) waiting for indexing.` : "Message index is up to date."} ${local?.pending_records ? `${local.pending_records} queued record(s).` : ""} ${brain.failed_jobs ? `${brain.failed_jobs} background job(s) need attention. Run membrain doctor.` : ""}`;
    $("extraction-detail").hidden = !extractionFailing;
    $("extraction-detail").textContent = extractionFailing
      ? `${extraction.failed_since_success} message(s) could not be read for notes (last error: ${extraction.last_error}). They are still stored and recalled; notes from them are missing. Run membrain doctor.`
      : "";
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
for (const button of $("tabs").querySelectorAll("button")) button.addEventListener("click", () => show(button.dataset.view));

async function open(key, brain, view = "notes") {
  state.key = key; state.brain = brain;
  if (!state.brain) state.brain = (await api("/v1/brains")).brains?.[0]?.id || "";
  if (!state.brain) throw new Error("No memory installation found. Run membrain plugin start first.");
  await api(`/v1/brains/${encodeURIComponent(state.brain)}/status`);
  $("signin").hidden = true; $("tabs").hidden = false;
  resetNoteForm();
  await Promise.all([loadRecording(), loadServiceStatus(), show(SHOWCASE ? "brain" : view)]);
  if (SHOWCASE) window.openShowcase();
}
onSubmit($("key-form"), () => open($("key").value.trim(), ""));
setInterval(() => { if (!DEMO && state.key && !$("tabs").hidden) { loadServiceStatus(); loadRecording(); } }, 30000);

(async () => {
  if (DEMO) return;
  const code = new URLSearchParams(location.search).get("code");
  if (code) {
    history.replaceState(null, "", "/memory");
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
