# A relevance floor for the automatic recall block: measured, not built

No runtime change (runtime `f69d4cda`, pin `3e888dd4`). Model-free, no cost. **Result: no rule tried saves context without losing evidence, so nothing was built.** The measurement scripts are kept: `locomo/recall_floor.py` (records route, scores and evidence for every line of the block and applies candidate rules) and `locomo/recall_floor_scenario.py` (replays the resume-after-correction worlds under each rule).

## Why it was measured

In the [resume-after-correction scenario](correction-visible-2026-11-18.md), after a busy week the per-prompt recall block cost 3,000 to 7,000 characters, most of it unrelated: the ten best meaning-only messages are always added, with no floor, and with keywords only a common query word matched filler ("set up my dev machine" pulled ten lines that shared only "up").

## Findings

- **On LoCoMo the block always refills to its 9,000-character limit**: a dropped line is replaced by the next candidate. A floor does not shrink the block there; it changes what is in it.
- **Baseline reproduced** by a fresh ingestion at this commit: 74.3% of 1,535 questions with all their evidence in the block (recorded: 74.1%), 72.3% on held-out conversations (recorded: 72.2%).
- **Where the block's characters go** (held out): keyword lines 70%, of which 3.9% are labelled evidence; meaning-only lines 13 to 15%, 0.5% evidence; the message following a hit 16%, 0.9% evidence. LoCoMo's evidence labels are strict: a line that is not evidence is often still on topic.
- **Meaning-only lines have no usable floor.** Evidence is 0.1 to 0.9% in every similarity band, and similarities are squeezed into 0.78 to 0.88. The best similarity does not even tell a prompt with nothing to find (median 0.830 over 120 unrelated coding prompts in English and Chinese) from a real question (0.846 to 0.850).
- **In the scenario the correction itself is a weak meaning-only hit**: sixth of ten at 0.807 with filler above it at 0.834 for "set up my dev machine", tenth of ten for the Chinese wording. Every cap or floor on meaning-only lines drops it.

## Candidate rules, held-out conversations

Mean block today: 8,375 characters. "Nothing to find": the 120 unrelated prompts.

| Rule | Evidence recall | Questions lost / gained | Mean block | Nothing to find |
| --- | --- | --- | --- | --- |
| Today | 72.3% | — | 8,375 | 4,458 |
| No meaning-only lines | 71.3% | 16 / 4 | 7,626 | 1,690; 34% empty |
| At most 3 meaning-only lines | 72.0% | 6 / 3 | 7,921 | 2,731 |
| At most 5 | 72.0% | 4 / 1 | 8,085 | 3,310 |
| Similarity at least 0.82 | 71.6% | 9 / 1 | 7,957 | 2,967; 9% empty |
| Within 0.03 of the best similarity | 72.3% | 1 / 1 | 8,066 | 4,388 |
| Keyword match ignored when every shared term is in at least 25% of the user's messages | 71.5% | 12 / 3 | 7,287 | 4,458 |
| The same at 20% | 71.4% | 14 / 4 | 7,235 | 4,440 |
| Inverse-frequency coverage floor | 71.5% | 12 / 3 | 7,190 | 4,425 |
| 30 lines offered instead of 40 | 71.7% | 9 / 2 | 7,869 | 4,458 |

The deliberate `memory_recall` is unchanged under every rule and returns every question a rule loses.

The only rule that removes the "up" filler in the scenario and keeps the correction is the common-term rule: 13% fewer characters for 0.8 points of held-out recall. The lost questions are almost all ones where a person's name is the only word shared with the evidence ("Joanna's first screenplay"), which is exactly what a memory about one person or one project looks like. Its constant cannot be told apart from anything between 0.2 and 0.5 on LoCoMo and sits next to the scenario's synthetic 28%; a product version would need term counts over the whole memory, whose cost is unmeasured.

## Decision

Nothing is built. The saving is small, the loss is measurable, and the one promising rule would hurt most in the memories the product is for. The scenario's filler was synthetic and written to open with "Next up is", which made a common word look like the problem.

What the measurement leaves open as the real levers: the block's size limit (set by [measurement](memory-path-recall-budget-2026-11-10.md) on 2026-11-10), and a cap on meaning-only lines for prompts with nothing to find (at most 3 would cut those blocks by 39% for 0.3 points), which these scores do not support on their own.

## Not measured

The effect on a host's answers; a Chinese memory with evidence labels; natural word frequencies in a real long history; old memories under the age weight (LoCoMo is stored within minutes); the cue route; Codex's 6,500-character limit.
