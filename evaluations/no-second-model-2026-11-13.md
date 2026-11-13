# No model of memBrain's own left to configure: the extraction model and the remote embedding provider are removed

Base: pin `c6c313ff` (runtime `bb55fb0`). Runtime commits `be09a3be`, `307c259f` and `4b0f9779`; pin commit `7a2a3253` points all nine launchers at the last. No migration. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## The decision this carries out

The owner's rule: a user who fits memBrain to an agent can use it at once; every function is exercised by that agent's own AI; memBrain ships no second AI and never asks the user to configure one; code that is no longer used is cleaned up. Two things in the package still let a user configure a model for memBrain itself. Both are removed here, as slices 3 and 4 of the [removal plan](audits-2026-11-12/unused-code-removal-plan.md). A sub-session did the work in its own working copy; the lead reviewed and merged it.

The same batch makes the age weight gentler; that change has its own [report](age-weight-and-importance-2026-11-13.md).

## What was removed

**The separate note-extraction model.** For bots whose model cannot call the note tool, the proxy and the AstrBot plugin could be given a model of the user's choice that read each exchange and wrote notes. `extraction.py`, its options and status lines, its three AstrBot settings and its line on the memory page are gone.

- **What users lose:** people who use memBrain through the proxy, or through AstrBot with a model that cannot call tools, no longer get new notes (plans, people, preferences, feelings on notes) written for them. Recording, recall before each reply, pausing, forgetting, export, boundaries and every note saved earlier keep working. AstrBot with a model that calls tools is unaffected.
- **Old settings** are ignored without an error: the proxy starts with the old variables set, also without the key it used to require; a saved AstrBot configuration that still holds the three settings loads; a caller that still passes an extractor is accepted.
- Notes the model wrote earlier are ordinary notes linked to their messages; forgetting those messages still removes them.

**The remote embedding provider.** A deployment could point memBrain at a paid embedding service. Only the local model remains.

- **What users lose:** a deployment that set only the remote service's settings now recalls by keywords until it is pointed at the local model. It gets one warning in the log that names the ignored settings, never their values, and nothing on screen. Desktop and plugin installations never had these settings.
- **Old vectors:** recall reads only the vectors of the configured model, so vectors a remote service wrote are ignored; the background fill embeds every current memory with the local model; editing or forgetting a memory deletes its vectors of every model. No memory is left without vectors once the local model is present. A test stores such vectors the old way and checks all three.
- **Ranking with the local model did not change:** the model-free evidence check on the three development conversations gives the same result before and after for every one of 385 questions, including each context's size.

In source: 794 lines removed and 67 added over 21 files; in tests 1,163 removed and 292 added. Four evaluation scripts that used the extraction model are kept as evidence, each with a first line saying which arm needs a runtime from `77c1f841` or earlier. No table or migration changed.

## What this means for R4

In the [fifth acceptance attempt](maturity-fifth-attempt-2026-11-07.md) the plugin path passed with 20 points and the note-extraction path failed with 16, on one privacy error that memory caused. The path that failed no longer exists. That does not make R4 pass: the attempt is recorded as failed, its plugin-path score is evidence for a much older runtime, and no attempt has been run since. A new attempt would have the plugin path and the full-history reference only; it is a paid evaluation and needs the owner's approval.

## Verification

- **Full local source suite on the pin commit `7a2a3253`**, with the local embedding model: 8,377 passed, 4 skipped (the Docker journeys), none failed, in 41 minutes; source and migrations unchanged during the run, and no other test session on the machine. There are 138 fewer tests than in the last run: the tests of the two removed parts are retired.
- The sub-session's own full run on the two removals alone: 8,374 passed and 2 failed, both expected (the pin test, and the test matrix that still named retired tests; the matrix is updated here).
- Nothing failed from the gentler age weight, whose own tests are in the suite.
- TypeScript client: 58 tests pass and the type check is clean. OpenClaw plugin: 10 pass, 2 skipped there (they need a real runtime and passed through the Python suite).
- New tests cover: a proxy environment and an AstrBot configuration that still name the extraction model, a caller that still passes an extractor, and a leftover status file, all ignored without an error; old remote embedding settings ignored with one warning, complete, partial or malformed; vectors and a query job stored the old way, then filled with the local model, recalled around and erased with their message.

## Not done, not known

- No real host, proxy or AstrBot runtime ran this.
- Failed jobs that an old remote embedding run left behind still count as failed in the status output.
- `run_locomo.py`'s extraction arm was already calling the model with an outdated signature before this removal; it is marked, not repaired.
- The cognition pipeline, its budgets, the belief writers and the bundled chat mode are still in the package (slices 5 to 8).
- Verify, native Windows, macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.
