# Source diversity and host admission

Repeated numeric-template memories could occupy the supplemental semantic pool, while multiple fragments from one source event could consume the host's vector-only admission slots. This follow-up addresses both problems on top of the [source-script projection experiment](maturity-source-script-2026-11-07.md). That report and its failed results remain unchanged. The current public development checks pass; installation qualification and full CI are still pending. No main merge or release is implied.

## Behavior

Semantic ranking keeps two early representatives of an exact numeric template before admitting independent records. Numeric sequences become typed slots; all other wording, negation, names, speaker/act envelope, world, claim kind and derivation remain distinct. This is ranking only: no source or assertion is merged or deleted. Text beyond 2,048 characters bypasses grouping. The supplemental search examines at most the existing scan budget (maximum 512), then retains its existing 16 candidates. Exact-quote, timeline and episode intents bypass diversification; lexical matching and the final candidate/context budgets are unchanged.

Host context admission now counts independent source event IDs, not fragments. Current-conversation and hidden/uninformative items are filtered before allocating the ten vector-only source slots. Sources already admitted through positive keyword evidence do not consume those slots. A vector-only source uses its strongest matching fragment. The message and context limits remain 12 and 9,000 characters; fallback rendering also respects `do_not_surface`.

A fuzzy-overlap prototype was rejected after tests showed that it deferred a negated account and a differently named person. Its two failures are retained. The shipped implementation uses exact numeric templates, not fuzzy semantic deduplication. This limited heuristic can still defer distinct numeric details; explicit-number retrieval has a lexical regression guard, and wider generalization is not established by these public cases.

## Evidence

The focused database/host group passes **163 tests**, and source-window, attribution and mood/relationship privacy checks pass **110 tests**. Earlier interference and four host-admission failures are preserved. The historical projection report separately records its 107 database checks and nine real local-model passage checks.

The unchanged public 1,000/10,000-source corpora were replayed through the ordinary HTTP service, the cached pinned ONNX model and complete `host.recall_context`. Each original question was asked once, without query warmups or retries. Original source/assertion documents and complete vector hashes match before and after. All service/database ports closed, and runtime files remained unchanged during measurement.

| Stored sources | API / final host hits | Median | P95 | Maximum |
| --- | --- | --- | --- | --- |
| 1,000 | 20/20 / 20/20 | 297.934 ms | 472.737 ms | 1,173.215 ms |
| 10,000 | 20/20 / 20/20 | 371.711 ms | 557.796 ms | 1,228.849 ms |

This recovers all prior public misses, including the case-3 regression from the projection-only experiment. Ordered single-run timings are descriptive, not a statistically established speedup.

A separate 10,000-source capacity probe used a fresh service, one recorded warmup per client, then the same 20 public questions per client. Eight clients rotated question order to avoid identical simultaneous requests. The existing five-second host budget was unchanged. Every measured request and warmup used one actual semantic recall without fallback; all expected sources reached context.

| Clients on one brain | Measured hits | Median | P95 | Maximum |
| --- | --- | --- | --- | --- |
| 1 | 20/20 | 362.881 ms | 540.741 ms | 541.591 ms |
| 8 | 160/160 | 1,676.405 ms | 2,086.856 ms | 2,295.151 ms |

There were no warmup errors. Core hashes and source files remained unchanged, and all ports closed. The concurrency result demonstrates contention that still matters for multi-agent use; it is not a capacity ceiling or formal R5 acceptance. No generation, paid provider or subscription calls were made. These public fixtures have been used for development and do not replace the frozen, failed/incomplete R4/C5 acceptance.

Runtime build: `83b6553be9ad09b4d5c54ba3d981de7d7223d03b72ee1f28bafe66107f0be1b6`. Schema 028: `478061ac77337fd25d87174df1185ab1d40ad4d4216290078fb26fd2f519fe39`. Raw responses, failures and harnesses are checksummed in [the evidence manifest](evidence/maturity-recall-diversity-2026-11-07/manifest.json); private profiles and corpus dumps are excluded.
