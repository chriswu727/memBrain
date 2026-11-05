# Preserved native engines and root copy integrity — 2026-11-05

Runtime **`8420d0f1f4fb10ccc87b9c73e71241df26f958bb`** adds durable engine copies
and replaces marker-only root copy reuse with full verification. Previously a
path-derived directory was reused whenever `.complete` existed, without checking
its binaries. **Automatic upgrade orchestration remains unfinished.** Default
selection still supplies pgserver / PostgreSQL 16.2; nine launchers pin `9f75361`.

## Behavior

`native_engine_store.preserve` copies already trusted inputs into a separate
content-addressed generation, preserving PostgreSQL's layout and external
`pgserver.libs`, `.dylibs` and `.libs` loader dependencies. A commitment covers file
bytes, paths, normalized executable modes, internal file links and empty directories.
It verifies source stability and the copy, fsyncs files/directories, writes a private
marker and publishes atomically. It does not establish supplier provenance.

Independent verification accepts the recorded commitment without the original
Python environment. Required tools, size and entry budgets are checked on capture.
External, dangling, cyclic and directory links, special files, unsafe copied
ownership/modes, hardlinked output and extra/missing/changed files are refused.
Internal relative file links remain relocatable. Threads/processes serialize.
Damaged generations and failed staging remain preserved; repair publishes elsewhere
without moving running binaries. Changed source or vendor libraries get a new
generation. Private copies restrict access; root copies retain readable/traversable
packaged files for the service account. Windows uses the established TokenUser ACLs.

The root embedded path now selects this verified store. Cluster paths, legacy
locations and accounts stay unchanged. The parent automatic upgrade controller and
nonroot transition have not yet adopted preservation.

## Verification

**233 local checks pass, zero skips**, including 27 engine-store guards and prior
cache/snapshot/SQL/profile/builder checks. Ruff, diff checks and final builds pass.
Tests cover source removal, independent files, generation reuse and damage,
hidden libraries, source mutation, space/publication failure, typed cycle errors,
private/shared access and cross-process/thread concurrency. The first 23 engine
tests pass; first Ruff reports import formatting, corrected before commit. Hidden
library and cycle cases bring the final engine count to 27.

The real harness preserves an original engine from a replaceable source copy,
makes that source path unavailable, and initializes using the preserved engine.
It snapshots, upgrades to 16.15 / vector 0.8.6, changes rows/roles/a second database,
then restores into a new directory and starts the preserved original engine.
Complete rows, roles/password hash, vector/index metadata, nearest results, second
database and custom configuration match. Source states remain preserved during
snapshot/restore and ports close. This is staged recovery, not automatic promotion
or an actual installer replacing a tool environment.

Initial source `307227b` passes all five platforms in
[41997183150](https://github.com/chriswu727/memBrain/actions/runs/41997183150), with
164 Mac/Linux guards and 156 Windows guards. Final cycle handling and CI path
filters pass in
[41998187425](https://github.com/chriswu727/memBrain/actions/runs/41998187425):

| Platform | Final job | Guards | Preserved-engine journey |
| --- | --- | ---: | --- |
| macOS ARM | 127146487397 | 166 | 16.2/0.6.2 upgrade and original-engine staged recovery |
| macOS Intel | 127146487672 | 166 | Same |
| Windows x86 | 127146487653 | 156 | Same |
| Linux x86 | 127146488020 | 166 | Same, ordinary user and root/service account |
| Linux ARM | 127146487702 | 166 | Fresh 16.15, ordinary user and root/service account |

No tests skip. Windows does not collect unsupported Unix link/pipe/shared-mode
cases. Linux ARM has no historical pgserver wheel and makes no 16.2 upgrade claim.
Existing native/cache, injected-host, all-database SQL and snapshot journeys also
pass. The Linux sparse ZIP64 case retains its component-only scope.

The final installed wheel matches **177 runtime files** and twelve native resources.
Its engine-store module verifies the original engine and starts the real restored
16.2/0.6.2 database with the complete SQL fingerprint intact. All **439 source/check
hashes** stay fixed during it. All 177 runtime inputs, including schema/migrations,
match the source archive. Local full recovery predates the cycle-only guard; final
CI runs complete fresh journeys at final source. No full-application or R1/R5 gate
is inherited from these component results.

| Final distribution | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 12,848,101 | `37fd7347b69886d1b6356d404e2317b5f22ca91c3381f38860f6c3d61eab328f` |
| Source archive | 14,644,666 | `1fa98c6349dad2209d688959c6596f868855492b0250a0f6d8865c17b182f2f5` |

## Retained failures and storage

The first actual local initdb fails because the initial copy omits macOS's external
`.dylibs/libpq.5.dylib`. Inspection finds three such files; the copy now includes
them and guards exercise nested hidden-library preservation. The second attempt
initializes, then snapshot space reservation correctly refuses to proceed. It
stops and preserves the database. After storage recovery, an external checker
resumes that exact initialized fixture using the unchanged fingerprint function
and completes upgrade/recovery. Both original failure results remain.

The first final-source wheel build runs out of local disk. Its source archive
completes but wheel creation fails. A premature installed check fails with
StopIteration because no wheel exists. Both logs remain. After storage recovery,
a new full source/wheel build, installed check and source-archive parity pass.
No dependency or space/test gate is weakened.

Identical public binaries use independently writable APFS clones: 6,574 files /
115,837,416 logical bytes verified, no hardlinks or removed packages. Two completed,
stopped owned synthetic PGdata directories are privately archived, every regular
file hashed and ports checked before only those directories are removed:

| Fixture | Files / dirs | Archive bytes | SHA-256 |
| --- | ---: | ---: | --- |
| Prior host-environment fixture | 1,274 / 27 | 6,386,508 | `e0d7babd4dbd745b1347d8c0e7b5ccd547e127be8301168bfac5f0b2f4ef2a4f` |
| Completed upgraded source | 1,580 / 28 | 8,675,460 | `2b097eb486d853f9a8d5ef8407c357318fc14f50e655daa9e0e30c44bbae43d5` |

All profiles, credentials, journals, snapshots, logs, models/packages and engine
copies remain preserved. The restored original-engine PGdata and earlier SQL
maintenance fixture remain stopped and present. The archived upgraded source is
absent: future work must restore or explicitly select the retained staged fixture,
not silently initialize a replacement.

The [33-payload manifest](maturity-native-engine-store-2026-11-05/manifest.json)
retains allowlisted logs, summaries and hashes. An exact scan of 340 known
credentials/DSNs from 71 profiles finds zero matches in the preceding 32 payloads;
it is not a general secret detector. Private profiles/journals, snapshots/physical
archives and engine/model/package caches are excluded. No model/Claude/subagent
calls ran.

Remaining: preserve original tools before environment replacement; durably bind
engines, backup, cluster, recovery binding and deletion head; implement transition,
promotion and admission-before-launch; adopt the target dependency and pins; then
complete full CI/R1/R5 and separately approved real behavior gates. See the
[integration contract](../architecture/native-engine-upgrade.md). No default merge,
tag or publication follows from this qualification.
