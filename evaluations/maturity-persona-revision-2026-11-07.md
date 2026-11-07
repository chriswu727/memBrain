# Personality evidence remains bound to the accepted revision

After accepting a personality suggestion, editing its original feedback message reused the same event ID with a newer revision. Personality history then quoted the edited wording as the earlier decision's evidence. The companion graph likewise connected the accepted personality and closed proposal to that later revision. This reproduced both before and after archive restore.

The runtime now quotes a current feedback revision only when it precedes the accepted personality record in the brain's event sequence. Closed proposals apply the same bound at their decision. The companion graph derives feedback edges from these eligible sources. The accepted personality card and decision remain intact; edited or erased old text is not copied into a historical snapshot. A revision made before acceptance remains eligible. Archive restore preserves the required sequence order. No schema, API-field or frontend change is needed.

## Verification

Four history regressions failed on the preceding implementation. Four graph-specific cases independently failed against the preceding installed wheel. Those failures are retained. The current source passes 209 personality, proposal, mood, relationship, graph and privacy checks, including nine revision cases covering acceptance, rejection, changed feedback kinds, restore, and revisions before acceptance.

A real PostgreSQL/HTTP/headless-Chromium journey accepts a suggestion, opens its 3D companion graph, revises one feedback message, reloads the graph, and opens the 3D view again. Both snapshots match all node IDs and typed edge endpoints from the API. Accepted-feedback edges decrease from three to two, the invalid proposal edge disappears, and the accepted casual personality remains. The first browser attempt timed out because the test expected the showcase to remain open across `brain-clear`; the application intentionally closes it. The corrected test verifies closure and reopens through the visible button. A nonexistent SDK method in that initial test was also corrected. The final browser test passes without frontend changes or page errors. This is graph correctness verification, not a hardware-performance benchmark.

The predecessor full Verify run [42372936732](https://github.com/chriswu727/memBrain/actions/runs/42372936732) finished with **7,801 passed, one failed, three warnings**. Its migration fixture used current publication code to seed a pre-026 database, but that writer requires the later `source_han_majority` column. The fixture now inserts old-format assertion/vector rows directly, verifies both are preserved through upgrade, and retains its downgrade refusal and row-policy assertions. Ten migration/schema checks pass. The failed full log is retained; it is not characterized as a passing run.

All nine launchers pin runtime `d84af8de6df189911c6a5c196cc133a2b0015899`. Four pin/matrix checks pass. An initial command named a nonexistent matrix test file and collected no tests; its log is retained alongside the corrected passing run. Ruff and diff checks pass.

The wheel was installed into a separate environment, sharing existing unchanged test dependencies. All **197 runtime inputs** match source. The installed package passes **220 checks in 55.82 seconds**, combining the 209 guards, browser journey and ten migration/schema checks. Its disposable database stops and test profile is removed. This is not a fresh dependency-installation test.

## Delivery status

Full Verify [42375927924](https://github.com/chriswu727/memBrain/actions/runs/42375927924) is running on exact launcher head `0e9fb042a1206b8307b5eca93f1430244bd52e91`. This branch includes the preceding source-diversity and local-query contention improvements plus the migration-fixture repair; it has not been promoted to integration. The current integration head remains `e90a7f52e9b0f4092987fb417bf6858a526f4e91`, whose Verify and Native checks passed. Earlier native and performance results apply to their recorded runtimes, not automatically to this successor.

Build: `ab07bee3e01c7bd12f7972150219d930dd6c01bdf0459d63a1b4182afec1e6e3`. Schema 028 is unchanged. Wheel SHA-256: `18bdba7f89397aacfd7459d808ef5e96fc3b95d7bf2d93bf7d31f8bc36a2eca9`. Public scripts, failures, raw results and integrity hashes are retained in [the evidence manifest](evidence/maturity-persona-revision-2026-11-07/manifest.json). Private profiles and dumps are excluded.

No paid provider, subscription behavioral evaluation or new held-out evaluation ran. R4 remains failed and C5 incomplete; main merge, tagging and release remain frozen.
