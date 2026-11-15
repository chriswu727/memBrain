# Deferred-note source lifecycle: 2026-11-14

Runtime `548674ce18a147b9fae00b547eae5f50dbbcaa69`; launcher pin and qualification source `0b0392bcbedabcf6b262efbdae3f612a556a9688`. [Implementation PR #70](https://github.com/chriswu727/memBrain/pull/70) merged as `13b0e906e0f3d5ecca1e3131803484bebb17c3f6`; its tree exactly matches the qualified source. Local dates use America/Toronto; execution continued into November 15 UTC. [Evidence](evidence/note-source-lifecycle-2026-11-14/local-checks.json).

## Behaviour delivered

An ordinary host note can precede the message that grounds it. Previously, a known old/deleted/undelivered source could also look like a message that had yet to arrive. The note could replace a valid interpretation, remain visible as “waiting”, and contribute a reported feeling or shared moment. A second defect let a note hidden or replaced before source arrival miss the dependency needed to erase its retained body later.

The source resolver now distinguishes an unknown identity from a known but unavailable exact revision. When a producer/key is already recorded, a new note must cite its current eligible original message. A stale, erased (where the identity survives), suppressed, retired, draft, cancelled, non-original or speculative future revision fails with `source_unavailable`. The transaction rolls back without replacing the existing note or storing an affect record.

A genuinely unknown source can still be attached during its host turn. Arrival of the exact eligible revision links it normally. Arrival of a different revision or ineligible record retires the interpretation and its dependent records, invalidates derived material and cached acknowledgements, and removes that note's shared-moment contribution. A later version cannot resurrect the interpretation. The host can write a new note from the new evidence. Independently sourced notes remain available; replacing a note continues to inherit its original privacy dependencies.

Source arrival now also links retained hidden/replaced interpretations for erasure without reactivating them. The erasure relationship survives archive restore and reaches old note and affect bodies. HTTP error handling, recording-revision fences and request idempotency retain their existing contracts. There is no new endpoint, migration, dependency or model call.

## Verification and retained failures

- Before the runtime fix: **9 failed, 1 passed** on the new ordinary-source/arrival regressions. The passing case was the valid exact-arrival/correction/cross-brain control. [Log](evidence/note-source-lifecycle-2026-11-14/before.log.gz).
- Review then reproduced the hidden-history deletion gap in **4 failing cases**, covering replacement/suppression and exact/skipped arrival revisions. [Log](evidence/note-source-lifecycle-2026-11-14/hidden-before.log.gz).
- **21 new lifecycle cases** cover those failures plus HTTP atomic refusal, future revisions, non-original records, idempotent replay, inherited pending references, archive restore and capture-revision fencing after digest-key erasure.
- The final runtime passes **35 focused PostgreSQL tests**, with zero skips, plus **2 installation-pin checks**. Ruff and diff checks pass.
- A broader **95-test lifecycle batch** passed during development, including the fixed-clock memory-evolution scenario and mood/relationship source privacy. It predates the bounded latest-revision query and removal of the rejected index migration, and is not presented as the final-source full qualification. Local batches overlap.
- Full Verify on the exact source passed: **4,105 Python tests, zero skipped, three existing fork warnings; 39 TypeScript tests, zero skipped**, plus Ruff, TypeScript type checking and both sdist/wheel builds. [Run 43669203478](https://github.com/chriswu727/memBrain/actions/runs/43669203478), [metadata](evidence/note-source-lifecycle-2026-11-14/ci-run.json), [complete job log](evidence/note-source-lifecycle-2026-11-14/ci-job.log.gz). The full Python suite took 1,228.46 seconds. The PR code review completed on the same source without findings.

Every local service test froze runtime files, verified they remained unchanged during execution and stopped its dedicated PostgreSQL instance. The task-owned synthetic databases and pytest directories were removed after compact results were retained: [cleanup](evidence/note-source-lifecycle-2026-11-14/cleanup.json). About 1.24 GiB was reclaimed. Source worktrees, real data, profiles, models, backups and the existing Claude remote-control session were kept.

## Performance boundary and rejected optimization

Known-source validation uses one batch of at most 64 identity lookups, each limited to its newest indexed revision. This avoids materializing a source's entire revision history. Arrival still uses the existing JSON-reference lookup, expanded to include retained hidden history. That lookup's cost can grow with the brain's retained events.

An expanded partial GIN index was tried on the same production SELECT, application database role, PostgreSQL 16.15 instance, connection configuration and synthetic data: two matching notes (one hidden) plus 10,000 unrelated notes, half hidden. Both arms used two warmup queries. After owner-run `ANALYZE`, both plans used a sequential scan and filtered 10,000 unrelated rows. Individual `EXPLAIN ANALYZE` executions were 4.863 ms with the original index and 5.314 ms with the proposed one. These are one-query plan observations, not a statistically supported latency comparison or end-to-end performance result. [Plans](evidence/note-source-lifecycle-2026-11-14/index-diagnostic.json).

The proposed migration was **rejected and removed**. Its index-use assertion remains a failed experiment. The earlier harness attempts also remain recorded: an app-role DDL permission error, then incorrectly running `ANALYZE` as that role before correcting it to the database owner. [Review](evidence/note-source-lifecycle-2026-11-14/index-experiment-review.json), [rejected SQL](evidence/note-source-lifecycle-2026-11-14/rejected-expanded-index.sql), [final failed assertion](evidence/note-source-lifecycle-2026-11-14/index-analyzed.log.gz). The retained script is an execution snapshot with the worktree path redacted; it references the rejected migration, not a shipped migration.

No general speedup, storage-capacity improvement, production scale, cold-start result or cross-machine comparison is claimed. The next performance work should measure retained-history growth and find an access path the application role actually uses while preserving erasure of hidden versions.

## Remaining limits

Existing unmatched legacy notes are not swept retroactively by this write/arrival check. Source identities removed to eliminate content-derived digests cannot be reconstructed; delayed writers must retain their captured `expected_recording_revision`. A source can be eligible without the host's interpretation being correct. The same-turn feature still trusts the host's judgement and does not add a second model.

This is engineering evidence on WSL/Linux. Windows-native/macOS and the other native platforms were not requalified for this runtime. No paid or subscription-backed behavioural evaluation ran. **R4 remains failed; C5 remains invalid/unscored; final release review remains open.**

Claude Fable 5.2 was invoked once for ordinary implementation with high effort and returned its weekly-quota limit without starting the work. Codex implemented and reviewed this batch. The repository's configured [automated PR code review](https://github.com/chriswu727/memBrain/pull/70#issuecomment-6888117729) completed on `0b0392bc` without findings; this is separate from behaviour or security acceptance. No Claude implementation is claimed. No AgentDetox work, main-branch push, release or tag is part of this delivery.
