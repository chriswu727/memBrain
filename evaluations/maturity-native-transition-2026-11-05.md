# Durable native transition controller — 2026-11-05

Runtime **`0ea4063d6cf50223086fef9ed1213376224cc9a5`** connects engine preservation,
immutable physical snapshots, SQL maintenance, guarded recovery promotion and
durable admission. **Installer handoff, default engine selection and normal API
startup have not yet adopted it.** The shipped dependency remains pgserver /
PostgreSQL 16.2; nine launchers still pin `9f75361`. This is internal controller
qualification, not a completed installed-product upgrade or release gate closure.

## Implemented lifecycle

`native_transition.session` holds lifecycle, profile, data-parent maintenance and
supervisor locks; independent registry locks are retained when a binding exists.
It requires a verified target and preserved original engine, an absent API, no
active supervisor/foreign client backends, and a matching owned running source.
It checks actual SQL version, superuser, loopback port, data path and cluster ID,
not just PG_VERSION. Unknown/newer sources are refused. Initial source versions
are the qualified 16.2 and 16.15; stopped first-time sources require the still-open
installer/cold-start handoff. Resumes use the recorded state.

The private journal lives in the stable installation directory, outside the data
directory being moved. It binds installation/principal/network identity, data and
log paths, service account, original engine commitment/version, target manifest,
cluster and original recovery-authority fingerprint. New processes derive the
layout from that journal, so a temporarily missing legacy data directory cannot
select a modern location or initialize a replacement.

Preparation stops only the identified source, creates/verifies a cold original
snapshot, records its receipt before loading the target, runs resumable all-database
catalog/vector maintenance, restarts and verifies again. An interrupted incomplete
snapshot gets a new destination; a completed receipt can be verified and attached
after a journal-write interruption. Once target maintenance begins, retries never
replace the original snapshot with partially upgraded data.

Explicit rollback checks both the recovery binding and independently verified
deletion-registry head. It verifies a fresh recovery stage before parking the
failed data and promoting the stage. Each rename is exclusive: Linux renameat2 /
RENAME_NOREPLACE, macOS RENAME_EXCL and Windows rename semantics refuse existing
destinations, including empty directories. Unsupported primitives fail closed.
Journal phases plus directory identities and complete snapshot verification resume
after either rename. Failed data stays preserved, and the failed target's SQL
journal is archived before restarting the original physical catalog. A stopped
unclean failed cluster can be identified only after pg_ctl reports it nonrunning;
original snapshots still require clean shutdown. An explicit retry after completed
rollback creates a new operation, history record and fresh backup.

Admission records bootstrapping before invoking application setup. It verifies
current migrations, reconciled recovery authority, the protected catalog views,
vector version/operations/indexes and the application role's least-privilege flags.
It then durably records admission before returning permission to launch an API.
After that point, rollback is permanently forbidden even if launch times out or
health was never observed. Forward restart verifies the target certificate without
requiring the old engine or physical backup. Handles cannot mutate after leaving
their lock context, and an API listener appearing after entry blocks recovery.
The caller must exit the session and retain its outer lifecycle lock when launching
the API; the existing default startup has not yet been wired to this contract.

## Verification

**270 local scoped tests pass, zero skips**, including 34 transition guards, prior
native/cache/snapshot/SQL/profile/builder cases, a cyclic-cache repair case and two
unclean-control guards. Ruff, diff checks and distribution builds pass. The first
transition run has **26 failures / 6 passes** because its synthetic fixture omits
the mandatory global/pg_control member; adding that fixture file yields 32 passes.
The two later guards cover expired handles and an API opening after entry. Initial
import-format/unused-import lint findings were corrected. All logs remain retained.

The local real journey reuses an owned stopped synthetic 16.2/0.6.2 fixture. It
upgrades, hard-exits a child with code **83** after parking the original data,
resumes from only the installation journal, restores the complete row/role/vector/
index/nearest fingerprint and archives the target SQL journal. A new operation
then takes a fresh backup. Interrupted application setup creates an independent
recovery binding; rollback is refused. Forward setup reconciles the schema and
authority, then a child exits **85** after durable admission. A new database write
survives the subsequent rollback refusal. Ports close. All **442 source/check
hashes** stay fixed during that journey.

