# Recall performance and complete verification, 2026-11-04

The candidate now passes full CI with **6,631 Python checks and zero skips**, plus the TypeScript and package checks. Fresh Mac launcher acceptance passes **49/49**. Eight-brain recall still exceeds its 600 ms target, and real R4/C5 behaviour remains unaccepted; publication and main merge remain frozen. No Claude session, paid host model or subscription-backed evaluation was called in this round. The pinned local embedding model was exercised on CPU.

Runtime pin: `a3ccbda7503b45611a2affd583aec03604fed904`; source/pin commit `15fa8ecc9f7c39083ac9bae068f1529fda750570`. Later commits change the clock test fixture, installation runner and full-CI configuration only. The complete green candidate is `1bfc2b96632a2f0bc3fe932c90506cd5e2ac9ad0`. A file diff confirms its `src/membrain` and `pyproject.toml` match the runtime pin exactly. All nine launchers use that pin.

[Machine-readable reports, hashes and compressed logs/harnesses](maturity-recall-2026-11-04/) retain successful and failed attempts. Local originals are under `/Users/yichen/tmp/membrain-performance-followup-20261103`. Earlier topology evidence remains in [the previous report](maturity-structure-performance-2026-11-03.md).

## Changes shipped

- Contract validators prebuild child validators from the immutable, linked schema and share one prepared root. Every value is still checked. Reference-bearing or scope-changing schema cases fall back to standard validation. Boolean schemas, conditional/array boundaries, formats and error details remain covered. Tests compare all error metadata against the plain published contract, reject mutations after a successful validation and verify valid request records are not retained by the validator.
- Each lexical scorer reuses parsed terms within its own call, capped at 128 texts and 16,384 input characters. Grouping by actual evidence origin, multilingual terms, conditions, scores and ranking remain unchanged. There is no global cache of personal text or retrieved results.
- Owner/tenant transaction settings and action deadlines each use one SQL round trip instead of two. Retrieval reuses its already-read working state under the same brain lock and still filters it against current evidence. Real RLS tests include pooled connections after both commit and rollback.
- Installation acceptance selects a distinct available pair of recovery ports, rather than fixed ports, and stops a failed restore before reading recovery state or activating it. A later port collision still fails; there is no automatic retry or discarded failure.
- The scenario-clock service fixture now explicitly uses the embedded database it requires. Docker-specific journeys remain separate. Full CI now enables all four Docker journeys, prepares/verifies a cached pinned local embedding model and runs both real local-model cases. No paid host is configured.

## Unchanged canonical R5

The public benchmark seeded eight brains with 1,000 keyword messages each and 100 notes in brain zero. Indexing settled before measuring. Semantic recall was off and model calls were zero. Each worker ran 21 queries and discarded its first; client start-up and reply generation were excluded. Visualization was unloaded. All **340 measured responses were nonempty**.

| Operation | Median | p95 | Target/result |
| --- | --- | --- | --- |
| Serial, 20 samples | 98.16 ms | 109.13 ms | <500 ms: pass |
| One brain, eight workers, 160 samples | 571.60 ms | 638.32 ms | ≤1,000 ms: pass |
| Eight brains, eight workers, 160 samples | 579.06 ms | 686.13 ms | ≤600 ms: **fail** |

The benchmark exited 1. [Full samples](maturity-recall-2026-11-04/recall-canonical.json) include machine, conditions and lock waits. The earlier runtime's 127.57/757.01/728.24 ms p95 figures came from a different randomly identified fixture; those two runs alone are not a controlled improvement claim. No budget, candidate limit or validation rule was reduced.

## Controlled runtime comparison and context parity

An isolated HTTP ABBA run used the same settled corpus for all four phases. Reference children restored all four changed runtime modules (`contracts`, `storage`, `lexical_candidates`, `service`) from `84e973a8686ee6716bcf11123498a914a28db804`. Candidate children used the current runtime. Each phase ran eight brains × 21 queries and discarded the first per worker, with no model calls and no visualization.

| Phase | Runtime | Samples | Median | p95 |
| --- | --- | --- | --- | --- |
| 1 | Reference | 160 | 701.73 ms | 815.35 ms |
| 2 | Candidate | 160 | 601.34 ms | 647.90 ms |
| 3 | Candidate | 160 | 608.34 ms | 674.54 ms |
| 4 | Reference | 160 | 715.32 ms | 772.20 ms |

For every measured brain/query pair, the **rendered memory context SHA-256 matched across all four phases**. All 640 measured contexts were nonempty. This checks what the plugin actually gives its host, not just a candidate count. The envelopes' random IDs/timing fields were not claimed byte-identical. Both candidate tails improve in this comparison, but still exceed 600 ms. [Raw timings and context hashes](maturity-recall-2026-11-04/runtime-abba.json).

## Fullscreen 3D open versus closed

A separate same-corpus comparison kept Chromium open on a blank page for closed phases and opened the actual authenticated memory page plus fullscreen hologram for open phases. Each phase used a fresh API process, the same current runtime and all three canonical recall workloads. Headed Chromium 153 used **Apple M4/Metal**, 1280×900/DPR1, with actual structural payloads containing **183 nodes/66 edges** at the default 200/400 limit. Inspector and hologram IDs/edges matched the API.

| Phase | View | Serial p95 | One-brain8 p95 | Eight-brains8 p95 |
| --- | --- | --- | --- | --- |
| 1 | Closed | 112.33 ms | 608.21 ms | 662.61 ms |
| 2 | Open | 117.06 ms | 670.10 ms | 661.48 ms |
| 3 | Open | 118.01 ms | 625.09 ms | 624.96 ms |
| 4 | Closed | 111.73 ms | 599.79 ms | 594.88 ms |

