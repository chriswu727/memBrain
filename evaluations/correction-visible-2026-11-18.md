# Resuming a project after a correction: measured, then a correction made visible as a correction

Runtime `0def5007`; launcher pin `8894746d`. No migration, no new dependency, no model call of memBrain's own, no new tool, no new user-facing control; the server instructions are unchanged (1,388 of 1,400 characters). **It closes no release gate**, and no acceptance run has been made on this runtime.

## The scenario

Taken from an outside review as the next thing a first user should get: "said last week, corrected midway, continue today, the source one click away".

- **Day 1:** the user and the agent decide on PostgreSQL for a project.
- **Day 3**, another conversation: "only the server uses PostgreSQL; local stays SQLite."
- **Day 8**, a new session: "finish the local install."
- **Wanted:** the agent goes on with SQLite without being told again, does not bring back "PostgreSQL everywhere", and the user can open the basis: which message said it, when, and what it replaced.

## What was measured first (no fix, no model)

`tests/resume_correction_world.py` drives the scenario through the Claude Code plugin's hooks and tools on a real service, with the days as real dates, and captures everything the host receives on day 8 before it answers. Five worlds: a host that saves and replaces notes as the session notice asks ("diligent") or calls no memBrain tool at all ("lazy"); a short history or a busy week (30 unrelated messages in between); recall by keywords only (a fresh installation before the embedding model is in place) or with the local model. Three wordings of the day-8 message: "finish the local install", "set up my dev machine", and one in Chinese.

| | What the host received on day 8 |
| --- | --- |
| Diligent host | The corrected note, in every session, whatever the wording. Nothing said it had replaced an earlier decision. After a busy week, recall put the day-1 message next to it, unmarked. |
| Lazy host, short history | Both messages, dated, the correction last. |
| Lazy host, busy week | Neither message in the session context; the correction arrived only if recall found it. With keywords only it was missed for "set up my dev machine" and for the Chinese wording. |

On the memory page: the corrected note listed the overruled day-1 message as one of its "2 original messages"; the replaced note had simply disappeared, with nothing saying what had been corrected; search and the map showed the old decision unmarked. `memory_recall` never returned the current note, because recall leaves out records the assistant wrote and notes are such records. A note carries no count of how often something was said and does not tell a stated fact from an inferred one (a feeling attached to a note does say "inferred").

## What a host model does with it (diagnostic probes, not a gate)

The captured inputs were replayed to the provider's host model (`deepseek-v4-pro`, the product's real tool schemas, captured recall answers; replies read by the lead, not scored blind). Replies are in [`evidence/resume-correction-probe-2026-11-18/`](evidence/resume-correction-probe-2026-11-18/). Conservative cost bound of the three rounds: 9.75 CNY.

