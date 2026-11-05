# Guarded native recall-response validation

Runtime `1ca3cb23381650e245c8320906b9c467a9e3ecd7` adds compiled native validation for completed recall responses with at least 16 items. All nine launchers pinned this revision during the frozen qualification; the [subsequent privacy follow-up](maturity-companion-privacy-2026-11-04.md) is tracked separately. **201 local PostgreSQL-backed regression checks pass, zero skips; CI-scope Ruff and sdist/wheel builds pass. Fresh installation passes 49/49 and all 166 installed files match. Canonical recall and all 36 fullscreen workload windows pass. Full CI is running.** Publication remains frozen. The previous runtime's [7,032 Python/50 TypeScript passes, 49-check installation and failed R5 windows](maturity-lexical-channels-2026-11-04.md) remain evidence for that revision only.

## Validation boundary

The accelerator retains the original Python validator for small recalls, other actions, rejected responses and every failed or unsupported accelerated check. It compiles only a bounded subset of the actual linked contract, uses the same Python date-time checker, disables external reference retrieval and admits only ordinary JSON-compatible values with finite, exactly bounded numbers. Custom validators, schemas, format/type checkers, changed prepared rules and unsupported values fall back. Invalid responses retain the original domain error and instance path.

Every accelerated call audits captured schema and prepared-rule containers for mutation and checks the instance again. The bounded cache retains compiled schemas, never response values or a prior validation result. First-use schema preparation and compilation are serialized; validation is outside the compilation lock. Accelerator metadata setup or compilation failures preserve reference validation. The dependency is pinned to `jsonschema-rs==0.60.3`; no existing dependency version is upgraded. Candidate selection, ranking, privacy/scope, receipts/traces, context/cost limits and admission policy remain unchanged.

## Controlled experiment, not R5 acceptance

Before the final cold-start locks and metadata fallback, the mutation-audited implementation runs a fixed **reference / native / native / reference** sequence on one verified restoration of the preceding failed corpus. Each arm uses a fresh real API, eight brains and all 20 canonical query forms per brain. No admission limit or model call is introduced. Normal receipts and traces accumulate between arms.

| Arm | Native validation | Host p95 ms | API CPU ms | Accelerated calls |
|---|---|---:|---:|---:|
| A1 | Disabled | 546.50 | 9,750.22 | 0/160 |
| B1 | Enabled | 457.72 | 8,484.99 | 160/160 |
| B2 | Enabled | 468.48 | 8,555.79 | 160/160 |
| A2 | Disabled | 524.58 | 9,495.87 | 0/160 |

All **640 contexts are nonempty**, every core recall completes, and the context hash for each `(brain, query)` matches across all four arms. All eight requests can remain active. Source/dependency/test hashes remain fixed throughout; ports close and the restored disposable copy is removed afterward. This instrumented experiment has no browser and measures a preceding implementation: it supports proceeding to qualification, not a release or final-runtime latency claim.

An earlier serialized-schema prototype also retains all 640 context hashes and p95 values 515.38/458.34/449.02/505.12 ms; that version is superseded. A real 51-item response microbenchmark of the mutation-audited version measures reference/native/native/reference median thread CPU 8.55/2.09/2.20/8.96 ms over 100 checks per arm. These microbenchmarks omit HTTP, SQL and rendering and precede the final locks. The private response fixture stays excluded from Git.

## Local verification and retained failures

The final contract/native/schema group passes **87 tests** against a real embedded PostgreSQL instance; the API/storage/response/isolation/feedback/adversarial/ranking group passes **114**. Both use the actual application role and preserve source hashes; API and database ports close. Native tests cover deterministic mutations, custom validator state, in-place prepared rules, date-time edge cases, number/subclass/depth exclusions, no response retention, offline compilation, concurrent first use and metadata failure fallback.

Earlier logs are retained: one test-authoring attempt used a dictionary monkeypatch helper on a list and failed; it was corrected without weakening the assertion. A later command named a nonexistent test file and collected nothing. Another invoked seven schema-compatibility cases without their required database environment (80 other checks passed, seven setup errors); the final 87-check dedicated-database run resolves that setup error. A pin attempt with an incorrect commit argument was rejected before changing any launcher; pins were then generated from the actual Git commit. No failed log is represented as a pass.

## Frozen runtime qualification

Source `efc8eb60b2ee91583bb46afc00f431e64d947057`, pin `1ca3cb2`, stays unchanged throughout the original canonical and complete fullscreen protocols. Only owned paths/output labels and runtime identity differ from the prior drivers; the exact diff is retained. All workloads, context/candidate limits, 21 rounds with only the declared first warmup excluded, page polling and release bars remain unchanged. No model is called.

