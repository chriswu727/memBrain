# Current candidate CI follow-up

Previous-source Verify [42124966090](https://github.com/chriswu727/memBrain/actions/runs/42124966090), head `f26d195`, finished with **two failures, 7,498 passes and three warnings in 2,054.36 seconds**. TypeScript, typechecking and package building were skipped after pytest failed. The first `gh run view --log` download contained only the initial part of pytest output; a direct job-log API download supplies the complete failure details and terminal summary preserved below. The partial download is not used to infer outcomes.

The failures were:

1. `test_failed_start_reaps_workers_and_allows_a_new_pool`: one worker remained alive after failed-start cleanup. The current runtime `174bc50` already [drains the captured pool manager](maturity-ci-closeout-2026-11-05.md); real failed-start and blocked-initializer tests pass locally.
2. `test_api_and_worker_share_factory_lifetime`: the test replaces the configured service with a fake and uses database DSN `unused`, but did not replace the newly introduced transaction-worker lifecycle. Its real child initializer correctly rejected that invalid DSN. The current test now substitutes the runner at the same dependency boundary, retains the configured worker count, verifies startup and shutdown order, and forbids a health check from dispatching a recall. The CLI worker still exercises the same service factory. No production startup check is bypassed or relaxed.

The factory failure reproduces locally before the fixture correction. After correction, the configuration, real recall-readiness, transaction-worker and desktop-startup group passes **62 checks in 1.81 seconds**. Ruff initially reports the expanded import's formatting; after applying its formatting correction, the full `src tests examples` scope passes. Whitespace checks pass. No runtime or launcher pin changes are needed for this test-only correction.

Previous-source native run `42124966174` remains **cancelled**, with four successful platform jobs and Intel Mac exceeding the 30-minute job limit despite successful individual steps. The [separate timeout analysis](maturity-round-evidence-2026-11-05.md) retains that outcome and explains the 45-minute Intel allowance without changing tests or performance bars.

Both old runs are now terminal. The current integration batch is ready for a new exact-source full Verify and five-platform native run. Its runtime remains `174bc50`, already qualified by [36/36 R5 windows](maturity-ci-closeout-2026-11-05.md) and [49/49 real Mac launcher checks](maturity-transaction-install-2026-11-05.md). Those scoped results do not establish the new full CI, R4/C5 or release readiness. No merge, tag, release or model behavior evaluation occurred.

The [five-payload manifest](evidence/maturity-ci-followup-2026-11-05/manifest.json) preserves the complete public CI job log and metadata, local before/after outputs and final Ruff output. Stored/original hashes and gzip round trips are verified.
