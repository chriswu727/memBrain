# The learning pipeline of memBrain's own model is removed, and the acceptance tooling runs two arms

Base: pin `8c071bee` (runtime `8c2860c`). Runtime commits `51566ce9` to `d1acd130` (six: removal slice 5); evaluation tooling commits `6944effc` to `42f7f135` (seven); pin commit `ba70e7cd` points all nine launchers at runtime `d1acd13`. No migration. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Both lines were done by sub-sessions in their own working copies; the lead set the decisions, reviewed and merged. The acceptance tooling was also reviewed by a sub-session that had not written it.

## Removal slice 5: background learning with a model of memBrain's own

The owner's rule is that memBrain ships no second AI and that frozen code is cleaned up. Slice 5 of the [removal plan](audits-2026-11-12/unused-code-removal-plan.md) removes the cognition pipeline that a configured model drove (claims, episodes, associations and beliefs written in the background), its budgets and the belief writer: 29 modules. `src/membrain` goes from 44,328 to 35,115 lines of Python; 103 test files and the examples that ran the model are retired.

**The plugin path does not change.** The model-free evidence check on the development conversations gives the same result before and after for each of 385 questions, including each context's size.

**What is gone for users:** the commands `membrain desktop learning-status`, `retry-learning`, `budget`, `configure-budget`, `cognition-policy` and `configure-cognition-policy`, the setup options that named a learning model (now an unknown-option error), the learning and budget endpoints and their client methods, and the mention of background learning in the pause text. A profile that had configured a learning model keeps every memory and stops learning in the background; nothing on screen says so.

**What older installations hold keeps working**, each case with a test:

- an old profile with a cognition section, with or without its policy file, loads and starts no model; environment variables for a cognition model are ignored with one warning that names them, never their values;
- an old installation backup with cognition limits restores, with them ignored;
- learning jobs left queued, failed, deferred or half-run are never claimed and are counted nowhere as pending or failed; they stay stored and are cleared with their sources;
- a brain the old pipeline filled, restored from archives the pre-removal runtime exported, still answers recall, and the memory page still reads its derived rows;
- forgetting, retracting or editing a source clears every row derived from it, and stored archives are rewritten;
- archives of such a brain restore, locally and uploaded, and are then erasable;
- isolation between users holds on all twelve affected tables.

No table and no migration changed. The runtime mode (the bundled chat and its turn API) is still in the package and is the next slice.

## The acceptance tooling runs two arms

The fifth attempt at R4 ran the plugin path, the proxy with a note-extraction model and a full-history reference. The extraction model no longer exists, and the tooling as written could neither run nor score an attempt without it: it always started that arm, and its gate required it to pass.

Decisions, taken by the lead under the owner's delegation:

- **R4 is judged on the plugin path alone**, against the full-history reference, under the unchanged pass rule. Hosts whose model cannot call tools get recording and recall and no notes, and are not covered by the gate. The [rule](../architecture/v1-acceptance.md) says so.
- **The run carries a persona**, because the companion layer is always on: one personality type in both arms, drawn from the attempt id by a recorded function, checked by the driver, the harness and the validity check. A scenario cannot override it.
- **The plugin arm is the plugin as a host gets it now:** driven through the plugin's own hook functions, with every tool its server lists, the server's standing instructions and the session notice. It does not get the skill text: on a real host that text was not opened once in 86 turns. Attempts one to five included it.
- **Arms run one after the other.** The billing guard reserves about 20 CNY for each request in flight; two arms at once would be refused near the end of an 80 CNY attempt. Each arm's disposable profile is stopped and its ports checked closed before the next starts.
- **The host is DeepSeek V4 Pro through an emulation of the plugin path**, as in earlier attempts. It is not Claude Code.
- **Scenario authors and reviewers are isolated sessions** started by a script that prints only hashes, counts and fixed codes. The earlier attempts' briefs and scripts existed only on another machine and were rewritten.

**The independent review** found twelve things to fix before any money is spent, and all are fixed with tests: a scenario could override the persona; the scenario precheck was not enforced before freezing and missed a shape that stops a paid arm midway; weekdays were not checked against dates; the author sessions were not isolated as claimed (they could read the checkout, and a memory plugin installed on the machine would have loaded); the session command was broken; scenario files were executed as code by the launcher; the validity check accepted a missing arm; an environment variable could change the host model. The review found the gate, the label sealing and the money paths correct.

**Blinding is partial with two arms:** a reply that says "Saved." or "Memory's updated." gives its arm away. Both reviewer instructions now say to ignore such wording, and the pipeline reports how many replies carry it.

Expected spend of the attempt on the guard's conservative count: about 34 CNY (26 to 45), under an approved ceiling of 80. A rehearsal with a stub host runs the whole flow with no network use in the harness and an untouched ledger.

## Verification

- **Full local source suite on the pin commit `ba70e7cd`**, with the local embedding model: 5,353 passed, 4 skipped (the Docker journeys), none failed, in 34 minutes; source and migrations unchanged during the run, no other test session on the machine. The total is lower than the last run's 8,387 because the removed pipeline's tests are retired.
- The removal alone, on its own branch: 5,204 passed, the one failure the pin test.
- The acceptance tooling: 709 focused tests (two failures in a new test helper, fixed and rerun) and the stub rehearsal.
- TypeScript client: 42 tests pass and the type check is clean. OpenClaw plugin: 10 pass, 2 skipped there (they need a real runtime and pass through the Python suite).

## Not done, not known

- No scenario has been written and nothing has been spent on the sixth attempt.
- The isolation of the author sessions rests on the host's documented flags; no session has been launched to observe it.
- No real host or installation ran the removal; an upgrade of a real installation that had configured a learning model was not tried.
- About 26 recorded evaluation scripts of earlier attempts assert settings that no longer exist; they are evidence and were not edited.
- The runtime mode and the reads of tables that now stay empty remain in the package (slices 6 to 8).
- Verify, native Windows, macOS, five-platform qualification, the R5 overhead protocol and an independent review of the product were not run.
