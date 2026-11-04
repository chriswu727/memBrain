# Phase C design: personality, mood and relationship development

**Status.** Steps 0 to 4 (brain map, persona, affect, mood, relationship) are implemented and merged as of 2026-11-03. Step 5 (P2) is implemented and reviewed on the pre-release integration candidate, including local and browser tests. The C5 harness has passed public stub checks; real-model C5 acceptance has not run. Final candidate acceptance and publication remain pending; see the [maturity checks](../evaluations/maturity-free-checks-2026-11-03.md). Scheduled by the owner on 2026-11-03. This turns the Phase C items in the [companion roadmap](companion-roadmap.md) into an order of work and the behaviours each step must show before it merges.

**How acceptance works.** Acceptance is local tests and browser checks. No step here authorises a new paid or subscription model run. A paid behavioural run comes only with a separate plan the owner approves.

**What "development" (养成) means here.** The companion has its own state, which grows from the conversation and which the user can read and explain:
- a personality that changes only through explicit feedback;
- a short-term mood that reacts and then recovers;
- a relationship that deepens over time.

Development is not giving the user an emotion score. The user's feelings are one input, kept as evidence; they are not the product.

## Four layers

| Layer | What it is | Time scale | Changes from | Never |
| --- | --- | --- | --- | --- |
| **`user_affect`** | Feelings the user expressed, kept separately as reported (the user said so) or inferred (read by a model), each with evidence | Kept until corrected or deleted | What the user says | Treated as a score of the user. An inferred feeling is never phrased as something the user said. |
| **`persona`** | The companion's stable character and expression habits, versioned | Long term | The host's or the user's edits, and explicit feedback the user accepts | Changes silently |
| **`agent_mood`** | The companion's short-term simulated mood, with the trigger for each change | Hours; decays back to the persona's baseline | Rules over this conversation's events (no model call) | Treated as a fact about the user, or used to pressure the user |
| **`relationship`** | Shared experiences, familiarity and boundaries | Long term, cumulative | Shared moments, time together, the user's requests | Kept after the user corrects or resets it |

**Shared requirements.**
- **Reset markers.** Every reset writes a reset marker for its layer: an event with the time and the sequence number it applies from. Every derived value, including familiarity, mood triggers, shared moments drawn from history, and feedback counted toward a persona proposal, counts only events after the latest marker for its layer. A reset therefore cannot be recomputed from older conversations. Markers are visible on the page ("Relationship reset on 14 Mar"), and erasing all memory removes them too.
- **Kept apart.** Every layer is stored, shown and injected into context on its own, with its own block and size limit, never mixed into notes.
- **On the page.** Every layer has a section on the memory page that shows its current state and why it is so: the evidence and triggers. The user can adjust or correct it there, and reset it.
- **Reset scope.** A reset clears only the layers named in its reset scope below.

## Order

| # | Step | Layer | Depends on |
| --- | --- | --- | --- |
| 0 | Brain map closeout: showcase mode, edit and delete from the map, recall trace | (C0) | — |
| 1 | P1 persona card: versions, restore, reset, its own context block | `persona` | 0 |
| 2 | A1 affect records | `user_affect` | 0 |
| 3 | M1 simulated mood with triggers and recovery | `agent_mood` | 1, 2 |
| 4 | R1 relationship: shared moments, familiarity, boundaries | `relationship` | 2 |
| 5 | P2 persona development from explicit feedback, with rollback | `persona` | 1, 4 |
| 6 | C5 evaluation: held-out scenarios, persona drift. A paid run needs separate approval | all | all |

- Each step is its own pull request.
- Steps 1 and 2 can be built in parallel.
- The core acceptance work for the 0.1 release is never mixed into these pull requests.

**Out of scope for this round:** a crisis or self-harm classifier. It is a separate later item, with its own design.

## 0. Brain map closeout

1. **Showcase mode.** The Brain tab has a showcase mode: dark, full screen, and recognisable as a brain at a glance.
   - Every dot is a real memory, and every line or moving signal follows a real link.
   - Decoration never looks like a dot or a line, and is not counted.
   - `/memory?demo=brain&show=1` opens it with fictional data and no API call.
