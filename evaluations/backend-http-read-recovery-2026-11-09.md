# Bounded recovery for closed memory read connections

PR #58 is merged into integration as `f0b9b3040544300d5914a1921c63675dc1f592ee`. The complete merge tree equals qualified source `8fa22d81b73e8e0108a9edafff335b22f6af3f1a`. Current engineering checks pass; earlier failed runs remain failures for their original candidates, and publication is still blocked. Documentation/evidence follow-ups change no runtime inputs. The [erasure report](backend-erasure-recording-fence-2026-11-09.md) retains its original failures and implementation details.

Runtime `b4d39b4c6ca6ce0ab1816fe620702b637e2bb6ec`; pinned source `8fa22d81b73e8e0108a9edafff335b22f6af3f1a`; build `b616c53c7f270ce7a679b54322d5ebea97fd4b9a218a82bbcec4d524ab4cecc8`; schema `4e3d5a4a8bc5c1bdacdb13b4a3b6b10fb7347ba3ba9e03d7ab6e288a5b1687b5`. All 209 runtime inputs match the extracted wheel.

## Behavior and diagnosis

The Python memory client repeats a bodyless GET at most once after `httpx.RemoteProtocolError` or `httpx.ReadError`. Authentication, recovery epoch, path and parameters are preserved. A static warning includes only the exception class, never the URL, request data, credentials or exception detail. If the second attempt fails, it propagates. Writes, requests carrying body arguments, timeouts, connect errors, HTTP error responses and malformed JSON do not trigger this recovery. Each attempt retains the configured HTTP timeout; this is not a shared wall-clock deadline. No model-provider transport or uncertain external delivery is retried.

The earlier CI failure was a closed persistent connection during a cognitive-usage snapshot, after hundreds of requests. Its server-side cause remains unproven. A deterministic real-TCP probe now closes a uvicorn keepalive connection after httpcore has checked it for reuse. The unchanged client fails with a connection reset; this client completes the read through a fresh connection. A separate real HTTP server closes after accepting a request, testing the ambiguous-response case and proving writes are not replayed. Fault injection establishes this failure mechanism and the recovery boundary, not the exact cause of the historical CI incident.

## Verification

- Source: 161 related tests pass: 41 client/recovery/matrix checks and 120 longitudinal, runtime, delivery, erasure and extraction checks. No skips. The complete local conversation scenario is included.
- Ruff, launcher pin checks and wheel/sdist builds pass. Package hashes are retained in the evidence identity.
- Extracted-wheel checks: the same 161 tests pass with existing development dependencies. Imports resolve to the wheel; subprocesses that sanitize import paths can use the matching checkout. This is not a separately provisioned dependency environment.
- [Native 42641749935](https://github.com/chriswu727/memBrain/actions/runs/42641749935) passes all five platforms: 47 audited logical summaries, five duplicate copies excluded, zero model calls and all recorded port closures passing. Previously checked supplier binaries from run 42574397718 are reused; supplier inputs are unchanged, and current application startup, upgrade, SQL maintenance and recovery checks run afresh. Automatic run 42641634923 was cancelled to avoid duplicate binary builds.
- [Verify 42641634827](https://github.com/chriswu727/memBrain/actions/runs/42641634827) passes **8,228 Python tests, zero skips, three multiprocessing fork warnings in 1,969.28 seconds**, plus **56 TypeScript tests, zero skips**, strict types, Ruff and package builds. Node action setup/teardown also emits existing `punycode` deprecations. The CLI aggregate log ended the pytest section early; the direct job-log endpoint provides the complete result. Both copies and their hashes are retained. The previously failing real-loopback scenario passes in this full run.

Initial reproduction failures, the fixture import error and its correction, and the copied native helper's masked baseline-SHA guard failure are retained alongside later successes. These diagnostics made no paid model calls. The duplicate automatic native build was cancelled; the manual run reuses previously qualified native binaries with current application checks.

## Scope and remaining gates

Healthy reads still issue one request. This change adds resilience to failed reads; it is not a measured recall speed improvement. No new large-corpus or R5 latency qualification is claimed. The earlier erasure runtime's local timing comparison remains scoped to that runtime.

R4 remains failed; C5 remains invalid/unscored. No new paid or subscription-backed acceptance ran. Module 1 still needs ephemeral durable turns, cross-adapter receipt normalization and local/server control synchronization. Main merge, tags and publication remain blocked.

Raw logs, package identities and checksummed compressed evidence are retained under [evidence](evidence/backend-http-read-recovery-2026-11-09). Stopped synthetic test databases are removed after each batch. The source and installed batches removed 125,366,173 and 125,489,029 bytes of stopped synthetic databases. The extracted wheel and 30,920,352 bytes of build outputs have been removed after parity/checksum checks. The first package-cleanup helper stopped on the generated `.gitignore` marker; its correction and the unretained extracted-wheel byte count are recorded. Final raw-file cleanup is recorded separately after checksum verification; real profiles, models, backups and the shared development environment are retained.
