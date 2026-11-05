# Recall attribution and rejected optimization prototypes

Source: `99d3133fd0d9fd7a020a70575f4ca083e696357f`; runtime: `47fcb96684b367dd2f6e30d4cdc6cb5657b5fa58`. These experiments do not change the production runtime and do not qualify R5. The current [34/36 fullscreen failure](maturity-familiarity-map-2026-11-05.md) remains authoritative. No traces, receipts or source memories were deleted to improve measurements.

## Storage experiment

The retained database's audit tables account for most of its storage. A repeatable sample of 10,000 trace rows was copied into temporary tables with the original indexes. Three repetitions compared default storage with `MAIN` targets of 1,024 and 512 bytes and an `EXTENDED` target of 512 bytes, reversing mode order on the middle repetition. Every copy preserved exact JSONB values, row identity, owner and `applied_at`.

All twelve copies occupied **15,671,296 bytes**, with an average document size of **1,148 bytes**. No storage reduction occurred. This is consistent with PostgreSQL's distinction between the threshold for invoking TOAST and the target size used after invocation; changing the target does not force every smaller row through compression. See the [PostgreSQL 16 TOAST documentation](https://www.postgresql.org/docs/16/storage-toast.html) and the native supplier's `heapam.c` threshold check. Temporary-table timings do not measure durable WAL or commit cost. No storage setting or migration was adopted.

The first driver attempted `CREATE TEMP TABLE AS` inside a read-only transaction and failed with `ReadOnlySqlTransaction`. Its source, error and cleanup result are retained. The corrected driver writes only temporary copies, rolls back and stops the owned database; it does not modify original table rows.

## Concurrent request attribution

An instrumented real API, using the normal two-worker runtime and retained corpus, completed three serial warmup calls and two groups of 160 calls across eight independent brains. All 323 host contexts were nonempty, no model calls were recorded, runtime hashes remained unchanged and owned ports closed. **The first recall attempt was rejected with `budget_exceeded` after 5,138.42 ms.** The host's existing fallback retried it and returned a context; consequently the recorder contains four warmup attempts, three completed and one rejected. Successful final contexts do not erase that cold-start failure. The executor is currently lazy, so its initial process startup falls inside the first request's budget; readiness/startup handling needs investigation and regression coverage.

| Mean stage time per recall | First concurrent group | Second concurrent group |
| --- | ---: | ---: |
| Candidate collection wall time | 81.10 ms | 126.22 ms |
| Candidate collection thread CPU | 22.91 ms | 22.52 ms |
| Existing compute queue/transfer/work wall time | 23.41 ms | 26.23 ms |
| Trace write wall time | 9.85 ms | 8.41 ms |
| Request receipt insert wall time | 5.59 ms | 4.95 ms |
| API process CPU per request | 55.86 ms | 50.48 ms |

Inclusive stages overlap. SQL wall time includes scheduling and server waits; this is not a proof that query execution alone caused the previous R5 failures. Instrumentation adds overhead. Client p95 was 617.55/428.20 ms, and these diagnostic windows do not replace the release protocol. The evidence points toward candidate processing and API-side contention as worthwhile targets, while audit writes alone do not account for the full observed latency.

## Deferred document query prototype

A query variant delayed fetching large memory documents until after the hashed and exact channels selected their candidates. It preserved both channel sentinels, document-key deduplication and ordering. Across 96 paired comparisons (eight brains, three queries, four repetitions), returned rows and truncation flags matched exactly.

The original/deferred median times by repetition were **9.764/6.431**, **6.133/6.263**, **6.014/6.237**, and **6.314/6.249 ms**. The aggregate favored the variant largely because the original ran first against colder data. Warm results did not demonstrate a stable improvement. The production query was left unchanged.

## Candidate scoring process prototype

The next prototype moved initial lexical scorer construction and candidate scores onto the existing two-worker pool. It added no workers, retained the current scoring rules and returned the scorer for subsequent source processing. This is experiment code, not a production-ready executor extension: its transport/error handling and budget interface would require implementation and tests before adoption.

A full HTTP **baseline / prototype / prototype / baseline** comparison completed all four phases, each with serial, same-brain and eight-brain workloads. It recorded **1,360 measured nonempty recalls**, plus declared first-call warmups. Context hashes agreed for all **160 distinct brain/query pairs**. All source, test and driver hashes remained unchanged; owned ports closed.

| Eight-brain result | Baseline 1 | Prototype 1 | Prototype 2 | Baseline 2 |
| --- | ---: | ---: | ---: | ---: |
| Median | 405.23 ms | 369.87 ms | 358.90 ms | 638.81 ms |
| p95 | 544.21 ms | 672.88 ms | 448.82 ms | 749.84 ms |

Baseline serial median also rose from 88.50 to 155.37 ms across the experiment. This drift limits causal attribution; the prototype itself still exceeded 600 ms once. It was not adopted, and the good middle window is not selected as qualification. A later system snapshot showed Spotlight activity but was not synchronized with measured requests and is not evidence of the cause.

## Delivery and next work

No speculative runtime optimization is included in this batch. Current-runtime [installation/upgrade/restore qualification](maturity-installed-candidate-2026-11-05.md) subsequently completed 49 checks with zero failures against the real pinned launchers. Claude delivered a contradictory-persona-feedback change at `67243f3c513c05701dc41bf92a6f3e478c3aad07` on `claude/companion-development`. Codex reviewed it and requested reproduction of a possible withdrawal-revival defect when a contradiction falls outside its 5,000-row scan, plus deletion/reset/restore regressions. That branch is not integrated or independently qualified here; the follow-up is recorded in [PR #43](https://github.com/chriswu727/memBrain/pull/43#issuecomment-6670156522). Codex retains performance, storage and integration ownership. Next runtime priority is reproducing and fixing cold executor startup before readiness, followed by controlled attribution of remaining tail latency. Full CI and all remaining behavior/performance gates remain required; no merge, tag or release was made.

The [evidence manifest](evidence/maturity-performance-attribution-2026-11-05/manifest.json) preserves drivers, failed and completed attempts, all samples and API logs. Compression round trips and stored/original hashes were verified. Exact scans against the three credentials in the owned benchmark profile found no matches; this is not a universal secret audit. No paid or subscription-backed model evaluation was run.
