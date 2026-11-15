# Memory evolution, evidence and enrichment: 2026-11-14

This batch joins three workstreams through observable evidence: correction/deletion across memory layers, a reproducible enrichment cost diagnostic, and experience-grounded companion state. It is not a new model or a behavioural acceptance. **R4 remains failed and C5 invalid/unscored.** No generative-model or subscription-backed evaluation, AgentDetox work, release or main-branch change was performed.

Runtime: `e8383a85d319e57a95f60b52dd64b930280c161d`. Launcher pin: `b4d0e76176c502ca74ccec7b602b44692efac866`. Final source including the corrected diagnostic: `f471c0db988f283c33f768a1a7ba6d7eaf2c37a1`. [Implementation PR #68](https://github.com/chriswu727/memBrain/pull/68) merged as `9e814d4f61fa90883ba2655ca0bb280a3053846c`; its tree exactly matches the qualified source. [Evidence bundle](evidence/memory-evolution-2026-11-14/qualification.json).

## A concrete provenance defect fixed

A host could propose “be more patient” using a message, then still have that suggestion accepted after the message had been edited to withdraw the request or erased. Citations by stable event ID also showed later revisions as though they explained an earlier suggestion or decision.

Host suggestions now expose an additive `evidence` object. It distinguishes available citations, messages not yet recorded, unavailable citations and suggestions that cited no messages. Counts describe citations; two forms naming the same message share one displayed quote. The API and memory page agree:

- A changed, erased, suppressed or ineligible cited message withdraws an undecided suggestion. The host must propose a fresh change against current evidence.
- A pending source cannot authorize acceptance. The page explains the wait and disables Accept; the service enforces it too. Deferred confirmation rechecks eligibility without preventing the user's message itself from being recorded.
- The source must still be an eligible real user message. Quotation, role-play and hypothetical hints cannot become evidence merely by arriving after the proposal.
- A historical accepted/rejected decision stays a decision. Its surviving quotes and graph edges cannot attribute a later revision to the original decision. Keeping an accepted persona is a user-choice rule, not proof that missing evidence remains valid.
- The companion graph now links an accepted host proposal to the persona version that names it, using the actual host-proposal field as the edge basis.

Reads batch citations and select each stable event's newest revision rather than materializing its full revision history. Acceptance and message changes retain the existing brain transaction lock. No migration, dependency upgrade, broad adapter rewrite or model call was introduced.

Uncited suggestions remain supported and visibly labelled, preserving existing callers. A restored reference whose source identity was not preserved is unavailable, not a message supposedly still waiting to record. This batch does not reconstruct that identity. Source eligibility and correct revision attribution do not establish that the host's interpretation is true; the existing user-confirmation requirement remains essential.

## A complete experience crossing the layers

The [fixed-clock scenario](../tests/test_memory_evolution_scenario.py) records a shared practice experience, attaches a source-linked note and an explicitly inferred feeling, writes retrieval cues, and proposes a persona change. It verifies that repeated state/graph reads create no experiences and do not promote the inference to a reported feeling.

Editing the original retires the old note/affect, removes its cue, removes the shared-moment contribution and withdraws the unaccepted persona suggestion. A new, explicitly reported feeling can explain the next simulated mood; a new persona change still requires the user's later confirmation. Three days without a trigger returns the simulated mood to baseline without changing the accepted persona. Source erasure removes the derived note and feeling and the decision's evidence; archive restore cannot invent that evidence. The user can restore the earlier persona and reset relationship history.

The pre-existing host/MCP lifecycle scenario also passed in the broader batch, including correction, erasure and prevention of resurrection from a pre-deletion archive. These are state invariants with scripted host choices, not proof of real host judgement, long-term personality consistency or human emotion.

## Same-source enrichment diagnostic

[Runner and protocol](memory-evolution/README.md); [fixed corpus](memory-evolution/fixture.json). WSL2 Linux, Python 3.12.16, PostgreSQL 16.15, loopback HTTP, semantic embeddings off, sequential concurrency, 40 synthetic messages and eight fixed questions. All arms use the production host recall/context path and the same 2,400-character final cap. The note arms include an uncached note read per query. Ten warm repetitions measure the same eight questions; they are not 80 independent examples.

| Arm | First-pass evidence present | Warm evidence present per eight questions | Warm median / p95 | Median supplied characters | Logical bytes in measured tables |
| --- | --- | --- | --- | --- | --- |
| Original records | 2/8 | 2/8 | 33.71 / 63.51 ms | 272 | 83,878 |
| Records + scripted notes | 6/8 | 6/8 | 43.71 / 67.91 ms | 1,686 | 102,146 |
| Records + notes + scripted cues | 6/8 | 8/8 | 48.12 / 94.96 ms | 2,057 | 105,018 |

First-pass latency medians/p95 were respectively 35.61/190.32, 66.61/367.63 and 75.37/206.05 ms. These first measurement requests follow a known-fact positive control; neither OS nor PostgreSQL caches were cleared. The first-pass shortfall in the cue arm is retained rather than replacing it with warm results.

In this small fixture, notes and cues expose more expected evidence at additional context, storage and latency cost. The cue batches carried 7,103 input characters and 471 scripted output characters; their measured batch read/write time was 33.22 ms. Note-write times were 80.54 ms in the note arm and 64.34 ms in the cue arm. These separate small-run timing differences are not an optimization claim. The logical row-size increase was 18,268 bytes for notes/dependencies and another 2,872 for cues/progress. It excludes indexes, WAL and filesystem allocation and says nothing about long-term storage growth.

No answer was generated or graded, and no host AI produced these notes/cues. This is a hand-authored diagnostic, not a held-out quality benchmark. The raw arm uses memBrain's existing record-retrieval path without enrichment, not an independently implemented search engine. Model token usage, model-generation latency/cost, large-corpus persona-evidence lookup cost and production capacity remain unmeasured. These numbers must not be compared with earlier Mac or temporary-chat measurements.

The [first contexts and all query measurements](evidence/memory-evolution-2026-11-14/queries.json.gz) are retained. The measured corrected harness was committed unchanged as `f471c0db`; the saved working-tree patch exactly matches that commit's delta from `b4d0e761`. Runtime and fixture hashes stayed unchanged during measurement.

## Verification and retained failures

- The pre-change reproducer failed on the actual defect: the changed-source proposal was still `open`.
- Development runs caught a changed same-turn refusal diagnostic and selection of an older row when an event had multiple revisions. Both were repaired before the final qualification. A missing `made_by` argument in the scenario fixture was also corrected.
- The broader local batch recorded **369 passed, 3 failed**. Those three failures were new fixture errors: two invalid interpretation-hint enum names and a browser assertion against a collapsed history section. They remain in the evidence.
- The final related batch recorded **67 passed**, including the cross-layer scenario, source corrections, archive cases, real Chromium UI, graph projection and translations. PostgreSQL stopped and the runtime remained unchanged throughout. These 67 overlap the broader batch and must not be added as distinct tests.
- Launcher pin checks: **2 passed**. Ruff passed for the runtime, tests, examples and diagnostic.
- Full Verify: **4,084 Python tests passed, zero skipped, three existing fork warnings; 39 TypeScript tests passed, zero skipped** on [run 43664724697](https://github.com/chriswu727/memBrain/actions/runs/43664724697). Ruff, the TypeScript type check and sdist/wheel builds passed. The earlier run [43664462365](https://github.com/chriswu727/memBrain/actions/runs/43664462365) was cancelled when the diagnostic correction was pushed; it is not a successful qualification.
- The **first comparison is invalid**: its script bypassed the production host historical cutoff and allocated too little internal document budget. Its empty recall cannot establish enrichment gains. Original results and an explicit invalidation are retained. The corrected runner uses the real host path and must pass a known-fact control in every arm before measuring.

This is WSL/Linux engineering evidence; it is not new Windows-native, macOS or real-host behavioural qualification. The prior five-platform native engine result remains evidence for its earlier source, not a new pass on this runtime.

All task-owned local test services and synthetic database/install directories were stopped and removed after results were retained ([cleanup](evidence/memory-evolution-2026-11-14/cleanup.json)). Source worktrees, real profiles, models, backups and Claude's Remote Control session were preserved.

## Next work

Use a larger fixed corpus and held-out questions to test enrichment without saturating eight hand-authored cases; measure long-term storage and source lookup at realistic history sizes. Ordinary note correctness still depends on the host's interpretation: provenance does not turn a guess into a fact. Broaden cross-layer cases to multiple conflicting sources and delayed edits before touching ranking rules. Real-host consolidation behaviour and longitudinal persona/relationship behaviour require their own valid acceptance protocol and any new paid authorization. This batch does not close R4, C5 or the final release gate.
