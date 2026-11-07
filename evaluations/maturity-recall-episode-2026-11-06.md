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

[Raw red/green logs, wrapper failures, package identity and cleanup receipts](evidence/maturity-recall-episode-2026-11-06/manifest.json) preserve the results. These source and installed checks do not substitute for full CI, clean-home launcher acceptance, complete fullscreen R5 or held-out R4/C5. The separately documented [49-check installation and 36-window visual qualification](maturity-installed-visual-2026-11-06.md) applies to the preceding runtime `004a0f1`; current-runtime requalification is still in progress. R4 remains failed, C5 incomplete, and release remains frozen.
