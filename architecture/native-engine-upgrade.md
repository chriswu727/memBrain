# Native engine candidate and integration requirements

The shipped dependency still selects pgserver 0.1.4 / PostgreSQL 16.2. The
qualification builder does not change that dependency or select a new engine at
runtime. The candidate combines the checksummed public PostgreSQL 16.15
distribution, portable pgvector 0.8.6 builds, and source-built OpenSSL 3.5.9 LTS
on macOS and Windows. Linux uses operating-system libraries; a successful Ubuntu
job does not establish compatibility with every distribution advertised by a
supplier wheel tag.

[`build_native_bundle.py`](../scripts/build_native_bundle.py) records source and
file hashes, native dependencies, compiler information, licenses and tool
versions. [`check_native_bundle.py`](../scripts/check_native_bundle.py) relocates
the artifact before exercising it. Whole-server archives remain qualification
artifacts; reviewed extension/crypto overlays are packaged in the source/wheel
candidate. There is no package publication or default-engine change.

## Distribution boundary

The supplier's Python wrapper must not execute: it extracts into its installed
package and deletes other extracted versions. memBrain needs its own private,
versioned cache, built from verified archives without mutating site-packages.
Availability detection must remain read-only. Cache preparation must serialize
concurrent processes, extract into a new staging directory, validate all required
tools/resources and their manifest, and publish the complete directory atomically.
A failed preparation must preserve existing data and must not silently select
16.2. Root service-account execution and relative native library paths must work
from the final cache, not just the compiler directory. Embedded database tools and
backup clients now use the shared native environment filter, including loader and
OpenSSL overrides and bundled module selection; service-account options are
preserved. The [environment qualification](../evaluations/maturity-native-environment-2026-11-05.md)
records actual injected-host journeys on all five platforms.

The private cache component is implemented in `native_bundle.py`: source and
overlay checksums, complete native manifests, private staging, process/thread
serialization, tool preflight and atomic publication. Corrupt generations are
retained and repaired into a new generation without moving a running server's
binary directory. Incomplete staging directories left by process death are
ignored and retained. Windows extraction explicitly binds every native file and
directory to TokenUser; Python's temporary Owner Rights ACL can otherwise name
Administrators, which PostgreSQL removes from its restricted token. Qualification
and retained failures are recorded in the
[cache report](../evaluations/maturity-native-cache-2026-11-04.md). This component
is not yet selected by the production embedded engine.

The supported platform contract must name actual native library requirements.
In particular, the inspected Linux binaries depend on libssl.so.3, libcrypto.so.3,
libxml2, Kerberos, zlib, LZ4 and Zstandard supplied by the host. Shipping an older
OpenSSL merely to avoid those requirements is not an acceptable substitute.
The macOS/Windows supplier's OpenSSL 3.6.3 is replaced in the candidate because
that release lacks subsequent fixes and its series is no longer supported.

## Existing installation transition

These are implementation requirements, not claims about an existing automatic
upgrader:

- Detect the running server version, not only PG_VERSION, which records the
  major version. A live 16.2 process must not survive a successful update by
  satisfying a generic pg_ctl status check.
- Verify the new cache before stopping the old server. Quiesce the API, stop the
  owned server, and create and verify a private cold full-cluster backup before
  loading the new engine or changing catalogs. A backup failure leaves the
  original stopped cluster intact. Reserve space for both the backup and staged
  rollback, preserve roles/custom configuration, and refuse unsupported external
  tablespace/WAL links or an unexpected major version explicitly.
- Keep custom settings, loopback binding, SCRAM credentials, role isolation and
  the existing root/legacy cluster locations. Do not discard a cluster to make
  initialization succeed.
- Apply the exact upstream CVE-2024-4317 catalog script to every database,
  including both templates. Replacing binaries alone leaves an old cluster's
  vulnerable view definitions unchanged.
- Serialize maintenance with an administrative advisory lock. Before enabling
  connections to a normally closed database, durably journal its OID, original
  connection permission and cluster identity. On resume, restore the original
  permissions before taking a new snapshot. Never infer the original permission
  from a database left open by an interrupted attempt.
- Record completed maintenance steps durably and make repeated execution safe.
  A failed catalog repair must prevent API readiness and preserve enough state
  for a retry to finish without exposing template0 indefinitely.
