# Provisional maturity checks, 2026-11-03

The first release remains frozen. Every result applies to the source named below. Runtime `9d8509c` has passed its local Python, SDK, package-content and Mac installation checks; both concurrent R5 targets remain unmet. Final combined-source Verify and the real-model R4/C5 gates remain open. No paid or subscription-backed behavioural evaluation has started.

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
| `98f416d` | 250 passed, no failures | `valid: true`, no retried empty replies | Permanent shared stops, failure supervision and signal cleanup; normal stub flow made no external call |

Machine-readable checker reports are in [maturity-free-practice-2026-11-03](maturity-free-practice-2026-11-03/). Raw failed logs and public-practice JSON/logs remain in this task's local evidence directory. Completed, reproducible temporary database/model copies were later removed to recover disk space; source fixtures and execution evidence are retained.

The new validity command rejects every reported harness degradation, malformed event evidence, missing/duplicate/out-of-order turns, mixed run identities and an empty run set. Invalid runs retain their JSON report and exit nonzero. Ten synthetic regressions failed on the earlier validator. No historical evaluation result was changed or re-scored.

## Clean full Mac invocation

Head `a113eaa` (pin `b1d70fc`) passed **6,470 tests, zero failures and zero skips**, in one full invocation (740.76 seconds). Required Chromium, Docker end-to-end flows, the real cached local embedding model, and launcher-pin checks were all enabled. The literal virtual-environment interpreter was supplied to the standalone chat test. Three Python deprecation warnings came from deliberate fork tests. Runtime source stayed unchanged throughout. This clean full result includes the shared-lock safety and proposal timestamp fixes; it predates the subsequent CPU optimization.

The second CPU candidate `efb0f6e` (pin `c0a1452`) subsequently passed **6,494 tests, zero failures and zero skips**, in one full invocation (724.26 seconds), with the same required browser, Docker and cached local-model options. Source and launchers stayed unchanged throughout. Three fork deprecation warnings remained. This full run covers the second CPU follow-up and map fix; it predates the evaluation stop-rule changes described below.

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

- Finish and independently validate concurrent-recall performance. The map follow-up below passed its 80-request reference run. Repeat the browser checks as part of the final candidate CI.
- Freeze and pin one combined source, then run Verify and the full installation acceptance on that candidate.
- Independently review and freeze the real behavioural acceptance plan and held-out scenarios. Obtain the owner's explicit approval for paid and subscription-backed evaluation, then pass R4 and C5. No such run has started.

An additional service-double regression found that `Mock(spec=MemoryService)` satisfies `isinstance` while its real class has no `handle` attribute. The fast-path check now uses guarded class-attribute lookup; real, overridden, invalid and mock-backed HTTP paths passed 34 API/context checks (1.51 seconds). This does not change the production memory algorithm or its budget.

## Map query follow-up

The full map benchmark at `dbc2818` still failed: 40 requests at 1,000 messages succeeded, then the first 10,000-message/200-node request returned 503 after 2,014.922 ms. The report has `completed: false` and `stopped: true`; [all 41 requests are retained](maturity-map-failure-2026-11-03.json). PostgreSQL logged the 2-second statement timeout on the note-source dependency join, distinct from the earlier brain-row lock timeout.

On that retained PostgreSQL 16.2 fixture, with indexing paused, EXPLAIN ANALYZE reported 988.077 ms for the original plan and 24.347 ms with nested-loop joins disabled. Both returned the same ordered 500 rows, with digest `ac13e76d49214dbabc89cdb0490dcee32cc1f3032bee7cc9aa620a3ed880d113`; [the summary](maturity-map-query-2026-11-03.json) also retains an unsuccessful lateral-join alternative (948.843 ms). The workaround changes the planner setting only for this query and restores it afterwards; request timeouts, bounds, filters and retries are unchanged.

The related test attempt first had 45 passes and 15 setup errors because initdb could not write its WAL on a full disk. After removing this task's stopped, reproducible benchmark clusters and completed test fixtures, the same group passed all 60 checks (19.53 seconds), without a code or assertion change. Failure logs and cleanup records are retained.

The unchanged 80-request reference map benchmark then passed on `1b2ef2a` (runtime `d7ca007`), with zero retries and the background indexer active. At 1,000 messages, 200/500-node p95 was 61.753/194.186 ms; at 10,000 messages it was 126.275/261.066 ms. The report records completion and service shutdown. [All raw samples](maturity-map-success-2026-11-03.json) are retained alongside the earlier failure. This measures bounded local HTTP maps during indexing, not browser rendering, semantic recall or total storage capacity.

The same candidate also passed 25 shared-lock, semantic-read and recovery-erasure tests directly against the installed macOS PostgreSQL 16.2 database (10.30 seconds), with the API service and background worker stopped. [Source and test metadata](maturity-native-pg16-locks-2026-11-03.json) are retained. This supplements the earlier full suite's PostgreSQL container coverage.

A later plain materialized-dependency CTE was also compared on the retained 10,000-message fixture. It took 1,696.260 ms, versus 1,357.966 ms for the original and 26.547 ms with nested-loop joins disabled; all returned the same ordered 500 rows. The fast plan was a merge join. This unsuccessful alternative is retained in [the SQL evidence](maturity-map-cte-query-2026-11-03.json). Larger brains have not been accepted by these runs.

