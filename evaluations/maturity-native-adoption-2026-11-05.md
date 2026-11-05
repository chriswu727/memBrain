# Default native engine adoption — 2026-11-05

The ordinary desktop/plugin lifecycle now uses the qualified PostgreSQL 16.15 / pgvector 0.8.6 bundle. The API can start only after durable engine admission, application initialization and recovery reconciliation. Five-platform qualification passes eleven ordinary startup/backup/recovery journeys, including two Linux root journeys. This is a product integration milestone; publication remains frozen.

Runtime and all nine host pins: `f441e4abdad55a0959be7071e799b429a3629a93`. The pin/documentation commit is `233f2cfc44c889f998f67299507b241f8485424c`, with the same runtime. [Evidence manifest](maturity-native-adoption-2026-11-05/manifest.json). This builds on the [internal transition controller](maturity-native-transition-2026-11-05.md).

## Resulting behavior

Previously the qualified native transition was an internal component; ordinary startup still selected pgserver's PostgreSQL 16.2. The default selector now prepares the checksummed 16.15 bundle and its packaged vector overlay. Availability checks do not extract a cache, and failure to prepare the target never silently selects the legacy engine.

Before starting an original database, `native_adoption` saves a private handoff outside the replaceable Python environment. It binds profile identity and ports, exact data/log paths and service account, the target manifest, the preserved original engine commitment/version and the original cluster identifier. A stopped legacy source requires clean PostgreSQL control data and a matching last recorded startup version; missing, unknown and newer source versions fail closed. The live source's authenticated SQL identity is checked before transition creation. The handoff precedes the profile fuse and any source start.

Adopted embedded profiles persist `native_engine: "16.15"`. The new loader accepts older profiles; Docker and unadopted profiles retain their previous serialization. The actual frozen `9f75361` loader rejects the new field, so a cached older runtime cannot reopen an adopted profile. The ordinary upgrade preserves installation/brain/tenant/principal identities, ports, passwords and cognition settings.

The stable transition journal takes precedence over filesystem location heuristics, including a temporarily absent data directory during recovery promotion. Initialization whose cluster identity has been recorded cannot recreate a missing cluster as an empty brain. The API port and supervisor lock block first adoption while a service is active. The existing controller still owns immutable original snapshots, catalog/vector repair, guarded pre-admission rollback and irreversible admission; an already admitted restart stays on the target engine.

`desktop._prepare_database` now calls the controller around application bootstrap. A first transition checks schema compatibility on its original running source before native catalog mutation. A recorded transition prepares its target before the schema check, which also handles a stopped admitted database. Application migration, brain initialization, deletion/recovery authority reconciliation and controller verification finish before `_launch`. The profile is reloaded before launch. Direct desktop/client entry points require an admitted native journal, and status cannot report a pending native service as ready.

MCP handoff from a uv cache now probes the installed tool's exact build identity with an isolated interpreter. A stale, missing or unresponsive installed runtime cannot receive the MCP process or mutate its profile. A mismatch exits with an actionable message on stderr; the tool and MCP source must be updated together. No automatic handoff to an incompatible older version is claimed.

The CPython 3.12 `embedded` extra retains pinned pgserver 0.1.4 binaries as migration input on the supported legacy platforms. They supply the original engine if an earlier uv installation has already been replaced. Normal application startup selects 16.15. This is **not** a claim that the package contains no old PostgreSQL binaries; the compatibility input and preserved rollback engines remain on disk. Linux ARM64 uses the new bundle and has no claimed legacy pgserver-wheel upgrade path.

## Actual qualification

