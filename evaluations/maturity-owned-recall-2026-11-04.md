# Recall ownership, evaluation integration and installation, 2026-11-04

The fresh canonical keyword benchmark passes all three recall bars, but a longer run with the fullscreen graph open exceeds the eight-brain bar. **R5 remains open.** Installation passes 49/49 and the installed-package/browser journey passes with 165 matching files. Full candidate CI and real R4/C5 behavioural acceptance remain open. There was no Claude call, paid host call or subscription-backed evaluation in this iteration.

Runtime pin: `7d8d45a84856ecff6463d7b83ca85c723e296be3`. The pin commit is `37fab4463b2faf52d543a3e996938826d51909a3`; the later evaluation/test candidate is `e5260bc1ff2a53ab0e516f9d95b311de45329917`. Its runtime and `pyproject.toml` match the pin byte for byte. All nine launchers use that pin.

[Measurements, provenance, hashes and retained logs](maturity-owned-recall-2026-11-04/) accompany this report. Local originals are under `/Users/yichen/tmp/membrain-goal-polish-20261104`. The [previous iteration](maturity-recall-followup-2026-11-04.md) remains historical evidence, including its failures.

## Runtime change

Candidate collection was repeatedly deep-copying records freshly decoded by psycopg. `_bind_document` now binds these owned database records in place, preserving their visibility, conversation/branch restrictions and support-path scopes while updating the current binding/generations. `_rebind` retains its complete deep copy for borrowed records. The change is limited to fresh rows in event reads, candidate collection, belief-memory loading and source/passage expansion. It adds no shared record cache. Schema validation, RLS, source checks, ranking and all candidate/context budgets remain unchanged.

Source-unit grouping computes each version's grouping key once per invocation. It retains the same reference/scope/world grouping and version limits. Regression tests verify that mutating returned memories and source events does not affect later database reads, alongside the existing borrowed-record isolation tests.

## Canonical R5: passing run, not stable qualification

The unchanged public benchmark built a fresh fixture: eight brains with 1,000 keyword messages each and 100 notes in brain zero. Indexing caught up, semantic recall was off, visualization was unloaded and model calls were zero. Each worker ran 21 queries and discarded its first. Client start-up and reply generation were excluded. The Mac used Python 3.12.13 and embedded PostgreSQL 16.2.

| Workload | Samples/nonempty | Median | p95 | Bar |
| --- | --- | --- | --- | --- |
| Serial | 20/20 | 88.13 ms | 101.47 ms | <500 ms: pass |
| One brain, eight workers | 160/160 | 498.38 ms | 555.69 ms | ≤1,000 ms: pass |
| Eight brains, eight workers | 160/160 | 507.48 ms | 564.33 ms | ≤600 ms: pass |

The benchmark exited 0. Map requests at both 200 and 500 nodes also completed without errors. This run does not erase the longer-window failures below. Neither this keyword fixture nor the map timings establish semantic-recall latency, maximum storage capacity or a service-level guarantee.

## Controlled comparison and context equality

Four fresh HTTP processes used one settled corpus: reference/candidate/candidate/reference, eight brains × 21 queries, discarding each worker's first. The reference restored the six changed modules from `cbacab4`; candidate files match the runtime pin. The original run preceded the commit, so the separate provenance manifest records and verifies both sets of file hashes.

| Phase | Runtime | Median | p95 |
| --- | --- | --- | --- |
| 1 | Reference | 579.69 ms | 647.02 ms |
| 2 | Candidate | 495.35 ms | 527.67 ms |
| 3 | Candidate | 497.65 ms | 549.82 ms |
| 4 | Reference | 564.52 ms | 587.45 ms |

All 640 measured contexts were nonempty. For every brain/query pair, the rendered context SHA-256 matched across all four phases. Random response IDs and timing fields were not claimed identical. The reference's last phase also meets 600 ms; no single phase is selected to qualify the release.

## Longer fullscreen comparison: incomplete and performance still open

The next diagnostic used the same candidate and settled corpus, headed Chromium 153 on Apple M4/Metal, 1280×900/DPR1, with normal page polling retained. Each phase ran three cycles of the unchanged serial/one-brain8/eight-brains8 workloads. Browser events were pumped while workers ran.

| Completed measurements | Duration | Serial p95, 60 samples | One-brain8 p95, 480 samples | Eight-brains8 p95, 480 samples |
| --- | --- | --- | --- | --- |
| Closed | 69.717 s | 103.52 ms | 549.51 ms | 575.73 ms |
| Fullscreen open | 72.455 s | 114.85 ms | 562.75 ms | **630.51 ms: fail** |

