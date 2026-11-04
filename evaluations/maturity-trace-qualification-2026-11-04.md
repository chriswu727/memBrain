# Trace runtime qualification and graph privacy follow-up

**Measured runtime `f1fc97b` passes the complete R5 workload.** The subsequent graph-only privacy runtime `b994ec8080d46ee861f6ed8738a1617929f50d2a` now masks recording times; its fresh installation, full CI and end-to-end qualification remain pending. No merge, tag or publication is authorized while remaining gates are open.

## Fixed reference-Mac performance

Source `9b9bad016ad7223991c98ee74e34ddb49ceb95b4`, all nine launchers pinned to runtime `f1fc97b193f816ccfe4d3988c797060fff2bbbc6`. This is the final ordered trace-set insertion implementation, not the earlier write-only prototype. No source, test, pin or benchmark input changes during either run; the wrappers verify their hashes and independently check that API/database ports close.

The unchanged canonical fixture uses eight independent brains, 1,000 keyword messages per brain and 100 notes in brain 0. Indexing settles before measurement. Each worker executes 21 queries, discarding only its declared first warm-up. There are no model calls. On Apple M4, ten cores, macOS 15.7.4, Python 3.12.13 and embedded PostgreSQL 16.2:

| Workload | Retained nonempty recalls | p95 ms | Bar ms |
|---|---:|---:|---:|
| Serial | 20 | 100.86 | <500 |
| Eight workers, one brain | 160 | 505.47 | ≤1,000 |
| Eight workers, eight brains | 160 | 509.02 | ≤600 |

All **340 recalls are nonempty**, exit 0. Map API p95 is 11.28/14.57 ms at 200/500 nodes; these API timings are not frame-rate or storage-capacity claims.

The complete hardware-backed closed/open/open/closed comparison then uses the same corpus, a fresh API per phase, three cycles per phase and every canonical workload per cycle. Normal page polling stays enabled. All **36/36 workload windows pass**, all **4,080 recalls are nonempty**, and all twelve eight-brain windows meet 600 ms:

| Phase | Eight-brain window p95 values, ms |
|---|---|
| Closed 1 | 526.73 / 540.06 / 494.88 |
| Open 1 | 513.04 / 515.22 / 484.00 |
| Open 2 | 489.28 / 511.32 / 521.32 |
| Closed 2 | 496.86 / 556.70 / 513.70 |

Maximum eight-brain window p95 is **556.70 ms**. Both open phases use ANGLE Metal on Apple M4, with 1,977/1,985 hologram frames during measurement. All **183 node IDs and 66 edges** match the actual authorized structure-map payload, including the fullscreen view. Both screenshots were visually inspected. There are no page errors, external requests or artifact failures; all six owned ports close. The shell and simulated-signal label are decoration, not extra records or a live execution trace.

This proves the fixed keyword/performance gate on the measured runtime. It does not establish semantic recall speed, large-corpus capacity, real host/model behaviour or a universal latency guarantee. The earlier `e749a24` four-window failure, maximum 742.02 ms, remains [retained evidence](maturity-boundary-refresh-2026-11-04.md). No unchanged rerun was used to replace it; the trace persistence implementation changed. The earlier [write diagnostics](maturity-recall-writes-2026-11-04.md) are separate from this end-to-end qualification.

## Sensitive recording-time masking

Read-through review finds that masked nodes hide text and details but retain `recorded_at`. Four actual-database regressions reproduce this on the legacy memory map, structure map, companion map and note-linked affect. Runtime `b994ec8` sets this field to null on masked nodes through the shared graph builder and legacy note/message/affect paths. It changes no stored record or timestamp. Public records and explicit authorized sensitive opt-in retain original timestamps where provided.

The first post-fix group has **92 passes and one failure**: a new test incorrectly expects episodes and patterns to have original timestamps, although those graph records never supplied them. The corrected test keeps every masking assertion, checks available timestamps and compares the original message timestamp exactly with its stored source. Two additional real-browser tests inspect private and public details in 2D and 3D.

The final local group passes **95 tests, zero skips**, including all memory/structure/companion map tests, observatory tests and the actual memory-page/3D browser journeys. Ruff and four pin/matrix checks pass. The nine launchers now pin `b994ec8`; install/upgrade/recovery and R5 requalification for this follow-up remain pending. The preceding `9b9bad0` CI is not yet complete; no full-CI result is inferred from local checks or an older candidate.

## Fixture preservation and remaining gates

The stopped passing `f1fc97b` fixture and its registry are privately cold-archived. All **1,487 regular-file hashes** are verified in a single forward stream before removing only the owned profile to reclaim space. The registry remains. Archive bytes and credentials are never committed; public metadata records its checksum. The earlier failing `e749a24` archive is also retained. This is evidence storage, separate from the product's backup/restore path, which must be qualified for the current runtime.

The [allowlisted manifest](maturity-trace-qualification-2026-11-04/manifest.json) binds raw samples, wrappers, screenshots, privacy failures and the final local result. No paid/subscription model test or additional Claude consultation is performed. R1 and current-runtime R5 await the new qualification; real R4/C5 and final independent/privacy/design acceptance, including remaining graph coverage, are still open. Goal work continues without a schedule.