| Question | Result |
| --- | --- |
| Day 1: does the host save the decision as a note? | 6 of 6 (English and Chinese) |
| Day 3: does it replace that note when corrected? | 9 of 9, citing the old note's id (three wordings, one Chinese) |
| Day 8, diligent worlds, before this change: goes on with SQLite? | 12 of 12 |
| Day 8, lazy worlds, before this change | 14 of 18; three plainly wrong (two installed PostgreSQL on the user's machine, one started PostgreSQL after the correction never arrived) and one hedged, all on "set up my dev machine" |
| Day 8, diligent worlds, after this change | 17 of 18 go on with SQLite, one asks about the machine first and names no database; none revives PostgreSQL locally |
| Does a reply cite the date unprompted? | 0 of 30 before; 1 of 18 after |

Reading: the path that works is the one the host model actually takes (it notes the decision and replaces the note), so nothing was built for the lazy host. The marks added below did not tempt the model to revive the old decision.

**Limits of the probes:** one model through an emulated host, not Claude Code; two or three trials per cell; when the model searched on its own, it was answered from recall results captured for three fixed queries, which favours it in the keyword-only world; days 1 and 3 were built from the captured day-8 context by hand.

## What changed

- **Lineage, derived on read.** A note saved with `replaces` is linked to each note it replaced by one dependency row holding ids only. The replaced note's sentence and date are read from its own record, never copied, so erasing it, or a message it rests on, removes the lineage text with it.
  - The host's note line gains a clause: `(replaces your note of 2026-11-02)`. It never quotes the old sentence.
  - The memory page shows, under the note: "Replaced an earlier note on 2026-11-04." and "Earlier (2026-11-02): Tidepool decision: use PostgreSQL as the project's database." A chain lists every earlier note, newest first.
- **Sources by role.** The page lists "Said on 2026-11-04:" (the correction) apart from "The earlier note was based on:" (the decision), each with its conversation. The roles are derived on read; nothing is stored.
- **An overruled message is marked where the host sees it**: `[2026-11-02 · superseded by your note of 2026-11-04]` in the history block and in recall results, and on the page's search, conversations and map. Only when a replaced note that still exists rests on that message and the current note has a message of its own: no text matching, no guessing.
- **`memory_recall` leads with up to three matching current notes**, marked as notes, before the messages.
- **Deleting or hiding a note now reaches the notes it replaced.** Before, deleting the current note left the replaced sentence stored and hidden, with no way to delete it short of its source message or erasing everything. The page asks "Delete this note and the earlier note it replaced? Their content is erased."
- Map labels cut at 80 characters end in "…".

Cost to the host: 35 characters per replacement note, 40 per marked line, 350 to 500 characters in a `memory_recall` answer that has matching notes; after a busy week the history block held 17 messages instead of 18.

## Trust checks

Each on its own installation, through the hooks, the note, forget and recall tools, the page's delete, export, and the user's downloaded copy uploaded again; on a chain of two notes and of three. After each act every reader is checked (notes block, history, per-prompt context, recall, `memory_recall`, the page's notes, messages and search, the map, a new export): no sentence or date of an erased or hidden record, no mark pointing at a note that is not current, lineage and both source lists matching a model of the dependencies.

Acts: delete the day-1 message; delete the day-3 message; delete the replaced note; delete the middle note of a chain; delete the current note; hide the current note; hide the day-1 message; restore a copy taken before the correction; delete the current note and restore a copy taken after; erase everything. All pass on both shapes. A property test runs 40 seeded sequences of 14 random acts with the same invariants after every step.

## Limits

- **Not tried on a real host.**
- **Nothing was built for a host that saves no notes.** After a busy week on a fresh installation, the correction reaches such a host only if recall finds it; the two keyword misses and the three unmarked lazy worlds stay as strict expected failures in the scenario tests.
- **Still missing from "the source one click away":** the host has no link it can give the user to the basis of a reply; a source message on the page does not open its conversation; nothing leads from a reply to what it rested on.
- **Still missing from "knows how much it knows":** no count of how often something was said, and a note does not say whether its fact was stated or inferred.
- Deleting the day-1 message still erases the corrected note too: a correction keeps its predecessor's source messages as deletion dependencies, because it may restate what it corrects.
- A message that both a replaced note and the current note cite counts as the earlier note's.
- Notes replaced before this runtime have no link: no lineage is shown, and deleting the current note leaves them stored.
- An export leaves out hidden records, so a restore into a new brain carries no lineage.
- Hermes' search does not lead with notes.

## Verification

All local, on Linux under WSL2; nothing was run in CI or on another platform.

| Check | Result | On |
| --- | --- | --- |
| Full source suite | 4,811 passed, none failed, 13 strict expected failures (the gaps listed under Limits, pinned by the scenario tests), 4 skipped (three desktop end-to-end tests that need Docker; one trust case that applies only to a chain of three notes), seven Python fork warnings; 55 minutes | `8894746d` (runtime `0def5007`, pinned) |
| Scenario tests before the change | 72 passed, 24 strict expected failures | `a0e34963` |
| Scenario tests after the change | 11 of those expected failures now pass and are asserted with exact text; 13 remain | `0def5007` |
| LoCoMo evidence recall | not rerun: the per-prompt recall block lists no notes and the benchmark has none, so its input is unchanged | — |

The suite is 13 minutes longer than before: each trust test starts its own installation.
