# Native engine update: isolated macOS qualification

The distributed dependency is still pgserver 0.1.4 / PostgreSQL 16.2. **This work does not change the installed runtime, launcher pins or release status.** It prepares an independently buildable PostgreSQL 16.15 wheel and verifies old data and installed native tools on this Apple Silicon Mac. R3 remains open; the current runtime's R5 still fails one eight-brain window at 892.11 ms.

## Build and provenance

[`scripts/build_embedded_postgres.py`](../scripts/build_embedded_postgres.py) downloads fixed PostgreSQL 16.15 and pgvector 0.6.2 archives, verifies both pinned SHA256 values before extraction, builds only in a new directory, and refuses unsupported hosts. PostgreSQL's archive checksum matches its [official source checksum](https://ftp.postgresql.org/pub/source/v16.15/postgresql-16.15.tar.bz2.sha256). pgvector's archive is pinned to the bytes retrieved from its upstream tag; it has no separate upstream checksum in this experiment. The extension version is preserved from the old wheel to isolate the server upgrade; its broader version/security assessment remains required.

The builder makes Mach-O library references relative to their installed locations, verifies each binary's architecture and minimum macOS version, applies and verifies ad-hoc code signatures, and writes platform-specific wheel metadata, source/file provenance, both upstream licenses and hashed RECORD entries. Ad-hoc signing is not Developer ID signing or notarization. No binary, wheel, tag or package is published.

The final wheel is `membrain_postgres-16.15.0-py3-none-macosx_15_0_arm64.whl`, **9,872,946 bytes**, SHA256 `a60321adfe777ff404e1e6f297e7bb62a4569524bc45405ddf087dad6a5c84e2`. This is a local qualification artifact, not a replacement requirement in pyproject.toml. Existing Python 3.13+/Linux/Windows support is not established by this build.

## Existing-profile upgrade

An APFS copy of the privately archived failed synthetic corpus starts first with 16.2, then with 16.15, using the same pgvector version and configuration. The original cluster is never started or modified by this experiment. All **27 public tables / 273,827 rows** retain identical ordered full-row SHA256 fingerprints. Vector distance and extension versions match, all indexes remain ready/valid, and restart preserves the result.

The old system views remain unpatched after only switching binaries. The official [16.3 migration instructions](https://www.postgresql.org/docs/release/16.3/) require `fix-CVE-2024-4317.sql` in every database, including template0/template1. Applying that server-supplied script twice in each of `agent_memory`, `postgres`, `template0` and `template1` changes both view predicates to the protected form without changing any user-table fingerprint. Original database connection permissions are restored. Restart verifies the protected views again. This is a controlled compatibility experiment, not a crash-safe automatic maintenance implementation or an API exploit demonstration.

The reviewed [16.15 release notes](https://www.postgresql.org/docs/release/16.15/) also call out configuration/data/index follow-up depending on installed features. Therefore the catalog script alone cannot certify all upgrade cases.

## Functional and installed-package checks

With locally built 16.15 selected by the external harness, **248 existing tests pass, zero skips**, covering storage/idempotency, tenant isolation, HTTP lifecycle, companion graph privacy, persona/proposals, affect/mood/relationship, recovery erasure/quarantine, a full streamed backup/recovery journey and native installation/restart. Application/test source hashes remain fixed. All 20 owned API/database port checks close. These are native-engine harness adaptations, not unchanged Docker CI or full R4/C5 evaluation.

The wheel is then installed by uv into a separate clean environment. All **1,646 packaged native files** match their manifest's bytes/hash/permissions. The entire original build directory is moved aside during execution. All seven native tools report 16.15; the installed engine passes **31 tests**, zero skips, including actual streamed backup/recovery, installation/restart, row isolation and companion privacy. All ten owned port checks close. The build directory remains absent throughout these tests and is restored afterwards. This verifies relocation rather than allowing the compiler prefix to satisfy missing libraries.

Six additional builder checks pass: wrong checksum before extraction, archive traversal, escaping symlink, preservation of an occupied build directory, unsupported-platform refusal before writing, and every wheel member/RECORD hash. Ruff and diff checks pass. No model, Claude or subscription call is made.

## Retained failed attempts

The first compatibility harness fails before collecting tests because its pytest reporting hook uses the wrong argument name; the script/log/result are retained. After correction, the separate 248-test run passes.

The first wheel uses an invalid `macosx_15_7_arm64` compatibility tag and uv refuses installation with exit 2. Its source, build log and failure metadata are retained. The corrected builder sets the deployment target explicitly, checks each Mach-O minimum and writes the supported `macosx_15_0_arm64` tag. A fresh complete build and actual installation produce the successful result above.

## Still required before adopting this engine

- Verified Linux, Windows and Intel Mac packaging, supported Python/platform installation and native dependency checks.
- A trusted distribution/dependency path and runtime selection; the default dependency still supplies 16.2.
- Automatic, resumable catalog maintenance with backup/failure recovery, including template connection permissions and concurrent starts.
- Extension version/security review and relevant release-note remediation for existing installations.
- Current-runtime installation, recovery, full CI and performance qualification after integration. The original R5 failure is not erased by this prototype.

[Allowlisted scripts, logs, fingerprints and metadata](maturity-native-engine-2026-11-04/manifest.json) exclude profiles, registries, private dumps, compiler trees, source archives and binary wheels.
