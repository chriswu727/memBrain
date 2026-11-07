# Bounded read-response caching and legacy diagnostic cleanup

Qualified runtime `493a14ffd98cd9b4a7e3cdc491852ad4898ee3d0`, build `0e0b3dc63848cfa5e14226f4009f683ec1b165f400c3ac73144d5ff449dc6b1c` bounds the complete response bodies retained by repeated read-only requests. The previously delivered long-source runtime remains a separate qualification. The cache changes have completed engineering qualification for integration; the independent release acceptance gates remain open.

## Behavior

`recall` and `inspect` share one private cache per brain: at most **128 responses**, **16 MiB of JSON-encoded content** and **24 hours**. Publication is serialized only at the end of the read transaction; scoring remains concurrent. Responses larger than the byte ceiling are returned without caching. Request fingerprints persist independently. A retained replay returns the original response; an expired, evicted, oversized or legacy replay returns `version_conflict` without executing recall again. Changing the original request content still produces `idempotency_conflict`.

Actual source changes and erasure clear the cache under the existing brain lock. Prepare receipts, actual selections and external feedback keep their existing lifecycle. Restored caches and maintenance cursors are cleared during quarantine, before activation. Private tables have forced row-level security and owner/brain foreign keys.

Migration 027 creates empty tables without updating millions of old rows. Each idle worker pass scans at most 256 old read receipts and 256 old trace rows using durable ordered cursors, clears legacy read-response bodies and deletes only `candidate_hit` diagnostics. Cursor progress and removal commit together. A nonblocking cache lock, a one-second statement timeout and a short lock timeout bound maintenance. Actual selections, quotations, external feedback and original memory content remain. The desktop worker runs this automatically; self-managed deployments need their worker running.

These are **live response-payload limits**, not a whole-database or filesystem quota. Minimal request fingerprints, real memory history and indexes still grow. PostgreSQL vacuuming reclaims or reuses dead-row space asynchronously. This implementation does not rewrite the entire historical database or run `VACUUM FULL`.

## Local verification

The final group passes **214 tests in 41.56 seconds**, covering serial/eight-thread bounds, shared recall/inspect limits, independent brains, exact retained replays, expired-key conflicts, oversized responses, source erasure, owner/tenant isolation, interrupted cleanup rollback, migration without legacy rewrites, old-reader refusal, actual feedback, prepared selections, process transactions and recovery. Ruff over all source/tests and diff checks pass.

Earlier outcomes are retained:

