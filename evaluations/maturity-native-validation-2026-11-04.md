# Guarded native recall-response validation

Runtime `1ca3cb23381650e245c8320906b9c467a9e3ecd7` adds compiled native validation for completed recall responses with at least 16 items. All nine launchers pin this revision. **201 local PostgreSQL-backed regression checks pass, zero skips; CI-scope Ruff and sdist/wheel builds pass. Fresh installation, full CI and complete R5 qualification for this runtime are pending.** Publication remains frozen. The previous runtime's [7,032 Python/50 TypeScript passes, 49-check installation and failed R5 windows](maturity-lexical-channels-2026-11-04.md) remain evidence for that revision only.

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

## Open gates

The final runtime needs fresh unchanged canonical and complete fullscreen R5 measurements, full CI and installation/installed-source parity. Real R4/C5 remains unapproved. Final independent/privacy/design review and working-state/full-familiarity graph coverage remain open. There is no schedule, new Claude call, merge, tag or publication.
