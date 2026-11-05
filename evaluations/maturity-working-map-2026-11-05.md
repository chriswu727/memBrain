# Persisted working memory in the brain views — 2026-11-05

Runtime: `491a592e32fc7325c1ed152f0e8f7d1a6a15322b`. Launcher/source commit used for fullscreen measurement: `c295f539702832008d1d83d83c01b48c29f60cdf`. Build ID: `5360a592d94575d28b3b0453e1fb82b750feb933f16d9caf13bad1b347c0f535`. Database schema is unchanged (`e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`). Publication remains frozen.

## What changed

The memory graph now reads actual persisted `memory_working_states` records. It projects the stored state version, items and open loops, with membership edges and evidence edges validated against the currently visible source revision, content hash and span. An empty/default state is not invented as a neuron. Unknown values have no invented evidence; inferred values remain labelled inferred. An expired item is visibly expired, and a past deadline never changes a planned loop to completed.

The same API nodes and edges reach the 2D view, 3D observatory and fullscreen hologram. English and Chinese details expose scope, revision, knowledge state, expiry, loop status and due time. The working region follows actual links. The light animation remains illustrative, not measured neural or agent activity.

Privacy checks cover direct sensitive notes, shared source material, sensitive descendants and sources outside the displayed evidence limit. Hidden evidence cannot leak the state branch label or timestamp. Missing, stale, changed, erased, suppressed or foreign-brain evidence removes the affected child and its links. Export/restore preserves the relationship to valid evidence under the restored brain identity. Reading the graph does not update working state or learning/access state.

The graph is intentionally bounded: state selection follows the graph node limit; state documents over 64 KiB are omitted with `truncated=true`; item text previews stop at 2,048 characters; evidence lookup is capped at 64–1,024 sources. The full records remain stored. Complete relationship familiarity summaries are still not represented, and this change does not claim new working-memory reasoning or human emotions.

## Verification

The final local database/browser group passed **104 tests in 59.19 seconds**, with zero skips: working map, structural map, memory map, companion map, hologram and observatory. It includes real Chromium English/Chinese detail checks and exact API/2D/observatory/hologram topology parity. Source and driver hashes stayed unchanged during the run; owned ports were closed afterward. Two launcher-pin checks and Ruff also passed before this report.

The preceding recall-worker runtime has now completed [full Verify 42100044108](https://github.com/chriswu727/memBrain/actions/runs/42100044108), source `02f1cef`: **7,400 Python tests passed, three warnings; 50 TypeScript tests passed; typecheck and build passed**. This is not full-suite evidence for the new working-map runtime. Its [native qualification 42098895915](https://github.com/chriswu727/memBrain/actions/runs/42098895915) passed all five platforms: macOS ARM64/Intel, Linux ARM64/x86-64 and Windows x86-64. Two build-only jobs were intentionally skipped. No native engine changes were made in this graph batch.

## Fullscreen latency with real working nodes

One synthetic working state was added to the retained benchmark corpus in a separate conversation/branch: two items (inferred goal and unknown attendance) and one planned loop. No existing messages or notes were removed. It contributes four actual nodes and five membership/evidence edges: **187 nodes and 71 edges**, matching the API in both open phases. This fixture change is explicit; the run is not an identical-dataset A/B estimate of graph overhead.

The complete closed/open/open/closed protocol used a fresh production API for each phase, three cycles per phase, normal page polling and the Apple M4 hardware WebGL renderer. All **36/36 windows passed**, with **4,080/4,080 nonempty measured recalls**. The worst individual-window p95 values were:

| Workload | Worst p95 | Bar |
| --- | ---: | ---: |
| Serial | 102.43 ms | 500 ms |
| Eight requests, same brain | 360.99 ms | 600 ms |
| Eight requests, eight brains | 362.81 ms | 600 ms |

Both open phases rendered throughout measurement (1,234 and 1,261 frames); screenshots were taken after measurement with motion paused. Both screenshots were inspected. No page errors or external browser requests were recorded. Source/driver hashes remained unchanged and all owned ports closed. The corpus is eight brains with 1,000 messages each and 100 notes in the first brain, plus the declared working state. No model calls were made. These are bounded reference-corpus measurements, not capacity or arbitrary-device guarantees; prior recall quality/equivalence evidence remains in the [worker report](maturity-recall-processes-2026-11-05.md).

## Failures retained

- The first local group failed **14 tests, with 19 passing** because the new test fixture used invalid time basis `explicit`. It was corrected to the existing contract value `source_explicit`; validation was not weakened. Subsequent intermediate groups passed 33 and 36 tests before the final 104-test group.
- The first seed attempt wrongly required the optional local embedding directory setting to be absent. The desktop registers a provider path before downloading a model. The guard now checks that no actual local model is installed. This failure occurred before starting PostgreSQL or writing state.
- The second seed attempt supplied `span=None` where the evidence contract permits an omitted span but requires an object if present. Validation rejected the state and the transaction did not save it. The final seed omits the optional span.
- The measurement wrapper was mistakenly started after that failed seed. It was explicitly aborted as invalid fixture qualification; its partial samples, commands and termination details are preserved in `visual-aborted-unseeded`. They are neither a performance pass nor a runtime performance failure. Owned processes were stopped and ports checked before the correctly seeded complete run.

## Evidence and remaining gates

The [manifest](evidence/maturity-working-map-2026-11-05/manifest.json) covers 35 payloads: raw timing samples, frozen drivers and hashes, final/intermediate/failed test outputs, seed attempts, aborted measurement, screenshots and preceding CI results. JSON/text/log payloads are gzip compressed with byte-for-byte decompression checked; the manifest records compressed and original SHA-256 hashes. Payloads were scanned against the three exact credentials in the owned benchmark profile with zero matches; that is not a universal secret audit.

Current-runtime full CI, remaining installed/host journeys, R4/C5 held-out behavior acceptance, complete familiarity representation and final review remain open. No paid/subscription evaluations, Claude sessions, release, tag or default-branch merge were performed for this batch.
