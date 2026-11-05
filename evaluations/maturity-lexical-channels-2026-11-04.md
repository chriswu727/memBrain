# Bounded candidate channels: merged reads

Runtime candidate `28c0b3ed34484b29550b6d2c011a819bcbce016b` merges the keyword and feature-hash candidate reads before transferring and decoding duplicate documents. All nine launchers pin this revision. **256 local regression tests pass with zero skips. Fresh installation passes 49/49 and all 165 installed files match. Fresh canonical recall passes, but the complete fullscreen R5 comparison FAILS: 33/36 windows pass, including 9/12 eight-brain windows.** Full CI is pending. The [previous complete R5 failure](maturity-release-qualification-2026-11-04.md) remains historical evidence, not a pass for this change. Publication remains frozen.

## Implementation

Both channels retain the same eligibility, tenant/owner/brain and conversation/branch filters, optional source cutoff, excluded versions and independent-source requirement. Each still ranks by distance with NULLs last, then ID/revision, and retains its own `limit + 1` sentinel. Only after those bounded reads does PostgreSQL deduplicate the admitted rows. Keyword-channel rows retain priority over hash-only rows, with original per-channel order. The overflow flag is calculated from each original capped channel, so overlapping results cannot conceal truncation.

The final Python deduplication remains. Queries without usable word terms and zero-sized limits preserve the separate-channel fallback. No ranking weights, candidate/context limits, validation, privacy, retention or concurrency policy changes. The query adds no schema migration or dependency.

## Controlled prototype

On source `ed95232`, before modifying the runtime, an external SQL prototype runs the predeclared **original / merged / merged / original** order. Each arm starts a fresh API on one hash-verified restoration of the failed qualification corpus, warms each of eight brains, then executes all 20 canonical query forms per brain through `host.recall_context`. Every measured sample is retained; ordinary receipts/traces accumulate across arms. No model is configured or called.

| Arm | Candidate reads | Host p95 ms | Mean ms | Maximum ms | API CPU ms |
|---|---|---:|---:|---:|---:|
| A1 | Separate | 685.20 | 497.88 | 978.55 | 10,951.90 |
| B1 | Merged prototype | 578.05 | 447.21 | 625.07 | 9,880.65 |
| B2 | Merged prototype | 562.46 | 446.27 | 593.61 | 9,398.52 |
| A2 | Separate | 619.17 | 477.66 | 750.37 | 10,598.12 |

All **640 contexts are nonempty**, their hashes match for each `(brain, query)` across all four arms, and every core recall completes with nonempty items and zero model/embedding usage. The diagnostic retains the original concurrency policy: its `slots` field is the variant selector (0=original, 1=merged), **not an admission limit**. Peak active core requests are 8/8/8/7. This contrasts with the earlier [admission experiment](maturity-cpu-attribution-2026-11-04.md), whose queue/deadline/fairness behavior is not accepted for production.

These are instrumented exploratory timings without a browser, not R5 qualification. Reference variation and accumulated database writes limit attribution. The shipping query uses JSONB memory IDs rather than the prototype's text extraction, and preserves the original zero-limit/no-word fallback and final Python deduplication. Its final timing must be measured separately. All 1,484 restored profile hashes and the existing registry are verified before startup; services stop, ports close, source stays unchanged and the successful disposable copy is removed.

## Regression evidence

The focused real PostgreSQL group passes **106 tests**, zero skips, including candidate collection, source bridges, historical neighborhoods, complete response validation and three new channel regressions. A further API/storage/scope/feedback/retrieval group passes **150 tests**, zero skips. Source hashes remain fixed through both groups and both API/database ports close afterward.

The new differential regression compares **144 combinations** of query, limit and optional historical filters against independent separate-channel SQL reads, comparing complete returned rows, order and truncation. Additional cases exercise overlapping physical rows sharing a document version, sentinel preservation, NULL-distance ordering and hash-only results. Existing isolation, hash-collision, invalidation, source-evidence and response-validation checks are retained. Query-count assertions are updated for the actual one-statement implementation while preserving bounded parameter and injection assertions.

Ruff passes the exact CI scope, `src tests examples`; `git diff --check` passes. The retained broader `ruff check .` scan, before this checkpoint's raw scripts are archived, fails with **74 findings, all in archived evaluation scripts**, including previously retained raw evidence. Its machine-readable output is preserved; those evidence files are not rewritten to manufacture a clean scan. Four immutable-pin/matrix guards also pass. No full-suite or release pass is claimed from these checks.

