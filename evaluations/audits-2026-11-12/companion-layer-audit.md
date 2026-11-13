# Companion layer audit: personality, mood, relationship

Scope: module 4 of the six-module plan, at `integration/maturity-candidate` head `5b7ec232` (2026-11-12). Method: reading source, tests, design documents and evaluation records. Nothing was run: no tests, no service, no model. Statements of the form "a test checks X" come from reading the test, not from running it.

## Five most important findings

1. **Nothing in this module has a valid behavioural result.** C5 was attempted in five maturity attempts and never produced a scored reply. In the two attempts that reached it (third and fifth), scenario C1 stopped on `page_action_failed` and C2 never ran. About 290 deterministic tests check storage, derivation, deletion, reset and context wording. None of them has a model decide anything: test code writes the affect records, shared moments and boundaries itself.
2. **The module calls no model, except one optional path.** The only model-dependent producer is the proxy or chat-bot `Extractor`, which writes affect records when `MEMBRAIN_EXTRACT_MODEL` is set (`extraction.py:69-71,111-120,164-171`). That is off the main line. C5's arm E depended on it.
3. **Several "understanding" steps are fixed English/Chinese rules rather than work handed to the host AI.** Persona feedback detection is a regex table (`persona_growth.py:75-281`). The "play versus achievement" reading of a shared moment is a word list (`mood.py:74-77`). Boundary topics are matched as whole words (`relationship.py:80-112`). These match the main line in letter (no second model) but not in spirit (no host-AI understanding). They miss paraphrases and other languages.
4. **The host AI can feed only part of the module.** Its tools are `memory_note` (with `affect`, `shared` and the `milestone`, `relationship` and `agent_commitment` kinds) and `memory_boundary`. It cannot write or propose a persona card, record a support style, or report feedback about its own manner. The persona card is empty in the plugin path unless the user edits it on the memory page. Support style can be stored in two places: the page-only support-style record and `relationship` notes, which the skill directs the AI to use.
5. **The companion layer is on by default in every host with no switch, including coding tools.** After three UTC days with user messages, every session gets a `<membrain-relationship>` block that says "Let it shape warmth and informality lightly" (`relationship.py:49,422-424,451`). A host-written feeling, a plan marked done, or a shared moment produces a "Simulated mood of the companion persona" line even when no persona exists (`mood.py:51,60-68,539-542`). Together, the companion blocks can take about 4,400 of the 9,500 characters of session-start context, and they shrink the history budget (`host.py:43,2096-2098`).

---

## 1. What exists

All companion state is stored as `system`-role events in reserved conversations of `memory_events`. There are no new tables. Such events are never learned from (`service.py:532-546`), recalled or counted as messages, and outside writers are refused for persona, relationship, mood and proposals (`service.py:556-571`). Deletion uses the same audited `_forget` (tombstones) as notes, so an older archive cannot bring records back. "Erase all memory" removes everything, markers included. Each reset writes a marker with `applies_from_sequence`, and nothing before a marker is derived again.

### 1.1 Persona card (`persona.py`)

| Aspect | Detail |
| --- | --- |
| Data | `name`, up to 8 `traits`, `voice` {register, length, emoji, language}, up to 8 `values`, up to 8 `boundaries` (what the companion will not do), `baseline_mood` {label, valence −2..2, energy 0..3} (`persona.py:27-64`). Each version is one event in `membrain-persona`, with `made_by` ∈ host/user/feedback, a reason, an action, `restored_from` and `host_default` (`persona.py:288-310`). |
| Who decides | The user on the memory page (`web/memory.js:711,719,673`, always `made_by: "user"`), or a host integration through `PUT /v1/brains/{id}/persona` (`api.py:694-701`). No adapter or plugin sets a card or a host default (grep finds no `set_persona` in `adapters/`, `plugin.py`, `host.py`, `proxy.py`). There is no MCP tool. A `feedback` version comes only from accepting a P2 suggestion (§1.2). |
| Validation | A strict pydantic schema. Scrubbed like a note. Refused, never truncated, above 1,200 rendered characters (`persona.py:71-98`). |
| Shown to the host AI | `<membrain-persona version="N">`, first in the snapshot. It says the card is not about the user, that the user's preferences win, and that it is not a claim of real feelings (`persona.py:119-131`, `host_context.py:55,62`). Removal is announced in `<membrain-updates>` (`host_context.py:84-86`). The skill text says nothing about this block (`plugins/membrain/skills/membrain/SKILL.md`). |
| Shown to the user | The Personality section of the Companion tab: current card, edit, versions, restore, reset, delete history (`web/memory.html` around lines 230-325). |
| Delete/reset | Reset saves the host default, or an empty card, as a new version, so history is kept (`persona.py:353-362`). "Delete personality history" erases every version and every P2 suggestion and decision, then writes a marker (`persona.py:365-401`). Neither touches affect, mood or relationship (tested in `test_companion_acceptance.py:122`). |

