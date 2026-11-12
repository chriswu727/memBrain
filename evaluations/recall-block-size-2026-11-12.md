# What limits recall now is the size of the recall block; following shared cues does not help

Model-free experiments on runtime `75f50fd`, 2026-11-12, with the service inside the measuring process so that settings could change between requests. The stored LoCoMo brains carry the cues a stand-in model wrote through the product's consolidation batches. **No model was called, and nothing in the product changed**: this records what was tried and what it implies. It closes no release gate: R4 remains failed and C5 invalid/unscored.

## Where recall still fails

On the held-out conversations, with cues, 183 of the 321 questions that need several evidence turns still lack some of their evidence in the recall block; 101 of them lack exactly one turn. Of the 351 missing evidence turns, 251 have a cue, and 77 share a cue phrase word for word with an evidence turn of the same question that was found. The block is full: 8,935 of its 9,000 characters on average.

## Following shared cues: no gain

Tried: a message that shares a cue phrase with a message recall has already found gets a share of that message's score ([patch](evidence/recall-block-2026-11-12/cue-siblings.patch), not merged). Development conversations, 383 questions, recall block, share of questions with all their evidence:

| | All | One evidence turn | Several |
| --- | --- | --- | --- |
| As it is | 84.1% | 94.2% | 52.2% |
| Shared cues at a quarter of the found message's score | 84.1% | 94.2% | 52.2% |
| At half | 83.8% | 93.8% | 52.2% |
| At half, following phrases carried by up to 30 messages | 83.3% | 93.1% | 52.2% |
| At the full score | 82.8% | 93.5% | 48.9% |

Nothing is gained at any weight and the block is the same size: what the shared cues bring in displaces as much evidence as it adds. The code was withdrawn.

## Fitting more into 9,000 characters: no gain

| Held-out conversations, 1,152 questions | All | One evidence turn | Several |
| --- | --- | --- | --- |
| As it is | 77.7% | 90.9% | 43.6% |
| Without the message that follows a recalled one | 77.5% | 89.7% | 46.1% |
| Long messages cut to 400 characters | 76.2% | 89.2% | 42.7% |
| Both | 76.0% | 88.1% | 44.9% |

Dropping the following messages trades single-evidence questions for several-evidence ones (18 gained, 20 lost). The development conversations show the same.

## A larger block: a clear gain

| Recall block | Held out, all | One evidence turn | Several | Several, mean share | Mean characters | Development, all |
| --- | --- | --- | --- | --- | --- | --- |
| 9,000 characters (as it is) | 77.7% | 90.9% | 43.6% | 70.1% | 8,927 | 84.1% |
| 12,000 | 80.3% | 91.7% | 50.8% | 73.8% | 11,931 | 86.4% |
| 15,000 | 82.1% | 92.7% | 54.8% | 76.9% | 14,617 | 88.8% |
| 18,000 | **83.8%** | 93.3% | 59.2% | 79.9% | 17,801 | 89.6% |

- Held out, paired against 9,000 characters: 35 gained and 5 lost at 12,000; 56 and 5 at 15,000; 75 and 5 at 18,000 (each p < 10⁻⁵).
- Median time of the recall call in one process: 140 ms at 9,000 characters, 180 ms at 12,000 and 15,000, 236 ms at 18,000.
- The ranking already puts the evidence in order; the block stops before reaching it.

## Why the block is 9,000 characters, and what follows

Claude Code keeps at most 10,000 characters of one hook's output, and Codex has a like limit; the block is set just under it. A larger block cannot be had by changing a number. It needs another way in: a second hook output for the same message, or a second batch the host AI fetches with the recall tool when the first is not enough.

Not known:

- **Whether more evidence in the context means more correct answers.** The whole conversation in the prompt scored no better than 18,000 characters of memBrain context did, so more text is not better by itself. This needs an answer run.
- Whether a host keeps two hook outputs for one message in full.
- What the extra 2,000 to 2,500 tokens a message and the extra time are worth to a user. That is the owner's call.

Files: [evidence/recall-block-2026-11-12](evidence/recall-block-2026-11-12/) holds the two sweep scripts, their tables and rows, and the withdrawn patch.