- First run: 126 passed, one shared-read audit failure. The audit now explicitly recognizes narrowly scoped cache and maintenance writes; maintenance publication uses the same per-brain lock and bounded queries.
- One invocation named a nonexistent recovery test file and exited during collection; no tests ran.
- Broader run: 212 passed, one quarantine fixture failure. That fixture relied on recall automatically creating historical candidate rows, which the preceding storage repair intentionally stopped. It now explicitly seeds a legacy snapshot trace and still verifies quarantine removes it. The corrected group first passed 213 tests; one additional combined-action/isolation case brings the final group to 214.
- Predecessor `99dadac` [Verify 42365805952](https://github.com/chriswu727/memBrain/actions/runs/42365805952) failed the same quarantine fixture: **7,758 passed, one failed, three warnings**. Subsequent TypeScript/build steps were skipped. Its raw job/pytest logs are retained; it is not described as green.

## Same-corpus HTTP storage measurement

A temporary installation receives 32 original messages. The predecessor `f668705` runs 2,000 ordinary HTTP recalls, then stops. The new service performs the ordinary schema upgrade and runs on the same source identities and contents, with normal background maintenance. No embedding, generation, paid provider or subscription is used.

The first new-runtime probe reached 250 successful recalls but failed while saving its report because PostgreSQL `sum(bigint)` returned a Python `Decimal`. Its script, logs, incomplete report and a separate read-only failure-state audit remain. All ports were confirmed closed. The corrected probe starts a fresh service with that existing cache/history and runs another 2,000 requests; this is not a pristine randomized latency comparison.

| State after each completed 2,000-request arm | Predecessor | New runtime |
| --- | ---: | ---: |
| Live original read-response bodies | 2,000 | 0 |
| New bounded response-cache rows | Not present | 110 |
| JSON-encoded cached response bytes | Not recorded | 16,694,168 |
| Live request-row bytes, including fingerprints | 47,479,956 | 1,074,088 |
| Live new cache-row bytes | Not present | 2,604,888 |
| Median HTTP latency | 20.601 ms | 21.401 ms |
| P95 HTTP latency | 21.713 ms | 22.339 ms |

The new request table contains 4,282 rows, including the first arm, the interrupted 250-call arm, the final arm and original observations. Every 250-query snapshot stays under both limits. All original event/assertion content hashes and the hash of the 2,000 returned parent-ID sets match across completed arms. The service/source hashes remain unchanged and all ports close. These timings describe this small lexical fixture, not general semantic recall performance or a statistically established improvement.

## Sustained allocation and vacuuming

A further **6,000 HTTP recalls** use the same sources with no manual vacuum or maintenance override. Every snapshot retains 110 responses under the 16 MiB encoded-content limit. Median/P95 latency is 21.564/22.310 ms. All original event and assertion hashes remain unchanged.

Physical relation size does not immediately follow live payload size. During this phase the response-cache relation, including indexes and dead/free space, rises to approximately 113 MB, then falls to **63,234,048 bytes** after ordinary autovacuum. The final live cache rows occupy **2,604,344 bytes** and encode **16,694,213 bytes**. Raw PostgreSQL vacuum counters/timestamps are retained. This demonstrates bounded live payload and observed reuse/reclamation over this run; it does not establish an absolute filesystem bound for arbitrary throughput or long transactions.

## Streamed recovery

The first actual backup probe backed up 110 cache rows, verified quarantine clearing and source-erasure replay, then failed at the HTTP check: its manually constructed client omitted the restored installation's recovery epoch. The 409 response body was not retained, so that failed run is not counted as a complete recovery pass.

The corrected independent probe uses the ordinary `open_client` helper. It backs up eight cached responses, erases one source after the checkpoint, restores into quarantine and activates explicitly. Both cache and cleanup-cursor tables are empty before activation; event rows exactly match the post-erasure source state. A client without recovery acknowledgement is explicitly checked and receives `recovery_acknowledgement_required`. The acknowledged client's old read key receives `version_conflict`, while a fresh HTTP recall succeeds without the erased source. The dump and temporary profiles are removed, all owned ports close, and no model calls occur.

## Installed and concurrent qualification

The exact pinned runtime passes the frozen **49-check** fresh installation, upgrade, MCP/proxy, restart, companion-state preservation and backup/restore journey. Both installed homes match all **194 runtime inputs**. Another **117 tests pass against the installed package** in 26.57 seconds. All four installation profiles' ports are closed. The preceding completed synthetic installation profiles were removed after checking ownership and closed ports, freeing approximately 1.07 GB; package environments, models, source and evidence remain.

The retained public R5 installation upgrades from schema 026 to 027. Twenty-five core tables are hashed before and after and remain unchanged; request/trace counts are also unchanged by migration. A private corpus dump is preserved separately, excluding operational request and trace payloads. It is not a product recovery bundle.

The exact installed runtime then passes all **36 concurrent/visual windows**, with **4,080 nonempty recalls**. Worst-window P95 is **240.87 ms serial**, **296.02 ms for eight readers of one brain**, and **337.05 ms for eight brains**. Both visible 3D phases show exactly **187 nodes and 71 edges** matching the stored structural API, rendered using Apple M4 Metal. Normal page polling remains active; 917 and 929 animation frames advance. There are no page errors or page external requests. Frozen source/driver hashes match and all ports close. These are fixture-specific observations, not a general speedup or capacity guarantee.

[Native run 42368702659](https://github.com/chriswu727/memBrain/actions/runs/42368702659) passes all five platforms on exact head `7a58d85869df1e34ecbf5d8a2dacedd9a88ba663`. Forty-seven audited journey summaries completed with zero model calls and all recorded ports closed. [Verify 42368700922](https://github.com/chriswu727/memBrain/actions/runs/42368700922) passes on that same head: **7,769 Python tests**, three retained fork deprecation warnings, **53 TypeScript tests**, strict types, Ruff and both package builds. Python completed in 2,571.24 seconds. No duplicate run was started.

Raw logs and scripts are retained in the accompanying evidence manifest. This engineering qualification does not satisfy the separate behavioral release gates. Separate exploratory source-script diagnostics are retained but do not modify this runtime or establish a new host hit rate. Its previous public cross-language misses remain unresolved. R4 remains failed, C5 incomplete; no fresh behavioral acceptance, main merge, tag or release is implied.