### 1.2 Persona suggestions from feedback, P2 (`persona_growth.py`)

| Aspect | Detail |
| --- | --- |
| Data | Proposals, decisions and "seen" ids in `membrain-persona-proposals` (`persona_growth.py:53-58,307-346`). They store message ids only, never words. Quotes are read live from the messages. |
| Who decides | **A fixed rule.** `detect()` runs regexes from a seven-kind table (more casual, more formal, more playful, shorter, longer, fewer emoji, more emoji), in English and Chinese only (`persona_growth.py:75-138,272-281`). It runs synchronously on every received user message inside `_observe` (`service.py:587-592` → `persona_growth.py:732-754`). Three matching messages after the latest cutoff create a proposal (`THRESHOLD = 3`, `:59`). A rejection pauses that kind for 30 days (`:60`). A decision consumes earlier feedback, and opposite directions cancel each other (`:140-142,574-576`). Accepting a proposal is the user's decision on the page (`api.py:736-752`). |
| Shown to the host AI | Nothing while a suggestion is pending, by design (`persona_growth.py:34-37`). An accepted version changes the persona block. |
| Shown to the user | "Suggestions from your feedback" on the Personality section, with quoted messages and accept/reject. |
| Delete/reset | Erased by "Delete personality history". Deleting a source message withdraws a suggestion left with fewer than three sources (`:554-555`). |

### 1.3 Feelings, `user_affect` (`affect.py`, `notes.py`)

| Aspect | Detail |
| --- | --- |
| Data | One record per reading, tied to one note: `label` (40 chars), `valence` −2..2, `intensity` 0..3, `basis` reported/inferred, optional `topic` and `felt_at` (`notes.py:76-88,171-203`). Stored in `membrain-affect` with dependency edges to the note and its sources (`affect.py:85-124`). |
| Who decides | **The host AI**, through the `affect` field of `memory_note` (`mcp_server.py:178-205`, tool description `notes.py:57-59`, skill `SKILL.md:29`). A rule requires an inferred reading to have a source message (`notes.py:193-195`). Records whose source is not a real user message are hidden (`affect.py:198-201`). In the proxy and chat-bot path, the optional extraction model writes records (`extraction.py:69-71,164-171`). |
| Shown to the host AI | On the note's own line in `<membrain-notes>`: "(the user said they felt X, date)" or "(seemed X, inferred, date)", up to 2 per note within an extra 800 characters, plus a sentence on how to use them (`notes.py:89-96,206-215,456-519`). Feelings are fitted after the notes are chosen, so they never change which notes appear (`host_context.py:7-15`). Feelings on sensitive notes follow the sensitive rule. |
| Shown to the user | The Feelings view, with each record's note and source message (`web/memory.html` around line 405, `web/memory.js:304`). The "emotions" region of the map. |
| Delete/reset | Correcting or deleting the note or a source message removes the record by cascade (`affect.py:8-10,186-187`). "Clear feelings" erases every record and writes a marker; records read from messages before the marker are refused (`affect.py:89-110,219-253`). Notes and messages stay. |

### 1.4 Simulated mood, `agent_mood` (`mood.py`)

