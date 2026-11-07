# Month precision in plans and commitments

Typed notes already accepted month-only dates such as `2028-02`, and the memory page kept that precision. The host context and relationship calculation instead converted them to the first day of the month. A February commitment therefore became missed on February 2; Coming up invented a February 1 date; and cancelled plans lost their protective priority before the month ended.

Date comparisons now use the end of the month when deciding whether its date has passed, including leap years. Coming up checks interval overlap with its existing 14-day window, preserves the original month, and explicitly says the day is unspecified. Open commitments cannot be marked missed or acknowledged until the whole month has passed. Cancellation priority lasts through that month. Exact-day behavior, explicit done/cancelled status, time-zone conventions, budgets and storage remain unchanged. Tool descriptions now explain the already-supported month form so a host need not invent a day. No schema or frontend change is needed.

## Evidence

The original code failed 13 of 14 new tests, including original and archive-restored commitments, both `due` and `occurs_at`, month boundaries, a leap day, and cancellation priority. One far-future case already passed. After the fix, a first selected run had 41 passes and two test failures: those assertions incorrectly rejected the legitimate current date in the context header. They now inspect the plan's own line; both the original baseline and that test-authoring failure remain in the evidence.

The complete relevant source group passes **154 tests in 39.44 seconds**, covering typed notes, relationship lifecycle/privacy, affect and mood as well as the new precision cases. Ruff across source/tests/examples and the diff check pass. All nine launchers pin runtime `f5e265c262b66e0c4f3ddb58a079c6fa14e625a4`; four installation-pin/matrix checks pass.

An isolated wheel installation matches all **197 runtime inputs** and passes **43 checks in 11.59 seconds**, covering the precision regressions, typed-note host integration and relationship source privacy. Its database stops and disposable profile is removed. Unchanged test dependencies are shared with the existing test environment; this is not a fresh dependency-installation test.

## Status

Full Verify [42376625930](https://github.com/chriswu727/memBrain/actions/runs/42376625930) is running on exact launcher head `4dc274c995d15223f904277389f2b52975964bee`. This successor contains the source-diversity, local-query contention and personality-revision changes and the legacy migration-fixture repair. It has not been promoted to integration. The integrated cache candidate remains `e90a7f52e9b0f4092987fb417bf6858a526f4e91`, with Verify and Native checks passed. The [current installed qualification](maturity-month-qualification-2026-11-07.md) now passes all 49 launcher checks, 197-input parity in both homes and the full 36-window visual/performance protocol; five-platform native qualification also passes, while full Verify remains pending before promotion.

Build: `f000dd0c0b0a431d2ca20a7add9304acfd8f6e0da9f46395f6588496ebabb52f`. Schema 028 is unchanged. Wheel SHA-256: `5cb3a4257eb4d0cf3b10c3921431998241864a2e47cbf8b4f64942092e1f2438`. [Raw evidence and hashes](evidence/maturity-month-precision-2026-11-07/manifest.json) exclude private profiles and dumps.

No paid model or subscription behavioral calls were made. These are public development checks; R4 remains failed and C5 incomplete. Main merge, tagging and publication remain frozen.
