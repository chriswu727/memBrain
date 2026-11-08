# Host turn isolation and bounded session-state work

This batch replaces the single pending slot with a ledger keyed by owner, producer and source event. It also binds explicit proxy session headers to the effective user, group and role-play identity. This is an integration candidate, not a release approval. R4 remains failed and C5 invalid/unscored; no paid or subscription-backed evaluation was run.

## Behavior

Overlapping turns retain their own input until the matching reply arrives, including reverse completion order. Context refresh no longer stores or removes live inputs. The reply's parent is copied from its actual input source key, so colon-containing host IDs remain intact. Mismatched users, producers, prompts, ambiguous callbacks and repeated completions cannot consume a different pending input. Hooks identify the owner/producer/turn when recovering an explicitly resumed input.

Pause scrubs all affected live inputs, including multiple turns sharing a session, while retaining another user's records. Erasure removes the erased user's staged content and keeps exclusion metadata so late callbacks do not restore it. Resume does not guess between multiple active turns. Legacy pending and paused state migrates on use; an upgraded active input is not immediately abandoned. Session expiration and mutation share the same lock.

State is bounded to 64 active turns and 256 completed markers. Overflow rejects new staging without evicting live inputs. Completed markers contain identity and fingerprints, not message text. Unknown callbacks in staged sessions remain rejected after marker compaction. A session that excluded or erased content requires staging even for a host that normally permits whole-turn callbacks. Session files retain the existing 14-day inactivity expiry; this is not an indefinite delivery ledger.

Hermes can still report a complete turn without prefetch through explicit `allow_unstaged=True`. It cannot use this fallback to consume another active input or bypass an exclusion in that session. Hosts without stable IDs cannot reliably distinguish identical overlapping prompts; those are excluded. Shared hosts must supply the same owner on both callbacks.

Each session file begins with an atomically written earliest-active timestamp (or null for no live turns). Abandonment housekeeping reads this small prefix before decoding a ledger. This avoids decoding all 256 finished markers in every historical session on each context refresh, while still finding an old unanswered input in a session with newer activity. Inputs older than 30 minutes are recorded on their own; late replies are not attached to another turn.

## Verification

Build identity: `d8c7126e4aff81ecf747063d81fcaa825f1653e1b64bafc599757ebdf7a970ca`. The first fixed-source group passes **195 tests**, zero skips, in 38.16 seconds. Verification is in progress. Final source, installed-wheel, launcher and CI receipts will be recorded here before integration merge. The reproducible offline measurement is `scripts/benchmark_host_turns.py`; delivery and service lookup are mocked, so its timings are local ledger overhead rather than model response or database recall latency.

The local benchmark records 1,000 prompt/finish pairs with a full 256-marker ledger: P50 **3.767 ms**, P95 **4.341 ms**, maximum **21.301 ms**. Eight-worker reverse-order completion of 64 staged inputs has P95 **8.852 ms**. Finished session state occupies **83,223 bytes** in this fixture. Five paired housekeeping samples over 500 completed sessions compare full decoding (median **149.155 ms**) with the atomic due-header path (median **40.678 ms**), approximately **73% less time**. This is a local synthetic comparison of the new state layout, not a production recall benchmark or a claim that R5 was rerun.

## Failures retained during development

- All **10 initial regression cases failed on the baseline**, reproducing cross-turn receipts, private callback revival, ambiguous selection, lost staged input, malformed colon-containing reply keys and duplicate receipts.
- The initial focused revision had **2 failed / 167 passed**: an already-handled pause was reapplied after resume, and a boundary test still mocked the removed pending-slot helper. The pause logic was corrected and the obsolete mock removed; its privacy assertions remain intact.
- An expanded run was stopped with **7 failed / 205 passed**. Six embedded-service readiness timeouts occurred while runtime files were changing, and one test caught unnecessary rewriting of another user's session. The runtime identity is computed at process import, so source edits can leave the test process and a newly started service with different identities. This run is not qualifying evidence. The unchanged-user write was removed.
- The first frozen-source group had **1 failed / 301 passed**: an extra resume response field changed the existing Hermes no-active-turn response. Compatibility was restored while keeping explicit refusal for ambiguous multi-turn resume.
- A subsequent run exhausted local disk and ended with `OSError: [Errno 28] No space left on device`. Its output is retained and it is not counted as a pass. Stopped, task-owned temporary PostgreSQL clusters were removed; subsequent groups use separate temporary roots and serial database execution.

## Boundaries

The repair covers the shared host lifecycle and adapters. It does not add a server-owned recording policy to raw HTTP/SDK observation, or transactional cancellation of a database write already in flight. It does not make local delivery crash-atomic across ledger updates and the database/spool; that pre-existing delivery boundary remains separate work. No new memory-quality, personality, emotion, 3D or R5 end-to-end performance result is claimed. Explicit proxy session names change on upgrade, while the user's stored brain remains the same.

Raw logs and measurements are retained under [evidence/backend-turn-isolation-2026-11-07](evidence/backend-turn-isolation-2026-11-07).
