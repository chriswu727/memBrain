# Recent first, but less steeply; and why cues are not a sign of importance

Base: pin `c6c313ff` (runtime `bb55fb0`). One runtime commit, `be09a3be`. No migration. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

It continues [the measurement of the age weight](time-depth-recall-2026-11-12.md). The owner's rule is that nothing is forgotten and that recent and important memories come first. "Recent first" exists, as a weight on age in automatic recall. "Important first" did not exist. Two questions were measured, both without a model, on LoCoMo conversations stored with each message at its session's date and asked one day after the last session. Sub-sessions of the lead ran both; the lead set the questions, the rules and the decision.

## Summary

- **Cues do not work as a sign of importance. Nothing was built from them.** The only judgement of importance memBrain has is the host AI's, which attaches a cue to a message that holds a lasting fact. Five ways of sparing cued memories from the age weight were measured; every one made questions about the last 30 days worse, and with all memories equally old every one lost between 1.3 and 7.6 points.
- **The age weight was too steep, and is now gentler.** A new memory outranked a six-month-old one of equal relevance by 3 to 1; it is now about 1.8 to 1 (`AccessPolicy.rank_floor` 0.30 in place of 0.15). On the seven conversations not used for tuning, all the evidence is shown for 76.2% of 1,152 questions, against 72.2% before; questions about the last 30 days lose 2 of 232.
- **"Important first" now has a first form:** a message a note was written from does not sink (added later the same day; see below). It passed its rule on the development conversations and is not yet checked on others.

## Cues as a sign of importance: measured and rejected

On the three development conversations (383 questions), with the cues a model wrote on 2026-11-11 standing in for a host's:

- 37.6% of the user's messages have a cue, the same share at every age. 82.1% of evidence turns have one, so a cue does mark what questions are later asked about, at about twice the base rate.
- But among the candidates recall ranks for a question, 44.5% are cued, and cued and uncued candidates have the same mean age. Sparing cued candidates lifts nearly half the list.

| Asked a day after the last session | All evidence shown | Questions gained / lost against the shipped weight | Of those, about the last 30 days |
| --- | --- | --- | --- |
| Shipped weight | 79.4% | | |
| No weight | 83.8% | 22 / 5 | 0 / 4 |
| Cued memories not weighted at all | 77.0% | 16 / 25 | 0 / 9 |
| Cued memories floored like a pinned one | 81.2% | 15 / 8 | 0 / 2 |
| Cued memories with a higher floor | 80.2% | 7 / 4 | 0 / 1 |
| Cued memories decaying four times slower | 79.9% | 8 / 6 | 0 / 1 |

A year after the last session, where every memory is equally old and the weight itself changes nothing, the same four ways lose 7.6, 4.9, 3.1 and 1.3 points: lifting the cued candidates pushes out evidence that has no cue, while the cued evidence was already reached through the cue route. That is the clean test of the cue as a sign of importance, and it fails.

The cue route itself is worth having, as measured before: with cues attached the shipped weight shows all the evidence for 79.4% of these questions, against 77.5% without them.

## The strength of the weight: chosen by a rule, checked on other conversations

With cues attached the shipped weight cost 4.4 points a day after the last session, and helped questions about the last 30 days (98.6% against 93.2% with no weight). The owner's design fixes the direction, recent first, not the ratio.

**The rule, fixed before the results were read:** a setting qualifies if, against the shipped weight, questions about the last 30 days lose at most one, and it gains at least eight questions overall; among those that qualify, take the one that favours recent memories most.

Development conversations, 383 questions (the ratio is the weight of a one-day-old memory over a 180-day-old one):

| Setting | Ratio | All evidence shown | Gained / lost against shipped | About the last 30 days |
| --- | --- | --- | --- | --- |
| Floor 0.15 (shipped) | 3.00 | 79.4% | | |
| Floor 0.30 | 1.83 | 81.5% | 9 / 1 | 0 / 1 |
| Floor 0.45 | 1.44 | 82.5% | 13 / 1 | 0 / 1 |
| Floor 0.60 | 1.24 | 83.3% | 18 / 3 | 0 / 3 |
| Floor 0.75 | 1.12 | 83.8% | 20 / 3 | 0 / 3 |
| Half-life × 2 | 2.52 | 80.4% | 5 / 1 | 0 / 1 |
| Half-life × 4 | 1.83 | 82.2% | 12 / 1 | 0 / 1 |
| No weight | 1.00 | 83.8% | 22 / 5 | 0 / 4 |

Floor 0.30, floor 0.45 and half-life × 4 qualify. The rule takes floor 0.30, which meets the threshold of eight exactly; it ties with half-life × 4 on the ratio at 180 days and favours recent memories more over the first months.

