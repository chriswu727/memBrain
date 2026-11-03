# Phase C design: personality, mood and relationship development

**Status.** Scheduled for implementation (owner, 2026-11-03). This turns the Phase C items in the [companion roadmap](companion-roadmap.md) into an order of work and the behaviours each step must show before it merges.

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
3. **Recall trace.** The map can light up the records the last recall used.
   - The service keeps the last 20 recalls, in memory only and never stored.
   - The backend is done (`memory-map?trace=true`).
4. **Empty and busy maps.** An empty memory shows the empty message. A busy database shows "Memory is busy updating" with a retry.

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

**Cross-session example.**
1. In sessions 1 and 2, the user asks for more casual replies three times.
2. Session 3's page shows one proposal ("more casual: from 3 messages").
3. Once it is accepted, session 4's context carries version 2.
4. After the user rolls back to version 1, session 5's context carries version 1's content again, as version 3.

**Reset scope.**
- Reset makes the host's default card, or an empty card, the current version. History is kept, so a reset can be undone.
- "Delete personality history" erases every version.
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
- "Clear feelings" deletes every affect record, reported and inferred.
- It also deletes the `agent_mood` triggers that came from those records.
- It leaves notes, messages, `persona` and `relationship` untouched.

## 3. `agent_mood`: M1 simulated mood

**State.** The companion's simulated mood is a small state: a `label` (for example calm, glad, concerned, playful or wistful), `valence` and `energy`.
- It starts at the persona card's `baseline_mood`.
- It decays back to the baseline with a half-life of 12 hours.

**Triggers.** Mood changes only through listed rules over events already stored, with no model call:
- the user reports good news (a reported positive affect, or a plan marked done) → glad;
- the user reports distress → concerned, and less playful;
- a shared joke or play, from a relationship moment → playful.

Absence, silence, or the user leaving are **never** triggers, so there is no "I missed you" sadness and no guilt.

Each change is stored with its trigger: the rule, the source record and the time.

**Context.** A single line in its own block:

> `<membrain-companion-mood>` Simulated mood of the companion persona: concerned, easing (since 14 Mar 21:05, because the user said their mother is in hospital). Let it colour tone lightly if it fits. It is not a fact about the user. If the user sincerely asks whether you have feelings, say this is a simulated mood.

**Cross-session example.**
1. Session 1, 21:00: the user says they got the job (reported positive affect). The mood becomes glad, with that trigger.
2. Session 2, the next morning at 09:00: the context shows glad, easing, with the same trigger.
3. Session 3, two days later: the mood is back at the baseline, and the context has no mood line.

The page shows the current mood, the trigger list and when it will be back at baseline. Every step is checked with a fixed clock.

**M1 acceptance (beyond the example).**
- **Ordinary moods only.** No trigger rule produces sadness from absence. A test runs a 30-day gap and expects the baseline.
- **Wording.** The mood line always says "simulated" and never states anything about the user.
- **Pin.** The user can pin the mood to the baseline. Pinned, no trigger changes it.

**Reset scope.**
- Reset puts the mood back at the baseline and deletes its trigger history.
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
