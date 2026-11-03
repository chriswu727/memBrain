# Phase C design: emotional memory, mood and persona

Status: **draft for the owner**, 2026-11-03. It turns the Phase C items in the [companion roadmap](companion-roadmap.md) into buildable steps. The order and the "may and may not" list need the owner's approval before C2 code is merged (roadmap decision 6).

C0, the brain-shaped memory map, shipped first: `GET /v1/brains/{id}/memory-map` and the Brain tab on the memory page.

## Build order

| Step | What | Depends on | Visible result |
| --- | --- | --- | --- |
| C2a | Affect on notes and messages | — | A note can carry how the user felt; the memory page shows and deletes it |
| C1a | Mood | C2a | Recall opens with the user's recent emotional trend, with evidence; the page can clear it |
| C0b | Emotion region and recall trace | C2a | The brain map gets an emotions region and lights up what the last recall used |
| C1 | Persona card | — | A versioned card the host or user sets, injected apart from user memory |
| C5 | Evaluation | all | New held-out scenarios for emotional continuity and persona stability |

C1 does not depend on C2a, so it can run in parallel.

## C2a. Affect

**Data.** A note gets an optional `affect` field. It is also used for messages, attached by the extraction model or the host.

```json
{"affect": {"label": "gutted", "valence": -2, "intensity": 2,
            "basis": "reported", "source_event_ids": ["..."], "felt_at": "2027-03-14"}}
```

- **`valence`** runs from -2 to 2, and **`intensity`** from 0 to 3. The label is the user's own word where there is one.
- **`basis`** is `reported` or `inferred`:
  - `reported` means the user said it: "I was gutted".
  - `inferred` means the model read it from the conversation. An inferred affect needs a source message.
  - The two are kept apart everywhere: in storage, in recall and on the page.

**Who sets it.**
- The note tool gains the field, and the extraction instructions say when to use it.
- The host never invents affect for a note without a source message.

**Recall.** A note with affect renders, for example, as "… (the user said they felt gutted, 14 Mar)" or "… (seemed anxious, inferred, 14 Mar)". An inferred affect is never phrased as something the user said.

**Rules** (from [memory quality and efficiency](memory-quality-and-efficiency.md)):
- Affect never raises a note's rank above a correction or a newer fact. It may break ties among equally relevant notes.
- A later reading never rewrites an earlier one. A new affect is a new record.
- Correcting, replacing or deleting a note or its source deletes its affect.
- Affect on a `sensitive` note is used only when the user raises the topic.

## C1a. Mood

Mood is computed, not stored. It is the last few affect records from the past 14 days, each weighted by its age (half-life of 3 days), with `reported` records counting twice an `inferred` one.

- **What the host sees.** A single line in the recall header, only when the evidence holds at least two records: "Recent mood (from what the user said): low — gutted about the job news (14 Mar), tired (16 Mar). Do not assume it still holds; ask."
- **What it may not do.** Mood is never shown as the assistant's own feeling. It never overrides what the user says in this turn.
- **User control.** The user sees the same line on the memory page and can clear it. Clearing deletes the affect records it used, not the notes.

## C0b. Emotion region and recall trace

- **Emotions region.** The memory map gets an `emotions` region. It holds a node for each affect record, with an edge to the note or message it belongs to.
- **Recall trace.**
  - Each recall writes the ids it used to a short in-memory ring, the last 20 recalls, which is not persisted.
  - `GET /v1/brains/{id}/memory-map?trace=last` marks those nodes, and the page lights them up.
  - This answers "why did it remember that?" without new storage.

## C1. Persona

- **The card.** A persona card is a versioned JSON document per brain: name, traits, voice, values and boundaries.
  - It is set by the host or by the user on the memory page, through `PUT /v1/brains/{id}/persona`.
  - It is injected as its own block, apart from user memory, and labelled with its version.
- **Learned style.** Style learned from the user (length, humour, formality, language) stays in `preference` notes the user can see. It is not copied into the card.
- **Old versions.** Earlier versions are kept, so an evaluation can say which persona produced which reply.

## May and may not (proposed, needs owner approval)

**May:**
- remember feelings the user expressed, with the evidence, and bring them up gently and in proportion ("how did the interview go? you were nervous about it");
- adjust tone to a recent mood.

**May not:**
- present an inferred feeling as something the user said;
- present the assistant as having real feelings;
- use guilt or absence to keep the user talking;
- raise a sensitive topic the user did not raise;
- keep any emotional record the user deleted.

**Crisis signals.**
- memBrain exposes a host hook that reports self-harm or crisis language seen in the stored text.
- The operator decides what to do with it. memBrain makes no clinical judgement and does not replace the operator's own duties.

## Evaluation

- **New held-out scenarios** for emotional continuity:
  - feelings reported and later referenced;
  - a mood that changes;
  - a sensitive topic the user did not raise again;
  - a deletion that must stick.
- **Scoring.** These scenarios use the same blinded pipeline as R4, with critical-error types for an inferred feeling stated as fact and for a deleted emotion that comes back.
- **Persona drift.** The same probe questions are asked across sessions and persona versions.
