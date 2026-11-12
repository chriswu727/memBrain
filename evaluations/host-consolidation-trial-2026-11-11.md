# Host consolidation tried: a real host follows it, and cues written batch by batch keep about four fifths of the gain

Two checks of [host consolidation](host-consolidation-2026-11-11.md), both approved by the owner on 2026-11-11: a trial on a real host with its subscription, on a model other than the largest, and the paid replay [planned beforehand](host-consolidation-replay-plan-2026-11-11.md) with a 3 CNY ceiling. Runtime `139c15f` for both; the changes they led to are runtimes `d9c1a70` (pin `837b4bb2`) and `75f50fd` (pin `59c6bc63`). It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

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

### Batches that end where a conversation ends (2026-11-12, runtime `75f50fd`)

To test whether cutting sessions into pieces caused the difference, a batch now ends at the end of a conversation when at least ten messages remain in it, and may hold up to 40 messages (8,000 characters). Replayed twice on the held-out conversations only, 150 batches and 4,431 messages each time.

| Held out, recall block | Questions | No cues | Batches of 20 | Batches ending with a conversation, first run | Second run | Whole sessions |
| --- | --- | --- | --- | --- | --- | --- |
| All | 1,152 | 72.2% | 76.9% | 77.6% | **77.3%** | 78.5% |
| One evidence turn | 831 | 86.6% | 90.7% | 91.1% | 90.6% | 91.2% |
| Several evidence turns | 321 | 34.9% | 41.1% | 42.7% | 43.0% | 45.5% |

- **The two runs of the same setup differ by 0.3 points** (20 questions gained, 23 lost between them). That is the size of the stand-in model's run-to-run variation, and the differences between ways of batching are not larger than it.
- Second run against batches of 20: 28 gained, 23 lost (p = 0.58). Against whole sessions: 20 gained, 33 lost (p = 0.10). Against no cues: 82 gained, 23 lost (p < 10⁻⁸).
- **So: cues written through the product's batches keep about four fifths of the gain, and how the batches are cut makes no measurable difference here.** The change is kept because it hands the host AI fewer and more coherent batches (150 against 222 on these conversations), not because it scored higher.
- The first run was thought to be held back by the replay's own limit of 1,500 output tokens, since 11 of 150 replies were unusable. The owner approved a second run with the limit at 4,000: 6 of 150 were still unusable and the score did not rise. Truncation was not the cause; what makes those replies unusable was not examined. A real host answers through a typed tool call and not through free-form JSON, so this may not carry over.
- An error of mine on the way: the first attempt removed the earlier cues from the held-out brains and then offered nothing, because review progress only moves forward and the harness had no way to restart it. It cost nothing; the harness now restarts the review of its own synthetic brains.

## Verification of the changes

The full local source suite on the pin commit `837b4bb2`, with the local embedding model: 8,532 passed, 4 skipped (the Docker journeys), none failed, in 58 minutes; source and migrations unchanged during the run. After the batching change, on pin commit `59c6bc63` (runtime `75f50fd`): 8,533 passed, 4 skipped, none failed, in 56 minutes. The [end-to-end test](../tests/test_memory_consolidation.py) now covers the threshold, the second call without a batch number and a call before any batch was handed out. GitHub Verify, native Windows and macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.

## Cost

Replays: **3.58 CNY** at ledger prices, of 4.5 CNY approved (3 CNY, then 1.5 CNY more for the second run on the held-out conversations): 1.44 CNY for the first replay (299 `deepseek-flash` calls), 1.09 CNY and 1.05 CNY for the two runs with the new batches (151 and 150 calls). The trial used the owner's Claude subscription: thirteen headless turns on Sonnet, about 0.47 USD at list prices by the host's own accounting, reading its cost figure as cumulative within a conversation, which is how it behaves.

Files: [results-2026-11-11](locomo/results-2026-11-11/) holds `recall-cues-host-replay-139c15f.jsonl.gz` and its summary, `host-replay-batches.json` and `host-replay-ledger.json`. The runs with the new batches are `recall-cues-host-replay-conversations-58d046b.jsonl.gz` and `-75f50fd.jsonl.gz`, with `host-replay-conversations-batches.json`, `-rerun-batches.json` and the two ledgers.