That local full journey precedes the final lightweight readiness/expired-handle
guards and version restriction. A final-source forward check verifies role/catalog/
vector readiness and no-rollback behavior; exact-source CI below exercises complete
fresh journeys with those final guards.

[Five-platform run 42009841971](https://github.com/chriswu727/memBrain/actions/runs/42009841971)
passes at the exact runtime source:

| Platform | Job | Guards | Actual transition |
| --- | --- | ---: | --- |
| Linux x86 | 127185767181 | 203 | 16.2 upgrade, ordinary user and root legacy account/path |
| Linux ARM | 127185767378 | 203 | Fresh 16.15, ordinary user and root legacy account/path |
| macOS ARM | 127185767475 | 203 | 16.2 upgrade |
| Windows x86 | 127185767664 | 193 | 16.2 upgrade |
| macOS Intel | 127185767725 | 203 | 16.2 upgrade |

No tests skip; Windows does not collect unsupported Unix cases. Linux ARM has no
historical pgserver wheel and makes no 16.2 upgrade claim. Each transition performs
real recovery/admission process deaths, actual application initialization and
authority reconciliation, and preserves post-admission writes. No HTTP API is
launched by this checker. Existing native/cache, injected-host, SQL maintenance,
preserved-engine snapshot and sparse ZIP64 journeys also pass.

The main root journeys exit after stage promotion but before its journal update.
Workflow-only `9f0ea3f` selects an additional earlier fault: original data is parked
and its pathname is absent. Both
[Linux x86 / job 127192446708](https://github.com/chriswu727/memBrain/actions/runs/42011812265)
and [Linux ARM / job 127192467818](https://github.com/chriswu727/memBrain/actions/runs/42011818757)
pass 203 guards and actual legacy-location recovery at this precise missing-data
window. Runtime, tests and harness are unchanged by that workflow commit.

The installed wheel and source archive match **178 runtime inputs**, with twelve
native resources. The installed controller reopens the real admitted fixture,
verifies target role/catalog/vector readiness and preserves rows/nearest results
while refusing rollback. A separate installed check verifies current application
schema and recovery reconciliation. Each retains all 442 source/check hashes and
closes ports. These results do not replace full application CI, R1 or R5.

| Distribution at `0ea4063` | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 12,855,558 | `3a3e8e866b54185e87e2b4a922cb530ce0b5a8afbbfa0de2339fc1f9504b2015` |
| Source archive | 14,657,194 | `064c764853a5b587778aebb5eb423aa01a06dfadfd760bb3c25292787d98b601` |

## Evidence and storage

The [37-payload manifest](maturity-native-transition-2026-11-05/manifest.json)
retains failures, frozen-source results, worker return codes, all seven successful
platform jobs and distribution hashes. An exact scan of 340 known credentials/DSNs
from 71 profiles finds zero matches in the preceding 36 payloads; it is not a
general secret detector. Profiles, live journals/registries, physical snapshots,
engine caches and private database archives are excluded. No model/Claude/subagent
calls ran.

Only completed owned synthetic PGdata is archived and removed after every-file
hash verification and closed-port checks: the prior maintenance fixture has 1,580
files / 28 directories, archive 9,336,918 bytes, SHA-256
`e9d5e64fb232976ef9c8f4bdfd070695af5e7270848faa540a238533f2519a19`;
the first completed failed target has 1,589 files / 28 directories, archive
9,425,522 bytes, SHA-256
`ad0778a3d1a04d829a9024949849427966ba69051b4f44d7aad7423268889ed8`.
Both archives are private. The qualifier's optional cleanup is not production
controller behavior. Identical public resources use 72 independently writable APFS
clones / 70,617,540 logical bytes verified, zero hardlinks. All profiles, journals,
snapshots, logs, models/packages and original engines remain preserved.

Remaining: an installer source handoff before environment replacement; fresh/cold
profile handling; default target/dependency selection and normal startup/admission;
preventing older startup code from bypassing an interrupted transition; secure
no-compiler Intel Mac crypto installation; stored working-state/full-familiarity
graph coverage; final repin/full CI/R1/R5, approved real R4/C5 and final reviews.
The installed-pin performance/application results retain their original scope.
No default merge, tag or publication follows from this component qualification.
