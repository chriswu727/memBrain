# Companion privacy outside the visible sample

Runtime `d4f0c03689459f84a2e3d25358e74479d1aa2968` repairs sensitive-derived companion nodes when their protected feedback source falls outside the bounded display sample. All nine launchers pin this revision. **85 PostgreSQL-backed graph/browser checks and four pin/matrix guards pass, zero skips; CI-scope Ruff passes. Fresh installation passes 49/49 and all 166 installed files match, including small-bound privacy checks. Complete performance recheck and full CI are pending.** Publication remains frozen.

## Reproduction and change

After the [preceding native runtime's frozen qualification](maturity-native-validation-2026-11-04.md), additional graph review finds that companion-map protection is resolved only for source rows remaining after the display limit. An accepted persona can still be visible when the sensitive feedback source is omitted. An external fixture at `max_nodes=2` fails; its 3/4-node controls pass. The one-failure/two-pass log is retained in the preceding evidence bundle.

Protection now considers every requested source ID, independently of how many source nodes and edges can be displayed. The ownership/scope and surviving-sensitive-record SQL predicates are unchanged. Six new combinations of 2/3/4 nodes and 0/400 edges verify masking of label/details/recording time and explicit reveal with the same identities and original timestamps. No storage, recall, ranking, context/cost budget, validation or retention change is introduced.

The final real PostgreSQL graph/browser group passes **85 tests**, including those six cases, with fixed source hashes and closed API/database ports. The original failing external test and later passing group are kept separately. This local repair is subsequent to the native runtime's installation and CI input and does not inherit its release pass automatically.

## Preceding native runtime

Runtime `1ca3cb2`, frozen at source `efc8eb6`, passes 201 local PostgreSQL checks, four pin/matrix guards, Ruff and package builds. Fresh installation passes **49/49**, all **166 installed files match**, and installed API/browser/privacy/boundary checks pass. Canonical p95 is **87.33/428.25/458.26 ms**; complete fullscreen qualification passes **36/36 windows**, all **4,080 recalls nonempty**, worst eight-brain window **471.41 ms**. Its full [Verify run 41947100144](https://github.com/chriswu727/memBrain/actions/runs/41947100144) passes 7,068 Python/50 TypeScript tests, zero skips, strict types, Ruff and builds. Its successful performance does not excuse the later reproduced privacy defect. Earlier failed runtimes and samples remain on record.

## Remaining gates

This repaired candidate needs fresh full qualification and CI. Real R4/C5 remains unapproved; working-state/full-familiarity graph coverage and final independent/privacy/design review remain open. No paid/subscription model call, additional Claude call, schedule, merge, tag or publication is performed.


## Current qualification: canonical passes; fullscreen execution incomplete

Frozen source `7f2c5fee252286fcd61572ed379280d4e46b7e63`, pin `d4f0c03`, passes fresh canonical recall: **88.17/466.84/427.23 ms** p95, all 340 recalls nonempty; map 200/map 500 p95 is 11.09/14.36 ms. Source hashes stay fixed and both ports close.

The complete fullscreen attempt exits1 and its application report explicitly has **completed=false, passed=false**. The first three phases finish with no failed windows; the fourth closes its blank page unexpectedly during the first same-brain concurrent workload. Playwright reports `TargetClosedError`; the page-close event is recorded with `expected=false`. There is no recorded page-crash event. The owner confirms manually closing that blank window. The wrapper's completed=true means the child command returned, not that qualification completed. All six ports close and source/driver hashes remain fixed. No full R5 pass is claimed from these partial samples or the preceding runtime's success.

Both finished open phases use actual Metal rendering,185 nodes/66 edges matching the API, normal page polling and visible frames 1,680/1,683; screenshots are inspected. That visual evidence does not complete the interrupted workload protocol. All samples and failure logs remain preserved. The original interrupted run remains preserved. A fresh full recheck begins after the functional installation checks, with only a descriptive document title on the otherwise blank page and unchanged workloads, warmups, limits and release bars.

[Current Verify 41949997913](https://github.com/chriswu727/memBrain/actions/runs/41949997913), job `126991429673`, is running for source `7f2c5fe`; migration/Ruff pass and Python tests are executing, TS/types/build pending. Publication remains frozen.


## Repaired installed package

The unchanged release checker passes **49/49**, zero failures. The actual installed interpreter verifies **166 exact files**, no unexpected files or mismatches, and directly repeats protected-feedback masking/reveal at 2/3/4 nodes with zero displayed edges. These installed checks pass. Three recording-time privacy paths, live boundary refresh, both graph layers/fullscreen/2D also pass; no page or outside-request errors, stop0, screenshot visually inspected. All five owned installation profiles have both API/database ports independently checked closed. The companion-source fix is therefore present and effective in the installed distribution, not only the development checkout.
