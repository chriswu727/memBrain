# Worker cleanup and projected-node interaction closeout

Runtime `174bc506595e9f96e4c38b0c10f737c7f98c639a`; launcher source `3f8a374f91c8724eb1c1784e9cb6d10ef09a4e52`. Publication remains frozen pending full current-source CI, installation journeys, R4/C5 and final review.

## Changes and independent review

Failed-start cleanup now saves the process-pool manager reference before shutdown clears it, terminates/kills workers as before, then drains the manager. This prevents cleanup from reporting completion while manager-side reaping is still active. Tests require the manager and children to be gone and a subsequent pool to work, including one and four permanently blocked initializers. Existing failed-start assertions are retained.

2D projection loses the depth dimension and can place one node over another's click target. The layout now assigns the nearest unused 24-unit cell in stable ID order. The 693 in-viewport cells accommodate the API contract's maximum of 500 nodes, with clearance for the maximum nine-unit radius and stroke. This changes display geometry only: real node/edge identities remain intact and 3D positions are unchanged. Tests reproduce the exact colliding IDs, check all pairs at 500 nodes, exercise real pointer clicks with privacy/date assertions, and confirm deterministic ordering and unchanged 3D positions.

A separate failure came from a 3D test assuming an individual node was always visible from the initial camera angle. The helper now rotates using actual mouse drags when the node is occluded, then still requires a genuine pointer hit on that exact node. A fixed 24-node probe confirms an initially occluded node is reached by rotating, with a changed camera view, the exact selected ID and no page errors. No forced click or direct selection bypass is used.

Codex wrote and tested the changes. An independent Claude CLI review completed in eight turns, with repository-read-only tools and no Desktop/browser tools. Its lifecycle/projection diagnoses and blocked-initializer test suggestion were useful. Its proposed process patch was not copied: it reads worker/manager references after shutdown has cleared them. Its bounded pairwise layout suggestion also did not guarantee separation or viewport bounds. The review and Codex's source-backed assessment are preserved; review output is not treated as proof or a test result. The owner's active Claude window must never be inspected or operated.

## Local verification

The initial manager-drain regression failed on the old implementation (one failed, four passed). Both deterministic projection cases failed before the fix. The focused corrected groups passed 41 worker/startup checks and seven projection/view checks. The expanded database/browser group initially had one failed, 118 passed and 21 errors: the driver omitted the migration credential, and a 3D target was legitimately occluded. The corrected driver retains the application role for requests and uses the migration role only for migrations. After fixing the interaction helper, all **140 checks pass in 72.10 seconds**, zero skips, with input hashes unchanged and owned ports closed. The original failures are retained. Ruff and whitespace checks pass; both launcher-pin checks pass.

An abbreviated pin argument was rejected before changing files; the full commit was then supplied and verified. No paid or subscription-backed model behavior evaluation, merge, release or tag occurred. CLI code-review collaboration is separate from behavior evaluation.

## Fullscreen R5 and installed artifact

The unchanged closed/open/open/closed protocol passes **36/36 windows** on this runtime. Every one of **4,080 measured recalls is nonempty**, with zero model calls. The retained eight-brain fixture, normal polling, fresh API per phase and Apple M4 Metal renderer are unchanged. Source/driver hashes are unchanged, all owned ports close normally, and browser error/external-request lists are empty.

| Phase | Eight-brain cycle 1 p95 | Cycle 2 | Cycle 3 |
| --- | ---: | ---: | ---: |
| Closed 1 | 323.08 ms | 412.91 ms | 403.03 ms |
| Open 1 | 266.21 ms | 294.49 ms | 398.97 ms |
| Open 2 | 313.47 ms | 316.07 ms | 336.15 ms |
| Closed 2 | 331.58 ms | 297.22 ms | 309.94 ms |

The worst serial p95 is **271.08 ms** (500 ms bar), same-brain concurrent p95 **603.83 ms** (1,000 ms bar), and eight-brain p95 **412.91 ms** (600 ms bar). Both open phases expose 187 nodes and 71 links; the hardware-rendered screenshots were captured after measurement with animation paused. This is lexical reference-fixture qualification, not real-model quality, arbitrary corpus capacity or universal hardware performance.

A new wheel and source archive build successfully. A separately installed wheel matches all **187 runtime inputs** and source build/schema identities; **44 checks pass in 2.60 seconds**, with unchanged source and installed hashes. Dependencies are reused. The complete launcher install/upgrade/restore journey remains to be qualified for this pin; this focused installed result is not R1 completion.

At evidence capture, previous-source Verify [42124966090](https://github.com/chriswu727/memBrain/actions/runs/42124966090) and native [42124966174](https://github.com/chriswu727/memBrain/actions/runs/42124966174), both at `f26d195`, are still running. Linux x86, Linux ARM and Mac ARM native jobs have completed successfully; Windows and Intel Mac remain in progress. Neither run covers this changed source. The local batch is held for push until the previous runs finish, so they are not canceled mid-verification. New-source CI remains required.

The [40-payload manifest](evidence/maturity-ci-closeout-2026-11-05/manifest.json) retains the independent review, before/after checks, exact performance driver and measurements, screenshots, installed evidence and prior CI snapshots. All payload hashes and compression round trips are verified; exact scans against the three owned-fixture credentials find no matches. This is not a universal secret scan. Earlier failures remain linked from the [transaction-worker report](maturity-transaction-workers-2026-11-05.md).
