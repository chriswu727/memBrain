# Long-source recall and bounded local encoding

Development build `80dec3b1782ede0349ceafe436f481ed8fb7ea16957bd62f435c74cdd9fe011a` adds overlapping local passage vectors while preserving the original assertion, source evidence and parent vector. Migration 026 adds private auxiliary index rows and an index-coverage version. Fresh installed-package qualification passes below, including installed HTTP, full R5 and public scale checks, but full CI remains open; this work is not yet delivered to the integration candidate. The nine development launchers pin runtime `3b4720ec3f6cde49b672ff6844f8bc8db02dfce9`.

## User-visible defect and repair

The previous local embedding model only encoded the first 512 tokens. Two long statements with identical beginnings but different passport locations at their ends produced exactly identical parent vectors. The repair indexes bounded overlapping original spans, then admits each parent only once. It neither manufactures separate facts nor adds artificial nodes to the memory graph.

Indexing alone was insufficient: the first full-service/host probe found the target and emitted its trace for a 28,045-character source, but the final context omitted its tail because the timeline response stopped at 20,000 characters. That failed probe is retained. The host now requests a fresh, bounded original-source window using the exact memory version. The endpoint checks the entire source against relationship boundaries before cropping, plus source revision/hash, scope, current parent and corrections. Failed fresh reads drop old timeline copies. Partial excerpts keep world and speech-act labels, and the original assertion remains available in the raw result.

The final cached-model probe delivers the passport location in the final host context for sources of **3,965, 28,045 and 47,645 characters**. All three exact source references also appear in the trace. This uses a real PostgreSQL database, the checksum-verified cached E5-small ONNX model and in-process service/host calls. It is not a complete external-network journey or a generated-answer evaluation. The earlier repaired run's full JSON was overwritten by its later replay before unique filenames were introduced; its log remains. The original failing JSON and final uniquely named bounded-batch result are preserved.

## Encoding resource regression found and fixed

The first passage implementation mixed the 512-token parent head with short passage windows in one inference batch. Padding every short passage to the head's width unnecessarily increased work and memory. Separate head/passage groups and batch limits based on padded width now prevent that multiplication. Input text, coverage, passage counts and unpadded token counts are identical across this comparison.

Each arm starts a new process on the same Apple M4 Mac, verifies cached model hashes and encodes the same ordered five texts once. The short first case includes model loading; subsequent cases use the loaded model. Memory is cumulative process peak RSS, including file verification and model loading, not an isolated tensor allocation or whole-system memory reading.

| Source characters | Passage vectors | Encoding before | Encoding after |
| --- | --- | --- | --- |
| 34 | 0 | 0.522 s | 0.519 s |
| 3,996 | 13 | 1.043 s | 0.125 s |
| 27,996 | 88 | 2.921 s | 0.535 s |
| 47,996 | 150 | 3.290 s | 0.866 s |
| 65,496 | 205 | 3.408 s | 1.174 s |

Peak RSS across the sequence falls from **3,088,138,240 to 1,026,555,904 bytes**. These are single-run component observations, not repeated statistical estimates, cross-device guarantees or user-facing query latency. Batch limits are 32 rows, 4,096 padded tokens and 1,048,576 attention positions. A maximum-length input regression checks those bounds and complete source coverage without running thousands of redundant model inferences.

## Migration, recovery and candidate cardinality

The actual migrations 001 through 025 are applied in a disposable schema before upgrading to the current migration set. Original embedding fields are unchanged, the new coverage marker defaults to the legacy version, repeat migration is harmless, RLS is forced, and an old migration set refuses downgrade. The migration/schema/backup transport group passes **45 tests**.

A real streamed desktop backup starts with 26 passage rows. One of the two source memories is erased after the backup. Restoring the earlier snapshot first enters quarantine, then explicit activation reconciles the current deletion registry: exactly 13 retained passage rows survive byte-for-byte, the other 13 do not resurrect, and the retained tail reaches the host. All owned ports close and temporary profiles/dumps are removed. This probe predates only the inference batching change; its exact build is recorded in its receipt. No provider was called: it uses deterministic test vectors.

A PostgreSQL regression gives one parent 100 near-identical passage hits. It still occupies one candidate slot and the second matching parent remains admitted. Further tests cover erasure during encoding, atomic publication, invalid vectors/coverage, backfill identities, source changes, privacy outside the cropped window, world/act labels and malformed fresh reads.

## Preliminary database cost

A disposable synthetic fixture contains 10,001 assertions with 384-dimensional vectors; they deliberately share one source and do not represent a realistic semantic corpus. Each phase measures 12 alternating old/new candidate-collection calls after two warmups. This measures candidate collection inside one database transaction, not full HTTP, model encoding, host formatting or concurrent workload.

| Fixture | New-path median | New-path maximum | Passage table and indexes |
| --- | --- | --- | --- |
| No passage rows | 162.08 ms | 167.46 ms | 16,384 bytes |
| 1,000 parents with eight passages each | 174.50 ms | 181.89 ms | 18,251,776 bytes |

The parent vector table and indexes occupy 21,987,328 bytes. The older path medians are 180.70 and 187.81 ms, but one old-path sample takes 8,824.47 ms. No query-plan/statistics evidence was captured to explain that outlier, so **no retrieval speedup is claimed**. Initial probe invocations failed because the test import path was absent and a fixture referenced a nonexistent column; both logs remain. Subsequent installed public scale and fullscreen R5 checks are recorded below; the synthetic timing comparison remains limited.

## Verification and remaining gates

