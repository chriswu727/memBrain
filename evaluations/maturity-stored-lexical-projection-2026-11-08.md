# Stored lexical projection

Runtime `d54a521b73bad6659359c0878d6b0310609233e0` replaces query-time PostgreSQL tokenization with a stored generated `search_lexemes` column. The expression remains `to_tsvector('simple', search_text)`. Migration 030 replaces the existing expression GIN index with a column GIN index. Candidate eligibility, independent channel limits, overflow sentinels, ordering, scope and ranking policy are unchanged. Content updates, erasure and archive restoration regenerate the projection inside the same database write.

Build: `8ad617800ab6be5706b8a37bf5163384087d035c2399fa185f428c04ea49a04d`. Schema: `cead8d1aec92ed9f78f2e56fd84e6e606995332ba7f907da97837888aa744c74`. All nine launchers pin this runtime in `8421b0bfd5cc0a6ac24a93e968ffee072109f6f5`. [PR #50](https://github.com/chriswu727/memBrain/pull/50) is integrated. Five-platform native qualification and full Verify pass; main and publication remain frozen on failed R4 and invalid/unscored C5. No paid or subscription-backed evaluation was run.

## Recall measurements

The retained public synthetic corpus contains 10,000 source events, assertions and whole-memory embeddings, with no passage embeddings. Twenty existing multilingual questions use actual cached local ONNX query embeddings and the ordinary host context path, with the original 5,000 ms budget. Four fresh-service phases run in baseline/candidate/candidate/baseline order. Each client performs one explicit warmup and twenty measured requests; phases run one client followed by eight clients sharing one brain. OS/database caches are not flushed. No generation/provider/subscription calls occur.

Both variants use the same migrated database and identical physical storage. The candidate is the extracted wheel; the baseline is that wheel with only `lexical_candidates.py` replaced by integration `268dbb3`'s recomputation implementation. Its build is `38f722a5de5b6c8a93aad2c9340ae60c6e1bf02f1f02af2edc23f445f0763826`. This isolates the query-expression change; it is not a comparison of pre-upgrade versus post-upgrade disk layouts. Each variant has a separate Python environment so spawned service/recall processes import the intended build. These measurements have no internal SQL/function instrumentation.

| Phase | Serial median / p95 | Eight-client median / p95 |
| --- | --- | --- |
| Baseline 1 | 305.094 / 493.697 ms | 868.103 / 931.245 ms |
| Candidate 1 | 284.140 / 465.039 ms | 855.026 / 923.573 ms |
| Candidate 2 | 284.019 / 477.953 ms | 869.890 / 913.610 ms |
| Baseline 2 | 310.911 / 502.722 ms | 926.641 / 1,032.081 ms |

Serial medians improve by about 7–9% on this workload. Concurrent ranges overlap; this does **not** establish a reliable concurrent speedup. All 720 measured requests and 36 warmups hit the expected source and use exactly one semantic recall without fallback. Four core-table snapshots and package source hashes remain unchanged; owned ports close after every phase. These are descriptive local measurements, not universal latency, maximum capacity, passage-heavy workload or R4/C5/R5 acceptance claims.

A separate strict comparison uses the same transaction, local embedding and fixed access time: twenty questions × three token budgets (2,048/12,000/64,000) × two intents (explore/exact quote). All **120 pairs** match in full ordered documents and complete candidate state. Core data remains unchanged and ports close afterward.

The initial rollback-only SQL prototype compared the same public corpus in ABBA order. Median lexical query time was 37.866/37.994 ms with recomputation and 16.303/16.025 ms with the projection. All outputs matched. This mixed-query, limit-128 component measurement uses an empty target and the default `include_speech=True`; the ordinary host excludes assistant speech and has conversation/branch scope. It is not complete host latency and includes questions with no word channel. Its apparent total-size decrease was heap compaction, not storage savings.

## Upgrade, storage and write cost

Migration 030 rewrites the assertion heap and rebuilds indexes under the migration transaction. It is an exclusive maintenance operation, not an online/no-lock migration. The obsolete expression index is dropped before the rewrite so it is not rebuilt only to be discarded. PostgreSQL's [stored generated text-search guidance](https://www.postgresql.org/docs/16/textsearch-tables.html) describes the read/write-storage tradeoff; the expression fixes the text configuration explicitly.

The cost probe uses ordinary logged tables copied from the public corpus with all indexes/defaults/generated columns. Both clones recreate the old expression index and REINDEX after loading, before comparing sizes; this avoids interpreting GIN pending-list or prior heap bloat differences as projection cost. LIKE does not copy foreign keys or RLS, so these are isolated database cost probes, not application ingestion latency or security tests. Five alternating 1,000-row insert/update transactions are rolled back; all raw samples are retained.

| Assertion rows | Baseline table + indexes + TOAST | Projected table + indexes + TOAST | Migration time | Logical projection bytes |
| --- | --- | --- | --- | --- |
| 10,000 | 41,312,256 bytes | 45,850,624 bytes | 0.447 s | 1,750,616 |
| 50,000 | 196,886,528 bytes | 217,718,784 bytes | 2.570 s | 8,753,080 |

Total assertion-relation storage grows about 11%; this is not total installation growth. Each 1,000-row insert batch has median 72.794 ms baseline versus 79.868 ms projected; text-update batches have medians 41.178 versus 44.643 ms. This includes normal database WAL/index work but no application/network/consolidation steps or commit fsync. The generated column adds roughly 7.1 ms per thousand inserts and 3.5 ms per thousand text updates in this probe. It does not claim zero write cost.

Upgrading the actual retained 10,000-memory profile took 0.731 s. All four core tables matched their prior JSON values after excluding only the newly derived field. The earlier unnormalized clone measurement and prototype are retained as exploratory results; use the normalized comparison above for storage conclusions. Timings are machine/workload-specific and cannot be extrapolated to arbitrarily large stores. Large deployments need a maintenance window and enough temporary disk/WAL headroom for the rewrite.

## Correctness and packaging

- 121 related source tests pass, zero skips (7.38 s); the same 121 tests pass against the extracted wheel (8.15 s).
- All 203 runtime inputs match the wheel byte-for-byte. Wheel/sdist build, Ruff, diff checks and both launcher-pin checks pass.
- Lexical tests compare complete rows and truncation flags across multilingual, rare, oversized and punctuation-containing queries, zero/small limits, conversation/branch scope, foreign owners, historical dependencies, exclusions and null embeddings.
- Migration tests preserve complete prior records, verify row security and the replacement index, reject the future schema with the old runtime, and inject a failure after DDL to verify rollback restores the old records/index/migration marker.
- Historical migration-028 tests explicitly stop at migration 028; all original `xmin`/`ctid` no-rewrite assertions remain. Migration 030 intentionally rewrites the table and has its own preservation/rollback tests.
- Actual content erasure clears the live rows' lexical terms; this is logical database erasure, not a forensic disk-wipe claim. Actual cognitive archive restoration recreates terms equal to the stored text.

[Verify 42464848140](https://github.com/chriswu727/memBrain/actions/runs/42464848140) passes on `8421b0bfd5cc0a6ac24a93e968ffee072109f6f5`: **8,028 Python tests**, zero skips, in **2,451.63 seconds**; **56 TypeScript tests**, zero failures/skips; strict types, Ruff and both package builds. Three existing multiprocessing fork warnings remain.

PR #50 merged into `integration/maturity-candidate` as `782a4fb054eb0eff6eacbc60562e2f38afff7fe9`. Its complete tree `adc045e9ec61a866065bd88b658c37401c30dd26` equals the qualified source tree. The documentation/evidence follow-up changes no runtime, schema, launcher, workflow or test inputs. Main remains unmerged and publication remains frozen. Native JSON evidence normalizes Windows CRLF to LF with JSON-value equality asserted, retaining original archive/member hashes and stored file hashes.

## Retained failures and qualification

The first HTTP comparison did not run recall: `host.start` timed out because the harness selected a baseline with PYTHONPATH while desktop startup deliberately removes that variable. The child loaded the checkout build, and its identity did not match the baseline client. The failed script/log/report remain preserved. Separate installed environments fix the harness; no product source or readiness check was weakened.

Native run 42464847388 encountered upstream HTTP 504 responses downloading OpenSSL on Windows and Intel macOS. Those build failures are retained and do not count as passing qualification. Windows passes the separate retry [42465082081](https://github.com/chriswu727/memBrain/actions/runs/42465082081). Intel macOS passes [42465201213](https://github.com/chriswu727/memBrain/actions/runs/42465201213) with the previous owned run's checksummed native bundle; native build inputs are unchanged from run 42459291814, while all current-source installation/upgrade/restore checks still run. The original run passes Linux x86_64/aarch64 and macOS arm64. All five platforms together provide **47 audited current-source execution summaries**, each completed with zero model calls and successful recorded port closures; five duplicate qualification copies are excluded. The original run remains failed because of its two upstream download failures. Optional Linux compatibility jobs were not selected. Full Verify passes as recorded above.

The initial `gh run view --log` export omitted the full pytest summary, so the evidence parser rejected it. The direct completed-job log includes all 8,028 results and the final summary; it is the authoritative retained log. No test was rerun or weakened to resolve this export issue.

[Evidence](evidence/maturity-stored-lexical-projection-2026-11-08) contains raw samples, reproduction scripts, import identities and check output. No private memory or held-out scenario is included. This optimization does not change or establish personality/emotion quality, behavioral privacy acceptance, or release readiness.

## Next performance target, not shipped

A separate instrumented serial diagnosis of the current wheel finds candidate collection still dominant: median 207.323 ms, including about 90.090 ms in the lexical route; the semantic-pool SQL has median 93.360 ms. Local query embedding has median 2.243 ms. These nested timings include a warmup and instrumentation overhead and must not be added together or substituted for the HTTP measurements above.

The SQL eligibility predicate reads `claim_kind`, derivation method and the statement from each eligible JSON document to exclude assistant speech before applying candidate limits. A rollback-only prototype stores **that exact SQL expression** as a generated boolean, while retaining the original scope/lifecycle filters and candidate algorithm. On twenty public queries, candidate-collection medians in ABBA order are 187.045 / 46.443 / 44.587 / 180.592 ms. Full ordered candidate documents and state match for each query in all phases. The schema change is rolled back and both ports close. No production file or migration includes this prototype. Privacy/null-semantics tests, write/storage/migration costs, HTTP measurements and packaged/native qualification are still required before adopting it; it is the next development target, not a shipped speed claim.

The first diagnostic attempt did not load instrumentation because Homebrew's standard-library `sitecustomize.py` took precedence. Its HTTP results are retained but excluded from diagnostic claims; a checked environment-local `.pth` import enabled the wrappers for the actual diagnostic run. This setup repair did not change application code or the uninstrumented ABBA results.
