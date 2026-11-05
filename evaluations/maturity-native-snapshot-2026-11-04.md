# Offline native snapshot qualification — 2026-11-04

The native upgrade candidate now has a private full-cluster snapshot and staged
recovery primitive. Runtime source is `48bccea209640b19bd3feace7cf874ee686698fd`;
`faa32b8` fixes root evidence export, and `ea01cf0` adds the large-file harness.
Those later commits do not change the runtime. **Production adoption and automatic
upgrade/rollback remain unfinished.** All nine launchers still pin `9f75361`, and
the default dependency still supplies PostgreSQL 16.2. No release gates close from
this component qualification alone.

## Implemented behavior

`native_snapshot.py` requires a cleanly stopped PostgreSQL 16 cluster, checks its
control identity/checkpoint and rejects unexpected majors, PID files, external
links, hardlinks and special files. It reserves backup plus staged recovery space
before writing. Complete file bytes, empty directories, modes, owners and timestamps
are preserved; the original cluster is rechecked before publishing a receipt.
The private receipt binds archive and manifest checksums. Partial archives remain
unpublished and preserved after failure or process death.

Recovery validates the receipt, complete archive and every member before creating
output. It refuses existing destinations and nesting inside a database cluster,
extracts into a new private directory, restores metadata and verifies all bytes
and control identity. It never replaces a running or existing cluster. The default
size budget is 64 GiB and is configurable by the internal caller; it is a limit,
not a verified capacity claim. Snapshot contents are private, not encrypted or
intended as a cross-host/user backup format.

**170 local tests pass, zero skips**, including 46 snapshot cases, cache/profile
guards, crash/interruption, corruption, traversal, size/free-space limits, existing
destination preservation, concurrency and fresh-stage retry. Ruff and diff checks
pass. The first Ruff invocation found an unused test import, fixed before commit;
its 43-test initial pass and subsequent results remain recorded.

## Actual database verification

The harness initializes a 1,000-row vector fixture, HNSW/IVF indexes, a separate
database and a login role. After a full snapshot, it loads PostgreSQL 16.15,
updates vector to 0.8.6, changes rows in both databases and changes the role. It
then restores to a new directory and starts the original engine. The complete
SQL fingerprint, roles/password hash, both databases, vector/index metadata,
nearest results and custom configuration match the original; both physical source
states remain untouched by their respective snapshot/restore operations. Ports
close. Linux root additionally preserves a root-owned, service-group-readable
configuration file while PostgreSQL runs under its service account.

| Platform | Successful run / job | Guards | Scope |
| --- | --- | ---: | --- |
| macOS ARM | 41981234589 / 127091562637 | 103 | 16.2/0.6.2 upgrade and original-engine staged recovery |
| macOS Intel | 41981234589 / 127091562244 | 103 | Same |
| Windows x86 | 41981234589 / 127091562306 | 102 | Same; FIFO creation is unavailable, no skipped tests |
| Linux x86 | 41981829842 / 127093459191 | 103 | Same, regular user and root/service account |
| Linux ARM | 41981832996 / 127093469151 | 103 | Fresh 16.15/0.8.6, regular user and root/service account |

Linux ARM has no historical pgserver wheel and does not claim a 16.2 upgrade.
All platforms also pass their native/tool/cache journeys. The first
[matrix fails overall](https://github.com/chriswu727/memBrain/actions/runs/41981234589):
both Linux user/root database journeys pass, but artifact upload cannot traverse
the root-private result directory. The workflow now exports only its non-secret
summary without changing cluster/backup permissions. Separate
[Linux x86](https://github.com/chriswu727/memBrain/actions/runs/41981829842) and
[Linux ARM](https://github.com/chriswu727/memBrain/actions/runs/41981832996) jobs pass.
There is no single all-platform green run; all failed logs remain retained.

The initial local M4 fixture passes in 765 ms for snapshot/create verification and
981 ms for staged recovery verification. That run precedes two destination/budget
guard additions; the committed runtime is qualified by CI and the wheel journey.
The built wheel imports the new module from its installed directory, restores the
actual private snapshot, starts the original engine and matches the complete SQL
fingerprint. **175 runtime files** match source/wheel; all twelve native resources
are present. All 416 source/check hashes recorded around that installed journey
remain unchanged during it. Later harness-only changes do not alter that runtime.

| Built distribution at `48bccea` | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 12,840,628 | `b413763691678e80c048cf109751d7f11b867bf7b526d4ce08426085054dafbe` |
| Source archive | 14,627,401 | `db88c4821feff6653ba5ecb4f12093047ea0de0f2c1bdd90dd5944043172143b` |

## Large streaming case

[Linux run 41983393800 / job 127098440151](https://github.com/chriswu727/memBrain/actions/runs/41983393800)
passes 103 guards, regular/root native journeys and an additional ZIP64 snapshot
with a **2 GiB + 4 KiB member**, beyond Python's ZIP64 threshold. The source member
is sparse zero-filled test data; restored bytes are streamed and fully hashed.
The total fixture is 2,202,601,648 bytes. Snapshot/create verification takes
16.04 s and staged recovery verification 17.40 s; Python peak RSS is **53.23 MiB**
against the fixed 512 MiB guard. This excludes the separate PostgreSQL processes.
It proves that case's streaming/ZIP64 behavior, not 64 GiB capacity, incompressible
data throughput, recall latency or a production SLA.

## Remaining work and preservation

The durable caller must bind the receipt to the original cluster and registry,
coordinate lifecycle locks, replace a running old engine, maintain every database
and template, restore original connection permissions after interruption, resume
vector/index work and safely journal staged recovery/promotion. It must prevent
rollback after API readiness/new writes/deletion-registry changes. Until that is
implemented, the selector and launchers remain unchanged. Final integrated full
CI/R1/R5, Intel Mac no-compiler installation, working-state/familiarity graph
coverage, real approved R4/C5 and final reviews remain open.

Three completed owned synthetic PGdata directories were privately archived after
ports closed. All 4,740 regular files and 84 directories were verified before only
those generated PGdata directories were removed. Profiles, receipts, the private
native snapshot, original archive, logs, packages and models remain preserved.
No paid/subscription model call, Claude request, subagent, schedule, merge, tag or
package publication occurred. The old installed-pin R1/R5 passes retain only their
original scope.

The [allowlisted manifest](maturity-native-snapshot-2026-11-04/manifest.json)
records original/compressed hashes and excludes credentials, profiles, native
snapshot/physical archives and binary/package/model caches.
