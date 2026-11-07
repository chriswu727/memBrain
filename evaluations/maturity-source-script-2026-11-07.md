# Source-script admission experiment: not promoted

This development experiment fixes an identified candidate-partition error, but **does not yet meet the public end-to-end regression bar**. Keep the delivered launchers on the separately qualified cache runtime. No main merge, release or fresh paid/subscription acceptance is authorized by these results.

## Identified defect and rejected alternatives

The previous supplemental vector pool treats any Han character as evidence that a whole statement belongs to that script. English receipts containing a Chinese place name consequently occupy the pool intended to recover Chinese memories for an English question. On the unchanged public 1,000-message database, the original passport and visitor-boundary targets rank 152 and 200 within that pool. Classifying the alphabetic characters in the actual source instead of the capture envelope moves them to ranks 1 and 3. Their stored vectors and original questions are unchanged. The Spanish keyring question remains a separate interference problem: its target ranks 25 behind similar photo-sorting records.

An offline comparison also tried encoding raw source text instead of role-wrapped statements with the same pinned ONNX model. Top-12 vector hits fell from 9/20 to 7/20. This alternative was rejected; the runtime retains its original vectors and encoding.

The first source-script implementation calculated the classification inside each query. It improved API admission but made the 10,000-message complete-host P95 approximately 982 ms. That run, its script and all responses are retained. It was not promoted.

## Current implementation

The supplemental pool uses a majority of alphabetic source characters, excluding the speaker/act envelope of a direct capture using its original source-span length. This is a bounded script-partition heuristic, not language identification or semantic understanding. The global candidate pool, supplemental pool size, embedding model and host budgets remain unchanged.

Migration 028 adds a nullable `source_han_majority` projection and an index of pending current records. Publication computes the projection once. Each idle worker pass fills at most 256 missing projections under the existing shared brain lock and a nonblocking projection lock; each batch commits atomically. New writes do not wait for historical backfill. Erasure clears the projection. Original assertion documents, source events and vectors remain unchanged. The actual migration test preserves row `xmin` and `ctid`, demonstrating that adding this projection does not rewrite the assertion heap.

Until a legacy row is indexed, a SQL fallback computes the same classification. PostgreSQL's POSIX alphabetic class failed parity on this machine's database locale. The fallback therefore uses explicit cached Unicode letter ranges matching Python and the database's `C` collation. It is short-circuited for indexed rows. This avoids repeating the expensive calculation after ordinary background catch-up, without silently excluding unindexed memories.

## Verification and remaining regression

The final database group passes **107 tests**, including source/metadata separation, mixed-script names, Greek/Cyrillic/accented text, migration, interrupted batch rollback, bounded background progress, cross-owner isolation, suppressed-source exclusion, cache behavior and recovery. **Nine cached local-model passage tests pass** separately. Ruff over all source/tests and diff checks pass.

Retained earlier outcomes:

- Three new candidate tests failed on the previous implementation while three existing tests passed. One query fixture was separated from incidental lexical overlap; all three failure cases still reproduced before the fix.
- POSIX alphabetic classification: six failed, 71 passed and nine optional model tests skipped. Explicit Unicode ranges corrected the mismatch; the next selected group passed 77 tests.
- The final broader invocation passed 107 database tests but had nine model-fixture setup errors because its environment named the model directory instead of the installation root. Only those nine affected tests were rerun with the correct root and passed in 7.24 seconds. The failed invocation remains in the evidence.
- An import-order lint failure was corrected; the final complete source/test lint passes.

The ordinary service upgrades and indexes the same public 1,000/10,000-message installations. After the normal worker finishes the new projection, each original question is asked once through `host.recall_context`, with unchanged budgets and no generation, retries or query warmups. Source/assertion documents and complete stored-vector hashes match before and after; all ports close.

| Corpus | Previous API / final host hits | Current API / final host hits | Current median / P95 |
| --- | --- | --- | --- |
| 1,000 messages | 18/20 / 17/20 | 20/20 / 18/20 | 293.960 / 472.901 ms |
| 10,000 messages | 17/20 / 17/20 | 19/20 / 17/20 | 368.738 / 540.438 ms |

The 10,000-message query-time implementation measured 796.317/982.077 ms; the persisted projection removes most of that observed overhead. These ordered single-run timings are descriptive, not a statistically established speedup over the previous delivered runtime. Background indexing time is recorded separately in the raw report.

At 1,000 messages, cases 12 and 16 still fail final host inclusion. At 10,000 messages, cases **3**, 12 and 16 fail: case 6 is recovered, but case 3 previously succeeded and is now excluded by the host's top-ten vector-only cutoff. The aggregate 17/20 therefore hides a regression. This build remains on its development branch, with no new installation pin or claim of release qualification.

Further work must address competition among highly similar source records and final context selection while retaining exact-query evidence, attribution, privacy and existing budgets. Increasing the result limit or tuning fixture-specific words would not establish that behavior. These public cases have been used for debugging; they do not replace the frozen R4/C5 acceptance, which remains failed/incomplete.

The accompanying manifest retains both complete public replays, failures and scripts. The raw diagnostic field `provider_calls: 0` counts external providers; those exploratory scripts explicitly use the cached local ONNX model. No paid provider, subscription call, protected evaluation corpus or private credential file was used.