- Upgrade pgvector through its supplied SQL upgrade path and inspect the relevant
  PostgreSQL/extension release notes for required index work. After that catalog
  upgrade, running the old 0.6.2 library is not a valid rollback. Rollback must
  restore the pre-upgrade backup; retry must use the new engine and extension.
  Automatic rollback is limited to the pre-readiness transition: never restore
  an old snapshot after new user writes or deletion-registry changes.
- Verify database version, extension version, protected view definitions, index
  readiness, representative vector operations and restart before declaring the
  installation ready. Journals, backups and credentials stay private.

## Durable lifecycle boundary still to implement

The engine preservation primitive is implemented in `native_engine_store.py`.
It verifies complete content-addressed copies, including packaged libraries outside
pginstall, and can validate a recorded copy without its original Python environment.
Root execution now uses it instead of marker-only shared copies; damaged generations
are preserved and repaired elsewhere. Actual preserved-engine upgrade/recovery
passes on all five platforms, including Linux service-account paths. See the
[engine-store evidence](../evaluations/maturity-native-engine-store-2026-11-05.md).
The source must already be trusted; this primitive does not establish provenance.

The parent controller must hold the profile lifecycle lock and the data-parent
maintenance lock across the transition. Before stopping a live process, verify its
loopback SQL identity, actual data directory, owning role and version; refuse an
unknown server or a downgrade. Keep a verified original-engine prefix outside any
replaceable tool environment when original-engine rollback is promised. A backup
of data alone does not preserve the executable or old vector library.

An installer can remove the old tools before the new runtime first launches.
Preserve and bind the original engine before replacing that environment, or supply
an independently verified original-engine input. Do not infer a stopped cluster's
patch version from PG_VERSION or trust a legacy marker as proof of binary integrity.

The parent journal must distinguish backup preparation, target maintenance,
bootstrap/restart verification, recovery staging/promotion and API admission. Bind
the immutable original backup to the original cluster plus both the recovery
binding document and deletion-registry head. Recheck these independent authorities
before restoring: bootstrap may initialize or reconcile them before an API exists.
An absent binding is an explicit original state, not permission to ignore a newly
created binding or registry.

Persist admission **before** launching the API process. A launch timeout or failed
health check cannot prove that no user write occurred. Once admission is durable,
retry on the target engine; never automatically replace its data with the old
snapshot. Recovery promotion must journal and reconcile each rename among the
exact original, preserved-failed and verified-stage paths. Existing directories
must not be overwritten. Preserve the failed SQL journal separately when returning
to an older physical snapshot; a completed target journal does not describe that
restored catalog. These are integration requirements, not implemented behavior.

## Acceptance after integration

The offline snapshot primitive is implemented in `native_snapshot.py`. It checks
clean shutdown/control identity, preserves every ordinary file/directory with
hashes and ownership/mode/timestamp metadata, reserves backup/recovery space and
binds the completed ZIP64 archive to a private receipt checksum. Recovery writes
only to a new staging directory, validates it and never promotes it over a live
cluster. Interrupted attempts remain preserved and unselected. Root/service-account
ownership and actual original-engine rollback are qualified; a streamed member
larger than two GiB is also tested. See the
[snapshot evidence](../evaluations/maturity-native-snapshot-2026-11-04.md).

The SQL component is implemented in `native_maintenance.py`: a cluster/operation/
backup-bound private journal, advisory lock, all-database catalog repair, vector
upgrade, reindex and verification. Closed databases temporarily allow only
superusers by setting connection limit zero in the same ALTER that opens them;
original flags and limits are restored first on resume, even before a missing
backup is rejected. Actual hard-exit/retry and nonowner statistics checks pass on
all five platforms, including both Linux root paths. See the
[maintenance evidence](../evaluations/maturity-native-maintenance-2026-11-05.md).
It does not stop/start engines or manage API admission.

These primitives are limited to the pre-readiness native upgrade transition. They
do not provide a registry-aware user backup/restore command. Their caller must durably bind the
receipt and original cluster/registry identity, retain the lifecycle lock, prevent
new user writes, journal staged recovery/promotion and refuse rollback after API
readiness or registry changes. The default selector and that durable maintenance
orchestrator are still required; neither cache nor snapshot components close them.
Once they are implemented, pin every launcher to the integrated
runtime and rerun actual fresh installation, upgrade, streamed backup/recovery,
full regression and complete performance acceptance. Existing 9f75361 R1/R5
results retain their original scope; neither a candidate builder nor a targeted
platform repair can transfer those results to a new runtime.
