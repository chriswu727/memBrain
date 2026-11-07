# Rare lexical cues under bounded candidate admission

Runtime `fb249da5d75b29a2eea0dcf6a19b29f0d2e29cc3` fixes a reproduced recall omission on a public synthetic corpus. Both previous admission channels ordered by feature-hash distance. A memory that matched the requested unique label could be discarded before the source-aware lexical scorer saw it, while many similar records matching common query words filled the candidate budget.

## Reproduction and repair

The original installed probe ingested 1,000 and then 10,000 distinct labelled messages, plus 100 source-linked plan notes. All 80 bounded structural-map requests succeeded. All 20 queries at 1,000 messages succeeded; at 10,000, the first query succeeded and the second omitted `memorykey000526`, stopping the run. This original run remains **failed**, with the remaining 18 queries unattempted. The queue had settled; direct inspection confirmed durable and indexed sequence 10,100 and a current eligible target. Its lexical score was 0.502 versus a maximum 0.004 among the admitted candidates, but it was absent from their pool.

Admission now projects eligible IDs, hash distance and search lexemes once. Each logical query word, including its stem aliases, gets at most `limit+1` narrow candidates. The full-text channel favors the smallest capped matching pools, then pool coverage and hash distance, within its original limit. The hash channel and pure-CJK fallback remain available. Full documents are read only after ID selection; final output remains at most `2*limit`. Both channels retain independent overflow sentinels before document deduplication. Scope, speech, lifecycle, excluded-version, independent-source and frozen-sequence filters run before selection. This is admission priority, not a new probability or exact corpus-wide IDF statistic.

Two real-hash regression cases failed before repair: a rare label accompanied by common words, and a target matching only the rare cue while distractors matched three common query words. An initial per-word database scan restored admission but was too expensive: paired candidate p95 was 490.914 ms versus 135.561 ms, and a 128-word query took 13,327.773 ms. Execution plans exposed repeated eligibility checks and tokenization. The shared projection removes that repetition; logical word ordinals also keep parser aliases from merging frequency groups.

## Exact installed runtime evidence

The related source group passed **307 tests**. After the final word-group guard, **25 lexical tests** passed again; the installed wheel passed **38 tests**. Both launcher-pin checks and full-source Ruff passed. All **187 installed runtime inputs** match the source; only `lexical_candidates.py` differs from runtime `5048e13`. Independent read-only review found no remaining correctness issue, while identifying the scaling limitation below.

On the retained, fully indexed 10,000-message corpus, the final installed paired candidate replay admitted the target in **20/20** queries versus **7/20** for the frozen predecessor implementation. With alternating execution order and no discarded samples or retries, p95 was **152.609 ms repaired versus 140.196 ms predecessor**; maxima were 164.560 and 181.179 ms. An earlier pre-final replay measured 127.862 versus 136.402 ms; both are retained, so these results are not presented as a stable speedup.

The actual installed HTTP recall path found **20/20** original targets: median **201.710 ms**, p95 **351.454 ms**, maximum **598.477 ms**, including its first request. All 40 structural-map requests satisfied unique-node, size and edge-endpoint checks. At 200 nodes/400 edges, map p95 was 50.119 ms; at 500/1,000 it was 60.466 ms. These map checks used the settled retained corpus and do not repeat the original concurrent-ingestion workload. All service/database ports closed.

This is literal-cue, keyword-mode evidence with synthetic messages, not semantic quality, arbitrary memory capacity or human-like emotional development. The shared projection still scales with eligible record count and text length, and up to 128 term scans can amplify temporary-file I/O after PostgreSQL spills beyond `work_mem`. No million-record latency claim is made.

## Exact-runtime installation and fullscreen qualification

The unchanged fresh-home launcher driver passed **49/49** checks across basic and companion homes: install/upgrade, cross-session recall, MCP correction and deletion, restart, stub proxy, backup/restore, persona, mood and relationship-state preservation. Both installed homes match all 187 runtime inputs. Four profiles stopped and all eight ports closed.

The complete closed/open/open/closed R5 protocol passed **36/36 windows**, with **4,080 nonempty measured recalls**. Worst individual-window p95 was **256.35 ms serial, 318.31 ms for eight workers on one brain and 295.06 ms for eight brains**, against unchanged limits of 500/1,000/600 ms. The retained reference corpus, three cycles per phase, discarded first sample per 21-query worker, fresh API per phase and normal 30-second polling were unchanged.

Chromium 153.0.8010.12 used Apple M4 Metal rendering at 1,280 × 900 and device pixel ratio 1. Both visible open phases showed **187 nodes and 71 edges**, with exact agreement against the structural API before and after measurement. Animation advanced 992 and 986 frames. There were no page errors or external HTTP requests. Source and driver hashes remained unchanged and all fixture ports closed.

## CI and release status

The predecessor candidate `3dbefa2`, runtime `5048e13`, completed [Verify 42345840409](https://github.com/chriswu727/memBrain/actions/runs/42345840409): **7,648 Python tests**, three warnings, **50 TypeScript tests**, type checking, Ruff and package build passed. Its [native run 42345840417](https://github.com/chriswu727/memBrain/actions/runs/42345840417) passed all five platforms; 47 distinct installed/native summaries were audited as completed, zero model calls and recorded ports closed. Those results belong to the predecessor, not this new runtime. Full candidate CI for `fb249da` remains pending.

[Raw failures, implementation variants, execution plans, paired timings, installed results, screenshots and predecessor CI](evidence/maturity-lexical-cue-2026-11-06/manifest.json) are preserved with hashes and owned-profile credential scans. Initial implementation failures from a missing `fetchall()` and a pin-test invocation naming a nonexistent file are retained separately from their corrected runs. No hidden scenarios or provider calls were used.

The [third behavioral attempt](maturity-third-attempt-2026-11-06.md) still fails R4 and leaves C5 incomplete. This repair does not establish the cause of that sealed failure or replace a fresh authorized acceptance run. Main merge, tagging and release remain frozen.