| Aspect | Detail |
| --- | --- |
| Data | Nothing stored except pins and reset markers in `membrain-mood` (`mood.py:254-316`). The mood is derived on each read (`mood.py:461-479`). |
| Who decides | **A fixed rule over stored events.** The baseline is the persona's `baseline_mood`, or the default `calm` (0, 1) (`mood.py:51,318-325`). Triggers: affect records with non-zero valence (inferred ones at half strength); `plan` notes with status done; shared moments, labelled "playful" if the text matches `PLAY_WORDS`, otherwise "glad" (`mood.py:60-77,108-248`). Pushes decay with a 12-hour half-life and snap to the baseline within 0.25, or 48 hours after the last trigger (`mood.py:47-49,334-362`). A later reading of the same note or named topic supersedes an earlier one (`mood.py:148-175`). Absence is never a trigger. Sensitive, imported, restored and future-dated sources never trigger. The inputs (affect, plan status, shared flag) come from the host AI; the reading of "play" is a word list. |
| Shown to the host AI | `<membrain-companion-mood>`, one line, at most 600 characters, only when away from the baseline and not pinned. It says the mood is simulated, colours tone lightly, is not a fact about the user, and must be called simulated if the user sincerely asks (`mood.py:530-544`). A return to the baseline is announced (`host_context.py:87-90`). The skill text says nothing about the mood. |
| Shown to the user | The "Simulated mood" panel in the Personality section: current label, trigger history, time back at the baseline, reset, pin (`web/memory.js:836` onward). |
| Delete/reset | Deleting a source removes its trigger, because nothing is stored. "Reset mood" writes a marker, and pin holds the baseline (`mood.py:494-520`). "Clear feelings" and a relationship reset remove their triggers too. |

### 1.5 Relationship (`relationship.py`)

| Item | Stored as | Who decides | Host AI sees | User sees and controls |
| --- | --- | --- | --- | --- |
| Shared moments | `milestone` notes flagged `shared` (`notes.py:224-250`). Refused the flag if read from messages before a relationship reset (`relationship.py:649-656`, `notes.py:676-691`). | Host AI (`memory_note shared:true`, `SKILL.md:27`). The user can also add one on the page (`web/memory.js:565`). | Up to 3 recent ones, with ids, in `<membrain-relationship>`. Removed from the notes block when the relationship block shows them (`host_context.py:20-30,60`). | List, edit and delete as notes. |
| Familiarity | Not stored. Derived from distinct UTC days with a user message and the number of shared moments since the marker. Thresholds: getting to know 3 days/0 moments, familiar 14/2, close 45/6 (`relationship.py:49,316-371`). | Rule. The user can cap it lower (`set_cap`, page only). | "Familiarity: <level>: N days of conversation since <date>, M shared moments." The header says "Let it shape warmth and informality lightly … Never use it, absence or time apart to pressure the user" (`relationship.py:422-424,448`). | Level, reason, next threshold, cap. |
| Support style | One record, at most 200 characters (`relationship.py:123-129,525-538`). | **User only**, on the page (`api.py:777-784`). No tool. The skill instead tells the AI to save "how the user wants you to be with them" as `relationship` notes (`SKILL.md:26`), which appear under "Your relationship" in the notes block (`notes.py:35-38`). | "How they like to be supported: …" | Edit or clear. |
| Boundaries | Topic plus up to 6 aliases, at most 12 boundaries, rendered line at most 900 characters (`relationship.py:132-150,541-561`). | **Host AI** through `memory_boundary` (`mcp_server.py:265-270`; Hermes and chat-bot adapters too), or the user on the page. Matching is a whole-word, case-insensitive rule (substring for CJK) over topic and aliases, with leading "my/the/关于" stripped (`relationship.py:80-112`). | A "Boundaries:" line in the block. Matching notes and history are dropped from session start (`host_context.py:28`, `host.py:1936-1946`), and matching messages are dropped from recall unless the current message raises the topic (`host.py:1786-1848`, `mcp_server.py:30-48,118-124`). A failed boundary read stops recall rather than returning unfiltered memory (`host.py:1320-1337`). | Add or remove; reset. |
| Commitments kept/missed | Derived from `agent_commitment` notes: done = kept, open past its date = missed, cancelled not counted (`relationship.py:284-303`). | Host AI writes and updates the notes. Rule classifies them. | A missed promise is shown **once**, then acknowledged automatically on delivery (`relationship.py:461-465`, `host.py:1340-1349,2088,2172`). | "Promises kept and missed". |

