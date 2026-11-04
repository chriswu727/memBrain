# Bounded candidate channels: merged reads

Runtime candidate `28c0b3ed34484b29550b6d2c011a819bcbce016b` merges the keyword and feature-hash candidate reads before transferring and decoding duplicate documents. All nine launchers pin this revision. **256 local regression tests pass with zero skips. Full CI, fresh installation and complete canonical/fullscreen R5 qualification are pending for this candidate.** The [previous complete R5 failure](maturity-release-qualification-2026-11-04.md) remains historical evidence, not a pass for this change. Publication remains frozen.

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

## Remaining qualification

Next, run the unchanged canonical keyword benchmark and complete closed/open/open/closed fullscreen protocol on the pinned candidate, with all raw windows, graph identities, polling, visual artifacts and shutdown checks. Full CI and actual installation parity are also required. Real R4/C5 still requires separate authorization; independent/privacy/design review and working-state/full-familiarity graph coverage remain open. No paid/subscription evaluation, additional Claude call, schedule, merge, tag or publication is performed.

The [allowlisted manifest](maturity-lexical-channels-2026-11-04/manifest.json) contains prototype scripts, raw compressed samples, successful regression outputs and the failed broad lint output. Private archives, registry/profile/connection files and response fixtures are excluded.