All 2,040 measured contexts in these two phases were nonempty. Individual eight-brain cycle p95 values were 549.86/535.33/**601.17** ms closed and 565.22/**703.54/617.36** ms open. This is still insufficient headroom, including some variation with the graph closed.

The real structural payload contained 181 nodes/66 edges. API and renderer identities/edges matched before and after measurement; the hologram rendered 2,116 frames and stayed visible. Six actual polling requests occurred: two rounds of brain status, local model/service status and recording status. The page does **not** normally poll the graph.

The comparison script incorrectly required a graph-poll request and exited 1 after the first open phase. The remaining open/closed phases did not run, so this is **not a completed ABBA acceptance**. Its partial measurements and failed script remain intact. A corrected, unexecuted follow-up checks the actual status polling and exits nonzero when the measured recall bars fail. No runtime behavior or recall threshold was changed to fix the harness. Further performance work precedes qualification.

## Evaluation tooling integrated

Claude's existing `claude/eval-hardening@857f9c5` was merged without calling a Claude session. It adds frozen-manifest attempt ordering, source/hash binding, explicit offline/live separation, shared spending-stop guards, count-only prechecks, strict scoring and source-grounded deletion/boundary resolution. These mechanisms do not grant permission to run a paid attempt.

The previously proposed bookkeeping patch is now integrated: if memory recording fails after a synthetic paid reply, the reply/usage row is saved, recording is marked unknown, the ledger is blocked and the original error propagates before another host call. The merged harness and regression file match the previously tested patch hashes. The historical proposal and its failures remain in the repository; they are not described as still pending at this candidate.

The combined local evaluation/billing/semantic-read/pin/matrix group passed **484 checks**, zero skips, two multiprocessing warnings, in 50.46 seconds. Inputs were public synthetic fixtures and provider responses were intercepted. This does not pass real R4 or C5.

## Verification and retained failure

- Initial scoped runtime/privacy/source checks: **107 passed**, 7.08 seconds. An earlier invocation named a nonexistent test file and exited 4 without running tests; its log is retained.
- Pin/matrix group: **4 passed**, 0.35 seconds. Ruff for `src`, `tests` and `examples` and `git diff --check` passed.
- Final supervisor, legacy acceptance, companion, pin and matrix compatibility group after the evaluation merge and documentation update: **38 passed**, 22.75 seconds.
- Full native run at `37fab44`: **6,627 passed, one failed, four skipped, three warnings**, 506.32 seconds. It is not a passing full run.
- The failure was a test-fixture collision: the erasure assertion searched the entire response for `7721`, which appeared in the legitimate timestamp `.177218Z`. The test now uses a distinctive full secret, deliberately fixes the recall timestamp to include those digits, and checks that neither the secret nor its event ID returns. The raw source must still be deleted; shared-read write guards remain unchanged. The corrected semantic/candidate/source/copy group passed **55**, 8.66 seconds.
- Fresh Mac launcher install/upgrade/restart/MCP/backup/restore acceptance at the current runtime: **49/49 passed**, complete, with the same frozen old basic and companion baselines.
- Installed interpreter/API/browser journey: **165 source/resource/migration files match**, no missing or unexpected files, memory and companion graphs match the API, fullscreen and 2D fallback work, no page errors or external requests, cleanup exits 0. Six task-owned profiles' API/database ports were independently checked closed.
- [Verify 41878447057](https://github.com/chriswu727/memBrain/actions/runs/41878447057) at `e5260bc` is running its full Python suite at this report's snapshot. The earlier runtime run [41876450754](https://github.com/chriswu727/memBrain/actions/runs/41876450754) was cancelled after the follow-up push; it has no completed test result. Neither is claimed green. The earlier `1bfc2b9` zero-skip CI result is historical, not a full check of this candidate.

The four native skips are the opt-in Docker desktop/recovery/upgrade/standalone-chat journeys; Docker Desktop remains unavailable locally. The current CI configuration enables them and both real pinned local-model cases. No failing assertion was disabled and no failed run was relabelled as passed.

## Remaining release work

R5 needs sustained headroom with normal fullscreen polling, followed by a complete comparison. Current full CI needs its actual result. R4/C5 need the separately approved frozen behavioural attempt; the 280 CNY proposal remains unapproved. The real model's handling of memory, personality, inferred feelings, relationship boundaries and resets is therefore unaccepted. Final candidate review, acceptance report and publication remain pending. No default-branch merge, tag, GitHub release or PyPI publication occurred.