## Shipping runtime: canonical passes, complete R5 fails

Source `26db0e08bb86396aa64c6b79ad0f2fc6fd0d4c8d`, pin `28c0b3e`, is frozen during the original canonical benchmark and complete closed/open/open/closed protocol. The drivers differ from the prior qualification only in owned paths/output labels and runtime identity; their exact diff is retained. Context/candidate limits, 21 rounds per worker with only the declared first warmup excluded, all workloads, normal page polling and release bars remain unchanged. No provider is called.

The fresh standard benchmark exits 0: serial/one-brain-eight/eight-brain-eight p95 is **129.91/511.87/595.15 ms**, all **340 recalls nonempty**. Map p95 at 200/500 nodes is **12.39/15.24 ms**. Source hashes remain unchanged and both ports close. The eight-brain result has little margin below 600 ms; it does not establish sustained success.

The complete fullscreen comparison finishes and exits 1. All **4,080 recalls** are nonempty. Serial and same-brain windows pass; three eight-brain windows fail:

| Phase | Cycle (zero-based) | Eight-brain p95 ms | Bar ms |
|---|---:|---:|---:|
| Open 1 | 2 | 703.72 | 600 |
| Open 2 | 0 | 606.04 | 600 |
| Closed 2 | 1 | 664.84 | 600 |

Eight-brain aggregate p95 by phase is **524.24/600.00/585.34/535.21 ms**. Passing aggregate figures do not override failed windows. The merged read reduces work in the controlled prototype, but this qualification does **not** demonstrate that it solves sustained tail latency or improves every production timing over earlier runtimes. No unchanged rerun is used to select a green result.

Both open phases use actual **ANGLE Metal on Apple M4**. The renderer's **186 node IDs and 66 edges** match the API before and after measurement. Normal status polls remain active, the page stays visible and the animation advances **1,945/1,928 frames**. Both post-measurement screenshots are visually inspected; page/external-request/artifact errors are zero. Source and driver hashes stay fixed; all six ports close. Visual correctness does not pass the failed latency gate.

The stopped failed fixture and its registry are privately archived. All **1,486 regular files** are hash-verified against the archive before removing only the owned disposable profile; the existing registry remains in place. Archive SHA-256 is `98c8ee798d41c59fca91bf699c66835d903f9110535b50fac5bb060379b3ca6e` (304,286,168 bytes). The private archive, inventory, credentials and profiles are excluded from Git. The separate completed regression cluster is removed only after port and hash checks; its profile, registry, packages and logs remain.

## Fresh installation and installed-runtime verification

The unchanged release checker passes **49/49 checks**, zero failures, on source/evidence head `38e61ad` with the same `28c0b3e` runtime. The original basic and companion baselines remain frozen. The only wrapper override is the location of an existing owned download cache; homes/installations are fresh. It exercises actual launcher upgrade, cross-session recall, all three MCP launchers, correction/deletion, restart, proxy, backup/restore/activation and preservation of companion persona, simulated mood, reported feelings, shared moments, boundaries and support style. No paid/subscription model evaluation is called. The release-harness SHA-256 is `1c6c20e4815864e42225c803659f35f29ae5330d379efbc7a76565fb48e8e9e4`.

The follow-up uses the **actual installed interpreter**, checks all **165 package/schema/migration files** against current source, and finds zero mismatches or unexpected files. It verifies recording-time masking on all three graph paths, explicit reveal of original times, and a boundary edit changing the next host context rather than replaying the cached contribution. After all fixture writes, pending jobs/index lag are recorded as **3/3 → 0/0** before graph snapshots. The actual installed API and browser agree on both graph layers; fullscreen and 2D work, with zero page errors or outside requests. Stop exits 0; the screenshot is visually inspected. All API/database ports of the five owned installation/follow-up profiles are independently checked closed.

This re-establishes current R1 evidence. It does not close R2, R5, behavioural acceptance or remaining graph/review coverage.

## Remaining qualification

Next, finish the already-running full CI. R5 stays open: further work must explain or control tail latency while preserving the same quality and release bars, rather than repeating this unchanged qualification. Real R4/C5 still requires separate authorization; independent/privacy/design review and working-state/full-familiarity graph coverage remain open. No paid/subscription evaluation, additional Claude call, schedule, merge, tag or publication is performed.

The [allowlisted manifest](maturity-lexical-channels-2026-11-04/manifest.json) contains prototype scripts, raw compressed samples, successful regression outputs and the failed broad lint output. Private archives, registry/profile/connection files and response fixtures are excluded.