## Second CPU follow-up

The four changes through `df6f662` remove copies of values that are immediately serialized, specialize stored JSON copies, encode plain action responses directly with a fallback to FastAPI's encoder, and save recall traces after validating the response that contains them. Independent review found that the copy helper reused non-JSON dictionary keys, which broke alias preservation when one key was also a value. A regression failed before the correction and passed afterwards. The string-key fast path remains; context budgets, candidates and validation contracts are unchanged. The combined API, trace, context, retrieval, shared-read and erasure group passed 156 checks, none skipped (21.85 seconds). These checks do not establish a concurrency-performance pass.

The unchanged reference benchmark on `efb0f6e` measured serial/one-brain/eight-brain p95 of **181.45/1,259.91/1,335.98 ms**, with medians 163.81/1,059.29/1,077.47 ms. All 340 responses were nonempty. Both concurrency targets still failed, so the process exited 1; the service was independently confirmed stopped. Settled 200/500-node map p95 was 10.54/14.23 ms, without errors. [Raw samples](maturity-cpu2-performance-2026-11-03.json) are retained. These measurements improve on the earlier CPU candidate but do not pass R5.

## Evaluation stop-rule follow-up

Independent offline reproduction found that a cap refusal did not persist a shared stop: after another request settled, a later reservation could proceed. The monetary bound held, but this contradicted the plan's stop rule. The fix persists the cap stop under the reservation lock, stops the shared attempt after any refused request, and lets known in-flight usage settle without reopening the run. An idempotent stop handle still refuses every provider request.

A fake-process reproduction also showed that the old runner let P and F continue after E exited 7. The runner now observes failures during the existing launch stagger and completion wait, records the failing arm and original exit code, stops the shared live ledger, then terminates and reaps its active children. SIGTERM unwinds the harness through shared-stop and disposable-service cleanup. The subprocess tests use fake interpreters and no provider connection, including the live-control path. The integrated billing, supervisor and C5 harness group passed 84 checks, none skipped (17.68 seconds); Ruff and Bash syntax checks passed. An earlier check passed all 80 tests but found one import-order lint error; that lint error was corrected and the expanded checks passed. Real-model execution remains unapproved, and the independently reviewed plan still has other open hardening items.

The complete public practice at `98f416d` then passed all 250 checks and strict validity, with no external network call. Both disposable memory profiles were independently confirmed stopped. Its [checker and validity files](maturity-free-practice-2026-11-03/) are retained. This normal path complements the fake-process failure tests; no real host or extraction model ran.

## Third CPU candidate

The source through `9ef6711` reuses exact-value context handles within one recall, checks literal capture once per item, extends the JSON copy to recall documents, and links pure local contract references without changing the published schema. An independent recursive-schema regression compares valid and invalid nested documents with the plain validator. The combined contract/API/budget/context/retrieval/lock/erasure group passed 217 checks, none skipped (27.13 seconds); Ruff and the four launcher/matrix checks passed. The earlier full 6,494-test result predates this source.

On `91271f5` (runtime pin `9d8509c`), the unchanged reference benchmark measured serial/one-brain/eight-brain p95 of **158.31/1,027.26/1,064.27 ms**, with medians 148.99/914.81/932.51 ms. All 340 responses were nonempty. Both concurrent targets still failed, so it exited 1; its service was independently confirmed stopped. [Raw samples](maturity-cpu3-performance-2026-11-03.json) are retained. No recall candidates or context budgets were reduced.

The same pinned runtime subsequently passed the complete Mac installation acceptance: **49 passed, zero failed**, `completed: true`. The basic and companion launcher baselines are unchanged. Fresh install, upgrade, MCP correction/deletion, cross-session recall, restart, installed stub proxy and companion backup/restore/activation all passed. Four installations were independently confirmed stopped afterwards. [Source and check names](maturity-install-mac-cpu3-2026-11-03.json) are retained. No paid or subscription-backed model was used; local embeddings were allowed. This installation pass does not pass R5, R4 or C5.

One clean full invocation at `8d85954`, still pinned to `9d8509c`, then passed **6,521 tests, zero failures and zero skips**, in 776.74 seconds. Required Chromium, Docker, real cached local embeddings and launcher checks were enabled. Source and pins stayed unchanged throughout, and provider API keys were removed. The three warnings were the same deliberate-fork deprecations. This full result includes contract linking, recursive-schema equivalence and the evaluation stop-rule changes; it predates the separate evaluation-hardening branches.

The installed package also matched **157 runtime, web, contract and migration files** byte for byte, with no missing, mismatched or unexpected files. [Hashes and tested dependency versions](maturity-package-parity-2026-11-03.json) are retained. On the same candidate the TypeScript SDK passed **44 tests** and its strict type check. Its OpenClaw wrapper, included in the full Python invocation, required all **7 Node tests** to pass against a real disposable service, with none skipped. [SDK source metadata](maturity-sdk-2026-11-03.json) is retained. These are local engineering passes, separate from unrun real-model behavioural acceptance.
