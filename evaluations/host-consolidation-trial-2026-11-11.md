# Host consolidation tried: a real host follows it, and cues written batch by batch keep three quarters of the gain

Two checks of [host consolidation](host-consolidation-2026-11-11.md), both approved by the owner on 2026-11-11: a trial on a real host with its subscription, on a model other than the largest, and the paid replay [planned beforehand](host-consolidation-replay-plan-2026-11-11.md) with a 3 CNY ceiling. Runtime `139c15f` for both; the changes they led to are runtime `d9c1a70` (pin `837b4bb2`). It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Trial on Claude Code

Claude Code 2.1.322, headless, model `claude-sonnet-5-5`, on WSL2. A copy of the plugin whose hooks and tool server run this repository's code directly instead of installing the pinned archive; a memory directory and ports of its own; nothing of the user's own configuration or memory was read or written by memBrain. Every message is synthetic. Thirteen turns in four conversations. [Turn-by-turn summaries](evidence/host-consolidation-trial-2026-11-11/) with identifiers removed.

**First version (runtime `139c15f`), seven turns in three conversations:**

- **The host AI did what the sentence asked every time it applied**: three times, in three conversations. It found the tool by name (Claude Code loads plugin tools on demand), called it without arguments, and called it again with cues and the right batch number. Nothing was refused.
- **It answered first in two of the three**, and consolidated before answering once.
- **The cues named categories.** "My sister Ana just moved to Porto for a job at a design studio" got "user's sister Ana relocation", "Ana's job and workplace", "user family members"; "I'm vegetarian" got "user dietary restrictions", "user food preferences"; a unit conversion and a request for weekend ideas got none. One cue restated a detail ("user pottery class schedule").
- **It reported on the indexing at length**: "I finished the memory indexing in the background. The two earlier messages it covered were a request for weekend ideas and a question about your family. Neither stated a new lasting fact, so nothing new was saved."
- **A session after a short one consolidated two questions and saved nothing.**
- **Cost on the host**: three more model calls per consolidation (finding the tool, the batch, the cues), each re-reading about 29,000 cached context tokens and adding a few hundred; about 0.02 USD at list prices by the host's own accounting, against about 0.008 USD for a plain short turn in the same conversation.

**Changes made (runtime `d9c1a70`):**

- The host AI is asked only once **five** messages await indexing.
- The sentence, the instructions and the tool's result all say not to describe the indexing beyond a few words.
- The second call no longer has to repeat the batch number; the tool remembers the batch it handed out (see the replay below).

**Revised version, six turns in one conversation:** no sentence until five messages had gathered; then one consolidation of five messages, cues for four and none for the unit conversion, no batch number passed, and the reply to the user was only the answer to their message ("Night shifts noted, so mornings are your sleep time.").

**What the trial does not show:** other hosts (Codex, WorkBuddy, CodeBuddy), smaller models, long conversations where the session opening is far back in the context, an interactive session in which the user watches the tool calls, or anything about answers. Thirteen turns on one model show that the path works, not how often it does.

## Replay: cues written through the product's batch format

`deepseek-flash` stood in for a host AI and was given exactly what `memory_consolidate` returned, through the real tool and service, until nothing was left ([script](locomo/host_consolidation_replay.py)): 299 batches, 5,882 messages offered, 2,264 given cues (3,589 phrases). No batch was refused by the tool; one reply was unreadable; **33 replies (11%) returned a different batch number from the one given**, which is why the tool now remembers it. Then the model-free evidence-recall harness, recall block, share of questions with all their evidence:

| | Questions | No cues | Cues from batches of 20 (this replay) | Cues from whole sessions (earlier) |
| --- | --- | --- | --- | --- |
| **Held-out conversations** | 1,152 | 72.2% | **76.9%** | 78.5% |
| Held out, one evidence turn | 831 | 86.6% | 90.7% | 91.2% |
| Held out, several evidence turns | 321 | 34.9% | 41.1% | 45.5% |
| Development conversations | 383 | 79.9% | 83.3% | 82.5% |
| All ten conversations | 1,535 | 74.1% | 78.5% | 79.5% |

- **Against no cues, held out: 72 questions gained all their evidence and 18 lost it** (exact two-sided binomial p < 10⁻⁷).
- **Against cues written from whole sessions, held out: 14 gained and 32 lost** (p = 0.011). The batch format keeps about three quarters of the gain (4.7 of 6.3 points) and loses most on questions that need several memories.
- Not isolated: whether the difference comes from batches that cut a session into pieces, from the changed instructions and examples, or from run-to-run variation of the model.

The answer check (80.7% to 83.2%) used the cues from whole sessions and was not repeated with these.

## Verification of the changes

The full local source suite on the pin commit `837b4bb2`, with the local embedding model: 8,532 passed, 4 skipped (the Docker journeys), none failed, in 58 minutes; source and migrations unchanged during the run. The [end-to-end test](../tests/test_memory_consolidation.py) now covers the threshold, the second call without a batch number and a call before any batch was handed out. GitHub Verify, native Windows and macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.

## Cost

Replay: **1.44 CNY** of the 3 CNY ceiling at ledger prices (299 `deepseek-flash` calls, 0.51 million input tokens). The trial used the owner's Claude subscription: thirteen headless turns on Sonnet, about 0.47 USD at list prices by the host's own accounting, reading its cost figure as cumulative within a conversation, which is how it behaves.

Files: [results-2026-11-11](locomo/results-2026-11-11/) holds `recall-cues-host-replay-139c15f.jsonl.gz` and its summary, `host-replay-batches.json` and `host-replay-ledger.json`.