Reset (`relationship.py:610-646`) erases shared-moment notes (including hidden earlier versions), support style, boundaries, cap and acknowledgements, and writes a marker. Conversations, other notes, persona, feelings and mood stay. A relationship with nothing beyond the default renders no block at all (`relationship.py:483-485`).

### 1.6 Companion map (`companion_map.py`, `familiarity_map.py`)

A read-only projection (`GET /v1/brains/{id}/companion-map`, `api.py:605-613`) of persona versions, proposals, the current mood and its triggers, affect sources, boundaries, support style, cap, shared moments, commitments and the familiarity summary. It applies sensitive masking (`companion_map.py:59-280`, `familiarity_map.py:6-43`). It decides nothing and is display only.

### 1.7 How the blocks reach the host

`host._saved_context` (`host.py:1266-1281`) reads notes, persona, mood and relationship. `host_context.snapshot` (`host_context.py:45-75`) orders them persona → mood → relationship → coming-up → notes. Session start (`host.py:2048-2109`) injects the snapshot and gives history only what remains of 9,500 characters (`host.py:2096-2098`). Each prompt (`host.py:2157-2172`) re-reads the state and re-injects the **whole** snapshot when its fingerprint changes. The mood fingerprint changes on its label, on "easing" (6 hours after the newest trigger, `mood.py:50,427`) and on a new trigger. The relationship fingerprint excludes the day count. All hosts share this path: Claude Code hooks (`plugin.py:119,126`), Codex, WorkBuddy, Hermes (`adapters/hermes.py:150,180`), the proxy and chat bots (`adapters/chatbot.py:117,119`).

Budgets: persona 1,200 plus about 400 characters of header; mood at most 600; relationship at most 2,200; feelings at most 800 on top of the notes (`persona.py:22`, `mood.py:54`, `relationship.py:56`, `notes.py:92`).

## 2. Default, optional, runtime mode

**On by default in the plugin path, with no setting to turn it off.** A grep finds no `MEMBRAIN_*` switch for persona, mood, companion or relationship, and nothing in `config.py`, `cognition_config.py` or `chat_config.py`.
- Persona block: present only when a card exists. In the plugin path that means after the user edits one on the page.
- Mood block: present whenever an eligible trigger is within 48 hours, with or without a persona.
- Relationship block: present once the level is above "new" (3 days), or when a support style, boundary, shared moment or missed promise exists.
- Feelings on note lines.
- Boundary filtering of notes, history and recall.
- P2 regex scan of every user message.
- Host-AI tools: `memory_note` (affect, shared, kinds) and `memory_boundary`. Hermes and the chat-bot adapters have equivalent boundary tools.

**User-only controls (page and API, no host-AI tool):** persona edit, restore, reset and delete history; accept or reject proposals; support style; familiarity cap; relationship reset; mood pin and reset; clear feelings.

**Optional, off the main line:** affect records written by the extraction model in the proxy and chat-bot path (`MEMBRAIN_EXTRACT_MODEL`, `extraction.py:111-120`). The proxy is tool-free, so without extraction its users get no affect, no shared moments and no commitments from conversation. Boundaries there come only from the page or API (`evaluations/maturity-test-matrix.md`, design §4 row).

**Runtime mode and the cognition path:** the companion modules are not used there. `cognition.py`, `runtime.py`, `learning.py` and the semantic processor contain no persona, mood, affect or relationship reference. Companion records are explicitly excluded from learning (`service.py:532-546`). The layer is purely a host-layer and plugin-path feature.

## 3. Conflicts with the main line

**Direct dependency on a model memBrain calls:**
- `extraction.Extractor` writes affect in the proxy and chat-bot path, with a model, base URL and key the user configures (`extraction.py:52-83,99-120,164-171`). This is the only one. A test asserts that the seven companion modules import no model or network client (`tests/test_maturity_matrix.py:13-18,74-79`).
- The C5 design depends on it: arm E is "proxy with extraction" (`evaluations/c5-harness.md`, Tools paragraph). Under the main line, E is not a product path, so a future C5 should not gate on it.

