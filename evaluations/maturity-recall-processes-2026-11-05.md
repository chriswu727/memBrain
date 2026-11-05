# Bounded recall processes: current latency qualification

Runtime `06f0dd32cef0327a4f519ea91b1e99e77c921be7`, frozen at source `51403b66c2155172ac3fa0151413f54a885f46d0`, moves recall scoring and context construction into two local spawned processes. The full fullscreen latency protocol passes **36/36 windows** on the retained reference corpus. This is a performance result, not release approval or evidence that humanlike memory, personality or emotion acceptance has passed.

Build identity is `279fb892d44151fafeb1e349286adf305babbfb524efe462c4864d9c4c59bae7`; schema remains `e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`. All nine launchers pin this runtime. Later MCP test-fixture corrections do not change runtime bytes.

## Implementation and correctness

The API retains database access, tenant/owner/brain scope, deletion locks, result validation, trace writes and request receipts. Only the pure computation receives the authorized snapshot. Workers are trusted local processes, not a security sandbox. They do not dispatch model calls. No ranking rule, source filter, context limit or validation was removed.

Admission is bounded to four tasks per worker, including running work. Queue and transfer time count against the computation deadline. A timed-out running task keeps its slot until it finishes, preventing unbounded accumulation. Overload, shutdown and worker failure produce retryable errors; the pool can recover after a crash without replaying the failed request automatically. Scenario clocks cross the process boundary explicitly and are restored after each task. Application shutdown joins the workers. `MEMBRAIN_RECALL_PROCESSES=0` selects inline mode; supported process counts are 1–4, default 2. Direct embedded services stay inline unless configured with a runner.

**322 focused tests pass, zero skips**, including real PostgreSQL erasure/read exclusion and request deduplication in both inline and process modes, output/provenance/context parity, overload, timeout admission, crash recovery, host/relationship behavior and zero-model C5/clock harness checks. Frozen test inputs remain unchanged and owned ports close. Both launcher-pin guards pass; Ruff and diff checks pass. A first parity assertion failed because it compared volatile elapsed time (56 passed, one failed); the corrected comparison validates then normalizes elapsed time and generated IDs/timestamps, while preserving substantive output fields. That initial failure is retained.

## Full HTTP comparison and memory cost

The full-request profile showed CPU work spread across scoring, JSON serialization and context construction; optimizing only one tiny cache had not solved the preceding latency failures. The retained profile and a process-isolation prototype informed this implementation. Instrumented profile timings are not release latency measurements.

The production comparison starts a fresh API in **inline / process / process / inline** order, using the same owned eight-brain corpus with 1,000 messages per brain. Each phase measures serial, eight callers of one brain and eight independent brains: 1,360 measured nonempty recalls, plus declared first-call warmups. Context hashes agree for all **160 distinct brain/query pairs**. Source and driver bytes remain unchanged; owned ports close. There is no browser in this comparison.

| Eight independent brains | Inline 1 | Process 1 | Process 2 | Inline 2 |
| --- | ---: | ---: | ---: | ---: |
| Median ms | 346.14 | 310.76 | 289.80 | 346.45 |
| p95 ms | 371.25 | 359.87 | 324.72 | 382.53 |
| API and worker RSS sum, MiB | 148.2 | 259.1 | 248.3 | 170.9 |

The memory numbers sum process RSS, including shared pages; they are not measurements of unique physical allocation. The extra workers trade additional memory for lower contention. Same-brain p95 improves from 410.13/410.68 ms to 329.68/335.75 ms; serial p95 is 86.09/89.32 ms inline and 84.70/81.85 ms with workers. These observations are limited to this machine and workload.

## Fullscreen protocol: 36/36 pass

The unchanged closed/open/open/closed protocol runs three cycles of all three workloads in each phase, with a fresh API per phase, hardware rendering, visible animation and normal status polling. Each worker makes 21 canonical queries; only its declared first warmup is discarded. All **4,080 measured recalls are nonempty**. Worst individual-window p95 is **124.04 ms serial**, **378.45 ms for eight callers of one brain**, and **359.68 ms for eight independent brains**, below the unchanged 500/1,000/600 ms bars.

| Phase | Eight-brain p95 cycle 0 | Cycle 1 | Cycle 2 |
| --- | ---: | ---: | ---: |
| First closed | 359.11 | 330.31 | 359.68 |
| First open | 332.47 | 330.06 | 314.27 |
| Second open | 339.49 | 341.61 | 335.61 |
| Last closed | 343.82 | 346.41 | 313.92 |

Both open phases render **183 nodes and 66 edges** exactly matching API node IDs and edges, using Apple M4 Metal. They record 1,234 and 1,225 animation frames. Screenshots were captured after measurement and inspected. Page errors and external page requests are empty; browser stderr retains a `DEPRECATED_ENDPOINT` registration message. The command exits zero, frozen source/tests/launchers/drivers remain unchanged, and all owned ports close. This is the first full run for this implementation, not a selected passing rerun.

The existing synthetic database is reused, not cloned into another installation. It contains normal access/trace writes from earlier experiments; the integration guards also create isolated random test scopes. These results do not claim a pristine fixture or a fresh installed-package run. Earlier failures, including the preceding runtime's [31/36 fullscreen result](maturity-recall-boundaries-2026-11-05.md), remain preserved.

## CI and remaining release gates

[Previous Verify 42093439325](https://github.com/chriswu727/memBrain/actions/runs/42093439325) completed with **5 failed, 7,371 passed**, three warnings. All five failures are MCP fixtures that only served the old relationship endpoint. The initial `gh run view --log-failed` output was incomplete; the direct job log contains the complete result and is retained as authoritative. The fixtures now exercise both the current boundary endpoint and legacy 404 fallback, including real stdio/HTTP transport and refusal to recall after boundary-read failures. All **10 MCP tests pass** locally with those corrections.

Full Verify must pass on the corrected candidate. The interim Verify `42098863774` was cancelled after confirming it still contained those known failing fixtures. [Five-platform native verification 42098895915](https://github.com/chriswu727/memBrain/actions/runs/42098895915) uses immutable source `51403b6`, including explicit spawned-worker tests, and reuses already-built native artifacts; it was running when this report was written. Redundant automatic native run `42098863635` was cancelled to avoid rebuilding the same binaries. Neither an in-progress nor cancelled run is counted as a pass.

Current latency now has a complete passing run. Remaining gates include full CI, installed runtime/host coverage, held-out R4/C5 behavior, persisted working-state and complete familiarity graph projection, and final independent review. The 3D match proves the currently projected bounded topology, not complete coverage of all memory structures. No paid/subscription model tests, Claude sessions, merge, tag or release were performed.

[Evidence directory](maturity-recall-processes-2026-11-05/) contains 29 payloads with a SHA-256 [manifest](maturity-recall-processes-2026-11-05/manifest.json): profiles, prototype and production comparisons, exact drivers, failures, passing guards and fullscreen captures. Logs are gzip-compressed with decompression equality checked. Exported bytes were scanned against three exact credential values in the owned benchmark profile, with no matches; this is not a universal secret scan.
