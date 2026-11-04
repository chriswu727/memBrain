# Current runtime: installation passes, sustained recall gate remains open

Tested source `281b06e585b0a9ca6b67e8892f3c6a3d69bc572f`; all nine launchers pin runtime `b994ec8080d46ee861f6ed8738a1617929f50d2a`. Source, tests, pins and qualification inputs stay unchanged during each verification. **R1 is verified again; R5 is not met.** Full CI is still in progress and is not inferred from older green runs.

## Fresh installed runtime

The original release-install checker passes **49/49 checks, zero failures** on the reference Mac. Basic and companion baselines are unchanged. The wrapper only shares the task's existing download cache; homes, profiles, installer commands, assertions, local-model defaults and recovery steps are unchanged. Provider credentials are removed; no behavioural model evaluation is made. Fresh installation, upgrade, MCP, proxy, restart, backup/restore/activation and companion preservation pass.

A separate fresh installed-interpreter/API/browser follow-up verifies:

- **165 package/resource files match exactly**, with no unexpected files.
- Recording times are null on masked nodes in legacy memory, structure and companion graphs. Explicit sensitive opt-in retains original note/message timestamps.
- The bot's next contribution omits a newly bounded factual note while preserving the boundary explanation; no private-cache invalidation is used.
- Both graph layers, fullscreen and the 2D fallback match actual API IDs/edges. No page error or external request; the screenshot was visually inspected. Stop exits 0.

The first follow-up fails a graph-ID comparison after adding privacy-fixture writes without waiting for their index. Its script, result, log and stopped profile are retained. That failure does not prove a runtime defect: no before/after ID diff was captured. A corrected **fresh** fixture keeps every equality assertion and waits after all newly added writes; it records pending jobs/index lag **3/3 → 0/0** before freezing expected graphs, then passes. This supports an unsettled-fixture explanation without claiming exact attribution for the first mismatch.

The graph repair itself has **95 local graph/browser tests passing, zero skips**, with four actual-database reproductions before the repair and 2D/3D detail checks; [prior report](maturity-trace-qualification-2026-11-04.md). Ruff and pin/matrix guards pass.

## Canonical and complete fullscreen performance

The unchanged fresh fixture uses eight independent brains, 1,000 keyword messages each and 100 notes in brain 0, with indexing settled and no model calls. Each worker runs 21 rounds, discarding only its declared first warm-up. Apple M4, ten cores, macOS 15.7.4, Python 3.12.13 and embedded PostgreSQL 16.2.

| Canonical workload | Nonempty recalls | p95 ms | Bar ms |
|---|---:|---:|---:|
| Serial | 20 | 97.61 | <500 |
| Eight workers, one brain | 160 | 476.12 | ≤1,000 |
| Eight workers, eight brains | 160 | 469.96 | ≤600 |

Canonical exits 0; all **340 recalls are nonempty**. Map API p95 is 10.89/14.29 ms at 200/500 nodes. These are keyword/API measurements, not semantic speed, frame-rate or storage-capacity guarantees.

The subsequent complete Metal closed/open/open/closed comparison **fails**, exit 1. All **4,080 recalls are nonempty**, but only **33/36 workload windows** and **9/12 eight-brain windows** pass. Serial and same-brain windows meet their bars. No sample beyond the declared warm-ups is discarded.

| Phase | Eight-brain window p95 values, ms | Aggregate p95 ms |
|---|---|---:|
| Closed 1 | **614.77 / 659.56** / 514.12 | 645.85 |
| Open 1 | 500.69 / 493.54 / 523.29 | 508.90 |
| Open 2 | **601.00** / 519.34 / 515.59 | 549.54 |
| Closed 2 | 531.91 / 532.06 / 542.51 | 541.51 |

Both open phases use actual ANGLE Metal on Apple M4. **181 node IDs and 66 edges match** the stored structure-map payload; normal polling stays enabled, visible hologram frames advance by 1,984/2,024, and there are no page/external/artifact errors. Both screenshots were inspected. Runtime and workload hashes remain unchanged, and all six performance-fixture ports close.

The earlier trace runtime `f1fc97b` passes every window, maximum eight-brain p95 556.70 ms, and remains [dated evidence](maturity-trace-qualification-2026-11-04.md). It does not replace this newer failure. The intervening code change only masks graph recording times; no cause is established for the new tail. Closed-phase failures prevent attributing it to rendering alone. No unchanged rerun is made to select a green result. Next diagnosis will separate per-thread CPU, event-loop/encoding work, database/server execution, scheduling waits, GC and maintenance on the retained failing corpus; the earlier concurrent cProfile attempt is not reused as valid per-request evidence.

## Evidence, storage and remaining gates

The complete stopped failing corpus and registry are privately cold-archived: **1,486 regular-file hashes** verify before removal of only the owned original profile. The registry and private archive remain; archive/credential bytes are excluded from Git. The earlier failing `e749a24` and passing `f1fc97b` private archives also remain.

To make room for verification, only stopped task-owned completed synthetic databases are removed after port checks and private file-hash inventories. Their packages, profiles, registries, model weights and measurement reports remain; their raw databases do not. The first failed installed follow-up is preserved. Six current remaining profiles have both API/database ports independently checked closed, in addition to the archived performance fixture's six ports.

Full Verify at [source `281b06e`](https://github.com/chriswu727/memBrain/actions/runs/41927888667) remains in progress. The superseded `9b9bad0` run is **cancelled**, with pytest cancelled and TypeScript/build steps skipped; it is not a green check. Cancelled metadata and all new failures are retained in the [allowlisted manifest](maturity-release-qualification-2026-11-04/manifest.json).

**R5, real R4/C5, final independent/privacy/design review and remaining graph coverage stay open.** No paid/subscription behavioural test, additional Claude consultation, main merge, tag or publication is performed. Goal work remains active without a schedule.