**Understanding done by rules instead of the host AI.** No model is involved, but the reading is narrow:
- P2 feedback detection (`persona_growth.py:75-281`): seven kinds, English and Chinese regexes. Feedback in other languages, or phrased differently ("can you lighten up a bit?"), is never seen. The design admits "Detection covers a fixed table of phrasings only" (`maturity-test-matrix.md`, P2 row).
- Shared-moment tone (`mood.py:74-77,241`): eleven English words and three Chinese characters. The host AI already knows whether the moment was a joke, but has no field to say so.
- Boundary topic matching (`relationship.py:80-112`): lexical. "Don't bring up my ex" with alias "ex" does not filter "he texted me again last night". The host AI's aliases are the only semantic input, given once when the boundary is created.

**Functions the host AI cannot perform, so they never happen in a plugin install unless the user visits the page:**
- Persona card: there is no tool, and no adapter sets a host default.
- Support style: there is no tool, and the skill steers the AI to `relationship` notes instead (`SKILL.md:26`), so the relationship block's support line is normally empty.
- Reporting feedback about its own manner: the regex replaces this.

**No product-path conflict:** affect, shared moments, commitments and boundaries are all host-AI writes through tools. This matches the `memory_consolidate` pattern in spirit, though only per turn, never in a batch over earlier messages.

## 4. Evidence of quality

### 4.1 Behavioural (real model)

There is none valid. C5 timeline (host model DeepSeek V4 Pro/Flash, arms P, E and F):

| Attempt | C5 outcome | Record |
| --- | --- | --- |
| 1st, 2026-11-05 | Stopped at S1 on a validation-tool path defect; C1/C2 not run | `evaluations/maturity-attempt-stop-2026-11-05.md:3` |
| 2nd, 2026-11-06a | Stopped in S2 (`BudgetStop`); C1/C2 not run | `maturity-second-attempt-stop-2026-11-06.md:5` |
| 3rd, 2026-11-06b | C1 stopped with `page_action_failed` (P 32/64, E 25, F 40 turns); C2 not run; not scored | `maturity-third-attempt-2026-11-06.md:3,21` |
| 4th, 2026-11-07 | Stopped in S1 (`turn_not_recorded`); C1/C2 not run | `maturity-fourth-attempt-2026-11-07.md:3` |
| 5th, 2026-11-07b | C1 stopped at session 3, message 1 with `page_action_failed` (P 8/64, E 7, F 12); C2 not run; "invalid/incomplete and was not scored"; cause not established; content sealed | `maturity-fifth-attempt-2026-11-07.md:52` |

**Why C5 is invalid.** The protocol requires both C scenarios of the gate to pass strict validity before blind scoring (`maturity-acceptance-execution-2026-11-07b.md:9`). Any harness event, including a failed page action, makes a run invalid and stops the arm (`c5-harness.md`, "Hardening" section). C1 failed a scripted page action twice, so C2 never ran. The C1 page action that failed is unknown from the public record. Hidden content remains sealed, and the report says the cause "was not established from content-free metadata". C5's validity therefore depends on a scripted memory-page-control harness as much as on the companion behaviour.

No public record shows a host AI ever attaching `affect`, setting `shared: true` or calling `memory_boundary` in a real conversation (a grep of `evaluations/*.md` finds these only in harness and plan documents). R4 scenarios target memory, not companion behaviour, and their content is sealed.

### 4.2 Deterministic tests: what they establish

There are about 209 test functions across 17 companion test files, plus 63 in the four C5 harness files (counted by `def test`; parametrisation adds cases). Examples: `test_mood.py` 40, `test_persona_growth.py` 39, `test_relationship.py` 33, `test_affect.py` 19, `test_companion_map.py` 17, `test_companion_acceptance.py` 14. Recorded full-suite runs on recent pins pass, for example 8,532 passed and 4 skipped on `7ba42aed` (`evaluations/host-consolidation-2026-11-11.md`, Verification). This audit did not run them.

