# Native engine candidate, dependency review and Windows profile repair

The installed launcher pin remains **9f75361**, with the previously recorded
49/49 installation and complete 36/36 performance acceptance. The integration
branch now also contains the Windows profile ACL repair in **d33a1be**, which is
not yet launcher-pinned or qualified by a new complete installation/performance
run. Its native dependency still selects PostgreSQL 16.2. **R3 remains open.**

This round supplies an independently checked PostgreSQL 16.15 / pgvector 0.8.6
candidate and repairs a Windows permission defect found while exercising it.
There is no default-engine switch, package publication, release, merge, paid
model call or Claude request. The [integration requirements](../architecture/native-engine-upgrade.md)
separate implemented qualification from the remaining automatic upgrade work.

## Candidate construction

[`build_native_bundle.py`](../scripts/build_native_bundle.py) downloads one of
five SHA256-pinned public `postgresql-binaries==16.15.0` wheels, verifies the
archive before extraction, and never imports the supplier's Python wrapper.
That wrapper extracts inside site-packages and deletes other extracted versions;
it is unsuitable for memBrain's required private, atomic engine cache.

The builder compiles upstream pgvector 0.8.6 with portable `OPTFLAGS=` rather
than a host-specific CPU target, records compiler/native dependency information,
and packages the extension's SQL upgrade paths and license. The source archive
SHA256 is `10bf9938906e5d643bbc4a7eea104b6f57ba4898e5b76b20e60484ea1d5a7f8f`.
The [upstream changelog](https://github.com/pgvector/pgvector/blob/v0.8.6/CHANGELOG.md)
records the intervening index, memory-safety and vacuum fixes. This is a source
and compatibility review, not a claim that every upstream extension feature has
been independently security-audited.

The inspected macOS supplier contains OpenSSL 3.6.3, below subsequent fixes and
outside the currently supported series. See the [official support/download
status](https://openssl-library.org/source/) and [advisories](https://openssl-library.org/news/vulnerabilities/).
The candidate builds **OpenSSL 3.5.9 LTS** from its official source on macOS and
Windows, verifies SHA256
`603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a`,
preserves its license/authors, relocates macOS library references, and verifies
ad-hoc signatures. This is not Developer ID signing or notarization. A version
finding is not a demonstrated exploit of memBrain's loopback, normally non-TLS
database.

Linux uses host-provided native libraries. The two functional jobs run on Ubuntu
22.04; they do not establish compatibility with arbitrary glibc distributions,
Alpine, or every system implied by a supplier wheel tag. The recorded OpenSSL
3.0.2 string alone does not identify Ubuntu's downstream security patch level.
Distribution support, library preflight and that security assessment remain
required before adoption.

## Per-platform functional qualification

[`check_native_bundle.py`](../scripts/check_native_bundle.py) checks all seven
relocated tools, constructs a 1,000-row vector fixture, exercises HNSW and IVFFlat
indexes before and after the extension update, compares the first ten results
with exact calculation, verifies actual index-scan plans, performs insert/delete,
vacuum and reindex, checks dump/restore and restart, repairs catalog views twice
in all four databases while restoring their connection permissions, and verifies
a real TLS 1.3 connection. Owned database ports close afterwards.

| Target | Native file hashes verified | Old 16.2 / vector 0.6.2 upgrade | Result |
| --- | ---: | --- | --- |
| macOS ARM64 | 1,479 | Yes | Pass |
| macOS Intel | 1,479 | Yes | Pass |
| Ubuntu x86_64 | 1,361 | Yes | Pass |
| Ubuntu ARM64 | 1,361 | Fresh candidate only | Pass |
| Windows x86_64 | 3,006 | Yes | Pass after ACL repair |

All **8,686** native file hashes are independently rechecked after downloading
the GitHub artifacts, including symlink targets and outer artifact digests.
Linux ARM64 has no corresponding historical pgserver wheel in this exercise;
it is not counted as an old-installation upgrade pass.

The four non-Windows results come from [run 41966197762](https://github.com/chriswu727/memBrain/actions/runs/41966197762)
at builder source `a5e559b`. That whole run fails its Windows job because NASM is
missing. Windows subsequently builds the same candidate successfully in
[run 41966608340](https://github.com/chriswu727/memBrain/actions/runs/41966608340),
and the unchanged compiled bundle passes the repaired checks in
[run 41969028210](https://github.com/chriswu727/memBrain/actions/runs/41969028210)
at `d33a1be`. That final job also passes **17 builder/ACL guards** and performs no
build, so its original compiler directory is absent. These are five scoped
platform passes from separate runs, **not one all-green matrix run**.

## Windows permission repair

The Windows build first succeeds but old `initdb` cannot read its password file.
Retaining that command's diagnostics exposes `Permission denied`. PostgreSQL
uses a restricted process token. An elevated-created file can be owned by the
Administrators group; granting only the owner-rights SID does not provide access
after that group is removed from the token.

`local_profile._restrict_windows_access` now obtains the process's TokenUser SID
and sets it as the file owner and the sole protected, inheritable full-access
entry. Passwords and profiles stay private to the current user. Native handles
and SID allocations are released on success and failure. The checker applies
the actual application helper to its directory and password file; it does not
grant access to Everyone or Users or skip the failing old-engine phase.

The local profile, SID/error-cleanup and builder checks pass **86 tests, zero
skips**, in 0.90 seconds. Ruff and diff checks pass. The real Windows worker then
passes old initialization, upgrade, vector/index operations, recovery, restart
and encryption with this ACL implementation. A complete host installation and
full candidate suite after the eventual native integration are still required.

## Larger existing-data and application checks

An existing isolated APFS copy starts with PostgreSQL 16.2 / vector 0.6.2, then
uses the downloaded CI-built 16.15 / vector 0.8.6 / OpenSSL 3.5.9 artifact on this
Mac M4. The CI compiler path does not exist on this computer. All **27 public
tables / 273,827 rows** preserve complete-row fingerprints through the extension
upgrade, repeated catalog repair and restart. Every complete row is hashed;
sorting the short hashes preserves duplicates without a large database sort.
There are no invalid indexes, and the original source cluster is never started
or modified.

With this candidate selected by the external harness, **248 existing tests pass,
zero skips**, in 29.88 seconds: storage, isolation, HTTP, companion privacy,
persona/proposals, affect, mood, relationship, erasure/quarantine, streamed
backup/recovery and native installation/restart. Source/test fingerprints stay
fixed and all 20 owned port checks close. The harness selects the native prefix,
defaults its new profiles to embedded, and replaces only Docker teardown with
stopping its owned native cluster. This is not unchanged Docker CI, default
dependency installation acceptance or new-runtime R5.

The [16.3](https://www.postgresql.org/docs/release/16.3/) and
[16.15](https://www.postgresql.org/docs/release/16.15/) upgrade guidance requires
more than changing executables. The official catalog script is applied twice
to `agent_memory`, `postgres`, `template0` and `template1`; original connection
permissions are restored and protected view definitions survive restart.
Migration sections from 16.3 through 16.15 are reviewed. A read-only check of
this fixture's business/control databases finds no partitioned tables, GiST/BRIN
indexes, logical slots, pgcrypto, ltree or btree_gist, and confirms the restricted
output-plugin setting and non-superuser/non-replication/non-bypass application
role. This scoped result cannot replace feature detection for another user's
existing database or a durable interruption-recovery journal.

## Full CI and lockfile audit

[Full Verify 41965410671](https://github.com/chriswu727/memBrain/actions/runs/41965410671)
at `5c73012`, whose application still matches pin `9f75361`, passes **7,095 Python
tests, zero skips**, with three existing fork/thread warnings, in 1,154.42
seconds; **50 TypeScript tests**, strict types, Ruff and both package builds also
pass. Four actual Docker journeys, the real pinned multilingual CPU model and
in-flight activation case are explicitly present as passed. The full log is
preserved. This predates the Windows SID repair and is not its full-suite result.

An [OSV batch](https://google.github.io/osv.dev/post-v1-querybatch/) query checks
**103 unique locked PyPI/npm package versions**, including optional/development
packages, with pagination handling and retained request/results: **zero advisory
matches** at capture. It does not scan vendored native libraries or prove that
unknown vulnerabilities do not exist. No dependency is changed by that audit.

## Failed evidence and remaining work

Preserved failures include a disk-full server-side fingerprint sort, an incorrect
COPY row-type assumption, the first header-path classification, the first local
license path, a first CI environment missing the runtime needed by global test
cleanup, the Windows license path, missing NASM, the initial discarded `initdb`
diagnostic and the actual Windows password-file permission failure. Adding a
secondary sort key initially prevented the vector query from exercising its
index; the corrected diagnostic checks actual index-scan plans. No failed run
is relabeled as a pass.

Only stopped, completed, owned synthetic database directories are removed after
private archive creation, every-file hash verification and closed-port checks.
Profiles, registries, logs, sources, binaries and archives remain. The separate
public-binary block-sharing step retains independently writable APFS clones,
with identical bytes, permissions, owners and timestamps; it uses no hardlinks.

Before R3 closes, implement trusted native resource distribution, the private
atomic cache, running-old-server replacement, backup/rollback and durable
catalog/extension maintenance. Then pin every launcher to the complete batch and
rerun fresh installation, full CI and complete R1/R5. The Windows-only source
change is intentionally not separately repinned while this integration is in
progress. Real R4/C5, remaining actual-graph coverage and final reviews stay open.

[79 allowlisted evidence files and hashes](maturity-native-suppliers-2026-11-04/manifest.json)
include complete CI logs and retained failures; exact scans of 275 known
credential/DSN values from 58 local profiles find zero matches in the 78 payloads.
Private database archives, profiles, registries, native binary archives and
compiler/model/package directories are excluded.
