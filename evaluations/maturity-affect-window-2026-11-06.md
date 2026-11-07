# Valid affect windows under unresolved inference load

Runtime `5048e13090202d3dd201227429d4d4cde66bd180` repairs a public-path defect in affect selection. Previously, the newest 501 raw records were selected before validating their evidence. A newer group of pending inferred feelings could hide an older supported feeling, report an empty complete result and incorrectly return mood to baseline. Even one pending record could hide the overflow indicator for 501 supported feelings.

The reader now scans by descending sequence in fixed batches of 256 raw records, collecting valid records until its requested window is full or history is exhausted. Reset boundaries and excluded archive imports are filtered before paging. Existing evidence validation, source privacy, ID selection and lock semantics remain intact. The 500-record public result still uses one additional valid record to determine completeness. This is an output window, not the storage capacity.

An intermediate implementation shrank batches to the remaining valid count. That could issue one query per pending record while seeking the last lookahead record. A regression reproduced that problem at the 21st query; fixed-size batches now satisfy the query budget, exact ordering and overflow checks. No arbitrary raw scan cap can silently turn an incomplete search into a complete result. Work still scales with the invalid history that must be examined; this change does not establish a constant-time or arbitrary-capacity guarantee.

## Verification

Both original public-path regressions failed on the predecessor runtime and pass after repair. The final source passed **257 related tests** across affect, mood, relationship, lifecycle, note workflow and graph behavior. A separately installed wheel passed **36 tests** and matches all **187 runtime inputs**. Only `affect.py` differs from the preceding runtime's package inputs. Full-source Ruff and both launcher-pin checks passed. Independent code review completed without remaining findings.

The installed build identity is `ecf661c042ee08cade66bec70690d44324d6799ea6c9ffbe133b84d3a9a92959`; the schema identity remains `e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`.

A disposable synthetic fixture contained 500 supported feelings, 200 completed plans, 200 shared moments and 501 newer pending feelings; every tenth supported source was sensitive. The predecessor incorrectly returned zero feelings. The installed repair returned all 500 with `complete=True`. Its first affect read took **63.52 ms**, with **58.42 ms warm p95** over 20 further reads. Mood took **154.07 ms first / 154.62 ms warm p95** and exposed no private reasons; relationship took **19.35 / 18.97 ms**. Each SQL statement had a three-second deadline. Autovacuum was disabled only on the disposable event/dependency fixture tables. All readers completed, the database stopped and its temporary profile was removed.

These timings measure restored correct work, not a speedup against the predecessor's incorrect empty result. They are direct service measurements, not the canonical recall/3D R5 protocol, semantic quality evidence or longitudinal personality evidence. Ordinary graph sampling has a separate preselection path; this repair does not claim to eliminate every graph sampling limit.

[Raw failures, passing tests, package hashes, benchmark scripts and cleanup receipts](evidence/maturity-affect-window-2026-11-06/manifest.json) retain all results. No model calls or held-out scenario access were used. Fresh full-install and R5 qualification are pending for this runtime. R4 remains failed, C5 remains incomplete, and release stays frozen.
