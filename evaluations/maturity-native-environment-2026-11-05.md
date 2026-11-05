# Embedded native process environment — 2026-11-05

Runtime **`ca85119b2170606135cd8e8548098331da3afa41`** uses the same controlled
native environment for database tools and backup clients. Previously these paths
filtered PostgreSQL/legacy memory variables but inherited dynamic-loader and
OpenSSL overrides from the host; backup clients also inherited Python overrides.
The shared environment strips PostgreSQL, memory, memBrain, Python, DYLD/LD and
OpenSSL configuration/module overrides, sets the C locale, and selects the bundled
OpenSSL module path when present. Backup clients receive only the owned password
and connection timeout afterward. Service-account execution options remain intact.

Four parameterized guards cover ordinary/service-account subprocesses with and
without bundled crypto modules, malicious host values, owned backup credentials,
required system variables and an unchanged parent environment. **196 local guards
plus ten native-builder guards pass, zero skips**; Ruff, diff checks and builds
pass. These are scoped checks, not the full application suite.

The real cache harness injects conflicting PostgreSQL host/port/user/database,
dynamic loader, crypto and memBrain values. It initializes PostgreSQL 16.15, writes
a vector row, invokes its actual pg_dump, restarts and reads the same row. The
client environment contains none of the injected values; the original environment
is restored even on failure. The supplier archive is unchanged, its Python wrapper
does not execute, and all ports close. Local M4 and all five platform journeys pass.

[Run 41993173758](https://github.com/chriswu727/memBrain/actions/runs/41993173758)
passes at this exact source:

| Platform | Job | Guards |
| --- | --- | ---: |
| Linux x86 | 127130005166 | 139 |
| Linux ARM | 127130005294 | 139 |
| macOS ARM | 127130005407 | 139 |
| macOS Intel | 127130005466 | 139 |
| Windows x86 | 127130005458 | 138 |

Windows has no FIFO case; no tests skip. Existing native/tool/cache, all-database
SQL-maintenance and snapshot journeys also pass, including both Linux
root/service-account SQL and snapshot paths. Linux ARM qualifies fresh 16.15,
not a historical 16.2 upgrade. The injected-host journey runs as the normal runner;
the service-account unit guards and separate root journeys have their stated scope.

The installed wheel matches **176 runtime files** and twelve native resources
(eleven have runtime-manifest suffixes). Its installed maintenance module repeats
verification on the real five-database fixture, preserves all rows/nearest results
and nonowner catalog protection, restarts and closes all ports. All **437 source/
check hashes** stay unchanged during that installed journey. The actual injected-
environment fixture is exercised separately by the source and installed CI harness.

| Distribution | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 12,844,933 | `9f569854c072547362ee2a1c9afbe1d97a71afe14ff42e8fb09e8d3ba9109b2d` |
| Source archive | 14,639,860 | `69467d49f5bd80227bd884ecf596234fade5fabb9f2d2518460cace9805418f2` |

The [eleven-payload evidence manifest](maturity-native-environment-2026-11-05/manifest.json)
retains local and CI logs, summaries and installed-wheel hashes. An exact scan of
330 known credentials/DSNs from 69 profiles finds zero matches in the ten payloads
preceding the scan summary. Private profiles, physical databases, snapshots,
journals and caches are excluded. No model or Claude calls ran. The successful
local fixture is stopped and preserved.

The production dependency still supplies PostgreSQL 16.2; nine launchers still pin
`9f75361`. The [SQL-maintenance qualification](maturity-native-maintenance-2026-11-05.md)
and its retained failures remain applicable to that unchanged component. Durable
parent lifecycle/recovery promotion, production adoption and final full CI/R1/R5
remain open. This change neither merges the default branch nor publishes a release.