The final bounded-encoding build passes **508 related Python tests**, including the real-model tail probe, migration, candidate cardinality, source boundaries, recovery, archive and native contract checks. The TypeScript suite passes **53 tests**, including Unicode projection parity and scoped window requests; strict types, Ruff and diff checks pass. Earlier failures are preserved: invalid HTTP fixture hostname, legacy TypeScript records missing optional derivation metadata, test import/fixture errors, and the original host-tail omission.

Candidate `badc404`, still the delivered integration head, failed [Verify 42359121591](https://github.com/chriswu727/memBrain/actions/runs/42359121591): **7,710 passed, one failed, three warnings**; subsequent TypeScript/build steps were skipped. The failure is an absolute-first ordering assertion. Twenty-four paired diagnostics show the old and new SQL paths retain identical roots; a separate 24-case counterfactual confirms the pre-fusion defect excludes the target every time. The development regression therefore checks bounded admission plus vector support, while the pure ranking test still checks weak-versus-strong lexical weighting. This is a supported test-contract correction, not a claim that the current candidate CI passed. Its native run passes all five platforms and 47 audited summaries.

## Exact installed package

Fresh launcher installation and upgrade, MCP, proxy, restart, companion-state preservation and streamed backup/restore pass **49/49 checks**. Both installed homes match all **192 runtime inputs**, build `80dec3b...` and schema `2d5ed57efb283d0e9a28fba22777ef7bae452a5843d07cce8cde0e7e9fe6826e`. Four profiles and all eight ports close. The actual installed package, resolved before test-only dependencies and without source shadowing, passes **171 related tests**. Its disposable test database stops and is removed. Four launcher-pin/matrix checks pass.

Development head `bc449e04163fd017ac33cd095274527798da2dce` is still running [Verify 42363211463](https://github.com/chriswu727/memBrain/actions/runs/42363211463). [Native 42363213186](https://github.com/chriswu727/memBrain/actions/runs/42363213186) passes all five platforms, including current Ubuntu. Its downloaded artifacts contain 47 audited completed summaries, zero model calls and closed recorded ports. Native checks reuse the verified previous engine artifacts. Pending Verify is not a pass.

The [evidence manifest](evidence/maturity-long-passages-2026-11-07/manifest.json) now records 177 raw payloads, including interrupted preparation attempts. Every archived payload matches its recorded hash and bytes; the added qualification payloads contain zero matches against 21 owned credential values. Private corpus dumps and profiles are excluded. Full CI must still precede integration delivery. R4 remains failed and C5 incomplete. No new paid/subscription behavioral evaluation ran; no main merge, tag or release is authorized.


## Installed HTTP and full host scale qualification

The actual installed `3b4720e` runtime, with a checksum-verified cached model and a fresh temporary database, delivers the final passport detail through ordinary HTTP and `host.recall_context` for sources of 3,965, 28,045 and 47,645 characters. All exact source references appear in the trace and host output stays within its existing 9,000-character ceiling. Deleting each source makes its previously valid source-window request return no windows. A separate source with a privacy boundary phrase outside the final cropped excerpt is correctly excluded by the server's whole-source check, even when the host supplies an empty boundary list. All owned ports close and the temporary installation is removed.

The same original 1,000- and 10,000-message public corpora were preserved before additive schema 026 upgrade. Core table contents were checked with bounded streaming hashes; operational request/trace tables were verified by exact counts. Private compressed corpus snapshots exclude operational history and are not product recovery bundles. After migration, all existing vectors retain their legacy coverage marker. The normal service then backfills the new coverage version in 12.634 and 110.665 seconds respectively; all 1,000/10,000 vectors are current and jobs have settled before querying.

The original twenty questions, exact source identities, host budgets and complete host path are unchanged. Each query runs once, with no warmups, retries, generation or semantic judge. Each corpus starts a fresh service.

| Corpus | API target | Host source selection | Final trace and context | Full-context P95 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 messages | 18/20 | 17/20 | 17/20 | 432.867 ms | 1,122.672 ms |
| 10,000 messages | 17/20 | 17/20 | 17/20 | 502.528 ms | 1,138.801 ms |

These retain the previous `fc149df` hit counts; the three previously missing host cases remain missing. The passage repair addresses long-source truncation, not those separate admission failures. Source hashes remain unchanged and all ports close. Timings are descriptive single-run observations, not a statistically established speedup or general accuracy claim.

## Fullscreen R5 and storage findings

The frozen driver runs the installed package with the original synthetic fixture in closed/open/open/closed order, three cycles per phase. All **36 windows pass**, and all **4,080 recalls are nonempty**. Worst-window P95 is **255.07 ms serial, 334.14 ms for eight concurrent requests to one brain, and 419.86 ms for eight brains**. Both visible phases contain exactly **187 stored-structure nodes and 71 edges**, with 991 and 1,037 rendered frames, no page errors and no page external requests. Chromium 153.0.8010.12 reports Apple M4 Metal hardware rendering. Source/driver hashes remain unchanged; all ports close. Browser-internal stderr warnings are retained and are not counted as page errors.

Two fixture-preparation attempts were interrupted and preserved: the first materialized large operational payloads in client memory, and the second streamed them unnecessarily and assumed no legacy vectors. Neither reached migration. The corrected preparation hashes the 24 core tables, counts the two operational tables, preserves all 60 legacy vectors and existing working nodes/edges, then upgrades successfully. Its private corpus snapshot excludes operational history; all original operational rows remain in the database.

The read-only storage audit exposed millions of duplicate candidate diagnostics and unbounded recall response caching. That led to the separately tested [passive diagnostic storage repair](maturity-recall-diagnostics-2026-11-07.md); its runtime is **not** the `3b4720e` installed runtime measured here. Eight stopped, already-qualified old temporary installation profile directories were removed after receipt and port checks, freeing about 2.1 GB. Installed packages, source, evidence, current installations, public corpora and sealed evaluation data were retained.
