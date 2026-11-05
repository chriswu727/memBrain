# Complete familiarity counts and graph evidence — 2026-11-05

Runtime: `47fcb96684b367dd2f6e30d4cdc6cb5657b5fa58`. Frozen fullscreen source/pin commit: `02679fb10219da2e41ea8068d8e3e38428542917`. Build ID: `30da9f98a0144b0a88fdb754adb7a4f214e654333ed95245406277506533e0dd`; schema unchanged (`e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`). **Current performance qualification fails; publication remains frozen.**

## Behavior and representation

The previous familiarity calculation inspected only the latest 2,500 milestone notes, then counted at most 500 shared moments. A real database regression demonstrates the defect: one existing shared moment followed by 2,500 ordinary milestones produces a count of zero. Display sampling was changing the relationship itself.

Shared moments now stream through the validated note parser in batches of 256. The calculation counts all visible, valid shared moments after the latest reset while retaining only the latest 500 for display. The relationship API reports `shared_moments_total` and `shared_moments_truncated`; the page explains the display limit. Reset reports and erases the complete shared-moment count. A 501-moment test verifies that the count remains 501, the display holds 500, and a reset removes all 501. This follows the preceding [long-history boundary/cap/reset fix](maturity-relationship-history-2026-11-05.md), which is included in this candidate.

The companion graph adds a **derived familiarity summary**, separate from its record nodes. It includes the same day/moment counts and cap used by the relationship rule. Its evidence references point only to shared moments, a cap and a reset marker actually present in the bounded graph. A reset node is a stored reset event; there is no invented familiarity neuron or dependency edge. A summary based on known sensitive conversation days or moments is masked by default, including private evidence outside the 500-item display and outside a one-node graph. Explicit authorized sensitive opt-in reveals it. Reset, source erasure and archive restore update the result from surviving records.

The English/Chinese sidebar labels the result as a calculation, not affection. Fullscreen remains the record graph. Real browser checks compare the API, 2D, observatory and hologram nodes/edges, exercise resets and layer changes, and verify localized summary text. This is not a claim of human feelings, new model reasoning or behavioral R4/C5 acceptance.

## Checks and retained failures

- The initial product regression failed with `0 == 1` for the displaced shared moment.
- The first expanded local run had **111 passes and two failures**: new browser fixtures called nonexistent `MemoryClient.store_note`. They were corrected to the real `write_note` API. The next group passed **113 tests in 70.55 seconds**.
- Adding archive-summary assertions, exact fullscreen/2D parity, reset checks and the mood suite produced **143 passes and one failure in 86.18 seconds**. The boundary-only guard still patched the removed `_moments` helper; it now patches the actual `_moment_state` aggregator and continues to forbid aggregation on boundary reads. That exact case passed separately (**one pass, 45 deselected, 7.97 seconds**). Runtime source hashes match the 143-pass run; only the guard target changed. This is not represented as one 144-pass invocation.
- Preceding working-map [full CI 42104743561](https://github.com/chriswu727/memBrain/actions/runs/42104743561), source `2b0719b`, finished with **two failures, 7,413 passes and three warnings**. Static region/edge inventories omitted `working`, `working_member` and `working_evidence`. Their exact expected inventories are corrected. A further local static test expected the old relationship-coverage wording; it now checks the explicit derived-summary explanation. The complete static group passes **12 tests**. No check was skipped or changed to accept arbitrary extra regions or edges.
- Two launcher-pin checks, full Ruff and diff checks pass. Current-runtime full CI remains required. Earlier worker-runtime full CI/native successes retain their historical scope.

## Current fullscreen result: failed

The unchanged closed/open/open/closed protocol used the retained eight-brain corpus, one persisted working state, fresh API per phase, normal polling and hardware WebGL. It completed all **36 windows** and **4,080 nonempty recalls**, with **34 windows passing and two eight-brain failures**:

| Window | Eight-brain p95 | Required maximum |
| --- | ---: | ---: |
| Second visible phase, cycle 3 | 645.75 ms | 600 ms |
| Final closed phase, cycle 2 | 638.78 ms | 600 ms |

Worst serial/same-brain/eight-brain p95 was **180.70/523.29/645.75 ms**, against the unchanged 500/1,000/600 ms bars. The later closed phase also slowed, so the data do not establish a renderer-specific cause. Both visible phases still matched the API's **187 nodes/71 edges**; screenshots were inspected. Frozen inputs were unchanged and owned ports closed. No samples or failing windows were discarded. The preceding runtime's 36/36 pass is not inherited, and no unchanged rerun was used to select a green result.

## Storage observation and next action

A separate post-run, read-only metadata inspection found a **3,652.50 MiB** retained test database. `memory_traces` occupied **2,351.23 MiB** (about 1,572,323 live rows), `memory_requests` **1,183.18 MiB** (about 30,792 live rows), and `memory_events` **34.96 MiB** (about 10,609 live rows). Sizes include each table's indexes and TOAST storage; row counts are PostgreSQL statistics estimates. This database includes accumulated benchmark activity and other owned synthetic test records, not only the eight reference brains.

These measurements show substantial audit-storage cost but **do not identify the cause of the two latency failures**. Inspection did not delete traces/receipts, vacuum away evidence or change the recall dataset. Next: inspect trace/receipt write and read paths and quantify lossless storage/write improvements while preserving complete audit data, idempotency, deletion and backup/restore behavior. A fresh installed-package/host qualification and R4/C5 still remain; paid or subscription model evaluations need separate approval.

## Evidence

The [32-payload manifest](evidence/maturity-familiarity-map-2026-11-05/manifest.json) includes failed and passing checks, runtime identities, the complete preceding CI job log, all latency samples, drivers, screenshots and the storage diagnostic. The initial local driver was reconstructed and its bytes matched its recorded hash. Text/log/JSON payloads are gzip compressed; decompression and both stored/original hashes were checked. Exact scans against the three credentials in the owned benchmark profile found no matches; no universal secret audit is claimed. No model evaluations or Claude sessions were used in this batch. No merge, tag or release was made.
