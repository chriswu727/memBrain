# Local query inference without durable job contention

Ordinary local semantic recall used the durable background-job path to prepare its query vector. Creating, claiming and publishing that job repeatedly requested an exclusive brain-row lock, even though a local query produces no persistent memory and incurs no provider charge. Concurrent readers held shared locks during retrieval, causing those query-job transactions to wait.

## Diagnosis and change

An instrumented installed-package replay of the unchanged public 10,000-source corpus measured the eight-client query-vector preparation stage at **826.931 ms median / 1,392.093 ms P95**, while actual ONNX inference took **2.004 / 2.377 ms**. Four exclusive brain-lock acquisitions were recorded per request; their individual P95 was 830.193 ms. These stage timings overlap and must not be added together. The diagnostic used a separate Python environment with timing wrappers, unchanged installed files and requests, and no paid/subscription calls. Its overhead means it is diagnostic evidence rather than an acceptance benchmark.

Unmetered local query inference now reads its source snapshot under the existing shared brain guard, releases the database transaction, and computes the vector. The enclosing action revalidates that snapshot under its normal brain lock before using the result. It creates no durable query job. Request receipts and bounded response-cache replay still enforce idempotency; a replay whose cached response expired still conflicts instead of silently computing a new reply. Simultaneous identical requests may compute the cheap local vector twice, but return one committed response; different payloads with the same request identity conflict.

Metered providers retain their durable job, lease, reservation, uncertainty and no-automatic-retry behavior. Local document indexing also retains its durable jobs. Source lookup is shared between the two query paths. A pending erasure can still require exclusive reconciliation; the optimization does not bypass recovery authority, generation checks, source revisions or tenant scope.

## Verification

The first four regression tests produced **two failures and two passes** on the previous code: a local query could not finish while an unrelated shared reader held the brain, and repeated local queries accumulated background jobs. After the change, the first selected group passed 23 tests. The broader group passed **92 tests**, including simultaneous request binding, source revision during preparation, erasure during inference, inference outside database locks, metered failure handling, job leases, read-cache behavior, recovery erasure and prepared-context selection. An added expired-cache replay assertion passes separately. Ruff and diff checks pass.

The same ordinary HTTP service, cached ONNX model, original questions and host budgets were used for the public replay. There were no query warmups, retries or generation calls in this replay.

| Corpus | API / final host hits | Median | P95 | Cold-inclusive maximum |
| --- | --- | --- | --- | --- |
| 1,000 sources | 20/20 / 20/20 | 289.562 ms | 470.310 ms | 1,270.218 ms |
| 10,000 sources | 20/20 / 20/20 | 369.914 ms | 549.603 ms | 1,226.999 ms |

The capacity probe uses a fresh service, one explicitly recorded warmup per client, then all 20 original questions per client, rotated by client index. Its five-second host budget is unchanged.

| Clients on one 10,000-source brain | Hits | Prior median / P95 | Current median / P95 |
| --- | --- | --- | --- |
| 1 | 20/20 | 362.882 / 540.741 ms | 364.625 / 546.363 ms |
| 8 | 160/160 | 1,676.405 / 2,086.856 ms | 1,041.000 / 1,103.997 ms |

Observed concurrent P95 falls approximately **47%** in this ordered comparison; it is not a population-wide latency guarantee. All measured requests and warmups retain actual semantic inference without fallback and include their expected source. The old query-job count stays **767 before and after**, showing no new query jobs were persisted. All original source/assertion/vector hashes remain unchanged; runtime files stayed fixed and every service/database port closed.

These are public development fixtures, not fresh held-out acceptance. R4 remains failed and C5 incomplete. No main merge, tag or release is authorized by this report. Installed-package qualification and full CI are pending. The preceding batch's 3D/structural and five-platform native results are historical evidence; this patch changes query inference only and does not claim those runs were repeated on this runtime.

Runtime build: `4f0ceb425c274678203a2db8bac48f986700d5d3d7c6dda617f503096209e8ab`. Schema 028 is unchanged. Failures, timing wrappers, full public responses and raw capacity samples are retained in [the checksummed evidence manifest](evidence/maturity-local-query-2026-11-07/manifest.json). Private profiles and corpus dumps are excluded.
