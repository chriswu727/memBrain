# Recall eligibility and episode membership retention

Runtime `ee644c99691546871465e15ddd9f12b394ff8a4e` repairs two independently reproduced memory defects. All nine launchers now pin this runtime. These repairs were derived from public code and synthetic tests, without reading held-out scenarios or making provider/subscription calls.

## Eligible memories receive the candidate budget

Previously, bounded lexical/vector queries selected their first candidates and only then removed assistant speech when the user had not asked for it. A dense set of nearby assistant statements could consume the scan budget and hide an otherwise valid user memory. The same late filtering affected association and episode expansion.

Ordinary recall now applies the existing assistant-speech definition before the SQL limits, across lexical, vector, source-bridge, passage, neighborhood, association and episode paths. This preserves the existing three claim kinds and legacy direct-capture marker; it does not guess roles from the language of a sentence. Explicit speech requests remain eligible. Additional retrieval cues cannot authorize speech. Learning callers and dependency loading retain their existing default behavior, and the scan limits are unchanged.

All **13 new candidate regressions failed on the baseline and pass after repair**. They include dense interference, synthetic vectors, cross-script retrieval, explicit Chinese/speech requests, legacy markers and graph expansion. A further **225 affected tests passed** in the isolated candidate worktree.

## Episode changes preserve valid semantic connections

Episode updates previously regenerated literal fragments and added only the current batch's claims. Existing semantic anchors, outlines and schemas disappeared from the new episode revision even when their source events remained members. This lost stored links used by both recall expansion and the structural graph.

An update now carries forward exact, current, available assertion versions from the previous episode membership. Newly generated fragments and claims are merged without duplicating identities. Each resulting episode accepts only memories whose complete evidence versions belong to it, including when an episode is split. Deleted, suppressed, invalidated, retracted, missing and noncurrent records are excluded. A newer replacement version is not linked automatically.

The original regression run reproduced **four failures**, with five exclusion controls already passing. The final **10 cases pass**, covering continue/close/reopen, all three semantic roles, exact graph edges, split boundaries, multi-source/contested members, retraction and replacement-version exclusion. An earlier invocation failed all nine fixture setups because the isolated wrapper omitted its migration connection; that failure remains in the evidence. Correcting the wrapper did not alter the product or acceptance assertions.

## Combined validation and limits

The combined source passes **347 related tests**, including consolidation, source recall, graph structure and archive behavior. A separately built and installed wheel matches all **187 runtime inputs** and passes **41 installed tests**. Its build identity is `f50158376a78f6d823c8c3fdcb2356a63402648f29fad4a921ebbb9a11b4ae81`. Both launcher-pin checks and full-source Ruff pass. All disposable test databases stopped and their profiles were removed.

[Raw red/green logs, wrapper failures, package identity and cleanup receipts](evidence/maturity-recall-episode-2026-11-06/manifest.json) preserve the results.

## Current-runtime installation and fullscreen qualification

The unchanged real-launcher acceptance driver passed **49/49 checks** against runtime `ee644c9`, using fresh basic and companion homes and the original frozen baselines. Both actual installations match all 187 runtime inputs. Upgrade, restart, MCP correction/deletion, the stub proxy, backup/restore activation and all companion persistence checks passed. All four profiles stopped and their eight ports closed.

The complete closed/open/open/closed fullscreen comparison also passed **all 36 windows**, with **4,080 nonempty recalls**. Worst individual-window p95 was **258.02 ms serial, 338.84 ms for eight workers on one brain, and 411.64 ms for eight brains**, below the unchanged 500/1,000/600 ms limits. The retained eight-brain corpus, 21-query worker protocol, declared first-query warmups, fresh APIs per phase and normal browser polling were unchanged. Chromium 153.0.8010.12 used Apple M4 Metal hardware rendering at 1,280 × 900, pixel ratio 1. Both open phases displayed 187 stored nodes and 71 edges whose exact identifiers and connections matched the real structure API before and after measurement; rendering advanced 1,152/1,165 frames. Screenshots were captured after timing with animation paused.

There were no page errors or external HTTP requests. Source/driver hashes remained unchanged and every fixture port closed. The [complete installed/visual evidence](evidence/maturity-recall-episode-installed-2026-11-06/manifest.json) retains the two exact source heads, runtime pin, scripts, all timings, screenshots and cleanup checks. Published payloads contain none of the owned test-profile credential values.

This qualifies keyword recall on the established reference fixture, with semantic processing disabled and no model calls. It does not establish arbitrary capacity or semantic/longitudinal quality. Full Verify for integration `72f2541` was superseded by the later affect-window repair before completion; no full Verify pass is claimed. R4 remains failed, C5 incomplete, and release remains frozen.


## CI disposition for this predecessor

Native qualification [42344062943](https://github.com/chriswu727/memBrain/actions/runs/42344062943) passed all five platforms on integration head `72f2541e09dd7a2ed6c36f818459a7606076c14d`. The artifact audit verified 47 completed summaries, zero model calls and every recorded port closure; five identical duplicate qualification summaries were excluded.

Verify [42344062942](https://github.com/chriswu727/memBrain/actions/runs/42344062942) was cancelled by workflow concurrency when integration advanced to `3dbefa2`, after the independently reproduced affect-window repair completed its scoped tests, fresh 49-check installation and complete 36-window R5 qualification. The cancelled run is not a passing result and was not restarted to search for a green outcome. [Raw job logs, artifact receipts and hashes](evidence/maturity-recall-episode-installed-2026-11-06/ci/manifest.json) preserve both outcomes. The successor requires its own full CI.
