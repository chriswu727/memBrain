# Recall lexical work and embedded buffer defaults

This follow-up preserves the current recall contract, ranking policy, context/candidate limits, native validation, privacy, complete traces/receipts and retention. It removes unnecessary lexical work and raises the embedded database's managed shared-buffer default from 32 to 128 MB. The latter adds 96 MB shared by the installation, not by every brain. **New-runtime full CI, installation and complete R5 qualification are pending.** The preceding `d4f0c03` failure at 892.11 ms remains retained; no release gate is closed by the experiments below.

## Lexical computation

Contraction regex replacements are skipped only after Unicode normalization/curly-apostrophe folding confirms there is no apostrophe. Stemming no longer slices words that do not have the tested suffix. Source-origin frequency sets/counters retain only query terms, while preserving the count of every origin, including unmatched origins. Ungrouped document deduplication still uses the complete term identity, so documents differing outside the query remain distinct. The weighting formula and ranking version do not change.

A fixed reference/prototype/prototype/reference pure CPU experiment over 252 actual synthetic stored memories runs 50 iterations per arm. Median CPU is **2.772 / 2.356 / 2.364 / 2.7895 ms**. All weights and scores are exactly equal throughout, and **5,278 tokenization examples** match the reference. This is about a 15% reduction in this small lexical fragment, not a 15% API speedup or an R5 pass.

## Embedded buffers

The same retained isolated synthetic corpus runs a predeclared **32/128/128/32 MB** experiment with fresh APIs, 32 warmups and 160 measured eight-brain recalls per arm. All **640 measured contexts are nonempty and identical by brain/query SHA256**; all 640 large responses use native validation. P95 is **487.66 / 421.49 / 447.64 / 441.89 ms**. The two settings overlap in latency; no consistent latency reduction or cause of the old failed window is established.

Both 128 MB arms record zero assertion/event main-heap cache misses, while both 32 MB arms record roughly 97,000 assertion and 19,000 event misses over the measured work. Assertion TOAST misses fall from roughly 44,000–47,000 to about 1,200. These are PostgreSQL buffer misses, not proof of physical disk reads. The larger default provides cache headroom; it is not presented as a proven solution for all tail latency. Config files and application source remain unchanged during the experiment, GC policy is unchanged and ports close.

Fresh clusters receive 128 MB. On a stopped existing cluster, only one exact generated memBrain configuration block using 32 MB is replaced, atomically. Unrelated bytes and later custom overrides remain intact; customized/ambiguous blocks, symlinks and hardlinks are left alone. LF/CRLF, file permissions and ownership are preserved. A running cluster is neither restarted nor rewritten; its old default is migrated on a later cold start. Failure to update configuration is reported before starting PostgreSQL, without exposing the underlying private exception. No data/catalog migration or change of PostgreSQL version is performed by this update.

## Local verification and retained instrumentation failures

The PostgreSQL-backed runtime/candidate/contracts/storage/privacy group passes **268 tests, zero skips**, before the final typed configuration-error wrapper. Its outer postcheck then fails on a deliberately malformed no-database profile from a validation test. The original failure is retained. A separate terminal inspection checks only profiles with actual database clusters and verifies all eight owned ports closed. The lost pre-run hash receipt is not reconstructed as proof. No passing tests are rerun merely to obtain a clean wrapper exit.

After the typed error wrapper, the final embedded group passes **19 tests, zero skips**, including fresh/default migration, no hot changes, LF/CRLF preservation, custom/ambiguous/link handling, failed atomic replacement, nonblocking FIFO handling and redacted startup failure. CI-scope Ruff and diff checks pass. An earlier no-database local command records 77 passes/three skips; the later PostgreSQL group covers those integration cases without skips.

The first function-profile attempt fails because overlapping cProfile instances conflict. A serial attempt completes but records negative own times with a thread-local clock, so its timing figures are not used as quantitative CPU evidence. Both are retained. The preceding [coarse CPU/SQL/GC attribution](maturity-recall-attribution-2026-11-04.md) remains separate and does not prove failure causality.

To make room for qualification, only 13 stopped, completed, owned synthetic native test clusters are archived with their profiles/registries, with **18,638 regular files** hash-verified before removing database directories. The private archive is 99,980,623 bytes, SHA256 `28fa5e9f41d1a7fc018654d09d526672959efd39420941e0f526182299f8bc7b`. Profiles, registries, models, packages, compiler trees and earlier failed-corpus archives are retained. Private archives and inventories are excluded from Git.

The PostgreSQL 16.2 security baseline, actual R4/C5 evaluation, remaining graph coverage and final reviews remain open. No unapproved paid/subscription model run, new Claude call, subagent, schedule, merge, tag or publication is performed.
