# Third maturity attempt: R4 failed; C5 incomplete

Attempt `maturity-20261106b` followed its [execution binding](maturity-acceptance-execution-2026-11-06b.md) on frozen source `2f7d9a9501f57a596d59ceb63a3a7db13c31820b`, with runtime `cc2a60176499c97bc7423199363dbd9311452dcf`. S1 and S2 completed and passed strict validity, making R4 eligible for scoring. C1 failed during execution and C2 did not run, so C5 is ineligible and was not scored. No release gate was relaxed.

## R4 result

The completed blind pipeline returned **FAIL**. The plugin arm fails both the relative score requirement and the prohibition on memory-caused critical errors. The extraction arm passes R4 for this attempt; that does not make the product accepted.

| Arm | S1 | S2 | Total | Memory-caused critical replies | Host-caused critical replies | R4 |
| --- | --- | --- | --- | --- | --- | --- |
| Plugin (`P`) | 9.5 | 8 | 17.5 | 2 | 1 | Fail |
| Extraction (`E`) | 10 | 10.5 | 20.5 | 0 | 0 | Pass |
| Full-history reference (`F`) | 10 | 9 | 19 | Not attributed | Not attributed | Reference |

The score threshold is 18, the reference total minus one. P has two type-4 marks (invented user facts) and one type-1 mark (unconfirmed completion). F has two critical replies, both type 4. The table's attribution counts are aggregate counts; it does not infer which individual mark has which cause.

All 22 second reviews, 38 R5 judgments, two resolutions and six attribution judgments completed and validated, with no review retries, missing/invalid attributions or disagreeing attribution pairs. R5 cleared none of its 19 candidate replies. Resolution removed type-4 marks from nine S1 replies and six S2 replies under R2 before tallying. The gate ran once and exited 1; scores were not adjusted by hand. All 513 frozen hashes matched. The [aggregate scoring receipt](maturity-third-attempt-2026-11-06.json) preserves the coordinator's summary, artifact hashes and validation counts without exposing held-out content.

## Execution stop and cost

Execution stopped at 22:20:08 UTC on November 6 (14:20:08 Vancouver). S1 completed 62 turns per arm and S2 64. C1 stopped with P at 32 of 64 turns, E at 25 and F at 40. P recorded `page_action_failed`; the first shared ledger stop reason was `harness_degraded`. A request recorded `provider_transport` with class `SystemExit` during termination. This does not establish an independent provider outage or timeout. The hidden C1/C2 material remains sealed.

The shared ledger reserved 717 requests and settled 716. Conservative settled cost is 48.080210 CNY; one unknown request retains its 20.054016 CNY reservation, for 68.134226 CNY accounted against the 280 CNY cap. The balance observation decreased from 190.88 to 182.20 CNY (8.68 CNY), which is not a final invoice. The ledger remains blocked; unknown reservations were not released. No automatic retry or additional paid attempt is authorized by this result.

## Development follow-up

A separate worktree reproduced two source-level defects using public synthetic inputs: auxiliary retrieval cues enabled assistant speech even when the current question did not ask for it, and draft/cancelled messages could be accepted as note sources. The repair narrows speech eligibility to the current request, filters direct host recall hits and fallback statements, and rejects unusable note sources atomically. Explicit requests for earlier assistant speech and delivered assistant commitments remain supported.

These are independently reproduced defects, **not an established explanation of the held-out errors**. Source links establish provenance and deletion dependencies; they do not prove a model-authored note's text is entailed by its sources. The stopped attempt and its frozen source remain unchanged. Any new behavioral acceptance must use new held-out scenarios and separate authorization. R4, C5 and final release review still block merging or publication.

Local regression checks reproduced 12 failures on the original implementation: six cognition/host cases, four PostgreSQL candidate cases, and two note-source cases. The repaired affected suites pass 221 distinct tests across runs: 159 cognition/context/host tests, 24 candidate tests, 15 note-workflow tests and 23 note/typed-note tests. Scope overlaps in intermediate runs are not added to this total. Full-source Ruff and diff checks pass. An independent source review found no blocking issue in the recall patch.

Local service verification initially failed because detached services strip `PYTHONPATH` and imported the old editable checkout. A small isolated interpreter referencing the new worktree resolved the build mismatch. Two overlapping real-service checks then encountered native startup guards; both passed in a serial rerun after the earlier processes ended. These failed attempts remain recorded locally. No model API was used. Full candidate CI and new-runtime installed qualification are still pending at this checkpoint.
