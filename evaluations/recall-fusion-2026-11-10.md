# Rebalancing the keyword and meaning routes in recall ranking

Base: pin `8223c2b6`. Runtime commit `b301c556`; pin commit `6c0f8d12` points all nine launchers at it. No migration. Second memory-quality batch measured against the [LoCoMo evidence-recall baseline](locomo-evidence-recall-2026-11-10.md). It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Everything ran on WSL2 Linux with task-owned embedded PostgreSQL 16.15 and pgvector 0.8.6. No model was called. GitHub Verify, native Windows and macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.

## What was wrong

The service ranks statements on two routes, keyword and meaning (embedding), and fuses the two rankings. Observing each stage on the three development conversations (519 evidence turns, runtime `1f5d268`; [ranking_stages.py](locomo/results-2026-11-10/ranking_stages.py), [output](locomo/results-2026-11-10/ranking-stages-1f5d268.txt)):

| Ranking | Evidence turns in the first 10 | In the first 62 (the candidates kept) |
| --- | --- | --- |
| Keyword route alone | 53.9% | 73.6% |
| Meaning route alone | 31.8% | 54.7% |
| Fused, as it was | 43.7% | 66.1% |

**The fused order was worse than the keyword route alone.** A keyword rank was multiplied by its raw lexical score (0.34 on average for the evidence) while a meaning rank counted in full, so the weaker route decided the order. Of the evidence turns that never reached the context, three quarters were lost at this step ("fused rank beyond 62": 30.6% of all evidence turns).

## What changed

One function, `_direct_candidates`:

- **Keyword matches count in proportion to the query's best lexical match.** A full match stays well ahead of a partial one, as before.
- **Weak overlap stays weak.** When even the best match covers less than 0.3 of the query's weighted terms, all keyword matches are scaled down with the square of the shortfall.
- **Meaning matches count half.**

## Result

Share of questions whose evidence turns are all in the recall block, same harness, data and stored installations:

| | Questions | `ede5769` (morning) | `1f5d268` | This runtime |
| --- | --- | --- | --- | --- |
| All | 1,535 | 52.7% | 60.6% | **68.0%** |
| Development conversations | 383 | 54.3% | 62.7% | 71.5% |
| Held-out conversations | 1,152 | 52.2% | 59.9% | **66.8%** |
| Held out, single-hop | 641 | 67.6% | 76.3% | 84.6% |
| Held out, temporal | 230 | 55.7% | 63.9% | 68.7% |
| Held out, multi-hop | 208 | 10.1% | 14.9% | 21.2% |
| Held out, open-domain | 73 | 26.0% | 31.5% | 35.6% |
| Held out, one evidence turn | 831 | 67.0% | 75.8% | 82.9% |
| Held out, several evidence turns | 321 | 13.7% | 18.7% | 25.2% |

- Against `1f5d268` on the held-out conversations, 89 questions gained all their evidence and 9 lost it (exact McNemar test, p < 0.001). The weights were chosen on the development conversations only.
- The recall block is 8,660 characters on average (8,523 before). Per-prompt recall takes 322 ms at the median and 348 ms at the 95th percentile, unchanged; session start 244 ms.
- Plain BM25 plus embedding retrieval over the same messages has all the evidence for 73.6% of questions at 9,000 characters (72.7% held out). The gap was 21 points in the morning and is under 6 now. Multi-hop questions remain far behind (21.2% against 30.8% held out).
- **Evidence only the meaning route can reach is not pushed out.** For the 61 development evidence turns with no keyword match, the share ranked within the 62 candidates kept is 36.1% before and after; within the first ten it falls from 13.1% to 8.2% (8 turns to 5).

## A variant that was rejected

The first version gave every keyword match full weight once its lexical score reached 0.2 and scaled it with the square below that, again with meaning at half. It measured slightly higher (held out 68.6%, all 69.8%) and passed the fusion unit tests, and was committed and pinned locally as `53edb4a6` / `0c582b27`. The full suite then failed two ranking tests on every run:

- `tests/test_candidates.py::test_episode_seeds_neither_boost_themselves_nor_exhaust_neighbor_slots`: a partial keyword match outranked the episode neighbour of a full match;
- `tests/test_source_candidates.py::test_broad_citation_does_not_inflate_concentration_of_disconnected_query_cues`: a source holding every query cue no longer scored twice one that scatters them.

Both tests pin the same thing, the distance between a strong and a partial match, which the threshold flattened. Those commits were never pushed and were replaced by the proportional rule above; its measurement files are kept with a `rejected-` prefix in [results-2026-11-10](locomo/results-2026-11-10/).

## Limits

- **The meaning route is still weak, and this change works around it.** Statements are embedded one sentence at a time, without their message's speaker, date or neighbouring sentences. Halving its weight is right for the ranking as it is; the repair is to embed statements with their context, which is the next piece of work. A follow-up diagnostic on this runtime ([message_level_routes.py](locomo/results-2026-11-10/message_level_routes.py), [output](locomo/results-2026-11-10/message-level-routes-b301c55.txt)) ranks source messages on the development conversations: the statement-level meaning route puts an evidence message in the first ten for 31.8% of evidence turns, the same model over whole messages for 53.4%, and the service's keyword route fused with that whole-message route for 62.2% (76.9% in the first forty), against 54.1% and 74.2% for plain BM25 plus embedding retrieval. That is a simulation, not an implementation.
- Queries whose answer shares no word with the question depend on the meaning route. They keep their place among the candidates on the development split, but rank lower within it. The project's cross-script fixture of 2026-11-07 was not rerun; its regression tests are part of the suite and pass.
- One benchmark, retrieval and not answers, with the limits listed in the [baseline](locomo-evidence-recall-2026-11-10.md#limits).

## Verification

Results and log hashes are in [results.json](evidence/recall-fusion-2026-11-10/results.json). The suite runs and their triage were carried out by a delegated agent; its numbers were checked against the result files.

| Run | Source | Result |
| --- | --- | --- |
| Ranking test files, fresh database | Working tree before the commit | 12 files on candidates, sources, fusion, semantic pools, cross-script recall and diversity: 222 passed |
| Full source suite, with the local embedding model | Pin commit `6c0f8d12` | **8,495 passed, 2 failed, 4 skipped**, 3 fork warnings, 47 min 43 s. Runtime and migration files unchanged during the run |
| Full source suite, rejected variant | `0c582b27` | 8,495 passed, 2 failed (the two ranking tests above, 3 of 3 on rerun), 4 skipped |
| LoCoMo evidence recall | Runtime commit, reused installations | Above |
| Ruff | `src tests examples` | Passed |

The embedding-model tests, skipped in every earlier local run for lack of the model, ran in both suite runs and passed (21 tests in three files). The 4 remaining skips are Docker journeys.

### Failures in the full run

- `tests/test_longitudinal_evaluation.py::test_complete_scenario_through_real_loopback_http_has_no_automatic_semantic_pass` stopped with `CampaignStopped: literal_work_previously_attempted`, raised by the background-learning harness before any result was checked. Rerun alone against the same database it passed 3 of 3, and it passed in the four earlier full runs on this machine, including the rejected variant's. Not reproduced; cause not established. It is not one of the four files known to fail intermittently, and it does exercise recall, so the change is not ruled out.
- `tests/test_longitudinal_learning.py::test_job_bound_stops_before_further_claims_and_keeps_pending_debt` failed its dispatch-limit assertion. That file is one of the four background-learning files that fail intermittently on earlier runtimes as well; it was not rerun.

Neither is counted as a pass.