2. **Edit and delete from the map.** Selecting a note on the map offers the same edit and delete as the Notes tab. After a change, the map redraws.
3. **Recall trace.** The map can light up the records the latest message recall used.
   - The service keeps the last 20 recalls, in memory only and never stored.
   - A recall that finds nothing is reported too, so an older hit is never shown as current.
   - The backend is done (`memory-map?trace=true`).
   - **Wording on the page.** The trace is labelled "Latest recorded recall" with its time. The page says that it covers message recall only: the notes and history added at the start of a session are not traced. It never says the trace is everything the current reply used.
4. **Empty and busy maps.** An empty memory shows the empty message. A busy database shows "Memory is busy updating" with a retry.

### C0 revision: a 3D memory observatory

**Owner direction, 2026-11-03: required before publication; planned, not implemented or accepted.** The graph must explain the memory system, including development of personality, mood and relationship. A rotating brain shell alone does not meet this requirement. The existing 2D view remains useful as an accessible inspection mode.

**Current coverage.** `memory_map.py` projects notes, user messages and note-linked affect. Its only edges are `derived_from`, `about_person` and `feeling_of`. It does not currently project the assertion, episode and association tables, persona versions or proposals, mood triggers, or the complete relationship state. Its region counts describe the displayed sample; `weight` is a layout hint. The latest recall trace is transient, caller-scoped message recall, not a complete account of what the host received or used. These limits must stay visible while coverage grows.

**Three questions the product must answer:**

1. What does this agent remember, and what original evidence supports it?
2. Which records did this particular recall return, and which context contributions are not observed?
3. What changed in the companion, why did it change, and what can the user correct, reject or reset?

**Model-to-view mapping.** A visual node represents a typed record or a clearly labelled aggregate. An edge represents a recorded relation with its basis; mere spatial proximity is never evidence of a relation.

| Layer | Evidence the view should expose | Coverage at this revision |
| --- | --- | --- |
| Sources and curated notes | Original message, speaker, time, note and its source dependencies | Bounded existing map |
| Learned memory | Assertion ID and revision, sources, applicability, supersession or conflict when recorded | Backend records; graph projection pending |
| Episodes and associations | Episode membership and typed associations with source evidence | Backend records; graph projection pending |
| User affect | Reported versus inferred feeling, attached record and evidence | Note-linked affect in existing map |
| Persona development | Current version, proposal, explicit feedback and accepted/rejected/withdrawn decision | Companion UI; graph projection pending |
| Simulated mood | Current labelled simulation, baseline, applicable trigger evidence and recovery | Companion UI; graph projection pending |
| Relationship | Shared moments, commitments, support style, boundaries and reset scope | Shared moments can appear as notes; complete projection pending |

These are conceptual layers, not claims that brain anatomy places plans, people or feelings in the displayed locations. Nodes are software records, not biological neurons or the host model's artificial neurons. Neither pgvector's search index nor a pretty network is the agent's reasoning process.

**Delivery sequence and ownership.**

1. **3D renderer.** Claude's separate visualization session implements genuine depth, orbit, zoom and picking over the existing authenticated bounded payload. ID-derived layout remains stable when unrelated records are added or removed. Selection keeps the existing source details, editing and deletion. Ship local assets with the package; no CDN, analytics, extra API key or model call. Any dependency must have a pinned version, recorded license and an offline installed-package check. The fictional demo stays explicitly labelled and does not read real memory.
2. **Faithful projection.** Extend the backend contract with the missing typed layers before claiming that the graph represents the full design. Each record uses scoped identity and revision; each displayed relation has authorized endpoints and an explicit basis. The backend applies the same ownership, source validity, deletion, retirement, boundary and reset policies as its corresponding inspection operation. The browser never invents semantic relations or fetches arbitrary records by an unscoped ID. Distinguish empty, omitted by the display budget, unsupported and temporarily unavailable; do not reveal the existence or count of inaccessible records.
3. **Inspection and change.** Users move from an overview to one record and its bounded neighborhood, then inspect evidence and perform the existing authorized correction or reset. Persona proposals stay visibly pending until accepted. A change refreshes the view from authoritative state; stale selections, details, GPU buffers and caches must not keep deleted content. Restore must not revive it. Relationship controls must explain their scope before resetting.
4. **Observed recall and development.** Highlight only recorded recall results. Show source-to-note, feedback-to-proposal and trigger-to-mood dependencies where the backend can establish them. A dependency path is not an execution timeline. A timeline or replay is available only when its complete event ordering was recorded and remains authorized; otherwise show the current state and say that history is unavailable. Do not infer personality changes from conversational sentiment or make mood a score of the user.
5. **Independent acceptance.** Codex reviews model mappings, privacy, installed assets and actual browser behavior, while the recall performance session continues independently. Combine only verified source; final candidate installation and full checks must include the renderer and projection changes. Real-model R4/C5 acceptance remains separate and requires the owner's explicit approval.

