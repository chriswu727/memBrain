# Cross-script admission and lexical strength in hybrid recall

Runtime `fc149dff6dbd7ae7e23c9b6bae7f8c64abff20db` combines two independently reproduced hybrid-recall repairs. The first, introduced in `bd10c4e504cffa034634ef1d43a35841c397451d`, repairs overlapping multilingual candidate admission. The other-script route previously removed every record already present anywhere in the global vector pool. A useful record near the back of that pool therefore could not be promoted, while the same record outside the pool could be promoted. The merger now deduplicates records as they are emitted, preserving early global entries and promoting later other-script entries once. Candidate, source, context and permission budgets are unchanged; the vector ranking marker is `script-balanced-v2`.

The second preserves lexical coverage when combining keyword and vector ranks. Previously, dividing by the largest lexical score promoted the strongest weak overlap to full weight even if no candidate matched the question well. In a reproduced host case, incidental character overlap and vector scores accumulated on unrelated records, putting the relevant fourth-ranked vector source at overall position 46. Normalization now uses a minimum denominator of one, so weak coverage stays weak while strong lexical coverage retains its weight. The keyword rank marker is `exact-word-hash-and-source-unit-origin-v5`. Source budgets, ten meaning-only candidates, twelve host messages and the context character limit are unchanged.

## Reproduction and scoped checks

One pure ranking regression and two real PostgreSQL regressions failed on the predecessor. The database cases cover Latin-query/CJK-source and CJK-query/Latin-source directions under a small context budget. The first database fixture invocation failed because its vectors were tuples rather than lists; that fixture error is retained separately from the corrected three ranking assertion failures.

After the first repair, **49 candidate, vector-job and speech-budget tests passed**. The fusion follow-up reproduced two assertion failures while preserving a strong-literal-match control. Its final combined group passes **277 tests**, covering lexical/vector candidates, source passages and neighborhoods, source isolation, rank fusion, plugin context and speech eligibility. Four launcher-pin/architecture guards and full-source Ruff also pass. The first Ruff run identified an import-order issue in the new test; its correction did not change test behavior. The runtime and nine updated launchers are pushed on the isolated development branch. Fresh installed-package qualification is complete below; full candidate CI for this repair remains pending.

## Local model protocol

The predecessor `0c8ea88` was exercised through its actual installed HTTP service, build `ccab88610a3fdabeb8f127a14b140c93d1a43e41d6c0c47f89c6b384d0fb4928`. The existing pinned multilingual-e5-small int8 ONNX files were checked against both published-in-code SHA-256 values and copied into a fresh synthetic installation. No download, paid provider, subscription, generation model or semantic judge was used.

Twenty predeclared public source/query pairs test cross-language phrasing. Their source messages are interleaved throughout the first 1,000 records; the corpus is then extended to 10,000 with synthetic distractors. Ordinary background workers create the text and vector indexes. Each phase waits for no index lag, no pending jobs and one stored vector per message. Queries run once each with semantic and lexical-only recall, alternating order. Every response, miss and timing is retained, including the first query. A hit requires the expected exact source-event reference in the response. This measures retrieval of these artificial facts, not answer correctness, general multilingual quality or held-out R4/C5 behavior.

The first 1,000 records settled after 26.049 seconds from ingestion start. Adding the next 9,000 records and completing both indexes took 560.463 seconds in the second phase. These are observations of this local fixture, not ingestion-rate guarantees.

| Corpus and runtime | Semantic hits | Lexical-only hits | Semantic p95 | Semantic maximum |
| --- | --- | --- | --- | --- |
| 1,000 messages, predecessor | 15/20 | 0/20 | 395.285 ms | 931.605 ms |
| Fresh identical 1,000-message content, repaired | 18/20 | 0/20 | 386.646 ms | 940.651 ms |
| 10,000 messages, predecessor | 17/20 | 0/20 | 320.948 ms | 327.968 ms |
| Same retained 10,000-message corpus, repaired | 17/20 | Not repeated | 481.060 ms | 1,095.990 ms |

The fresh smaller replay uses identical cases, queries, templates and corpus-construction function, checked by comparing their parsed syntax trees. It has new event identities and ingestion times. The larger replay reuses the exact retained corpus and original target event identities. The repaired service configuration matches its source build `b58d3e3c362f17da7c311625ae0217fbe56c0032c6a35eb8b73d0c132666198d`. All runs completed, their frozen script/source hashes remained unchanged, and their service/database ports closed.

There is **no improvement in the 10,000-message hit rate**, and no stable latency speedup is claimed. The repaired larger replay starts a fresh service/model; its first-query cost is retained. The original larger phase followed the smaller phase in an already-running service.

## What the misses establish

Read-only vector diagnostics on the retained corpus explain the nonmonotonic admission behavior. For cases 5, 9 and 11, the target is the closest other-script record. Within the first 1,000 records, its old vector rank is 122, 106 or 145; the repair promotes each to rank 4. In the larger corpus those targets are outside the global scan window, so even the old other-script path already promotes them to rank 4. The fresh smaller replay recovers these three additional targets.

Cases 6 and 12 remain missing in both smaller replays. At 10,000 records their global ranks are 4,725 and 4,469, and their other-script ranks are 1,629 and 2,001. Mixed-script distractors occupy the other-script quota: an otherwise English sentence containing a Chinese place name qualifies for that route. Case 16 is found in the smaller corpus but is rank 142 in both vector lists at 10,000 and remains missing. Promoting overlap cannot recover records absent from the bounded other-script pool. These observations require further retrieval-quality work; they are not evidence that all remaining failures have one cause.