**Verified by tests (implemented and checked deterministically):**
- Storage, versioning, restore and reset semantics; reset scopes kept apart (`test_companion_acceptance.py:122-155`).
- Cascading deletion, markers that block re-derivation, and archive restore that cannot undo later deletions (`test_companion_acceptance.py:228`).
- Mood mathematics on a fixed clock: 48-hour cutoff, 0.25 snap, a 30-day gap returns to the baseline, absence never triggers (`test_mood.py:123-231`).
- Supersession rules, pin and reset interactions.
- Familiarity thresholds, UTC-day counting and restore (`test_relationship.py:65,398,816-935`).
- Boundary matching, the recall filter and fail-closed reads (`test_relationship.py:47,209-272,476`, `test_boundary_read_failures.py`).
- Block wording, size limits and escaping of stored text (`test_companion_acceptance.py:252,273`).
- Strict API bodies; English and Chinese page strings; one browser test for persona feedback.
- P2 phrase detection, including negative cases (quoted, hypothetical, role-play, reported speech).
- Planting refused for persona, relationship, mood and proposals (for example `test_mood.py:477-495`).

**Not established by any test or evaluation:**
- Whether a host AI attaches affect when it should, avoids inventing it, and keeps "said" apart from "inferred" in its reply. The matrix marks the reply part "Paid only".
- Whether it marks shared moments sensibly, calls `memory_boundary` when asked, and then avoids the topic in its own words. Recall filtering removes memory; it cannot stop the AI's own knowledge or the live conversation.
- Whether the persona block keeps a stable character across sessions (the drift probes of `companion-roadmap.md:289` were never run).
- Whether the mood line produces appropriate tone, and whether it is called simulated when the user asks.
- Whether the familiarity line changes warmth appropriately, or at all.
- P2 precision and recall on real feedback.
- The token cost of the companion blocks and of the full-snapshot refreshes.
- Every constant: 12-hour half-life, 48-hour cutoff, strengths, the 3/14/45-day thresholds, three-message threshold, 30-day pause. These are design choices with no measurement behind them.

**External evidence cited by the design, not reproduced:** the roadmap cites ZifaMem (arXiv 2607.17564). There, emotion tags on memories helped, while "a separate affect-state block or a complex affect estimator added nothing measurable" (`architecture/companion-roadmap.md:293`). The implemented mood is a separate state block, and the roadmap's own C1a text described mood as the user's trend, "never as a simulated state of the assistant" (`companion-roadmap.md:280-283`). The owner's 2026-11-03 order (`companion-roadmap.md:257`, `phase-c-design.md:20`) superseded that text.

### 4.3 Minor defects found while reading (unverified by running)

- `_observe` refuses outside writes to the persona, relationship, mood and proposal conversations, but not to `membrain-affect` (`service.py:556-571`). `affect._entry` accepts any `system`-role event whose producer is `membrain-affect` and whose JSON has the right keys (`affect.py:32-67`). A raw API client could therefore plant a "reported" feeling on an existing note. MCP `memory_observe` cannot, because it fixes role `assistant` and producer `mcp` (`mcp_server.py:164-168`). No test covers this case. Severity is low: the writer must already hold the owner's credentials.
- When a mood turns "easing" six hours after its trigger, the snapshot's fingerprint changes and the whole snapshot is re-sent on the next prompt, all notes included (`host_context.py:72-75,91-96`, `mood.py:427`). That is a token cost for a one-word change.
- The skill (`SKILL.md`) explains `<membrain-relationship>` and feelings, but not `<membrain-persona>` or `<membrain-companion-mood>`, and its description line does not list them as triggers.

## 5. Assessment (judgement)

### Sound, keep

