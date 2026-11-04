# Recall CPU attribution and admission experiments

Runtime remains `b994ec8080d46ee861f6ed8738a1617929f50d2a`; repository source is `cab954408d8cb72ff56c2c97aacf7b7a259219d4`, with no runtime changes from the fully verified `281b06e` source. **No product optimization is shipped in this checkpoint. R5 still fails the latest complete qualification (33/36 windows pass).** These experiments diagnose that failure; their timings do not replace it.

## Whole host path and thread CPU

The failed qualification's private cold archive is restored and all **1,484 profile files** are verified before startup. The existing recovery registry is verified without overwriting it. The diagnostic executes the actual `host.recall_context` path, including boundaries, recall, timeline/replies and the transient trace endpoint. It records thread CPU separately from elapsed time, process CPU, event-loop thread CPU, JSON response encoding and garbage collections. Instrumentation observes garbage collection without changing its policy. It records SQL labels without parameter values.

Three serial requests and 32 requests across eight independent brains all return nonempty contexts; all core outcomes complete and model/embedding usage is zero. During the eight-brain batch:

| Measurement | Total ms |
|---|---:|
| Batch elapsed | 2,035.95 |
| API process CPU | 2,128.30 |
| Event-loop thread CPU | 202.79 |
| Core responder thread CPU | 1,628.52 |
| Candidate collection CPU | 770.43 |
| ActionResponse validation CPU | 283.32 |
| Context fitting measurement CPU | 118.95 |
| Generation-2 collection CPU | 95.82 |

These categories overlap and must not be summed. SQL elapsed time includes scheduling, GIL contention and server waits; it is not PostgreSQL executor-only time. The API process consumes approximately one CPU core during this batch. That supports investigating Python-side work and scheduling, rather than concluding that SQL storage is inherently unsuitable. It does not establish a single exclusive cause or general capacity limit. Average host latency is 504.69 ms and the maximum is 616.33 ms **under instrumentation**.

A separate, warmed core profile removes API and pool threads and asserts `threading.active_count() == 1` before and after each of two actual recalls. Both complete with 51 items. Unlike earlier conflicting concurrent cProfile attempts, these profiles isolate the calling Python thread. They identify candidate collection, JSON/schema traversal, lexical parsing and context fitting as relevant locations. Profiling itself raises CPU time to approximately 86.5 ms per call; those absolute timings are not production latency measurements. No additional server-side EXPLAIN evidence was gathered in this checkpoint.

## Validation prototype, rejected for shipping

An external conservative positive-check prototype is tried against one actual retained response (51 items, 241,026 bytes). In a 20-iteration CPU microbenchmark the existing validator has median 8.488 ms and the prototype 5.931 ms. An exploratory differential sample checks 1,806 valid/mutated documents, including 258 accepted positives, without an observed false acceptance. This is a limited sample, not proof of compatibility with every evolved schema, custom checker, numeric/subclass behavior or mutation.

The approximately 2.6 ms saving does not justify shipping duplicated validation logic with an unproven compatibility surface. The prototype remains outside the runtime. Its fixture stays private; the small result metadata records the prior tool output, not an independently retained benchmark execution log. The production validator and all validation boundaries remain unchanged.

## Predeclared admission comparisons

The experiment fixes the complete arm order before running: **unlimited / four slots / four slots / unlimited / unlimited / two slots / two slots / unlimited**. Each arm starts a fresh API process, warms one request per brain, then measures all 20 canonical query forms on each of eight brains. A shared verified restoration accumulates ordinary receipts/traces across arms. No sample, trace, receipt or memory is discarded to improve timing.

| Arm | Concurrent core slots | Host p95 ms | Mean ms | Maximum ms | API CPU ms | Mean queue ms |
|---|---:|---:|---:|---:|---:|---:|
| A1 | Unlimited | 550.79 | 471.73 | 630.48 | 10,491.05 | 0.00 |
| B1 | 4 | 509.18 | 446.97 | 634.08 | 10,211.82 | 21.55 |
| B2 | 4 | 548.06 | 450.95 | 580.46 | 10,257.08 | 17.34 |
| A2 | Unlimited | 534.75 | 446.44 | 603.37 | 10,073.64 | 0.00 |
| A3 | Unlimited | 644.42 | 494.21 | 694.72 | 10,552.59 | 0.00 |
| C1 | 2 | 500.31 | 435.30 | 646.03 | 9,482.30 | 189.44 |
| C2 | 2 | 505.59 | 438.37 | 732.82 | 9,561.11 | 189.13 |
| A4 | Unlimited | 547.46 | 450.79 | 584.24 | 10,232.63 | 0.00 |

All **1,280 measured host contexts** are nonempty. Their SHA-256 values match the first arm for every `(brain, query)` pair; all 1,280 core outcomes complete with nonempty items and zero model/embedding calls. The measured maximum active core calls matches each slot limit. This protects the actual returned context in this fixture; it does not certify every recall result field, mixed-write workload or provider mode.

Two slots reduce p95 and process CPU in both measured arms, but introduce approximately 189 ms of mean queue wait, and the second arm's maximum reaches 732.82 ms. Four slots show a smaller, inconsistent gain relative to their adjacent references. Reference variation, accumulated database writes and the absence of a browser limit causal interpretation. The semaphore prototype has no bounded admission queue, queue deadline, writer-fairness policy or provider-I/O isolation. **It is not production-ready and is not installed or pinned.** No GC tuning, process pool, dependency replacement or shortened recall budget is shipped.

## Evidence and next action

The [allowlisted manifest](maturity-cpu-attribution-2026-11-04/manifest.json) retains diagnostic scripts, compressed raw measurements, logs and metadata. Private archives, profile files, connection strings, registry records and response fixtures are excluded. Every successful restored copy is stopped, its ports checked closed, and only that disposable copy is removed. Source hashes are unchanged throughout. All local diagnostic processes are terminal.

Next, investigate whether a bounded recall execution policy can preserve total request deadlines, cancellation, fairness and concurrent writes without holding scarce slots through slow provider calls. Compare it against the unchanged runtime before deciding to implement it. Separately, candidate-read/decoding work remains an evidence-backed optimization target. Do not repeat the unchanged full qualification to select a green run. Full CI remains the earlier confirmed 7,029 Python/50 TypeScript pass; no new runtime suite is claimed here. Real R4/C5, final independent/privacy/design review and remaining graph coverage also stay open. No paid/subscription model call, additional Claude consultation, schedule, merge, tag or publication is performed.
