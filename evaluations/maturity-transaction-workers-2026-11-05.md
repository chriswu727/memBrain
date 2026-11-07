# Bounded full-transaction recall workers

Runtime: `d32e93f8ace920cb016a574f69a75a9bb3a205f2`; launcher source: `6e9276e6f38b3b642e51b4e9d8772090abdacf2a`. **The complete fullscreen performance protocol passes all 36 windows.** Publication remains frozen: current-runtime full CI, complete installation journeys, R4/C5 and final review remain open. The previous full CI has two unresolved failures described below.

## Architecture and tradeoff

The default HTTP service now uses four bounded processes for complete recall and preparation transactions. Candidate collection, ranking, owner/tenant checks, brain locking, response validation, traces and idempotency receipts stay in the same worker transaction. The original request is preserved for idempotency; only internal computation receives the remaining budget. The parent also validates returned responses, including responses from custom or overridden service implementations.

The existing admission bound, startup readiness, timeout handling and broken-pool recovery are reused. A timed-out running task holds its slot until it actually completes. Queue and transaction work share an absolute monotonic deadline; database timeouts and computation are clamped to remaining time, and a final deadline check before commit rolls back an expired transaction, including a receipt already inserted. Workers carry the application database connection settings and recovery owner identities, but not API keys, administrative database credentials, model sessions or model transports. Query embedding remains in the parent and is handed off once with the provider-space identity. The core remains independent of host frameworks. Inline SDK behavior is retained; `MEMBRAIN_RECALL_PROCESSES=0` opts out for constrained installations.

The larger process pool costs memory. One production-process snapshot during the final closed phase totals **417,840 KiB (408.05 MiB)** for the API and descendants. This is one sample, not a peak or leak bound; it excludes PostgreSQL, Chromium and a local embedding model. No model is installed in the performance fixture. Parent-only provider ownership is tested with a stub transport; this batch does not qualify real ONNX throughput or total semantic-mode memory.

## Why this change

The preceding runtime's instrumented HTTP run attributes about 43.4–43.6 ms of API-process CPU to each concurrent host recall. Service response processing accounts for 29.1–29.5 ms, including 19.7–19.9 ms in collection; SQL execute/fetch accounts for 7.7–7.9 ms and JSON decoding for 3.7–4.2 ms, with overlapping inclusive scopes. JSON response encoding costs about 0.9 ms. This points to collection and transaction work in the API process rather than a primarily HTTP serialization problem. The instrumented results are diagnostic, not qualification measurements.

A separate four-worker prototype completed 1,360 measured HTTP recalls in baseline/prototype/prototype/baseline order, with identical context hashes for all 160 distinct brain/query pairs. Eight-brain p95 was **359.83 / 288.21 / 290.20 / 350.60 ms**. Prototype serial p95 increased to 240.06–242.56 ms versus baseline 100.75–116.50 ms; memory also increased. That prototype lacked production deadline/recovery handling and could duplicate provider resources. The implementation above adds those protections. Prototype numbers are not substituted for the production result below.

## Fullscreen performance qualification

The unchanged closed/open/open/closed protocol uses fresh API processes, three cycles per phase, the retained eight-brain corpus (1,000 messages per brain), normal 30-second polling and the real Apple M4 Metal renderer. All declared warmups and measured samples are retained. **4,080 of 4,080 measured recalls are nonempty; zero model calls occur.** Source and driver hashes remain unchanged, all owned ports close, and the browser closes normally. There are no page errors or external browser requests.

| Phase | Eight-brain cycle 1 p95 | Cycle 2 | Cycle 3 |
| --- | ---: | ---: | ---: |
| Closed 1 | 326.17 ms | 332.10 ms | 338.43 ms |
| Open 1 | 369.37 ms | 385.82 ms | 417.35 ms |
| Open 2 | 401.23 ms | 333.57 ms | 371.74 ms |
| Closed 2 | 364.21 ms | 317.39 ms | 309.53 ms |

All 12 eight-brain windows meet 600 ms. The worst serial window is **332.91 ms** against 500 ms; the worst same-brain window is **565.94 ms** against 1,000 ms. Thus all 36 windows pass. Both open phases display **187 stored/derived nodes and 71 evidence/membership edges**. Screenshots are captured after measurement with animation paused; the shell and simulated signals are illustrative, not additional memories or biological measurements. This reference-fixture pass is not a capacity limit, a universal device claim or a real-model behavioral acceptance result.

The first attempt at runtime `f766285` failed before workloads started: stripping API credentials also removed the recovery authority's owner identities. The guard correctly refused startup. The fix passes owner principals separately without API credentials, preserves recovery reconciliation, and adds a registered-owner process test. Only the subsequent `d32e93f` run above qualifies; the failed attempt remains in `visual/` and the completed attempt in `visual-v2/`.

## Verification and failures retained

- The real-PostgreSQL guard group passed **83 tests in 10.83 seconds**, zero skips. It covers seven full-transaction cases, pure executor/readiness behavior, response validation, HTTP, vectors, tenant/owner isolation and recovery erasure/quarantine. Full canonical result equality uses the same explicit access timestamp. Idempotency conflict/replay, deletion invalidation, lock timeout, parent-only embedding, killed-worker recovery and registered recovery identities are exercised. An injected delay after an actual receipt INSERT verifies rollback of both receipt and trace on expiration.
- The final control/startup group passed **33 tests in 1.27 seconds**. In-process desktop control fixtures explicitly disable spawned recall workers because their fake database is not usable across processes; these tests do not qualify the default worker path. The real-database cases and HTTP performance run cover that path.
- The first readiness group had two failures from obsolete two-worker constructor mocks. A result-parity test then found tiny timestamp-dependent ranking differences; an explicit access timestamp is now forwarded, without removing score comparisons. A rollback assertion initially queried the wrong table and failed; its corrected query passed. Five desktop control tests initially failed because their mocked database could not be used by spawned children. All original failure logs remain in the evidence bundle.
- Both launcher pin checks pass. Ruff and whitespace checks passed before qualification. The source archive and wheel build successfully. A separately installed wheel matches all **187 runtime inputs** and the source build/schema identities; **41 installed checks pass in 1.80 seconds**, with source and installed hashes unchanged. Existing development dependencies are reused. This is not a clean dependency installation or complete install/upgrade/restore acceptance.
- Previous-source Verify [42120264525](https://github.com/chriswu727/memBrain/actions/runs/42120264525), at `f10b136`/runtime `c7db087`, **fails: 2 failed, 7,481 passed, 3 warnings**. The 2D privacy browser case cannot click a node whose projected center is covered by a neighboring node. The failed-start test observes a worker still alive after cleanup. TypeScript and build steps are skipped after pytest fails. These are unresolved follow-up work, not waived failures or a green result for this runtime.
- Previous-source native CI [42120264677](https://github.com/chriswu727/memBrain/actions/runs/42120264677) passes five platforms and includes the then-current readiness/startup tests. It does not qualify the new full-transaction architecture. New-head CI is required.

Codex implemented and tested this batch. Independent Claude review is being requested through a separate CLI session restricted to repository reads, with no Desktop or browser tools. The user's active Claude window must not be inspected or operated. A review request does not count as a completed review.

The [manifest](evidence/maturity-transaction-workers-2026-11-05/manifest.json) retains 65 payloads: diagnostics, prototype, successful and failed checks, both fullscreen attempts, installed checks and earlier CI evidence. Copied bytes/SHA-256 and compression round trips are verified. Exact checks against three owned-fixture credentials find no matches; this is not a universal secret audit. No paid or subscription-backed model evaluation, merge, tag or release occurred.
