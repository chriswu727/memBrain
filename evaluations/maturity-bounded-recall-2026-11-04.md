# Bounded recall work and current installation, 2026-11-04

Current source/launcher commit: `38c948a2f63664db6e169e324fce0522154ec563`. Runtime installed by all nine launchers: `60b8b746d5f389ef4a89e50564cc6280284dce44`. Full CI passes **6,994 Python tests with zero skips**, 44 TypeScript tests, strict type checking, Ruff and package builds. Fresh Mac installation passes **49/49**, and 165 installed files match the checkout. The canonical recall benchmark passes; a completed fullscreen comparison passes its phase aggregates, but two canonical-size windows exceed 600 ms. **Performance stability and real R4/C5 acceptance remain open.**

The [evidence directory](maturity-bounded-recall-2026-11-04/) contains raw measurements, an offline window audit, installation results, module hashes and an archive of 116 logs/harnesses. Archive and member hashes were independently read back and verified. Disposable profile credentials are redacted. Local originals remain under `/Users/yichen/tmp/membrain-sql-recall-20261104`. The [previous report](maturity-owned-recall-2026-11-04.md) remains a historical snapshot, including its failed full native run and incomplete comparison. No paid model, subscription evaluation or Claude session was called in this iteration. The Goal is active; the earlier heartbeat is paused.

## Implemented runtime changes

`1423776` prepares exact builtin Python type sets for the immutable contract schemas. A positive match handles only the `type` keyword; every other constraint still runs. Floats used as integers, subclasses, other numeric classes, unsupported declarations and extended validators fall back to the original Draft 2020-12 implementation. Cached child validators require the same validator class and format checker. This also repairs four reproduced custom-type-checker mismatches; overrides of keyword handlers retain their behavior. No record, validation result or user data is cached across requests.

`60b8b74` reuses the serialized lengths of fixed JSON field names and two fixed metadata values during one context-fitting invocation. Mutable status/limitation values are still measured each time. Existing full-render parity, relation/source checks, collision checks and exact UTF-8 budget accounting remain in place.

The lexical parse cache remains private to one scorer/request. Its bounds are now **512 strings and 65,536 input characters**, up from 128/16,384, to avoid reparsing the bounded candidate set. This trades bounded request memory for less CPU work; character count is not a bound on total process bytes. A new request starts a new cache. Candidate counts, query term limits, context budgets, ranking, ownership, RLS, erasure and schema constraints are unchanged.

Focused native checks pass: 44 contract tests, then 107 runtime/privacy/source checks, and 115 checks for the final fitting/lexical bundle. These groups overlap and must not be added together. The pin/matrix group passes four checks. Ruff passes. Regressions cover nonstandard numbers and subclasses, sibling constraints, custom type/keyword handlers, mutable limitations with CJK/emoji, exact whole-render lengths, independent cache lifetime, oversized strings and both cache bounds.

## Controlled comparisons

Each comparison uses a settled keyword corpus, four fresh HTTP processes in reference/candidate/candidate/reference order, eight brains × 21 queries per worker, discarding each worker's first query. Every measured context is nonempty. All 640 rendered-context hashes match across phases in each comparison; response IDs and timings are not asserted equal. The three integrated module files match their archived prototypes byte for byte and match the runtime pin.

| Change | Reference p95, phases 1/4 | Candidate p95, phases 2/3 | Decision |
| --- | --- | --- | --- |
| Key-first lexical SQL | 514.23 / 546.28 ms | 557.97 / 540.34 ms | Rejected; no consistent tail improvement |
| Prepared type checks | 572.35 / 516.47 ms | 492.46 / 500.49 ms | Integrated with correctness regressions |
| Fitting metadata and bounded parse reuse | 757.61 / 530.45 ms | 490.68 / 489.81 ms | Integrated with correctness/bound regressions |

The rejected SQL prototype also passes 450 exact row/order/truncation comparisons plus branch/empty-scope probes. It is retained as evidence and is **not in the runtime**. RSS samples vary between phases and do not establish a memory limit or absence of leaks. The bundle comparison did not successfully save its server GC log at SIGTERM; a missing log is not evidence of zero collections.

## Current canonical benchmark

The unchanged public benchmark creates eight brains with 1,000 keyword messages each and 100 notes in brain zero, waits for indexing, uses one service with semantic recall off, and makes no model calls. Client startup and reply generation are excluded. Machine: Apple M4, 10 cores, macOS 15.7.4, Python 3.12.13, embedded PostgreSQL 16.2. Each worker runs 21 queries and discards its first.

| Workload | Samples/nonempty | Median | p95 | Bar |
| --- | --- | --- | --- | --- |
| Serial | 20/20 | 82.56 ms | 94.78 ms | <500 ms: pass |
| One brain, eight workers | 160/160 | 453.63 ms | 476.74 ms | ≤1,000 ms: pass |
| Eight brains, eight workers | 160/160 | 465.54 ms | 528.58 ms | ≤600 ms: pass |

The benchmark exits 0. Map requests at both 200 and 500 nodes complete without errors. This establishes neither maximum storage capacity nor semantic-recall latency nor a service-level guarantee.

## Completed fullscreen comparison and window failure

The current runtime completes closed/open/open/closed with headed Chromium 153 on Apple M4/Metal, 1280×900/DPR1. Each phase has three cycles of the unchanged recall workloads, a fresh API process and normal page polling. Browser events are pumped during recall. Screenshots pause animation only after measurement. There are **4,080 measured nonempty recalls**, with no page errors or external requests.

