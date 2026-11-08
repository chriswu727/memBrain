# Stored recall eligibility

Runtime `10dbeb05eaaca1aca4a69962585fa07dc2957566` removes repeated JSON-document reads from ordinary recall's assistant-speech exclusion. Migration 031 stores the **exact previous SQL predicate** as the generated boolean `recall_non_speech`. `_eligible` uses that column when speech is excluded. Owner, tenant, brain, conversation/branch scope, current-version/lifecycle controls, requested-speech inclusion, candidate limits and ranking remain unchanged. This projection is one retrieval filter, not a replacement for authorization or evidence validation.

Build: `023580cb5ff5900d6f0f3a425f5df813886a06b1ca189eac6c88513382e17f07`. Schema: `c48792e8a1d8c4d6cf7c591c92f6529dda10ee1d801d7f332b284cda52b272d8`. All nine launchers pin this runtime in `2c230565aef47452847449aca4667c6f0eb10f38`. [PR #51](https://github.com/chriswu727/memBrain/pull/51) merged into integration as `17508898f9056e5f6bea210fcdfb69cc44836925`. Its complete tree `568a4f13f36d32d4adfd10bdbfc9951b91b93283` equals the exact qualified source tree. Five-platform native qualification and full Verify pass. Documentation/evidence follow-ups change no implementation inputs. Main, tags and publication remain frozen on failed R4 and invalid/unscored C5. No paid or subscription-backed evaluation was run.

## Complete host recall

The retained public synthetic corpus contains 10,000 source events, assertions and whole-memory embeddings, with no passage embeddings. Twenty existing multilingual questions use actual cached local ONNX embeddings and ordinary host context rendering. The 5,000 ms host budget, candidate limits and questions are unchanged. Four fresh-service phases run in baseline/candidate/candidate/baseline order; each phase has one client followed by eight simultaneous clients sharing one brain. Each client has one explicit warmup followed by all twenty measured questions, rotated by client index. OS/database caches are not flushed. These timings have no internal function/SQL instrumentation.

Both variants use the same migrated database and physical storage. The candidate is the extracted wheel; the baseline is that wheel with only `candidates.py` replaced by integration `a3d9970`'s original implementation. Its build is `1bd6f38f8fa0dfb7020ee21cde4108d2fca768ec5d83ca4e4e97003dc75ebc94`. Separate Python environments ensure spawned services/workers load the intended version. This isolates the predicate change, not pre-upgrade versus post-upgrade physical layout.

| Phase | Serial median / p95 | Eight-client median / p95 |
| --- | --- | --- |
| Baseline 1 | 282.704 / 467.448 ms | 798.747 / 861.482 ms |
| Candidate 1 | 146.288 / 331.152 ms | 300.615 / 416.249 ms |
| Candidate 2 | 144.102 / 328.043 ms | 291.942 / 392.137 ms |
| Baseline 2 | 289.458 / 480.202 ms | 817.182 / 893.910 ms |

Serial median latency falls about **48–50%** and eight-client median latency about **62–64%** in this workload. All **720 measured requests and 36 warmups** hit the expected source using exactly one semantic recall without fallback. All four core-table snapshots and package source hashes remain unchanged; owned ports close after every phase. These are local descriptive measurements, not a universal latency guarantee, memory-capacity ceiling, passage-heavy result, first-install latency or R4/C5/R5 acceptance. Warmup latencies remain in the evidence and are not represented by the measured medians.

The independent strict comparison covers twenty questions × three token budgets (2,048/12,000/64,000) × two intents (explore/exact quote), using the same transaction, local embedding and fixed access time. All **120 pairs** match in full ordered candidate documents and complete candidate state. Core data remains unchanged and ports close. The comparison swaps the shared eligibility function so lexical, semantic, source and passage candidate routes use the correct baseline/candidate predicate; it does not substitute an approximate vector algorithm.

## Storage, write and upgrade cost

The generated column recomputes with document changes, including updates and archive restoration. It preserves SQL's three truth values: missing/null fields are not coerced into admission. Content-erased rows still fail the independent `document IS NOT NULL` condition, even where the derived predicate itself is true. This is logical row filtering, not a forensic disk-erasure claim.

Migration 031 rewrites the assertion heap and rebuilds existing indexes inside the migration transaction. It requires an exclusive maintenance window and temporary disk/WAL headroom. The cost probe uses ordinary logged clones of the public corpus with all defaults, indexes and generated columns, and REINDEXes both clones after loading. LIKE does not copy foreign keys or row security; these are isolated database cost measurements, not application ingestion latency or security qualification. Five alternating insert/update samples each affect 1,000 rows and roll back. Updates change both `document.statement` and `search_text`; samples include ordinary index/WAL work but exclude application/network/consolidation and commit fsync.

| Rows | Baseline assertion relation total | Projected total | Migration time | Logical flag bytes |
| --- | --- | --- | --- | --- |
| 10,000 | 45,383,680 bytes | 45,850,624 bytes | 0.556 s | 10,000 |
| 50,000 | 216,481,792 bytes | 216,678,400 bytes | 2.265 s | 50,000 |

Totals include the table, indexes and TOAST. Additional relation storage is about **1.03%** at 10,000 and **0.09%** at 50,000; page packing and rewrite layout affect the physical result, so this is not a general fixed overhead percentage. The logical flag occupies one byte per non-null row in these samples. Median 1,000-row insert time changes from **83.875 to 99.614 ms** (about 15.7 ms more). Update medians are **97.132 versus 92.012 ms**; the small decrease does not establish a write-speed improvement. All samples remain recorded.

Upgrading the actual retained 10,000-memory profile took **0.444 s**. All four core tables matched their prior JSON values after excluding only the new derived flag. Temporary cost tables were rolled back and owned ports closed. These timings do not extrapolate to arbitrarily large installations.

## Correctness and package verification

- 243 related source tests pass, zero skips, in 20.50 seconds. A strengthened archive-restoration assertion was then verified with all 19 archive tests (1.83 seconds); this is not 19 additional unique tests.
- The same 243 related tests pass against the extracted wheel in its separate environment, zero skips, in 22.67 seconds. All 204 runtime inputs match source byte-for-byte. Wheel/sdist builds, Ruff, diff checks and both launcher-pin checks pass.
- 871 raw JSON/SQL-null combinations preserve the previous predicate's exact true/false/null values, including absent fields, malformed types, assistant claim kinds and direct-capture prefixes.
- Explicit owner, conversation, branch and lifecycle checks preserve admission under both aliases, both current-version modes and both speech-inclusion modes. Existing bounded speech/semantic/lexical/source/passage/window/neighborhood tests remain active.
- Changing a document changes its admission immediately. Nulling content excludes it in both speech modes. Actual archive restoration regenerates flags matching valid documents' speech classification.
- Migration tests inject a failure after DDL and preserve all prior records and the migration marker on rollback. Successful upgrade is repeatable, preserves all prior columns including lexical terms, retains forced row security, and is rejected by an older runtime.
- Historical migration-030 tests explicitly stop at 030; their record, rollback, index, RLS and compatibility assertions remain unchanged. The new 031 migration has its own preservation tests.

## Qualification and limits

[Native qualification 42509325198](https://github.com/chriswu727/memBrain/actions/runs/42509325198) passes all five platforms on exact source `2c230565aef47452847449aca4667c6f0eb10f38`. All 47 audited current-run execution summaries complete with zero model calls and successful recorded port closures; five duplicate qualification copies are excluded. Optional Linux compatibility jobs were not selected. Windows JSON line endings are normalized to LF with value equality asserted and both original/stored hashes retained. [Full Verify 42509327602](https://github.com/chriswu727/memBrain/actions/runs/42509327602) passes 8,032 Python tests with zero skips in 1,779.28 seconds, 56 TypeScript tests, strict types, Ruff and wheel/sdist builds. Three existing multiprocessing fork warnings remain. Native qualification reuses checksummed owned bundles from run 42459291814: native build scripts, supplier configuration/resources, dependency lockfile and workflow are unchanged from that qualified run. All current-source installation, upgrade, recovery, rollback, permissions and port-closure checks still run; this does not claim fresh recompilation of native suppliers.

[Evidence](evidence/maturity-stored-recall-eligibility-2026-11-08) retains raw samples, import/build identities, reproduction scripts, costs and check output. No private profile, credential, model binary or held-out scenario is included. The public corpus generator and original provenance remain in the [preceding evidence](evidence/maturity-stored-lexical-projection-2026-11-08/public-corpus-cases.json).

This changes retrieval computation, not memory extraction quality, personality/emotion behavior or release acceptance. No paid evaluation or publication was performed.

## Remaining latency diagnosis

A separate instrumented serial run finds candidate collection at median **73.207 ms**, lexical routing at **25.515 ms**, and semantic-pool SQL at **26.377 ms**. Local query embeddings have median **2.142 ms**. These stages nest and include instrumentation overhead and a warmup; do not sum them or substitute them for the uninstrumented comparison.

The three slowest measured serial requests in that diagnostic are each the first request handled by a different recall worker (the explicit warmup reached the fourth worker). Their complete-context times are 318–352 ms; subsequent requests are faster. A follow-up fresh-service diagnostic times `native_contracts._compiled`: its first call in each of five processes (API plus four recall workers) takes **131–152 ms**, whereas the 37 cached lookups have median **0.000458 ms**. This identifies response-validator preparation/import/schema checking as a substantial first-use cost; it does not explain every cold-start cost. No validation rule or production initialization behavior was changed. Cold-start/warmup latency remains in the evidence. Moving preparation before readiness is a future candidate requiring startup, optional-accelerator fallback and validation-integrity tests, not a shipped fix.
