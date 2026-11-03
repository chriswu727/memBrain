# Provisional maturity checks, 2026-11-03

The first release remains frozen. These are free implementation and harness checks, not a real-model R4 or C5 result. They do not establish that the final candidate has passed its launcher-pin check, Verify, installation acceptance or performance gates.

## Independent Mac checks

The full Python run used the temporary merge `4f91a34`: integration source `88ccada` plus the scenario-clock runtime from `66d8814`. Runtime source files remained unchanged throughout the run. `tests/test_installation_pin.py` was deliberately excluded because the integration branch had not received its final common pin.

| Check | Result |
| --- | --- |
| First full Python invocation | 6,229 passed, 1 failed, 122 setup errors, 6 skipped; 490.15 seconds |
| Failed cases after supplying the missing migration credentials | 123 passed, none skipped; 16.15 seconds |
| Six optional cases enabled explicitly | 6 passed, none skipped; 57.47 seconds |

All 123 failures/errors in the first invocation were PostgreSQL privilege errors: the operator supplied the restricted application connection but omitted `MEMORY_MIGRATION_DATABASE_URL`. The rerun supplied the dedicated migration connection and application password without changing tests or runtime code. The failed log is retained. The six optional cases were the Docker desktop flow, full streamed backup/recovery, independent package upgrade, standalone chat, real local embedding similarity, and model activation during requests. `MEMORY_DESKTOP_E2E=1` and a cached local embedding model enabled them. No paid host or extraction model was called.

This accounts for all 6,358 cases in that invocation across three runs. It is not a claim that the first invocation passed, or that later runtime changes have already passed the same full run.

Subsequent independent checks:

- The corrected C5 harness at `4a0210d`, combined with strict scoring validation: 101 clock, harness, scoring and matrix checks passed, none skipped.
- Intentional recording pauses initially produced two `message_identity_unknown` errors despite correctly storing nothing. A real-service regression reproduced this. `ad216e5` distinguishes an intentionally unrecorded turn from a missing recorded turn and still rejects unexpected stored messages. The related group passed 105 checks; the expanded practice scenario below exercises the actual pause/resume tools.
- The familiarity restore change at `717f168`, combined with the integrated runtime: 314 restore-related checks passed, none skipped; 53.25 seconds. An independent review found schema-valid timestamps that overflow UTC conversion. The subsequent input guard is included in `fc7d2f7`; its 211 related integration checks passed on Mac, none skipped (24.30 seconds). The TypeScript SDK passed 44 tests and its type check after adding the optional original-recording timestamp to its contract.

A later full invocation at `4b20f76`, with Docker, cached local embeddings and required Chromium enabled, passed 6,392 cases and failed one, with none skipped (546.04 seconds). The standalone-chat subprocess used an incorrectly resolved virtual-environment interpreter, which selected system Python without the package. That case passed unchanged when given the literal virtual-environment Python path (12.89 seconds). Both logs are retained. This accounts for all 6,393 cases across those two runs; it is not one clean full invocation and predates the portable familiarity merge.

The independent Chromium/browser group passed 110 checks, none skipped (14.45 seconds), including native confirmation acceptance/dismissal, both languages, phone and desktop widths, and a seeded login session that the fictional showcase must not use. Native occurrence-range rejection passed 116 related checks after three regressions failed on the old source. An earlier incomplete UTC fallback still let the worker fail; that failed log is retained.

## Public practice runs

Both runs used deterministic local host/extractor stubs, keyword recall, a disposable scenario-clock profile per memory arm, and the public `c5-practice-scenario.py`. The harness refused external socket connections. These runs used no held-out scenario and made no real-model call. Both services were independently confirmed stopped afterwards.

| Source | Layer checks | Strict validity | Scope |
| --- | --- | --- | --- |
| `aa1aa6e` | 236 passed, no failures | `valid: true`, no retried empty replies | Persona acceptance, feelings, mood decay, boundaries, reset and deletion |
| `ad216e5` | 250 passed, no failures | `valid: true`, no retried empty replies | The same checks, plus two intentionally unrecorded plugin turns followed by a recorded resume turn |
| `506cf29` | 250 passed, no failures | `valid: true`, no retried empty replies | Integrated portable familiarity history and the initial live-budget wiring; stub mode made no external call |
| `a0dd70a` | 250 passed, no failures | `valid: true`, no retried empty replies | Reviewed budget follow-up and allowlisted local-service startup; stub mode made no external call |

Machine-readable checker reports are in [maturity-free-practice-2026-11-03](maturity-free-practice-2026-11-03/). Raw failed logs and complete public-practice run artifacts remain in this task's local evidence directory.

The new validity command rejects every reported harness degradation, malformed event evidence, missing/duplicate/out-of-order turns, mixed run identities and an empty run set. Invalid runs retain their JSON report and exit nonzero. Ten synthetic regressions failed on the earlier validator. No historical evaluation result was changed or re-scored.

## Clean full Mac invocation

Head `a113eaa` (pin `b1d70fc`) passed **6,470 tests, zero failures and zero skips**, in one full invocation (740.76 seconds). Required Chromium, Docker end-to-end flows, the real cached local embedding model, and launcher-pin checks were all enabled. The literal virtual-environment interpreter was supplied to the standalone chat test. Three Python deprecation warnings came from deliberate fork tests. Runtime source stayed unchanged throughout. This clean full result includes the shared-lock safety and proposal timestamp fixes; it predates the subsequent CPU optimization.

