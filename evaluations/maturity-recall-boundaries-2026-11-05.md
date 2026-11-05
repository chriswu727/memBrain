# Recall boundary projection and retained performance failures

Runtime `edb67078ff629e44861fbdf6a467574852fd4d58`, frozen at source `215f8be38ae56e43588f4ce1157573537a37bcef`, adds an authenticated boundary-only relationship read. Host recall previously computed familiarity, shared moments and commitments just to obtain current topic boundaries. It now reads the same relationship records and reset state under the same brain lock, without those unrelated aggregations. It does not cache boundaries, change retrieval ranking or reduce context budgets. Older services fall back on 404/405; other errors and malformed responses stop recall.

Build identity: `93c19d1ae5ea32f39d908fb4c7eee8929e6f7344d6cf8285de57b314ca33ee4c`. Schema remains `e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`. All nine launchers pin the runtime above.

## Verification and measured effect

The relationship, Python client and host groups pass **130 tests, no skips**, including current and older-service MCP recall, add/remove/reset, restored boundaries, ownership and authentication rejection, failure propagation and prevention of history aggregation in the new read. Both installation-pin guards pass; Ruff and diff checks pass. An initial command named a nonexistent test file and ran no tests. The first actual group had **one failure, 138 passes and three skips**: its mock MCP transport returned an unrelated success body for the new route. The mock now explicitly covers both current and older services. Three unrelated database-dependent context tests skipped in that first invocation are not represented as passes in the final 130-test group.

A full HTTP host-recall comparison uses the existing owned eight-brain synthetic corpus, 1,000 messages per brain, in **before/after/after/before** order. Each phase includes serial, eight callers of one brain and eight independent brains. Each worker makes 21 calls, discarding only its first timing sample: **1,360 measured nonempty recalls**, plus declared warmups. The returned context hashes match across all phases for **160 distinct brain/query pairs**. This comparison changes only the host's choice of boundary reader; both sides use the current API runtime. It is not a comparison between complete historical installations.

| Independent-brain workload | First before | First after | Second after | Last before |
| --- | ---: | ---: | ---: | ---: |
| Median ms | 387.87 | 354.64 | 369.39 | 406.46 |
| p95 ms | 480.96 | 391.23 | 530.25 | 588.24 |

The medians improved in this comparison; tail latency still varies. There was no browser in this experiment, so these numbers do not qualify fullscreen release performance. Actual recall traces are written normally; the retained corpus is not a pristine pre-experiment snapshot. Source and driver hashes remain unchanged during each run, and all owned ports close afterward.

## Full fullscreen protocol: failed

The existing closed/open/open/closed driver is reused, changing only its output directory and runtime identity. Each phase starts a fresh API; each has three cycles and all three canonical workloads, with normal page polling. **31 of 36 latency windows pass**, all **4,080 measured recalls are nonempty**, and the run exits **1**. Failed windows are:

| Phase | Zero-based cycle | Workload | p95 ms | Bar ms |
| --- | ---: | --- | ---: | ---: |
| First open | 0 | Eight independent brains | 869.38 | 600 |
| First open | 2 | Eight independent brains | 661.05 | 600 |
| Last closed | 1 | Eight callers, one brain | 1144.17 | 1000 |
| Last closed | 1 | Eight independent brains | 661.64 | 600 |
| Last closed | 2 | Eight independent brains | 721.14 | 600 |

Failures also occur after closing the visualization: this evidence does not establish rendering as the sole cause, and the optimization does not solve the release latency gate. This result does not replace or erase the [earlier failed run](maturity-linux-integration-2026-11-05.md). No unchanged rerun was used to select passing timings.

Both visible fullscreen phases render **183 nodes and 66 edges** matching the API, using the Apple M4 Metal renderer, with 1,987 and 1,616 recorded animation frames. Page errors and page external requests are empty. Both screenshots complete and were inspected. Browser process stderr contains a `DEPRECATED_ENDPOINT` registration message; this is not a claim of an entirely empty browser log. All owned ports close, and all frozen source, test, launcher and driver inputs remain unchanged. These checks do not close the missing working-state and complete familiarity projections.

## Rejected optimization and previous CI

A bounded per-request lexical score cache was implemented and tested, then removed because a read-only candidate-collection ABBA comparison showed no consistent benefit. Its patch, baseline, samples and 99 passing focused tests are retained separately. Exact candidate documents, order and rank signals matched for 96 distinct brain/query pairs; that equivalence did not justify keeping an optimization without demonstrated benefit. None of that rejected cache remains in this runtime.

The preceding runtime `11eee62`, at immutable source `d23a4bd`, now has [successful full CI](https://github.com/chriswu727/memBrain/actions/runs/42088118987): **7,362 Python tests passed**, three warnings, **50 TypeScript tests passed with zero skips**, TypeScript type checking and wheel/sdist builds succeeded. Its [five-platform native matrix](https://github.com/chriswu727/memBrain/actions/runs/42088113547) also succeeded; build-only jobs were intentionally skipped. Those CI results apply to that preceding source. [Current Verify](https://github.com/chriswu727/memBrain/actions/runs/42093439325), dispatched at exact source `215f8be`, is pending at this checkpoint. No new native matrix was dispatched for the boundary-only change.

## Evidence and remaining work

[Evidence directory](maturity-recall-boundaries-2026-11-05/) contains raw samples, drivers, rejected changes, failed and passing local outputs, screenshots and previous CI logs/metadata, with a SHA-256 [manifest](maturity-recall-boundaries-2026-11-05/manifest.json). The exported bytes were checked against the owned benchmark profile's known credentials; no matches were found. This is not a universal secret detector. The evidence diff check initially rejected trailing whitespace in a raw failed-test log and the rejected patch; both exact byte streams are now gzip-compressed, with decompression equality checked. Tests use no paid or subscription model calls. The existing synthetic database is reused rather than copied into another installation.

Current performance acceptance, remaining installation/host coverage, real R4/C5 behavior, working-state and complete familiarity projections, and final independent reviews remain open. The next performance investigation must distinguish core request CPU/serialization and database waits from visualization load; another small cache or an unchanged timing rerun is not justified by these results. Release remains frozen: no merge, tag or publication.
