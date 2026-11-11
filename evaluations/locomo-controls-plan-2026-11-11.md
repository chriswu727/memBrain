# Plan: two controls for the 88.1% on messages alone, and a cue-enrichment simulation (paid, approved 2026-11-11)

Status: **run on 2026-11-11; [result](locomo-controls-and-cues-2026-11-11.md).** The cue simulation was also run on the held-out conversations, which this plan did not list, because its instructions had been written from the development conversations. The text below is the plan as written before any call. Follows the [consolidation result](locomo-consolidation-2026-11-11.md). The owner approved these runs on 2026-11-11 with DeepSeek. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Why

Messages alone scored 88.1% on the three development conversations, above the full-context score of 81.8% from 2026-10-29 on the same conversations. That comparison is across runs twelve days apart and on conversations used for tuning. Two controls make it a measurement:

1. **Held-out conversations, messages alone.** The seven conversations never used for tuning (1,155 questions), `plain` arm of [consolidation_experiment.py](locomo/consolidation_experiment.py), unchanged. With the development split this gives a complete LoCoMo score for the current runtime, comparable in method with the 2026-10-29 and 2026-11-01 runs (plugin path 76.4%, with extraction 78.4%, Mem0 81.3%, full context 81.4%).
2. **Full context, same day, development conversations.** The whole dated conversation in the prompt, as the `F` arm of [run_locomo.py](locomo/run_locomo.py), same answer model, judge and settings, through the same ledger. It shows whether the answer model or judge has moved since 2026-10-29.

## Cue enrichment, simulated

The notes result and the owner's remark that notes are not how memory works point at a different kind of consolidation: attach cues to the original memories so that recall finds them, and keep showing the original message. Before anything is built, a simulation on the development conversations:

- one `deepseek-flash` call per session returns, for each turn, a few short cue phrases: the kind of fact the turn holds and whom it is about (for example "hobby", "relationship status", "home country"), without restating the turn;
- the plain index of [the association simulation](locomo-multi-evidence-2026-11-11.md) (BM25 and whole-message embeddings) is rebuilt with each turn's cues added to its indexed text;
- the measure is the same as there: questions with all their evidence in the first 40 messages, for one and for several evidence turns.

It is a simulation with a plain index, not the product. If it does not raise multi-evidence questions clearly above the first pass (35.9% all found, 59.7% share), the idea stops there.

## Spending control

Same ledger and rules as the [consolidation plan](locomo-consolidation-plan-2026-11-11.md#spending-control), same run directory, so spending is cumulative: 38.07 CNY spent, ceiling raised to **85 CNY**. Expected at ledger prices: held-out answers about 18 CNY, full-context control about 20 CNY, cue generation about 2 CNY. A full-context request is large, so its worst case before sending is about 0.2 CNY; the run stops when that no longer fits.

## How the results will be read

- The held-out score is the number that counts for "messages alone"; the development score was reached on conversations used for tuning.
- If full context on the development conversations is again near 81.8%, the answer model and judge have not moved and the 88.1% stands against it. If it is clearly different, earlier and current scores are not comparable and only same-day arms are.
- Nothing here is behavioural acceptance, and one benchmark of this kind does not show how the product behaves with a real host.
