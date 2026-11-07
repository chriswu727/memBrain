# Passive recall diagnostic storage

Repeated recalls duplicated each candidate diagnostic: once inside the idempotent response receipt and again as a separate learning trace row. The service now keeps those diagnostics in the response receipt only. The returned contract and replay response remain unchanged. Context selections, quotations and external feedback continue to have durable learning records. Source invalidation and deletion continue to invalidate response receipts.

## Observed accumulation

A read-only aggregate of the retained synthetic performance database found **4,459,878 `candidate_hit` rows and 10 `context_selected` rows**. The trace relation occupied 6,928,384,000 bytes including indexes and possible free/dead space. The request relation occupied 3,485,982,720 bytes; 87,554 live recall responses accounted for 3,272,970,890 bytes measured with `pg_column_size(response)`. Original events occupied 38,379,520 bytes including indexes. This database includes multiple test brains and repeated stress runs; these are not normal-user capacity estimates or a benchmark of memory usefulness.

The measurement used bounded aggregate SQL, a read-only transaction and a statement timeout. It completed in 1.88 seconds and stopped the owned database. No historical rows were deleted. Internal feedback readers use actual selection/quotation records and prepare receipts, not passive candidate hits; the existing external-feedback regressions verify this boundary.

## Controlled checks

The new serial and four-thread regressions fail on the original implementation: **2 failed, 1 passed**. Each repeated-read arm accumulated 16 duplicate trace rows. With the repair, the feedback, autonomous feedback, response validation, process transaction and new storage suites pass **119 tests in 19.00 seconds**. They check exact replay responses, key conflicts, original assertions, absence of artificial reinforcement, deletion invalidation, worker failure and transactional rollback. Ruff and diff checks pass.

The first repaired run was **118 passed, 1 failed**: an existing test explicitly expected duplicate SQL trace storage. Its replacement checks the exact returned diagnostics inside the durable replay receipt. The failed output is retained; this intentional persistence-policy change does not weaken response validation. Direct `_save_traces` validation and duplicate-key behavior still pass.

A separate comparison uses the original installed service module and the repaired module against the **same database, original source identities, fixed clock, questions and budgets**. All 20 canonical full results match. Only ephemeral recall/snapshot/trace identities, timestamps and elapsed time are normalized. Original calls add one row per returned diagnostic; repaired calls add none.

## Write-volume probe

Two disposable databases receive the same 32-message template and 200 recall requests each, with no model calls. The baseline uses the actual installed `3b4720e` package. The repaired arm uses this development source. Each returns 4,600 candidate diagnostics.

| Additional live row data | Original | Repaired |
| --- | ---: | ---: |
| Candidate trace rows | 4,600 | 0 |
| Candidate trace bytes | 6,072,000 | 0 |
| Request receipt bytes | 3,648,286 | 3,663,120 |

These are sums of `pg_column_size(row)`, not filesystem space reclaimed, WAL bytes or index sizes. Source event and assertion counts and byte totals remain unchanged within each arm. The fresh fixtures have different source identities and ingestion times: their tied result subsets differ, so they do not establish result parity. The same-corpus comparison above does. Wall times are retained (4.535 versus 4.426 seconds), but this single ordered comparison does **not** establish a latency improvement.

The initial probe failed before recall because a helper allowed only 20 pending jobs for 32 newly ingested sources; the corrected probe drains after each observation. Its failure, unregistered-marker warnings and original script are retained. All disposable test databases stop and their profiles are removed.

## Remaining product work

This repair prevents new duplicate candidate rows. It does **not** remove the historical 4.46 million rows or bound response-cache growth. Normal writes invalidate cached response bodies, but repeated read-only requests retain complete responses indefinitely. Bounded receipt retention must preserve request fingerprints, explicit expired-replay behavior, current-source/privacy validation and prepare/feedback bindings. Historical cleanup must be incremental and avoid a large startup delete or disk-intensive database rewrite. No source memories, personality, emotion or relationship history should be pruned by a diagnostic-cache policy.

The [raw evidence manifest](evidence/maturity-recall-diagnostics-2026-11-07/manifest.json) retains failures and successful checks. This is development work based on the passage candidate; full CI and integration delivery remain separate gates. R4 remains failed, C5 incomplete, and no new paid or subscription evaluation ran. No main merge, tag or release occurred.
