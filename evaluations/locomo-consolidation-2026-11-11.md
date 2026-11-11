# Consolidation into notes did not help LoCoMo answers; messages alone scored 88.1% on the development split

Result of the [plan of 2026-11-11](locomo-consolidation-plan-2026-11-11.md), run as written. Runtime `933f4d8` (checkout `e4727375`), three development conversations, 385 questions, DeepSeek paid calls approved by the owner. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Result

Answers by `deepseek-flash` with thinking off, judged by the same model with Mem0's judge prompt. Every arm answered the same 385 questions.

| | Messages only (`plain`) | Notes after every turn (`turn`, Flash) | Notes after every session (`session`, Pro) |
| --- | --- | --- | --- |
| All questions (385) | **88.1%** | 84.7% | 86.0% |
| Several evidence turns (92) | **76.1%** | 68.5% | 65.2% |
| One evidence turn (291) | 91.8% | 89.7% | 92.4% |
| Multi-hop (74) | 75.7% | 73.0% | 71.6% |
| Temporal (90) | 88.9% | 88.9% | 94.4% |
| Open-domain (21) | 85.7% | 61.9% | 52.4% |
| Single-hop (200) | 92.5% | 89.5% | 91.0% |
| Notes written | 0 | 170 | 102 |
| Model calls and cost while storing | none | 1,451 calls, 7.19 CNY | 70 calls, 12.74 CNY |

- **Neither form of notes improved answers, and on the questions they were meant for they did worse.** Against messages alone, on questions with several evidence turns: session consolidation gained 3 and lost 13 (exact binomial p = 0.02); per-turn extraction gained 3 and lost 10 (p = 0.09). On all questions: session gained 12 and lost 20 (p = 0.22); per-turn gained 10 and lost 23 (p = 0.04).
- Per conversation, messages alone were ahead in all three: 90.1%, 82.7% and 88.8%, against 87.5%, 81.5% and 86.8% with session notes.
- Session notes did better on temporal questions (94.4% against 88.9%), where a note carries an absolute date.
- **By the plan's rule, consolidation in this form is not built into the product.**

### Why the notes did not help

From the notes each arm wrote ([consolidation-notes.json.gz](locomo/results-2026-11-11/consolidation-notes.json.gz)) and the contexts:

- **Most notes were never shown.** The session-start block holds about 3,300 to 3,900 characters of notes: 10 to 15 notes out of 27 to 83. Which ones are shown is decided by kind and recency, not by the question.
- **The notes that were shown took the place of history.** The context is the same size in every arm (about 17,900 characters); the notes block replaces about a third of the session-start part.
- **Merging happened, but what remained still read as one note per event.** The Pro model proposed 207 notes; 192 were saved, 90 of them replacing an earlier note, 15 were refused by the note writer (mostly for length) and one output was unreadable, leaving 102. Reading them, a list of everything a person does, the thing a multi-evidence question needs, mostly did not come to exist; this was judged by reading the notes and not measured.
- **A partial note can mislead.** Asked whether a person lives near a beach or the mountains, the arm with notes answered "mountains" from a note, where recall alone had shown the turn about weekly ocean sunsets.

These are observations on this run, not a tested explanation. Which of them matters most was not isolated.

### Messages alone: 88.1%

On the same three conversations, with the same answer model and judge, the [2026-10-29 run](locomo-2026-10-29.md) scored the plugin path 70.1%, then 77.1% after its recall changes, and the full conversation in the prompt 81.8%. Since then the recall block was enlarged, the ranking routes rebalanced and statements embedded as whole messages; evidence recall on these conversations rose from 54.3% to 79.9%.

**The comparison with 81.8% is across runs twelve days apart and is not a same-day measurement.** The provider serves `deepseek-flash` under one name and may have changed it; the full-context arm was not repeated. The seven held-out conversations were not run. Until both are, this is a strong indication on the development split and not a result.

## Cost

38.07 CNY of the 60 CNY ceiling, priced at peak rates without cache discount; the provider's actual charge was not read. 3,983 Flash calls (12.4 million input tokens) and 71 Pro calls (0.2 million input, 0.41 million output tokens, most of it reasoning). No request ended without usage accounting, and none was refused.

- Answering 385 questions cost about 6 CNY per arm.
- Per-turn extraction cost 0.005 CNY a turn.
- Session consolidation cost 0.18 CNY a session, about thirty-five times a turn's extraction, for fewer notes.

## What happened during the run

- The pilot on `conv-30` completed for 8.79 CNY and decided nothing, as planned.
- The run on the other two conversations was stopped by the two-hour limit of the shell that started it, during the session arm's consolidation of `conv-41` (session 28 of 32). It was resumed for that arm and conversation only. The consolidation call in flight when it was stopped has no ledger entry and was repeated; its cost, at most 0.3 CNY, is not in the total.
- One additional Pro call and one Flash call were made before the pilot to check the key and the model names (0.0014 CNY, in the ledger as `preflight`).

## Limits

- One benchmark of two people chatting, stored as one user's messages, with no assistant replies; one answer model and a judge of the same family; one run per arm.
- The notes arms were limited by the product's own session-start budget for notes. A design that brings a note to the context because the question calls for it was not tested; nor was consolidation by the host's own model.
- 92 multi-evidence questions support a statement about the direction of the difference, not its size.

Files: answers per arm, the ledger, the notes and the summary are in [results-2026-11-11](locomo/results-2026-11-11/) (`consolidation-*`).
