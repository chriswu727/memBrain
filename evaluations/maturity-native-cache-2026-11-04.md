# Native cache candidate qualification — 2026-11-04

The candidate now packages reviewed pgvector/OpenSSL overlays and assembles a
verified private PostgreSQL installation without executing the supplier's Python
wrapper or changing site-packages. It is **not** the production embedded selector:
the dependency and nine launcher pins still select the previously qualified
`9f75361` runtime / pgserver PostgreSQL 16.2. Native adoption, durable automatic
maintenance, rollback, final repinning, full CI and new-runtime R1/R5 remain open.
No model/subscription calls, merge, release, tag or package publication occurred.

## Implemented and verified

Source `113e34047624911ca5275824cacb8f71befd41a8` includes the cache and the
Windows extraction/profile-lock repairs. It passes **124 local tests, zero
skips**, Ruff and diff checks. The guards cover source/overlay corruption,
unexpected or missing native files, path escapes, low disk space, damaged cache
repair while retaining the old executable path, process death before publication,
four concurrent threads/processes, private Windows ACLs and empty-file locking.
An abandoned incomplete staging directory is preserved and never selected.

The twelve native resources include five overlays, five complete manifests, their
index and attribution notice. They preserve the previously reviewed PostgreSQL
16.15 / portable pgvector 0.8.6 / macOS-Windows OpenSSL 3.5.9 LTS provenance and
licenses. The optional supplier remains separately installed; the overlays contain
no PostgreSQL server executable. Compressed native resources now contribute to
BUILD_ID. [Native source/build qualification](maturity-native-suppliers-2026-11-04.md).

The current wheel and source have exact **174 runtime-file** parity, including all
native overlays/manifests; all twelve native resources match the wheel. The test
imports `native_bundle` from the installed wheel and exercises real database
initialization, vector creation/write, a bundled-client data dump and restart
without changing the product selector. Supplier files remain unchanged, its Python
wrapper is never imported, and test ports close. The 146 recorded source/check
files match their hashes after verification.

| Distribution | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 12,835,238 | `cd544d646dbe9354f24d7a5e9d9f08fbe19438e8491eb50dabe975bf150ce704` |
| Source archive | 14,616,047 | `8d21fbc9dc012e6e5db5a3acfb4cac8fd6fbbfb6df47f5cfb314eb1ca42d9086` |

## Platform results retain their source scope

There is no all-platform green run at the final source. Four platforms pass at
`5636ddf`; Windows passes after the repairs at `113e340`. These are component
qualifications, not full application installation, R1/R5 or distribution-wide
security certification. Each passing job tests actual relocated native tools,
the existing vector/catalog/dump/restore fixture, and a fresh database made from
the installed supplier plus packaged cache. Linux ARM has no historical pgserver
wheel, so its native fixture starts fresh rather than claiming an old-engine
upgrade. Linux system-library requirements remain explicit.

| Platform | Run / job | Guards | Native files | First / warm preparation, ms |
| --- | --- | ---: | ---: | ---: |
| macOS ARM | 41975951731 / 127074731013 | 53 | 1,481 | 1,356 / 360 |
| macOS Intel | 41975951731 / 127074730945 | 53 | 1,481 | 3,889 / 1,266 |
| Linux ARM | 41975951731 / 127074731166 | 53 | 1,363 | 751 / 241 |
| Linux x86 | 41975951731 / 127074731176 | 53 | 1,363 | 593 / 177 |
| Windows x86 | 41977492349 / 127079670924 | 57 | 3,008 | 5,740 / 1,589 |

All passing cache journeys preserve vector rows through restart, produce an
actual SQL data dump, leave supplier bytes unchanged, avoid the supplier wrapper
and close ports. These single-run startup observations include full manifest and
tool checks; they are not recall latency percentiles or a startup SLA.
Local M4 cold preparation after the ACL repair is 1,836 ms and warm preparation
168 ms. The final installed-wheel run uses an existing verified cache; its first
lookup must not be described as a cold extraction.

