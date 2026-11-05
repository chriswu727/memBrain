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
from the final cache, not just the compiler directory.

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

## Acceptance after integration

The default selector, durable maintenance journal, verified physical backup and
rollback are still required; the cache component alone does not close them.
Once they are implemented, pin every launcher to the integrated
runtime and rerun actual fresh installation, upgrade, streamed backup/recovery,
full regression and complete performance acceptance. Existing 9f75361 R1/R5
results retain their original scope; neither a candidate builder nor a targeted
platform repair can transfer those results to a new runtime.
