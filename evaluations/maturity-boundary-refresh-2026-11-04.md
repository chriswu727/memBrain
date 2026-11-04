# Boundary failures and stale host context

Runtime source: `e749a24e86d45d25d1a06d9fcba223e9adf69fcb`. Launcher qualification is in progress. This follows the [TypeScript companion extension](maturity-typescript-companion-2026-11-04.md), whose interfaces do not change here.

## Defects and repair

Two recall helpers converted any relationship-read failure into an empty boundary list. Authentication failures, busy/recovery responses, server errors or a timeout could therefore disable topic filtering. Standalone MCP now reads boundaries before recall and returns a tool error if the read fails. The shared host helper propagates failures so its caller can omit recall while the conversation continues. A session snapshot failure also prevents unfiltered history from being injected. The older-service 404/405 route-absence compatibility remains explicit.

Separately, bot/proxy and OpenClaw adapters replayed a personal-context block for five minutes, and Hermes cached its provider block. Page/API changes did not invalidate those process-local copies. In a real local service reproduction, adding a relationship boundary left the old factual note in the next request even though the request also carried an updated boundary instruction.

The adapters now refresh their memory contribution on each request, or whenever Hermes asks for its provider block. `ChatMemory(block_seconds=...)` remains accepted for constructor compatibility, but cannot enable stale personal-context caching. Persona, feelings, mood, boundaries, shared moments and history therefore come from the current service snapshot. This does not withdraw material already supplied to a model or rewrite a host's independently retained transcript. [Host compatibility](../docs/host-compatibility.md) distinguishes those limits from implemented interfaces and native-host verification.

## Regression and live-service evidence

- Before the first repair, **17 new failure-path cases failed**; four route-absence compatibility cases passed. After it, the related host/MCP/relationship/plugin/adapter group passed **193 tests**, zero skips.
- Three additional Python cache/session cases and one selected OpenClaw case failed before their repair. The final expanded group, including proxy and companion acceptance regressions, passes **231 tests**, zero skips. The Python OpenClaw wrapper drives all **eight JavaScript cases through a real embedded runtime**.
- Four pin/matrix guards pass; Ruff over `src`, `tests` and `examples` passes.
- A fresh real local-service reproduction compares the previous adapter with the repaired adapter under the same current healthy host implementation. The previous adapter still returns the protected fact after the boundary is added (exit 1); the repaired adapter does not (exit 0). Both retain the boundary explanation, including its alias, for the host to follow. These are synthetic data and zero model calls.

The evidence preserves the initial post-repair MCP run with **three fixture failures**: the old HTTP stubs did not implement the relationship GET, previously hidden by the blanket exception handler. The fixtures now answer that actual route; existing protocol assertions remain. It also preserves the first live harness's overbroad assertion that the alias `Jordan` must disappear everywhere. A boundary must still name its alias. The corrected v2 harness instead checks removal of the complete factual note while requiring the boundary explanation; it uses fresh profiles for both sides. No failed run is relabelled as passed.

## Context cost and recall

Removing the cache performs additional current-state reads. A separate four-phase reference/current/current/reference diagnostic used one synthetic user, one bounded note, one boundary, recording paused, one service and no concurrent benchmark. Each phase discarded its declared first call and retained 20 samples. Reference median was **25.73/25.33 ms**, current median **53.36/53.88 ms**; p95 was **29.09/27.14 ms** versus **56.62/58.12 ms**. This small fixture measures the Python request adapter's refresh cost, not native OpenClaw/Hermes application latency, storage capacity or R5 acceptance.

The fresh unchanged canonical R5 fixture at this runtime source passes: **100.47 ms serial, 491.08 ms one-brain eight-worker, 520.83 ms eight-brain eight-worker p95**. All **340 measured recalls are nonempty**; map requests at 200/500 nodes have no errors. Eight brains each carry 1,000 keyword messages, brain zero has 100 notes, indexing is settled, semantic recall is off, and no model call is made. It uses 21 queries per worker and discards the first. Machine remains Apple M4/10 cores, macOS 15.7.4, Python 3.12.13, PostgreSQL 16.2. Benchmark exit 0; API/database ports are confirmed closed.

## Fullscreen comparison: failed, gate reopened

The complete headed-Metal closed/open/open/closed comparison finishes with **4,080 nonempty recalls**, matching actual **181 nodes/66 edges** in both open phases, normal polling and no page/outside-request/artifact errors. It **fails R5**, exit 1: **32/36 workload windows pass**, but four of twelve eight-brain windows exceed 600 ms (703.47, 700.02, 742.02 and 650.51 ms p95). Phase aggregate eight-brain p95 is **536.78/546.69/688.29/663.51 ms**. Failure persists in the final closed phase; this does not establish the 3D renderer or the cache repair as its cause. Every window and sample is retained; the canonical pass does not clear this failure.

R5 is reopened for the current candidate. The [earlier qualified runtime](maturity-private-paths-2026-11-04.md) remains a dated pass, not a substitute. No unchanged benchmark is repeated to select a passing run. Fresh installation/parity and full CI for this repaired runtime are still pending at this report revision.

The [allowlisted evidence](maturity-boundary-refresh-2026-11-04/manifest.json) contains scripts, failed and passed logs, synthetic contexts, raw benchmark samples, screenshots and file hashes. Profiles, connection credentials and database files are excluded.

Real-model R4/C5, final independent review and the complete release checklist remain open. No paid/subscription behavioural evaluation is authorized or started by this change. The Goal is active, the heartbeat remains paused, and merge/tag/publication remain frozen.
