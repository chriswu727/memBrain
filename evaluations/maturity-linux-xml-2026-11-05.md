# Linux XML ABI candidate qualification — 2026-11-05

The existing packaged Linux PostgreSQL 16.15 executable cannot load on Ubuntu 26 because it requires `libxml2.so.2`. Candidate build `cc599cc` supplies a separately compiled, security-patched library without changing any existing engine file. The [qualification run](https://github.com/chriswu727/memBrain/actions/runs/42079033486) is terminal **SUCCESS** on x86_64 and ARM64, both on Ubuntu 22.04 and on Ubuntu 26.04. The same Ubuntu 22 build artifacts are downloaded and relocated on Ubuntu 26; they are not rebuilt there.

This qualifies the native candidates, **not the currently shipped package**. Runtime commit and all nine installation pins remain `73ee62ee5796902249ddd20b08ed7e4ad6922b3f`; packaged resources, migration SQL and schema are unchanged. Installed-package integration, already-admitted engine revision handling and full application verification remain required. [Hashed public evidence](maturity-linux-xml-2026-11-05/manifest.json).

## Build and verification

The builder pins Ubuntu's `2.9.13+dfsg-1ubuntu0.14` source descriptor, original archive and Debian patch archive by SHA-256. The descriptor signature and 38-patch series were investigated in the [restart-preflight evidence](maturity-restart-preflight-2026-11-05.md). The version is listed in Ubuntu's [security notice](https://ubuntu.com/security/notices/USN-8910-1). The builder regenerates the patched Autotools files and runs `make check` before copying the library.

Ubuntu's source archive excludes the upstream `test` and `result` trees. The builder restores only those data trees from the [official 2.9.13 archive](https://download.gnome.org/sources/libxml2/2.9/), pinned against its published SHA-256, **before applying the Debian security patches**. It rejects traversal and external links and materializes the two internal archive hard links as independent regular files. Upstream source files outside those two trees are not replaced; test data is not included in the native runtime bundle.

Both architectures pass 3,350 regression tests, nine recursion tests and the API test driver's 280,912 cases across 1,164 functions. The optional external W3C conformance suite is absent and reports zero tests; it is explicitly outside this evidence. Chinese GB18030, Japanese Shift-JIS and ISO-8859-1 inputs round-trip to UTF-8 using the built library's iconv support. The library is built without ICU to avoid depending on the old ICU 70 ABI. zlib and LZMA support remain enabled.

The ELF check requires the actual `libxml2.so.2` soname, rejects build-prefix RPATH/RUNPATH entries and limits dynamic dependencies to reviewed system libraries. ARM's observed `ld-linux-aarch64.so.1` dependency is accepted only on ARM. The PostgreSQL binaries retain their original relative runpath; the relocated loader check confirms that PostgreSQL resolves the newly bundled library, not a system copy. Build and qualification commands remove inherited loader overrides.

All four native journeys assert:

- All seven PostgreSQL tools report 16.15, and extracted engine files match their manifest.
- Unicode XML, namespaces, XPath and XMLTABLE return expected results; malformed XML is rejected.
- 1,000 synthetic vector rows retain their fingerprint, approximate-index results match exact results, and expected vector indexes are used.
- Restart, backup and restore preserve the rows; catalog repair remains idempotent and an actual TLS connection is established.
- The owned port is closed at completion and no model calls are made.

These are fresh native database journeys. They do not replace the existing legacy-adoption, root/service-account, API, quarantine-recovery or full installed-package gates.

| Candidate artifact | SHA-256 |
| --- | --- |
| Linux x86_64, built on Ubuntu 22 | `06719c32aa16c69164f01e2d92207bca136528e38e6ebafebd36d2c09a87e6ce` |
| Linux ARM64, built on Ubuntu 22 | `846651a0cc3ea215b028a9affc77cce2ec0f97f199782ce46e561d2a7e8d2c0e` |

Comparison with both currently packaged Linux manifests finds **zero changes to existing files**. Each candidate adds the shared library and four license/provenance files. The two PostgreSQL/pgvector license files normally added by the packaging step remain packaging inputs, not missing engine files. Complete candidate manifests and the four qualification summaries are retained in the evidence.

Local validation passes 24 builder/resource tests, Ruff and the diff whitespace check. Workflow YAML parses successfully. Local test counts are recorded from observed tool output; a raw pytest log was not saved.

## Retained failures

| Run | Outcome and correction |
| --- | --- |
| [42077081721](https://github.com/chriswu727/memBrain/actions/runs/42077081721) | Both architectures failed with mismatched pre-generated Automake definitions. Regenerate the patched build system with `autoreconf -fi`. |
| [42077413444](https://github.com/chriswu727/memBrain/actions/runs/42077413444) | Both builds reached tests but the repacked source lacked thread fixtures. Restore the pinned upstream data before patch application. |
| [42078205260](https://github.com/chriswu727/memBrain/actions/runs/42078205260) | Upstream checks passed. x86 qualification found an XMLTABLE test syntax error; ARM hit the dependency guard. Parenthesize the parameter cast and retain the rejected ELF details. |
| [42078677946](https://github.com/chriswu727/memBrain/actions/runs/42078677946) | x86 native qualification passed; ARM's system dynamic loader was rejected. Add the observed loader to the ARM-only allowance with a cross-architecture rejection test. |

The first attempt to fetch a completed job's log returned a transient GitHub API error; re-reading the same job succeeded. No job was restarted merely because its log was unavailable. Logs and job status documents retain all four failed runs. They are not counted as successful Ubuntu 26 verification.

## Next integration boundary

An admitted transition binds its exact target prefix and manifest. Replacing packaged resources without a revision policy would invalidate existing installations. The verified additive-only candidate makes it possible to require that every previous engine file remain byte-for-byte and mode-for-mode identical, while allowing only the reviewed XML additions. This comparison is evidence for the next implementation, not an implemented migration policy.

The integration must retain the old engine and transition evidence, preflight the new target before stopping a live service, preserve the data directory/system identifier/recovery authority, make the target switch crash-safe, and forbid restoring pre-admission data after application traffic. It must also exercise interrupted transitions and root/service-account ownership. Only after those checks should the new resources enter the default package, followed by full application and current-candidate performance/behavior acceptance.

No default-branch merge, tag, publication, paid/subscription model evaluation, Claude call, Docker restart or local data deletion occurred in this batch.