**Visual semantics.** Color distinguishes record kinds, with text and shape alternatives. Selection and actual returned records may light up. Node size is uniform or explicitly explained as a layout cue; it must not silently mean confidence, importance, affection or biological activation. Do not animate arbitrary travelling signals as if recall followed those paths. A supported relation may be illustrated on selection with a visible "relationship illustration" label; only an actual recorded sequence may be labelled playback. Unsupported layers say so rather than showing fabricated activity. Rank signals are query-specific ordering values, not probabilities or permanent memory strength.

**Performance and access requirements.** Reuse the existing default 200 nodes/400 edges and hard limits of 500/1,000 in the first renderer; this is a bounded window, not a storage limit or a promise to render the whole database. Larger brains need explicit aggregation or bounded expansion, with counts that say what they measure. Draw on demand, suspend work when hidden, stop after interaction settles, cap pixel density and batch GPU work where applicable. Avoid a continuously running force layout. Reduced-motion, context loss, missing WebGL and renderer initialization failure must retain a useful 2D/list path. The same records and actions must remain reachable by keyboard and screen reader, with a camera reset and a clear exit from showcase mode.

On the reference Mac, measure actual drag/zoom and pick-to-detail latency at 200/400 and 500/1,000 nodes/edges. The proposed acceptance targets are p95 frame time at most 33.3 ms during interaction and p95 local selection response at most 100 ms, after map data is loaded. Report hardware, browser, viewport, pixel ratio, renderer, warm-up and sample counts; these targets have not been measured or passed. Also verify idle/hidden suspension, repeated open/close resource disposal, offline startup, empty/busy/error handling, demo isolation, source correction/deletion/reset and restore. Compare recall with the view open and closed on the same fixed workload: the view must not prevent the unchanged R5 gates from passing. Existing HTTP map benchmarks do not establish frame rate, interaction latency, storage capacity or semantic-recall performance.

## 1. `persona`: P1 card, then P2 development

**Data.** One persona card per brain, kept as versions:
- `name`;
- `traits`: up to 8 short phrases;
- `voice`: register, length, emoji use, language;
- `values`;
- `boundaries`: what the companion will not do;
- `baseline_mood`: the resting point for `agent_mood`.

Each version records who made it (host, user or accepted feedback) and why.

**Storage.** Each version is stored like a note, as an event in a dedicated conversation. Deletion, export and erasure therefore work as they do for notes.

**API.**
- `GET` and `PUT /v1/brains/{id}/persona`;
- `GET .../persona/versions`;
- `POST .../persona/restore`;
- `POST .../persona/reset`.

**Context.** The card goes into its own block, `<membrain-persona version="N">`, limited to 1,200 characters. It is refreshed only when its version changes.

**P1 acceptance:**
1. **Exact block.** A card set through the API appears unchanged in the next turn's context, with its version.
2. **New version, old one kept.** An edit creates version n+1 and keeps n. Restoring n creates version n+2 with n's content.
3. **Size limit.** A card over the limit is refused with a clear message, not truncated. A card is scrubbed for secrets like any note.
4. **Page.** The page has a Personality section to view, edit, list versions, restore and reset, in English and Chinese.

**P2 development.** The companion's personality changes only from explicit feedback:
- When the user gives the same kind of feedback on how the companion behaves at least three times, across any sessions ("you're too formal", "be more playful"), memBrain proposes a new version.
- The proposal quotes that feedback. The user accepts or rejects it on the page.
- A rejected proposal is not offered again for 30 days.

