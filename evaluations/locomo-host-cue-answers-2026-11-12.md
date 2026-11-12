# Cues written through the product's batches keep the answer gain: 82.7% of held-out LoCoMo questions, against 80.7% without cues

Result of the [plan of 2026-11-12](locomo-host-cue-answers-plan-2026-11-12.md), run as written. Runtime `75f50fd`. DeepSeek paid calls approved by the owner with a 20 CNY ceiling. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Result

Seven held-out conversations, 1,155 questions, every question in a new session; answers by `deepseek-flash` with thinking off, judged by the same model with Mem0's judge prompt. The cues were written by a model standing in for a host AI, given the product's consolidation batches through the real tool ([replay](host-consolidation-trial-2026-11-11.md)); attaching them here made no model call. The other two columns are the runs of 2026-11-11 on the same questions, not repeated.

| | Questions | Messages alone | Cues from the product's batches | Cues from whole sessions |
| --- | --- | --- | --- | --- |
| **All held-out questions** | 1,155 | 80.7% | **82.7%** | 83.2% |
| Several evidence turns | 321 | 67.6% | 71.7% | 72.9% |
| One evidence turn | 831 | 85.7% | 86.9% | 87.1% |
| Multi-hop | 208 | 67.3% | 72.6% | 75.0% |
| Temporal | 231 | 79.7% | 83.5% | 84.0% |
| Open-domain | 75 | 58.7% | 57.3% | 57.3% |
| Single-hop | 641 | 88.0% | 88.6% | 88.6% |

- **Against messages alone: 61 questions gained, 38 lost** (exact two-sided binomial p = 0.027). On questions with several evidence turns: 28 gained, 15 lost (p = 0.07).
- **Against cues from whole sessions: 36 gained, 42 lost** (p = 0.57). The two ways of writing cues are not distinguishable in answers.
- Six of the seven conversations are ahead of messages alone and one is level; none is significant on its own.
- The context is 18,206 characters on average, and the host searched with the recall tool on 208 questions.

## What this does and does not show

- The gain in answers does not depend on cues written from one prompt per finished session: it holds when the product's own tool hands the messages out in batches and its own instructions are followed.
- **The writer was still a stand-in model, not a host.** Real hosts were tried separately for whether they do the work at all ([trial](host-consolidation-trial-2026-11-11.md)): Claude Code on Sonnet and on Haiku did. Cues written by a real host over a long history have not been scored.
- One run per arm, one benchmark, one answer model and a judge of the same family.

## Cost

**18.33 CNY** of the 20 CNY ceiling at ledger prices (2,518 `deepseek-flash` calls, 9.0 million input tokens). No request ended without usage accounting; none was refused.

Files are in [results-2026-11-11](locomo/results-2026-11-11/): `answers-host-batch-cues-heldout.jsonl.gz`, `host-batch-cues-heldout.tar.gz` (the cues) and `host-cue-answers-ledger.json`.
