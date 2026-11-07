# Exact semantic recall with shared distance computation

Runtime `cebc6d829536fb2ab45e92a5d16ecc67e8d14597` computes eligible vector and passage distances once for the global and cross-script candidate pools. Each pool retains its independent limit, overflow sentinel, distance/ID ordering, visibility and scope filtering, best-passage selection, content-hash validation and subsequent diversification. Full documents are loaded only for selected candidates. This removes duplicate exact-distance work without changing recall policy or introducing approximate nearest-neighbor retrieval.

Candidate build: `5f8ad59f4ef931f000b1c2531eb0f735262823e550fd825bffb206d9336fc11e`. Schema remains `478061ac77337fd25d87174df1185ab1d40ad4d4216290078fb26fd2f519fe39`. All nine launchers pin this runtime in `06d97a830b352abf0598ca391682cb0af6edb791`. Baseline is integration `a72205640f49dd6fcb1840c903f2bbec4a9594cc`, build `483d6508d9e4b873e88a6aac413b49115ba134588d962b431e9c4b72235ea6a3`.

## Measured behavior

The same retained public synthetic corpus contains 10,000 source events, 10,000 assertions and 10,000 whole-memory embeddings; it contains no passage embeddings. Actual cached local ONNX query embeddings and the ordinary host context path were used, without generation, provider calls or subscription calls. Twenty existing questions were run serially and with eight simultaneous clients sharing one brain. Each client had one explicit warmup, followed by twenty measured questions. The existing 5,000 ms host budget was unchanged.

An initial instrumented diagnosis identified two repeated semantic SQL queries as substantial work; local query embedding had a 3.6 ms p95 in that mixed workload. The table below uses **uninstrumented** service processes and only client-side timing, in baseline/candidate/candidate/baseline order. Every phase starts a fresh service.

| Phase | Serial median / p95 | Eight-client median / p95 | Expected hits |
| --- | --- | --- | --- |
| Baseline 1 | 389.481 / 590.048 ms | 1,161.841 / 1,464.204 ms | 180/180 |
| Candidate 1 | 322.063 / 505.953 ms | 880.327 / 1,015.953 ms | 180/180 |
| Candidate 2 | 318.385 / 509.530 ms | 895.097 / 983.372 ms | 180/180 |
| Baseline 2 | 389.072 / 575.860 ms | 1,191.879 / 1,307.394 ms | 180/180 |

All 720 measured requests and 36 warmups hit the expected source and used one actual semantic recall without fallback. Each phase preserved the four core tables byte-for-byte at the JSON snapshot level, preserved source hashes, and closed its owned ports. These results establish an improvement on this machine and corpus, not a universal latency guarantee, maximum capacity, or passage-heavy performance result. Services restarted between phases; operating-system and database caches were not flushed.

A separate strict baseline/candidate comparison covered twenty queries, token budgets 2,048/12,000/64,000 and explore/exact-quote intents: **120/120 pairs were equal**, including full ordered candidate documents and complete candidate state. Both implementations used the same transaction, embedding and fixed access time. Core tables remained unchanged and ports closed afterward. Dedicated database tests cover best-passage selection, distance ties, independent limits, English/Chinese queries and projected/legacy script metadata.

## Verification and limits

- Source: 118 related tests passed, zero skips; Ruff and diff checks passed.
- Installed wheel, imported from its isolated environment outside the checkout: the same 118 tests passed, zero skips. The first copied-test invocation failed during collection because three fixture imports were absent; the complete fixture dependency closure was copied and that setup failure is preserved alongside the successful run. No product source change was needed.
- Installation pins: both consistency tests passed. Wheel build succeeded.
- [PR 45](https://github.com/chriswu727/memBrain/pull/45) targets the maturity integration branch. [Verify 42421334797](https://github.com/chriswu727/memBrain/actions/runs/42421334797) passed on `06d97a8`: 7,881 Python tests, zero skips, 53 TypeScript tests, strict types, Ruff and both package builds. Three existing multiprocessing fork warnings remain recorded. The complete Python suite took 2,538.68 seconds; this CI runtime is separate from recall latency. PR 45 merged into integration as `29656d2`; runtime, tests, launchers, schemas and CI definitions match the qualified source.

The [evidence manifest](evidence/maturity-shared-semantic-pools-2026-11-07/manifest.json) binds compressed raw reports, timing samples, checks and reproduction scripts. The retained synthetic corpus is the previously established public corpus; scripts refer to its local installation path. No held-out acceptance scenario or private profile is included.

This change does not alter the frozen fifth-attempt checkout or claim its behavioral results for the new runtime. Main merge and publication remain blocked by outstanding behavioral acceptance. The next performance target is lexical candidate preparation, which remains substantial in the instrumented profile; no lexical optimization is included here. A read-only plan diagnostic on the same corpus confirms that the sampled eight-term Spanish query materializes all 10,000 eligible rows and does not use the existing lexical GIN index (111.202 ms in that isolated EXPLAIN ANALYZE). The separate sampled hash-only query intentionally has no word channel and does not establish an index defect. These two plan observations are diagnostic, not another speed benchmark; owned ports closed afterward.

A follow-up read-only SQL prototype joined each term against the indexed assertion relation instead of reusing materialized lexemes. All 160 ABBA calls retained equal lexical outputs, but the actual word-channel medians regressed from 116.985 to 244.214 ms at limit 128 and from 128.888 to 250.387 ms at limit 512. This prototype was **rejected** and never changed runtime source. Its script, raw samples and closed-port result remain in the archive. The initial console summary incorrectly selected query types by case index; the corrected summary selects cases whose SQL actually used the word channel and preserves the initial output. Lack of GIN use alone is not evidence that forcing this join improves recall.
