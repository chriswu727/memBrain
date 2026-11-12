# Plan: do cues written through the product's batches keep the answer gain?

Written before the run. Paid DeepSeek calls, approved by the owner on 2026-11-12; ceiling **20 CNY**. Runtime `75f50fd` (pin `59c6bc63`). It closes no release gate.

## Question

With cues written from whole sessions, held-out LoCoMo answers rose from 80.7% to 83.2% ([report](locomo-cue-answers-2026-11-11.md)). Cues written through the product's consolidation batches keep about four fifths of the evidence gain ([report](host-consolidation-trial-2026-11-11.md)). Do they keep the answer gain?

## Design

- The cues the stand-in model wrote in the second replay of 2026-11-12 (batches ending with a conversation; 1,527 cued messages on the seven held-out conversations) are read from those stored brains ([export_replay_cues.py](locomo/results-2026-11-11/export_replay_cues.py)) and attached, without a model call, to freshly stored copies of the same conversations: arm `cues` of [consolidation_experiment.py](locomo/consolidation_experiment.py).
- The same 1,155 questions, answer model, judge and procedure as the earlier check. Compared, paired, with messages alone (80.7%) and with whole-session cues (83.2%), both from 2026-11-11 and not repeated.
- Reported as before: all questions, by category and by number of evidence turns, gained and lost with an exact binomial test, cost.

## Reading the result beforehand

- Two runs of one setup differ by a few tenths of a point in evidence recall, and answers add the answer model's and the judge's own variation, so a difference of a point from the whole-session result would not mean much.
- The question that matters is against messages alone: if these cues give no gain there, host consolidation in its present form is not yet worth what it costs the host, and the instructions and batch format are the next thing to work on.
- This still uses a stand-in model for the host AI. It is not a measurement of any real host.

## Cost

About 18.3 CNY expected at ledger prices, in its own run directory with a 20 CNY ceiling.