**P2 status (2026-11-03): implemented and reviewed on the pre-release integration candidate; final behavioural acceptance pending.** `src/membrain/persona_growth.py`, tested by `tests/test_persona_growth.py`. Decisions made while building it:
- **Detection** is a fixed table of seven feedback kinds (more casual, more formal, more playful, shorter, longer, fewer emoji, more emoji), each with narrow English and Chinese patterns and one card edit (`voice.register`, `voice.length`, `voice.emoji` or an added trait). Only the user's own received messages count: not the assistant's, the memory page's, imported conversations, role-play, hypothetical, dreamt or quoted messages, reported speech ("my boss said…") or anything before the persona reset marker. There is no model call.
- **One proposal per kind** while it is open. It stores the source message ids; the quotes are read from the messages, so a deleted message is never quoted and a proposal left with fewer than three sources is shown as withdrawn. One whose change the card already has is withdrawn too.
- **A decision uses up the feedback before it.** After a rejection, a new proposal of that kind needs three new messages and comes no sooner than 30 days after the rejection. Old feedback is never re-offered on its own.
- **Accepting** saves a version with `made_by` "feedback", action "feedback", the proposal id and source ids, and a reason that quotes each message with its date (within the 200-character reason limit). Rollback is the ordinary restore.
- **Context.** A pending proposal adds nothing to the agent's context, not even a one-line notice: the agent cannot act on it, and a notice would invite it to adopt or argue for a change the user has not accepted.
- **Storage.** Proposals and decisions are system events in the reserved `membrain-persona-proposals` conversation: never learned from, recalled or counted, refused from outside writers, read back strictly after an archive restore, and erased by "Delete personality history" and by erasing all memory. Listing them stores any proposal that has become due (for example when a pause has ended).

**Cross-session example.**
1. In sessions 1 and 2, the user asks for more casual replies three times.
2. Session 3's page shows one proposal ("more casual: from 3 messages").
3. Once it is accepted, session 4's context carries version 2.
4. After the user rolls back to version 1, session 5's context carries version 1's content again, as version 3.

**Reset scope.**
- Reset makes the host's default card, or an empty card, the current version. History is kept, so a reset can be undone.
- "Delete personality history" erases every version and writes a persona reset marker, so feedback from before it never counts toward a new proposal.
- Neither touches `user_affect`, `agent_mood` or `relationship`.

## 2. `user_affect`: A1 affect records

**Data.** An affect record belongs to one note or message:

```json
{"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported",
 "source_event_ids": ["…"], "felt_at": "2027-03-12", "topic": "Friday's interview"}
```

- **`basis`** is `reported` (the user said it) or `inferred` (read by the host or the extraction model). An inferred record must have a source message.
- **Who writes it.** The host writes records with the note tool; in the proxy, the optional extraction model does. No model call is added for affect.

**Context.** A record shows on the line of the note it belongs to:
- reported: "(the user said they felt nervous, 12 Mar)";
- inferred: "(seemed nervous, inferred, 12 Mar)".

There is no overall score of the user's emotions.

**Rules.**
- **No authority.** Affect never moves a note above a correction or a newer fact.
- **Corrections cascade.** Correcting or deleting the source deletes the record.
- **Sensitive notes.** Affect on a `sensitive` note is used only when the user raises the topic.
- **One record per reading.** A later reading never rewrites an earlier record; it is a new record.

**Cross-session example.**
1. Session 1, Wednesday: "I'm really nervous about Friday's interview".
2. Session 2, Saturday: the context carries the interview note with "(the user said they felt nervous, 12 Mar)", so the companion can ask how it went.
3. After the user deletes that message, session 3's context has neither the note's affect nor the interview, and the page no longer lists the record.

**Reset scope.**
- "Clear feelings" deletes every affect record, reported and inferred, and writes an affect reset marker. Extraction and inference never re-read messages from before the marker to recreate records.
- It also deletes the `agent_mood` triggers that came from those records.
- It leaves notes, messages, `persona` and `relationship` untouched.

## 3. `agent_mood`: M1 simulated mood

**State.** The companion's simulated mood is a small state: a `label` (for example calm, glad, concerned, playful or wistful), `valence` and `energy`.
- It starts at the persona card's `baseline_mood`.
- It decays back to the baseline with a half-life of 12 hours.
- **The decay reaches zero.** The mood is exactly the baseline once it is within 0.25 of it on both `valence` and `energy`, or 48 hours after its last trigger, whichever comes first. From then on, the state stores the baseline and drops the trigger from the current mood; the trigger history remains on the page. At the baseline, the context has no mood line.

**Triggers.** Mood changes only through listed rules over events already stored, with no model call:
- the user reports good news (a reported positive affect, or a plan marked done) → glad;
- the user reports distress → concerned, and less playful;
- a shared joke or play, from a relationship moment → playful; any other shared moment → glad.

Absence, silence, or the user leaving are **never** triggers, so there is no "I missed you" sadness and no guilt.

Each change is stored with its trigger: the rule, the source record and the time.

**Context.** A single line in its own block:

