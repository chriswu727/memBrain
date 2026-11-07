# Successive feelings, startup diagnostics and recall performance

Runtime: `c7db08733e09bb30e90b2200458cefeb105811db`; launcher source: `05ab9632715b62d6a5fa1cd097a7c9ef937da7ff`. Publication remains frozen. **Full R5 failed: 26 of 36 workload windows passed.** Earlier installation and performance passes do not qualify this changed runtime.

## Implemented behavior and collaboration

Claude supplied `8867fc6` and `8febd2c` on `claude/companion-development`, integrated as `8c47fd7` and `7db427b`. A later affect record for the same note or exact explicit topic supersedes an earlier trigger. Topic comparison normalizes case and whitespace; it does not infer related topics. Reported feelings can replace reported or inferred feelings; inferred feelings cannot replace a reported feeling. Neutral and sensitive corrections can end an old trigger without exposing themselves as public triggers. Historical views before the correction retain the old trigger. Deleting the correction can reactivate a still-live predecessor. Reset, pinning and restore exclusions remain in force. The memory page names the superseded status in both languages.

Codex replaced the quadratic successor search with a reverse index retaining separate reported and inferred successors for each note and topic. A nearer inferred record cannot hide a later reported correction. The earliest eligible note/topic successor wins without transitive topic merging or persistent caches.

The separate Claude review session [identified two startup gaps](https://github.com/chriswu727/memBrain/pull/43#issuecomment-6670613008): native CI omitted readiness coverage, and Uvicorn's unsuccessful startup could raise `SystemExit` without a structured failure record. Codex added readiness/startup tests to the native matrix and its relevant path filters. Desktop startup now records unsuccessful exits and returns an actionable failure, including construction-time exits and a server returning without becoming ready. Exception text and string exit codes are not copied into logs. Normal shutdown and clean exits retain cleanup behavior.

## Verification

- The mood index passed 18 focused tests, including independent ordered-pair oracle comparisons over 16 seeded histories and note/topic competition cases.
- The combined real-PostgreSQL group passed **374 tests in 113.26 seconds**, with no skips. It covers API, executor/readiness, persona growth, mood/succession, affect, relationship, host and maturity behavior. Source/test hashes remained unchanged and owned ports closed.
- The later desktop/executor/readiness group passed **111 tests in 4.27 seconds**. Failed before-fix evidence remains: four failures and two passes for startup diagnosis, then one construction-time regression caught before the final correction. Intermediate 108/111-pass runs are retained rather than counted as additional coverage.
- All nine launchers pin `c7db087`; both pin checks passed. Ruff and whitespace checks passed before qualification.
- A source distribution and wheel built successfully. The separately installed wheel matches all **185 runtime inputs** and the source build/schema identities. **49 installed-wheel checks passed in 1.89 seconds**, covering mood indexing, executor behavior, readiness, startup failures and the actual imported package identity. Source and installed hashes remained unchanged. This uses existing third-party dependencies; it is not a clean dependency installation, launcher upgrade or full R1 qualification. It is separate from the earlier 49-journey launcher acceptance result.
- Earlier-source native CI [42116516451](https://github.com/chriswu727/memBrain/actions/runs/42116516451), at `6cee3ea`, passed all five platforms. That workflow did not yet include the new readiness/startup tests; it does not qualify those changes. Full CI [42116516361](https://github.com/chriswu727/memBrain/actions/runs/42116516361) at that same earlier source passed 7,447 Python tests with three warnings, 50 TypeScript tests, strict type checking, Ruff and package builds. New-runtime CI and applicable installed qualification remain required.

## Mood calculation diagnostic

Six mocked record workloads compare the original successor scan with the index, using 50, 250 and 501 records, repeated or distinct topics, mixed reported/inferred bases, neutral corrections and sensitive records. Each uses 12 repetitions with alternating order. Every complete trigger list is equal.

| 501-record workload | Original median | Indexed median |
| --- | ---: | ---: |
| Distinct topics | 43.217 ms | 0.651 ms |
| Repeated topics | 2.023 ms | 1.031 ms |

This isolates Python mood calculation. It excludes database access, HTTP and model work and is not an end-to-end latency or R5 claim.

## Fullscreen R5: failed

The unchanged closed/open/open/closed protocol uses fresh API processes, three cycles per phase, the retained eight-brain corpus, normal 30-second page polling and hardware WebGL. Every workload keeps the declared warmups and all measured samples. All **4,080 measured recalls were nonempty**. No model calls occurred. Source and driver hashes remained unchanged; the browser and owned ports closed normally.

| Phase | Eight-brain cycle 1 p95 | Cycle 2 | Cycle 3 |
| --- | ---: | ---: | ---: |
| Closed 1 | 809.13 ms | 670.79 ms | 1,353.78 ms |
| Open 1 | 641.01 ms | 548.36 ms | 511.25 ms |
| Open 2 | 530.71 ms | 647.56 ms | 1,176.95 ms |
| Closed 2 | 678.71 ms | 649.59 ms | 1,043.14 ms |

Nine eight-brain windows exceed 600 ms. Open 2's third same-brain window also fails at 1,448.89 ms against its 1,000 ms bar. Serial windows pass. Neither phase aggregation nor the three good eight-brain windows erase the ten failures. Failures with the page closed prevent attributing the result solely to rendering; this run does not establish a causal regression from the mood index.

Both open phases use the Apple M4 Metal renderer and expose 187 stored/derived graph nodes and 71 evidence/membership edges, with no page errors or external requests. Screenshots were captured after measurement with animation paused. The decorative brain silhouette and simulated signals are presentation; they are not additional stored memories or biological neural measurements.

## Full-request process experiment

A separate, non-production prototype compares the current API-thread collection/two compute workers with two initialized workers owning complete recall service transactions. Authentication and other endpoints remain in the API. The database transaction, idempotency lock, response validation, traces and receipt write stay together in one worker.

The baseline/prototype/prototype/baseline experiment completed **1,360 measured recalls**, plus declared warmups, with identical context hashes for all 160 distinct brain/query pairs. Inputs remained unchanged, no model calls occurred and owned ports closed.

| Eight-brain result | Baseline 1 | Prototype 1 | Prototype 2 | Baseline 2 |
| --- | ---: | ---: | ---: | ---: |
| Median | 365.77 ms | 368.15 ms | 328.38 ms | 400.94 ms |
| p95 | 573.89 ms | 502.27 ms | 390.47 ms | 469.86 ms |
| API and worker RSS | 263.34 MiB | 301.83 MiB | 304.23 MiB | 261.59 MiB |

The results warrant further investigation but do not establish a stable speedup: the ranges overlap and both baseline windows also pass 600 ms. This shorter experiment excludes the fullscreen workload. The prototype is not adopted: it lacks production queue-deadline, admission, crash-recovery and lifecycle handling, and additional service processes may duplicate local model resources. Its fixed outer timeout is not a replacement for the request budget. Context equality on this fixture does not qualify privacy, recovery, local-model behavior or general recall quality.

The [evidence manifest](evidence/maturity-mood-succession-2026-11-05/manifest.json) preserves 44 payloads, including all failed checks and R5 measurements. The initial whitespace check rejected trailing spaces in two raw pytest failure logs. Those exact logs are now stored compressed, with the failed formatting check retained. Copies and compression round trips were verified by bytes and SHA-256. Exact scans against three credentials from the owned benchmark profile found no matches; this is not a universal secret audit. No paid or subscription-backed model evaluation, merge, tag or release occurred.