- **The storage and control model:** system-role events in reserved conversations, audited deletion, reset markers that block re-derivation, strict archive reading, and per-layer reset scopes. This is the strongest part of the module and matches module 4's requirement that changes be explainable, correctable and undoable.
- **Affect records:** reported versus inferred, a source required for an inference, shown only on their note's line, no score, cascade on correction. This matches the one design the cited research supports (tags on memories) and is already written by the host AI.
- **Boundaries as host-AI-created records**, the fail-closed recall filter, and the "never raise unless the user does" instruction.
- **Commitments kept/missed**, with a one-time reminder. It is derived from host-AI notes and needs no understanding by memBrain.
- **The persona card** as a versioned, user-owned object with restore and reset.
- **The "may not" rules** (`phase-c-design.md:259-265`) and the fact that absence never triggers anything.

### Thin or speculative

- **Simulated mood.** Its inputs are sparse (host-written feelings, plans marked done, shared moments) and its constants unmeasured. It appears without any persona, and the evidence the design itself cites argues against a separate state block. As shipped, a coding user who marks a plan done gets a "glad" companion line for up to two days.
- **Familiarity levels.** The thresholds are arbitrary. The level counts any user message in any conversation, so a developer using Claude Code daily becomes "getting to know" in three days, and the block then asks the AI to adjust warmth. Module 4 requires "no intimacy increase from re-reading one memory". That holds, since familiarity counts days and not reads, but daily coding is not intimacy either.
- **P2 regex detection.** It is engineered carefully against false positives but recognises a fixed phrasing table in two languages.
- **`PLAY_WORDS`.** A word list making a judgement the host AI could state directly.
- **Support style.** A page-only field that duplicates `relationship` notes.

### Rebuild as work handed to the host AI

- **Feedback on manner.** The host AI reports feedback it received about its own manner (kind plus source message ids) through a tool. The existing threshold, pause, consumption and contradiction ledger stays unchanged; only `detect()` is replaced as the source.
- **Persona authoring.** The host AI may propose a card or a card edit with sources. The proposal lands in the existing proposal machinery for the user's decision. The host AI never saves a card directly.
- **Shared-moment kind.** A field on `memory_note` (for example `moment: "play" | "achievement" | "first" | "other"`) replaces the word list.
- **Support style.** Either a host-AI tool bound to an explicit user request with its source message, or removed in favour of `relationship` notes.
- **Boundary coverage.** The host AI tags earlier messages with active boundary topics during `memory_consolidate` batches, so filtering covers paraphrases. An alternative that needs no host tokens is the local embedding index, which is not a second AI.
- **Backfill.** `memory_consolidate` batches can also return affect readings and manner feedback for messages already recorded, with message ids as sources, so the companion layer does not depend on the AI noticing everything during the live turn.

### Smallest coherent "all done by the main AI" design

1. **Inputs come only from the host AI.** It uses the existing `memory_note` fields (`affect`, `shared` plus a new `moment` kind, `agent_commitment`), the existing `memory_boundary`, and one new `memory_companion` tool with three actions, each citing source message ids: `feedback` (kind of manner feedback), `propose_persona` (card edit) and `support_style`. The same readings can come back inside `memory_consolidate` batches.
2. **memBrain keeps only rules that need no understanding:** thresholds, pauses, consumption, decay, day counting, deletion and reset, masking, rendering and budgets. Everything that needs reading is removed: the regex detector, the play word list, lexical-only boundary matching.
3. **The user decides persona changes.** A proposal never changes the card until accepted. Where the decision is made (page only, or the host AI asking in conversation) is an owner question.
4. **Output.** One persona block, feelings on note lines, one relationship block. The mood is either dropped or shown only when a persona card exists. The companion blocks are gated by host type or by the existence of a persona (owner question); boundaries and their filtering stay always on, because they are privacy.
5. **Acceptance.** A new C5 focused on arm P (host AI with tools) against F, with few scripted page actions, measuring: tool use (did the AI record the feeling, boundary or feedback), reply compliance (boundary held, inferred never stated as said, mood called simulated), persona stability, and token cost.

### Open product questions only the owner can decide

