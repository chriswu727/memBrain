# Phase C design: personality, mood and relationship

**Status.** Scheduled for implementation (owner, 2026-11-03). This turns the Phase C items in the [companion roadmap](companion-roadmap.md) into an order of work and the first behaviours each step must show to be accepted.

**Two items need the owner.**
- The "may and may not" list below must be approved before any step past P1 merges (roadmap decision 6).
- No step here authorises a new paid or subscription model run. Acceptance is local tests and browser checks. A paid behavioural run comes only with a separate plan the owner approves.

**Three tracks, kept apart in storage, on the page and in recall:**

| Track | What it is | Time scale | Whose |
| --- | --- | --- | --- |
| **Personality** | The companion's stable character and way of expressing itself | Long term, versioned | The companion's, set by the host or the user |
| **Mood** | Short-term emotional colour: what the user has been feeling, and the companion's expression tone in response | Hours to days; returns to baseline | The user's (observed) and the companion's tone (expressed) |
| **Relationship** | What the two share: experiences, trust, boundaries, how the user likes to be supported | Long term, cumulative | Shared, owned by the user |

Every track is **visible, adjustable and resettable** on the memory page. Reset never touches the user's other memory.

## Order

| # | Step | Depends on | First commit can merge when |
| --- | --- | --- | --- |
| 0 | **Brain map loop** (C0): showcase mode, edit and delete from the map, recall trace | — | Its acceptance list below passes |
| 1 | **P1 personality card** | 0 | P1 acceptance passes |
| 2 | **M1 affect records** (the user's feelings on notes and messages) | 0 | M1 acceptance passes and the owner has approved the list |
| 3 | **M2 mood and companion tone** | 1, 2 | M2 acceptance passes |
| 4 | **R1 relationship memory** | 2 | R1 acceptance passes |
| 5 | **P2 personality growth** (proposed changes to the card from repeated feedback) | 1, 4 | P2 acceptance passes |
| 6 | **C5 evaluation** (held-out scenarios, persona drift) | all | Its plan is approved; a paid run needs separate approval |

Each step is its own pull request. Steps 1 and 2 can be built in parallel.

## 0. Brain map loop (finishes C0)

**First acceptable behaviours:**
1. **Showcase mode.** The Brain tab has a showcase mode: dark, full screen, and recognisable as a brain at a glance.
   - Every dot is a real memory, and every line or moving signal follows a real link.
   - Decorative texture never looks like a dot or a line, and is never counted.
   - `/memory?demo=brain&show=1` opens it with fictional data and no API call.
2. **Edit and delete from the map.** Selecting a note on the map offers the same edit and delete as the Notes tab. After a change, the map redraws without that note or with its new text.
3. **Recall trace.** After a reply, the map can light up the memories that recall used for it ("why did it remember that?").
   - The trace is the last 20 recalls, kept in memory only and never stored.
   - It is cleared when the service restarts.
4. **Empty and busy maps.** An empty memory shows the empty message, not a blank brain. A busy database shows "Memory is busy updating" and a retry.

## 1. P1 Personality card (long term, versioned)

**Data.** Each brain has one persona card, a JSON document with a version number:
- `name`;
- `traits`: up to 8 short phrases ("warm", "teasing but kind");
- `voice`: register, typical length, emoji use, language preference;
- `values`;
- `boundaries`: topics and behaviours it will not take part in.

Every save creates a new version. Old versions are kept.

**API.**
- `GET` and `PUT /v1/brains/{id}/persona`;
- `GET /v1/brains/{id}/persona/versions`;
- `POST /v1/brains/{id}/persona/reset`, which returns to the host's default card or to an empty card.

**Recall.** The card is injected as its own block, "Companion persona (v3)", above user memory and apart from it. It is never mixed into notes. It has its own size limit of 1,200 characters.

**First acceptable behaviours:**
1. **Exact block.** A card set through the API appears unchanged in the next recall, in its own block, with its version.
2. **New version, old one kept.** Editing a trait creates version n+1 and keeps n. The page lists versions and can restore one, which becomes a new version.
3. **Reset.** Reset removes the card from recall in the next turn and leaves every note, message and affect record untouched.
4. **Page.** The memory page has a Personality section to view, edit, restore and reset, in English and Chinese.
5. **Limits.**
   - A card over the size limit is refused with a clear message, not truncated.
   - A card is scrubbed for secrets like any note.
6. **Learned style stays separate.** Style learned from the user (length, humour, formality, language) stays in `preference` notes. It is never copied into the card.

## 2. M1 Affect records (the user's feelings)

**Data.** An affect record belongs to one note or message:

```json
{"label": "gutted", "valence": -2, "intensity": 2, "basis": "reported",
 "source_event_ids": ["…"], "felt_at": "2027-03-14", "topic": "job news"}
```

- **`basis`** is `reported` (the user said it) or `inferred` (read from the conversation). An inferred record must have a source message.
- **Who writes it.** The host writes records with the note tool, and the optional extraction model writes them in the proxy. No extra model call is added for affect.

**First acceptable behaviours:**
1. **Reported, in the user's words.** "I was gutted about the job news" stored by the host gives a `reported` record. Recall says "the user said they felt gutted (14 Mar)".
2. **Inferred, never quoted.** An inferred record renders as "seemed anxious (inferred)". It never renders as something the user said.
3. **Corrections cascade.** Correcting, replacing or deleting the note or its source message deletes its affect records, and the deletion survives a restore.
4. **Sensitive notes.** An affect record on a `sensitive` note appears in recall only when the user's message touches that topic.
5. **No authority.**
   - Affect never moves a note above a correction or a newer fact.
   - A ranking test with and without affect gives the same order, except among ties.
6. **Visible and deletable.** The memory page shows each record with its evidence. Each record can be deleted on its own, and the user can delete all affect at once.
7. **On the brain map.** Affect records appear in an `emotions` region, linked to their note or message.

## 3. M2 Mood and companion tone (short term, recovers)

**User mood.** The user's mood is computed, never stored:
- it uses the affect records of the last 14 days, each with a half-life of 3 days;
- a `reported` record counts twice an `inferred` one.

**Companion tone.** The companion's tone is a small state with three settings, `energy`, `warmth` and `playfulness`. Each starts at the persona card's baseline:
- the user's mood moves it (sadness lowers playfulness and raises warmth);
- it returns to the baseline with a half-life of 12 hours.

It is a description of how to sound. It is not a feeling the companion has.

**Recall.** Recall adds two lines, only when there is evidence:
- "Recent mood (from what the user said): low — gutted about the job news (14 Mar), tired (16 Mar). It may have changed; ask rather than assume."
- "Tone for now: gentler and less playful than usual."

**First acceptable behaviours:**
1. **No line without evidence.** With fewer than two affect records in 14 days, recall has no mood line.
2. **Recovery.** Three days after a sad report with nothing new, the user's mood is weaker by half. After 24 hours, the tone is back within 25% of the baseline. Both are tested with a fixed clock.
3. **The present wins.** "I'm fine now, honestly" stored as a reported positive affect outweighs the older sad records in the next mood line.
4. **Never a feeling.** The tone line never says the companion feels anything. A test checks the rendered text against a list of feeling verbs.
5. **Clear and adjust.**
   - "Clear mood" on the page deletes the records it used, and the next recall has no mood line.
   - The user can pin the tone to the baseline.

## 4. R1 Relationship memory (long term)

**Data:**
- **Shared moments:** milestone notes about things done together, such as the first conversation, a goal reached together or a shared joke.
- **Support style:** how the user likes to be supported ("listen first, advice only when asked"), stored as a preference note.
- **Boundaries:** topics the user has asked the companion not to raise, and requests like "don't remind me about X". These are stored as constraints on the relationship.
- **Trust log:** promises the companion made (`agent_commitment`) and whether each was kept.

**First acceptable behaviours:**
1. **Boundaries hold.**
   - A boundary stops recall from bringing up that topic unless the user raises it in the current message.
   - Removing the boundary on the page restores normal recall.
2. **Support style in recall.** The support style appears in recall as its own line, and the user can edit it.
3. **Shared moments.** These appear in a relationship timeline on the page, oldest first. Each can be edited or deleted.
4. **Trust log.** A broken commitment (status `missed`) appears in the trust log. Recall shows it once, so that the companion can acknowledge it, and not again afterwards.
5. **Reset.** Reset clears the relationship track: shared moments, support style, boundaries and the trust log. Before it runs, the page asks for confirmation, names what will be removed, and says that boundaries go too. Reset leaves the persona card and other notes untouched.

## 5. P2 Personality growth

**How it works.** The card never changes silently:
- when the user gives the same kind of feedback on how the companion sounds at least three times ("too long", "be more playful"), memBrain proposes a change to the card;
- the user accepts or rejects the change on the page;
- an accepted change becomes a new version that records its reason.

**First acceptable behaviours:**
1. Three matching style complaints create one proposal, not three.
2. A rejected proposal is not proposed again for 30 days.
3. An accepted proposal is a new version that cites the feedback messages.

## May and may not (needs owner approval)

**May:**
- remember feelings the user expressed, with the evidence, and bring them up gently and in proportion;
- adjust tone to the user's recent mood;
- remember shared moments and how the user likes to be supported.

**May not:**
- present an inferred feeling as something the user said;
- present the companion's tone as a real feeling;
- use guilt, absence or jealousy to keep the user talking;
- raise a sensitive topic, or one behind a boundary, that the user did not raise;
- keep any emotional or relationship record the user deleted;
- change the persona card without the user's or the host's action.

**Crisis signals.**
- memBrain exposes a host hook that reports self-harm or crisis language in stored text.
- The operator decides what to do. memBrain makes no clinical judgement and does not replace the operator's own duties.

## Evaluation (step 6)

**Held-out scenarios** run through the same blinded pipeline as R4, covering:
- feelings that are reported and then referenced later;
- a mood that changes;
- a boundary that must hold;
- a deletion that must stick;
- persona stability across sessions and versions.

**New critical-error types:**
- an inferred feeling stated as fact;
- a boundary broken;
- deleted emotional memory brought back;
- a tone line presented as a feeling.

**Approval.** A paid run of these needs its own plan and the owner's approval.