**The seven conversations not used for tuning** were then stored with their dates (4,431 turns, every one read back at its session's date) and given the cues a stand-in host wrote through the product's own consolidation batches (34.5% of messages, 78.4% of evidence turns). 1,152 questions:

| | Shipped (0.15) | Floor 0.30 | Floor 0.45 | Half-life × 4 | No weight |
| --- | --- | --- | --- | --- | --- |
| All evidence shown | 72.2% | **76.2%** | 76.9% | 74.7% | 77.9% |
| Oldest evidence under 30 days (232) | 90.1% | 89.2% | 88.8% | 88.4% | 86.2% |
| 30 to 90 days (249) | 86.3% | 87.6% | 87.6% | 88.4% | 87.1% |
| 90 to 180 days (309) | 67.0% | 73.1% | 74.1% | 72.8% | 75.7% |
| Over 180 days (362) | 55.5% | 62.7% | 64.4% | 58.3% | 68.0% |
| Gained / lost against shipped | | 51 / 5 | 60 / 6 | 37 / 8 | 80 / 15 |
| Of those, about the last 30 days | | 0 / 2 | 0 / 3 | 0 / 4 | 0 / 9 |

Floor 0.30 gains in each of the ten conversations. It recovers about 70% of what removing the weight would, at under a quarter of the loss on recent questions.

**Changed:** `rank_floor` 0.30 (and the floor for distinctive events, which must not be lower, 0.40). Nothing else: the half-life, the tiers and the search made on purpose, which ignores the weight, are as they were.

## Important first: a message a note was written from does not sink

Added on 2026-11-13, after the owner asked for another way to make "important first" real. Runtime commit `fc99653b`.

**The sign of importance.** When the host AI saves a note it cites the message the fact came from. That is the only judgement of importance that is both deliberate and rare: notes written turn by turn cite one message each, and their sources were 11% of the user's messages and 35% of evidence turns, three times the base rate, where cues covered 45% of candidates.

**Two forms failed before one passed**, on the three development conversations with the notes a stand-in host wrote on 2026-11-11 and their real cited sources:

| Form | A day after the last session | A year after, all memories equally old |
| --- | --- | --- |
| The source message weighted as if recorded today | 9 questions gained, 4 lost | 6 lost net |
| The source message given the highest weight among that request's candidates | 9 gained, 4 lost; none about the last 30 days | identical for all 383 questions |

With every memory equally old the age weight changes nothing and the order is by relevance alone; a fixed high weight for noted messages is then a boost beyond relevance and pushes out better matches. So importance is made to cancel sinking and nothing more: a noted message ranks as if it were as recent as the most recent memory it competes with, never higher. This form has no number to tune.

**The rule, fixed before each round:** against the shipped weight, at most one question about the last 30 days lost a day after the last session and at most one lost net a year after; and at least four gained net, or noted evidence older than 90 days shown at least five points more often without other evidence falling by more than one. Result with the built code, which reproduces the measurement question for question: all evidence shown for 82.8% of 383 questions against 81.5%; noted evidence older than 90 days shown 92.2% of the time against 81.7%; evidence without a note older than 90 days 70.4% against 69.8%.

**Only notes citing at most two messages count.** Notes written once per session cited 3.7 messages on average, made a quarter of all messages "important" and failed the rule (two recent questions lost; other old evidence down 5.3 points).

**What this does not show.**

- It was not checked on other conversations: the seven not used for tuning have no notes. Writing them needs a paid stand-in host.
- The gain is small, five questions net on 383, just over the threshold and within the noise of one run. Its cost falls on evidence 30 to 90 days old that has no note: 4 of 73 such turns were no longer shown.
- LoCoMo's questions are not specially about what a host would note; two thirds of evidence turns have no note behind them.
- The notes are a stand-in's. A real host notes what it judges lasting, and cites the current message.
- A replacement note keeps the messages the old note cited; a note corrected twice may come to cite three and stop anchoring.

Evidence: [results](locomo/results-2026-11-13-age-weight/anchors/) (the three rounds' reports, per-question rows, the notes' real sources, the run with the built code).

## What the weight's strength does not show

- **The benefit of putting recent memories first.** LoCoMo asks about old and new sessions alike, so it measures what the preference costs and not what it gives a user who mostly talks about recent things. The floor was chosen to give up little of it, not shown to be the best trade.
- A history a year long with newer memories on top was not built.
- The cues are a model's, written from one prompt, not a live host's. One run each; differences of one to three questions are noise.
- The development threshold was met only just. The held-out result is the stronger evidence.
- The full suite ran on this change together with the two removals of the same batch: 8,377 passed, none failed ([record](no-second-model-2026-11-13.md)).

Evidence and scripts: [results](locomo/results-2026-11-13-age-weight/) (the three reports, per-question rows for every arm, the date check of the held-out brains).