API inclusion also overstates what a chat host necessarily receives. Applying the unchanged host source selector to the retained responses gives **14/20 before and 16/20 after** on 1,000 messages, and **17/20 before and after** on 10,000. This is an offline source-selection check; it does not execute timeline reads, relationship boundary filtering or final context rendering. The full-host comparison below subsequently verified actual timeline reads, trace publication and final context rendering. API inclusion of 18/20 still does not mean the agent receives 18/20.

## Final full-host comparison

The final repair and the original installed `0c8ea88` each ran the actual `host.recall_context` path on both exact retained corpora and the original twenty questions. The client records the real recall response and emitted trace without replacing the API response, timeline, relationship-boundary checks or formatter. Every call is retained; there are no warmups, retries, changed questions or larger budgets. Each corpus starts a fresh service. The original installed arm ran after the repaired arm, so the timings are not a randomized speed comparison.

| Corpus and runtime | API target references | Host source selection | Final trace and context | Full-context p95 | Maximum |
| --- | --- | --- | --- | --- | --- |
| 1,000, original installed `0c8ea88` | 15/20 | 14/20 | 14/20 | 394.354 ms | 1,020.417 ms |
| 1,000, final `fc149df` | 18/20 | 17/20 | 17/20 | 395.096 ms | 993.072 ms |
| 10,000, original installed `0c8ea88` | 17/20 | 17/20 | 17/20 | 488.639 ms | 1,066.746 ms |
| 10,000, final `fc149df` | 17/20 | 17/20 | 17/20 | 504.343 ms | 1,229.560 ms |

On the same 1,000-message fixture, the first repair alone delivered 16/20 final contexts; preserving lexical strength recovers one additional case. The final source build is `6be440c1b4ff0f5b8962f0e07f91e337815a09df429db659461d9f9454a45ce2`. Both sources' hashes remain unchanged, service configurations match their source, and all ports close. Final trace membership agrees with the target's actual text in the context. This verifies an improvement from 14 to 17 retrieved facts delivered to the host on this public small fixture; it does not measure generated answers, independent behavioral acceptance or a general recall success rate.

The 10,000-message result remains 17/20. Cases 6, 12 and 16 are still absent from the final context at both sizes. Their low vector admission/ranking is not repaired by either change. Increasing output limits or relabeling API-only matches as successful host memory was not used to claim improvement.

These diagnostics are public engineering probes. They neither expose the sealed behavioral scenarios nor establish why the prior R4 attempt failed. R4 remains failed, C5 incomplete, and any new paid/subscription acceptance needs separate authorization. Main merge, tagging and release remain frozen.

## Exact-runtime installation and fullscreen qualification

Fresh installation, upgrade, restart, MCP, proxy, companion preservation and backup/restore pass **49/49 checks**. Both installed homes match all **187 runtime inputs** of `fc149df`, build `6be440c1b4ff0f5b8962f0e07f91e337815a09df429db659461d9f9454a45ce2`. Schema identity is unchanged. The interpreter bound to the actual installed package passes **112 tests** covering both new regressions, candidates, lexical recall, plugin context and matrix boundaries. Its temporary database stops and profile is removed; four installer profiles and all eight ports close.

The unchanged closed/open/open/closed R5 protocol passes **36/36 windows**, with **4,080 nonempty measured recalls**. Worst window p95 is **422.79 ms serial, 317.04 ms for eight workers on one brain and 546.25 ms for eight brains**, below 500/1,000/600 ms. It uses the retained keyword fixture, three cycles per phase, fresh service per phase and normal polling. This establishes reference-fixture overhead, not semantic-model capacity or a speedup.

Both visible open phases match 187 nodes and 71 edges against the structural API. Chromium 153.0.8010.12 uses Apple M4 Metal rendering; animation advances 1,046 and 1,088 frames. Neither phase reports page errors or external requests.

Source and driver hashes are unchanged and all ports close. [The evidence manifest](evidence/maturity-semantic-balance-2026-11-07/manifest.json) retains baseline failures, all public-model misses, host contexts, installation checks, raw measurements and predecessor CI in 160 hashed payloads. Every archived payload decompresses to its original bytes; scanning found zero owned-profile credential matches.

## Current candidate CI follow-up

Candidate `badc404` subsequently failed [Verify 42359121591](https://github.com/chriswu727/memBrain/actions/runs/42359121591): 7,710 Python tests passed, one absolute-first ranking assertion failed, and three warnings were reported. TypeScript and build steps were skipped. Its [native run](https://github.com/chriswu727/memBrain/actions/runs/42359121592) passes all five platforms and 47 audited summaries. The paired diagnostic evidence and development test correction are recorded in the [long-passage follow-up](maturity-long-passages-2026-11-07.md); the failed candidate run is not relabeled as successful.

## Predecessor CI and delivery status

Candidate `9c80bbd`, runtime `0c8ea88`, completed [Verify 42355778548](https://github.com/chriswu727/memBrain/actions/runs/42355778548): **7,705 Python tests**, three fork-related deprecation warnings, **51 TypeScript tests**, strict types, Ruff and builds pass. [Native 42355778384](https://github.com/chriswu727/memBrain/actions/runs/42355778384) passes all five platforms; 47 distinct summaries report completed checks, zero model calls and all recorded ports closed. Complete raw Verify logs and their hashes are archived. These passes belong to the predecessor; the current candidate failure is recorded above. R4/C5 and final review remain open, so no main merge, tag or release is authorized.