| Phase | Duration | Serial p95, 60 samples | One-brain8 p95, 480 samples | Eight-brains8 p95, 480 samples |
| --- | --- | --- | --- | --- |
| Closed | 67.837 s | 111.89 ms | 560.74 ms | 570.31 ms |
| Fullscreen open | 68.014 s | 111.89 ms | 518.31 ms | 527.25 ms |
| Fullscreen open | 67.663 s | 111.60 ms | 540.09 ms | 528.45 ms |
| Closed | 66.856 s | 109.57 ms | 521.92 ms | 551.08 ms |

All four phase aggregates pass and the original comparison script exits 0. **That does not make every canonical-size window pass.** The separate offline audit reapplies the unchanged bars to all 36 workload windows and exits 1: eight-brain cycle 2 of the first open phase reaches **671.06 ms** over 160 samples; cycle 1 of the final closed phase reaches **605.36 ms**. No timing samples or windows are discarded. All eight workers slow together in the last round of the 671.06 ms window. The aggregate result and the failed window audit are both preserved; R5 stability qualification stays open.

Both open phases use the actual structural payload, **182 nodes/66 edges**. IDs and edges match API data before and after measurement. The hologram renders 2,042/2,032 frames, remains visible, and observes six real status/model/recording polls per open phase. The page does not normally poll the graph. Contours and simulated signals remain presentation; they are not stored biological neurons or live internal electrical telemetry.

## Retained failed attempts and bounded diagnostics

- The first simultaneous profiling attempt fails with `ValueError: Another profiling tool is already active`. Sequential profiling succeeds; instrumented times are not native latency. The inclusive client journey also captures work outside the immediate client and is not claimed isolated client-only CPU evidence.
- The earlier type-plan comparison stops on a screenshot timeout after eight-brain phase p95 values of 620.33/541.65/562.98 ms. The final closed phase never runs. It is incomplete, not a passing comparison.
- The first current-runtime comparison stops in its second open phase with `TargetClosedError`. Its completed phases measure 548.78/585.12 ms; neither those phases nor the incomplete run qualifies the release. No cause of that browser exit was established.
- The first short browser-lifetime probe fails because its close-event callback accepted the event as its captured dictionary. A new, corrected probe completes eight real open/render/close cycles, including screenshots, without an unexpected page close or crash. The completed comparison records every page close as expected and the browser's final process exit as 0. This does not retroactively explain the earlier exit.
- An earlier sustained GC diagnostic retains only its initial server buffer and drops 31,161 events. Its recorded maximum of 24.91 ms is therefore not the maximum over the whole run.

A follow-up diagnostic on the current runtime records complete per-generation GC counts/maxima and the slowest 64 event details, rather than truncating an initial buffer. It completes 1,440 nonempty keyword recalls: p95 **535.17 ms**, maximum **1,064.62 ms**. It is diagnostic, not another R5 qualification. Normal GC stays enabled and its thresholds are unchanged; no collection is forced.

The server observes 42,052 collections, including 316 generation-2 collections, with a complete-run maximum of **80.36 ms**. Client GC maximum is 8.92 ms. Some slow requests overlap server collections, but the recorded GC pauses alone do not explain the roughly one-second burst; overlap is not a sole-cause finding. PostgreSQL sampling completes without errors and mostly sees `ClientRead` while waiting for Python; IO, lock and vacuum-delay states also occur. Stack/CPU and wait attribution during the shared burst is the next performance investigation. The diagnostic's observer overhead and top-64 event detail limit remain explicit.

## Installation, package/browser and CI

The current pin passes the real clean-home Mac launcher journey **49/49**, exit 0, with the unchanged frozen basic baseline `d0d7a0379f7ac5f1b81dad04504601bb6606f1b0` and companion baseline `19e894ca9e08cf65fa071e8019789499953478d0`. It covers upgrade, cross-session recall, MCP save/correct/delete, restart, stub proxy, backup/restore/activation, persona, mood, reported feelings, shared moments, boundaries with aliases and support style. No real host model is used.

From the installed interpreter and API, **165 runtime/schema/migration/resource files match** source with no missing or unexpected files. Both memory and companion graph IDs/edges match the API; fullscreen 3D, accepted persona development and 2D fallback work. The browser reports zero page errors and zero external requests. Cleanup exits 0; seven task-owned profiles' API/database ports are separately confirmed closed. Local Docker remains unavailable and was not restarted.

| Source candidate | Full CI run | Python | TypeScript | Other checks |
| --- | --- | --- | --- | --- |
| `e5260bc` | [41878447057](https://github.com/chriswu727/memBrain/actions/runs/41878447057) | 6,970 passed, zero skips | 44 passed | Ruff, strict types, sdist/wheel pass |
| `ded4ae2` | [41884456254](https://github.com/chriswu727/memBrain/actions/runs/41884456254) | 6,992 passed, zero skips | 44 passed | Ruff, strict types, sdist/wheel pass |
| **`38c948a`** | [41889908273](https://github.com/chriswu727/memBrain/actions/runs/41889908273) | **6,994 passed, zero skips, three warnings, 1,305.55 s** | **44 passed** | **Ruff, strict types, sdist/wheel pass** |

The current full CI explicitly passes all four real Docker desktop/recovery/upgrade/standalone-chat journeys and the pinned real local-model/activation cases. Full decoded CI logs are retained. The older CLI log for `e5260bc` was truncated after 16%; its complete connector log is the source for that run's counts. Three Python multiprocessing/fork deprecation warnings remain, not failed assertions. Current Mac verification is the focused native groups plus the real install/browser journeys, not a claim that a new full native Mac suite was run.

## Remaining work

Reduce the synchronized recall tail without weakening validation, candidate/context bounds or privacy, then qualify every retained canonical-size window. R4/C5 still need a separately approved, frozen real behavioural attempt; the 280 CNY draft and subscription scenario/reviewer use remain unapproved. Final independent candidate review, acceptance report, default-branch merge, tag and publication remain pending. No release action was performed.