## Reference performance baseline

The Mac baseline used runtime `fc7d2f7` (build `f32a502d7f0eae685fc854fe9d12183b98377f11615232208a4c057769e45e79`) and the benchmark script from `8a4965a`, on an Apple M4, Python 3.12.13 and embedded PostgreSQL 16.2. It seeded 1,000 keyword messages per brain across eight brains, plus 100 notes in the first brain, and waited for all indexing to settle. Each worker ran 21 recalls and discarded the first. No remote provider was configured. The bulk-write probe was disabled.

| Warm operation | Samples | p95 | Target met |
| --- | --- | --- | --- |
| Serial plugin recall | 20 | 480.25 ms | Yes, under 500 ms |
| Eight concurrent recalls, one brain | 160 | 2,390.70 ms | No, target at most 1,000 ms |
| Eight concurrent recalls, eight brains | 160 | 2,139.97 ms | No, target at most 600 ms |
| Memory map, 200 nodes | 20 | 18.78 ms | Settled-index observation only |
| Memory map, 500 nodes | 20 | 14.37 ms | Settled-index observation only |

All 340 recall responses were nonempty. The benchmark exited 1 because both concurrency bars failed; its service was confirmed stopped. [Raw samples and lock-wait summary](maturity-free-performance-2026-11-03.json) are retained. This is a baseline, not final R5 acceptance or a capacity claim, and does not erase the earlier 10,000-message map failure during indexing.

## Installed candidate on Mac

At integration head `6656720` (launcher pin `a01903af60780225e118c1e6abdee87a87ebd47f`), the full clean-home installation check passed all 49 checks. It used basic launcher fixture `d0d7a0379f7ac5f1b81dad04504601bb6606f1b0` and companion fixture `19e894ca9e08cf65fa071e8019789499953478d0`, each through its own frozen launchers. The check covered upgrade, cross-session recall, MCP changes/deletion, restart, the installed proxy against a local stub, and full backup/restore/activation with persona, feelings, mood, boundaries, shared moments and support style. [Check names and source metadata](maturity-install-mac-2026-11-03.json) are retained. This validates that candidate; later runtime changes need their own final acceptance. No paid or subscription-backed host was used.

PR review then identified an overflow in archived personality-proposal timestamps. Five parser regressions failed on the earlier code; two self-consistent archive restores reproduced HTTP 500 when listing suggestions, including an otherwise valid rejection timestamp whose 30-day pause overflowed. The fix ignores malformed internal records and verifies that rejection deadlines fit. Its persona/growth/relationship/companion group passed 170 checks, none skipped (15.37 seconds). Initial fixture-only failures (a stale content hash, then an incorrectly unpacked installation fixture) remain in the raw logs.

## Prospective billing-control checks

The evaluation-only guard and its C5 wiring passed 125 related offline checks at `506cf29`. Claude independently reviewed the code without running a model. The follow-up binds the full attempt to one ledger/policy, isolates local-service environment variables, reserves the complete published output bound and structures malformed-request refusals. Its related group passed 138 tests, none skipped (14.73 seconds). One preceding run had a false privacy-fixture failure because the literal word `private` matched macOS's temporary-directory path; the corrected fixture checks unique message and key strings. That failed log is retained. No API key or real provider was used. The public stub follow-up at `a0dd70a` passed all 250 checks and strict validity, with no external calls or retried empty replies. Its services stopped normally. Claude independently reviewed the actual `a0dd70a` source and reported 36 billing-guard checks passing with no further code finding. Provider policy, budget headroom and the complete behavioural plan still need freezing and approval; this grants no paid-run authorization.

## CPU follow-up

The early private safety/CPU combination `c3f2cff` improved serial/one-brain/eight-brain p95 to 234.31/1,781.39/1,903.34 ms, still failing both concurrent targets. Independent review found that the new HTTP fast path bypassed a subclass's overridden `handle`: the valid fixture returned 500 on the new route and 200 on the old route. `fa07a86` preserves subclass, instance-patch and duck-typed handlers and validates their responses. Seven independent HTTP checks passed, followed by 23 context/HTTP unit checks.

After merging that CPU head as `5175284`, 190 retrieval/context/semantic/shared-lock regressions passed (25.17 seconds). Its reference benchmark p95 values were 374.47/1793.52/2286.82 ms for serial/one-brain/eight-brain recall. All 340 replies were nonempty. The benchmark exited 1 because both concurrency targets still failed; the service stopped. Context budgets and fixture sizes were unchanged. [Raw CPU-candidate samples](maturity-cpu-performance-2026-11-03.json) are retained, including the higher eight-brain tail latency. The clean full suite above does not cover these later CPU changes.

## Still required

- Finish and independently validate the concurrent-recall/map performance change. Repeat the browser checks as part of the final candidate CI.
- Freeze and pin one combined source, then run Verify and the full installation acceptance on that candidate.
- Independently review and freeze the real behavioural acceptance plan and held-out scenarios. Obtain the owner's explicit approval for paid and subscription-backed evaluation, then pass R4 and C5. No such run has started.

An additional service-double regression found that `Mock(spec=MemoryService)` satisfies `isinstance` while its real class has no `handle` attribute. The fast-path check now uses guarded class-attribute lookup; real, overridden, invalid and mock-backed HTTP paths passed 34 API/context checks (1.51 seconds). This does not change the production memory algorithm or its budget.
