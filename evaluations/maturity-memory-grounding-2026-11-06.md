# Memory grounding repair

Runtime `f9bcf2e0301af39027d5afc07b9afe7469232aab`, pinned by all nine launchers in `df3ceaee0989ace2db6eed8fb102cd06f8c112fe`, repairs two independently reproduced problems in memory provenance. It does not establish the cause of the [third attempt's held-out failures](maturity-third-attempt-2026-11-06.md), and does not pass R4 or C5.

An earlier question such as “Which kettle did you recommend?” was included as an auxiliary retrieval cue for a later ordinary question. The combined text enabled assistant-speech candidates even though the current request did not ask for them. The host also filtered following assistant replies but not directly ranked assistant messages or its statement fallback. The repair makes speech eligibility depend on the current request, while retaining cues for ranking, and filters all host recall paths. Explicit queries and API intents asking for assistant speech remain supported.

Separately, note writes accepted draft/cancelled message IDs as source evidence even though ordinary source linking excludes those delivery states. They now fail atomically with `source_unavailable`, leaving a replaced note unchanged. Delivered assistant commitments remain valid. Source links establish provenance and deletion dependencies, not semantic entailment of model-authored summaries.

## Verification

Twelve new regression cases failed on the original implementation. The repaired affected suites pass **221 distinct tests** across runs, plus two launcher-pin checks. Full-source Ruff and diff checks pass; independent review found no blocking recall issue. Local service tests initially imported the old editable runtime because detached services discard `PYTHONPATH`; a small isolated interpreter resolved that mismatch. Two overlapping native-startup checks passed when rerun serially. The failed attempts were retained locally.

A freshly built and installed wheel matches all **187 runtime inputs**, with build identity `b6e841c782a95363291a520a8404c89e08b446c332a868b2b1a98b74f9c1ec5d`. Four real-service checks pass: first use/correction/deletion, hooks across sessions, complete history across sessions, and typed-note/alias recall. This is scoped installed verification, not a fresh complete launcher upgrade/restore qualification.

Exact-candidate [Native qualification](https://github.com/chriswu727/memBrain/actions/runs/42337452261) passes on all five platforms. Its 47 distinct result/qualification summaries report completion, zero model calls and successful recorded port closure checks; five duplicate qualification copies are excluded. Two optional dispatch-only Linux jobs were not selected. [Full logs, terminal metadata and summaries](evidence/maturity-memory-grounding-2026-11-06/ci/manifest.json) are retained. Exact-candidate [Verify](https://github.com/chriswu727/memBrain/actions/runs/42337452260) passes: 7,583 Python tests, 50 TypeScript tests, strict TypeScript checking, Ruff and package builds. The three Python warnings and the cache-path/Actions runtime warnings remain in the retained raw job log. The CLI combined log omitted part of pytest output; the complete raw job log was fetched separately and used for the count.

## Installed performance

The unchanged canonical benchmark ran once against the fresh wheel on the reference Mac: 1,000 keyword messages per brain, eight brains, 100 notes in the first brain, index caught up before measurement, semantic model disabled, zero model calls. Each worker performs 21 rounds and discards only its first warm-up. It excludes client startup and reply generation. The optional bulk-write extension was not run.

| Workload | Measured calls | p95 | Required bound | Result |
| --- | ---: | ---: | ---: | --- |
| Serial recall | 20 | 222.65 ms | <500 ms | Pass |
| Eight concurrent recalls, one brain | 160 | 360.87 ms | ≤1,000 ms | Pass |
| Eight concurrent recalls, eight brains | 160 | 332.39 ms | ≤600 ms | Pass |
| Map, 200-node limit | 20 | 10.84 ms | No gate in this run | No errors |
| Map, 500-node limit | 20 | 14.28 ms | No gate in this run | No errors |

All 340 measured recalls returned nonempty content. This workload measures latency, not answer accuracy or general memory capacity. It is not a semantic-recall result or the complete 36-window fullscreen R5 comparison. [Raw measurements, installed parity and hashes](evidence/maturity-memory-grounding-2026-11-06/manifest.json) are retained. The synthetic test and benchmark databases were stopped and removed after verification; benchmark API/database ports were confirmed closed. Original memory databases, models and frozen acceptance material were preserved.
