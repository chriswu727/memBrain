# Plan: do cues change LoCoMo answers?

Written before the run. Paid DeepSeek calls, approved by the owner on 2026-11-11 with a ceiling of **25 CNY**. Runtime `6a136d6` (pin `7f27eb6d`). It closes no release gate.

## Question

[Cues attached to messages](message-cues-2026-11-11.md) put all the evidence in the recall block for 78.5% of held-out questions instead of 72.2%. That measures retrieval. Does a host answer more questions correctly?

## Design

- **Arm `cues`** of [consolidation_experiment.py](locomo/consolidation_experiment.py): the seven held-out conversations stored afresh as the plugin path stores them, the cues of the [simulation](locomo-controls-and-cues-2026-11-11.md) attached (no model call), every question asked in a new session; answers by `deepseek-flash` with thinking off, judged by the same model with Mem0's judge prompt. 1,155 questions.
- **Compared with** today's answers on messages alone for the same questions (`answers-plain`, runtime `933f4d8`; the commits since do not change recall without cues). That arm is not repeated: it would cost as much again, and the same-day full-context control moved by less than two points in twelve days.
- **Reported**: accuracy on all held-out questions and by category and number of evidence turns; paired gained and lost with an exact binomial test; context size; cost.
- The development conversations are not run: the cue weights were chosen on them.

## Reading the result beforehand

- Messages alone already answer 80.7% of these questions, level with the whole conversation in the prompt (81.2%). The room above that is what the answer model gets wrong with the evidence in front of it, so a small difference, or none, would not be surprising.
- A clear loss (more questions lost than gained, p < 0.05) would mean the extra messages distract, and the weights would be revisited before anything else is built on cues.
- Otherwise cues stay as built: the evidence measure is the one they were designed against, and the next work is the host AI writing them.

## Cost

About 18.5 CNY expected at ledger prices (the same questions cost 18.4 CNY without cues), in a new run directory with its own ledger and a 25 CNY ceiling. A request that could exceed the ceiling is refused before it is sent.
