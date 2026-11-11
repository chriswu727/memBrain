# Questions that need several memories: what recall cannot reach

Runtime `02a1aec`. A model-free analysis on the three LoCoMo development conversations, following the [message-context embedding batch](message-context-embeddings-2026-11-10.md), which left questions with several evidence turns at about a third for both memBrain and plain retrieval. No source change. It closes nothing: **R4 remains failed and C5 invalid/unscored.**

## A second pass seeded by the first does not help

The first idea was spreading activation: let the memories found for a question act as cues for further ones. Simulated at message level with BM25 and whole-message embeddings ([association_feedback.py](locomo/results-2026-11-11/association_feedback.py), 291 questions with one evidence turn and 92 with several, first 40 messages):

| Ranking | One evidence turn: found | Several: all found | Several: share found |
| --- | --- | --- | --- |
| First pass | 86.9% | 35.9% | 59.7% |
| Plus the query moved toward the mean of the top 3 hits (best of six settings) | 84.2% | 37.0% | 59.7% |
| Plus each of the top 3 hits as its own cue (best of four) | 83.8% | 31.5% | 52.7% |
| Plus the distinctive words of the top 10 hits added to the query (best of three) | 84.9% | 33.7% | 57.1% |

Every variant loses single-evidence questions, and none gains more than one question among the 92. The hits that would have to act as cues are close to the question, not to the other evidence. **This direction is closed; nothing was implemented.**

## What the missed evidence looks like

For the same 92 questions the 228 evidence turns rank, in the first pass ([missed_evidence.py](locomo/results-2026-11-11/missed_evidence.py)): 132 within the first 40 messages, 19 at 40 to 79, 26 at 80 to 159, 27 at 160 to 319 and 24 beyond. The evidence sits in two or more sessions for 77 of them.

The turns that rank low do not resemble the question. Three examples from the first conversation, with the rank of each evidence turn:

- *"What activities does Melanie partake in?"* (pottery, camping, painting, swimming): the pottery class ranks 1; "we went camping with my fam" 107; "I'm off to go swimming with the kids" 85; the fourth evidence turn 157. None of the three quoted says "activities".
- *"What is Caroline's relationship status?"* (single): "It'll be tough as a single parent" ranks 322.
- *"Where did Caroline move from 4 years ago?"* (Sweden): "a gift from my grandma in my home country, Sweden" ranks 95; the turn that says "4 years" ranks 0.

Each of these asks for something the conversation never states in one place: a list of what a person does, a status implied by a remark, a fact that follows from two others. A larger block would have to hold several hundred messages to contain them, and a better ranking of single messages cannot bring a turn about swimming to the top for a question about activities.

## What follows

This is the job of consolidation, not of recall: turning episodes into knowledge about a person, with its sources, before the question is asked. In the default plugin path that knowledge exists only as notes the host model chooses to save, or as notes written by the optional extraction model; the 2026-11-01 answer run measured 78.4% with extraction against 76.4% without. Three things are not known and cannot be measured without a model:

- how much of the multi-evidence gap notes close when they are written for every conversation;
- what that costs per turn, for a host model or for an extraction model;
- whether a consolidation pass over a finished conversation (one call per session instead of one per turn) does as well.

Measuring them needs paid model calls and therefore the owner's approval. The evidence-recall harness cannot score derived notes, since a note is not one of the dataset's evidence turns; an answer-level run or a check of answer terms in the context is required.

## Limits

Three conversations, message-level simulation with a plain index, one small embedding model. A stronger embedding model might move some of the 40-to-159 turns into the block; that was not tried.
