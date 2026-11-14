# After the real-host trial: instructions where the host reads them, and a first form of "important first"

Base: pin `7a2a3253` (runtime `4b0f977`). Runtime commits `3c3b46c6` to `fc99653b` (seven); pin commit `d2e9ac1a` points all nine launchers at the last. No migration. No model of memBrain's was called; the trial used the host's own models on the owner's approval. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Two lines of work, each done by sub-sessions in their own working copies and reviewed and merged by the lead.

**Added on 2026-11-14: the second line was withdrawn.** The anchor rule described under "Important first" failed its check on the conversations not used for tuning and was removed from the runtime the next day (`8c2860c4`); see the [report](age-weight-and-importance-2026-11-13.md). The rest of this record stands.

## From the trial

The [trial](host-trial-2026-11-13.md) has the detail. What changed in the product:

- **Standing instructions from the tool server.** In Claude Code the plugin's tools are loaded on demand and its skill was never opened, so a behaviour the session notice did not name did not happen. The server now sends about 1,300 characters saying when each tool is for, and the notice gains one sentence on manner feedback and persona proposals and a clause on hard moments (348 characters more in its longest form, about one or two fewer history lines at session start).
- **Dates written for the host are the user's local dates**, in notes, history, recalled messages, consolidation batches and the relationship block, as the mood line already was. Stored times and API fields stay in UTC; days of conversation are still counted in UTC.
- **`/membrain:` command lines** are still recorded, because a persona switch cites them as its source, and are left out of the history block, consolidation batches and recall.
- **Note guidance:** the user's family, friends and pets are `person`; `constraint` is a limit on what the user can do, not their job; never note what the user did not state.
- **A proposal adds to the persona card.** Traits, values and boundaries in a proposal are added to the card's, not put in their place, so "be more patient" no longer has to repeat, or wipe, the personality type's own values.
- **Two wordings:** the consolidation result tells the host to write its answer if it has not; a hard moment is saved with what the user felt.

## Important first

A message that a current note was written from, when the note cites at most two messages, gets the highest age weight among the candidates of its request. The [report](age-weight-and-importance-2026-11-13.md) has the measurement, the two forms that failed first, and what is not shown.

## Verification

- **Full local source suite on the pin commit `d2e9ac1a`**, with the local embedding model: 8,395 passed, 4 skipped (the Docker journeys), none failed, in 42 minutes; source and migrations unchanged during the run, and no other test session on the machine.
- Each line's own runs before the merge: the trial fixes with a full suite of their own (8,386 passed, the one failure the pin test); the anchor rule with its focused files (36 passed after five of its own new tests were corrected) and a run of the built code that reproduces the measurement for every question.
- TypeScript client and OpenClaw plugin tests pass (the two that need a real runtime run through the Python suite).

## Not done, not known

- The three wordings changed after the second trial round were not tried on a host again.
- The anchor rule is checked on the development conversations only.
- No host other than Claude Code ran any of this; no interactive session.
- The memory page's familiarity line still writes the UTC day; a recall cue taken from the previous prompt can still be a command line.
- Verify, native Windows, macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.
