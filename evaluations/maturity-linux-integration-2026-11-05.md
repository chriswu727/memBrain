# Packaged Linux XML compatibility and installed upgrade qualification

Runtime `603e0a2e233f6f35f85f73010e370c1e434b164f`, frozen at source `9a17e6cc7eb89e51fa9d5019ff0b9c1c10aa7099`, integrates the [qualified XML candidates](maturity-linux-xml-2026-11-05.md). The [five-platform installed-package run](https://github.com/chriswu727/memBrain/actions/runs/42083489224) passes, including **15 real default-startup, interrupted-adoption and HTTP backup/recovery journeys**. Both Linux architectures run on **Ubuntu 26.04**, where the earlier package failed to load. A separate local Mac test passes isolated pinned uv installation and replacement of an active old installation. These checks do not by themselves qualify release performance, the complete host matrix or real R4/C5 behavior.

The runtime build identity is `99d5c45e20d1e29882a9151107f85b1740c027d09e32d772164c34f00fd55ecf`. All nine host installation pins identify this runtime. The schema fingerprint remains `e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`.

## Existing engine bindings remain intact

Fresh Linux installations receive the verified XML library in their packaged native overlay. An existing transition can continue to bind its exact previous engine manifest. The runtime accepts only the explicitly pinned predecessor whose existing files are all byte-for-byte and mode-for-mode identical to the current manifest; the difference must be exactly the XML library and its four license/provenance files. Arbitrary older or modified engines are not admitted by this rule.

The previous engine directory and its transition journal are not rewritten. Instead, the loader receives an internally constructed path to a separate, verified directory containing only `libxml2.so.2`. Inherited loader overrides are removed. The dependency has a pinned size and hash, strict owner/mode/link checks, a locked atomic publication step, low-space rejection and a repair path that retains corrupt prior entries. Root/service-account installations use a separate root-owned readable cache rather than the ordinary user's private cache. Preflight checks use the same account-specific environment before stopping a working service.

Packaging preserves both old Linux manifests, updates both Linux overlays, and keeps Mac/Windows resources byte-identical. The packaging command requires qualified manifests and independently enforces the exact additive difference. This is a specific compatibility rule for this reviewed predecessor, not unrestricted native-engine downgrade support.

## Actual installed-package evidence

| Platform | Unit guards | Installed adoption/recovery journeys |
| --- | ---: | ---: |
| macOS ARM64 | 267 | 2 |
| macOS x86_64 | 267 | 2 |
| Windows x86_64 | 257 | 2 |
| Ubuntu 26 x86_64 | 267 + 16 Linux dependency guards | 5 |
| Ubuntu 26 ARM64 | 267 + 16 Linux dependency guards | 4 |

The reported test groups have no skipped tests. Workflow build-only jobs are intentionally skipped because the run reuses already qualified candidate binaries. Platform-specific steps retain their explicit scope: legacy 16.2 adoption is not run on Linux ARM, and the large ZIP64 check runs on Linux x86. Those omissions are not represented as passing coverage.

All 15 adoption journeys verify an interrupted handoff, admission before API startup, retained credentials, cold restart and HTTP recall, rejection of a broken loader without stopping the live service, successful verified restart, private backup, quarantine before activation, restored recall, rotated recovery credentials and closed owned ports. The applicable legacy paths also preserve 1,000 vector rows. Four Linux journeys additionally bind the previous manifest, prove the old engine remains unchanged and inspect the actual PostgreSQL process's mapped XML library against the pinned hash, for both ordinary and service-account operation.

Separate component journeys retain SQL maintenance, native snapshots, original-engine rollback and the post-admission rollback barrier. The Linux x86 ZIP64 test handles a 2,147,487,744-byte member with a reported Python peak RSS of 58.25 MiB. This is one bounded-memory snapshot measurement, not a general memory-capacity claim.

Local focused validation passes 156 tests with no skips, followed by both installation-pin guards. Ruff and the diff check pass. Those local counts were observed in tool output; raw logs were not saved. CI logs and structured results are retained in the [evidence directory](maturity-linux-integration-2026-11-05/manifest.json).

## Isolated uv installation and active replacement on Mac

The local driver creates separate tool/bin directories, a new owned download cache and fresh profiles. `uv tool install` resolves the pinned GitHub archives with the embedded and semantic extras. The installed interpreter confirms memBrain, PostgreSQL binaries, ONNX Runtime, tokenizers and psycopg distributions reside inside its own environment. No foreign dependency directory is attached.

The first journey installs the current runtime, starts the service, writes and recalls a synthetic Biscuit memory, then stops it. The second installs `73ee62e`, writes the memory and leaves its service running while uv replaces the actual tool environment with `603e0a2`. The new host detects `restart_required`, automatically restarts to a different service instance, recalls the original memory and preserves the exact profile and native-transition journal bytes. The new build identity and package direct URL match the requested current runtime. Both profiles' ports close, and all 544 frozen tracked inputs remain unchanged.

This verifies real dependency installation and active environment replacement on macOS ARM64. It may reuse the existing verified Mac native cache; semantic model download is disabled and no model calls occur. It does not establish Windows active-environment replacement, every host launcher, a wholly cold native cache, custom-source provenance or semantic first-use acceptance.

## Current-runtime performance failure

The unchanged fresh canonical fixture on `603e0a2` passes: serial/same-brain-eight/eight-brain-eight p95 is **91.07 / 592.29 / 457.44 ms**, with all 340 recalls nonempty. The database is PostgreSQL 16.15 on the ten-core Apple ARM reference machine, Python 3.12.13. Map 200/map 500 p95 is 11.73/15.64 ms. Frozen inputs remain unchanged and both ports close.

The complete closed/open/open/closed fullscreen protocol then finishes with **34/36 latency windows passing**, **4,080 nonempty recalls**, and exit 1. In the second open phase, zero-based cycles 1 and 2 have eight-brain p95 **671.78 ms** and **619.51 ms**, exceeding the unchanged 600 ms bar. A screenshot after the first open phase also times out after 10 seconds; the remaining phases still run. The missing screenshot is not claimed inspected. The second open-phase screenshot is saved and visually inspected.

Both open phases render 183 actual graph nodes and 66 edges matching the API, using ANGLE Metal on Apple M4, with normal polling and 1,788/1,812 advancing animation frames. Page-error and page-origin external-request lists are empty; browser stderr still contains Chromium registration diagnostics, preserved in the raw log. All recorded close events are expected. The driver and source hashes remain fixed and every owned port closes. This is a completed **failed qualification**, not an interrupted run or a reason to select another unchanged green attempt. Prior `9f75361` timings do not supersede it.

Two subsequent diagnostics reuse the owned synthetic corpus, with no browser and no release timing claim. The concurrent attribution run completes 163 nonempty recalls; its 160-request concurrent group uses 8,621.83 ms process CPU, with 5,375.35 ms measured inside recall and 3,109.59 ms inside candidate collection. Categories are inclusive and must not be added. A separate single-request-at-a-time function profile completes 23 nonempty recalls with no negative profiler times. It identifies repeated row decoding, source-unit key serialization, sentence segmentation and access-state computation as candidate inspection targets. Instrumentation adds overhead, and neither diagnostic establishes why the two fullscreen windows exceeded the bar. Both preserve source hashes and close their ports.

## Full CI failure and scoped repairs

[Full Verify at `9a17e6c`](https://github.com/chriswu727/memBrain/actions/runs/42083494088) finishes with **26 failed, 7,205 passed, 124 setup errors and three warnings**, in 1,289.83 seconds. TypeScript checks and package builds do not run after that failure. The successful standalone native matrix does not replace this result.

A local two-test sequence reproduces the scenario-clock leak: the simulated slow-start test passes, then an unrelated startup guard fails because `MEMBRAIN_EVALUATION_CLOCK` still names the preceding test's profile. Deleting an absent environment variable with `monkeypatch.delenv(..., raising=False)` registered no restoration; the harness subsequently wrote it directly. The fixture now sets the disabled empty value, guaranteeing restoration. Production clock refusal is unchanged.

A separate restrictive-umask run reproduces both shared-cache failures. New shared engine/dependency roots requested mode 0755 but inherited 0700 from umask 0077. Runtime `11eee622127dc246c3e7d0af3471832d4dbf405f` explicitly sets permissions only on roots it just created. Existing unsafe or inaccessible shared roots are rejected without changing permissions. Tests cover umasks 0022/0027/0077 and preservation of existing 0700/0777 roots. The scenario-clock, desktop startup, dependency, preservation, adoption, transition, packaging and actual private-message startup group passes **238 tests, no skips**; both current pin guards, Ruff and diff checks pass. Red and green outputs are retained.

All nine pins now identify `11eee62`, with build identity `d07373c29d70fe560ec9ac4dc3f259383e7a69c3027b91ff4e2584bba841d6f6`. [Native qualification](https://github.com/chriswu727/memBrain/actions/runs/42088113547) and [full Verify](https://github.com/chriswu727/memBrain/actions/runs/42088118987) are dispatched for exact source `d23a4bdbc25eab8362b408305eee7fea9d1b5477`; their results remain pending at this report's checkpoint. The earlier performance failure remains open. The local fix does not prove every preceding CI error has been resolved.

## Retained integration failures and remaining gates

The first local integration group had four failures and 118 passes because fake desktop layouts lacked the real layout's `account` field. A focused capture retains four failures and 20 passes. The fixtures now model both ordinary and service-account layouts, and assert the account-specific loader preflight before shutdown; the final group above passes. An import-order Ruff failure was also corrected. The earlier Linux loader failure and all four native candidate build failures remain in the linked reports.

The evidence diff check rejected the Windows JSON reports' original CRLF bytes as trailing whitespace. The exact bytes are retained in gzip rather than normalized, and the failing diff output is retained. The final evidence diff check passes.

Full application CI, current performance acceptance, remaining installation/host coverage, working-state and complete familiarity projection, real R4/C5 acceptance and final reviews remain release gates. No merge, tag, publication, unapproved paid/subscription model evaluation, Claude call, Docker restart or deletion of existing local data is part of this batch.