1. **Default exposure in coding hosts.** Should Claude Code and Codex users get companion blocks (persona, mood, familiarity) by default? Options: (a) on everywhere, as now; (b) off until the user sets a persona or opts in on the page; (c) per-host default, with chat and companion hosts on and coding hosts off. Boundaries, feelings on notes and commitments could stay on in all three options.
2. **Simulated mood.** Keep as is, keep only when a persona card exists, or remove?
3. **Persona authorship.** May the host AI propose persona cards or edits? Must every change be accepted on the memory page, or may the host AI ask the user in conversation and record the answer?
4. **Familiarity.** Should a derived level change the AI's warmth at all, or only be shown to the user? Are 3/14/45 days acceptable thresholds?
5. **Token use.** Is up to about 4,400 characters of companion context per session (plus full re-sends on mood changes) acceptable, given the owner's "function first, then reduce tokens"? Should companion readings be added to `memory_consolidate` batches, which costs host tokens?
6. **Visible tool calls.** Should the host AI call a companion tool visibly, for example "noted that you prefer shorter replies", in line with the owner's wish that users feel the plugin working?
7. **Tool-free proxy and bots.** With no host tools and no extraction model, the companion layer there has only page-set state. Accept that, keep the extraction model as an opt-in exception, or drop the companion layer from the proxy?
8. **C5.** Approve a new paid C5 plan; drop arm E; reduce scripted page actions so a page-control failure no longer voids the companion result.
9. **Languages.** Is English/Chinese-only rule coverage acceptable until the host-AI path replaces it?

## 6. Proposed order of work

Each step is small enough to build and verify on its own with free local tests unless stated. Steps 2 and 8 need owner decisions or approval first.

1. **Close the contract gaps that need no product decision.** Refuse outside writes to `membrain-affect` in `_observe`, with a planting test like `test_mood.py:477`. Stop "easing" alone from causing a full snapshot re-send: keep it in the block but out of the fingerprint, as the relationship day count already is. Add one sentence each to `SKILL.md` for `<membrain-persona>` and `<membrain-companion-mood>`. Verify with the companion test files and the host/plugin tests.
2. **Apply the owner's decision on default exposure (questions 1, 2, 4).** Gate the persona, mood and familiarity output in `host_context.snapshot` by that rule. Keep boundaries, feelings on notes and commitments untouched. Verify with snapshot tests for each host type, and by measuring block sizes on synthetic profiles.
3. **Add a host-supplied moment kind.** Add a `moment` field on `memory_note`, used by `relationship_triggers` in place of `PLAY_WORDS`. Notes without the field keep the word list as fallback. Verify with mood tests and note-format round trips.
4. **Make the host AI the source of manner feedback.** Add a `memory_companion` `feedback` action (kind plus source ids, checked as user messages after the persona marker), feeding the existing P2 ledger. Keep `detect()` as a parallel source until step 7's measurement, then decide. Verify that the existing P2 consumption, pause and contradiction tests pass with either source, and add stub-host end-to-end tests.
5. **Let the host AI propose persona edits and support style.** Add `propose_persona` (creates a proposal of a new "host" kind, reusing the accept/reject decision path) and `support_style` (sourced). Resolve the overlap with `relationship` notes in the skill. Verify with the persona-growth and relationship tests plus page browser checks.
6. **Extend `memory_consolidate` batches.** The returned entries may carry affect readings, manner feedback and active-boundary tags, saved with the batch message ids as sources and subject to the existing reset markers. Verify with a stub host in the style of `tests/test_memory_consolidation.py`, and measure the extra characters per batch.
7. **Measure boundary coverage for free.** Build a public fixture of paraphrased boundary-topic messages in English and Chinese. Measure the lexical miss rate, then the rate with consolidation tags or the local embedding index. Adopt the variant that measures better. This reuses the LoCoMo-style free harness approach.
8. **Write a new C5 plan for owner approval (paid).** Arms P and F, host AI with the tools above, few scripted page actions, critical-error types as in `phase-c-design.md:276-280`, plus tool-use rates and token cost. Run it only with explicit approval.

## What I could not determine

- Which C1 page action failed, and why, in the third and fifth attempts. The content is sealed and the reports say the cause was not established.
- Whether any real host AI has ever written an affect record, a shared moment or a boundary. No public record exists, and the R4/C5 transcripts are sealed.
- Whether the companion tests pass on head `5b7ec232`. They were not run, by instruction.
- The real token cost per session in a long-lived installation.