The four-platform run is [failed overall](https://github.com/chriswu727/memBrain/actions/runs/41975951731)
because Windows fresh initialization failed. The later
[Windows qualification succeeds](https://github.com/chriswu727/memBrain/actions/runs/41977492349).
All original build artifacts were reused with their checksums; none was rebuilt
to select a different engine result.

## Retained failures and repairs

- The first local installed-supplier attempt exited 120 with an empty log and no
  result document. Free disk space was low, but its cause was not recovered.
  It is not classified as a successful run or a proven disk-full error.
- With phase checkpoints, a subsequent local run initializes the database and
  writes a vector row, then fails because the harness appends `--version` after
  pg_dump connection arguments. The repaired harness exercises an actual data
  dump. Its original failed result remains in the evidence.
- Windows at `5636ddf` and diagnostic `05cd1f7` fails fresh initialization.
  All four environment/private-password variants exit 3221225781 before creating
  PG_VERSION. Python creates extracted directories with an Owner Rights ACL;
  PostgreSQL's restricted token drops Administrators. The cache now gives every
  extracted directory/file an explicit TokenUser owner and private ACL before
  executing native tools. The cache format prefix changes so old prototype
  generations are not silently reused. Source references:
  [CPython 3.12.10 mkdir](https://github.com/python/cpython/blob/v3.12.10/Modules/posixmodule.c#L5024),
  [PostgreSQL 16.15 restricted token](https://github.com/postgres/postgres/blob/REL_16_15/src/common/restricted_token.c).
- At `94744fa`, all four diagnostic initdb variants succeed after that repair,
  but the primary job fails one process-concurrency guard (53 pass / 1 fail), so
  its cache acceptance step is not reached. Full raw bootstrap diagnostics remain
  local and in the original artifact; a checksummed summary is committed instead
  of 89 MB of debug SQL. The original assertion truncated worker details, so that
  exact worker failure cannot be reconstructed from its log.
- Independently, profile-lock initialization wrote a sentinel byte before taking
  the byte lock. Two first creators can race with a held byte lock. Removing that
  write retains exclusion: Windows explicitly supports locking beyond EOF.
  The deterministic no-prelock-write guard, actual four-process preparation and
  real Windows fresh/cache/upgrade journeys pass at `113e340`. This does not
  retroactively prove the truncated worker's exact error.
  [Microsoft locking contract](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/locking?view=msvc-170).

## Remaining integration work

The production selector must not switch until a running 16.2 cluster is safely
stopped, backed up and transitioned. PG_VERSION records only the major version;
generic pg_ctl status is insufficient. Every database/template needs the official
catalog repair, durable original connection flags, resumable extension/index work,
and verified rollback before API readiness. Old pgvector libraries cannot serve
already upgraded extension catalogs. See the
[integration requirements](../architecture/native-engine-upgrade.md).

Intel Mac installation also remains a separate gap: CI builds cryptography
50.0.2 from source with its preinstalled compiler/Rust toolchain. Upstream removed
Intel Mac wheels in 49.0.0; older universal wheels omit later security fixes.
No insecure dependency downgrade or end-user no-compiler promise is made.
[Upstream changelog](https://cryptography.io/en/latest/changelog/).

The complete old installed-pin performance pass is retained at its original
scope. It is not transferred to this candidate. Real paid R4/C5 and final scope
reviews remain open. Failed results, packages, models, profiles and registries
remain preserved. Four owned stopped synthetic clusters were privately archived,
all 5,096 regular files/108 directories verified, and only their generated PGdata
directories removed; the archive itself remains private. Identical public native
files use independently writable APFS clones, never hardlinks.

The [allowlisted evidence manifest](maturity-native-cache-2026-11-04/manifest.json)
records raw and compressed checksums. It excludes profiles, credentials, private
database archives, package/wheel caches and large debug bootstrap SQL.