[Final five-platform run](https://github.com/chriswu727/memBrain/actions/runs/42021276190) at `233f2cf` is terminal success:

| Platform | Guards | Ordinary adoption/recovery journeys |
| --- | ---: | --- |
| macOS ARM64 | 222, zero skips | Fresh + legacy 16.2 |
| macOS Intel | 222, zero skips | Fresh + legacy 16.2 |
| Windows x86_64 | 212, zero skips | Fresh + legacy 16.2 |
| Linux x86_64 | 222, zero skips | Fresh + legacy 16.2 + root under the original legacy account/path |
| Linux ARM64 | 222, zero skips | Fresh + root |

Each of the eleven journeys uses a real installed package and ordinary `desktop.start`, deliberately exits a child with code 87 after durable handoff/fuse, retries from that state, verifies 16.15/0.8.6 and preserved identities, writes a memory through HTTP, stops and cold-restarts, then recalls it. Each also takes a private backup, restores into quarantine, verifies that quarantine blocks the API, explicitly activates the new recovery epoch, starts through native admission and recalls the restored memory. Restored credentials rotate. Legacy journeys preserve 1,000 vector rows and their nearest results. All eleven result documents record completion, zero model calls and closed owned ports. The component cache, SQL maintenance, cold snapshot, guarded rollback/admission and Linux ZIP64 journeys also pass in the same run.

Separate root repair runs at `f441e4a` also pass: [Linux x86](https://github.com/chriswu727/memBrain/actions/runs/42020891911), [Linux ARM](https://github.com/chriswu727/memBrain/actions/runs/42020895083). They are additional evidence, not extra independent product cases.

Local checks:

- 337 native/profile/lifecycle checks pass. Three actual fresh database tests were explicitly deferred because of local disk limits.
- 55 host unit checks pass with five real database tests explicitly selected out by their decorators; two installation-pin checks pass. The seven focused handoff checks are included in those 55, not added again.
- The existing admitted M4 fixture uses its nondefault `snapshot-restored` data directory through ordinary start, HTTP observe, stop, cold restart and HTTP recall. All 1,000 existing vector fixture rows remain; all other profile fields remain unchanged. The actual frozen old profile loader refuses the adopted configuration. Owned ports close afterward. This is a forward restart proof, not a fresh installation proof.
- An isolated build probe using the real current interpreter succeeds. Ruff, lock consistency and diff checks pass. Local verification input hashes remain unchanged through each frozen run.

Full application CI at `233f2cf` is tracked separately: [Verify](https://github.com/chriswu727/memBrain/actions/runs/42021033658). Its result is not inferred from the native matrix.

## Packaging and disk limitations

Source, wheel and source distribution have identical contents for **179 runtime inputs**, including **12 native resources**, and the same build/schema identities. The wheel builds directly from source. The source distribution also builds and its runtime inputs match individually; the combined local wheel-from-sdist command failed under disk pressure and is not labeled successful.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `membrain_ai-0.1.0-py3-none-any.whl` | 12,859,445 | `f07d70339a83ac3b49566c59bfed47f025eaf130ba5fe986d3c9c3066b8362b1` |
| `membrain_ai-0.1.0.tar.gz` | 14,667,597 | `fe3dbbceb34ee3114b78956ed4fcc906c768944644d0420837a110890c21d1dd` |

Local isolated uv installation of that wheel **failed with ENOSPC**. Python ensurepip succeeded, but a separate offline pip installation also failed with ENOSPC. The partial environment is unqualified. It is not an installed-wheel success. The five-platform ordinary journeys above execute CI's installed package; a clean current pinned uv installation still needs its own complete qualification. The earlier candidate's 49/49 installation result is not transferred.

Disk recovery only replaced 1,477 byte-identical public engine files with independently writable APFS clones, sharing 42,280,640 logical bytes. Every replacement preserves content and has one link; no packages, models, profiles, journals, snapshots or private archives were deleted. No owned PostgreSQL data was found in the failed local host test tree: engine preservation failed before a handoff/cluster was created, and partial copies remain preserved. Available space is still very limited and fluctuates; the snapshot reserve is not bypassed.

## Retained failures

- Initial Ruff reported one import ordering finding, which was corrected. The initial scoped unit run passed 175 checks; subsequent expanded runs passed 334, 335 and finally 337.
- The first real default restart tried schema preflight before starting an admitted stopped database and failed `database_unavailable`. The fixture stayed stopped with data preserved. The ordering fix has a regression test; the subsequent real restart proofs pass. The v2 JSON filename contains the final v3 replay result; the separate v2/v3 logs preserve both invocations.
- A broad local host selector accidentally included real database tests despite the disk constraint. The resulting run has **2 failed, 49 passed, 3 deselected and 6 errors**, plus two cache-write warnings, including engine-preservation and spool ENOSPC errors. Its original output is retained. The later 55-pass unit selection does not turn that failed run green.
- [Initial matrix at c166fee](https://github.com/chriswu727/memBrain/actions/runs/42019426316) is overall **failure**. All three macOS/Windows jobs pass; both Linux jobs complete their ordinary user journeys but fail the new root journey because the harness points root at the ordinary user's private cache. Owner checks correctly reject that cache. The root cache is now separate, and later matrices pass. The harness no longer attempts to stop an already closed, never-started database and mask the primary setup exception.
- Local `build --no-isolation` failed because hatchling was absent from the development environment. Isolated uv built the sdist but its wheel step hit ENOSPC; a direct wheel build passed. An external parity helper initially imported a deliberately deleted private `_MANIFEST` value, then correctly used the public `package_manifest` API. The failed isolated uv wheel installation remains recorded.
- The redundant automatic native rebuild was superseded by the dispatched qualification of the same source with the already checksummed native inputs. A canceled duplicate is not a passing check and is not included in the result table.

## Remaining publication gates

Do not merge the default branch, tag, publish to PyPI or release this candidate yet. Complete current pinned clean-install/upgrade qualification, finish the full application CI result, and run current-candidate performance qualification after the remaining graph workload is finalized. The earlier `9f75361` 36/36 R5 result remains evidence for that earlier candidate. Real R4/C5 evaluations still need their separately approved concrete plan and have not been run.

The 3D structure still explicitly reports working state as not projected; the companion map does not include complete familiarity aggregates. Those gaps and the final independent review remain open. No biological/human-memory equivalence is asserted. No Claude/subagent calls, paid/subscription model tests, Docker restart, schedule, merge or publication were used for this batch.

The evidence bundle contains 116 hashed payloads. An exact-value scan checked 100 payloads against 345 known local credential/DSN values from 72 profiles with zero matches; its summary is included. Fifteen later public installer/storage/CI diagnostics were manually inspected and are outside that exact-value scan count. This is not a general secret detector. Private profiles, databases, journals, snapshots, archives, binaries and models are excluded.

The filesystem subsequently could not create even Git's index lock. A new, verified 128 MiB virtual RAM disk was created; ownership could not be enabled without root, so no private database archive or database removal was performed there. It holds only public repository/package data. Replacing one already incomplete public wheel-install file with a COW copy also failed; its complete, byte-identical original remains in the repository and its verified public RAM copy remains available. Existing working installations, models and private data were not altered. Public evidence is committed and pushed through a temporary RAM Git repository borrowing the original objects read-only; synchronizing the original local checkout still needs free space.

## Full application CI timeout and diagnostic follow-up

Verify42021033658 at233f2cf ended CANCELLED at its45-minute job limit. Pytest reached14% and reported four C5 local-memory fixture setup errors after approximately600seconds each; it never emitted a full-suite summary. TypeScript/typecheck/build steps did not run. This result is not green. The existing harness caught every DesktopError and waited as though each were a slow service start, hiding permanent startup errors. Six zero-model unit guards reproduce five failures/one pass before narrowing the retry to service_start_timeout, then six passes afterward. The original error object is re-raised immediately for permanent failures; genuinely slow startup still waits. A five-minute early deterministic service-start diagnostic will expose the actual remaining startup error before another full-suite wait. This is a test-harness diagnostic change; it does not establish that the underlying service startup failure is fixed, does not change the179 runtime inputs or pins, and does not run an approved real C5 model evaluation. The first local attempt also failed before collection because the root filesystem had no usable temporary directory; the subsequent red/green checks use the public RAM volume for pytest temporary files.

Ruff initially could not create its cache on the full root filesystem; the no-cache check of both changed harness/test files passes.

The narrowed startup retry exposes the actual early failure in Verify42029073879 at060dae0: the zero-model real service fixture errors in1.98seconds with embedded_database_dependencies_missing from native_bundle._versions. The ubuntu-latest host cannot load at least one supplier tool. Earlier successful Linux native matrices use ubuntu-22.04; compatibility with the newer host is not established. A failure-only diagnostic now checks the supplier checksum, extracts it in the CI temporary directory, and prints each tool return code/loader message and ldd result. No host fallback, test skip, timeout increase or native version downgrade is introduced. The exact missing library still needs the diagnostic result.

Verify42030170096 atd77388e remains FAILURE, but its loader diagnostic completes: the hosted runner is Ubuntu26.04.1; postgres exits127 because libxml2.so.2 is missing, and ldd marks that exact soname not found. pg_ctl,initdb,pg_dump,pg_restore,psql andpg_config all report16.15 successfully. The [official Ubuntu26.04 file list](https://packages.ubuntu.com/resolute/all/libxml2-16/filelist) supplies libxml2.so.16/16.1.2 instead. This is an actual Linux host ABI gap; installing the current package alone does not establish compatibility with an older soname. The Ubuntu22.04 matrix results remain valid for their hosts and are not generalized to26.04. The packaging/runtime compatibility fix is not implemented yet.
