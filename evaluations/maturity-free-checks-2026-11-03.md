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

Machine-readable checker reports are in [maturity-free-practice-2026-11-03](maturity-free-practice-2026-11-03/). Raw failed logs and complete public-practice run artifacts remain in this task's local evidence directory.

The new validity command rejects every reported harness degradation, malformed event evidence, missing/duplicate/out-of-order turns, mixed run identities and an empty run set. Invalid runs retain their JSON report and exit nonzero. Ten synthetic regressions failed on the earlier validator. No historical evaluation result was changed or re-scored.

## Still required

- Finish and independently validate the concurrent-recall/map performance change. Repeat the browser checks as part of the final candidate CI.
- Freeze and pin one combined source, then run Verify and the full installation acceptance on that candidate.
- Independently review and freeze the real behavioural acceptance plan and held-out scenarios. Obtain the owner's explicit approval for paid and subscription-backed evaluation, then pass R4 and C5. No such run has started.