All **1,360 measured recalls** were nonempty. Open phases rendered 777/734 hologram frames in 27.058/26.507 seconds, stayed visible and recorded no page errors or external requests. Closing released the renderer. Normal page polling remained enabled, but no browser API request occurred during these 26–27 second windows. Longer polling-active sessions and maximum-density graphs are not covered by this run. The final closed phase passes all bars in isolation; the earlier phases and canonical failure remain failures, so R5 is **not cleared by selecting that phase**. [All samples](maturity-recall-2026-11-04/visual-recall-abba.json).

The graph continues to show bounded actual stored versions and relationships. Brain shell/projector geometry is decorative; travelling signals are simulated. This work does not claim biological anatomy or live electrical/execution telemetry.

## Memory diagnostic

A diagnostic, not a latency benchmark, enabled `tracemalloc`, ran four 72-request batches per implementation and explicitly collected garbage between batches. All 576 recalls were nonempty. After the final two batches, the reference's live traced Python heap was 28.53/28.57 MB and the candidate's 35.17/35.16 MB (decimal MB). The last-sample difference is approximately **6.6 MB**; the candidate's last two samples did not continue growing. RSS snapshots varied substantially and include allocations outside the traced Python heap. These short, collection-assisted observations are **not** a long-duration leak, total-memory or capacity acceptance. [Raw heap/GC/RSS data](maturity-recall-2026-11-04/heap-diagnostic.json).

The first prototype built validators separately per definition and had much larger RSS snapshots; it was replaced with one shared schema root before committing. A separate scalar fast-path prototype matched 6,000 deterministic mutation cases and improved isolated validation microbenchmarks, but received no HTTP acceptance and **is not integrated**. Neither prototype is the shipping implementation. Their source and results remain in the archive.

## Complete verification and retained failures

- [GitHub Verify 41792234847](https://github.com/chriswu727/memBrain/actions/runs/41792234847) at `1bfc2b9`: **6,631 passed, zero failed/skipped, one warning**, 1,258.55 seconds. All four Docker journeys and both real local-embedding cases explicitly passed. **44 TypeScript tests**, strict typecheck, Ruff, sdist and wheel passed. [Structured CI proof](maturity-recall-2026-11-04/ci.json) and the full job log are retained.
- Mac/embedded full run at `a0d4682`: **6,625 passed, four skipped, three warnings**, 513.32 seconds. The four Docker opt-in journeys were not enabled locally because Docker Desktop could not start; they were subsequently exercised in Linux CI. Both cached local-model cases ran on Mac. This is not a zero-skip Mac run.
- Final harness/clock/pin/matrix group after the recovery-runner fix: **41 passed**, zero skipped, 7.64 seconds. The related native backend/contract/isolation group passed **157**, zero skipped, 19.38 seconds. Earlier standalone source checks with two/three database skips are preliminary evidence, not final acceptance.
- Final clean-home Mac launcher acceptance: **49/49 passed, completed**, at the unchanged runtime pin and unchanged frozen old baselines. [Results](maturity-recall-2026-11-04/install-final.json).
- Independent installed interpreter/API/browser smoke completed: **165 source/resource/migration files matched byte for byte**, no missing/unexpected files, both graph layers, exact API/3D identities and 2D fallback, no page errors/external requests. Its fixture stopped with exit 0. Its `source_commit` records the earlier equivalent runtime baseline `a0d4682`; runtime files remain identical at the later test/workflow heads. [Package proof](maturity-recall-2026-11-04/installed-package.json).
- Local sdist/wheel built successfully after the final runtime; neither was published.

Failures are preserved in the archive, rather than converted into passes:

| Attempt | Actual result | Follow-up |
| --- | --- | --- |
| Initial native invocation | No tests; exit 4, nonexistent test filename | Corrected the command |
| Native setup before role bootstrap | 68 passed, two failed, 71 setup errors | Dedicated fixture's application password differed from its role; bootstrap restored its own credentials, then 157 checks passed |
| First full Mac run | 6,624 passed, one failed, four skipped | Clock fixture required embedded binaries but started Docker; changed its engine, preserving every clock/mood/day-count assertion |
| First clock edit | 12 passed, one failed | Edited a unit helper call rather than the service fixture; corrected the service fixture, then 13 clock checks passed |
| First installed acceptance | 46 passed, two failed, incomplete | Fixed recovery ports conflicted, then the runner read nonexistent recovery status; distinct available ports and explicit failure stop were verified, then the fresh 49-check run passed |
| First expanded-CI workflow at `e7c6771` | Failed before any job, no Python test result | Job-level environment used unavailable `runner` context; moved the model path to an available `github.workspace` expression, then full CI passed |

The failed install's disposable homes, caches and databases were removed only after checking that none of their recorded ports was listening. Its original results and log remain. Fixture credentials in published raw logs are redacted. No user's Docker engine or unrelated service was restarted.

## Release status

Installation and complete CI now have current passing evidence. Concurrent eight-brain R5 remains open, with substantial tail variation. Real R4 memory usefulness and C5 personality/feeling/mood/relationship behaviour remain unaccepted; six historical R4 attempts remain failures. The separate evaluation-hardening/bookkeeping handoff and final independent release review remain pending. No new held-out scenario or paid/subscription evaluation was run, and the 280 CNY proposal is still an unapproved draft. No main merge, tag, GitHub release or PyPI publication is made by this report.
