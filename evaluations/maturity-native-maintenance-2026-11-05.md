# Resumable native SQL maintenance — 2026-11-05

Runtime source **`dc7aae46c03345749ead3bb8909e45e7ee4d3f1f`** adds a private,
resumable all-database catalog/vector maintenance component. **Automatic upgrade,
recovery promotion and production selection are still unfinished.** Default
installs still use pgserver / PostgreSQL 16.2; all nine launchers pin `9f75361`.
These results do not qualify final installation, full application CI or R1/R5.

## Behavior

`native_maintenance.maintain` requires the pinned 16.15 server, the owned cluster
path/system identity, an absent API listener and a verified pre-upgrade physical
snapshot. A private journal binds the operation, installation, cluster, snapshot
receipt and original database inventory. Filesystem and administrative advisory
locks serialize maintenance. It refuses unknown identities, inventory changes,
newer extension versions and mismatched backups.

The exact packaged upstream CVE-2024-4317 script is SHA-256 verified before use.
Every database, including both templates and databases originally closed to
connections, receives the repair. Existing vector extensions use the supplied
upgrade path to 0.8.6, including a quoted custom schema; absent extensions remain
absent. Each database is reindexed, protected view definitions/ownership/barriers
and valid indexes are checked, and schema-qualified vector arithmetic is tested.
Committed progress is durable and completed steps are verified on repeated calls.

Before opening a closed database, the original OID/name, connection flag and limit
are durable. One ALTER sets `ALLOW_CONNECTIONS true CONNECTION LIMIT 0`: PostgreSQL
allows the maintenance superuser and blocks ordinary roles, including after a
hard process exit. Resume first restores interrupted connection controls, even
when the supplied backup is missing. Original flags, limits and ACLs are preserved.
The parent lifecycle controller must still exclude concurrent application writes;
this component does not quiesce an API, stop/start engines or promote a recovery.

## Verification

**202 local tests pass, zero skips**, including 32 new maintenance guards and 170
prior cache/snapshot/profile guards. Ruff and diff checks pass. The first unit run
has 16 failures and 8 passes because the fake SQL parser assumes one space before a
negative literal; psycopg renders two. The parser was corrected and failures remain
in the evidence. Later tests add cross-cluster backup refusal, catalog predicates
and a committed-extension/reindex-failure retry.

The actual database harness creates five databases, 1,000 vector rows, HNSW/IVF
indexes, a quoted closed database with limit three, a custom extension schema and
a nonowner role. A child process exits with code 73 immediately after opening
template0 at limit zero. An actual ordinary-role connection is refused. Resume
restores flags before rejecting a missing backup, then completes all databases
with the verified original snapshot. Full row/nearest-result fingerprints, ACLs
and flags match, both statistics views hide private values, and repeat/restart
checks pass. Every saved API/database port closes.

The old 16.2 fixture exposes expression statistics to the statistics-object owner
without table access, but its MCV view already filters by column privilege:
baseline visibility is **`[0, 1]`**, not `[1, 1]`. The repaired result is `[0, 0]`.
Fresh 16.15 Linux ARM starts and ends at `[0, 0]` and makes no legacy-upgrade claim.

One [five-platform run](https://github.com/chriswu727/memBrain/actions/runs/41991396178)
passes at the exact runtime source:

| Platform | Job | Guards | Actual SQL maintenance |
| --- | --- | ---: | --- |
| macOS ARM | 127124222017 | 135 | 16.2/0.6.2 → 16.15/0.8.6 |
| macOS Intel | 127124221981 | 135 | Same |
| Windows x86 | 127124222116 | 134 | Same; no FIFO case, zero skips |
| Linux x86 | 127124221616 | 135 | Same, ordinary user and root/service account |
| Linux ARM | 127124222053 | 135 | Fresh 16.15, ordinary user and root/service account |

All five also pass the existing native/cache/snapshot journeys. Linux x86 repeats
the sparse ZIP64 member over two GiB: 53.36 MiB Python peak RSS. That is a component
memory check, not whole-plugin RSS, incompressible throughput or a capacity SLA.

The installed wheel has **176 exact runtime files**, eleven runtime native-resource
entries and twelve native resource files including NOTICE.md. Its maintenance
module imports from the installed directory and successfully verifies/repeats
maintenance on the previously qualified real fixture, preserving complete rows,
nearest results and role protection through restart. All 436 source/check file
hashes remain unchanged during that journey. This is an installed repeat check;
the source and CI harnesses exercise actual upgrades and interruptions.

| Distribution | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 12,845,001 | `656d0c94cc772e5fe4e7a68cb566ff0c5ccdd7ea535c668333296decedd70a75` |
| Source archive | 14,638,375 | `4b838d9429d064523a1ac57f038b15410d0cc6a099b9890b875a99d57fc79703` |

## Retained failures and boundaries

Four local actual attempts fail before the final pass: an incorrect legacy stats
expectation twice, then an actual identity-check defect, then an overly strict
driver-error assertion. PostgreSQL's `inet_server_addr()::text` includes `/32`;
the runtime now checks `host(inet_server_addr())`. A refused libpq connection has
no psycopg SQLSTATE here; the harness requires the specific database-limit error
text and accepts absent SQLSTATE or 53300. It does not accept arbitrary errors.
The standalone statistics diagnosis saves valid results and stops its database,
then its display helper fails while looking for a WHERE clause absent from the
old expression view. Its output is diagnostic evidence, not a successful check.

The four stopped failed clusters were privately archived, every regular file
hashed and all ports checked before only their owned PGdata directories were
removed: 6,320 files, 112 directories, 34,140,010 archive bytes, SHA-256
`d99c0ab86153f457bb7f3ea2f15d203ef7c04875015041415137ef6b791a134e`.
Profiles, journals, snapshots, logs, binaries and packages remain preserved. The
successful fixture remains stopped and available. No model or Claude calls ran.

The [evidence manifest](maturity-native-maintenance-2026-11-05/manifest.json)
contains 28 allowlisted payloads. An exact scan of 325 known credentials/DSNs from
68 profiles finds zero matches in the 27 payloads preceding the scan summary.
Private journals, backups, database archives and package/model caches are excluded.
This scan is not a general secret detector.

The durable parent lifecycle, registry-aware pre-admission recovery, default engine
adoption, secure no-compiler Intel Mac installation and final integrated acceptance
remain open. No default-branch merge, tag or publication is authorized by these
component results. See the [integration contract](../architecture/native-engine-upgrade.md).