Fresh canonical p95 is **87.33/428.25/458.26 ms** (serial/one-brain-eight/eight-brain-eight), all **340 recalls nonempty**; map200/map500 p95 is **10.99/14.72 ms**, with no errors. Source hashes remain fixed and both ports close.

Complete closed/open/open/closed qualification exits0, completed/passed true: **36/36 workload windows**, including **12/12 eight-brain windows**, pass. All **4,080 recalls are nonempty**. Worst eight-brain window p95 is **471.41 ms**; phase aggregate p95 is438.43/447.23/450.33/448.34ms. Individual eight-brain window p95 values are428.83/443.77/436.55,442.88/458.36/437.32,471.41/448.17/440.33,448.59/443.22/448.34ms. None is discarded.

Both open phases use **ANGLE Metal on Apple M4**. All **183 node IDs and66 edges** match the API before and after measurement. Normal page/status polling remains active, the document stays visible and animation advances1,597/1,577frames. Screenshots are visually inspected; page/external-request/artifact errors are zero. Source/driver hashes remain fixed and all six ports close. This establishes performance on the reference fixture, not unlimited capacity or semantic/model latency.

The stopped passing corpus is privately archived and all **1,490 regular files** verified, archive SHA256 `3ab9a621a4a5d57f3bd391f2f47eebd20d2c5d824d83d4b6dd698caf8be815d7`,313,058,770bytes. Only its now-backed-up disposable PostgreSQL directory is removed; profile and registry remain. Earlier failing archives remain untouched. Identical public ONNX model files in completed installation environments are retained as independent APFS copy-on-write clones, with content/mode/owner/mtime checked; no hardlinks or package/model deletion. Measured free-space gains are1,776,828,416bytes across earlier environments and474,382,336bytes in the newly completed one.

## Fresh installation and installed runtime

The unchanged frozen release checker passes **49/49**, zero failures, including basic/companion baseline upgrades, real host/MCP/proxy recall, restart, backup/restore/activation and companion controls. Only an existing download-cache location is overridden; homes/installations are fresh. Original checker SHA256 is `1c6c20e4815864e42225c803659f35f29ae5330d379efbc7a76565fb48e8e9e4`.

The actual installed interpreter verifies **166 exact package/schema/migration files**, zero unexpected files or mismatches, and installed `jsonschema-rs0.60.3`. Added fixture writes settle before snapshots. Three recording-time privacy paths, explicit reveal of original times, live boundary refresh, both graph layers/fullscreen/2D pass; no page or outside-request errors, stop0, screenshot inspected. All five owned installation/follow-up profiles have both API/database ports independently checked closed.

## Independent graph review: reproduced and repaired privacy boundary

After those frozen checks finish, an external regression reveals an existing companion-map defect: with `max_nodes=2`, a sensitive-feedback-derived persona can remain unmasked when the protected source lies outside the bounded source sample. The same fixture at3/4nodes passes: **one failure/two passes** are retained.

Follow-up source `d4f0c03689459f84a2e3d25358e74479d1aa2968` resolves protection over every requested source before applying display bounds. Six new node/edge-cap cases also check explicit reveal and unchanged identities/timestamps. The real PostgreSQL graph/browser group passes **85 tests**, zero skips; Ruff passes. This fix is subsequent to the frozen native qualification and is not included in its installed package or CI input. Its launcher pin and final qualification are pending. The known defect blocks publication until that repaired candidate is verified.

## Full CI and open gates

[Verify41947100144](https://github.com/chriswu727/memBrain/actions/runs/41947100144), job126981919797, is running at source `efc8eb6`; frozen sync/model setup/migration/Ruff have passed and Python is still executing. TypeScript/types/build remain pending. No full CI pass is claimed yet.

The new privacy follow-up needs coherent launcher pins and final qualification; the preceding native pin has49/166installation and36/36performance evidence. Real R4/C5 remains unapproved. Final independent/privacy/design review and working-state/full-familiarity graph coverage remain open. There is no schedule, new Claude call, merge, tag or publication.


The [allowlisted manifest](maturity-native-validation-2026-11-04/manifest.json) preserves75 artifacts plus the manifest, including raw compressed samples, failed logs, drivers and inspected screenshots. An exact-value scan checks35 credential/DSN values from7 owned profiles and finds no match; private fixtures, archives, file inventories, registries and profiles are excluded.
