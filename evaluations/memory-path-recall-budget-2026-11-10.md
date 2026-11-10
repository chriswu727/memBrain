# Recall block budget, note paging and extraction outcomes

Base: pin `77adbe69`. Runtime commit `1f5d2688`; pin commit `8223c2b6` points all nine launchers at it. No migration. This is the first memory-quality batch measured against the [LoCoMo evidence-recall baseline](locomo-evidence-recall-2026-11-10.md). It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Everything ran on WSL2 Linux with task-owned embedded PostgreSQL 16.15 and pgvector 0.8.6. No model was called. GitHub Verify, native Windows and macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.

## What changed

| Change | Before | Now |
| --- | --- | --- |
| Recall block size | At most twelve recalled source messages, however short; about half of the 9,000 characters went unused on LoCoMo | Up to forty, so the character budget decides. The eight following messages are unchanged: more of them crowded out evidence in the development sweep |
| Previous-prompt cue (audit H3) | Hosts that call `session_context` before every message (chat bots, the proxy, OpenClaw) lost the previous prompt each time, so their recall never had the cue the hooks have | The cue is kept across that call; a pause still clears it |
| Notes beyond the newest 200 (audit M1) | Only the newest 200 current notes were read, so an older pinned note or constraint was no longer a candidate for the session-start block, and an older note could not be replaced | Every current note is read, in up to ten pages of 200. When a later page cannot be read, the newest notes still show and the block says some were left out |
| Unreadable extraction output (audit M2) | Cut-off or malformed model output counted as a successful read with no notes and reset the failure count | It is a failed read, `unreadable_model_output`, and shows as degraded in the extraction status. An empty or `{"notes": []}` answer is still a normal read |

## Evidence recall

Same harness, data and installations as the baseline; only the host-side selection changed, so the stored brains were reused. Share of questions whose evidence turns are all in the recall block:

| | Questions | Runtime `ede5769` | This runtime |
| --- | --- | --- | --- |
| All | 1,535 | 52.7% | **60.6%** |
| Development conversations | 383 | 54.3% | 62.7% |
| Held-out conversations | 1,152 | 52.2% | **59.9%** |
| Held out, single-hop | 641 | 67.6% | 76.3% |
| Held out, temporal | 230 | 55.7% | 63.9% |
| Held out, multi-hop | 208 | 10.1% | 14.9% |
| Held out, open-domain | 73 | 26.0% | 31.5% |
| Held out, one evidence turn | 831 | 67.0% | 75.8% |
| Held out, several evidence turns | 321 | 13.7% | 18.7% |

- On the held-out conversations 93 questions gained all their evidence and 4 lost it (exact McNemar test, p < 0.001). The cap was chosen on the development conversations only.
- The recall block grew from 4,839 to 8,523 characters on average, within the 9,000 it was always allowed. The whole context grew from 14,124 to 17,808 characters and holds all the evidence for 62.7% of questions (55.1% before).
- Time did not change: per-prompt recall 322 ms median and 350 ms at the 95th percentile (324 and 350 before); session start 244 ms median (239 before).
- **Plain retrieval is still ahead.** BM25 plus embedding retrieval over the same messages has all the evidence for 73.6% of questions at 9,000 characters. The remaining gap is in which statements the service ranks first; about four in ten evidence turns were not among the statements it returned in the baseline's stage breakdown, and this batch does not change that.

Rows, summary and the comparison are in [results-2026-11-10](locomo/results-2026-11-10/) (`recall-1f5d268.jsonl.gz`, `compare-ede5769-1f5d268.txt`).

## Limits

- **More recalled lines reach the host on every prompt** when messages are short. Whether a host answers better, or misuses lines that are not relevant, is not measured here; the earlier answer run improved when the block went from eight to twelve messages, which is the only answer-level evidence in the same direction. Token use per prompt rises with the block.
- The cue change alters what recall is asked on chat-bot and proxy hosts from the second message of a session on. LoCoMo questions each start a new session, so the measurement above does not exercise it; it is covered by tests only.
- Note paging adds reads at session start once there are more than 200 current notes: one per further 200 notes, at most nine.
- The measurement shares the baseline's limits: retrieval and not answers, one benchmark, no notes, no corrections, no ageing.

## Verification

Results and log hashes are in [results.json](evidence/memory-path-recall-budget-2026-11-10/results.json). The suite run, its triage and the LoCoMo rerun were carried out by a delegated agent and its reported numbers were checked against the result files.

| Run | Source | Result |
| --- | --- | --- |
| New regressions | Runtime commit | `tests/test_recall_budget_and_notes.py`: 13 passed; the file does not import on the previous runtime |
| Full source suite | Pin commit `8223c2b6` | **8,486 passed, 0 failed, 15 skipped**, 3 fork warnings, 48 min 43 s. Runtime and migration files unchanged during the run |
| Ruff | `src tests examples` | Passed |
| LoCoMo evidence recall | Runtime commit, reused installations | Above; same 1,540 question ids and evidence lists as the baseline |

The 15 skips are Docker journeys and tests that need the pinned local embedding model. None of the four background-learning test files that failed intermittently in [the previous batch](backend-conversation-pause-scope-2026-11-10.md) failed in this run; that is one run and does not show they are fixed.

A pre-check of ten test files without a database was stopped by its ten-minute limit before it finished and produced no result; the full run above covers those files.
