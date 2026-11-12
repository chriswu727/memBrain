# First test on a benchmark memBrain was not tuned on: level with plain retrieval for what users said, far behind for what the assistant said, and two seconds a recall

Result of the [plan of 2026-11-12](longmemeval-plan-2026-11-12.md), run as written: 60 LongMemEval questions, ten of each type, on runtime `75f50fd` unchanged, no cues and no notes. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Result

Share of questions whose evidence turns are all shown. M is memBrain through the plugin path; R is plain retrieval (BM25 and the same embedding model) over the same stored turns, filling the same number of characters.

| | Questions | M, recall block | R, same size as the block | M, whole context | R, same size as the context |
| --- | --- | --- | --- | --- | --- |
| **All** | 60 | 78.3% | 86.7% | 78.3% | **96.7%** |
| Evidence in what the user said | 51 | 90.2% | 84.3% | 90.2% | 96.1% |
| Evidence in what the assistant said | 9 | 11.1% | 100% | 11.1% | 100% |
| Knowledge update | 10 | 90% | 100% | 90% | 100% |
| Several sessions | 10 | 100% | 70% | 100% | 100% |
| One session, assistant's words | 10 | 20% | 100% | 20% | 100% |
| One session, a preference | 10 | 70% | 60% | 70% | 80% |
| One session, user's words | 10 | 90% | 100% | 90% | 100% |
| Temporal reasoning | 10 | 100% | 90% | 100% | 100% |

- Recall block against plain retrieval of the same size: memBrain complete where plain retrieval is not on 5 questions, the reverse on 10 (exact two-sided binomial p = 0.30).
- Whole context against plain retrieval of the same size: 1 against 12 (p = 0.003).
- The recall block averaged 7,448 characters and the whole context 16,702. Half the blocks were under 8,000 characters.
- **One recall took 2.07 seconds at the median and 3.1 seconds at the 95th percentile** (two workers ran side by side; the one history run alone before the sample took 1.9 seconds). On LoCoMo it is about 0.33 seconds.

## What it shows

**1. For what the user said, the ranking carries over.** On the 51 questions whose evidence is in the user's messages, the recall block has all of it for 90.2%, against 84.3% for plain retrieval of the same size. The sample is small and the difference is not significant, but the ranking chosen on LoCoMo is not behind on a different kind of history, and it is ahead on questions that span several sessions.

**2. What the assistant said is almost never shown.** memBrain shows the assistant's earlier words only when the question is recognised as asking about them, and it recognises that by a short list of phrasings ("you said", "you suggested", "you recommended"). Of the ten questions of this kind, the list matched two. The others say "the two companies you mentioned", "you told me", "can you remind me of...", "our previous conversation about...". Plain retrieval, which has no such rule, shows the evidence for all ten. This is a rule that works on the phrasings it was written for and fails on ordinary ones.

**3. At equal total size, plain retrieval is far ahead.** Half of memBrain's context is the session opening: the most recent messages. In a history of fifty sessions the answer is rarely among them, so that half adds no evidence here (the whole context finds exactly what the recall block finds), while plain retrieval spends every character on what matches the question. On LoCoMo the two were level because the histories are short.

**4. Recall is slow on a larger history.** About 500 messages, many of them long assistant replies that are stored sentence by sentence, take two seconds a recall. Every user message would wait that long before the host starts to answer. LoCoMo did not show this. Which step takes the time has not been measured yet.

## What it does not show

- **Answers.** Nothing was generated. An answer run on this benchmark is a paid step for the owner to approve.
- **Cues.** None were written, so the mechanism that gained most on LoCoMo was not tested here.
- **Per-type differences.** Ten questions a type; one question is ten points.
- The session opening is not useless in use: it carries recent context a user expects the host to have. This benchmark only asks about the past.

## What follows

Three defects to work on, each to be checked afterwards on LongMemEval questions outside this sample, so that the fix is not fitted to these sixty:

1. Recall time on larger histories.
2. Recognising that a question is about what the assistant said, without a list of phrasings.
3. How the context is divided between recent messages and recalled ones when the history is long.

The decision on a larger recall block ([report](recall-block-size-2026-11-12.md)) should wait for these: the block was not even full on half of these questions, and the evidence that was missing was withheld by a rule, not by size.

Files: [results-2026-11-12](longmemeval/results-2026-11-12/) holds the rows and the table. The dataset is not in the repository.
