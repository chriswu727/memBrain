# The bundled runtime mode is removed, and erasure leaves no digest in the database

Base: pin `ba70e7cd` (runtime `d1acd13`). Runtime commits `298078e1` to `1665381a` (seventeen: removal slices 6, 7 and 8 and the digest erasure), pin commit `8259e41e`. No migration. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

This record was written on 2026-11-15, after the fact. The lead's session ran out of its weekly allowance while this batch's full suite was running, and the batch went unrecorded. Codex then continued from `8259e41e` at the owner's request; its [closeout](backend-host-erasure-2026-11-14.md) keeps these commits as they were and reports the interrupted run. The numbers below are the sub-session's own runs on its branch and that closeout's; the lead did not see a full run of `8259e41e` finish.

A sub-session did the work in its own working copy; the lead set the decisions and merged.

## Removal slices 6 to 8

**Slice 6, the runtime mode.** memBrain is a brain fitted to agent hosts, not a chat product of its own. Removed: `membrain desktop chat`, `configure-chat` and `turn-status`; the turn lifecycle HTTP API (`runtime/status`, `runtime/scope`, `runtime/turns`, the temporary-turn routes, `orient`); the session runtime and its Python and TypeScript clients (`open_agent`, `RuntimeClient`, `activeScope()`); twenty modules. `src/membrain` goes from 35,059 to 29,460 lines; since the removals began, from 44,328.

- **The plugin path does not change:** the model-free evidence check gives the same result for each of 385 questions, and a plugin-path start loads the same 56 modules as before.
- **The four public memory actions stay** (`prepare`, `commit`, `feedback`, `checkpoint`, and the MCP tools `memory_prepare` and `memory_checkpoint`) and work without a turn. Whether to retire them is not decided.
- **What older installations hold keeps working**, from fixtures the pre-removal runtime itself wrote (22 turns in every stage, reviews, deliveries, feedback, working states) and 29 data tests that pass before and after: the brain loads and serves recall and the memory page; pausing stops unfinished turns; forgetting erases their messages; the exported archive restores and is then erasable. An old profile with `chat.json` and `sessions/` loads; backups carry both unread and restore them unchanged. Removed commands are refused by the argument parser; removed HTTP paths answer 404.

**Slice 7, narrowed.** Recall no longer reads data that nothing writes any more: stored associations no longer expand recall, recall reads no working state, and conditions are no longer evaluated against supplied context observations. A fresh brain's recall is unchanged (385 of 385). For a brain an older runtime filled, the old rows are ignored by recall, still shown on the memory page and still erased with their sources; tests pin each. `prepare` still shows the working state that `commit` and `checkpoint` write.

**Slice 8.** Six contract definitions that nothing reads and no archive uses are removed from the schema and the TypeScript types; archives from before the removals still validate and restore. HTTP mappings for conflicts nothing raises are gone. The request read timeout, 615 seconds for jobs that no longer exist, is 120; that figure is reasoned from the 30-second transaction cap, not measured.

## Erasure leaves no digest of an erased message in the database

**Found while removing the runtime mode.** An unverified private note said erasure might leave message text in the turn table's JSON columns. Tested: it does not; no text of an erased message was left in any column of any table. What was left were SHA-256 digests tied to the erased content, on old turn rows and, for every user, on the message's own row (`content_hash`, `input_hash`). A digest of a short message can be confirmed by guessing it. Reading the local database is needed to try, the same access that reads every memory the user did not erase.

**Changed:** after `erase_content`, nothing stored in the memory database lets someone confirm a guess of the erased text.

- The message's own digests are wiped; where a column cannot be empty it holds 64 zeros, which no real digest takes.
- A copy of an erased message sent again is refused as stale, without being compared with what was erased; a host drops its queued copy quietly and the user sees it as excluded, not as a failure. The refusal works by the source's identity, not by a digest of its content.
- An older archive that still holds the message restores without it, counted as excluded, with no error.
- Stored observation requests of the brain are deleted; other request fingerprints, feedback contributions' content digests and every digest on old turn rows that named erased content are wiped. Source keys that were themselves derived from content are renamed.
- Left on purpose, each with its reason in the test: embedding job ids (a digest of ids, not content), lease-token digests (of a random token), reviewer configuration fingerprints, and the erasure receipt's digest of ids.
- Hiding a message is not erasing it and wipes nothing; a test keeps the difference.

The test collects every digest-shaped value that appeared while a message, its reply, a cue, a note, a recall and an export were recorded, erases, and searches every column of every table for each of them.

**What this batch did not solve**, and what happened next: the plugin's own local files could still hold a refused copy's text and prompt digests after a single-message erasure, and a replay after an unrelated memory change failed and left its text in the refused file. Both were fixed afterwards by Codex: [host erasure](backend-host-erasure-2026-11-14.md). Backups and exports made before an erasure necessarily contain the content; the [reference](../docs/reference.md) says so.

## Verification

- The sub-session's full local suite on its final tree, which is this batch's source before the pin: 4,049 passed, 3 skipped (the Docker journeys), 1 failed, the pin test that every unpinned change fails.
- The lead's full run on the pin commit `8259e41e` was interrupted by the allowance limit. Codex's closeout reports the existing local evidence for these commits as 4,050 passed with three Docker skips, and later full runs on GitHub passed on the sources that contain them (4,066, then 4,105 tests).
- Model-free evidence check on the development conversations, before and after slice 6 and again after slice 7: identical for 385 of 385 questions.
- TypeScript client: 39 tests pass and the type check is clean. OpenClaw plugin: 10 pass, 2 skipped there.

## Not done, not known

- No real host or installation ran this; an upgrade of a real installation that used the chat mode was not tried.
- The 120-second timeout is not measured.
- The public actions `prepare`, `commit`, `feedback` and `checkpoint` remain; nothing in the plugin path needs them.
- Verify and the native platforms were not run for this pin; they were run for later sources, as the later records say.
