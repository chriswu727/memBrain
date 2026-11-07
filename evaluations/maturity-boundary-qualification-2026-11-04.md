# Boundary/context repair: installation and harness qualification

Runtime remains `e749a24e86d45d25d1a06d9fcba223e9adf69fcb` in all nine launchers. Installation source is `b406c1981275b33986c986d84bf0a6dca3325f54`; follow-up `ba863a9642f3106a0b3b057021a103483019dc00` removes two obsolete test/evaluation references to the deleted context cache. It changes no installed runtime, schema, dependency or launcher pin.

**R1 passes again; R5 remains open.** The [boundary/context repair report](maturity-boundary-refresh-2026-11-04.md) retains the complete failing fullscreen comparison: 32/36 workload windows pass, four eight-brain windows fail, maximum p95 742.02 ms, including failures in the final closed phase. No unchanged performance run was repeated to replace that result.

## Installed runtime

The unchanged release checker passes **49/49** fresh-Mac checks, zero failures, using basic fixture `d0d7a0379f7ac5f1b81dad04504601bb6606f1b0` and companion fixture `19e894ca9e08cf65fa071e8019789499953478d0`. The wrapper shares only the task's download cache; homes, profiles, baselines, assertions, default local-model behaviour and launcher commands remain unchanged. Provider credentials are removed. Install, upgrade, MCP, proxy, restart, backup/restore, activation and companion preservation pass.

A separate installed-interpreter/API/browser check passes:

- **165 runtime/resource files match** the repository exactly; no unexpected package files.
- The installed bot adapter's next request omits a newly bounded factual note while retaining the boundary explanation, without manual cache invalidation.
- Both stored-memory/companion graph layers match authorized API identities and edges. Fullscreen and the 2D fallback work; zero page errors or external requests. This is an installed-package functional check, not a new frame-rate or R5 pass.
- Stop exits 0. All API/database ports for **14 task-owned profiles** are independently confirmed closed.

## Failed CI and harness follow-up

[Verify at `b406c19`](https://github.com/chriswu727/memBrain/actions/runs/41910834961) **fails**: **7,023 Python tests pass, one fails**, zero skips, three warnings, 1,314.30 seconds. `tests/test_roleplay.py::test_roleplay_and_real_life_never_mix_on_a_real_service` still calls `bot._blocks.clear()`. TypeScript and build steps do not run after pytest fails. The complete compressed log and its hash are retained.

The first current public stub rehearsal also fails: arm E's page-action driver still calls `chat._forget_blocks(...)`. The supervisor stops P/F; the incomplete run fails strict validity and is not scored. Its logs, rows, page actions and invalidity report are retained.

Follow-up `ba863a9` removes those obsolete private-cache calls rather than adding an unused cache back. All role-play isolation assertions and public scenario criteria remain unchanged. Relevant verification passes:

- **Six role-play tests**, zero skips.
- **483 harness/driver/scoring/billing-guard tests**, zero skips, two existing multiprocessing-fork warnings; synthetic/stub inputs only.
- A fresh public P/E/F rehearsal, with the corrected harness hash recorded, passes **250 checks**, strict validity true, no problems and no empty-reply retries. The largest reference prompt is 1,163 tokens. The harness refuses external sockets; no real model/evaluation call is made. This proves mechanics, not R4/C5.
- Pin/matrix guards and Ruff pass. [Full Verify for `ba863a9`](https://github.com/chriswu727/memBrain/actions/runs/41915395596) now passes **7,024 Python tests, zero skips**, three warnings, **50 TypeScript tests**, strict types, Ruff and sdist/wheel builds. All four actual Docker journeys and real pinned local-model/activation cases pass. The complete log and source-bound result are included in the evidence; the earlier failure remains a failure.

The earlier [SDK source `78a225d`](maturity-typescript-companion-2026-11-04.md) passed full CI with 7,000 Python tests/zero skips, 50 TypeScript tests, strict types and packaging. That result stays attached to its source.

The C-2 interface inventory is complete for the declared surface: missing standalone MCP/control paths, custom-client orchestration and unverified native host journeys are explicit. This satisfies the documentation/interface gate, not real-model C5 or final independent review.

## Storage diagnosis and fixture preservation

The stopped failed performance fixture and its registry are preserved in a **private 299,708,428-byte cold archive**, with **1,487 regular-file SHA-256 comparisons** before removing the original disposable profile. It contains fixture credentials and is excluded from Git. Two incomplete archive attempts are recorded; the second reports ENOSPC. A later verification pass replaces repeated backward gzip seeks with a single forward stream and verifies every file. The current failing comparison's samples and fixture remain preserved.

Cleanup covers task-owned passing pytest fixtures, an unused memBrain download cache and an older completed synthetic benchmark database. Older raw measurements/reports, its file-hash inventory and registry remain; its raw database is not retained. Local embedding weights are preserved. The newer failed fixture is fully retained in the private archive.

A metadata-only restoration of that archive verifies 1,485 profile files, leaves the existing registry intact, queries the task-owned PostgreSQL instance with transaction writes disabled, then stops it and removes the restored diagnostic copy. The first diagnostic start fails because the tar data filter does not preserve directory permissions; repairing only the owned copy's profile/database directories to 0700 allows the metadata check. This is not the product's backup/restore path, which passed the 49-check run.

The measured database is 668,422,627 bytes. `memory_traces` uses **350.9 MiB** and `memory_requests` **177.5 MiB**, together about **83%** of those bytes, including their indexes/TOAST. `pg_stat_user_tables` reports `n_live_tup` 236,118 and 4,911 respectively; these are statistics, not a storage-capacity guarantee. User-event storage is 27.3 MiB and assertions 60.6 MiB. These measurements identify substantial recall bookkeeping to investigate. They do **not** establish its contribution to the failed latency windows or authorize discarding feedback traces/idempotency guarantees.

The [allowlisted manifest](maturity-boundary-qualification-2026-11-04/manifest.json) binds scripts, installed hashes, failed/passed public evidence and metadata. Private archives, profiles, passwords and connection files are excluded.

Real R4/C5, final independent review and the remaining release gates stay open. The Goal remains active with no schedule; merge/tag/publication and unapproved paid/subscription behavioural work remain frozen.