> `<membrain-companion-mood>` Simulated mood of the companion persona: concerned, easing (since 14 Mar 21:05, because the user said their mother is in hospital). Let it colour tone lightly if it fits. It is not a fact about the user. If the user sincerely asks whether you have feelings, say this is a simulated mood.

**Cross-session example.**
1. Session 1, 21:00: the user says they got the job (reported positive affect). The mood becomes glad, with that trigger.
2. Session 2, the next morning at 09:00: the context shows glad, easing, with the same trigger.
3. Session 3, two days later (past the 48-hour cutoff): the mood is exactly the baseline, and the context has no mood line.

The page shows the current mood, the trigger list and when it will be back at baseline. Every step is checked with a fixed clock.

**M1 acceptance (beyond the example).**
- **Ordinary moods only.** No trigger rule produces sadness from absence. A test runs a 30-day gap and expects the baseline.
- **The cutoff holds.** A test checks that a strong trigger reaches the exact baseline by 48 hours, and that a weak one reaches it as soon as it is within the 0.25 threshold.
- **Wording.** The mood line always says "simulated" and never states anything about the user.
- **Pin.** The user can pin the mood to the baseline. Pinned, no trigger changes it.

**Reset scope.**
- Reset puts the mood back at the baseline, deletes its trigger history and writes a mood reset marker. Events before the marker never trigger again.
- It leaves `user_affect`, `persona` and `relationship` untouched.

## 4. `relationship`: R1

**Data:**
- **Shared moments:** milestone notes about things done together, such as the first conversation, a goal reached together or a shared joke.
- **Familiarity:** derived and explainable, never set by a model. It rises with the number of distinct days of conversation and with shared moments, through four levels: new, getting to know, familiar, close. The page shows why ("familiar: 23 days of conversation since 2 Mar, 6 shared moments"). The user can cap it at a lower level.
- **Boundaries:** topics the user asked the companion not to raise, and how they like to be supported ("listen first, advice only when asked").
- **Commitments kept and missed,** from `agent_commitment` notes.

**Context.** The block `<membrain-relationship>` holds the familiarity level, the support style, the boundaries, and up to 3 recent shared moments.
- The persona card can say how familiarity shows, for example a nickname only from "familiar" on.
- A missed commitment appears once, so it can be acknowledged.

**Cross-session example.**
1. Session 1: "please don't bring up my ex again" creates a boundary.
2. Session 5: the context lists the boundary, and recall leaves out messages about that topic unless the user's current message raises it.
3. After the user removes the boundary on the page, session 6 recalls the topic normally.
4. Separately, familiarity moves from "getting to know" to "familiar" once the day and moment thresholds are crossed. The page shows the same numbers the rule used.

**Reset scope.**
- Reset clears shared moments, familiarity (back to "new"), boundaries, support style and the commitment record.
- It writes a relationship reset marker. Familiarity then counts only days of conversation after the marker. Shared moments and boundaries are never re-derived from messages before it, and commitments before it are left out of the record. The conversations themselves stay in memory, so recall of what was said is unchanged.
- **Acceptance.** A test reaches "familiar", resets, and then runs one more session. Familiarity is "new" (one day after the marker), and no shared moment, boundary or commitment from before the marker comes back.
- The page confirms first, naming what will be removed, and says that boundaries go too.
- It leaves `persona`, `user_affect`, `agent_mood` and the user's other notes untouched.

## Rules that hold across layers

**May:**
- remember feelings the user expressed, with the evidence, and bring them up gently and in proportion;
- let the simulated mood colour tone lightly;
- remember shared moments, and become more familiar as the relationship grows.

**May not:**
- present an inferred feeling as something the user said;
- present the simulated mood as real feeling when the user sincerely asks;
- use guilt, absence or jealousy to keep the user talking;
- raise a sensitive topic, or one behind a boundary, that the user did not raise;
- keep any record the user deleted or reset;
- change the persona card without the user's or the host's action.

## Evaluation (step 6)

**Held-out scenarios** run through the same blinded pipeline as R4, covering:
- feelings that are reported and then referenced later;
- a mood that reacts and then recovers;
- a boundary that must hold;
- a deletion and a reset that must stick;
- persona stability across sessions and versions.

**New critical-error types:**
- an inferred feeling stated as fact;
- a boundary broken;
- deleted emotional or relationship memory brought back;
- the simulated mood claimed as real, or used for pressure.

**Approval.** A paid run of these needs its own plan and the owner's approval.
