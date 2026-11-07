# Recall persistence: write reduction and diagnosis

Runtime candidate `f1fc97b193f816ccfe4d3988c797060fff2bbbc6` includes two changes: invalidated request receipts are no longer rewritten, and recall traces are inserted as one ordered JSONB set. All nine launchers now pin this candidate. Its full CI, fresh installation and end-to-end R5 qualification are pending. The earlier `ba863a9`/`e749a24` qualification remains historical; its fullscreen R5 failure is not replaced by a microbenchmark.

## Invalidated request receipts

Real PostgreSQL regressions fail on the previous implementation in both ordinary source editing and recovery quarantine: an already-NULL receipt receives a new `xmin` despite retaining identical content. The repair adds `response IS NOT NULL` to both invalidation statements. It preserves the row, key and request fingerprint; live responses are still invalidated. Tests check that a different brain is untouched, the current response replays exactly, old matching requests return `version_conflict`, mismatched fingerprints return `idempotency_conflict`, and repeated quarantine remains idempotent.

The first post-repair run had one test-authoring error: an existing assertion was accidentally placed inside the new test. It was moved back to its original test, with the assertion retained. The first wider command selected a nonexistent test file and ran no tests. The corrected real-database group passes **47 tests**, zero skips. Both owned ports close after every run.

On the preserved failed R5 fixture, brain 0 has **2,850 receipts and all are non-NULL**. Consequently, this predicate does not reduce writes on that recorded state and is not established as a fix for its latency failure. A fixed original/filtered/filtered/original `EXPLAIN ANALYZE` experiment rolls back each update and confirms unchanged response counts. It selects the same 2,850 rows every time. The first cold operation writes full-page images; later operations do not. Their timings/WAL differences cannot be attributed to the predicate. No index, receipt deletion, retention limit or schema migration is introduced.

## Trace persistence

Concurrent SQL timers on a fresh, hash-verified restoration find candidate reads and trace insertion as substantial wait locations. Sixteen core recall actions all complete with 51 items/traces, approximately 241 KB per response. These timers include client scheduling and database waits; they are not PostgreSQL executor-only timings or complete plugin latency.

The old implementation already uses pipelined `executemany`. The prototype instead sends the complete trace array in one statement through `jsonb_array_elements`, retaining every document and `ON CONFLICT DO NOTHING`. Its fixed A/B/B/A experiment uses eight brains, ten batches of 51 actual retained trace documents per worker and phase, with transaction/commit included. Every batch is validated before timing; no timed sample is discarded. It excludes reads, HTTP, host context and the renderer.

| Phase | Implementation | Batches | Median ms | p95 ms | Exact documents verified |
|---|---|---:|---:|---:|---:|
| A1 | Pipelined inserts | 80 | 14.40 | 22.61 | 4,080 |
| B1 | JSONB set prototype | 80 | 2.94 | 4.87 | 4,080 |
| B2 | JSONB set prototype | 80 | 2.76 | 4.39 | 4,080 |
| A2 | Pipelined inserts | 80 | 15.03 | 18.44 | 4,080 |

All **16,320 documents match exactly**. The shipping implementation additionally uses explicit ordinality and ordering so the first document wins when a batch repeats an ID. This ordering clause was not in the timed prototype; the table is not a measurement of the final shipping statement. Final database regression coverage verifies validation before any write, empty batches, duplicate IDs with different valid documents, existing-row preservation and both already-validated/untrusted call paths. Feedback, dynamics and trace retention remain intact.

The broader group passes **203 tests**, zero skips, after fixing a missing test import. The preceding run retains **202 passes and one NameError failure**. After explicit ordering is added, the affected response-validation, feedback and dynamics group passes **156 tests**, zero skips. Ruff and the two immutable runtime-pin checks pass. No test assertion or validation boundary is weakened.

## Diagnostic limits and retained failures

The initial diagnostic refuses to start because it incorrectly assumes an optional local-model directory cannot exist when weights are absent. A corrected attempt encounters conflicting concurrent cProfile instances in this Python runtime. Its incomplete profiling output and HTTP 500 errors are retained and do not count as application qualification. The revised diagnostic completes 16 SQL-timed concurrent recalls and two separately CPU-profiled serial recalls. Even the serial cProfile records contain process-level activity from other threads; their function times are exploratory and cannot establish per-request CPU attribution. The SQL timers and trace-write comparison drive the next action.

Every restoration verifies all **1,485 profile file hashes** against the private cold archive before starting, and verifies the existing recovery registry without overwriting it. API/database processes are stopped and ports checked; successful disposable restored copies are removed. The original private archive is retained and never committed. No paid or subscription model call, external model provider, Docker restart or unrelated cleanup is used.

The [allowlisted manifest](maturity-recall-writes-2026-11-04/manifest.json) preserves scripts, raw samples, successful checks and failed diagnostic/test outputs. **R1 needs requalification for the new runtime; R5, real R4/C5 and final independent/design/privacy review remain open.** Publication, merge and tagging remain frozen. Next: fresh fixed canonical and full fullscreen qualification, plus installation/recovery acceptance, without changing their bars or selecting an unchanged rerun for a green result.
