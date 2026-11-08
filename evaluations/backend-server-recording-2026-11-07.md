# Server recording-control qualification

Runtime `f9e35a3515d3e00db0a6f2ac8bd1856a2bc93347`, build `26673a0d5e4c4f3ed3d67dad86c58ff6e70e6ba99fa03a7365cfcecbd6e9b1cb`. All nine launchers pin this runtime. This is an integrated pre-release change; no main merge, release, paid or subscription-backed evaluation is authorized by this report. R4 remains failed and C5 invalid/unscored.

## Delivered behavior

An authenticated per-brain recording policy lives in PostgreSQL, with compare-and-set revision checks. Policy changes and source ingestion hold the same brain lock. A prior write must finish before pause returns; a queued write sees the policy after obtaining the lock. Paused ingestion rejects new observations, notes, event-backed companion changes, archive uploads/restores and new durable-runtime turns. Reads, exports and core erasure remain usable.

Pausing closes unfinished durable turns and releases their scope reservations. In-flight generation and delivery retain uncertainty rather than being described as successfully cancelled. Confirmed delivery is not relabeled and may finish bookkeeping. Resuming does not revive an old turn. Host delivery drops explicit server rejections instead of preserving them in either spool file.

Migration 029 gives existing brains an unpaused policy at revision zero and preserves existing turn rows. The HTTP, Python and TypeScript interfaces require an explicit expected revision; a stale resume cannot overwrite a newer decision. Owner and brain isolation are tested.

## Verification

- 303 related source tests pass, zero skips, in 86.51 seconds, including real PostgreSQL transactions, upgrade migration, archives, host privacy, durable turns, API/SDK and native response-contract validation.
- 73 extracted-wheel tests pass, zero skips; the final installed group additionally exercises real HTTP rejection through host delivery and spool replay. All 201 runtime inputs match source byte-for-byte. Strict types, Ruff and wheel/sdist builds pass; 55 TypeScript tests pass with zero failures/skips.
- Both launcher equality checks pass. [Full Verify 42452597105](https://github.com/chriswu727/memBrain/actions/runs/42452597105) succeeds on `24fc22d9dadf453c37fc48cb6ffb333ce739211a`: **7,997 Python tests** in **2,224.30 seconds**, zero skips; **55 TypeScript tests**, zero failures/skips; strict types, Ruff and wheel/sdist builds pass. Three existing multiprocessing fork warnings remain.
- [Native qualification 42452597071](https://github.com/chriswu727/memBrain/actions/runs/42452597071) passes Windows x86_64, macOS arm64/x86_64 and Linux aarch64/x86_64. The 47 current-run summaries all report completion, zero model calls and successful recorded port closures; five duplicate qualification copies were excluded. Optional Linux compatibility jobs were not selected. This qualifies the engine/install/recovery checks, not every native agent/model journey.
- A fresh local instance was paused, fully stopped and restarted through the extracted-wheel runtime. Revision 1 and the paused state survived; a new write was rejected. Explicit resume advanced to revision 2, and only the resumed input was stored.
- A synthetic scale probe has 20,000 completed turns and eight active turns per pause. The actual candidate scan uses `memory_runtime_turns_pending_scope`, reading three shared buffers rather than scanning historical turns. Ten local pause operations have median **4.193 ms**, maximum **10.268 ms**, including connection/transaction overhead. All 80 active turns close and all 20,000 historical turn stages remain unchanged. This measures policy-control cost, not recall latency or a production capacity ceiling.

[PR #48](https://github.com/chriswu727/memBrain/pull/48) merged into `integration/maturity-candidate` as `9c940cc4198b4e44504024a4d7097589eaca6252`. Its complete tree `e9aad2af69bb97d81b682c2c5d875786aa5389b8` equals the qualified source tree. The evidence/status follow-up changes no runtime, schema, launcher, workflow or test inputs. Main remains unmerged and publication frozen.

## Retained development failures

The first local run had 1 pass and 10 setup errors because the disposable database role had not been provisioned. The wrapper now runs the application's role provisioning before tests; it does not use a privileged connection for application assertions. The next run had 10 passes and one failure: the HTTP response schema did not yet allow the new `recording_paused` code, causing a validation response instead of the intended rejection. The JSON contract and TypeScript error type were extended; the unchanged rejection assertion then passed. Both logs are retained.

## Scope still open

This server switch is independent of the existing local conversation/timed pause files. It does not clear disconnected hosts' staged inputs or queues, synchronize those local controls, or erase already stored history or external transcripts. Processing of existing memories may continue; this is a source-ingestion control, not a no-processing guarantee. A direct caller can deliberately submit content after recording resumes; denied request IDs are not a permanent tombstone ledger. An ephemeral durable-runtime chat mode and crash-atomic host ledger/delivery remain unimplemented. No new recall-latency, behavioral or personality/emotion acceptance is claimed.

See [API semantics](../docs/reference.md#server-recording-control) and [evidence](evidence/backend-server-recording-2026-11-07).
